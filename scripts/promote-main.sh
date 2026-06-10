#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: scripts/promote-main.sh <issue-number> <pr-title>"
  echo "Example: scripts/promote-main.sh 12 \"Add player jump\""
}

if [ "$#" -lt 2 ]; then
  usage
  exit 1
fi

issue_number="$1"
shift
pr_title="$*"

if ! [[ "$issue_number" =~ ^[0-9]+$ ]]; then
  echo "Issue number must be numeric."
  exit 1
fi

branch_name="$(git branch --show-current)"

case "$branch_name" in
  main|dev|"")
    echo "Run this from the issue branch after it has already been merged into dev."
    exit 1
    ;;
esac

git fetch origin
git push -u origin "$branch_name"

body="Closes #$issue_number

## Summary

dev에서 검증한 이슈 브랜치를 main에 반영합니다.

## Verification

- [ ] dev 브랜치에서 동작 확인
- [ ] main 반영 전 충돌 확인

## Notes and Risks

-"

if command -v gh >/dev/null 2>&1; then
  gh pr create \
    --base main \
    --head "$branch_name" \
    --title "$pr_title" \
    --body "$body"
else
  echo "GitHub CLI 'gh' is not installed or not available."
  echo "Create the PR manually: $branch_name -> main"
fi
