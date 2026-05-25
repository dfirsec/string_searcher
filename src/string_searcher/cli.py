"""Argparse, executor wiring, and the orchestrating `main`."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
import time
from collections.abc import Callable
from collections.abc import Sequence
from concurrent.futures import Executor
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path

from rich.console import Console
from rich.traceback import install as install_rich_traceback

from .config import DEFAULT_EXTENSIONS
from .config import SearchConfig
from .config import SearchInputs
from .config import build_config
from .core import FileMatch
from .core import scan_directory
from .core import search_file
from .errors import InvalidExtensionError
from .errors import SearchError
from .rendering import render_extension_help
from .rendering import render_match
from .rendering import render_summary
from .similarity import suggest_extensions

_BANNER = r"""
    .▄▄ · ▄▄▄▄▄▄▄▄  ▪   ▐ ▄  ▄▄ •
    ▐█ ▀. •██  ▀▄ █·██ •█▌▐█▐█ ▀ ▪
    ▄▀▀▀█▄ ▐█.▪▐▀▀▄ ▐█·▐█▐▐▌▄█ ▀█▄
    ▐█▄▪▐█ ▐█▌·▐█•█▌▐█▌██▐█▌▐█▄▪▐█
     ▀▀▀▀  ▀▀▀ .▀  ▀▀▀▀▀▀ █▪·▀▀▀▀
    .▄▄ · ▄▄▄ . ▄▄▄· ▄▄▄   ▄▄·  ▄ .▄▄▄▄ .▄▄▄
    ▐█ ▀. ▀▄.▀·▐█ ▀█ ▀▄ █·▐█ ▌▪██▪▐█▀▄.▀·▀▄ █·
    ▄▀▀▀█▄▐▀▀▪▄▄█▀▀█ ▐▀▀▄ ██ ▄▄██▀▐█▐▀▀▪▄▐▀▀▄
    ▐█▄▪▐█▐█▄▄▌▐█ ▪▐▌▐█•█▌▐███▌██▌▐▀▐█▄▄▌▐█•█▌
     ▀▀▀▀  ▀▀▀  ▀  ▀ .▀  ▀·▀▀▀ ▀▀▀ · ▀▀▀ .▀  ▀
"""

ExecutorFactory = Callable[[SearchConfig], tuple[type[Executor], int]]


def load_acceptable_extensions() -> frozenset[str]:
    path = Path(__file__).parent / "file_extensions.json"
    return frozenset(json.loads(path.read_text(encoding="utf-8")))


# Windows caps ProcessPoolExecutor at 61 workers (see CPython's _MAX_WINDOWS_WORKERS).
_WINDOWS_PROCESS_POOL_CAP = 61


def default_executor_factory(cfg: SearchConfig) -> tuple[type[Executor], int]:
    """Regex search is CPU-bound (ProcessPool); literal search is I/O-bound (ThreadPool)."""
    cores = multiprocessing.cpu_count()
    if cfg.use_regex:
        workers = 3 * cores
        if sys.platform == "win32":
            workers = min(workers, _WINDOWS_PROCESS_POOL_CAP)
        return ProcessPoolExecutor, workers
    return ThreadPoolExecutor, 5 * cores


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="string_searcher")
    parser.add_argument("directory", help="The directory to search")
    parser.add_argument("search_term", help="The string to search for")
    parser.add_argument("--maxdepth", type=int, default=1, help="Max recursion depth (default 1; -1 = unlimited)")
    parser.add_argument(
        "-e", "--extensions", default=DEFAULT_EXTENSIONS, help="Comma-separated extensions, e.g. .txt,.py,.md"
    )
    parser.add_argument(
        "-m", "--maxline", type=int, default=1000, help="Truncate displayed lines longer than this (default 1000)"
    )
    parser.add_argument("-c", "--case-sensitive", action="store_true")
    parser.add_argument("--start-date", help="Filter by mtime >= start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Filter by mtime <= end date (YYYY-MM-DD)")
    parser.add_argument("--size-limit", type=float, help="Max file size in KB")
    return parser


def _run_pool(
    cfg: SearchConfig,
    files: Sequence[Path],
    factory: ExecutorFactory,
    console: Console,
) -> list[FileMatch]:
    executor_cls, workers = factory(cfg)
    console.print(f":fire: Using {workers} {executor_cls.__name__} workers\n")
    matches: list[FileMatch] = []
    with console.status("Searching..."), executor_cls(max_workers=workers) as pool:
        futures = {pool.submit(search_file, path, cfg): path for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                matches.extend(future.result())
            except Exception as exc:  # noqa: BLE001 — boundary: worker failures must not abort the run
                console.print(f"[red]{path} generated an exception :scream: :{exc}[/red]")
    return matches


def main(
    argv: Sequence[str] | None = None,
    *,
    console: Console | None = None,
    executor_factory: ExecutorFactory = default_executor_factory,
    acceptable_extensions: frozenset[str] | None = None,
) -> int:
    """Library-friendly entrypoint. Returns a process exit code."""
    console = console or Console(highlight=False)
    args = _build_arg_parser().parse_args(argv)
    acceptable = acceptable_extensions or load_acceptable_extensions()

    inputs = SearchInputs(
        directory=args.directory,
        search_term=args.search_term,
        maxdepth=args.maxdepth,
        extensions=args.extensions,
        maxline=args.maxline,
        case_sensitive=args.case_sensitive,
        start_date=args.start_date,
        end_date=args.end_date,
        size_limit_kb=args.size_limit,
    )
    try:
        cfg = build_config(inputs, acceptable, suggest_extensions)
    except InvalidExtensionError as exc:
        console.print(f":no_entry: [red]\\[ERROR][/red] {exc}")
        if exc.suggestions:
            console.print(render_extension_help(exc.suggestions))
        return 1
    except SearchError as exc:
        console.print(f":no_entry: [red]\\[ERROR][/red] {exc}")
        return 1

    scan = scan_directory(cfg)
    matches = _run_pool(cfg, scan.files, executor_factory, console)

    files_with_hits = {m.file for m in matches}
    for match in matches:
        console.print(render_match(match, maxline=cfg.maxline))
    console.print(
        render_summary(
            directories=scan.directories,
            files_with_hits=len(files_with_hits),
            term=args.search_term,
            maxdepth=cfg.maxdepth,
        )
    )
    return 0


def entrypoint() -> None:
    """Console-script wrapper that prints the banner and timing."""
    install_rich_traceback(show_locals=True)
    console = Console(highlight=False)
    console.print(_BANNER, style="bright_cyan")
    start = time.perf_counter()
    try:
        code = main(console=console)
    except KeyboardInterrupt:
        console.print("Search cancelled :relieved:")
        sys.exit(130)
    console.print(f"Elapsed time: {time.perf_counter() - start:.2f} seconds")
    sys.exit(code)
