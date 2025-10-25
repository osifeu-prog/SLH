import os
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from web3 import Web3
from web3.exceptions import ContractLogicError

BSC_RPC_URL = os.environ.get("BSC_RPC_URL", "").strip()
CHAIN_ID = int(os.environ.get("CHAIN_ID", "97"))
TOKEN_ADDR_RAW = os.environ.get("SELA_TOKEN_ADDRESS", "").strip()
SYMBOL_OVERRIDE = os.environ.get("SELA_SYMBOL_OVERRIDE", "").strip() or None
DEC_OVERRIDE = os.environ.get("SELA_DECIMALS_OVERRIDE", "").strip()
DEC_OVERRIDE_INT: Optional[int] = int(DEC_OVERRIDE) if DEC_OVERRIDE.isdigit() else None
TREASURY_PK = os.environ.get("TREASURY_PRIVATE_KEY", "").strip()
TREASURY_ADDRESS_RAW = os.environ.get("TREASURY_ADDRESS", "").strip()
GAS_PRICE_FLOOR_WEI = int(os.environ.get("GAS_PRICE_FLOOR_WEI", "0") or "0")

if not BSC_RPC_URL:
    raise RuntimeError("BSC_RPC_URL is required")

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
if not w3.is_connected():
    raise RuntimeError("Web3 failed to connect to BSC RPC")

def _cs(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid address: {addr}")

TOKEN_ADDR = _cs(TOKEN_ADDR_RAW) if TOKEN_ADDR_RAW else None
TREASURY_ADDRESS = _cs(TREASURY_ADDRESS_RAW) if TREASURY_ADDRESS_RAW else None

ERC20_ABI = [
  {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
  {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
  {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
  {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
  {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"stateMutability":"nonpayable","type":"function"}
]

def _contract():
    if not TOKEN_ADDR:
        raise HTTPException(status_code=500, detail="SELA_TOKEN_ADDRESS not set")
    return w3.eth.contract(address=TOKEN_ADDR, abi=ERC20_ABI)

def _gas_price():
    gp = w3.eth.gas_price
    return gp if gp > GAS_PRICE_FLOOR_WEI else GAS_PRICE_FLOOR_WEI

app = FastAPI(title="SLH API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
)

def add_dual_route(path: str, method: str):
    def deco(func):
        if method == "get":
            app.get(path)(func); app.get("/api"+path)(func); app.get("/v1"+path)(func)
        else:
            app.post(path)(func); app.post("/api"+path)(func); app.post("/v1"+path)(func)
        return func
    return deco

@app.get("/healthz")
def healthz():
    return {"ok": True, "chain_id": CHAIN_ID, "connected": w3.is_connected()}

@add_dual_route("/tokeninfo", "get")
def tokeninfo():
    c = _contract()
    try: name = c.functions.name().call()
    except Exception: name = "SLH"
    try: symbol = SYMBOL_OVERRIDE or c.functions.symbol().call()
    except Exception: symbol = SYMBOL_OVERRIDE or "SLH"
    try: decimals = DEC_OVERRIDE_INT if DEC_OVERRIDE_INT is not None else c.functions.decimals().call()
    except Exception: decimals = DEC_OVERRIDE_INT if DEC_OVERRIDE_INT is not None else 18
    try: total = c.functions.totalSupply().call()
    except Exception: total = None
    return {"address": TOKEN_ADDR, "name": name, "symbol": symbol, "decimals": decimals, "totalSupply": str(total) if total is not None else None, "chainId": CHAIN_ID}

@add_dual_route("/balance/{address}", "get")
def balance(address: str):
    c = _contract()
    addr = _cs(address)
    try:
        bal = c.functions.balanceOf(addr).call()
        return {"address": addr, "balance": str(bal), "token": TOKEN_ADDR}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=f"Contract error: {e}") from e

@add_dual_route("/estimate/{op}/{to}/{amount}", "get")
def estimate(op: Literal["mint","transfer"], to: str, amount: str):
    c = _contract()
    to_cs = _cs(to)
    amt = int(amount)
    if op == "mint":
        tx = c.functions.mint(to_cs, amt).build_transaction({
            "from": TREASURY_ADDRESS or to_cs,
            "chainId": CHAIN_ID,
            "nonce": w3.eth.get_transaction_count(TREASURY_ADDRESS or to_cs),
            "gasPrice": _gas_price(),
        })
    else:
        tx = c.functions.transfer(to_cs, amt).build_transaction({
            "from": TREASURY_ADDRESS or to_cs,
            "chainId": CHAIN_ID,
            "nonce": w3.eth.get_transaction_count(TREASURY_ADDRESS or to_cs),
            "gasPrice": _gas_price(),
        })
    gas = w3.eth.estimate_gas(tx)
    return {"gas": int(gas), "gasPrice": str(tx["gasPrice"]), "op": op}

def _send_tx(tx):
    if not TREASURY_PK or not TREASURY_ADDRESS:
        raise HTTPException(status_code=400, detail="TREASURY_PRIVATE_KEY / TREASURY_ADDRESS missing")
    tx["nonce"] = w3.eth.get_transaction_count(TREASURY_ADDRESS)
    tx["gasPrice"] = _gas_price()
    if "gas" not in tx:
        tx["gas"] = w3.eth.estimate_gas(tx)
    signed = w3.eth.account.sign_transaction(tx, private_key=TREASURY_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    rec = w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"txHash": tx_hash.hex(), "status": rec.status, "gasUsed": rec.gasUsed}

@add_dual_route("/mint", "post")
def mint_query(to: str, amount: int):
    c = _contract()
    to_cs = _cs(to)
    tx = c.functions.mint(to_cs, int(amount)).build_transaction({
        "from": TREASURY_ADDRESS,
        "chainId": CHAIN_ID,
    })
    return _send_tx(tx)

@add_dual_route("/transfer", "post")
def transfer_query(to: str, amount: int):
    c = _contract()
    to_cs = _cs(to)
    tx = c.functions.transfer(to_cs, int(amount)).build_transaction({
        "from": TREASURY_ADDRESS,
        "chainId": CHAIN_ID,
    })
    return _send_tx(tx)
