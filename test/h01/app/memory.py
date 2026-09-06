"""Test-only connection adapter for the isolated H0.1 failure-matrix stack.

This is NOT part of the frozen H0.1 design (transactional_memory.py and
outbox.py import ``memory.get_connection`` from the production karmo app,
which is not present in this repository). It exists solely to point the
verbatim frozen modules at the local, synthetic, Docker-based test database
defined in test/h01/docker-compose.yml. It performs no production access.

Connection parameters come only from environment variables (with isolated
test-stack defaults) so no credentials are hardcoded here.
"""

import os
from contextlib import contextmanager

import psycopg

_DEFAULTS = {
    "KARMO_H01_TEST_PG_HOST": "127.0.0.1",
    "KARMO_H01_TEST_PG_PORT": "55432",
    "KARMO_H01_TEST_PG_DB": "karmo_h01_test",
    "KARMO_H01_TEST_PG_USER": "karmo_h01_test",
    "KARMO_H01_TEST_PG_PASSWORD": "karmo_h01_test_synthetic_local_only",
}


def _conninfo():
    values = {key: os.environ.get(key, default) for key, default in _DEFAULTS.items()}
    return (
        f"host={values['KARMO_H01_TEST_PG_HOST']} "
        f"port={values['KARMO_H01_TEST_PG_PORT']} "
        f"dbname={values['KARMO_H01_TEST_PG_DB']} "
        f"user={values['KARMO_H01_TEST_PG_USER']} "
        f"password={values['KARMO_H01_TEST_PG_PASSWORD']}"
    )


@contextmanager
def get_connection():
    """Yield a connection to the isolated test PostgreSQL instance.

    Commits on clean exit, rolls back (and re-raises) on exception — matching
    the atomicity the frozen ``remember_exchange`` docstring relies on.
    """
    conn = psycopg.connect(_conninfo())
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()
