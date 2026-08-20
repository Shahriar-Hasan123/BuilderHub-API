from django.db import transaction
from apps.pages.models import Page
from apps.sites.models import Site, SitePublishVersion
from apps.sites.services.blob_store import BlobStore
from apps.sites.services.publish_asset_service import PublishAssetService
from apps.sites.services.publish_content_service import PublishContentService
from apps.sites.services.publish_version_service import PublishVersionService


class PublishService:
    def __init__(self):
        self.blobs = BlobStore()
        self.content = PublishContentService()
        self.assets = PublishAssetService(self.blobs)
        self.versions = PublishVersionService(
            self.blobs,
            self.assets,
            self.content,
        )

    def publish(self, site, user=None, request=None):
        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )
        self.content.validate_readiness(site, pages)
        (
            header_json,
            footer_json,
            page_jsons,
            header_hash,
            footer_hash,
            page_hashes,
            asset_hashes,
        ) = self.versions.hashes(site, pages, request)

        previous_files = {}
        try:
            previous_files.update(
                self.assets.replace_published_files(
                    site, header_json, footer_json, page_jsons
                )
            )
            previous_files.update(
                self.assets.cleanup_orphan_pages(site, page_jsons.keys())
            )

            with transaction.atomic():
                locked_site = Site.objects.select_for_update().get(pk=site.id)
                version = self.versions.find_or_create(
                    locked_site,
                    (header_hash, footer_hash, page_hashes, asset_hashes),
                    user=user,
                )
                locked_site.status = locked_site.Status.PUBLISHED
                locked_site.current_published_version = version
                locked_site.save(update_fields=["status", "current_published_version"])
                Page.objects.filter(pk__in=[page.pk for page in pages]).update(
                    status=Page.Status.PUBLISHED
                )
        except Exception:
            self.assets.restore_published_files(previous_files)
            raise

        site.refresh_from_db(fields=["status", "current_published_version"])
        return {
            "message": "Site published successfully.",
            "site": {
                "id": site.id,
                "status": site.status,
                "current_published_version": version.version_number,
            },
            "version": {
                "id": version.id,
                "number": version.version_number,
                "published_at": version.created_at,
                "published_by": version.published_by_id,
            },
            "snapshot": self.assets.snapshot_response(site, page_jsons, request),
        }

    def has_unpublished_changes(self, site, request=None):
        current = site.current_published_version
        if not current:
            return True

        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )
        _, _, _, header_hash, footer_hash, page_hashes, asset_hashes = self.versions.hashes(
            site, pages, request
        )

        return (
            header_hash != current.header_hash
            or footer_hash != current.footer_hash
            or page_hashes != current.page_hashes
            or asset_hashes != current.asset_hashes
        )

