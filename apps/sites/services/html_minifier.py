import re

from bs4 import BeautifulSoup, Comment

PRESERVE_WHITESPACE_TAGS = {"script", "style", "pre", "textarea"}


class HTMLMinifier:
    """Repairs malformed HTML (unclosed tags, broken structure) by parsing
    and re-serializing it, then cleans up whitespace in ordinary text:
    whitespace-only text nodes (pure indentation between tags) are removed
    entirely, and text nodes with real content have internal whitespace
    runs collapsed to a single space. Content inside <script>, <style>,
    <pre>, and <textarea> is left completely untouched, since altering
    whitespace there can break code or meaningful formatting. This is a
    structural/whitespace cleanup only — it does NOT strip tags, apply a
    security allowlist, or remove attributes."""

    def minify(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for text_node in soup.find_all(string=True):
            if isinstance(text_node, Comment):
                continue
            if self._is_inside_preserved_tag(text_node):
                continue

            if not text_node.strip():
                text_node.extract()
            else:
                collapsed = re.sub(r"\s+", " ", str(text_node))
                text_node.replace_with(collapsed)

        root = soup.body or soup
        return str(root).strip()

    def _is_inside_preserved_tag(self, text_node) -> bool:
        for parent in text_node.parents:
            if getattr(parent, "name", None) in PRESERVE_WHITESPACE_TAGS:
                return True
        return False
