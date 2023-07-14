"""Search all files in a directory for a given string."""

import argparse
import multiprocessing
import os
import re
import sys
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console(highlight=False)

# Common text-based file extensions
ACCEPTABLE_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".xml",
    ".html",
    ".htm",
    ".rst",
    ".ini",
    ".py",
    ".js",
    ".css",
    ".yml",
    ".yaml",
    ".php",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
}


def search_file(file_path: Path, search_term: str, use_regex: bool, file_extensions: set[str]) -> list[str]:
    """Search a file for a given string."""
    results = []
    if file_path.is_file() and file_path.suffix.lower() in file_extensions:
        with file_path.open(encoding="utf8", errors="ignore") as f:
            for idx, line in enumerate(f):
                match = re.search(search_term, line) if use_regex else search_term in line
                if match:
                    highlighted_line = re.sub(search_term, f"[bold][green]{search_term}[/green][/bold]", line)
                    results.append(
                        f"[yellow]{file_path}[/yellow] - [cyan]Line {idx + 1}[/cyan]\n{highlighted_line}",
                    )
    return results


def scan_directory(path: Path, depth: int, extensions: set[str], current_depth: int = 0) -> tuple[int, Iterable[Path]]:
    """Recursively scan a directory up to a given depth and yield files."""
    count = 0
    files = []
    # ignore depth limit when depth is -1
    if path.is_dir() and (depth == -1 or current_depth <= depth):
        for entry in os.scandir(path):
            entry_path = Path(entry.path)
            if entry.is_file() and entry_path.suffix.lower() in extensions:
                files.append(entry_path)
            elif entry.is_dir() and (depth == -1 or current_depth < depth):  # only traverse to specified depth
                sub_count, sub_files = scan_directory(entry_path, depth, extensions, current_depth + 1)
                count += sub_count
                files.extend(sub_files)
        count += 1

    return count, files


def search_worker(use_regex: bool, search_term: str, user_extensions: set[str], all_files: Iterable[Path]) -> int:
    """Search Worker."""
    num_cores = multiprocessing.cpu_count()
    num_workers = 3 * num_cores if use_regex else 5 * num_cores

    # choose executor type based on whether the task is CPU-bound or IO-bound
    # regex searches are CPU-intensive, so use ProcessPoolExecutor
    # non-regex searches are IO-bound, so use ThreadPoolExecutor
    executor_class = ProcessPoolExecutor if use_regex else ThreadPoolExecutor
    console.print(f":fire: Using {num_workers} {executor_class.__name__} workers\n")

    results_count = 0
    try:
        all_results = []
        with console.status("Searching..."), executor_class(max_workers=num_workers) as executor:
            futures_to_files = {
                executor.submit(
                    search_file,
                    file_path,
                    search_term,
                    use_regex,
                    user_extensions,
                ): file_path
                for file_path in all_files
            }
            for future in as_completed(futures_to_files):
                file_path = futures_to_files[future]
                try:
                    lines = future.result()
                    if lines:
                        results_count += 1
                    all_results.extend(lines)
                except Exception as exc:
                    console.print(f"[red]{file_path} generated an exception :scream: :{exc}[/red]")

        # print all results after `console.status` is finished
        for result in all_results:
            console.print(result)

    except KeyboardInterrupt:
        console.print("Search cancelled :relieved:")
        sys.exit(1)

    return results_count


def arg_parser() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=str, help="The directory to search")
    parser.add_argument("search_term", type=str, help="The string to search for")
    parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="The maximum depth to recurse. Default is 1. Use '--depth -1' for all subdirectories",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        type=str,
        default=".txt,.md,.csv,.xml,.html,.py,.js,.css,.yml,.yaml",
        help="The file extensions to search in. Provide a comma separated list e.g., .txt,.py,.md",
    )
    return parser.parse_args()


def main() -> None:
    """Main function."""
    args = arg_parser()
    base_path = Path(args.directory)

    # decide whether to use regex based on search_term
    use_regex = re.search(r"[.*+?^${}()|[\]\\]", args.search_term) is not None
    search_term = f"\b({args.search_term})\b" if use_regex else args.search_term

    # convert user-provided extensions to a set
    user_extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions.lower().split(",")}

    # check if user-provided extensions are acceptable
    if not user_extensions.issubset(ACCEPTABLE_EXTENSIONS):
        console.print("Invalid extension(s) provided. Please ensure they are text-based files. :expressionless:")
        sys.exit(1)

    # store results of the directory scan for further processing
    directory_count, all_files = scan_directory(base_path, args.depth, user_extensions)

    # run search worker
    results_count = search_worker(use_regex, search_term, user_extensions, all_files)

    # results summary
    depth_summary = "all" if args.depth == -1 else args.depth
    pnl = Panel(
        f"Crawled {directory_count} directories at a maximum depth of {depth_summary}. "
        f"Found results in {results_count} files for search term '{args.search_term}'.",
        expand=False,
        border_style="blue",
    )
    console.print(pnl)


if __name__ == "__main__":
    # Banner ('Elite') courtesy of https://manytools.org/hacker-tools/ascii-banner/
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
    console.print(banner, style="bold cyan")
    main()
