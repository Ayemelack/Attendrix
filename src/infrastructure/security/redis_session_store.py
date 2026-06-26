"""
REDIS SESSION STORE
Attendrix distributed attendance system

Phase 2E — Replaces in-memory session/rate-limit storage with Redis-backed
persistent storage. All classes gracefully fall back to in-memory storage
when Redis is unavailable.
"""

import json
import time
import logging
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import asdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _get_config(key: str, default: Any = None) -> Any:
    """Read a value from Flask current_app config, or fall back to environment."""
    try:
        from flask import current_app
        if current_app:
            return current_app.config.get(key, default)
    except (RuntimeError, ImportError):
        pass
    import os
    return os.environ.get(key, default)


def _redis_url() -> str:
    val = _get_config('REDIS_URL', 'redis://localhost:6379/0')
    if isinstance(val, str):
        return val
    return val or 'redis://localhost:6379/0'


def _redis_enabled() -> bool:
    val = _get_config('REDIS_SESSION_ENABLED', False)
    if isinstance(val, str):
        return val.lower() in ('1', 'true', 'yes')
    return bool(val)


def _redis_prefix() -> str:
    val = _get_config('REDIS_PREFIX', 'attendrix:')
    return str(val) if val else 'attendrix:'


def _session_ttl() -> int:
    val = _get_config('REDIS_SESSION_TTL', 86400)
    try:
        return int(val)
    except (TypeError, ValueError):
        return 86400


# ---------------------------------------------------------------------------
# 1. RedisSessionStore
# ---------------------------------------------------------------------------

