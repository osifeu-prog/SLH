import os
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from web3 import Web3
from web3.middleware import geth_poa_middleware

from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SLH API", version="1.0.0")

# ---- ENV ----
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "").strip()
SELA_TOKEN_ADDRESS = os.getenv("SELA_TOKEN_ADDRESS", "").strip()
CHAIN_ID = int(os.getenv("CHAIN_ID", "97"))
GAS_PRICE_FLOOR_WEI = int(os.getenv("GAS_PRICE_FLOOR_WEI", "500000000"))  # 0.5 gwei
SELA_DECIMALS_OVERRIDE = os.getenv("SELA_DECIMALS_OVERRIDE", "").strip() or None
SELA_SYMBOL_OVERRIDE = os.getenv("SELA_SYMBOL_OVERRIDE", "").strip() or None
SELA_MINT_FUNCS = os.getenv("SELA_MINT_FUNCS", "ownerMint,mintTo,mint")
TREASURY_PRIVATE_KEY = os.getenv("TREASURY_PRIVATE_KEY", "").strip() or None
TREASURY_ADDRESS = (os.getenv("TREASURY_ADDRESS", "").strip() or None)
NFT_CONTRACT = os.getenv("NFT_CONTRACT", "").strip() or None

if not BSC_RPC_URL:
    raise RuntimeError("BSC_RPC_URL missing")

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
# BSC testnet/mainnet require POA middleware in web3.py v6 for some providers
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

def to_checksum(addr: str) -> str:
    if not Web3.is_address(addr):
        raise HTTPException(400, detail="Invalid address format")
    return Web3.to_checksum_address(addr)

# derive address if private key present
if TREASURY_PRIVATE_KEY and not TREASURY_ADDRESS:
    acct = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
    TREASURY_ADDRESS = acct.address

# contract
ERC20_ABI = [{"constant": true, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"}, {"constant": true, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"}, {"constant": true, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"}, {"constant": true, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"constant": true, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"constant": false, "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}, {"constant": false, "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "mint", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]
if not SELA_TOKEN_ADDRESS:
    raise RuntimeError("SELA_TOKEN_ADDRESS missing")
TOKEN = w3.eth.contract(address=to_checksum(SELA_TOKEN_ADDRESS), abi=ERC20_ABI)

def get_decimals() -> int:
    if SELA_DECIMALS_OVERRIDE:
        return int(SELA_DECIMALS_OVERRIDE)
    return TOKEN.functions.decimals().call()

def get_symbol() -> str:
    if SELA_SYMBOL_OVERRIDE:
        return SELA_SYMBOL_OVERRIDE
    return TOKEN.functions.symbol().call()

def to_wei_human(amount_human: str) -> int:
    d = Decimal(amount_human)
    decimals = get_decimals()
    factor = Decimal(10) ** decimals
    return int(d * factor)

def format_units(value: int) -> str:
    decimals = get_decimals()
    factor = Decimal(10) ** decimals
    return str(Decimal(value) / factor)

@app.get("/health")
def health():
    return {"ok": True, "chainId": CHAIN_ID}

@app.get("/tokeninfo")
def tokeninfo():
    name = TOKEN.functions.name().call()
    symbol = get_symbol()
    decimals = get_decimals()
    supply = TOKEN.functions.totalSupply().call()
    return {
        "address": Web3.to_checksum_address(SELA_TOKEN_ADDRESS),
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
        "totalSupply": format_units(supply),
    }

@app.get("/balance/{address}")
def balance(address: str):
    addr = to_checksum(address)
    bal = TOKEN.functions.balanceOf(addr).call()
    return {"address": addr, "balance": format_units(bal)}

class TxIn(BaseModel):
    to: str
    amount: str  # human units

def _pick_gas_price(floor: int, override: Optional[int]) -> int:
    net_gas = int(w3.eth.gas_price)
    if override is not None and override > 0:
        net_gas = override
    return max(net_gas, floor)

@app.get("/estimate/{op}")
def estimate(op: str, to: str = Query(...), amount: str = Query(...), gasPriceWei: Optional[int] = Query(None)):
    to_addr = to_checksum(to)
    amt = to_wei_human(amount)
    if op not in {"mint", "transfer"}:
        raise HTTPException(400, "op must be 'mint' or 'transfer'")
    try:
        if op == "mint":
            fn = TOKEN.functions.mint(to_addr, amt)
        else:
            # transfer from TREASURY
            if not TREASURY_ADDRESS:
                raise HTTPException(400, "TREASURY_ADDRESS not configured")
            fn = TOKEN.functions.transfer(to_addr, amt)
        gas = fn.estimate_gas({"from": TREASURY_ADDRESS} if op == "transfer" else {"from": TREASURY_ADDRESS or to_addr})
        gp = _pick_gas_price(GAS_PRICE_FLOOR_WEI, gasPriceWei)
        total = gas * gp
        return {"gas": int(gas), "gasPriceWei": int(gp), "totalWei": int(total)}
    except Exception as e:
        raise HTTPException(400, f"estimate failed: {e}" )

def _build_and_send(fn):
    if not TREASURY_PRIVATE_KEY:
        raise HTTPException(400, "TREASURY_PRIVATE_KEY not configured")
    acct = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
    nonce = w3.eth.get_transaction_count(acct.address)
    gas = fn.estimate_gas({"from": acct.address})
    gas_price = _pick_gas_price(GAS_PRICE_FLOOR_WEI, None)
    tx = fn.build_transaction({
        "from": acct.address,
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "gas": gas,
        "gasPrice": gas_price
    })
    signed = w3.eth.account.sign_transaction(tx, TREASURY_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return {"txHash": tx_hash.hex(), "gas": int(gas), "gasPriceWei": int(gas_price)}

@app.post("/mint")
def mint(inp: TxIn):
    to_addr = to_checksum(inp.to)
    amt = to_wei_human(inp.amount)
    fn = TOKEN.functions.mint(to_addr, amt)
    return _build_and_send(fn)

@app.post("/transfer")
def transfer(inp: TxIn):
    to_addr = to_checksum(inp.to)
    amt = to_wei_human(inp.amount)
    fn = TOKEN.functions.transfer(to_addr, amt)
    return _build_and_send(fn)
