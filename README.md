# Social Media Helpers

A collection of Python tools for managing, analysing, and growing a social media presence. Built for creators who want to automate the tedious parts and focus on content.

---

## Tools

| Tool | What it does |
|------|-------------|
| [`photo-sorter`](./plugins/photo-sorter/) | Auto-sorts iPhone/Mac photos and videos into albums using Claude AI vision |
| [`viral-content-analysis`](./plugins/viral-content-analysis/) | Tracks competitor Instagram accounts and surfaces top-performing posts, hooks, and formats into Notion |
| [`instagram-stats`](./plugins/instagram-stats/) | Pulls your Instagram post and Reel stats into a structured Excel spreadsheet via the Instagram Graph API |

---

## Install via Claude Code (recommended)

These tools are published as a Claude Code marketplace plugin. No terminal setup required — Claude walks you through configuration on first run.

1. Open Claude Code → **Customize** → **Add marketplace**
2. Enter: `CKrogmann/Social-Media-Helpers`
3. Install the tools you want

Then use the slash commands:
- `/photo-sorter` — sort your photos
- `/viral-content-analysis` — run competitor analysis
- `/instagram-stats` — refresh your stats

---

## Run directly from the terminal

### 1. Clone the repo

```bash
git clone https://github.com/CKrogmann/Social-Media-Helpers.git
cd Social-Media-Helpers
```

### 2. Install dependencies

```bash
pip install anthropic requests openpyxl imageio-ffmpeg instaloader notion-client
```

See each tool's README for exact requirements.

### 3. Set your API keys

```bash
export ANTHROPIC_API_KEY=your_anthropic_key      # photo-sorter, viral-content-analysis
export INSTAGRAM_APP_ID=your_facebook_app_id     # instagram-stats (optional)
export INSTAGRAM_APP_SECRET=your_facebook_secret # instagram-stats (optional)
```

Add these to your `~/.zshrc` or `~/.bash_profile` to make them permanent.

### 4. Run a tool

Each tool has a guided first-run setup wizard:

```bash
python3 plugins/photo-sorter/src/photo_sorter.py
python3 plugins/viral-content-analysis/src/viral_content_analysis.py
python3 plugins/instagram-stats/src/instagram_stats_updater.py
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
Social-Media-Helpers/
├── .claude-plugin/
│   └── marketplace.json          # Claude Code marketplace config
├── plugins/
│   ├── photo-sorter/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── commands/
│   │   │   └── photo-sorter.md   # slash command definition
│   │   ├── src/
│   │   │   └── photo_sorter.py
│   │   └── README.md
│   ├── viral-content-analysis/   # same structure
│   └── instagram-stats/          # same structure
├── .env.example
├── release.sh                    # bump versions and publish
└── setup.sh
```
