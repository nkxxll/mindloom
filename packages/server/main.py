import asyncio
import logging

import uvicorn

from mindloom import app

logger = logging.getLogger(__name__)


async def main():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
