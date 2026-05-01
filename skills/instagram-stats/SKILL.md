---
name: instagram-stats
description: Refresh Instagram post and reel stats in the Excel planning sheet via the Instagram Graph API. Use when asked to update Instagram stats, refresh analytics, or run the stats updater.
allowed-tools: Bash(python3 *)
---

## Instagram Stats Updater

Pulls your Instagram post and reel metrics (likes, comments, reach, saves, shares, views) into an Excel file. Updates a rolling 90-day window each run. Preserves any manually entered fields.

**Output:** `~/Celina Krogmann SM Planning.xlsx`

## Check setup

```bash
python3 -c "
import json, os
from datetime import datetime, timezone
cfg_path = os.path.expanduser('~/.instagram_stats_config.json')
if os.path.exists(cfg_path):
    cfg = json.load(open(cfg_path))
    has_token = bool(cfg.get('access_token'))
    has_app = bool(os.getenv('INSTAGRAM_APP_ID') and os.getenv('INSTAGRAM_APP_SECRET'))
    if has_token:
        expires = cfg.get('token_expires', '')
        print('CONFIGURED')
        print(f'Token expires: {expires}')
        print(f'App credentials: {\"via env vars\" if has_app else \"missing — set INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET\"}')
    else:
        print('NEEDS_SETUP: access_token missing in ~/.instagram_stats_config.json')
        print('  Generate a token at developers.facebook.com and add it to the config file.')
else:
    print('NEEDS_SETUP: config file not found')
    print('  Run the script once in your terminal to create it, then add your access_token.')
"
```

If `NEEDS_SETUP`: tell the user to:
1. Go to developers.facebook.com → their app → Instagram → Generate Token
2. Add it to `~/.instagram_stats_config.json` under `"access_token"`

If `CONFIGURED`: proceed to run.

## Run

```bash
INSTAGRAM_APP_ID="$INSTAGRAM_APP_ID" INSTAGRAM_APP_SECRET="$INSTAGRAM_APP_SECRET" python3 ~/social-media-helpers/instagram-stats/instagram_stats_updater.py 2>&1
```

## Report back

After running, tell the user:
- How many posts and reels were fetched
- How many rows were updated in the Excel file
- Whether the access token was refreshed
- Where the file was saved
- Any warnings (e.g. posts outside the 90-day window keeping old stats)
