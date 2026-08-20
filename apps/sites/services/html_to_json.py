class HTMLToJSONConverter:
    def convert_header(self, site, html):
        return {
            "site_id": site.id,
            "site_name": site.name,
            "type": "header",
            "html": html,
            "favicon": site.favicon.name if site.favicon else None,
            "logo": site.logo.name if site.logo else None,
            "thumbnail": site.thumbnail.name if site.thumbnail else None,
            "global_css": site.global_css.name if site.global_css else None,
        }

    def convert_footer(self, site, html):
        return {
            "site_id": site.id,
            "site_name": site.name,
            "type": "footer",
            "html": html,
        }

    def convert_page(self, site, page, html):
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
            "css": page.css.name if page.css else None,
            "hero_image": page.hero_image.name if page.hero_image else None,
            "canonical_url": page.canonical_url,
            "created_by": page.created_by_id,
            "updated_by": page.updated_by_id,
        }
