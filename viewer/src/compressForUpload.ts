import { isHeicFile } from "./isHeic";
import { loadLibheif, type HeifImage } from "./loadLibheif";

export const UPLOAD_MAX_DIM = 1920;
export const UPLOAD_WEBP_QUALITY = 0.8;
export const THUMB_MAX_DIM = 256;

export function scaledDimensions(
  width: number,
  height: number,
  maxDim: number,
): { width: number; height: number } {
  const scale = Math.min(1, maxDim / Math.max(width, height));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

function displayHeifImage(image: HeifImage): Promise<HTMLCanvasElement> {
  const w = image.get_width();
  const h = image.get_height();
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas not available");

  const imageData = ctx.createImageData(w, h);
  for (let i = 0; i < w * h; i++) {
    imageData.data[i * 4 + 3] = 255;
  }

  return new Promise((resolve, reject) => {
    image.display(imageData, (displayData) => {
      if (!displayData) {
        reject(new Error("HEIF display failed"));
        return;
      }
      ctx.putImageData(displayData, 0, 0);
      resolve(canvas);
    });
  });
}

async function decodeHeicToCanvas(file: File): Promise<HTMLCanvasElement> {
  const libheif = await loadLibheif();
  const buffer = await file.arrayBuffer();
  const decoder = new libheif.HeifDecoder();
  const images = decoder.decode(buffer);
  if (!images.length) {
    throw new Error("No images in HEIF file");
  }
  return displayHeifImage(images[0]);
}

async function decodeImageToCanvas(file: File): Promise<HTMLCanvasElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Failed to load image"));
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas not available");
    ctx.drawImage(img, 0, 0);
    return canvas;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function decodeToCanvas(file: File): Promise<HTMLCanvasElement> {
  if (await isHeicFile(file)) {
    return decodeHeicToCanvas(file);
  }
  return decodeImageToCanvas(file);
}

export function resizeCanvas(source: HTMLCanvasElement, maxDim: number): HTMLCanvasElement {
  const { width, height } = scaledDimensions(source.width, source.height, maxDim);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas not available");
  ctx.drawImage(source, 0, 0, width, height);
  return canvas;
}

export function canvasToWebp(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("canvas.toBlob failed"))),
      "image/webp",
      quality,
    );
  });
}

export function uploadFileName(originalName: string): string {
  const stem = originalName.replace(/\.[^/.]+$/, "") || "photo";
  return `${stem}.webp`;
}

export async function prepareUploadFile(
  file: File,
): Promise<{ uploadFile: File; thumbnailUrl: string }> {
  const source = await decodeToCanvas(file);
  const uploadCanvas = resizeCanvas(source, UPLOAD_MAX_DIM);
  const thumbCanvas = resizeCanvas(source, THUMB_MAX_DIM);

  const [uploadBlob, thumbBlob] = await Promise.all([
    canvasToWebp(uploadCanvas, UPLOAD_WEBP_QUALITY),
    canvasToWebp(thumbCanvas, UPLOAD_WEBP_QUALITY),
  ]);

  const uploadFile = new File([uploadBlob], uploadFileName(file.name), {
    type: "image/webp",
  });
  const thumbnailUrl = URL.createObjectURL(thumbBlob);
  return { uploadFile, thumbnailUrl };
}
