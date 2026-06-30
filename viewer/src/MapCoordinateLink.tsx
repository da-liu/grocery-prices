import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const TOOLTIP_WIDTH = 280;
const TOOLTIP_HEIGHT = 200;
const TOOLTIP_GAP = 8;
const HIDE_DELAY_MS = 120;

function mapsUrl(lat: number, lon: number) {
  return `https://www.google.com/maps?q=${lat},${lon}`;
}

const MAP_TOOLTIP_ZOOM = 15;

function mapsEmbedUrl(lat: number, lon: number) {
  return `https://maps.google.com/maps?q=${lat},${lon}&z=${MAP_TOOLTIP_ZOOM}&output=embed`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function MapCoordinateLink({ lat, lon }: { lat: number; lon: number }) {
  const anchorRef = useRef<HTMLAnchorElement>(null);
  const hideTimerRef = useRef<number | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;

    const rect = anchor.getBoundingClientRect();
    const left = clamp(
      rect.left,
      TOOLTIP_GAP,
      window.innerWidth - TOOLTIP_WIDTH - TOOLTIP_GAP,
    );
    const belowTop = rect.bottom + TOOLTIP_GAP;
    const aboveTop = rect.top - TOOLTIP_HEIGHT - TOOLTIP_GAP;
    const top =
      belowTop + TOOLTIP_HEIGHT <= window.innerHeight - TOOLTIP_GAP
        ? belowTop
        : clamp(aboveTop, TOOLTIP_GAP, window.innerHeight - TOOLTIP_HEIGHT - TOOLTIP_GAP);

    setPosition({ top, left });
  }, []);

  const showTooltip = useCallback(() => {
    window.clearTimeout(hideTimerRef.current);
    updatePosition();
    setOpen(true);
  }, [updatePosition]);

  const hideTooltip = useCallback(() => {
    hideTimerRef.current = window.setTimeout(() => setOpen(false), HIDE_DELAY_MS);
  }, []);

  useEffect(() => {
    if (!open) return;

    const onScrollOrResize = () => updatePosition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    return () => window.clearTimeout(hideTimerRef.current);
  }, []);

  const label = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;

  return (
    <>
      <a
        ref={anchorRef}
        href={mapsUrl(lat, lon)}
        target="_blank"
        rel="noreferrer"
        className="map-coordinate-link"
        aria-describedby={open ? "map-coordinate-tooltip" : undefined}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
      >
        {label}
      </a>
      {open &&
        createPortal(
          <div
            id="map-coordinate-tooltip"
            role="tooltip"
            className="map-tooltip"
            style={{ top: position.top, left: position.left }}
            onMouseEnter={showTooltip}
            onMouseLeave={hideTooltip}
          >
            <iframe
              title={`Google Map for ${label}`}
              src={mapsEmbedUrl(lat, lon)}
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>,
          document.body,
        )}
    </>
  );
}
