import hashlib

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class BloobStore:
    BASE_DIR = "assets/blobs"

    def hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _blob_path(self, content_hash: str) -> str:
        return f"{self.BASE_DIR}/{content_hash[:2]}/{content_hash}"

    def put(self, content: str) -> str:
        """Stores content if not already present, returns its hash."""
        content_hash = self.hash_content(content)
        blob_path = self._blob_path(content_hash)
        if not default_storage.exists(blob_path):
            default_storage.save(blob_path, ContentFile(content.encode("utf-8")))
        return content_hash

    def read(self, content_hash: str) -> str:
        with default_storage.open(self._blob_path(content_hash), "r") as f:
            return f.read()

    def exists(self, content_hash: str) -> bool:
        return default_storage.exists(self._blob_path(content_hash))
