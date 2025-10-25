import os
from typing import Optional, List, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Query
from pydantic import BaseModel
from web3 import Web3
from web3.middleware import geth_poa_middleware

# === ENV ===
BSC_RPC_URL            = os.getenv("BSC_RPC_URL", "").strip()
SELA_TOKEN_ADDRESS     = os.getenv("SELA_TOKEN_ADDRESS", "").strip()
CHAIN_ID               = int(os.getenv("CHAIN_ID", "97"))  # 97=testnet, 56=mainnet
TREASURY_PRIVATE_KEY   = os.getenv("TREASURY_PRIVATE_KEY", "").strip()
TREASURY_ADDRESS       = os.getenv("TREASURY_ADDRESS", "").strip()
SELA_SYMBOL_OVERRIDE   = os.getenv("SELA_SYMBOL_OVERRIDE", "").strip()
SELA_DECIMALS_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE", "").strip()
SELA_MINT_FUNCS        = os.getenv("SELA_MINT_FUNCS", "ownerMint,mintTo,mint").strip()
GAS_PRICE_FLOOR_WEI    = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0"))

if not BSC_RPC_URL:        raise RuntimeError("BSC_RPC_URL missing")
if not SELA_TOKEN_ADDRESS: raise RuntimeError("SELA_TOKEN_ADDRESS missing")

# === Web3 ===
w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL, request_kwargs={"timeout": 30}))
try:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
except Exception:
    pass

# Derive address when only PK provided
if TREASURY_PRIVATE_KEY and not TREASURY_ADDRESS:
    acct = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
    TREASURY_ADDRESS = acct.address

def _ck(addr: str) -> str:
    if not Web3.is_address(addr):
        raise HTTPException(status_code=400, detail="invalid address")
    return Web3.to_checksum_address(addr)

# === ERC20 minimal ABI (+ common mint names) ===
ERC20_ABI = [
    {"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mintTo","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"ownerMint","outputs":[],"stateMutability":"nonpayable","type":"function"},
]

def _contract():
    return w3.eth.contract(address=_ck(SELA_TOKEN_ADDRESS), abi=ERC20_ABI)

def _mint_fn(contract, to_addr: str, amt: int):
    names: List[str] = [n.strip() for n in SELA_MINT_FUNCS.split(",") if n.strip()]
    names += ["mint", "mintTo", "ownerMint"]
    for nm in names:
        try:
            return getattr(contract.functions, nm)(to_addr, amt)
        except Exception:
            continue
    raise HTTPException(status_code=400, detail="no mint function found on token contract")

def _min_gas_price(override: Optional[int]=None) -> int:
    floor = max(GAS_PRICE_FLOOR_WEI, 0)
    try:
        cur = int(w3.eth.gas_price)
    except Exception:
        cur = floor
    if override and override > 0:
        cur = int(override)
    return max(cur, floor)

# === FastAPI ===
app = FastAPI(title="SLH API", version="1.0.0")
router = APIRouter()

@router.get("/")
def index():
    return {"ok": True, "service": "slh_API", "chain_id": CHAIN_ID,
            "routes": ["/healthz","/health","/tokeninfo",
                       "/balance/{address}","/estimate/{op}","POST /mint","POST /transfer"]}

@router.get("/healthz")
@router.get("/health")
def health():
    return {"ok": bool(w3.is_connected()), "chain_id": CHAIN_ID}

@router.get("/tokeninfo")
def tokeninfo():
    c = _contract()
    try:
        name = c.functions.name().call()
        symbol = c.functions.symbol().call()
        decimals = int(c.functions.decimals().call())
        supply = int(c.functions.totalSupply().call())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"onchain error: {e}")
    if SELA_SYMBOL_OVERRIDE:
        symbol = SELA_SYMBOL_OVERRIDE
    if SELA_DECIMALS_OVERRIDE:
        try: decimals = int(SELA_DECIMALS_OVERRIDE)
        except Exception: pass
    return {"address": _ck(SELA_TOKEN_ADDRESS), "name": name, "symbol": symbol,
            "decimals": decimals, "totalSupply": str(supply), "chain_id": CHAIN_ID}

@router.get("/balance/{address}")
def balance(address: str):
    c = _contract()
    user = _ck(address)
    try:
        bal = int(c.functions.balanceOf(user).call())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"onchain error: {e}")
    return {"address": user, "balance": str(bal), "chain_id": CHAIN_ID}

@router.get("/estimate/{op}")
def estimate(op: Literal["mint","transfer"],
             to: str = Query(...),
             amount: str = Query(...),
             gasPriceWei: Optional[int] = Query(None)):
    c = _contract()
    to_ck = _ck(to)
    try:
        amt = int(amount)
    except Exception:
        raise HTTPException(status_code=400, detail="amount must be integer (wei)")
    if op == "mint":
        fn = _mint_fn(c, to_ck, amt)
        sender = TREASURY_ADDRESS or to_ck
    else:
        if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
            raise HTTPException(status_code=400, detail="transfer requires TREASURY_PRIVATE_KEY & TREASURY_ADDRESS")
        fn = c.functions.transfer(to_ck, amt)
        sender = TREASURY_ADDRESS
    try:
        tx = fn.build_transaction({"from": sender, "chainId": CHAIN_ID, "nonce": w3.eth.get_transaction_count(sender), "gasPrice": _min_gas_price(gasPriceWei)})
        gas = int(w3.eth.estimate_gas(tx))
        total = int(tx["gasPrice"]) * gas
        return {"op": op, "to": to_ck, "amount": str(amt), "gas": gas, "gasPriceWei": int(tx["gasPrice"]), "totalWei": total, "chain_id": CHAIN_ID}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"estimate error: {e}")

class TxBody(BaseModel):
    to: str
    amount: str  # wei

def _send_tx(fn):
    if not TREASURY_PRIVATE_KEY or not TREASURY_ADDRESS:
        raise HTTPException(status_code=400, detail="missing TREASURY_PRIVATE_KEY / TREASURY_ADDRESS")
    acct = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
    nonce = w3.eth.get_transaction_count(acct.address, "pending")
    tx = fn.build_transaction({"from": acct.address, "chainId": CHAIN_ID, "nonce": nonce, "gasPrice": _min_gas_price()})
    gas = int(w3.eth.estimate_gas(tx))
    tx["gas"] = gas
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.rawTransaction)
    return {"txHash": txh.hex(), "gas": gas, "gasPriceWei": int(tx["gasPrice"]), "chain_id": CHAIN_ID}

@router.post("/mint")
def do_mint(body: TxBody):
    c = _contract()
    to_ck = _ck(body.to)
    amt = int(body.amount)
    fn = _mint_fn(c, to_ck, amt)
    return _send_tx(fn)

@router.post("/transfer")
def do_transfer(body: TxBody):
    c = _contract()
    to_ck = _ck(body.to)
    amt = int(body.amount)
    return _send_tx(c.functions.transfer(to_ck, amt))

# mount at root + /api + /v1 (to kill 404s in bot)
app.include_router(router)
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/v1")
