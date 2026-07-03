def _seed_user_products(client, username: str, token: str) -> tuple[str, list[str]]:
    from extract_server.users_db import _connect
    from grocery_extract.catalog_db import list_product_rows, save_photo_ingest
    from grocery_extract.user_paths import user_root

    with _connect() as conn:
        user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()["id"]

    user_dir = user_root(user_id)
    batch_dir = user_dir / "photos" / "2026_06_30" / "jpg"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "IMG_0001.jpg").write_bytes(b"jpg")
    (batch_dir / "IMG_0002.jpg").write_bytes(b"jpg")

    save_photo_ingest(
        user_id,
        photo_id="IMG_0001",
        photo_type="shelf",
        original_blob_key=None,
        jpeg_blob_key=f"users/{user_id}/photos/2026_06_30/jpg/IMG_0001.jpg",
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at="2026-06-30T19:00:00-04:00",
        store_location_id=None,
        extractor="cursor_sdk",
        raw_response="[]",
        products=[
            {"product_name": "Milk", "price": 5.99, "category": "dairy"},
            {"product_name": "Bread", "price": 3.49, "category": "bakery"},
        ],
    )
    save_photo_ingest(
        user_id,
        photo_id="IMG_0002",
        photo_type="shelf",
        original_blob_key=None,
        jpeg_blob_key=f"users/{user_id}/photos/2026_06_30/jpg/IMG_0002.jpg",
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at="2026-06-30T20:00:00-04:00",
        store_location_id=None,
        extractor="cursor_sdk",
        raw_response="[]",
        products=[{"product_name": "Eggs", "price": 4.99, "category": "dairy"}],
    )

    headers = {"Authorization": f"Bearer {token}"}
    products = client.get("/api/products", headers=headers).json()
    return user_id, [product["id"] for product in products if not product.get("extraction_empty")]


def test_delete_product(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "deleter", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    _user_id, product_ids = _seed_user_products(client, "deleter", token)
    img1_ids = [
        product["id"]
        for product in client.get("/api/products", headers=headers).json()
        if product["image_id"] == "IMG_0001"
    ]
    milk_id, bread_id = img1_ids

    products = client.get("/api/products", headers=headers).json()
    assert len(products) == 3

    delete = client.delete(f"/api/products/{milk_id}", headers=headers)
    assert delete.status_code == 200, delete.text

    products = client.get("/api/products", headers=headers).json()
    assert len(products) == 2
    names = {product["product_name"] for product in products}
    assert names == {"Bread", "Eggs"}


def test_bulk_delete_products(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "bulkdeleter", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    _user_id, product_ids = _seed_user_products(client, "bulkdeleter", token)

    bulk = client.post(
        "/api/products/bulk-delete",
        headers=headers,
        json={"ids": product_ids},
    )
    assert bulk.status_code == 200, bulk.text
    body = bulk.json()
    assert body["deleted"] == 3
    assert body["photos_removed"] == 2
    assert body["failed"] == []

    products = client.get("/api/products", headers=headers).json()
    assert products == []
