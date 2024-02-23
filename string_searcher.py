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
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.traceback import install
from utils.helpers import arg_parser
from utils.helpers import get_closest_matches
from utils.helpers import valid_date

install(show_locals=True)
console = Console(highlight=False)

# Common text-based file extensions
root = Path(__file__).parent
extensions_file = Path(root / "utils" / "file_extensions.json").resolve()
with Path.open(extensions_file) as f:
    ACCEPTABLE_EXTENSIONS = set(json.load(f))


class FileSearcher:
    """Class used to search all files in a directory for a given search term."""

    def __init__(
        self: "FileSearcher",
        directory: str,
        search_term: str,
        maxdepth: int,
        extensions: str,
        maxline: int,
        case_sensitive: bool,
        start_date: str | None,
        end_date: str | None,
        size_limit: float = sys.maxsize,
    ) -> None:
        """Initialize the FileSearcher class."""
        self.directory = Path(directory)
        self.search_term = search_term
        self.maxdepth = maxdepth
        self.extensions = {ext if ext.startswith(".") else f".{ext}" for ext in extensions.lower().split(",")}
        self.maxline = maxline
        self.case_sensitive = case_sensitive
        self.start_date = valid_date(start_date) if start_date else None
        self.end_date = valid_date(end_date) if end_date else None
        self.size_limit = size_limit * 1024 if size_limit else None

        # Check if args.search_term is empty or contains double quotes.
        if not self.search_term:
            console.print(
                ":no_entry: [red]\\[ERROR][/red] Search term is empty. If your search term includes special "
                "characters like $, enclose it in single quotes (e.g., '$search').",
            )
            sys.exit(1)

        # Check if args.search_term contains any special characters that need to be escaped.
        self.use_regex = re.search(r"[.*+?^$%{}()|[\]\\]", self.search_term) is not None

        # Set flags based on case sensitivity and compile search term into a regular expression pattern.
        flags = 0 if self.case_sensitive else re.IGNORECASE
        if self.use_regex:
            self.search_term_pattern = re.compile(self.search_term, flags=flags)
        else:
            self.search_term_pattern = re.compile(r"(?<!\w)" + re.escape(self.search_term) + r"(?!\w)", flags=flags)

        # Check if user-provided extensions are acceptable.
        if not self.extensions.intersection(ACCEPTABLE_EXTENSIONS):
            closest_extensions = get_closest_matches(str(self.extensions), ACCEPTABLE_EXTENSIONS)
            if closest_extensions:
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
                    matches = list(self.search_term_pattern.finditer(display_line))
                    if matches:
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
    """Main entry point for the script."""
    try:
        args = arg_parser()
        searcher = FileSearcher(
            args.directory,
            args.search_term,
            args.maxdepth,
            args.extensions,
            args.maxline,
            args.case_sensitive,
            args.start_date,
            args.end_date,
            args.size_limit,
        )
        searcher.get_results()
    except argparse.ArgumentTypeError as err:
        console.print(f":no_entry: [red]\\[ERROR][/red] {err}")
        sys.exit(1)


if __name__ == "__main__":
    banner = """
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
    console.print(banner, style="bright_cyan")

    start = time.perf_counter()
    main()
    end = time.perf_counter()
    console.print(f"Elapsed time: {end - start:.2f} seconds")
