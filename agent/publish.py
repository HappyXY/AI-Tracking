"""Write monthly digest Markdown and commit/push to git."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from monthly import DEFAULT_CATEGORIES, merge_day_into_monthly, monthly_path, parse_category_bullets


def digest_path(repo_root: Path, day: date) -> Path:
    """Path to the monthly digest file for the given day."""
    return monthly_path(repo_root, day)


def build_monthly_markdown(
    repo_root: Path,
    day: date,
    day_markdown_or_sections: str | dict[str, list[str]],
    cfg: dict[str, Any],
) -> str:
    categories = cfg.get("categories") or list(DEFAULT_CATEGORIES)
    if isinstance(day_markdown_or_sections, dict):
        day_sections = day_markdown_or_sections
    else:
        day_sections = parse_category_bullets(day_markdown_or_sections, categories)

    path = monthly_path(repo_root, day)
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    sources = None
    mail_cfg = cfg.get("mail") or {}
    # Prefer labels from keywords config for the header
    kws = mail_cfg.get("sender_keywords") or []
    if kws:
        # Stable display names
        sources = ["AINews", "AlphaSignal"]

    return merge_day_into_monthly(
        existing,
        day,
        day_sections,
        categories=categories,
        sources=sources,
    )


def write_digest(
    repo_root: Path,
    day: date,
    markdown_or_sections: str | dict[str, list[str]],
    cfg: dict[str, Any] | None = None,
) -> Path:
    cfg = cfg or {}
    content = build_monthly_markdown(repo_root, day, markdown_or_sections, cfg)
    path = monthly_path(repo_root, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        text=True,
        capture_output=True,
    )


def publish(
    repo_root: Path,
    day: date,
    markdown_or_sections: str | dict[str, list[str]],
    cfg: dict[str, Any],
) -> Path | None:
    git_cfg = cfg.get("git") or {}
    remote = git_cfg.get("remote") or "origin"
    branch = git_cfg.get("branch") or "main"
    prefix = git_cfg.get("commit_prefix") or "digest"
    do_push = bool(git_cfg.get("push", True))

    path = write_digest(repo_root, day, markdown_or_sections, cfg)
    rel = path.relative_to(repo_root)

    # Best-effort sync before commit
    _run_git(repo_root, "pull", "--rebase", remote, branch, check=False)

    _run_git(repo_root, "add", str(rel))
    status = _run_git(repo_root, "status", "--porcelain", str(rel))
    if not status.stdout.strip():
        print(f"No changes to commit for {rel}")
        return path

    month = f"{day.year:04d}-{day.month:02d}"
    msg = f"{prefix}: {month} (+{day.isoformat()})"
    _run_git(repo_root, "commit", "-m", msg)

    if do_push:
        push = _run_git(repo_root, "push", "-u", remote, branch, check=False)
        if push.returncode != 0:
            raise RuntimeError(f"git push failed:\n{push.stderr or push.stdout}")
        print(f"Pushed {rel} ({msg})")
    else:
        print(f"Committed {rel} ({msg}); push disabled")

    return path
