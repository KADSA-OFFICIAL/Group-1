extends SceneTree

## CI용 씬 로드 검증 스크립트 (Godot 헤드리스 전용).
## scenes/ 아래 모든 .tscn을 load + instantiate 하고, scripts/ 아래 모든 .gd를
## 컴파일해서 구조 오류와 스크립트 오류를 잡는다.
## 실행: godot --headless --script res://tools/ci_load_scenes.gd
## 실패한 씬이나 스크립트가 있으면 종료 코드 1.
##
## _init()이 아니라 _initialize()에서 도는 이유(#183): --script로 넘긴 MainLoop는
## main.cpp가 autoload 전역 상수(Sfx 등)를 등록하기 *전에* 인스턴스화한다.
## _init()에서 씬을 로드하면 Sfx를 참조하는 스크립트가 전부
## "Compile Error: Identifier not found: Sfx"로 컴파일에 실패하고, 씬은 스크립트가
## 빠진 채로 멀쩡히 로드되므로 검사가 통과해 버린다. _initialize()는 OS::run()이
## Main::start() 뒤에 부르므로 autoload가 이미 등록돼 있다.

const SCENES_DIR := "res://scenes"
const SCRIPTS_DIR := "res://scripts"


func _initialize() -> void:
	var failed: Array[String] = []

	failed.append_array(_check_autoloads())
	failed.append_array(_check_scripts())
	failed.append_array(_check_scenes())

	if not failed.is_empty():
		printerr("")
		for path in failed:
			printerr("  실패: ", path)
		quit(1)
		return

	quit(0)


## autoload가 실제로 등록됐는지 확인한다. 등록 전에 검사가 돌면 스크립트 컴파일이
## 통째로 실패하는데도 씬 로드는 성공하므로, 조용히 무의미한 검사로 되돌아간다.
## 엔진 버전이 올라가 순서가 바뀌면 여기서 먼저 걸리게 한다.
func _check_autoloads() -> Array[String]:
	var failed: Array[String] = []
	var expected := _autoload_names()

	if expected.is_empty():
		print("autoload 없음 (project.godot)")
		return failed

	for autoload_name in expected:
		if root.has_node(NodePath(autoload_name)):
			print("  ok  autoload ", autoload_name)
		else:
			printerr("AUTOLOAD MISSING: ", autoload_name)
			failed.append("autoload " + autoload_name)

	return failed


func _autoload_names() -> Array[String]:
	var names: Array[String] = []
	for info in ProjectSettings.get_property_list():
		var key: String = info.get("name", "")
		if key.begins_with("autoload/"):
			names.append(key.trim_prefix("autoload/"))
	names.sort()
	return names


## 씬에 붙지 않은 스크립트까지 포함해 전부 컴파일해 본다. 씬만 검사하면
## 스크립트가 빠진 채로 인스턴스화가 성공해 버리므로 이 검사가 따로 필요하다.
##
## null 검사만으로는 부족하다 — 파스 오류가 난 스크립트도 load()는
## "Failed to load script ... Parse error"를 찍은 뒤 **null이 아닌** 무효
## GDScript를 돌려준다(CI run 31898238404에서 확인). 유효성은
## can_instantiate()로 본다(GDScript::can_instantiate은 컴파일 성공 여부다).
func _check_scripts() -> Array[String]:
	var failed: Array[String] = []
	var paths := _collect(SCRIPTS_DIR, ".gd")
	paths.sort()

	if paths.is_empty():
		printerr("검사할 스크립트를 찾지 못했다: ", SCRIPTS_DIR)
		return ["(스크립트 없음) " + SCRIPTS_DIR]

	for path in paths:
		var compiled: Resource = load(path)
		if compiled == null or not (compiled is GDScript):
			printerr("SCRIPT LOAD FAILED: ", path)
			failed.append(path)
			continue

		if not (compiled as GDScript).can_instantiate():
			printerr("SCRIPT LOAD FAILED (컴파일 실패): ", path)
			failed.append(path)
			continue

		print("  ok  ", path)

	print("스크립트 %d개 검사, 실패 %d개" % [paths.size(), failed.size()])
	return failed


func _check_scenes() -> Array[String]:
	var failed: Array[String] = []
	var paths := _collect(SCENES_DIR, ".tscn")
	paths.sort()

	if paths.is_empty():
		printerr("검사할 씬을 찾지 못했다: ", SCENES_DIR)
		return ["(씬 없음) " + SCENES_DIR]

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

	print("씬 %d개 검사, 실패 %d개" % [paths.size(), failed.size()])
	return failed


func _collect(dir_path: String, suffix: String) -> Array[String]:
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
			found.append_array(_collect(full, suffix))
		elif entry.ends_with(suffix):
			found.append(full)

		entry = dir.get_next()
	dir.list_dir_end()

	return found
