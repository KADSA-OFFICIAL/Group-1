# GitHub Workflow

이 문서는 Group-1 프로젝트에서 새 기능, 개선, 버그 수정, 문서 작업을 시작하고 마무리하는 표준 흐름입니다. 이 저장소는 [AGENTS.md](../AGENTS.md)의 issue-first harness를 기준으로 작업합니다.

## 브랜치 역할

| 브랜치 | 역할 |
| --- | --- |
| `main` | 안정 버전. 실제 제출, 발표, 배포 기준입니다. |
| `dev` | 개발 통합 브랜치. 완료된 작업 브랜치를 먼저 모읍니다. |
| `feat-<issue>-<slug>` | 새 기능 작업 브랜치입니다. |
| `fix-<issue>-<slug>` | 버그 수정 작업 브랜치입니다. |
| `issue-<issue>-<slug>` | 개선, 문서, 설정, 정리 등 일반 작업 브랜치입니다. |

## 기본 흐름

1. GitHub에서 이슈를 만듭니다.
2. 이슈 번호를 기준으로 `dev`에서 로컬 브랜치를 만듭니다.
3. 로컬 브랜치에서 작업합니다.
4. 작업이 끝나면 커밋합니다.
5. 원격 작업 브랜치로 푸시합니다.
6. 작업 브랜치에서 `dev`로 Pull Request를 만듭니다.
7. `dev`에서 확인 후, 문제가 없으면 같은 원격 작업 브랜치에서 `main`으로 Pull Request를 만듭니다.
8. `main`에 머지된 뒤 원격 작업 브랜치를 삭제합니다.

## 이슈 만들기

GitHub의 `Issues -> New issue`에서 작업 종류에 맞는 템플릿을 선택합니다.

- Feature: 새 기능
- Improvement: 기존 기능 개선
- Bug: 버그 수정
- Task: 문서, 설정, 정리 등 일반 작업

이슈 제목 예시:

```text
[Feature] 플레이어 점프 기능 추가
[Improvement] 적 추적 속도 조정
[Bug] 카메라가 벽 근처에서 떨리는 문제
[Task] 프로젝트 폴더 구조 정리
```

## 로컬 작업 시작

이슈를 만든 뒤 아래 명령으로 작업 브랜치를 만듭니다.

```bash
scripts/start-task.sh 12 feat player-jump
```

위 명령은 `dev`를 최신 상태로 맞춘 뒤 `feat-12-player-jump` 브랜치를 만듭니다.

작업 종류는 다음 중 하나를 사용합니다.

```text
feat
fix
issue
```

## 작업 마무리

작업이 끝나면 아래 명령으로 커밋, 푸시, `dev` 대상 PR 생성을 진행합니다.

```bash
scripts/finish-task.sh 12 "Add player jump"
```

이 스크립트는 현재 브랜치의 변경사항을 커밋하고, 원격 브랜치로 푸시한 뒤 GitHub CLI가 준비되어 있으면 `dev` 대상 PR을 만듭니다.

PR 본문에는 `Closes #12`를 포함합니다. GitHub는 기본 브랜치인 `main`에 머지될 때 이슈를 닫습니다.

## main 반영

`dev`에 머지된 작업이 안정적이면 같은 작업 브랜치에서 아래 명령으로 `main` 대상 PR을 만듭니다.

```bash
scripts/promote-main.sh 12 "Add player jump"
```

이 명령은 현재 작업 브랜치를 원격에 다시 푸시하고, GitHub CLI가 준비되어 있으면 `main` 대상 PR을 만듭니다.

## PR 규칙

- 작업 PR의 base branch는 `dev`입니다.
- main 반영 PR의 base branch는 `main`, compare branch는 같은 원격 작업 브랜치입니다.
- PR에는 테스트/확인 내용을 적습니다.
- 게임 플레이에 영향이 있으면 가능하면 스크린샷이나 짧은 녹화도 첨부합니다.
- 충돌이 나면 작업 브랜치에서 `dev`를 먼저 반영한 뒤 다시 푸시합니다.
