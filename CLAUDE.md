# Group-1 Claude Harness

이 저장소는 issue-first workflow를 사용합니다. Claude Code는 새 기능, 버그 수정, 개선, 리팩터링, 동작 변경을 시작하기 전에 이 하네스를 따라야 합니다.

## 게임 정보 (방과 후)

2D 탑다운 공포 방탈출, Godot 4.6. 주인공 이설이 국어책을 가지러 밤의 학교에 들어가 실종 사건의 진실과 마주친다.
적대자는 괴물이 아니라 **수위 박종태** — 10년 전 딸 박시우가 학교폭력 후 투신했고 학교가 무대응하자 스스로 '심판'을 집행한다. 실종 학생 5명 중 일부는 오해로 지목됐다는 것이 주제.
시나리오 전문: `docs/story.md` (구글 문서 사본 — 대사·지문 원문 + 구현이 기획서와 갈라진 지점 정리).
원본: https://docs.google.com/document/d/1c8rXO7bLU_HvOPKYClmRSG2P97Vloo7maXblYMaQ70E — 원본이 바뀌면 사본도 갱신할 것.
전체 스펙과 4단계 작업 계획은 GitHub 이슈 #137(epic)에 기록돼 있다 — 스토리 작업 전에 먼저 읽을 것.

### 씬 흐름

main_menu → intro(프롤로그 컷신: street→back_gate→art_room→cabinet→next_room, scripts/ui/intro.gd의 SCRIPT_NODES) → main(본편, **4층에서 시작**) → ending → main_menu
5층은 프롤로그 컷신 전용이며 본편에서 방문하지 않는다(MAX_FLOOR=4). 규칙 칠판·사망 엔딩은 구 시나리오 요소로 제거됨.

### 구조 요약

