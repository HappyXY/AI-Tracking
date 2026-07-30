# AI Tracking

Daily digests of AI progress from **AINews** and **AlphaSignal** (Apple Mail → categorized Markdown → this repo).

## Layout

```text
digest/YYYY/MM/YYYY-MM-DD.md   # daily digests
agent/                         # local runner
```

## One-time setup (Apple Mail — recommended, free)

Classic Outlook for Mac now requires a Microsoft 365 subscription to go online.  
This project defaults to **Apple Mail**, which can sync Outlook.com / Microsoft accounts without Office.

### 1. Add your Microsoft account to Mail.app

1. Open **Mail** (邮件)
2. **Mail → Settings → Accounts** → add account → **Microsoft Exchange** or **Outlook.com** / Microsoft 365
3. Sign in with the mailbox that receives AINews / AlphaSignal
4. Wait until messages appear in the inbox

### 2. Python env

```bash
cd /path/to/AI-Tracking
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp agent/config.example.yaml agent/config.yaml   # if needed
cp .env.example .env
```

Edit `.env`:

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-flash
```

`mail.backend` defaults to `apple_mail` — no Azure / no M365.

### 3. Automation permission

First run may prompt: allow Terminal / Cursor to control **Mail**.

System Settings → Privacy & Security → Automation.

### 4. Dry-run

```bash
./agent/run.sh --dry-run
```

### 5. Publish + daily schedule

```bash
./agent/run.sh
./agent/launchd/install_launchd.sh   # daily 09:00
```

## Other backends (optional)

```yaml
mail:
  backend: apple_mail   # default — Apple Mail
  # backend: mac        # classic Outlook (needs M365 online)
  # backend: graph      # Microsoft Graph (needs your own Entra app)
```

## Digest format

```markdown
# AI Digest — 2026-07-20

Sources: AINews, AlphaSignal

## LLM
- ...
```

Empty categories are omitted.

## Notes

- Duplicate emails are skipped via `agent/.state/processed.json` (local).
- If the Mac is asleep/off at 09:00, run `./agent/run.sh` manually that day.
