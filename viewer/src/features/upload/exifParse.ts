export interface PhotoMetadata {
  dateTime?: string;
  dateTimeOriginal?: string;
  gpsLatitude?: number;
  gpsLongitude?: number;
}

const TAG_DATETIME = 0x0132;
const TAG_EXIF_IFD = 0x8769;
const TAG_GPS_IFD = 0x8825;
const TAG_DATETIME_ORIGINAL = 0x9003;
const TAG_GPS_LAT_REF = 0x0001;
const TAG_GPS_LAT = 0x0002;
const TAG_GPS_LON_REF = 0x0003;
const TAG_GPS_LON = 0x0004;

const TYPE_ASCII = 2;
const TYPE_LONG = 4;
const TYPE_RATIONAL = 5;

type ByteOrder = "little" | "big";

interface IfdEntry {
  tag: number;
  type: number;
  count: number;
  valueOffset: number;
  entryOffset: number;
}

function readU16(view: DataView, offset: number, order: ByteOrder): number {
  return view.getUint16(offset, order === "little");
}

function readU32(view: DataView, offset: number, order: ByteOrder): number {
  return view.getUint32(offset, order === "little");
}

function readByteOrder(view: DataView, offset: number): ByteOrder | null {
  const b0 = view.getUint8(offset);
  const b1 = view.getUint8(offset + 1);
  if (b0 === 0x49 && b1 === 0x49) return "little";
  if (b0 === 0x4d && b1 === 0x4d) return "big";
  return null;
}

function readIfd(view: DataView, tiffStart: number, ifdOffset: number, order: ByteOrder): Map<number, IfdEntry> {
  const base = tiffStart + ifdOffset;
  const count = readU16(view, base, order);
  const entries = new Map<number, IfdEntry>();
  let pos = base + 2;
  for (let i = 0; i < count; i++) {
    entries.set(readU16(view, pos, order), {
      tag: readU16(view, pos, order),
      type: readU16(view, pos + 2, order),
      count: readU32(view, pos + 4, order),
      valueOffset: readU32(view, pos + 8, order),
      entryOffset: pos,
    });
    pos += 12;
  }
  return entries;
}

function readAscii(view: DataView, offset: number, length: number): string {
  let text = "";
  for (let i = 0; i < length; i++) {
    const code = view.getUint8(offset + i);
    if (code === 0) break;
    text += String.fromCharCode(code);
  }
  return text;
}

function readAsciiTag(
  view: DataView,
  tiffStart: number,
  entry: IfdEntry,
): string | undefined {
  if (entry.type !== TYPE_ASCII || entry.count < 1) return undefined;
  const offset =
    entry.count <= 4 ? entry.entryOffset + 8 : tiffStart + entry.valueOffset;
  return readAscii(view, offset, entry.count);
}

function readULongTag(
  view: DataView,
  tiffStart: number,
  entry: IfdEntry,
  order: ByteOrder,
): number | undefined {
  if (entry.type !== TYPE_LONG || entry.count < 1) return undefined;
  if (entry.count * 4 <= 4) {
    return readU32(view, entry.entryOffset + 8, order);
  }
  return readU32(view, tiffStart + entry.valueOffset, order);
}

function readRationalTag(
  view: DataView,
  tiffStart: number,
  entry: IfdEntry,
  order: ByteOrder,
): number[] {
  if (entry.type !== TYPE_RATIONAL || entry.count < 1) return [];
  const offset = tiffStart + entry.valueOffset;
  const values: number[] = [];
  for (let i = 0; i < entry.count; i++) {
    const num = readU32(view, offset + i * 8, order);
    const den = readU32(view, offset + i * 8 + 4, order);
    values.push(den === 0 ? 0 : num / den);
  }
  return values;
}

function dmsToDecimal(dms: number[], ref: string | undefined): number | undefined {
  if (dms.length < 3) return undefined;
  const decimal = dms[0] + dms[1] / 60 + dms[2] / 3600;
  if (ref === "S" || ref === "W") return -decimal;
  return decimal;
}

