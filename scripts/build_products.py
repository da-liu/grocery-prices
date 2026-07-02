#!/usr/bin/env python3
"""Merge EXIF metadata with product extractions into products.jsonl."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grocery_extract.products_builder import OUT_PATH, write_products_jsonl

# Products keyed by image stem (without extension). Multiple products per image allowed.
PRODUCTS: dict[str, list[dict]] = {
    "IMG_2027": [
        {"product_name": "Pearl River Bridge Superfine Soy", "product_name_zh": "珠江橋牌鼓油王生抽", "brand": "Pearl River Bridge", "price": 3.99, "unit": "EA", "barcode": "72223701004", "size": "500ml", "category": "condiments"},
        {"product_name": "Pearl River Bridge Superior Dark Soy Sauce", "product_name_zh": "珠江橋牌老抽王", "brand": "Pearl River Bridge", "price": 3.99, "unit": "EA", "size": "500ml", "category": "condiments"},
        {"product_name": "Pearl River Bridge Mushroom Dark Soy Sauce", "product_name_zh": "珠江橋牌草菇老抽", "brand": "Pearl River Bridge", "price": 3.99, "unit": "EA", "size": "500ml", "category": "condiments"},
    ],
    "IMG_2028": [
        {"product_name": "Pearl River Bridge Seasoned Soy Sauce for Steamed Fish", "product_name_zh": "一滴香蒸魚豉油", "brand": "Pearl River Bridge", "price": 2.99, "unit": "EA", "regular_price": None, "is_special": True, "promo": "2 for $5.00", "size": "500ml", "category": "condiments"},
        {"product_name": "Pearl River Bridge Superior Light Soy Sauce", "product_name_zh": "生抽王", "brand": "Pearl River Bridge", "price": 2.99, "unit": "EA", "size": "500ml", "category": "condiments"},
    ],
    "IMG_2029": [
        {"product_name": "Pearl River Bridge Mushroom Dark Soy Sauce", "product_name_zh": "珠江橋牌草菰老抽", "brand": "Pearl River Bridge", "price": 8.99, "unit": "EA", "size": "1.8L", "barcode": "72233781804", "category": "condiments"},
        {"product_name": "Pearl River Bridge Golden Label Light Soy Sauce", "product_name_zh": "珠江橋牌金標生抽王", "brand": "Pearl River Bridge", "price": 8.99, "unit": "EA", "size": "1.8L", "barcode": "72233781803", "category": "condiments"},
    ],
    "IMG_2030": [
        {"product_name": "Gray Ridge Brown Eggs", "brand": "Gray Ridge", "price": 4.59, "unit": "EA", "size": "12 extra large", "category": "dairy-eggs"},
        {"product_name": "Gray Ridge White Eggs", "product_name_zh": "大白雞蛋", "brand": "Gray Ridge", "price": 4.39, "unit": "EA", "size": "12 extra large", "category": "dairy-eggs"},
        {"product_name": "Lactantia Milk", "brand": "Lactantia", "price": 5.99, "unit": "EA", "category": "dairy-eggs"},
        {"product_name": "Natrel Ultrafiltered Milk 3.25%", "brand": "Natrel", "price": 6.99, "unit": "EA", "category": "dairy-eggs"},
        {"product_name": "Natrel Free 2% Milk", "brand": "Natrel", "price": 6.99, "unit": "EA", "category": "dairy-eggs"},
    ],
    "IMG_2031": [
        {"product_name": "Hikari Organic Miso (White)", "product_name_zh": "有機白味噌", "brand": "Hikari", "price": 8.99, "unit": "EA", "size": "500g", "category": "condiments"},
        {"product_name": "Organic Miso", "product_name_zh": "有機味噌", "brand": "Hikari", "price": 8.99, "unit": "EA", "size": "500g", "category": "condiments"},
        {"product_name": "Marukome Miso", "product_name_zh": "味噌", "brand": "Marukome", "price": 7.99, "unit": "EA", "size": "1000g", "category": "condiments"},
    ],
    "IMG_2032": [
        {"product_name": "CJ Haechandle Ssamjang", "brand": "CJ", "price": 4.99, "unit": "EA", "size": "500g", "category": "condiments"},
        {"product_name": "Marukome Organic Miso", "brand": "Marukome", "price": 7.99, "unit": "EA", "size": "500g", "category": "condiments"},
        {"product_name": "Hanamaruki Red Miso", "brand": "Hanamaruki", "price": None, "size": "500g", "category": "condiments", "notes": "Price not visible on tag"},
    ],
    "IMG_2033": [
        {"product_name": "Seasoned Soybean Paste", "product_name_zh": "韓國辣椒醬", "price": 5.99, "unit": "EA", "category": "condiments"},
        {"product_name": "Hot Pepper Bean Paste", "product_name_zh": "韓國辣椒醬", "price": 5.99, "unit": "EA", "category": "condiments"},
        {"product_name": "Sempio Gochujang", "brand": "Sempio", "price": None, "size": "500g", "category": "condiments"},
        {"product_name": "CJ Doenjang", "brand": "CJ", "price": None, "size": "500g", "category": "condiments"},
    ],
    "IMG_2034": [
        {"product_name": "Sunrise Original Tofu Dessert", "product_name_zh": "日昇原味豆腐花", "brand": "Sunrise", "price": 1.99, "unit": "EA", "size": "300g", "category": "tofu"},
        {"product_name": "Sunrise Banana Tofu Dessert", "product_name_zh": "日昇香蕉豆腐花", "brand": "Sunrise", "price": 1.99, "unit": "EA", "category": "tofu"},
        {"product_name": "Whipped Cream", "product_name_zh": "奶油", "price": 7.99, "unit": "EA", "category": "dairy-eggs"},
        {"product_name": "Beancurd Roll", "product_name_zh": "響鈴卷", "price": 4.99, "unit": "EA", "category": "tofu"},
        {"product_name": "Lactantia Lactose Free 2% Milk", "product_name_zh": "牛奶2%", "brand": "Lactantia", "price": 10.99, "unit": "EA", "size": "4L", "category": "dairy-eggs"},
        {"product_name": "Sealtest 2% Milk", "product_name_zh": "全脂鲜奶", "brand": "Sealtest", "price": 8.59, "unit": "EA", "size": "4L", "category": "dairy-eggs"},
    ],
    "IMG_2035": [
        {"product_name": "Sunrise Medium Firm Tofu", "brand": "Sunrise", "price": 2.79, "unit": "EA", "size": "454g", "category": "tofu"},
        {"product_name": "Sunrise Firm Tofu", "brand": "Sunrise", "price": 3.29, "unit": "EA", "size": "500g", "category": "tofu"},
        {"product_name": "Sunrise Soft Tofu", "brand": "Sunrise", "price": 2.29, "unit": "EA", "size": "530g", "category": "tofu"},
        {"product_name": "Sunrise Extra Firm Tofu", "brand": "Sunrise", "price": 3.79, "unit": "EA", "category": "tofu"},
    ],
    "IMG_2036": [
        {"product_name": "Wah Chong Pressed Tofu", "product_name_zh": "大華白豆腐", "brand": "Wah Chong", "price": 3.59, "unit": "EA", "category": "tofu"},
        {"product_name": "San Sui Multi Usage Tofu", "product_name_zh": "山水百搭豆腐", "brand": "San Sui", "price": 2.39, "unit": "EA", "size": "454g", "category": "tofu"},
        {"product_name": "Vitasoy Silken Tofu", "product_name_zh": "維他山水嫩豆腐", "brand": "Vitasoy", "price": 2.39, "unit": "EA", "category": "tofu"},
    ],
    "IMG_2037": [
        {"product_name": "To Fu Superior Sweetened Soya Drink", "product_name_zh": "有糖豆漿", "brand": "To Fu Superior", "price": 3.29, "unit": "EA", "size": "2L", "category": "beverages"},
        {"product_name": "To Fu Superior Unsweetened Soya", "product_name_zh": "無糖豆漿", "brand": "To Fu Superior", "price": 3.29, "unit": "EA", "size": "2L", "category": "beverages"},
        {"product_name": "Sweetened Soy Beverage", "price": 2.99, "unit": "EA", "category": "beverages"},
        {"product_name": "Black Soy Beverage (Unsweetened)", "price": 3.59, "unit": "EA", "category": "beverages"},
        {"product_name": "To Fu Superior Seasoned Dry Tofu", "brand": "To Fu Superior", "price": 3.59, "unit": "EA", "size": "250g", "category": "tofu"},
        {"product_name": "To Fu Superior Fried Bean Curd", "brand": "To Fu Superior", "price": 3.79, "unit": "EA", "category": "tofu"},
    ],
    "IMG_2038": [
        {"product_name": "Special Dried Shiitake Mushroom", "product_name_zh": "花菇", "price": 9.99, "unit": "EA", "regular_price": 10.99, "is_special": True, "category": "dried-goods"},
        {"product_name": "Shine Farm Dried Shiitake Mushroom", "product_name_zh": "軒農椎茸光麵菇", "brand": "Shine Farm", "price": 8.99, "unit": "EA", "is_special": True, "category": "dried-goods"},
        {"product_name": "Heritage Delicious Premium Dried Shiitake Mushrooms", "product_name_zh": "古早味精選冬菇", "brand": "Heritage Delicious", "price": 13.99, "unit": "EA", "category": "dried-goods"},
    ],
    "IMG_2039": [
        {"product_name": "Redpath Special Fine Granulated Sugar", "brand": "Redpath", "price": 3.99, "unit": "EA", "size": "2kg", "category": "pantry"},
        {"product_name": "Windsor Table Salt", "brand": "Windsor", "price": 2.99, "unit": "EA", "category": "pantry"},
        {"product_name": "Mr. Goudas Table Salt", "brand": "Mr. Goudas", "price": 3.99, "unit": "EA", "category": "pantry"},
    ],
    "IMG_2040": [
        {"product_name": "Golden Phoenix Jasmine Rice", "product_name_zh": "金鳳香米", "brand": "Golden Phoenix", "price": 19.99, "unit": "EA", "regular_price": 23.99, "is_special": True, "category": "rice"},
        {"product_name": "Rose Brand Jasmine Rice", "product_name_zh": "玫瑰花茉莉香米", "brand": "Rose Brand", "price": 23.99, "unit": "EA", "size": "8kg", "category": "rice"},
        {"product_name": "Rose Brand Sweet Rice", "product_name_zh": "玫瑰牌糯米", "brand": "Rose Brand", "price": 26.99, "unit": "EA", "size": "18lb", "category": "rice"},
    ],
    "IMG_2041": [
        {"product_name": "Mr. Goudas Calrose Rice", "product_name_zh": "日本蓬萊米", "brand": "Mr. Goudas", "price": 17.99, "unit": "EA", "size": "15lb", "category": "rice"},
        {"product_name": "Tastie Jasmine Rice", "product_name_zh": "品坊茉莉香米", "brand": "Tastie", "price": 11.99, "unit": "bag", "size": "8.0kg", "barcode": "077092087112", "category": "rice"},
        {"product_name": "Phoenix Barge Jasmine Rice", "product_name_zh": "鳳艇香米", "price": 19.99, "unit": "EA", "regular_price": 22.99, "is_special": True, "category": "rice"},
    ],
    "IMG_2042": [
        {"product_name": "Pearl Rice from Northeast China", "product_name_zh": "東北稻田臻選珍珠貢米", "price": 17.99, "unit": "bag", "category": "rice"},
        {"product_name": "Thai Hom Mali Rice Pacific Gold", "product_name_zh": "財仔得米", "price": 22.99, "unit": "EA", "category": "rice"},
        {"product_name": "Botan Calrose Rice", "product_name_zh": "牡丹圓米", "brand": "Botan", "price": 19.99, "unit": "EA", "regular_price": 23.99, "is_special": True, "size": "6.8kg", "category": "rice"},
        {"product_name": "Ox Head White Fragrant Rice", "product_name_zh": "牛頭香米", "price": 25.99, "unit": "EA", "regular_price": 25.99, "category": "rice"},
        {"product_name": "Ox Head White Fragrant Rice (Special)", "product_name_zh": "牛頭香米", "price": 22.99, "unit": "EA", "regular_price": 25.99, "is_special": True, "category": "rice"},
        {"product_name": "Tsuru Mai Brown Rice", "product_name_zh": "仙鶴牌糙米", "brand": "Tsuru Mai", "price": 25.99, "unit": "EA", "category": "rice"},
    ],
    "IMG_2043": [
        {"product_name": "Lao Gan Ma Chilli in Oil With Peanuts", "product_name_zh": "油辣椒", "brand": "Lao Gan Ma", "price": 3.29, "unit": "EA", "size": "275g", "category": "condiments"},
        {"product_name": "Lao Gan Ma Hot Pepper Sauce (Black Beans)", "product_name_zh": "风味豆豉油制辣椒", "brand": "Lao Gan Ma", "price": 3.29, "unit": "EA", "category": "condiments"},
        {"product_name": "Lao Gan Ma Chili Sauce", "brand": "Lao Gan Ma", "price": 3.29, "unit": "EA", "category": "condiments"},
    ],
    "IMG_2044": [
        {"product_name": "Cauliflower", "product_name_zh": "椰菜花", "price": 4.76, "unit_price": 2.49, "unit": "lb", "net_weight_lb": 1.91, "packed_on": "2024-JAN-29", "barcode": "0200109004767", "category": "produce"},
    ],
    "IMG_2045": [
        {"product_name": "Mini Potatoes (Finger)", "product_name_zh": "袋裝手指薯仔", "price": 2.99, "unit": "lb", "barcode": "0000000004350", "category": "produce"},
        {"product_name": "Shanghai Bok Choy", "product_name_zh": "上海白", "price": 1.99, "unit": "lb", "barcode": "0000000004196", "category": "produce"},
    ],
    "IMG_2046": [
        {"product_name": "Basil", "product_name_zh": "香花草（九層塔）", "price": 2.08, "unit_price": 12.99, "unit": "lb", "net_weight_lb": 0.16, "packed_on": "26.JN.27", "barcode": "2220159002087", "category": "produce-herbs"},
    ],
    "IMG_2047": [
        {"product_name": "Thyme", "product_name_zh": "百里香", "price": 1.99, "unit": "EA", "packed_on": "26.JN.23", "barcode": "0220341001997", "category": "produce-herbs"},
    ],
    "IMG_2048": [
        {"product_name": "Thyme", "product_name_zh": "百里香", "price": 1.99, "unit": "EA", "packed_on": "26.JN.28", "barcode": "0220341001997", "category": "produce-herbs"},
    ],
    "IMG_2049": [
        {"product_name": "Rosemary", "price": 1.99, "unit": "EA", "packed_on": "26.JN.26", "barcode": "0200215001995", "category": "produce-herbs"},
    ],
    "IMG_2050": [
        {"product_name": "LGM Hot Sauce with Black Beans", "product_name_zh": "老干妈风味豆豉", "brand": "Lao Gan Ma", "price": 7.99, "unit": "bottle", "size": "740g", "barcode": "00692180470152", "category": "condiments"},
    ],
    "IMG_2051": [
        {"product_name": "TG Frozen Shrimp Peeled & Deveined 31-40", "product_name_zh": "蝦中之皇速凍蝦蝦仁", "price": 8.99, "unit": "box", "size": "380g", "regular_price": 11.99, "is_special": True, "barcode": "00006139124056", "category": "frozen-seafood"},
        {"product_name": "AP Headless Shrimp 8/12", "product_name_zh": "泰國無頭白蝦", "price": 10.99, "unit": "box", "size": "380g", "barcode": "00006139124039", "category": "frozen-seafood"},
    ],
    "IMG_2052": [
        {"product_name": "Goat Meat", "product_name_zh": "羊肉", "price": 14.05, "unit_price": 6.99, "net_weight": 2.01, "packed_on": "26-06-22", "barcode": "0200067914054", "category": "meat"},
        {"product_name": "Goat Meat", "product_name_zh": "羊肉", "price": 14.96, "unit_price": 6.99, "net_weight": 2.14, "packed_on": "26-06-22", "barcode": "0200067214963", "category": "meat"},
        {"product_name": "Lamb Leg with Skin", "product_name_zh": "有皮羊腿", "price": 12.38, "unit_price": 7.99, "net_weight": 1.55, "packed_on": "26-06-23", "barcode": "0200060312389", "category": "meat"},
    ],
    "IMG_2053": [
        {"product_name": "T&T Brown Rice Vermicelli", "brand": "T&T", "price": 3.99, "unit": "EA", "size": "400g", "unit_price_per_100g": 0.99, "category": "noodles"},
        {"product_name": "Rose Brand Vermicelli", "brand": "Rose Brand", "price": 3.49, "unit": "EA", "size": "454g", "unit_price_per_100g": 0.77, "category": "noodles"},
        {"product_name": "Pacific Star Jasmine Rice", "brand": "Pacific Star", "price": 27.99, "unit": "EA", "size": "8kg", "category": "rice"},
    ],
    "IMG_2054": [
        {"product_name": "Jasmine White Scented Rice", "brand": "Rose Brand", "price": 25.99, "unit": "EA", "size": "8kg", "category": "rice"},
    ],
    "IMG_2055": [
        {"product_name": "Tilda Pure Basmati Rice", "brand": "Tilda", "price": 19.99, "unit": "EA", "size": "4.54kg (10lb)", "category": "rice"},
    ],
    "IMG_2058": [
        {"product_name": "Montreal-Style Smoked Meat", "brand": "Schinkel's Legacy", "price": 4.99, "unit": "100g", "unit_price_per_100g": 4.99, "category": "deli"},
    ],
    "IMG_2059": [
        {"product_name": "New York Deli-Style Smoked Brisket", "brand": "Farm Boy", "price": 4.49, "unit": "100g", "unit_price_per_100g": 4.49, "category": "deli"},
    ],
    "IMG_2060": [
        {"product_name": "Tomato Paste", "brand": "Hunt's", "price": 1.79, "unit": "EA", "size": "156ml", "category": "canned-goods"},
    ],
    "IMG_2061": [
        {"product_name": "Diced Tomatoes With No Added Salt", "brand": "Farm Boy", "price": 2.49, "unit": "EA", "size": "796ml", "category": "canned-goods"},
        {"product_name": "Diced Tomatoes With Garlic, Basil & Oregano", "brand": "Farm Boy", "price": 2.49, "unit": "EA", "size": "796ml", "category": "canned-goods"},
        {"product_name": "Whole Tomatoes", "brand": "Farm Boy", "price": 2.49, "unit": "EA", "size": "796ml", "category": "canned-goods"},
        {"product_name": "Crushed Tomatoes", "brand": "Farm Boy", "price": 2.49, "unit": "EA", "size": "796ml", "category": "canned-goods"},
    ],
    "IMG_2062": [
        {"product_name": "Striploin Grilling Steak", "price": 26.99, "unit": "lb", "unit_price": 26.99, "category": "meat", "notes": "Canada AAA Beef, aged 14 days"},
        {"product_name": "Prime Rib Oven Roast", "price": 23.99, "unit": "lb", "unit_price": 23.99, "category": "meat", "notes": "Canada AAA Beef, aged 14 days"},
        {"product_name": "Sirloin Tip Oven Roast", "price": 10.99, "unit": "lb", "unit_price": 10.99, "is_special": True, "category": "meat", "notes": "Canada AAA Beef"},
        {"product_name": "Rib Eye Grilling Steak", "price": 29.99, "unit": "lb", "unit_price": 29.99, "is_special": True, "category": "meat", "notes": "Canada AAA Beef"},
    ],
    "IMG_2063": [
        {"product_name": "Mini-Wheats Original Cereal", "brand": "Kellogg's", "price": 5.99, "unit": "EA", "size": "650g", "regular_price": 8.49, "is_special": True, "category": "cereal"},
    ],
    "IMG_2064": [
        {"product_name": "Raisin Bran Cereal", "brand": "Kellogg's", "price": 5.99, "unit": "EA", "size": "600g", "regular_price": 8.49, "is_special": True, "unit_price_per_100g": 1.00, "category": "cereal"},
    ],
    "IMG_2065": [
        {"product_name": "Ketchup Chips", "brand": "Lay's", "price": 3.49, "unit": "EA", "size": "220g", "regular_price": 4.49, "is_special": True, "promo": "2 for $6.00", "category": "snacks"},
        {"product_name": "Cheese & Onion Chips", "brand": "Lay's", "price": 3.49, "unit": "EA", "size": "220g", "regular_price": 4.49, "is_special": True, "promo": "2 for $6.00", "category": "snacks"},
        {"product_name": "Classic Chips", "brand": "Lay's", "price": 3.49, "unit": "EA", "size": "220g", "regular_price": 4.49, "is_special": True, "promo": "2 for $6.00", "category": "snacks"},
        {"product_name": "All Dressed Chips", "brand": "Lay's", "price": 3.49, "unit": "EA", "size": "220g", "regular_price": 4.49, "is_special": True, "promo": "2 for $6.00", "category": "snacks"},
        {"product_name": "Wavy Salt & Vinegar Chips", "brand": "Lay's", "price": 3.49, "unit": "EA", "size": "220g", "regular_price": 4.49, "is_special": True, "promo": "2 for $6.00", "category": "snacks"},
    ],
    "IMG_2066": [
        {"product_name": "Caramel Almond Crunch Ice Cream Bars", "brand": "Häagen-Dazs", "price": 4.99, "unit": "EA", "size": "3x88ml", "regular_price": 7.29, "is_special": True, "category": "frozen-desserts"},
    ],
    "IMG_2067": [
        {"product_name": "Strawberry Ice Cream", "brand": "Häagen-Dazs", "price": 4.99, "unit": "EA", "size": "450ml", "regular_price": 6.99, "is_special": True, "unit_price_per_100g": 1.11, "category": "frozen-desserts"},
        {"product_name": "Coffee Ice Cream", "brand": "Häagen-Dazs", "price": 4.99, "unit": "EA", "size": "450ml", "regular_price": 6.99, "is_special": True, "unit_price_per_100g": 1.11, "category": "frozen-desserts"},
        {"product_name": "White Chocolate Raspberry Truffle Ice Cream", "brand": "Häagen-Dazs", "price": 4.99, "unit": "EA", "size": "450ml", "regular_price": 6.99, "is_special": True, "unit_price_per_100g": 1.11, "category": "frozen-desserts"},
    ],
    "IMG_2068": [
        {"product_name": "Essentials Crushed Tomatoes", "brand": "Longo's", "price": 1.99, "unit": "EA", "size": "796ml", "category": "canned-goods"},
        {"product_name": "Essentials Diced Tomatoes", "brand": "Longo's", "price": 1.99, "unit": "EA", "size": "796ml", "category": "canned-goods"},
        {"product_name": "Essentials Whole Tomatoes", "brand": "Longo's", "price": 1.99, "unit": "EA", "size": "796ml", "category": "canned-goods"},
    ],
    "IMG_2069": [
        {"product_name": "Spaghetti", "brand": "Italpasta", "price": 2.49, "unit": "EA", "size": "900g", "regular_price": 3.49, "is_special": True, "unit_price_per_100g": 0.28, "category": "pasta"},
        {"product_name": "Capellini", "brand": "Italpasta", "price": 2.49, "unit": "EA", "size": "900g", "regular_price": 3.49, "is_special": True, "unit_price_per_100g": 0.28, "category": "pasta"},
        {"product_name": "Linguine", "brand": "Italpasta", "price": 2.49, "unit": "EA", "size": "900g", "regular_price": 3.49, "is_special": True, "unit_price_per_100g": 0.28, "category": "pasta"},
        {"product_name": "Fusilli", "brand": "Italpasta", "price": 2.49, "unit": "EA", "size": "900g", "regular_price": 3.49, "is_special": True, "unit_price_per_100g": 0.28, "category": "pasta"},
    ],
    "IMG_2070": [
        {"product_name": "Skim Milk", "brand": "Beatrice", "price": 6.49, "unit": "EA", "size": "4L", "category": "dairy-eggs"},
        {"product_name": "1% Milk", "brand": "Beatrice", "price": 6.49, "unit": "EA", "size": "4L", "category": "dairy-eggs"},
        {"product_name": "2% Milk", "brand": "Beatrice", "price": 6.49, "unit": "EA", "size": "4L", "category": "dairy-eggs"},
        {"product_name": "PurFiltre 1% Milk", "brand": "Lactantia", "price": 6.49, "unit": "EA", "size": "2L", "category": "dairy-eggs"},
    ],
    "IMG_2071": [
        {"product_name": "Value Pack Boneless Pork Loin Centre Cut Fast Fry", "brand": "Longo's", "price": 4.58, "unit": "EA", "unit_price": 7.69, "net_weight": 0.596, "barcode": "208210004584", "category": "meat", "notes": "Local Ontario corn-fed pork"},
    ],
    "IMG_2072": [
        {"product_name": "Value Pack Boneless Pork Loin Fast Fry Chops", "brand": "Longo's", "price": 3.49, "unit": "lb", "unit_price": 3.49, "regular_price": 5.99, "is_special": True, "barcode": "203211002218", "category": "meat", "notes": "Shelf promo $3.49/lb, was $5.99/lb"},
    ],
    "IMG_2073": [
        {"product_name": "Fresh Pork Button Bones", "brand": "Longo's", "price": 2.49, "unit": "lb", "unit_price": 2.49, "regular_price": 3.49, "is_special": True, "category": "meat", "notes": "Fresh Ontario"},
    ],
}


def main() -> None:
    count = write_products_jsonl(PRODUCTS)
    print(f"Wrote {count} products to {OUT_PATH}")


if __name__ == "__main__":
    main()
