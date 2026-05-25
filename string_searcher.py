"""Backwards-compatible entrypoint: `python string_searcher.py ...` still works."""

import sys
from pathlib import Path

# Make the src layout importable when running this script directly.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from string_searcher.cli import entrypoint

if __name__ == "__main__":
    entrypoint()
