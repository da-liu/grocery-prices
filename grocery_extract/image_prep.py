from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from grocery_extract.exif import tool_path

LLM_MAX_DIM = 1280
DEFAULT_LLM_SCALE_PERCENT = 25


def _image_dimensions(image_path: Path) -> tuple[int, int]:
    width = subprocess.check_output(
        [tool_path("sips"), "-g", "pixelWidth", str(image_path)],
        text=True,
    )
    height = subprocess.check_output(
        [tool_path("sips"), "-g", "pixelHeight", str(image_path)],
        text=True,
    )
    w = int(width.strip().rsplit(":", 1)[-1].strip())
    h = int(height.strip().rsplit(":", 1)[-1].strip())
    return w, h


def resize_to_scale_percent(source: Path, scale_pct: float, dest: Path) -> tuple[int, int, int]:
    """Resize image to scale_pct of original max dimension. Returns (width, height, bytes)."""
    source = source.resolve()
    width, height = _image_dimensions(source)
    max_dim = max(1, round(max(width, height) * scale_pct / 100))
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [tool_path("sips"), "-Z", str(max_dim), "-s", "format", "jpeg", str(source), "--out", str(dest)],
        check=True,
        capture_output=True,
    )
    out_w, out_h = _image_dimensions(dest)
    return out_w, out_h, dest.stat().st_size


def llm_scale_percent() -> int:
    raw = os.environ.get("GROCERY_EXTRACT_SCALE_PCT", str(DEFAULT_LLM_SCALE_PERCENT)).strip()
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_LLM_SCALE_PERCENT


def prepare_image_for_llm(
    image_path: Path,
    *,
    scale_pct: int | None = None,
    max_dim: int | None = None,
) -> Path:
    """Return a temporary JPEG for LLM input using either scale-percent or max-dimension rules."""
    image_path = image_path.resolve()
    if scale_pct is not None:
        if scale_pct <= 0 or scale_pct >= 100:
            return image_path
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        out_path = Path(tmp.name)
        resize_to_scale_percent(image_path, scale_pct, out_path)
        return out_path
    return downscale_image_for_llm(image_path, max_dim=LLM_MAX_DIM if max_dim is None else max_dim)


def downscale_image_for_llm(image_path: Path, max_dim: int = LLM_MAX_DIM) -> Path:
    """Return a JPEG path suitable for vision extraction (downscaled when large)."""
    image_path = image_path.resolve()
    if max_dim <= 0:
        return image_path
    width, height = _image_dimensions(image_path)
    if max(width, height) <= max_dim:
        return image_path

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    out_path = Path(tmp.name)
    subprocess.run(
        [tool_path("sips"), "-Z", str(max_dim), "-s", "format", "jpeg", str(image_path), "--out", str(out_path)],
        check=True,
        capture_output=True,
    )
    return out_path
