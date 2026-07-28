/**
 * Minimal, dependency-free .xlsx reader for the intake upload.
 *
 * Reads the first worksheet of an Excel workbook into string[][] using only
 * standard browser APIs (DecompressionStream + DOMParser), so no npm
 * dependency or lockfile change is needed. Handles shared strings, inline
 * strings, booleans, numbers, and date/datetime cells (Excel serials are
 * converted to "YYYY-MM-DD HH:MM:SS" when the cell carries a date format).
 */

const ZIP_EOCD_SIG = 0x06054b50;
const ZIP_CENTRAL_SIG = 0x02014b50;
const ZIP_LOCAL_SIG = 0x04034b50;

interface ZipEntry {
  name: string;
  method: number;
  compressedSize: number;
  localHeaderOffset: number;
}

function readEntries(view: DataView): ZipEntry[] {
  // Locate End-Of-Central-Directory from the tail (max comment 64 KiB).
  let eocd = -1;
  const stop = Math.max(0, view.byteLength - 65558);
  for (let i = view.byteLength - 22; i >= stop; i -= 1) {
    if (view.getUint32(i, true) === ZIP_EOCD_SIG) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) {
    throw new Error("Not a valid .xlsx file (zip directory missing).");
  }

  const count = view.getUint16(eocd + 10, true);
  let offset = view.getUint32(eocd + 16, true);
  const entries: ZipEntry[] = [];
  const decoder = new TextDecoder();

  for (let i = 0; i < count; i += 1) {
    if (view.getUint32(offset, true) !== ZIP_CENTRAL_SIG) {
      break;
    }
    const method = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localHeaderOffset = view.getUint32(offset + 42, true);
    const name = decoder.decode(
      new Uint8Array(view.buffer, view.byteOffset + offset + 46, nameLength),
    );
    entries.push({ name, method, compressedSize, localHeaderOffset });
    offset += 46 + nameLength + extraLength + commentLength;
  }

  return entries;
}

async function readFileFromZip(buffer: ArrayBuffer, entries: ZipEntry[], name: string) {
  const entry = entries.find((candidate) => candidate.name === name);
  if (!entry) {
    return null;
  }

  const view = new DataView(buffer);
  const base = entry.localHeaderOffset;
  if (view.getUint32(base, true) !== ZIP_LOCAL_SIG) {
    throw new Error(`Corrupt .xlsx: bad local header for ${name}.`);
  }
  const nameLength = view.getUint16(base + 26, true);
  const extraLength = view.getUint16(base + 28, true);
  const dataStart = base + 30 + nameLength + extraLength;
  const compressed = new Uint8Array(buffer, dataStart, entry.compressedSize);

  if (entry.method === 0) {
    return new TextDecoder().decode(compressed);
  }
  if (entry.method !== 8) {
    throw new Error(`Unsupported zip compression method ${entry.method} in .xlsx.`);
  }

  const stream = new Blob([compressed])
    .stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  return new Response(stream).text();
}

function parseXml(xml: string): Document {
  return new DOMParser().parseFromString(xml, "application/xml");
}

