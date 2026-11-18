"""FastAPI app: health, arena, leaderboard and trace viewer data.

The static pages in web/ are served from the same process, so the whole demo is one container.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentguard.arena import MAX_TEXT_CHARS, Arena, ArenaError
from agentguard.config import load_env
from agentguard.llm.budget import DailyBudgetExhausted
from agentguard.tracing.store import DEFAULT_PATH, TraceStore

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class AttemptIn(BaseModel):
    nickname: str = Field(default="anonymous", max_length=40)
    level: int
    goal: str = Field(max_length=20)
    channel: str = Field(max_length=20)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS * 2)


def create_app(trace_store: TraceStore | None = None, arena: Arena | None = None) -> FastAPI:
    load_env()
    app = FastAPI(title="AgentGuard")
    traces = trace_store or TraceStore(DEFAULT_PATH)
    arena = arena or Arena.from_env(traces)
    app.state.traces, app.state.arena = traces, arena

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/traces")
    def recent_traces() -> list[dict]:
        return traces.recent()

    @app.get("/api/trace/{trace_id}")
    def get_trace(trace_id: str) -> dict:
        trace = traces.get(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return trace

    @app.get("/api/arena/options")
    def arena_options() -> dict:
        return arena.options()

    @app.post("/api/arena/attempt")
    def arena_attempt(body: AttemptIn, request: Request) -> JSONResponse:
        client = request.client.host if request.client else "unknown"
        try:
            result = arena.attempt(
                body.nickname, body.level, body.goal, body.channel, body.text, client
            )
        except ArenaError as exc:
            return JSONResponse({"error": str(exc)}, status_code=exc.status)
        except DailyBudgetExhausted:
            return JSONResponse(
                {"error": "The model's free daily allowance is used up. Try after 00:00 UTC."},
                status_code=503,
            )
        return JSONResponse(result)

    @app.get("/api/leaderboard")
    def leaderboard() -> dict:
        return arena.leaderboard()

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
