#!/bin/bash
# Cleanup orphaned worktrees after commit/deploy
# Called manually or as post-workflow step

WORKTREE_DIR=".claude/worktrees"

if [ ! -d "$WORKTREE_DIR" ]; then
  echo "No worktrees directory found"
  exit 0
fi

count=0
for wt in "$WORKTREE_DIR"/agent-*; do
  [ -d "$wt" ] || continue
  # Remove the worktree via git
  git worktree remove "$wt" --force 2>/dev/null
  if [ $? -eq 0 ]; then
    ((count++))
  else
    # Fallback: manual cleanup
    rm -rf "$wt"
    ((count++))
  fi
done

# Prune stale worktree references
git worktree prune 2>/dev/null

echo "Cleaned up $count worktree(s)"
