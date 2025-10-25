from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
from web3 import Web3

app = FastAPI(title="SLH API", version="1.0.0")

# --- ENV ---
CHAIN_ID               = int(os.getenv("CHAIN_ID", "97"))               # default BSC testnet
BSC_RPC_URL            = os.getenv("BSC_RPC_URL", "")
SELA_TOKEN_ADDRESS     = os.getenv("SELA_TOKEN_ADDRESS", "")
SELA_SYMBOL_OVERRIDE   = os.getenv("SELA_SYMBOL_OVERRIDE")
SELA_DECIMALS_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE")
SELA_MINT_FUNCS        = os.getenv("SELA_MINT_FUNCS", "ownerOnly:mint")
GAS_PRICE_FLOOR_WEI    = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0") or 0)

TREASURY_PRIVATE_KEY   = os.getenv("TREASURY_PRIVATE_KEY", "")
TREASURY_ADDRESS       = os.getenv("TREASURY_ADDRESS", "")

# --- Web3 setup ---
w3 = None
token = None

ERC20_MIN_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

def _init_web3():
    global w3, token
    if not BSC_RPC_URL:
        return
    w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL, request_kwargs={"timeout": 20}))
    if SELA_TOKEN_ADDRESS and w3.is_address(SELA_TOKEN_ADDRESS):
        token = w3.eth.contract(address=Web3.to_checksum_address(SELA_TOKEN_ADDRESS), abi=ERC20_MIN_ABI)

_init_web3()

def _decimals() -> int:
    if SELA_DECIMALS_OVERRIDE:
        try:
            return int(SELA_DECIMALS_OVERRIDE)
        except Exception:
            pass
    if token:
        try:
            return int(token.functions.decimals().call())
        except Exception:
            return 18
    return 18

def _symbol() -> str:
    if SELA_SYMBOL_OVERRIDE:
        return SELA_SYMBOL_OVERRIDE
    if token:
        try:
            return token.functions.symbol().call()
        except Exception:
            return "SELA"
    return "SELA"

class EstimationRequest(BaseModel):
    op: str
    to: str
    amount: Optional[str] = None

class MintRequest(BaseModel):
    to: str
    amount: str

class SendRequest(BaseModel):
    to: str
    amount: str

@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "chain_id": CHAIN_ID,
        "has_rpc": bool(BSC_RPC_URL),
        "has_token": bool(SELA_TOKEN_ADDRESS),
        "has_treasury": bool(TREASURY_PRIVATE_KEY and TREASURY_ADDRESS),
    }

@app.get("/routes")
def routes():
    return sorted([{"path": r.path, "name": r.name} for r in app.router.routes], key=lambda x: x["path"])

@app.get("/tokeninfo")
def tokeninfo():
    if not w3 or not token:
        raise HTTPException(status_code=500, detail="RPC or token contract not initialized")
    try:
        name = token.functions.name().call()
    except Exception:
        name = "Unknown"
    try:
        symbol = _symbol()
    except Exception:
        symbol = "SELA"
    try:
        decimals = _decimals()
    except Exception:
        decimals = 18
    try:
        total_supply = token.functions.totalSupply().call()
    except Exception:
        total_supply = 0

    return {
        "address": Web3.to_checksum_address(SELA_TOKEN_ADDRESS) if SELA_TOKEN_ADDRESS else None,
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
        "totalSupply": str(total_supply),
        "chainId": CHAIN_ID,
    }

@app.get("/balance/{address}")
def balance(address: str):
    if not w3:
        raise HTTPException(status_code=500, detail="RPC not initialized")
    if not w3.is_address(address):
        raise HTTPException(status_code=400, detail="invalid address")
    if not token:
        raise HTTPException(status_code=500, detail="token not initialized")

    try:
        raw = token.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return {"address": Web3.to_checksum_address(address), "raw": str(raw), "decimals": _decimals(), "symbol": _symbol()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"balance error: {e}")

@app.post("/mint")
def mint(body: MintRequest):
    if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
        raise HTTPException(status_code=403, detail="mint disabled: missing treasury creds")
    raise HTTPException(status_code=501, detail="mint not implemented yet in this minimal API")

@app.post("/send")
def send(body: SendRequest):
    if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
        raise HTTPException(status_code=403, detail="send disabled: missing treasury creds")
    raise HTTPException(status_code=501, detail="send not implemented yet in this minimal API")

@app.post("/estimate")
def estimate(body: EstimationRequest):
    return JSONResponse({"op": body.op, "estimated": None, "note": "estimator stub"}, status_code=200)
