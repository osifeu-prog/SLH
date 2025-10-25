import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from web3.middleware import geth_poa_middleware

app = FastAPI(title="SLH API", version="1.0.0")

# -------- ENV --------
RPC_URL            = os.getenv("BSC_RPC_URL", "")
CHAIN_ID           = int(os.getenv("CHAIN_ID", "0") or "0")
TOKEN_ADDRESS      = os.getenv("SELA_TOKEN_ADDRESS", "")
DECIMALS_OVERRIDE  = os.getenv("SELA_DECIMALS_OVERRIDE")
SYMBOL_OVERRIDE    = os.getenv("SELA_SYMBOL_OVERRIDE")
MINT_FUNCS         = [s.strip() for s in os.getenv("SELA_MINT_FUNCS", "").split(",") if s.strip()]
GAS_PRICE_FLOOR    = int(os.getenv("GAS_PRICE_FLOOR_WEI", "0") or "0")
TREASURY_PK        = os.getenv("TREASURY_PRIVATE_KEY")  # optional
TREASURY_ADDRESS   = os.getenv("TREASURY_ADDRESS")      # optional
DEFAULT_WALLET     = os.getenv("DEFAULT_WALLET")        # optional

# -------- Web3 --------
w3 = None
contract = None
token_decimals = None
token_symbol = None

ERC20_ABI = [
  {"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}
]

def _init():
    global w3, contract, token_decimals, token_symbol
    if not RPC_URL or not TOKEN_ADDRESS:
        return
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    # חלק מרשתות BSC testnet/sidechain דורשות POA middleware
    try:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass
    if not w3.is_connected():
        raise RuntimeError("Web3 connection failed")

    contract = w3.eth.contract(address=Web3.to_checksum_address(TOKEN_ADDRESS), abi=ERC20_ABI)
    if DECIMALS_OVERRIDE:
        token_decimals = int(DECIMALS_OVERRIDE)
    else:
        try:
            token_decimals = contract.functions.decimals().call()
        except Exception:
            token_decimals = 18

    token_symbol = SYMBOL_OVERRIDE or (contract.functions.symbol().call() if contract else "SELA")

try:
    _init()
except Exception as e:
    # נטפל בשגיאה ברנטיים בראוטים; לא נעצור את השרת
    w3 = None
    contract = None

# -------- Models --------
class TxReq(BaseModel):
    to: str
    amount: int  # בכמות של Whole tokens אם נשתמש ב-decimals, או ב-wei אם תרצה raw

# -------- Helpers --------
def _ensure_ready(require_pk: bool = False):
    if not RPC_URL or not TOKEN_ADDRESS or not contract or not w3:
        raise HTTPException(500, detail="API not configured (RPC/TOKEN_ADDRESS).")
    if require_pk and not TREASURY_PK:
        raise HTTPException(500, detail="Missing TREASURY_PRIVATE_KEY for tx.")

def _gas_price():
    gp = w3.eth.gas_price
    return max(gp, GAS_PRICE_FLOOR) if GAS_PRICE_FLOOR else gp

def _scale_amount(amount_tokens: int) -> int:
    # amount נכנס ביחידות טוקן שלמות → נהפוך ליחידות ERC20 (wei-like)
    d = token_decimals if token_decimals is not None else 18
    return int(amount_tokens) * (10 ** d)

# -------- Routes --------
@app.get("/healthz")
def healthz():
    return {"ok": True, "web3": bool(w3 and w3.is_connected()), "chainId": CHAIN_ID or None}

@app.get("/tokeninfo")
def tokeninfo():
    _ensure_ready()
    try:
        name = contract.functions.name().call()
    except Exception:
        name = None
    try:
        symbol = token_symbol or (contract.functions.symbol().call())
    except Exception:
        symbol = None
    try:
        decimals = token_decimals if token_decimals is not None else contract.functions.decimals().call()
    except Exception:
        decimals = None
    try:
        total = contract.functions.totalSupply().call()
    except Exception:
        total = None
    return {"address": Web3.to_checksum_address(TOKEN_ADDRESS),
            "name": name, "symbol": symbol, "decimals": decimals, "totalSupply": total}

@app.get("/balance/{address}")
def balance(address: str):
    _ensure_ready()
    try:
        addr = Web3.to_checksum_address(address)
    except Exception:
        raise HTTPException(400, detail="invalid address")
    try:
        raw = contract.functions.balanceOf(addr).call()
        d = token_decimals if token_decimals is not None else 18
        scaled = float(raw) / float(10 ** d)
        return {"address": addr, "raw": str(raw), "decimals": d, "amount": scaled}
    except Exception as e:
        raise HTTPException(500, detail=f"balance error: {e}")

@app.post("/mint")
def mint(req: TxReq):
    _ensure_ready(require_pk=True)
    # נמצא פונקציית mint חוקית לפי SELA_MINT_FUNCS, אחרת נחזיר 400
    candidates = MINT_FUNCS or ["mint", "ownerMint", "mintTo"]
    fn = None
    for name in candidates:
        if hasattr(contract.functions, name):
            fn = name
            break
    if not fn:
        raise HTTPException(400, detail="no mint function configured/found")

    try:
        to = Web3.to_checksum_address(req.to)
    except Exception:
        raise HTTPException(400, detail="invalid to address")

    amount = _scale_amount(req.amount)
    acct = w3.eth.account.from_key(TREASURY_PK)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = getattr(contract.functions, fn)(to, amount).build_transaction({
        "chainId": CHAIN_ID or w3.eth.chain_id,
        "from": acct.address,
        "nonce": nonce,
        "gasPrice": _gas_price(),
    })
    # estimate gas
    tx["gas"] = tx.get("gas") or w3.eth.estimate_gas(tx)
    signed = w3.eth.account.sign_transaction(tx, private_key=TREASURY_PK)
    try:
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        return {"txHash": tx_hash.hex(), "function": fn}
    except Exception as e:
        raise HTTPException(500, detail=f"mint error: {e}")

@app.post("/send")
def send(req: TxReq):
    _ensure_ready(require_pk=True)
    try:
        to = Web3.to_checksum_address(req.to)
    except Exception:
        raise HTTPException(400, detail="invalid to address")
    amount = _scale_amount(req.amount)

    acct = w3.eth.account.from_key(TREASURY_PK)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = contract.functions.transfer(to, amount).build_transaction({
        "chainId": CHAIN_ID or w3.eth.chain_id,
        "from": acct.address,
        "nonce": nonce,
        "gasPrice": _gas_price(),
    })
    tx["gas"] = tx.get("gas") or w3.eth.estimate_gas(tx)
    signed = w3.eth.account.sign_transaction(tx, private_key=TREASURY_PK)
    try:
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        return {"txHash": tx_hash.hex()}
    except Exception as e:
        raise HTTPException(500, detail=f"send error: {e}")
