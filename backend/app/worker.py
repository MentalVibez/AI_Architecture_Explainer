import asyncio
import logging

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.services.worker_runtime import run_worker_loop

configure_logging(settings.environment)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("starting_codebase_atlas_worker")
    await run_worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
