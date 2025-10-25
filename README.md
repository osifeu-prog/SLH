# SLH

Mono-repo:
- **slh_API** (FastAPI / Web3) – exposes: `/healthz`, `/tokeninfo`, `/balance/{address}`, `POST /mint`, `POST /send`
- **SLH_bot** (Telegram bot) – polling/webhook. Uses SLH_API_BASE.

> Secrets live only in local `.env` files (ignored by git).
