# Ticketmaster API Setup

Get your free Ticketmaster API key to enable concert tracking.

## Step 1: Register for API Key

1. Go to: https://developer.ticketmaster.com/
2. Click **"Get Your API Key"** (top right corner)
3. Fill in the registration form:
   - **First Name**: Your first name
   - **Last Name**: Your last name
   - **Email**: Your email address
   - **Company**: `Personal Project` (or your name)
   - **Company Website**: Your GitHub profile URL or `http://localhost:8000`
   - **App Name**: `Curator Concert Tracker`
   - **App URL**: `http://localhost:8000`
   - **Phone Number**: Your phone number
4. Click **"Register"**
5. Check your email and verify your account

## Step 2: Get Your API Key

1. After verifying your email, log in to: https://developer-acct.ticketmaster.com/user/login
2. Go to your dashboard
3. You'll see your **Consumer Key** - this is your API key
4. Copy it!

## Step 3: Add to .env

Open your `.env` file and add this line:

```bash
TICKETMASTER_API_KEY=paste_your_key_here
```

**Example:**
```bash
TICKETMASTER_API_KEY=AbCd1234EfGh5678IjKl9012MnOp3456
```

## Step 4: Test It

```bash
source venv/bin/activate
python -m curator.core.orchestrator
```

The concert agent will:
- Fetch your 166 Spotify followed artists
- Search Ticketmaster for concerts in New York, Brooklyn, and Jersey City
- Save any found concerts to the database
- Send you an email notification if concerts are found

## API Limits

- **Free Tier**: 5,000 requests per day
- **Rate Limit**: 5 requests per second
- **Cost**: $0/month

With 166 artists and 3 locations, each run uses ~500 requests, so you can run it 10x per day easily.

## Troubleshooting

**"Invalid ApiKey" error**
- Make sure you copied the entire Consumer Key from the dashboard
- Check for extra spaces before/after the key in .env
- Verify the key is on the line: `TICKETMASTER_API_KEY=your_key`

**"No concerts found"**
- This might be expected if none of your artists are touring in your area
- The agent only shows new concerts (not duplicates)
- Try expanding locations in `config.json` under concert agent `genres` field

**Need to change locations?**
Edit `config.json`:
```json
{
  "id": "concert",
  "filters": {
    "genres": ["New York", "Los Angeles", "Chicago"]
  }
}
```
