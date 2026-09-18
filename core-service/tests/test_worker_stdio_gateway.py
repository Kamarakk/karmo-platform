import io
import json

from core_service.worker_stdio_gateway import (
    MAX_FRAME_BYTES,
    GatewayRequest,
    WorkerStdioGatewayError,
    dispatch_request,
    serve_one,
)


class Backend:
    def __init__(self):
        self.calls = []

    def heartbeat(self, **kwargs):
        self.calls.append(("heartbeat", kwargs))
        return {"heartbeat": "accepted"}

    def poll(self, **kwargs):
        self.calls.append(("poll", kwargs))
        return None

    def authorize_execution(self, **kwargs):
        self.calls.append(("authorize_execution", kwargs))
        return {"authorized": True}

    def submit_result(self, **kwargs):
        self.calls.append(("submit_result", kwargs))
        return {"accepted": True}


def _frame(operation, payload, request_id="req-1"):
    return (json.dumps({
        "version": 1,
        "request_id": request_id,
        "operation": operation,
        "payload": payload,
    }) + "\n").encode()


def test_gateway_binds_ssh_key_identity_before_backend_dispatch():
    backend = Backend()
    request = GatewayRequest(
        request_id="req-1",
        operation="heartbeat",
        payload={
            "worker_id": "karmo-worker02",
            "credential_token": "credential",
            "lease_seconds": 90,
        },
    )
    try:
        dispatch_request(request, backend=backend, expected_worker_id="karmo-worker01")
    except WorkerStdioGatewayError as exc:
        assert str(exc) == "worker_identity_mismatch"
    else:
        raise AssertionError("identity mismatch was accepted")
    assert backend.calls == []


def test_gateway_allows_only_fixed_operations():
    stdout = io.BytesIO()
    code = serve_one(
        backend=Backend(),
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("shell", {"worker_id": "karmo-worker01"})),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 2
    assert response["ok"] is False
    assert response["error"] == "operation_not_allowed"


def test_gateway_rejects_extra_payload_fields():
    stdout = io.BytesIO()
    code = serve_one(
        backend=Backend(),
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
            "command": "id",
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 2
    assert response["error"] == "invalid_payload_schema"


def test_gateway_heartbeat_dispatches_bound_identity():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 0
    assert response["ok"] is True
    assert backend.calls == [("heartbeat", {
        "worker_id": "karmo-worker01",
        "credential_token": "credential",
        "lease_seconds": 90,
        "ollama_snapshot": None,
    })]


def test_gateway_heartbeat_accepts_valid_ollama_snapshot():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
            "ollama_snapshot": {"loaded_models": ["qwen3:8b", "granite3.3:2b"]},
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 0
    assert response["ok"] is True
    assert backend.calls == [("heartbeat", {
        "worker_id": "karmo-worker01",
        "credential_token": "credential",
        "lease_seconds": 90,
        "ollama_snapshot": {"loaded_models": ["qwen3:8b", "granite3.3:2b"]},
    })]


def test_gateway_heartbeat_rejects_malformed_ollama_snapshot():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
            "ollama_snapshot": {"loaded_models": "not-a-list"},
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 2
    assert response["error"] == "invalid_ollama_snapshot"
    assert backend.calls == []


def test_gateway_heartbeat_rejects_oversized_ollama_snapshot():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
            "ollama_snapshot": {"loaded_models": [f"model-{i}" for i in range(100)]},
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 2
    assert response["error"] == "invalid_ollama_snapshot"
    assert backend.calls == []


def test_gateway_heartbeat_rejects_unknown_ollama_snapshot_shape():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
            "ollama_snapshot": {"loaded_models": ["qwen3:8b"], "extra_field": "x"},
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 2
    assert response["error"] == "invalid_ollama_snapshot"
    assert backend.calls == []


def test_gateway_poll_validates_capability_shape():
    stdout = io.BytesIO()
    code = serve_one(
        backend=Backend(),
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("poll", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "capabilities": ["ok", 7],
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 2
    assert response["error"] == "invalid_capabilities"


def test_gateway_requires_core_authorization_before_execution():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("authorize_execution", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease": {"job_id": "job", "lease_token": "lease"},
            "execution_ticket": "ticket",
        })),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 0
    assert response["result"] == {"authorized": True}
    assert backend.calls[0][0] == "authorize_execution"


def test_gateway_rejects_empty_credential_before_backend_dispatch():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "",
            "lease_seconds": 90,
        })),
        stdout=stdout,
    )
    assert code == 2
    assert backend.calls == []
    assert json.loads(stdout.getvalue())["error"] == "invalid_credential_token"


def test_gateway_never_discloses_backend_exception_details():
    class FailingBackend(Backend):
        def heartbeat(self, **kwargs):
            raise RuntimeError("DATABASE_PASSWORD=do-not-leak")

    stdout = io.BytesIO()
    code = serve_one(
        backend=FailingBackend(),
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("heartbeat", {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
        })),
        stdout=stdout,
    )
    rendered = stdout.getvalue().decode()
    assert code == 3
    assert "DATABASE_PASSWORD" not in rendered
    assert json.loads(rendered)["error"] == "coordinator_refused"


def test_gateway_rejects_oversized_input_without_backend_call():
    backend = Backend()
    stdout = io.BytesIO()
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(b"x" * (MAX_FRAME_BYTES + 1)),
        stdout=stdout,
    )
    assert code == 2
    assert backend.calls == []
    assert json.loads(stdout.getvalue())["error"] == "invalid_frame"


def test_submit_result_keeps_ticket_envelope_and_terminal_state_structured():
    backend = Backend()
    stdout = io.BytesIO()
    payload = {
        "worker_id": "karmo-worker01",
        "credential_token": "credential",
        "lease": {"job_id": "job", "lease_token": "lease"},
        "execution_ticket": "ticket",
        "result": {"status": "healthy"},
        "envelope": {"payload": {"key_id": "worker-key-v1"}, "signature": "sig"},
        "success": True,
        "error": None,
    }
    code = serve_one(
        backend=backend,
        expected_worker_id="karmo-worker01",
        stdin=io.BytesIO(_frame("submit_result", payload)),
        stdout=stdout,
    )
    assert code == 0
    assert backend.calls[0][0] == "submit_result"
    assert backend.calls[0][1]["execution_ticket"] == "ticket"
    assert backend.calls[0][1]["success"] is True
