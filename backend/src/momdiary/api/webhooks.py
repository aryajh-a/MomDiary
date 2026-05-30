"""Clerk webhook router (POST /v1/webhooks/clerk) — feature 008.

The signature **is** the authentication; no `get_current_user` dep here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.api.dependencies import get_session_store
from momdiary.auth.webhooks import (
    WebhookSignatureError,
    handle_user_deleted,
    handle_user_updated,
    verify_svix,
)
from momdiary.db.engine import get_session
from momdiary.observability.middleware import current_correlation_id
from momdiary.schemas.webhooks import ClerkWebhookEnvelope

router = APIRouter(tags=["webhooks"], prefix="/webhooks")


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "error": code,
            "message": message,
            "correlation_id": current_correlation_id() or "unknown",
        },
    )


@router.post("/clerk", status_code=200)
async def clerk_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    body = await request.body()
    # Svix expects a plain dict of headers (case-insensitive).
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        verify_svix(headers, body)
    except WebhookSignatureError as err:
        raise _err(401, "invalid_signature", str(err)) from err

    try:
        envelope = ClerkWebhookEnvelope.model_validate_json(body)
    except Exception as err:
        raise _err(400, "invalid_body", str(err)) from err

    event_type = envelope.type
    data = envelope.data

    if event_type == "user.deleted":
        clerk_user_id = data.get("id")
        if not isinstance(clerk_user_id, str):
            raise _err(400, "invalid_body", "user.deleted: missing data.id")
        store = get_session_store()

        async def _purge(user_id: int) -> int:
            # The chat store has a `purge_user` method added in T019.
            purge = getattr(store, "purge_user", None)
            if purge is None:
                return 0
            return await purge(user_id)

        deleted = await handle_user_deleted(
            db, clerk_user_id=clerk_user_id, chat_store_purge=_purge
        )
        return {"event": event_type, "deleted": deleted}

    if event_type == "user.updated":
        clerk_user_id = data.get("id")
        if not isinstance(clerk_user_id, str):
            raise _err(400, "invalid_body", "user.updated: missing data.id")
        primary_id = data.get("primary_email_address_id")
        emails = data.get("email_addresses") or []
        email: str | None = None
        email_verified: bool | None = None
        if isinstance(emails, list):
            for entry in emails:
                if not isinstance(entry, dict):
                    continue
                if entry.get("id") == primary_id:
                    addr = entry.get("email_address")
                    if isinstance(addr, str):
                        email = addr
                    verif = entry.get("verification") or {}
                    if isinstance(verif, dict):
                        status_val = verif.get("status")
                        if status_val == "verified":
                            email_verified = True
                        elif status_val is not None:
                            email_verified = False
                    break
        mutated = await handle_user_updated(
            db,
            clerk_user_id=clerk_user_id,
            email=email,
            email_verified=email_verified,
        )
        return {"event": event_type, "mutated": mutated}

    # Unknown event types are acknowledged (200) so Clerk doesn't retry.
    return {"event": event_type, "ignored": True}
