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

# ── 필터·발소리 (#611) ───────────────────────────────────────────

def biquad(samples: list[float], kind: str, freq: float, q: float) -> list[float]:
    """2차 필터(RBJ 쿡북). 1차 저역 통과(noise_burst의 low_pass)로는 '어느 대역이
    울리는가'를 못 고른다 — 구두 뒤꿈치의 딱 소리와 바닥의 둔탁함은 대역이 다르다.

    kind: "low" / "high" / "band"(정점 이득 0dB).
    """
    w0 = math.tau * freq / RATE
    cos_w, alpha = math.cos(w0), math.sin(w0) / (2.0 * q)
    if kind == "low":
        b0, b1, b2 = (1 - cos_w) / 2, 1 - cos_w, (1 - cos_w) / 2
    elif kind == "high":
        b0, b1, b2 = (1 + cos_w) / 2, -(1 + cos_w), (1 + cos_w) / 2
    else:
        b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * cos_w, 1 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0

    out: list[float] = []
    x1 = x2 = y1 = y2 = 0.0
    for x in samples:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out.append(y)
    return out


def hit(noise: Noise, seconds: float, attack: float, decay: float,
        kind: str, freq: float, q: float) -> list[float]:
    """필터 건 노이즈 한 번의 타격. 지수 감쇠라 꼬리가 자연스럽게 사라진다.

    **발진기(삼각파·구형파)를 쓰지 않는다.** 예전 발소리는 삼각파가 90→55Hz로
    떨어지는 성분이 있어서 음정이 들렸고 그게 "뽁"이었다(#611). 신발과 바닥은
    음정 없이 대역만 있다.
    """
    total = int(RATE * seconds)
    attack_samples = max(int(RATE * attack), 1)
    raw = []
    for i in range(total):
        env = min(1.0, i / attack_samples) * math.exp(-i / (RATE * decay))
        raw.append(noise.next() * env)
    return biquad(raw, kind, freq, q)


def offset(samples: list[float], seconds: float) -> list[float]:
    return chain(silence(seconds), samples)


def footstep(seed: int, heel: float, toe_delay: float, click_hz: float,
             toe_weight: float) -> list[float]:
    """구두 한 걸음 — 뒤꿈치 착지 → 앞꿈치 스침 + 복도 반사음.

    느리게 걷는 어른은 뒤꿈치가 먼저 딱 닿고 60~90ms 뒤 앞꿈치가 내려앉는다.
    두 타격이 한 덩어리로 붙어 있으면 공이 튀는 소리(뽁)로 들리고, 갈라져 있어야
    발로 읽힌다. 뒤꿈치는 고역 딸깍 + 바닥 울림 + 몸무게(저역), 앞꿈치는 그보다
    약하고 무디다. 마지막으로 빈 복도의 짧은 반사를 얹는다 — 마른 소리만 있으면
    방음실 바닥을 두드리는 것처럼 들린다.
    """
    noise = Noise(seed=seed)
    dry = mix(
        # 뒤꿈치: 딱딱한 굽이 닿는 딸깍
        gain(hit(noise, 0.05, 0.0008, 0.007, "band", click_hz, 1.3), 0.55 * heel),
        # 뒤꿈치: 바닥이 받는 둔탁함
        gain(hit(noise, 0.09, 0.0015, 0.020, "band", 210.0, 1.8), 1.30 * heel),
        # 몸무게 — 가장 낮은 대역
        gain(hit(noise, 0.12, 0.004, 0.030, "low", 120.0, 0.7), 0.90 * heel),
        # 앞꿈치: 밑창이 내려앉는 소리. 굽보다 약하고 무디다.
        offset(gain(hit(noise, 0.10, 0.006, 0.028, "band", 950.0, 0.9),
                    0.42 * toe_weight), toe_delay),
        offset(gain(hit(noise, 0.08, 0.004, 0.022, "band", 300.0, 1.4),
                    0.55 * toe_weight), toe_delay),
        # 밑창이 바닥 먼지를 긁는 스침 — 두 타격 사이를 잇는다.
        gain(hit(noise, toe_delay + 0.06, 0.03, 0.035, "high", 3800.0, 0.7), 0.10),
    )

    # 복도 반사. 간격을 고르게 두면 금속성 울림(콤 필터)이 되므로 서로소에 가깝게
    # 흩는다. 반사는 벽이 고역을 먹으므로 저역 통과를 건다.
    reflections = [0.0] * (len(dry) + int(RATE * 0.16))
    for delay, amount in ((0.019, 0.30), (0.033, 0.22), (0.052, 0.16),
                          (0.077, 0.11), (0.101, 0.07), (0.139, 0.04)):
        start = int(RATE * delay)
        for i, value in enumerate(dry):
            reflections[start + i] += value * amount
    # 예전 발소리(피크 0.58)와 크기를 맞춘다. StepSound의 volume_db(-4)와 거리
    # 감쇠는 그 크기를 기준으로 맞춰 둔 값이다.
    return gain(mix(dry, biquad(reflections, "low", 2400.0, 0.7)), FOOTSTEP_LEVEL)


FOOTSTEP_LEVEL = 1.9

# 발소리 변형(#611). 같은 파일을 0.52초마다 되풀이하면 메트로놈이다 —
# 왼발(1·3)은 무겁고 앞꿈치가 늦게, 오른발(2·4)은 조금 가볍고 밝게 둔다.
# 재생 쪽(sound_manager.STEP_VARIANTS)이 번갈아 고르고 음높이도 흔든다.
JANITOR_STEPS = {
    "janitor_step":   dict(seed=61101, heel=1.00, toe_delay=0.074, click_hz=2700.0, toe_weight=1.00),
    "janitor_step_2": dict(seed=61102, heel=0.90, toe_delay=0.063, click_hz=3100.0, toe_weight=0.85),
    "janitor_step_3": dict(seed=61103, heel=1.00, toe_delay=0.081, click_hz=2500.0, toe_weight=0.95),
    "janitor_step_4": dict(seed=61104, heel=0.86, toe_delay=0.068, click_hz=2900.0, toe_weight=0.80),
}


def build_all() -> dict[str, list[float]]:
    noise = Noise()
    sounds: dict[str, list[float]] = {}

    # 수위 발소리 — 구두 한 걸음(뒤꿈치 → 앞꿈치 + 복도 반사), 변형 넷(#611).
    # 각자 고정 시드를 쓴다 — 공용 noise를 쓰면 다른 소리를 하나 더할 때마다
    # 발소리가 바뀐다.
    for name, params in JANITOR_STEPS.items():
        sounds[name] = footstep(**params)
    # 예전 발소리가 공용 noise에서 꺼내 쓰던 만큼(0.16초) 넘긴다. 안 넘기면
    # 뒤에 오는 문·은신·잉크·스팅어가 전부 다른 노이즈를 받아 바이트가 바뀐다.
    noise_burst(0.16, noise)

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
