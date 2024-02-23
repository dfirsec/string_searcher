"""Utility functions for string_searcher."""

import argparse
import sys
from datetime import datetime
from difflib import SequenceMatcher

from rich.console import Console
from rich.traceback import install

install(show_locals=True)
console = Console()


def arg_parser() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=str, help="The directory to search")
    parser.add_argument("search_term", type=str, help="The string to search for")
    parser.add_argument(
        "--maxdepth",
        type=int,
        default=1,
        help="The maximum depth to recurse. Default is 1. Use '--maxdepth -1' for all subdirectories",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        type=str,
        default=".bat,.cfg,.csv,.css,.html,.ini,.js,.log,.md,.ps1,.py,.sh,.txt,.xml,.yaml,.yml",
        help="The file extensions to search in. Provide a comma separated list e.g., .txt,.py,.md",
    )
    parser.add_argument(
        "-m",
        "--maxline",
        type=int,
        default=1000,
        help="The maximum line length to display. Default is 1000. Adjust if line is truncated.",
    )
    parser.add_argument("-c", "--case-sensitive", action="store_true", help="Perform a case-sensitive search")
    parser.add_argument(
        "--start-date",
        type=str,
        help="The start date for modification date filtering. Use format YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="The end date for modification date filtering. Use format YYYY-MM-DD",
    )
    parser.add_argument("--size-limit", type=float, help="The maximum file size to consider in kilobytes")

    args = parser.parse_args()

    # Validate start_date and end_date
    date_format = "%Y-%m-%d"
    if args.start_date:
        try:
            datetime.strptime(args.start_date, date_format).astimezone()
        except ValueError:
            console.print(":no_entry: [red]\\[ERROR][/red] Invalid start date. Use format YYYY-MM-DD.")
            sys.exit(1)
    if args.end_date:
        try:
            datetime.strptime(args.end_date, date_format).astimezone()
        except ValueError:
            console.print(":no_entry: [red]\\[ERROR][/red] Invalid end date. Use format YYYY-MM-DD.")
            sys.exit(1)

    return args


def valid_date(date_str: str) -> datetime:
    """Validate date string and return a datetime object to FileSearcher class."""
    date = datetime.strptime(date_str, "%Y-%m-%d").astimezone()
    if date_str != date.strftime("%Y-%m-%d"):
        msg = f"Date must be in 'YYYY-MM-DD' format, but got {date_str}"
        raise argparse.ArgumentTypeError(msg)
    return date


def similarity_score(a: str, b: str) -> float:
    """Return the similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).get_matching_blocks()[0].size / max(len(a), len(b))


def get_closest_matches(extension: str, possibilities: set, n: int = 3) -> list[str]:
    """Return a list of the best "good enough" matches for a given word."""
    scores = [(similarity_score(extension, possibility), possibility) for possibility in possibilities]
    scores.sort(reverse=True)
    return [match for score, match in scores[:n] if score > 0.25]
