from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.core.dto import LockAcquireResult
from apps.core.exceptions import LockNotHeldError, ResourceLockedError


class SiteLockService:
    def __init__(self):
        self.ttl = settings.RESOURCE_LOCK_TTL_SECONDS

    def _key(self, site_id):
        return f"lock:site:{site_id}"

    def acquire(self, site_id, user):
        key = self._key(site_id)
        now = timezone.now().isoformat()
        new_lock = {
            "user_id": user.id,
            "username": user.username,
            "locked_at": now,
            "last_activity_at": now,
        }

        acquire = cache.add(key, new_lock, self.ttl)
        if acquire:
            return LockAcquireResult(
                created=True,
                user_id=user.id,
                username=user.username,
                locked_at=now,
                last_activity_at=now,
                ttl_remaining_seconds=self.ttl,
            )
        current = cache.get(key)
        if current and current["user_id"] == user.id:
            current["last_activity_at"] = now
            cache.set(key, current, timeout=self.ttl)
            return LockAcquireResult(
                created=False,
                user_id=current["user_id"],
                username=current["username"],
                locked_at=current["locked_at"],
                last_activity_at=now,
                ttl_remaining_seconds=self.ttl,
            )

        raise ResourceLockedError(
            locked_by=current["username"] if current else "unknown"
        )

    def refresh(self, site_id, user):
        key = self._key(site_id)
        current = cache.get(key)

        if not current:
            raise LockNotHeldError()

        if current["user_id"] != user.id:
            raise ResourceLockedError(locked_by=current["username"])

        current["last_activity_at"] = timezone.now().isoformat()
        cache.set(key, current, timeout=self.ttl)

    def release(self, site_id, user):
        key = self._key(site_id)
        current = cache.get(key)

        if not current:
            raise LockNotHeldError()

        if current["user_id"] != user.id:
            raise ResourceLockedError(locked_by=current["username"])

        cache.delete(key)

    def status(self, site_id):
        key = self._key(site_id)
        current = cache.get(key)

        if not current:
            return {"locked": False, "detail": "No active lock exist in this site now"}

        return {
            "locked": True,
            "user_id": current["user_id"],
            "locked_by": current["username"],
            "locked_at": current["locked_at"],
            "last_activity_at": current["last_activity_at"],
            "ttl_remaining_seconds": cache.ttl(key),
        }

    def clear(self, site_id):
        cache.delete(self._key(site_id))
