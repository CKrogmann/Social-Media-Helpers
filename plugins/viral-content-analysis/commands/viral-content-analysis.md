---
description: Track competitor Instagram accounts and surface top-performing posts, hooks, and formats into Notion
---

# Viral Content Analysis

Scrapes public Instagram accounts you define, identifies top posts by views and engagement, analyzes hooks and content formats with Claude, and pushes findings into three Notion databases. First run = 180-day lookback. Monthly runs = 90-day refresh.

## Find the script

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "viral_content_analysis.py" 2>/dev/null | head -1)
if [ -z "$SCRIPT" ]; then
  SCRIPT=$(find ~/social-media-helpers -name "viral_content_analysis.py" 2>/dev/null | head -1)
fi
echo "SCRIPT: $SCRIPT"
```

If no script is found, tell the user to install from: https://github.com/CKrogmann/Social-Media-Helpers

## Check setup

```bash
python3 -c "
import json, os
from pathlib import Path
cfg = Path.home() / '.viral_content_config.json'
if cfg.exists():
    data = json.load(open(cfg))
    accounts = data.get('accounts', [])
    has_notion = bool(data.get('notion_token') and data.get('notion_page_id'))
    if accounts and has_notion:
        print('CONFIGURED')
        print(f'Accounts: {accounts}')
        print(f'Last run: {data.get(\"last_run\", \"never\")}')
    else:
        missing = []
        if not accounts: missing.append('accounts')
        if not has_notion: missing.append('Notion credentials')
        print(f'NEEDS_SETUP: missing {\", \".join(missing)}')
else:
    print('NEEDS_SETUP')
"
```

If `NEEDS_SETUP`: tell the user to run the script directly in their terminal to complete setup — it will walk them through adding accounts and Notion credentials interactively.

## Run

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 "$SCRIPT" 2>&1
```

This may take several minutes depending on how many accounts are tracked.

## Report back

Tell the user:
- How many accounts were analyzed
- How many viral posts were found and pushed to Notion
- How many content patterns were identified
- Lookback window used (180 days first run, 90 days after)
- Any rate-limited or failed accounts
