
import os, re, json, logging, asyncio
from typing import Dict
from decimal import Decimal

import httpx
from httpx import Timeout, Limits
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# -------- Config via ENV --------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","")
TESTNET_API_BASE = os.getenv("TESTNET_API_BASE","").rstrip("/")
MAINNET_API_BASE = os.getenv("MAINNET_API_BASE","").rstrip("/")
DEFAULT_NET = os.getenv("DEFAULT_NET","testnet").lower()  # testnet | mainnet
LOG_LEVEL = os.getenv("LOG_LEVEL","INFO").upper()
ADMIN_USER_IDS = [int(x.strip()) for x in os.getenv("ADMIN_USER_IDS","").split(",") if x.strip()]

timeout = Timeout(30.0)
limits = Limits(max_connections=100, max_keepalive_connections=20)

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger("slh.bot")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

# -------- State --------
# Per-chat preferences: network + mode
STATE: Dict[int, Dict[str,str]] = {}   # {chat_id: {"net": "testnet|mainnet", "mode": "user|admin"}}

# Shared HTTP client
HTTP = httpx.AsyncClient(timeout=timeout, limits=limits, headers={"User-Agent":"SLH-Telegram-Bot/2.1"})

def api_base_for(chat_id: int) -> str:
    net = STATE.get(chat_id, {}).get("net", DEFAULT_NET)
    if net == "mainnet":
        return MAINNET_API_BASE or TESTNET_API_BASE
    return TESTNET_API_BASE or MAINNET_API_BASE

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

def _valid_addr(a: str) -> bool:
    return re.match(r"^0x[a-fA-F0-9]{40}$", a) is not None

def _explorer_for(chain_id: int) -> str:
    return "https://bscscan.com" if chain_id == 56 else "https://testnet.bscscan.com"

async def _get(path: str, chat_id: int):
    base = api_base_for(chat_id)
    for p in [path, f"/api{path}", f"/v1{path}"]:
        url = f"{base}{p}"
        try:
            r = await HTTP.get(url)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log.warning("GET %s failed: %s", url, e)
    raise RuntimeError(f"GET failed for ['{base}{path}','{base}/api{path}','{base}/v1{path}']")

async def _post(path: str, payload: dict, chat_id: int):
    base = api_base_for(chat_id)
    for p in [path, f"/api{path}", f"/v1{path}"]:
        url = f"{base}{p}"
        try:
            r = await HTTP.post(url, json=payload)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log.warning("POST %s failed: %s", url, e)
    raise RuntimeError(f"POST failed for ['{base}{path}','{base}/api{path}','{base}/v1{path}']")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mode = STATE.get(chat_id, {}).get("mode","user")
    net = STATE.get(chat_id, {}).get("net", DEFAULT_NET)
    admins = " (admin)" if mode=="admin" else ""
    await update.message.reply_text(
f"""SLH Bot is up{admins}!
Current network: *{net}*
/use testnet – switch to Testnet
/use mainnet – switch to Mainnet

/tokeninfo – contract stats
/balance <address>
/estimate <mint|transfer> <to> <amount_wei>
{"*/mint <to> <amount_wei>* (admin)\n*/send <to> <amount_wei>* (admin)" if mode=="admin" else ""}
/mode user|admin – toggle view (admin auth required)
/stats – debug info""",
        parse_mode="Markdown"
    )

async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /mode user|admin")
        return
    wanted = context.args[0].lower()
    if wanted not in ("user","admin"):
        await update.message.reply_text("Mode must be user|admin"); return
    if wanted=="admin" and not is_admin(user_id):
        await update.message.reply_text("❌ Admins only."); return
    STATE.setdefault(chat_id, {})["mode"] = wanted
    await update.message.reply_text(f"Mode set to {wanted}")

async def use_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /use testnet|mainnet"); return
    net = context.args[0].lower()
    if net not in ("testnet","mainnet"):
        await update.message.reply_text("Network must be testnet|mainnet"); return
    STATE.setdefault(chat_id, {})["net"] = net
    await update.message.reply_text(f"Switched to *{net}*.", parse_mode="Markdown")

