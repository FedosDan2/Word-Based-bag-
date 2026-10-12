import asyncio
import logging

from bugizslov.bot import run_bot
from bugizslov.config import Settings


def main() -> None:
    settings = Settings.from_env()
    settings.validate()
    try:
        asyncio.run(run_bot(settings))
    except KeyboardInterrupt:
        logging.info("Bot stopped")


if __name__ == "__main__":
    main()
