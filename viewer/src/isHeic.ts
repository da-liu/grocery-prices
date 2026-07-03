export async function isHeicFile(file: File): Promise<boolean> {
  const buffer = await file.arrayBuffer();
  const brand = new TextDecoder("utf-8")
    .decode(buffer.slice(8, 12))
    .replace("\0", " ")
    .trim();
  return ["mif1", "msf1", "heic", "heix", "hevc", "hevx"].includes(brand);
}
