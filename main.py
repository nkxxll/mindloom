import asyncio

import uvicorn

from mindloom import app


async def main():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
    server = uvicorn.Server(config)
    await server.serve()  # this blocks


if __name__ == "__main__":
    asyncio.run(main())
