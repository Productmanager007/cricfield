import { readFileSync } from "node:fs";
import path from "node:path";
import type { Meta } from "./meta";

// The sensitivity block scripts/export_web.py writes, computed by
// sensitivity.py's regimes over the same data as the leaderboard.
export type Sensitivity = {
  source: string;
  baseline_regime: string;
  min_balls: number;
  regression_balls: number;
  top_n: number;
  regimes: { name: string; credit_share: Record<string, number>; spearman: number }[];
  spearman_min: number;
  spearman_max: number;
  top_n_held_in_all: number;
  top_n_held: string[];
  seconds: number;
};

export type MetaAtBuild = Meta & {
  assumptions: Record<string, unknown>;
  caveats: string[];
  sensitivity?: Sensitivity;
};

// Build time only: meta.json as the build step copied it into public/data, so a
// page rendered from it describes exactly the export the site serves.
export function readMetaAtBuild(): MetaAtBuild {
  return JSON.parse(readFileSync(path.join(process.cwd(), "public", "data", "meta.json"), "utf8"));
}

// The methodology page says the head of the table is its least stable part.
// That claim rests on the export's own figures, so the build checks it rather
// than trusting it: if every top-N name survives every credit regime, there is
// no churn and the sentence is false.
export function readSensitivity(meta: MetaAtBuild): Sensitivity {
  const s = meta.sensitivity;
  if (!s || !Array.isArray(s.regimes) || s.regimes.length === 0) {
    throw new Error(
      "Methodology page: public/data/meta.json has no sensitivity block. Re-export with scripts/export_web.py, which now publishes one.",
    );
  }
  if (s.top_n_held_in_all >= s.top_n) {
    throw new Error(
      `Methodology page: the claim needs rewriting; the data is not wrong. All ${s.top_n} of the top ${s.top_n} hold under every credit regime, so the head of the table is no longer the unstable part the stability section says it is. Rewrite that section against this export.`,
    );
  }
  return s;
}
