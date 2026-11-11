#!/usr/bin/env python3
"""긴 음악(루프·테마)을 Ogg Vorbis로 굽는다(#855).

**마스터는 PCM wav다** — `assets/audio/masters/`(`.gdignore`라 Godot이 안 읽고
내보내기에도 안 들어간다). 거기 있는 wav를 전부 같은 상대 경로의 `.ogg`로
`assets/audio/` 아래에 굽는다.

    assets/audio/masters/title.wav           → assets/audio/title.ogg
    assets/audio/masters/ext/chase_eerie.wav → assets/audio/ext/chase_eerie.ogg

마스터를 만드는 쪽은 그대로다 — `gen_music.py`(타이틀·프롤로그·엔딩)와
`import_ext_audio.py`(외부 루프 셋)가 마스터 폴더에 쓰고, 이 도구가 뒤를 잇는다.
외부 음원의 원본 팩은 저장소에 없으므로(#713) 마스터를 지우면 다시 못 굽는다.

    python3 tools/encode_music.py            # 굽고 검사
    python3 tools/encode_music.py --check    # 검사만(이미 구운 ogg를 마스터와 대조)

**표준 라이브러리만으로는 Vorbis를 못 굽는다.** `soundfile`(libsndfile 휠, Vorbis
쓰기 내장)과 `numpy`가 필요하다: `pip install soundfile numpy`.

#185에서 QOA(손실)가 지글거림·딸깍을 냈다 — 20샘플마다 4비트 잔차로 깎는 코덱이라
사각파 모서리를 못 따라갔다. Vorbis는 MDCT 지각 코덱이고 품질을 높게 잡는다
(`QUALITY`). 효과음은 짧아서 이득이 없으므로 PCM 그대로다.

**결정론적이다.** libsndfile은 Ogg 스트림 일련번호를 무작위로 고르므로 그대로면
같은 마스터를 구워도 바이트가 매번 달라 diff가 생긴다. 페이지마다 일련번호를
`SERIAL`로 고정하고 CRC를 다시 계산한다(인코딩 자체는 결정론적이다).

검사(실패하면 종료 코드 1):
  - 디코드한 샘플 수 = 마스터 샘플 수. 인코더 패딩·프리스킵으로 길이가 바뀌면
    루프 주기가 어긋나 매 바퀴 박자가 밀린다.
  - 루프 이음매(끝 → 처음 점프)가 마스터보다 `SEAM_SLACK` 넘게 커지지 않는다.
  - 마스터 대비 신호 대 잡음비가 `MIN_SNR_DB` 이상(깨진 인코딩만 잡는 문턱이다).
"""
from __future__ import annotations

import io
import pathlib
import struct
import sys

try:
    import numpy as np
    import soundfile as sf
except ImportError:
    raise SystemExit("soundfile·numpy가 필요하다: pip install soundfile numpy")

ROOT = pathlib.Path(__file__).resolve().parent.parent
MASTERS = ROOT / "assets/audio/masters"
OUT = ROOT / "assets/audio"

## libsndfile의 압축 단계(0~1). Vorbis 품질 = 1 - 이 값이라 0.2 = q0.8(약 q8).
## 22050Hz 모노에서 곡당 200KB 안팎이다 — 0.3(q7)보다 10% 크지만 손실 코덱으로
## 한 번 데인 자리(#185)라 한 단 위로 잡았다.
QUALITY = 0.2
SERIAL = 0x0B55_855  # 아무 값이나 고정이면 된다(이슈 번호를 넣었다).
SEAM_SLACK = 0.02
## 파형 SNR은 귀가 듣는 품질이 아니다 — 지각 코덱은 잡음성 고역(추격 루프의
## 쇳소리 질감)을 파형째 맞추지 않으므로 그런 곡은 낮게 나온다(실측: 음정 있는
## 곡 36~38dB, 바람 29dB, 추격 23.6dB — q1.0으로 올려도 26.7dB). 이 문턱은 음질
## 판정이 아니라 **인코딩이 깨졌는지**(엉뚱한 파일·채널·샘플레이트)만 잡는다.
MIN_SNR_DB = 20.0


def _crc_table() -> list[int]:
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
        table.append(r & 0xFFFFFFFF)
    return table


_CRC = _crc_table()


def _ogg_crc(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CRC[((crc >> 24) & 0xFF) ^ b]
    return crc


def fix_serial(data: bytes) -> bytes:
    """모든 Ogg 페이지의 일련번호를 SERIAL로 바꾸고 CRC를 다시 쓴다."""
    out = bytearray()
    pos = 0
    while pos < len(data):
        if data[pos:pos + 4] != b"OggS":
            raise SystemExit(f"Ogg 페이지가 아니다(오프셋 {pos})")
        segments = data[pos + 26]
        table = data[pos + 27:pos + 27 + segments]
        size = 27 + segments + sum(table)
        page = bytearray(data[pos:pos + size])
        struct.pack_into("<I", page, 14, SERIAL)
        struct.pack_into("<I", page, 22, 0)
        struct.pack_into("<I", page, 22, _ogg_crc(bytes(page)))
        out += page
        pos += size
    return bytes(out)


def encode(x: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, x, rate, format="OGG", subtype="VORBIS", compression_level=QUALITY)
    return fix_serial(buf.getvalue())


def check(name: str, x: np.ndarray, data: bytes) -> list[str]:
    y, _ = sf.read(io.BytesIO(data), dtype="float64")
    problems = []
    if len(y) != len(x):
        problems.append(f"{name}: 길이가 바뀌었다({len(x)} → {len(y)}샘플) — 루프 주기가 어긋난다")
        return problems
    seam_x = abs(x[-1] - x[0])
    seam_y = abs(y[-1] - y[0])
    if seam_y > seam_x + SEAM_SLACK:
        problems.append(f"{name}: 루프 이음매가 커졌다({seam_x:.4f} → {seam_y:.4f})")
    err = y - x
    snr = 10 * np.log10(np.sum(x * x) / max(np.sum(err * err), 1e-20))
    if snr < MIN_SNR_DB:
        problems.append(f"{name}: 원본 대비 SNR {snr:.1f}dB < {MIN_SNR_DB}")
    print(f"  {name:28s} {len(x) / 22050:5.1f}s  {len(data) / 1024:6.0f}KB  "
          f"SNR {snr:5.1f}dB  이음매 {seam_x:.4f}→{seam_y:.4f}")
    return problems


def main() -> int:
    check_only = "--check" in sys.argv
    masters = sorted(MASTERS.rglob("*.wav"))
    if not masters:
        raise SystemExit(f"마스터가 없다: {MASTERS}")
    problems: list[str] = []
    total_wav = total_ogg = 0
    for src in masters:
        rel = src.relative_to(MASTERS).with_suffix(".ogg")
        dst = OUT / rel
        x, rate = sf.read(str(src), dtype="float64")
        if x.ndim != 1:
            problems.append(f"{rel}: 모노가 아니다")
            continue
        if check_only:
            if not dst.exists():
                problems.append(f"{rel}: ogg가 없다 — 굽지 않았다")
                continue
            data = dst.read_bytes()
            if data != encode(x, rate):
                problems.append(f"{rel}: 마스터에서 다시 구운 것과 다르다 — 굽기를 다시 돌릴 것")
        else:
            data = encode(x, rate)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        problems += check(str(rel), x, data)
        total_wav += src.stat().st_size
        total_ogg += len(data)

    print(f"  합계 wav {total_wav / 1e6:.2f}MB → ogg {total_ogg / 1e6:.2f}MB")
    if problems:
        print(f"\n문제 {len(problems)}건:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
