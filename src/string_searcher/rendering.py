"""Rich formatting for matches and the summary panel — no business logic."""

from rich.panel import Panel

from .core import FileMatch


def render_match(match: FileMatch, *, maxline: int) -> str:
    """Render one FileMatch with highlighted spans; truncate the visible line at `maxline`."""
    line = match.line
    truncated = len(line) > maxline
    visible = line[:maxline] if truncated else line
    parts: list[str] = []
    cursor = 0
    for start, end in match.spans:
        if start >= maxline:
            break
        span_end = min(end, maxline)
        parts.extend((visible[cursor:start], f"[green1]{visible[start:span_end]}[/green1]"))
        cursor = span_end
    parts.append(visible[cursor:])
    suffix = "[grey50]...\\[truncated][/grey50]" if truncated else ""
    return (
        f"[yellow]{match.file}[/yellow] - "
        f"[cyan]Line {match.line_number}[/cyan] "
        f"([magenta]{match.mtime}[/magenta])\n"
        f"{''.join(parts)}{suffix}\n"
    )


def render_summary(*, directories: int, files_with_hits: int, term: str, maxdepth: int) -> Panel:
    """Render a summary of the search results."""
    depth = "all" if maxdepth == -1 else maxdepth
    return Panel(
        f"Crawled {directories} directories at a max depth of {depth}. "
        f"Found results in {files_with_hits} files for search term '{term}.'",
        title="Summary Results",
        expand=False,
        border_style="blue",
    )


def render_extension_help(suggestions: list[str]) -> Panel:
    """Render a help panel for unrecognised extensions."""
    body = (
        f"Did you mean to search for one of these extensions? :thinking_face:\n\n"
        f"[bright_white]{', '.join(suggestions)}[/bright_white]"
    )
    return Panel(body, title="Closest Extension Matches", expand=False, border_style="blue")
