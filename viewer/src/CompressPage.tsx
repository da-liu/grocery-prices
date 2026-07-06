import { useCallback, useEffect, useRef, useState } from "react";
import {
  compressImageFile,
  downloadCompressedResult,
  formatDuration,
  formatEncodeStep,
  formatFileSize,
  revokeCompressResult,
  type CompressEncodeStep,
  type CompressImageResult,
} from "./compressImage";

function CompressPhotoCard({ result }: { result: CompressImageResult }) {
  const statusLabel = result.error
    ? "Error"
    : result.compressed
      ? "Compressed"
      : "No change needed";

  return (
    <article className="metadata-photo-card compress-photo-card">
      <header className="metadata-photo-card-header">
        {result.thumbnailUrl ? (
          <img
            src={result.thumbnailUrl}
            alt=""
            className="metadata-photo-thumb"
            loading="lazy"
          />
        ) : (
          <div className="metadata-photo-thumb metadata-photo-thumb--placeholder" aria-hidden="true">
            IMG
          </div>
        )}
        <div className="metadata-photo-meta">
          <h2>{result.fileName}</h2>
          <p>
            {formatFileSize(result.originalSize)}
            {result.compressed && (
              <>
                {" "}
                → {formatFileSize(result.compressedSize)}
              </>
            )}
          </p>
          <p className={`compress-status compress-status--${result.error ? "error" : result.compressed ? "done" : "skip"}`}>
            {statusLabel} · {formatDuration(result.durationMs)}
          </p>
        </div>
        <button
          type="button"
          className="compress-download-btn"
          disabled={Boolean(result.error)}
          onClick={() => downloadCompressedResult(result)}
        >
          Download
        </button>
      </header>

      {result.error && <p className="status error">{result.error}</p>}

      {result.encodeSteps.length > 0 && (
        <details className="compress-encode-log">
          <summary>
            {result.encodeSteps.length} encode {result.encodeSteps.length === 1 ? "step" : "steps"}
          </summary>
          <ol className="compress-encode-log-list">
            {result.encodeSteps.map((step, index) => (
              <li key={`${step.pass}-${step.iteration}-${index}`}>{formatEncodeStep(step)}</li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}

export function CompressPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [photos, setPhotos] = useState<CompressImageResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<{ completed: number; total: number; fileName: string } | null>(
    null,
  );
  const [elapsedMs, setElapsedMs] = useState(0);
  const [batchDurationMs, setBatchDurationMs] = useState<number | null>(null);
  const [liveEncodeStep, setLiveEncodeStep] = useState<CompressEncodeStep | null>(null);
  const [error, setError] = useState<string | null>(null);
  const batchStartedRef = useRef<number | null>(null);

  const revokeAll = useCallback((rows: CompressImageResult[]) => {
    for (const row of rows) {
      revokeCompressResult(row);
    }
  }, []);

  useEffect(() => {
    return () => revokeAll(photos);
  }, [photos, revokeAll]);

  useEffect(() => {
    if (!loading) return;

    const tick = () => {
      if (batchStartedRef.current != null) {
        setElapsedMs(Math.round(performance.now() - batchStartedRef.current));
      }
    };

    tick();
    const intervalId = window.setInterval(tick, 100);
    return () => window.clearInterval(intervalId);
  }, [loading]);

  async function handleFiles(files: FileList | null | undefined) {
    if (!files?.length) return;

    setLoading(true);
    setError(null);
    setBatchDurationMs(null);
    setLiveEncodeStep(null);
    batchStartedRef.current = performance.now();
    setElapsedMs(0);

    const selected = Array.from(files);
    setProgress({ completed: 0, total: selected.length, fileName: selected[0]?.name ?? "" });
    try {
      const results: CompressImageResult[] = [];
      for (let index = 0; index < selected.length; index++) {
        const file = selected[index]!;
        setProgress({ completed: index, total: selected.length, fileName: file.name });
        setLiveEncodeStep(null);
        results.push(
          await compressImageFile(file, {
            onEncodeStep: (step) => setLiveEncodeStep(step),
          }),
        );
      }
      const totalMs =
        batchStartedRef.current != null
          ? Math.round(performance.now() - batchStartedRef.current)
          : results.reduce((sum, result) => sum + result.durationMs, 0);
      setBatchDurationMs(totalMs);
      setPhotos((current) => {
        revokeAll(current);
        return results;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not compress photos");
    } finally {
      setLoading(false);
      setProgress(null);
      setLiveEncodeStep(null);
      batchStartedRef.current = null;
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function clearPhotos() {
    setPhotos((current) => {
      revokeAll(current);
      return [];
    });
    setBatchDurationMs(null);
    setError(null);
  }

  function downloadAll() {
    for (const result of photos) {
      if (!result.error) {
        downloadCompressedResult(result);
      }
    }
  }

  const compressedCount = photos.filter((photo) => photo.compressed).length;
  const progressPercent =
    progress && progress.total > 0
      ? Math.round(((progress.completed + 1) / progress.total) * 100)
      : 0;

  return (
    <section className="panel metadata-page compress-page">
      <div className="panel-header">
        <div>
          <h1>Compress</h1>
          <p className="subtitle">
            Upload photos to re-encode any image larger than 450 KB to WebP at roughly 450 KB.
          </p>
        </div>
        {photos.length > 0 && (
          <div className="compress-header-actions">
            {compressedCount > 0 && (
              <button type="button" className="ghost" onClick={downloadAll}>
                Download all
              </button>
            )}
            <button type="button" className="ghost" onClick={clearPhotos}>
              Clear
            </button>
          </div>
        )}
      </div>

      <div
        className="metadata-dropzone"
        onDragOver={(event) => {
          event.preventDefault();
        }}
        onDrop={(event) => {
          event.preventDefault();
          void handleFiles(event.dataTransfer.files);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <p>Drop photos here or</p>
        <button
          type="button"
          className="metadata-upload-btn"
          disabled={loading}
          onClick={() => inputRef.current?.click()}
        >
          {loading ? "Compressing…" : "Choose photos"}
        </button>
      </div>

      {loading && progress && (
        <div className="compress-progress">
          <p className="compress-progress-label">
            Compressing {Math.min(progress.completed + 1, progress.total)} of {progress.total}
            {progress.fileName ? `: ${progress.fileName}` : ""}
            {" · "}
            {formatDuration(elapsedMs)}
          </p>
          <div
            className="upload-status-progress compress-progress-bar"
            role="progressbar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Compression progress"
          >
            <div
              className="upload-status-progress-bar"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          {liveEncodeStep && (
            <p className="compress-live-step">{formatEncodeStep(liveEncodeStep)}</p>
          )}
        </div>
      )}

      {error && <p className="status error">{error}</p>}

      {batchDurationMs != null && photos.length > 0 && (
        <p className="compress-batch-timing">
          Processed {photos.length} {photos.length === 1 ? "photo" : "photos"} in{" "}
          {formatDuration(batchDurationMs)}
        </p>
      )}

      {photos.length > 0 && (
        <div className="metadata-photo-list">
          {photos.map((result) => (
            <CompressPhotoCard key={result.id} result={result} />
          ))}
        </div>
      )}
    </section>
  );
}
