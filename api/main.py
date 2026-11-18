"""FastAPI app: health, trace viewer data, and (added in the next part) the arena and leaderboard.

The static pages in web/ are served from the same process, so the whole demo is one container.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from agentguard.tracing.store import DEFAULT_PATH, TraceStore

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(trace_store: TraceStore | None = None) -> FastAPI:
    app = FastAPI(title="AgentGuard")
    traces = trace_store or TraceStore(DEFAULT_PATH)
    app.state.traces = traces

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

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
