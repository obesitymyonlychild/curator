# GitHub Actions Setup Guide

## Step 1: Push your code to GitHub

```bash
# Initialize git (if not already done)
git add .
git commit -m "Add Curator deal tracking system"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/curator.git
git branch -M main
git push -u origin main
```

## Step 2: Add GitHub Secrets

Go to your GitHub repository settings:
1. Click **Settings** tab
2. Click **Secrets and variables** → **Actions**
3. Click **New repository secret**

Add these secrets one by one:

### Required for Email Notifications:

**Secret Name:** `SMTP_USER`  
**Value:** Your Gmail address (e.g., wufeii1999@gmail.com)

**Secret Name:** `SMTP_PASS`  
**Value:** Your Gmail app password (16 characters, no spaces)

**Secret Name:** `SMTP_HOST`  
**Value:** `smtp.gmail.com`

### Optional (for Claude Haiku genre classification):

**Secret Name:** `ANTHROPIC_API_KEY`  
**Value:** Your Anthropic API key from https://console.anthropic.com/

### Optional (for Telegram notifications):

**Secret Name:** `TELEGRAM_BOT_TOKEN`  
**Value:** Your Telegram bot token

**Secret Name:** `TELEGRAM_CHAT_ID`  
**Value:** Your Telegram chat ID

## Step 3: Verify GitHub Actions

After pushing your code and adding secrets:

1. Go to the **Actions** tab in your GitHub repository
2. You should see the "Curator Agent Run" workflow
3. Click **Run workflow** to test it manually
4. It will run automatically every day at midnight UTC

## Step 4: Monitor runs

- Check the **Actions** tab to see workflow runs
- View logs to see if deals were found
- Check your email for notifications when deals are discovered

## Database Persistence (Optional)

The current setup uploads the database as an artifact (kept for 7 days). 

For long-term persistence, consider:
- Using GitHub Actions cache
- Storing in a cloud database (SQLite on S3, PostgreSQL, etc.)
- Using GitHub Releases to store the database

## Cost Estimation

- GitHub Actions: **Free** (2000 minutes/month)
- Email notifications: **Free**
- Anthropic API (genre classification): **~$1-3/month** (optional)
- **Total: $0-3/month**
