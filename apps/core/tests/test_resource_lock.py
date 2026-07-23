from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.sites.models import Site
from apps.core.services.resource_lock import SiteLockService
from apps.core.exceptions import ResourceLockedError, LockNotHeldError

User = get_user_model()


class SiteLockServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass12345")
        self.other = User.objects.create_user(username="other", password="pass12345")
        self.site = Site.objects.create(user=self.owner, name="Core Lock Test Site")
        self.service = SiteLockService()
        self.addCleanup(self.service.clear, self.site.id)

    def test_acquire_creates_new_lock(self):
        result = self.service.acquire(self.site.id, self.owner)
        self.assertTrue(result.created)
        self.assertEqual(result.user_id, self.owner.id)
        self.assertEqual(result.locked_at, result.last_activity_at)

    def test_acquire_by_same_user_refreshes_not_creates(self):
        first = self.service.acquire(self.site.id, self.owner)
        second = self.service.acquire(self.site.id, self.owner)
        self.assertFalse(second.created)
        self.assertEqual(second.locked_at, first.locked_at)

    def test_acquire_by_other_user_raises_locked(self):
        self.service.acquire(self.site.id, self.owner)
        with self.assertRaises(ResourceLockedError) as ctx:
            self.service.acquire(self.site.id, self.other)
        self.assertEqual(ctx.exception.locked_by, self.owner.username)

    def test_refresh_by_holder_succeeds(self):
        self.service.acquire(self.site.id, self.owner)
        self.service.refresh(self.site.id, self.owner)

    def test_refresh_by_non_holder_raises_locked(self):
        self.service.acquire(self.site.id, self.owner)
        with self.assertRaises(ResourceLockedError):
            self.service.refresh(self.site.id, self.other)

    def test_refresh_without_lock_raises_not_held(self):
        with self.assertRaises(LockNotHeldError):
            self.service.refresh(self.site.id, self.owner)

    def test_release_by_holder_clears_lock(self):
        self.service.acquire(self.site.id, self.owner)
        self.service.release(self.site.id, self.owner)
        self.assertFalse(self.service.status(self.site.id)["locked"])

    def test_release_by_non_holder_raises_locked(self):
        self.service.acquire(self.site.id, self.owner)
        with self.assertRaises(ResourceLockedError):
            self.service.release(self.site.id, self.other)

    def test_release_without_lock_raises_not_held(self):
        with self.assertRaises(LockNotHeldError):
            self.service.release(self.site.id, self.owner)

    def test_status_when_unlocked(self):
        self.assertEqual(
            self.service.status(self.site.id),
            {"locked": False, "detail": "No active lock exist in this site now"},
        )

    def test_status_when_locked_includes_metadata(self):
        self.service.acquire(self.site.id, self.owner)
        result = self.service.status(self.site.id)
        self.assertTrue(result["locked"])
        self.assertEqual(result["user_id"], self.owner.id)
        self.assertEqual(result["locked_by"], self.owner.username)
        self.assertIn("locked_at", result)
        self.assertIn("last_activity_at", result)
        self.assertIsInstance(result["ttl_remaining_seconds"], int)

    def test_clear_removes_lock_regardless_of_holder(self):
        self.service.acquire(self.site.id, self.owner)
        self.service.clear(self.site.id)
        self.assertFalse(self.service.status(self.site.id)["locked"])