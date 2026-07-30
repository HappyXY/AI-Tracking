"""Shared mail models and helpers for AI Tracking fetchers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import html2text

from paths import PROCESSED_PATH, ensure_dirs


@dataclass
class MailMessage:
    id: str
    internet_message_id: str
    subject: str
    sender: str
    received_at: str
    body_text: str
    web_link: str
    source_label: str


def load_processed() -> set[str]:
    ensure_dirs()
    if not PROCESSED_PATH.exists():
        return set()
    try:
        data = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"))
        return set(data.get("ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_processed(ids: set[str], keep_last: int = 2000) -> None:
    ensure_dirs()
    ordered = list(ids)[-keep_last:]
    PROCESSED_PATH.write_text(
        json.dumps({"ids": ordered}, indent=2),
        encoding="utf-8",
    )


def html_to_text(html: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(html or "").strip()


def source_label(sender: str, subject: str, keywords: list[str]) -> str:
    blob = f"{sender} {subject}".lower()
    if "alphasignal" in blob or "alpha signal" in blob:
        return "AlphaSignal"
    if "ainews" in blob or "ai news" in blob:
        return "AINews"
    for kw in keywords:
        if kw.lower() in blob:
            return kw
    return "Unknown"


def matches_sender(sender: str, subject: str, keywords: list[str]) -> bool:
    blob = f"{sender} {subject}".lower()
    return any(kw.lower() in blob for kw in keywords)


def truncate_body(text: str, max_chars: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[truncated]"
    return text
