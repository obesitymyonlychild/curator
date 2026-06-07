"""Concert tracking agent using Spotify + Bandsintown."""
import os
import requests
from typing import Optional
from datetime import datetime

from curator.core.base_agent import BaseAgent, RawItem
from curator.core.db import Deal
from curator.core.config import CuratorConfig
from curator.core.spotify_auth import get_followed_artists


class ConcertAgent(BaseAgent):
    """Agent for tracking concerts of Spotify-followed artists."""

    agent_id = "concert"
    source = "bandsintown"

    def __init__(self, config: CuratorConfig):
        super().__init__(config)
        self.location = self.agent_config.filters.genres[0] if self.agent_config.filters.genres else "San Francisco, CA"
        self.radius = 50  # miles

    def fetch(self) -> list[RawItem]:
        """Fetch concerts for followed Spotify artists.

        Returns:
            List of RawItem objects representing concerts
        """
        items = []

        # Get followed artists from Spotify
        print("Fetching followed artists from Spotify...")
        artists = get_followed_artists()

        if not artists:
            print("No artists found. Make sure Spotify credentials are configured.")
            return items

        print(f"Checking concerts for {len(artists)} artists...")

        # Check Bandsintown for each artist
        for artist in artists:
            try:
                concerts = self._get_artist_concerts(artist['name'])
                for concert in concerts:
                    items.append(
                        RawItem(
                            external_id=concert['id'],
                            name=f"{artist['name']} - {concert['venue']['name']}",
                            data={
                                'artist': artist,
                                'concert': concert
                            }
                        )
                    )
            except Exception as e:
                print(f"Error fetching concerts for {artist['name']}: {e}")
                continue

        print(f"Found {len(items)} upcoming concerts")
        return items

    def _get_artist_concerts(self, artist_name: str) -> list[dict]:
        """Get concerts for a specific artist from Bandsintown.

        Args:
            artist_name: Name of the artist

        Returns:
            List of concert dicts
        """
        # Bandsintown API
        app_id = os.getenv("BANDSINTOWN_APP_ID", "curator")

        try:
            # Search for artist events
            url = f"https://rest.bandsintown.com/artists/{requests.utils.quote(artist_name)}/events"
            params = {
                "app_id": app_id,
                "date": "upcoming"
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 404:
                # Artist not found, that's ok
                return []

            response.raise_for_status()
            events = response.json()

            # Filter by location if specified
            if self.location and self.location != "worldwide":
                filtered_events = []
                for event in events:
                    venue = event.get('venue', {})
                    location_str = f"{venue.get('city', '')}, {venue.get('region', '')}, {venue.get('country', '')}"

                    # Simple location matching
                    if self.location.lower() in location_str.lower():
                        filtered_events.append(event)

                return filtered_events

            return events if isinstance(events, list) else []

        except Exception as e:
            print(f"Bandsintown API error for {artist_name}: {e}")
            return []

    def to_deal(self, item: RawItem) -> Optional[Deal]:
        """Convert a concert to a Deal.

        Args:
            item: Raw item from fetch()

        Returns:
            Deal object or None to skip
        """
        artist = item.data['artist']
        concert = item.data['concert']
        venue = concert.get('venue', {})

        # Parse date
        datetime_str = concert.get('datetime', '')
        try:
            event_date = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            date_display = event_date.strftime("%Y-%m-%d")
        except:
            date_display = datetime_str[:10] if datetime_str else "TBA"

        # Location
        location = f"{venue.get('city', 'Unknown')}, {venue.get('region', '')}"
        if venue.get('country'):
            location += f", {venue['country']}"

        # Ticket info
        offers = concert.get('offers', [])
        ticket_url = offers[0].get('url') if offers else concert.get('url', '')
        ticket_status = offers[0].get('status') if offers else 'available'

        return Deal(
            id=None,
            agent_id=self.agent_id,
            source=self.source,
            external_id=concert['id'],
            name=f"{artist['name']} at {venue.get('name', 'TBA')}",
            icon="🎵",
            discount_pct=0,  # Not applicable for concerts
            original_price=0.0,  # Could parse from offers if available
            sale_price=0.0,
            rating=artist.get('popularity', 0) / 10.0,  # Spotify popularity as rating
            genre=artist.get('genres', ['Unknown'])[0] if artist.get('genres') else 'Unknown',
            mac=False,  # Not applicable
            watchlist_hit=False,  # Will be set by base agent
            raw={
                'artist': artist['name'],
                'venue': venue.get('name', 'TBA'),
                'location': location,
                'date': date_display,
                'datetime': datetime_str,
                'ticket_url': ticket_url,
                'ticket_status': ticket_status,
                'lineup': concert.get('lineup', []),
            },
            found_at=datetime.utcnow().strftime("%Y-%m-%d"),
        )
