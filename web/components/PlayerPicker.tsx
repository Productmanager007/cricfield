"use client";

import { useEffect, useId, useMemo, useState } from "react";
import type { Player } from "@/lib/players";

const SHOWN = 8;

// Search-to-pick. Matching is the leaderboard's: a case-insensitive substring
// of the fielder's name, trimmed, listed in exported rank order.
export function PlayerPicker({
  id,
  label,
  colour,
  players,
  selected,
  exclude,
  onSelect,
}: {
  id: string;
  label: string;
  colour: string;
  players: Player[];
  selected: Player | null;
  // The other side's pick, so one player cannot be compared with themselves.
  exclude: string | null;
  onSelect: (slug: string) => void;
}) {
  const listId = useId();
  const [query, setQuery] = useState(selected?.fielder ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    setQuery(selected?.fielder ?? "");
  }, [selected]);

  const q = query.trim().toLowerCase();
  const matches = useMemo(
    () => (q === "" ? [] : players.filter((p) => p.slug !== exclude && p.fielder.toLowerCase().includes(q))),
    [players, q, exclude],
  );
  const shown = matches.slice(0, SHOWN);
  const listOpen = open && q !== "" && query !== selected?.fielder;

  function choose(p: Player) {
    onSelect(p.slug);
    setQuery(p.fielder);
    setOpen(false);
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted">
        <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: colour }} />
        {label}
      </label>
      <input
        id={id}
        type="search"
        role="combobox"
        aria-expanded={listOpen}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={listOpen && shown[active] ? `${listId}-${active}` : undefined}
        value={query}
        placeholder="Search fielder"
        autoComplete="off"
        spellCheck={false}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (!listOpen) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, shown.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter" && shown[active]) {
            e.preventDefault();
            choose(shown[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        className="mt-1 h-9 w-full rounded border border-border bg-panel px-2.5 text-[13px] text-text placeholder:text-faint focus:border-amber focus:outline-none"
      />
      {listOpen && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-80 w-full overflow-y-auto rounded border border-border bg-panel2 py-1 text-[13px] shadow-lg"
        >
          {shown.map((p, i) => (
            <li
              key={p.slug}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              // Keep focus in the input so blur does not close the list before the click lands.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(p)}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-baseline justify-between gap-3 px-2.5 py-1.5 ${i === active ? "bg-border" : ""}`}
            >
              <span className="text-text">{p.fielder}</span>
              <span className="shrink-0 text-[11px] tabular-nums text-faint">
                #{p.rank} · {p.role}
              </span>
            </li>
          ))}
          {matches.length === 0 && <li className="px-2.5 py-1.5 text-faint">No fielder matches “{query.trim()}”.</li>}
          {matches.length > shown.length && (
            <li className="px-2.5 py-1 text-[11px] text-faint">{matches.length - shown.length} more — keep typing</li>
          )}
        </ul>
      )}
    </div>
  );
}
