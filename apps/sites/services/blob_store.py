import hashlib

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class BlobStore:
    BASE_DIR = "assets/blobs"

    def _as_bytes(self, content):
        return content.encode("utf-8") if isinstance(content, str) else bytes(content)

    def hash_content(self, content) -> str:
        return hashlib.sha256(self._as_bytes(content)).hexdigest()

    def _blob_path(self, content_hash: str) -> str:
        return f"{self.BASE_DIR}/{content_hash[:2]}/{content_hash}"

    def put(self, content) -> str:
        """Stores content if not already present, returns its hash."""
        content_hash = self.hash_content(content)
        blob_path = self._blob_path(content_hash)
        if not default_storage.exists(blob_path):
            default_storage.save(blob_path, ContentFile(self._as_bytes(content)))
        return content_hash

    def read(self, content_hash: str) -> bytes:
        with default_storage.open(self._blob_path(content_hash), "rb") as f:
            return f.read()

    def exists(self, content_hash: str) -> bool:
        return default_storage.exists(self._blob_path(content_hash))
