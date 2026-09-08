"""
Does a change to the model load on the era axis?

A change that looks small in aggregate can still be systematic along a time
boundary. The Impact Player field-time normalisation was the first such case:
overall Spearman between the old and new leaderboards was 0.998, which reads
as "nothing moved", while players whose careers are mostly post-2023 gained
roughly eighteen ranks each and pre-2023-only players lost a few. Both facts
were true at once, and only the second one mattered.

This script exists so the next change is checked with the same instrument
rather than a fresh scratchpad script whose definitions have quietly drifted.

Give it two leaderboard CSVs and the dataset they were built from:

    python scripts/era_effect.py --before old.csv --after new.csv \
        --data ipl_json.zip

It computes each player's share of field time on or after `--boundary` from
the raw deliveries, then reports how rank and rate changes correlate with that
share. Read-only: it reads CSVs and match data, and writes nothing.

Reading the output: a correlation near zero means the change was era-neutral.
A large positive `d_per100` correlation means later-era players gained. That
is not automatically wrong -- a correction to a bias that only affected one
era SHOULD load on that era -- but it must be a known consequence rather than
a discovered one, especially before stacking another era-sensitive change on
top.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cricfield.parse import load_deliveries  # noqa: E402

REQUIRED = ("fielder", "fraa_per_100", "balls_in_field")


def _load_board(path: str, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"{label} ({path}) is missing column(s): {', '.join(missing)}")
    # Rank from the values, not from row order -- a CSV may have been re-sorted.
    df = df.sort_values("fraa_per_100", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df[["fielder", "fraa_per_100", "balls_in_field", "rank"]]


def era_share(deliveries: pd.DataFrame, boundary: int) -> pd.DataFrame:
    """Each player's share of field time in seasons >= boundary."""
    d = deliveries.copy()
    d["season"] = pd.to_datetime(d["date"]).dt.year
    inn = (
        d.groupby(["match_id", "innings", "fielding_team", "season"])
        .agg(balls=("is_legal", "size"), xi=("fielding_xi", "first"))
        .reset_index()
        .explode("xi")
        .rename(columns={"xi": "fielder"})
    )
    inn = inn[inn["fielder"].notna()]
    tot = inn.groupby("fielder")["balls"].sum()
    late = inn[inn["season"] >= boundary].groupby("fielder")["balls"].sum()
    out = pd.DataFrame({"total": tot, "late": late}).fillna({"late": 0.0})
    out["late_share"] = out["late"] / out["total"]
    return out.reset_index()[["fielder", "late_share"]]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Era sensitivity of a model change.")
    p.add_argument("--before", required=True, help="leaderboard CSV, before the change")
    p.add_argument("--after", required=True, help="leaderboard CSV, after the change")
    p.add_argument("--data", required=True, help="the dataset both were built from")
    p.add_argument("--match-type", default="T20")
    p.add_argument("--boundary", type=int, default=2023,
                   help="first season of the later era (default 2023, Impact Player)")
    a = p.parse_args(argv)

    before = _load_board(a.before, "--before")
    after = _load_board(a.after, "--after")

    match_type = None if a.match_type.upper() == "ALL" else a.match_type
    print(f"Parsing {a.data} ...", file=sys.stderr)
    shares = era_share(load_deliveries(a.data, match_type=match_type), a.boundary)

    m = before.merge(after, on="fielder", suffixes=("_old", "_new")).merge(
        shares, on="fielder", how="left"
    )
    only_before = set(before["fielder"]) - set(after["fielder"])
    only_after = set(after["fielder"]) - set(before["fielder"])

    m["d_rank"] = m["rank_new"] - m["rank_old"]
    m["d_per100"] = m["fraa_per_100_new"] - m["fraa_per_100_old"]

    print(f"\n=== population ===\n")
    print(f"  before : {len(before):,} players")
    print(f"  after  : {len(after):,} players")
    print(f"  common : {len(m):,}")
    if only_before:
        print(f"  dropped out ({len(only_before)}): "
              f"{', '.join(sorted(only_before)[:8])}"
              f"{' ...' if len(only_before) > 8 else ''}")
    if only_after:
        print(f"  came in ({len(only_after)}): "
              f"{', '.join(sorted(only_after)[:8])}"
              f"{' ...' if len(only_after) > 8 else ''}")

    overall = spearmanr(m["fraa_per_100_old"], m["fraa_per_100_new"])
    print(f"\n=== overall agreement ===\n")
    print(f"  Spearman(old, new)   = {overall.statistic:.5f}")
    print(f"  mean |rank movement| = {m['d_rank'].abs().mean():.2f}")
    print(f"  max  |rank movement| = {int(m['d_rank'].abs().max())}")

    print(f"\n=== era effect (boundary {a.boundary}) ===\n")
    bands = pd.cut(
        m["late_share"], [-0.01, 0.001, 0.25, 0.75, 1.01],
        labels=[f"0% (pre-{a.boundary} only)", "0-25%", "25-75%",
                f">75% (mostly {a.boundary}+)"],
    )
    g = m.groupby(bands, observed=True).agg(
        n=("d_rank", "size"),
        mean_d_rank=("d_rank", "mean"),
        mean_abs_d_rank=("d_rank", lambda s: s.abs().mean()),
        mean_d_per100=("d_per100", "mean"),
    )
    print(g.round(4).to_string())

    r_rank = spearmanr(m["late_share"], m["d_rank"])
    r_rate = spearmanr(m["late_share"], m["d_per100"])
    print(f"\n  Spearman(late_share, d_rank)   = {r_rank.statistic:+.4f}  p={r_rank.pvalue:.3g}")
    print(f"  Spearman(late_share, d_per100) = {r_rate.statistic:+.4f}  p={r_rate.pvalue:.3g}")

    print(f"\n  biggest movers by |rank change|:")
    top = m.reindex(m["d_rank"].abs().sort_values(ascending=False).index).head(10)
    print(top[["fielder", "rank_old", "rank_new", "d_rank", "late_share"]]
          .round(3).to_string(index=False))

    strong = abs(r_rate.statistic) >= 0.3
    print(f"\n{'-' * 60}")
    print("Era-sensitive: the change moves later-era players differently."
          if strong else
          "Era-neutral on this measure.")
    print("This script reports; it does not judge whether that is correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
