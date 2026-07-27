from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.sites.models import Site

User = get_user_model()


class SiteListCreateAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="site_owner", password="pass12345"
        )
        self.list_create_url = reverse("site-list-create")

    def _auth(self, username, password):
        response = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_list_all_sites(self):
        Site.objects.create(user=self.owner, name="Visible To Everyone")
        self._auth("site_owner", "pass12345")
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_creating_site_sets_requesting_user_as_owner(self):
        self._auth("site_owner", "pass12345")
        response = self.client.post(self.list_create_url, {"name": "New Site"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        site = Site.objects.get(pk=response.data["id"])
        self.assertEqual(site.user, self.owner)
        self.assertEqual(site.updated_by, self.owner)


class SiteDetailAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="detail_owner", password="pass12345"
        )
        self.editor = User.objects.create_user(
            username="detail_editor", password="pass12345"
        )
        self.stranger = User.objects.create_user(
            username="detail_stranger", password="pass12345"
        )

        can_edit_perm = Permission.objects.get(codename="can_edit_site")
        self.editor.user_permissions.add(can_edit_perm)

        self.site = Site.objects.create(user=self.owner, name="Detail Test Site")
        self.detail_url = reverse("site-detail", kwargs={"pk": self.site.id})

    def _auth(self, username, password):
        response = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_any_authenticated_user_can_read(self):
        self._auth("detail_stranger", "pass12345")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update(self):
        self._auth("detail_owner", "pass12345")
        response = self.client.patch(self.detail_url, {"name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_with_global_permission_can_update(self):
        self._auth("detail_editor", "pass12345")
        response = self.client.patch(self.detail_url, {"name": "Renamed By Editor"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_without_permission_cannot_update(self):
        self._auth("detail_stranger", "pass12345")
        response = self.client.patch(self.detail_url, {"name": "Hack Attempt"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        self._auth("detail_owner", "pass12345")
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Site.objects.filter(pk=self.site.id).exists())

    def test_nonexistent_site_returns_404(self):
        self._auth("detail_owner", "pass12345")
        missing_url = reverse("site-detail", kwargs={"pk": 999999})
        response = self.client.get(missing_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
