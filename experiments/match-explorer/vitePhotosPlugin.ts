import fs from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Connect } from "vite";
import type { Plugin } from "vite";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));
const DATA_ROOT = path.join(REPO_ROOT, "data");
const PREVIEW_ROOT = path.join(REPO_ROOT, ".tmp-jpg");

const MIME_TYPES: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".png": "image/png",
};

function resolvePhotoPath(rel: string): string | null {
  const previewPath = path.resolve(PREVIEW_ROOT, rel);
  if (previewPath.startsWith(PREVIEW_ROOT) && fs.existsSync(previewPath) && fs.statSync(previewPath).isFile()) {
    return previewPath;
  }

  const dataPath = path.resolve(DATA_ROOT, rel);
  if (dataPath.startsWith(DATA_ROOT) && fs.existsSync(dataPath) && fs.statSync(dataPath).isFile()) {
    return dataPath;
  }

  return null;
}

function servePhotosMiddleware(
  req: IncomingMessage,
  res: ServerResponse,
  next: Connect.NextFunction,
) {
  const urlPath = req.url?.split("?")[0] ?? "";
  const rel = decodeURIComponent(urlPath.replace(/^\/+/, ""));

  if (!rel || rel.includes("..")) {
    res.statusCode = 400;
    res.end("Bad path");
    return;
  }

  const filePath = resolvePhotoPath(rel);
  if (!filePath) {
    res.statusCode = 404;
    res.end("Not found");
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  res.setHeader("Content-Type", MIME_TYPES[ext] ?? "application/octet-stream");
  res.setHeader("Cache-Control", "public, max-age=3600");
  fs.createReadStream(filePath).pipe(res);
}

export function serveDataPhotos(): Plugin {
  return {
    name: "serve-data-photos",
    configureServer(server) {
      server.middlewares.use("/photos", servePhotosMiddleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use("/photos", servePhotosMiddleware);
    },
  };
}
