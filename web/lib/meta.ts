// The fields of web-data/meta.json this site reads, as written by
// scripts/export_web.py. The exporter owns the shape; this only types it.
export type Meta = {
  generated_at: string;
  matches: number;
  deliveries: number;
  season_min: number;
  season_max: number;
  qualified_fielders: number;
  git_commit: string;
  git_dirty: boolean | null;
  // Absent from exports that predate it, which is read as unknown.
  git_dirty_known?: boolean;
  git_source: string;
};

export async function loadMeta(): Promise<Meta> {
  const res = await fetch("/data/meta.json");
  if (!res.ok) throw new Error(`/data/meta.json returned HTTP ${res.status}`);
  return res.json();
}

export type DirtyState = "clean" | "modified" | "unknown";

// architecture.md §14: read git_dirty_known before git_dirty. A null
// git_dirty treated as falsy would report an unverified tree as clean.
export function dirtyState(meta: Meta): DirtyState {
  if (meta.git_dirty_known !== true || meta.git_dirty === null) return "unknown";
  return meta.git_dirty ? "modified" : "clean";
}
