# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CLI tool that searches text-based files in a directory tree for a string or regex, with rich-formatted output. Requires Python >=3.14. Single runtime dependency: `rich`.

## Commands

Install (uv is the active lockfile; poetry.lock also present):

```powershell
uv sync
```

Run the searcher:

```powershell
uv run python string_searcher.py <directory> <search_term> [--maxdepth N] [-e .py,.md] [--maxline N] [-c] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--size-limit KB]
```

`--maxdepth -1` recurses fully. `-c` enables case-sensitive matching.

There is no test suite, lint config, or build step beyond `hatchling` packaging.

## Architecture

Two-stage pipeline in `string_searcher.py`:

1. **`FileSearcher.scan_directory`** — recursive `os.scandir` walk that filters by extension, mtime range, and size limit (`is_valid_file`), bounded by `--maxdepth`. Returns the full file list eagerly (not a generator), so very large trees materialize in memory.
2. **`FileSearcher.search_worker`** — dispatches `search_file` across a pool. **Executor choice depends on the search term**: if the term contains regex metacharacters (`.*+?^$%{}()|[]\`), it is treated as a real regex and run on a `ProcessPoolExecutor` (CPU-bound); otherwise the term is escaped with word-boundary lookarounds (`(?<!\w)term(?!\w)`) and run on a `ThreadPoolExecutor` (I/O-bound). Worker count is `3×cores` for regex, `5×cores` for plain. This branch is set in `__init__` via `self.use_regex` and is the single most important design decision in the file — changing how a term is detected as regex changes which executor runs.

File reading uses 8 KB chunked reads with a `remaining_line` carry-over so line numbers stay correct across chunk boundaries without loading the whole file. Long lines are truncated to `--maxline` for display only; matching still runs on the truncated string.

Results accumulate in memory and are printed only after `console.status("Searching...")` exits, so `rich`'s spinner does not interleave with output.

## Extension validation

`utils/file_extensions.json` is the canonical allow-list of text extensions (loaded at import time into `ACCEPTABLE_EXTENSIONS`). User-supplied `-e` extensions must intersect this set, or the tool exits and suggests near-matches via `get_closest_matches` (a custom prefix-weighted similarity in `utils/helpers.py`, not `difflib.get_close_matches`). When adding support for a new extension, edit the JSON file rather than the default list in `arg_parser`.
