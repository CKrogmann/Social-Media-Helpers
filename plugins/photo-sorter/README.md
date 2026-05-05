# Photo Sorter

Auto-sorts your iPhone and Mac photos (and videos) into albums using Claude AI vision. Set up your albums once, then run it every few days (or on a schedule) to keep your library organised automatically.

---

## What it does

- Reads your Photos library and finds unsorted images from the last 30 days
- Sends each photo to Claude, which classifies it into one of your defined albums
- Skips photos where confidence is below 75% — they stay unsorted rather than ending up in the wrong place
- Deduplicates bursts — keeps only the first shot when multiple photos were taken within 3 seconds
- Falls back to assisted (manual review) mode if the auto error rate exceeds 20%
- Logs everything to `~/photo_sorter.log`

---

## Requirements

- macOS (uses Apple's Photos SQLite database and AppleScript)
- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

### Step 1 — Install Python dependencies

```bash
pip install anthropic
```

### Step 2 — Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up or log in
3. Click **API Keys** → **Create Key**
4. Copy the key

Set it as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

To make this permanent, add it to your shell profile (`~/.zshrc` or `~/.bash_profile`):

```bash
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

### Step 3 — Create your albums in the Photos app

Before running the sorter, create the albums you want in the Photos app. The album names must exist before the script can add photos to them.

Open Photos → File → New Album (or click the + button in the sidebar). Create one album for each category you want to sort into.

### Step 4 — Run the first-time setup

Run the script directly in your terminal. It will walk you through a one-time setup:

```bash
python3 photo_sorter.py
```

You'll be asked to enter:
- **Your name** — used to personalise Claude's sorting decisions
- **Context** — what is this library for? (e.g. "social media content for a fitness creator based in London")
- **Albums** — for each album: the exact name as it appears in the Photos app, and what should go there

Your answers are saved to `~/.photo_sorter_config.json` and used on every future run.

---

## Running it

After setup, just run:

```bash
ANTHROPIC_API_KEY=your_key python3 photo_sorter.py
```

It processes up to 200 photos per run. If you have more, run it again — it picks up where it left off.

---

## Automated schedule (optional)

Run automatically every 3 days at 9am:

```bash
crontab -e
```

Add this line (replace the path with where you cloned the repo):

```
0 9 */3 * * ANTHROPIC_API_KEY=your_key python3 /path/to/photo-sorter/photo_sorter.py >> ~/photo_sorter.log 2>&1
```

---

## Configuration

All settings are saved to `~/.photo_sorter_config.json` after first run. You can edit it directly to:

- Change album names or sorting criteria
- Add or remove albums
- Adjust `user_context` to change how Claude interprets your photos

```json
{
  "user_name": "Your Name",
  "user_context": "social media content for a lifestyle creator",
  "albums": {
    "album_1": {
      "name": "Travel",
      "criteria": "photos taken abroad, landmarks, airports, nature from trips"
    },
    "album_2": {
      "name": "Food",
      "criteria": "restaurant meals, home cooking, coffee, food flat lays"
    }
  },
  "general_rules": "Only include photos where I am clearly visible. Skip blurry shots."
}
```

---

## Troubleshooting

**Photos aren't being found**
Make sure your Photos library is in the default location (`~/Pictures/Photos Library.photoslibrary`). If you moved it, update `PHOTOS_DB` and `ORIGINALS_DIR` in the script.

**Photos aren't being added to albums**
Make sure the album names in your config match *exactly* what's in the Photos app (including capitalisation and punctuation).

**High skip rate**
Lower the `CONFIDENCE_THRESHOLD` in the script (default: 75) or refine your album criteria in the config.
