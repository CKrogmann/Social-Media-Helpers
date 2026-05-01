# Social Media Helpers

A collection of Python tools for managing, analyzing, and growing a social media presence. Built for creators who want to automate the boring parts and focus on content.

---

## Tools

| Tool | What it does |
|------|-------------|
| [`photo-sorter`](./photo-sorter/) | Auto-sorts iPhone/Mac photos into albums using Claude AI vision |
| [`viral-content-analysis`](./viral-content-analysis/) | Tracks competitor accounts and surfaces top-performing posts, hooks, and formats into Notion |
| [`instagram-stats`](./instagram-stats/) | Pulls your Instagram post stats into a structured Excel sheet via the Instagram Graph API |

---

## Setup

### 1. Install dependencies

Each tool has its own requirements. See the individual README in each folder.

### 2. Set environment variables

Create a `.env` file in the root (see `.env.example`) or export variables in your shell:

```bash
export ANTHROPIC_API_KEY=your_key_here       # photo-sorter, viral-content-analysis
export INSTAGRAM_APP_ID=your_app_id          # instagram-stats
export INSTAGRAM_APP_SECRET=your_app_secret  # instagram-stats
```

### 3. Run a tool

```bash
python3 photo-sorter/photo_sorter.py
python3 viral-content-analysis/viral_content_analysis.py
python3 instagram-stats/instagram_stats_updater.py
```

---

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) (for photo-sorter and viral-content-analysis)
- A Facebook Developer app with Instagram Graph API access (for instagram-stats)

---

## Structure

```
social-media-helpers/
├── photo-sorter/               # AI-powered photo organizer
│   ├── README.md
│   └── photo_sorter.py
├── viral-content-analysis/     # Competitor content tracker
│   ├── README.md
│   └── viral_content_analysis.py
└── instagram-stats/            # Instagram stats → Excel
    ├── README.md
    └── instagram_stats_updater.py
```
