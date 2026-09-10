// The fields of web-data/seasons/<slug>.json this site reads, as written by
// scripts/export_web.py. The exporter owns the shape; this only types it.
export type Season = {
  season: number;
  // Null for a substitute-only season: credit earned, no field time.
  role: string | null;
  innings_fielded: number;
  balls_in_field: number;
  catches: number;
  run_outs: number;
  stumpings: number;
  fraa: number;
  // Unshrunk, unlike the career fraa_per_100. Null when there is no field time.
  fraa_per_100_raw: number | null;
  qualifies: boolean;
};

export type SeasonFile = { fielder: string; slug: string; seasons: Season[] };

export async function loadSeasons(slug: string): Promise<SeasonFile> {
  const res = await fetch(`/data/seasons/${slug}.json`);
  if (!res.ok) throw new Error(`/data/seasons/${slug}.json returned HTTP ${res.status}`);
  return res.json();
}