/** Excel serial (1900 date system) -> "YYYY-MM-DD HH:MM:SS". */
function serialToDateString(serial: number): string {
  const ms = Math.round((serial - 25569) * 86400 * 1000);
  const date = new Date(ms);
  const pad = (value: number) => String(value).padStart(2, "0");
  const ymd = `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
  const hms = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
  return hms === "00:00:00" ? ymd : `${ymd} ${hms}`;
}

const BUILTIN_DATE_FORMATS = new Set([
  14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
  45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58,
]);

function isDateFormatCode(code: string): boolean {
  // Strip quoted literals, [] sections and colors, then look for date tokens.
  const cleaned = code.replace(/"[^"]*"/g, "").replace(/\[[^\]]*\]/g, "");
  return /[dmhys]/i.test(cleaned) && !/#|0\.0|%/.test(cleaned);
}

/** style index -> isDate, from xl/styles.xml. */
function buildDateStyleLookup(stylesXml: string | null): Set<number> {
  const dateStyles = new Set<number>();
  if (!stylesXml) {
    return dateStyles;
  }
  const doc = parseXml(stylesXml);

  const customDateFormats = new Set<number>();
  doc.querySelectorAll("numFmts > numFmt").forEach((node) => {
    const id = Number(node.getAttribute("numFmtId"));
    const code = node.getAttribute("formatCode") ?? "";
    if (Number.isFinite(id) && isDateFormatCode(code)) {
      customDateFormats.add(id);
    }
  });

  doc.querySelectorAll("cellXfs > xf").forEach((node, index) => {
    const numFmtId = Number(node.getAttribute("numFmtId"));
    if (BUILTIN_DATE_FORMATS.has(numFmtId) || customDateFormats.has(numFmtId)) {
      dateStyles.add(index);
    }
  });

  return dateStyles;
}

function buildSharedStrings(sharedXml: string | null): string[] {
  if (!sharedXml) {
    return [];
  }
  const doc = parseXml(sharedXml);
  return Array.from(doc.querySelectorAll("sst > si")).map((si) =>
    Array.from(si.querySelectorAll("t"))
      .map((t) => t.textContent ?? "")
      .join(""),
  );
}

/** "BC42" -> zero-based column index. */
function columnIndexFromRef(ref: string): number {
  let column = 0;
  for (const char of ref) {
    if (char < "A" || char > "Z") {
      break;
    }
    column = column * 26 + (char.charCodeAt(0) - 64);
  }
  return column - 1;
}

function firstSheetPath(entries: ZipEntry[]): string {
  // Prefer the conventional path; fall back to any worksheet present.
  if (entries.some((entry) => entry.name === "xl/worksheets/sheet1.xml")) {
    return "xl/worksheets/sheet1.xml";
  }
  const sheet = entries.find((entry) => /^xl\/worksheets\/sheet\d+\.xml$/.test(entry.name));
  if (!sheet) {
    throw new Error("The workbook contains no worksheets.");
  }
  return sheet.name;
}

export async function parseXlsxToRows(buffer: ArrayBuffer): Promise<string[][]> {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("This browser cannot read .xlsx files - upload a CSV export instead.");
  }

  const entries = readEntries(new DataView(buffer));
  const [sheetXml, sharedXml, stylesXml] = await Promise.all([
    readFileFromZip(buffer, entries, firstSheetPath(entries)),
    readFileFromZip(buffer, entries, "xl/sharedStrings.xml"),
    readFileFromZip(buffer, entries, "xl/styles.xml"),
  ]);
  if (!sheetXml) {
    throw new Error("The workbook contains no worksheet data.");
  }

  const sharedStrings = buildSharedStrings(sharedXml);
  const dateStyles = buildDateStyleLookup(stylesXml);
  const rows: string[][] = [];

  const doc = parseXml(sheetXml);
  doc.querySelectorAll("sheetData > row").forEach((rowNode) => {
    const row: string[] = [];
    rowNode.querySelectorAll("c").forEach((cell) => {
      const ref = cell.getAttribute("r") ?? "";
      const index = ref ? columnIndexFromRef(ref) : row.length;
      const type = cell.getAttribute("t") ?? "n";
      const styleIndex = Number(cell.getAttribute("s") ?? -1);

      let value = "";
      if (type === "inlineStr") {
        value = cell.querySelector("is")?.textContent ?? "";
      } else {
        const raw = cell.querySelector("v")?.textContent ?? "";
        if (type === "s") {
          value = sharedStrings[Number(raw)] ?? "";
        } else if (type === "b") {
          value = raw === "1" ? "TRUE" : "FALSE";
        } else if (type === "str" || type === "e") {
          value = raw;
        } else {
          // Numeric cell: render date-formatted serials as timestamps.
          const numeric = Number(raw);
          value =
            raw !== "" && Number.isFinite(numeric) && dateStyles.has(styleIndex)
              ? serialToDateString(numeric)
              : raw;
        }
      }

      while (row.length < index) {
        row.push("");
      }
      row[index] = value;
    });
    rows.push(row);
  });

  // Pad ragged rows to the header width so downstream length checks pass.
  const width = rows.reduce((max, row) => Math.max(max, row.length), 0);
  return rows
    .map((row) => {
      const padded = row.slice();
      while (padded.length < width) {
        padded.push("");
      }
      return padded;
    })
    .filter((row) => row.some((cellValue) => cellValue.trim() !== ""));
}
