extends SceneTree

## CI용 씬 로드 검증 스크립트 (Godot 헤드리스 전용).
## scenes/ 아래 모든 .tscn을 load + instantiate 해서 구조 오류를 잡는다.
## 실행: godot --headless --script res://tools/ci_load_scenes.gd
## 실패한 씬이 있으면 종료 코드 1.

const SCENES_DIR := "res://scenes"


func _init() -> void:
	var paths := _collect_scenes(SCENES_DIR)
	paths.sort()

	if paths.is_empty():
		printerr("검사할 씬을 찾지 못했다: ", SCENES_DIR)
		quit(1)
		return

	var failed: Array[String] = []

	for path in paths:
		var packed: Resource = load(path)
		if packed == null:
			printerr("LOAD FAILED: ", path)
			failed.append(path)
			continue

		if not packed is PackedScene:
			printerr("NOT A PackedScene: ", path)
			failed.append(path)
			continue

		var instance: Node = (packed as PackedScene).instantiate()
		if instance == null:
			printerr("INSTANTIATE FAILED: ", path)
			failed.append(path)
			continue

		print("  ok  ", path)
		instance.free()

	print("\n씬 %d개 검사, 실패 %d개" % [paths.size(), failed.size()])

	if not failed.is_empty():
		for path in failed:
			printerr("  실패: ", path)
		quit(1)
		return

	quit(0)


func _collect_scenes(dir_path: String) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		printerr("디렉터리를 열 수 없다: ", dir_path)
		return found

	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry.begins_with("."):
			entry = dir.get_next()
			continue

		var full := dir_path.path_join(entry)
		if dir.current_is_dir():
			found.append_array(_collect_scenes(full))
		elif entry.ends_with(".tscn"):
			found.append(full)

		entry = dir.get_next()
	dir.list_dir_end()

	return found
