import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/features/auth/AuthContext";
import { useCatalog } from "../CatalogContext";
import { completeOnboarding } from "@/shared/api/api";
import { Coachmark } from "./Coachmark";
import {
  type ActiveTip,
  type ContextualOnboardingTipId,
  coachmarkViewFor,
  findMultiProductImageId,
  findProductForImage,
  findRelatedProductTarget,
  hasCompletedTip,
  ONBOARDING_MULTI_PRODUCT_PHOTO,
  ONBOARDING_RELATED_PRODUCTS,
  photoLinkSelector,
  photoProductRowSelector,
  relatedProductsSelector,
  sortFilterSelector,
} from "./tips";

function scrollToSelector(selector: string) {
  window.requestAnimationFrame(() => {
    document.querySelector(selector)?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  });
}

export function ContextualOnboardingProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, refresh, applyUser } = useAuth();
  const catalog = useCatalog();
  const [activeTip, setActiveTip] = useState<ActiveTip | null>(null);
  const [locallyCompleted, setLocallyCompleted] = useState<string[]>([]);
  const completingRef = useRef(false);
  const activeTipRef = useRef<ActiveTip | null>(null);
  activeTipRef.current = activeTip;

  const completed = [
    ...new Set([...(user?.onboarding_completed ?? []), ...locallyCompleted]),
  ];
  const compact =
    catalog.selectionMode || catalog.browseQuery.gridColumns >= 3;
  const canShowTips =
    Boolean(user) &&
    !user!.needs_onboarding &&
    !catalog.showOnboarding &&
    !catalog.productsLoading &&
    catalog.products.length > 0 &&
    !compact;

  const completeTip = useCallback(
    async (tipId: ContextualOnboardingTipId) => {
      if (completingRef.current) return;
      completingRef.current = true;
      setLocallyCompleted((prev) =>
        prev.includes(tipId) ? prev : [...prev, tipId],
      );
      setActiveTip(null);
      try {
        const profile = await completeOnboarding(tipId);
        applyUser(profile);
        await refresh();
      } finally {
        completingRef.current = false;
      }
    },
    [applyUser, refresh],
  );

  const dismissActiveTip = useCallback(() => {
    const tip = activeTipRef.current;
    if (!tip) return;
    void completeTip(tip.id);
  }, [completeTip]);

  useEffect(() => {
    if (!canShowTips || activeTip || completingRef.current) return;

    const preferMulti = Boolean(catalog.multiProductTipImageId);
    const multiDone = hasCompletedTip(completed, ONBOARDING_MULTI_PRODUCT_PHOTO);
    const relatedDone = hasCompletedTip(completed, ONBOARDING_RELATED_PRODUCTS);

    if (!multiDone && (preferMulti || !relatedDone)) {
      const imageId = findMultiProductImageId(
        catalog.photoGroupSizes,
        catalog.multiProductTipImageId,
      );
      const product = imageId
        ? findProductForImage(catalog.products, imageId)
        : undefined;

      if (
        imageId &&
        product &&
        catalog.browseQuery.viewMode === "products" &&
        !catalog.selectionMode
      ) {
        setActiveTip({
          id: ONBOARDING_MULTI_PRODUCT_PHOTO,
          step: 1,
          imageId,
          productId: product.id,
        });
        scrollToSelector(photoLinkSelector(product.id));
        return;
      }
    }

    if (!relatedDone && catalog.browseQuery.viewMode === "products") {
      const target = findRelatedProductTarget(
        catalog.browseDisplayed,
        catalog.productsById,
      );
      if (target) {
        setActiveTip({
          id: ONBOARDING_RELATED_PRODUCTS,
          productId: target.id,
        });
        scrollToSelector(relatedProductsSelector(target.id));
      }
    }
  }, [
    activeTip,
    canShowTips,
    catalog.browseDisplayed,
    catalog.browseQuery.viewMode,
    catalog.multiProductTipImageId,
    catalog.photoGroupSizes,
    catalog.products,
    catalog.productsById,
    catalog.selectionMode,
    completed,
  ]);

  useEffect(() => {
    if (activeTip?.id !== ONBOARDING_MULTI_PRODUCT_PHOTO) return;

    if (activeTip.step === 1 && catalog.browseQuery.viewMode === "photos") {
      setActiveTip({ ...activeTip, step: 2 });
      scrollToSelector(photoProductRowSelector(activeTip.imageId));
    } else if (
      activeTip.step === 2 &&
      catalog.browseQuery.viewMode === "products"
    ) {
      setActiveTip({ ...activeTip, step: 3 });
      scrollToSelector(sortFilterSelector());
    }
  }, [activeTip, catalog.browseQuery.viewMode]);

  const view = activeTip ? coachmarkViewFor(activeTip) : null;

  return (
    <>
      {children}
      {view && <Coachmark {...view} onDismiss={dismissActiveTip} />}
    </>
  );
}
