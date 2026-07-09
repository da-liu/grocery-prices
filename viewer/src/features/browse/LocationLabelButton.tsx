import { MapPin } from "lucide-react";
import "./LocationLabelButton.css";
interface LocationLabelButtonProps {
  onClick: () => void;
  needsLabel?: boolean;
}

export function LocationLabelButton({ onClick, needsLabel }: LocationLabelButtonProps) {
  return (
    <button
      type="button"
      className={needsLabel ? "location-label-btn needs-label" : "location-label-btn"}
      aria-label={needsLabel ? "Label this location" : "Change store label"}
      title={needsLabel ? "Label this location" : "Change store label"}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <MapPin size={13} fill="currentColor" aria-hidden />
    </button>
  );
}
