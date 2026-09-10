"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { loadPlayers, type Player } from "@/lib/players";

// Every value shown is a field of players.json as exported. Sorting and search
// reorder and hide rows; nothing here computes, rounds or ranks
// (architecture.md §14). The load order is the exported `rank`, read.

type Key = "rank" | "fielder" | "role" | "balls_in_field" | "catches" | "run_outs" | "stumpings" | "fraa" | "fraa_per_100";
type Sort = { key: Key; dir: "asc" | "desc" };

type Column = {
  key: Key;
  label: string;
  title: string;
  numeric: boolean;
  // Which viewports show the column. Below 640px only rank, fielder, FRAA and
  // FRAA/100 remain, so the table narrows instead of scrolling sideways.
  visibility: string;
  // Preferred width, so columns hold still as search and sort change which
  // rows are shown. The fielder column takes whatever is left.
  width: string;
  render: (p: Player) => ReactNode;
};

const COLUMNS: Column[] = [
  { key: "rank", label: "#", title: "Rank, as exported", numeric: true, visibility: "", width: "w-10", render: (p) => <span className="text-faint">{p.rank}</span> },
  {
    key: "fielder",
    label: "Fielder",
    title: "Fielder",
    numeric: false,
    visibility: "",
    width: "",
    render: (p) => (
      <>
        <span className="font-medium text-text">{p.fielder}</span>
        {/* Role rides under the name until its own column appears at lg. */}
        <span className="block text-[11px] leading-4 text-faint lg:hidden">{p.role}</span>
      </>
    ),
  },
  { key: "role", label: "Role", title: "Role", numeric: false, visibility: "hidden lg:table-cell", width: "w-24", render: (p) => <span className="text-muted">{p.role}</span> },
  // Mostly whole numbers, so padding its few fractions would push the column's
  // digits away from its right-aligned header. Right-aligned as exported.
  { key: "balls_in_field", label: "Balls", title: "Balls in field", numeric: true, visibility: "hidden sm:table-cell", width: "w-24", render: (p) => <Figure value={p.balls_in_field} /> },
  { key: "catches", label: "Catches", title: "Catches", numeric: true, visibility: "hidden sm:table-cell", width: "w-20", render: (p) => <Figure value={p.catches} /> },
  { key: "run_outs", label: "Run outs", title: "Run outs", numeric: true, visibility: "hidden md:table-cell", width: "w-20", render: (p) => <Figure value={p.run_outs} /> },
  { key: "stumpings", label: "Stumpings", title: "Stumpings", numeric: true, visibility: "hidden md:table-cell", width: "w-24", render: (p) => <Figure value={p.stumpings} /> },
  { key: "fraa", label: "FRAA", title: "Fielding runs above average", numeric: true, visibility: "", width: "w-24", render: (p) => <Figure value={p.fraa} places={3} signed /> },
  { key: "fraa_per_100", label: "FRAA/100", title: "FRAA per 100 balls in field", numeric: true, visibility: "", width: "w-24", render: (p) => <Figure value={p.fraa_per_100} places={3} signed /> },
];

export function Leaderboard() {
  const [players, setPlayers] = useState<Player[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>({ key: "rank", dir: "asc" });

  useEffect(() => {
    loadPlayers().then(setPlayers, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const rows = useMemo(() => {
    if (players === null) return [];
    const q = query.trim().toLowerCase();
    const sign = sort.dir === "asc" ? 1 : -1;
    return players
      .filter((p) => p.fielder.toLowerCase().includes(q))
      .sort((a, b) => sign * compare(a[sort.key], b[sort.key]) || a.rank - b.rank);
  }, [players, query, sort]);

  function onSort(column: Column) {
    setSort((s) =>
      s.key === column.key
        ? { key: s.key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key: column.key, dir: column.numeric && column.key !== "rank" ? "desc" : "asc" },
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-4 pb-16 pt-4 sm:px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-base font-semibold tracking-tight sm:text-lg">Fielding leaderboard</h1>
          <p className="text-[13px] text-muted">Qualified IPL fielders. FRAA: fielding runs above average.</p>
        </div>
        <div className="flex items-center gap-3">
          <label htmlFor="search" className="sr-only">
            Search fielders by name
          </label>
          <input
            id="search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search fielder"
            autoComplete="off"
            spellCheck={false}
            className="h-8 w-full rounded border border-border bg-panel px-2.5 text-[13px] text-text placeholder:text-faint focus:border-amber focus:outline-none sm:w-56"
          />
          <span className="shrink-0 text-xs tabular-nums text-faint">
            {players !== null && `${rows.length} of ${players.length}`}
          </span>
        </div>
      </div>

      {error !== null ? (
        <div role="alert" className="mt-4 rounded border border-negative bg-panel p-4 text-[13px]">
          <p className="font-semibold text-negative">Could not load players.json</p>
          <p className="mt-1 font-mono text-muted">{error}</p>
        </div>
      ) : players === null ? (
        <p className="mt-4 text-[13px] text-faint">Loading players.json…</p>
      ) : (
        <>
          <table className="mt-3 w-full border-collapse text-[13px] tabular-nums">
            <thead>
              <tr>
                {COLUMNS.map((c) => {
                  const active = sort.key === c.key;
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                      className={`${c.visibility} ${c.width} sticky top-0 z-10 bg-bg px-2 font-medium shadow-[inset_0_-1px_0_#242C38] ${c.numeric ? "text-right" : "text-left"}`}
                    >
                      <button
                        type="button"
                        onClick={() => onSort(c)}
                        title={c.title}
                        className={`inline-flex h-8 items-center gap-1 whitespace-nowrap text-[11px] uppercase tracking-wider ${c.numeric ? "flex-row-reverse" : ""} ${active ? "text-text" : "text-muted hover:text-text"}`}
                      >
                        {c.label}
                        <span aria-hidden className={active ? "text-amber" : "invisible"}>
                          {sort.dir === "asc" ? "▲" : "▼"}
                        </span>
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.slug} className="border-b border-border/60 hover:bg-panel2">
                  {COLUMNS.map((c) => (
                    <td key={c.key} className={`${c.visibility} px-2 py-1.5 align-top ${c.numeric ? "text-right" : "text-left"}`}>
                      {c.render(p)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-4 text-[13px] text-muted">No fielder matches “{query.trim()}”.</p>}
        </>
      )}
    </main>
  );
}

function compare(x: string | number, y: string | number): number {
  return typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
}

// Shows the exported number's own digits. Missing trailing zeros are padded
// invisibly so decimal points line up; nothing is rounded, and a fraction
// longer than `places` is shown whole.
function Figure({ value, places = 0, signed = false }: { value: number; places?: number; signed?: boolean }) {
  const text = String(value);
  const fraction = text.split(".")[1] ?? "";
  const pad = places > fraction.length ? `${fraction ? "" : "."}${"0".repeat(places - fraction.length)}` : "";
  const tone = !signed || value === 0 ? "" : value > 0 ? "text-positive" : "text-negative";
  return (
    <span className={tone}>
      {signed && value > 0 ? "+" : ""}
      {text}
      {pad && (
        <span aria-hidden className="invisible select-none">
          {pad}
        </span>
      )}
    </span>
  );
}
