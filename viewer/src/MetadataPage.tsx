import { useCallback, useEffect, useRef, useState } from "react";
import {
  extractPhotoMetadata,
  formatMetadataValue,
  hasPhotoMetadata,
  revokePhotoMetadataResult,
  type PhotoMetadataResult,
} from "./extractPhotoMetadata";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const METADATA_FIELDS = [
  { key: "dateTime", label: "DateTime" },
  { key: "dateTimeOriginal", label: "DateTime original" },
  { key: "gpsLatitude", label: "GPS latitude" },
  { key: "gpsLongitude", label: "GPS longitude" },
] as const;

function MetadataPhotoCard({ result }: { result: PhotoMetadataResult }) {
  return (
    <article className="metadata-photo-card">
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
            —
          </div>
        )}
        <div className="metadata-photo-meta">
          <h2>{result.fileName}</h2>
          <p>
            {formatFileSize(result.fileSize)} · {result.fileType || "unknown type"}
          </p>
        </div>
      </header>

      {result.error && <p className="status error">{result.error}</p>}

      {!result.error && !hasPhotoMetadata(result.metadata) && (
        <p className="status">No date or GPS metadata found in this file.</p>
      )}

      {!result.error && hasPhotoMetadata(result.metadata) && (
        <dl className="metadata-fields">
          {METADATA_FIELDS.map(({ key, label }) => (
            <div key={key} className="metadata-field">
              <dt>{label}</dt>
              <dd>{formatMetadataValue(result.metadata[key])}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

export function MetadataPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [photos, setPhotos] = useState<PhotoMetadataResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const revokeAll = useCallback((rows: PhotoMetadataResult[]) => {
    for (const row of rows) {
      revokePhotoMetadataResult(row);
    }
  }, []);

  useEffect(() => {
    return () => revokeAll(photos);
  }, [photos, revokeAll]);

  async function handleFiles(files: FileList | null | undefined) {
    if (!files?.length) return;

    setLoading(true);
    setError(null);

    const selected = Array.from(files);
    try {
      const results = await Promise.all(selected.map((file) => extractPhotoMetadata(file)));
      setPhotos((current) => {
        revokeAll(current);
        return results;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read photo metadata");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function clearPhotos() {
    setPhotos((current) => {
      revokeAll(current);
      return [];
    });
    setError(null);
  }

  return (
    <section className="panel metadata-page">
      <div className="panel-header">
        <div>
          <h1>Metadata</h1>
          <p className="subtitle">Upload a photo to inspect capture time and GPS location.</p>
        </div>
        {photos.length > 0 && (
          <button type="button" className="ghost" onClick={clearPhotos}>
            Clear
          </button>
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
          {loading ? "Reading metadata…" : "Choose photos"}
        </button>
      </div>

      {error && <p className="status error">{error}</p>}

      {photos.length > 0 && (
        <div className="metadata-photo-list">
          {photos.map((result) => (
            <MetadataPhotoCard key={result.id} result={result} />
          ))}
        </div>
      )}
    </section>
  );
}
