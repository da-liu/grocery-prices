import { useEffect, useMemo, useState } from "react";
import { MapCoordinateLink } from "./MapCoordinateLink";
import { PhotoLightbox } from "./PhotoLightbox";
import { StoreLink } from "./StoreLink";
import type { Product } from "./types";
import "./App.css";

function formatPrice(price: number | null | undefined, currency = "CAD") {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
  }).format(price);
}

function ProductCard({ product }: { product: Product }) {
  const imgSrc = `/${product.image_path}`;
  const { latitude, longitude } = product.location;
  const [lightboxOpen, setLightboxOpen] = useState(false);

  return (
    <article className="card">
      <button
        type="button"
        className="card-image-wrap"
        aria-label={`View full photo of ${product.product_name}`}
        onClick={() => setLightboxOpen(true)}
      >
        <img src={imgSrc} alt={product.product_name} loading="lazy" />
        {product.is_special && <span className="badge special">Special</span>}
      </button>
      {lightboxOpen && (
        <PhotoLightbox
          src={imgSrc}
          alt={product.product_name}
          onClose={() => setLightboxOpen(false)}
        />
      )}
      <div className="card-body">
        <h2>{product.product_name}</h2>
        {product.product_name_zh && (
          <p className="zh">{product.product_name_zh}</p>
        )}
        <div className="price-row">
          <span className="price">{formatPrice(product.price, product.price_currency)}</span>
          {product.unit && <span className="unit">/ {product.unit}</span>}
          {product.regular_price != null && product.is_special && (
            <span className="was">was {formatPrice(product.regular_price)}</span>
          )}
        </div>
        {product.promo && <p className="promo">{product.promo}</p>}
        <dl className="meta">
          {product.brand && (
            <>
              <dt>Brand</dt>
              <dd>{product.brand}</dd>
            </>
          )}
          {product.size && (
            <>
              <dt>Size</dt>
              <dd>{product.size}</dd>
            </>
          )}
          {product.unit_price != null && (
            <>
              <dt>Unit price</dt>
              <dd>{formatPrice(product.unit_price)}/{product.unit ?? "unit"}</dd>
            </>
          )}
          {product.barcode && (
            <>
              <dt>Barcode</dt>
              <dd className="mono">{product.barcode}</dd>
            </>
          )}
          {product.packed_on && (
            <>
              <dt>Packed on</dt>
              <dd>{product.packed_on}</dd>
            </>
          )}
          <dt>Store</dt>
          <dd>
            <StoreLink location={product.location} />
          </dd>
          <dt>Address</dt>
          <dd>{product.location.address}</dd>
          {latitude != null && longitude != null && (
            <>
              <dt>Map</dt>
              <dd>
                <MapCoordinateLink lat={latitude} lon={longitude} />
              </dd>
            </>
          )}
          <dt>Category</dt>
          <dd>{product.category}</dd>
          <dt>Photo</dt>
          <dd className="mono">{product.image_id}</dd>
        </dl>
      </div>
    </article>
  );
}

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [store, setStore] = useState("all");
  const [category, setCategory] = useState("all");

  useEffect(() => {
    fetch("/products.jsonl")
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load products (${r.status})`);
        return r.text();
      })
      .then((text) => {
        const rows = text
          .trim()
          .split("\n")
          .filter(Boolean)
          .map((line) => JSON.parse(line) as Product);
        setProducts(rows);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const stores = useMemo(
    () => [...new Set(products.map((p) => p.location.store))].sort(),
    [products],
  );

  const categories = useMemo(
    () => [...new Set(products.map((p) => p.category))].sort(),
    [products],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return products.filter((p) => {
      if (store !== "all" && p.location.store !== store) return false;
      if (category !== "all" && p.category !== category) return false;
      if (!q) return true;
      const hay = [
        p.product_name,
        p.product_name_zh,
        p.brand,
        p.location.store,
        p.category,
        p.barcode,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [products, search, store, category]);

  const priced = filtered.filter((p) => p.price != null);
  const avgPrice =
    priced.length > 0
      ? priced.reduce((s, p) => s + (p.price ?? 0), 0) / priced.length
      : 0;

  return (
    <div className="app">
      <header className="header">
        <div>
          <p className="eyebrow">Toronto grocery price tracker</p>
          <h1>Grocery Prices</h1>
          <p className="subtitle">
            {products.length} products from {new Set(products.map((p) => p.image_id)).size} photos
          </p>
        </div>
        <div className="stats">
          <div className="stat">
            <span className="stat-value">{filtered.length}</span>
            <span className="stat-label">shown</span>
          </div>
          <div className="stat">
            <span className="stat-value">{stores.length}</span>
            <span className="stat-label">stores</span>
          </div>
          <div className="stat">
            <span className="stat-value">{formatPrice(avgPrice)}</span>
            <span className="stat-label">avg price</span>
          </div>
        </div>
      </header>

      <section className="filters">
        <input
          type="search"
          placeholder="Search products, brands, barcodes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search products"
        />
        <select value={store} onChange={(e) => setStore(e.target.value)} aria-label="Filter by store">
          <option value="all">All stores</option>
          {stores.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Filter by category">
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </section>

      {loading && <p className="status">Loading products…</p>}
      {error && <p className="status error">{error}</p>}

      {!loading && !error && (
        <main className="grid">
          {filtered.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </main>
      )}

      {!loading && !error && filtered.length === 0 && (
        <p className="status">No products match your filters.</p>
      )}
    </div>
  );
}

export default App;
