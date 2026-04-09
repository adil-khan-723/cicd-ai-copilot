import hashlib
import hmac
import time
from fastapi import Request, HTTPException


async def validate_jenkins_webhook(request: Request, secret: str) -> None:
    """Validate Jenkins webhook HMAC signature if secret is configured."""
    if not secret:
        return
    signature = request.headers.get("X-Jenkins-Signature", "")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing Jenkins signature")
    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={expected}", signature):
        raise HTTPException(status_code=401, detail="Invalid Jenkins signature")


async def validate_github_webhook(request: Request, secret: str) -> None:
    """Validate GitHub Actions webhook HMAC signature if secret is configured."""
    if not secret:
        return
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing GitHub signature")
    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={expected}", signature):
        raise HTTPException(status_code=401, detail="Invalid GitHub signature")
