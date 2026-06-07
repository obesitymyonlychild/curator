# Curator — Claude Code context

## What this is
A personal deal & discovery agent platform. Lightweight agents poll external APIs (Steam, etc.),
filter results by user preferences, persist to SQLite, and send notifications via Telegram or email.
The system is designed to be cost-efficient: most logic is deterministic code; Claude Haiku is
called only for ambiguous genre classification (~$1–3/month total).

---

## Architecture

```
curator/
├── agents/
│   └── steam_agent.py       # Steam deals: Mac-only, discount %, rating, genre
├── core/
│   ├── base_agent.py        # Abstract base — all agents subclass this
│   ├── config.py            # Config dataclasses + load/save (config.json)
│   ├── db.py                # SQLite: deals table + run_log table
│   ├── notifier.py          # Telegram + email dispatch
│   └── orchestrator.py      # Runs all enabled agents; entry point for cron
├── api/
│   └── main.py              # FastAPI server — dashboard backend
├── .github/workflows/
│   └── curator.yml          # GitHub Actions: runs every 6h for free
├── config.json              # Runtime config (auto-created on first run)
├── curator.db               # SQLite DB (auto-created on first run)
└── requirements.txt
```

---

## Key concepts

### BaseAgent contract
Every agent must implement exactly two methods:

```python
def fetch(self) -> list[RawItem]:
    # Pull raw data from source API. Return RawItem list.

def to_deal(self, item: RawItem) -> Deal | None:
    # Convert one RawItem to a Deal. Return None to skip.
```

The base class handles everything else: filter evaluation, watchlist matching,
DB persistence, and run logging. Adding a new agent = new file + two methods.

### Filter chain (base_agent.py → passes_filters)
1. `min_discount` — agent-level filter vs global floor, whichever is higher
2. `min_rating` — same pattern
3. `genres` — allowlist; empty list = accept all
4. Watchlist hits bypass filters and are always saved

### Config (config.json)
- `agents[]` — per-agent: `enabled`, `schedule`, `filters`
- `watchlist[]` — cross-agent watch items with optional `app_id`
- `notifications` — Telegram + email toggles and credentials
- `global_min_discount`, `global_min_rating` — floors applied across all agents

### DB schema
- `deals` — one row per (agent_id, external_id, date). Idempotent upserts; no duplicates.
- `run_log` — one row per agent run with start/end time, deals_found, status, error_msg.

---

## Run commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all enabled agents once (creates config.json + curator.db on first run)
python -m curator.core.orchestrator

# Start API server for dashboard (http://localhost:8000)
uvicorn curator.api.main:app --reload

# API docs (auto-generated)
open http://localhost:8000/docs

# Run a specific agent only
python -c "
from curator.core.config import load_config
from curator.core.orchestrator import run_all
print(run_all(['steam']))
"
```

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Optional | Haiku genre classification fallback |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram notifications |
| `TELEGRAM_CHAT_ID` | Optional | Your Telegram chat ID |
| `SMTP_HOST` | Optional | Email digest (default: smtp.gmail.com) |
| `SMTP_USER` | Optional | Gmail address |
| `SMTP_PASS` | Optional | Gmail app password |
| `CURATOR_CONFIG` | Optional | Path to config.json (default: ./config.json) |
| `CURATOR_DB` | Optional | Path to curator.db (default: ./curator.db) |

---

## How to add a new agent

1. Create `curator/agents/my_agent.py`:

```python
from curator.core.base_agent import BaseAgent, RawItem
from curator.core.db import Deal
from curator.core.config import AgentConfig, CuratorConfig
from datetime import datetime

class MyAgent(BaseAgent):
    agent_id = "my_agent"
    source   = "my_source"

    def fetch(self) -> list[RawItem]:
        # call your API, return RawItem list
        ...

    def to_deal(self, item: RawItem) -> Deal | None:
        # map to Deal dataclass or return None to skip
        return Deal(
            id=None,
            agent_id=self.agent_id,
            source=self.source,
            external_id=item.external_id,
            name=item.name,
            icon="📦",
            discount_pct=0,
            original_price=0.0,
            sale_price=0.0,
            rating=None,
            genre="Other",
            mac=False,
            watchlist_hit=False,
            raw=item.data,
            found_at=datetime.utcnow().strftime("%Y-%m-%d"),
        )
```

2. Register in `curator/core/orchestrator.py` registry dict:

```python
registry = {
    "steam":    SteamAgent,
    "my_agent": MyAgent,    # ← add here
}
```

3. Add an entry to `config.json` under `"agents"`:

```json
{ "id": "my_agent", "enabled": true, "schedule": "every_6h", "filters": {} }
```

---

## API endpoints (api/main.py)

| Method | Path | Description |
|---|---|---|
| GET | `/config` | Full config |
| PATCH | `/config/agents/{id}` | Update agent (enabled, schedule, filters) |
| PATCH | `/config/settings` | Update global settings + notifications |
| GET | `/watchlist` | List watchlist items |
| POST | `/watchlist` | Add item `{name, source, app_id?}` |
| DELETE | `/watchlist/{id}` | Remove item |
| GET | `/feed` | Recent deals (params: agent_id, watchlist_only, limit) |
| GET | `/feed/stats` | Summary counts for dashboard |
| GET | `/runs` | Run history |
| POST | `/run` | Trigger manual run (param: agent_id?) |

---

## Cost model

| Component | Cost |
|---|---|
| Steam API calls | Free |
| GitHub Actions cron (every 6h) | Free (<2000 min/month) |
| SQLite DB | Free |
| Telegram notifications | Free |
| Claude Haiku 4.5 (genre fallback only) | ~$1–3/month |
| **Total** | **~$1–3/month** |

Genre classification uses Haiku only when Steam's own tags don't match the known genre list.
In practice, >90% of games resolve without an API call. With prompt caching, the Haiku cost
drops another 90%.