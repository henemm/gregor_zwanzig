#!/usr/bin/env bash
# Dumps all open GitHub Issues mit Label "for:claude-design" als Markdown-Dateien
# nach docs/claude-design-queue/ — zum Lesen durch Claude Design via github_read_file.
#
# Verwendung: bash scripts/dump-claude-design-issues.sh
# Danach:     git add docs/claude-design-queue/ && git commit && git push

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

QUEUE_DIR="docs/claude-design-queue"
mkdir -p "$QUEUE_DIR"

echo "→ Hole Issue-Liste..."
ISSUE_NUMBERS=$(gh issue list \
  --label "for:claude-design" \
  --state open \
  --limit 100 \
  --json number \
  --jq '.[].number')

if [ -z "$ISSUE_NUMBERS" ]; then
  echo "Keine offenen Issues mit Label 'for:claude-design' gefunden."
  exit 0
fi

echo "→ Schreibe _index.json..."
gh issue list \
  --label "for:claude-design" \
  --state open \
  --limit 100 \
  --json number,title,labels,url,createdAt \
  | python3 -c "
import sys, json
issues = json.load(sys.stdin)
# Sortiert nach Nummer aufsteigend
issues.sort(key=lambda x: x['number'])
print(json.dumps({'generated_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z', 'count': len(issues), 'issues': issues}, indent=2, ensure_ascii=False))
" > "$QUEUE_DIR/_index.json"

echo "→ Schreibe Issue-Dateien..."
for N in $ISSUE_NUMBERS; do
  FILE="$QUEUE_DIR/issue-${N}.md"
  gh issue view "$N" \
    --json number,title,body,labels,url,createdAt \
    | python3 -c "
import sys, json
d = json.load(sys.stdin)
labels = ' '.join('\`' + l['name'] + '\`' for l in d['labels'])
print(f'# #{d[\"number\"]} — {d[\"title\"]}')
print()
print(f'**Labels:** {labels}')
print(f'**URL:** {d[\"url\"]}')
print(f'**Erstellt:** {d[\"createdAt\"][:10]}')
print()
print('---')
print()
print(d['body'])
" > "$FILE"
  echo "  ✓ issue-${N}.md"
done

echo ""
echo "Fertig. $(echo "$ISSUE_NUMBERS" | wc -w) Dateien in $QUEUE_DIR/"
echo ""
echo "Nächste Schritte:"
echo "  git add $QUEUE_DIR/"
echo "  git commit -m 'chore: update claude-design-queue'"
echo "  git push origin main"
