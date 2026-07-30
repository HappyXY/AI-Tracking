"""Shared paths and config loading for the AI Tracking agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
STATE_DIR = AGENT_DIR / ".state"
CONFIG_PATH = AGENT_DIR / "config.yaml"
EXAMPLE_CONFIG_PATH = AGENT_DIR / "config.example.yaml"
USER_CONFIG_DIR = Path.home() / ".config" / "ai-tracking"
MSAL_CACHE_PATH = USER_CONFIG_DIR / "msal_cache.bin"
PROCESSED_PATH = STATE_DIR / "processed.json"


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(AGENT_DIR / ".env")

    cfg_path = path or CONFIG_PATH
    if not cfg_path.exists():
        if EXAMPLE_CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Missing {cfg_path}. Copy agent/config.example.yaml to "
                "agent/config.yaml and fill in azure.client_id / llm settings."
            )
        raise FileNotFoundError(f"Missing config: {cfg_path}")

    with cfg_path.open(encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    azure = cfg.setdefault("azure", {})
    azure["client_id"] = os.getenv("AZURE_CLIENT_ID", azure.get("client_id") or "")

    llm = cfg.setdefault("llm", {})
    llm["api_key"] = os.getenv("OPENAI_API_KEY", llm.get("api_key") or "")
    llm["base_url"] = os.getenv("OPENAI_BASE_URL", llm.get("base_url") or "https://api.openai.com/v1")
    llm["model"] = os.getenv("OPENAI_MODEL", llm.get("model") or "gpt-4o-mini")

    git = cfg.setdefault("git", {})
    root = git.get("repo_root") or ""
    git["repo_root"] = str(Path(root).expanduser()) if root else str(REPO_ROOT)

    return cfg
