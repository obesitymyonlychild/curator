"""Base agent class that all agents inherit from."""
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from .config import CuratorConfig, AgentConfig
from .db import Deal, RawItem, upsert_deal, create_run_log, update_run_log


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    agent_id: str = ""
    source: str = ""

    def __init__(self, config: CuratorConfig):
        """Initialize agent with config."""
        self.config = config
        self.agent_config = self._get_agent_config()

    def _get_agent_config(self) -> AgentConfig:
        """Get this agent's config from the global config."""
        for agent in self.config.agents:
            if agent.id == self.agent_id:
                return agent
        raise ValueError(f"Agent {self.agent_id} not found in config")

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Fetch raw items from the external source.

        Returns:
            List of RawItem objects with external_id, name, and raw data.
        """
        pass

    @abstractmethod
    def to_deal(self, item: RawItem) -> Optional[Deal]:
        """Convert a raw item to a Deal.

        Args:
            item: The raw item from fetch()

        Returns:
            Deal object if the item should be saved, None to skip.
        """
        pass

    def is_watchlist_hit(self, item: RawItem) -> bool:
        """Check if an item matches the watchlist."""
        for watch_item in self.config.watchlist:
            # Check if source matches
            if watch_item.source != self.source:
                continue

            # Check by app_id if provided
            if watch_item.app_id and watch_item.app_id == item.external_id:
                return True

            # Check by name (case-insensitive partial match)
            if watch_item.name.lower() in item.name.lower():
                return True

        return False

    def passes_filters(self, deal: Deal) -> bool:
        """Check if a deal passes the configured filters.

        Watchlist hits always pass filters.
        """
        if deal.watchlist_hit:
            return True

        # Get effective min_discount (agent > global)
        min_discount = self.agent_config.filters.min_discount or self.config.global_min_discount
        if deal.discount_pct < min_discount:
            return False

        # Get effective min_rating (agent > global)
        min_rating = self.agent_config.filters.min_rating or self.config.global_min_rating
        if deal.rating is not None and deal.rating < min_rating:
            return False

        # Check genres (empty list = accept all)
        if self.agent_config.filters.genres:
            if deal.genre not in self.agent_config.filters.genres:
                return False

        # Check Mac filter
        if self.agent_config.filters.mac_only and not deal.mac:
            return False

        return True

    def run(self) -> dict:
        """Run the agent: fetch, filter, and save deals.

        Returns:
            Dictionary with run summary.
        """
        log_id = create_run_log(self.agent_id)

        try:
            # Fetch raw items
            items = self.fetch()

            # Process each item
            deals_saved = 0
            for item in items:
                # Check watchlist
                is_watchlist = self.is_watchlist_hit(item)

                # Convert to deal
                deal = self.to_deal(item)
                if deal is None:
                    continue

                # Mark watchlist hits
                if is_watchlist:
                    deal.watchlist_hit = True

                # Apply filters
                if not self.passes_filters(deal):
                    continue

                # Save to DB
                upsert_deal(deal)
                deals_saved += 1

            # Update log
            update_run_log(log_id, status="success", deals_found=deals_saved)

            return {
                "agent_id": self.agent_id,
                "status": "success",
                "deals_found": deals_saved,
                "items_fetched": len(items),
            }

        except Exception as e:
            # Log error
            error_msg = str(e)
            update_run_log(log_id, status="error", error_msg=error_msg)

            return {
                "agent_id": self.agent_id,
                "status": "error",
                "error": error_msg,
                "deals_found": 0,
            }
