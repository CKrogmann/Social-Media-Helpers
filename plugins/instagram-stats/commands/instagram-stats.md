---
description: Refresh Instagram post and reel stats in an Excel planning sheet via the Instagram Graph API
---

# Instagram Stats Updater

Pulls your Instagram post and reel metrics (likes, comments, reach, saves, shares, views) into an Excel file. Updates a rolling 90-day window each run. Preserves manually entered fields.

## Find the script

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "instagram_stats_updater.py" 2>/dev/null | head -1)
if [ -z "$SCRIPT" ]; then
  SCRIPT=$(find ~/social-media-helpers -name "instagram_stats_updater.py" 2>/dev/null | head -1)
fi
echo "SCRIPT: $SCRIPT"
```

If no script is found, tell the user to install from: https://github.com/CKrogmann/Social-Media-Helpers

## Check setup

```bash
python3 -c "
import json, os
from datetime import datetime, timezone
cfg_path = os.path.expanduser('~/.instagram_stats_config.json')
if os.path.exists(cfg_path):
    cfg = json.load(open(cfg_path))
    has_token = bool(cfg.get('access_token'))
    print('CONFIGURED' if has_token else 'NEEDS_SETUP: access_token missing')
    if has_token:
        print(f'Token expires: {cfg.get(\"token_expires\", \"unknown\")}')
else:
    print('NEEDS_SETUP: no config file')
"
```

If `NEEDS_SETUP`: tell the user to generate an access token at developers.facebook.com and add it to `~/.instagram_stats_config.json`.

## Run

```bash
INSTAGRAM_APP_ID="$INSTAGRAM_APP_ID" INSTAGRAM_APP_SECRET="$INSTAGRAM_APP_SECRET" python3 "$SCRIPT" 2>&1
```

## Report back

Tell the user:
- How many posts and reels were fetched
- How many rows were updated in the Excel file
- Whether the access token was auto-refreshed
- Where the file was saved
- Any warnings about posts outside the 90-day window
