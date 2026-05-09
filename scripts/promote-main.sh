#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: scripts/promote-main.sh <release-title> [issue-numbers]"
  echo "Example: scripts/promote-main.sh \"Release: week 1 gameplay update\" \"12 15 18\""
}

if [ "$#" -lt 1 ]; then
  usage
  exit 1
fi

release_title="$1"
issue_numbers="${2:-}"

git fetch origin

if git show-ref --verify --quiet refs/heads/dev; then
  git switch dev
elif git show-ref --verify --quiet refs/remotes/origin/dev; then
  git switch --track origin/dev
else
  echo "origin/dev does not exist."
  exit 1
fi

git pull --ff-only origin dev
git push origin dev

closing_lines=""
for issue in $issue_numbers; do
  if [[ "$issue" =~ ^[0-9]+$ ]]; then
    closing_lines="$closing_lines
Closes #$issue"
  fi
done

body="## 릴리스 내용

dev 브랜치에서 검증한 변경사항을 main에 반영합니다.
$closing_lines

## 확인한 내용

- [ ] dev 브랜치에서 실행 또는 빌드 확인
- [ ] 주요 게임 흐름 확인
- [ ] 릴리스에 포함할 이슈 확인"

if command -v gh >/dev/null 2>&1; then
  gh pr create \
    --base main \
    --head dev \
    --title "$release_title" \
    --body "$body"
else
  echo "GitHub CLI 'gh' is not installed or not available."
  echo "Create the PR manually: dev -> main"
fi