- `scenes/main/main.tscn` = 조립 씬: Darkness(CanvasModulate 어둠), Background(층 씬 인스턴스), Player, GameState, HUD, UI(FloorLabel·FadeRect). 루트 스크립트 `scripts/game/floor_manager.gd`가 층 전환·시작 힌트·페이드 담당.
- 층 씬 `scenes/background/school_floor_1~5.tscn`: **3400×2500, 손도면 기반(#159)**. 씬을 손으로 고치지 말고 **`tools/gen_floors.py`의 LAYOUT 테이블을 고친 뒤 재생성**한다(5개 층 전체를 만든다).
- 층 구조: 북쪽 교실 열(2·3·4층 9칸, 5층 8칸) → 북쪽 복도 → 중간 띠(좌: 계단실·남녀화장실·막힌공간 / 우: 창고·막힌공간·남녀화장실, **사선**) → 공백 구역을 가로지르는 **중앙다리**(유일한 남북 통로) → 남쪽 복도·특별실동 → 하단 띠(대형실·계단실·화장실). 1층만 도면이 달라 아래쪽 절반만 건물(교실1~3·운동장출입구·교무실 / 현관·수위실·창고).
- 계단실: 좌측 `(300,720)~(740,1000)`, 하단 중앙 `(1450,2120)~(1890,2440)`. **1층은 계단이 한 곳뿐**이고 위치도 다르다 `(220,2120)~(660,2440)`. **2층 하단 계단은 영구 봉인**(그 아래가 1층 현관이라 내려갈 자리가 없음) — `gen_floors.py`의 `SEALED`.
- 건물 밖 공백(중앙다리 양옆, 1층 북쪽 절반)은 **벽으로 막는 것만으로 부족**하다. 안쪽 칸이 통행 가능으로 남아 수위 스폰 후보에 들어가므로 `fill_void()`로 실체를 채운다.
- 벽 규약: 두께 16px, 방 문 폭 110px(가로 중앙, 방 중심 y<900이면 아래변/아니면 위변). 벽은 충돌(WC_*)+시각(WV_*)+광원 차단(Occ_/LO_*) 3종 세트 — 벽 수정 시 셋 다 갱신. 생성 도구는 `tools/`(재실행 경고는 각 스크립트 주석 참조).
- 계단: 가운데 난간으로 반 분할(왼쪽=위층▲, 오른쪽=아래층▼, 방향 표지+목적지 층 번호 표시). 층마다 계단 위치·개수가 다르므로 `floor_manager.gd`의 **층별 `STAIRS` 사각형**에서 트리거 존·도착점을 계산한다(고정 상수 아님). 입구는 층별 열쇠 `stair_key_N`으로 개방(소모형, 그 층 계단 전부 개방).
- 상태 영속: `scripts/game/game_state.gd` — 인벤토리(최대 5개), 플래그(set_flag/has_flag)로 문 개방·아이템 획득 기록(층 씬이 재로드돼도 유지).
- 상호작용(E): `scripts/interactions/` — interactable(조사), locked_door(열쇠 문), pickup_item(접촉 획득), exit_door(현관 탈출→엔딩). Area2D는 collision_layer 2, prompt_text로 "[E] …" 안내 표시.
- 잉크통(#169): 4층 정보부실에서 얻는 `ink_can`을 **Q**로 바라보는 방향에 던진다(1회용). `scenes/items/ink_projectile.tscn`이 레이캐스트로 벽을 확인하며 날아가다 터지고, 반경 120px 안의 수위를 5초간 멈춘다(`janitor.blind()` — 추적·접촉 판정 정지, 층을 옮기면 해제). 쓸 수 있는 아이템의 조작 키는 `hud.gd`의 `USABLE_ITEM_KEYS`에 적어 R 패널에 표시한다.
- 플레이어 스프라이트(#210): 원본 캐릭터 아트 `assets/sprites/source/player_design.png`(대기 정면 + 달리기 측면 두 포즈)에서 **`tools/gen_player_sprites.py`가 60×72 도트 스프라이트를 잘라 낸다**(표준 라이브러리만, 결정론적). 크기를 바꾸려면 그 스크립트의 `CANVAS_W`/`CANVAS_H`를 고치고 다시 돌린 뒤 `player_controller.gd`의 `SPRITE_OFFSET_Y`(발끝을 충돌 캡슐 바닥에 맞추는 값)도 같이 맞춘다. 포즈 전환·좌우 반전은 `player_controller.gd`의 `_update_sprite()` — **사람 그림이라 이동 각도로 회전시키지 않는다**. 수위는 아직 `Polygon2D` 도형이다.
- 조명: main의 CanvasModulate + 플레이어 PointLight2D(shadow_enabled) — 벽 차단체 때문에 벽 너머는 보이지 않음. 문·창문 틈으로만 빛이 샘.
- UI: R 인벤토리 패널(5슬롯), 좌상단 HUD(목표/소지품)+층 표시, 하단 알림(game_state.request_notice).
- 사운드(#9): 에셋을 받아오지 않고 **`tools/gen_sfx.py`가 8비트 톤으로 합성**해 `assets/audio/*.wav`로 커밋한다(표준 라이브러리만, 고정 시드라 재생성해도 바이트가 같다). 톤을 바꾸려면 그 스크립트의 `build_all()` 숫자를 고치고 다시 돌린다. 비위치 효과음은 autoload `Sfx`(`scripts/game/sound_manager.gd`)의 `Sfx.play(&"id")`, 위치가 정보인 소리(수위 발소리·열쇠·문)는 `janitor.tscn`의 AudioStreamPlayer2D가 낸다. **하단 알림 텍스트는 소리와 병행**한다 — 소리를 못 듣는 상황에서도 단서가 남아야 한다. 오디오 버스는 Master 하나뿐이고 음량은 `sound_manager.gd`의 `VOLUMES`에서 맞춘다.
- 앰비언트·추격 BGM(#176): `tools/gen_music.py`가 만든다(루프라 위상을 루프 길이에 맞춰 고정하고, 이음매 불연속을 자체 검사한다). 본편 진입에 `Sfx.start_music()`, 체포·탈출에 `Sfx.stop_music()`. 수위가 `Sfx.set_chasing()`으로 매 프레임 추격 여부를 알리면 추격 BGM이 페이드 인하고 앰비언트가 낮아진다. **해제는 2.5초 미룬다** — `lose_sight_seconds`(1.5)보다 길어야 모퉁이에서 음악이 깜빡이지 않는다. 루프 지점은 `.import`가 아니라 런타임에 정한다(그 파일은 커밋에 빠질 수 있다).
- 수위(#141): 4층은 안전 구간(`floor_manager.JANITOR_FREE_FLOOR`), 3·2·1층에서 활동. 순찰은 층 씬의 `Door_*`에서 뽑은 **문 앞 대기 지점을 최근접 이웃으로 이은 고정 루트를 왕복**하고, 문마다 1.8초 멈춰 방을 확인한다. 들리는 거리(720px) 안에서만 혼잣말·열쇠 소리, 420px 안이면 발소리를 하단 알림으로 낸다. 발각(접촉 30px) → 체포 게임 오버. 루트 점검은 `tools/verify_janitor_route.py`.

### 진행 요소 위치

- 본편은 4층 복도(579,692)에서 시작해 계단 열쇠로 3→2→1층 하강, 1층 수위실 금고에서 front_gate_key를 얻어 현관 탈출. **열쇠는 전부 접촉 획득**(E 불필요), 잉크통 등 조사 오브젝트만 E.
- 계단 열쇠(#159 재배치, **열쇠 하나당 획득처 하나**): stair_key_4 = 4층 다산7실 / stair_key_3 = 3층 2학년부 고리 / stair_key_2 = 2층 하단 남자화장실 배수구 / stair_key_1 = 1층 창고(하강엔 불필요). 중복 열쇠는 인벤토리(5칸)만 먹어서 걷어냈다 — 4층 컴퓨터실(#219)·4층 창고 태호 쪽지(#222)·3층 2학년부 보관함(#207)은 열쇠 없이 단서로만 남는다.
- 단서 오브젝트(#159/#161 선택지3로 새 맵에 맞게 개정 — **플래그 ID는 그대로**): 4층 다산7실(하람 메모)·창고(태호 쪽지)·창의체험부(시우 상담기록·그림)·정보부실(대응 매뉴얼·잉크통)·컴퓨터실(조민혁)·다산6실(졸업앨범), 3층 생활지도부(임나연)·2학년부(종태 기록·열쇠 보관함)·진로실(전단), 2층 체육창고(강유진)·하단 남자화장실(끌린 자국)·교육실(백승호), 1층 교무실(교장 편지)·수위실(사진벽·학생증·공책·금고).
- 단서 본문(메시지·플래그·스크립트)은 `tools/story_objects.json`에 있고 `gen_floors.py`의 `PLACEMENT`가 방만 지정한다. 방을 옮기려면 PLACEMENT만 고치면 된다.
- 엔딩은 "방과 후" 1종(러닝타임 축소, 2026-07-28 사용자 결정) — 현관에서 분기 판정이 없다. 단서 플래그는 조사 기록용이며 진행을 막지 않는다. 신고 선택지·숨은 엔딩·재조사는 넣지 않는다.
- 새 기획서 기준 스토리 작업(#137 1~4단계)은 전부 끝났다. 옥상 씬은 계획 없음.

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

- 맵 관련 변경은 **`python3 tools/gen_floors.py` 재생성 후** 아래 4개를 모두 돌립니다:
  `verify_scenes.py`(정합성·깨진 실수 값) / `verify_floor_reach.py`(방 도달성·막힌 공간 봉인·카메라 한계) /
  `verify_stairs.py`(floor_manager 계단 좌표 ↔ 씬 대조) / `verify_progression.py`(4층→1층 현관 완주 가능).
- 씬이나 스크립트를 고쳤으면 **푸시 전에 `python3 tools/verify_scenes.py`를 실행**합니다.
  load_steps, 리소스 참조, 노드 부모 경로, 형제 이름 중복, 스크립트 $NodePath,
  벽 충돌↔광원 차단체 1:1을 검사합니다(Godot 불필요, 수초).
- 효과음을 고쳤으면 `python3 tools/gen_sfx.py`, 앰비언트·BGM은 `python3 tools/gen_music.py`로
  재생성합니다(길이·피크·DC 오프셋·루프 이음매를 스스로 검사하고, 결정론적이라
  톤을 안 바꿨으면 diff가 나오지 않습니다).
- 수위 순찰·문 배치를 건드렸으면 `python3 tools/verify_janitor_route.py`
  (문 앞 대기 지점이 벽에 안 박히는지·계단에서 닿는지·루트가 맵을 가로지르지 않는지).
- 기하·좌표를 바꿨으면 해당 이슈에 맞는 임시 검증 스크립트로 대조합니다.
- 플레이어 입력, UI, 충돌, 게임 흐름 확인은 사용자의 수동 F5에 의존합니다.
- 푸시하면 GitHub Actions(`.github/workflows/ci.yml`)가 정적 검사와 함께
  Godot 4.6 헤드리스 임포트·전체 씬 로드를 실행합니다. 결과는 `gh pr checks <번호>`로 확인합니다.
  씬 로드는 `tools/ci_load_scenes.gd`가 맡고 씬뿐 아니라 `scripts/` 아래 `.gd`도 전부
  컴파일해 봅니다. 이 스크립트는 **`_init()`이 아니라 `_initialize()`에서 돌아야 합니다**(#183) —
  `--script`로 넘긴 MainLoop는 autoload(`Sfx`) 등록보다 먼저 만들어져서, `_init()`에서
  로드하면 `Sfx` 참조 스크립트가 전부 컴파일에 실패합니다(그래도 씬 로드는 성공해 검사가 통과함).

PR 본문에는 실제로 확인한 내용을 기록합니다.

## Pull Requests

- PR 제목은 이슈에서 해결한 결과를 요약합니다.
- PR 본문에는 `Closes #<issue-number>`를 포함합니다.
- PR 본문에는 summary, verification, residual risks를 포함합니다.
- 검증 내용이 기록되기 전에는 머지하지 않습니다.

## Merge Flow

- 이슈를 해결하고 검증을 마친 뒤 이슈 브랜치에 커밋하고 원격 저장소에 푸시합니다.
- 이슈 브랜치에서 `dev`로 첫 번째 PR을 엽니다.
- PR이 mergeable/CLEAN이고 CI 체크가 통과했고 변경 파일이 이슈 범위와 일치하면 자동으로 머지합니다.
- CI가 실행 중이면(mergeStateStatus가 UNSTABLE 등) 완료를 기다린 뒤 판단합니다. 실패하면 머지하지 않고 원인을 고칩니다.
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
