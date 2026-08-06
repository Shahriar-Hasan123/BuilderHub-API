import json

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify

from apps.core.exceptions import PublishValidationError
from apps.pages.models import Page
from apps.sites.models import SitePublishVersion
from apps.sites.services.blob_store import BloobStore
from apps.sites.services.html_minifier import HTMLMinifier
from apps.sites.services.html_to_json import HTMLToJSONConverter


class PublishService:
    def __init__(self):
        self.minifier = HTMLMinifier()
        self.converter = HTMLToJSONConverter()
        self.blob = BloobStore()

    def _validate_readiness(self, site, pages):
        if not site.header or not site.footer:
            raise PublishValidationError(
                "Both header and footer HTML are required to publish."
            )
        if not pages:
            raise PublishValidationError(
                "Site must have at least one enabled page with HTML to publish."
            )
        if not self._read(site.header).strip():
            raise PublishValidationError("Header file is empty.")
        if not self._read(site.footer).strip():
            raise PublishValidationError("Footer file is empty.")

    def _read(self, file_field):
        with file_field.open("r") as f:
            return f.read()

    def _build_contents(self, site, pages):

        header_html = self.minifier.minify(self._read(site.header))
        header_content = json.dumps(self.converter.convert_header(site, header_html))

        footer_html = self.minifier.minify(self._read(site.footer))
        footer_content = json.dumps(self.converter.convert_footer(site, footer_html))

        page_contents = {}

        for page in pages:
            html = self._read(page.html)
            minified_html = self.minifier.minify(html)

            page_json = self.converter.convert_page(
                site,
                page,
                minified_html,
            )

            page_contents[page.slug] = json.dumps(page_json)

        return header_content, footer_content, page_contents

    def _safe_write(self, path: str, content: str) -> str:
        """Writes new content under a temp name first, confirms it landed,
        then removes the old file and writes the final name — never a
        moment where neither the old nor the new file exists."""
        temp_path = f"{path}.tmp"
        if default_storage.exists(temp_path):
            default_storage.delete(temp_path)
        default_storage.save(temp_path, ContentFile(content.encode("utf-8")))

        if default_storage.exists(path):
            default_storage.delete(path)
        default_storage.save(path, ContentFile(content.encode("utf-8")))
        default_storage.delete(temp_path)

        return path

    def _cleanup_orphan_pages(self, site, expected_slugs):
        pages_dir = f"assets/sites/{slugify(site.name)}/pages/"
        expected_filenames = {f"{slug}.json" for slug in expected_slugs}

        try:
            _, filenames = default_storage.listdir(pages_dir)
        except FileNotFoundError:
            return

        for filename in filenames:
            if filename not in expected_filenames and not filename.endswith(".tmp"):
                default_storage.delete(f"{pages_dir}{filename}")

    def _materialize(self, site, header_hash, footer_hash, page_hashes):

        written_files = [
            self._safe_write(
                f"assets/sites/{slugify(site.name)}/header.json",
                self.blob.read(header_hash),
            ),
            self._safe_write(
                f"assets/sites/{slugify(site.name)}/footer.json",
                self.blob.read(footer_hash),
            ),
        ]
        for slug, page_hash in page_hashes.items():
            written_files.append(
                self._safe_write(
                    f"assets/sites/{slugify(site.name)}/pages/{slug}.json",
                    self.blob.read(page_hash),
                )
            )
        self._cleanup_orphan_pages(site, page_hashes.keys())
        return written_files

    def _next_version_number(self, site):
        latest = site.publish_versions.aggregate(Max("version_number"))[
            "version_number__max"
        ]
        return (latest or 0) + 1

    def publish(self, site, user=None):
        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )
        self._validate_readiness(site, pages)

        header_content, footer_content, page_contents = self._build_contents(
            site, pages
        )

        header_hash = self.blob.put(header_content)
        footer_hash = self.blob.put(footer_content)
        page_hashes = {
            slug: self.blob.put(content) for slug, content in page_contents.items()
        }

        written_files = self._materialize(site, header_hash, footer_hash, page_hashes)

        with transaction.atomic():
            version = SitePublishVersion.objects.create(
                site=site,
                version_number=self._next_version_number(site),
                header_hash=header_hash,
                footer_hash=footer_hash,
                page_hashes=page_hashes,
                published_by=user,
            )
            site.status = site.Status.PUBLISHED
            site.current_published_version = version
            site.updated_by = user
            site.save(
                update_fields=["status", "current_published_version", "updated_by"]
            )
            Page.objects.filter(pk__in=[p.pk for p in pages]).update(
                status=Page.Status.PUBLISHED,
                updated_by=user,
            )

        return {
            "site_id": site.id,
            "status": "published",
            "version_number": version.version_number,
            "assets_path": f"assets/sites/{slugify(site.name)}/",
            "files": written_files,
        }

    def rollback(self, site, version: SitePublishVersion, user=None):
        if version.site_id != site.id:
            raise PublishValidationError(
                "This publish version does not belong to this site."
            )

        written_files = self._materialize(
            site, version.header_hash, version.footer_hash, version.page_hashes
        )

        with transaction.atomic():
            site.status = site.Status.PUBLISHED
            site.current_published_version = version
            site.updated_by = user
            site.save(
                update_fields=["status", "current_published_version", "updated_by"]
            )
            Page.objects.filter(site=site, slug__in=version.page_hashes.keys()).update(
                status=Page.Status.PUBLISHED,
                updated_by=user,
            )

        return {
            "site_id": site.id,
            "status": "rolled_back",
            "version_number": version.version_number,
            "assets_path": f"assets/sites/{slugify(site.name)}/",
            "files": written_files,
        }
