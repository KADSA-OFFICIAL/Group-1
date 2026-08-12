#!/usr/bin/env python3
"""8비트 톤의 효과음을 합성해 assets/audio/*.wav로 쓴다 (#9).

외부 에셋을 받아오지 않는다 — 표준 라이브러리(wave/math/random)만으로 만든다.
라이선스 관리가 필요 없고, 톤이 마음에 안 들면 아래 SFX 표의 숫자를 고쳐
다시 돌리면 된다(gen_floors.py가 씬을 만드는 것과 같은 방식).

PR #173이 화면을 8비트 도트로 바꾸고 있어서 파형도 거기 맞췄다 —
사인파 대신 구형파·삼각파·의사 노이즈를 쓴다.

  python tools/gen_sfx.py            # 생성
  python tools/gen_sfx.py --check    # 생성하지 않고 기존 파일 점검만

결정론적이다. 노이즈는 고정 시드 LCG로 만들어 몇 번을 돌려도 같은 바이트가
나온다 — 재생성이 diff를 만들면 안 된다(random 모듈을 쓰지 않는 이유).

한국어 Windows에서는 UTF-8 강제가 필요하다: PYTHONUTF8=1 python ...
"""

from __future__ import annotations

import math
import pathlib
import struct
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets/audio"

RATE = 22050          # 레트로 감성 + 파일 크기. 8kHz는 너무 뭉개진다.
PEAK_CEILING = 0.89   # 클리핑 여유. 1.0까지 채우면 믹스에서 지직거린다.


# ── 파형 ─────────────────────────────────────────────────────────

class Noise:
    """고정 시드 선형합동 난수. random 모듈을 쓰면 파이썬 버전에 따라
    수열이 달라져 재생성이 diff를 만들 수 있다."""

    def __init__(self, seed: int = 20260812) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 2147483647.5 - 1.0


def square(phase: float, duty: float = 0.5) -> float:
    return 1.0 if (phase % 1.0) < duty else -1.0


def triangle(phase: float) -> float:
    position = phase % 1.0
    return 4.0 * abs(position - 0.5) - 1.0


def saw(phase: float) -> float:
    return 2.0 * (phase % 1.0) - 1.0


# ── 엔벨로프 ─────────────────────────────────────────────────────

def envelope(index: int, total: int, attack: float, release: float,
             curve: float = 1.0) -> float:
    """attack/release는 전체 길이에 대한 비율. curve>1이면 더 빨리 꺼진다."""
    attack_samples = max(int(total * attack), 1)
    release_samples = max(int(total * release), 1)
    if index < attack_samples:
        return index / attack_samples
    remaining = total - index
    if remaining < release_samples:
        return (remaining / release_samples) ** curve
    return 1.0


# ── 개별 소리 ────────────────────────────────────────────────────

def tone(duration: float, start_hz: float, end_hz: float, wave_fn,
         attack: float = 0.02, release: float = 0.35, curve: float = 1.0,
         duty: float = 0.5) -> list[float]:
    """start_hz에서 end_hz로 미끄러지는 음. 8비트 효과음의 기본 재료다."""
    total = int(RATE * duration)
    out: list[float] = []
    phase = 0.0
    for i in range(total):
        ratio = i / max(total - 1, 1)
        hz = start_hz * (end_hz / start_hz) ** ratio     # 지수 보간 = 음정 감각
        phase += hz / RATE
        value = wave_fn(phase, duty) if wave_fn is square else wave_fn(phase)
        out.append(value * envelope(i, total, attack, release, curve))
    return out


def noise_burst(duration: float, noise: Noise, low_pass: float = 0.35,
                attack: float = 0.01, release: float = 0.8,
                curve: float = 1.6) -> list[float]:
    """저역 통과를 건 노이즈. 발소리·철퍽·덜컹의 재료."""
    total = int(RATE * duration)
    out: list[float] = []
    filtered = 0.0
    for i in range(total):
        filtered += (noise.next() - filtered) * low_pass
        out.append(filtered * envelope(i, total, attack, release, curve))
    return out


def silence(duration: float) -> list[float]:
    return [0.0] * int(RATE * duration)


def mix(*layers: list[float]) -> list[float]:
    """길이가 다른 층을 겹친다. 가장 긴 것에 맞춘다."""
    length = max((len(layer) for layer in layers), default=0)
    out = [0.0] * length
    for layer in layers:
        for i, value in enumerate(layer):
            out[i] += value
    return out


