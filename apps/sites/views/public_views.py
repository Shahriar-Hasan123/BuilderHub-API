import json

from django.core.files.storage import default_storage
from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify
from rest_framework.views import APIView


class PublishedPageView(APIView):
    authentication_classes = []
    permission_classes = []

    def read_json(self, path):
        if not default_storage.exists(path):
            raise Http404("Published content was not found.")

        try:
            with default_storage.open(path, "r") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise Http404("Published content is invalid.") from exc

    def get(self, request, site_slug, page_slug=None):
        site_slug = slugify(site_slug)
        base_path = f"published/sites/{site_slug}"

        header = self.read_json(f"{base_path}/header.json")

        footer = self.read_json(f"{base_path}/footer.json")

        if page_slug is None:
            try:
                _, filenames = default_storage.listdir(f"{base_path}/pages/")
            except FileNotFoundError as exc:
                raise Http404("No published pages were found.") from exc

            page_files = sorted(
                filename for filename in filenames if filename.endswith(".json")
            )

            if not page_files:
                raise Http404("No published pages were found.")

            page_slug = page_files[0].removesuffix(".json")

        page_slug = slugify(page_slug)

        page = self.read_json(f"{base_path}/pages/{page_slug}.json")

        return render(
            request,
            "published_site.html",
            {
                "header": header,
                "page": page,
                "footer": footer,
            },
        )
