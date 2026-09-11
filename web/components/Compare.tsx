"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { CareerLine } from "@/components/CareerStats";
import { PlayerPicker } from "@/components/PlayerPicker";
import { SeasonChart } from "@/components/SeasonChart";
import { LowSampleTag, SeasonTable } from "@/components/SeasonTable";
import { loadMeta, type Meta } from "@/lib/meta";
import { loadPlayers, type Player } from "@/lib/players";
import { loadSeasons, type Season } from "@/lib/seasons";
import { SERIES, type Side } from "@/lib/series";

// Two players side by side. players.json and meta.json load with the route;
// picking a player then fetches that player's season file and nothing else,
// so picking two fetches exactly two (MILESTONE Phase 4). The pair lives in
// the query string, ?a=<slug>&b=<slug>, so a comparison can be pasted as a
// link. Common seasons are a filter over exported rows; nothing is summed,
// averaged or re-derived (architecture.md §14).

const SIDES: Side[] = ["a", "b"];
const LABEL: Record<Side, string> = { a: "First player", b: "Second player" };

type Picked = Record<Side, string | null>;

export function Compare() {
  const [players, setPlayers] = useState<Player[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [linkIssues, setLinkIssues] = useState<string[]>([]);
  const [picked, setPicked] = useState<Picked>({ a: null, b: null });
  const [seasons, setSeasons] = useState<Record<string, Season[]>>({});
  const [seasonErrors, setSeasonErrors] = useState<Record<string, string>>({});
  const requested = useRef(new Set<string>());

  useEffect(() => {
    Promise.all([loadPlayers(), loadMeta()])
      .then(([list, m]) => {
        const known = new Set(list.map((p) => p.slug));
        const query = new URLSearchParams(window.location.search);
        const initial: Picked = { a: null, b: null };
        const issues: string[] = [];
        for (const side of SIDES) {
          const slug = query.get(side);
          if (!slug) continue;
          if (!known.has(slug)) issues.push(`The link names “${slug}”, which is not a player in this export.`);
          else if (side === "b" && slug === initial.a) issues.push("The link names the same player twice. Pick a second player.");
          else initial[side] = slug;
        }
        setPlayers(list);
        setMeta(m);
        setLinkIssues(issues);
        setPicked(initial);
      })
      .catch((e: unknown) => setLoadError(e instanceof Error ? e.message : String(e)));
  }, []);

  // Each picked player's season file, fetched once.
  useEffect(() => {
    for (const slug of [picked.a, picked.b]) {
      if (!slug || requested.current.has(slug)) continue;
      requested.current.add(slug);
      loadSeasons(slug).then(
        (file) => setSeasons((s) => ({ ...s, [slug]: file.seasons })),
        (e: unknown) => setSeasonErrors((s) => ({ ...s, [slug]: e instanceof Error ? e.message : String(e) })),
      );
    }
  }, [picked]);

  // Keep the address bar carrying the pair. replaceState, not the router, so
  // updating it requests nothing.
  useEffect(() => {
    if (players === null) return;
    const query = new URLSearchParams();
    for (const side of SIDES) if (picked[side]) query.set(side, picked[side] as string);
    const search = query.toString() ? `?${query}` : "";
    if (search !== window.location.search) window.history.replaceState(null, "", `${window.location.pathname}${search}`);
  }, [picked, players]);

  const bySlug = useMemo(() => new Map((players ?? []).map((p) => [p.slug, p])), [players]);

  return (
    <main className="mx-auto max-w-5xl px-4 pb-16 pt-4 sm:px-6">
      <h1 className="text-base font-semibold tracking-tight sm:text-lg">Compare fielders</h1>
      <p className="text-[13px] text-muted">
        Pick two players. The address bar then carries both, so the comparison can be shared as a link.
      </p>

      {loadError !== null ? (
        <div role="alert" className="mt-4 rounded border border-negative bg-panel p-4 text-[13px]">
          <p className="font-semibold text-negative">Could not load players.json</p>
          <p className="mt-1 font-mono text-muted">{loadError}</p>
        </div>
      ) : players === null || meta === null ? (
        <p className="mt-4 text-[13px] text-faint">Loading players.json…</p>
      ) : (
        <>
          {linkIssues.map((issue) => (
            <p key={issue} role="alert" className="mt-3 text-[13px] text-negative">
              {issue}
            </p>
          ))}
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {SIDES.map((side) => (
              <PlayerPicker
                key={side}
                id={`pick-${side}`}
                label={LABEL[side]}
                colour={SERIES[side]}
                players={players}
                selected={picked[side] ? (bySlug.get(picked[side] as string) ?? null) : null}
                exclude={picked[side === "a" ? "b" : "a"]}
                onSelect={(slug) => setPicked((p) => ({ ...p, [side]: slug }))}
              />
            ))}
          </div>
          <Comparison picked={picked} bySlug={bySlug} seasons={seasons} errors={seasonErrors} meta={meta} />
        </>
      )}
    </main>
  );
}

function Comparison({
  picked,
  bySlug,
  seasons,
  errors,
  meta,
}: {
  picked: Picked;
  bySlug: Map<string, Player>;
  seasons: Record<string, Season[]>;
  errors: Record<string, string>;
  meta: Meta;
}) {
  if (!picked.a || !picked.b) {
    return (
      <p className="mt-6 text-[13px] text-faint">
        {picked.a || picked.b ? "Now pick a second player." : "Pick two players to compare."}
      </p>
    );
  }
  const slugs = [picked.a, picked.b];
  const failed = slugs.filter((s) => errors[s]);
  if (failed.length > 0) {
    return (
      <div role="alert" className="mt-6 rounded border border-negative bg-panel p-4 text-[13px]">
        <p className="font-semibold text-negative">Could not load a season file</p>
        {failed.map((s) => (
          <p key={s} className="mt-1 font-mono text-muted">
            {errors[s]}
          </p>
        ))}
      </div>
    );
  }
  const [rowsA, rowsB] = slugs.map((s) => seasons[s]);
  if (!rowsA || !rowsB) return <p className="mt-6 text-[13px] text-faint">Loading season files…</p>;

  const pair = slugs.map((s) => bySlug.get(s) as Player);
  const inB = new Set(rowsB.map((s) => s.season));
  const years = rowsA.map((s) => s.season).filter((year) => inB.has(year));
  const common = new Set(years);
  const shared = [rowsA, rowsB].map((rows) => rows.filter((s) => common.has(s.season)));

  return (
    <>
      <section aria-label="Career figures" className="mt-6 grid gap-6 md:grid-cols-2 md:gap-4">
        {pair.map((p, i) => (
          <div key={p.slug} data-player-panel={SIDES[i]} className="min-w-0">
            <PlayerHeading player={p} colour={SERIES[SIDES[i]]} level="h2" />
            <div className="mt-1">
              <CareerLine career={p} meta={meta} grid="grid-cols-2 sm:grid-cols-3" />
            </div>
          </div>
        ))}
      </section>

      {years.length === 0 ? (
        <section data-no-common-seasons role="status" className="mt-8 rounded border border-border bg-panel p-4 text-[13px]">
          <p className="font-semibold text-text">No common seasons</p>
          <p className="mt-1 leading-5 text-muted">
            {pair.map((p, i) => {
              const rows = i === 0 ? rowsA : rowsB;
              const first = rows[0].season;
              const last = rows[rows.length - 1].season;
              return (
                <span key={p.slug}>
                  {i > 0 && "; "}
                  {first === last ? (
                    <>
                      {p.fielder}&apos;s only season in this export is <span className="tabular-nums text-text">{first}</span>
                    </>
                  ) : (
                    <>
                      {p.fielder}&apos;s seasons in this export span{" "}
                      <span className="tabular-nums text-text">
                        {first}–{last}
                      </span>
                    </>
                  )}
                </span>
              );
            })}
            . They share no season, so there is nothing to set side by side and no chart.
          </p>
        </section>
      ) : (
        <section aria-label="Common seasons" className="mt-8">
          <h2 className="text-sm font-semibold">Common seasons</h2>
          <p className="mt-1 max-w-3xl text-[13px] leading-5 text-muted">
            <strong className="font-medium text-text">Season rates are raw FRAA/100, unshrunk:</strong> each season&apos;s
            FRAA per 100 balls in field at face value. They are not the shrunk career FRAA/100 above, and a short season
            swings them hard.
          </p>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted">
            <LowSampleTag />
            <span>
              Under <span className="tabular-nums text-text">{meta.season_qualify_balls}</span> balls in field. Shown, not
              dropped; read its rate as noise.
            </span>
          </p>

          <SeasonChart
            years={years}
            threshold={meta.season_qualify_balls}
            series={[
              { side: "a", name: pair[0].fielder, colour: SERIES.a, seasons: shared[0] },
              { side: "b", name: pair[1].fielder, colour: SERIES.b, seasons: shared[1] },
            ]}
          />

          <div className="mt-6 grid gap-6 md:grid-cols-2 md:gap-4">
            {pair.map((p, i) => (
              <div key={p.slug} data-season-table={SIDES[i]} className="min-w-0">
                <PlayerHeading player={p} colour={SERIES[SIDES[i]]} level="h3" />
                <SeasonTable seasons={shared[i]} columns={["season", "balls", "fraa", "raw"]} label={`${p.fielder}, common seasons`} />
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function PlayerHeading({ player, colour, level }: { player: Player; colour: string; level: "h2" | "h3" }) {
  const Heading = level;
  return (
    <Heading className="flex items-center gap-2 text-base font-semibold">
      <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: colour }} />
      {/* No prefetch: a pick must fetch its season file and nothing else. */}
      <Link href={`/player/${player.slug}`} prefetch={false} className="hover:text-amber hover:underline">
        {player.fielder}
      </Link>
    </Heading>
  );
}
