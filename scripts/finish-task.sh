#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: scripts/finish-task.sh <issue-number> <commit-message>"
  echo "Example: scripts/finish-task.sh 12 \"Add player jump\""
}

if [ "$#" -lt 2 ]; then
  usage
  exit 1
fi

issue_number="$1"
shift
commit_message="$*"

if ! [[ "$issue_number" =~ ^[0-9]+$ ]]; then
  echo "Issue number must be numeric."
  exit 1
fi

branch_name="$(git branch --show-current)"

case "$branch_name" in
  main|dev|"")
    echo "Run this from a task branch, not from '$branch_name'."
    exit 1
    ;;
esac

if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "$commit_message"
else
  echo "No local changes to commit. Continuing with push and PR creation."
fi

git push -u origin "$branch_name"

if command -v gh >/dev/null 2>&1; then
  gh pr create \
    --base dev \
    --head "$branch_name" \
    --title "$commit_message" \
    --body "Refs #$issue_number

## 변경 내용

-

## 확인한 내용

- [ ] 로컬에서 실행 또는 빌드 확인
- [ ] 기존 기능 영향 확인"
else
  echo "GitHub CLI 'gh' is not installed or not available."
  echo "Create the PR manually: $branch_name -> dev"
fi
