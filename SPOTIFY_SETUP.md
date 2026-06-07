# Spotify Concert Tracking Setup

The concert agent automatically tracks concerts for artists you follow on Spotify!

## Step 1: Create a Spotify App

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click **"Create app"**
4. Fill in the details:
   - **App name**: Curator Concert Tracker
   - **App description**: Personal concert tracking
   - **Redirect URI**: `http://localhost:8888/callback`
   - **APIs**: Select "Web API"
5. Click **"Save"**
6. You'll see your **Client ID** and **Client Secret** - copy these!

## Step 2: Add Credentials to .env

Edit your `.env` file and add:

```bash
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

## Step 3: Enable Concert Agent

Edit `config.json` and set the concert agent to enabled:

```json
{
  "agents": [
    {
      "id": "concert",
      "enabled": true,
      "schedule": "every_24h",
      "filters": {
        "genres": ["Your City, State"]  // e.g., "San Francisco, CA" or "worldwide"
      }
    }
  ]
}
```

## Step 4: First Time Authentication

The first time you run the concert agent, it will:

1. Open your browser to authenticate with Spotify
2. Ask you to authorize the app
3. Redirect back to localhost (you'll see a "site can't be reached" - that's OK!)
4. Copy the full URL from your browser
5. Paste it into the terminal when prompted

After this one-time setup, the agent will remember your authorization.

## Step 5: Test It!

```bash
# Run the concert agent manually
python -m curator.core.orchestrator

# Or via the API
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d '{"agent_id": "concert"}'
```

## How It Works

**Daily Process:**
1. Fetches your followed artists from Spotify (all of them!)
2. Checks Bandsintown for upcoming concerts
3. Filters by your location (if specified)
4. Saves new concerts to the database
5. Sends email notifications for new findings

**Location Filtering:**

- Set `"genres": ["San Francisco, CA"]` for local concerts only
- Set `"genres": ["worldwide"]` or `"genres": []` for all concerts globally
- Matches city, state, and country from venue location

## Troubleshooting

**"Spotify credentials not found"**
- Make sure your `.env` file has `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`
- Restart the app after adding credentials

**"Failed to authenticate"**
- Check that redirect URI is exactly: `http://localhost:8888/callback`
- Make sure it matches in both the Spotify app settings AND your `.env`

**"No artists found"**
- Make sure you're following artists on Spotify
- Check that authentication completed successfully

**Want to re-authenticate?**
- Delete the `.spotify_cache` file
- Run the agent again - it will re-prompt for authorization

## GitHub Actions Setup

Add these secrets to your repository:

1. Go to: https://github.com/YOUR_USERNAME/curator/settings/secrets/actions
2. Add:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`

**Note**: GitHub Actions cannot do interactive OAuth, so you must authenticate locally first. The `.spotify_cache` file contains your refresh token. You have two options:

**Option A**: Add the refresh token as a secret (more secure):
1. After authenticating locally, find your refresh token in `.spotify_cache`
2. Add it as `SPOTIFY_REFRESH_TOKEN` secret in GitHub

**Option B**: Use a long-lived access pattern (simpler):
The current implementation uses SpotifyOAuth which handles token refresh automatically.

## Cost

- Spotify API: **Free** (50,000 requests/day)
- Bandsintown API: **Free** (unlimited for personal use)
- **Total**: **$0/month**

Enjoy never missing a concert from your favorite artists again!
