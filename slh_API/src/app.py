from __future__ import annotations
import asyncio, logging, os
from decimal import Decimal, getcontext, ROUND_DOWN
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status, APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, BaseSettings, Field, validator
from web3 import Web3
from web3.middleware import geth_poa_middleware

# high precision
getcontext().prec = 78
getcontext().rounding = ROUND_DOWN

class Settings(BaseSettings):
    BSC_RPC_URL: str = Field(..., env="BSC_RPC_URL")
    SELA_TOKEN_ADDRESS: str = Field(..., env="SELA_TOKEN_ADDRESS")
    CHAIN_ID: int = Field(97, env="CHAIN_ID")
    GAS_PRICE_FLOOR_WEI: int = Field(1_000_000_000, env="GAS_PRICE_FLOOR_WEI")
    SELA_DECIMALS_OVERRIDE: Optional[int] = Field(None, env="SELA_DECIMALS_OVERRIDE")
    SELA_SYMBOL_OVERRIDE: Optional[str] = Field(None, env="SELA_SYMBOL_OVERRIDE")
    SELA_MINT_FUNCS: str = Field("ownerMint,mintTo,mint", env="SELA_MINT_FUNCS")
    TREASURY_PRIVATE_KEY: Optional[str] = Field(None, env="TREASURY_PRIVATE_KEY")
    TREASURY_ADDRESS: Optional[str] = Field(None, env="TREASURY_ADDRESS")
    DRY_RUN: bool = Field(False, env="DRY_RUN")
    class Config:
        env_file = ".env"
        case_sensitive = True
    @validator("SELA_TOKEN_ADDRESS","TREASURY_ADDRESS", pre=True)
    def _strip(cls, v): return v.strip() if isinstance(v,str) else v

settings = Settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("slh_api")

w3 = Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

if settings.TREASURY_PRIVATE_KEY and not settings.TREASURY_ADDRESS:
    settings.TREASURY_ADDRESS = w3.eth.account.from_key(settings.TREASURY_PRIVATE_KEY).address
    log.info("Derived TREASURY_ADDRESS from private key")

ERC20_MIN_ABI = [
    {"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"mint","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"mintTo","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"ownerMint","outputs":[],"stateMutability":"nonpayable","type":"function"}
]
TOKEN = w3.eth.contract(address=Web3.to_checksum_address(settings.SELA_TOKEN_ADDRESS), abi=ERC20_MIN_ABI)

def to_checksum(addr: str) -> str:
    if not Web3.is_address(addr):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid address")
    return Web3.to_checksum_address(addr)

@lru_cache(maxsize=8)
def get_decimals() -> int:
    if settings.SELA_DECIMALS_OVERRIDE is not None:
        return int(settings.SELA_DECIMALS_OVERRIDE)
    try:
        return int(TOKEN.functions.decimals().call())
    except Exception:
        return 18

@lru_cache(maxsize=8)
def get_symbol() -> str:
    if settings.SELA_SYMBOL_OVERRIDE:
        return settings.SELA_SYMBOL_OVERRIDE
    try:
        return TOKEN.functions.symbol().call()
    except Exception:
        return "TOKEN"

def human_to_wei(amount_human: str) -> int:
    d = Decimal(amount_human)
    if d < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="amount must be non-negative")
    factor = Decimal(10) ** get_decimals()
    return int((d * factor).to_integral_value(rounding=ROUND_DOWN))

def wei_to_human(v: int) -> str:
    factor = Decimal(10) ** get_decimals()
    return str(Decimal(v) / factor)

def _pick_gas_price(floor: int, override: Optional[int]) -> int:
    try:
        net = int(w3.eth.gas_price)
    except Exception:
        net = floor
    if override and override > 0:
        net = int(override)
    return max(net, floor)

_nonce_lock = asyncio.Lock()
async def _next_nonce(address: str) -> int:
    async with _nonce_lock:
        return w3.eth.get_transaction_count(address, "pending")

core = APIRouter()

@core.get("/", response_class=PlainTextResponse)
async def root():
    return "SLH API up"

@core.get("/healthz")
async def healthz():
    return {"ok": True, "chainId": settings.CHAIN_ID}

@core.get("/tokeninfo")
async def tokeninfo():
    try:
        name = TOKEN.functions.name().call()
    except Exception:
        name = None
    sym = get_symbol()
    dec = get_decimals()
    try:
        supply = TOKEN.functions.totalSupply().call()
        supply_h = wei_to_human(supply)
    except Exception:
        supply_h = None
    return {
        "address": Web3.to_checksum_address(settings.SELA_TOKEN_ADDRESS),
        "name": name,
        "symbol": sym,
        "decimals": dec,
        "totalSupply": supply_h
    }

