"""Fetch newsletter messages from macOS Apple Mail via AppleScript (no M365 needed)."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta
from typing import Any

from mail_common import (
    MailMessage,
    html_to_text,
    load_processed,
    matches_sender,
    source_label,
    truncate_body,
)

REC_SEP = "\x1e"
FIELD_SEP = "\x1f"


def _run_osascript(script: str, timeout: int = 180) -> str:
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("osascript not found — Apple Mail backend requires macOS.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Mail AppleScript timed out. Is Mail.app hung or syncing?") from exc

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        hint = ""
        low = err.lower()
        if "not allowed" in low or "not authorized" in low or "1002" in err:
            hint = (
                "\nGrant Automation permission: System Settings → Privacy & Security → "
                "Automation → allow your terminal/Python to control Mail."
            )
        raise RuntimeError(f"Mail AppleScript failed:\n{err}{hint}")

    return proc.stdout or ""


def _parse_mail_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    patterns = [
        "%A, %B %d, %Y at %I:%M:%S %p",
        "%A, %B %d, %Y at %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%d/%m/%Y %H:%M:%S",
        "%Y年%m月%d日 %H:%M:%S",
    ]
    cleaned = re.sub(r"\s+", " ", value)
    for fmt in patterns:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _fetch_raw(lookback_hours: int, scan_limit: int) -> str:
    # Mail.app: scan inbox messages (usually newest-first).
    script = f'''
set recSep to (ASCII character 30)
set fieldSep to (ASCII character 31)
set lookbackHours to {int(lookback_hours)}
set scanLimit to {int(scan_limit)}
set cutOff to (current date) - (lookbackHours * hours)
set outText to ""
set taken to 0

tell application "Mail"
  if (count of accounts) is 0 then error "Mail.app has no accounts. Add your Outlook.com / Microsoft account in Mail → Settings → Accounts."

  set msgs to {{}}
  try
    set msgs to (messages of inbox whose date received ≥ cutOff)
  on error
    try
      set msgs to messages of inbox
    on error
      set msgs to {{}}
    end try
  end try

  set total to count of msgs
  if total is 0 then return ""

  repeat with i from 1 to total
    if taken ≥ scanLimit then exit repeat
    set m to item i of msgs

    set mid to ""
    set subj to ""
    set senderText to ""
    set recvText to ""
    set bodyText to ""
    set recv to missing value

    try
      set recv to date received of m
    end try
    if recv is not missing value and recv < cutOff then
      -- skip older
    else
      try
        set mid to message id of m as string
      end try
      if mid is "" then
        try
          set mid to (id of m as string)
        end try
      end if
      try
        set subj to subject of m as string
      end try
      try
        set senderText to sender of m as string
      end try
      try
        if recv is not missing value then set recvText to (recv as string)
      end try
      try
        set bodyText to content of m as string
      end try

      set outText to outText & mid & fieldSep & subj & fieldSep & senderText & fieldSep & recvText & fieldSep & bodyText & recSep
      set taken to taken + 1
    end if
  end repeat
end tell

return outText
'''
    return _run_osascript(script)


def _inbox_count() -> int:
    out = _run_osascript(
        'tell application "Mail" to return (count of messages of inbox) as string',
        timeout=60,
    )
    try:
        return int((out or "0").strip() or "0")
    except ValueError:
        return 0


def fetch_messages_apple_mail(cfg: dict[str, Any]) -> list[MailMessage]:
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
    scan_limit = int(mail_cfg.get("mac_scan_limit") or max(max_messages * 5, 80))

    processed = load_processed()
    cut_off = datetime.now() - timedelta(hours=lookback_hours)

    raw = _fetch_raw(lookback_hours, scan_limit)
    if not raw.strip():
        count = _inbox_count()
        if count == 0:
            raise RuntimeError(
                "Mail.app inbox has 0 messages.\n"
                "1) Open Mail → Settings → Accounts → add your Microsoft / Outlook.com account\n"
                "2) Wait until inbox finishes syncing\n"
                "3) Re-run ./agent/run.sh --dry-run"
            )
        print(
            f"Scanned Mail.app inbox ({count} messages) but none matched "
            f"keywords {keywords} in the last {lookback_hours}h "
            f"(or all matched mail was already processed)."
        )
        return []

    messages: list[MailMessage] = []
    for record in raw.split(REC_SEP):
        if not record.strip():
            continue
        parts = record.split(FIELD_SEP, 4)
        if len(parts) < 5:
            continue
        mid, subject, sender, received, body = parts
        mid = mid.strip()
        subject = subject.strip() or "(no subject)"
        sender = sender.strip()
        received = received.strip()
        body = body or ""

        dedupe_key = mid or f"{sender}|{subject}|{received}"
        if not dedupe_key or dedupe_key in processed:
            continue
        if not matches_sender(sender, subject, keywords):
            continue

        recv_dt = _parse_mail_date(received)
        if recv_dt is not None and recv_dt < cut_off:
            continue

        if re.search(r"<\s*(html|body|div|p|br|table)\b", body, re.I):
            text = html_to_text(body)
        else:
            text = body.strip()
        text = truncate_body(text, max_body_chars)

        messages.append(
            MailMessage(
                id=mid,
                internet_message_id=dedupe_key,
                subject=subject,
                sender=sender,
                received_at=received,
                body_text=text,
                web_link="",
                source_label=source_label(sender, subject, keywords),
            )
        )
        if len(messages) >= max_messages:
            break

    return messages
