#!/usr/bin/env python3
"""외부 음원을 게임용으로 가공한다(#713). 표준 라이브러리만.

**원본 팩은 저장소에 넣지 않는다** — Liminal Games 팩은 "팩 자체를 재배포하지
말 것"이 조건이고, 원본 wav는 곡당 10~24MB다. 여기서 가공한 결과
(`assets/audio/ext/*.wav`)만 커밋하고, 출처·라이선스는 `CREDITS.md`에 적는다.

    python3 tools/import_ext_audio.py <Horror Sound Pack 폴더> <Liminal PCM 폴더>

- `<Horror Sound Pack 폴더>`: phlegmlee "Horror Sound Pack.zip"을 푼 곳(`Music/`이 있는 폴더).
- `<Liminal PCM 폴더>`: Liminal Games "horror_sfx_vol_1"의 MP3를 PCM wav로 푼 곳.
  표준 라이브러리로는 MP3를 못 풀어서 브라우저의 `decodeAudioData`로 한 번
  풀었다(모노로 섞은 16bit wav — `wind7.wav`, `creak6.wav`).

**루프는 그대로 쓰면 안 된다.** "Loopable"이라고 적힌 곡도 첫 0.25초가 디지털
무음이고 몇 초에 걸쳐 페이드인한다(실측: 끝 -26dB → 처음 -41dB). 그대로 돌리면
한 바퀴마다 소리가 푹 꺼진다. 그래서 페이드인을 건너뛴 자리(`skip`)에서 루프를
시작하고, 마지막 `xfade`초를 그 시작 구간과 교차 페이드해 이음매를 없앤다 —
끝에서 시작으로 넘어가는 순간 이미 시작 구간의 소리가 나고 있다.
"""
import array
import math
import pathlib
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/audio/ext"
RATE = 22050          # 게임의 다른 소리와 같은 샘플레이트(gen_sfx/gen_music)
TAPS = 31             # 44100 → 22050 저역 통과 필터 길이


