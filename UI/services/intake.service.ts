import { mockIntakeSummary } from "@/data/mock-intake";
import type { FlaggedRow, IntakeRuleStat, IntakeSummary } from "@/types/domain";

export async function getIntakeSummary(): Promise<IntakeSummary> {
  return mockIntakeSummary;
}

type LedgerRow = Record<string, string>;

const ruleOrder: Array<{ rule: string; tone: IntakeRuleStat["tone"] }> = [
  { rule: "Materiality >= $25k", tone: "danger" },
  { rule: "FX outlier", tone: "warning" },
  { rule: "Round-number", tone: "warning" },
  { rule: "Segregation of duties", tone: "danger" },
  { rule: "Duplicate", tone: "info" },
  { rule: "Unknown vendor", tone: "danger" },
  { rule: "Off-hours posting", tone: "info" },
];

function parseDelimitedRows(text: string, delimiter: "," | "\t") {
  const rows: string[][] = [];
  let current = "";
  let row: string[] = [];
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && next === '"' && inQuotes) {
      current += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === delimiter && !inQuotes) {
      row.push(current.trim());
      current = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(current.trim());
      if (row.some(Boolean)) {
        rows.push(row);
      }
      row = [];
      current = "";
      continue;
    }

    current += char;
  }

  row.push(current.trim());
  if (row.some(Boolean)) {
    rows.push(row);
  }

  return rows;
}

function normalizeHeader(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function getValue(row: LedgerRow, keys: string[]) {
  return keys.map((key) => row[key]).find((value) => value && value.trim().length > 0) ?? "";
}

function parseAmount(value: string) {
  const cleaned = value.replace(/[^0-9.-]/g, "");
  const parsed = Number(cleaned);

  return Number.isFinite(parsed) ? parsed : 0;
}

function formatAmount(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function isWeekendOrOffHours(value: string) {
  if (!value) {
    return false;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return false;
  }

  const day = date.getDay();
  const hour = date.getHours();

  return day === 0 || day === 6 || hour < 6 || hour > 20;
}

function ruleLabelsForRow(row: LedgerRow, duplicateKeys: Set<string>) {
  const amount = Math.abs(parseAmount(getValue(row, ["amount_usd", "amount", "debit", "credit"])));
  const vendor = getValue(row, ["vendor", "vendor_name", "supplier"]);
  const currency = getValue(row, ["currency", "ccy"]).toUpperCase();
  const fxRate = parseAmount(getValue(row, ["fx_rate_used", "fx_rate", "rate"]));
  const postedBy = getValue(row, ["posted_by", "created_by", "user"]).toLowerCase();
  const date = getValue(row, ["date", "posted_at", "posting_date", "timestamp"]);
  const duplicateKey = `${vendor.toLowerCase()}|${amount}`;
  const rules: string[] = [];

  if (amount >= 25_000) {
    rules.push("materiality");
  }

  if (amount >= 1_000 && amount % 1_000 === 0) {
    rules.push("round-number");
  }

  if ((currency && currency !== "USD" && fxRate === 0) || fxRate > 2 || (fxRate > 0 && fxRate < 0.2)) {
    rules.push("fx outlier");
  }

  if (["admin", "system", "rkumar"].some((token) => postedBy.includes(token))) {
    rules.push("segregation of duties");
  }

  if (duplicateKeys.has(duplicateKey)) {
    rules.push("duplicate");
  }

  if (!vendor || /unknown|test|family holdings|adreach/i.test(vendor)) {
    rules.push("unknown vendor");
  }

  if (isWeekendOrOffHours(date)) {
    rules.push("off-hours");
  }

  return rules;
}

function toRuleStats(flaggedRows: FlaggedRow[]) {
  const counts = new Map<string, number>();
  const ruleNameByFlag: Record<string, string> = {
    materiality: "Materiality >= $25k",
    "fx outlier": "FX outlier",
    "round-number": "Round-number",
    "segregation of duties": "Segregation of duties",
    duplicate: "Duplicate",
    "unknown vendor": "Unknown vendor",
    "off-hours": "Off-hours posting",
  };

  flaggedRows.forEach((row) => {
    row.rules.forEach((rule) => {
      const label = ruleNameByFlag[rule] ?? rule;
      counts.set(label, (counts.get(label) ?? 0) + 1);
    });
  });

  return ruleOrder.map((rule) => ({
    ...rule,
    count: counts.get(rule.rule) ?? 0,
  }));
}

function readFileText(file: File) {
  const textReader = (file as File & { text?: () => Promise<string> }).text;

  if (typeof textReader === "function") {
    return textReader.call(file);
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("Unable to read the uploaded file."));
    reader.readAsText(file);
  });
}

export async function parseLedgerFile(file: File): Promise<IntakeSummary> {
  const text = await readFileText(file);
  const delimiter = file.name.toLowerCase().endsWith(".tsv") ? "\t" : ",";
  const parsedRows = parseDelimitedRows(text, delimiter);
  const [rawHeaders, ...rawDataRows] = parsedRows;

  if (!rawHeaders || rawHeaders.length === 0) {
    throw new Error("The uploaded file does not contain a header row.");
  }

  const headers = rawHeaders.map(normalizeHeader);
  let parseErrors = 0;
  const rows: LedgerRow[] = [];

  rawDataRows.forEach((rawRow) => {
    if (rawRow.length !== headers.length) {
      parseErrors += 1;
      return;
    }

    rows.push(
      headers.reduce<LedgerRow>((acc, header, index) => {
        acc[header] = rawRow[index] ?? "";
        return acc;
      }, {}),
    );
  });

  const seen = new Set<string>();
  const duplicates = new Set<string>();
  rows.forEach((row) => {
    const vendor = getValue(row, ["vendor", "vendor_name", "supplier"]).toLowerCase();
    const amount = Math.abs(parseAmount(getValue(row, ["amount_usd", "amount", "debit", "credit"])));
    const key = `${vendor}|${amount}`;

    if (seen.has(key)) {
      duplicates.add(key);
    }
    seen.add(key);
  });

  const flaggedRows = rows
    .map((row): FlaggedRow => {
      const amount = Math.abs(parseAmount(getValue(row, ["amount_usd", "amount", "debit", "credit"])));

      return {
        txnId: getValue(row, ["txn_id", "transaction_id", "id"]) || "UNMAPPED",
        vendor: getValue(row, ["vendor", "vendor_name", "supplier"]) || "Unknown vendor",
        account: getValue(row, ["account", "category", "gl_account"]) || "Unmapped account",
        amount: formatAmount(amount),
        rules: ruleLabelsForRow(row, duplicates),
      };
    })
    .filter((row) => row.rules.length > 0)
    .slice(0, 50);

  return {
    fileName: file.name,
    rowsIngested: rows.length,
    flagged: flaggedRows.length,
    cleared: Math.max(rows.length - flaggedRows.length, 0),
    parseErrors,
    estCostUsd: Number((flaggedRows.length * 0.21).toFixed(2)),
    columns: headers,
    ruleStats: toRuleStats(flaggedRows),
    flaggedRows,
  };
}
