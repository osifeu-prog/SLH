# SLH Railway Stable Pack (API + Bot)

**API** (FastAPI) exposes `/healthz`, `/tokeninfo`, `/balance/{address}`, `/estimate/{op}/{to}/{amount}`, `POST /mint`, `POST /transfer`.
Same endpoints also work under `/api/...` and `/v1/...`.

**Bot** (python-telegram-bot) supports `/start`, `/tokeninfo`, `/balance`, `/estimate`, `/mint`, `/send`.

## Railway ENV
### slh_API
- `BSC_RPC_URL` (required)
- `SELA_TOKEN_ADDRESS` (required, checksummed)
- `TREASURY_PRIVATE_KEY` + `TREASURY_ADDRESS` (for write ops)
- `CHAIN_ID=97` (BSC testnet), `SELA_SYMBOL_OVERRIDE=SLH` (optional), `SELA_DECIMALS_OVERRIDE=18` (optional), `GAS_PRICE_FLOOR_WEI` (optional)

Start: `uvicorn src.app:app --host 0.0.0.0 --port 8080`

### SLH_bot
- `TELEGRAM_BOT_TOKEN` (required)
- `SLH_API_BASE` (e.g. `https://slhapi-bot.up.railway.app`)
- `ADMIN_CHAT_IDS` (optional), `LOG_LEVEL=INFO` (optional)

Start: `python -m src.bot`
