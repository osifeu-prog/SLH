import os
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ===== ENV =====
BSC_RPC_URL            = os.getenv("BSC_RPC_URL", "")
CHAIN_ID               = int(os.getenv("CHAIN_ID", "0") or 0)
SELA_TOKEN_ADDRESS     = os.getenv("SELA_TOKEN_ADDRESS", "")
SELA_SYMBOL_OVERRIDE   = os.getenv("SELA_SYMBOL_OVERRIDE")
SELA_DECIMALS_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE")
SELA_DECIMALS_OVERRIDE = int(SELA_DECIMALS_OVERRIDE) if SELA_DECIMALS_OVERRIDE else None

# ===== Web3 + Contract =====
w3 = None
token = None
token_decimals = None
token_symbol = None

ERC20_ABI = [
  {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":True,"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
]

def _mk_w3() -> Web3:
    if not BSC_RPC_URL:
        raise RuntimeError("BSC_RPC_URL env missing")
    provider = Web3.HTTPProvider(BSC_RPC_URL, request_kwargs={"timeout": 20})
    return Web3(provider)

def _mk_token(w3: Web3):
    if not SELA_TOKEN_ADDRESS:
        return None
    return w3.eth.contract(address=Web3.to_checksum_address(SELA_TOKEN_ADDRESS), abi=ERC20_ABI)

app = FastAPI(title="SLH API", version="1.0.0")

@app.on_event("startup")
def _on_startup():
    global w3, token, token_decimals, token_symbol
    w3 = _mk_w3()
    token = _mk_token(w3)
    if token:
        try:
            token_decimals = SELA_DECIMALS_OVERRIDE or int(token.functions.decimals().call())
        except Exception:
            token_decimals = SELA_DECIMALS_OVERRIDE or 18
        try:
            token_symbol = SELA_SYMBOL_OVERRIDE or str(token.functions.symbol().call())
        except Exception:
            token_symbol = SELA_SYMBOL_OVERRIDE or "SELA"

def _have_rpc() -> bool:
    try:
        return bool(w3 and w3.is_connected())
    except Exception:
        return False

def _human(amount_wei: int, decimals: int) -> float:
    scale = 10 ** decimals
    return float(amount_wei) / float(scale)

@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "chain_id": CHAIN_ID,
        "has_rpc": _have_rpc(),
        "has_token": bool(token),
        "has_treasury": bool(os.getenv("TREASURY_PRIVATE_KEY") or os.getenv("TREASURY_ADDRESS")),
    }

@app.get("/routes")
def routes() -> List[Dict[str, str]]:
    items = []
    for r in app.router.routes:
        if hasattr(r, "path") and hasattr(r, "methods"):
            items.append({"path": r.path, "methods": ",".join(sorted(r.methods))})
    return items

@app.get("/tokeninfo")
def tokeninfo() -> Dict[str, Any]:
    if not token:
        raise HTTPException(status_code=500, detail="token contract not configured")
    try:
        name = str(token.functions.name().call())
    except Exception:
        name = "SELA"
    sym = token_symbol or "SELA"
    dec = token_decimals or 18
    try:
        total = int(token.functions.totalSupply().call())
    except Exception:
        total = 0
    return {
        "name": name,
        "symbol": sym,
        "decimals": dec,
        "totalSupply": total,
        "totalHuman": _human(total, dec),
        "address": Web3.to_checksum_address(SELA_TOKEN_ADDRESS),
        "chainId": CHAIN_ID,
    }

@app.get("/balance/{address}")
def balance(address: str) -> Dict[str, Any]:
    if not token:
        raise HTTPException(status_code=500, detail="token contract not configured")
    try:
        chk = Web3.to_checksum_address(address)
    except Exception:
        raise HTTPException(status_code=400, detail="bad address")
    try:
        bal = int(token.functions.balanceOf(chk).call())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"balance error: {e}")
    dec = token_decimals or 18
    return {
        "address": chk,
        "balance": bal,
        "balanceHuman": _human(bal, dec),
        "symbol": token_symbol or "SELA",
        "decimals": dec,
    }

class EstimateOut(BaseModel):
    op: str
    to: str
    amount: str
    note: str

@app.get("/estimate/{op}/{to}/{amount}", response_model=EstimateOut)
def estimate(op: str, to: str, amount: str):
    # שמים Placeholder עד שנחבר טרנזקציות בפועל
    if op not in ("mint", "transfer"):
        raise HTTPException(status_code=400, detail="op must be mint|transfer")
    try:
        _ = Web3.to_checksum_address(to)
    except Exception:
        raise HTTPException(status_code=400, detail="bad 'to' address")
    return EstimateOut(op=op, to=to, amount=str(amount), note="gas estimation placeholder (to be implemented)")

