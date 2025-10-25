
# SLH Bot (Telegram)

Commands:
- `/start`
- `/tokeninfo`
- `/balance <address>`
- `/estimate <mint|transfer> <to> <amount_wei>`
- `/mint <to> <amount_wei>`
- `/send <to> <amount_wei>`

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export SLH_API_BASE=http://127.0.0.1:8080
python src/bot.py
```
If `PUBLIC_URL` is set, the bot serves a webhook on `PORT` (default 8080). Otherwise it falls back to polling.
