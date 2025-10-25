
# SLH API (FastAPI)

Endpoints:
- `GET /healthz`
- `GET /tokeninfo` (also `/api/tokeninfo`, `/v1/tokeninfo`)
- `GET /balance/{address}`
- `GET /estimate/{op}?to=...&amount=...` (op: mint|transfer)
- `POST /mint` (body: {"to","amount(wei)"})
- `POST /transfer` (body: {"to","amount(wei)"})

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export BSC_RPC_URL=...
export SELA_TOKEN_ADDRESS=...
uvicorn src.app:app --host 0.0.0.0 --port 8080
```

## Docker
```bash
docker build -t slh-api .
docker run -p 8080:8080 --env-file ./env.example slh-api
```
