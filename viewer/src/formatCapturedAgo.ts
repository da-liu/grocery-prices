const MS_PER_DAY = 24 * 60 * 60 * 1000;

function calendarMonthsAndDays(from: Date, to: Date) {
  let months =
    (to.getFullYear() - from.getFullYear()) * 12 +
    (to.getMonth() - from.getMonth());
  let days = to.getDate() - from.getDate();

  if (days < 0) {
    months -= 1;
    days += new Date(to.getFullYear(), to.getMonth(), 0).getDate();
  }

  return { months, days };
}

export function formatCapturedAgo(
  capturedAt: string | undefined,
  now: Date = new Date(),
): string | null {
  if (!capturedAt) return null;

  const captured = new Date(capturedAt);
  if (Number.isNaN(captured.getTime())) return null;

  const totalDays = Math.floor((now.getTime() - captured.getTime()) / MS_PER_DAY);
  if (totalDays < 0) return "today";
  if (totalDays === 0) return "today";
  if (totalDays === 1) return "1 day ago";
  if (totalDays < 30) return `${totalDays} days ago`;

  const { months, days } = calendarMonthsAndDays(captured, now);
  if (months === 0) return `${totalDays} days ago`;

  const parts: string[] = [];
  parts.push(months === 1 ? "1 mon" : `${months} mon`);
  if (days === 1) parts.push("1 day");
  else if (days > 0) parts.push(`${days} days`);

  return parts.join(" ");
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
