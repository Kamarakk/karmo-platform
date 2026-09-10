"""Proves single-sourcing, per the Core v2 Test Strategy's own acceptance
gate: importing the same value from two different call sites must yield
the SAME object/value from the SAME source -- not merely two literals
that happen to currently agree."""

import config


def _call_site_one():
    return config.qdrant_url()


def _call_site_two():
    return config.qdrant_url()


def test_two_call_sites_get_identical_value_from_one_source(monkeypatch):
    monkeypatch.setenv("KARMO_QDRANT_URL", "http://synthetic-test-host:9999")

    assert _call_site_one() == _call_site_two() == "http://synthetic-test-host:9999"


def test_default_used_when_env_not_set(monkeypatch):
    monkeypatch.delenv("KARMO_QDRANT_URL", raising=False)

    assert config.qdrant_url() == "http://127.0.0.1:6333"


def test_postgres_connection_params_never_include_a_password_key():
    params = config.postgres_connection_params()

    assert "password" not in params
    assert set(params) == {"host", "port", "dbname", "user"}


def test_secret_reference_returns_env_var_name_not_a_value():
    ref = config.get_secret_ref("postgres_password")

    assert ref == "KARMO_DB_PASSWORD"
    assert "=" not in ref  # a name, never a value-shaped string


def test_resolve_secret_reads_from_environment_and_never_hardcodes(monkeypatch):
    monkeypatch.setenv("KARMO_DB_PASSWORD", "synthetic-test-only-value")

    assert config.resolve_secret("postgres_password") == "synthetic-test-only-value"


def test_resolve_secret_refuses_when_unset(monkeypatch):
    monkeypatch.delenv("KARMO_DB_PASSWORD", raising=False)

    with _raises_configuration_error():
        config.resolve_secret("postgres_password")


def _raises_configuration_error():
    import pytest

    return pytest.raises(config.ConfigurationError)


def test_collection_name_domain_override_is_independent_of_environment_config(monkeypatch):
    """An isolated test suite overriding just the 'documents' collection
    name must not need to touch, or be affected by, Qdrant host/port
    environment configuration at all -- domain config and environment
    config are genuinely independent axes."""
    monkeypatch.setenv("KARMO_COLLECTION_DOCUMENTS", "karmo_h04_test_documents")
    monkeypatch.delenv("KARMO_QDRANT_URL", raising=False)

    assert config.collection_name("documents") == "karmo_h04_test_documents"
    assert config.qdrant_url() == "http://127.0.0.1:6333"  # unaffected


def test_collection_name_default_matches_production_name():
    assert config.collection_name("documents") == "karmo_documents"
    assert config.collection_name("semantic_memory") == "karmo_semantic_memory"


def test_unknown_collection_key_refuses_rather_than_guessing():
    with _raises_configuration_error():
        config.collection_name("not_a_real_domain")


def test_embedding_model_name_and_vector_size_always_returned_together():
    """Never separately -- exactly the I-06 gap this design closes."""
    model = config.embedding_model()

    assert set(model) == {"name", "vector_size"}
    assert model["name"] == "embeddinggemma"
    assert model["vector_size"] == 768


def test_runtime_discovery_reads_actual_version_not_a_hardcoded_guess():
    class FakeModule:
        __version__ = "9.9.9-synthetic"

    assert config.discover_dependency_version(FakeModule) == "9.9.9-synthetic"


def test_runtime_discovery_falls_back_when_version_attribute_absent():
    class FakeModuleWithoutVersion:
        pass

    assert config.discover_dependency_version(FakeModuleWithoutVersion) == "unknown"
