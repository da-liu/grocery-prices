import { useMemo, useState } from "react";
import type { Manifest, MatchDetail, PhotoRecord, ProductRecord, RankedMatch, ScorerId } from "@/lib/types";
import { formatScore, scorePairDetail, tierLabel, toSighting } from "@/lib/matching";
import { JsonPanel } from "@/components/JsonPanel";
import { MatchStepsPanel } from "@/components/MatchStepsPanel";
import { OpenImageLink, photoImageUrl } from "@/components/OpenImageLink";
import { ProductPicker } from "@/components/ProductPicker";
import "./App.css";

interface AppProps {
  manifest: Manifest;
}

type ViewMode = "matches" | "pairwise";

export default function App({ manifest }: AppProps) {
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(manifest.photos[0]?.id ?? null);
  const [sourceProductId, setSourceProductId] = useState<string | null>(manifest.products[0]?.id ?? null);
  const [compareTargetId, setCompareTargetId] = useState<string | null>(null);
  const [expandedMatchId, setExpandedMatchId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("matches");
  const [excludeSamePhoto, setExcludeSamePhoto] = useState(false);
  const [scorerMode, setScorerMode] = useState<ScorerId>(
    manifest.config.default_scorer ?? "production",
  );
  const [query, setQuery] = useState("");

  const activeScorer = manifest.config.scorers?.[scorerMode];

  const photosById = useMemo(() => {
    const map = new Map<string, PhotoRecord>();
    for (const photo of manifest.photos) {
      map.set(photo.id, photo);
    }
    return map;
  }, [manifest.photos]);

  const productsByPhoto = useMemo(() => {
    const map = new Map<string, ProductRecord[]>();
    for (const product of manifest.products) {
      const list = map.get(product.photo_id) ?? [];
      list.push(product);
      map.set(product.photo_id, list);
    }
    return map;
  }, [manifest.products]);

  const selectedPhoto = manifest.photos.find((p) => p.id === selectedPhotoId) ?? null;
  const sourceProduct = manifest.products.find((p) => p.id === sourceProductId) ?? null;

  const allMatches = useMemo(() => {
    if (!sourceProduct) return [] as RankedMatch[];
    const source = toSighting(sourceProduct);
    const ranked: RankedMatch[] = [];

    for (const target of manifest.products) {
      const detail = scorePairDetail(
        source,
        toSighting(target),
        sourceProduct.embedding,
        target.embedding,
        manifest.config.min_score,
        { excludeSamePhoto, scorerMode },
      );
      if (excludeSamePhoto && detail.skipped) continue;
      ranked.push({ target, detail });
    }

    ranked.sort((a, b) => {
      if (b.detail.final_score !== a.detail.final_score) {
        return b.detail.final_score - a.detail.final_score;
      }
      return a.target.product_name.localeCompare(b.target.product_name);
    });
    return ranked;
  }, [excludeSamePhoto, manifest.config.min_score, manifest.products, scorerMode, sourceProduct]);

  const filteredMatches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allMatches;
    return allMatches.filter(({ target, detail }) => {
      const haystack = [
        target.product_name,
        target.image_id,
        target.barcode ?? "",
        tierLabel(detail.tier),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [allMatches, query]);

  const pairwiseDetail = useMemo((): MatchDetail | null => {
    if (!sourceProduct || !compareTargetId) return null;
    const target = manifest.products.find((p) => p.id === compareTargetId);
    if (!target) return null;
    return scorePairDetail(
      toSighting(sourceProduct),
      toSighting(target),
      sourceProduct.embedding,
      target.embedding,
      manifest.config.min_score,
      { excludeSamePhoto, scorerMode },
    );
  }, [compareTargetId, excludeSamePhoto, manifest.config.min_score, manifest.products, scorerMode, sourceProduct]);

  const aboveThresholdCount = allMatches.filter((m) => m.detail.above_threshold).length;

  function selectSourceProduct(id: string | null) {
    setSourceProductId(id);
    setExpandedMatchId(null);
    if (id) setViewMode("matches");
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Match Explorer</h1>
          <p className="subtitle">
            {manifest.stats.photo_count} photos · {manifest.stats.product_count} products ·{" "}
            {manifest.stats.with_embedding} with embeddings · min score {manifest.config.min_score}
            {activeScorer ? ` · ${activeScorer.formula}` : ""}
          </p>
          {activeScorer?.experiment && (
            <p className="experiment-metrics">
              Labeled-pair experiment: F1 {activeScorer.experiment.best_f1.toFixed(3)} · AUC{" "}
              {activeScorer.experiment.auc.toFixed(3)} · best threshold{" "}
              {activeScorer.experiment.best_threshold.toFixed(3)}
            </p>
          )}
        </div>
        <div className="header-actions">
          <label className="scorer-select">
            <span>Scorer</span>
            <select value={scorerMode} onChange={(e) => setScorerMode(e.target.value as ScorerId)}>
              {Object.values(manifest.config.scorers ?? {}).map((scorer) => (
                <option key={scorer.id} value={scorer.id}>
                  {scorer.label}
                </option>
              ))}
            </select>
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={excludeSamePhoto}
              onChange={(e) => setExcludeSamePhoto(e.target.checked)}
            />
            Exclude same-photo pairs (production behavior)
          </label>
          <div className="view-toggle">
            <button
              type="button"
              className={viewMode === "matches" ? "active" : ""}
              onClick={() => setViewMode("matches")}
            >
              All matches
            </button>
            <button
              type="button"
              className={viewMode === "pairwise" ? "active" : ""}
              onClick={() => setViewMode("pairwise")}
            >
              Compare two
            </button>
          </div>
        </div>
      </header>

      <div className="layout">
        <aside className="panel photos-panel">
          <h2>Photos</h2>
          <ul className="photo-list">
            {manifest.photos.map((photo) => (
              <li key={photo.id}>
                <div className={`photo-list-item${photo.id === selectedPhotoId ? " selected" : ""}`}>
                  <button
                    type="button"
                    className="photo-select"
                    onClick={() => setSelectedPhotoId(photo.id)}
                  >
                    <span className="photo-id">{photo.image_id}</span>
                    <span className="photo-meta">
                      {photo.date_folder} · {photo.product_count} products
                    </span>
                  </button>
                  <OpenImageLink
                    href={photoImageUrl(photo)}
                    label={photo.image_id}
                  />
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <section className="panel extraction-panel">
          <h2>Extraction JSON</h2>
          {selectedPhoto ? (
            <PhotoExtractionView
              photo={selectedPhoto}
              products={productsByPhoto.get(selectedPhoto.id) ?? []}
              selectedProductId={sourceProductId}
              onSelectProduct={selectSourceProduct}
            />
          ) : (
            <p className="empty">Select a photo</p>
          )}
        </section>

        <section className="panel match-panel">
          <h2>Product matching</h2>
          <ProductPicker
            products={manifest.products}
            sourceId={sourceProductId}
            onSourceChange={selectSourceProduct}
          />

          {sourceProduct && viewMode === "matches" && (
            <>
              <div className="match-toolbar">
                <input
                  type="search"
                  placeholder="Filter matches…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <span className="match-summary">
                  {filteredMatches.length} pairs · {aboveThresholdCount} above threshold
                </span>
              </div>
              <div className="match-table-wrap">
                <table className="match-table">
                  <thead>
                    <tr>
                      <th>Target product</th>
                      <th>Photo</th>
                      <th>Score</th>
                      <th>Path</th>
                      <th>Threshold</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredMatches.map(({ target, detail }) => {
                      const rowKey = target.id;
                      const expanded = expandedMatchId === rowKey;
                      return (
                        <MatchRow
                          key={rowKey}
                          target={target}
                          targetPhoto={photosById.get(target.photo_id) ?? null}
                          detail={detail}
                          expanded={expanded}
                          onToggle={() => setExpandedMatchId(expanded ? null : rowKey)}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {sourceProduct && viewMode === "pairwise" && (
            <div className="pairwise">
              <ProductPicker
                label="Compare with"
                products={manifest.products.filter((p) => p.id !== sourceProduct.id)}
                sourceId={compareTargetId}
                onSourceChange={setCompareTargetId}
              />
              {pairwiseDetail && compareTargetId && (
                <MatchStepsPanel
                  detail={pairwiseDetail}
                  source={sourceProduct}
                  target={manifest.products.find((p) => p.id === compareTargetId)!}
                />
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function PhotoExtractionView({
  photo,
  products,
  selectedProductId,
  onSelectProduct,
}: {
  photo: PhotoRecord;
  products: ProductRecord[];
  selectedProductId: string | null;
  onSelectProduct: (id: string) => void;
}) {
  return (
    <div className="extraction-view">
      <div className="extraction-meta">
        <dl>
          <dt>Image</dt>
          <dd className="image-id-row">
            {photo.image_id}
            <OpenImageLink href={photoImageUrl(photo)} label={photo.image_id} />
          </dd>
          <dt>Date folder</dt>
          <dd>{photo.date_folder}</dd>
          <dt>Source file</dt>
          <dd>{photo.path}</dd>
          <dt>Products in photo</dt>
          <dd>{products.length}</dd>
        </dl>
        <ul className="product-chips">
          {products.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={`product-chip${p.id === selectedProductId ? " selected" : ""}`}
                onClick={() => onSelectProduct(p.id)}
                title="Select for product matching"
              >
                <span>{p.product_name}</span>
                {p.barcode && <code>{p.barcode}</code>}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <JsonPanel value={photo.extraction} />
    </div>
  );
}

function MatchRow({
  target,
  targetPhoto,
  detail,
  expanded,
  onToggle,
}: {
  target: ProductRecord;
  targetPhoto: PhotoRecord | null;
  detail: MatchDetail;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className={detail.skipped ? "skipped" : detail.above_threshold ? "above" : ""}>
        <td>
          <button type="button" className="row-toggle" onClick={onToggle}>
            {expanded ? "▾" : "▸"} {target.product_name}
          </button>
        </td>
        <td>
          <span className="photo-cell">
            {target.image_id}
            {targetPhoto && (
              <OpenImageLink
                href={photoImageUrl(targetPhoto)}
                label={target.image_id}
              />
            )}
          </span>
        </td>
        <td className="score">{formatScore(detail.final_score)}</td>
        <td>{tierLabel(detail.tier)}</td>
        <td>{detail.above_threshold ? "pass" : detail.skipped ? "skip" : "below"}</td>
      </tr>
      {expanded && (
        <tr className="steps-row">
          <td colSpan={5}>
            <MatchStepsPanel detail={detail} />
          </td>
        </tr>
      )}
    </>
  );
}
