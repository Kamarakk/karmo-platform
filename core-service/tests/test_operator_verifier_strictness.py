from core_service.operator import KarmoOperator


class AmbiguousVerifierClient:
    def __init__(self, verifier_reply):
        self.verifier_reply = verifier_reply

    def chat(self, *, model, messages, temperature=0.2):
        if model == "llama3.2:3b":
            return self.verifier_reply
        return "hostname karmo-test mode READ_ONLY"


def _status(_args=None):
    return {
        "host": {"hostname": "karmo-test"},
        "services": {},
        "containers": {"containers": []},
        "mode": "READ_ONLY",
    }


def test_verifier_accepts_only_exact_pass_token():
    operator = KarmoOperator(
        model_client=AmbiguousVerifierClient("PASS but I am not certain"),
        status_reader=_status,
    )

    response = operator.handle("show KarmoLab status")

    assert response["verification"] == "FAIL"
    assert response["message"] == "KarmoLab READ completed; showing verified raw evidence."
    assert response["evidence"]["mode"] == "READ_ONLY"


def test_verifier_exact_pass_still_releases_summary():
    operator = KarmoOperator(
        model_client=AmbiguousVerifierClient("  pass  "),
        status_reader=_status,
    )

    response = operator.handle("show KarmoLab status")

    assert response["verification"] == "PASS"
    assert response["message"] == "hostname karmo-test mode READ_ONLY"
