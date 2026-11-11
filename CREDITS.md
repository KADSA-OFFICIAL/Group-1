# 크레딧 — 외부 에셋

> 게임 안 크레딧 창(타이틀 오른쪽 아래, #865)은 `scripts/ui/credits_panel.gd`의 `SECTIONS`가 그린다.
> 여기 표를 고치면 그 표도 같이 고칠 것.

「방과 후」는 학교 프로젝트(비상업)다. 여기 없는 그림·소리는 전부 이 저장소의
`tools/gen_*.py`가 만들었거나 팀이 직접 그린 원본에서 구운 것이다. 교장실·보건실
가구, 선반·캐비닛·창고 상자, 단서 그림 셋(`assets/sprites/furniture/`)은
`tools/gen_furniture_sprites.py`가 굽는다 — 예전 Darklight Academia Furniture Pack은
"AI 관련 프로젝트 사용 금지" 조항 때문에 #791에서 걷어냈다.

## 소리 (#713)

| 게임 안 파일 | 쓰는 곳 | 원본 | 제작자 | 라이선스 |
|---|---|---|---|---|
| `assets/audio/ext/ambience_dark.ogg` | 본편 앰비언트 | "Dark Ambient Music - Loopable" — [Horror Sound Pack](https://phlegmlee.itch.io/horror-sound-pack) | Phlegmlee | CC0 1.0 |
| `assets/audio/ext/chase_eerie.ogg` | 추격 BGM | "Eerie Loop" — 같은 팩 | Phlegmlee | CC0 1.0 |
| `assets/audio/ext/door_creak.wav` | 문 여닫기(이설·수위) | "Creaking Door (6)" — [Free Horror SFX vol.1](https://liminal-space-dev.itch.io/free-horror-sfx-sounds) | Liminal Games | CC0 1.0 (팩 자체 재배포 금지) |
| `assets/audio/ext/yard_wind.ogg` | 운동장 바람 | "Ambient Wind (7)" — 같은 팩 | Liminal Games | CC0 1.0 (팩 자체 재배포 금지) |

- 원본 팩은 저장소에 넣지 않는다. 가공(모노·22050Hz·루프 이음매·음량)은
  `tools/import_ext_audio.py`가 하고, 그 결과만 커밋한다. 루프 셋은 가공 결과(PCM)를
  마스터(`assets/audio/masters/ext/`, 내보내기 제외)로 두고 `tools/encode_music.py`가
  Ogg Vorbis로 구운 것을 게임이 쓴다(#855).
- Liminal Games 팩은 페이지에 AI로 만든 소리라고 적혀 있다.

## Haunted School 그림 (#717, #723, #725, #727)

| 게임 안 파일 | 쓰는 곳 | 원본 | 제작자 | 조건 |
|---|---|---|---|---|
| `assets/sprites/ext/hs_*.png` | 2·3층 교실 학생 자리·교탁, 교무실·부서실 책상 섬(#717), 단서 그림 13개(#723), 방 바닥 5종(#725, `Inside_A2.png` — 교무실·수위실·화장실·창고 등), 벽 앞면(#727, `Inside_A4.png`) | [Haunted School Tiles - RMMZ](https://thurraya.itch.io/haunted-school-rpmmz) `Inside_B.png` | Thurraya | CC BY-NC 4.0 — 비상업 사용, 원본 그대로 재배포·재판매 금지, AI·LLM 학습·NFT 사용 금지, 크레딧 선택 |

- 원본 시트는 저장소에 넣지 않는다. 쓰는 칸만 잘라 넣는다(`tools/import_ext_sprites.py --haunted`).
  게임에서는 1배(그림 1칸 = 월드 1px)로 놓는다.

## Top Down Pixel Art Horror 그림 (#763)

| 게임 안 파일 | 쓰는 곳 | 원본 | 제작자 | 조건 |
|---|---|---|---|---|
| `assets/sprites/ext/hr_*.png` | 복도·교실 사물함(앞모습·옆모습), 현관 신발장 | [Top Down Pixel Art Horror](https://kamisama887.itch.io/lorenz-fries-school-horror) 무료판 `Inside_D.png` | AnisAous | 개인(비상업) 사용 무료, 수정 허용, 팩 판매·단독 업로드 금지, 크레딧 선택 |

- 원본 시트는 저장소에 넣지 않는다. 쓰는 칸만 잘라 넣는다(`tools/import_ext_sprites.py --horror`).

## 글꼴

| 글꼴 | 라이선스 |
|---|---|
| East Sea Dokdo | SIL OFL 1.1 — `assets/fonts/EastSeaDokdo-OFL.txt` |
| Yeon Sung | SIL OFL 1.1 — `assets/fonts/YeonSung-OFL.txt` |
| Noto Sans KR | SIL OFL 1.1 — `assets/fonts/NotoSansKR-OFL.txt` |
