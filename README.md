# Group-1

2D 공포 방탈출 게임 프로젝트입니다. 주인공은 국어책을 가지러 밤의 학교에 갔다가, 창문 너머로 시체를 묻는 수위 아저씨를 목격하고 학교 안에 갇히게 됩니다.

## 실행 씬

- 메인 씬: `res://scenes/main/main.tscn`
- 이동: `WASD` 또는 방향키
- 조사/상호작용: `E`

## 협업용 씬 분리

- 배경/맵: `scenes/background`
- 플레이어: `scenes/player`
- UI: `scenes/ui`
- 게임 상태/조립: `scenes/main`, `scripts/game`

자세한 규칙은 `docs/scene_structure.md`를 참고하세요.

## 협업 워크플로우

2인 협업은 `feat/fix/issue → dev → main` 흐름을 따릅니다. 검증된 코드만 `main`에 들어갑니다.

- 2인 협업 가이드: `docs/collaboration.md`
- 명령 흐름(스크립트): `docs/github-workflow.md`
- 작업 규칙(하네스): `CLAUDE.md`, `AGENTS.md`

```bash
scripts/start-task.sh 12 feat player-jump   # 이슈 12로 dev에서 작업 브랜치 시작
scripts/finish-task.sh 12 "Add player jump" # 커밋·푸시·dev 대상 PR
scripts/promote-main.sh 12 "Add player jump"# dev 검증 후 main 대상 PR
```
