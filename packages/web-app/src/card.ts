import { parse } from "yaml";
import type { ParsedCard } from "./types";

export function parseNodeCard(source: string): ParsedCard {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return { metadata: {}, markdown: source };
  return {
    metadata: (parse(match[1]) || {}) as ParsedCard["metadata"],
    markdown: match[2].trim(),
  };
}

export function formatBytes(value: unknown) {
  const bytes = Number(value || 0);
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}
