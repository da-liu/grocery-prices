import { useUploadQueue } from "./UploadQueueContext";

export function UploadPage() {
  const { enqueueFiles, activeCount } = useUploadQueue();
  const busy = activeCount > 0;

  function handleCapture(file: File | null, source: "shelf" | "receipt" = "shelf") {
    if (!file) return;
    enqueueFiles([file], source);
  }

  function handleBulk(files: FileList | null) {
    if (!files?.length) return;
    enqueueFiles(Array.from(files), "receipt");
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h1>Capture & upload</h1>
          <p className="subtitle">
            Take an in-store shelf photo or import receipt images. You can queue multiple photos
            while earlier ones are still processing.
          </p>
        </div>
      </div>

      <div className={`upload-actions${busy ? " upload-actions--dimmed" : ""}`}>
        <label className="upload-card">
          <span className="upload-card-title">Shelf photo</span>
          <span className="upload-card-hint">Opens camera on mobile</span>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => {
              handleCapture(e.target.files?.[0] ?? null, "shelf");
              e.target.value = "";
            }}
          />
        </label>

        <label className="upload-card">
          <span className="upload-card-title">Choose photos</span>
          <span className="upload-card-hint">Select one or more · HEIC, JPG, PNG, WebP</span>
          <input
            type="file"
            accept="image/*,.heic"
            multiple
            onChange={(e) => {
              if (e.target.files?.length) enqueueFiles(Array.from(e.target.files), "shelf");
              e.target.value = "";
            }}
          />
        </label>

        <label className="upload-card">
          <span className="upload-card-title">Receipt bulk import</span>
          <span className="upload-card-hint">Select multiple receipt photos</span>
          <input
            type="file"
            accept="image/*,.heic"
            multiple
            onChange={(e) => {
              handleBulk(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
      </div>
    </section>
  );
}