class RedisSessionStore:
    """Low-level Redis key-value store with in-memory fallback.

    Provides a dict-like interface with TTL support, set operations, and
    pattern-based key scanning.
    """

    def __init__(self, redis_url: Optional[str] = None, default_prefix: Optional[str] = None):
        self._redis_url = redis_url or _redis_url()
        self._prefix = default_prefix or _redis_prefix()
        self._client: Optional[Any] = None
        self._lock = threading.Lock()
        self._fallback: Dict[str, Any] = {}
        self._fallback_ttl: Dict[str, float] = {}

    # -- connection management ------------------------------------------------

    def _get_client(self):
        """Lazy-initialize Redis connection. Returns None if unavailable."""
        if self._client is not None:
            try:
                self._client.ping()
                return self._client
            except Exception:
                self._client = None

        if not _redis_enabled():
            return None

        with self._lock:
            if self._client is not None:
                return self._client
            try:
                import redis
                self._client = redis.from_url(
                    self._redis_url,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    decode_responses=True,
                )
                self._client.ping()
                logger.info("RedisSessionStore: connected to %s", self._redis_url)
            except Exception as exc:
                logger.warning("RedisSessionStore: Redis unavailable (%s) – using in-memory fallback", exc)
                self._client = None
            return self._client

    def _key(self, name: str) -> str:
        return f"{self._prefix}{name}"

    def _is_fallback(self) -> bool:
        return self._get_client() is None

    # -- core operations ------------------------------------------------------

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store JSON-serializable value with optional TTL (seconds)."""
        client = self._get_client()
        if client is not None:
            try:
                data = json.dumps(value, default=str)
                if ttl is not None:
                    client.setex(self._key(key), ttl, data)
                else:
                    client.set(self._key(key), data)
                return True
            except Exception as exc:
                logger.error("RedisSessionStore.set(%s) failed: %s", key, exc)
                return False

        serialised = json.dumps(value, default=str)
        self._fallback[self._key(key)] = serialised
        if ttl is not None:
            self._fallback_ttl[self._key(key)] = time.time() + ttl
        return True

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize a stored value."""
        client = self._get_client()
        if client is not None:
            try:
                data = client.get(self._key(key))
                if data is None:
                    return None
                return json.loads(data)
            except Exception as exc:
                logger.error("RedisSessionStore.get(%s) failed: %s", key, exc)
                return None

        fkey = self._key(key)
        raw = self._fallback.get(fkey)
        if raw is None:
            return None
        expiry = self._fallback_ttl.get(fkey)
        if expiry is not None and time.time() > expiry:
            self._fallback.pop(fkey, None)
            self._fallback_ttl.pop(fkey, None)
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def delete(self, key: str) -> bool:
        """Remove a key."""
        client = self._get_client()
        if client is not None:
            try:
                client.delete(self._key(key))
                return True
            except Exception as exc:
                logger.error("RedisSessionStore.delete(%s) failed: %s", key, exc)
                return False

        fkey = self._key(key)
        self._fallback.pop(fkey, None)
        self._fallback_ttl.pop(fkey, None)
        return True

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        client = self._get_client()
        if client is not None:
            try:
                return bool(client.exists(self._key(key)))
            except Exception as exc:
                logger.error("RedisSessionStore.exists(%s) failed: %s", key, exc)
                return False

        fkey = self._key(key)
        expiry = self._fallback_ttl.get(fkey)
        if expiry is not None and time.time() > expiry:
            self._fallback.pop(fkey, None)
            self._fallback_ttl.pop(fkey, None)
            return False
        return fkey in self._fallback

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on an existing key."""
        client = self._get_client()
        if client is not None:
            try:
                client.expire(self._key(key), ttl)
                return True
            except Exception as exc:
                logger.error("RedisSessionStore.expire(%s) failed: %s", key, exc)
                return False

        self._fallback_ttl[self._key(key)] = time.time() + ttl
        return True

    def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomically increment a key. Returns the new value."""
        client = self._get_client()
        if client is not None:
            try:
                pkey = self._key(key)
                value = client.incrby(pkey, amount)
                if ttl is not None:
                    client.expire(pkey, ttl)
                return value
            except Exception as exc:
                logger.error("RedisSessionStore.increment(%s) failed: %s", key, exc)
                return 0

        fkey = self._key(key)
        current = self._fallback.get(fkey, "0")
        try:
            new_val = int(current) + amount
        except (ValueError, TypeError):
            new_val = amount
        self._fallback[fkey] = str(new_val)
        if ttl is not None:
            self._fallback_ttl[fkey] = time.time() + ttl
        return new_val

    # -- set operations -------------------------------------------------------

    def add_to_set(self, key: str, member: str) -> bool:
        """Add a member to a Redis set."""
        client = self._get_client()
        if client is not None:
            try:
                client.sadd(self._key(key), member)
                return True
            except Exception as exc:
                logger.error("RedisSessionStore.add_to_set(%s) failed: %s", key, exc)
                return False

        fkey = self._key(key)
        if fkey not in self._fallback or not isinstance(self._fallback.get(fkey), list):
            self._fallback[fkey] = []
        if member not in self._fallback[fkey]:
            self._fallback[fkey].append(member)
        return True

    def is_in_set(self, key: str, member: str) -> bool:
        """Check if member is in a Redis set."""
        client = self._get_client()
        if client is not None:
            try:
                return bool(client.sismember(self._key(key), member))
            except Exception as exc:
                logger.error("RedisSessionStore.is_in_set(%s) failed: %s", key, exc)
                return False

        fkey = self._key(key)
        members = self._fallback.get(fkey, [])
        return member in members if isinstance(members, list) else False

    def get_set_members(self, key: str) -> Set[str]:
        """Get all members of a Redis set."""
        client = self._get_client()
        if client is not None:
            try:
                return set(client.smembers(self._key(key)))
            except Exception as exc:
                logger.error("RedisSessionStore.get_set_members(%s) failed: %s", key, exc)
                return set()

        fkey = self._key(key)
        members = self._fallback.get(fkey, [])
        return set(members) if isinstance(members, list) else set()

    # -- scanning / maintenance -----------------------------------------------

    def get_keys(self, pattern: str) -> List[str]:
        """Get all keys matching a glob pattern (prefix is prepended)."""
        client = self._get_client()
        if client is not None:
            try:
                full_pattern = self._key(pattern)
                keys = client.keys(full_pattern)
                prefix_len = len(self._prefix)
                return [k[prefix_len:] for k in keys]
            except Exception as exc:
                logger.error("RedisSessionStore.get_keys(%s) failed: %s", pattern, exc)
                return []

        import fnmatch
        full_pattern = self._key(pattern)
        matched = []
        for fkey in self._fallback:
            if fnmatch.fnmatch(fkey, full_pattern):
                expiry = self._fallback_ttl.get(fkey)
                if expiry is None or time.time() <= expiry:
                    prefix_len = len(self._prefix)
                    matched.append(fkey[prefix_len:])
        return matched

    def flush_all(self) -> bool:
        """Clear all keys with the configured prefix. Logs a warning."""
        logger.warning("RedisSessionStore.flush_all(): clearing all keys with prefix '%s'", self._prefix)
        client = self._get_client()
        if client is not None:
            try:
                keys = client.keys(f"{self._prefix}*")
                if keys:
                    client.delete(*keys)
                return True
            except Exception as exc:
                logger.error("RedisSessionStore.flush_all() failed: %s", exc)
                return False

        self._fallback.clear()
        self._fallback_ttl.clear()
        return True

    def health_check(self) -> bool:
        """Ping Redis. Returns True if healthy, False otherwise."""
        client = self._get_client()
        if client is not None:
            try:
                return client.ping()
            except Exception:
                return False
        return False


