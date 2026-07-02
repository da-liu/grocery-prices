import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface PhotoLightboxProps {
  src: string;
  alt: string;
  onClose: () => void;
}

const MIN_SCALE = 1;
const MAX_SCALE = 4;

function getTouchDistance(touches: TouchList) {
  if (touches.length < 2) return 0;
  const dx = touches[0].clientX - touches[1].clientX;
  const dy = touches[0].clientY - touches[1].clientY;
  return Math.hypot(dx, dy);
}

export function PhotoLightbox({ src, alt, onClose }: PhotoLightboxProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const scaleRef = useRef(1);
  const translateRef = useRef({ x: 0, y: 0 });
  const pinchStartRef = useRef({ distance: 0, scale: 1 });
  const panStartRef = useRef({ x: 0, y: 0, translateX: 0, translateY: 0 });

  function applyTransform() {
    const img = imgRef.current;
    if (!img) return;
    const { x, y } = translateRef.current;
    img.style.transform = `translate(${x}px, ${y}px) scale(${scaleRef.current})`;
    viewportRef.current?.classList.toggle("is-zoomed", scaleRef.current > 1);
  }

  function resetTransform() {
    scaleRef.current = 1;
    translateRef.current = { x: 0, y: 0 };
    applyTransform();
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    function onTouchStart(event: TouchEvent) {
      if (event.touches.length === 2) {
        pinchStartRef.current = {
          distance: getTouchDistance(event.touches),
          scale: scaleRef.current,
        };
      } else if (event.touches.length === 1 && scaleRef.current > 1) {
        panStartRef.current = {
          x: event.touches[0].clientX,
          y: event.touches[0].clientY,
          translateX: translateRef.current.x,
          translateY: translateRef.current.y,
        };
      }
    }

    function onTouchMove(event: TouchEvent) {
      if (event.touches.length === 2) {
        event.preventDefault();
        const distance = getTouchDistance(event.touches);
        if (!pinchStartRef.current.distance) return;
        const next =
          pinchStartRef.current.scale * (distance / pinchStartRef.current.distance);
        scaleRef.current = Math.min(MAX_SCALE, Math.max(MIN_SCALE, next));
        if (scaleRef.current <= 1) {
          translateRef.current = { x: 0, y: 0 };
        }
        applyTransform();
      } else if (event.touches.length === 1 && scaleRef.current > 1) {
        event.preventDefault();
        const touch = event.touches[0];
        translateRef.current = {
          x: panStartRef.current.translateX + (touch.clientX - panStartRef.current.x),
          y: panStartRef.current.translateY + (touch.clientY - panStartRef.current.y),
        };
        applyTransform();
      }
    }

    function onTouchEnd(event: TouchEvent) {
      if (event.touches.length < 2) {
        pinchStartRef.current = { distance: 0, scale: scaleRef.current };
      }
      if (scaleRef.current <= 1) {
        resetTransform();
      }
    }

    img.addEventListener("touchstart", onTouchStart, { passive: true });
    img.addEventListener("touchmove", onTouchMove, { passive: false });
    img.addEventListener("touchend", onTouchEnd, { passive: true });
    img.addEventListener("touchcancel", onTouchEnd, { passive: true });

    return () => {
      img.removeEventListener("touchstart", onTouchStart);
      img.removeEventListener("touchmove", onTouchMove);
      img.removeEventListener("touchend", onTouchEnd);
      img.removeEventListener("touchcancel", onTouchEnd);
    };
  }, []);

  return createPortal(
    <div
      className="photo-lightbox-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      onClick={onClose}
    >
      <button
        type="button"
        className="photo-lightbox-close"
        aria-label="Close photo"
        onClick={onClose}
      >
        ×
      </button>
      <div ref={viewportRef} className="photo-lightbox-viewport">
        <img
          ref={imgRef}
          className="photo-lightbox-image"
          src={src}
          alt={alt}
          draggable={false}
          onClick={(event) => event.stopPropagation()}
        />
      </div>
    </div>,
    document.body,
  );
}
