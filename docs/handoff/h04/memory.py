import os
import psycopg

def get_connection():
    password = os.environ.get("KARMO_DB_PASSWORD")

    if not password:
        raise RuntimeError("KARMO_DB_PASSWORD is not set")

    return psycopg.connect(
        host="127.0.0.1",
        port=5433,
        dbname="karmo",
        user="karmo",
        password=password,
    )


def initialize_memory():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS karmo_memory (
                    id BIGSERIAL PRIMARY KEY,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id BIGSERIAL PRIMARY KEY,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)


def remember(key, value):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO karmo_memory (memory_key, memory_value) VALUES (%s, %s)",
                (key, value),
            )


def recall(key):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT memory_value
                FROM karmo_memory
                WHERE memory_key = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (key,))
            result = cur.fetchone()
            return result[0] if result else None


def remember_turn(role, content):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_memory (role, content) VALUES (%s, %s)",
                (role, content),
            )


def recent_turns(limit=6):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, content
                FROM conversation_memory
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))

            rows = cur.fetchall()
            rows.reverse()
            return rows
