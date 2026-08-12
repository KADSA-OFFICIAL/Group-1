#!/usr/bin/env python3
"""밤 학교 앰비언트와 추격 BGM을 합성한다 (#176).

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

    tracks = {"ambience": build_ambience(), "chase": build_chase()}
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
