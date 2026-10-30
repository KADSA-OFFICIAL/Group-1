extends RefCounted
## 이설의 수첩(#705) — 무엇이 적히고 언제 풀리는가.
##
## 단서를 조사하면 자막이 한 번 뜨고 끝나서, 스토리를 단서만으로 따라가기 어려웠다
## (사용자 보고). 원문 테마는 "퍼즐 조각이 하나씩 맞춰지면서 이설은 깨닫는다"
## (`docs/story.md` 1장)인데 게임에는 이설이 조각을 잇는 자리가 없었다.
##
## - **칸(`entries`)**: 플래그 하나가 서면 이설의 메모 한 줄이 적힌다. 못 찾은 칸은
##   `????`로 남아 얼마나 남았는지 보인다.
## - **정리(`links`)**: `needs`의 플래그가 **전부** 서면 풀린다 — 이설이 조각을 잇는 줄.
##
## 화면(`journal_panel.gd`)과 떼어 둔 이유: `verify_progression`이 여기 적힌 플래그가
## 씬이나 스크립트에서 **실제로 서는지** 본다. 오타 난 플래그는 영영 안 풀리는데,
## 화면에서는 그냥 `????`로 남아 아무도 모른다.
##
## **플래그 ID는 바꾸지 않는다** — 엔딩 판정(#353)·층별 표(#665)가 같은 이름을 쓴다.

const SECTIONS := [
	{
		"title": "박시우",
		"entries": [
			["read_siwoo_painting",
				"미술실 액자 — 서명 '박시우'. 나무 그늘 아래 붓끝으로 눌러 쓴 '도와줘'."],
			["read_siwoo_counseling",
				"상담기록부 — 1학년 박시우, 상담 7번. 학교 회신은 '가해 학생 특정 어려움. 추가 조치 없음.'"],
			["read_siwoo_past",
				"10년 전 졸업앨범, 추모 면의 시우. 신문 스크랩 — '교내 추락 사고로 학생 1명 사망'."],
			["saw_photo_wall",
				"수위실 사진 벽 — 한가운데 시우. 둘레에 이 학교 아이들, 몇 명에 붉은 동그라미."],
		],
		"links": [
			[["read_siwoo_painting", "read_siwoo_counseling", "read_siwoo_past"],
				"시우는 괴롭힘 끝에 죽었다. 도와 달라고 일곱 번을 말했는데, 학교는 '사고'로 덮었다."],
		],
	},
	{
		"title": "수위 박종태",
		"entries": [
			["heard_confession",
				"숨어서 들었다. '시우야… 아빠가 하나씩 치웠어. 심판이야, 죄 있는 애들만.'"],
			["read_janitor_warning",
				"2년 전 인사 기록 — 밤에 학생을 '훈계'해 주의 조치. 교감 메모: '30년 근무자다. 더 문제 삼지 말자.'"],
			["read_principal_letter",
				"교장에게 보낸 편지 — '제 딸 시우가 죽은 지 10년입니다. …이제는 제가 하겠습니다. — 박종태'"],
			["read_janitor_notebook",
				"수위실 공책 — 이름 옆에 '죄'가 하나씩. 조민혁 옆에는 '집에서 맞고 온다. 확실하지 않다. 그래도 만약을 위해.'"],
		],
		"links": [
			[["heard_confession", "read_siwoo_counseling"],
				"수위 아저씨는 시우의 아버지다. 학교가 하지 않은 '심판'을 혼자 하고 있다."],
		],
	},
	{
		"title": "사라진 아이들",
		"entries": [
			["saw_dates",
				"준비실 벽의 날짜 다섯 — 뉴스에서 들은 실종 시기와 같다."],
			["saw_belongings",
				"준비실 비닐봉투 — 단추, 이름표, 머리끈. 한 사람 것이 아니다."],
			["found_imnayeon",
				"임나연(1-6) — 'SNS 따돌림 주도'로 찍혔다. 캡처를 보면 단톡방 농담 한 줄이 퍼진 것뿐이다. 실종 신고."],
			["found_jominhyuk",
				"조민혁(2-2) — 뉴스에서 실종됐다던 2학년 이름이다."],
			["read_taeho_note",
				"태호의 쪽지 — '민혁아, 걸리면 너만 혼나.' 민혁이를 감싸 주던 친구가 있었다."],
			["found_kangyujin",
				"강유진(3-1) — 후배를 때려 병원에 보냈다. 쪽지 뒷면에 어른 글씨: '아무도 안 도와주니까 내가 한다.'"],
			["saw_shower_marks",
				"2층 화장실 — 바닥에 길게 끌린 자국. 벽에 손끝으로 쓴 '살려'."],
			["found_head_key",
				"2층 창고. …조민혁이었다. 눈이 있어야 할 자리에 열쇠가 박혀 있었다."],
			["saw_student_cards",
				"수위실 서랍 — 사라진 아이들의 학생증이 각을 맞춰 나란히 놓여 있다."],
		],
		"links": [
			[["found_imnayeon", "found_jominhyuk", "found_kangyujin"],
				"셋 다 아저씨 눈에 '죄 있는 애'로 찍혔다. 유진 선배는 정말 후배를 때렸다. 그런데 나연이는… 단톡방 농담 한 줄이었다."],
			[["found_imnayeon", "found_jominhyuk", "found_kangyujin", "read_janitor_notebook"],
				"민혁이는 집에서 맞고 오던 애였다. 아저씨도 확실하지 않았다. 그래도 데려갔다."],
		],
	},
	{
		"title": "학교가 덮은 것",
		"entries": [
			["read_report_flyer",
				"학교폭력 신고 절차 전단 위에 빨간 X. 여백 — '이걸로 해결된 적 있어?'"],
			["read_crisis_manual",
				"'학생 사망 사고 대응 매뉴얼 — 언론 차단, 유가족 합의 우선, 재학생 동요 최소화.'"],
		],
		"links": [
			[["read_report_flyer", "read_crisis_manual", "read_siwoo_counseling"],
				"학교는 막는 법이 아니라 덮는 법을 알고 있었다. 시우 때도, 지금도."],
		],
	},
]