def chain(*parts: list[float]) -> list[float]:
    out: list[float] = []
    for part in parts:
        out.extend(part)
    return out


def gain(samples: list[float], amount: float) -> list[float]:
    return [value * amount for value in samples]


def dc_block(samples: list[float], pole: float = 0.995) -> list[float]:
    """평균을 0으로 되돌리는 1차 고역 통과.

    duty가 0.5가 아닌 구형파는 평균이 0이 아니다(duty 0.28이면 -0.44). 그대로
    두면 소리가 시작·끝나는 순간 스피커가 튀어 "툭" 소리가 난다. 자체 점검이
    keys·ui_click에서 이걸 잡아냈다.
    """
    out: list[float] = []
    previous_in = 0.0
    previous_out = 0.0
    for value in samples:
        previous_out = value - previous_in + pole * previous_out
        previous_in = value
        out.append(previous_out)
    return out


# ── 소리 정의 ────────────────────────────────────────────────────
#
# 톤을 바꾸고 싶으면 여기 숫자만 고치고 다시 돌린다.

def build_all() -> dict[str, list[float]]:
    noise = Noise()
    sounds: dict[str, list[float]] = {}

    # 수위 발소리 — 낮고 둔탁하게. 순찰 속도(130)에 맞춰 짧게 끊는다.
    sounds["janitor_step"] = mix(
        gain(noise_burst(0.16, noise, low_pass=0.14, release=0.85), 0.9),
        gain(tone(0.10, 90, 55, triangle, release=0.7), 0.35),
    )

    # 열쇠꾸러미 — 짧은 고음 클릭 여러 개를 어긋나게 겹친다.
    keys_layers = []
    for offset, hz in ((0.00, 2600), (0.045, 3300), (0.085, 2100), (0.13, 2950)):
        keys_layers.append(chain(
            silence(offset),
            gain(tone(0.05, hz, hz * 0.82, square, attack=0.005,
                      release=0.9, curve=2.2, duty=0.28), 0.3),
        ))
    sounds["keys"] = mix(*keys_layers)

    # 문 열림 — 삐걱(느린 상승) + 걸쇠 딸깍
    sounds["door_open"] = mix(
        gain(tone(0.42, 210, 320, saw, attack=0.25, release=0.5), 0.16),
        gain(noise_burst(0.42, noise, low_pass=0.08, release=0.6), 0.3),
        chain(silence(0.34), gain(noise_burst(0.07, noise, low_pass=0.5), 0.45)),
    )

    # 잠긴 문 — 덜컹, 안 열림
    sounds["door_locked"] = mix(
        gain(noise_burst(0.18, noise, low_pass=0.22, release=0.9, curve=2.0), 0.75),
        gain(tone(0.12, 150, 96, square, release=0.8, duty=0.35), 0.3),
    )

    # 조사(E) — 짧고 건조한 블립
    sounds["investigate"] = gain(
        tone(0.09, 880, 1180, square, attack=0.02, release=0.6, duty=0.5), 0.34)

    # 아이템 획득 — 상승 아르페지오 3음
    sounds["pickup"] = chain(
        gain(tone(0.07, 660, 660, square, release=0.5, duty=0.5), 0.32),
        gain(tone(0.07, 880, 880, square, release=0.5, duty=0.5), 0.32),
        gain(tone(0.16, 1320, 1320, square, release=0.75, duty=0.5), 0.34),
    )

    # 은신 진입/퇴장 — 사물함 문 여닫힘(방향만 반대)
    sounds["hide_in"] = mix(
        gain(noise_burst(0.22, noise, low_pass=0.12, release=0.75), 0.5),
        gain(tone(0.20, 300, 150, triangle, release=0.7), 0.22),
    )
    sounds["hide_out"] = mix(
        gain(noise_burst(0.22, noise, low_pass=0.12, release=0.75), 0.5),
        gain(tone(0.20, 150, 300, triangle, release=0.7), 0.22),
    )

    # 계단 층 전환 — 내려가는 느낌의 하강 4음
    sounds["stairs"] = chain(
        gain(tone(0.08, 520, 520, triangle, release=0.5), 0.26),
        gain(tone(0.08, 440, 440, triangle, release=0.5), 0.26),
        gain(tone(0.08, 350, 350, triangle, release=0.5), 0.26),
        gain(tone(0.22, 262, 262, triangle, release=0.8), 0.28),
    )

    # 잉크통 던지기 — 공기 가르는 소리(고역 노이즈 하강)
    sounds["ink_throw"] = mix(
        gain(noise_burst(0.20, noise, low_pass=0.7, attack=0.15, release=0.6), 0.34),
        gain(tone(0.20, 700, 240, saw, attack=0.1, release=0.7), 0.12),
    )
    # 터짐 — 철퍽
    sounds["ink_splash"] = mix(
        gain(noise_burst(0.34, noise, low_pass=0.2, release=0.85, curve=1.8), 0.8),
        gain(tone(0.14, 260, 70, triangle, release=0.8), 0.3),
    )

    # 발각 스팅어 — 불협 2음이 위로 치솟는다
    sounds["spotted"] = mix(
        gain(tone(0.55, 300, 900, square, attack=0.01, release=0.45, duty=0.5), 0.3),
        gain(tone(0.55, 318, 954, square, attack=0.01, release=0.45, duty=0.5), 0.24),
    )

    # 체포 스팅어 — 무겁게 내려앉는다
    sounds["caught"] = mix(
        gain(tone(0.95, 420, 62, square, attack=0.01, release=0.55, duty=0.5), 0.32),
        gain(tone(0.95, 210, 31, triangle, attack=0.01, release=0.55), 0.26),
        gain(noise_burst(0.5, noise, low_pass=0.1, release=0.9), 0.22),
    )

    # 탈출 — 문 열림 + 해방되는 상승 화음
    sounds["escape"] = mix(
        gain(tone(0.9, 392, 784, triangle, attack=0.05, release=0.5), 0.26),
        chain(silence(0.12), gain(tone(0.78, 523, 1046, triangle,
                                       attack=0.05, release=0.5), 0.2)),
        gain(noise_burst(0.3, noise, low_pass=0.09, release=0.7), 0.2),
    )

    # UI 클릭
    sounds["ui_click"] = gain(
        tone(0.06, 1050, 700, square, attack=0.01, release=0.7, duty=0.3), 0.3)

    return sounds


