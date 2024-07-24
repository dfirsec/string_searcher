"""Search all files in a directory for a given search term."""

import argparse
import json
import multiprocessing
import os
import re
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from utils.helpers import arg_parser
from utils.helpers import get_closest_matches
from utils.helpers import valid_date

console = Console(highlight=False)

# Common text-based file extensions
root = Path(__file__).parent
extensions_file = Path(root / "utils" / "file_extensions.json").resolve()
with Path.open(extensions_file) as f:
    ACCEPTABLE_EXTENSIONS = set(json.load(f))


@dataclass
class SearchConfig:
    """Data class to store search configuration options."""

    directory: str
    search_term: str
    maxdepth: int
    extensions: str | None = None
    maxline: int = 1000
    case_sensitive: bool = False
    start_date: str | None = None
    end_date: str | None = None
    size_limit: float | None = None


class FileSearcher:
    """Class used to search all files in a directory for a given search term."""

    def __init__(self, config: SearchConfig):
        """Initialize the FileSearcher class."""
        self.config = config
        self.directory = Path(config.directory)
        self.search_term = config.search_term
        self.maxdepth = config.maxdepth
        self.extensions = (
            {ext if ext.startswith(".") else f".{ext}" for ext in config.extensions.lower().split(",")}
            if config.extensions
            else ACCEPTABLE_EXTENSIONS
        )
        self.maxline = config.maxline
        self.case_sensitive = config.case_sensitive
        self.start_date = valid_date(config.start_date) if config.start_date else None
        self.end_date = valid_date(config.end_date) if config.end_date else None

        # Convert size limit to kilobytes - set to None if no limit
        if config.size_limit is not None:
            self.size_limit = config.size_limit * 1024 if config.size_limit != sys.maxsize else None
        else:
            self.size_limit = None

        # Initialize search term pattern and flags
        self._validate_search_term()
        self._prepare_search_term()
        self._validate_extensions()

    def _validate_search_term(self) -> None:
        """Validate the search term and check if it is a regex pattern."""
        if not self.search_term:
            console.print(
                ":no_entry: [red]\\[ERROR][/red] Search term is empty. If your search term includes special "
                "characters like $, enclose it in single quotes (e.g., '$search').",
            )
            sys.exit(1)

    def _prepare_search_term(self) -> None:
        """Prepare the search term by compiling the regex pattern if needed."""
        self.use_regex = re.search(r"[.*+?^$%{}()|[\]\\]", self.search_term) is not None
        flags = 0 if self.case_sensitive else re.IGNORECASE
        if self.use_regex:
            self.search_term_pattern = re.compile(self.search_term, flags=flags)
        else:
            self.search_term_pattern = re.compile(r"(?<!\w)" + re.escape(self.search_term) + r"(?!\w)", flags=flags)

    def _validate_extensions(self) -> None:
        """Validate the file extensions provided by the user."""
        if self.config.extensions and not self.extensions.intersection(ACCEPTABLE_EXTENSIONS):
            if closest_extensions := get_closest_matches(str(self.extensions), ACCEPTABLE_EXTENSIONS):
                console.print(
                    Panel(
                        "Did you mean to search for one of these extensions? "
                        f":thinking_face:\n\n[bright_white]{', '.join(closest_extensions)}[/bright_white]",
                        title="Closest Extension Matches",
                        expand=False,
                        border_style="blue",
                    ),
                )
            else:
                console.print(
                    "Invalid extension(s) provided. Please ensure they are text-based files. :expressionless:",
                )
            sys.exit(1)

    def is_valid_file(self: "FileSearcher", file_path: Path) -> bool:
        """Check if a file is valid based on the extension, modification date, and size."""
        modification_date = datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()
        return (
            file_path.is_file()
            and file_path.suffix.lower() in self.extensions
            and (self.start_date is None or self.start_date <= modification_date)
            and (self.end_date is None or modification_date <= self.end_date)
            and (self.size_limit is None or Path.stat(file_path).st_size <= self.size_limit)
        )

    def search_file(self: "FileSearcher", file_path: Path) -> list[str]:
        """Search a file for a given search term."""
        results = []

        if not self.is_valid_file(file_path):
            return results

        modification_date = datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()

        remaining_line = ""
        line_count = 0
        chunk_size = 8192
        with file_path.open(encoding="utf8", errors="ignore") as f:
            while chunk := f.read(chunk_size):
                lines = (remaining_line + chunk).split("\n")
                remaining_line = lines.pop()  # carry remaining line to next chunk
                for idx, line in enumerate(lines, start=line_count + 1):
                    line_count = idx
                    display_line = line
                    display_line = (
                        f"{line[:self.maxline]}[grey50]...\\[truncated][/grey50]" if len(line) > self.maxline else line
                    )
                    if matches := list(self.search_term_pattern.finditer(display_line)):
                        result_line = display_line
                        for match in reversed(matches):  # reverse to avoid messing up indices
                            start = match.start()
                            end = match.end()
                            result_line = (
                                f"{result_line[:start]}[green1]{result_line[start:end]}[/green1]" f"{result_line[end:]}"
                            )
                        results.append(
                            f"[yellow]{file_path}[/yellow] - [cyan]Line {line_count}[/cyan] ([magenta]"
                            f"{modification_date}[/magenta])\n"
                            f"{result_line}\n",
                        )
        return results

    def scan_directory(self: "FileSearcher", path: Path, depth: int = 0) -> tuple[int, Iterable[Path]]:
        """Recursively scan a directory up to a given max depth and yield files.

        ...

        Notes:
        -----
            Use of os.scandir() was slightly faster than Path.iterdir()
        """
        count = 0
        files = []
        if path.is_dir() and (self.maxdepth == -1 or depth <= self.maxdepth):  # ignore depth limit if max depth is -1
            for entry in os.scandir(path):
                entry_path = Path(entry.path)
                if self.is_valid_file(entry_path):
                    files.append(entry_path)
                elif entry.is_dir() and (self.maxdepth == -1 or depth < self.maxdepth):  # traverse to specified depth
                    sub_count, sub_files = self.scan_directory(entry_path, depth + 1)
                    count += sub_count
                    files.extend(sub_files)
            count += 1
        return count, files

    def search_worker(self: "FileSearcher", all_files: Iterable[Path]) -> int:
        """Searches for the given search term in all files in the given directory.

        ...

        Notes:
        -----
            Choose the executor type based on whether the task is CPU-bound or IO-bound
            Regex searches are CPU-intensive, so use ProcessPoolExecutor
            Non-regex searches are IO-bound, so use ThreadPoolExecutor
        """
        num_cores = multiprocessing.cpu_count()
        num_workers = 3 * num_cores if self.use_regex else 5 * num_cores

        executor_class = ProcessPoolExecutor if self.use_regex else ThreadPoolExecutor
        console.print(f":fire: Using {num_workers} {executor_class.__name__} workers\n")

        results_count = 0
        try:
            all_results = []
            with console.status("Searching..."), executor_class(max_workers=num_workers) as executor:
                futures_to_files = {executor.submit(self.search_file, file_path): file_path for file_path in all_files}
                for future in as_completed(futures_to_files):
                    file_path = futures_to_files[future]
                    try:
                        lines = future.result()
                        if lines:
                            results_count += 1
                        all_results.extend(lines)
                    except Exception as exc:
                        console.print(f"[red]{file_path} generated an exception :scream: :{exc}[/red]")

            # Print all results after `console.status` is finished
            for result in all_results:
                console.print(result)

        except KeyboardInterrupt:
            console.print("Search cancelled :relieved:")
            sys.exit(1)

        return results_count

    def get_results(self: "FileSearcher") -> None:
        """Main function that executes the search process."""
        # Return the number the number of directories and files found in the directory tree.
        directory_count, all_files = self.scan_directory(self.directory)

        # Return the number of files that contain the search term.
        results_count = self.search_worker(all_files)

        # Print a summary of the search.
        depth_summary = "all" if self.maxdepth == -1 else self.maxdepth
        console.print(
            Panel(
                f"Crawled {directory_count} directories at a max depth of {depth_summary}. "
                f"Found results in {results_count} files for search term '{self.search_term}.'",
                title="Summary Results",
                expand=False,
                border_style="blue",
            ),
        )


