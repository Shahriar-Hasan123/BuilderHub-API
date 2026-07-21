from django.core.cache import cache
from django.conf import settings
from apps.core.exceptions import ResourceLockedError, LockNotHeldError


class SiteLockService:
    def __init__(self):
        self.ttl = settings.RESOURCE_LOCK_TTL_SECONDS

    def _key(self, site_id):
        return f"lock:site:{site_id}"

    def acquire(self, site_id, username):
        key = self._key(site_id)

        acquire = cache.add(key, username, self.ttl)

        if acquire:
            return

        current_holder = cache.get(key)
        if current_holder == username:
            cache.set(key, username, self.ttl)
            return
        raise ResourceLockedError(locked_by=current_holder)

    def refresh(self, site_id, username):
        key = self._key(site_id)
        current_holder = cache.get(key)
        
        if not current_holder:
            raise LockNotHeldError()
        
        if current_holder != username:
            raise ResourceLockedError(locked_by=current_holder)
        
        cache.set(key, username, timeout=self.ttl)

    def release(self, site_id, username):
        key = self._key(site_id)
        current_holder = cache.get(key)
        
        if not current_holder:
            raise LockNotHeldError()
        
        if current_holder != username:
            raise ResourceLockedError(locked_by=current_holder)
        
        cache.delete(key)
