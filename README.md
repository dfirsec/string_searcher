# String Searcher

A fast CLI tool that searches text-based files in a directory tree for a string or regex, with rich-formatted output and highlighted matches.

## Features

- Auto-detects regex vs. literal search based on the search term
- Word-boundary matching for literal terms (so `foo` does not match `foobar`)
- Recursive search with configurable depth
- Filter by file extension, modification date range, and file size
- Streaming line-by-line reader (handles large files without loading them into memory)
- Parallel execution: `ProcessPoolExecutor` for regex (CPU-bound), `ThreadPoolExecutor` for literal (I/O-bound)
- Rich-formatted output with highlighted matches

## Requirements

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```text
git clone https://github.com/dfirsec/string_searcher.git
cd string_searcher
uv sync
```

Add `--extra test` if you want to run the test suite:

```text
uv sync --extra test
```

## Usage

There are three ways to run it.

### 1. Via the root script (matches the original workflow)

```text
uv run python string_searcher.py <directory> <search_term> [options]
```

### 2. Via the installed console script

`uv sync` installs a `string-searcher` entry point:

```text
uv run string-searcher <directory> <search_term> [options]
```

### 3. As a Python module

```text
uv run python -m string_searcher.cli <directory> <search_term> [options]
```

### Examples

```text
# Find every occurrence of "TODO" in the current directory (depth 1)
uv run python string_searcher.py . TODO

# Recurse through all subdirectories
uv run python string_searcher.py . TODO --maxdepth -1

# Restrict to Python and Markdown files
uv run python string_searcher.py . TODO --maxdepth -1 -e .py,.md

# Case-sensitive regex search for function definitions
uv run python string_searcher.py src "^def\s+\w+" --maxdepth -1 -c

# Only files modified in a date range, capped at 500 KB
uv run python string_searcher.py logs ERROR \
    --start-date 2026-01-01 --end-date 2026-05-25 --size-limit 500
```

### Options

| Option                    | Default            | Description                                                                           |
| ------------------------- | ------------------ | ------------------------------------------------------------------------------------- |
| `directory`               | —                  | Directory to search (positional).                                                     |
| `search_term`             | —                  | String or regex to find (positional). Quote terms containing shell metacharacters.    |
| `--maxdepth N`            | `1`                | Max recursion depth. Use `-1` for unlimited.                                          |
| `-e, --extensions LIST`   | text-file defaults | Comma-separated extensions, e.g. `.py,.md`.                                           |
| `-m, --maxline N`         | `1000`             | Truncate displayed lines longer than N characters. Matches past N are still reported. |
| `-c, --case-sensitive`    | off                | Case-sensitive matching.                                                              |
| `--start-date YYYY-MM-DD` | none               | Only files modified on/after this date.                                               |
| `--end-date YYYY-MM-DD`   | none               | Only files modified on/before this date.                                              |
| `--size-limit KB`         | none               | Skip files larger than this many kilobytes.                                           |

The default extension allow-list lives in `src/string_searcher/file_extensions.json`. If you pass an unrecognized extension, the tool suggests close matches before exiting.

## Project layout

```text
string_searcher.py              # thin shim — calls into the package
src/string_searcher/
    cli.py                      # argparse + main + executor wiring
    config.py                   # SearchConfig dataclass + validation
    core.py                     # scan_directory + search_file (pure logic)
    rendering.py                # rich formatting
    similarity.py               # extension-suggestion helper
    errors.py                   # exception hierarchy
    file_extensions.json        # text-file allow-list
tests/                          # pytest suite
```

## Running the tests

```text
uv sync --extra test
uv run pytest
```

## Library use

The package is importable. `main()` accepts an `argv` list, a `rich.Console`, and an `executor_factory`, so it is straightforward to call from another script or test.

```python
from string_searcher.cli import main

exit_code = main(["./logs", "ERROR", "--maxdepth", "-1"])
```

## License

MIT. See `LICENSE`.

## Credits

- [rich](https://github.com/Textualize/rich) — console output
- Banner text from [Manytools](https://manytools.org/hacker-tools/ascii-banner/)
- Text-file extension list from [File-Extensions](https://www.file-extensions.org/filetype/extension/name/text-files)

## Contributing

Pull requests welcome.