def read_mono(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit(f"{path.name}: 16bit만 받는다({sw * 8}bit)")
    a = array.array("h", raw)
    if sys.byteorder != "little":
        a.byteswap()
    out = array.array("f", [0.0]) * n
    for i in range(n):
        s = 0
        for c in range(ch):
            s += a[i * ch + c]
        out[i] = s / ch / 32768.0
    return out, sr


def rms_db(x):
    return 20 * math.log10(math.sqrt(sum(v * v for v in x) / len(x)) + 1e-12)


def peak_db(x):
    return 20 * math.log10(max(abs(v) for v in x) + 1e-12)


def make_loop(x, sr, skip, xfade, cut_end=0.0):
    """페이드인을 건너뛰고 끝을 시작 구간과 교차 페이드한 루프."""
    s, c = int(skip * sr), int(xfade * sr)
    end = len(x) - int(cut_end * sr)
    body = x[s + c:end]
    head = x[s:s + c]
    n = len(body)
    for i in range(c):
        t = (i + 0.5) / c
        # 등전력 — 서로 다른 구간을 섞으므로 진폭이 아니라 에너지를 보존한다.
        body[n - c + i] = body[n - c + i] * math.cos(t * math.pi / 2) \
            + head[i] * math.sin(t * math.pi / 2)
    return body


def halve(x, circular):
    """44100 → 22050. 창 씌운 sinc 저역 통과 후 한 칸씩 건너뛴다.

    루프는 **원형으로** 거른다 — 끝 샘플의 필터가 처음 샘플을 본다. 아니면
    이음매 양쪽 15샘플이 0으로 채워진 것처럼 걸러져 딸깍 소리가 난다.
    """
    half = TAPS // 2
    fc = 0.225                           # 약 9.9kHz / 44.1kHz
    h = []
    for k in range(-half, half + 1):
        sinc = 2 * fc if k == 0 else math.sin(2 * math.pi * fc * k) / (math.pi * k)
        win = 0.42 + 0.5 * math.cos(math.pi * k / half) + 0.08 * math.cos(2 * math.pi * k / half)
        h.append(sinc * win)
    g = sum(h)
    h = [v / g for v in h]
    n = len(x)
    out = array.array("f", [0.0]) * (n // 2)
    for j in range(n // 2):
        i = 2 * j
        acc = 0.0
        for k in range(TAPS):
            idx = i + k - half
            if circular:
                idx %= n
            elif idx < 0 or idx >= n:
                continue
            acc += h[k] * x[idx]
        out[j] = acc
    return out


def gain_to(x, rms_target=None, peak_max=-1.0):
    """RMS를 목표에 맞추되 피크가 `peak_max`를 넘으면 그만큼 덜 올린다."""
    g = 0.0 if rms_target is None else rms_target - rms_db(x)
    g = min(g, peak_max - peak_db(x)) if rms_target is not None else peak_max - peak_db(x)
    k = 10 ** (g / 20)
    for i in range(len(x)):
        x[i] *= k
    return x


def write(name, x):
    OUT.mkdir(parents=True, exist_ok=True)
    a = array.array("h", (max(-32767, min(32767, int(round(v * 32767)))) for v in x))
    if sys.byteorder != "little":
        a.byteswap()
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(a.tobytes())


def check_loop(name, x):
    """이음매 검사 — 끝과 처음의 샘플 차, 양쪽 0.25초 크기 차."""
    q = RATE // 4
    jump = abs(x[-1] - x[0])
    gap = abs(rms_db(x[-q:]) - rms_db(x[:q]))
    if jump > 0.05 or gap > 4.0:
        raise SystemExit(f"{name}: 이음매가 튄다(샘플 차 {jump:.3f}, 크기 차 {gap:.1f}dB)")
    return jump, gap


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    pack, pcm = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    jobs = [
        # (출력, 원본, 페이드인 건너뛰기, 교차 페이드, 끝 자르기, 목표 RMS)
        # 본편 앰비언트 — 3초부터 고른 크기(-13~-17dB)가 이어진다.
        ("ambience_dark.wav", pack / "Music/Dark Ambient Music - Loopable.wav", 3.0, 2.0, 0.0, -16.0),
        # 추격 — 7초 주기로 맥박이 친다. 4초부터가 첫 맥박.
        ("chase_eerie.wav", pack / "Music/Eerie Loop.wav", 4.0, 2.0, 0.0, None),
        # 운동장 바람 — 22초 내내 -36dB로 고른 것을 골랐다. 끝 0.3초는 디코더 꼬리라 자른다.
        ("yard_wind.wav", pcm / "wind7.wav", 0.5, 1.5, 0.3, -20.0),
    ]
    for name, src, skip, xf, cut, target in jobs:
        x, sr = read_mono(src)
        if sr != 44100:
            raise SystemExit(f"{src.name}: 44100Hz가 아니다({sr})")
        y = halve(make_loop(x, sr, skip, xf, cut), circular=True)
        gain_to(y, target)
        jump, gap = check_loop(name, y)
        write(name, y)
        print(f"{name}: {len(y) / RATE:.1f}s RMS {rms_db(y):.1f}dB 피크 {peak_db(y):.1f}dB "
              f"이음매 {jump:.4f}/{gap:.1f}dB")

    # 문 여닫기 — 1초짜리 삐걱임. 루프가 아니라 꼬리 무음만 잘라 낸다.
    x, sr = read_mono(pcm / "creak6.wav")
    y = halve(x, circular=False)
    last = max(i for i, v in enumerate(y) if abs(v) > 10 ** (-60 / 20))
    y = y[:last + 1]
    fade = int(0.02 * RATE)
    for i in range(fade):
        y[len(y) - fade + i] *= 1 - (i + 1) / fade
    gain_to(y, None, peak_max=-3.0)
    write("door_creak.wav", y)
    print(f"door_creak.wav: {len(y) / RATE:.2f}s RMS {rms_db(y):.1f}dB 피크 {peak_db(y):.1f}dB")


if __name__ == "__main__":
    main()
