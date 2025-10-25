
# SLH_Railway_Stable

Two services ready for Railway:

```
SLH_Railway_Stable/
 ├─ slh_API/       # FastAPI + Web3
 └─ SLH_bot/       # Telegram bot (webhook-ready)
```

## Railway (quick)
- Create two services from these folders (Dockerfile-based).
- Fill envs from `env.example` files.
- API should answer `/healthz`, `/tokeninfo`, `/balance/{address}`.
- Bot will use webhook if `PUBLIC_URL` is set, otherwise polling.

## Smoke tests (curl)
```bash
curl -s https://<api>.railway.app/healthz
curl -s https://<api>.railway.app/tokeninfo
curl -s https://<api>.railway.app/balance/0x693db6c817083818696a7228aEbfBd0Cd3371f02
```

## Notes
- Amounts are in **wei**.
- For write ops, API requires `TREASURY_PRIVATE_KEY` (+ some BNB testnet for gas).
