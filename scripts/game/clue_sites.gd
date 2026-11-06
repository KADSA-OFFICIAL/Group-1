## 생성물 — tools/gen_floors.py가 `CLUE_SITES`에서 쓴다. 손으로 고치지 말 것(#794).
##
## 층 → 묶음 목록. 묶음마다 함께 움직이는 노드(`nodes`)와 후보 자리(`sites`)가
## 있고, 자리마다 방 키·노드 자리(`pos`)·상호작용 표시 자리(`mark`)·가리키는 말(`hint`).
## 첫 후보가 씬에 구워진 기본 자리다. 고르기·적용은 `clue_shuffle.gd`.
extends RefCounted

const SITES := {
	3: [
		{
			"nodes": ["KeyCabinet", "SpareKeyHook"],
			"sites": [
				{"room": "North5", "hint": "", "pos": [Vector2(1558, 420), Vector2(1558, 480)], "mark": [Vector2(1558, 420), Vector2(1558, 480)]},
				{"room": "North3", "hint": "", "pos": [Vector2(990, 280), Vector2(1050, 280)], "mark": [Vector2(990, 280), Vector2(1050, 280)]},
				{"room": "North6", "hint": "", "pos": [Vector2(2098, 150), Vector2(2098, 210)], "mark": [Vector2(2098, 150), Vector2(2098, 210)]},
			],
		},
		{
			"nodes": ["NayeonClue"],
			"sites": [
				{"room": "North4", "hint": "", "pos": [Vector2(1200, 268)], "mark": [Vector2(1200, 268)]},
				{"room": "CareerDept", "hint": "", "pos": [Vector2(1140, 1252)], "mark": [Vector2(1140, 1252)]},
				{"room": "North2", "hint": "", "pos": [Vector2(640, 280)], "mark": [Vector2(640, 280)]},
			],
		},
		{
			"nodes": ["CounselRecord"],
			"sites": [
				{"room": "North4", "hint": "", "pos": [Vector2(1455, 268)], "mark": [Vector2(1455, 268)]},
				{"room": "North1", "hint": "", "pos": [Vector2(300, 280)], "mark": [Vector2(300, 280)]},
				{"room": "Class6", "hint": "", "pos": [Vector2(600, 1350)], "mark": [Vector2(600, 1350)]},
			],
		},
		{
			"nodes": ["JanitorWarning"],
			"sites": [
				{"room": "North5", "hint": "", "pos": [Vector2(1800, 290)], "mark": [Vector2(1800, 290)]},
				{"room": "CareerDept", "hint": "", "pos": [Vector2(795, 1460)], "mark": [Vector2(795, 1460)]},
				{"room": "North6", "hint": "", "pos": [Vector2(2180, 280)], "mark": [Vector2(2180, 280)]},
			],
		},
		{
			"nodes": ["ReportFlyer"],
			"sites": [
				{"room": "CareerDept", "hint": "", "pos": [Vector2(860, 1250)], "mark": [Vector2(860, 1250)]},
				{"room": "Class6", "hint": "", "pos": [Vector2(300, 1350)], "mark": [Vector2(300, 1350)]},
				{"room": "North2", "hint": "", "pos": [Vector2(603, 160)], "mark": [Vector2(603, 160)]},
			],
		},
		{
			"nodes": ["InkCan"],
			"sites": [
				{"room": "StorageR", "hint": "", "pos": [Vector2(2090, 893.6)], "mark": [Vector2(2090, 893.6)]},
				{"room": "CareerDept", "hint": "", "pos": [Vector2(1310, 1460)], "mark": [Vector2(1310, 1460)]},
				{"room": "North3", "hint": "", "pos": [Vector2(978, 160)], "mark": [Vector2(978, 160)]},
			],
		},
		{
			"nodes": ["ScienceClue"],
			"sites": [
				{"room": "ScienceLab1", "hint": "", "pos": [Vector2(1990, 1280)], "mark": [Vector2(1990, 1280)]},
				{"room": "StorageR", "hint": "", "pos": [Vector2(2040, 790)], "mark": [Vector2(2040, 790)]},
				{"room": "Class6", "hint": "", "pos": [Vector2(520, 1350)], "mark": [Vector2(520, 1350)]},
			],
		},
		{
			"nodes": ["TaehoNote"],
			"sites": [
				{"room": "ScienceLab1", "hint": "", "pos": [Vector2(2190, 1280)], "mark": [Vector2(2190, 1280)]},
				{"room": "North1", "hint": "", "pos": [Vector2(232, 160)], "mark": [Vector2(232, 160)]},
				{"room": "StorageR", "hint": "", "pos": [Vector2(2110, 790)], "mark": [Vector2(2110, 790)]},
			],
		},
	],
	2: [
		{
			"nodes": ["HeadKey"],
			"sites": [
				{"room": "StorageR", "hint": "2층 창고 적재함", "pos": [Vector2(2215, 950)], "mark": [Vector2(2173, 950)]},
				{"room": "North2", "hint": "2층 2반 교실", "pos": [Vector2(640, 280)], "mark": [Vector2(598, 280)]},
				{"room": "WomensRoomL", "hint": "2층 여자 화장실", "pos": [Vector2(1215, 850)], "mark": [Vector2(1173, 850)]},
			],
		},
		{
			"nodes": ["YujinClue"],
			"sites": [
				{"room": "PEDept", "hint": "", "pos": [Vector2(946.7, 1390.8)], "mark": [Vector2(946.7, 1390.8)]},
				{"room": "PEStorage", "hint": "", "pos": [Vector2(680, 1250)], "mark": [Vector2(680, 1250)]},
				{"room": "North1", "hint": "", "pos": [Vector2(300, 280)], "mark": [Vector2(300, 280)]},
			],
		},
		{
			"nodes": ["CrisisManual"],
			"sites": [
				{"room": "PEDept", "hint": "", "pos": [Vector2(1158, 1391)], "mark": [Vector2(1158, 1391)]},
				{"room": "North4", "hint": "", "pos": [Vector2(1200, 268)], "mark": [Vector2(1200, 268)]},
				{"room": "EduRoom", "hint": "", "pos": [Vector2(2060, 1290)], "mark": [Vector2(2060, 1290)]},
			],
		},
		{
			"nodes": ["HistoryClue"],
			"sites": [
				{"room": "StorageR", "hint": "", "pos": [Vector2(2000, 950)], "mark": [Vector2(2000, 950)]},
				{"room": "EduRoom", "hint": "", "pos": [Vector2(2110, 1350)], "mark": [Vector2(2110, 1350)]},
				{"room": "North4", "hint": "", "pos": [Vector2(1455, 268)], "mark": [Vector2(1455, 268)]},
			],
		},
		{
			"nodes": ["ShowerMarks"],
			"sites": [
				{"room": "MensRoomL", "hint": "", "pos": [Vector2(880, 935)], "mark": [Vector2(880, 935)]},
				{"room": "WomensRoomL", "hint": "", "pos": [Vector2(1155, 935)], "mark": [Vector2(1155, 935)]},
			],
		},
	],
	1: [
		{
			"nodes": ["PrincipalLetter"],
			"sites": [
				{"room": "PrincipalRoom", "hint": "", "pos": [Vector2(1570, 290)], "mark": [Vector2(1570, 290)]},
				{"room": "StaffRoom", "hint": "", "pos": [Vector2(1200, 480)], "mark": [Vector2(1200, 480)]},
				{"room": "NurseRoom", "hint": "", "pos": [Vector2(270, 440)], "mark": [Vector2(270, 440)]},
			],
		},
		{
			"nodes": ["StudentCards"],
			"sites": [
				{"room": "JanitorRoom", "hint": "", "pos": [Vector2(1520, 800)], "mark": [Vector2(1520, 800)]},
				{"room": "StaffRoom", "hint": "", "pos": [Vector2(1110, 330)], "mark": [Vector2(1110, 330)]},
				{"room": "PrincipalRoom", "hint": "", "pos": [Vector2(1460, 470)], "mark": [Vector2(1460, 470)]},
			],
		},
		{
			"nodes": ["JanitorNotebook"],
			"sites": [
				{"room": "JanitorRoom", "hint": "", "pos": [Vector2(1810, 800)], "mark": [Vector2(1810, 800)]},
				{"room": "Entrance", "hint": "", "pos": [Vector2(1400, 800)], "mark": [Vector2(1400, 800)]},
				{"room": "NurseRoom", "hint": "", "pos": [Vector2(410, 440)], "mark": [Vector2(410, 440)]},
			],
		},
	],
}

## 다른 묶음의 자리를 말하는 단서: 노드 → [그 노드의 층, 대상 층, 대상 묶음 첫 노드].
## 문구 속 대상의 **첫 후보 hint**를 그 판에 고른 후보의 hint로 바꾼다.
const HINT_TARGETS := {"KeyCabinet": [3, "2", "HeadKey"]}
