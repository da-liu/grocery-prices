export function formatPrice(
  price: number | null | undefined,
  currency = "CAD",
): string {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
  }).format(price);
}
