import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

failures: dict[str, deque] = defaultdict(deque)


def serializer():
    return URLSafeTimedSerializer(settings().secret_key, salt="noteforge-session-v1")


def password_matches(password: str) -> bool:
    cfg = settings()
    # Slow derivation on both sides, constant-time comparison, no password stored in DB.
    salt = hashlib.sha256(cfg.secret_key.encode()).digest()[:16]
    a = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    b = hashlib.scrypt(cfg.admin_password.encode(), salt=salt, n=16384, r=8, p=1)
    return hmac.compare_digest(a, b)


def login_rate_limit(request: Request):
    # Single API process; global limit also covers proxy deployments without trusting spoofable XFF.
    stamp = time.monotonic()
    q = failures["global"]
    while q and q[0] < stamp - 60:
        q.popleft()
    if len(q) >= 10:
        raise HTTPException(429, "Too many login attempts. Try again in a minute.")
    q.append(stamp)


def credential_id():
    return hmac.new(
        settings().secret_key.encode(), settings().admin_password.encode(), hashlib.sha256
    ).hexdigest()


def require_auth(request: Request):
    try:
        value = serializer().loads(
            request.cookies.get("nf_session", ""), max_age=settings().session_hours * 3600
        )
        fingerprint = credential_id()
        if value != {"role": "admin", "credential": fingerprint}:
            raise BadSignature("Invalid session")
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Sign in to NoteForge")
