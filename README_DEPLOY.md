# SLH Deploy Pack — Bot + API (BNB Chain)

This pack gives you a clean, production-ready baseline for:
- **slh_API** (FastAPI + Web3): `/healthz`, `/token/balance/{addr}`, `/transfer/slh`
- **SLH_bot** (python-telegram-bot v20): `/start`, `/setwallet`, `/balance`, `/send`

## Quick Start (Local, with Docker Compose)

1) Copy `.env.example` to `.env` and fill values.
2) (Optional) Copy `api/.env.example` -> `api/.env`, and `bot/.env.example` -> `bot/.env`
3) Run:
```bash
docker compose up --build
```
4) Bot will run in polling mode. API will expose port **8080**.  
5) Test API:
```bash
curl http://localhost:8080/healthz
```

## Railway (Two Services)

- Service 1: **slh_API**
  - Start command: `uvicorn api.main:app --host 0.0.0.0 --port 8080`
  - PORT: `8080`
  - Vars (minimum):  
    `BSC_RPC_URL`, `CHAIN_ID`, `SELA_TOKEN_ADDRESS`, `OPERATOR_PK`  
    Optional: `INTERNAL_API_KEY`, `GAS_PRICE_GWEI`, `GAS_LIMIT`
- Service 2: **SLH_bot**
  - Start command: `python bot/bot.py`
  - Vars: `TELEGRAM_BOT_TOKEN`, `SLH_API_BASE`, `PERSIST_FILE="data/users.json"`  
    Optional: `APPROVED_CHAT_ID`, `USE_WEBHOOK`, `WEBHOOK_URL`, `LOG_LEVEL`

> Security: If you set `INTERNAL_API_KEY` on the API, set the same value in the bot's env as `INTERNAL_API_KEY`. The bot will send it as `X-Internal-Key` header in `/transfer/slh` calls.

## Network Modes

- **Mainnet** (default): `CHAIN_ID=56`, `BSC_RPC_URL=https://bsc-dataseed.binance.org`
- **Testnet**: `CHAIN_ID=97`, `BSC_RPC_URL=https://data-seed-prebsc-1-s1.binance.org:8545/`

Prefer to verify on **Testnet** first with a Test token + BNB-t for gas.

## Health & Logs

- API: `/healthz` returns `chain_id`, `operator_address`, `token_address`
- Bot: `LOG_LEVEL=DEBUG` during tests; revert to `INFO` in production.

## Files

- `docker-compose.yml`: local stack
- `api/`: FastAPI app + ERC20 ABI
- `bot/`: Telegram bot + simple JSON store (atomic)
- `scripts/`: helper scripts for local run

---
**Note:** This is a minimal, safe baseline. For persistent user data in production, replace JSON store with a database (e.g., SQLite/PG/Redis) and add rate-limiting & auth in API.