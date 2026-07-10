import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";
import "./Coachmark.css";

export interface CoachmarkProps {
  targetSelector: string;
  title: string;
  body: string;
  onDismiss: () => void;
  /** When set, shows a primary dismiss button. */
  actionLabel?: string;
  /** When false, clicks on the highlighted target are swallowed. */
  allowTargetClick?: boolean;
}

const ANCHOR_NAME = "--coachmark-target";

function isHeaderTarget(target: HTMLElement): boolean {
  return Boolean(
    target.closest(".top-bar, .top-bar-actions, .app-header, header") ||
      target.matches("[data-onboarding-target='sort-filter']"),
  );
}

function suppressNextClick() {
  const blockClick = (ev: MouseEvent) => {
    ev.preventDefault();
    ev.stopPropagation();
    cleanup();
  };
  const cleanup = () => {
    window.removeEventListener("click", blockClick, true);
    window.clearTimeout(timer);
  };
  window.addEventListener("click", blockClick, true);
  const timer = window.setTimeout(cleanup, 500);
}

/**
 * Tip uses the Popover API (top layer) + CSS anchor positioning so it stays
 * tethered to the target without JS geometry math or overflow clipping.
 */
export function Coachmark({
  targetSelector,
  title,
  body,
  onDismiss,
  actionLabel,
  allowTargetClick = true,
}: CoachmarkProps) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const [targetEl, setTargetEl] = useState<HTMLElement | null>(null);
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  useLayoutEffect(() => {
    const el = document.querySelector(targetSelector);
    if (!(el instanceof HTMLElement)) {
      setTargetEl(null);
      return;
    }
    const target = el;

    const icon = isHeaderTarget(target);
    target.classList.add("coachmark-target-active");
    if (icon) target.classList.add("coachmark-target-active--icon");
    target.style.setProperty("anchor-name", ANCHOR_NAME);
    target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "auto" });
    setTargetEl(target);

    return () => {
      target.classList.remove("coachmark-target-active", "coachmark-target-active--icon");
      target.style.removeProperty("anchor-name");
      setTargetEl(null);
    };
  }, [targetSelector]);

  useLayoutEffect(() => {
    const popover = popoverRef.current;
    if (!targetEl || !popover) return;

    try {
      popover.showPopover({ source: targetEl });
    } catch {
      popover.showPopover();
    }

    return () => {
      if (popover.matches(":popover-open")) {
        popover.hidePopover();
      }
    };
  }, [targetEl]);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      const node = e.target;
      if (!(node instanceof Node)) return;

      const tip = popoverRef.current;
      if (tip?.contains(node)) return;

      const target = document.querySelector(targetSelector);
      if (target instanceof HTMLElement && target.contains(node)) {
        if (!allowTargetClick) {
          e.preventDefault();
          e.stopPropagation();
          suppressNextClick();
        }
        return;
      }

      // Block outside interaction; dismiss only via the explicit button.
      e.preventDefault();
      e.stopPropagation();
      suppressNextClick();
    }

    window.addEventListener("pointerdown", onPointerDown, true);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown, true);
    };
  }, [targetSelector, allowTargetClick]);

  function handlePrimaryPointerDown(e: ReactPointerEvent<HTMLButtonElement>) {
    e.stopPropagation();
  }

  function handlePrimaryClick(e: ReactMouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    e.stopPropagation();
    onDismissRef.current();
  }

  if (!targetEl) return null;

  return createPortal(
    <>
      <div className="coachmark-scrim" aria-hidden />
      <div
        ref={popoverRef}
        id="coachmark-dialog"
        className="coachmark-card"
        popover="manual"
        role="dialog"
        aria-modal={actionLabel ? true : undefined}
        aria-labelledby="coachmark-title"
      >
        <h3 id="coachmark-title">{title}</h3>
        <p>{body}</p>
        {actionLabel && (
          <button
            type="button"
            data-testid="coachmark-got-it"
            onPointerDown={handlePrimaryPointerDown}
            onClick={handlePrimaryClick}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </>,
    document.body,
  );
}