# ---------------------------------------------------------------------------
# 2. RedisRateLimiter
# ---------------------------------------------------------------------------

class RedisRateLimiter:
    """Sliding-window counter rate limiter backed by Redis.

    Falls back to in-memory :class:`EnhancedRateLimiter` when Redis is
    unavailable or ``REDIS_SESSION_ENABLED`` is ``False``.
    """

    def __init__(self, store: Optional[RedisSessionStore] = None):
        self._store = store or RedisSessionStore()
        self._fallback_limiter: Optional[Any] = None

    def _get_fallback(self):
        if self._fallback_limiter is None:
            try:
                from src.infrastructure.security_legacy import EnhancedRateLimiter
                self._fallback_limiter = EnhancedRateLimiter()
            except ImportError:
                from ...security_legacy import EnhancedRateLimiter
                self._fallback_limiter = EnhancedRateLimiter()
        return self._fallback_limiter

    def _use_redis(self) -> bool:
        return self._store.health_check()

    def is_limited(self, key: str, limit: int = 60, window: int = 60,
                   block_duration: int = 300) -> Tuple[bool, int]:
        """Check if *key* is rate-limited.

        Returns ``(is_limited, retry_after_seconds)``.
        """
        if not self._use_redis():
            return self._get_fallback().is_limited(key=key, limit=limit, window=window,
                                                    block_duration=block_duration)

        now = time.time()
        window_key = f"ratelimit:{key}:window"
        block_key = f"ratelimit:{key}:blocked"

        block_until = self._store.get(block_key)
        if block_until is not None:
            remaining = int(block_until - now) + 1
            if remaining > 0:
                return True, remaining
            self._store.delete(block_key)

        timestamps = self._store.get_set_members(window_key)
        cutoff = now - window
        active = [t for t in timestamps if float(t) > cutoff]

        if len(active) >= limit:
            offense_key = f"ratelimit:{key}:offense"
            offense_count = self._store.increment(offense_key, 1, ttl=86400)
            multipliers = [1, 2, 4, 8, 16, 32, 64]
            idx = min(offense_count - 1, len(multipliers) - 1)
            effective_block = block_duration * multipliers[idx]

            self._store.set(block_key, now + effective_block, ttl=effective_block + 1)
            self._store.delete(window_key)
            return True, effective_block

        active.append(str(now))
        for t in active:
            self._store.add_to_set(window_key, t)
        self._store.expire(window_key, window + 10)

        return False, 0

    def get_remaining(self, key: str, limit: int = 60, window: int = 60) -> int:
        """Get remaining requests before rate limit is hit."""
        if not self._use_redis():
            fallback = self._get_fallback()
            return fallback.get_remaining(scope=key, limit=limit, window=window)

        window_key = f"ratelimit:{key}:window"
        timestamps = self._store.get_set_members(window_key)
        cutoff = time.time() - window
        active = [t for t in timestamps if float(t) > cutoff]
        return max(0, limit - len(active))

    def reset(self, key: str) -> bool:
        """Clear rate-limit data for *key*."""
        if not self._use_redis():
            self._get_fallback().clear(key=key)
            return True

        self._store.delete(f"ratelimit:{key}:window")
        self._store.delete(f"ratelimit:{key}:blocked")
        self._store.delete(f"ratelimit:{key}:offense")
        return True

    def get_block_time(self, key: str) -> int:
        """Return remaining block time in seconds (0 if not blocked)."""
        if not self._use_redis():
            return 0

        block_until = self._store.get(f"ratelimit:{key}:blocked")
        if block_until is None:
            return 0
        remaining = int(block_until - time.time())
        return max(0, remaining)


