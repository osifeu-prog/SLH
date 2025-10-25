import os
from typing import Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
from web3 import Web3
from eth_utils import to_checksum_address

# ---- ENV ----
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "").strip()
SELA_TOKEN_ADDRESS_RAW = os.getenv("SELA_TOKEN_ADDRESS", "").strip()
TREASURY_PRIVATE_KEY = os.getenv("TREASURY_PRIVATE_KEY", "").strip()  # אופציונלי למינט/שליחה
TREASURY_ADDRESS_RAW = os.getenv("TREASURY_ADDRESS", "").strip()       # מומלץ להגדיר אם יש PK
CHAIN_ID = int(os.getenv("CHAIN_ID", "97"))  # BSC testnet = 97
SELA_SYMBOL_OVERRIDE = os.getenv("SELA_SYMBOL_OVERRIDE", "").strip()
SELA_DECIMALS_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE", "").strip()
GAS_PRICE_FLOOR_WEI = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0"))

if not BSC_RPC_URL:
    raise RuntimeError("BSC_RPC_URL missing")

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL, request_kwargs={"timeout": 30}))

def _ck(addr: str) -> str:
    try:
        return to_checksum_address(addr)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid address (EIP-55)")

SELA_TOKEN_ADDRESS = _ck(SELA_TOKEN_ADDRESS_RAW) if SELA_TOKEN_ADDRESS_RAW else None
TREASURY_ADDRESS = _ck(TREASURY_ADDRESS_RAW) if TREASURY_ADDRESS_RAW else None

# ---- Minimal ERC20 ABI (name, symbol, decimals, totalSupply, balanceOf, transfer) + mint ----
ERC20_ABI = [
    {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    # project-specific (owner-only):
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"stateMutability":"nonpayable","type":"function"},
]

def _contract():
    if not SELA_TOKEN_ADDRESS:
        raise HTTPException(status_code=500, detail="SELA_TOKEN_ADDRESS not set")
    return w3.eth.contract(address=SELA_TOKEN_ADDRESS, abi=ERC20_ABI)

def _min_gas_price():
    gp = w3.eth.gas_price
    return max(gp, GAS_PRICE_FLOOR_WEI) if GAS_PRICE_FLOOR_WEI > 0 else gp

# ---- FastAPI ----
app = FastAPI(title="SLH API", version="1.0")
router = APIRouter()

@router.get("/healthz")
def healthz():
    ok = w3.is_connected()
    return {"ok": ok, "chain_id": CHAIN_ID}

@router.get("/tokeninfo")
def tokeninfo():
    c = _contract()
    try:
        name = c.functions.name().call()
        symbol = c.functions.symbol().call()
        decimals = c.functions.decimals().call()
        total = c.functions.totalSupply().call()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"onchain error: {str(e)}")

    # overrides (optional)
    if SELA_SYMBOL_OVERRIDE:
        symbol = SELA_SYMBOL_OVERRIDE
    if SELA_DECIMALS_OVERRIDE:
        try:
            decimals = int(SELA_DECIMALS_OVERRIDE)
        except:
            pass

    return {
        "address": SELA_TOKEN_ADDRESS,
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
        "totalSupply": str(total),
        "chain_id": CHAIN_ID,
    }

@router.get("/balance/{address}")
def balance(address: str):
    user = _ck(address)
    c = _contract()
    try:
        bal = c.functions.balanceOf(user).call()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"onchain error: {str(e)}")
    return {"address": user, "balance": str(bal)}

@router.get("/estimate/{op}/{to}/{amount}")
def estimate(op: Literal["mint","transfer"], to: str, amount: str):
    if op == "mint" and not TREASURY_PRIVATE_KEY:
        raise HTTPException(status_code=400, detail="mint requires TREASURY_PRIVATE_KEY")
    to_ck = _ck(to)
    c = _contract()
    amt = int(amount)

    if op == "mint":
        fn = c.functions.mint(to_ck, amt)
        sender = TREASURY_ADDRESS
    else:
        if not TREASURY_PRIVATE_KEY:
            raise HTTPException(status_code=400, detail="transfer requires TREASURY_PRIVATE_KEY")
        fn = c.functions.transfer(to_ck, amt)
        sender = TREASURY_ADDRESS

    try:
        tx = fn.build_transaction({
            "from": sender,
            "chainId": CHAIN_ID,
            "nonce": w3.eth.get_transaction_count(sender),
            "gasPrice": _min_gas_price(),
        })
        gas = w3.eth.estimate_gas(tx)
        return {"op": op, "to": to_ck, "amount": str(amt), "gas": int(gas), "gasPrice": str(tx["gasPrice"])}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"estimate error: {str(e)}")

class TxBody(BaseModel):
    to: str
    amount: str

def _send_tx(fn):
    if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
        raise HTTPException(status_code=400, detail="missing TREASURY_PRIVATE_KEY / TREASURY_ADDRESS")
    nonce = w3.eth.get_transaction_count(TREASURY_ADDRESS)
    tx = fn.build_transaction({
        "from": TREASURY_ADDRESS,
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "gasPrice": _min_gas_price(),
    })
    # gas limit via estimate
    gas_est = w3.eth.estimate_gas(tx)
    tx["gas"] = int(gas_est)
    signed = w3.eth.account.sign_transaction(tx, private_key=TREASURY_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return {"txHash": tx_hash.hex()}

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

# ---- register routes on root + /api + /v1 ----
app.include_router(router)                 # /
app.include_router(router, prefix="/api")  # /api
app.include_router(router, prefix="/v1")   # /v1
