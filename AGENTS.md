# Group-1 Codex Harness

이 저장소는 issue-first workflow를 사용합니다. Codex는 새 기능, 버그 수정, 개선, 리팩터링, 동작 변경을 시작하기 전에 이 하네스를 따라야 합니다.

## 게임 정보 (방과 후)

2D 탑다운 공포 방탈출, Godot 4.6. 주인공 이설이 밤 10시 30분 국어책을 가지러 학교에 갔다가 갇히고, 5층 미술실에서 시작해 1층 현관으로 탈출한다.
시나리오 문서: https://docs.google.com/document/d/1q5yRBDpXJDYmvcUaN82z0U_xv3DtuZPG5ipWiTHMZVc

### 씬 흐름

main_menu → intro(프롤로그 장면 그래프: 집→TV→정문→뒷문→미술실→규칙 칠판→분기 2개+사망 엔딩, scripts/ui/intro.gd의 SCRIPT_NODES) → main(게임 본편) → ending(기본 엔딩) → main_menu

### 구조 요약

- `scenes/main/main.tscn` = 조립 씬: Darkness(CanvasModulate 어둠), Background(층 씬 인스턴스), Player, GameState, HUD, UI(FloorLabel·FadeRect). 루트 스크립트 `scripts/game/floor_manager.gd`가 층 전환·시작 힌트·페이드 담당.
- 층 씬 `scenes/background/school_floor_1~5.tscn`: 2800×1800, 공통 뼈대(상단 교실 8칸). 계단실 2곳은 전 층 동일 좌표 — 좌상단 (120,720)~(560,1000), 중앙 하단 (1180,1400)~(1560,1680).
- 벽 규약: 두께 16px, 방 문 폭 110px(가로 중앙, 방 중심 y<900이면 아래변/아니면 위변). 벽은 충돌(WC_*)+시각(WV_*)+광원 차단(Occ_/LO_*) 3종 세트 — 벽 수정 시 셋 다 갱신. 생성 도구는 `tools/`(재실행 경고는 각 스크립트 주석 참조).
- 계단: 가운데 난간으로 반 분할(왼쪽=위층▲, 오른쪽=아래층▼). 층 전환 트리거 존·도착점은 floor_manager.gd 상수. 입구는 층별 열쇠 `stair_key_N`으로 개방(소모형, 한 번에 그 층 2곳 개방).
- 상태 영속: `scripts/game/game_state.gd` — 인벤토리(최대 5개), 플래그(set_flag/has_flag)로 문 개방·아이템 획득 기록(층 씬이 재로드돼도 유지).
- 상호작용(E): `scripts/interactions/` — interactable(조사), locked_door(열쇠 문), pickup_item(접촉 획득), exit_door(현관 탈출→엔딩). Area2D는 collision_layer 2, prompt_text로 "[E] …" 안내 표시.
- 조명: main의 CanvasModulate + 플레이어 PointLight2D(shadow_enabled) — 벽 차단체 때문에 벽 너머는 보이지 않음. 문·창문 틈으로만 빛이 샘.
- UI: R 인벤토리 패널(5슬롯), 좌상단 HUD(목표/소지품)+층 표시, 하단 알림(game_state.request_notice).

### 진행 요소 위치

