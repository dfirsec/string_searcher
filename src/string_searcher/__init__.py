"""Public package surface."""

from .config import SearchConfig
from .config import build_config
from .config import build_pattern
from .config import normalize_extensions
from .config import parse_date
from .core import FileMatch
from .core import ScanResult
from .core import scan_directory
from .core import search_file
from .errors import EmptySearchTermError
from .errors import InvalidDateError
from .errors import InvalidExtensionError
from .errors import SearchError

__all__ = [
    "EmptySearchTermError",
    "FileMatch",
    "InvalidDateError",
    "InvalidExtensionError",
    "ScanResult",
    "SearchConfig",
    "SearchError",
    "build_config",
    "build_pattern",
    "normalize_extensions",
    "parse_date",
    "scan_directory",
    "search_file",
]
