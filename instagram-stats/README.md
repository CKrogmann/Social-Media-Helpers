# Instagram Stats

Pulls your Instagram post stats into a structured Excel sheet via the Instagram Graph API. Keeps the newest posts at the top, refreshes 90-day rolling stats on every run, and never overwrites manually entered fields.

---

## What it does

- Fetches all your Instagram posts with metrics: likes, comments, reach, impressions, saves, shares
- Updates a rolling 90-day stats window every run (older posts keep their last known stats)
- Sorts posts newest-first in Excel
- Preserves any notes or manually entered fields in the spreadsheet
- Removes duplicate rows automatically
- Auto-refreshes your access token before it expires (no re-auth needed for 60 days)

**Output:** `~/Celina Krogmann SM Planning.xlsx` (configurable)

---

## Setup

### 1. Install dependencies

```bash
pip install requests openpyxl
```

### 2. Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com/) and create an app
2. Add the **Instagram Graph API** product
3. Generate a long-lived access token for your Instagram account
4. Copy your **App ID**, **App Secret**, and **Access Token**

### 3. Set environment variables

```bash
export INSTAGRAM_APP_ID=your_app_id
export INSTAGRAM_APP_SECRET=your_app_secret
```

### 4. First run

```bash
python3 instagram_stats_updater.py
```

On first run, you'll be prompted to enter your access token and Instagram user ID. These are saved to `~/.instagram_stats_config.json`.

---

## Config

Stored in `~/.instagram_stats_config.json`:

```json
{
  "access_token": "your_long_lived_token",
  "ig_user_id": "your_instagram_user_id",
  "app_id": "...",
  "app_secret": "...",
  "token_expires": "2026-07-01T00:00:00+00:00"
}
```

To find your Instagram user ID: use the [Graph API Explorer](https://developers.facebook.com/tools/explorer/) and query `me?fields=id,name` with your token.

---

## Cron setup (weekly)

```bash
crontab -e
# Add this line (runs every Monday at 7am):
0 7 * * 1 python3 /path/to/instagram_stats_updater.py
```

---

## Excel output format

| Column | Description |
|--------|-------------|
| Post Date | When the post was published |
| Format | Static / Carousel / Reel |
| Caption | First 100 characters |
| Likes | Total likes |
| Comments | Total comments |
| Reach | Unique accounts reached |
| Impressions | Total impressions |
| Saves | Total saves |
| Shares | Total shares |

---

## Requirements

- Python 3.10+
- `requests`, `openpyxl` packages
- A Facebook Developer app with Instagram Graph API access
- A business or creator Instagram account