# ---------------------------------------------------------------------------
# 3. RedisSessionManager
# ---------------------------------------------------------------------------

class RedisSessionManager:
    """Redis-backed session manager following the same API as
    :class:`src.infrastructure.security.session_security.SessionManager`.

    Falls back to an in-memory :class:`SessionManager` when Redis is
    unavailable.
    """

    def __init__(self, store: Optional[RedisSessionStore] = None,
                 token_ttl_seconds: Optional[int] = None):
        self._store = store or RedisSessionStore()
        self._token_ttl = token_ttl_seconds or _session_ttl()
        self._fallback_manager: Optional[Any] = None
        self._fallback_lock = threading.Lock()

    def _get_fallback(self):
        if self._fallback_manager is None:
            with self._fallback_lock:
                if self._fallback_manager is None:
                    try:
                        from src.infrastructure.security.session_security import SessionManager
                        self._fallback_manager = SessionManager(
                            token_ttl_seconds=self._token_ttl,
                        )
                    except ImportError:
                        from .session_security import SessionManager
                        self._fallback_manager = SessionManager(
                            token_ttl_seconds=self._token_ttl,
                        )
        return self._fallback_manager

    def _use_redis(self) -> bool:
        return self._store.health_check()

    def _make_session_key(self, token_id: str) -> str:
        return f"session:{token_id}"

    def _make_user_sessions_key(self, user_id: str) -> str:
        return f"user_sessions:{user_id}"

    def _now(self) -> int:
        return int(time.time())

    def create_session(self, user_id: str, device_fingerprint_id: str,
                       institution_id: str, ip_address: str, **kwargs) -> Any:
        """Create a new session, store in Redis with TTL.

        Returns a :class:`SessionToken`-compatible dict.
        """
        if not self._use_redis():
            return self._get_fallback().create_session(
                user_id, device_fingerprint_id, institution_id, ip_address,
            )

        import uuid
        import hashlib

        now = self._now()
        token_id = hashlib.sha256(
            f"{uuid.uuid4()}{now}{uuid.uuid4()}".encode()
        ).hexdigest()

        session = {
            "token_id": token_id,
            "user_id": user_id,
            "device_fingerprint_id": device_fingerprint_id,
            "institution_id": institution_id,
            "ip_address": ip_address,
            "issued_at": now,
            "expires_at": now + self._token_ttl,
            "last_activity": now,
            "rotation_count": 0,
            "is_valid": True,
        }

        self._store.set(
            self._make_session_key(token_id),
            session,
            ttl=self._token_ttl,
        )

        user_key = self._make_user_sessions_key(user_id)
        self._store.add_to_set(user_key, token_id)
        self._store.expire(user_key, self._token_ttl)

        logger.info(
            "RedisSessionManager: session created user=%s device=%s institution=%s",
            user_id, device_fingerprint_id, institution_id,
        )

        return session

    def validate_session(self, token_id: str, device_fingerprint_id: Optional[str] = None,
                         ip_address: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[Any]]:
        """Validate a session token.

        Returns ``(is_valid, error_message, session_dict)``.
        """
        if not self._use_redis():
            return self._get_fallback().validate_session(
                token_id, device_fingerprint_id, ip_address,
            )

        session = self._store.get(self._make_session_key(token_id))
        if session is None:
            return False, "Session not found", None

        now = self._now()

        if not session.get("is_valid", True):
            return False, "Session invalidated", session

        if now > session.get("expires_at", 0):
            logger.warning("RedisSessionManager: expired session %s", token_id)
            self._store.delete(self._make_session_key(token_id))
            return False, "Session expired. Please log in again.", session

        if device_fingerprint_id and session.get("device_fingerprint_id") != device_fingerprint_id:
            logger.warning(
                "RedisSessionManager: device mismatch token=%s expected=%s got=%s",
                token_id, session.get("device_fingerprint_id"), device_fingerprint_id,
            )
            return False, "Session device mismatch. Please re-authenticate.", session

        if ip_address and session.get("ip_address") and session["ip_address"] != ip_address:
            logger.warning(
                "RedisSessionManager: IP mismatch token=%s expected=%s got=%s",
                token_id, session.get("ip_address"), ip_address,
            )

        session["last_activity"] = now
        self._store.set(
            self._make_session_key(token_id),
            session,
            ttl=max(1, session["expires_at"] - now),
        )

        return True, None, session

    def rotate_token(self, old_token_id: str, device_fingerprint_id: str,
                     ip_address: str) -> Tuple[bool, Optional[str], Optional[Any]]:
        """Rotate a session token (issue new, invalidate old)."""
        if not self._use_redis():
            return self._get_fallback().rotate_token(old_token_id, device_fingerprint_id, ip_address)

        is_valid, error, old_session = self.validate_session(old_token_id, device_fingerprint_id)
        if not is_valid:
            return False, error, None

        new_session = self.create_session(
            user_id=old_session["user_id"],
            device_fingerprint_id=device_fingerprint_id,
            institution_id=old_session.get("institution_id", ""),
            ip_address=ip_address,
        )
        new_session["rotation_count"] = old_session.get("rotation_count", 0) + 1

        old_session["is_valid"] = False
        self._store.set(
            self._make_session_key(old_token_id),
            old_session,
            ttl=max(1, old_session["expires_at"] - self._now()),
        )

        logger.info(
            "RedisSessionManager: token rotated user=%s count=%s",
            old_session["user_id"], new_session["rotation_count"],
        )

        return True, None, new_session

    def invalidate_session(self, token_id: str) -> bool:
        """Explicitly invalidate a session (logout)."""
        if not self._use_redis():
            return self._get_fallback().invalidate_session(token_id)

        session = self._store.get(self._make_session_key(token_id))
        if session is None:
            return False

        session["is_valid"] = False
        self._store.set(
            self._make_session_key(token_id),
            session,
            ttl=max(1, session.get("expires_at", self._now() + 3600) - self._now()),
        )

        user_key = self._make_user_sessions_key(session.get("user_id", ""))
        self._store.add_to_set(user_key, token_id)

        logger.info("RedisSessionManager: session invalidated user=%s", session.get("user_id"))
        return True

    def invalidate_user_sessions(self, user_id: str, except_token_id: Optional[str] = None) -> int:
        """Invalidate all sessions for a user, optionally keeping one active."""
        if not self._use_redis():
            return self._get_fallback().invalidate_user_sessions(user_id, except_token_id)

        user_key = self._make_user_sessions_key(user_id)
        token_ids = self._store.get_set_members(user_key)
        count = 0

        for tid in token_ids:
            if tid == except_token_id:
                continue
            session = self._store.get(self._make_session_key(tid))
            if session is not None:
                session["is_valid"] = False
                remaining_ttl = max(1, session.get("expires_at", self._now() + 3600) - self._now())
                self._store.set(self._make_session_key(tid), session, ttl=remaining_ttl)
                count += 1

        logger.warning(
            "RedisSessionManager: invalidated %d sessions for user %s",
            count, user_id,
        )
        return count

    def cleanup_expired_sessions(self) -> int:
        """Redis handles TTL expiry automatically — no-op.

        For in-memory fallback, delegates to the fallback manager.
        """
        if not self._use_redis():
            return self._get_fallback().cleanup_expired_sessions()
        return 0

    def get_active_session_count(self, user_id: str) -> int:
        """Count active (non-expired, valid) sessions for a user."""
        if not self._use_redis():
            sessions = getattr(self._get_fallback(), "sessions", {})
            count = 0
            for s in sessions.values():
                if s.user_id == user_id and s.is_valid and not s.is_expired:
                    count += 1
            return count

        user_key = self._make_user_sessions_key(user_id)
        token_ids = self._store.get_set_members(user_key)
        count = 0

        for tid in token_ids:
            session = self._store.get(self._make_session_key(tid))
            if session is None:
                continue
            if session.get("is_valid", False) and self._now() <= session.get("expires_at", 0):
                count += 1

        return count

    def update_activity(self, token_id: str) -> bool:
        """Update session last-activity timestamp."""
        if not self._use_redis():
            return self._get_fallback().update_activity(token_id)

        session = self._store.get(self._make_session_key(token_id))
        if session is None:
            return False

        session["last_activity"] = self._now()
        remaining_ttl = max(1, session.get("expires_at", self._now() + 3600) - self._now())
        self._store.set(self._make_session_key(token_id), session, ttl=remaining_ttl)
        return True


