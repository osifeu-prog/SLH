from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
import os

app = FastAPI(title="SLH API", version="1.0.0")

RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
CHAIN_ID = int(os.getenv("CHAIN_ID", "56"))
TOKEN_ADDRESS = Web3.to_checksum_address(os.getenv("SELA_TOKEN_ADDRESS", "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"))
TREASURY_PK = os.getenv("TREASURY_PRIVATE_KEY")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

ERC20_MIN_ABI = [
  {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
  {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
  {"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"type":"function"},
]

token = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_MIN_ABI)

class EstimateReq(BaseModel):
    kind: str      # "mint" | "transfer"
    to: str
    amount: str    # יחידות שלמות (לפני המרת דצימלים)

class TxReq(BaseModel):
    to: str
    amount: str

def to_checksum(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid address")

def amount_to_wei(amount_str: str) -> int:
    dec = token.functions.decimals().call()
    amt = int(amount_str)
    return amt * (10 ** dec)

def build_tx(sender: str):
    nonce = w3.eth.get_transaction_count(sender)
    return {"chainId": CHAIN_ID, "nonce": nonce, "gasPrice": w3.eth.gas_price}

@app.get("/healthz")
def healthz():
    return {"ok": True, "rpc": RPC_URL, "chainId": CHAIN_ID, "token": TOKEN_ADDRESS}

@app.get("/tokeninfo")
def tokeninfo():
    try:
        return {
            "address": TOKEN_ADDRESS,
            "name": token.functions.name().call(),
            "symbol": token.functions.symbol().call(),
            "decimals": token.functions.decimals().call(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"tokeninfo error: {e}")

@app.get("/balance/{address}")
def balance(address: str):
    try:
        addr = to_checksum(address)
        bal = token.functions.balanceOf(addr).call()
        decimals = token.functions.decimals().call()
        return {"address": addr, "balance_raw": str(bal), "decimals": decimals}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"balance error: {e}")

@app.post("/estimate")
def estimate(req: EstimateReq):
    to = to_checksum(req.to)
    amount = amount_to_wei(req.amount)
    sender = w3.eth.account.from_key(TREASURY_PK).address if TREASURY_PK else to
    tx_common = build_tx(sender)
    try:
        if req.kind.lower() == "transfer":
            tx = token.functions.transfer(to, amount).build_transaction({"from": sender, **tx_common})
        elif req.kind.lower() == "mint":
            tx = token.functions.mint(to, amount).build_transaction({"from": sender, **tx_common})
        else:
            raise HTTPException(status_code=400, detail="kind must be 'mint' or 'transfer'")

        gas = w3.eth.estimate_gas(tx)
        return {"gas": gas, "gasPrice": str(tx["gasPrice"]), "estimatedFeeWei": str(gas * tx["gasPrice"])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"estimate error: {e}")

@app.post("/mint")
def mint(req: TxReq):
    if not TREASURY_PK:
        raise HTTPException(status_code=403, detail="TREASURY_PRIVATE_KEY not configured")
    to = to_checksum(req.to)
    amount = amount_to_wei(req.amount)
    account = w3.eth.account.from_key(TREASURY_PK)
    tx_common = build_tx(account.address)
    try:
        tx = token.functions.mint(to, amount).build_transaction({"from": account.address, **tx_common})
        gas = w3.eth.estimate_gas(tx)
        tx["gas"] = gas
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        return {"txHash": tx_hash.hex()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"mint error: {e}")

@app.post("/send")
def send(req: TxReq):
    if not TREASURY_PK:
        raise HTTPException(status_code=403, detail="TREASURY_PRIVATE_KEY not configured")
    to = to_checksum(req.to)
    amount = amount_to_wei(req.amount)
    account = w3.eth.account.from_key(TREASURY_PK)
    tx_common = build_tx(account.address)
    try:
        tx = token.functions.transfer(to, amount).build_transaction({"from": account.address, **tx_common})
        gas = w3.eth.estimate_gas(tx)
        tx["gas"] = gas
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        return {"txHash": tx_hash.hex()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"send error: {e}")
