# Social Media Helpers

A collection of Python tools for managing, analysing, and growing a social media presence. Built for creators who want to automate the tedious parts and focus on content.

Each tool has a guided first-run setup — just run it once in your terminal and it walks you through everything.

---

## Tools

| Tool | What it does |
|------|-------------|
| [`photo-sorter`](./photo-sorter/) | Auto-sorts iPhone/Mac photos and videos into albums using Claude AI vision |
| [`viral-content-analysis`](./viral-content-analysis/) | Tracks competitor Instagram accounts and surfaces top-performing posts, hooks, and formats into Notion |
| [`instagram-stats`](./instagram-stats/) | Pulls your Instagram post and Reel stats into a structured Excel spreadsheet via the Instagram Graph API |

---

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/CKrogmann/Social-Media-Helpers.git
cd Social-Media-Helpers
```

### 2. Install dependencies

Each tool installs its own requirements. A common starting point:

```bash
pip install anthropic requests openpyxl imageio-ffmpeg instaloader
```

See each tool's README for the exact requirements.

### 3. Set your API keys

```bash
export ANTHROPIC_API_KEY=your_anthropic_key      # photo-sorter, viral-content-analysis
export INSTAGRAM_APP_ID=your_facebook_app_id     # instagram-stats (optional but recommended)
export INSTAGRAM_APP_SECRET=your_facebook_secret # instagram-stats (optional but recommended)
```

Add these to your `~/.zshrc` or `~/.bash_profile` to make them permanent.

### 4. Run a tool

Each tool has a guided first-run wizard:

```bash
python3 photo-sorter/photo_sorter.py
python3 viral-content-analysis/viral_content_analysis.py
python3 instagram-stats/instagram_stats_updater.py
```

---

## Using with Claude Code

If you use [Claude Code](https://claude.ai/code), you can install these as skills that let you trigger each tool by typing a slash command.

### Install via plugin (recommended)

This repo is published as a Claude Code plugin. Install it with:

```
/install-plugin https://github.com/CKrogmann/Social-Media-Helpers
```

Then use:
- `/photo-sorter` — sort your photos
- `/viral-content-analysis` — run competitor analysis
- `/instagram-stats` — refresh your stats

### Install manually via setup script

```bash
bash setup.sh
```

This symlinks the skills into `~/.claude/skills/`. Then add these lines to `~/.claude/CLAUDE.md`:

```
## Social Media Helpers
- `/photo-sorter` — auto-sort Photos library into albums using Claude AI
- `/viral-content-analysis` — track competitor Instagram accounts, push to Notion
- `/instagram-stats` — refresh Instagram post stats in Excel
```

---

## Requirements

| Tool | Requirements |
|------|-------------|
| photo-sorter | macOS, Python 3.10+, Anthropic API key |
| viral-content-analysis | Python 3.10+, Anthropic API key, Notion account |
| instagram-stats | Python 3.10+, Facebook Developer app, Business/Creator Instagram account |

---

## Project structure

```
social-media-helpers/
├── photo-sorter/
│   ├── README.md
│   └── photo_sorter.py
├── viral-content-analysis/
│   ├── README.md
│   └── viral_content_analysis.py
├── instagram-stats/
│   ├── README.md
│   └── instagram_stats_updater.py
├── skills/                   # Claude Code skill definitions
│   ├── photo-sorter/
│   ├── viral-content-analysis/
│   └── instagram-stats/
├── .env.example
└── setup.sh
```
