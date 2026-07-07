from extract_server.extraction.scoring import benchmark, name_similarity, price_match, score_image


def test_name_similarity_exact():
    assert name_similarity("Hunt's Tomato Paste", "Hunt's Tomato Paste") == 1.0


def test_name_similarity_substring():
    assert name_similarity("Mini-Wheats Original", "Kellogg's Mini-Wheats Original Cereal") >= 0.9


def test_price_match_tolerance():
    assert price_match(3.49, 3.49)
    assert price_match(3.49, 3.50, tol=0.02)
    assert not price_match(3.49, 4.49)


def test_score_image_partial_match():
    expected = [
        {"product_name": "Pearl River Bridge Superfine Soy", "price": 3.99, "category": "condiments"},
        {"product_name": "Pearl River Bridge Dark Soy", "price": 3.99, "category": "condiments"},
    ]
    actual = [
        {"product_name": "Pearl River Bridge Superfine Soy", "price": 3.99, "category": "condiments"},
    ]
    score = score_image("IMG_2027", expected, actual)
    assert score.expected_count == 2
    assert score.recall == 0.5
    assert score.precision == 1.0


def test_benchmark_aggregate():
    report = benchmark(
        {
            "A": [{"product_name": "Milk", "price": 6.49, "category": "dairy-eggs"}],
            "B": [{"product_name": "Eggs", "price": 4.59, "category": "dairy-eggs"}],
        },
        {
            "A": [{"product_name": "Milk", "price": 6.49, "category": "dairy-eggs"}],
            "B": [{"product_name": "Eggs", "price": 4.59, "category": "dairy-eggs"}],
        },
    )
    summary = report.summary()
    assert summary["mean_recall"] == 1.0
    assert summary["mean_f1"] == 1.0
