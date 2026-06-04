#!/usr/bin/env bash
# Verify that the handoff packet arrived intact by comparing file count and
# byte sizes against MANIFEST.txt. Exit 0 = OK, exit 1 = mismatch.
# MANIFEST.txt itself is excluded from the comparison.
set -e
cd "$(dirname "$0")/.."
manifest="claude-code-handoff/MANIFEST.txt"
[ -f "$manifest" ] || { echo "ERR · MANIFEST.txt missing"; exit 1; }

expected_files=$(grep -c "^claude-code-handoff/" "$manifest" || true)
actual_files=$(find claude-code-handoff -type f -not -name 'MANIFEST.txt' | wc -l | tr -d ' ')
echo "Expected files (excl. MANIFEST): $expected_files"
echo "Found    files (excl. MANIFEST): $actual_files"

mismatch=0
while IFS=$'\t' read -r path bytes; do
  [[ "$path" =~ ^# ]] && continue
  [[ -z "$path" ]] && continue
  if [ ! -f "$path" ]; then
    echo "MISS · $path"
    mismatch=1
    continue
  fi
  actual=$(wc -c < "$path" | tr -d ' ')
  if [ "$actual" != "$bytes" ]; then
    echo "SIZE · $path  expected=$bytes actual=$actual"
    mismatch=1
  fi
done < "$manifest"

if [ "$mismatch" -eq 0 ] && [ "$expected_files" = "$actual_files" ]; then
  echo "OK · handoff packet intact"
  exit 0
else
  echo "FAIL · packet incomplete or modified — ask for a fresh zip"
  exit 1
fi
