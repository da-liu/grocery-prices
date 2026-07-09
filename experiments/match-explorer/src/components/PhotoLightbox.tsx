import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import "./PhotoLightbox.css";

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

function getTouchCenter(touches: TouchList) {
  if (touches.length < 2) return { x: 0, y: 0 };
  return {
    x: (touches[0].clientX + touches[1].clientX) / 2,
    y: (touches[0].clientY + touches[1].clientY) / 2,
  };
}

export function PhotoLightbox({ src, alt, onClose }: PhotoLightboxProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const scaleRef = useRef(1);
  const translateRef = useRef({ x: 0, y: 0 });

  const pinchStartRef = useRef({
    distance: 0,
    scale: 1,
    imageRelativeCenter: { x: 0, y: 0 },
    globalCenter: { x: 0, y: 0 },
    translate: { x: 0, y: 0 },
  });

  const panStartRef = useRef({ x: 0, y: 0, translateX: 0, translateY: 0 });
  const mousePanRef = useRef({ active: false, x: 0, y: 0, translateX: 0, translateY: 0 });

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

  function zoomAt(clientX: number, clientY: number, nextScale: number) {
    const img = imgRef.current;
    if (!img) return;

    const clamped = Math.min(MAX_SCALE, Math.max(MIN_SCALE, nextScale));
    const scaleRatio = clamped / scaleRef.current;
    const rect = img.getBoundingClientRect();
    const imageRelativeCenter = {
      x: clientX - (rect.left + rect.width / 2),
      y: clientY - (rect.top + rect.height / 2),
    };

    translateRef.current = {
      x: translateRef.current.x - imageRelativeCenter.x * (scaleRatio - 1),
      y: translateRef.current.y - imageRelativeCenter.y * (scaleRatio - 1),
    };
    scaleRef.current = clamped;

    if (scaleRef.current <= 1) {
      translateRef.current = { x: 0, y: 0 };
    }
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
    resetTransform();
  }, [src]);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    function onTouchStart(event: TouchEvent) {
      if (event.touches.length === 2) {
        const globalCenter = getTouchCenter(event.touches);
        const rect = img!.getBoundingClientRect();
        const imageRelativeCenter = {
          x: globalCenter.x - (rect.left + rect.width / 2),
          y: globalCenter.y - (rect.top + rect.height / 2),
        };

        pinchStartRef.current = {
          distance: getTouchDistance(event.touches),
          scale: scaleRef.current,
          imageRelativeCenter,
          globalCenter,
          translate: { ...translateRef.current },
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
        const start = pinchStartRef.current;
        if (!start.distance) return;

        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, start.scale * (distance / start.distance)));
        const scaleRatio = nextScale / start.scale;
        const currentCenter = getTouchCenter(event.touches);
        const driftX = currentCenter.x - start.globalCenter.x;
        const driftY = currentCenter.y - start.globalCenter.y;

        translateRef.current = {
          x: start.translate.x - start.imageRelativeCenter.x * (scaleRatio - 1) + driftX,
          y: start.translate.y - start.imageRelativeCenter.y * (scaleRatio - 1) + driftY,
        };
        scaleRef.current = nextScale;

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
      if (event.touches.length === 1 && scaleRef.current > 1) {
        panStartRef.current = {
          x: event.touches[0].clientX,
          y: event.touches[0].clientY,
          translateX: translateRef.current.x,
          translateY: translateRef.current.y,
        };
      }

      if (event.touches.length < 2) {
        pinchStartRef.current.distance = 0;
      }

      if (scaleRef.current <= 1) {
        resetTransform();
      }
    }

    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const delta = event.deltaY > 0 ? -0.12 : 0.12;
      zoomAt(event.clientX, event.clientY, scaleRef.current * (1 + delta));
    }

    function onMouseDown(event: MouseEvent) {
      if (scaleRef.current <= 1 || event.button !== 0) return;
      mousePanRef.current = {
        active: true,
        x: event.clientX,
        y: event.clientY,
        translateX: translateRef.current.x,
        translateY: translateRef.current.y,
      };
    }

    function onMouseMove(event: MouseEvent) {
      if (!mousePanRef.current.active || scaleRef.current <= 1) return;
      translateRef.current = {
        x: mousePanRef.current.translateX + (event.clientX - mousePanRef.current.x),
        y: mousePanRef.current.translateY + (event.clientY - mousePanRef.current.y),
      };
      applyTransform();
    }

    function onMouseUp() {
      mousePanRef.current.active = false;
    }

    function onDoubleClick(event: MouseEvent) {
      event.preventDefault();
      if (scaleRef.current > 1) {
        resetTransform();
      } else {
        zoomAt(event.clientX, event.clientY, 2);
      }
    }

    const passiveOption = { passive: true } as const;
    const activeOption = { passive: false } as const;

    img.addEventListener("touchstart", onTouchStart, passiveOption);
    img.addEventListener("touchmove", onTouchMove, activeOption);
    img.addEventListener("touchend", onTouchEnd, passiveOption);
    img.addEventListener("touchcancel", onTouchEnd, passiveOption);
    img.addEventListener("wheel", onWheel, activeOption);
    img.addEventListener("mousedown", onMouseDown);
    img.addEventListener("dblclick", onDoubleClick);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    return () => {
      img.removeEventListener("touchstart", onTouchStart);
      img.removeEventListener("touchmove", onTouchMove);
      img.removeEventListener("touchend", onTouchEnd);
      img.removeEventListener("touchcancel", onTouchEnd);
      img.removeEventListener("wheel", onWheel);
      img.removeEventListener("mousedown", onMouseDown);
      img.removeEventListener("dblclick", onDoubleClick);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [src]);

  return createPortal(
    <div
      className="photo-lightbox-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      onClick={onClose}
    >
      <button type="button" className="photo-lightbox-close" aria-label="Close photo" onClick={onClose}>
        <X size={28} aria-hidden />
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
      <div className="photo-lightbox-caption">{alt}</div>
    </div>,
    document.body,
  );
}
