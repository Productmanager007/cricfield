import { readFileSync } from "node:fs";
import path from "node:path";
import type { Meta } from "./meta";
import type { Player } from "./players";

// The limitations note names players as evidence. Their ranks are read at build
// time from the copy the build step has just made, so the note cannot quote a
// rank from a different export than the one the site serves. If any of them
// leaves the export, or ranks well enough that the note's claim no longer
// holds, the build fails rather than printing a stale claim.
const EVIDENCE_PLAYERS = ["RA Jadeja", "SA Yadav"];

// The note says elite ground fielders rank far below their reputation. A
// player inside the top tenth of qualified fielders no longer evidences that.
const TOP_SHARE_THAT_FALSIFIES = 0.1;

export type Evidence = { player: string; rank: number };

export function readLimitationsEvidence(): { evidence: Evidence[]; of: number } {
  const dir = path.join(process.cwd(), "public", "data");
  const players: Player[] = JSON.parse(readFileSync(path.join(dir, "players.json"), "utf8"));
  const meta: Meta = JSON.parse(readFileSync(path.join(dir, "meta.json"), "utf8"));
  if (typeof meta.qualified_fielders !== "number") {
    throw new Error("Limitations note: public/data/meta.json has no qualified_fielders.");
  }
  const of = meta.qualified_fielders;

  const evidence: Evidence[] = [];
  const problems: string[] = [];
  for (const name of EVIDENCE_PLAYERS) {
    const player = players.find((p) => p.fielder === name);
    if (!player) {
      problems.push(`${name} is not in public/data/players.json`);
    } else if (player.rank <= of * TOP_SHARE_THAT_FALSIFIES) {
      problems.push(`${name} is ${player.rank} of ${of}, inside the top ${TOP_SHARE_THAT_FALSIFIES * 100}% of qualified fielders`);
    } else {
      evidence.push({ player: player.fielder, rank: player.rank });
    }
  }
  if (problems.length > 0) {
    throw new Error(
      `Limitations note: the claim needs rewriting; the data is not wrong. ${problems.join("; ")}. ` +
        "This export no longer shows elite ground fielders ranking far below their reputation as the note says. " +
        "Rewrite the evidence in components/LimitationsNote.tsx and lib/limitations.ts.",
    );
  }
  return { evidence, of };
}
