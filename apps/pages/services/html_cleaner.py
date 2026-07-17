from bs4 import BeautifulSoup


class HTMLCleaner:

    ALLOWED_ATTRS = {
        "a": ["href", "title", "target", "rel"],
        "img": ["src", "alt", "title", "width", "height"],
        "td": ["colspan", "rowspan"],
        "th": ["colspan", "rowspan"],
    }

    def clean(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove unnecessary tags
        for tag in soup.find_all(["style", "meta", "head", "script"]):
            tag.decompose()

        # Remove unwanted attributes
        for tag in soup.find_all(True):
            allowed = self.ALLOWED_ATTRS.get(tag.name, [])
            tag.attrs = {
                key: value for key, value in tag.attrs.items() if key in allowed
            }

        # Unwrap spans
        for span in soup.find_all("span"):
            span.unwrap()

        # Remove empty tags (preserve img/br and their containers)
        for tag in soup.find_all():
            if tag.get_text(strip=True):
                continue
            if tag.name in ["img", "br"]:
                continue
            if tag.find("img") or tag.find("br"):
                continue
            tag.decompose()

        return str(soup.body or soup)
