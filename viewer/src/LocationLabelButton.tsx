interface LocationLabelButtonProps {
  onClick: () => void;
  needsLabel?: boolean;
}

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7Zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5Z"
      />
    </svg>
  );
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
      <PinIcon />
    </button>
  );
}
