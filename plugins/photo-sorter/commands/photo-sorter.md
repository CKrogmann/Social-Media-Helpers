---
description: Auto-sort your Photos library into custom albums using Claude AI vision
---

# Photo Sorter

Sorts your iPhone/Mac photos and videos into albums using Claude AI vision. Processes the last 30 days of unsorted photos, up to 200 per batch.

## Find the script

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "photo_sorter.py" 2>/dev/null | head -1)
if [ -z "$SCRIPT" ]; then
  SCRIPT=$(find ~/social-media-helpers -name "photo_sorter.py" 2>/dev/null | head -1)
fi
echo "SCRIPT: $SCRIPT"
```

If no script is found, tell the user to install from: https://github.com/CKrogmann/Social-Media-Helpers

## Check setup

```bash
python3 -c "
import json
from pathlib import Path
cfg = Path.home() / '.photo_sorter_config.json'
if cfg.exists():
    data = json.load(open(cfg))
    albums = data.get('albums', {})
    print('CONFIGURED' if albums else 'NEEDS_SETUP')
    if albums:
        print(f'User: {data.get(\"user_name\", \"unknown\")}')
        print(f'Albums: {[v[\"name\"] for v in albums.values()]}')
else:
    print('NEEDS_SETUP')
"
```

If `NEEDS_SETUP`: tell the user they need to run the script once directly in their terminal to complete the one-time setup (it will ask for their name, context, and album definitions). It cannot prompt interactively through Claude Code:

```
python3 ~/.claude/plugins/cache/social-media-helpers/photo-sorter/latest/src/photo_sorter.py
```

Or if running from a cloned repo: `python3 ~/social-media-helpers/photo-sorter/photo_sorter.py`

## Run

```bash
python3 "$SCRIPT" 2>&1
```

## Report back

Tell the user:
- How many photos/videos were sorted and skipped
- Which albums received new items
- Current mode (auto or assisted)
- Whether the 200-photo batch limit was hit and they need to run again
- Any errors
