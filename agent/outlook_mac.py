"""Fetch newsletter messages from the Microsoft Outlook Mac desktop app via AppleScript."""

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

# Record / field separators unlikely to appear in normal mail metadata
REC_SEP = "\x1e"
FIELD_SEP = "\x1f"
OUTLOOK_DEFAULTS_DOMAIN = "com.microsoft.Outlook"


def _is_new_outlook() -> bool:
    """New Outlook (Monarch) does not expose synced mail to AppleScript."""
    try:
        proc = subprocess.run(
            ["defaults", "read", OUTLOOK_DEFAULTS_DOMAIN, "IsRunningNewOutlook"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip() in {"1", "true", "YES"}:
            return True
        proc2 = subprocess.run(
            ["defaults", "read", OUTLOOK_DEFAULTS_DOMAIN, "RunningNewOutlook"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc2.returncode == 0 and proc2.stdout.strip() in {"1", "true", "YES"}
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _new_outlook_error() -> RuntimeError:
    return RuntimeError(
        "Detected New Outlook (IsRunningNewOutlook=1). AppleScript cannot read synced mail "
        "in New Outlook — inbox appears empty.\n\n"
        "Fix: open Microsoft Outlook → menu bar → turn OFF «New Outlook» "
        "(use classic Outlook), then sign in / wait for inbox sync, and re-run.\n"
        "Or from Terminal (then fully quit & reopen Outlook):\n"
        "  defaults write com.microsoft.Outlook IsRunningNewOutlook -bool false\n"
        "  defaults write com.microsoft.Outlook RunningNewOutlook -bool false"
    )


def _inbox_message_count() -> int:
    out = _run_osascript(
        'tell application "Microsoft Outlook" to return (count of messages of inbox) as string',
        timeout=60,
    )
    try:
        return int((out or "0").strip() or "0")
    except ValueError:
        return 0


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
        raise RuntimeError("osascript not found — Path B requires macOS.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Outlook AppleScript timed out. Is Outlook hung or syncing?") from exc

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        hint = ""
        low = err.lower()
        if "not allowed assistive" in low or "not authorized" in low or "1002" in err:
            hint = (
                "\nGrant Automation permission: System Settings → Privacy & Security → "
                "Automation → allow your terminal/Python to control Microsoft Outlook."
            )
        if "new outlook" in low or "doesn’t understand" in low or "does not understand" in low:
            hint += (
                "\nIf you use New Outlook, turn it OFF: Outlook → Settings/Help → "
                "uncheck New Outlook (classic Outlook has AppleScript support)."
            )
        raise RuntimeError(f"Outlook AppleScript failed:\n{err}{hint}")

    return proc.stdout or ""


def _fetch_raw(lookback_hours: int, scan_limit: int) -> str:
    # Classic Microsoft Outlook for Mac scripting dictionary.
    # Prefer whose-date filter; then take up to scan_limit messages.
    script = f'''
set recSep to (ASCII character 30)
set fieldSep to (ASCII character 31)
set lookbackHours to {int(lookback_hours)}
set scanLimit to {int(scan_limit)}
set cutOff to (current date) - (lookbackHours * hours)
set outText to ""
set taken to 0

tell application "Microsoft Outlook"
  if not (exists inbox) then error "Outlook inbox not found. Is an account signed in?"

  set msgs to {{}}
  try
    set msgs to (messages of inbox whose time received ≥ cutOff)
  on error
    set msgs to messages of inbox
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
      set recv to time received of m
    end try
    if recv is not missing value and recv < cutOff then
      -- skip older when falling back to unfiltered inbox list
    else
      try
        set mid to (id of m) as string
      end try
      try
        set subj to subject of m as string
      end try
      try
        set s to sender of m
        set sName to ""
        set sAddr to ""
        try
          set sName to name of s as string
        end try
        try
          set sAddr to address of s as string
        end try
        set senderText to sName & " <" & sAddr & ">"
      end try
      try
        if recv is not missing value then set recvText to (recv as string)
      end try
      try
        set bodyText to plain text content of m as string
      end try
      if bodyText is "" then
        try
          set bodyText to content of m as string
        end try
      end if

      set outText to outText & mid & fieldSep & subj & fieldSep & senderText & fieldSep & recvText & fieldSep & bodyText & recSep
      set taken to taken + 1
    end if
  end repeat
end tell

return outText
'''
    return _run_osascript(script)


def _parse_outlook_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    # AppleScript date strings vary by locale, e.g.
    # "Monday, July 27, 2026 at 9:15:00 AM"
    # Try a few common patterns; fall back to accepting the message.
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


def fetch_messages_mac(cfg: dict[str, Any]) -> list[MailMessage]:
    if _is_new_outlook():
        # Fail fast with actionable guidance instead of a silent empty inbox.
        raise _new_outlook_error()

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
        count = _inbox_message_count()
        if count == 0:
            raise RuntimeError(
                "Outlook classic inbox has 0 messages. "
                "Sign in to your account in Outlook and wait until mail finishes syncing, "
                "then re-run. (If New Outlook is on, turn it off first.)"
            )
        print(
            f"Scanned Outlook inbox ({count} messages) but none matched "
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

        recv_dt = _parse_outlook_date(received)
        if recv_dt is not None and recv_dt < cut_off:
            continue

        # Body may be HTML from `content` fallback
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


def check_outlook_available() -> str:
    """Return Outlook app name if scriptable; raise with guidance otherwise."""
    script = '''
    try
      tell application "System Events"
        if not (exists process "Microsoft Outlook") then
          -- app may still be scriptable when not running; continue
        end if
      end tell
      tell application "Microsoft Outlook"
        return name
      end tell
    on error errMsg number errNum
      error errMsg & " (" & errNum & ")"
    end try
    '''
    return _run_osascript(script, timeout=60).strip()