- 5층: 미술실(시작, 문 영구 잠금) → 아래쪽 창문 → 남쪽 외벽 난간 → 빈 교실 창문 → 복도. 계단 열쇠는 보건실. 미술실 칠판 조사 가능.
- 계단 열쇠: 4층 과학 실험실, 3층 방송실, 2층 체력단련실, 1층 행정실(복귀용).
- 1층: 수위실(실종자 물품·금고 일지·현관 열쇠꾸러미 front_gate_key) → 현관 로비 남쪽 현관에서 E → 기본 엔딩.
- 미구현: 괴물 추격 AI(시나리오 #5), 숨은 엔딩(#11, 손전등 처치+국어책 일지), 옥상 씬.

### 개발 시 주의

- 이 환경에는 Godot 바이너리가 없음 — 실행 검증(F5)은 사용자가 수동으로 함. 정적 검증(기하·경로 대조 스크립트)을 기록하고 PR을 연 뒤 사용자 확인을 기다린다.
- .tscn 수정 시 `load_steps` = ext_resource 수 + sub_resource 수 + 1 유지.
- project.godot에 사용자의 미커밋 변경이 있을 수 있음 — 내 커밋에 섞지 말 것(필요 시 stash로 분리).
- .gd 스크립트를 새로 만들면 사용자 에디터가 .uid 파일을 생성함 — 발견 시 해당 이슈 브랜치에 커밋.

## Issue-First Rule

- 기능, 버그 수정, 개선, 리팩터링 작업은 GitHub 이슈 없이 구현을 시작하지 않습니다.
- 사용자가 이슈 없이 작업을 요청하면 GitHub 접근 권한이 있을 때 먼저 이슈를 만듭니다.
- GitHub 접근 권한이 없으면 사용자에게 이슈 없이 진행해도 되는지 확인하고, 최종 응답에 이슈 생성이 막혔다는 점을 남깁니다.
- 이슈 번호는 브랜치 이름, 커밋 메시지, PR 본문에 포함합니다.
- 관련 없는 정리 작업은 별도 이슈와 별도 브랜치로 분리합니다.

## Required Issue Detail

모든 기능, 개선, 버그 이슈에는 아래 항목이 있어야 합니다.

- Summary: 무엇이 바뀌어야 하는지.
- Motivation or Problem: 왜 필요한지.
- Current Behavior: 현재 어떻게 동작하는지.
- Expected Behavior: 완료 후 어떻게 동작해야 하는지.
- Scope: 영향을 받을 게임 시스템, 씬, 스크립트, 에셋, 문서.
- Acceptance Criteria: 완료를 증명할 구체적인 기준.
- Verification Plan: 실행할 명령이나 수동 확인 방법.

버그 수정 이슈에는 추가로 아래 항목이 필요합니다.

- Reproduction Steps.
- Actual Result.
- Expected Result.
- Environment, when relevant.

새 기능 이슈에는 추가로 아래 항목이 필요합니다.

- Player Flow.
- Non-goals.
- UX, input, balance, or settings expectations, when relevant.

## Branching

- 이슈 하나당 브랜치 하나를 만듭니다.
- 브랜치 이름은 짧고 이슈 번호를 포함합니다.
- 권장 형식:
  - `issue-<number>-short-topic`
  - `fix-<number>-short-topic`
  - `feat-<number>-short-topic`

## Implementation

- 파일을 수정하기 전에 이슈를 읽고 의도한 동작을 확인합니다.
- 변경 범위는 이슈에 적힌 내용으로 제한합니다.
- 기존 프로젝트 패턴을 우선합니다.
- 큰 구조 변경이나 폴더 정리는 해당 이슈가 직접 요구할 때만 합니다.

## Verification

변경한 파일과 게임 엔진 상태에 맞춰 가장 작은 의미 있는 검증부터 실행합니다.

- Godot 프로젝트 설정 확인
- 변경한 씬 또는 스크립트 수동 실행
- 플레이어 입력, UI, 충돌, 게임 흐름 확인
- 사용 가능한 테스트나 빌드 명령이 생기면 해당 명령 실행

PR 본문에는 실제로 확인한 내용을 기록합니다.

## Pull Requests

- PR 제목은 이슈에서 해결한 결과를 요약합니다.
- PR 본문에는 `Closes #<issue-number>`를 포함합니다.
- PR 본문에는 summary, verification, residual risks를 포함합니다.
- 검증 내용이 기록되기 전에는 머지하지 않습니다.

## Merge Flow

- 이슈를 해결하고 검증을 마친 뒤 이슈 브랜치에 커밋하고 원격 저장소에 푸시합니다.
- 이슈 브랜치에서 `dev`로 첫 번째 PR을 엽니다.
- PR이 mergeable/CLEAN이고 변경 파일이 이슈 범위와 일치하면 자동으로 머지합니다.
- 같은 원격 이슈 브랜치에서 `main`으로 두 번째 PR을 열고, 같은 기준을 확인한 뒤 자동으로 머지합니다.
- `main`은 브랜치 보호(리뷰 승인 1개 필수)가 있으므로, 기준을 충족한 PR은 admin 권한(`gh pr merge --admin`)으로 머지합니다. (사용자 승인: 2026-07-05)
- `main` 머지가 끝나면 원격 이슈 브랜치를 삭제합니다.
- 정리 후 로컬 저장소는 삭제된 이슈 브랜치가 아니라 `main` 또는 `dev`에 둡니다.

자동 머지를 멈추고 사용자에게 보고하는 예외:

- 코드 충돌이 있거나 mergeable/CLEAN이 아닌 경우
- 이슈 범위 밖의 파일 변경이 섞인 경우
- 검증이 누락되었거나 미완인 경우(예: 자격증명·바이너리 부족으로 실행 확인 불가)
- 사용자가 "머지하지 말라"고 지시한 경우
- 되돌리기 어려운 부수효과가 있는 경우(데이터 마이그레이션, 배포 트리거 등)
