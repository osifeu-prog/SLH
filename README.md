# SLH Railway Aligned Starter

This pack contains two **Python** services, aligned to your Railway variables:

- `slh_API/` — FastAPI service exposing token endpoints (mint, transfer, estimate, tokeninfo, balance).
- `SLH_bot/` — Telegram bot service (python-telegram-bot v20) that uses the API.

## Railway Variables

### For `slh_API` service
- `BSC_RPC_URL` (required)
- `SELA_TOKEN_ADDRESS` (required, checksummed)
- `TREASURY_PRIVATE_KEY` (optional, required for on-chain mint/transfer)
- `TREASURY_ADDRESS` (optional, derived from private key if missing)
- `CHAIN_ID` (default 97 for BSC Testnet)
- `GAS_PRICE_FLOOR_WEI` (default 500000000)
- `SELA_DECIMALS_OVERRIDE` (optional; if not set, read from chain)
- `SELA_SYMBOL_OVERRIDE` (optional)
- `SELA_MINT_FUNCS` (compat string e.g. `ownerMint,mintTo,mint`)
- `NFT_CONTRACT` (optional, reserved for NFT expansion)
- `DEFAULT_WALLET` (optional, used by demo endpoints)
- `DEFAULT_META_CID` (optional, used by demo endpoints)
- `SELA_AMOUNT` (optional, used by demo endpoints)

### For `SLH_bot` service
- `TELEGRAM_BOT_TOKEN` (required)
- `SLH_API_BASE` (required; e.g. `https://<your-api>.up.railway.app` or local `http://localhost:8000`)
- `BOT_MODE` (optional: `polling` (default) or `webhook`)
- `BOT_WEBHOOK_PUBLIC_BASE` (required if webhook)
- `BOT_WEBHOOK_PATH` (default `/slh-bot`)
- `BOT_WEBHOOK_SECRET` (optional HMAC header value)
- `ADMIN_CHAT_IDS` (comma separated)
- `DEFAULT_WALLET`, `DEFAULT_META_CID`, `SELA_AMOUNT` (optional pass-through)
- `LOG_LEVEL` (default `INFO`)
- `TZ` (default `UTC`)
- `PYTHONUNBUFFERED` (default `1`)

## Local Dev

```bash
# API
cd slh_API
python -m venv .venv && source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env  # edit values
uvicorn app:app --reload --port 8000

# BOT
cd ../SLH_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # set TELEGRAM_BOT_TOKEN and SLH_API_BASE at least
python bot.py
```

## Endpoints (API)

- `GET /health`
- `GET /tokeninfo`
- `GET /balance/{address}`
- `GET /estimate/{op}` — query `to`, `amount` (human units), `gasPriceWei` optional
- `POST /mint` — body: `{"to": "...", "amount": "10.5"}` (human units); needs TREASURY_PRIVATE_KEY
- `POST /transfer` — same shape; needs TREASURY_PRIVATE_KEY

All math uses on-chain decimals (or `SELA_DECIMALS_OVERRIDE`). Addresses validated to EIP‑55 checksum.
