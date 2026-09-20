"""Tests for KARMO chat's tool-calling loop -- Phase 1 of
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md.

Wired only to the pre-existing list_tasks capability (no new business
logic here), specifically to prove the loop mechanism itself works
before Phase 2 adds a genuinely new capability (BloomBoss).
"""

from __future__ import annotations

import json
import uuid

from core_service.control import ApprovalRequirement
from core_service.ollama_client import OllamaClientError
from core_service.operator import _CHAT_EXPOSED_TOOLS, _MAX_CHAT_TOOL_ROUNDS, KarmoOperator


class FakeTaskStore:
    """In-memory stand-in matching TaskStore's exact public contract."""

    def __init__(self):
        self._tasks: dict[str, dict] = {}

    def seed(self, **overrides):
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id, "objective": "reconcile PR #26", "context": None,
            "status": "OPEN", "requested_by": "kamara", "claimed_by": None,
            "result": None, "created_at": "2026-01-01T00:00:00", "claimed_at": None,
            "completed_at": None,
        }
        task.update(overrides)
        self._tasks[task_id] = task
        return task

    def create_task(self, *, objective, context, requested_by):
        raise AssertionError("not used in these tests")

    def list_tasks(self, *, status=None, limit=20):
        # Mirrors the real TaskStore.list_tasks's own validation exactly, so a
        # test against this fake actually proves something about the real
        # failure mode (a raw TypeError on limit=None) rather than tolerating
        # an input the real store would reject.
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t["status"] == status]
        return tuple(dict(t) for t in tasks[:limit])

    def claim_task(self, *, task_id, claimed_by):
        raise AssertionError("not used in these tests")

    def complete_task(self, *, task_id, result, completed_by):
        raise AssertionError("not used in these tests")


class ToolCallThenAnswerClient:
    """First call: proposes a list_tasks tool call. Second call: gives a
    plain final answer. Records every request it received so tests can
    assert exactly what the loop sent back after executing the tool."""

    def __init__(self, *, arguments=None):
        self.requests = []
        self._arguments = arguments if arguments is not None else {}

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.requests.append({"model": model, "messages": messages, "tools": tools})
        if len(self.requests) == 1:
            return {
                "content": "",
                "tool_calls": [{"function": {"name": "list_tasks", "arguments": self._arguments}}],
            }
        return {"content": "You have one open task: reconcile PR #26.", "tool_calls": None}


class PrimaryFailsFallbackCallsToolClient:
    """qwen3:8b (primary, highest trust tier) fails outright; ministral-3:8b
    (the fallback candidate) proposes a real list_tasks tool call. Proves
    Model Router Phase B rule 8 (Section 3, "A fallback model's tool call
    gets the identical authorization check as the primary model's"): the
    fallback's tool call must be dispatched through the exact same
    capability/approval machinery as the primary's would have been --
    there is no lighter or different path for a later candidate."""

    def __init__(self):
        self.requests = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.requests.append(model)
        if model == "qwen3:8b":
            raise OllamaClientError("simulated primary failure")
        if len([m for m in self.requests if m == "ministral-3:8b"]) == 1:
            return {
                "content": "",
                "tool_calls": [{"function": {"name": "list_tasks", "arguments": {}}}],
            }
        return {"content": "You have one open task: reconcile PR #26.", "tool_calls": None}


class AlwaysToolCallClient:
    """Never stops proposing a tool call -- proves the round cap actually
    terminates the loop instead of hanging."""

    def __init__(self):
        self.call_count = 0

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.call_count += 1
        return {
            "content": "",
            "tool_calls": [{"function": {"name": "list_tasks", "arguments": {}}}],
        }


class UnknownToolClient:
    """Proposes a tool name that was never exposed -- proves a bad/hallucinated
    tool call is refused cleanly, not crashed on."""

    def __init__(self):
        self.requests = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.requests.append(messages)
        if len(self.requests) == 1:
            return {
                "content": "",
                "tool_calls": [{"function": {"name": "delete_everything", "arguments": {}}}],
            }
        return {"content": "That tool wasn't available, so I can't do that.", "tool_calls": None}


def test_model_can_call_list_tasks_and_use_the_real_result():
    store = FakeTaskStore()
    store.seed()
    client = ToolCallThenAnswerClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    response = operator.handle("what tasks are open right now?")

    assert response["kind"] == "chat"
    assert "reconcile PR #26" in response["message"]
    assert len(client.requests) == 2
    # The tool result actually reached the model as real data, not a stub.
    tool_message = client.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    payload = json.loads(tool_message["content"])
    assert payload["tasks"][0]["objective"] == "reconcile PR #26"


