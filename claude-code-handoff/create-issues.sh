#!/usr/bin/env bash
# Fallback script — only if you want to run the issue creation manually
# instead of letting Claude Code do it.
#
# Prereqs:
#   - gh CLI installed and authenticated (`gh auth status`)
#   - jq installed
#   - Run this from the repo root (cd /path/to/gregor_zwanzig)
#   - Copy this handoff folder into the repo first (or adjust paths below)
#
# Usage:
#   bash claude-code-handoff/create-issues.sh
#
# What it does:
#   1. Creates missing labels
#   2. Commits screenshots to .github/issue-assets/ and pushes
#   3. Creates the issues from issues.json (count read dynamically via jq)

set -euo pipefail

REPO="henemm/gregor_zwanzig"
HANDOFF="$(cd "$(dirname "$0")" && pwd)"

echo "== Step 1: Ensure labels exist =="
declare -A LABELS=(
  ["design-compliance"]="c45a2a:Design system compliance issue"
  ["foundation"]="8c3e1a:Foundational change — do first"
  ["feature"]="2a6cb3:New feature"
  ["backend-coordination"]="6b675c:Requires backend changes"
  ["breaking-change"]="a83232:Breaking change to existing UX"
  ["ux"]="c08a1a:UX improvement"
  ["bug"]="a83232:Bug fix"
  ["priority:high"]="a83232:High priority"
  ["priority:medium"]="c08a1a:Medium priority"
  ["area:tokens"]="9a958a:"
  ["area:home"]="9a958a:"
  ["area:trips"]="9a958a:"
  ["area:editor"]="9a958a:"
  ["area:alerts"]="9a958a:"
  ["area:reports"]="9a958a:"
  ["area:compare"]="9a958a:"
  ["area:mobile"]="9a958a:"
  ["area:output"]="9a958a:Briefing-Output · Spalten/Detail/Aus-Layout"
  ["accessibility"]="2a6cb3:WCAG-Konformität, Kontrast, Tastatur, Screenreader"
  ["area:sidebar"]="9a958a:"
  ["area:weather"]="9a958a:"
  ["area:components"]="9a958a:"
)
for label in "${!LABELS[@]}"; do
  spec="${LABELS[$label]}"
  color="${spec%%:*}"
  desc="${spec#*:}"
  if ! gh label list --repo "$REPO" --limit 100 | grep -qx "$label	.*"; then
    if [ -n "$desc" ]; then
      gh label create "$label" --color "$color" --description "$desc" --repo "$REPO" || true
    else
      gh label create "$label" --color "$color" --repo "$REPO" || true
    fi
    echo "  + created $label"
  else
    echo "  · $label already exists"
  fi
done

echo
echo "== Step 2: Commit screenshots =="
mkdir -p .github/issue-assets
cp "$HANDOFF"/screenshots/*.png .github/issue-assets/
if git diff --quiet --cached -- .github/issue-assets/ && git diff --quiet -- .github/issue-assets/; then
  echo "  · no changes to commit"
else
  git add .github/issue-assets/
  git commit -m "chore(design): add design-compliance issue screenshots"
  git push origin "$(git rev-parse --abbrev-ref HEAD)"
fi

echo
echo "  Waiting 5s for raw.githubusercontent.com propagation…"
sleep 5

echo
echo "== Step 3: Create issues =="
ISSUES_JSON="$HANDOFF/issues.json"
count="$(jq 'length' "$ISSUES_JSON")"

for i in $(seq 0 $((count - 1))); do
  title="$(jq -r ".[$i].title" "$ISSUES_JSON")"
  body_file="$HANDOFF/$(jq -r ".[$i].body_file" "$ISSUES_JSON")"
  label_args=()
  while IFS= read -r label; do
    label_args+=(--label "$label")
  done < <(jq -r ".[$i].labels[]" "$ISSUES_JSON")

  echo "  [$i] $title"
  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    "${label_args[@]}" \
    --body-file "$body_file"
done

echo
echo "== Done. List all created issues =="
gh issue list --repo "$REPO" --label "design-compliance" --limit 20
