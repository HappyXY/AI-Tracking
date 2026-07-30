#!/usr/bin/env python3
"""Daily AI Tracking runner: Mail → LLM digest → monthly Markdown → git publish."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Allow `python agent/run.py` from repo root or agent/
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from outlook import fetch_messages, save_processed  # noqa: E402
from paths import PROCESSED_PATH, ensure_dirs, load_config  # noqa: E402
from publish import build_monthly_markdown, publish, write_digest  # noqa: E402
from summarize import summarize_sections  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch AI newsletters and publish a monthly digest")
    p.add_argument(
        "--date",
        type=str,
        default=None,
        help="Digest date YYYY-MM-DD (default: today)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + summarize, print merged monthly Markdown, skip git and processed-state",
    )
    p.add_argument(
        "--no-push",
        action="store_true",
        help="Commit locally but do not git push",
    )
    p.add_argument(
        "--skip-git",
        action="store_true",
        help="Write monthly digest file only; no commit/push",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs()
    cfg = load_config(args.config)

    day = date.fromisoformat(args.date) if args.date else date.today()
    backend = ((cfg.get("mail") or {}).get("backend") or "apple_mail").strip().lower()
    print(f"AI Tracking run for {day.isoformat()} (mail.backend={backend})")

    messages = fetch_messages(cfg)
    if not messages:
        print("No new matching emails in lookback window. Exiting.")
        return 0

    print(f"Fetched {len(messages)} message(s):")
    for m in messages:
        print(f"  - [{m.source_label}] {m.subject}")

    sections = summarize_sections(messages, cfg, day=day)
    repo_root = Path((cfg.get("git") or {}).get("repo_root") or AGENT_DIR.parent)
    monthly_md = build_monthly_markdown(repo_root, day, sections, cfg)

    if args.dry_run:
        print(f"\n----- monthly digest preview (digest/{day.year:04d}-{day.month:02d}.md) -----\n")
        print(monthly_md)
        return 0

    if args.skip_git:
        path = write_digest(repo_root, day, sections, cfg)
        print(f"Wrote {path}")
    else:
        if args.no_push:
            cfg.setdefault("git", {})["push"] = False
        path = publish(repo_root, day, sections, cfg)
        print(f"Digest at {path}")

    # Mark as processed only after successful write/publish
    ids = {m.internet_message_id or m.id for m in messages}
    existing: set[str] = set()
    if PROCESSED_PATH.exists():
        try:
            existing = set(json.loads(PROCESSED_PATH.read_text(encoding="utf-8")).get("ids", []))
        except (json.JSONDecodeError, OSError):
            existing = set()
    save_processed(existing | ids)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 — top-level CLI
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
