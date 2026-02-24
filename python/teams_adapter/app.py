"""Teams adapter web application — receives Bot Framework messages, forwards to ZeroClaw."""

import logging
import sys

from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity

from .bot import ZeroClawTeamsBot
from .config import settings
from .zeroclaw_client import ZeroClawClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Bot Framework adapter
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.bot_app_id,
    app_password=settings.bot_app_secret,
)
adapter = BotFrameworkAdapter(adapter_settings)

# ZeroClaw gateway client
zeroclaw_client = ZeroClawClient(
    gateway_url=settings.zeroclaw_gateway_url,
    token=settings.zeroclaw_gateway_token,
    timeout=settings.zeroclaw_timeout,
)

# Bot instance
bot = ZeroClawTeamsBot(zeroclaw_client)


async def on_error(context, error):
    """Global error handler for the adapter."""
    logger.exception("Unhandled bot error: %s", error)
    await context.send_activity("Sorry, something went wrong. Please try again.")


adapter.on_turn_error = on_error


async def messages(request: web.Request) -> web.Response:
    """Handle incoming Bot Framework messages at POST /api/messages."""
    if "application/json" not in request.headers.get("Content-Type", ""):
        return web.Response(status=415, text="Unsupported media type")

    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    response = await adapter.process_activity(activity, auth_header, bot.on_turn)

    if response:
        return web.json_response(data=response.body, status=response.status)
    return web.Response(status=201)


async def health(request: web.Request) -> web.Response:
    """Health check — verifies adapter is running and ZeroClaw is reachable."""
    gw_healthy = await zeroclaw_client.health_check()
    status = {"adapter": "ok", "zeroclaw_gateway": "ok" if gw_healthy else "unreachable"}
    http_status = 200 if gw_healthy else 503
    return web.json_response(status, status=http_status)


def create_app() -> web.Application:
    """Create the aiohttp web application."""
    app = web.Application()
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)
    return app


def main():
    """Entry point for the Teams adapter."""
    logger.info(
        "Starting Teams adapter on %s:%d", settings.adapter_host, settings.adapter_port
    )
    logger.info("ZeroClaw gateway: %s", settings.zeroclaw_gateway_url)
    app = create_app()
    web.run_app(app, host=settings.adapter_host, port=settings.adapter_port)


if __name__ == "__main__":
    main()
