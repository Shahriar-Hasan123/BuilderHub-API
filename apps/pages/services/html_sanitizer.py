import bleach
from apps.pages.constants import ALLOWED_TAGS, ALLOWED_ATTRS, ALLOWED_PROTOCOLS


class HTMLSanitizer:
    """Cleans HTML to prevent XSS by allowing only safe tags, attributes, and protocols."""

    def sanitize(self, html: str) -> str:
        return bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRS,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
        )
