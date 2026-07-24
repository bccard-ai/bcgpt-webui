import traceback
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from bcgpt.config import ENV


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Returns structured JSON with a request_id for correlation.
    In development mode, includes the error detail for debugging.
    In production, returns a generic message to avoid leaking internals.
    """
    request_id = str(uuid4())
    logger.error(
        "Unhandled exception (request_id={}): {}",
        request_id,
        str(exc),
    )
    logger.error(traceback.format_exc())

    detail = "Internal Server Error"
    if ENV == "dev":
        detail = f"{detail}: {str(exc)}"

    return JSONResponse(
        status_code=500,
        content={"detail": detail, "request_id": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for request validation errors (Pydantic/FastAPI validation).

    Always returns validation error details since they are user-input errors,
    not internal server information.
    """
    request_id = str(uuid4())
    logger.warning(
        "Validation error (request_id={}): {}",
        request_id,
        exc.errors(),
    )

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "request_id": request_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handler for Starlette HTTPException (includes FastAPI HTTPException).

    Returns the exception detail with a request_id for correlation.
    """
    request_id = str(uuid4())
    logger.warning(
        "HTTP exception {} (request_id={}): {}",
        exc.status_code,
        request_id,
        exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
    )
