"""Spotify authentication helper."""
import os
from typing import Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth


def get_spotify_client() -> Optional[spotipy.Spotify]:
    """Get authenticated Spotify client.

    Returns:
        Spotify client if credentials are available, None otherwise
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

    if not client_id or not client_secret:
        print("Spotify credentials not found in environment")
        return None

    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-follow-read",
            cache_path=".spotify_cache"
        ))
        return sp
    except Exception as e:
        print(f"Failed to authenticate with Spotify: {e}")
        return None


def get_followed_artists() -> list[dict]:
    """Get list of artists the user follows on Spotify.

    Returns:
        List of artist dicts with 'id' and 'name' keys
    """
    sp = get_spotify_client()
    if not sp:
        return []

    try:
        artists = []
        results = sp.current_user_followed_artists(limit=50)

        while results:
            for artist in results['artists']['items']:
                artists.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'genres': artist.get('genres', []),
                    'popularity': artist.get('popularity', 0)
                })

            # Check if there are more artists
            if results['artists']['next']:
                results = sp.next(results['artists'])
            else:
                break

        print(f"Found {len(artists)} followed artists on Spotify")
        return artists

    except Exception as e:
        print(f"Error fetching followed artists: {e}")
        return []
