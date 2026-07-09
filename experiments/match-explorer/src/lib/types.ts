export type ScorerId = "production" | "emb_rapidfuzz";

export interface ScorerExperimentMetrics {
  best_f1: number;
  best_threshold: number;
  auc: number;
  separation: number;
  f1_at_min_score?: number;
}

export interface ScorerConfig {
  id: ScorerId;
  label: string;
  formula: string;
  experiment?: ScorerExperimentMetrics | null;
}

export interface ManifestConfig {
  min_score: number;
  top_n: number;
  embed_model: string;
  default_scorer: ScorerId;
  scorers: Record<ScorerId, ScorerConfig>;
}

export interface ManifestStats {
  photo_count: number;
  product_count: number;
  with_embedding: number;
}

export interface PhotoRecord {
  id: string;
  image_id: string;
  date_folder: string;
  path: string;
  image_file: string | null;
  meta: Record<string, unknown>;
  extraction: Record<string, unknown>;
  product_count: number;
}

export interface ProductRecord {
  id: string;
  photo_id: string;
  image_id: string;
  date_folder: string;
  extraction_index: number;
  product_name: string;
  category: string;
  brand?: string | null;
  barcode?: string | null;
  price?: number | null;
  embedding?: number[] | null;
}

export interface Manifest {
  generated_at: string;
  config: ManifestConfig;
  stats: ManifestStats;
  photos: PhotoRecord[];
  products: ProductRecord[];
}

export interface MatchSighting {
  id: string;
  photo_id: string;
  product_name: string;
  category: string;
  brand: string | null;
  barcode: string | null;
}

export interface MatchStep {
  id: string;
  label: string;
  value: string | number | boolean | null;
  note?: string;
}

export type MatchTier =
  | "skipped"
  | "barcode"
  | "exact_name"
  | "composite_embedding"
  | "composite_emb_rapidfuzz";

export interface MatchDetail {
  source_id: string;
  target_id: string;
  final_score: number;
  tier: MatchTier;
  skipped: boolean;
  skip_reason?: string;
  above_threshold: boolean;
  steps: MatchStep[];
}

export interface RankedMatch {
  target: ProductRecord;
  detail: MatchDetail;
}
