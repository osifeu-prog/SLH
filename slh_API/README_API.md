# SLH_API quick check
- Start command on Railway:  uvicorn src.app:app --host 0.0.0.0 --port 8080
- Health:    GET /healthz  -> 200
- TokenInfo: GET /tokeninfo (also /api/tokeninfo, /v1/tokeninfo)
- Balance:   GET /balance/<address> (also /api/... , /v1/...)
- Estimate:  GET /estimate/<mint|transfer>/<to>/<amount>
- Mint:     POST /mint     JSON: {"to":"<addr>", "amount":"<wei>"}
- Transfer: POST /transfer JSON: {"to":"<addr>", "amount":"<wei>"}
Required ENV:
- BSC_RPC_URL
- SELA_TOKEN_ADDRESS (checksummed)
Optional (required for mint/transfer):
- TREASURY_PRIVATE_KEY, TREASURY_ADDRESS
- CHAIN_ID=97 (default), SELA_SYMBOL_OVERRIDE, SELA_DECIMALS_OVERRIDE, GAS_PRICE_FLOOR_WEI
