"""Summarize newsletter emails into categorized Markdown digests."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from mail_common import MailMessage
from monthly import DEFAULT_CATEGORIES, parse_category_bullets

SYSTEM_PROMPT = """You are an AI research digest editor.
Given one or more newsletter emails about AI progress, produce a Markdown fragment
that will be merged into a monthly tracking file.

Rules:
1. Output ONLY Markdown. No preamble or code fences.
2. Do NOT include a top-level # title. Do NOT include a Sources line.
3. Use ONLY these section headings (omit any section with no items):
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
8. Do not add dates in bullets; the pipeline tags the day automatically.
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


def _fallback_sections(messages: list[MailMessage]) -> dict[str, list[str]]:
    bullets = []
    for msg in messages:
        link = f" — {msg.web_link}" if msg.web_link else ""
        bullets.append(f"**{msg.source_label}**: {msg.subject}{link}")
    return {c: [] for c in DEFAULT_CATEGORIES} | {"Other": bullets}


def _normalize_llm_markdown(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("markdown"):
            content = content[len("markdown") :].lstrip()
    return content.strip() + ("\n" if not content.endswith("\n") else "")


def summarize_sections(
    messages: list[MailMessage],
    cfg: dict[str, Any],
    day: date | None = None,
) -> dict[str, list[str]]:
    """Return {category: [bullet texts]} for today's emails."""
    if not messages:
        raise ValueError("No messages to summarize")

    day = day or date.today()
    categories = cfg.get("categories") or list(DEFAULT_CATEGORIES)
    llm = cfg.get("llm") or {}
    api_key = (llm.get("api_key") or "").strip()
    base_url = (llm.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = llm.get("model") or "gpt-4o-mini"
    temperature = float(llm.get("temperature") if llm.get("temperature") is not None else 0.2)
    max_tokens = int(llm.get("max_tokens") or 4000)

    if not api_key:
        return _fallback_sections(messages)

    system = SYSTEM_PROMPT + "\nAllowed headings: " + ", ".join(f"## {c}" for c in categories)
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
        content = _normalize_llm_markdown(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM response: {data}") from exc

    sections = parse_category_bullets(content, categories)
    if not any(sections.values()):
        # Model returned unexpected shape — fall back
        return _fallback_sections(messages)
    return sections


def summarize(messages: list[MailMessage], cfg: dict[str, Any], day: date | None = None) -> str:
    """Backward-compatible: return a day fragment Markdown (sections only)."""
    sections = summarize_sections(messages, cfg, day=day)
    categories = cfg.get("categories") or list(DEFAULT_CATEGORIES)
    lines: list[str] = []
    for cat in categories:
        bullets = sections.get(cat) or []
        if not bullets:
            continue
        lines.append(f"## {cat}")
        lines.append("")
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")
    return ("\n".join(lines).rstrip() + "\n") if lines else "## Other\n\n- (no items)\n"
