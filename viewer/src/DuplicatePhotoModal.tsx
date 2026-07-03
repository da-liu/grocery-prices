import type { DuplicateAction } from "./api";

interface DuplicatePhotoModalProps {
  duplicateOf: string;
  fileName: string;
  thumbnailUrl: string;
  onChoose: (action: DuplicateAction) => void;
}

export function DuplicatePhotoModal({
  duplicateOf,
  fileName,
  thumbnailUrl,
  onChoose,
}: DuplicatePhotoModalProps) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal duplicate-modal" role="dialog" aria-labelledby="duplicate-title">
        <header className="modal-header">
          <h2 id="duplicate-title">Duplicate photo detected</h2>
          <p className="subtitle">
            This photo matches <strong>{duplicateOf}</strong> already in your catalog.
          </p>
        </header>

        <div className="duplicate-preview">
          {thumbnailUrl ? (
            <img src={thumbnailUrl} alt="" />
          ) : (
            <div className="duplicate-preview-placeholder" aria-hidden="true" />
          )}
          <span>{fileName}</span>
        </div>

        <div className="duplicate-actions">
          <button type="button" className="duplicate-action" onClick={() => onChoose("skip")}>
            Skip upload
          </button>
          <button type="button" className="duplicate-action" onClick={() => onChoose("replace")}>
            Replace {duplicateOf}
          </button>
          <button type="button" className="duplicate-action primary" onClick={() => onChoose("new")}>
            Upload as new photo
          </button>
        </div>
      </div>
    </div>
  );
}