function findJpegExifTiffStart(view: DataView): number | null {
  if (view.byteLength < 4 || view.getUint16(0) !== 0xffd8) return null;

  let offset = 2;
  while (offset + 4 < view.byteLength) {
    if (view.getUint8(offset) !== 0xff) break;
    const marker = view.getUint8(offset + 1);
    if (marker === 0xda || marker === 0xd9) break;

    const segmentLength = readU16(view, offset + 2, "big");
    if (segmentLength < 2 || offset + 2 + segmentLength > view.byteLength) break;

    if (marker === 0xe1 && segmentLength >= 8) {
      const header = offset + 4;
      if (
        view.getUint8(header) === 0x45 &&
        view.getUint8(header + 1) === 0x78 &&
        view.getUint8(header + 2) === 0x69 &&
        view.getUint8(header + 3) === 0x66 &&
        view.getUint8(header + 4) === 0 &&
        view.getUint8(header + 5) === 0
      ) {
        return header + 6;
      }
    }

    offset += 2 + segmentLength;
  }

  return null;
}

function isPlausibleTiffStart(view: DataView, offset: number): boolean {
  if (offset + 8 > view.byteLength) return false;
  const order = readByteOrder(view, offset);
  if (!order || readU16(view, offset + 2, order) !== 42) return false;

  const ifdOffset = readU32(view, offset + 4, order);
  if (ifdOffset < 4 || ifdOffset > 64) return false;

  const ifdStart = offset + ifdOffset;
  if (ifdStart + 2 > view.byteLength) return false;

  const entryCount = readU16(view, ifdStart, order);
  return entryCount > 0 && entryCount <= 256;
}

function findTiffStartByMagic(view: DataView): number | null {
  const limit = view.byteLength - 8;
  for (let offset = 0; offset <= limit; offset++) {
    if (isPlausibleTiffStart(view, offset)) return offset;
  }
  return null;
}

function findExifTiffStart(view: DataView): number | null {
  const fromJpeg = findJpegExifTiffStart(view);
  if (fromJpeg != null && isPlausibleTiffStart(view, fromJpeg)) return fromJpeg;
  return findTiffStartByMagic(view);
}

export function parseExifMetadata(buffer: ArrayBuffer): PhotoMetadata {
  const view = new DataView(buffer);
  const tiffStart = findExifTiffStart(view);
  if (tiffStart == null) return {};

  const order = readByteOrder(view, tiffStart);
  if (!order || readU16(view, tiffStart + 2, order) !== 42) return {};

  const metadata: PhotoMetadata = {};
  const ifd0 = readIfd(view, tiffStart, readU32(view, tiffStart + 4, order), order);

  const dateTime = ifd0.get(TAG_DATETIME);
  if (dateTime) metadata.dateTime = readAsciiTag(view, tiffStart, dateTime);

  const exifIfdOffset = ifd0.get(TAG_EXIF_IFD);
  if (exifIfdOffset) {
    const exifIfd = readIfd(view, tiffStart, readULongTag(view, tiffStart, exifIfdOffset, order) ?? 0, order);
    const dateTimeOriginal = exifIfd.get(TAG_DATETIME_ORIGINAL);
    if (dateTimeOriginal) {
      metadata.dateTimeOriginal = readAsciiTag(view, tiffStart, dateTimeOriginal);
    }
  }

  const gpsIfdOffset = ifd0.get(TAG_GPS_IFD);
  if (gpsIfdOffset) {
    const gpsIfd = readIfd(view, tiffStart, readULongTag(view, tiffStart, gpsIfdOffset, order) ?? 0, order);
    const latRef = gpsIfd.get(TAG_GPS_LAT_REF);
    const lat = gpsIfd.get(TAG_GPS_LAT);
    const lonRef = gpsIfd.get(TAG_GPS_LON_REF);
    const lon = gpsIfd.get(TAG_GPS_LON);
    if (lat) metadata.gpsLatitude = dmsToDecimal(readRationalTag(view, tiffStart, lat, order), latRef ? readAsciiTag(view, tiffStart, latRef) : undefined);
    if (lon) metadata.gpsLongitude = dmsToDecimal(readRationalTag(view, tiffStart, lon, order), lonRef ? readAsciiTag(view, tiffStart, lonRef) : undefined);
  }

  return metadata;
}
