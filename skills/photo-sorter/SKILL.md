---
name: photo-sorter
description: Auto-sort your Photos library into albums using Claude AI vision. Use when asked to sort photos, organize albums, run the photo sorter, or classify photos.
allowed-tools: Bash(python3 *)
---

## Photo Sorter

Sorts iPhone/Mac photos and videos into albums using Claude AI vision. Runs on the last 30 days of unsorted photos, up to 200 per batch.

## Check setup

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

If output is `NEEDS_SETUP`: tell the user to run the script directly in their terminal first to complete the one-time setup — it will ask for their name, context, and album definitions. The script cannot prompt interactively when run through Claude Code.

```
python3 ~/social-media-helpers/photo-sorter/photo_sorter.py
```

If output is `CONFIGURED`: proceed to run the sorter.

## Run

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 ~/social-media-helpers/photo-sorter/photo_sorter.py 2>&1
```

## Report back

After running, tell the user:
- How many photos/videos were sorted and how many were skipped
- Which albums received new photos (if logged)
- The current mode (auto or assisted)
- Whether the batch limit was hit and they need to run again
- Any errors or warnings
