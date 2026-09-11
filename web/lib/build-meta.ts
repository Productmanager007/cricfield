import { readFileSync } from "node:fs";
import path from "node:path";
import type { Meta } from "./meta";

export type MetaAtBuild = Meta & {
  assumptions: Record<string, unknown>;
  caveats: string[];
};

// Build time only: meta.json as the build step copied it into public/data, so a
// page rendered from it describes exactly the export the site serves.
export function readMetaAtBuild(): MetaAtBuild {
  return JSON.parse(readFileSync(path.join(process.cwd(), "public", "data", "meta.json"), "utf8"));
}
