import json

from django.conf import settings

from apps.core.exceptions import PublishValidationError
from apps.pages.models import Page


class RestoreService:
    def __init__(self, blobs, assets):
        self.blobs = blobs
        self.assets = assets

    def _storage_path(self, value):
        if not value:
            return value
        marker = settings.MEDIA_URL.rstrip("/") + "/"
        return value.split(marker, 1)[-1] if marker in value else value

    def restore(self, site, version, user):
        if version.site_id != site.id:
            raise PublishValidationError(
                "This publish version does not belong to this site."
            )

        header_data = json.loads(self.blobs.read(version.header_hash).decode("utf-8"))
        footer_data = json.loads(self.blobs.read(version.footer_hash).decode("utf-8"))
        page_data_by_slug = {
            slug: json.loads(self.blobs.read(page_hash).decode("utf-8"))
            for slug, page_hash in version.page_hashes.items()
        }
        asset_hashes = version.asset_hashes or {}

        site.name = header_data["site_name"]
        self.assets.restore_file_content(
            site, "header", "header.html", header_data["html"].encode("utf-8")
        )
        self.assets.restore_file_content(
            site, "footer", "footer.html", footer_data["html"].encode("utf-8")
        )
        self.assets.restore_file(
            site, "global_css", asset_hashes.get("site.global_css")
        )
        for field_name in ("favicon", "logo", "thumbnail"):
            self.assets.restore_file_reference(
                site,
                field_name,
                self._storage_path(header_data.get(field_name)),
            )
        site.updated_by = user

        pages_by_slug = {page.slug: page for page in site.pages.all()}
        restored_pages = []
        for slug, data in page_data_by_slug.items():
            page = pages_by_slug.get(slug) or Page(
                site=site,
                slug=slug,
                created_by=user,
            )
            page.title = data["title"]
            page.meta_description = data["meta_description"]
            page.page_type = data["page_type"]
            self.assets.restore_file_content(
                page,
                "html",
                f"{slug}.html",
                data["html"].encode("utf-8"),
            )
            self.assets.restore_file(
                page,
                "css",
                asset_hashes.get(f"page:{slug}:css"),
            )
            self.assets.restore_file_reference(
                page,
                "hero_image",
                self._storage_path(data.get("hero_image")),
            )
            page.enable = True
            page.status = Page.Status.PUBLISHED
            page.updated_by = user
            page.save()
            restored_pages.append(slug)

        restored_slugs = set(page_data_by_slug)
        pages_to_remove = [
            page
            for slug, page in pages_by_slug.items()
            if slug not in restored_slugs and page.pk
        ]
        removed_pages = [page.slug for page in pages_to_remove]
        for page in pages_to_remove:
            self.assets.delete_page_files(page)
        if pages_to_remove:
            Page.objects.filter(pk__in=[page.pk for page in pages_to_remove]).delete()

        site.save(
            update_fields=[
                "name",
                "header",
                "footer",
                "favicon",
                "logo",
                "thumbnail",
                "global_css",
                "updated_by",
            ]
        )
        return {
            "restored_pages": restored_pages,
            "removed_pages": removed_pages,
        }
