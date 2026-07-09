import { useEffect, useMemo, useRef, useState } from "react";
import type { ProductRecord } from "@/lib/types";

interface ProductPickerProps {
  products: ProductRecord[];
  sourceId: string | null;
  onSourceChange: (id: string | null) => void;
  label?: string;
}

export function ProductPicker({ products, sourceId, onSourceChange, label = "Source product" }: ProductPickerProps) {
  const [filter, setFilter] = useState("");
  const selectRef = useRef<HTMLSelectElement>(null);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return products;
    return products.filter((p) =>
      [p.product_name, p.image_id, p.barcode ?? "", p.category].join(" ").toLowerCase().includes(q),
    );
  }, [filter, products]);

  useEffect(() => {
    if (!sourceId) return;
    const visible = filtered.some((p) => p.id === sourceId);
    if (!visible && products.some((p) => p.id === sourceId)) {
      setFilter("");
    }
  }, [sourceId, filtered, products]);

  useEffect(() => {
    const select = selectRef.current;
    if (!select || !sourceId) return;
    const option = select.querySelector(`option[value="${CSS.escape(sourceId)}"]`);
    option?.scrollIntoView({ block: "nearest" });
  }, [sourceId, filtered]);

  return (
    <div className="product-picker">
      <label>
        {label}
        <input
          type="search"
          placeholder="Search products…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </label>
      <select
        ref={selectRef}
        value={sourceId ?? ""}
        onChange={(e) => onSourceChange(e.target.value || null)}
        size={8}
      >
        {filtered.map((product) => (
          <option key={product.id} value={product.id}>
            {product.product_name} · {product.image_id}
            {product.barcode ? ` · ${product.barcode}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
