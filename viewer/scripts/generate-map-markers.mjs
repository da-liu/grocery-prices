/**
 * Generates the compact ring-dot PNG for store list map previews.
 * Run: npm run generate:markers
 */
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../public/markers");

const ACCENT = { fill: "#2563eb", name: "accent" };

function ringDotSmSvg(fill) {
  // Google Static Maps with scale=2 rejects icons below ~24px and falls back to the default pin.
  const size = 24;
  const center = size / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${center}" cy="${center}" r="${center - 1}" fill="#ffffff" stroke="${fill}" stroke-width="1.5"/>
    <circle cx="${center}" cy="${center}" r="${size * 0.175}" fill="${fill}"/>
  </svg>`;
}

await mkdir(outDir, { recursive: true });

const filename = `ring-dot-list-test24.png`;
const png = await sharp(Buffer.from(ringDotSmSvg(ACCENT.fill))).png().toBuffer();
await writeFile(path.join(outDir, filename), png);
console.log(`Wrote ${filename}`);
