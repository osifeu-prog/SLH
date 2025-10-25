
import os
from typing import Optional, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Query
from pydantic import BaseModel
from web3 import Web3
from web3.middleware import geth_poa_middleware

try:
    from eth_utils import to_checksum_address as _to_ck
except Exception:
    _to_ck = None

# ==== ENV ====
BSC_RPC_URL           = os.getenv("BSC_RPC_URL", "").strip()
SELA_TOKEN_ADDRESS    = os.getenv("SELA_TOKEN_ADDRESS", "").strip()
TREASURY_PRIVATE_KEY  = os.getenv("TREASURY_PRIVATE_KEY", "").strip()   # optional for mint/transfer
TREASURY_ADDRESS      = os.getenv("TREASURY_ADDRESS", "").strip()       # recommended if PK is set
CHAIN_ID              = int(os.getenv("CHAIN_ID", "97"))
SELA_SYMBOL_OVERRIDE  = os.getenv("SELA_SYMBOL_OVERRIDE", "").strip()
SELA_DECIMALS_OVERRIDE= os.getenv("SELA_DECIMALS_OVERRIDE", "").strip()
GAS_PRICE_FLOOR_WEI   = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0"))

if not BSC_RPC_URL:
    raise RuntimeError("BSC_RPC_URL missing")

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL, request_kwargs={"timeout": 30}))
try:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
except Exception:
    pass

def _ck(addr: str) -> str:
    try:
        if _to_ck:
            return _to_ck(addr)
        if not Web3.is_address(addr):
            raise ValueError("bad address")
        return Web3.to_checksum_address(addr)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid address (EIP-55)")

if TREASURY_PRIVATE_KEY and not TREASURY_ADDRESS:
    acct = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
    TREASURY_ADDRESS = acct.address

ERC20_ABI = [
    {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"stateMutability":"nonpayable","type":"function"},
]

def _contract():
    if not SELA_TOKEN_ADDRESS:
        raise HTTPException(status_code=500, detail="SELA_TOKEN_ADDRESS not set")
    return w3.eth.contract(address=_ck(SELA_TOKEN_ADDRESS), abi=ERC20_ABI)

def _min_gas_price(override: Optional[int]=None) -> int:
    floor = GAS_PRICE_FLOOR_WEI if GAS_PRICE_FLOOR_WEI > 0 else 0
    cur = w3.eth.gas_price
    if override is not None and override > 0:
        cur = override
    return max(cur, floor)

app = FastAPI(title="SLH API", version="1.0")
router = APIRouter()

@router.get("/")
def index():
    return {
        "ok": True,
        "service": "slh_API",
        "chain_id": CHAIN_ID,
        "routes": [
            "/healthz",
            "/tokeninfo", "/token/info",
            "/balance/{address}", "/token/balance/{address}",
            "/estimate/{op}?to=...&amount=...&gasPriceWei=",
            "POST /mint", "POST /transfer",
        ],
    }

@router.get("/healthz")
def healthz():
    return {"ok": bool(w3.is_connected()), "chain_id": CHAIN_ID}

@router.get("/tokeninfo")
@router.get("/token/info")
def tokeninfo():
    c = _contract()
    try:
        name     = c.functions.name().call()
        symbol   = c.functions.symbol().call()
        decimals = c.functions.decimals().call()
        total    = c.functions.totalSupply().call()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"onchain error: {e}")

    if SELA_SYMBOL_OVERRIDE:
        symbol = SELA_SYMBOL_OVERRIDE
    if SELA_DECIMALS_OVERRIDE:
        try:
            decimals = int(SELA_DECIMALS_OVERRIDE)
        except Exception:
            pass

    return {
        "address": Web3.to_checksum_address(SELA_TOKEN_ADDRESS),
        "name": name,
        "symbol": symbol,
        "decimals": int(decimals),
        "totalSupply": str(total),
        "chain_id": CHAIN_ID,
    }

@router.get("/balance/{address}")
@router.get("/token/balance/{address}")
def balance(address: str):
    c = _contract()
    user = _ck(address)
    try:
        bal = c.functions.balanceOf(user).call()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"onchain error: {e}")
    return {"address": user, "balance": str(bal)}

@router.get("/estimate/{op}")
def estimate(
    op: Literal["mint","transfer"],
    to: str = Query(..., description="recipient address"),
    amount: str = Query(..., description="amount in wei (string)"),
    gasPriceWei: Optional[int] = Query(None)
):
    to_ck = _ck(to)
    amt = int(amount)
    c = _contract()

    if op == "mint":
        fn = c.functions.mint(to_ck, amt)
        sender = TREASURY_ADDRESS or to_ck
    else:
        if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
            raise HTTPException(status_code=400, detail="transfer requires TREASURY_PRIVATE_KEY and TREASURY_ADDRESS")
        fn = c.functions.transfer(to_ck, amt)
        sender = TREASURY_ADDRESS

    try:
        tx = fn.build_transaction({
            "from": sender,
            "chainId": CHAIN_ID,
            "nonce": w3.eth.get_transaction_count(sender),
            "gasPrice": _min_gas_price(gasPriceWei),
        })
        gas = w3.eth.estimate_gas(tx)
        return {"op": op, "to": to_ck, "amount": str(amt), "gas": int(gas), "gasPriceWei": int(tx["gasPrice"])}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"estimate error: {e}")

class TxBody(BaseModel):
    to: str
    amount: str

def _send_tx(fn):
    if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
        raise HTTPException(status_code=400, detail="missing TREASURY_PRIVATE_KEY / TREASURY_ADDRESS")
    acct  = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx    = fn.build_transaction({
        "from": acct.address,
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "gasPrice": _min_gas_price(),
    })
    gas   = w3.eth.estimate_gas(tx)
    tx["gas"] = gas
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.rawTransaction)
    return {"txHash": txh.hex(), "gas": int(gas), "gasPriceWei": int(tx["gasPrice"])}

@router.post("/mint")
def do_mint(body: TxBody):
    to_ck = _ck(body.to)
    amt = int(body.amount)
    c = _contract()
    return _send_tx(c.functions.mint(to_ck, amt))

@router.post("/transfer")
def do_transfer(body: TxBody):
    to_ck = _ck(body.to)
    amt = int(body.amount)
    c = _contract()
    return _send_tx(c.functions.transfer(to_ck, amt))

app.include_router(router)
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/v1")
