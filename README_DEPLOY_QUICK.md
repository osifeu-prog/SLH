# 🚀 SLH Release (API + Bot) — Transfer-Ready

This bundle contains:
- `api/` — FastAPI service exposing `POST /transfer/slh`
- `bot/` — Telegram bot with persistent menu and wallet saving

## ✅ What works
- Save user's wallet (users.json on disk)
- Keep the reply keyboard pinned/persistent
- Transfer SLH **from OPERATOR (custody)** to any 0x address via the API
- Health endpoint `/healthz`

## 🔧 Railway ENV (API)
Set on **slh_API** service:
```
SELA_TOKEN_ADDRESS=0xEf633c34715A5A581741379C9D690628A1C82B74
CHAIN_ID=56
BSC_RPC_URL=https://bsc-dataseed.binance.org
OPERATOR_PK=<private key WITHOUT 0x>
GAS_PRICE_GWEI=3
GAS_LIMIT=120000
```

Start command (Railway): `uvicorn main:app --host 0.0.0.0 --port 8080`

## 🔧 Railway ENV (Bot)
Set on **SLH_bot** service:
```
TELEGRAM_BOT_TOKEN=<your bot token>
SLH_API_BASE=https://slhapi-bot.up.railway.app
```

Start command: `python app_webhook.py`

## 🧪 One‑liner test (Windows PowerShell)
```powershell
Invoke-RestMethod -Uri "https://slhapi-bot.up.railway.app/healthz" -Method Get
$body = @{ to_addr = "0x2f6E71ab803C6877C0c592A817c07C47C3489f29"; amount_slh = "0.1" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://slhapi-bot.up.railway.app/transfer/slh" -Method Post -ContentType "application/json" -Body $body
```

## 🧭 In the bot
- `/start`
- send your `0x...` — the bot saves it
- press **💸 העברה** → paste friend address → send amount like `0.1`
- bot returns `tx_hash` on success

Good luck and have fun! 🎉
