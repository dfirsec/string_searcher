"""Search configuration: dataclass + pure validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import EmptySearchTermError
from .errors import InvalidDateError
from .errors import InvalidExtensionError

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable

DATE_FORMAT = "%Y-%m-%d"
DEFAULT_EXTENSIONS = ".bat,.cfg,.csv,.css,.html,.ini,.js,.log,.md,.ps1,.py,.sh,.txt,.xml,.yaml,.yml"
_REGEX_METACHARS = re.compile(r"[.*+?^$%{}()|[\]\\]")


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Validated, immutable search parameters."""

    directory: Path
    pattern: re.Pattern[str]
    use_regex: bool
    extensions: frozenset[str]
    maxdepth: int
    maxline: int
    start_date: datetime | None
    end_date: datetime | None
    size_limit_bytes: int | None


def parse_date(date_str: str | None) -> datetime | None:
    """Parse a strict YYYY-MM-DD date string; reject unpadded variants like 2024-1-5."""
    if date_str is None:
        return None
    try:
        parsed = datetime.strptime(date_str, DATE_FORMAT).astimezone()
    except ValueError as exc:
        msg = f"Invalid date '{date_str}'. Use format YYYY-MM-DD."
        raise InvalidDateError(msg) from exc
    if parsed.strftime(DATE_FORMAT) != date_str:
        msg = f"Date must be zero-padded YYYY-MM-DD, got '{date_str}'."
        raise InvalidDateError(msg)
    return parsed


def normalize_extensions(raw: str) -> frozenset[str]:
    """Split a comma-separated extension list and prefix bare names with '.'."""
    return frozenset(
        ext if ext.startswith(".") else f".{ext}" for ext in (e.strip().lower() for e in raw.split(",")) if ext
    )


def build_pattern(term: str, *, case_sensitive: bool) -> tuple[re.Pattern[str], bool]:
    """Compile `term` as regex (if it contains metacharacters) or as a word-bounded literal."""
    if not term:
        msg = (
            "Search term is empty. If your term includes special characters like $, "
            "enclose it in single quotes (e.g., '$search')."
        )
        raise EmptySearchTermError(msg)
    flags = 0 if case_sensitive else re.IGNORECASE
    if _REGEX_METACHARS.search(term):
        return re.compile(term, flags=flags), True
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=flags), False


def build_config(
    *,
    directory: str,
    search_term: str,
    maxdepth: int,
    extensions: str,
    maxline: int,
    case_sensitive: bool,
    start_date: str | None,
    end_date: str | None,
    size_limit_kb: float | None,
    acceptable_extensions: Iterable[str],
    suggester: Callable[[str, Iterable[str]], list[str]],
) -> SearchConfig:
    """Build a validated SearchConfig or raise a SearchError subclass."""
    pattern, use_regex = build_pattern(search_term, case_sensitive=case_sensitive)
    ext_set = normalize_extensions(extensions)
    acceptable = frozenset(acceptable_extensions)
    if not ext_set & acceptable:
        raise InvalidExtensionError(ext_set, suggester(str(ext_set), acceptable))
    return SearchConfig(
        directory=Path(directory),
        pattern=pattern,
        use_regex=use_regex,
        extensions=ext_set,
        maxdepth=maxdepth,
        maxline=maxline,
        start_date=parse_date(start_date),
        end_date=parse_date(end_date),
        # Preserves original semantics: 0 / None / negative-ish → no limit.
        size_limit_bytes=int(size_limit_kb * 1024) if size_limit_kb else None,
    )
