import os, logging, asyncio, re
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional
from dotenv import load_dotenv
import httpx
from httpx import Timeout, Limits
from pydantic import BaseModel, Field, validator
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

class BotConfig(BaseModel):
    TELEGRAM_BOT_TOKEN: str
    SLH_API_BASE: str
    MAINNET_API_BASE: Optional[str] = None
    GROUP_INVITE_LINK: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    ADMIN_CHAT_IDS: List[int] = Field(default_factory=list)
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    @validator("SLH_API_BASE","MAINNET_API_BASE", pre=True)
    def _strip(cls, v): return v.rstrip("/") if isinstance(v,str) and v else v
    @validator("ADMIN_CHAT_IDS", pre=True)
    def _admins(cls, v):
        if isinstance(v,str): return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v or []
    class Config: env_file = ".env"

config = BotConfig(
    TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN"),
    SLH_API_BASE=os.getenv("SLH_API_BASE"),
    MAINNET_API_BASE=os.getenv("MAINNET_API_BASE"),
    GROUP_INVITE_LINK=os.getenv("GROUP_INVITE_LINK"),
    LOG_LEVEL=os.getenv("LOG_LEVEL","INFO"),
    ADMIN_CHAT_IDS=os.getenv("ADMIN_CHAT_IDS",""),
)

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("slh.bot")

timeout = Timeout(config.REQUEST_TIMEOUT)
limits = Limits(max_connections=100, max_keepalive_connections=20)

class SLHAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=timeout, limits=limits, headers={"User-Agent":"SLH-Telegram-Bot/2.1"})
    async def __aenter__(self): return self
    async def __aexit__(self,*a): await self.client.aclose()
    def _validate_addr(self, a: str):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", a): raise ValueError("invalid address")
    def _validate_amount(self, s: str):
        try:
            d = Decimal(s)
            if d <= 0: raise ValueError()
        except (InvalidOperation, ValueError): raise ValueError("invalid amount")
    async def _req(self, method, path, **kw):
        last = None
        for i in range(config.MAX_RETRIES):
            try:
                r = await self.client.request(method, f"{self.base_url}{path}", **kw)
                r.raise_for_status(); return r.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500: raise
                last = e
            except Exception as e:
                last = e
            if i < config.MAX_RETRIES-1:
                await asyncio.sleep(config.RETRY_DELAY * (2**i))
        raise last or Exception("request failed")
    async def tokeninfo(self): return await self._req("GET","/tokeninfo")
    async def balance(self, addr: str):
        self._validate_addr(addr); return await self._req("GET", f"/balance/{addr}")
    async def estimate(self, op: str, to: str, amount: str):
        self._validate_addr(to); self._validate_amount(amount)
        return await self._req("GET", f"/estimate/{op}", params={"to":to,"amount":amount})
    async def mint(self, to: str, amount: str):
        self._validate_addr(to); self._validate_amount(amount)
        return await self._req("POST","/mint", json={"to":to,"amount":amount})
    async def transfer(self, to: str, amount: str):
        self._validate_addr(to); self._validate_amount(amount)
        return await self._req("POST","/transfer", json={"to":to,"amount":amount})

