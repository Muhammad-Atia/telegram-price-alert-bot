"""Telegram price alert bot.

/add BTCUSDT > 70000   alert when BTCUSDT trades at or above 70,000
/add ETHUSDT < 2500    alert when ETHUSDT trades at or below 2,500
/list                  your active alerts
/remove 3              delete alert #3
/price SOLUSDT         current price

A JobQueue task asks Binance for the prices of every watched symbol in one request every CHECK_INTERVAL seconds;
an alert that fires is sent once and removed.
"""
from __future__ import annotations

import logging
import os

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from .alerts import ParseError, fmt, list_text, parse_add, triggered_text
from .binance import BASE, Binance
from .store import Store

log = logging.getLogger("price-alert-bot")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHECK_INTERVAL = float(os.environ.get("CHECK_INTERVAL", "15"))
MAX_ALERTS_PER_CHAT = int(os.environ.get("MAX_ALERTS_PER_CHAT", "20"))
DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
BINANCE_BASE_URL = os.environ.get("BINANCE_BASE_URL", BASE)

HELP = (
    "<b>Price alerts from Binance</b>\n\n"
    "/add BTCUSDT &gt; 70000 — alert at or above\n"
    "/add ETHUSDT &lt; 2500 — alert at or below\n"
    "/list — your alerts\n"
    "/remove ID — delete one\n"
    "/price SYMBOL — current price"
)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP, parse_mode=ParseMode.HTML)


async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    store: Store = ctx.bot_data["store"]
    bn: Binance = ctx.bot_data["binance"]
    chat = update.effective_chat.id
    try:
        symbol, op, price = parse_add(" ".join(ctx.args))
    except ParseError as e:
        await update.effective_message.reply_text(str(e))
        return
    if symbol not in await bn.symbols():
        await update.effective_message.reply_text(f"{symbol} is not a Binance spot symbol (try BTCUSDT, ETHUSDT, SOLUSDT…)")
        return
    if store.count(chat) >= MAX_ALERTS_PER_CHAT:
        await update.effective_message.reply_text(f"Limit reached ({MAX_ALERTS_PER_CHAT} alerts). Remove one with /remove ID")
        return
    a = store.add(chat, symbol, op, price)
    last = await bn.price(symbol)
    await update.effective_message.reply_text(f"✅ Alert #{a.id} set: {a.describe()}\nNow: {fmt(last)}")


async def list_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(list_text(ctx.bot_data["store"].for_chat(update.effective_chat.id)))


async def remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if len(ctx.args) != 1 or not ctx.args[0].lstrip("#").isdigit():
        await update.effective_message.reply_text("Usage: /remove ID   (see /list)")
        return
    ok = ctx.bot_data["store"].remove(update.effective_chat.id, int(ctx.args[0].lstrip("#")))
    await update.effective_message.reply_text("🗑 Removed." if ok else "No such alert in this chat.")


async def price(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bn: Binance = ctx.bot_data["binance"]
    symbol = (ctx.args[0] if ctx.args else "").upper()
    if symbol not in await bn.symbols():
        await update.effective_message.reply_text("Usage: /price BTCUSDT")
        return
    await update.effective_message.reply_text(f"{symbol}: {fmt(await bn.price(symbol))}")


async def check(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """One request for all watched symbols; fire, notify, then delete the alert (fires once)."""
    store: Store = ctx.bot_data["store"]
    alerts = store.all()
    if not alerts:
        return
    try:
        last = await ctx.bot_data["binance"].prices({a.symbol for a in alerts})
    except httpx.HTTPError as e:   # network hiccup or rate limit: try again on the next tick
        log.warning("price check failed: %r", e)
        return
    for a in alerts:
        p = last.get(a.symbol)
        if p is not None and a.hit(p):
            await ctx.bot.send_message(a.chat_id, triggered_text(a, p), parse_mode=ParseMode.HTML)
            store.remove(a.chat_id, a.id)
            log.info("alert %s fired: %s at %s", a.id, a.describe(), p)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("handler error", exc_info=ctx.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Something went wrong, please try again.")


async def post_init(app: Application) -> None:
    app.bot_data["binance"] = Binance(BINANCE_BASE_URL)
    app.bot_data["store"] = Store(DB_PATH)
    app.job_queue.run_repeating(check, interval=CHECK_INTERVAL, first=5)


async def post_shutdown(app: Application) -> None:
    await app.bot_data["binance"].close()


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)   # httpx logs every request URL, which contains the bot token
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (copy .env.example to .env)")
    app = Application.builder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_alerts))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("price", price))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
