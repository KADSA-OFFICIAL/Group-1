extends RefCounted
## 판마다 단서·열쇠 자리를 고른다(#794).
##
## 1~3층의 단서·열쇠는 층 씬에 기본 자리(첫 후보)로 구워져 있고, 후보 표는
## `clue_sites.gd`(`tools/gen_floors.py`의 `CLUE_SITES`에서 나온 생성물)에 있다.
## 새 판을 시작하면(`GameState._ready`, 체크포인트 복원이 아닐 때) `new_run()`이
## 묶음마다 후보 하나를 고르고, `floor_manager._swap_floor()`가 층 씬을 트리에
## **붙이기 전에** `apply()`로 노드와 상호작용 표시(`WallGlow/Marks/Mark_<이름>`)를
## 옮긴다 — 붙인 뒤에 옮기면 `_ready`에서 자리를 읽는 것들(표시 밝기·근접
## 클로즈업)이 첫 프레임을 기본 자리로 본다.
##
## **집기는 모든 후보 자리를 피하게 구워져 있다**(`gen_floors.SITE_CLEAR`). 그래서
## 여기서는 옮기기만 하면 되고, 어느 후보든 걸어서 닿는지는
## `tools/verify_clue_sites.py`가 후보 번호마다 씬을 다시 구워 본다.

const ClueSites = preload("res://scripts/game/clue_sites.gd")

## 묶음("층:첫 노드") → 고른 후보 번호. static이라 층 씬·본편 씬이 바뀌어도 남는다 —
## 체크포인트 재시도는 같은 배치를 이어 쓰고(그 층에서 이미 본 단서가 그 자리에
## 있어야 한다), 새 판에서만 다시 고른다.
static var _choice: Dictionary = {}


## 새 판의 배치를 고른다. `seed_value`를 주면 그 시드로(스모크가 쓴다).
static func new_run(seed_value: int = -1) -> void:
	var rng := RandomNumberGenerator.new()
	if seed_value >= 0:
		rng.seed = seed_value
	else:
		rng.randomize()
	_choice.clear()
	for fl in ClueSites.SITES:
		for group in ClueSites.SITES[fl]:
			var sites: Array = group["sites"]
			_choice[_key(int(fl), str(group["nodes"][0]))] = rng.randi_range(0, sites.size() - 1)


## 묶음(첫 노드 이름)에 고른 후보 번호. 아직 안 골랐으면 지금 고른다 —
## 에디터에서 층 씬만 띄운 경우 등.
static func choice(fl: int, first_node: String) -> int:
	if _choice.is_empty():
		new_run()
	return int(_choice.get(_key(fl, first_node), 0))


## 묶음에 고른 후보(`{"room", "hint", "pos", "mark"}`). 그런 묶음이 없으면 빈 사전.
static func site(fl: int, first_node: String) -> Dictionary:
	var group := _group(fl, first_node)
	if group.is_empty():
		return {}
	return group["sites"][choice(fl, first_node)]


## 층 씬(트리에 붙이기 전)의 단서·표시를 이 판의 자리로 옮긴다.
static func apply(floor_root: Node, fl: int) -> void:
	if not ClueSites.SITES.has(fl):
		return
	for group in ClueSites.SITES[fl]:
		var nodes: Array = group["nodes"]
		var chosen: Dictionary = group["sites"][choice(fl, str(nodes[0]))]
		for i in nodes.size():
			var node := floor_root.get_node_or_null(NodePath(str(nodes[i]))) as Node2D
			if node != null:
				node.position = chosen["pos"][i]
			var mark := floor_root.get_node_or_null(
				NodePath("WallGlow/Marks/Mark_" + str(nodes[i]))) as Node2D
			if mark != null:
				mark.position = chosen["mark"][i]
	# 다른 묶음의 자리를 말하는 단서 — 3층 열쇠 보관함 점검표가 2층 열쇠 방을 가리킨다.
	for node_name in ClueSites.HINT_TARGETS:
		var target: Array = ClueSites.HINT_TARGETS[node_name]
		if int(target[0]) != fl:
			continue
		var node := floor_root.get_node_or_null(NodePath(str(node_name)))
		var group := _group(int(target[1]), str(target[2]))
		if node == null or group.is_empty() or not ("message" in node):
			continue
		var default_hint: String = group["sites"][0]["hint"]
		var chosen_hint: String = site(int(target[1]), str(target[2]))["hint"]
		node.set("message", str(node.get("message")).replace(default_hint, chosen_hint))


static func _group(fl: int, first_node: String) -> Dictionary:
	for group in ClueSites.SITES.get(fl, []):
		if str(group["nodes"][0]) == first_node:
			return group
	return {}


static func _key(fl: int, first_node: String) -> String:
	return "%d:%s" % [fl, first_node]