# ── 쓰기·점검 ────────────────────────────────────────────────────

def normalize(samples: list[float]) -> tuple[list[float], float]:
    """피크가 천장을 넘으면만 줄인다. 소리마다 의도한 크기 차이를 지우지 않으려고
    항상 최대로 올리지는 않는다."""
    peak = max((abs(value) for value in samples), default=0.0)
    if peak > PEAK_CEILING:
        scale = PEAK_CEILING / peak
        return [value * scale for value in samples], peak
    return samples, peak


def write_wav(path: pathlib.Path, samples: list[float]) -> None:
    frames = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(value * 32767))))
        for value in samples)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(frames)


def check(name: str, samples: list[float], peak: float) -> list[str]:
    problems = []
    if not samples:
        problems.append(f"{name}: 비어 있다")
        return problems
    if len(samples) < RATE * 0.03:
        problems.append(f"{name}: 너무 짧다 ({len(samples) / RATE * 1000:.0f}ms)")
    if len(samples) > RATE * 3.0:
        problems.append(f"{name}: 너무 길다 ({len(samples) / RATE:.2f}s) — 효과음 범위를 넘는다")
    final_peak = max(abs(value) for value in samples)
    if final_peak > 0.999:
        problems.append(f"{name}: 클리핑 (피크 {final_peak:.3f})")
    if final_peak < 0.02:
        problems.append(f"{name}: 사실상 무음 (피크 {final_peak:.3f})")
    offset = sum(samples) / len(samples)
    if abs(offset) > 0.05:
        problems.append(f"{name}: DC 오프셋 {offset:+.3f} — 재생 시 툭 소리가 난다")
    return problems


def main() -> int:
    check_only = "--check" in sys.argv
    if not check_only:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    sounds = build_all()
    problems: list[str] = []
    total_bytes = 0
    for name, raw in sorted(sounds.items()):
        samples, raw_peak = normalize(dc_block(raw))
        problems.extend(check(name, samples, raw_peak))

        path = OUT_DIR / f"{name}.wav"
        if not check_only:
            write_wav(path, samples)
        size = path.stat().st_size if path.exists() else 0
        total_bytes += size
        print(f"  {name:16s} {len(samples) / RATE:5.2f}s  "
              f"피크 {max(abs(v) for v in samples):.2f}  {size / 1024:6.1f}KB"
              + ("  (천장 초과분 감쇠)" if raw_peak > PEAK_CEILING else ""))

    print(f"효과음 {len(sounds)}개, 합계 {total_bytes / 1024:.0f}KB")

    if problems:
        print(f"\n문제 {len(problems)}건:")
        for message in problems:
            print(f"  - {message}")
        return 1

    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
