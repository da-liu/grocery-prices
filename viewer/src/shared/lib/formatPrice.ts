export function formatPrice(price: number | null | undefined): string {
  if (price == null) return "—";
  return price.toLocaleString(undefined, {
    style: "currency",
    currency: "CAD",
  });
}
