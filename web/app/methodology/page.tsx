import type { Metadata } from "next";
import Link from "next/link";
import { Fragment, type ReactNode } from "react";
import { ordinal } from "@/components/LimitationsNote";
import { readMetaAtBuild } from "@/lib/build-meta";
import { DIRTY } from "@/lib/dirty";
import { readLimitationsEvidence } from "@/lib/limitations";
import { dirtyState } from "@/lib/meta";

export const metadata: Metadata = { title: "Methodology" };

// The page that answers "why should I believe any of this". Every assumption,
// caveat and provenance field is read from meta.json at build time, from the
// copy the build step made, so changing a constant in the model, re-exporting
// and rebuilding changes this page with no edit here (MILESTONE Phase 5).

// What each exported assumption means. No value is written here; values come
// from meta.json. An assumption the exporter adds without a description below
// still renders, flagged, rather than being left off.
const MEANING: Record<string, string> = {
  CREDIT_SHARE:
    "Share of a wicket's value credited to the fielder, by how the batter was out. The bowler keeps the rest. A judgement call, not a finding — see how stable the rankings are.",
  RUN_OUT_PRIMARY_SHARE:
    "When a run out credits more than one fielder, the first named takes this fraction of the fielders' share and the others split the remainder evenly.",
  FIELD_TIME_NORMALISATION:
    "What to do when a squad lists more than eleven players, as it can under the Impact Player rule from 2023. drop-and-scale removes listed players who took no visible part in the match, then scales the rest so an innings carries exactly eleven players' worth of field time.",
  FIELDERS_PER_SIDE: "A rule of cricket, not a tunable.",
  CATCH_MODAL_MIN:
    "Keeper inference, when there is no stumping to go on: a team's catch leader for the season is taken as its keeper only with at least this many catches.",
  CATCH_MODAL_MARGIN: "…and only with a lead of at least this many catches over the next fielder.",
  SEASON_BASELINE_SHRINKAGE_BALLS:
    "Each season's expected-credit rate for a role is pulled toward that role's rate across all seasons, as if this many balls at the all-season rate were added to the season's own.",
  regression_balls:
    "The career FRAA/100 rate is multiplied by balls ÷ (balls + regression_balls). A player with exactly this much field time keeps half their observed rate; with less, more of it is pulled to zero.",
  min_balls: "Career balls in the field a player needs to appear on the leaderboard.",
  season_qualify_balls:
    "Balls in the field a season needs before its rate is read as more than noise. Seasons below it are shown, marked low sample, never dropped.",
};

// sensitivity.py's regimes. Not in the export: the script is run by hand.
const REGIMES: [string, string, string, string][] = [
  ["baseline", "0.30", "0.40", "0.90"],
  ["catch-heavy", "0.50", "0.50", "0.90"],
  ["runout-light", "0.30", "0.40", "0.50"],
  ["flat", "0.40", "0.40", "0.40"],
  ["bowler-generous", "0.15", "0.25", "0.80"],
];

const SECTIONS: [string, string][] = [
  ["how", "How FRAA is computed"],
  ["blind", "What it cannot see"],
  ["stability", "How stable the rankings are"],
  ["assumptions", "Assumptions"],
  ["caveats", "Caveats"],
  ["provenance", "Provenance"],
];

