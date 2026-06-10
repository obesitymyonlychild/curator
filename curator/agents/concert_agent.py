"""Concert tracking agent using Spotify + Ticketmaster."""
import os
import requests
import time
from typing import Optional
from datetime import datetime

from curator.core.base_agent import BaseAgent, RawItem
from curator.core.db import Deal
from curator.core.config import CuratorConfig
from curator.core.spotify_auth import get_followed_artists


class ConcertAgent(BaseAgent):
    """Agent for tracking concerts of Spotify-followed artists."""

    agent_id = "concert"
    source = "ticketmaster"

    def __init__(self, config: CuratorConfig):
        super().__init__(config)
        self.locations = self.agent_config.filters.genres if self.agent_config.filters.genres else ["San Francisco, CA"]
        self.api_key = os.getenv("TICKETMASTER_API_KEY")

    def passes_filters(self, deal):
        """Override base filter to skip genre check.

        For concerts, we use the genres field for location filtering
        (already done in fetch()), so we skip the genre check here.
        """
        if deal.watchlist_hit:
            return True

        # Check min_discount (should be 0 for concerts)
        if self.agent_config.filters.min_discount is not None:
            min_discount = self.agent_config.filters.min_discount
        else:
            min_discount = self.config.global_min_discount

        if deal.discount_pct < min_discount:
            return False

        # Check min_rating
        if self.agent_config.filters.min_rating is not None:
            min_rating = self.agent_config.filters.min_rating
        else:
            min_rating = self.config.global_min_rating

        if deal.rating is not None and deal.rating < min_rating:
            return False

        # Skip genre check - we use genres for location filtering in fetch()
        # Skip mac_only check - not applicable for concerts

        return True

    def fetch(self) -> list[RawItem]:
        """Fetch concerts for followed Spotify artists.

        Returns:
            List of RawItem objects representing concerts
        """
        items = []

        if not self.api_key:
            print("Ticketmaster API key not found. Please set TICKETMASTER_API_KEY in .env")
            print("Get your free API key at: https://developer.ticketmaster.com/")
            return items

        # Get followed artists from Spotify
        print("Fetching followed artists from Spotify...")
        artists = get_followed_artists()

        if not artists:
            print("No artists found. Make sure Spotify credentials are configured.")
            return items

        print(f"Checking concerts for {len(artists)} artists in {', '.join(self.locations)}...")

        # Check Ticketmaster for each artist
        for artist in artists:
            try:
                concerts = self._get_artist_concerts(artist['name'])
                for concert in concerts:
                    items.append(
                        RawItem(
                            external_id=concert['id'],
                            name=f"{artist['name']} - {concert['_embedded']['venues'][0]['name']}",
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
        """Get concerts for a specific artist from Ticketmaster.

        Args:
            artist_name: Name of the artist

        Returns:
            List of concert dicts
        """
        try:
            all_events = []

            # Search in each location
            for location in self.locations:
                url = "https://app.ticketmaster.com/discovery/v2/events.json"
                params = {
                    "apikey": self.api_key,
                    "keyword": artist_name,
                    "city": location,
                    "countryCode": "US",
                    "classificationName": "Music",
                    "size": 20
                }

                response = requests.get(url, params=params, timeout=10)

                # Rate limiting: Ticketmaster allows 5 requests/second
                time.sleep(0.25)  # 250ms = 4 requests/second to be safe

                if response.status_code == 401:
                    print("Invalid Ticketmaster API key")
                    return []

                if response.status_code == 404:
                    continue  # No events found for this location

                response.raise_for_status()
                data = response.json()

                # Extract events from response
                if "_embedded" in data and "events" in data["_embedded"]:
                    events = data["_embedded"]["events"]
                    # Filter to only include events where the artist name matches closely
                    for event in events:
                        event_name = event.get("name", "").lower()
                        if artist_name.lower() in event_name:
                            all_events.append(event)

            return all_events

        except Exception as e:
            print(f"Ticketmaster API error for {artist_name}: {e}")
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

        # Get venue info
        venues = concert.get('_embedded', {}).get('venues', [])
        venue = venues[0] if venues else {}

        # Parse date
        dates = concert.get('dates', {})
        start = dates.get('start', {})
        date_str = start.get('localDate', 'TBA')
        time_str = start.get('localTime', '')
        datetime_str = f"{date_str} {time_str}".strip()

        # Location
        city = venue.get('city', {}).get('name', 'Unknown')
        state = venue.get('state', {}).get('stateCode', '')
        location = f"{city}, {state}" if state else city

        # Ticket info
        ticket_url = concert.get('url', '')
        sales = concert.get('sales', {})
        public_sale = sales.get('public', {})
        ticket_status = public_sale.get('startDateTime', 'Check venue')

        # Price info
        price_ranges = concert.get('priceRanges', [])
        min_price = price_ranges[0].get('min', 0.0) if price_ranges else 0.0
        max_price = price_ranges[0].get('max', 0.0) if price_ranges else 0.0

        return Deal(
            id=None,
            agent_id=self.agent_id,
            source=self.source,
            external_id=concert['id'],
            name=f"{artist['name']} at {venue.get('name', 'TBA')}",
            icon="🎵",
            discount_pct=0,  # Not applicable for concerts
            original_price=max_price,
            sale_price=min_price,
            rating=artist.get('popularity', 0) / 10.0,  # Spotify popularity as rating
            genre=artist.get('genres', ['Unknown'])[0] if artist.get('genres') else 'Unknown',
            mac=False,  # Not applicable
            watchlist_hit=False,  # Will be set by base agent
            raw={
                'artist': artist['name'],
                'venue': venue.get('name', 'TBA'),
                'location': location,
                'date': date_str,
                'time': time_str,
                'datetime': datetime_str,
                'ticket_url': ticket_url,
                'ticket_status': ticket_status,
                'price_range': f"${min_price}-${max_price}" if min_price > 0 else "TBA",
            },
            found_at=datetime.utcnow().strftime("%Y-%m-%d"),
        )
