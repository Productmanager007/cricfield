"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Season } from "@/lib/seasons";

// The one chart: raw FRAA/100 per common season, two series. Bars read
// `fraa_per_100_raw` as exported. The only arithmetic here maps values to
// pixels and picks round axis ticks; no value is derived.

export type ChartSeries = { side: "a" | "b"; name: string; colour: string; seasons: Season[] };

const TOP = 12;
const PLOT = 200;
const X_AXIS = 26;
const LEFT = 44;
const RIGHT = 6;
const BAR_MAX = 24;
const GAP = 2;
const RADIUS = 4;
const GRID = "#242C38";
const BASELINE = "#5A636D";
const INK_MUTED = "#8B949E";

export function SeasonChart({ years, series, threshold }: { years: number[]; series: [ChartSeries, ChartSeries]; threshold: number }) {
  const uid = useId().replace(/:/g, "");
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const bySeason = series.map((s) => new Map(s.seasons.map((row) => [row.season, row])));
  const values = series.flatMap((s) => s.seasons.map((row) => row.fraa_per_100_raw)).filter((v): v is number => v !== null);
  const scale = niceScale(Math.min(0, ...values), Math.max(0, ...values));
  const plotWidth = Math.max(0, width - LEFT - RIGHT);
  const band = years.length > 0 ? plotWidth / years.length : 0;
  const barWidth = Math.max(2, Math.min(BAR_MAX, (band * 0.72 - GAP) / 2));
  const y = (v: number) => TOP + ((scale.max - v) / (scale.max - scale.min)) * PLOT;
  const zero = y(0);
  const labelEvery = band >= 16 ? 1 : 2;
  const yearLabel = (year: number) => (band >= 32 ? String(year) : `’${String(year).slice(2)}`);
  const hasNull = series.some((s) => s.seasons.some((row) => row.fraa_per_100_raw === null));
  const hasLow = series.some((s) => s.seasons.some((row) => !row.qualifies));
  const height = TOP + PLOT + X_AXIS;

  return (
    <figure className="mt-4">
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted">
        <span className="font-medium text-text">Raw FRAA/100 by season · unshrunk</span>
        {series.map((s) => (
          <span key={s.side} className="inline-flex items-center gap-1.5">
            <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: s.colour }} />
            {s.name}
          </span>
        ))}
        {hasLow && (
          <span className="inline-flex items-center gap-1.5">
            <svg aria-hidden width="14" height="10">
              <rect width="14" height="10" rx="2" fill={INK_MUTED} fillOpacity="0.25" />
              <path d="M-2,12 L12,-2 M4,12 L18,-2" stroke={INK_MUTED} strokeWidth="1.5" />
            </svg>
            <span>
              Low sample: under <span className="tabular-nums">{threshold}</span> balls
            </span>
          </span>
        )}
        {hasNull && <span>No bar: no balls in field that season</span>}
      </figcaption>

      <div ref={box} className="relative mt-2" style={{ height }}>
        {width > 0 && (
          <svg data-chart width={width} height={height} className="block overflow-visible">
            <defs>
              {series.map((s) => (
                <pattern key={s.side} id={`${uid}-hatch-${s.side}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(135)">
                  <rect width="6" height="6" fill={s.colour} fillOpacity="0.22" />
                  <rect width="2" height="6" fill={s.colour} />
                </pattern>
              ))}
            </defs>

            {scale.ticks.map((t) => (
              <g key={t}>
                <line x1={LEFT} x2={width - RIGHT} y1={y(t)} y2={y(t)} stroke={t === 0 ? BASELINE : GRID} strokeWidth="1" shapeRendering="crispEdges" />
                <text x={LEFT - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill={INK_MUTED} style={{ fontVariantNumeric: "tabular-nums" }}>
                  {formatTick(t)}
                </text>
              </g>
            ))}

            {years.map((year, i) => {
              const x0 = LEFT + i * band;
              const pairWidth = barWidth * 2 + GAP;
              const start = x0 + (band - pairWidth) / 2;
              return (
                <g key={year}>
                  {hover === i && <rect x={x0} y={TOP} width={band} height={PLOT} fill="#E6EDF3" fillOpacity="0.05" />}
                  {series.map((s, k) => {
                    const row = bySeason[k].get(year);
                    const x = start + k * (barWidth + GAP);
                    if (!row || row.fraa_per_100_raw === null) {
                      return <g key={s.side} data-series={s.side} data-season={year} data-null="true" />;
                    }
                    const d = barPath(x, barWidth, zero, y(row.fraa_per_100_raw));
                    return row.qualifies ? (
                      <path key={s.side} data-bar data-series={s.side} data-season={year} data-low-sample="false" d={d} fill={s.colour} />
                    ) : (
                      <path key={s.side} data-bar data-series={s.side} data-season={year} data-low-sample="true" d={d} fill={`url(#${uid}-hatch-${s.side})`} />
                    );
                  })}
                  {i % labelEvery === 0 && (
                    <text x={x0 + band / 2} y={TOP + PLOT + 17} textAnchor="middle" fontSize="11" fill={INK_MUTED} style={{ fontVariantNumeric: "tabular-nums" }}>
                      {yearLabel(year)}
                    </text>
                  )}
                  <rect
                    data-hit={year}
                    x={x0}
                    y={TOP}
                    width={band}
                    height={PLOT}
                    fill="transparent"
                    tabIndex={0}
                    aria-label={`${year}: ${series.map((s, k) => `${s.name} ${describe(bySeason[k].get(year))}`).join("; ")}`}
                    onPointerEnter={() => setHover(i)}
                    onPointerLeave={() => setHover((h) => (h === i ? null : h))}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover((h) => (h === i ? null : h))}
                    className="outline-none"
                  />
                </g>
              );
            })}
          </svg>
        )}

        {hover !== null && width > 0 && (
          <div
            data-tooltip
            role="status"
            className="pointer-events-none absolute z-10 w-48 rounded border border-border bg-panel2 px-2.5 py-2 text-[12px] shadow-lg"
            style={{ left: Math.max(0, Math.min(width - 192, LEFT + hover * band + band / 2 - 96)), top: 0 }}
          >
            <p className="font-medium tabular-nums text-text">{years[hover]}</p>
            {series.map((s, k) => {
              const row = bySeason[k].get(years[hover]);
              return (
                <p key={s.side} className="mt-1 flex items-center gap-2">
                  <span aria-hidden className="inline-block h-0.5 w-3" style={{ backgroundColor: s.colour }} />
                  <span className="font-semibold tabular-nums text-text">{valueText(row)}</span>
                  <span className="truncate text-muted">{s.name}</span>
                  {row && !row.qualifies && <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wider text-amber">low</span>}
                </p>
              );
            })}
          </div>
        )}
      </div>
    </figure>
  );
}

