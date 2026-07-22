from dataclasses import dataclass


@dataclass
class LockAcquireResult:
    created: bool
    user_id: bool
    username: str
    locked_at: str
    last_activity_at: str
    ttl_remaining_seconds: int
