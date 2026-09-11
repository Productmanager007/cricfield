import type { ReactNode } from "react";
import { Figure } from "@/components/Figure";
import type { Season } from "@/lib/seasons";

// Season rows as exported, with low-sample seasons marked. Shared by the player
// page and compare, so a thin season is marked the same way on both. Rows are
// shown in the order given; the table reads each row's `qualifies` flag and
// never compares balls to the threshold itself.

export type SeasonColumnKey = "season" | "role" | "innings" | "balls" | "catches" | "run_outs" | "stumpings" | "fraa" | "raw";

type Options = { tagInline: string; substituteLabel: string };

type Column = {
  label: string;
  title: string;
  numeric: boolean;
  render: (s: Season, options: Options) => ReactNode;
};

const COLUMNS: Record<SeasonColumnKey, Column> = {
  season: {
    label: "Season",
    title: "Season",
    numeric: false,
    render: (s, { tagInline, substituteLabel }) => (
      <>
        <span className="font-medium text-text">{s.season}</span>
        {!s.qualifies && (
          <span className={`mt-0.5 block ${tagInline}`}>
            <LowSampleTag />
          </span>
        )}
        {s.role === null && <span className={`block text-[11px] leading-4 text-faint ${substituteLabel}`}>substitute only</span>}
      </>
    ),
  },
  role: {
    label: "Role",
    title: "Role that season",
    numeric: false,
    render: (s) =>
      s.role ?? (
        <span className="text-faint" title="No field time this season: credited only as a substitute fielder">
          substitute
        </span>
      ),
  },
  innings: { label: "Innings", title: "Innings fielded", numeric: true, render: (s) => <Figure value={s.innings_fielded} /> },
  balls: { label: "Balls", title: "Balls in field", numeric: true, render: (s) => <Figure value={s.balls_in_field} /> },
  catches: { label: "Catches", title: "Catches", numeric: true, render: (s) => <Figure value={s.catches} /> },
  run_outs: { label: "Run outs", title: "Run outs", numeric: true, render: (s) => <Figure value={s.run_outs} /> },
  stumpings: { label: "Stumpings", title: "Stumpings", numeric: true, render: (s) => <Figure value={s.stumpings} /> },
  fraa: { label: "FRAA", title: "Fielding runs above average, this season", numeric: true, render: (s) => <Figure value={s.fraa} places={4} signed /> },
  raw: {
    label: "Raw FRAA/100",
    title: "This season's FRAA per 100 balls in field, unshrunk",
    numeric: true,
    render: (s) =>
      s.fraa_per_100_raw === null ? (
        <span className="text-faint" title="No balls in field, so no rate">
          —
        </span>
      ) : (
        <Figure value={s.fraa_per_100_raw} places={4} signed />
      ),
  },
};

// Hatched, so a thin season reads differently before any label is read.
export const LOW_SAMPLE_ROW = "bg-[repeating-linear-gradient(135deg,rgba(240,162,2,0.08)_0_2px,transparent_2px_8px)]";

export function SeasonTable({
  seasons,
  columns,
  visibility = {},
  tagInline = "",
  substituteLabel = "",
  label,
}: {
  seasons: Season[];
  columns: SeasonColumnKey[];
  // Tailwind display classes per column, for columns that hide on narrow screens.
  visibility?: Partial<Record<SeasonColumnKey, string>>;
  // Where the LOW SAMPLE tag moves inline beside the year; it stacks below otherwise.
  tagInline?: string;
  // Where "substitute only" under the year hides because a role column shows it.
  substituteLabel?: string;
  label?: string;
}) {
  const options = { tagInline, substituteLabel };
  return (
    <table aria-label={label} className="mt-3 w-full border-collapse text-[13px] tabular-nums">
      <thead>
        <tr>
          {columns.map((key) => (
            <th
              key={key}
              scope="col"
              title={COLUMNS[key].title}
              className={`${visibility[key] ?? ""} px-2 py-2 align-bottom text-[11px] font-medium uppercase tracking-wider text-muted shadow-[inset_0_-1px_0_#242C38] ${COLUMNS[key].numeric ? "text-right" : "text-left"}`}
            >
              {COLUMNS[key].label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {seasons.map((s) => (
          <tr key={s.season} data-season={s.season} className={`border-b border-border/60 ${s.qualifies ? "" : LOW_SAMPLE_ROW}`}>
            {columns.map((key, i) => (
              <td
                key={key}
                className={`${visibility[key] ?? ""} px-2 py-1.5 align-top ${COLUMNS[key].numeric ? "text-right" : "text-left"} ${
                  s.qualifies ? "" : i === 0 ? "shadow-[inset_2px_0_0_#F0A202]" : "opacity-60"
                }`}
              >
                {COLUMNS[key].render(s, options)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function LowSampleTag() {
  return (
    <span className="inline-block whitespace-nowrap rounded-sm border border-amber/60 px-1 text-[10px] font-semibold uppercase leading-4 tracking-wider text-amber">
      Low sample
    </span>
  );
}
