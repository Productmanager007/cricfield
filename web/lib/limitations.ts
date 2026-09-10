import { readFileSync } from "node:fs";
import path from "node:path";
import type { Meta } from "./meta";
import type { Player } from "./players";

// The limitations note names one player as evidence. The rank is read at build
// time from the copy the build step has just made, so the note cannot quote a
// rank from a different export than the one the site serves. If the player
// leaves the export, or ranks well enough that the note's claim no longer
// holds, the build fails rather than printing a stale claim.
const EVIDENCE_PLAYER = "RA Jadeja";

// The note says elite ground fielders rank far below their reputation. A
// player inside the top tenth of qualified fielders no longer evidences that.
const TOP_SHARE_THAT_FALSIFIES = 0.1;

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
  const of = meta.qualified_fielders;
  if (player.rank <= of * TOP_SHARE_THAT_FALSIFIES) {
    throw new Error(
      `Limitations note: the claim needs rewriting; the data is not wrong. ${EVIDENCE_PLAYER} is ${player.rank} of ${of}, ` +
        `inside the top ${TOP_SHARE_THAT_FALSIFIES * 100}% of qualified fielders, so this export no longer shows an elite ` +
        `ground fielder ranking far below their reputation. Rewrite the evidence in components/LimitationsNote.tsx.`,
    );
  }
  return { player: player.fielder, rank: player.rank, of };
}
