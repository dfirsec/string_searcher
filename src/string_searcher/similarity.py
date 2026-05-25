"""Suggest near-matching extensions from the allow-list."""

from collections.abc import Iterable
from difflib import SequenceMatcher


def _score(a: str, b: str) -> float:
    """Ratio of longest leading matching block to the longer string."""
    return SequenceMatcher(None, a, b).get_matching_blocks()[0].size / max(len(a), len(b))


def suggest_extensions(
    requested: str,
    candidates: Iterable[str],
    *,
    limit: int = 3,
    threshold: float = 0.25,
) -> list[str]:
    """Return up to `limit` candidates whose similarity to `requested` exceeds `threshold`."""
    scored = [(_score(requested, c), c) for c in candidates]
    scored.sort(reverse=True)
    return [name for score, name in scored[:limit] if score > threshold]
