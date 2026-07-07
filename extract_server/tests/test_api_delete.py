def _seed_user_products(client, username: str, token: str) -> tuple[str, list[str]]:
    from extract_server.db import get_conn
    from extract_server.db import save_photo_extraction, list_product_rows, save_photo
    from extract_server.extraction.paths import user_root

    user_id = get_conn().execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()["id"]

    user_dir = user_root(user_id)
    batch_dir = user_dir / "photos" / "2026_06_30"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "IMG_0001.webp").write_bytes(b"webp")
    (batch_dir / "IMG_0002.webp").write_bytes(b"webp")

    save_photo(
        user_id,
        photo_id="IMG_0001",
        blob_key=f"users/{user_id}/photos/2026_06_30/IMG_0001.webp",
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at="2026-06-30T19:00:00-04:00",
        store_location_id=None,
    )
    save_photo_extraction(
        user_id,
        "IMG_0001",
        extractor="cursor_sdk",
        raw_response="[]",
        products=[
            {"product_name": "Milk", "price": 5.99, "category": "dairy"},
            {"product_name": "Bread", "price": 3.49, "category": "bakery"},
        ],
        photo_type="shelf",
    )
    save_photo(
        user_id,
        photo_id="IMG_0002",
        blob_key=f"users/{user_id}/photos/2026_06_30/IMG_0002.webp",
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at="2026-06-30T20:00:00-04:00",
        store_location_id=None,
    )
    save_photo_extraction(
        user_id,
        "IMG_0002",
        extractor="cursor_sdk",
        raw_response="[]",
        products=[{"product_name": "Eggs", "price": 4.99, "category": "dairy"}],
        photo_type="shelf",
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


def test_delete_photo(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "photodeleter", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    _user_id, _product_ids = _seed_user_products(client, "photodeleter", token)

    products = client.get("/api/products", headers=headers).json()
    assert len(products) == 3

    delete = client.delete("/api/photos/IMG_0001", headers=headers)
    assert delete.status_code == 204, delete.text

    products = client.get("/api/products", headers=headers).json()
    assert len(products) == 1
    assert products[0]["image_id"] == "IMG_0002"
    assert products[0]["product_name"] == "Eggs"

    media = client.get("/api/media/IMG_0001", headers=headers)
    assert media.status_code == 404
