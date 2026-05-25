"""Pure scanning and matching primitives — no console I/O, no process control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import NamedTuple

if TYPE_CHECKING:
    from .config import SearchConfig


@dataclass(frozen=True, slots=True)
class FileMatch:
    """A single regex match within a file, with metadata for rendering and filtering."""

    file: Path
    line_number: int
    mtime: datetime
    line: str
    spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class ScanResult:
    """The result of scanning a directory: all files that passed the filters, and a count of all directories visited."""

    directories: int
    files: tuple[Path, ...]


class _LineContext(NamedTuple):
    path: Path
    line_no: int
    mtime: datetime


def _accepts(stat: os.stat_result, suffix: str, cfg: SearchConfig) -> bool:
    if suffix.lower() not in cfg.extensions:
        return False
    if cfg.size_limit_bytes is not None and stat.st_size > cfg.size_limit_bytes:
        return False
    if cfg.start_date is None and cfg.end_date is None:
        return True
    mtime = datetime.fromtimestamp(stat.st_mtime).astimezone()
    if cfg.start_date is not None and mtime < cfg.start_date:
        return False
    return cfg.end_date is None or mtime <= cfg.end_date


def scan_directory(cfg: SearchConfig) -> ScanResult:
    """Walk `cfg.directory` up to `cfg.maxdepth` and collect files passing all filters."""
    files: list[Path] = []
    directories = _walk(cfg.directory, cfg, depth=0, files=files)
    return ScanResult(directories=directories, files=tuple(files))


def _walk(root: Path, cfg: SearchConfig, *, depth: int, files: list[Path]) -> int:
    if not root.is_dir() or (cfg.maxdepth != -1 and depth > cfg.maxdepth):
        return 0
    count = 1
    try:
        scandir_ctx = os.scandir(root)
    except OSError:
        return count
    with scandir_ctx as entries:
        for entry in entries:
            entry_path = Path(entry.path)
            if entry.is_file(follow_symlinks=False):
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                if _accepts(stat, entry_path.suffix, cfg):
                    files.append(entry_path)
            elif entry.is_dir(follow_symlinks=False) and (cfg.maxdepth == -1 or depth < cfg.maxdepth):
                count += _walk(entry_path, cfg, depth=depth + 1, files=files)
    return count


def search_file(path: Path, cfg: SearchConfig) -> list[FileMatch]:
    """Stream-read `path` in 8KB chunks and return every line that matches `cfg.pattern`."""
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    except OSError:
        return []
    matches: list[FileMatch] = []
    line_no = 0
    remainder = ""
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            while chunk := fh.read(8192):
                lines = (remainder + chunk).split("\n")
                remainder = lines.pop()
                for line in lines:
                    line_no += 1
                    _collect(matches, line, _LineContext(path=path, line_no=line_no, mtime=mtime), cfg)
            if remainder:
                line_no += 1
                _collect(matches, remainder, _LineContext(path=path, line_no=line_no, mtime=mtime), cfg)
    except OSError:
        return matches
    return matches


def _collect(
    matches: list[FileMatch],
    line: str,
    ctx: _LineContext,
    cfg: SearchConfig,
) -> None:
    """If `line` matches `cfg.pattern`, append a FileMatch to `matches`."""
    if spans := tuple((m.start(), m.end()) for m in cfg.pattern.finditer(line)):
        matches.append(FileMatch(file=ctx.path, line_number=ctx.line_no, mtime=ctx.mtime, line=line, spans=spans))
