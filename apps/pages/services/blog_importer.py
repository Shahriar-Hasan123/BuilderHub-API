from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.utils.text import slugify

from apps.pages.dto import ImportResult
from apps.pages.exceptions import GoogleDocsFetchError
from apps.pages.models import Page
from apps.pages.services.google_docs_client import GoogleDocsClient
from apps.pages.services.html_cleaner import HTMLCleaner
from apps.pages.services.html_sanitizer import HTMLSanitizer
from apps.pages.services.image_handler import ImageHandler


class BlogImporterService:
    def __init__(
        self,
        docs_client: GoogleDocsClient,
        image_handler: ImageHandler,
        html_cleaner: HTMLCleaner,
        html_sanitizer: HTMLSanitizer,
    ):
        self.docs_client = docs_client
        self.image_handler = image_handler
        self.html_cleaner = html_cleaner
        self.html_sanitizer = html_sanitizer

    def run(self, doc_id: str, tab_ids: list[str], site) -> list[ImportResult]:
        return [self._import_tab(doc_id, tab_id, site) for tab_id in tab_ids]

    def _import_tab(self, doc_id: str, tab_id: str, site) -> ImportResult:
        try:
            raw_html = self.docs_client.export_tab_html(doc_id, tab_id)
        except GoogleDocsFetchError as exc:
            return ImportResult(tab_id=tab_id, status="failed", reason=str(exc))

        title = self._extract_title(raw_html)
        if not title:
            return ImportResult(
                tab_id=tab_id, status="failed", reason="No <h1> title found in tab"
            )

        html_with_local_images = self.image_handler.process(raw_html)
        cleaned_html = self.html_cleaner.clean(html_with_local_images)
        safe_html = self.html_sanitizer.sanitize(cleaned_html)
        slug = slugify(title)
        slug_max_length = Page._meta.get_field("slug").max_length or 100
        slug = slug[:slug_max_length]

        page, created = Page.objects.get_or_create(
            site=site,
            slug=slug,
            defaults={
                "title": title,
                "page_type": Page.PageType.BLOG,
                "status": Page.Status.DRAFT,
                "created_by": site.user,
                "updated_by": site.user,
            },
        )

        if not created:
            page.title = title
            page.updated_by = site.user
            if page.html:
                page.html.delete(save=False)

        page.html.save(
            f"{slug}.html", ContentFile(safe_html.encode("utf-8")), save=False
        )
        page.save()

        return ImportResult(
            tab_id=tab_id, title=title, status="created" if created else "updated"
        )

    def _extract_title(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        if not h1:
            return ""
        text = h1.get_text(strip=True)
        h1.decompose()
        return text
