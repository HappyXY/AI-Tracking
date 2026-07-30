"""Fetch AINews / AlphaSignal messages (Apple Mail by default; Outlook Mac / Graph optional)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import msal

from apple_mail import fetch_messages_apple_mail
from mail_common import (
    MailMessage,
    html_to_text,
    load_processed,
    matches_sender,
    save_processed,
    source_label,
    truncate_body,
)
from outlook_mac import fetch_messages_mac
from paths import MSAL_CACHE_PATH, ensure_dirs

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Re-export for run.py / summarize.py
__all__ = [
    "MailMessage",
    "fetch_messages",
    "save_processed",
]


class TokenCache:
    def __init__(self, path=MSAL_CACHE_PATH) -> None:
        self.path = path
        self.cache = msal.SerializableTokenCache()
        if path.exists():
            self.cache.deserialize(path.read_text(encoding="utf-8"))

    def persist(self) -> None:
        if self.cache.has_state_changed:
            ensure_dirs()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(self.cache.serialize(), encoding="utf-8")


def acquire_token(cfg: dict[str, Any]) -> str:
    azure = cfg.get("azure") or {}
    client_id = (azure.get("client_id") or "").strip()
    if not client_id:
        raise ValueError(
            "azure.client_id is empty. Set it in agent/config.yaml or AZURE_CLIENT_ID."
        )

    authority = azure.get("authority") or "https://login.microsoftonline.com/common"
    scopes = azure.get("scopes") or ["https://graph.microsoft.com/Mail.Read"]

    token_cache = TokenCache()
    app = msal.PublicClientApplication(
        client_id,
        authority=authority,
        token_cache=token_cache.cache,
    )

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])

    if not result:
        result = app.acquire_token_interactive(scopes=scopes)

    token_cache.persist()

    if not result or "access_token" not in result:
        err = (result or {}).get("error_description") or (result or {}).get("error") or "unknown"
        raise RuntimeError(f"Failed to acquire Microsoft Graph token: {err}")

    return result["access_token"]


def _parse_received(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_messages_graph(cfg: dict[str, Any], access_token: str | None = None) -> list[MailMessage]:
    mail_cfg = cfg.get("mail") or {}
    keywords = mail_cfg.get("sender_keywords") or [
        "ainews",
        "ai news",
        "alphasignal",
        "alpha signal",
    ]
    lookback_hours = int(mail_cfg.get("lookback_hours") or 36)
    max_messages = int(mail_cfg.get("max_messages") or 50)
    max_body_chars = int(mail_cfg.get("max_body_chars") or 12000)

    token = access_token or acquire_token(cfg)
    processed = load_processed()
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "$select": "id,internetMessageId,subject,from,receivedDateTime,body,bodyPreview,webLink",
        "$orderby": "receivedDateTime desc",
        "$top": str(min(max_messages * 3, 100)),
        "$filter": f"receivedDateTime ge {since_iso}",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.body-content-type="html"',
    }

    url = f"{GRAPH_BASE}/me/messages"
    raw_items: list[dict[str, Any]] = []

    with httpx.Client(timeout=60.0) as client:
        while url and len(raw_items) < max_messages * 3:
            resp = client.get(url, headers=headers, params=params if "?" not in url else None)
            resp.raise_for_status()
            payload = resp.json()
            raw_items.extend(payload.get("value") or [])
            url = payload.get("@odata.nextLink")
            params = None

    messages: list[MailMessage] = []
    for item in raw_items:
        msg_id = item.get("id") or ""
        internet_id = item.get("internetMessageId") or msg_id
        dedupe_key = internet_id or msg_id
        if not dedupe_key or dedupe_key in processed:
            continue

        from_obj = ((item.get("from") or {}).get("emailAddress") or {})
        sender = f"{from_obj.get('name') or ''} <{from_obj.get('address') or ''}>".strip()
        subject = item.get("subject") or "(no subject)"
        if not matches_sender(sender, subject, keywords):
            continue

        received = item.get("receivedDateTime") or ""
        received_dt = _parse_received(received)
        if received_dt and received_dt < since:
            continue

        body = item.get("body") or {}
        content = body.get("content") or item.get("bodyPreview") or ""
        content_type = (body.get("contentType") or "text").lower()
        if content_type == "html":
            text = html_to_text(content)
        else:
            text = content.strip()
        text = truncate_body(text, max_body_chars)

        messages.append(
            MailMessage(
                id=msg_id,
                internet_message_id=internet_id,
                subject=subject,
                sender=sender,
                received_at=received,
                body_text=text,
                web_link=item.get("webLink") or "",
                source_label=source_label(sender, subject, keywords),
            )
        )
        if len(messages) >= max_messages:
            break

    return messages


def fetch_messages(cfg: dict[str, Any], access_token: str | None = None) -> list[MailMessage]:
    mail_cfg = cfg.get("mail") or {}
    backend = (mail_cfg.get("backend") or "apple_mail").strip().lower()
    if backend in {"apple_mail", "mail", "mailapp", "apple"}:
        return fetch_messages_apple_mail(cfg)
    if backend in {"mac", "outlook_mac", "desktop", "outlook"}:
        return fetch_messages_mac(cfg)
    if backend in {"graph", "msgraph", "azure"}:
        return fetch_messages_graph(cfg, access_token=access_token)
    raise ValueError(
        f"Unknown mail.backend: {backend!r} (use 'apple_mail', 'mac', or 'graph')"
    )
