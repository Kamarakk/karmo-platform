"""A trivial, synthetic test file for the pytest capability handler to
run -- has nothing to do with worker-runtime's own test suite."""


def test_synthetic_addition():
    assert 1 + 1 == 2


def test_synthetic_string():
    assert "karmo"[:5] == "karmo"
