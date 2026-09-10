// The fields of web-data/players.json this site reads, as written by
// scripts/export_web.py. The exporter owns the shape; this only types it.
export type Player = {
  fielder: string;
  slug: string;
  role: string;
  rank: number;
  balls_in_field: number;
  catches: number;
  run_outs: number;
  stumpings: number;
  fraa: number;
  fraa_per_100: number;
};

export async function loadPlayers(): Promise<Player[]> {
  const res = await fetch("/data/players.json");
  if (!res.ok) throw new Error(`/data/players.json returned HTTP ${res.status}`);
  return res.json();
}