export default function MethodologyPage() {
  const meta = readMetaAtBuild();
  const { evidence, of } = readLimitationsEvidence();
  const dirty = DIRTY[dirtyState(meta)];
  const share = (kind: string) => {
    const value = (meta.assumptions.CREDIT_SHARE as Record<string, unknown> | undefined)?.[kind];
    if (typeof value !== "number") throw new Error(`Methodology page: meta.json assumptions.CREDIT_SHARE has no number for "${kind}".`);
    return <Value>{value}</Value>;
  };
  const scalar = (key: string) => {
    const value = meta.assumptions[key];
    if (typeof value !== "number" && typeof value !== "string") throw new Error(`Methodology page: meta.json assumptions has no ${key}.`);
    return <Value>{value}</Value>;
  };

  return (
    <main className="mx-auto max-w-5xl px-4 pb-20 pt-4 sm:px-6">
      <div className="max-w-3xl">
        <h1 className="text-lg font-semibold tracking-tight sm:text-xl">Methodology</h1>
        <p className="mt-1 text-[14px] leading-6 text-muted">
          How FRAA is made, what it assumes, where it is blind, and how far the rankings move when the assumptions do. The
          assumptions, caveats and provenance below are read from the export this site was built from.
        </p>
        <nav aria-label="On this page" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="text-muted underline decoration-border underline-offset-4 hover:text-text">
              {label}
            </a>
          ))}
        </nav>

        <Section id="how" title="How FRAA is computed">
          <ol className="list-decimal space-y-3 pl-5 marker:text-faint">
            <li>
              <Strong>Price the wicket.</Strong> Every wicket falls at a known moment: so many balls left, so many wickets
              down. From every delivery in the data, the model knows how many more runs a batting side usually scores from
              that position. Losing a wicket leaves the side expecting fewer. That difference, in runs, is the
              wicket&apos;s price.
            </li>
            <li>
              <Strong>Split it between bowler and fielder.</Strong> The fielder&apos;s share depends on how the batter was
              out: {share("caught")} of the price for a catch, {share("stumped")} for a stumping, {share("run out")} for a
              run out. Bowled, lbw and caught-and-bowled give the fielder nothing. The bowler keeps the rest. When a run
              out involves several fielders, the first named takes {scalar("RUN_OUT_PRIMARY_SHARE")} of the fielders&apos;
              share.
            </li>
            <li>
              <Strong>Add it up.</Strong> A fielder&apos;s shares of every wicket they were credited on, summed over their
              career, are their runs saved.
            </li>
            <li>
              <Strong>Charge for time in the field.</Strong> A player who fields more gets more chances, so runs saved on
              its own mostly measures playing time. Every player is charged what an average fielder would have earned in
              the same field time — worked out separately for wicketkeepers and outfielders, because a keeper gets chances
              a mid-on never sees, and season by season, because some seasons have more wickets than others.
            </li>
            <li>
              <Strong>FRAA is the difference.</Strong> Runs saved minus that expected amount. Above zero, the player
              converted more than an average fielder would have in their time on the field; below zero, fewer.
            </li>
          </ol>
          <p>
            FRAA/100 is FRAA per 100 balls in the field, pulled toward zero for players with little field time so that two
            lucky matches cannot top the table. A player needs {scalar("min_balls")} balls in the field to appear on the
            leaderboard. The export also prices wickets in win probability during chases; this site shows runs only.
          </p>
        </Section>

        <Section id="blind" title="What this model cannot see">
          <p>
            <Strong>The data records dismissals, not fielding.</Strong> Cricsheet&apos;s ball-by-ball records say who took a
            catch, made a stumping or was involved in a run out. They have no misfields, boundary saves, dropped catches,
            diving stops or direct hits that missed. So the model sees only the fielding that ends in a wicket. It measures
            chance conversion and run-out threat; it is not a complete fielding rating.
          </p>
          <div data-evidence className="rounded border border-amber/40 bg-panel px-4 py-3">
            <p className="text-text">
              Elite ground fielders rank far below their reputation:{" "}
              {evidence.map((e, i) => (
                <Fragment key={e.player}>
                  {i > 0 && " and "}
                  {e.player}
                  {i === 0 ? " is " : " "}
                  <span className="font-semibold tabular-nums">
                    {ordinal(e.rank)}
                    {i === 0 && ` of ${of}`}
                  </span>
                </Fragment>
              ))}
              .
            </p>
            <p className="mt-1">
              Their value is in the stops, saves and throws the data does not record. When a ranking disagrees with an
              informed observer about players like these, the model is usually the one that is wrong, for the reason
              stated here.
            </p>
          </div>
          <p>
            <Strong>Every catch is priced the same.</Strong> A regulation catch at mid-off and a diving one-hander score
            identically; the data carries no measure of difficulty. This is the model&apos;s biggest single weakness.
          </p>
          <p>
            <Strong>From 2023, which eleven took the field is not recorded.</Strong> Under the Impact Player rule, squads
            list twelve or thirteen names with no marker for the starting eleven. Field time is normalised
            (FIELD_TIME_NORMALISATION, below), but inside those innings one player&apos;s field time can still be off by up
            to a twelfth, and that error falls on post-2023 careers.
          </p>
        </Section>

        <Section id="stability" title="How stable the rankings are">
          <p>
            The credit shares are judgement calls, so the whole model has been re-run under five different sets of them to
            see how far the order moves.
          </p>
          <div className="grid gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-2">
            <Headline value="0.963–0.989" label="Rank correlation (Spearman) of the whole table with the baseline, across the five regimes" />
            <Headline value="4 of 10" label="Top-10 names that stay in the top 10 under all five regimes" />
          </div>
          <p>
            <Strong>The head of the table is its least stable part.</Strong> The overall order barely moves, but a top-10
            place rests on a handful of credited wickets, and changing a share reorders them. The top is the part anyone
            reads, so treat a top-10 placing as provisional: quote the band, not the rank.
          </p>
          <table className="w-full border-collapse text-[13px] tabular-nums">
            <caption className="pb-2 text-left text-[12px] text-faint">Fielder&apos;s share of the wicket&apos;s value in each regime</caption>
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-muted">
                <th scope="col" className="py-1.5 pr-2 text-left font-medium">Regime</th>
                <th scope="col" className="px-2 py-1.5 text-right font-medium">Catch</th>
                <th scope="col" className="px-2 py-1.5 text-right font-medium">Stumping</th>
                <th scope="col" className="py-1.5 pl-2 text-right font-medium">Run out</th>
              </tr>
            </thead>
            <tbody>
              {REGIMES.map(([name, caught, stumped, runOut]) => (
                <tr key={name} className="border-t border-border/60">
                  <th scope="row" className="py-1.5 pr-2 text-left font-mono font-normal text-text">
                    {name}
                  </th>
                  <td className="px-2 py-1.5 text-right">{caught}</td>
                  <td className="px-2 py-1.5 text-right">{stumped}</td>
                  <td className="py-1.5 pl-2 text-right">{runOut}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p data-sensitivity-source className="text-[12px] leading-5 text-faint">
            Source: <code className="font-mono">sensitivity.py</code> on the IPL bundle (1,243 matches, 2008–2026), recorded
            in the README at commit b16bca2 on 2026-09-08. The model code had not changed since that commit as of
            2026-09-11. Unlike everything below, these figures are not in the export and are not recomputed when it
            changes.
          </p>
        </Section>

        <Section id="assumptions" title="Assumptions in this export">
          <p>
            Read from <code className="font-mono text-text">meta.json</code> when this site was built. Change one in the
            model, re-export and rebuild, and this list changes with no edit to the site.
          </p>
          <dl className="divide-y divide-border rounded border border-border bg-panel">
            {Object.entries(meta.assumptions).map(([key, value]) => (
              <div key={key} data-assumption={key} className="px-4 py-3">
                <dt className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <code className="break-all font-mono text-[13px] text-text">{key}</code>
                  <span data-assumption-value className="font-mono text-[13px] tabular-nums text-text">
                    <AssumptionValue value={value} />
                  </span>
                </dt>
                <dd className="mt-1 text-[13px] leading-5 text-muted">
                  {MEANING[key] ?? <span className="text-negative">Not yet described on this page.</span>}
                </dd>
              </div>
            ))}
          </dl>
        </Section>

        <Section id="caveats" title="Caveats in this export">
          <ul className="list-disc space-y-2 pl-5 marker:text-faint">
            {meta.caveats.map((caveat) => (
              <li key={caveat} data-caveat>
                {caveat}
              </li>
            ))}
          </ul>
        </Section>

        <Section id="provenance" title="Provenance">
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-4">
            <Fact label="Matches" value={meta.matches.toLocaleString("en-GB")} />
            <Fact label="Deliveries" value={meta.deliveries.toLocaleString("en-GB")} />
            <Fact label="Seasons" value={`${meta.season_min}–${meta.season_max}`} />
            <Fact label="Qualified fielders" value={String(meta.qualified_fielders)} />
          </dl>
          <dl className="rounded border border-border bg-panel px-4 py-3">
            <dt className="text-[11px] uppercase tracking-wider text-muted">Export commit</dt>
            <dd className="mt-1 break-all font-mono text-[13px] text-text">{meta.git_commit}</dd>
            <dd data-dirty-state className={`mt-1 text-[13px] ${dirty.tone}`}>
              {dirty.label}
            </dd>
            <dd className="mt-2 text-[12px] text-faint tabular-nums">
              Generated {meta.generated_at} · git read via {meta.git_source}
            </dd>
          </dl>
          <p>
            This page was rendered when the site was built.{" "}
            <Link href="/provenance" className="text-text underline decoration-border underline-offset-4 hover:decoration-text">
              The provenance check
            </Link>{" "}
            reads the same file from the live site at runtime, so the two can be compared.
          </p>
        </Section>
      </div>
    </main>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="mt-10 scroll-mt-4 border-t border-border pt-6">
      <h2 id={`${id}-heading`} className="text-base font-semibold tracking-tight text-text">
        {title}
      </h2>
      <div className="mt-3 space-y-3 text-[14px] leading-6 text-muted">{children}</div>
    </section>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <strong className="font-medium text-text">{children}</strong>;
}

function Value({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[13px] text-text">{children}</span>;
}

function Headline({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-panel px-4 py-3">
      <p className="text-2xl font-semibold text-text">{value}</p>
      <p className="mt-1 text-[12px] leading-5 text-muted">{label}</p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel px-3 py-2.5">
      <dt className="text-[11px] uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums text-text">{value}</dd>
    </div>
  );
}

function AssumptionValue({ value }: { value: unknown }) {
  if (value !== null && typeof value === "object") {
    return (
      <span className="grid grid-cols-[auto_auto] justify-end gap-x-3 text-right">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <Fragment key={k}>
            <span className="text-muted">{k}</span>
            <span>{String(v)}</span>
          </Fragment>
        ))}
      </span>
    );
  }
  return <>{String(value)}</>;
}
