"""
Does FRAA carry residual team structure?

THE CONCERN
-----------
`fielding.py` charges every player an expected share of credit proportional to
balls in the field:

    expected_runs_saved = runs_per_ball[role] * balls_in_field

That baseline assumes chances arrive uniformly per ball fielded, at a rate set
only by the player's role. It does not condition on who was bowling. If one
attack generates more edges, more stumping chances, or more pressure run-outs
than another, then its fielders accrue credit they did not individually earn,
and FRAA is measuring the bowling attack through them.

WHAT THIS SCRIPT DOES
---------------------
Measurement, not repair. For each fielding team it reports:

  * total balls fielded (team innings length, not summed across the XI)
  * credited dismissals per 1000 balls fielded -- the opportunity rate
  * mean FRAA of its qualified fielders
  * the spread of those FRAA values

Then it compares the spread of team means against the pooled within-team
spread. If team means are tightly clustered relative to the noise between
players, the uniform baseline is defensible on this dataset. If they separate,
the baseline needs conditioning on the bowling side.

This script reads the model; it does not change it.

    python scripts/diagnose_baseline.py --data sample_data --min-balls 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cricfield.fielding import CREDIT_SHARE, fielding_leaderboard  # noqa: E402
from cricfield.parse import load_deliveries  # noqa: E402
from cricfield.value import RunExpectancy  # noqa: E402


def credited_kinds() -> set[str]:
    """Dismissal kinds that put runs on a fielder's account."""
    return {k for k, v in CREDIT_SHARE.items() if v > 0}


def team_balls_fielded(deliveries: pd.DataFrame) -> pd.DataFrame:
    """
    Balls each team spent in the field.

    One row per (match, innings, fielding team) collapsed to a team total. This
    is the innings length -- NOT the per-player figure in fielding.py, which
    repeats each innings across all eleven fielders.
    """
    per_innings = (
        deliveries.groupby(["match_id", "innings", "fielding_team"])
        .agg(balls=("is_legal", "size"))
        .reset_index()
    )
    return (
        per_innings.groupby("fielding_team")
        .agg(
            balls_fielded=("balls", "sum"),
            innings_fielded=("balls", "size"),
        )
        .reset_index()
    )


