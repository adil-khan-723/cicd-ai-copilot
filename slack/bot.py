"""
Slack bot entrypoint — Socket Mode.
Registers all handlers and starts the Bolt app.
Run with: python -m slack.bot
"""
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from config import get_settings
from slack.approval_handler import register_approval_handlers
from slack.copilot_handler import register_copilot_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> App:
    settings = get_settings()
    app = App(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )
    register_approval_handlers(app)
    register_copilot_handlers(app)
    return app


if __name__ == "__main__":
    settings = get_settings()
    app = create_app()
    logger.info("Starting Slack bot in Socket Mode...")
    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()
