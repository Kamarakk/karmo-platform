from core_service.delegation_cache import DelegationCache


def test_miss_then_hit_returns_the_stored_answer():
    cache = DelegationCache()
    assert cache.get("tool-a", "what is bloomboss?") is None
    cache.set("tool-a", "what is bloomboss?", "a plant marketplace")
    assert cache.get("tool-a", "what is bloomboss?") == "a plant marketplace"


def test_normalization_is_case_and_whitespace_insensitive():
    cache = DelegationCache()
    cache.set("tool-a", "  What Is   BloomBoss?  ", "a plant marketplace")
    assert cache.get("tool-a", "what is bloomboss?") == "a plant marketplace"
    assert cache.get("tool-a", "WHAT IS BLOOMBOSS?") == "a plant marketplace"


def test_different_question_is_a_miss():
    cache = DelegationCache()
    cache.set("tool-a", "what is bloomboss?", "a plant marketplace")
    assert cache.get("tool-a", "what is karmo?") is None


def test_same_question_different_tool_id_does_not_collide():
    """ask_claude and ask_gpt share one process-wide cache instance in
    production -- must never answer one tool's question with the other
    tool's cached response, even for identical question text."""
    cache = DelegationCache()
    cache.set("ask_claude", "same question", "claude's answer")
    cache.set("ask_gpt", "same question", "gpt's answer")
    assert cache.get("ask_claude", "same question") == "claude's answer"
    assert cache.get("ask_gpt", "same question") == "gpt's answer"


def test_entry_expires_after_its_ttl():
    fake_now = [1000.0]
    cache = DelegationCache(ttl_seconds=60.0, time_fn=lambda: fake_now[0])

    cache.set("tool-a", "question", "answer")
    assert cache.get("tool-a", "question") == "answer"

    fake_now[0] = 1000.0 + 59.9
    assert cache.get("tool-a", "question") == "answer"

    fake_now[0] = 1000.0 + 60.0
    assert cache.get("tool-a", "question") is None


def test_max_entries_evicts_the_soonest_to_expire_entry():
    fake_now = [0.0]
    cache = DelegationCache(ttl_seconds=100.0, max_entries=2, time_fn=lambda: fake_now[0])

    cache.set("tool-a", "first", "answer-1")
    fake_now[0] = 1.0
    cache.set("tool-a", "second", "answer-2")
    fake_now[0] = 2.0
    cache.set("tool-a", "third", "answer-3")

    assert len(cache) == 2
    assert cache.get("tool-a", "first") is None
    assert cache.get("tool-a", "second") == "answer-2"
    assert cache.get("tool-a", "third") == "answer-3"


def test_clear_empties_the_cache():
    cache = DelegationCache()
    cache.set("tool-a", "question", "answer")
    cache.clear()
    assert cache.get("tool-a", "question") is None
    assert len(cache) == 0
