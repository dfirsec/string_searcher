from __future__ import annotations

import io
from concurrent.futures import Executor
from concurrent.futures import Future

import pytest
from rich.console import Console
from string_searcher.cli import main


class _SyncExecutor(Executor):
    """Run submitted callables synchronously for deterministic tests."""

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def submit(self, fn, /, *args, **kwargs):
        fut: Future = Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            fut.set_exception(exc)
        return fut

    def shutdown(self, wait=True, *, cancel_futures=False) -> None:
        pass


def _sync_factory(_cfg):
    return _SyncExecutor, 1


@pytest.fixture
def captured() -> Console:
    return Console(file=io.StringIO(), highlight=False, width=200, force_terminal=False)


def _output(c: Console) -> str:
    return c.file.getvalue()  # type: ignore[union-attr]


def test_main_reports_matches(sample_tree, captured) -> None:
    code = main(
        [str(sample_tree), "hello", "--maxdepth", "-1"],
        console=captured,
        executor_factory=_sync_factory,
        acceptable_extensions=frozenset({".txt", ".py"}),
    )
    out = _output(captured)
    assert code == 0
    assert "Line 1" in out
    assert "Summary Results" in out


def test_main_invalid_extension_returns_1(tmp_path, captured) -> None:
    code = main(
        [str(tmp_path), "x", "-e", ".xyz"],
        console=captured,
        executor_factory=_sync_factory,
        acceptable_extensions=frozenset({".py", ".txt"}),
    )
    assert code == 1
    assert "ERROR" in _output(captured)


def test_main_empty_search_term_returns_1(tmp_path, captured) -> None:
    code = main(
        [str(tmp_path), ""],
        console=captured,
        executor_factory=_sync_factory,
        acceptable_extensions=frozenset({".py", ".txt"}),
    )
    assert code == 1


def test_main_invalid_date_returns_1(tmp_path, captured) -> None:
    code = main(
        [str(tmp_path), "x", "--start-date", "2024/01/01"],
        console=captured,
        executor_factory=_sync_factory,
        acceptable_extensions=frozenset({".py", ".txt"}),
    )
    assert code == 1
