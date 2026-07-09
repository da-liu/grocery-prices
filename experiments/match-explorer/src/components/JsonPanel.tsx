import { useMemo } from "react";

function stringify(value: unknown, indent = 0): string {
  const pad = "  ".repeat(indent);
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    const items = value.map((item) => `${pad}  ${stringify(item, indent + 1)}`);
    return `[\n${items.join(",\n")}\n${pad}]`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return "{}";
    const lines = entries.map(
      ([key, val]) => `${pad}  ${JSON.stringify(key)}: ${stringify(val, indent + 1)}`,
    );
    return `{\n${lines.join(",\n")}\n${pad}}`;
  }
  return String(value);
}

export function JsonPanel({ value }: { value: unknown }) {
  const text = useMemo(() => stringify(value), [value]);
  return <pre className="json-panel">{text}</pre>;
}