# ---------------------------------------------------------------------------
# 4. RedisTokenBlacklist
# ---------------------------------------------------------------------------

class RedisTokenBlacklist:
    """Blacklist for JWT tokens using Redis with TTL auto-cleanup.

    Falls back to an in-memory set when Redis is unavailable.
    """

    def __init__(self, store: Optional[RedisSessionStore] = None):
        self._store = store or RedisSessionStore()
        self._fallback: Dict[str, float] = {}

    def _use_redis(self) -> bool:
        return self._store.health_check()

    def _blacklist_key(self, jti: str) -> str:
        return f"blacklist:{jti}"

    def blacklist(self, jti: str, expires_at: int) -> bool:
        """Add *jti* to the blacklist until *expires_at* (unix timestamp).

        The TTL is calculated as ``expires_at - now`` so the entry is
        automatically removed by Redis when the token would have expired.
        """
        ttl = max(1, expires_at - int(time.time()))

        if self._use_redis():
            try:
                self._store.set(self._blacklist_key(jti), True, ttl=ttl)
                return True
            except Exception as exc:
                logger.error("RedisTokenBlacklist.blacklist(%s) failed: %s", jti, exc)
                return False

        self._fallback[jti] = time.time() + ttl
        return True

    def is_blacklisted(self, jti: str) -> bool:
        """Check if *jti* is blacklisted."""
        if self._use_redis():
            try:
                return self._store.exists(self._blacklist_key(jti))
            except Exception as exc:
                logger.error("RedisTokenBlacklist.is_blacklisted(%s) failed: %s", jti, exc)
                return False

        expiry = self._fallback.get(jti)
        if expiry is None:
            return False
        if time.time() > expiry:
            self._fallback.pop(jti, None)
            return False
        return True

    def cleanup(self) -> int:
        """Remove expired blacklist entries (Redis auto-cleanup; fallback only)."""
        if self._use_redis():
            return 0

        now = time.time()
        expired = [jti for jti, exp in self._fallback.items() if now > exp]
        for jti in expired:
            self._fallback.pop(jti, None)
        return len(expired)


# ---------------------------------------------------------------------------
# Module-level convenience instances
# ---------------------------------------------------------------------------

redis_session_store = RedisSessionStore()
redis_rate_limiter = RedisRateLimiter(redis_session_store)
redis_session_manager = RedisSessionManager(redis_session_store)
redis_token_blacklist = RedisTokenBlacklist(redis_session_store)
