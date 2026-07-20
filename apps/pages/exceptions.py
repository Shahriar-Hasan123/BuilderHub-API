# apps/pages/exceptions.py
class GoogleDocsFetchError(Exception):
    """Raised when a tab's HTML export cannot be fetched."""

    pass
