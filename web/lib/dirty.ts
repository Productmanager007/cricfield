import type { DirtyState } from "./meta";

// architecture.md §14's three provenance states, as the site words them.
// Unknown is never shown as clean.
export const DIRTY: Record<DirtyState, { label: string; tone: string }> = {
  clean: { label: "Tracked files matched this commit", tone: "text-positive" },
  modified: {
    label: "Tracked files were modified: this commit does not describe the code that ran",
    tone: "text-negative",
  },
  unknown: { label: "Dirty state unknown: nothing verified the tree was clean", tone: "text-amber" },
};
