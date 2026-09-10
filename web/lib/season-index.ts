import { readFileSync } from "node:fs";
import path from "node:path";

// Build time only: the display name -> slug index the build step copied into
// public/data. It decides which player pages exist.
export function readSeasonIndex(): Record<string, string> {
  return JSON.parse(readFileSync(path.join(process.cwd(), "public", "data", "seasons", "index.json"), "utf8"));
}
