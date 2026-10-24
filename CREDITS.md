# 크레딧 — 외부 에셋

「방과 후」는 학교 프로젝트(비상업)다. 여기 없는 그림·소리는 전부 이 저장소의
`tools/gen_*.py`가 만들었거나 팀이 직접 그린 원본에서 구운 것이다.

## 소리 (#713)

| 게임 안 파일 | 쓰는 곳 | 원본 | 제작자 | 라이선스 |
|---|---|---|---|---|
| `assets/audio/ext/ambience_dark.wav` | 본편 앰비언트 | "Dark Ambient Music - Loopable" — [Horror Sound Pack](https://phlegmlee.itch.io/horror-sound-pack) | Phlegmlee | CC0 1.0 |
| `assets/audio/ext/chase_eerie.wav` | 추격 BGM | "Eerie Loop" — 같은 팩 | Phlegmlee | CC0 1.0 |
| `assets/audio/ext/door_creak.wav` | 문 여닫기(이설·수위) | "Creaking Door (6)" — [Free Horror SFX vol.1](https://liminal-space-dev.itch.io/free-horror-sfx-sounds) | Liminal Games | CC0 1.0 (팩 자체 재배포 금지) |
| `assets/audio/ext/yard_wind.wav` | 운동장 바람 | "Ambient Wind (7)" — 같은 팩 | Liminal Games | CC0 1.0 (팩 자체 재배포 금지) |

- 원본 팩은 저장소에 넣지 않는다. 가공(모노·22050Hz·루프 이음매·음량)은
  `tools/import_ext_audio.py`가 하고, 그 결과만 커밋한다.
- Liminal Games 팩은 페이지에 AI로 만든 소리라고 적혀 있다.

## 가구 그림 (#716)

| 게임 안 파일 | 쓰는 곳 | 원본 | 제작자 | 조건 |
|---|---|---|---|---|
| `assets/sprites/ext/` 중 `hs_`가 아닌 것 | 1층 교장실(책상·소파·안락의자·책장·괘종시계·지구본·스탠드·화병·러그), 보건실 침대, 단서 그림 셋(시우 그림·인사 기록·대응 매뉴얼, #723) | [Darklight Academia Furniture Pack](https://kueyhorse.itch.io/darklight-academia-furniture-pack) 무료판 | kueyhorse | 비상업 사용 허용, 원본·수정본 재배포·재판매 금지, NFT·AI 관련 프로젝트·생성기·학습 도구 사용 금지 |

- 원본 팩은 저장소에 넣지 않는다. 쓰는 그림만 투명 여백을 잘라 넣는다
  (`tools/import_ext_sprites.py`). 크기는 바꾸지 않고 게임에서 정수 2배로 놓는다.

## Haunted School 그림 (#717, #721)

| 게임 안 파일 | 쓰는 곳 | 원본 | 제작자 | 조건 |
|---|---|---|---|---|
| `assets/sprites/ext/hs_*.png` | 2·3층 교실 학생 자리·교탁, 교무실·부서실 책상 섬(#717), 복도 철제 사물함(#721), 단서 그림 13개(#723), 방·복도 바닥 7종(#725, `Inside_A2.png`), 벽 앞면(#727, `Inside_A4.png`) | [Haunted School Tiles - RMMZ](https://thurraya.itch.io/haunted-school-rpmmz) `Inside_B.png` | Thurraya | CC BY-NC 4.0 — 비상업 사용, 원본 그대로 재배포·재판매 금지, AI·LLM 학습·NFT 사용 금지, 크레딧 선택 |

- 원본 시트는 저장소에 넣지 않는다. 쓰는 칸만 잘라 넣는다(`tools/import_ext_sprites.py --haunted`).
  게임에서는 1배(그림 1칸 = 월드 1px)로 놓는다.

## 글꼴

| 글꼴 | 라이선스 |
|---|---|
| East Sea Dokdo | SIL OFL 1.1 — `assets/fonts/EastSeaDokdo-OFL.txt` |
| Yeon Sung | SIL OFL 1.1 — `assets/fonts/YeonSung-OFL.txt` |
| Noto Sans KR | SIL OFL 1.1 — `assets/fonts/NotoSansKR-OFL.txt` |
