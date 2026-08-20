import json

from apps.core.exceptions import PublishValidationError
from apps.sites.services.html_minifier import HTMLMinifier
from apps.sites.services.html_to_json import HTMLToJSONConverter


class PublishContentService:
    def __init__(self):
        self.minifier = HTMLMinifier()
        self.converter = HTMLToJSONConverter()

    def read(self, file_field):
        with file_field.open("r") as file:
            return file.read()

    def validate_readiness(self, site, pages):
        if not site.header or not site.footer:
            raise PublishValidationError(
                "Both header and footer HTML are required to publish."
            )
        if not pages:
            raise PublishValidationError(
                "Site must have at least one enabled page with HTML to publish."
            )
        if not self.read(site.header).strip():
            raise PublishValidationError("Header file is empty.")
        if not self.read(site.footer).strip():
            raise PublishValidationError("Footer file is empty.")

    def build_json(self, site, pages, request=None):
        header_html = self.minifier.minify(self.read(site.header))
        header_json = json.dumps(
            self.converter.convert_header(site, header_html, request),
            indent=2,
        ) + "\n"

        footer_html = self.minifier.minify(self.read(site.footer))
        footer_json = json.dumps(
            self.converter.convert_footer(site, footer_html, request),
            indent=2,
        ) + "\n"

        page_jsons = {
            page.slug: json.dumps(
                self.converter.convert_page(
                    site, page, self.minifier.minify(self.read(page.html)), request
                ),
                indent=2,
            ) + "\n"
            for page in pages
        }
        return header_json, footer_json, page_jsons
