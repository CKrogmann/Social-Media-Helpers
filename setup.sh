#!/bin/bash
# Install Social Media Helper skills into Claude Code
# Run once: bash setup.sh

SKILLS_DIR="$HOME/.claude/skills"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing Social Media Helper skills..."
mkdir -p "$SKILLS_DIR"

for skill in photo-sorter viral-content-analysis instagram-stats; do
  target="$SKILLS_DIR/$skill"
  source="$REPO_DIR/skills/$skill"

  if [ -L "$target" ]; then
    rm "$target"
  elif [ -d "$target" ]; then
    echo "  ⚠️  $target already exists and is not a symlink — skipping. Remove it manually to reinstall."
    continue
  fi

  ln -s "$source" "$target"
  echo "  ✓ /$(basename $skill) → $source"
done

echo ""
echo "Done. Skills available in Claude Code:"
echo "  /photo-sorter"
echo "  /viral-content-analysis"
echo "  /instagram-stats"
echo ""
echo "Add these to ~/.claude/CLAUDE.md to register them:"
echo ""
echo "## Social Media Helpers"
echo "- \`/photo-sorter\` — auto-sort Photos library into albums using Claude AI"
echo "- \`/viral-content-analysis\` — track competitor Instagram accounts, push to Notion"
echo "- \`/instagram-stats\` — refresh Instagram post stats in Excel"
