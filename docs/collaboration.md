# 2인 협업 가이드

Group-1은 두 명이 함께 작업하는 Godot 4 프로젝트입니다. 이 문서는 두 사람이 충돌 없이,
검증된 코드만 `main`에 남기도록 일하는 방법을 정리합니다. 규칙의 근거는
[CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md)의 issue-first 하네스이고,
명령 흐름은 [github-workflow.md](github-workflow.md)에 있습니다.

## 브랜치 모델

```
feat/fix/issue-<번호>-<주제>   ← 각자 작업하는 일회용 브랜치
        │  (PR)
        ▼
       dev                     ← 통합/테스트. 먼저 여기 모아서 확인
        │  (PR, 검증 후)
        ▼
       main                    ← 안정 버전. 발표/제출 기준. 항상 실행 가능 상태 유지
```

- `main`에는 **검증을 마친 코드만** 들어갑니다. 직접 커밋 금지, 항상 PR로.
- `dev`에서 먼저 합쳐 보고, Godot에서 실행해 문제가 없을 때만 `main`으로 올립니다.
- 작업 브랜치는 **이슈 1개당 1개**, 끝나면 삭제합니다.

## 하루 작업 흐름

```bash
# 1. GitHub에서 이슈 생성 (템플릿: Feature / Improvement / Bug / Task)

# 2. 이슈 번호로 dev에서 작업 브랜치 시작 (dev를 최신화한 뒤 분기)
scripts/start-task.sh 12 feat player-jump

# 3. 작업 + Godot에서 확인

# 4. 커밋·푸시하고 dev 대상 PR 생성
scripts/finish-task.sh 12 "Add player jump"

# 5. dev에서 확인되면 같은 브랜치에서 main 대상 PR 생성
scripts/promote-main.sh 12 "Add player jump"

# 6. main 머지 후 원격 작업 브랜치 삭제
```

## 두 명이 부딪히지 않으려면

- **작업 시작 전에 이슈를 자기 앞으로 assign**해서 누가 무엇을 하는지 드러냅니다.
- 가능하면 **서로 다른 씬/스크립트 파일**을 건드리도록 이슈를 나눕니다.
  Godot의 `.tscn` 파일은 충돌이 나면 손으로 합치기 까다롭습니다.
- 항상 **`start-task.sh`로 시작**하세요. 이 스크립트가 `dev`를 최신으로 당겨오므로
  상대의 최근 작업 위에서 시작하게 됩니다.
- 충돌이 나면 작업 브랜치에서 `dev`를 먼저 머지해 해결한 뒤 다시 푸시합니다.
  (`git merge origin/dev` → 충돌 해결 → 커밋 → 푸시)
- 상대의 PR은 **CODEOWNERS 기준으로 자동 지정된 리뷰**를 한 번씩 봐 줍니다.

## 최초 1회 GitHub 설정 (저장소 관리자)

아래는 한 번만 해두면 2인 협업이 안전해지는 설정입니다.

### 1) 공동작업자 초대
`Settings → Collaborators` 에서 상대를 Write 권한으로 초대합니다.

### 2) `main`, `dev` 브랜치 보호
`Settings → Branches → Add branch ruleset`(또는 Branch protection rules)에서
`main`과 `dev` 각각에 대해:

- Require a pull request before merging (직접 푸시 차단)
- Require approvals: 1 (상대 1명 승인)
- Require review from Code Owners
- Require branches to be up to date before merging
- Do not allow bypassing the above settings

gh CLI로도 설정할 수 있습니다(관리자 권한 필요):

```bash
gh api -X PUT repos/KADSA-OFFICIAL/Group-1/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_pull_request_reviews[required_approving_review_count]=1' \
  -f 'required_pull_request_reviews[require_code_owner_reviews]=true' \
  -F 'enforce_admins=true' \
  -F 'required_status_checks=null' \
  -F 'restrictions=null'
# dev 도 동일하게 branches/dev/protection 으로 반복
```

### 3) CODEOWNERS 확인
[.github/CODEOWNERS](../.github/CODEOWNERS)에 두 멤버(`@LouizXT`, `@1jealy`)가
모두 들어 있는지 확인합니다. 멤버가 바뀌면 사용자명을 갱신합니다.

### 4) PR 머지 방식
`Settings → General → Pull Requests`에서 "Allow squash merging"만 켜두면
`main` 히스토리가 깔끔하게 유지됩니다.
