"""FastAPI delivery layer."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.config import Settings, get_settings
from app.container import build_copilot
from app.domain.models import ChatRequest, ChatResponse, PublicChatRequest
from app.exceptions import CopilotError
from app.observability import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    copilot = build_copilot(active_settings)
    app = FastAPI(
        title="Driver Retention Copilot",
        version=__version__,
        description="Evidence-grounded Strategist/Critic workflow. Recommendations are not execution.",
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-process-time-ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
        return response

    @app.exception_handler(CopilotError)
    async def handle_copilot_error(_: Request, exc: CopilotError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/chat", response_model=ChatResponse)
    def chat(payload: PublicChatRequest) -> ChatResponse:
        try:
            return copilot.run(ChatRequest.model_validate(payload.model_dump()))
        except CopilotError:
            raise
        except Exception as exc:  # Unexpected internals are not exposed to clients.
            raise HTTPException(status_code=500, detail="Internal copilot failure") from exc

    return app
