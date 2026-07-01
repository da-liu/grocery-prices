import { useMemo } from "react";
import { formatCapturedAt } from "./formatCapturedAgo";
import type { Product } from "./types";

function formatPrice(price: number | null | undefined) {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
  }).format(price);
}

function productKey(product: Product): string {
  if (product.barcode) return `barcode:${product.barcode}`;
  return `name:${product.product_name.trim().toLowerCase()}`;
}

interface ProductGroup {
  key: string;
  label: string;
  entries: Product[];
  cheapest: Product | null;
}

function buildGroups(products: Product[]): ProductGroup[] {
  const map = new Map<string, ProductGroup>();
  for (const product of products) {
    if (product.price == null) continue;
    const key = productKey(product);
    const existing = map.get(key);
    if (existing) {
      existing.entries.push(product);
    } else {
      map.set(key, {
        key,
        label: product.product_name,
        entries: [product],
        cheapest: null,
      });
    }
  }

  const groups = [...map.values()];
  for (const group of groups) {
    group.entries.sort((a, b) => {
      const ta = a.captured_at ? new Date(a.captured_at).getTime() : 0;
      const tb = b.captured_at ? new Date(b.captured_at).getTime() : 0;
      return tb - ta;
    });
    group.cheapest = group.entries.reduce<Product | null>((best, current) => {
      if (current.price == null) return best;
      if (!best || (best.price ?? Infinity) > current.price) return current;
      return best;
    }, null);
  }

  return groups
    .filter((group) => group.entries.length > 0)
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function ComparePage({
  products,
  query,
  onDeleteProduct,
  deletingId,
}: {
  products: Product[];
  query: string;
  onDeleteProduct?: (productId: string) => void;
  deletingId?: string | null;
}) {
  const groups = useMemo(() => buildGroups(products), [products]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return groups.filter((g) => {
        const stores = new Set(g.entries.map((x) => x.location.store));
        return g.entries.length > 1 || stores.size > 1;
      });
    }
    return groups.filter((g) => g.label.toLowerCase().includes(q));
  }, [groups, query]);

  const multiStore = filtered.filter((g) => {
    const stores = new Set(g.entries.map((e) => e.location.store));
    return stores.size > 1 || g.entries.length > 1;
  });

  return (
    <section className="panel compare-panel">
      <div className="compare-list">
        {multiStore.map((group) => (
          <article key={group.key} className="compare-card">
            <header>
              <h2>{group.label}</h2>
              {group.cheapest && (
                <p className="compare-best">
                  Best: {formatPrice(group.cheapest.price)} at {group.cheapest.location.store}
                </p>
              )}
            </header>
            <table>
              <thead>
                <tr>
                  <th>Store</th>
                  <th>Price</th>
                  <th>When</th>
                  {onDeleteProduct && <th className="compare-actions-col" aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {group.entries.map((entry) => (
                  <tr
                    key={entry.id}
                    className={entry.id === group.cheapest?.id ? "cheapest" : undefined}
                  >
                    <td>{entry.location.store}</td>
                    <td>{formatPrice(entry.price)}</td>
                    <td title={formatCapturedAt(entry.captured_at) ?? undefined}>
                      {formatCapturedAt(entry.captured_at) ?? "—"}
                    </td>
                    {onDeleteProduct && (
                      <td className="compare-actions-col">
                        <button
                          type="button"
                          className="row-delete"
                          aria-label={`Delete ${entry.product_name}`}
                          disabled={deletingId === entry.id}
                          onClick={() => onDeleteProduct(entry.id)}
                        >
                          Delete
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </article>
        ))}
      </div>

      {multiStore.length === 0 && (
        <p className="status">No comparable products yet. Upload more photos across stores.</p>
      )}
    </section>
  );
}
