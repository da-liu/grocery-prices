"""Load shelf and receipt eval images with ground truth."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT_DIR / "manifest.json"
SHELF_GT_PATH = ROOT / "extract_server" / "tests" / "fixtures" / "ground_truth_products.json"
RECEIPTS_DIR = ROOT / "data" / "receipts"

PhotoType = Literal["shelf", "receipt"]
SubsetName = Literal["quick", "default", "full"]

# 8 shelf images used in benchmark tests.
DEFAULT_SHELF_IDS = [
    "IMG_2027",
    "IMG_2030",
    "IMG_2044",
    "IMG_2053",
    "IMG_2058",
    "IMG_2061",
    "IMG_2065",
    "IMG_2071",
]

QUICK_SHELF_IDS = ["IMG_2027", "IMG_2030", "IMG_2061"]
QUICK_RECEIPT_IDS = ["IMG_2079", "IMG_2080", "IMG_2081"]


@dataclass(frozen=True)
class EvalImage:
    image_id: str
    path: Path
    expected_type: PhotoType
    expected_products: list[dict]
    product_count: int


def _find_shelf_image(image_id: str) -> Path | None:
    data_dir = ROOT / "data"
    for batch_dir in sorted(data_dir.glob("20*")):
        for candidate in (
            batch_dir / "jpg" / f"{image_id}.jpg",
            batch_dir / f"{image_id}.jpg",
        ):
            if candidate.exists():
                return candidate
    test_dir = data_dir / "test-data"
    if test_dir.is_dir():
        for candidate in (
            test_dir / f"{image_id}.jpg",
        ):
            if candidate.exists():
                return candidate
    return None


def _find_receipt_image(image_id: str) -> Path | None:
    for ext in (".jpg", ".jpeg"):
        path = RECEIPTS_DIR / f"{image_id}{ext}"
        if path.exists():
            return path
    return None


def load_shelf_ground_truth() -> dict[str, list[dict]]:
    payload = json.loads(SHELF_GT_PATH.read_text())
    return {k: [dict(p) for p in v] for k, v in payload.items()}


def load_receipt_ground_truth() -> dict[str, list[dict]]:
    truth: dict[str, list[dict]] = {}
    for path in sorted(RECEIPTS_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        image_id = payload["image_id"]
        truth[image_id] = [dict(p) for p in payload.get("products", [])]
    return truth


def load_all_eval_images() -> list[EvalImage]:
    images: list[EvalImage] = []

    shelf_gt = load_shelf_ground_truth()
    for image_id in sorted(shelf_gt):
        path = _find_shelf_image(image_id)
        if path is None:
            raise FileNotFoundError(f"Shelf image not found: {image_id}")
        products = shelf_gt[image_id]
        images.append(
            EvalImage(
                image_id=image_id,
                path=path,
                expected_type="shelf",
                expected_products=products,
                product_count=len(products),
            )
        )

    for path in sorted(RECEIPTS_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        image_id = payload["image_id"]
        image_path = _find_receipt_image(image_id)
        if image_path is None:
            raise FileNotFoundError(f"Receipt image not found: {image_id}")
        products = [dict(p) for p in payload.get("products", [])]
        images.append(
            EvalImage(
                image_id=image_id,
                path=image_path,
                expected_type="receipt",
                expected_products=products,
                product_count=len(products),
            )
        )

    return images


def build_manifest() -> list[dict]:
    return [
        {
            "image_id": img.image_id,
            "path": str(img.path.relative_to(ROOT)),
            "expected_type": img.expected_type,
            "product_count": img.product_count,
        }
        for img in load_all_eval_images()
    ]


def write_manifest() -> None:
    MANIFEST_PATH.write_text(json.dumps(build_manifest(), indent=2) + "\n")


def ground_truth_by_image(images: list[EvalImage] | None = None) -> dict[str, list[dict]]:
    images = images or load_all_eval_images()
    return {img.image_id: img.expected_products for img in images}


def subset_image_ids(name: SubsetName) -> list[str]:
    receipt_ids = sorted(load_receipt_ground_truth())
    if name == "quick":
        return QUICK_SHELF_IDS + QUICK_RECEIPT_IDS
    if name == "default":
        return DEFAULT_SHELF_IDS + receipt_ids
    if name == "full":
        shelf_gt = load_shelf_ground_truth()
        return sorted(shelf_gt) + receipt_ids
    raise ValueError(f"Unknown subset: {name}")


def load_subset(name: SubsetName) -> list[EvalImage]:
    wanted = set(subset_image_ids(name))
    return [img for img in load_all_eval_images() if img.image_id in wanted]


if __name__ == "__main__":
    write_manifest()
    images = load_all_eval_images()
    print(f"Wrote {MANIFEST_PATH} ({len(images)} images)")
