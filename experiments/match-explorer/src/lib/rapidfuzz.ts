import * as fuzz from "fuzzball";

/** RapidFuzz WRatio normalized to [0, 1]. */
export function wratioScore(a: string, b: string): number {
  return fuzz.WRatio(a, b) / 100;
}
