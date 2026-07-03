const MS_PER_MINUTE = 60 * 1000;
const MS_PER_HOUR = 60 * MS_PER_MINUTE;
const MS_PER_DAY = 24 * MS_PER_HOUR;

function startOfLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Calendar days between two instants (local midnight boundaries). */
function calendarDaysBetween(earlier: Date, later: Date): number {
  return Math.round(
    (startOfLocalDay(later).getTime() - startOfLocalDay(earlier).getTime()) / MS_PER_DAY,
  );
}

function formatShortCaptureDate(captured: Date, now: Date): string {
  const sameYear = captured.getFullYear() === now.getFullYear();
  return captured.toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

/**
 * Relative capture time for shelf-tag photos.
 *
 * Follows common design-system guidance:
 * - Count days by calendar date, not elapsed 24h windows (Atlassian).
 * - Use minutes/hours for same-day recency (Cloudscape).
 * - Use "yesterday" for one calendar day back (Atlassian).
 * - Switch to a short absolute date after one week (Atlassian).
 * - Pair with formatCapturedAt in a tooltip for the precise timestamp.
 *
 * EXIF DateTimeOriginal has no timezone; captured_at strings are local time.
 */
export function formatCapturedAgo(
  capturedAt: string | undefined,
  now: Date = new Date(),
): string | null {
  if (!capturedAt) return null;

  const captured = new Date(capturedAt);
  if (Number.isNaN(captured.getTime())) return null;

  const calendarDays = calendarDaysBetween(captured, now);
  if (calendarDays < 0) return "today";

  if (calendarDays === 0) {
    const elapsedMs = now.getTime() - captured.getTime();
    if (elapsedMs < MS_PER_MINUTE) return "just now";
    if (elapsedMs < MS_PER_HOUR) {
      const minutes = Math.floor(elapsedMs / MS_PER_MINUTE);
      return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
    }
    const hours = Math.floor(elapsedMs / MS_PER_HOUR);
    return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  }

  if (calendarDays === 1) return "yesterday";
  if (calendarDays < 7) return `${calendarDays} days ago`;
  if (calendarDays === 7) return "1 week ago";

  return formatShortCaptureDate(captured, now);
}

export function formatCapturedAt(capturedAt: string | undefined) {
  if (!capturedAt) return null;
  const captured = new Date(capturedAt);
  if (Number.isNaN(captured.getTime())) return null;
  return captured.toLocaleString("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
