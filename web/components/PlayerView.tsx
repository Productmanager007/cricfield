"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { Figure } from "@/components/Figure";
import { loadMeta, type Meta } from "@/lib/meta";
import { loadPlayers, type Player } from "@/lib/players";
import { loadSeasons, type Season } from "@/lib/seasons";

// Career line from players.json, seasons from seasons/<slug>.json, the
// low-sample threshold from meta.json. Every value is read as exported: the
// page sums, averages and rounds nothing, and it reads each season's
// `qualifies` flag rather than comparing balls to the threshold itself
// (architecture.md §14).

type Loaded = { career: Player; seasons: Season[]; meta: Meta };

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
          <CareerLine career={data.career} meta={data.meta} />
          <SeasonTable seasons={data.seasons} meta={data.meta} />
        </>
      )}
    </main>
  );
}

function CareerLine({ career, meta }: { career: Player; meta: Meta }) {
  return (
    <section aria-label="Career">
      <p className="text-[13px] text-muted">
        Career · rank <span className="tabular-nums text-text">{career.rank}</span> of{" "}
        <span className="tabular-nums">{meta.qualified_fielders}</span> qualified fielders · {career.role}
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Balls in field">
          <Figure value={career.balls_in_field} />
        </Stat>
        <Stat label="Catches">
          <Figure value={career.catches} />
        </Stat>
        <Stat label="Run outs">
          <Figure value={career.run_outs} />
        </Stat>
        <Stat label="Stumpings">
          <Figure value={career.stumpings} />
        </Stat>
        <Stat label="FRAA" stat="fraa" note="Career total">
          <Figure value={career.fraa} signed />
        </Stat>
        <Stat
          label="FRAA/100 · shrunk"
          stat="fraa_per_100"
          note={`Career rate, shrunk toward average (regression_balls ${meta.assumptions.regression_balls})`}
        >
          <Figure value={career.fraa_per_100} signed />
        </Stat>
      </dl>
    </section>
  );
}

function Stat({ label, stat, note, children }: { label: string; stat?: string; note?: string; children: ReactNode }) {
  return (
    <div className="bg-panel px-3 py-2.5">
      <dt className="text-[11px] uppercase tracking-wider text-muted">{label}</dt>
      <dd data-stat={stat} className="mt-0.5 text-xl font-semibold tabular-nums">
        {children}
      </dd>
      {note && <dd className="mt-0.5 text-[11px] leading-4 text-faint">{note}</dd>}
    </div>
  );
}

type SeasonColumn = {
  label: string;
  title: string;
  numeric: boolean;
  // Below 640px only season, balls, FRAA and raw FRAA/100 remain.
  visibility: string;
  render: (s: Season) => ReactNode;
};

const SEASON_COLUMNS: SeasonColumn[] = [
  {
    label: "Season",
    title: "Season",
    numeric: false,
    visibility: "",
    render: (s) => (
      <>
        <span className="font-medium text-text">{s.season}</span>
        {!s.qualifies && (
          <span className="mt-0.5 block md:ml-2 md:mt-0 md:inline">
            <LowSampleTag />
          </span>
        )}
        {s.role === null && <span className="block text-[11px] leading-4 text-faint sm:hidden">substitute only</span>}
      </>
    ),
  },
  {
    label: "Role",
    title: "Role that season",
    numeric: false,
    visibility: "hidden sm:table-cell",
    render: (s) =>
      s.role ?? (
        <span className="text-faint" title="No field time this season: credited only as a substitute fielder">
          substitute
        </span>
      ),
  },
  { label: "Innings", title: "Innings fielded", numeric: true, visibility: "hidden lg:table-cell", render: (s) => <Figure value={s.innings_fielded} /> },
  { label: "Balls", title: "Balls in field", numeric: true, visibility: "", render: (s) => <Figure value={s.balls_in_field} /> },
  { label: "Catches", title: "Catches", numeric: true, visibility: "hidden sm:table-cell", render: (s) => <Figure value={s.catches} /> },
  { label: "Run outs", title: "Run outs", numeric: true, visibility: "hidden md:table-cell", render: (s) => <Figure value={s.run_outs} /> },
  { label: "Stumpings", title: "Stumpings", numeric: true, visibility: "hidden md:table-cell", render: (s) => <Figure value={s.stumpings} /> },
  { label: "FRAA", title: "Fielding runs above average, this season", numeric: true, visibility: "", render: (s) => <Figure value={s.fraa} places={4} signed /> },
  {
    label: "Raw FRAA/100",
    title: "This season's FRAA per 100 balls in field, unshrunk",
    numeric: true,
    visibility: "",
    render: (s) =>
      s.fraa_per_100_raw === null ? (
        <span className="text-faint" title="No balls in field, so no rate">
          —
        </span>
      ) : (
        <Figure value={s.fraa_per_100_raw} places={4} signed />
      ),
  },
];

// Hatched, so a thin season reads differently before any label is read.
const LOW_SAMPLE_ROW = "bg-[repeating-linear-gradient(135deg,rgba(240,162,2,0.08)_0_2px,transparent_2px_8px)]";

function SeasonTable({ seasons, meta }: { seasons: Season[]; meta: Meta }) {
  return (
    <section aria-label="Seasons" className="mt-6">
      <h2 className="text-sm font-semibold">Season by season</h2>
      <p className="mt-1 max-w-3xl text-[13px] leading-5 text-muted">
        <strong className="font-medium text-text">Raw FRAA/100 is unshrunk.</strong> It is each season&apos;s FRAA per
        100 balls in field taken at face value: not the same quantity as the shrunk career FRAA/100 above, and a short
        season swings it hard.
      </p>
      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted">
        <LowSampleTag />
        <span>
          Under <span className="tabular-nums text-text">{meta.season_qualify_balls}</span> balls in field. Shown, not
          dropped; read its rate as noise.
        </span>
      </p>

      <table className="mt-3 w-full border-collapse text-[13px] tabular-nums">
        <thead>
          <tr>
            {SEASON_COLUMNS.map((c) => (
              <th
                key={c.label}
                scope="col"
                title={c.title}
                className={`${c.visibility} px-2 py-2 align-bottom text-[11px] font-medium uppercase tracking-wider text-muted shadow-[inset_0_-1px_0_#242C38] ${c.numeric ? "text-right" : "text-left"}`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {seasons.map((s) => (
            <tr key={s.season} data-season={s.season} className={`border-b border-border/60 ${s.qualifies ? "" : LOW_SAMPLE_ROW}`}>
              {SEASON_COLUMNS.map((c, i) => (
                <td
                  key={c.label}
                  className={`${c.visibility} px-2 py-1.5 align-top ${c.numeric ? "text-right" : "text-left"} ${
                    s.qualifies ? "" : i === 0 ? "shadow-[inset_2px_0_0_#F0A202]" : "opacity-60"
                  }`}
                >
                  {c.render(s)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function LowSampleTag() {
  return (
    <span className="inline-block whitespace-nowrap rounded-sm border border-amber/60 px-1 text-[10px] font-semibold uppercase leading-4 tracking-wider text-amber">
      Low sample
    </span>
  );
}