class SLHBot:
    def __init__(self):
        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self.api_base = config.SLH_API_BASE
        self.admin_mode: Dict[int,bool] = {}
        self._add_handlers()
    def _add_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.start))
        self.app.add_handler(CommandHandler("tokeninfo", self.cmd_tokeninfo))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("estimate", self.cmd_estimate))
        self.app.add_handler(CommandHandler("mint", self.cmd_mint))
        self.app.add_handler(CommandHandler("send", self.cmd_send))
        self.app.add_handler(CommandHandler("use", self.cmd_use))
        self.app.add_handler(CommandHandler("mode", self.cmd_mode))
        self.app.add_error_handler(self.on_error)
    async def is_admin(self, uid:int) -> bool: return uid in config.ADMIN_CHAT_IDS
    async def start(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        link = f"\nJoin: {config.GROUP_INVITE_LINK}" if config.GROUP_INVITE_LINK else ""
        txt = ("SLH Bot is up!\n"
               "/tokeninfo – contract stats\n"
               "/balance <address>\n"
               "/estimate <mint|transfer> <to> <amount>\n"
               "/mint <to> <amount> (owner)\n"
               "/send <to> <amount> (owner)\n"
               "/use <testnet|mainnet>\n"
               "/mode <user|admin>" + link)
        await u.message.reply_text(txt)
    async def cmd_use(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        args = u.message.text.split()[1:] if u.message and u.message.text else []
        if not args:
            await u.message.reply_text("usage: /use <testnet|mainnet>"); return
        net = args[0].lower()
        if net == "mainnet":
            if not config.MAINNET_API_BASE:
                await u.message.reply_text("MAINNET_API_BASE not set"); return
            self.api_base = config.MAINNET_API_BASE
        elif net == "testnet":
            self.api_base = config.SLH_API_BASE
        else:
            await u.message.reply_text("must be 'testnet' or 'mainnet'"); return
        await u.message.reply_text(f"using {net}: {self.api_base}")
    async def cmd_mode(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        args = u.message.text.split()[1:] if u.message and u.message.text else []
        if not args:
            await u.message.reply_text("usage: /mode <user|admin>"); return
        uid = u.effective_user.id
        if args[0].lower()=="admin":
            if not await self.is_admin(uid):
                await u.message.reply_text("admins only"); return
            self.admin_mode[uid] = True
            await u.message.reply_text("admin mode on"); return
        self.admin_mode[uid] = False
        await u.message.reply_text("user mode on")
    async def cmd_tokeninfo(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        try:
            async with SLHAPIClient(self.api_base) as api:
                ti = await api.tokeninfo()
            await u.message.reply_text(
                f"Token\nContract: `{ti.get('address')}`\nSymbol: {ti.get('symbol')}\nDecimals: {ti.get('decimals')}\nTotal: {ti.get('totalSupply')}",
                parse_mode="Markdown")
        except Exception as e:
            await u.message.reply_text(f"tokeninfo failed: {e}")
    async def cmd_balance(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        args = u.message.text.split()[1:] if u.message and u.message.text else []
        if len(args)!=1:
            await u.message.reply_text("usage: /balance <address>"); return
        try:
            async with SLHAPIClient(self.api_base) as api:
                b = await api.balance(args[0])
                ti = await api.tokeninfo()
            await u.message.reply_text(f"{b.get('address')}\n{b.get('balance')} {ti.get('symbol')}")
        except Exception as e:
            await u.message.reply_text(f"balance failed: {e}")
    async def cmd_estimate(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        args = u.message.text.split()[1:] if u.message and u.message.text else []
        if len(args)!=3:
            await u.message.reply_text("usage: /estimate <mint|transfer> <to> <amount>"); return
        op,to,amt = args
        try:
            async with SLHAPIClient(self.api_base) as api:
                est = await api.estimate(op,to,amt)
            gwei = Decimal(est["gasPriceWei"]) / Decimal(1_000_000_000)
            fee = Decimal(est["totalWei"]) / Decimal(1e18)
            await u.message.reply_text(f"Gas: {est['gas']}\nGasPrice: {gwei:.2f} Gwei\nTotal: {fee:.8f} BNB")
        except Exception as e:
            await u.message.reply_text(f"estimate failed: {e}")
    async def cmd_mint(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if not await self.is_admin(uid) or not self.admin_mode.get(uid, False):
            await u.message.reply_text("admin + /mode admin required"); return
        args = u.message.text.split()[1:]
        if len(args)!=2:
            await u.message.reply_text("usage: /mint <to> <amount>"); return
        to,amt = args
        try:
            async with SLHAPIClient(self.api_base) as api:
                tx = await api.mint(to,amt)
            await u.message.reply_text(f"minted\nTx: `{tx.get('txHash')}`", parse_mode="Markdown")
        except Exception as e:
            await u.message.reply_text(f"mint failed: {e}")
    async def cmd_send(self, u:Update, c:ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if not await self.is_admin(uid) or not self.admin_mode.get(uid, False):
            await u.message.reply_text("admin + /mode admin required"); return
        args = u.message.text.split()[1:]
        if len(args)!=2:
            await u.message.reply_text("usage: /send <to> <amount>"); return
        to,amt = args
        try:
            async with SLHAPIClient(self.api_base) as api:
                tx = await api.transfer(to,amt)
            await u.message.reply_text(f"sent\nTx: `{tx.get('txHash')}`", parse_mode="Markdown")
        except Exception as e:
            await u.message.reply_text(f"send failed: {e}")
    async def on_error(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        log.error("Update error", exc_info=ctx.error)
        try:
            if u and u.effective_message:
                await u.effective_message.reply_text("unexpected error")
        except: pass
    def run(self):
        log.info("Starting bot (run_polling)...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

def main():
    SLHBot().run()

if __name__ == "__main__":
    main()
