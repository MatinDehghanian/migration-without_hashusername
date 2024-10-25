import logging
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from utils.log import logger
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)

from jobs import stop_scheduler, start_scheduler
from routers import subscription
from fastapi_responses import custom_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException
from utils.config import (
    UVICORN_HOST,
    UVICORN_PORT,
    UVICORN_UDS,
    UVICORN_SSL_CERTFILE,
    UVICORN_SSL_KEYFILE,
    DOCS,
)

__version__ = "0.1.0"


async def create_app() -> FastAPI:

    app = FastAPI(
        title="Migration",
        description="API to proxy subscription requests between users and backend system",
        version=__version__,
        docs_url="/docs" if DOCS else None,
        redoc_url="/redoc" if DOCS else None,
    )

    app.openapi = custom_openapi(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request, exc):
        logger.error(f"An HTTP error!: {repr(exc)}")
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        logger.error(f"The client sent invalid data!: {exc}")
        return await request_validation_exception_handler(request, exc)

    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name

    # Include the router
    app.include_router(subscription.router)

    return app


async def setup_event_handlers(app: FastAPI):
    """Set up event handlers for the application."""

    @app.on_event("startup")
    async def on_startup():
        await start_scheduler()
        logger.info("Application started successfully.")

    @app.on_event("shutdown")
    async def on_shutdown():
        await stop_scheduler()
        logger.info("Application shut down successfully.")


async def main():
    """Main function to run the application."""
    app = await create_app()
    await setup_event_handlers(app)

    config = uvicorn.Config(
        app,
        host=UVICORN_HOST,
        port=UVICORN_PORT,
        uds=UVICORN_UDS,
        ssl_certfile=UVICORN_SSL_CERTFILE,
        ssl_keyfile=UVICORN_SSL_KEYFILE,
        workers=1,
        log_level=logging.INFO,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
