"""
Standing data-quality sweep. Read-only: it reports, it never repairs.

Run this against any dataset before trusting a leaderboard built from it. The
checks exist because each one has already caught something real in the IPL
bundle, and because a silent data fault is far more expensive than a loud one.

  1. Parse warnings raised while loading.
  2. Match accounting -- .json entries in the archive vs matches parsed. A
     non-zero difference means matches were dropped without saying so.
  3. Fielding XI size per innings. Cricsheet includes substitutes and Impact
     Player replacements, so an XI can list 12 or 13 names. Every listed player
     is credited with the full innings of field time, which inflates the
     denominator in `field_time` and dilutes every expected-credit charge.
  4. Innings length, and per-player balls-per-innings. A player averaging more
     than a full innings is impossible and means the explode/merge has
     duplicated rows somewhere.
  5. A player appearing for two franchises in one season. Season is the
     calendar year of the first date in `info.dates`; IPL seasons do not
     straddle years, so the year is a safe proxy. A hit is a genuine
     mid-season transfer, a name collision in the Cricsheet registry, or a
     parse bug -- all three are worth knowing about, and a collision silently
     merges two careers into one row.

    python scripts/data_quality.py --data ipl_json.zip
"""

from __future__ import annotations

import argparse
import sys
import warnings
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cricfield.parse import load_deliveries  # noqa: E402

# A T20 innings is 120 legal balls; extras push the real figure a little higher.
# Anything above this per innings is structurally impossible, not merely odd.
MAX_BALLS_PER_INNINGS = 150


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Data-quality sweep. Reports only.")
    p.add_argument("--data", required=True, help="Cricsheet .zip or directory of .json")
    p.add_argument("--match-type", default="T20")
    p.add_argument("--gender", default=None)
    a = p.parse_args(argv)

    match_type = None if a.match_type.upper() == "ALL" else a.match_type
    findings = 0

    # --- 1. warnings during parse ---
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        d = load_deliveries(a.data, match_type=match_type, gender=a.gender)

    print("=== 1. warnings during load_deliveries ===")
    if caught:
        findings += 1
        seen: dict[str, int] = defaultdict(int)
        for w in caught:
            seen[f"{w.category.__name__}: {w.message}"] += 1
        for k, v in sorted(seen.items(), key=lambda x: -x[1]):
            print(f"  [{v}x] {k}")
    else:
        print("  none")

    # --- 2. match accounting ---
    print("\n=== 2. match accounting ===")
    parsed = d["match_id"].nunique()
    if str(a.data).lower().endswith(".zip"):
        entries = [n for n in zipfile.ZipFile(a.data).namelist() if n.endswith(".json")]
    else:
        entries = [str(f) for f in Path(a.data).glob("*.json")]
    diff = len(entries) - parsed
    print(f"  .json entries : {len(entries):,}")
    print(f"  parsed        : {parsed:,}")
    print(f"  difference    : {diff:,}")
    if diff:
        findings += 1
        print("  -> matches were dropped; filters or parse failures")

    print(f"\n  deliveries : {len(d):,} ({int(d['is_legal'].sum()):,} legal)")
    print(f"  date range : {d['date'].min()} .. {d['date'].max()}")

    # --- 3. fielding XI size ---
    inn = (
        d.groupby(["match_id", "innings", "fielding_team"])
        .agg(balls=("is_legal", "size"), xi=("fielding_xi", "first"))
        .reset_index()
    )
    inn["xi_size"] = inn["xi"].apply(lambda x: len(x) if x is not None else 0)
    print("\n=== 3. fielding XI size per innings ===")
    print(inn["xi_size"].value_counts().sort_index().to_string())
    oversized = int((inn["xi_size"] > 11).sum())
    if oversized:
        findings += 1
        print(f"  -> {oversized:,} innings ({oversized/len(inn):.1%}) list more than 11")
        print("     every listed player gets full field time, inflating the denominator")

    # --- 4. innings length and per-player field time ---
    print("\n=== 4. innings length ===")
    print(f"  min {inn['balls'].min()}  median {inn['balls'].median():.0f}  max {inn['balls'].max()}")

    ex = inn.explode("xi").rename(columns={"xi": "fielder"})
    ex = ex[ex["fielder"].notna()]
    per = (
        ex.groupby("fielder")
        .agg(balls_in_field=("balls", "sum"), innings=("balls", "size"))
        .reset_index()
    )
    per["balls_per_innings"] = per["balls_in_field"] / per["innings"]
    print(f"\n  balls per innings fielded: min {per['balls_per_innings'].min():.1f}  "
          f"median {per['balls_per_innings'].median():.1f}  "
          f"max {per['balls_per_innings'].max():.1f}")
    bad = per[per["balls_per_innings"] > MAX_BALLS_PER_INNINGS]
    if len(bad):
        findings += 1
        print(f"  -> {len(bad)} player(s) above {MAX_BALLS_PER_INNINGS}/innings (impossible):")
        print(bad.nlargest(10, "balls_per_innings").to_string(index=False))
    else:
        print(f"  no player exceeds {MAX_BALLS_PER_INNINGS} balls per innings")

    # --- 5. one player, two franchises, one season ---
    d = d.copy()
    d["season"] = pd.to_datetime(d["date"]).dt.year
    sx = (
        d.groupby(["match_id", "innings", "fielding_team", "season"])
        .agg(xi=("fielding_xi", "first"))
        .reset_index()
        .explode("xi")
        .rename(columns={"xi": "fielder"})
    )
    sx = sx[sx["fielder"].notna()]
    multi = (
        sx.groupby(["fielder", "season"])["fielding_team"]
        .nunique()
        .reset_index(name="n_teams")
    )
    multi = multi[multi["n_teams"] > 1].sort_values(["season", "fielder"])

    print("\n=== 5. players on >1 franchise in one season ===")
    print("  (season = calendar year of the first date; IPL seasons do not straddle years)")
    if len(multi):
        findings += 1
        rows = []
        for r in multi.itertuples(index=False):
            teams = sorted(
                sx[(sx["fielder"] == r.fielder) & (sx["season"] == r.season)][
                    "fielding_team"
                ].unique()
            )
            rows.append({"fielder": r.fielder, "season": r.season,
                         "teams": " | ".join(teams)})
        with pd.option_context("display.width", 250, "display.max_colwidth", 90):
            print(pd.DataFrame(rows).to_string(index=False))
        print("  -> transfer, registry name collision, or parse bug. A collision")
        print("     merges two careers into one row without complaining.")
    else:
        print("  none")

    print(f"\n{'-' * 58}")
    print(f"{findings} check(s) raised something. This script reports only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
