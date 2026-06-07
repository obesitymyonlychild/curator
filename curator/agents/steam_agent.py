"""Steam deals agent."""
import os
import requests
from typing import Optional
from datetime import datetime

from curator.core.base_agent import BaseAgent, RawItem
from curator.core.db import Deal
from curator.core.config import CuratorConfig


class SteamAgent(BaseAgent):
    """Agent for fetching Steam deals."""

    agent_id = "steam"
    source = "steam"

    # Known genre mappings from Steam tags
    GENRE_MAP = {
        "Action": "Action",
        "Adventure": "Adventure",
        "RPG": "RPG",
        "Strategy": "Strategy",
        "Simulation": "Simulation",
        "Indie": "Indie",
        "Puzzle": "Puzzle",
        "Horror": "Horror",
        "Platformer": "Platformer",
        "Racing": "Racing",
        "Sports": "Sports",
        "Fighting": "Fighting",
        "Shooter": "Shooter",
        "Open World": "Adventure",
        "Survival": "Survival",
        "Roguelike": "Roguelike",
        "Turn-Based": "Strategy",
        "Real-Time Strategy": "Strategy",
        "Tactical": "Strategy",
    }

    def fetch(self) -> list[RawItem]:
        """Fetch deals from Steam API.

        Uses the Steam Store API to get featured deals and specials.
        """
        items = []

        try:
            # Fetch featured deals
            response = requests.get(
                "https://store.steampowered.com/api/featured/",
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Process featured items
            if "featured_win" in data:
                for game in data["featured_win"]:
                    if game.get("discount_percent", 0) > 0:
                        items.append(
                            RawItem(
                                external_id=str(game["id"]),
                                name=game["name"],
                                data=game,
                            )
                        )

            # Process daily deals
            if "daily_deals" in data:
                for game in data["daily_deals"]:
                    if game.get("discount_percent", 0) > 0:
                        items.append(
                            RawItem(
                                external_id=str(game["id"]),
                                name=game["name"],
                                data=game,
                            )
                        )

            # Fetch specials page (more deals)
            specials_response = requests.get(
                "https://store.steampowered.com/api/featuredcategories/",
                timeout=30,
            )
            specials_response.raise_for_status()
            specials_data = specials_response.json()

            if "specials" in specials_data:
                for game in specials_data["specials"]["items"][:50]:  # Limit to 50
                    if game.get("discount_percent", 0) > 0:
                        items.append(
                            RawItem(
                                external_id=str(game["id"]),
                                name=game["name"],
                                data=game,
                            )
                        )

        except Exception as e:
            print(f"Error fetching Steam data: {e}")

        return items

    def _get_game_details(self, app_id: str) -> Optional[dict]:
        """Fetch detailed game info from Steam API.

        Args:
            app_id: Steam app ID

        Returns:
            Game details dict or None if failed
        """
        try:
            response = requests.get(
                f"https://store.steampowered.com/api/appdetails?appids={app_id}",
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if app_id in data and data[app_id]["success"]:
                return data[app_id]["data"]

        except Exception as e:
            print(f"Error fetching game details for {app_id}: {e}")

        return None

    def _classify_genre(self, tags: list[str]) -> str:
        """Classify game genre from Steam tags.

        Uses known genre mappings first, falls back to Claude Haiku if needed.

        Args:
            tags: List of Steam genre/category tags

        Returns:
            Genre string
        """
        # Try known mappings first
        for tag in tags:
            if tag in self.GENRE_MAP:
                return self.GENRE_MAP[tag]

        # Fall back to Claude Haiku for ambiguous cases
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

                prompt = f"Classify this game into ONE genre category based on these tags: {', '.join(tags[:10])}\n\n"
                prompt += "Choose from: Action, Adventure, RPG, Strategy, Simulation, Indie, Puzzle, Horror, Platformer, Racing, Sports, Fighting, Shooter, Survival, Roguelike, Other\n\n"
                prompt += "Return ONLY the genre name, nothing else."

                message = client.messages.create(
                    model="claude-haiku-4.5",
                    max_tokens=10,
                    messages=[{"role": "user", "content": prompt}],
                )

                genre = message.content[0].text.strip()
                return genre if genre else "Other"

            except Exception as e:
                print(f"Genre classification failed: {e}")

        # Default fallback
        return "Other"

    def to_deal(self, item: RawItem) -> Optional[Deal]:
        """Convert a Steam game to a Deal.

        Args:
            item: Raw item from fetch()

        Returns:
            Deal object or None to skip
        """
        game = item.data
        app_id = item.external_id

        # Get detailed info
        details = self._get_game_details(app_id)
        if not details:
            # Use basic info from featured data
            discount_pct = game.get("discount_percent", 0)
            original_price = game.get("original_price", 0) / 100.0
            sale_price = game.get("final_price", 0) / 100.0
            mac_support = game.get("platforms", {}).get("mac", False)
            rating = None
            genre = "Other"
        else:
            # Use detailed info
            discount_pct = game.get("discount_percent", 0)
            original_price = details.get("price_overview", {}).get("initial", 0) / 100.0
            sale_price = details.get("price_overview", {}).get("final", 0) / 100.0
            mac_support = details.get("platforms", {}).get("mac", False)

            # Get rating from metacritic or Steam reviews
            rating = None
            if "metacritic" in details and "score" in details["metacritic"]:
                rating = details["metacritic"]["score"] / 10.0

            # Get genre
            genres = details.get("genres", [])
            tags = [g["description"] for g in genres]
            if not tags:
                tags = details.get("categories", [])
                tags = [c["description"] for c in tags]

            genre = self._classify_genre(tags) if tags else "Other"

        # Skip free games or games with no discount
        if discount_pct == 0 or original_price == 0:
            return None

        return Deal(
            id=None,
            agent_id=self.agent_id,
            source=self.source,
            external_id=app_id,
            name=item.name,
            icon="🎮",
            discount_pct=discount_pct,
            original_price=original_price,
            sale_price=sale_price,
            rating=rating,
            genre=genre,
            mac=mac_support,
            watchlist_hit=False,
            raw=game,
            found_at=datetime.utcnow().strftime("%Y-%m-%d"),
        )
