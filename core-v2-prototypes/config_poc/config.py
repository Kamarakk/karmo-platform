"""KARMO Core configuration single-sourcing -- ISOLATED PROOF OF CONCEPT.

Not imported by any existing KARMO module. Proves the single-source
design from docs/architecture/KARMO_CONFIGURATION_SINGLE_SOURCING_DESIGN.md
without changing any current runtime behavior: every existing module
keeps its own independent constant exactly as it is today.

Five categories, matching the design doc:
- STATIC CODE CONSTANT: not this module's concern (stays inline in code).
- ENVIRONMENT CONFIGURATION: env-var override + documented default.
- SECRET REFERENCE: a name/location only -- get_secret_ref() returns the
  ENV VAR NAME to read, never a value. This module never reads or prints
  the actual secret.
- RUNTIME DISCOVERY: read from the running system, not assumed.
- DOMAIN CONFIGURATION: identifies a logical resource, env-overridable
  per key, distinct from environment configuration.
"""

import os


class ConfigurationError(ValueError):
    """Raised when a required piece of configuration is genuinely
    missing and has no safe default -- refuse, don't guess, matching
    every other KARMO tool's refusal pattern."""


# --- Environment configuration ---------------------------------------

_DEFAULTS = {
    "KARMO_QDRANT_URL": "http://127.0.0.1:6333",
    "KARMO_PG_HOST": "127.0.0.1",
    "KARMO_PG_PORT": "5433",
    "KARMO_PG_DB": "karmo",
    "KARMO_PG_USER": "karmo",
}


def qdrant_url():
    return os.environ.get("KARMO_QDRANT_URL", _DEFAULTS["KARMO_QDRANT_URL"])


def postgres_connection_params():
    """Returns the non-secret connection parameters as a dict. The
    caller is responsible for combining this with a secret reference
    (see get_secret_ref) -- this function never touches the password."""
    return {
        "host": os.environ.get("KARMO_PG_HOST", _DEFAULTS["KARMO_PG_HOST"]),
        "port": os.environ.get("KARMO_PG_PORT", _DEFAULTS["KARMO_PG_PORT"]),
        "dbname": os.environ.get("KARMO_PG_DB", _DEFAULTS["KARMO_PG_DB"]),
        "user": os.environ.get("KARMO_PG_USER", _DEFAULTS["KARMO_PG_USER"]),
    }


# --- Secret reference ---------------------------------------------------

def get_secret_ref(name):
    """Returns the environment variable NAME that holds a secret --
    never the value. Mirrors the Mandatory Production Access
    Authorization Gate's secret-handling rule and every existing KARMO
    module's own pattern (KARMO_DB_PASSWORD, POSTGRES_PASSWORD)."""
    known = {
        "postgres_password": "KARMO_DB_PASSWORD",
    }
    if name not in known:
        raise ConfigurationError(f"no known secret reference named {name!r}")
    return known[name]


def resolve_secret(name):
    """Reads the secret VALUE from the environment, using the reference
    from get_secret_ref -- the only function in this module that touches
    an actual secret value, and it never logs, prints, or returns it
    wrapped in anything that could be accidentally serialized/printed
    (callers must use it immediately, not store it)."""
    env_var = get_secret_ref(name)
    value = os.environ.get(env_var)
    if not value:
        raise ConfigurationError(f"{env_var} is not set")
    return value


# --- Domain configuration -----------------------------------------------

_COLLECTION_NAMES = {
    "documents": "karmo_documents",
    "semantic_memory": "karmo_semantic_memory",
    "h00_dense_baseline": "karmo_h00_dense_baseline",
}


def collection_name(domain_key):
    """Domain-configured, env-overridable per key -- so an isolated test
    suite can override just ``documents`` (e.g. to
    ``karmo_h04_test_documents``) without touching the environment
    configuration (host/port) at all, and without redeclaring the
    production name anywhere else."""
    if domain_key not in _COLLECTION_NAMES:
        raise ConfigurationError(f"no known collection domain key: {domain_key!r}")
    override_env = f"KARMO_COLLECTION_{domain_key.upper()}"
    return os.environ.get(override_env, _COLLECTION_NAMES[domain_key])


_EMBEDDING_MODEL = {"name": "embeddinggemma", "vector_size": 768}


def embedding_model():
    """Model name and vector size are returned TOGETHER, deliberately --
    never separately, so a future model change cannot accidentally update
    one without the other (exactly the I-06 gap Workstream 4's F4 finding
    flagged: karmo_semantic_memory carries no model/version provenance
    today)."""
    return dict(_EMBEDDING_MODEL)


# --- Runtime discovery ----------------------------------------------------

def discover_dependency_version(module):
    """Read a dependency's actual version from the imported module,
    never hardcode it -- the pattern document_ingest.py/
    document_ingest_h04.py already use correctly for Docling, generalized
    here so every future Core v2 dependency uses the same one function
    instead of each module reimplementing the same getattr/except
    shape."""
    return getattr(module, "__version__", "unknown")
