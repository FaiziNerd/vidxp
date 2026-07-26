#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://github.com/grayhatdevelopers/vidxp/blob/main"
README="README.md"
README_BAK="$README.bak"

echo "📝 Backing up original README..."
cp "$README" "$README_BAK"

echo "🔧 Processing README.md for PyPI rendering..."
python utils/fix_readme_links.py "$BASE_URL" "$README" --inplace

echo "📦 Building package..."
python -m build

echo "♻️ Restoring original README..."
mv "$README_BAK" "$README"

echo "✅ Build finished. Original README restored."