def team_credited_dismissals(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Count of dismissals that carry fielder credit, per fielding team."""
    kinds = credited_kinds()
    w = deliveries[deliveries["wicket"]].copy()
    w["has_fielder"] = w["fielders"].apply(lambda f: bool(f) and len(f) > 0)
    w["is_credited"] = w["dismissal_kind"].isin(kinds) & w["has_fielder"]
    return (
        w.groupby("fielding_team")
        .agg(
            wickets=("wicket", "size"),
            credited_dismissals=("is_credited", "sum"),
        )
        .reset_index()
    )


def fielder_primary_team(deliveries: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each fielder to the team they fielded most balls for.

    Cricsheet substitutes can appear for a side they are not squadded to, so
    this is modal, not definitional. `team_share` exposes how clean the
    assignment is; anything well below 1.0 means the player is split.
    """
    inn = (
        deliveries.groupby(["match_id", "innings", "fielding_team"])
        .agg(balls=("is_legal", "size"), fielding_xi=("fielding_xi", "first"))
        .reset_index()
    )
    inn = inn.explode("fielding_xi").rename(columns={"fielding_xi": "fielder"})
    inn = inn[inn["fielder"].notna()]

    by_team = (
        inn.groupby(["fielder", "fielding_team"])
        .agg(balls=("balls", "sum"))
        .reset_index()
    )
    total = by_team.groupby("fielder")["balls"].transform("sum")
    by_team["team_share"] = by_team["balls"] / total

    idx = by_team.groupby("fielder")["balls"].idxmax()
    return by_team.loc[idx, ["fielder", "fielding_team", "team_share"]].reset_index(
        drop=True
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Measure residual team structure in FRAA."
    )
    p.add_argument("--data", required=True, help="Cricsheet .zip or directory of .json")
    p.add_argument("--match-type", default="T20")
    p.add_argument("--gender", default=None)
    p.add_argument("--max-matches", type=int, default=None)
    p.add_argument("--min-balls", type=int, default=600)
    p.add_argument("--regression-balls", type=int, default=1200)
    p.add_argument("--out", default=None, help="optional CSV of the team table")
    a = p.parse_args(argv)

    match_type = None if a.match_type.upper() == "ALL" else a.match_type

    print(f"Parsing {a.data} ...", file=sys.stderr)
    deliveries = load_deliveries(
        a.data, match_type=match_type, gender=a.gender, max_matches=a.max_matches
    )
    print(
        f"  {len(deliveries):,} deliveries across "
        f"{deliveries['match_id'].nunique():,} matches",
        file=sys.stderr,
    )

    print("Fitting run expectancy ...", file=sys.stderr)
    run_model = RunExpectancy().fit(deliveries)

    print("Scoring fielders ...", file=sys.stderr)
    board = fielding_leaderboard(
        deliveries,
        run_model,
        None,
        min_balls=a.min_balls,
        regression_balls=a.regression_balls,
    )

    # --- assemble the team table -------------------------------------------
    balls = team_balls_fielded(deliveries)
    dismissals = team_credited_dismissals(deliveries)
    teams = balls.merge(dismissals, on="fielding_team", how="left")
    teams["credited_per_1000"] = (
        teams["credited_dismissals"] / teams["balls_fielded"] * 1000
    )

    assign = fielder_primary_team(deliveries)
    qualified = board.merge(assign, on="fielder", how="left")

    agg = (
        qualified.groupby("fielding_team")
        .agg(
            qualified_fielders=("fraa", "size"),
            mean_fraa=("fraa", "mean"),
            sd_fraa=("fraa", "std"),
            min_fraa=("fraa", "min"),
            max_fraa=("fraa", "max"),
        )
        .reset_index()
    )
    agg["range_fraa"] = agg["max_fraa"] - agg["min_fraa"]

    table = teams.merge(agg, on="fielding_team", how="left").sort_values(
        "mean_fraa", ascending=False
    )

    show = [
        "fielding_team",
        "balls_fielded",
        "credited_dismissals",
        "credited_per_1000",
        "qualified_fielders",
        "mean_fraa",
        "sd_fraa",
        "min_fraa",
        "max_fraa",
    ]
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print("\nFRAA by fielding team\n")
        print(table[show].round(3).to_string(index=False))

    # --- the actual question -----------------------------------------------
    between = float(np.std(table["mean_fraa"].dropna(), ddof=1))
    within = float(np.sqrt(np.nanmean(np.square(table["sd_fraa"].dropna()))))
    ratio = between / within if within else float("nan")
    spread = float(table["credited_per_1000"].max() - table["credited_per_1000"].min())
    rel = spread / float(table["credited_per_1000"].mean())

    print("\n" + "-" * 62)
    print("Opportunity rate spread (credited dismissals per 1000 balls)")
    print(f"  min {table['credited_per_1000'].min():.3f}   "
          f"max {table['credited_per_1000'].max():.3f}   "
          f"spread {spread:.3f} ({rel:.1%} of mean)")
    print("\nTeam structure in FRAA")
    print(f"  SD of team mean FRAA (between teams) : {between:.3f}")
    print(f"  pooled SD within teams               : {within:.3f}")
    print(f"  ratio between/within                 : {ratio:.3f}")
    print("-" * 62)
    print(
        "\nA ratio near zero means team means are indistinguishable against\n"
        "player-level noise, and the uniform baseline survives on this data.\n"
        "A large ratio means FRAA is partly measuring the bowling attack and\n"
        "the expected-credit baseline needs conditioning on the bowling side.\n"
        "This script does not decide the threshold; it reports the numbers."
    )

    if a.out:
        table.to_csv(a.out, index=False)
        print(f"Team table -> {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
