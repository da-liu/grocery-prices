import { describe, expect, it } from "vitest";
import { getBrowserCurrency } from "./getBrowserCurrency";

describe("getBrowserCurrency", () => {
  it("returns CAD for en-CA", () => {
    expect(getBrowserCurrency("en-CA")).toBe("CAD");
  });

  it("returns USD for en-US", () => {
    expect(getBrowserCurrency("en-US")).toBe("USD");
  });

  it("returns GBP for en-GB", () => {
    expect(getBrowserCurrency("en-GB")).toBe("GBP");
  });

  it("returns TWD for zh-Hant-TW", () => {
    expect(getBrowserCurrency("zh-Hant-TW")).toBe("TWD");
  });

  it("falls back to USD for unmapped region", () => {
    expect(getBrowserCurrency("en-XX")).toBe("USD");
  });

  it("falls back to USD for invalid locale tag", () => {
    expect(getBrowserCurrency("invalid")).toBe("USD");
  });
});