@core.get("/balance/{address}")
async def balance(address: str):
    addr = to_checksum(address)
    try:
        bal = TOKEN.functions.balanceOf(addr).call()
    except Exception:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="balance fetch failed")
    return {"address": addr, "balance": wei_to_human(bal)}

@core.get("/estimate/{op}")
async def estimate(op: str, to: str = Query(...), amount: str = Query(...), gasPriceWei: Optional[int] = Query(None)):
    op = op.lower()
    if op not in {"mint","transfer"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="op must be mint|transfer")
    to_addr = to_checksum(to)
    amt = human_to_wei(amount)
    try:
        if op == "mint":
            fn = None
            for n in [x.strip() for x in settings.SELA_MINT_FUNCS.split(",") if x.strip()] + ["mint","mintTo","ownerMint"]:
                try:
                    fn = getattr(TOKEN.functions, n)(to_addr, amt)
                    break
                except Exception:
                    continue
            if fn is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no mint function")
            from_addr = settings.TREASURY_ADDRESS or to_addr
        else:
            if not settings.TREASURY_ADDRESS:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="TREASURY_ADDRESS not configured")
            fn = TOKEN.functions.transfer(to_addr, amt)
            from_addr = settings.TREASURY_ADDRESS
        gas = fn.estimate_gas({"from": from_addr})
        gp = _pick_gas_price(settings.GAS_PRICE_FLOOR_WEI, gasPriceWei)
        return {"gas": int(gas), "gasPriceWei": int(gp), "totalWei": int(gas)*int(gp)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"estimate failed: {e}")

async def _build_and_send(fn):
    if settings.DRY_RUN:
        log.info("DRY_RUN enabled; tx not broadcast")
    priv = settings.TREASURY_PRIVATE_KEY
    if not priv:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="TREASURY_PRIVATE_KEY not configured")
    acct = w3.eth.account.from_key(priv)
    nonce = await _next_nonce(acct.address)
    try:
        gas = fn.estimate_gas({"from": acct.address})
    except Exception:
        gas = 200_000
    gp = _pick_gas_price(settings.GAS_PRICE_FLOOR_WEI, None)
    tx = fn.build_transaction({"from": acct.address, "chainId": settings.CHAIN_ID, "nonce": nonce, "gas": int(gas), "gasPrice": int(gp)})
    signed = w3.eth.account.sign_transaction(tx, priv)
    if settings.DRY_RUN:
        return {"txHash": None, "gas": int(gas), "gasPriceWei": int(gp), "rawTx": signed.rawTransaction.hex()}
    h = w3.eth.send_raw_transaction(signed.rawTransaction)
    return {"txHash": h.hex(), "gas": int(gas), "gasPriceWei": int(gp)}

class TxIn(BaseModel):
    to: str
    amount: str
    @validator("to")
    def _addr(cls, v):
        if not Web3.is_address(v):
            raise ValueError("invalid address")
        return Web3.to_checksum_address(v)

@core.post("/mint")
async def mint(inp: TxIn):
    to_addr = inp.to
    amt = human_to_wei(inp.amount)
    fn = None
    for n in [x.strip() for x in settings.SELA_MINT_FUNCS.split(",") if x.strip()] + ["mint","mintTo","ownerMint"]:
        try:
            fn = getattr(TOKEN.functions, n)(to_addr, amt)
            break
        except Exception:
            continue
    if fn is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no mint function")
    return await _build_and_send(fn)

@core.post("/transfer")
async def transfer(inp: TxIn):
    if not settings.TREASURY_PRIVATE_KEY:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="TREASURY_PRIVATE_KEY not configured")
    to_addr = inp.to
    amt = human_to_wei(inp.amount)
    fn = TOKEN.functions.transfer(to_addr, amt)
    return await _build_and_send(fn)

app = FastAPI(title="SLH API", version="1.0.2")
# mount same routes under "", "/api", "/v1"
for prefix in ("", "/api", "/v1"):
    app.include_router(core, prefix=prefix)

@app.exception_handler(HTTPException)
async def http_exc(_, exc: HTTPException):
    return JSONResponse(exc.status_code, {"detail": exc.detail})

@app.exception_handler(Exception)
async def generic_exc(_, exc: Exception):
    logging.getLogger("slh_api").exception("Unhandled exception")
    return JSONResponse(status.HTTP_500_INTERNAL_SERVER_ERROR, {"detail":"internal server error"})
