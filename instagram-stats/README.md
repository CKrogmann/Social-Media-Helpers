# Instagram Stats

Pulls your Instagram post and Reel stats into a structured Excel spreadsheet via the Instagram Graph API. Keeps the newest posts at the top, refreshes 90-day rolling stats on every run, and never overwrites fields you've filled in manually.

---

## What it does

- Fetches all your Instagram posts and Reels with metrics: views, likes, comments, reach, saves, shares, profile visits, follows
- Refreshes stats for posts from the last 90 days on every run (older posts keep their last known stats)
- Creates a structured Excel file with separate sheets for Posts and Reels — no setup needed on your end
- Sorts everything newest-first
- Preserves manually entered fields (content pillar, asset name, hook text, etc.)
- Removes duplicate rows automatically
- Auto-refreshes your access token before it expires — no manual re-auth for up to 60 days

---

## Requirements

- Python 3.10+
- A **Business or Creator** Instagram account (Personal accounts don't have API access)
- A Facebook Developer app with Instagram Graph API access

---

## Setup

### Step 1 — Install Python dependencies

```bash
pip install requests openpyxl
```

### Step 2 — Create a Facebook Developer App

You need this to generate an access token that lets the script read your Instagram stats.

1. Go to [developers.facebook.com](https://developers.facebook.com/) and log in with your Facebook account
2. Click **My Apps** → **Create App**
3. Choose **Other** as the use case → **Next**
4. Select **Business** as the app type → **Next**
5. Give your app a name (anything you like) → **Create App**
6. On the dashboard, find **Instagram** and click **Set up**
7. Follow the prompts to connect your Instagram account

### Step 3 — Generate an Access Token

1. In your app dashboard, click **Instagram** in the left menu
2. Click **Generate Access Token**
3. Log in with your Instagram account when prompted
4. Copy the long token that appears — you'll need this in the next step

### Step 4 — Set environment variables (optional)

If you have an App ID and App Secret (found in your app's Basic Settings), set them so the script can auto-refresh your token:

```bash
export INSTAGRAM_APP_ID=your_app_id
export INSTAGRAM_APP_SECRET=your_app_secret
```

To make permanent:

```bash
echo 'export INSTAGRAM_APP_ID=your_app_id' >> ~/.zshrc
echo 'export INSTAGRAM_APP_SECRET=your_app_secret' >> ~/.zshrc
source ~/.zshrc
```

### Step 5 — Run first-time setup

```bash
python3 instagram_stats_updater.py
```

The script will walk you through three steps:

1. **Paste your access token** — the one from Step 3
2. **Connect your account** — your Instagram User ID is fetched automatically from the token (no manual lookup needed)
3. **Choose where to save your spreadsheet** — press Enter for the default (`~/Instagram Stats {year}.xlsx`) or enter a custom path

A new Excel file is created automatically with the right sheets and column headers. Nothing to set up in Excel yourself.

---

## Subsequent runs

After setup, just run:

```bash
python3 instagram_stats_updater.py
```

The script reads your existing spreadsheet, fetches fresh stats from the API, merges everything, and saves. Your manually entered fields are always preserved.

---

## Automated schedule (optional)

Run every Monday at 7am:

```bash
crontab -e
```

Add this line (replace the path):

```
0 7 * * 1 python3 /path/to/instagram-stats/instagram_stats_updater.py >> ~/instagram_stats.log 2>&1
```

---

## Excel structure

The script creates two sheets, one for Posts and one for Reels. Both are named by year (e.g. `Instagram Posts 2026`) and a new pair is created automatically each January.

**Posts sheet columns:**

| Column | Description |
|--------|-------------|
| Post Date | When the post was published |
| Content Pillar | Fill in manually — your content category |
| Asset | Fill in manually — asset name or description |
| Format | Static / Carousel / Reel (from API) |
| Views | Fill in manually for posts (API doesn't provide this) |
| Reach | Unique accounts reached |
| Avg Reach | Average reach across all posts (formula) |
| Views/Reach | Ratio (formula) |
| Interactions | Total interactions |
| Interaction Rate | Interactions ÷ Reach (formula) |
| Likes | Total likes |
| Saves | Total saves |
| Shares | Total shares |
| Profile Visits | Visits from this post |
| Follows | New follows from this post |
| Follow Rate | Follows ÷ Profile Visits (formula) |
| % Men | Fill in manually from Instagram Insights |
| % Women | Calculated as 1 − % Men (formula) |
| Score | Composite performance score (formula) |

**Reels sheet** has the same structure plus Series and Hook columns.

---

## Configuration

Stored in `~/.instagram_stats_config.json`. You generally don't need to edit this directly — setup handles it all. But if you need to update your token manually:

```json
{
  "access_token": "your_long_lived_token",
  "ig_user_id": "your_instagram_user_id",
  "app_id": "...",
  "app_secret": "...",
  "token_expires": "2026-07-01T00:00:00+00:00",
  "excel_path": "/Users/you/Instagram Stats 2026.xlsx"
}
```

---

## Troubleshooting

**"First-time setup required" error**
Run the script directly in a terminal (not via Claude Code) for the initial setup — it needs interactive input.

**Token expired**
Go to developers.facebook.com → your app → Instagram → Generate Access Token. Update `access_token` in `~/.instagram_stats_config.json`.

**"API error" on a post**
Posts published before your account was a Business/Creator account don't have insights available. The script uses existing stats from Excel as fallback, so nothing is lost.

**Excel file not found**
Update `excel_path` in `~/.instagram_stats_config.json` to point to your file's current location, or delete the config entry and run setup again to create a fresh file.
