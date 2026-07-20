from rest_framework.exceptions import APIException
from rest_framework import status


class ResourceLockedError(Exception):
    """Internal signal that a site is currently locked by another user."""
    def __init__(self, locked_by: str):
        self.locked_by = locked_by
        super().__init__(f"Site is currently locked by {locked_by}")


class SiteLockedAPIException(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = "This site is currently being edited. Please try again later."
    default_code = "site_locked"