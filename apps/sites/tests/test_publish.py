import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.pages.models import Page
from apps.sites.models import Site

User = get_user_model()


def html_file(name, content):
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/html")


class SitePublishAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="publish_owner", password="pass12345"
        )
        self.editor = User.objects.create_user(
            username="publish_editor", password="pass12345"
        )
        self.stranger = User.objects.create_user(
            username="publish_stranger", password="pass12345"
        )

        can_edit_perm = Permission.objects.get(codename="can_edit_site")
        self.editor.user_permissions.add(can_edit_perm)

        self.site = Site.objects.create(user=self.owner, name="Publish Test Site")
        self.addCleanup(cache.delete, f"lock:site:{self.site.id}")
        self.publish_url = reverse("site-publish", kwargs={"pk": self.site.id})

    def _auth(self, username, password):
        response = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def _add_header_footer(self):
        self.site.header = html_file("header.html", "<header>  <p>Head</p>  </header>")
        self.site.footer = html_file("footer.html", "<footer><li>Broken")
        self.site.save()

    def _add_page(self, title="Home"):
        return Page.objects.create(
            site=self.site,
            title=title,
            slug=title.lower().replace(" ", "-"),
            enable=True,
            html=html_file(f"{title}.html", f"<main>   <h1>{title}</h1>   </main>"),
            created_by=self.owner,
        )

    # ---- Happy path ----

    def test_publish_success_creates_json_assets_and_updates_status(self):
        self._add_header_footer()
        page = self._add_page("Home")

        self._auth("publish_owner", "pass12345")
        response = self.client.post(self.publish_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "published")
        self.assertEqual(len(response.data["files"]), 3)  # header + footer + 1 page

        self.site.refresh_from_db()
        page.refresh_from_db()
        self.assertEqual(self.site.status, Site.Status.PUBLISHED)
        self.assertEqual(page.status, Page.Status.PUBLISHED)

        for relative_path in response.data["files"]:
            self.assertTrue(default_storage.exists(relative_path))

    def test_whitespace_and_malformed_html_is_cleaned(self):
        self._add_header_footer()
        self._add_page("Home")

        self._auth("publish_owner", "pass12345")
        response = self.client.post(self.publish_url)

        header_path = next(
            f for f in response.data["files"] if f.endswith("header.json")
        )
        with default_storage.open(header_path) as f:
            data = json.loads(f.read())

        self.assertNotIn("\n", data["html"])
        self.assertNotIn("  ", data["html"])
        self.assertIn("><", data["html"])

    # ---- Validation (400) ----

    def test_missing_header_or_footer_returns_400(self):
        self._add_page("Home")  # no header/footer set

        self._auth("publish_owner", "pass12345")
        response = self.client.post(self.publish_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_enabled_pages_returns_400(self):
        self._add_header_footer()  # header/footer set, but no pages

        self._auth("publish_owner", "pass12345")
        response = self.client.post(self.publish_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- Authorization ----

    def test_non_owner_without_permission_returns_403(self):
        self._add_header_footer()
        self._add_page("Home")

        self._auth("publish_stranger", "pass12345")
        response = self.client.post(self.publish_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_global_permission_can_publish(self):
        self._add_header_footer()
        self._add_page("Home")

        self._auth("publish_editor", "pass12345")
        response = self.client.post(self.publish_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---- Locking ----

    def test_locked_by_another_user_returns_423(self):
        self._add_header_footer()
        self._add_page("Home")

        self._auth("publish_owner", "pass12345")
        self.client.post(reverse("site-lock", kwargs={"pk": self.site.id}))

        self._auth("publish_editor", "pass12345")
        response = self.client.post(self.publish_url)
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)
