#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: scripts/start-task.sh <issue-number> <feature|improvement|bugfix|docs|chore> <slug>"
  echo "Example: scripts/start-task.sh 12 feature player-jump"
}

if [ "$#" -ne 3 ]; then
  usage
  exit 1
fi

issue_number="$1"
kind="$2"
slug="$3"

case "$kind" in
  feature|improvement|bugfix|docs|chore) ;;
  *)
    echo "Invalid kind: $kind"
    usage
    exit 1
    ;;
esac

if ! [[ "$issue_number" =~ ^[0-9]+$ ]]; then
  echo "Issue number must be numeric."
  exit 1
fi

if ! [[ "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Slug must use lowercase letters, numbers, and hyphens only."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Working tree has uncommitted changes. Commit or stash them first."
  exit 1
fi

git fetch origin

if git show-ref --verify --quiet refs/heads/dev; then
  git switch dev
elif git show-ref --verify --quiet refs/remotes/origin/dev; then
  git switch --track origin/dev
else
  echo "origin/dev does not exist yet. Create and push dev before starting tasks."
  exit 1
fi

git pull --ff-only origin dev

branch_name="$kind/$issue_number-$slug"

if git show-ref --verify --quiet "refs/heads/$branch_name"; then
  echo "Local branch already exists: $branch_name"
  exit 1
fi

git switch -c "$branch_name"

echo "Ready on $branch_name"
