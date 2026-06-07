"""Configuration management for Curator."""
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class AgentFilters:
    """Filters specific to an agent."""
    min_discount: Optional[int] = None
    min_rating: Optional[float] = None
    genres: list[str] = field(default_factory=list)
    mac_only: bool = False


@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    id: str
    enabled: bool = True
    schedule: str = "every_6h"
    filters: AgentFilters = field(default_factory=AgentFilters)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        filters = data.get("filters", {})
        if isinstance(filters, dict):
            filters = AgentFilters(**filters)
        return cls(
            id=data["id"],
            enabled=data.get("enabled", True),
            schedule=data.get("schedule", "every_6h"),
            filters=filters,
        )


@dataclass
class WatchlistItem:
    """A watchlist item that bypasses filters."""
    id: int
    name: str
    source: str = "steam"
    app_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "WatchlistItem":
        return cls(**data)


@dataclass
class NotificationConfig:
    """Notification settings."""
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    email_to: Optional[str] = None


@dataclass
class CuratorConfig:
    """Main configuration for Curator."""
    agents: list[AgentConfig] = field(default_factory=list)
    watchlist: list[WatchlistItem] = field(default_factory=list)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    global_min_discount: int = 0
    global_min_rating: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "CuratorConfig":
        agents = [AgentConfig.from_dict(a) for a in data.get("agents", [])]
        watchlist = [WatchlistItem.from_dict(w) for w in data.get("watchlist", [])]
        notifications = NotificationConfig(**data.get("notifications", {}))
        return cls(
            agents=agents,
            watchlist=watchlist,
            notifications=notifications,
            global_min_discount=data.get("global_min_discount", 0),
            global_min_rating=data.get("global_min_rating", 0.0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "agents": [
                {
                    "id": a.id,
                    "enabled": a.enabled,
                    "schedule": a.schedule,
                    "filters": asdict(a.filters),
                }
                for a in self.agents
            ],
            "watchlist": [asdict(w) for w in self.watchlist],
            "notifications": asdict(self.notifications),
            "global_min_discount": self.global_min_discount,
            "global_min_rating": self.global_min_rating,
        }


def get_config_path() -> str:
    """Get the config file path from env or default."""
    return os.getenv("CURATOR_CONFIG", "./config.json")


def load_config() -> CuratorConfig:
    """Load config from JSON file or create default."""
    config_path = get_config_path()

    if not os.path.exists(config_path):
        # Create default config
        config = CuratorConfig(
            agents=[
                AgentConfig(
                    id="steam",
                    enabled=True,
                    schedule="every_24h",
                    filters=AgentFilters(min_discount=10, min_rating=9.2, mac_only=True),
                ),
                AgentConfig(
                    id="concert",
                    enabled=False,  # Disabled by default until Spotify credentials are added
                    schedule="every_24h",
                    filters=AgentFilters(genres=["San Francisco, CA"]),  # Default location in genres field
                )
            ],
            watchlist=[],
            notifications=NotificationConfig(),
            global_min_discount=20,
            global_min_rating=6.0,
        )
        save_config(config)
        return config

    with open(config_path, "r") as f:
        data = json.load(f)

    return CuratorConfig.from_dict(data)


def save_config(config: CuratorConfig) -> None:
    """Save config to JSON file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)
