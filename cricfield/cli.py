"""
Command line entrypoint.

    python -m cricfield.cli --data ipl_json.zip --out leaderboard.csv
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from .fielding import fielding_leaderboard
from .parse import load_deliveries, match_outcomes
from .value import RunExpectancy, WinProbability


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fielding Runs Above Average, from Cricsheet data.")
    p.add_argument("--data", required=True, help="Cricsheet .zip or directory of .json")
    p.add_argument("--match-type", default="T20", help="T20 / ODI / IT20 / Test / MDM, or ALL")
    p.add_argument("--gender", default=None, help="male / female (default: both)")
    p.add_argument("--max-matches", type=int, default=None)
    p.add_argument("--min-balls", type=int, default=600, help="minimum field time to qualify")
    p.add_argument("--regression-balls", type=int, default=1200)
    p.add_argument("--out", default="fielding_leaderboard.csv")
    p.add_argument("--top", type=int, default=20)
    a = p.parse_args(argv)

    match_type = None if a.match_type.upper() == "ALL" else a.match_type

    print(f"Parsing {a.data} ...", file=sys.stderr)
    deliveries = load_deliveries(
        a.data, match_type=match_type, gender=a.gender, max_matches=a.max_matches
    )
    n_matches = deliveries["match_id"].nunique()
    print(f"  {len(deliveries):,} deliveries across {n_matches:,} matches", file=sys.stderr)

    print("Fitting run expectancy ...", file=sys.stderr)
    run_model = RunExpectancy().fit(deliveries)

    wp_model = None
    try:
        print("Fitting win probability ...", file=sys.stderr)
        wp_model = WinProbability().fit(deliveries, match_outcomes(a.data, match_type))
    except ValueError as e:
        print(f"  skipped: {e}", file=sys.stderr)

    print("Scoring fielders ...", file=sys.stderr)
    board = fielding_leaderboard(
        deliveries,
        run_model,
        wp_model,
        min_balls=a.min_balls,
        regression_balls=a.regression_balls,
    )
    board.to_csv(a.out, index=False)

    show = [
        "fielder", "role", "balls_in_field", "catches", "run_outs",
        "stumpings", "runs_saved", "fraa", "fraa_per_100",
    ]
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print(f"\nTop {a.top} by FRAA per 100 balls in the field\n")
        print(board[show].head(a.top).to_string(index=False))
        print(f"\nBottom 5\n")
        print(board[show].tail(5).to_string(index=False))
    print(f"\nFull table -> {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
