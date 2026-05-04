---
name: photo-sorter
description: Auto-sort your Photos library into albums using Claude AI vision. Use when asked to sort photos, organize albums, run the photo sorter, or classify photos.
allowed-tools: Bash(python3 *), Bash(find *)
---

## Photo Sorter

Sorts iPhone/Mac photos and videos into albums using Claude AI vision. Runs on the last 30 days of unsorted photos, up to 200 per batch.

## Step 1 — Find the script

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "photo_sorter.py" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && SCRIPT=$(find ~ -maxdepth 4 -name "photo_sorter.py" 2>/dev/null | grep -v ".git" | head -1)
echo "SCRIPT=$SCRIPT"
```

Do not tell the user about this step. Just proceed.

## Step 2 — Check setup

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

If output is `NEEDS_SETUP`: tell the user to run the script directly in their terminal to complete the one-time setup. It will ask for their name, context, and album definitions. The script cannot prompt interactively through Claude Code.

```
python3 /path/to/photo-sorter/photo_sorter.py
```

(Use the path from `SCRIPT=` in Step 1.)

If output is `CONFIGURED`: proceed to Step 3.

## Step 3 — Run

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 "$SCRIPT" 2>&1
```

## Step 4 — Report back

After running, tell the user:
- How many photos/videos were sorted and how many were skipped
- Which albums received new photos (if logged)
- The current mode (auto or assisted)
- Whether the batch limit was hit and they need to run again
- Any errors or warnings
