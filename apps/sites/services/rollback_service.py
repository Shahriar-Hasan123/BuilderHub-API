from django.db import transaction

from apps.core.exceptions import PublishValidationError
from apps.sites.services.blob_store import BlobStore
from apps.sites.services.publish_asset_service import PublishAssetService
from apps.sites.services.restore_service import RestoreService
from apps.sites.services.publish_service import PublishService


class RollbackService:
    def __init__(self):
        blobs = BlobStore()
        assets = PublishAssetService(blobs)
        self.restore_service = RestoreService(blobs, assets)
        self.publisher = PublishService()

    def has_unpublished_changes(self, site, request=None):
        return self.publisher.has_unpublished_changes(site, request)

    def restore_source(self, site, version, user):
        return self.restore_service.restore(site, version, user)

    def rollback(self, site, version, user=None, request=None):
        if version.site_id != site.id:
            raise PublishValidationError(
                "This publish version does not belong to this site."
            )

        current = site.current_published_version
        from_version = current.version_number if current else None

        with transaction.atomic():
            restore_result = self.restore_source(site, version, user)
            self.publisher.publish(site, user=user, request=request)

        return {
            "message": "Rollback completed successfully.",
            "from_version": {"number": from_version},
            "to_version": {"number": version.version_number},
            "restored": {
                "site": True,
                "header": True,
                "footer": True,
                "pages": restore_result["restored_pages"],
                "assets": True,
            },
            "removed": {"pages": restore_result["removed_pages"]},
        }
