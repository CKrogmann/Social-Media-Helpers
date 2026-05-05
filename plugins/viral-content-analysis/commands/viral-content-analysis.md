---
description: Track competitor Instagram accounts and surface top-performing posts, hooks, and formats into Notion
---

## Viral Content Analysis

Scrapes public Instagram accounts the user has configured, identifies top posts (1M+ views or top 20% engagement), analyses hooks and formats with Claude, and pushes findings to three Notion databases. First run = 180-day lookback. Subsequent runs = 90-day rolling refresh.

---

## Step 1 — Find or install the script (silent)

Do not mention this step to the user.

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "viral_content_analysis.py" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && SCRIPT=$(find ~ -maxdepth 4 -name "viral_content_analysis.py" 2>/dev/null | grep -v ".git" | head -1)
if [ -z "$SCRIPT" ]; then
  git clone https://github.com/CKrogmann/Social-Media-Helpers ~/social-media-helpers 2>&1 | tail -3
  SCRIPT="$HOME/social-media-helpers/viral-content-analysis/viral_content_analysis.py"
fi
echo "SCRIPT=$SCRIPT"
```

Then install dependencies silently:

```bash
pip3 install anthropic requests imageio-ffmpeg instaloader -q 2>&1 | tail -5
```

---

## Step 2 — Check if already configured

```bash
python3 -c "
import json
from pathlib import Path
cfg_path = Path.home() / '.viral_content_config.json'
if cfg_path.exists():
    cfg = json.load(open(cfg_path))
    accounts = cfg.get('accounts', [])
    has_notion = bool(cfg.get('notion_token') and cfg.get('notion_page_id'))
    if accounts and has_notion:
        print('CONFIGURED')
        print(f'Accounts: {accounts}')
        print(f'Last run: {cfg.get(\"last_run\", \"never\")}')
    else:
        missing = []
        if not accounts: missing.append('accounts')
        if not has_notion: missing.append('Notion credentials')
        print(f'NEEDS_SETUP: {\" + \".join(missing)}')
else:
    print('NEEDS_SETUP')
"
```

If `CONFIGURED` → jump to **Step 5**.

If `NEEDS_SETUP` → continue to **Step 3**.

---

## Step 3 — Collect accounts

Tell the user:

> **Which Instagram accounts do you want to track?**
>
> Enter the handles you want to analyse — these should be public accounts in your niche (competitors, inspiration accounts, top creators). No @ needed.
>
> Example: `garyvee, hubspot, later, socialmediaexaminer`
>
> You can always add more later by editing `~/.viral_content_config.json`.

Wait for the user's response. Parse the handles from whatever they type (comma-separated, space-separated, or one per line — strip @ symbols). Save the list for Step 4c.

---

## Step 4 — Collect Notion credentials

### 4a — Integration token

Tell the user:

> **Now let's connect Notion — this is where your viral post data and content patterns will live.**
>
> **Step 1: Create a Notion integration**
> 1. Open [notion.so/my-integrations](https://www.notion.so/my-integrations) in your browser
> 2. Click **+ New integration**
> 3. Give it any name (e.g. "Content Tracker") and click **Submit**
> 4. Copy the token shown on the next screen — it starts with `secret_`
>
> **Paste your Notion integration token here:**

Wait for the token. Validate it starts with `secret_` — if not, ask them to double-check they copied the full token.

### 4b — Notion page ID

Tell the user:

> **Step 2: Create a Notion page and connect the integration**
> 1. Open Notion and create a new blank page (this is where your three databases will be built — Viral Posts, Content Patterns, and Niche Journey)
> 2. On that page, click the **···** menu in the top right → **Connections** → find your integration and click **Connect**
> 3. Copy the page URL from your browser — it looks like:
>    `https://notion.so/Your-Page-Title-abc123def456ghij`
> 4. Your **page ID** is the last part of that URL after the final `-` or `/`:
>    In the example above it would be `abc123def456ghij`
>    _(If there's a `?v=...` at the end, ignore everything from the `?` onwards)_
>
> **Paste your Notion page URL or page ID here:**

Wait for their response. If they paste a full URL, extract the page ID from it (the 32-character hex string, possibly with hyphens). If they paste the ID directly, use it as-is.

### 4c — Write the config file

Once you have accounts, token, and page ID, write the config silently:

```bash
python3 - << 'PYEOF'
import json, os, sys

accounts   = ACCOUNTS_LIST_HERE      # replace with Python list e.g. ["garyvee", "hubspot"]
token      = "NOTION_TOKEN_HERE"
page_id    = "NOTION_PAGE_ID_HERE"

cfg = {
    "accounts":                accounts,
    "notion_token":            token,
    "notion_page_id":          page_id,
    "notion_viral_posts_db":   None,
    "notion_patterns_db":      None,
    "notion_niche_journey_db": None,
    "last_run":                None,
    "niche_journey_completed": [],
    "thresholds": {
        "reel_views": 1000000,
        "top_pct":    0.20,
    },
}
with open(os.path.expanduser("~/.viral_content_config.json"), "w") as f:
    json.dump(cfg, f, indent=2)
print(f"Config saved. Tracking {len(accounts)} accounts.")
PYEOF
```

After writing, tell the user:

> ✓ All set! Starting your first analysis now — this looks back 180 days across all your accounts and may take 10–20 minutes depending on how many posts are found. I'll keep you updated as it runs.

---

## Step 5 — Run the analysis

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 "$SCRIPT" 2>&1
```

---

## Step 6 — Report back

After running, summarise for the user in plain language:
- How many accounts were analysed
- How many viral posts were found and pushed to Notion
- How many content patterns were identified
- The lookback window used (180 days = first run, 90 days = recurring)
- Any accounts that were skipped (rate-limited, private, or not found)
- Tell them to open Notion and check their three new databases: **Viral Posts**, **Content Patterns**, and **Niche Journey**
