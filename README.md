# Group-1

KADSA Group-1 게임 프로젝트 저장소입니다.

## GitHub 작업 흐름

이 프로젝트는 `issue -> branch -> commit -> PR to dev -> PR to main` 흐름으로 작업합니다.

- 안정 버전은 `main` 브랜치에 둡니다.
- 새 기능, 개선, 버그 수정은 `dev`에서 작업 브랜치를 만들어 진행합니다.
- 작업 브랜치 이름은 `feature/12-player-jump`, `bugfix/18-camera-jitter`처럼 이슈 번호를 포함합니다.
- 작업 PR은 먼저 `dev`로 올립니다.
- `dev`에서 문제가 없으면 `dev -> main` PR을 올립니다.

자세한 규칙과 로컬 명령은 [docs/github-workflow.md](docs/github-workflow.md)를 확인하세요.
