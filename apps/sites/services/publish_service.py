import json

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from apps.core.exceptions import PublishValidationError
from apps.pages.models import Page
from apps.sites.services.html_minifier import HTMLMinifier
from apps.sites.services.html_to_json import HTMLToJSONConverter


class PublishService:
    def __init__(self):
        self.minifier = HTMLMinifier()
        self.converter = HTMLToJSONConverter()

    def _validate_readiness(self, site, pages):
        if not site.header or not site.footer:
            raise PublishValidationError("Both header and footer HTML are required to publish.")
        if not pages:
            raise PublishValidationError("Site must have at least one enabled page with HTML to publish.")
        if not self._read(site.header).strip():
            raise PublishValidationError("Header file is empty.")
        if not self._read(site.footer).strip():
            raise PublishValidationError("Footer file is empty.")

    def _read(self, file_field):
        with file_field.open("r") as f:
            return f.read()

    def _build_artifacts(self, site, pages):
        artifacts = []

        header_html = self.minifier.minify(self._read(site.header))
        artifacts.append(
            (
                f"assets/sites/{site.id}/header.json",
                json.dumps(self.converter.convert_header(site, header_html)),
            )
        )

        footer_html = self.minifier.minify(self._read(site.footer))
        artifacts.append(
            (
                f"assets/sites/{site.id}/footer.json",
                json.dumps(self.converter.convert_footer(site, footer_html)),
            )
        )

        for page in pages:
            page_html = self.minifier.minify(self._read(page.html))
            artifacts.append(
                (
                    f"assets/sites/{site.id}/pages/{page.slug}.json",
                    json.dumps(self.converter.convert_page(site, page, page_html)),
                )
            )

        return artifacts

    def _write_json(self, relative_path, data):
        content = json.dumps(data, indent=2)
        if default_storage.exists(relative_path):
            default_storage.delete(relative_path)
        default_storage.save(relative_path, ContentFile(content.encode("utf-8")))
        return relative_path
    
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
    
    def _cleanup_orphan_pages(self, site, pages):
        pages_dir = f"assets/sites/{site.id}/pages/"
        expected_filenames = {f"{page.slug}.json" for page in pages}

        try:
            _, filenames = default_storage.listdir(pages_dir)
        except FileNotFoundError:
            return

        for filename in filenames:
            if filename not in expected_filenames and not filename.endswith(".tmp"):
                default_storage.delete(f"{pages_dir}{filename}")
                
    def publish(self, site):
        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )
        self._validate_readiness(site, pages)

        artifacts = self._build_artifacts(site, pages)
        
        written_files = [self._safe_write(path, content) for path, content in artifacts]   
          
        self._cleanup_orphan_pages(site, pages)
        
        with transaction.atomic():
            site.status = site.Status.PUBLISHED
            site.save(update_fields=["status"])
            Page.objects.filter(pk__in=[p.pk for p in pages]).update(status=Page.Status.PUBLISHED)

        return {
            "site_id": site.id,
            "status": "published",
            "assets_path": f"assets/sites/{site.id}/",
            "files": written_files,
        }
        
