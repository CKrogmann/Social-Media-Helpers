---
name: viral-content-analysis
description: Track competitor Instagram accounts and surface top-performing posts, hooks, and formats into Notion. Use when asked to run viral content analysis, check competitors, or update the content tracker.
allowed-tools: Bash(python3 *), Bash(find *)
---

## Viral Content Analysis

Scrapes public Instagram accounts the user has configured, identifies top posts (1M+ views or top 20% engagement), analyses hooks and formats with Claude, and pushes findings to three Notion databases. First run = 180-day lookback. Subsequent runs = 90-day rolling refresh.

## Step 1 — Find the script

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "viral_content_analysis.py" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && SCRIPT=$(find ~ -maxdepth 4 -name "viral_content_analysis.py" 2>/dev/null | grep -v ".git" | head -1)
echo "SCRIPT=$SCRIPT"
```

Do not tell the user about this step. Just proceed.

## Step 2 — Check setup

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
        if not accounts: missing.append('accounts to track')
        if not has_notion: missing.append('Notion credentials')
        print(f'NEEDS_SETUP: missing {\", \".join(missing)}')
else:
    print('NEEDS_SETUP')
"
```

If output is `NEEDS_SETUP`: tell the user to run the script directly in their terminal. It will walk them through entering the Instagram accounts they want to track and their Notion credentials:

```
python3 /path/to/viral-content-analysis/viral_content_analysis.py
```

(Use the path from `SCRIPT=` in Step 1.)

If `CONFIGURED`: proceed to Step 3.

## Step 3 — Run

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 "$SCRIPT" 2>&1
```

This may take several minutes depending on how many accounts are being tracked.

## Step 4 — Report back

After running, tell the user:
- How many accounts were analysed
- How many viral posts were found and pushed to Notion
- How many content patterns were identified
- The lookback window used (180 days = first run, 90 days = recurring)
- Any accounts that were rate-limited or failed
- Where to find results (Notion page name/link if available in the output)
