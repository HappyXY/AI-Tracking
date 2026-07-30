"""Write digest Markdown and commit/push to git."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from typing import Any


def digest_path(repo_root: Path, day: date) -> Path:
    return repo_root / "digest" / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"


def write_digest(repo_root: Path, day: date, markdown: str) -> Path:
    path = digest_path(repo_root, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        text=True,
        capture_output=True,
    )


def publish(repo_root: Path, day: date, markdown: str, cfg: dict[str, Any]) -> Path | None:
    git_cfg = cfg.get("git") or {}
    remote = git_cfg.get("remote") or "origin"
    branch = git_cfg.get("branch") or "main"
    prefix = git_cfg.get("commit_prefix") or "digest"
    do_push = bool(git_cfg.get("push", True))

    path = write_digest(repo_root, day, markdown)
    rel = path.relative_to(repo_root)

    # Best-effort sync before commit
    _run_git(repo_root, "pull", "--rebase", remote, branch, check=False)

    _run_git(repo_root, "add", str(rel))
    status = _run_git(repo_root, "status", "--porcelain", str(rel))
    if not status.stdout.strip():
        print(f"No changes to commit for {rel}")
        return path

    msg = f"{prefix}: {day.isoformat()}"
    _run_git(repo_root, "commit", "-m", msg)

    if do_push:
        push = _run_git(repo_root, "push", remote, branch, check=False)
        if push.returncode != 0:
            raise RuntimeError(
                f"git push failed:\n{push.stderr or push.stdout}"
            )
        print(f"Pushed {rel} ({msg})")
    else:
        print(f"Committed {rel} ({msg}); push disabled")

    return path
