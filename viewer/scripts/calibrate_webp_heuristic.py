#!/usr/bin/env python3
"""Calibrate WebP compress heuristics on sample JPEGs (Pillow; close to browser canvas)."""
from __future__ import annotations

import json
import math
import statistics
from io import BytesIO
from pathlib import Path

from PIL import Image

TARGET = 450 * 1024
ROOT = Path(__file__).resolve().parents[2]
MAX_EDGE = 2048  # speed: downscale huge photos before sweep
GAMMA = 3.2
PROBE_Q = 0.82


def collect_samples(limit: int = 12) -> list[Path]:
    paths: list[Path] = []
    for pattern in ("data/**/*.jpg", "data/**/*.jpeg", "extract_server/data/**/*.jpg"):
        paths.extend(ROOT.glob(pattern))
    unique = sorted({p.resolve() for p in paths if p.is_file()})
    return [p for p in unique if p.stat().st_size > TARGET][:limit]


def load_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img.load()
    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    return img


def encode_webp(img: Image.Image, scale: float, quality: float) -> tuple[bytes, int, int]:
    w = max(1, round(img.width * scale))
    h = max(1, round(img.height * scale))
    resized = img.resize((w, h), Image.Resampling.LANCZOS)
    buf = BytesIO()
    resized.save(buf, format="WEBP", quality=max(1, min(100, int(round(quality * 100)))))
    return buf.getvalue(), w, h


def find_best_under_target(img: Image.Image) -> tuple[int, float, float]:
    """Coarse grid ground truth."""
    best: tuple[int, float, float] | None = None
    for scale in (1.0, 0.85, 0.7, 0.55, 0.4, 0.3):
        for q in (0.9, 0.75, 0.6, 0.45, 0.3):
            data, _, _ = encode_webp(img, scale, q)
            if len(data) <= TARGET and (best is None or len(data) > best[0]):
                best = (len(data), scale, q)
    if best is None:
        data, _, _ = encode_webp(img, 0.25, 0.25)
        return len(data), 0.25, 0.25
    return best


def guess_from_original(orig_bytes: int, pixels: int, target_bytes: int) -> tuple[float, float]:
    """Heuristic from JPEG file size + pixel count (no encode)."""
    ratio = target_bytes / orig_bytes
    megapixels = pixels / 1_000_000
    # Fitted loosely from grocery photo set; re-run this script to refresh.
    scale = min(1.0, max(0.2, ratio ** 0.42 * (1.0 + 0.08 * max(0, megapixels - 2))))
    quality = min(0.92, max(0.3, 0.55 + 0.12 * math.log10(orig_bytes / target_bytes)))
    return scale, quality


def probe_extrapolate(img: Image.Image) -> tuple[int, float, float, int]:
    data, _, _ = encode_webp(img, 1.0, PROBE_Q)
    s0 = len(data)
    if s0 <= TARGET:
        q = min(0.95, PROBE_Q * (TARGET / s0) ** (1 / GAMMA))
        out, _, _ = encode_webp(img, 1.0, q)
        return len(out), 1.0, q, 2 if q != PROBE_Q else 1

    scale = min(1.0, math.sqrt(TARGET / s0) * 0.96)
    out, _, _ = encode_webp(img, scale, PROBE_Q)
    encodes = 2
    if len(out) > TARGET:
        scale *= math.sqrt(TARGET / len(out))
        out, _, _ = encode_webp(img, scale, PROBE_Q)
        encodes = 3
    return len(out), scale, PROBE_Q, encodes


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return slope, my - slope * mx


def main() -> None:
    rows = []
    for path in collect_samples():
        orig = path.stat().st_size
        img = load_image(path)
        pixels = img.width * img.height
        bpp = orig / pixels
        best_size, best_scale, best_q = find_best_under_target(img)
        guess_scale, guess_q = guess_from_original(orig, pixels, TARGET)
        guess_data, _, _ = encode_webp(img, guess_scale, guess_q)
        probe_size, probe_scale, probe_q, probe_encodes = probe_extrapolate(img)
        rows.append(
            {
                "file": path.name,
                "orig": orig,
                "pixels": pixels,
                "bpp": round(bpp, 4),
                "best": {"size": best_size, "scale": best_scale, "q": best_q},
                "guess": {"size": len(guess_data), "scale": guess_scale, "q": guess_q},
                "probe": {
                    "size": probe_size,
                    "scale": probe_scale,
                    "q": probe_q,
                    "encodes": probe_encodes,
                },
            }
        )

    print(f"Samples: {len(rows)} (target {TARGET // 1024} KB)\n")
    for r in rows:
        print(
            f"{r['file']}: orig {r['orig']//1024}KB | "
            f"best {r['best']['size']//1024}KB s={r['best']['scale']:.2f} q={r['best']['q']:.2f} | "
            f"probe {r['probe']['size']//1024}KB ({r['probe']['encodes']} enc) | "
            f"guess {r['guess']['size']//1024}KB"
        )

    log_orig = [math.log(r["orig"]) for r in rows]
    print("\nRegression (ground-truth scale/q vs log orig bytes):")
    for key in ("best",):
        ys_scale = [r[key]["scale"] for r in rows]
        ys_q = [r[key]["q"] for r in rows]
        s_scale, i_scale = linear_fit(log_orig, ys_scale)
        s_q, i_q = linear_fit(log_orig, ys_q)
        print(f"  scale = {s_scale:.4f} * log(orig) + {i_scale:.4f}")
        print(f"  q     = {s_q:.4f} * log(orig) + {i_q:.4f}")

    log_bpp = [math.log(r["bpp"]) for r in rows]
    s_q, i_q = linear_fit(log_bpp, [r["best"]["q"] for r in rows])
    print(f"  q vs log(bpp): {s_q:.4f} * log(bpp) + {i_q:.4f}")

    def under(rows_, path: str) -> int:
        return sum(1 for r in rows_ if r[path]["size"] <= TARGET)

    print(
        f"\nUnder target: guess {under(rows,'guess')}/{len(rows)}, "
        f"probe {under(rows,'probe')}/{len(rows)}, "
        f"best {under(rows,'best')}/{len(rows)}"
    )
    print(f"Avg probe encodes: {statistics.mean(r['probe']['encodes'] for r in rows):.1f}")

    out = Path(__file__).with_name("calibrate_webp_results.json")
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
