"""FastAPI entry point. Arena, trace and leaderboard endpoints are added in Step 5."""

from fastapi import FastAPI

app = FastAPI(title="AgentGuard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
