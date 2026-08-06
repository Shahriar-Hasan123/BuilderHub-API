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
        self.blobs = BloobStore()

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

    def _snapshot_source(self, site, pages):
        header_content = self._read(site.header)
        footer_content = self._read(site.footer)
        header_hash = self.blobs.put(header_content)
        footer_hash = self.blobs.put(footer_content)
        page_hashes = {
            page.slug: self.blobs.put(self._read(page.html)) for page in pages
        }
        return header_hash, footer_hash, page_hashes

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

    def _generate_and_write_output(self, site, pages):

        written_files = []

        header_html = self.minifier.minify(self._read(site.header))
        written_files.append(
            self._safe_write(
                f"assets/sites/{slugify(site.name)}/header.json",
                json.dumps(self.converter.convert_header(site, header_html)),
            )
        )

        footer_html = self.minifier.minify(self._read(site.footer))
        written_files.append(
            self._safe_write(
                f"assets/sites/{slugify(site.name)}/footer.json",
                json.dumps(self.converter.convert_footer(site, footer_html)),
            )
        )

        for page in pages:
            page_html = self.minifier.minify(self._read(page.html))
            written_files.append(
                self._safe_write(
                    f"assets/sites/{slugify(site.name)}/pages/{page.slug}.json",
                    json.dumps(self.converter.convert_page(site, page, page_html)),
                )
            )

        self._cleanup_orphan_pages(site, [p.slug for p in pages])
        return written_files

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

    def _find_matching_version(self, site, header_hash, footer_hash, page_hashes):
        return site.publish_versions.filter(
            header_hash=header_hash,
            footer_hash=footer_hash,
            page_hashes=page_hashes,
        ).first()

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

        header_hash, footer_hash, page_hashes = self._snapshot_source(site, pages)
        existing_version = self._find_matching_version(
            site, header_hash, footer_hash, page_hashes
        )

        written_files = self._generate_and_write_output(site, pages)

        with transaction.atomic():
            version = existing_version or SitePublishVersion.objects.create(
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

    def has_unpublished_changes(self, site):
        """True if live editable source differs from what's currently published."""
        current = site.current_published_version
        if not current:
            return True

        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )
        header_hash, footer_hash, page_hashes = self._snapshot_source(site, pages)

        return (
            header_hash != current.header_hash
            or footer_hash != current.footer_hash
            or page_hashes != current.page_hashes
        )

    def restore_source(self, site, version):
        if version.site_id != site.id:
            raise PublishValidationError(
                "This publish version does not belong to this site."
            )

        pages_by_slug = {p.slug: p for p in site.pages.all()}
        missing_slugs = sorted(
            slug for slug in version.page_hashes if slug not in pages_by_slug
        )

        if missing_slugs:
            raise PublishValidationError(
                "Cannot restore version "
                f"{version.version_number}: page(s) {', '.join(missing_slugs)} "
                "existed at that version but have since been deleted."
            )

        header_content = self.blobs.read(version.header_hash)
        footer_content = self.blobs.read(version.footer_hash)
        page_contents = {
            slug: self.blobs.read(page_hash)
            for slug, page_hash in version.page_hashes.items()
        }

        # Restore site header/footer without immediately saving the model so we
        # can update both fields in a single atomic save.
        site.header.save(
            "header.html", ContentFile(header_content.encode("utf-8")), save=False
        )
        site.footer.save(
            "footer.html", ContentFile(footer_content.encode("utf-8")), save=False
        )

        # Restore page HTML files and preserve only the pages that existed
        # in the requested version. Any newer pages are disabled so they are
        # excluded from the republished output.
        target_slugs = set(page_contents)
        pages_to_save = []
        for slug, page in pages_by_slug.items():
            if slug in target_slugs:
                page.html.save(
                    f"{slug}.html",
                    ContentFile(page_contents[slug].encode("utf-8")),
                    save=False,
                )
                page.enable = True
                pages_to_save.append((page, ["html", "enable"]))
            else:
                if page.enable:
                    page.enable = False
                    page.status = Page.Status.DRAFT
                    pages_to_save.append((page, ["enable", "status"]))

        with transaction.atomic():
            site.save(update_fields=["header", "footer"])
            for page, update_fields in pages_to_save:
                page.save(update_fields=update_fields)
