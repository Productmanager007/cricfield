"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Season } from "@/lib/seasons";

// The one chart: raw FRAA/100 per common season, two series. Bars read
// `fraa_per_100_raw` as exported. The only arithmetic here maps values to
// pixels and picks round axis ticks; no value is derived.
//
// The axis is scaled to qualifying seasons. The model reads a low-sample
// season's rate as noise, so that season must not set the scale every other
// bar is measured against: one 108-ball season at +12.13 otherwise flattens a
// career of seasons near ±0.5 to a few pixels each. A low-sample value may
// stretch the axis by one gridline. Past that, its bar runs beyond the axis
// into a margin, is cut with a break mark, and carries its exact value at the
// tip. Every season is still drawn and every value is still readable.

export type ChartSeries = { side: "a" | "b"; name: string; colour: string; seasons: Season[] };

const TOP = 12;
const PLOT = 200;
const X_AXIS = 26;
const LEFT = 44;
const RIGHT = 6;
const OVER = 28; // margin a cut bar runs into, above or below the plot
const OVERRUN = 14; // how far a cut bar extends past the axis
const BAR_MAX = 24;
const GAP = 2;
const RADIUS = 4;
const SURFACE = "#0D1117";
const GRID = "#242C38";
const BASELINE = "#5A636D";
const INK = "#E6EDF3";
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
  const rated = series.flatMap((s) => s.seasons).filter((row) => row.fraa_per_100_raw !== null);
  const axis = axisFor(rated);
  const beyond = (v: number) => (v > axis.max ? 1 : v < axis.min ? -1 : 0);
  const cutUp = rated.some((row) => beyond(row.fraa_per_100_raw as number) === 1);
  const cutDown = rated.some((row) => beyond(row.fraa_per_100_raw as number) === -1);

  const plotTop = TOP + (cutUp ? OVER : 0);
  const plotBottom = plotTop + PLOT;
  const height = plotBottom + (cutDown ? OVER : 0) + X_AXIS;
  const plotWidth = Math.max(0, width - LEFT - RIGHT);
  const band = years.length > 0 ? plotWidth / years.length : 0;
  const barWidth = Math.max(2, Math.min(BAR_MAX, (band * 0.72 - GAP) / 2));
  const y = (v: number) => plotTop + ((axis.max - v) / (axis.max - axis.min)) * PLOT;
  const zero = y(0);
  // A "’08" label is about 18px wide at 11px; below 20px per season they touch.
  const labelEvery = band >= 20 ? 1 : 2;
  const yearLabel = (year: number) => (band >= 32 ? String(year) : `’${String(year).slice(2)}`);
  const hasNull = series.some((s) => s.seasons.some((row) => row.fraa_per_100_raw === null));
  const hasLow = series.some((s) => s.seasons.some((row) => !row.qualifies));
  const hitTop = TOP;
  const hitHeight = height - X_AXIS - TOP;

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
        {(cutUp || cutDown) && (
          <span className="inline-flex items-center gap-1.5">
            <svg aria-hidden width="10" height="14">
              <rect x="2" width="6" height="14" rx="1" fill={INK_MUTED} fillOpacity="0.6" />
              <path d="M0,6.5 L10,4 M0,10 L10,7.5" stroke={SURFACE} strokeWidth="1.5" />
            </svg>
            <span>Cut bar: a low-sample rate past the axis, value printed at its tip</span>
          </span>
        )}
        {hasNull && <span>No bar: no balls in field that season</span>}
      </figcaption>
      {(cutUp || cutDown) && (
        <p className="mt-1 text-[12px] text-faint">The axis is scaled to qualifying seasons, so a thin season cannot set it.</p>
      )}

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

            {axis.ticks.map((t) => (
              <g key={t}>
                <line x1={LEFT} x2={width - RIGHT} y1={y(t)} y2={y(t)} stroke={t === 0 ? BASELINE : GRID} strokeWidth="1" shapeRendering="crispEdges" />
                <text x={LEFT - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill={INK_MUTED} style={{ fontVariantNumeric: "tabular-nums" }}>
                  {signed(t)}
                </text>
              </g>
            ))}

            {years.map((year, i) => {
              const x0 = LEFT + i * band;
              const start = x0 + (band - (barWidth * 2 + GAP)) / 2;
              return (
                <g key={year}>
                  {hover === i && <rect x={x0} y={hitTop} width={band} height={hitHeight} fill={INK} fillOpacity="0.05" />}
                  {series.map((s, k) => {
                    const row = bySeason[k].get(year);
                    const x = start + k * (barWidth + GAP);
                    if (!row || row.fraa_per_100_raw === null) {
                      return <g key={s.side} data-series={s.side} data-season={year} data-null="true" />;
                    }
                    const direction = beyond(row.fraa_per_100_raw);
                    const end = direction === 1 ? plotTop - OVERRUN : direction === -1 ? plotBottom + OVERRUN : y(row.fraa_per_100_raw);
                    const fill = row.qualifies ? s.colour : `url(#${uid}-hatch-${s.side})`;
                    return (
                      <g key={s.side}>
                        <path
                          data-bar
                          data-series={s.side}
                          data-season={year}
                          data-low-sample={row.qualifies ? "false" : "true"}
                          data-overflow={direction === 0 ? "false" : "true"}
                          d={barPath(x, barWidth, zero, end)}
                          fill={fill}
                        />
                        {direction !== 0 && (
                          <>
                            <path
                              d={breakMark(x, barWidth, direction === 1 ? plotTop - 3 : plotBottom + 3, direction)}
                              stroke={SURFACE}
                              strokeWidth="1.5"
                              fill="none"
                            />
                            <text
                              data-overflow-label
                              x={x + barWidth / 2}
                              y={direction === 1 ? end - 4 : end + 11}
                              textAnchor="middle"
                              fontSize="10"
                              fill={INK}
                              style={{ fontVariantNumeric: "tabular-nums" }}
                            >
                              {valueText(row)}
                            </text>
                          </>
                        )}
                      </g>
                    );
                  })}
                  {i % labelEvery === 0 && (
                    <text x={x0 + band / 2} y={height - X_AXIS + 17} textAnchor="middle" fontSize="11" fill={INK_MUTED} style={{ fontVariantNumeric: "tabular-nums" }}>
                      {yearLabel(year)}
                    </text>
                  )}
                  <rect
                    data-hit={year}
                    x={x0}
                    y={hitTop}
                    width={band}
                    height={hitHeight}
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

// Round ticks over the qualifying seasons (all seasons if none qualify), then
// at most one extra gridline each way for a low-sample value just past them.
function axisFor(rows: Season[]): { min: number; max: number; ticks: number[] } {
  const value = (row: Season) => row.fraa_per_100_raw as number;
  const qualifying = rows.filter((row) => row.qualifies).map(value);
  const basis = qualifying.length > 0 ? qualifying : rows.map(value);
  let { min, max, step } = niceScale(Math.min(0, ...basis), Math.max(0, ...basis));
  const low = rows.filter((row) => !row.qualifies).map(value);
  if (low.some((v) => v < min && v >= min - step)) min = tidy(min - step);
  if (low.some((v) => v > max && v <= max + step)) max = tidy(max + step);
  const ticks: number[] = [];
  for (let t = min; t <= max + step / 2; t += step) ticks.push(tidy(t));
  return { min, max, ticks };
}

function niceScale(lo: number, hi: number): { min: number; max: number; step: number } {
  const span = hi - lo || 1;
  const rough = span / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? 10 * magnitude;
  const min = tidy(Math.floor(lo / step) * step);
  const max = tidy(Math.max(Math.ceil(hi / step) * step, min + step));
  return { min, max, step };
}

const tidy = (n: number) => Number(n.toFixed(10));

function signed(n: number): string {
  return n > 0 ? `+${n}` : String(n);
}

function valueText(row: Season | undefined): string {
  if (!row || row.fraa_per_100_raw === null) return "no field time";
  return signed(row.fraa_per_100_raw);
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

// Two slanted surface-coloured strokes across a bar, just past the axis.
function breakMark(x: number, w: number, at: number, direction: number): string {
  const next = at - direction * 3.5;
  return `M${x - 1},${at + 1.5} L${x + w + 1},${at - 1.5} M${x - 1},${next + 1.5} L${x + w + 1},${next - 1.5}`;
}
