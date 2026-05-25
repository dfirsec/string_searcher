from __future__ import annotations

import re

import pytest
from string_searcher.config import build_config
from string_searcher.config import build_pattern
from string_searcher.config import normalize_extensions
from string_searcher.config import parse_date
from string_searcher.errors import EmptySearchTermError
from string_searcher.errors import InvalidDateError
from string_searcher.errors import InvalidExtensionError


class TestParseDate:
    def test_returns_none_for_none(self) -> None:
        assert parse_date(None) is None

    def test_parses_padded_date(self) -> None:
        result = parse_date("2024-03-05")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 5

    @pytest.mark.parametrize("bad", ["2024-3-5", "not-a-date", "2024/03/05", ""])
    def test_rejects_invalid(self, bad) -> None:
        with pytest.raises(InvalidDateError):
            parse_date(bad)


class TestNormalizeExtensions:
    def test_prepends_dot(self) -> None:
        assert normalize_extensions("py,txt") == frozenset({".py", ".txt"})

    def test_preserves_dot(self) -> None:
        assert normalize_extensions(".py,.md") == frozenset({".py", ".md"})

    def test_lowercases_and_strips(self) -> None:
        assert normalize_extensions(" .PY , .Md ") == frozenset({".py", ".md"})

    def test_drops_empty(self) -> None:
        assert normalize_extensions(",,.py,") == frozenset({".py"})


class TestBuildPattern:
    def test_literal_uses_word_boundaries(self) -> None:
        pat, used_regex = build_pattern("foo", case_sensitive=False)
        assert used_regex is False
        assert pat.search("foo bar")
        assert not pat.search("foobar")

    def test_regex_metachars_trigger_regex_mode(self) -> None:
        pat, used_regex = build_pattern("fo+", case_sensitive=True)
        assert used_regex is True
        assert pat.search("foooo")

    def test_case_sensitive_flag(self) -> None:
        pat, _ = build_pattern("Foo", case_sensitive=True)
        assert pat.search("Foo")
        assert not pat.search("foo")

    def test_empty_raises(self) -> None:
        with pytest.raises(EmptySearchTermError):
            build_pattern("", case_sensitive=False)


class TestBuildConfig:
    def _kwargs(self, **overrides):
        base = {
            "directory": ".",
            "search_term": "foo",
            "maxdepth": 1,
            "extensions": ".py,.txt",
            "maxline": 1000,
            "case_sensitive": False,
            "start_date": None,
            "end_date": None,
            "size_limit_kb": None,
            "acceptable_extensions": {".py", ".txt", ".md"},
            "suggester": lambda req, cands: [],
        }
        base.update(overrides)
        return base

    def test_happy_path(self) -> None:
        cfg = build_config(**self._kwargs())
        assert cfg.use_regex is False
        assert cfg.size_limit_bytes is None
        assert ".py" in cfg.extensions

    def test_zero_size_limit_treated_as_none(self) -> None:
        cfg = build_config(**self._kwargs(size_limit_kb=0))
        assert cfg.size_limit_bytes is None

    def test_size_limit_converted_to_bytes(self) -> None:
        cfg = build_config(**self._kwargs(size_limit_kb=2.5))
        assert cfg.size_limit_bytes == 2560

    def test_invalid_extension_raises_with_suggestions(self) -> None:
        called = {}

        def suggester(req, cands):
            called["req"] = req
            return [".py"]

        with pytest.raises(InvalidExtensionError) as exc_info:
            build_config(**self._kwargs(extensions=".xyz", suggester=suggester))
        assert exc_info.value.suggestions == [".py"]
        assert called["req"]

    def test_regex_metachars_route_to_regex(self) -> None:
        cfg = build_config(**self._kwargs(search_term="fo+"))
        assert cfg.use_regex is True
        assert isinstance(cfg.pattern, re.Pattern)
