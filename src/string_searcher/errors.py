"""Domain exceptions for string_searcher."""


class SearchError(Exception):
    """Base class for configuration and execution errors."""


class EmptySearchTermError(SearchError):
    """Raised when the search term is empty."""


class InvalidDateError(SearchError):
    """Raised when a date is not strict YYYY-MM-DD."""


class InvalidExtensionError(SearchError):
    """Raised when no requested extension is in the allow-list."""

    def __init__(self, requested: frozenset[str], suggestions: list[str]) -> None:
        self.requested = requested
        self.suggestions = suggestions
        msg = f"None of the requested extensions {sorted(requested)} are recognized text-file extensions."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        super().__init__(msg)
