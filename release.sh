#!/bin/bash
# Bump versions across all plugin files and push to GitHub.
# Usage: bash release.sh 1.2.0

set -e

NEW_VERSION="${1}"

if [ -z "$NEW_VERSION" ]; then
  # Auto-increment patch version from current marketplace.json
  CURRENT=$(grep -m1 '"version"' .claude-plugin/marketplace.json | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
  MAJOR=$(echo "$CURRENT" | cut -d. -f1)
  MINOR=$(echo "$CURRENT" | cut -d. -f2)
  PATCH=$(echo "$CURRENT" | cut -d. -f3)
  NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
  echo "Auto-incrementing $CURRENT → $NEW_VERSION"
fi

echo "Releasing version $NEW_VERSION..."

# Update the three plugin.json files
for plugin in photo-sorter viral-content-analysis instagram-stats; do
  FILE="plugins/$plugin/.claude-plugin/plugin.json"
  sed -i '' "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$FILE"
  echo "  ✓ $FILE"
done

# Update the three entries in marketplace.json
sed -i '' "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/g" .claude-plugin/marketplace.json
echo "  ✓ .claude-plugin/marketplace.json"

# Commit and push
git add plugins/photo-sorter/.claude-plugin/plugin.json \
        plugins/viral-content-analysis/.claude-plugin/plugin.json \
        plugins/instagram-stats/.claude-plugin/plugin.json \
        .claude-plugin/marketplace.json

git commit -m "Release v$NEW_VERSION"
git push origin main

echo ""
echo "Done! v$NEW_VERSION is live. Users will see the Update button on next marketplace refresh."