def main() -> None:
    """Main script execution."""
    try:
        args = arg_parser()
        config = SearchConfig(
            directory=args.directory,
            search_term=args.search_term,
            maxdepth=args.maxdepth,
            extensions=args.extensions if hasattr(args, "extensions") else None,
            maxline=args.maxline,
            case_sensitive=args.case_sensitive,
            start_date=args.start_date,
            end_date=args.end_date,
            size_limit=args.size_limit,
        )
        searcher = FileSearcher(config)
        searcher.get_results()
    except argparse.ArgumentTypeError as err:
        console.print(f":no_entry: [red]\\[ERROR][/red] {err}")
        sys.exit(1)


if __name__ == "__main__":
    banner = r"""
   _____ __       _
  / ___// /______(_)___  ____ _
  \__ \/ __/ ___/ / __ \/ __ `/
 ___/ / /_/ /  / / / / / /_/ /
/____/\__/_/  /_/_/ /_/\__, / __
  / ___/___  ____ ____/____/_/ /_  ___  _____
  \__ \/ _ \/ __ `/ ___/ ___/ __ \/ _ \/ ___/
 ___/ /  __/ /_/ / /  / /__/ / / /  __/ /
/____/\___/\__,_/_/   \___/_/ /_/\___/_/
"""

    console.print(banner, style="bright_cyan")

    start = time.perf_counter()
    main()
    end = time.perf_counter()
    console.print(f"Elapsed time: {end - start:.2f} seconds")
