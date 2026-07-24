from rest_framework import status
from rest_framework.exceptions import APIException


class ResourceLockedError(Exception):
    """Internal signal that a site is currently locked by another user."""

    def __init__(self, locked_by: str):
        self.locked_by = locked_by
        super().__init__(f"Site is currently locked by {locked_by}")


class SiteLockedAPIException(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = "This site is currently being edited. Please try again later."
    default_code = "site_locked"


class LockNotHeldError(Exception):
    pass


class NoActiveLockAPIException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "No active lock exists for this site (it may have already expired)."
    )
    default_code = "no_active_lock"


class PublishValidationError(Exception):
    """Raised when a site fails a publish readiness check
    (missing header/footer, or no enabled pages with HTML)."""

    pass
