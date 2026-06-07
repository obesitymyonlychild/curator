"""FastAPI server for Curator dashboard."""
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from curator.core.config import load_config, save_config, AgentFilters, WatchlistItem
from curator.core.db import get_deals, get_run_logs, get_feed_stats, init_db
from curator.core.orchestrator import run_all


app = FastAPI(title="Curator API", version="1.0.0")


# Initialize DB on startup
@app.on_event("startup")
async def startup_event():
    init_db()


# Request/Response models
class UpdateAgentRequest(BaseModel):
    enabled: Optional[bool] = None
    schedule: Optional[str] = None
    filters: Optional[AgentFilters] = None


class UpdateSettingsRequest(BaseModel):
    global_min_discount: Optional[int] = None
    global_min_rating: Optional[float] = None
    telegram_enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    email_to: Optional[str] = None


class AddWatchlistRequest(BaseModel):
    name: str
    source: str = "steam"
    app_id: Optional[str] = None


class RunAgentRequest(BaseModel):
    agent_id: Optional[str] = None


# Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Curator API", "version": "1.0.0"}


@app.get("/config")
async def get_config():
    """Get full configuration."""
    config = load_config()
    return config.to_dict()


@app.patch("/config/agents/{agent_id}")
async def update_agent(agent_id: str, request: UpdateAgentRequest):
    """Update agent configuration."""
    config = load_config()

    # Find agent
    agent = None
    for a in config.agents:
        if a.id == agent_id:
            agent = a
            break

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Update fields
    if request.enabled is not None:
        agent.enabled = request.enabled
    if request.schedule is not None:
        agent.schedule = request.schedule
    if request.filters is not None:
        agent.filters = request.filters

    save_config(config)
    return {"status": "success", "agent": agent_id}


@app.patch("/config/settings")
async def update_settings(request: UpdateSettingsRequest):
    """Update global settings and notifications."""
    config = load_config()

    # Update global settings
    if request.global_min_discount is not None:
        config.global_min_discount = request.global_min_discount
    if request.global_min_rating is not None:
        config.global_min_rating = request.global_min_rating

    # Update notification settings
    if request.telegram_enabled is not None:
        config.notifications.telegram_enabled = request.telegram_enabled
    if request.telegram_bot_token is not None:
        config.notifications.telegram_bot_token = request.telegram_bot_token
    if request.telegram_chat_id is not None:
        config.notifications.telegram_chat_id = request.telegram_chat_id
    if request.email_enabled is not None:
        config.notifications.email_enabled = request.email_enabled
    if request.smtp_host is not None:
        config.notifications.smtp_host = request.smtp_host
    if request.smtp_port is not None:
        config.notifications.smtp_port = request.smtp_port
    if request.smtp_user is not None:
        config.notifications.smtp_user = request.smtp_user
    if request.smtp_pass is not None:
        config.notifications.smtp_pass = request.smtp_pass
    if request.email_to is not None:
        config.notifications.email_to = request.email_to

    save_config(config)
    return {"status": "success"}


@app.get("/watchlist")
async def get_watchlist():
    """Get watchlist items."""
    config = load_config()
    return {"watchlist": [w.__dict__ for w in config.watchlist]}


@app.post("/watchlist")
async def add_watchlist(request: AddWatchlistRequest):
    """Add item to watchlist."""
    config = load_config()

    # Generate new ID
    next_id = max([w.id for w in config.watchlist], default=0) + 1

    # Create item
    item = WatchlistItem(
        id=next_id,
        name=request.name,
        source=request.source,
        app_id=request.app_id,
    )

    config.watchlist.append(item)
    save_config(config)

    return {"status": "success", "item": item.__dict__}


@app.delete("/watchlist/{item_id}")
async def remove_watchlist(item_id: int):
    """Remove item from watchlist."""
    config = load_config()

    # Find and remove item
    item = None
    for i, w in enumerate(config.watchlist):
        if w.id == item_id:
            item = config.watchlist.pop(i)
            break

    if not item:
        raise HTTPException(status_code=404, detail=f"Watchlist item {item_id} not found")

    save_config(config)
    return {"status": "success", "removed": item.__dict__}


@app.get("/feed")
async def get_feed(
    agent_id: Optional[str] = None,
    watchlist_only: bool = False,
    limit: int = 50,
):
    """Get recent deals feed."""
    deals = get_deals(agent_id=agent_id, watchlist_only=watchlist_only, limit=limit)
    return {"deals": [d.__dict__ for d in deals], "count": len(deals)}


@app.get("/feed/stats")
async def get_stats():
    """Get feed statistics."""
    stats = get_feed_stats()
    return stats


@app.get("/runs")
async def get_runs(agent_id: Optional[str] = None, limit: int = 20):
    """Get run history."""
    logs = get_run_logs(agent_id=agent_id, limit=limit)
    return {"runs": [log.__dict__ for log in logs], "count": len(logs)}


@app.post("/run")
async def trigger_run(request: RunAgentRequest):
    """Trigger a manual agent run."""
    agent_ids = [request.agent_id] if request.agent_id else None
    result = run_all(agent_ids)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
