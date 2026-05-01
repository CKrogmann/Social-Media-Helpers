# Viral Content Analysis

Tracks 10–15 public Instagram accounts, surfaces their top-performing posts, hooks, formats, and content patterns, then pushes everything into your Notion workspace. Run it once for a 180-day deep dive, then monthly to stay current.

---

## What it does

- Scrapes public Instagram accounts you define (no account required)
- Identifies top posts by views and engagement (reels over 1M views, top 20% by engagement)
- Extracts hooks, content formats, and visual patterns using Claude AI
- Organizes findings into three Notion databases:
  - **Viral Posts** — individual top-performing posts
  - **Content Patterns** — recurring hooks and formats that work
  - **Niche Journey** — per-account analysis of how their content evolved
- First run: 180-day lookback. Monthly runs: 90-day refresh.

---

## Setup

### 1. Install dependencies

```bash
pip install anthropic requests imageio-ffmpeg
```

Optional (for video analysis):
```bash
brew install ffmpeg
```

### 2. Set your API key

```bash
export ANTHROPIC_API_KEY=your_key_here
```

### 3. Set up Notion

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Copy your integration token
3. Share your target Notion page with the integration
4. Copy the page ID from the URL

### 4. First run

```bash
python3 viral_content_analysis.py
```

On first run, you'll be prompted to enter:
- Instagram accounts to track (e.g. `@handle1, @handle2`)
- Your Notion token and page ID

Config is saved to `~/.viral_content_config.json`.

---

## Config

Stored in `~/.viral_content_config.json`:

```json
{
  "accounts": ["handle1", "handle2"],
  "notion_token": "secret_...",
  "notion_page_id": "your-page-id",
  "thresholds": {
    "reel_views": 1000000,
    "top_pct": 0.20
  }
}
```

Adjust `reel_views` and `top_pct` to change what counts as "viral" for your niche.

---

## Cron setup (monthly)

```bash
crontab -e
# Add this line (runs on the 1st of each month at 8am):
0 8 1 * * ANTHROPIC_API_KEY=your_key python3 /path/to/viral_content_analysis.py
```

---

## Requirements

- Python 3.10+
- `anthropic`, `requests`, `imageio-ffmpeg` packages
- An [Anthropic API key](https://console.anthropic.com/)
- A Notion account with API access
