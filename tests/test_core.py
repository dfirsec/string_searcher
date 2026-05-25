from __future__ import annotations

import os
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

from string_searcher.config import build_config
from string_searcher.core import scan_directory
from string_searcher.core import search_file

if TYPE_CHECKING:
    from pathlib import Path


def _cfg(directory: Path, *, term: str = "hello", **overrides):
    base = {
        "directory": str(directory),
        "search_term": term,
        "maxdepth": 1,
        "extensions": ".txt,.py",
        "maxline": 1000,
        "case_sensitive": False,
        "start_date": None,
        "end_date": None,
        "size_limit_kb": None,
        "acceptable_extensions": {".txt", ".py"},
        "suggester": lambda r, c: [],
    }
    base.update(overrides)
    return build_config(**base)


class TestScanDirectory:
    def test_respects_maxdepth_zero(self, sample_tree) -> None:
        cfg = _cfg(sample_tree, maxdepth=0)
        scan = scan_directory(cfg)
        names = {p.name for p in scan.files}
        assert names == {"a.txt", "b.py"}

    def test_recurses_when_unlimited(self, sample_tree) -> None:
        cfg = _cfg(sample_tree, maxdepth=-1)
        scan = scan_directory(cfg)
        names = {p.name for p in scan.files}
        assert {"a.txt", "b.py", "c.txt", "d.txt"} <= names

    def test_filters_by_extension(self, sample_tree) -> None:
        cfg = _cfg(sample_tree, maxdepth=-1, extensions=".py", acceptable_extensions={".py"})
        scan = scan_directory(cfg)
        assert all(p.suffix == ".py" for p in scan.files)

    def test_filters_by_size(self, sample_tree) -> None:
        big = sample_tree / "big.txt"
        big.write_text("hello\n" + ("x" * 5000), encoding="utf-8")
        cfg = _cfg(sample_tree, size_limit_kb=1)  # 1024 bytes
        scan = scan_directory(cfg)
        assert big not in scan.files

    def test_filters_by_date_range(self, sample_tree) -> None:
        old = sample_tree / "old.txt"
        old.write_text("hello\n", encoding="utf-8")
        past = (datetime.now() - timedelta(days=10)).timestamp()
        os.utime(old, (past, past))
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        cfg = _cfg(
            sample_tree,
            start_date=date.today().strftime("%Y-%m-%d"),
            end_date=tomorrow,
        )
        scan = scan_directory(cfg)
        assert old not in scan.files

    def test_nonexistent_dir_yields_empty(self, tmp_path) -> None:
        cfg = _cfg(tmp_path / "nope")
        scan = scan_directory(cfg)
        assert scan.files == ()


class TestSearchFile:
    def test_finds_all_matches_case_insensitive(self, sample_tree) -> None:
        cfg = _cfg(sample_tree)
        results = search_file(sample_tree / "a.txt", cfg)
        line_nums = [r.line_number for r in results]
        assert line_nums == [1, 3]

    def test_no_match_returns_empty(self, sample_tree) -> None:
        cfg = _cfg(sample_tree, term="zzznotpresent")
        assert search_file(sample_tree / "a.txt", cfg) == []

    def test_matches_past_maxline_still_found(self, tmp_path) -> None:
        # Behavior change vs. original: previously these were silently dropped.
        long_line = ("x" * 2000) + " hello\n"
        f = tmp_path / "long.txt"
        f.write_text(long_line, encoding="utf-8")
        cfg = _cfg(tmp_path, maxline=100)
        results = search_file(f, cfg)
        assert len(results) == 1
        assert results[0].line_number == 1

    def test_handles_file_without_trailing_newline(self, tmp_path) -> None:
        f = tmp_path / "noeol.txt"
        f.write_bytes(b"hello world")
        cfg = _cfg(tmp_path)
        results = search_file(f, cfg)
        assert len(results) == 1
        assert results[0].line_number == 1

    def test_chunk_boundary_line_numbers(self, tmp_path) -> None:
        # Force lines to straddle the 8192-byte chunk boundary.
        f = tmp_path / "big.txt"
        f.write_text(("a" * 100 + "\n") * 200 + "hello\n", encoding="utf-8")
        cfg = _cfg(tmp_path)
        results = search_file(f, cfg)
        assert results[0].line_number == 201
