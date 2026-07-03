import { describe, expect, it } from "vitest";
import { formatCapturedAgo, formatCapturedAt } from "./formatCapturedAgo";

/** Local Date constructor helper (month is 0-indexed). */
function local(y: number, m: number, d: number, h = 12, min = 0, sec = 0) {
  return new Date(y, m, d, h, min, sec);
}

describe("formatCapturedAgo", () => {
  describe("calendar-day counting (Atlassian: days by date, not 24h elapsed)", () => {
    it("reports 2 calendar days for Tue evening photo viewed Thu afternoon", () => {
      const now = local(2026, 6, 2, 15, 0); // Thu Jul 2
      expect(formatCapturedAgo("2026-06-30T19:46:05", now)).toBe("2 days ago");
    });

    it("reports 2 calendar days even before the same clock time on Thu", () => {
      const now = local(2026, 6, 2, 8, 0); // Thu Jul 2 morning
      expect(formatCapturedAgo("2026-06-30T19:46:05", now)).toBe("2 days ago");
    });

    it("uses yesterday for one calendar day back", () => {
      const now = local(2026, 6, 2, 10, 0);
      expect(formatCapturedAgo("2026-07-01T22:30:00", now)).toBe("yesterday");
    });

    it("uses yesterday even when fewer than 24 hours have elapsed", () => {
      const now = local(2026, 6, 2, 6, 0); // Thu 6am
      expect(formatCapturedAgo("2026-07-01T20:00:00", now)).toBe("yesterday");
    });

    it("uses hours ago on the same calendar day", () => {
      const now = local(2026, 6, 2, 20, 0);
      expect(formatCapturedAgo("2026-07-02T08:00:00", now)).toBe("12 hours ago");
    });
  });

  describe("sub-day granularity on the same calendar day (Cloudscape)", () => {
    it("shows minutes ago within the last hour", () => {
      const now = local(2026, 6, 2, 15, 30);
      expect(formatCapturedAgo("2026-07-02T15:05:00", now)).toBe("25 minutes ago");
    });

    it("shows 1 minute ago singular", () => {
      const now = local(2026, 6, 2, 15, 2);
      expect(formatCapturedAgo("2026-07-02T15:01:00", now)).toBe("1 minute ago");
    });

    it("shows hours ago after 60 minutes on the same day", () => {
      const now = local(2026, 6, 2, 15, 0);
      expect(formatCapturedAgo("2026-07-02T12:00:00", now)).toBe("3 hours ago");
    });

    it("shows 1 hour ago singular", () => {
      const now = local(2026, 6, 2, 15, 0);
      expect(formatCapturedAgo("2026-07-02T14:00:00", now)).toBe("1 hour ago");
    });
  });

  describe("week and multi-day windows", () => {
    it("shows 1 week ago at exactly 7 calendar days", () => {
      const now = local(2026, 6, 9, 12, 0);
      expect(formatCapturedAgo("2026-07-02T08:00:00", now)).toBe("1 week ago");
    });

    it("shows X days ago between 2 and 6 calendar days", () => {
      const now = local(2026, 6, 5, 12, 0); // Jul 5
      expect(formatCapturedAgo("2026-06-30T19:46:05", now)).toBe("5 days ago");
    });
  });

  describe("older captures switch to absolute date (Atlassian: > 7 days)", () => {
    it("shows a short absolute date between 8 and 29 calendar days", () => {
      const now = local(2026, 6, 15, 12, 0); // Jul 15
      const label = formatCapturedAgo("2026-06-30T19:46:05", now);
      expect(label).toMatch(/Jun/);
      expect(label).toMatch(/30/);
      expect(label).not.toContain("ago");
    });

    it("shows a short absolute date after 7 calendar days", () => {
      const now = local(2026, 6, 10, 12, 0); // Jul 10
      const label = formatCapturedAgo("2026-06-30T19:46:05", now);
      expect(label).toMatch(/Jun/);
      expect(label).toMatch(/30/);
      expect(label).not.toContain("ago");
    });

    it("includes year when capture is from a prior calendar year", () => {
      const now = local(2027, 0, 15, 12, 0); // Jan 15, 2027
      const label = formatCapturedAgo("2026-06-30T19:46:05", now);
      expect(label).toMatch(/2026/);
    });
  });

  describe("edge cases", () => {
    it("returns null for missing input", () => {
      expect(formatCapturedAgo(undefined)).toBeNull();
    });

    it("returns null for invalid input", () => {
      expect(formatCapturedAgo("not-a-date")).toBeNull();
    });

    it("treats EXIF-style local timestamps without timezone as local time", () => {
      const parsed = new Date("2026-06-30T19:46:05");
      expect(parsed.getHours()).toBe(19);
      expect(parsed.getMinutes()).toBe(46);
    });
  });
});

describe("formatCapturedAt (absolute tooltip)", () => {
  it("shows full local date and time for hover title", () => {
    const label = formatCapturedAt("2026-06-30T19:46:05");
    expect(label).toMatch(/2026/);
    expect(label).toMatch(/Jun/);
    expect(label).toMatch(/30/);
  });
});
