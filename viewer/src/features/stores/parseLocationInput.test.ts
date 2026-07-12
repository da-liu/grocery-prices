import { describe, expect, it } from "vitest";
import { canCreateStoreFromDraft, parseLocationInput } from "./parseLocationInput";

describe("parseLocationInput", () => {
  it("parses plain lat, lon", () => {
    expect(parseLocationInput("43.65, -79.38")).toEqual({
      latitude: 43.65,
      longitude: -79.38,
    });
  });

  it("parses Google Maps @lat,lon URLs", () => {
    expect(
      parseLocationInput("https://www.google.com/maps/@43.63943,-79.38029,17z"),
    ).toEqual({
      latitude: 43.63943,
      longitude: -79.38029,
    });
  });

  it("parses ?q=lat,lon", () => {
    expect(parseLocationInput("https://maps.google.com/?q=43.65,-79.38")).toEqual({
      latitude: 43.65,
      longitude: -79.38,
    });
  });

  it("parses place URLs with @ coordinates", () => {
    expect(
      parseLocationInput(
        "https://www.google.com/maps/place/Loblaws/@43.6487,-79.3817,17z/data=!3m1!4b1",
      ),
    ).toEqual({
      latitude: 43.6487,
      longitude: -79.3817,
    });
  });

  it("parses !3d!4d data coordinates", () => {
    expect(
      parseLocationInput(
        "https://www.google.com/maps/place/Store/data=!3d43.641!4d-79.377",
      ),
    ).toEqual({
      latitude: 43.641,
      longitude: -79.377,
    });
  });

  it("rejects invalid or empty input", () => {
    expect(parseLocationInput("")).toBeNull();
    expect(parseLocationInput("not a location")).toBeNull();
    expect(parseLocationInput("91, 0")).toBeNull();
    expect(parseLocationInput("0, 200")).toBeNull();
  });
});

describe("canCreateStoreFromDraft", () => {
  it("requires name and valid coordinates", () => {
    expect(
      canCreateStoreFromDraft({ name: "Loblaws", latitude: 43.65, longitude: -79.38 }),
    ).toBe(true);
    expect(
      canCreateStoreFromDraft({ name: "  ", latitude: 43.65, longitude: -79.38 }),
    ).toBe(false);
    expect(
      canCreateStoreFromDraft({ name: "Loblaws", latitude: null, longitude: -79.38 }),
    ).toBe(false);
    expect(
      canCreateStoreFromDraft({ name: "Loblaws", latitude: 43.65, longitude: null }),
    ).toBe(false);
  });
});
