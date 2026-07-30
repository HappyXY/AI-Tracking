"""Monthly digest merge: one Markdown file per month, categorized sections."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

DEFAULT_CATEGORIES = [
    "LLM",
    "VLM",
    "Agent",
    "Image Model",
    "Video Model",
    "Other",
]

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^(\s*[-*+]\s+)(.*)$")
_DAY_TAG_RE = re.compile(r"^\*\((\d{4}-\d{2}-\d{2})\)\*\s*")


def monthly_path(repo_root: Path, day: date) -> Path:
    return repo_root / "digest" / f"{day.year:04d}-{day.month:02d}.md"


def parse_category_bullets(markdown: str, categories: list[str] | None = None) -> dict[str, list[str]]:
    """Parse ## Category sections into {category: [bullet text without leading '- ']}."""
    cats = categories or DEFAULT_CATEGORIES
    cat_set = {c.lower(): c for c in cats}
    result: dict[str, list[str]] = {c: [] for c in cats}
    current: str | None = None

    for raw in (markdown or "").splitlines():
        line = raw.rstrip()
        m = _HEADING_RE.match(line)
        if m:
            name = m.group(1).strip()
            current = cat_set.get(name.lower())
            if current is None:
                # Unknown heading — map to Other if present
                current = cat_set.get("other")
            continue
        if current is None:
            continue
        bm = _BULLET_RE.match(line)
        if not bm:
            continue
        text = bm.group(2).strip()
        if text:
            result[current].append(text)
    return result


def parse_monthly_file(markdown: str, categories: list[str] | None = None) -> dict[str, list[str]]:
    """Parse an existing monthly file (bullets may already include *(YYYY-MM-DD)* tags)."""
    return parse_category_bullets(markdown, categories)


def _strip_day_tag(text: str) -> str:
    return _DAY_TAG_RE.sub("", text).strip()


def _bullet_day(text: str) -> str | None:
    m = _DAY_TAG_RE.match(text.strip())
    return m.group(1) if m else None


def merge_day_into_monthly(
    existing_markdown: str | None,
    day: date,
    day_sections: dict[str, list[str]],
    categories: list[str] | None = None,
    sources: list[str] | None = None,
) -> str:
    """
    Merge today's categorized bullets into the monthly document.

    - Bullets are stored as: *(YYYY-MM-DD)* summary
    - Re-running the same day replaces that day's bullets (idempotent)
    - Newest days stay near the top within each category
    """
    cats = categories or DEFAULT_CATEGORIES
    existing = parse_monthly_file(existing_markdown or "", cats)
    day_s = day.isoformat()

    merged: dict[str, list[str]] = {}
    for cat in cats:
        kept = [b for b in existing.get(cat, []) if _bullet_day(b) != day_s]
        fresh = [f"*({day_s})* {_strip_day_tag(b)}" for b in day_sections.get(cat, []) if b.strip()]
        # Newest first: today's items, then previous (already roughly newest-first)
        merged[cat] = fresh + kept

    src = ", ".join(sources) if sources else "AINews, AlphaSignal"
    lines = [
        f"# AI Tracking — {day.year:04d}-{day.month:02d}",
        "",
        f"> Sources: {src} · Updated: {day_s}",
        "",
    ]
    for cat in cats:
        bullets = merged.get(cat) or []
        if not bullets:
            continue
        lines.append(f"## {cat}")
        lines.append("")
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
