import requests
from apps.pages.exceptions import GoogleDocsFetchError


class GoogleDocsClient:
    EXPORT_URL = "https://docs.google.com/document/d/{doc_id}/export"

    def export_tab_html(self, doc_id: str, tab_id: str) -> str:
        try:
            url = self.EXPORT_URL.format(doc_id=doc_id)
            response = requests.get(
                url, params={"format": "html", "tab": tab_id}, timeout=15
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            raise GoogleDocsFetchError(
                f"Failed to fetch tab '{tab_id}' from doc '{doc_id}': {exc}"
            ) from exc

        return response.text
