#!/usr/bin/env python3
"""밤 학교 앰비언트와 추격 BGM(#176), 타이틀·프롤로그 테마(#606), 엔딩 테마 셋(#676)을
합성한다.

gen_sfx.py(#9)와 같은 원칙 — 표준 라이브러리만, 고정 시드, 결정론적.
파형 도구는 gen_sfx.py에서 가져다 쓴다(중복 정의하면 톤이 갈라진다).

효과음과 다른 점은 **루프**다. 끝과 처음이 이어져야 하므로

  1. 모든 재료를 루프 길이의 정수배 주기로 만든다(위상이 끝에서 0으로 돌아온다)
  2. 마지막에 루프 경계의 불연속(끝 샘플 ↔ 첫 샘플 차이)을 직접 측정해 검사한다

Godot 쪽 loop 설정은 .import 파일이 아니라 런타임에서 한다
(sound_manager.gd의 _prepare_loop) — .import는 에디터가 만드는 파일이라
커밋되지 않을 수 있어 의존하지 않는다.

  python tools/gen_music.py            # 생성
  python tools/gen_music.py --check    # 점검만

한국어 Windows에서는 UTF-8 강제가 필요하다: PYTHONUTF8=1 python ...
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from gen_sfx import (  # noqa: E402  (경로 조정 뒤에 임포트해야 한다)
    OUT_DIR, PEAK_CEILING, RATE, Noise, envelope, gain, mix,
    normalize, square, triangle, write_wav,
)

# 루프 길이. 길수록 반복이 덜 들리지만 파일이 커진다(22.05kHz 모노 = 초당 43KB).
AMBIENCE_SECONDS = 12.0
CHASE_SECONDS = 8.0

# 테마(#606)는 박자로 길이를 정한다 — 8마디(4/4) 한 바퀴.
# 템포는 한 박이 **정수 샘플**이 되는 값만 쓴다(22050·60/BPM). 72 → 18375,
# 70 → 18900. 66처럼 나누어떨어지지 않으면 마디가 반 샘플씩 밀려 루프 끝에서
# 박이 어긋난다.
TITLE_BPM = 72
PROLOGUE_BPM = 70
THEME_BARS = 8
BEATS_PER_BAR = 4

# 엔딩 테마(#676) — 엔딩마다 한 곡, 길이는 타이틀과 같은 8마디.
# 63 → 21000, 75 → 17640, 60 → 22050 샘플/박.
AFTER_SCHOOL_BPM = 63
ADULTS_WORK_BPM = 75
BREAK_TIME_BPM = 60

# 루프 경계에서 이만큼 넘게 튀면 "툭" 소리가 난다.
SEAM_TOLERANCE = 0.02


def cycles(hz: float, duration: float) -> float:
    """duration 안에 정수 번 들어가도록 주파수를 살짝 당긴다.

    이렇게 해야 루프 끝에서 위상이 정확히 0으로 돌아와 이음매가 안 들린다.
    12초 루프에서 55Hz를 55.0833Hz로 미는 정도라 음정 차이는 들리지 않는다.
    """
    return max(round(hz * duration), 1) / duration


def drone(duration: float, hz: float, wave_fn, amount: float) -> list[float]:
    """루프 안에서 위상이 딱 맞아떨어지는 지속음."""
    locked = cycles(hz, duration)
    total = int(RATE * duration)
    return [wave_fn(locked * i / RATE) * amount for i in range(total)]


def breathing(duration: float, hz: float, wave_fn, amount: float,
              sway_hz: float, sway_depth: float) -> list[float]:
    """음량이 천천히 오르내리는 지속음. 흔들림 주기도 루프에 맞춘다 —
    고정 음량 드론만 쌓으면 기계음처럼 들린다."""
    locked = cycles(hz, duration)
    locked_sway = cycles(sway_hz, duration)
    total = int(RATE * duration)
    out = []
    for i in range(total):
        seconds = i / RATE
        sway = 1.0 - sway_depth + sway_depth * (
            0.5 + 0.5 * math.sin(math.tau * locked_sway * seconds))
        out.append(wave_fn(locked * seconds) * amount * sway)
    return out


def creaks(duration: float, noise: Noise, count: int, amount: float) -> list[float]:
    """간헐적인 삐걱임. 루프 끝에 걸치지 않도록 앞쪽 구간에만 놓는다."""
    total = int(RATE * duration)
    out = [0.0] * total
    for _ in range(count):
        # 위치는 노이즈로 흩되 루프 끝 1.5초 안에는 두지 않는다.
        start = int(RATE * (0.4 + (duration - 1.9) * (abs(noise.next()) % 1.0)))
        length = int(RATE * (0.25 + 0.35 * abs(noise.next())))
        hz = 300.0 + 500.0 * abs(noise.next())
        for i in range(length):
            if start + i >= total:
                break
            ratio = i / length
            value = triangle((hz + 60.0 * ratio) * i / RATE)
            out[start + i] += value * amount * envelope(i, length, 0.4, 0.6, 1.4)
    return out


def pulse_track(duration: float, bpm: float, notes: list[float],
                amount: float, note_length: float) -> list[float]:
    """추격용 반복 음형. 박자 수가 루프 안에 정수로 들어가게 맞춘다."""
    total = int(RATE * duration)
    beat_samples = int(RATE * 60.0 / bpm)
    out = [0.0] * total

    beat = 0
    position = 0
    while position < total:
        hz = notes[beat % len(notes)]
        length = min(int(beat_samples * note_length), total - position)
        for i in range(length):
            value = square((hz * i) / RATE, 0.5)
            out[position + i] += value * amount * envelope(i, length, 0.02, 0.5, 1.2)
        position += beat_samples
        beat += 1
    return out


def build_ambience() -> list[float]:
    noise = Noise(seed=771103)
    duration = AMBIENCE_SECONDS
    return mix(
        # 건물이 내는 낮은 웅웅거림 — 두 음을 살짝 어긋나게 겹쳐 맥놀이를 만든다.
        breathing(duration, 55.0, triangle, 0.30, 0.08, 0.35),
        breathing(duration, 82.5, triangle, 0.16, 0.055, 0.45),
        drone(duration, 110.0, triangle, 0.05),
        creaks(duration, noise, count=5, amount=0.06),
    )


def build_chase() -> list[float]:
    duration = CHASE_SECONDS
    # 단조 반음 위주의 낮은 음형 — 쫓기는 느낌.
    bass = [98.0, 98.0, 104.0, 98.0, 87.0, 98.0, 104.0, 110.0]
    return mix(
        gain(pulse_track(duration, 150.0, bass, 0.30, 0.55), 1.0),
        gain(pulse_track(duration, 75.0, [49.0, 52.0], 0.22, 0.9), 1.0),
        breathing(duration, 294.0, triangle, 0.05, 0.5, 0.6),
    )


# ── 테마 (#606) ──────────────────────────────────────────────────
#
# 앰비언트·추격은 드론과 반복 음형이라 위상만 맞추면 루프가 됐다. 테마는
# 선율이라 음표가 루프 끝에 걸린다 — 마지막 마디의 오르골 꼬리가 끝을 넘는다.
# 잘라 내면 되감길 때 소리가 뚝 끊기므로, 넘친 꼬리를 **처음으로 감아 넣는다**
# (place). 한 바퀴를 돌고 들어오는 첫 마디에는 앞 바퀴의 잔향이 실려 있어
# 실제로 연주가 이어지는 것처럼 들린다.

NOTE_NAMES = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6,
              "G": 7, "G#": 8, "A": 9, "Bb": 10, "B": 11}


def hz(name: str) -> float:
    """"G#4" → 415.30. 옥타브 숫자는 과학적 음높이 표기(C4 = 가온 다)."""
    pitch, octave = name[:-1], int(name[-1])
    midi = 12 * (octave + 1) + NOTE_NAMES[pitch]
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def place(out: list[float], start: int, samples: list[float],
          amount: float = 1.0) -> None:
    """루프 버퍼에 음을 얹는다. 끝을 넘친 부분은 처음으로 감는다."""
    total = len(out)
    start %= total
    for i, value in enumerate(samples):
        out[(start + i) % total] += value * amount


def tail_fade(index: int, total: int, ratio: float = 0.12) -> float:
    """음 끝을 0으로 내린다. 감쇠가 덜 끝난 채 자르면 그 자리에서 툭 튄다."""
    fade = max(int(total * ratio), 1)
    remaining = total - index
    return remaining / fade if remaining < fade else 1.0


def music_box(freq: float, seconds: float, detune_cents: float = 0.0,
              wow: float = 0.004, decay: float = 0.85) -> list[float]:
    """오르골 한 음. 삼각파에 2배·3배음을 얕게 얹어 쇠붙이 소리를 낸다.

    3배음을 정확히 3이 아니라 3.01로 둔 것은 금속 빗살의 비조화 배음 흉내다.
    wow는 태엽이 고르게 안 풀리는 느린 음정 흔들림 — '고장 난' 느낌의 절반이다.
    나머지 절반은 음마다 다른 detune(몇 센트 낮게)이 낸다.
    """
    total = int(RATE * seconds)
    base = freq * 2.0 ** (detune_cents / 1200.0)
    attack = int(RATE * 0.004)
    out: list[float] = []
    phase = 0.0
    for i in range(total):
        t = i / RATE
        phase += base * (1.0 + wow * math.sin(math.tau * 0.7 * t)) / RATE
        value = (triangle(phase) * 0.75 + triangle(phase * 2.0) * 0.18
                 + triangle(phase * 3.01) * 0.07)
        env = math.exp(-t / decay) * min(1.0, i / attack) * tail_fade(i, total)
        out.append(value * env)
    return out


def soft_bass(freq: float, seconds: float, decay: float = 1.6) -> list[float]:
    """마디 첫 박의 낮은 음. 오르골만 있으면 바닥이 없어 장난감처럼 들린다."""
    total = int(RATE * seconds)
    attack = int(RATE * 0.03)
    out: list[float] = []
    for i in range(total):
        t = i / RATE
        env = math.exp(-t / decay) * min(1.0, i / attack) * tail_fade(i, total, 0.2)
        out.append(triangle(freq * t) * env)
    return out


def pad(freqs: list[float], seconds: float) -> list[float]:
    """화음 패드. 음마다 두 줄을 몇 센트 어긋나게 겹쳐(코러스) 숨을 쉬게 한다.

    양 끝 35%가 사인 곡선으로 오르내리므로, 마디보다 길게 잡아 앞뒤 마디와
    겹쳐 놓으면 화음이 이음매 없이 바뀐다.
    """
    total = int(RATE * seconds)
    edge = int(total * 0.35)
    out: list[float] = []
    for i in range(total):
        t = i / RATE
        if i < edge:
            env = math.sin(0.5 * math.pi * i / edge) ** 2
        elif total - i < edge:
            env = math.sin(0.5 * math.pi * (total - i) / edge) ** 2
        else:
            env = 1.0
        value = 0.0
        for freq in freqs:
            value += triangle(freq * t) + triangle(freq * 1.004 * t)
        out.append(value * env / (2 * len(freqs)))
    return out


def thump(seconds: float = 0.42) -> list[float]:
    """밤길 걸음 같은 낮은 둥. 음정이 90 → 45Hz로 떨어지는 삼각파."""
    total = int(RATE * seconds)
    out: list[float] = []
    phase = 0.0
    for i in range(total):
        ratio = i / total
        phase += 90.0 * (0.5 ** ratio) / RATE
        out.append(triangle(phase) * envelope(i, total, 0.03, 0.85, 2.2))
    return out


def theme_grid(bpm: int, bars: int = THEME_BARS) -> tuple[int, int, int]:
    """(한 박 샘플 수, 한 마디 샘플 수, 전체 샘플 수)."""
    beat = RATE * 60 // bpm
    assert beat * bpm == RATE * 60, f"{bpm} BPM은 한 박이 정수 샘플이 아니다"
    bar = beat * BEATS_PER_BAR
    return beat, bar, bar * bars


def chord(*names: str) -> list[float]:
    return [hz(name) for name in names]


def build_title() -> list[float]:
    """학교 종소리(웨스트민스터 차임)를 단조로 비튼 오르골.

    한국 학교 종 "미도레솔 / 솔레미도"는 장조의 3·1·2·5도다. 같은 도수를
    가단조에 옮기면 C·A·B·E — 윤곽과 리듬은 그대로라 누구나 종소리로 알아듣는데
    음색이 어둡다. 방과 후, 아무도 없는 학교에서 혼자 울리는 종.
    """
    beat, bar, total = theme_grid(TITLE_BPM)
    out = [0.0] * total
    noise = Noise(seed=606001)

    # 마디마다 (화음, 베이스, [(박, 음, 길이(박))]).
    # 1~4마디 종소리 두 소절, 5~6마디 대답, 7~8마디는 태엽이 풀리며 성글어진다.
    score = [
        (chord("A3", "C4", "E4"), "A2", [(0, "C5", 1), (1, "A4", 1), (2, "B4", 1), (3, "E4", 1)]),
        (chord("G#3", "B3", "E4"), "E2", [(0, "E4", 1), (1, "B4", 1), (2, "C5", 1), (3, "A4", 1)]),
        (chord("A3", "C4", "E4"), "A2", [(0, "C5", 1), (1, "B4", 1), (2, "A4", 1), (3, "E4", 1)]),
        (chord("G#3", "B3", "E4"), "E2", [(0, "E4", 1), (1, "B4", 1), (2, "C5", 1), (3, "A4", 1)]),
        (chord("D3", "F3", "A3"), "D2", [(0, "F5", 1), (1, "E5", 1), (2, "D5", 1), (3, "A4", 1)]),
        (chord("G#3", "B3", "E4"), "E2", [(0, "B4", 1), (1, "G#4", 1), (2, "A4", 2)]),
        (chord("F3", "A3", "C4"), "F2", [(0, "A4", 2), (2.5, "E4", 1.5)]),
        (chord("G#3", "B3", "D4"), "E2", [(0, "B3", 3)]),
    ]

    for index, (harmony, root, notes) in enumerate(score):
        bar_start = index * bar
        # 패드는 앞뒤로 1/4마디씩 넘쳐 이웃 화음과 겹친다(첫 마디 앞쪽은 끝으로 감긴다).
        place(out, bar_start - bar // 4, pad(harmony, 1.5 * bar / RATE), 0.10)
        place(out, bar_start, soft_bass(hz(root), 2.2 * bar / RATE), 0.22)
        for when, name, length in notes:
            # 음마다 0~-14센트 처진다 — 조율이 풀린 빗살.
            detune = -7.0 - 7.0 * noise.next()
            seconds = max(length * beat / RATE + 1.4, 2.0)
            # 마지막 마디는 태엽이 다 풀린 것처럼 흔들림이 커진다.
            wow = 0.012 if index == len(score) - 1 else 0.004
            place(out, bar_start + int(when * beat),
                  music_box(hz(name), seconds, detune, wow), 0.42)
            # 낮은 옥타브 메아리 — 빈 교실에 울리는 잔향.
            place(out, bar_start + int((when + 0.75) * beat),
                  music_box(hz(name) / 2.0, seconds, detune, wow, 0.6), 0.08)
    return out


def build_prologue() -> list[float]:
    """학원에서 학교로 걷는 밤길. 느린 걸음 박동 위에 패드, 가로등 같은 높은 음.

    5~6마디에서 타이틀의 종소리가 반 박자로 느려져 멀리서 한 번 들린다 — 학교가
    가까워진다. 7마디의 Bb 화음(가단조 위의 나폴리 화음)이 뒷문 앞의 불안이고,
    8마디의 E로 첫 마디 Am에 되돌아간다.
    """
    beat, bar, total = theme_grid(PROLOGUE_BPM)
    out = [0.0] * total

    harmony = [
        chord("A2", "E3", "B3", "C4"),     # Am(add9)
        chord("F2", "C3", "E3", "A3"),     # Fmaj7
        chord("A2", "E3", "B3", "C4"),
        chord("G2", "D3", "E3", "B3"),     # G6
        chord("D3", "F3", "A3", "C4"),     # Dm7
        chord("F2", "C3", "E3", "A3"),
        chord("Bb2", "D3", "F3", "A3"),    # Bbmaj7 — 불안
        chord("E2", "B2", "D3", "G#3"),    # E7
    ]
    for index, freqs in enumerate(harmony):
        place(out, index * bar - bar // 4, pad(freqs, 1.5 * bar / RATE), 0.16)
        place(out, index * bar, soft_bass(freqs[0] / 2.0, 1.6 * bar / RATE, 2.4), 0.20)

    # 걸음: 1·3박. 둘째 걸음은 조금 약하게 — 똑같으면 메트로놈이다.
    for index in range(THEME_BARS):
        place(out, index * bar, thump(), 0.30)
        place(out, index * bar + 2 * beat, thump(), 0.22)

    # 가로등: 성긴 높은 음. 박 끝에 걸쳐 두고 3/4박 뒤 메아리를 두 번.
    lamps = [(0, 1.5, "E5"), (1, 3.5, "C6"), (2, 1.5, "B5"), (3, 2.5, "E5"),
             (6, 1.5, "D5"), (7, 0.5, "G#5")]
    for index, when, name in lamps:
        start = index * bar + int(when * beat)
        voice = music_box(hz(name), 2.4, -4.0, 0.002, 0.7)
        place(out, start, voice, 0.16)
        place(out, start + int(0.75 * beat), voice, 0.07)
        place(out, start + int(1.5 * beat), voice, 0.03)

    # 멀리서 들리는 종소리 — 타이틀 동기를 2박씩 늘려 5~6마디에.
    for step, name in enumerate(["C5", "A4", "B4", "E4"]):
        start = 4 * bar + step * 2 * beat
        voice = music_box(hz(name), 3.2, -10.0, 0.006, 1.1)
        place(out, start, voice, 0.20)
        place(out, start + beat, voice, 0.08)
    return out


# ── 엔딩 테마 (#676) ─────────────────────────────────────────────
#
# 엔딩 셋(#353)이 각자 한 곡이고, 셋 다 타이틀의 학교 종 동기(가단조 C·A·B·E)를
# 쓴다 — 같은 종이 결말마다 다르게 울린다.
#
#   방과 후      종이 더 고장 났다. 둘째 소절의 마지막 음(A)이 끝내 안 온다 —
#                아무에게도 말하지 못한 결말.
#   어른들의 일  종 대신 일정한 낮은 박동(굴러가는 절차)과 형광등 같은 높은
#                지속음. 종 동기는 라단조로 낮게 한 번 지나가고, 마지막 화음은
#                3음이 없는 sus4라 풀리지 않는다.
#   쉬는 시간    앞 네 마디는 고장 난 종, 뒤 네 마디에서 같은 도수가 처음으로
#                **장조 원형**("미도레솔 / 솔레미도")으로, 조율된 오르골로 울린다 —
#                마지막 장면의 "종이 울렸다".


def ring(out: list[float], start: int, beat: int,
         notes: list[tuple[float, str, float]], noise: Noise, amount: float,
         detune: tuple[float, float], wow: float, decay: float = 0.85,
         echo: float = 0.08) -> None:
    """마디 하나의 오르골 선율. notes는 [(박, 음, 길이(박))].

    detune은 (최소, 최대) 센트 — 음마다 그 사이에서 처진다. echo는 3/4박 뒤
    한 옥타브 아래 메아리의 크기다(타이틀과 같은 잔향).
    """
    for when, name, length in notes:
        cents = detune[0] + (detune[1] - detune[0]) * (0.5 + 0.5 * noise.next())
        seconds = max(length * beat / RATE + 1.4, 2.0)
        place(out, start + int(when * beat),
              music_box(hz(name), seconds, cents, wow, decay), amount)
        if echo > 0.0:
            place(out, start + int((when + 0.75) * beat),
                  music_box(hz(name) / 2.0, seconds, cents, wow, decay * 0.7), echo)


def build_after_school() -> list[float]:
    """기본 엔딩 "방과 후". 타이틀보다 느리고, 더 풀리고, 선율이 점점 성겨진다.

    2마디에서 종 동기의 둘째 소절(E·B·C·A)이 C에서 멈춘다 — 4박이 비어 있다.
    5마디부터 종이 반으로 성겨지고 8마디는 화음만 남는다. 마지막 화음이 3음
    없는 Esus4라 단조로 돌아가는 첫 마디가 해결이 아니라 되풀이로 들린다.
    """
    beat, bar, total = theme_grid(AFTER_SCHOOL_BPM)
    out = [0.0] * total
    noise = Noise(seed=676001)

    score = [
        (chord("A3", "C4", "E4"), "A2", [(0, "C5", 1), (1, "A4", 1), (2, "B4", 1), (3, "E4", 1)]),
        # E·B·C 다음의 A가 안 온다.
        (chord("E3", "A3", "B3"), "E2", [(0, "E4", 1), (1, "B4", 1), (2, "C5", 1)]),
        (chord("F3", "A3", "C4", "E4"), "F2", [(0, "C5", 1.5), (1.5, "B4", 0.5), (2, "A4", 2)]),
        (chord("D3", "F3", "A3"), "D2", [(0, "F4", 2), (2, "E4", 2)]),
        (chord("A3", "C4", "E4"), "A2", [(0, "C5", 2), (2, "A4", 2)]),
        (chord("E3", "A3", "B3"), "E2", [(0, "B4", 2), (2, "E4", 2)]),
        (chord("F3", "A3", "C4"), "F2", [(0, "E4", 3)]),
        (chord("E3", "A3", "B3"), "E2", []),
    ]
    for index, (harmony, root, notes) in enumerate(score):
        bar_start = index * bar
        place(out, bar_start - bar // 4, pad(harmony, 1.5 * bar / RATE), 0.11)
        place(out, bar_start, soft_bass(hz(root), 2.2 * bar / RATE), 0.22)
        # 타이틀(-7~-14센트, wow 0.004)보다 더 처지고 더 흔들린다.
        ring(out, bar_start, beat, notes, noise, 0.40, (-18.0, -6.0), 0.008)
    return out


def build_adults_work() -> list[float]:
    """신고 엔딩 "어른들의 일". 라단조, 박마다 짧고 낮은 음이 일정하게 굴러간다.

    오르골이 주인공이 아니다 — 절차가 굴러가는 소리(박동)와 형광등(높은 A의
    지속음)이 깔리고, 종 동기는 5~6마디에 라단조 도수(F·D·E·A)로 낮게 한 번만
    지나간다. 형광등의 A가 7마디 Eb 화음(나폴리)과 증4도로 부딪친다 — 경찰서의
    "지나치게 밝은" 불빛 아래의 불안이다.
    """
    beat, bar, total = theme_grid(ADULTS_WORK_BPM)
    out = [0.0] * total
    noise = Noise(seed=676002)

    harmony = [
        (chord("D3", "A3", "E4", "F4"), "D2"),     # Dm(add9)
        (chord("Bb2", "F3", "A3", "D4"), "Bb1"),   # Bbmaj7
        (chord("G2", "D3", "F3", "Bb3"), "G1"),    # Gm7
        (chord("A2", "D3", "E3", "A3"), "A1"),     # Asus4 — 3음 없음
        (chord("D3", "A3", "E4", "F4"), "D2"),
        (chord("Bb2", "F3", "A3", "D4"), "Bb1"),
        (chord("Eb3", "G3", "Bb3", "D4"), "Eb2"),  # Ebmaj7 — 나폴리
        (chord("A2", "D3", "E3", "A3"), "A1"),
    ]
    for index, (freqs, root) in enumerate(harmony):
        bar_start = index * bar
        place(out, bar_start - bar // 4, pad(freqs, 1.5 * bar / RATE), 0.12)
        place(out, bar_start, soft_bass(hz(root), 1.6 * bar / RATE, 2.0), 0.20)
        # 박동: 근음 한 옥타브 위를 짧게 뜯는다. 1·3박이 강하다 — 똑같으면 메트로놈이다.
        tick = soft_bass(hz(root) * 2.0, 0.45, 0.12)
        for step in range(BEATS_PER_BAR):
            place(out, bar_start + step * beat, tick, 0.17 if step % 2 == 0 else 0.10)

    # 형광등 — 화음이 바뀌어도 그대로인 높은 A. 천천히 숨을 쉰다.
    hum = breathing(total / RATE, hz("A5"), triangle, 0.022, 0.4, 0.5)
    for i, value in enumerate(hum):
        out[i] += value

    # 위쪽의 성긴 선율 — 1~4마디 질문, 7~8마디는 A에서 멈춘다.
    upper = [
        (0, [(0, "E5", 2)]), (1, [(0, "D5", 2)]), (2, [(0, "F5", 2)]), (3, [(0, "E5", 1)]),
        (6, [(0, "Bb4", 2), (2, "G4", 2)]), (7, [(0, "A4", 4)]),
    ]
    for index, notes in upper:
        ring(out, index * bar, beat, notes, noise, 0.22, (-5.0, -2.0), 0.002, 1.0, 0.05)

    # 종 동기 — 라단조 3·1·2·5도(F·D·E·A)를 두 박씩, 낮게.
    bell = [(0, "F4", 2), (2, "D4", 2), (4, "E4", 2), (6, "A3", 2)]
    ring(out, 4 * bar, beat, bell, noise, 0.30, (-4.0, -2.0), 0.002, 1.4, 0.10)
    return out


def build_break_time() -> list[float]:
    """히든 엔딩 "쉬는 시간". 고장 난 종이 네 마디 만에 고쳐진다.

    1~4마디는 타이틀과 같은 가단조 종(C·A·B·E)이 처진 오르골로 울린다. 4마디
    끝의 E 화음이 5마디 C장조로 반음계적으로 넘어가며 같은 도수가 장조 원형
    (E·C·D·G / G·D·E·C — "미도레솔 / 솔레미도")이 된다. 이 절반은 조율이 맞고
    (detune 0) 흔들림이 거의 없고 잔향이 길다. 8마디 C에서 1마디 Am으로는
    나란한조라 매끄럽게 되감긴다.
    """
    beat, bar, total = theme_grid(BREAK_TIME_BPM)
    out = [0.0] * total
    noise = Noise(seed=676003)

    broken = [
        (chord("A3", "C4", "E4"), "A2", [(0, "C5", 1), (1, "A4", 1), (2, "B4", 1), (3, "E4", 1)]),
        (chord("G#3", "B3", "E4"), "E2", [(0, "E4", 1), (1, "B4", 1), (2, "C5", 1), (3, "A4", 1)]),
        (chord("F3", "A3", "C4", "E4"), "F2", [(0, "C5", 1), (1, "B4", 1), (2, "A4", 1), (3, "E4", 1)]),
        (chord("G#3", "B3", "D4", "E4"), "E2", [(0, "E4", 1), (1, "B4", 1), (2, "C5", 2)]),
    ]
    whole = [
        (chord("C3", "E3", "G3", "B3"), "C2", [(0, "E5", 1), (1, "C5", 1), (2, "D5", 1), (3, "G4", 1)]),
        (chord("G2", "D3", "G3", "B3"), "G1", [(0, "G4", 1), (1, "D5", 1), (2, "E5", 1), (3, "C5", 1)]),
        (chord("F3", "A3", "C4", "E4"), "F2", [(0, "E5", 1), (1, "D5", 1), (2, "C5", 1), (3, "G4", 1)]),
        (chord("C3", "E3", "G3"), "C2", [(0, "G4", 1), (1, "D5", 1), (2, "E5", 1), (3, "C5", 1)]),
    ]
    for index, (harmony, root, notes) in enumerate(broken):
        bar_start = index * bar
        place(out, bar_start - bar // 4, pad(harmony, 1.5 * bar / RATE), 0.09)
        place(out, bar_start, soft_bass(hz(root), 2.2 * bar / RATE), 0.20)
        ring(out, bar_start, beat, notes, noise, 0.36, (-14.0, -4.0), 0.006)
    for index, (harmony, root, notes) in enumerate(whole, start=len(broken)):
        bar_start = index * bar
        # 고쳐진 쪽은 화음이 두텁고 따뜻하다.
        place(out, bar_start - bar // 4, pad(harmony, 1.5 * bar / RATE), 0.13)
        place(out, bar_start, soft_bass(hz(root), 2.2 * bar / RATE, 2.2), 0.22)
        ring(out, bar_start, beat, notes, noise, 0.40, (0.0, 0.0), 0.0015, 1.2, 0.11)
    return out


def dc_block_loop(samples: list[float], pole: float = 0.995) -> list[float]:
    """루프용 DC 차단.

    gen_sfx의 dc_block은 필터 상태가 0에서 시작한다. 일회성 효과음에서는
    문제가 없지만 루프에서는 시작 부분만 과도응답이 실려 되감기는 순간
    값이 튄다(앰비언트에서 0.0268 — 자체 검사가 잡아냈다).
    한 바퀴 미리 돌려 상태를 정상 구간으로 데워 두면 끝과 처음이 이어진다.
    """
    previous_in = 0.0
    previous_out = 0.0
    for value in samples:            # 워밍업 — 출력은 버린다
        previous_out = value - previous_in + pole * previous_out
        previous_in = value

    out: list[float] = []
    for value in samples:
        previous_out = value - previous_in + pole * previous_out
        previous_in = value
        out.append(previous_out)
    return out


def seam_gap(samples: list[float]) -> float:
    """루프가 되감길 때의 순간 점프량."""
    return abs(samples[0] - samples[-1]) if samples else 0.0


def main() -> int:
    check_only = "--check" in sys.argv
    if not check_only:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    tracks = {"ambience": build_ambience(), "chase": build_chase(),
              "title": build_title(), "prologue": build_prologue(),
              "ending_after_school": build_after_school(),
              "ending_adults_work": build_adults_work(),
              "ending_break_time": build_break_time()}
    problems: list[str] = []

    for name, raw in sorted(tracks.items()):
        samples, raw_peak = normalize(dc_block_loop(raw))
        path = OUT_DIR / f"{name}.wav"
        if not check_only:
            write_wav(path, samples)

        gap = seam_gap(samples)
        peak = max(abs(value) for value in samples)
        size = path.stat().st_size if path.exists() else 0
        print(f"  {name:10s} {len(samples) / RATE:5.2f}s  피크 {peak:.2f}  "
              f"이음매 {gap:.4f}  {size / 1024:6.0f}KB"
              + ("  (천장 초과분 감쇠)" if raw_peak > PEAK_CEILING else ""))

        if gap > SEAM_TOLERANCE:
            problems.append(f"{name}: 루프 이음매가 {gap:.4f} 튄다 "
                            f"(허용 {SEAM_TOLERANCE}) — 되감길 때 툭 소리가 난다")
        if peak > 0.999:
            problems.append(f"{name}: 클리핑 (피크 {peak:.3f})")
        if peak < 0.05:
            problems.append(f"{name}: 사실상 무음 (피크 {peak:.3f})")

    if problems:
        print(f"\n문제 {len(problems)}건:")
        for message in problems:
            print(f"  - {message}")
        return 1

    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
