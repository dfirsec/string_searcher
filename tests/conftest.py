"""Shared fixtures."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def quiet_console() -> Console:
    """Console that captures output instead of touching the terminal."""
    return Console(file=io.StringIO(), highlight=False, width=200, force_terminal=False)


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """A small directory tree with text + wrong-extension files for scanning tests."""
    (tmp_path / "a.txt").write_text("hello world\nfoo bar\nHELLO again\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def foo():\n    return 'hello'\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("nested hello\n", encoding="utf-8")
    deep = sub / "deeper"
    deep.mkdir()
    (deep / "d.txt").write_text("very deep hello\n", encoding="utf-8")
    (tmp_path / "skip.bin").write_text("hello but wrong ext\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def acceptable() -> frozenset[str]:
    return frozenset({".txt", ".py", ".md", ".log"})
