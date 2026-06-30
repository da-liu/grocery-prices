import { useEffect } from "react";
import { createPortal } from "react-dom";

interface PhotoLightboxProps {
  src: string;
  alt: string;
  onClose: () => void;
}

export function PhotoLightbox({ src, alt, onClose }: PhotoLightboxProps) {
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
      <img
        className="photo-lightbox-image"
        src={src}
        alt={alt}
        onClick={(event) => event.stopPropagation()}
      />
    </div>,
    document.body,
  );
}
