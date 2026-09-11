import type { ReactNode } from "react";
import { Figure } from "@/components/Figure";
import type { Meta } from "@/lib/meta";
import type { Player } from "@/lib/players";

// A player's career line, read as exported from players.json. The player page
// and compare both render this, so a player cannot read differently on the two.
export function CareerLine({ career, meta, grid }: { career: Player; meta: Meta; grid: string }) {
  return (
    <section aria-label="Career">
      <p data-stat="rank" className="text-[13px] text-muted">
        Career · rank <span className="tabular-nums text-text">{career.rank}</span> of{" "}
        <span className="tabular-nums">{meta.qualified_fielders}</span> qualified fielders · {career.role}
      </p>
      <dl className={`mt-3 grid gap-px overflow-hidden rounded border border-border bg-border ${grid}`}>
        <Stat label="Balls in field" stat="balls_in_field">
          <Figure value={career.balls_in_field} />
        </Stat>
        <Stat label="Catches" stat="catches">
          <Figure value={career.catches} />
        </Stat>
        <Stat label="Run outs" stat="run_outs">
          <Figure value={career.run_outs} />
        </Stat>
        <Stat label="Stumpings" stat="stumpings">
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

function Stat({ label, stat, note, children }: { label: string; stat: string; note?: string; children: ReactNode }) {
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
