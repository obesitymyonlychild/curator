"""Steam deals agent."""
import os
import requests
import time
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
                for game in specials_data["specials"]["items"]:  # Get all specials
                    if game.get("discount_percent", 0) > 0:
                        items.append(
                            RawItem(
                                external_id=str(game["id"]),
                                name=game["name"],
                                data=game,
                            )
                        )

            # Fetch top sellers on sale
            if "top_sellers" in specials_data:
                for game in specials_data["top_sellers"]["items"]:
                    if game.get("discount_percent", 0) > 0:
                        items.append(
                            RawItem(
                                external_id=str(game["id"]),
                                name=game["name"],
                                data=game,
                            )
                        )

            # Fetch new releases on sale
            if "new_releases" in specials_data:
                for game in specials_data["new_releases"]["items"]:
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

        # Deduplicate by app ID
        seen = set()
        unique_items = []
        for item in items:
            if item.external_id not in seen:
                seen.add(item.external_id)
                unique_items.append(item)

        print(f"Found {len(unique_items)} unique games on sale (from {len(items)} total)")
        return unique_items

    def _get_game_details(self, app_id: str, retries: int = 3) -> Optional[dict]:
        """Fetch detailed game info from Steam API with retry logic.

        Args:
            app_id: Steam app ID
            retries: Number of retry attempts

        Returns:
            Game details dict or None if failed
        """
        for attempt in range(retries):
            try:
                # Add small delay to avoid rate limiting
                if attempt > 0:
                    time.sleep(0.5 * attempt)  # Exponential backoff: 0.5s, 1s, 1.5s

                response = requests.get(
                    f"https://store.steampowered.com/api/appdetails?appids={app_id}",
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                if app_id in data and data[app_id]["success"]:
                    return data[app_id]["data"]
                elif app_id in data and not data[app_id]["success"]:
                    # Game not found or unavailable, no point retrying
                    return None

            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    print(f"Timeout fetching details for {app_id}, retrying... (attempt {attempt + 1}/{retries})")
                    continue
            except Exception as e:
                if attempt < retries - 1:
                    print(f"Error fetching game details for {app_id}: {e}, retrying...")
                    continue
                else:
                    print(f"Failed to fetch game details for {app_id} after {retries} attempts: {e}")

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

        # Small delay to avoid rate limiting (100ms between games)
        time.sleep(0.1)

        # Get detailed info with retries
        details = self._get_game_details(app_id)

        # Extract platform support - try both sources
        mac_support = False

        if details:
            # Prefer detailed API data
            mac_support = details.get("platforms", {}).get("mac", False)
            discount_pct = game.get("discount_percent", 0)
            original_price = details.get("price_overview", {}).get("initial", 0) / 100.0
            sale_price = details.get("price_overview", {}).get("final", 0) / 100.0

            # Get rating from metacritic or Steam reviews
            rating = None
            if "metacritic" in details and "score" in details["metacritic"]:
                rating = details["metacritic"]["score"] / 10.0
            elif "recommendations" in details and "total" in details["recommendations"]:
                # Use Steam review score as fallback
                # Convert recommendations to approximate rating (rough estimate)
                total_reviews = details["recommendations"]["total"]
                if total_reviews > 100:  # Only trust games with enough reviews
                    # Steam doesn't provide exact positive/negative split in appdetails
                    # We'll parse from the featured data if available
                    pass

            # Get genre
            genres = details.get("genres", [])
            tags = [g["description"] for g in genres]
            if not tags:
                tags = details.get("categories", [])
                tags = [c["description"] for c in tags]

            genre = self._classify_genre(tags) if tags else "Other"
        else:
            # Fallback to basic info from featured data
            discount_pct = game.get("discount_percent", 0)
            original_price = game.get("original_price", 0) / 100.0
            sale_price = game.get("final_price", 0) / 100.0

            # Try to get platform from featured data
            # Featured API sometimes includes platform in different formats
            if "platforms" in game:
                platforms = game["platforms"]
                if isinstance(platforms, dict):
                    mac_support = platforms.get("mac", False)
                elif isinstance(platforms, str):
                    # Sometimes it's a string like "windows,mac,linux"
                    mac_support = "mac" in platforms.lower()

            rating = None
            genre = "Other"

            # Log when we couldn't get detailed info
            print(f"No detailed info for {item.name} ({app_id}), using featured data only")

        # Log platform detection for debugging
        platform_source = "detailed API" if details else "featured data"
        print(f"{item.name}: Mac={mac_support} (from {platform_source})")

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
