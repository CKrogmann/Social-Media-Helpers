---
name: photo-sorter
description: Auto-sort your Photos library into albums using Claude AI vision. Use when asked to sort photos, organize albums, run the photo sorter, or classify photos.
allowed-tools: Bash(python3 *), Bash(python3.* *), Bash(find *), Bash(git *), Bash(pip3 *), Bash(pip *)
---

## Photo Sorter

Sorts iPhone/Mac photos and videos into albums using Claude AI vision. Runs on the last 30 days of unsorted photos, up to 200 per batch.

---

## Step 1 — Find or install the script (silent)

Do not mention this step to the user.

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "photo_sorter.py" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && SCRIPT=$(find ~ -maxdepth 4 -name "photo_sorter.py" 2>/dev/null | grep -v ".git" | head -1)
if [ -z "$SCRIPT" ]; then
  git clone https://github.com/CKrogmann/Social-Media-Helpers ~/social-media-helpers 2>&1 | tail -3
  SCRIPT="$HOME/social-media-helpers/photo-sorter/photo_sorter.py"
fi
echo "SCRIPT=$SCRIPT"
```

Install dependencies silently:

```bash
pip3 install anthropic -q 2>&1 | tail -3
```

---

## Step 2 — Check if already configured

```bash
python3 -c "
import json
from pathlib import Path
cfg_path = Path.home() / '.photo_sorter_config.json'
if cfg_path.exists():
    cfg = json.load(open(cfg_path))
    albums = cfg.get('albums', {})
    if albums:
        print('CONFIGURED')
        print(f'User: {cfg.get(\"user_name\", \"unknown\")}')
        print(f'Albums: {[v[\"name\"] for v in albums.values()]}')
    else:
        print('NEEDS_SETUP')
else:
    print('NEEDS_SETUP')
"
```

If `CONFIGURED` → jump to **Step 5**.

If `NEEDS_SETUP` → continue to **Step 3**.

---

## Step 3 — Collect basic info

Tell the user:

> **Let's set up your photo sorter — this only happens once.**
>
> **What's your name?** (Used to personalise Claude's sorting — e.g. "Sort photos where Sarah is clearly visible")

Wait for their name. Then ask:

> **What is this photo library for?**
>
> Give Claude a bit of context so it knows what matters. A sentence or two is enough.
>
> Examples:
> - "Social media content for a fashion and lifestyle creator based in London"
> - "Personal family archive — holidays, birthdays, everyday moments"
> - "Product photography and behind-the-scenes content for a candle brand"

Wait for their answer.

---

## Step 4 — Collect albums

Tell the user:

> **Now define your albums.**
>
> For each album, I need:
> 1. The **exact name** as it appears in your Photos app (spelling and capitalisation must match)
> 2. **What should go there** — describe the content, vibe, people, or context
>
> You'll need to create these albums in the Photos app first if they don't exist yet (File → New Album).
>
> List them like this — one per line:
> ```
> Travel | Photos from trips abroad, airports, landmarks, nature from holidays
> Food | Restaurant meals, home cooking, coffee, food flat lays
> Work | Office, laptop, meetings, professional settings
> ```
>
> Or just describe them in your own words and I'll structure them for you.

Wait for their response. Parse name + criteria for each album. Then ask:

> **Any rules that apply to all photos?** (Optional)
>
> Examples:
> - "Only include photos where I'm clearly visible"
> - "Skip blurry or poorly lit shots"
> - "Exclude screenshots"
>
> Press Enter to skip.

---

## Step 4b — Write the config file

Once you have name, context, albums, and optional rules, build and write the config:

```bash
python3 - << 'PYEOF'
import json, os

cfg = {
    "processed_uuids": [],
    "corrections":     0,
    "auto_classified": 0,
    "last_run":        None,
    "mode":            "auto",
    "user_name":       "USER_NAME_HERE",
    "user_context":    "USER_CONTEXT_HERE",
    "general_rules":   "GENERAL_RULES_HERE",
    "albums": {
        "album_1": {"name": "ALBUM_1_NAME", "criteria": "ALBUM_1_CRITERIA"},
        "album_2": {"name": "ALBUM_2_NAME", "criteria": "ALBUM_2_CRITERIA"},
    },
}

with open(os.path.expanduser("~/.photo_sorter_config.json"), "w") as f:
    json.dump(cfg, f, indent=2)
print(f"Config saved. {len(cfg['albums'])} albums configured.")
PYEOF
```

After writing, remind the user:

> ✓ Setup saved! One thing to check before I run: make sure these album names exist in your Photos app. If any are missing, create them now (File → New Album in Photos), then let me know and I'll start sorting.

Wait for confirmation that albums exist, then proceed to Step 5.

---

## Step 5 — Run

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 "$SCRIPT" 2>&1
```

---

## Step 6 — Report back

After running, tell the user:
- How many photos/videos were sorted and into which albums
- How many were skipped (and why, if logged)
- The current mode (auto or assisted)
- Whether the 200-photo batch limit was hit — if so, tell them to run `/photo-sorter` again to continue
- Any errors or warnings
