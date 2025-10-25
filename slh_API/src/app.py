# FastAPI SLH API - BSC Testnet
import os
from typing import Literal, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from web3.exceptions import ContractLogicError

BSC_RPC_URL = os.getenv("BSC_RPC_URL", "").strip()
SELA_TOKEN_ADDRESS = os.getenv("SELA_TOKEN_ADDRESS", "").strip()
TREASURY_PRIVATE_KEY = os.getenv("TREASURY_PRIVATE_KEY", "").strip()
TREASURY_ADDRESS = os.getenv("TREASURY_ADDRESS", "").strip()
CHAIN_ID = int(os.getenv("CHAIN_ID", "97"))
SELA_SYMBOL_OVERRIDE = os.getenv("SELA_SYMBOL_OVERRIDE", "").strip() or None
SELA_DECIMALS_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE", "").strip() or None
GAS_PRICE_FLOOR_WEI = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0"))

if not BSC_RPC_URL:
    raise RuntimeError("Missing BSC_RPC_URL")
if not SELA_TOKEN_ADDRESS:
    raise RuntimeError("Missing SELA_TOKEN_ADDRESS")

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
if not w3.is_connected():
    raise RuntimeError("Web3 failed to connect to RPC")

def to_checksum(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid EIP-55 address")

ERC20_ABI = [
    {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function","stateMutability":"view"},
    {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function","stateMutability":"view"},
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function","stateMutability":"view"},
    {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function","stateMutability":"view"},
    {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function","stateMutability":"view"},
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function","stateMutability":"nonpayable"},
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"type":"function","stateMutability":"nonpayable"},
]

token_addr = to_checksum(SELA_TOKEN_ADDRESS)
token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)

def get_symbol() -> str:
    if SELA_SYMBOL_OVERRIDE:
        return SELA_SYMBOL_OVERRIDE
    try:
        return token.functions.symbol().call()
    except Exception:
        return "SLH"

def get_decimals() -> int:
    if SELA_DECIMALS_OVERRIDE:
        try:
            return int(SELA_DECIMALS_OVERRIDE)
        except Exception:
            pass
    try:
        return token.functions.decimals().call()
    except Exception:
        return 18

def ensure_gas_price(params: dict) -> dict:
    gp = params.get("gasPrice") or params.get("maxFeePerGas")
    floor = GAS_PRICE_FLOOR_WEI
    if floor and (gp is None or gp < floor):
        params["gasPrice"] = floor
        params.pop("maxFeePerGas", None)
        params.pop("maxPriorityFeePerGas", None)
    return params

app = FastAPI(title="SLH API", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/tokeninfo")
def tokeninfo():
    sym = get_symbol()
    decimals = get_decimals()
    try:
        ts = token.functions.totalSupply().call()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"totalSupply failed: {e}")
    return {"contract": token_addr, "symbol": sym, "decimals": decimals, "totalSupply": str(ts), "chainId": CHAIN_ID}

@app.get("/balance/{address}")
def balance(address: str):
    addr = to_checksum(address)
    try:
        bal = token.functions.balanceOf(addr).call()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"balanceOf failed: {e}")
    return {"address": addr, "balance": str(bal), "symbol": get_symbol(), "decimals": get_decimals()}

@app.get("/estimate/{op}/{to}/{amount}")
def estimate(op: Literal["mint","transfer"], to: str, amount: str):
    to_addr = to_checksum(to)
    amt = int(amount)
    caller = TREASURY_ADDRESS or None
    if caller is None:
        raise HTTPException(status_code=400, detail="Missing TREASURY_ADDRESS")
    if op == "transfer":
        tx = token.functions.transfer(to_addr, amt).build_transaction({"from": caller})
    else:
        tx = token.functions.mint(to_addr, amt).build_transaction({"from": caller})
    tx = ensure_gas_price(tx)
    gp = tx.get("gasPrice") or tx.get("maxFeePerGas")
    gl = tx.get("gas", None)
    if gl is None:
        try:
            gl = w3.eth.estimate_gas(tx)
        except Exception:
            gl = 120000
    return {"op": op, "to": to_addr, "amount": str(amt), "gasLimit": int(gl), "gasPrice": int(gp) if gp else None}

class TxRequest(BaseModel):
    to: str
    amount: int

def _require_owner():
    if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
        raise HTTPException(status_code=400, detail="Owner credentials missing")

def _sign_and_send(tx):
    tx = ensure_gas_price(tx)
    tx["nonce"] = w3.eth.get_transaction_count(TREASURY_ADDRESS)
    if "gas" not in tx:
        try:
            tx["gas"] = w3.eth.estimate_gas(tx)
        except Exception:
            tx["gas"] = 200000
    signed = w3.eth.account.sign_transaction(tx, private_key=TREASURY_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()

@app.post("/mint")
def post_mint(req: TxRequest):
    _require_owner()
    to_addr = to_checksum(req.to)
    amt = int(req.amount)
    try:
        tx = token.functions.mint(to_addr, amt).build_transaction({"from": TREASURY_ADDRESS, "chainId": CHAIN_ID})
        h = _sign_and_send(tx)
        return {"status": "submitted", "hash": h}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=f"Contract reverted: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"mint failed: {e}")

@app.post("/transfer")
def post_transfer(req: TxRequest):
    _require_owner()
    to_addr = to_checksum(req.to)
    amt = int(req.amount)
    try:
        tx = token.functions.transfer(to_addr, amt).build_transaction({"from": TREASURY_ADDRESS, "chainId": CHAIN_ID})
        h = _sign_and_send(tx)
        return {"status": "submitted", "hash": h}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=f"Contract reverted: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"transfer failed: {e}")

# expose also under /api and /v1
from fastapi import FastAPI as _F, APIRouter
def clone_routes(src_app: FastAPI):
    r = APIRouter()
    for route in src_app.router.routes:
        path = getattr(route, "path", None)
        endpoint = getattr(route, "endpoint", None)
        methods = getattr(route, "methods", None)
        if path and endpoint and methods:
            r.add_api_route(path, endpoint=endpoint, methods=list(methods))
    new_app = _F()
    new_app.include_router(r)
    return new_app

api_app = clone_routes(app)
v1_app = clone_routes(app)

from fastapi.middleware.cors import CORSMiddleware
for inst in (app, api_app, v1_app):
    inst.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

root = _F()
root.mount("/", app)
root.mount("/api", api_app)
root.mount("/v1", v1_app)
app = root
