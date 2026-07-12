import { useEffect, useState } from "react";
import { extractionProgressPercent } from "./extractionProgress";

export function ExtractionProgressBar({
  startedAt,
  ariaLabel = "Reading prices progress",
}: {
  startedAt: number;
  ariaLabel?: string;
}) {
  const [, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setTick((value) => value + 1), 200);
    return () => window.clearInterval(id);
  }, []);

  const percent = extractionProgressPercent(startedAt);

  return (
    <div
      className="upload-status-progress"
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel}
    >
      <div className="upload-status-progress-bar" style={{ width: `${percent}%` }} />
    </div>
  );
}
