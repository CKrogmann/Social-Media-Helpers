---
description: Refresh Instagram post and reel stats in an Excel spreadsheet via the Instagram Graph API
---

# Instagram Stats Updater

## Step 1 — Find or install the script (silent)

Do not mention this step to the user.

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "instagram_stats_updater.py" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && SCRIPT=$(find ~ -maxdepth 4 -name "instagram_stats_updater.py" 2>/dev/null | grep -v ".git" | head -1)
if [ -z "$SCRIPT" ]; then
  git clone https://github.com/CKrogmann/Social-Media-Helpers ~/social-media-helpers 2>&1 | tail -3
  SCRIPT="$HOME/social-media-helpers/instagram-stats/instagram_stats_updater.py"
fi
echo "SCRIPT=$SCRIPT"
```

Install dependencies silently:

```bash
pip3 install requests openpyxl -q 2>&1 | tail -3
```

---

## Step 2 — Check if already configured

```bash
python3 -c "
import json, os
p = os.path.expanduser('~/.instagram_stats_config.json')
cfg = json.load(open(p)) if os.path.exists(p) else {}
ready = bool(cfg.get('access_token') and cfg.get('ig_user_id') and cfg.get('excel_path'))
print('READY' if ready else 'NEEDS_SETUP')
"
```

If `READY` → jump to **Step 5**.

If `NEEDS_SETUP` → continue to **Step 3**.

---

## Step 3 — Get the access token

Tell the user:

> **To pull your Instagram stats I need an access token — a secure key that lets me read your post data.**
>
> **How to get yours (takes ~2 minutes):**
>
> 1. Go to [developers.facebook.com](https://developers.facebook.com) and log in with your Facebook account
> 2. Click **My Apps** → open your app (or create one: **Create App → Other → Business**)
> 3. In the left menu click **Instagram** → click **Generate Access Token**
> 4. Log in with your Instagram account when prompted
> 5. Copy the long token that appears
>
> **Paste your access token here:**

Wait for the token.

---

## Step 4 — Fetch account + create spreadsheet

Once you have the token, fetch the Instagram user ID automatically and set up the Excel file:

```bash
python3 - << 'PYEOF'
import json, os, requests, openpyxl, sys
from datetime import datetime, timezone, timedelta

token = "ACCESS_TOKEN_HERE"
base  = "https://graph.facebook.com/v25.0"

# Fetch user ID from token
r = requests.get(f"{base}/me", params={"fields": "id,name", "access_token": token}).json()
if "id" not in r:
    print(f"ERROR: Could not connect — {r.get('error', {}).get('message', 'invalid token')}")
    sys.exit(1)

ig_id   = r["id"]
ig_name = r.get("name", "")
print(f"Connected: {ig_name} (ID: {ig_id})")

# Create Excel file
year        = datetime.now().year
excel_path  = os.path.expanduser(f"~/Instagram Stats {year}.xlsx")
if not os.path.exists(excel_path):
    post_headers = ["Post Date","Content Pillar","Asset","Format","Views","Reach","Avg Reach","Views/Reach","Interactions","Interaction Rate","Likes","Saves","Shares","Profile Visits","Follows","Follow Rate","% Men","% Women","","Score"]
    reel_headers = ["Post Date","Content Pillar","Series","Asset","Hook","Views","Reach","Avg Reach","Views/Reach","Interactions","Interaction Rate","Likes","Saves","Shares","Follows","Follow Rate","% Men","% Women","","Score"]
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(f"Instagram Posts {year}"); ws.append(post_headers)
    ws = wb.create_sheet(f"Instagram Reels {year}"); ws.append(reel_headers)
    wb.save(excel_path)
    print(f"Created: {excel_path}")
else:
    print(f"Using existing: {excel_path}")

# Write config
cfg = {
    "access_token":  token,
    "ig_user_id":    ig_id,
    "app_id":        os.getenv("INSTAGRAM_APP_ID", ""),
    "app_secret":    os.getenv("INSTAGRAM_APP_SECRET", ""),
    "token_expires": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
    "last_run":      None,
    "excel_path":    excel_path,
}
with open(os.path.expanduser("~/.instagram_stats_config.json"), "w") as f:
    json.dump(cfg, f, indent=2)
print("Config saved.")
PYEOF
```

Replace `ACCESS_TOKEN_HERE` with the token the user pasted.

If the script prints `ERROR:` — tell the user their token looks invalid and ask them to double-check they copied the full token and try again.

If successful, tell the user:

> ✓ Connected! Pulling your stats now and building your spreadsheet...

---

## Step 5 — Run the script

```bash
python3 "$SCRIPT" 2>&1
```

---

## Step 6 — Report back in plain English

Tell the user:
- How many posts and reels were pulled from Instagram
- The full path to their Excel file
- Whether the token was refreshed automatically
- If anything went wrong, explain what happened and what to do — no technical jargon
