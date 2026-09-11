"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CareerLine } from "@/components/CareerStats";
import { LowSampleTag, SeasonTable, type SeasonColumnKey } from "@/components/SeasonTable";
import { loadMeta, type Meta } from "@/lib/meta";
import { loadPlayers, type Player } from "@/lib/players";
import { loadSeasons, type Season } from "@/lib/seasons";

// Career line from players.json, seasons from seasons/<slug>.json, the
// low-sample threshold from meta.json. Every value is read as exported: the
// page sums, averages and rounds nothing, and it reads each season's
// `qualifies` flag rather than comparing balls to the threshold itself
// (architecture.md §14).

type Loaded = { career: Player; seasons: Season[]; meta: Meta };

// Below 640px only season, balls, FRAA and raw FRAA/100 remain.
const COLUMNS: SeasonColumnKey[] = ["season", "role", "innings", "balls", "catches", "run_outs", "stumpings", "fraa", "raw"];
const VISIBILITY: Partial<Record<SeasonColumnKey, string>> = {
  role: "hidden sm:table-cell",
  innings: "hidden lg:table-cell",
  catches: "hidden sm:table-cell",
  run_outs: "hidden md:table-cell",
  stumpings: "hidden md:table-cell",
};

export function PlayerView({ slug, fielder }: { slug: string; fielder: string }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([loadPlayers(), loadSeasons(slug), loadMeta()])
      .then(([players, file, meta]) => {
        const career = players.find((p) => p.slug === slug);
        if (!career) throw new Error(`${slug} is not in /data/players.json`);
        setData({ career, seasons: file.seasons, meta });
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [slug]);

  return (
    <main className="mx-auto max-w-5xl px-4 pb-16 pt-4 sm:px-6">
      <Link href="/" className="text-[13px] text-muted hover:text-text">
        ← Leaderboard
      </Link>
      <h1 className="mt-1 text-lg font-semibold tracking-tight sm:text-xl">{fielder}</h1>

      {error !== null ? (
        <div role="alert" className="mt-4 rounded border border-negative bg-panel p-4 text-[13px]">
          <p className="font-semibold text-negative">Could not load this player</p>
          <p className="mt-1 font-mono text-muted">{error}</p>
        </div>
      ) : data === null ? (
        <p className="mt-4 text-[13px] text-faint">Loading…</p>
      ) : (
        <>
          <CareerLine career={data.career} meta={data.meta} grid="grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" />
          <section aria-label="Seasons" className="mt-6">
            <h2 className="text-sm font-semibold">Season by season</h2>
            <p className="mt-1 max-w-3xl text-[13px] leading-5 text-muted">
              <strong className="font-medium text-text">Raw FRAA/100 is unshrunk.</strong> It is each season&apos;s FRAA
              per 100 balls in field taken at face value: not the same quantity as the shrunk career FRAA/100 above, and a
              short season swings it hard.
            </p>
            <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted">
              <LowSampleTag />
              <span>
                Under <span className="tabular-nums text-text">{data.meta.season_qualify_balls}</span> balls in field.
                Shown, not dropped; read its rate as noise.
              </span>
            </p>
            <SeasonTable
              seasons={data.seasons}
              columns={COLUMNS}
              visibility={VISIBILITY}
              tagInline="md:ml-2 md:mt-0 md:inline"
              substituteLabel="sm:hidden"
            />
          </section>
        </>
      )}
    </main>
  );
}
