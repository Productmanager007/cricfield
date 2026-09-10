import { readFileSync } from "node:fs";
import path from "node:path";
import type { Meta } from "./meta";
import type { Player } from "./players";

// The limitations note names one player as evidence. The rank is read at build
// time from the copy the build step has just made, so the note cannot quote a
// rank from a different export than the one the site serves. If the player
// leaves the export, the build fails rather than printing a stale claim.
const EVIDENCE_PLAYER = "RA Jadeja";

export function readLimitationsEvidence(): { player: string; rank: number; of: number } {
  const dir = path.join(process.cwd(), "public", "data");
  const players: Player[] = JSON.parse(readFileSync(path.join(dir, "players.json"), "utf8"));
  const meta: Meta = JSON.parse(readFileSync(path.join(dir, "meta.json"), "utf8"));

  const player = players.find((p) => p.fielder === EVIDENCE_PLAYER);
  if (!player) {
    throw new Error(
      `Limitations note: ${EVIDENCE_PLAYER} is not in public/data/players.json. Rewrite the note's evidence against this export.`,
    );
  }
  if (typeof meta.qualified_fielders !== "number") {
    throw new Error("Limitations note: public/data/meta.json has no qualified_fielders.");
  }
  return { player: player.fielder, rank: player.rank, of: meta.qualified_fielders };
}
