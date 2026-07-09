import type { MatchDetail, MatchSighting, MatchStep, MatchTier, ScorerId } from "./types";
import { wratioScore } from "./rapidfuzz";

const STOP_TOKENS = new Set([
  "with", "and", "the", "a", "an", "of", "for", "in", "on", "w", "ea", "pkg", "pack",
  "value", "fresh", "food", "foods", "mart", "label", "superior", "bridge",
]);

const GENERIC_PRODUCT_TOKENS = new Set([
  "rice", "ball", "balls", "pork", "soy", "sauce", "milk", "egg", "eggs", "tofu",
  "chips", "tomato", "tomatoes", "pasta", "frozen", "fresh", "boneless", "whole",
  "thyme", "herb", "herbs", "spice", "spices",
]);

const EMB_RAPIDFUZZ_EMB_WEIGHT = 0.6;
const EMB_RAPIDFUZZ_RF_WEIGHT = 0.4;
const PRODUCTION_EMB_WEIGHT = 0.75;
const PRODUCTION_TOK_WEIGHT = 0.25;

export interface ScorePairOptions {
  excludeSamePhoto?: boolean;
  scorerMode?: ScorerId;
}

export function normalizeName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

function tokenize(name: string): string[] {
  return normalizeName(name)
    .split(" ")
    .filter((t) => t && !STOP_TOKENS.has(t));
}

