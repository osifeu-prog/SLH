import os, json, math
from decimal import Decimal
from typing import Optional
from fastapi import FastAPI, HTTPException, Body, Header
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware

load_dotenv()

BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
CHAIN_ID = int(os.getenv("CHAIN_ID", "56"))
SELA_TOKEN_ADDRESS = os.getenv("SELA_TOKEN_ADDRESS", "").strip()
OPERATOR_PK = (os.getenv("OPERATOR_PK") or "").strip()
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()
GAS_PRICE_GWEI = os.getenv("GAS_PRICE_GWEI", "").strip()
GAS_LIMIT = int(os.getenv("GAS_LIMIT", "120000"))

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
# For BSC testnet/mainnet we sometimes need this middleware style for POA chains
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

if not w3.is_connected():
    raise RuntimeError("Web3 provider is not connected. Check BSC_RPC_URL.")

# Load ERC20 ABI
here = os.path.dirname(__file__)
with open(os.path.join(here, "erc20_abi.json"), "r", encoding="utf-8") as f:
    ERC20_ABI = json.load(f)

def token_contract():
    if not Web3.is_address(SELA_TOKEN_ADDRESS):
        raise HTTPException(status_code=500, detail="SELA_TOKEN_ADDRESS is invalid or missing")
    return w3.eth.contract(address=Web3.to_checksum_address(SELA_TOKEN_ADDRESS), abi=ERC20_ABI)

def operator_address() -> Optional[str]:
    if not OPERATOR_PK:
        return None
    acct = w3.eth.account.from_key(OPERATOR_PK)
    return acct.address

class TransferIn(BaseModel):
    to_addr: str = Field(..., description="Recipient address (0x...)")
    amount_slh: Decimal = Field(..., gt=Decimal('0'), description="Amount of SLH in token units")

app = FastAPI(title="SLH API", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "chain_id": CHAIN_ID,
        "token_address": Web3.to_checksum_address(SELA_TOKEN_ADDRESS) if Web3.is_address(SELA_TOKEN_ADDRESS) else None,
        "operator_address": operator_address(),
        "rpc_ok": w3.is_connected(),
    }

@app.get("/token/balance/{address}")
def token_balance(address: str):
    if not Web3.is_address(address):
        raise HTTPException(status_code=400, detail="invalid address")
    c = token_contract()
    bal = c.functions.balanceOf(Web3.to_checksum_address(address)).call()
    decimals = c.functions.decimals().call()
    human = Decimal(bal) / Decimal(10) ** Decimal(decimals)
    return {"ok": True, "address": Web3.to_checksum_address(address), "balance": str(human), "decimals": decimals}

@app.post("/transfer/slh")
def transfer_slh(data: TransferIn, x_internal_key: Optional[str] = Header(None, convert_underscores=True)):
    # Optional internal API key guard
    if INTERNAL_API_KEY:
        if not x_internal_key or x_internal_key != INTERNAL_API_KEY:
            raise HTTPException(status_code=403, detail="forbidden")

    if not OPERATOR_PK:
        raise HTTPException(status_code=500, detail="server not configured (OPERATOR_PK missing)")

    if not Web3.is_address(data.to_addr):
        raise HTTPException(status_code=400, detail="invalid to_addr")

    c = token_contract()

    decimals = c.functions.decimals().call()
    amount_wei = int(Decimal(data.amount_slh) * (Decimal(10) ** Decimal(decimals)))

    sender = w3.eth.account.from_key(OPERATOR_PK)
    sender_addr = sender.address

    # sanity: operator has token balance?
    op_bal = c.functions.balanceOf(sender_addr).call()
    if op_bal < amount_wei:
        raise HTTPException(status_code=400, detail="insufficient token balance in operator")

    # gas price
    if GAS_PRICE_GWEI:
        gp = int(Decimal(GAS_PRICE_GWEI) * (10 ** 9))
    else:
        gp = w3.eth.gas_price

    nonce = w3.eth.get_transaction_count(sender_addr)

    tx = c.functions.transfer(Web3.to_checksum_address(data.to_addr), amount_wei).build_transaction({
        "chainId": CHAIN_ID,
        "from": sender_addr,
        "nonce": nonce,
        "gas": GAS_LIMIT,
        "gasPrice": gp,
        "value": 0
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=OPERATOR_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction).hex()

    return {"ok": True, "tx_hash": tx_hash, "from": sender_addr, "to": Web3.to_checksum_address(data.to_addr), "amount_slh": str(data.amount_slh)}
