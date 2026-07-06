from __future__ import annotations

import json

import pytest

from experiment.dataset import (
    DEFAULT_SHELF_IDS,
    QUICK_RECEIPT_IDS,
    QUICK_SHELF_IDS,
    load_all_eval_images,
    load_subset,
    subset_image_ids,
)


def test_load_all_eval_images_count():
    images = load_all_eval_images()
    assert len(images) == 51
    shelf = [img for img in images if img.expected_type == "shelf"]
    receipt = [img for img in images if img.expected_type == "receipt"]
    assert len(shelf) == 45
    assert len(receipt) == 6


def test_all_image_paths_exist():
    for img in load_all_eval_images():
        assert img.path.exists(), img.image_id
        assert img.product_count == len(img.expected_products)
        assert img.product_count > 0


def test_receipt_ground_truth_schema():
    for img in load_all_eval_images():
        if img.expected_type != "receipt":
            continue
        for product in img.expected_products:
            assert product.get("product_name")
            assert product.get("category")
            assert product.get("price") is not None


def test_subset_sizes():
    assert len(subset_image_ids("quick")) == len(QUICK_SHELF_IDS) + len(QUICK_RECEIPT_IDS)
    assert len(subset_image_ids("default")) == len(DEFAULT_SHELF_IDS) + 6
    assert len(subset_image_ids("full")) == 51


def test_load_subset_quick():
    images = load_subset("quick")
    assert len(images) == 6
    ids = {img.image_id for img in images}
    assert ids == set(QUICK_SHELF_IDS + QUICK_RECEIPT_IDS)


def test_manifest_matches_loader():
    from experiment.dataset import MANIFEST_PATH, build_manifest

    on_disk = json.loads(MANIFEST_PATH.read_text())
    generated = build_manifest()
    assert len(on_disk) == len(generated) == 51