function tokenJaccard(a: string, b: string, ignoreGeneric = false): number {
  const ta = new Set(
    tokenize(a).filter((t) => !(ignoreGeneric && GENERIC_PRODUCT_TOKENS.has(t))),
  );
  const tb = new Set(
    tokenize(b).filter((t) => !(ignoreGeneric && GENERIC_PRODUCT_TOKENS.has(t))),
  );
  if (ta.size === 0 || tb.size === 0) return 0;
  let intersection = 0;
  for (const t of ta) {
    if (tb.has(t)) intersection += 1;
  }
  const union = ta.size + tb.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i += 1) {
    dot += a[i]! * b[i]!;
    normA += a[i]! * a[i]!;
    normB += b[i]! * b[i]!;
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

function embeddingScore(vectorA: number[] | null | undefined, vectorB: number[] | null | undefined): number {
  if (!vectorA || !vectorB) return 0;
  return (cosineSimilarity(vectorA, vectorB) + 1) / 2;
}

function round(n: number, digits = 4): number {
  const factor = 10 ** digits;
  return Math.round(n * factor) / factor;
}

function finalizeResult(
  source: MatchSighting,
  target: MatchSighting,
  final: number,
  tier: MatchTier,
  steps: MatchStep[],
  minScore: number,
  samePhoto: boolean,
  excludeSamePhoto: boolean,
): MatchDetail {
  const skipped = samePhoto && excludeSamePhoto;
  return {
    source_id: source.id,
    target_id: target.id,
    final_score: final,
    tier,
    skipped,
    skip_reason: skipped ? "Same photo (excluded in production related search)" : undefined,
    above_threshold: !skipped && final >= minScore,
    steps,
  };
}

export function scorePairDetail(
  source: MatchSighting,
  target: MatchSighting,
  vectorA: number[] | null | undefined,
  vectorB: number[] | null | undefined,
  minScore: number,
  options: ScorePairOptions = {},
): MatchDetail {
  const excludeSamePhoto = options.excludeSamePhoto ?? true;
  const scorerMode = options.scorerMode ?? "production";
  const steps: MatchStep[] = [];
  const samePhoto = source.photo_id === target.photo_id;

  if (source.id === target.id) {
    return {
      source_id: source.id,
      target_id: target.id,
      final_score: 0,
      tier: "skipped",
      skipped: true,
      skip_reason: "Same product",
      above_threshold: false,
      steps: [{ id: "skip", label: "Skipped", value: "self" }],
    };
  }

  if (samePhoto) {
    steps.push({
      id: "same_photo",
      label: "Same photo",
      value: true,
      note: excludeSamePhoto
        ? "Production matcher excludes co-photo products from related search"
        : "Included for full pairwise matrix",
    });
  }

  steps.push(
    { id: "source_name", label: "Source name", value: source.product_name },
    { id: "target_name", label: "Target name", value: target.product_name },
    { id: "source_barcode", label: "Source barcode", value: source.barcode ?? null },
    { id: "target_barcode", label: "Target barcode", value: target.barcode ?? null },
  );

  if (source.barcode && target.barcode && source.barcode === target.barcode) {
    steps.push({ id: "path", label: "Match path", value: "barcode" });
    return finalizeResult(source, target, 1.0, "barcode", steps, minScore, samePhoto, excludeSamePhoto);
  }

  const normA = normalizeName(source.product_name);
  const normB = normalizeName(target.product_name);
  steps.push(
    { id: "normalized_source", label: "Normalized source", value: normA },
    { id: "normalized_target", label: "Normalized target", value: normB },
  );

  if (normA === normB) {
    steps.push({ id: "path", label: "Match path", value: "exact_name" });
    return finalizeResult(source, target, 1.0, "exact_name", steps, minScore, samePhoto, excludeSamePhoto);
  }

  const compositeTier: MatchTier =
    scorerMode === "emb_rapidfuzz" ? "composite_emb_rapidfuzz" : "composite_embedding";
  steps.push({ id: "scorer_mode", label: "Scorer", value: scorerMode });
  steps.push({ id: "path", label: "Match path", value: compositeTier });

  const rawCosine = vectorA && vectorB ? cosineSimilarity(vectorA, vectorB) : null;
  const emb = embeddingScore(vectorA, vectorB);

  let composite: number;
  if (scorerMode === "emb_rapidfuzz") {
    const rapidfuzz = wratioScore(source.product_name, target.product_name);
    composite = EMB_RAPIDFUZZ_EMB_WEIGHT * emb + EMB_RAPIDFUZZ_RF_WEIGHT * rapidfuzz;
    steps.push(
      { id: "embedding_cosine", label: "Embedding cosine similarity", value: rawCosine === null ? null : round(rawCosine) },
      { id: "embedding_score", label: "Embedding score (cosine+1)/2", value: round(emb) },
      { id: "rapidfuzz_wratio", label: "RapidFuzz WRatio", value: round(rapidfuzz) },
      {
        id: "composite_formula",
        label: "Composite formula",
        value: `${EMB_RAPIDFUZZ_EMB_WEIGHT} * emb + ${EMB_RAPIDFUZZ_RF_WEIGHT} * rapidfuzz`,
      },
      { id: "composite_raw", label: "Composite raw", value: round(composite) },
    );
  } else {
    const tok = tokenJaccard(source.product_name, target.product_name, true);
    composite = PRODUCTION_EMB_WEIGHT * emb + PRODUCTION_TOK_WEIGHT * tok;
    steps.push(
      { id: "embedding_cosine", label: "Embedding cosine similarity", value: rawCosine === null ? null : round(rawCosine) },
      { id: "embedding_score", label: "Embedding score (cosine+1)/2", value: round(emb) },
      { id: "token_jaccard", label: "Token Jaccard (ignore generic)", value: round(tok) },
      {
        id: "composite_formula",
        label: "Composite formula",
        value: `${PRODUCTION_EMB_WEIGHT} * emb + ${PRODUCTION_TOK_WEIGHT} * tok`,
      },
      { id: "composite_raw", label: "Composite raw", value: round(composite) },
    );
  }

  steps.push({ id: "final_score", label: "Final score", value: round(composite) });
  return finalizeResult(
    source,
    target,
    composite,
    compositeTier,
    steps,
    minScore,
    samePhoto,
    excludeSamePhoto,
  );
}

export function toSighting(product: {
  id: string;
  photo_id: string;
  product_name: string;
  category: string;
  brand?: string | null;
  barcode?: string | null;
}): MatchSighting {
  return {
    id: product.id,
    photo_id: product.photo_id,
    product_name: product.product_name,
    category: product.category,
    brand: product.brand ?? null,
    barcode: product.barcode ?? null,
  };
}

export function formatScore(score: number): string {
  return score.toFixed(3);
}

export function tierLabel(tier: MatchTier): string {
  switch (tier) {
    case "barcode":
      return "Barcode";
    case "exact_name":
      return "Exact name";
    case "composite_embedding":
      return "Composite + embedding";
    case "composite_emb_rapidfuzz":
      return "Emb 0.6 + RapidFuzz 0.4";
    case "skipped":
      return "Skipped";
    default:
      return tier;
  }
}
