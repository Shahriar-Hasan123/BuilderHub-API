from django.core.management.base import BaseCommand, CommandError

from apps.pages.services.blog_importer import BlogImporterService
from apps.pages.services.google_docs_client import GoogleDocsClient
from apps.pages.services.html_cleaner import HTMLCleaner
from apps.pages.services.html_sanitizer import HTMLSanitizer
from apps.pages.services.image_handler import ImageHandler
from apps.sites.models import Site


class Command(BaseCommand):
    help = "Import blogs from a public Google Docs document, one tab per blog."

    def add_arguments(self, parser):
        parser.add_argument("--doc-id", required=True, help="Google Docs document ID")
        parser.add_argument(
            "--tabs",
            required=True,
            help="Comma-separated tab IDs, e.g. t.0,t.abc123",
        )
        parser.add_argument("--site-id", required=True, type=int, help="Target Site ID")

    def handle(self, *args, **options):
        doc_id = options["doc_id"]
        tab_ids = [t.strip() for t in options["tabs"].split(",") if t.strip()]

        try:
            site = Site.objects.get(pk=options["site_id"])
        except Site.DoesNotExist:
            raise CommandError(f"Site with id {options['site_id']} does not exist.")

        importer = BlogImporterService(
            docs_client=GoogleDocsClient(),
            image_handler=ImageHandler(),
            html_cleaner=HTMLCleaner(),
            html_sanitizer=HTMLSanitizer(),
        )

        results = importer.run(doc_id=doc_id, tab_ids=tab_ids, site=site)
        self._print_summary(results)

    def _print_summary(self, results):
        counts = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        for result in results:
            counts[result.status] += 1
            marker = {
                "created": self.style.SUCCESS("✓ created"),
                "updated": self.style.SUCCESS("✓ updated"),
                "skipped": self.style.WARNING("→ skipped"),
                "failed": self.style.ERROR("✗ failed"),
            }[result.status]
            label = result.title or result.tab_id
            line = f"{marker}  {label}"
            if result.reason:
                line += f"  ({result.reason})"
            self.stdout.write(line)

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Done — created: {counts['created']}, updated: {counts['updated']}, "
                f"skipped: {counts['skipped']}, failed: {counts['failed']}"
            )
        )