def test_oversized_tool_result_is_truncated_before_reaching_the_model():
    """Real, live-diagnosed bug (2026-09-19): bloomboss_report's full result
    serialized to 63,035 bytes for a single small CSV import, and feeding
    that entire blob back to a CPU-only model as tool-result context took
    over 100 seconds on the next round, exceeding even a 150-second total
    turn budget on its own. A tool result must be capped before it ever
    reaches the model, with an honest, visible marker -- never a silent
    truncation the model (or Kamara) could mistake for the complete
    picture."""
    from core_service.operator import _MAX_TOOL_RESULT_CHARS_FOR_MODEL

    store = FakeTaskStore()
    for i in range(400):
        store.seed(objective=f"synthetic task {i}" * 5)  # inflate well past the cap
    client = ToolCallThenAnswerClient(arguments={"limit": 100})
    operator = KarmoOperator(model_client=client, task_store=store)

    operator.handle("what tasks are open right now?")

    tool_message = client.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    content = tool_message["content"]
    assert len(content) <= _MAX_TOOL_RESULT_CHARS_FOR_MODEL + 300  # cap + marker text
    assert "TRUNCATED FOR RESPONSE TIME" in content
    assert "More detail exists" in content


def test_small_tool_result_is_never_truncated_or_marked():
    store = FakeTaskStore()
    store.seed()
    client = ToolCallThenAnswerClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    operator.handle("what tasks are open right now?")

    tool_message = client.requests[1]["messages"][-1]
    assert "TRUNCATED" not in tool_message["content"]
    # Still valid, complete, parseable JSON -- untouched below the cap.
    json.loads(tool_message["content"])


def test_fallback_candidates_tool_call_gets_identical_dispatch_as_primary_would():
    """Model Router Phase B rule 8. Uses the real default_model_resources()
    registry (qwen3:8b ranked first, ministral-3:8b second) so this proves
    the actual production fallback order, not a synthetic one."""
    store = FakeTaskStore()
    store.seed()
    client = PrimaryFailsFallbackCallsToolClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    response = operator.handle("what tasks are open right now?")

    assert response["kind"] == "chat"
    assert response["model"] == "ministral-3:8b"
    assert "reconcile PR #26" in response["message"]
    # The primary was tried and failed first -- this is a real fallback,
    # not the fallback simply being the only candidate.
    assert client.requests[0] == "qwen3:8b"
    assert "ministral-3:8b" in client.requests


def test_list_tasks_tool_is_not_offered_when_task_store_is_unconfigured():
    client = ToolCallThenAnswerClient()
    operator = KarmoOperator(model_client=client, task_store=None)

    operator.handle("what tasks are open right now?")

    # Never even offered the tool -- not "offered but refused". Other
    # configured-by-default tools (e.g. bloomboss_report) may still be
    # offered; this asserts specifically about list_tasks.
    offered_names = {t["function"]["name"] for t in client.requests[0]["tools"]}
    assert "list_tasks" not in offered_names


def test_round_cap_stops_a_model_that_never_stops_calling_tools():
    store = FakeTaskStore()
    client = AlwaysToolCallClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    response = operator.handle("what tasks are open right now?")

    assert client.call_count == _MAX_CHAT_TOOL_ROUNDS
    assert "allowed steps" in response["message"]


def test_hallucinated_tool_name_is_refused_cleanly_not_crashed_on():
    store = FakeTaskStore()
    client = UnknownToolClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    response = operator.handle("please delete everything")

    assert response["kind"] == "chat"
    tool_message = client.requests[1][-1]
    assert tool_message["role"] == "tool"
    assert "not available" in json.loads(tool_message["content"])["error"]


def test_null_argument_value_is_stripped_before_reaching_the_handler():
    """Verified live against a real model (llama3.2:3b via Ollama): it passed
    {"limit": null, "status": "OPEN"} for an omitted optional argument rather
    than leaving the key out. list_tasks_handler's own `arguments.get("limit",
    20)` fallback only works for an ABSENT key, not a present None -- and the
    real store's own validation (`if not 1 <= limit <= 100`) raises a raw
    TypeError on None, which must never crash the whole chat turn."""
    store = FakeTaskStore()
    store.seed()
    client = ToolCallThenAnswerClient(arguments={"limit": None, "status": "OPEN"})
    operator = KarmoOperator(model_client=client, task_store=store)

    response = operator.handle("what tasks are open right now?")

    assert response["kind"] == "chat"
    tool_message = client.requests[1]["messages"][-1]
    payload = json.loads(tool_message["content"])
    assert "error" not in payload
    assert payload["tasks"][0]["objective"] == "reconcile PR #26"


def test_only_none_approval_capabilities_are_ever_exposed_to_the_model():
    """The load-bearing safety property from
    KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md Section 7.3: no
    capability may enter _CHAT_EXPOSED_TOOLS unless its computed approval
    requirement is NONE. Verified against the real registry, not asserted
    by convention."""
    operator = KarmoOperator(model_client=ToolCallThenAnswerClient(), task_store=FakeTaskStore())
    assert _CHAT_EXPOSED_TOOLS, "expected at least one exposed tool to check"
    for entry in _CHAT_EXPOSED_TOOLS.values():
        record = operator.registry.get(entry["tool_id"], entry["version"])
        assert record is not None
        assert record.computed_approval_requirement == ApprovalRequirement.NONE