async def tokeninfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        data = await _get("/tokeninfo", chat_id)
        supply = data.get("totalSupply")
        chain_id = data.get("chain_id", 97)
        msg = (f"📊 *Token Info*\n"
               f"*Network:* {'Mainnet' if chain_id==56 else 'Testnet'} (chainId {chain_id})\n"
               f"*Contract:* `{data.get('address')}`\n"
               f"*Name:* {data.get('name')}  *Symbol:* {data.get('symbol')}  *Decimals:* {data.get('decimals')}\n"
               f"*Total Supply:* {supply}")
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ tokeninfo failed: {e}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args)!=1:
        await update.message.reply_text("Usage: /balance <address>"); return
    addr = context.args[0]
    if not _valid_addr(addr):
        await update.message.reply_text("❌ invalid address"); return
    try:
        data = await _get(f"/balance/{addr}", chat_id)
        chain_id = data.get("chain_id", 97)
        # amount returned in wei (string)
        wei = Decimal(data.get("balance","0"))
        # need decimals/symbol; fetch tokeninfo:
        ti = await _get("/tokeninfo", chat_id)
        dec = int(ti.get("decimals",18))
        sym = ti.get("symbol","SLH")
        human = (wei / (Decimal(10) ** dec)).quantize(Decimal("0.000001"))
        await update.message.reply_text(
            f"💰 *Balance*\n"
            f"*Address:* `{data.get('address')}`\n"
            f"*Amount:* {human} {sym}\n"
            f"*Network:* {'Mainnet' if chain_id==56 else 'Testnet'}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ balance failed: {e}")

async def estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args)!=3:
        await update.message.reply_text("Usage: /estimate <mint|transfer> <to> <amount_wei>"); return
    op,to,amount = context.args
    if op not in ("mint","transfer"):
        await update.message.reply_text("op must be mint|transfer"); return
    if not _valid_addr(to):
        await update.message.reply_text("❌ invalid address"); return
    try:
        data = await _get(f"/estimate/{op}?to={to}&amount={amount}", chat_id)
        chain_id = data.get("chain_id",97)
        gwei = Decimal(data["gasPriceWei"]) / Decimal(1_000_000_000)
        total_bnb = Decimal(data["gasPriceWei"]) * Decimal(data["gas"]) / Decimal(1e18)
        await update.message.reply_text(
            f"⚡ *Estimation ({op})*\n"
            f"Gas: {data['gas']}  |  GasPrice: {gwei:.2f} Gwei\n"
            f"Total Fee: {total_bnb:.8f} {'BNB' if chain_id==56 else 'tBNB'}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ estimate failed: {e}")

async def mint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admins only."); return
    if len(context.args)!=2:
        await update.message.reply_text("Usage: /mint <to> <amount_wei>"); return
    to,amount = context.args
    if not _valid_addr(to):
        await update.message.reply_text("❌ invalid address"); return
    try:
        data = await _post("/mint", {"to": to, "amount": amount}, chat_id)
        chain_id = data.get("chain_id",97)
        expl = _explorer_for(chain_id)
        h = data.get("txHash")
        link = f"{expl}/tx/{h}" if h else expl
        await update.message.reply_text(
            f"✅ Mint sent.\nTx: `{h}`\n{link}", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ mint failed: {e}")

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admins only."); return
    if len(context.args)!=2:
        await update.message.reply_text("Usage: /send <to> <amount_wei>"); return
    to,amount = context.args
    if not _valid_addr(to):
        await update.message.reply_text("❌ invalid address"); return
    try:
        data = await _post("/transfer", {"to": to, "amount": amount}, chat_id)
        chain_id = data.get("chain_id",97)
        expl = _explorer_for(chain_id)
        h = data.get("txHash")
        link = f"{expl}/tx/{h}" if h else expl
        await update.message.reply_text(
            f"✅ Transfer sent.\nTx: `{h}`\n{link}", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ send failed: {e}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    net = STATE.get(chat_id, {}).get("net", DEFAULT_NET)
    mode = STATE.get(chat_id, {}).get("mode","user")
    await update.message.reply_text(
        f"📈 Stats\nNet: {net}\nMode: {mode}\nTestnet API: {TESTNET_API_BASE}\nMainnet API: {MAINNET_API_BASE}"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("use", use_cmd))
    app.add_handler(CommandHandler("mode", mode_cmd))
    app.add_handler(CommandHandler("tokeninfo", tokeninfo))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("estimate", estimate))
    app.add_handler(CommandHandler("mint", mint))
    app.add_handler(CommandHandler("send", send))
    app.add_handler(CommandHandler("stats", stats))

    # polling by default; webhook can be added later similarly
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
