from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.services.resource_lock import SiteLockService
from apps.pages.models import Page
from apps.sites.models import Site

User = get_user_model()


class PageListCreateAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="page_view_owner", password="pass12345"
        )
        self.editor = User.objects.create_user(
            username="page_view_editor", password="pass12345"
        )
        self.stranger = User.objects.create_user(
            username="page_view_stranger", password="pass12345"
        )

        can_edit_perm = Permission.objects.get(codename="can_edit_site")
        self.editor.user_permissions.add(can_edit_perm)

        self.site = Site.objects.create(user=self.owner, name="Page View Test Site")
        self.addCleanup(cache.delete, f"lock:site:{self.site.id}")
        self.list_create_url = reverse(
            "page-list-create", kwargs={"site_pk": self.site.id}
        )

    def _auth(self, username, password):
        response = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_any_authenticated_user_can_list_pages(self):
        Page.objects.create(
            site=self.site,
            title="Visible Page",
            slug="visible-page",
            created_by=self.owner,
        )
        self._auth("page_view_stranger", "pass12345")
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_owner_can_create_page(self):
        self._auth("page_view_owner", "pass12345")
        response = self.client.post(self.list_create_url, {"title": "New Page"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        page = Page.objects.get(pk=response.data["id"])
        self.assertEqual(page.site, self.site)
        self.assertEqual(page.created_by, self.owner)
        self.assertEqual(page.slug, "new-page")

    def test_user_without_permission_cannot_create_page(self):
        self._auth("page_view_stranger", "pass12345")
        response = self.client.post(self.list_create_url, {"title": "Blocked Page"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_creating_page_locks_the_parent_site(self):
        self._auth("page_view_owner", "pass12345")
        self.client.post(self.list_create_url, {"title": "First Blog Post"})

        self._auth("page_view_editor", "pass12345")
        response = self.client.post(self.list_create_url, {"title": "Second Blog Post"})
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)

    def test_listing_pages_does_not_trigger_lock(self):
        self._auth("page_view_stranger", "pass12345")
        self.client.get(self.list_create_url)

        lock_status = SiteLockService().status(self.site.id)
        self.assertFalse(lock_status["locked"])

    def test_lock_on_one_site_does_not_affect_another(self):
        other_site = Site.objects.create(user=self.owner, name="Other Independent Site")
        self.addCleanup(cache.delete, f"lock:site:{other_site.id}")
        other_url = reverse("page-list-create", kwargs={"site_pk": other_site.id})

        self._auth("page_view_owner", "pass12345")
        self.client.post(self.list_create_url, {"title": "Locks Site A"})

        self._auth("page_view_editor", "pass12345")
        response = self.client.post(other_url, {"title": "Should work on Site B"})
        self.assertNotEqual(response.status_code, status.HTTP_423_LOCKED)

    def test_nonexistent_site_returns_404(self):
        self._auth("page_view_owner", "pass12345")
        missing_url = reverse("page-list-create", kwargs={"site_pk": 999999})
        response = self.client.get(missing_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PageDetailAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="page_detail_owner", password="pass12345"
        )
        self.editor = User.objects.create_user(
            username="page_detail_editor", password="pass12345"
        )
        self.stranger = User.objects.create_user(
            username="page_detail_stranger", password="pass12345"
        )

        can_edit_perm = Permission.objects.get(codename="can_edit_site")
        self.editor.user_permissions.add(can_edit_perm)

        self.site = Site.objects.create(user=self.owner, name="Page Detail Test Site")
        self.addCleanup(cache.delete, f"lock:site:{self.site.id}")
        self.page = Page.objects.create(
            site=self.site,
            title="Detail Page",
            slug="detail-page",
            created_by=self.owner,
        )
        self.detail_url = reverse(
            "page-detail", kwargs={"site_pk": self.site.id, "pk": self.page.id}
        )

    def _auth(self, username, password):
        response = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_any_authenticated_user_can_read(self):
        self._auth("page_detail_stranger", "pass12345")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update(self):
        self._auth("page_detail_owner", "pass12345")
        response = self.client.patch(self.detail_url, {"title": "Updated Title"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_with_global_permission_can_update(self):
        self._auth("page_detail_editor", "pass12345")
        response = self.client.patch(self.detail_url, {"title": "Editor Updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_without_permission_cannot_update(self):
        self._auth("page_detail_stranger", "pass12345")
        response = self.client.patch(self.detail_url, {"title": "Hack Attempt"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_updating_page_locks_the_parent_site(self):
        self._auth("page_detail_owner", "pass12345")
        self.client.patch(self.detail_url, {"title": "Locked Update"})

        self._auth("page_detail_editor", "pass12345")
        response = self.client.patch(self.detail_url, {"title": "Blocked Update"})
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)

    def test_owner_can_delete(self):
        self._auth("page_detail_owner", "pass12345")
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Page.objects.filter(pk=self.page.id).exists())

    def test_page_from_wrong_site_returns_404(self):
        other_site = Site.objects.create(user=self.owner, name="Unrelated Site")
        self._auth("page_detail_owner", "pass12345")
        wrong_url = reverse(
            "page-detail", kwargs={"site_pk": other_site.id, "pk": self.page.id}
        )
        response = self.client.get(wrong_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
