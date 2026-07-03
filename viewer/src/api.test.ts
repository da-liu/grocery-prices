import { describe, expect, it } from "vitest";
import { describeRequestError } from "./api";

describe("describeRequestError", () => {
  it("keeps non-network error messages unchanged", () => {
    expect(describeRequestError(new Error("503 from backend"), "status", "https://api.example.com")).toBe(
      "503 from backend",
    );
  });

  it("formats upload fetch failures clearly", () => {
    expect(describeRequestError(new Error("Failed to fetch"), "upload", "https://api.example.com")).toBe(
      "Could not reach API at https://api.example.com. Check network or try again.",
    );
  });

  it("formats status polling fetch failures with recovery hint", () => {
    expect(describeRequestError(new Error("Load failed"), "status", "https://api.example.com")).toBe(
      "Lost connection while checking upload progress at https://api.example.com. Your photo may still finish processing; refresh in a moment.",
    );
  });
});
