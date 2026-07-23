from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.sites.models import Site
from apps.core.services.resource_lock import SiteLockService

User = get_user_model()


class SiteLockAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="lock_owner", password="pass12345")
        self.editor = User.objects.create_user(username="lock_editor", password="pass12345")
        self.stranger = User.objects.create_user(username="lock_stranger", password="pass12345")

        can_edit_perm = Permission.objects.get(codename="can_edit_site")
        self.editor.user_permissions.add(can_edit_perm)

        self.site = Site.objects.create(user=self.owner, name="API Lock Test Site")
        self.addCleanup(cache.delete, f"lock:site:{self.site.id}")

        self.lock_url = reverse("site-lock", kwargs={"pk": self.site.id})
        self.detail_url = reverse("site-detail", kwargs={"pk": self.site.id})

    def _auth(self, username, password):
        response = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_status_when_unlocked(self):
        self._auth("lock_stranger", "pass12345")
        response = self.client.get(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["locked"])

    def test_owner_can_acquire_lock(self):
        self._auth("lock_owner", "pass12345")
        response = self.client.post(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        self.assertEqual(response.data["locked_by"], "lock_owner")

    def test_owner_reacquiring_refreshes_not_creates(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)
        response = self.client.post(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])

    def test_user_without_permission_cannot_acquire(self):
        self._auth("lock_stranger", "pass12345")
        response = self.client.post(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_blocked_while_owner_holds_lock(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)

        self._auth("lock_editor", "pass12345")
        response = self.client.post(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)
        self.assertIn("lock_owner", response.data["detail"])

    def test_heartbeat_by_holder_succeeds(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)
        response = self.client.patch(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_heartbeat_by_non_holder_returns_locked(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)

        self._auth("lock_editor", "pass12345")
        response = self.client.patch(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)

    def test_heartbeat_without_active_lock_returns_conflict(self):
        self._auth("lock_owner", "pass12345")
        response = self.client.patch(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_release_by_holder_succeeds(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)
        response = self.client.delete(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        status_response = self.client.get(self.lock_url)
        self.assertFalse(status_response.data["locked"])

    def test_release_by_non_holder_returns_locked(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)

        self._auth("lock_editor", "pass12345")
        response = self.client.delete(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)

    def test_release_without_active_lock_returns_conflict(self):
        self._auth("lock_owner", "pass12345")
        response = self.client.delete(self.lock_url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_get_on_resource_never_triggers_lock(self):
        self._auth("lock_stranger", "pass12345")
        self.client.get(self.detail_url)

        status_response = self.client.get(self.lock_url)
        self.assertFalse(status_response.data["locked"])

    def test_write_operation_enforces_lock_across_users(self):
        self._auth("lock_owner", "pass12345")
        self.client.patch(self.detail_url, {"name": "Renamed by owner"})

        self._auth("lock_editor", "pass12345")
        response = self.client.patch(self.detail_url, {"name": "Renamed by editor"})
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)

    def test_deleting_site_clears_its_lock(self):
        self._auth("lock_owner", "pass12345")
        self.client.post(self.lock_url)

        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        lock_status = SiteLockService().status(self.site.id)
        self.assertFalse(lock_status["locked"])