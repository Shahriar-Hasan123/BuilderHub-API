from django.db.models import Max

from apps.sites.models import SitePublishVersion


class PublishVersionService:
    def __init__(self, blobs, assets, content):
        self.blobs = blobs
        self.assets = assets
        self.content = content

    def hashes(self, site, pages, request=None):
        header_json, footer_json, page_jsons = self.content.build_json(
            site, pages, request
        )
        header_hash = self.blobs.put(header_json.encode("utf-8"))
        footer_hash = self.blobs.put(footer_json.encode("utf-8"))
        page_hashes = {
            slug: self.blobs.put(content.encode("utf-8"))
            for slug, content in page_jsons.items()
        }
        asset_hashes = self.assets.snapshot_assets(site, pages)
        return header_json, footer_json, page_jsons, header_hash, footer_hash, page_hashes, asset_hashes

    def next_number(self, site):
        latest = site.publish_versions.aggregate(Max("version_number"))[
            "version_number__max"
        ]
        return (latest or 0) + 1

    def find_or_create(self, site, hashes, user=None):
        header_hash, footer_hash, page_hashes, asset_hashes = hashes
        existing = site.publish_versions.filter(
            header_hash=header_hash,
            footer_hash=footer_hash,
            page_hashes=page_hashes,
            asset_hashes=asset_hashes,
        ).first()
        return existing or SitePublishVersion.objects.create(
            site=site,
            version_number=self.next_number(site),
            header_hash=header_hash,
            footer_hash=footer_hash,
            page_hashes=page_hashes,
            asset_hashes=asset_hashes,
            published_by=user,
        )
