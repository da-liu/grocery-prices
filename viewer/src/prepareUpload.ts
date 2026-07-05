export type PreparePhase = "ready";

export type PrepareUploadResult = {
  uploadFile: File;
  thumbnailUrl: string;
  skipped: boolean;
};

function canPreviewInBrowser(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase();
  return ext !== "heic" && ext !== "heif";
}

export async function prepareUploadFile(
  file: File,
  onProgress: (phase: PreparePhase) => void,
): Promise<PrepareUploadResult> {
  onProgress("ready");
  return {
    uploadFile: file,
    thumbnailUrl: canPreviewInBrowser(file) ? URL.createObjectURL(file) : "",
    skipped: true,
  };
}
