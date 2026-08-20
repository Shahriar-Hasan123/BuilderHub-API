from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import slugify


class PublishAssetService:
    def __init__(self, blobs):
        self.blobs = blobs

    def snapshot_file(self, file_field):
        if not file_field:
            return None
        with file_field.open("rb") as file:
            content_hash = self.blobs.put(file.read())
        return {
            "hash": content_hash,
            "name": file_field.name.rsplit("/", 1)[-1],
        }

    def snapshot_assets(self, site, pages):
        assets = {"site.global_css": self.snapshot_file(site.global_css)}
        for page in pages:
            assets[f"page:{page.slug}:css"] = self.snapshot_file(page.css)
        return assets

    def restore_file_content(self, instance, field_name, filename, content):
        field = getattr(instance, field_name)
        path = field.field.generate_filename(instance, filename)
        previous_path = field.name
        previous_content = None
        if default_storage.exists(path):
            with default_storage.open(path, "rb") as file:
                previous_content = file.read()
            default_storage.delete(path)
        try:
            default_storage.save(path, ContentFile(content))
        except Exception:
            if previous_content is not None:
                default_storage.save(path, ContentFile(previous_content))
            raise
        if previous_path and previous_path != path and default_storage.exists(previous_path):
            default_storage.delete(previous_path)
        field.name = path

    def restore_file(self, instance, field_name, asset):
        if asset is None:
            field = getattr(instance, field_name)
            if field:
                field.delete(save=False)
            setattr(instance, field_name, None)
            return
        self.restore_file_content(
            instance,
            field_name,
            asset["name"],
            self.blobs.read(asset["hash"]),
        )

    def restore_file_reference(self, instance, field_name, path):
        getattr(instance, field_name).name = path or None

    def replace_published_file(self, path, content):
        content_bytes = content.encode("utf-8")
        previous_bytes = None
        if default_storage.exists(path):
            with default_storage.open(path, "rb") as file:
                previous_bytes = file.read()
            default_storage.delete(path)
        try:
            default_storage.save(path, ContentFile(content_bytes))
        except Exception:
            if default_storage.exists(path):
                default_storage.delete(path)
            if previous_bytes is not None:
                default_storage.save(path, ContentFile(previous_bytes))
            raise

    def restore_published_files(self, previous_files):
        for path, content in previous_files.items():
            if content is None:
                if default_storage.exists(path):
                    default_storage.delete(path)
            else:
                if default_storage.exists(path):
                    default_storage.delete(path)
                default_storage.save(path, ContentFile(content))

    def replace_published_files(self, site, header_json, footer_json, page_jsons):
        base_path = f"published/sites/{slugify(site.name)}"
        contents = {
            f"{base_path}/header.json": header_json,
            f"{base_path}/footer.json": footer_json,
        }
        contents.update(
            {
                f"{base_path}/pages/{slug}.json": content
                for slug, content in page_jsons.items()
            }
        )
        previous_files = {}
        for path, content in contents.items():
            if default_storage.exists(path):
                with default_storage.open(path, "rb") as file:
                    previous_files[path] = file.read()
            else:
                previous_files[path] = None
            self.replace_published_file(path, content)
        return previous_files

    def materialize_version(self, site, version):
        header_json = self.blobs.read(version.header_hash).decode("utf-8")
        footer_json = self.blobs.read(version.footer_hash).decode("utf-8")
        page_jsons = {
            slug: self.blobs.read(page_hash).decode("utf-8")
            for slug, page_hash in version.page_hashes.items()
        }
        previous_files = self.replace_published_files(
            site,
            header_json,
            footer_json,
            page_jsons,
        )
        previous_files.update(
            self.cleanup_orphan_pages(site, page_jsons.keys())
        )
        return previous_files

    def delete_page_files(self, page):
        for field_name in ("html", "css", "hero_image"):
            field = getattr(page, field_name)
            if field and field.name and default_storage.exists(field.name):
                default_storage.delete(field.name)

    def cleanup_orphan_pages(self, site, expected_slugs):
        pages_dir = f"published/sites/{slugify(site.name)}/pages/"
        expected_filenames = {f"{slug}.json" for slug in expected_slugs}
        try:
            _, filenames = default_storage.listdir(pages_dir)
        except FileNotFoundError:
            return {}

        deleted_files = {}
        for filename in filenames:
            if filename not in expected_filenames and not filename.endswith(".tmp"):
                path = f"{pages_dir}{filename}"
                with default_storage.open(path, "rb") as file:
                    deleted_files[path] = file.read()
                default_storage.delete(path)
        return deleted_files

    def public_url(self, path, request=None):
        relative_url = f"{settings.MEDIA_URL.rstrip('/')}/{path.lstrip('/')}"
        return request.build_absolute_uri(relative_url) if request else relative_url

    def snapshot_response(self, site, page_jsons, request=None):
        base_path = f"published/sites/{slugify(site.name)}"
        pages = [
            {
                "slug": slug,
                "name": f"{slug}.json",
                "url": self.public_url(
                    f"{base_path}/pages/{slug}.json", request
                ),
            }
            for slug in page_jsons
        ]
        return {
            "directory": self.public_url(f"{base_path}/", request),
            "files": {
                "header": {
                    "name": "header.json",
                    "url": self.public_url(f"{base_path}/header.json", request),
                },
                "footer": {
                    "name": "footer.json",
                    "url": self.public_url(f"{base_path}/footer.json", request),
                },
                "pages": pages,
            },
        }
