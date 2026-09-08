"""
How much of the leaderboard is the data, and how much is my assumptions?

The credit shares in fielding.py are judgement calls. Before anyone acts on
a ranking, they are entitled to know whether it survives a reasonable
change to those calls. This script re-runs the model under several credit
regimes and reports how much the order moves.

If the top of the table reshuffles the moment you nudge the run-out share,
the honest headline is "we measure run-out involvement", not "we measure
fielding".

    python sensitivity.py --data sample_data
"""

from __future__ import annotations

import argparse

import pandas as pd
from scipy.stats import spearmanr

from cricfield import fielding
from cricfield.fielding import fielding_leaderboard
from cricfield.parse import load_deliveries, match_outcomes
from cricfield.value import RunExpectancy, WinProbability

REGIMES: dict[str, dict[str, float]] = {
    "baseline":        {"caught": 0.30, "stumped": 0.40, "run out": 0.90},
    "catch-heavy":     {"caught": 0.50, "stumped": 0.50, "run out": 0.90},
    "runout-light":    {"caught": 0.30, "stumped": 0.40, "run out": 0.50},
    "flat":            {"caught": 0.40, "stumped": 0.40, "run out": 0.40},
    "bowler-generous": {"caught": 0.15, "stumped": 0.25, "run out": 0.80},
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--match-type", default="T20")
    p.add_argument("--min-balls", type=int, default=600)
    p.add_argument("--top", type=int, default=10)
    a = p.parse_args()

    deliveries = load_deliveries(a.data, match_type=a.match_type)
    run_model = RunExpectancy().fit(deliveries)
    try:
        wp_model = WinProbability().fit(deliveries, match_outcomes(a.data, a.match_type))
    except ValueError:
        wp_model = None

    boards: dict[str, pd.DataFrame] = {}
    original = dict(fielding.CREDIT_SHARE)
    for name, shares in REGIMES.items():
        fielding.CREDIT_SHARE.update(original)
        fielding.CREDIT_SHARE.update(shares)
        boards[name] = fielding_leaderboard(
            deliveries, run_model, wp_model, min_balls=a.min_balls
        ).set_index("fielder")["fraa_per_100"]
    fielding.CREDIT_SHARE.update(original)

    print("\nRank correlation with baseline (Spearman)\n")
    base = boards["baseline"]
    for name, s in boards.items():
        joined = pd.concat([base, s], axis=1, keys=["base", "alt"]).dropna()
        rho = spearmanr(joined["base"], joined["alt"]).statistic
        print(f"  {name:<18} rho = {rho:.3f}")

    print(f"\nTop {a.top} under each regime\n")
    top = pd.DataFrame(
        {name: s.sort_values(ascending=False).head(a.top).index.tolist()
         for name, s in boards.items()}
    )
    top.index = [f"#{i+1}" for i in range(len(top))]
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(top.to_string())

    always = set.intersection(*[set(top[c]) for c in top.columns])
    print(
        f"\nIn every regime's top {a.top}: "
        f"{', '.join(sorted(always)) if always else '(nobody -- the ranking is assumption-driven)'}"
    )


if __name__ == "__main__":
    main()
