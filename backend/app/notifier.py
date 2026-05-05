from __future__ import annotations

from dataclasses import dataclass

import httpx

from .models import PushoverProfile
from .security import decrypt_secret


@dataclass
class NotificationResult:
    status: str
    response: str


async def send_pushover(
    profile: PushoverProfile,
    *,
    title: str,
    message: str,
    url: str | None = None,
    priority: int | None = None,
) -> NotificationResult:
    token = decrypt_secret(profile.app_token_encrypted)
    user = decrypt_secret(profile.user_key_encrypted)
    if not token or not user:
        return NotificationResult(status="failed", response="Pushover credentials could not be decrypted.")

    payload: dict[str, str | int] = {
        "token": token,
        "user": user,
        "title": title,
        "message": message,
        "priority": profile.default_priority if priority is None else priority,
    }
    if profile.default_device:
        payload["device"] = profile.default_device
    if url:
        payload["url"] = url
        payload["url_title"] = "Open page"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://api.pushover.net/1/messages.json", data=payload)
        if response.is_success:
            return NotificationResult(status="sent", response=response.text[:2000])
        return NotificationResult(status="failed", response=response.text[:2000])
    except httpx.HTTPError as exc:
        return NotificationResult(status="failed", response=str(exc))

