# Viral Content Analysis

Tracks public Instagram accounts, surfaces their top-performing posts, hooks, formats, and content patterns, then pushes everything into your Notion workspace. Run it once for a 180-day deep dive, then monthly to stay current.

---

## What it does

- Scrapes any public Instagram accounts you choose (no Instagram account required)
- Identifies top posts by views and engagement — reels over 1M views, or the top 20% by engagement rate
- Extracts hooks, content formats, and visual patterns using Claude AI
- Optionally transcribes the first 5 seconds of Reels to capture audio hooks (requires Whisper)
- Organises findings into three Notion databases:
  - **Viral Posts** — every top-performing post with engagement stats and hook analysis
  - **Content Patterns** — recurring hooks and formats that explain why content works
  - **Niche Journey** — per-account analysis of how their content evolved over time
- First run: 180-day lookback. Subsequent runs: 90-day rolling refresh.

---

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- A [Notion](https://notion.so) account

---

## Setup

### Step 1 — Install Python dependencies

```bash
pip install anthropic requests imageio-ffmpeg instaloader
```

Optional: for audio hook transcription from Reels:

```bash
pip install openai-whisper
brew install ffmpeg   # macOS — or use your system package manager
```

### Step 2 — Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up or log in → click **API Keys** → **Create Key**
3. Copy the key and set it as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

To make it permanent:

```bash
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

### Step 3 — Set up Notion

You need a Notion integration that can write to your workspace.

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration** → give it a name (e.g. "Content Tracker") → **Submit**
3. Copy the **Internal Integration Token** (starts with `secret_`)
4. Create a blank Notion page where your databases will live
5. On that page, click the `...` menu → **Add connections** → select your integration
6. Copy the **page ID** from the URL — it's the long string after the last `/` (e.g. `https://notion.so/My-Page-abc123def456` → page ID is `abc123def456`)

### Step 4 — Run first-time setup

```bash
python3 viral_content_analysis.py
```

On first run, you'll be prompted to enter:
- **Instagram accounts to track** — enter handles one by one (no `@` needed), press Enter twice when done
- **Notion integration token** — the `secret_` token from Step 3
- **Notion page ID** — from the URL of the page you created

Everything is saved to `~/.viral_content_config.json`. The script then immediately runs its first 180-day analysis.

---

## Subsequent runs

After setup, just run:

```bash
ANTHROPIC_API_KEY=your_key python3 viral_content_analysis.py
```

Each run refreshes the last 90 days of data and pushes any new viral posts to Notion. Duplicates are automatically skipped.

---

## Automated schedule (monthly)

```bash
crontab -e
```

Add this line (replace the path and key):

```
0 8 1 * * ANTHROPIC_API_KEY=your_key python3 /path/to/viral-content-analysis/viral_content_analysis.py >> ~/viral_content_analysis.log 2>&1
```

This runs on the 1st of each month at 8am.

---

## Configuration

Stored in `~/.viral_content_config.json`. You can edit it to:

- Add or remove tracked accounts
- Adjust what counts as "viral" for your niche

```json
{
  "accounts": ["account1", "account2", "account3"],
  "notion_token": "secret_...",
  "notion_page_id": "your-page-id",
  "thresholds": {
    "reel_views": 1000000,
    "top_pct": 0.20
  }
}
```

**`reel_views`** — minimum views for a Reel to qualify as viral (default: 1,000,000)
**`top_pct`** — top percentage by engagement rate for posts and carousels (default: 20%)

Adjust these to match the scale of your niche. For smaller niches (under 100k followers), try `reel_views: 100000` and `top_pct: 0.10`.

---

## Troubleshooting

**"Rate limited" for an account**
Instagram limits how fast you can scrape. The script automatically waits 15 minutes and retries once. If it keeps failing, wait a few hours and run again.

**"Profile not found"**
The account may have changed their handle or been deleted. Remove it from `accounts` in your config.

**Notion push failing**
Make sure you shared the target page with your integration (Step 3, point 5 above). The integration must have access to write to that specific page.
