import { resolveRelatedProducts } from "../browseQuery";
import type { Product } from "@/shared/types/types";

export const ONBOARDING_RELATED_PRODUCTS = "related_products" as const;
export const ONBOARDING_MULTI_PRODUCT_PHOTO = "multi_product_photo" as const;

export type ContextualOnboardingTipId =
  | typeof ONBOARDING_RELATED_PRODUCTS
  | typeof ONBOARDING_MULTI_PRODUCT_PHOTO;

export type ActiveTip =
  | { id: typeof ONBOARDING_RELATED_PRODUCTS; productId: string }
  | {
      id: typeof ONBOARDING_MULTI_PRODUCT_PHOTO;
      step: 1 | 2 | 3;
      imageId: string;
      productId: string;
    };

export type CoachmarkView = {
  targetSelector: string;
  title: string;
  body: string;
  /** Omit for tips that advance by interacting with the target. */
  actionLabel?: string;
  /** When false, clicks on the highlighted target are swallowed. */
  allowTargetClick?: boolean;
};

export function hasCompletedTip(
  completed: string[] | undefined,
  tip: ContextualOnboardingTipId,
): boolean {
  return (completed ?? []).includes(tip);
}

export function findMultiProductImageId(
  photoGroupSizes: ReadonlyMap<string, number>,
  preferredImageId?: string | null,
): string | null {
  if (preferredImageId && (photoGroupSizes.get(preferredImageId) ?? 0) >= 2) {
    return preferredImageId;
  }
  for (const [imageId, count] of photoGroupSizes) {
    if (count >= 2) return imageId;
  }
  return null;
}

export function findProductForImage(
  products: Product[],
  imageId: string,
): Product | undefined {
  return products.find((product) => product.image_id === imageId);
}

export function findRelatedProductTarget(
  products: Product[],
  productsById: Map<string, Product>,
): Product | null {
  for (const product of products) {
    if (resolveRelatedProducts(product, productsById).length > 0) {
      return product;
    }
  }
  return null;
}

export function relatedProductsSelector(productId: string): string {
  return `#product-${productId} [data-onboarding-target="related-products"]`;
}

export function photoLinkSelector(productId: string): string {
  return `#product-${productId} [data-onboarding-target="photo-link"]`;
}

export function photoProductRowSelector(imageId: string): string {
  return `#photo-${imageId} [data-onboarding-target="photo-product-row"]`;
}

export function sortFilterSelector(): string {
  return `[data-onboarding-target="sort-filter"]`;
}

const RELATED_COPY = {
  title: "Related products",
  body: "We surface the same or similar items from your past photos and other stores, so you can compare what this price should look like.",
} as const;

const MULTI_STEPS = {
  1: {
    title: "Multiple products in one photo",
    body: "This shelf photo has more than one product. Use the Photo link to see everything from that photo together.",
  },
  2: {
    title: "Back to product view",
    body: "Click any product here to jump back to its product card in the catalog.",
  },
  3: {
    title: "Switch views anytime",
    body: "You can also change between product and photo view in Sort & filter.",
  },
} as const;

/** Copy used by tests and UI assertions. */
export const TIP_COPY = {
  [ONBOARDING_RELATED_PRODUCTS]: RELATED_COPY,
  multiProductStep1: MULTI_STEPS[1],
  multiProductStep2: MULTI_STEPS[2],
  multiProductStep3: MULTI_STEPS[3],
} as const;

export function coachmarkViewFor(tip: ActiveTip): CoachmarkView {
  if (tip.id === ONBOARDING_RELATED_PRODUCTS) {
    return {
      targetSelector: relatedProductsSelector(tip.productId),
      title: RELATED_COPY.title,
      body: RELATED_COPY.body,
      actionLabel: "Got it",
    };
  }

  if (tip.step === 1) {
    return {
      targetSelector: photoLinkSelector(tip.productId),
      title: MULTI_STEPS[1].title,
      body: MULTI_STEPS[1].body,
    };
  }

  if (tip.step === 2) {
    return {
      targetSelector: photoProductRowSelector(tip.imageId),
      title: MULTI_STEPS[2].title,
      body: MULTI_STEPS[2].body,
    };
  }

  return {
    targetSelector: sortFilterSelector(),
    title: MULTI_STEPS[3].title,
    body: MULTI_STEPS[3].body,
    actionLabel: "Got it",
    allowTargetClick: false,
  };
}