## 수첩이 쓰는 플래그 전부 — 검사기가 읽는다.
static func all_flags() -> Array:
	var out: Array = []
	for s in SECTIONS:
		for e in s["entries"]:
			if e[0] not in out:
				out.append(e[0])
		for l in s["links"]:
			for f in l[0]:
				if f not in out:
					out.append(f)
	return out


## 지금 풀린 줄 수(칸 + 정리). 새 내용이 적혔는지 알아볼 때 쓴다.
static func unlocked_count(flags: Array) -> int:
	var n := 0
	for s in SECTIONS:
		for e in s["entries"]:
			if e[0] in flags:
				n += 1
		for l in s["links"]:
			if _all_in(l[0], flags):
				n += 1
	return n


static func _all_in(needs: Array, flags: Array) -> bool:
	for f in needs:
		if f not in flags:
			return false
	return true


## 화면에 그릴 BBCode. 못 찾은 칸은 `????`, 정리는 풀렸을 때만 보인다
## (아직 안 풀린 정리까지 `????`로 세면 칸 수가 부풀어 "몇 개 남았나"가 흐려진다).
static func render(flags: Array) -> String:
	var lines: PackedStringArray = []
	for s in SECTIONS:
		var got := 0
		for e in s["entries"]:
			if e[0] in flags:
				got += 1
		lines.append("[font_size=30][color=#e8dcc0]%s[/color][/font_size]  [color=#8a8478](%d/%d)[/color]"
			% [s["title"], got, s["entries"].size()])
		for e in s["entries"]:
			if e[0] in flags:
				lines.append("[color=#d6d2c8]·  %s[/color]" % e[1])
			else:
				lines.append("[color=#55524d]·  ????[/color]")
		for l in s["links"]:
			if _all_in(l[0], flags):
				lines.append("[color=#d9a441]→  %s[/color]" % l[1])
		lines.append("")
	return "\n".join(lines)
