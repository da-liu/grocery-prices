import { getBrowserCurrency } from "./getBrowserCurrency";

let cachedCurrency: string | undefined;

function getCachedCurrency(): string {
  if (cachedCurrency === undefined) {
    cachedCurrency = getBrowserCurrency();
  }
  return cachedCurrency;
}

export function formatPrice(price: number | null | undefined): string {
  if (price == null) return "—";
  return price.toLocaleString(undefined, {
    style: "currency",
    currency: getCachedCurrency(),
  });
}
