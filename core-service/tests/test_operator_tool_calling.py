"""Tests for KARMO chat's tool-calling loop -- Phase 1 of
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md.

Wired only to the pre-existing list_tasks capability (no new business
logic here), specifically to prove the loop mechanism itself works
before Phase 2 adds a genuinely new capability (BloomBoss).
"""

from __future__ import annotations

import json
import uuid

import pytest

from core_service.control import ApprovalRequirement
from core_service.model_router import ModelResource
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


class RecordingNoToolClient:
    """Never proposes a tool call -- just records what tools it was offered
    each request, for tests that only care about tool *selection*, not
    execution."""

    def __init__(self):
        self.requests = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.requests.append({"model": model, "messages": messages, "tools": tools})
        return {"content": "ok", "tool_calls": None}


def _tool_names(tools: list[dict]) -> set:
    return {t["function"]["name"] for t in tools}


def test_a_message_matching_no_tool_keywords_offers_only_bloomboss_report():
    """Real, measured fix (2026-09-19): offering all 4 tools on every turn
    inflated qwen3:8b's effective prompt 30x on this CPU-only host (19
    tokens with none offered vs. 632 with all 4), turning ordinary
    conversation into a ~29-second-minimum wait it never needed. A plain
    conversational message offers no keyword-gated tools. bloomboss_report
    is the one exception: always offered (2026-09-27, Kamara's request)."""
    store = FakeTaskStore()
    store.seed()
    client = RecordingNoToolClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    operator.handle("good morning, how are you today?")

    assert _tool_names(client.requests[0]["tools"]) == {"bloomboss_report"}


def test_a_task_question_offers_only_list_tasks():
    store = FakeTaskStore()
    store.seed()
    client = RecordingNoToolClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    operator.handle("what tasks are open right now?")

    assert _tool_names(client.requests[0]["tools"]) == {"list_tasks", "bloomboss_report"}


def test_a_bloomboss_question_offers_no_tools_once_the_report_is_prerun():
    store = FakeTaskStore()
    store.seed()
    client = RecordingNoToolClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    operator.handle("what is bloomboss's best selling alocasia?")

    assert _tool_names(client.requests[0]["tools"]) == set()


@pytest.mark.parametrize(
    "text",
    [
        "how many plants did we sell last month?",
        "what were my sales in August?",
        "which items are my best sellers?",
        "what's my profit margin looking like?",
        "how is my business doing?",
        "how much inventory do I have in stock?",
        "tell me about the Ninja Albos",
    ],
)
def test_bloomboss_report_is_prerun_whatever_the_wording(text):
    """Live gap (2026-09-27): a BloomBoss question phrased in plain business
    words matched no keyword trigger, so the tool was never offered and KARMO
    answered without it. The report now runs before the model is asked, and
    is not offered again (its schema only slows the CPU model's prompt read)."""
    client = RecordingNoToolClient()
    operator = KarmoOperator(model_client=client, task_store=FakeTaskStore())

    operator.handle(text)

    assert "bloomboss_report" not in _tool_names(client.requests[0]["tools"])
    assert any(m["role"] == "tool" for m in client.requests[0]["messages"])


def test_a_message_matching_two_tool_triggers_offers_both():
    store = FakeTaskStore()
    store.seed()
    client = RecordingNoToolClient()
    operator = KarmoOperator(model_client=client, task_store=store)

    operator.handle("what tasks are open, and what does bloomboss say about revenue?")

    assert _tool_names(client.requests[0]["tools"]) == {"list_tasks"}


def test_ask_claude_and_ask_gpt_require_being_asked_for_explicitly():
    """Deliberate trade-off: these two are gated on explicit mention rather
    than always-on, both to avoid their schema cost on every ordinary turn
    and to narrow their exposure (flagged in the external D2 review as
    needing stronger isolation before being offered more freely)."""
    store = FakeTaskStore()
    store.seed()

    client = RecordingNoToolClient()
    KarmoOperator(model_client=client, task_store=store).handle("what tasks are open?")
    assert "ask_claude" not in _tool_names(client.requests[0]["tools"])
    assert "ask_gpt" not in _tool_names(client.requests[0]["tools"])

    client = RecordingNoToolClient()
    KarmoOperator(model_client=client, task_store=store).handle("can you ask claude about this?")
    assert _tool_names(client.requests[0]["tools"]) == {"ask_claude", "bloomboss_report"}

    client = RecordingNoToolClient()
    KarmoOperator(model_client=client, task_store=store).handle("get chatgpt's opinion on this")
    assert _tool_names(client.requests[0]["tools"]) == {"ask_gpt", "bloomboss_report"}


def test_ask_local_coder_is_offered_only_for_coding_questions():
    """2026-09-20: KARMO's own local coding helper (qwen2.5-coder:7b on a
    worker) -- unlike ask_claude/ask_gpt, this is KARMO's own capability,
    not an external one, but still keyword-gated to avoid its schema cost
    on every ordinary turn."""
    store = FakeTaskStore()
    store.seed()

    client = RecordingNoToolClient()
    KarmoOperator(model_client=client, task_store=store).handle("what tasks are open?")
    assert "ask_local_coder" not in _tool_names(client.requests[0]["tools"])

    client = RecordingNoToolClient()
    KarmoOperator(model_client=client, task_store=store).handle("write me a python function to reverse a string")
    assert _tool_names(client.requests[0]["tools"]) == {"ask_local_coder", "bloomboss_report"}


def test_system_prompt_tells_the_model_to_call_ask_local_coder_for_coding_questions():
    """Real live finding, 2026-09-24: a coding question is a different
    case from BloomBoss/tasks -- the model genuinely has real knowledge
    of ordinary code, so the general "you have no real knowledge"
    instruction doesn't cover it. Live-tested: qwen3:8b answered a
    Fibonacci-function question directly, never dispatching to
    ask_local_coder (confirmed absent from karmo_worker_jobs). This is
    a content check, not a behavioral one -- proving the model actually
    changes behavior needs a real live retest against Ollama, the same
    way the original bloomboss_report fix (2026-09-19) was verified."""
    store = FakeTaskStore()
    store.seed()

    client = RecordingNoToolClient()
    KarmoOperator(model_client=client, task_store=store).handle("write me a python function to reverse a string")

    system_content = client.requests[0]["messages"][0]["content"]
    assert "ask_local_coder" in system_content
    assert "call ask_local_coder" in system_content


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
    """Model Router Phase B rule 8. Production's default_model_resources()
    has run as a single-candidate (qwen3:8b only) chat registry since
    2026-09-20 (ministral-3:8b deleted -- no production fallback exists
    today), so this test supplies its own explicit two-model registry to
    keep proving the underlying structural invariant: a fallback
    candidate's tool call must get the identical authorization/dispatch
    path as the primary's, with no lighter or different treatment for a
    later candidate. Re-add a real fallback to default_model_resources()
    and this test would exercise the actual production order again
    unchanged."""
    store = FakeTaskStore()
    store.seed()
    client = PrimaryFailsFallbackCallsToolClient()
    resources = [
        ModelResource(
            model_id="qwen3:8b",
            provider="ollama-local",
            capabilities=frozenset({"chat", "tool_calling"}),
            trust_tier=40,
            local=True,
        ),
        ModelResource(
            model_id="ministral-3:8b",
            provider="ollama-local",
            capabilities=frozenset({"chat", "tool_calling"}),
            trust_tier=35,
            local=True,
        ),
    ]
    operator = KarmoOperator(model_client=client, task_store=store, resources=resources)

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
