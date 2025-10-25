"""
FastAPI shim for SLH:
/healthz, /tokeninfo, /balance/{address}, /mint
Env: BSC_RPC_URL, CHAIN_ID, SELA_TOKEN_ADDRESS, TREASURY_PRIVATE_KEY (opt),
SELA_DECIMALS_OVERRIDE, SELA_SYMBOL_OVERRIDE, SELA_MINT_FUNCS, GAS_PRICE_FLOOR_WEI
"""
import os
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from web3 import Web3
from web3.middleware import geth_poa_middleware

app = FastAPI(title="SLH API Shim")

BSC_RPC_URL = os.getenv("BSC_RPC_URL", "").strip()
CHAIN_ID = int(os.getenv("CHAIN_ID", "56"))
TOKEN_ADDR = Web3.to_checksum_address(os.getenv("SELA_TOKEN_ADDRESS", "0x0000000000000000000000000000000000000000"))
DEC_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE")
SYM_OVERRIDE = os.getenv("SELA_SYMBOL_OVERRIDE")
MINT_FUNCS: List[str] = [x.strip() for x in os.getenv("SELA_MINT_FUNCS", "ownerMint,mint").split(",") if x.strip()]
GAS_PRICE_FLOOR_WEI = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0"))
TREASURY_PK = os.getenv("TREASURY_PRIVATE_KEY", "").strip()

if not BSC_RPC_URL:
    raise RuntimeError("BSC_RPC_URL missing")

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL, request_kwargs={"timeout": 30}))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

TREASURY_ADDR = None
if TREASURY_PK:
    try:
        TREASURY_ADDR = w3.eth.account.from_key(TREASURY_PK).address
    except Exception:
        TREASURY_ADDR = None

ERC20_ABI = [
  {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}
]
for mf in MINT_FUNCS:
  ERC20_ABI.append({"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":mf,"outputs":[],"type":"function"})

token = w3.eth.contract(address=TOKEN_ADDR, abi=ERC20_ABI)

def _gas_price():
    try:
        gp = w3.eth.gas_price
    except Exception:
        gp = w3.to_wei("2", "gwei")
    return max(gp, GAS_PRICE_FLOOR_WEI)

def _decimals():
    if DEC_OVERRIDE and DEC_OVERRIDE.isdigit():
        return int(DEC_OVERRIDE)
    try:
        return token.functions.decimals().call()
    except Exception:
        return 18

def _symbol():
    if SYM_OVERRIDE:
        return SYM_OVERRIDE
    try:
        return token.functions.symbol().call()
    except Exception:
        return "SELA"

@app.get("/healthz")
def healthz():
    try:
        block = w3.eth.block_number
        return {"ok": True, "chain_id": CHAIN_ID, "block": block}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/tokeninfo")
@app.get("/api/tokeninfo")
@app.get("/v1/tokeninfo")
def tokeninfo():
    try:
        try:
            name = token.functions.name().call()
        except Exception:
            name = "Token"
        return {
            "address": TOKEN_ADDR,
            "name": name,
            "symbol": _symbol(),
            "decimals": _decimals(),
            "totalSupply": str(token.functions.totalSupply().call()),
            "chainId": CHAIN_ID
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"tokeninfo error: {e}")

@app.get("/balance/{address}")
@app.get("/api/balance/{address}")
@app.get("/v1/balance/{address}")
def balance(address: str):
    try:
        addr = Web3.to_checksum_address(address)
        bal = token.functions.balanceOf(addr).call()
        return {"address": addr, "balance": str(bal), "decimals": _decimals(), "symbol": _symbol()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"balance error: {e}")

class MintReq(BaseModel):
    to: str = Field(..., description="recipient address")
    amount: str = Field(..., description="human amount, scaled by decimals")

def _mint_fn():
    for mf in MINT_FUNCS:
        if hasattr(token.functions, mf):
            return getattr(token.functions, mf)
    return None

@app.post("/mint")
@app.post("/api/mint")
@app.post("/v1/mint")
def mint(req: MintReq):
    if not TREASURY_PK or not TREASURY_ADDR:
        raise HTTPException(status_code=403, detail="mint disabled: missing TREASURY_PRIVATE_KEY")
    mf = _mint_fn()
    if not mf:
        raise HTTPException(status_code=400, detail=f"mint function not found. Tried: {MINT_FUNCS}")
    try:
        to = Web3.to_checksum_address(req.to)
        dec = _decimals()
        if dec == 18:
            amt = int(Web3.to_wei(str(req.amount), "ether"))
        else:
            amt = int(float(req.amount) * (10 ** dec))
        nonce = w3.eth.get_transaction_count(TREASURY_ADDR)
        tx = mf(to, amt).build_transaction({
            "chainId": CHAIN_ID,
            "from": TREASURY_ADDR,
            "nonce": nonce,
            "gasPrice": _gas_price()
        })
        tx["gas"] = w3.eth.estimate_gas(tx)
        signed = w3.eth.account.sign_transaction(tx, private_key=TREASURY_PK)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        return {"txHash": tx_hash.hex(), "from": TREASURY_ADDR, "to": to, "amount": str(amt)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"mint error: {e}")
