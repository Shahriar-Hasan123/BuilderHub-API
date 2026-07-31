
from apps.core.exceptions import ResourceLockedError, SiteLockedAPIException
from apps.core.services.resource_lock import SiteLockService


class SiteLockMixin:
    def enforce_site_lock(self, request, site):
        try:
            SiteLockService().acquire(site.id, request.user)
        except ResourceLockedError as exc:
            raise SiteLockedAPIException(
                detail=f"This site is currently being edited by {exc.locked_by}. Please try again later."
            )