"""Summarize newsletter emails into categorized Markdown digests."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from mail_common import MailMessage

SYSTEM_PROMPT = """You are an AI research digest editor.
Given one or more newsletter emails about AI progress, produce a Markdown digest.

Rules:
1. Output ONLY Markdown. No preamble or code fences.
2. Start with exactly:
   # AI Digest — {date}
   then a blank line, then:
   Sources: {sources}
3. Then use ONLY these section headings (omit any section with no items):
   ## LLM
   ## VLM
   ## Agent
   ## Image Model
   ## Video Model
   ## Other
4. Under each section, use bullet points. Each bullet is one concrete advance:
   - One sentence summary
   - Optionally append (Source: Title) or a link if present in the email
5. Deduplicate overlapping items across emails. Prefer specific model/product names.
6. Ignore ads, unsubscribe noise, and pure marketing fluff without technical substance.
7. Write in the same language as the majority of the source content (English newsletters → English).
"""


def _build_user_payload(messages: list[MailMessage], day: date) -> str:
    parts = [f"Digest date: {day.isoformat()}", ""]
    for i, msg in enumerate(messages, 1):
        parts.append(f"===== Email {i} ({msg.source_label}) =====")
        parts.append(f"From: {msg.sender}")
        parts.append(f"Subject: {msg.subject}")
        parts.append(f"Received: {msg.received_at}")
        if msg.web_link:
            parts.append(f"Link: {msg.web_link}")
        parts.append("")
        parts.append(msg.body_text)
        parts.append("")
    return "\n".join(parts)


def _fallback_digest(messages: list[MailMessage], day: date) -> str:
    sources = sorted({m.source_label for m in messages if m.source_label != "Unknown"})
    lines = [
        f"# AI Digest — {day.isoformat()}",
        "",
        f"Sources: {', '.join(sources) if sources else 'newsletter'}",
        "",
        "## Other",
    ]
    for msg in messages:
        link = f" — {msg.web_link}" if msg.web_link else ""
        lines.append(f"- **{msg.source_label}**: {msg.subject}{link}")
    lines.append("")
    return "\n".join(lines)


def summarize(messages: list[MailMessage], cfg: dict[str, Any], day: date | None = None) -> str:
    if not messages:
        raise ValueError("No messages to summarize")

    day = day or date.today()
    llm = cfg.get("llm") or {}
    api_key = (llm.get("api_key") or "").strip()
    base_url = (llm.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = llm.get("model") or "gpt-4o-mini"
    temperature = float(llm.get("temperature") if llm.get("temperature") is not None else 0.2)
    max_tokens = int(llm.get("max_tokens") or 4000)

    categories = cfg.get("categories") or [
        "LLM",
        "VLM",
        "Agent",
        "Image Model",
        "Video Model",
        "Other",
    ]
    sources = sorted({m.source_label for m in messages if m.source_label != "Unknown"})
    system = SYSTEM_PROMPT.format(
        date=day.isoformat(),
        sources=", ".join(sources) if sources else "AINews, AlphaSignal",
    )
    # Remind model of allowed headings from config
    system += "\nAllowed headings: " + ", ".join(f"## {c}" for c in categories)

    if not api_key:
        return _fallback_digest(messages, day)

    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _build_user_payload(messages, day)},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM response: {data}") from exc

    # Strip accidental fences
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("markdown"):
            content = content[len("markdown") :].lstrip()

    if not content.startswith("#"):
        # Soft recover: prepend title if model skipped it
        header = (
            f"# AI Digest — {day.isoformat()}\n\n"
            f"Sources: {', '.join(sources) if sources else 'AINews, AlphaSignal'}\n\n"
        )
        content = header + content

    if not content.endswith("\n"):
        content += "\n"
    return content
