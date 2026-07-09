import { Image } from "lucide-react";
import type { PhotoRecord } from "@/lib/types";
import { useLightbox } from "@/components/LightboxContext";

const PHOTOS_BASE = "/photos/";

export function photoImageUrl(photo: Pick<PhotoRecord, "image_file">): string | null {
  if (!photo.image_file) return null;
  return `${PHOTOS_BASE}${photo.image_file.split("/").map(encodeURIComponent).join("/")}`;
}

export function OpenImageLink({
  href,
  label,
  className,
}: {
  href: string | null;
  label: string;
  className?: string;
}) {
  const { openLightbox } = useLightbox();

  if (!href) return null;

  return (
    <button
      type="button"
      className={className ?? "open-image-link"}
      title={`View ${label}`}
      aria-label={`View ${label}`}
      onClick={(e) => {
        e.stopPropagation();
        openLightbox(href, label);
      }}
    >
      <Image size={14} aria-hidden />
    </button>
  );
}
