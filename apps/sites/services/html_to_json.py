class HTMLToJSONConverter:
    def _url(self, path, request=None):
        if not path or request is None:
            return path
        return request.build_absolute_uri(f"/media/{path}")

    def convert_header(self, site, html, request=None):
        return {
            "site_id": site.id,
            "site_name": site.name,
            "type": "header",
            "html": html,
            "favicon": self._url(site.favicon.name, request) if site.favicon else None,
            "logo": self._url(site.logo.name, request) if site.logo else None,
            "thumbnail": self._url(site.thumbnail.name, request) if site.thumbnail else None,
            "global_css": self._url(site.global_css.name, request) if site.global_css else None,
        }

    def convert_footer(self, site, html, request=None):
        return {
            "site_id": site.id,
            "site_name": site.name,
            "type": "footer",
            "html": html,
        }

    def convert_page(self, site, page, html, request=None):
        return {
            "site_id": site.id,
            "page_id": page.id,
            "slug": page.slug,
            "title": page.title,
            "status": page.status,
            "enable": page.enable,
            "meta_description": page.meta_description,
            "page_type": page.page_type,
            "html": html,
            "css": self._url(page.css.name, request) if page.css else None,
            "hero_image": self._url(page.hero_image.name, request) if page.hero_image else None,
            "canonical_url": page.canonical_url,
            "created_by": page.created_by_id,
            "updated_by": page.updated_by_id,
        }
