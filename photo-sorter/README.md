# Photo Sorter

Auto-sorts your iPhone and Mac photos (and videos) into albums using Claude AI vision. Runs quietly in the background — set it up once, let it handle the chaos.

---

## What it does

- Reads your Photos library and identifies unsorted images
- Sends each photo to Claude, which classifies it into one of your defined albums
- Skips photos where confidence is below 75% (asks you instead)
- Deduplicates bursts — keeps only the first shot when multiple photos were taken within 3 seconds
- Falls back to assisted (manual review) mode if error rate exceeds 20%
- Logs everything to `~/photo_sorter.log`

**Default albums:**

| Album key | Photos app album |
|-----------|-----------------|
| `model_bts` | Model - BTS |
| `model_editorial` | Model - Editorial |
| `lifestyle_peaceful` | Lifestyle - Peaceful |
| `lifestyle_cute` | Lifestyle - Cute |
| `business` | Business - Startup |
| `skip` | *(skipped, not moved)* |

---

## Setup

### 1. Install dependencies

```bash
pip install anthropic
```

### 2. Set your API key

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Or add it to your `.env` file in the repo root.

### 3. Create albums in Photos app

Open the Photos app and create the albums listed above. Make sure the names match exactly.

### 4. Run

```bash
python3 photo_sorter.py
```

On first run it processes up to 200 unsorted photos. After that, run it every few days (or set up a cron job).

---

## Cron setup (optional)

Run automatically every 3 days at 9am:

```bash
crontab -e
# Add this line:
0 9 */3 * * ANTHROPIC_API_KEY=your_key python3 /path/to/photo_sorter.py
```

---

## Config

Settings are saved to `~/.photo_sorter_config.json` after first run. You can edit:

- `CONFIDENCE_THRESHOLD` — minimum confidence to auto-sort (default: 75)
- `BATCH_SIZE` — photos processed per run (default: 200)
- `ALBUMS` — customize album names to match your Photos library

---

## Requirements

- macOS (uses Apple Photos SQLite database)
- Python 3.10+
- `anthropic` Python package
- An [Anthropic API key](https://console.anthropic.com/)
