import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiohttp import web

from app.bot.handlers import router
from app.config import config

logger = structlog.get_logger()


# ── Webhook handler ──────────────────────────────────────────────────────────

async def webhook_handler(request: web.Request) -> web.Response:
    """Receive Telegram update via POST and feed it to the dispatcher."""
    # Validate secret token if configured
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if config.telegram_webhook_secret and secret_header != config.telegram_webhook_secret:
        return web.Response(status=403, text="Invalid secret token")

    bot: Bot = request.app["bot"]
    dp: Dispatcher = request.app["dp"]

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return web.Response(status=200)


async def on_webhook_startup(app: web.Application) -> None:
    """Register the webhook URL with Telegram on startup."""
    bot: Bot = app["bot"]
    await bot.set_webhook(
        url=config.telegram_webhook_url,
        secret_token=config.telegram_webhook_secret or None,
        drop_pending_updates=True,
    )
    logger.info(
        "webhook_registered",
        url=config.telegram_webhook_url,
        port=config.telegram_webhook_port,
    )


async def on_webhook_shutdown(app: web.Application) -> None:
    """Clean up bot session and optionally delete the webhook."""
    bot: Bot = app["bot"]
    # Delete webhook so polling mode can be used next time without conflict
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()
    logger.info("webhook_deleted")


# ── Mode runners ─────────────────────────────────────────────────────────────

async def run_webhook_mode() -> None:
    """Start the bot in webhook mode: listen for Telegram POST requests."""
    bot = Bot(token=config.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app.router.add_post("/telegram/webhook", webhook_handler)
    app.on_startup.append(on_webhook_startup)
    app.on_shutdown.append(on_webhook_shutdown)

    port = config.telegram_webhook_port
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    logger.info("bot_webhook_mode_listening", port=port, path="/telegram/webhook")
    await site.start()

    # Block forever (until signal or exception)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def run_polling_mode() -> None:
    """Start the bot in polling mode: long-poll Telegram for updates."""
    bot = Bot(token=config.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Ensure no stale webhook is registered before polling
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("bot_polling_mode_started")
    await dp.start_polling(bot)


# ── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    mode = config.telegram_mode
    logger.info("pitch_wow_bot_starting", mode=mode)

    if mode == "webhook":
        if not config.telegram_webhook_url:
            logger.error("webhook_mode_requires_TELEGRAM_WEBHOOK_URL")
            raise SystemExit(1)
        await run_webhook_mode()
    else:
        await run_polling_mode()


if __name__ == "__main__":
    asyncio.run(main())
