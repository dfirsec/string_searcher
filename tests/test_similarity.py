from string_searcher.similarity import suggest_extensions


def test_returns_close_matches() -> None:
    candidates = {".py", ".pyx", ".pyi", ".js", ".md"}
    result = suggest_extensions(".py", candidates, limit=3)
    assert ".py" in result
    assert len(result) <= 3


def test_threshold_filters_unrelated() -> None:
    result = suggest_extensions(".py", {".zzzzzz"}, threshold=0.9)
    assert result == []


def test_limit_respected() -> None:
    result = suggest_extensions(".py", {".py", ".pyx", ".pyi", ".pyc"}, limit=2)
    assert len(result) == 2
