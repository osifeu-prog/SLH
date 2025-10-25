# SLH Railway Aligned Starter

## Quick Ops

### API (slh_API)
- Endpoints are registered **with and without** prefix:
  - `/healthz`
  - `/tokeninfo`, `/api/tokeninfo`, `/v1/tokeninfo`
  - `/balance/{address}`, `/api/balance/{address}`, `/v1/balance/{address}`
  - `/estimate/{op}/{to}/{amount}` (+ `/api/...`, `/v1/...`)
  - `POST /mint`, `POST /transfer` (+ `/api/...`, `/v1/...`)
- ENV (Railway):
  - `BSC_RPC_URL` (required)
  - `SELA_TOKEN_ADDRESS` (required — checksummed)
  - `TREASURY_PRIVATE_KEY`, `TREASURY_ADDRESS` (for mint/transfer from owner)
  - `CHAIN_ID=97`, `SELA_SYMBOL_OVERRIDE=SLH`, `SELA_DECIMALS_OVERRIDE=18` (optional)
  - `GAS_PRICE_FLOOR_WEI` (optional)
- Run local:
  ```powershell
  cd slh_API
  python -m venv .venv && .\\.venv\\Scripts\\Activate.ps1
  pip install -r requirements.txt
  uvicorn src.app:app --host 0.0.0.0 --port 8080
  ```

### Bot (SLH_bot)
- Commands:
  - `/start`, `/tokeninfo`, `/balance <addr>`, `/estimate <mint|transfer> <to> <amount>`, `/mint`, `/send`
- ENV (Railway):
  - `TELEGRAM_BOT_TOKEN` (required)
  - `SLH_API_BASE` → e.g. `https://slhapi-bot.up.railway.app` (no trailing slash)
  - `ADMIN_CHAT_IDS` → comma-separated list (optional; empty = allow all)
  - `LOG_LEVEL=INFO`, `TZ`, etc. (optional)
- Run local:
  ```powershell
  cd SLH_bot
  python -m venv .venv && .\\.venv\\Scripts\\Activate.ps1
  pip install -r requirements.txt
  python src/bot.py
  ```

### Notes
- Bot tries `/tokeninfo` and falls back to `/api/tokeninfo` automatically.
- API exposes both root and `/api` and `/v1` routes — לא צריך לשנות את SLH_API_BASE אם תשאירו אותה בשורש.
- כל הכתובות נבדקות ב־EIP-55 (checksum). שגיאת כתובת תחזיר 400.
