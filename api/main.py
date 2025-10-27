# FastAPI SLH Transfer API
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import os
from web3 import Web3
from decimal import Decimal

# ------- ENV -------
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
CHAIN_ID = int(os.getenv("CHAIN_ID", "56"))
SELA_TOKEN_ADDRESS = os.getenv("SELA_TOKEN_ADDRESS", "0xEf633c34715A5A581741379C9D690628A1C82B74")
OPERATOR_PK = os.getenv("OPERATOR_PK", "").removeprefix("0x")
GAS_PRICE_GWEI = int(os.getenv("GAS_PRICE_GWEI", "3"))
GAS_LIMIT = int(os.getenv("GAS_LIMIT", "120000"))

# ------- WEB3 -------
w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))

ERC20_ABI = [
  {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
  {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}
]
token = w3.eth.contract(address=Web3.to_checksum_address(SELA_TOKEN_ADDRESS), abi=ERC20_ABI)

def _operator_address() -> str:
    if not OPERATOR_PK:
        raise RuntimeError("OPERATOR_PK is missing")
    acct = w3.eth.account.from_key(OPERATOR_PK)
    return acct.address

def _to_wei(amount_slh: str|float|int) -> int:
    dec = token.functions.decimals().call()
    q = Decimal(str(amount_slh))
    return int(q * (Decimal(10) ** dec))

class TransferRequest(BaseModel):
    to_addr: str = Field(..., description="Recipient EVM address 0x...")
    amount_slh: str = Field(..., description="Human amount, e.g., '0.1'")

class TransferResponse(BaseModel):
    ok: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    network_mode: str = "mainnet"
    chain_id: int = CHAIN_ID
    token: str = SELA_TOKEN_ADDRESS

app = FastAPI(title="SLH Transfer API", version="1.0.0")

@app.get("/healthz")
def healthz():
    try:
        name = token.functions.name().call()
        symbol = token.functions.symbol().call()
        return {
            "ok": True,
            "network_mode": "mainnet" if CHAIN_ID == 56 else "testnet",
            "chain_id": CHAIN_ID,
            "token": SELA_TOKEN_ADDRESS,
            "token_name": name,
            "token_symbol": symbol
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/transfer/slh", response_model=TransferResponse)
def transfer_slh(req: TransferRequest):
    from web3 import Web3
    try:
        # Basic validations
        if not w3.is_address(req.to_addr):
            raise HTTPException(status_code=400, detail="Invalid to_addr")

        if not OPERATOR_PK:
            raise HTTPException(status_code=500, detail="Operator key missing")

        sender = _operator_address()
        to_checksum = Web3.to_checksum_address(req.to_addr)

        amount_wei = _to_wei(req.amount_slh)
        if amount_wei <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")

        # Check operator balance
        op_bal = token.functions.balanceOf(sender).call()
        if op_bal < amount_wei:
            raise HTTPException(status_code=402, detail="Operator has insufficient SLH balance")

        # Build tx
        nonce = w3.eth.get_transaction_count(sender)
        tx = token.functions.transfer(to_checksum, amount_wei).build_transaction({
            "from": sender,
            "chainId": CHAIN_ID,
            "nonce": nonce,
            "gas": GAS_LIMIT,
            "gasPrice": w3.to_wei(GAS_PRICE_GWEI, "gwei"),
        })

        signed = w3.eth.account.sign_transaction(tx, private_key=OPERATOR_PK)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction).hex()

        return TransferResponse(ok=True, tx_hash=tx_hash)
    except HTTPException as he:
        raise he
    except Exception as e:
        return TransferResponse(ok=False, error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
