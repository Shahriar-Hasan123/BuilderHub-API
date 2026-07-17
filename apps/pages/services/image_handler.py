import base64
import re
import uuid
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class ImageHandler:
    """Extracts base64-embedded images from exported HTML, saves them to
    media storage, and rewrites <img> src attributes to point locally."""
    
    DATA_URI_PATTERN = re.compile(r"^data:image/(?P<ext>\w+);base64,(?P<data>.+)$")

    def process(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        
        for img in soup.find_all("img"):
            src = img.get("src", "")
            match = self.DATA_URI_PATTERN.match(src)
            if not match:
                continue
            
            ext = match.group("ext")
            raw_data = base64.b64decode(match.group("data"))
            filename = f"pages/images/{uuid.uuid4().hex}.{ext}"
            
            saved_path = default_storage.save(filename, ContentFile(raw_data))
            img["src"] = default_storage.url(saved_path)
            
        return str(soup)