function valueText(row: Season | undefined): string {
  if (!row || row.fraa_per_100_raw === null) return "no field time";
  return row.fraa_per_100_raw > 0 ? `+${row.fraa_per_100_raw}` : String(row.fraa_per_100_raw);
}

function describe(row: Season | undefined): string {
  return `${valueText(row)}${row && !row.qualifies ? " (low sample)" : ""}`;
}

// A column with a 4px rounded end at the value and a square end at zero.
function barPath(x: number, w: number, base: number, end: number): string {
  const h = Math.abs(end - base);
  const r = Math.min(RADIUS, w / 2, h);
  if (h === 0) return `M${x},${base} H${x + w}`;
  if (end < base) {
    return `M${x},${base} V${end + r} Q${x},${end} ${x + r},${end} H${x + w - r} Q${x + w},${end} ${x + w},${end + r} V${base} Z`;
  }
  return `M${x},${base} V${end - r} Q${x},${end} ${x + r},${end} H${x + w - r} Q${x + w},${end} ${x + w},${end - r} V${base} Z`;
}

// Round tick values spanning [lo, hi], always including zero.
function niceScale(lo: number, hi: number): { min: number; max: number; ticks: number[] } {
  const span = hi - lo || 1;
  const rough = span / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? 10 * magnitude;
  const min = Math.floor(lo / step) * step;
  const max = Math.max(Math.ceil(hi / step) * step, min + step);
  const ticks: number[] = [];
  for (let t = min; t <= max + step / 2; t += step) ticks.push(Number(t.toFixed(10)));
  return { min, max, ticks };
}

function formatTick(t: number): string {
  return t > 0 ? `+${t}` : String(t);
}
