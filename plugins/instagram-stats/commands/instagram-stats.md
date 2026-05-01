---
description: Refresh Instagram post and reel stats in an Excel planning sheet via the Instagram Graph API
---

# Instagram Stats Updater

Pulls your Instagram post and reel metrics into an Excel file. Updates a rolling 90-day window each run.

## Step 1 — Find the script

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "instagram_stats_updater.py" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && SCRIPT=$(find ~/social-media-helpers -name "instagram_stats_updater.py" 2>/dev/null | head -1)
echo "${SCRIPT:-NOT_FOUND}"
```

If `NOT_FOUND`, tell the user the plugin isn't installed and stop.

## Step 2 — Check config

```bash
python3 -c "
import json, os
p = os.path.expanduser('~/.instagram_stats_config.json')
if os.path.exists(p):
    cfg = json.load(open(p))
    print('CONFIGURED' if cfg.get('access_token') else 'NEEDS_TOKEN')
else:
    print('NEEDS_SETUP')
"
```

## Step 3 — If CONFIGURED, skip to Step 5.

## Step 4 — If NEEDS_SETUP or NEEDS_TOKEN, guide the user through setup

Tell the user warmly:

> To pull your Instagram stats, I need a token that gives me read access to your account. Here's how to get one — it takes about 2 minutes:
>
> 1. Go to **[developers.facebook.com](https://developers.facebook.com)**
> 2. Open your app (it may be called something like "Celina Stats" or "Instagram Stats")
> 3. In the left sidebar, click **Instagram** → **Generate Access Token**
> 4. Follow the prompts to connect your Instagram account
> 5. Copy the token that appears — it's a long string starting with `EAA...`
>
> Once you have it, paste it here and I'll set everything up for you.

Then wait for the user to paste their token. When they do:

1. Ask for their Instagram user ID if you don't already know it. Tell them:
   > I also need your Instagram User ID (a number like `17841401302003364`). You can find it by going to your Facebook Developer app → Instagram → and looking for "Instagram User ID" or "Business Account ID".

2. Once you have both values, write the config file:

```bash
python3 -c "
import json, os
from datetime import datetime, timezone, timedelta
cfg = {
    'access_token': 'PASTE_TOKEN_HERE',
    'ig_user_id': 'PASTE_USER_ID_HERE',
    'app_id': os.getenv('INSTAGRAM_APP_ID', ''),
    'app_secret': os.getenv('INSTAGRAM_APP_SECRET', ''),
    'token_expires': (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
    'last_run': None
}
with open(os.path.expanduser('~/.instagram_stats_config.json'), 'w') as f:
    json.dump(cfg, f, indent=2)
print('Config saved.')
"
```

Replace `PASTE_TOKEN_HERE` and `PASTE_USER_ID_HERE` with the actual values before running.

3. Confirm: "All set! Running your stats now..."

## Step 5 — Check for Excel file

```bash
ls ~/Desktop/"Celina Krogmann SM Planning.xlsx" 2>/dev/null || \
ls ~/"Celina Krogmann SM Planning.xlsx" 2>/dev/null || \
find ~ -maxdepth 3 -name "*.xlsx" 2>/dev/null | head -5
```

If the Excel file isn't found at the expected path, ask the user where their planning spreadsheet is saved and note it for them. The script writes to `~/Celina Krogmann SM Planning.xlsx` by default — if theirs is elsewhere, tell them to move or rename it there.

## Step 6 — Run

```bash
INSTAGRAM_APP_ID="${INSTAGRAM_APP_ID}" INSTAGRAM_APP_SECRET="${INSTAGRAM_APP_SECRET}" python3 "$SCRIPT" 2>&1
```

## Step 7 — Report back

Tell the user in plain language:
- How many posts and reels were fetched
- How many rows were updated in the Excel file
- Where the file is saved (full path)
- Whether their token was auto-refreshed
- If anything went wrong, explain it simply and what to do next
