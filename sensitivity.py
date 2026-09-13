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

# The regime every other one is compared against.
BASELINE = "baseline"

# The shares the regimes vary. Any other dismissal kind keeps whatever
# fielding.CREDIT_SHARE gives it, in every regime.
VARIED = ("caught", "stumped", "run out")

# Deliberate perturbations of the model's shares, not copies of them: each one
# is an argument someone could make about how much of a wicket the fielder
# earned. These are the judgement calls being tested, so they stay literal.
ALTERNATIVES: dict[str, dict[str, float]] = {
    "catch-heavy":     {"caught": 0.50, "stumped": 0.50, "run out": 0.90},
    "runout-light":    {"caught": 0.30, "stumped": 0.40, "run out": 0.50},
    "flat":            {"caught": 0.40, "stumped": 0.40, "run out": 0.40},
    "bowler-generous": {"caught": 0.15, "stumped": 0.25, "run out": 0.80},
}


def _baseline_shares() -> dict[str, float]:
    """
    The model's own shares, read from fielding rather than restated.

    Every correlation below is measured against the baseline, so the baseline
    has to BE the model. Written out here once, it would go stale the first
    time CREDIT_SHARE changed, and "correlation with baseline" would quietly
    mean correlation with the shares the model used to have.
    """
    return {kind: fielding.CREDIT_SHARE[kind] for kind in VARIED}


REGIMES: dict[str, dict[str, float]] = {BASELINE: _baseline_shares(), **ALTERNATIVES}


def _assert_baseline_is_the_model() -> None:
    """Fail loudly if a refactor ever detaches the baseline from the model."""
    current = _baseline_shares()
    if REGIMES[BASELINE] != current:
        raise ValueError(
            "sensitivity: the baseline regime has diverged from "
            f"fielding.CREDIT_SHARE ({REGIMES[BASELINE]} vs {current}). Every "
            "correlation is measured against the baseline, so publishing this "
            "would compare the model against shares it does not use. Rebuild "
            "REGIMES from fielding.CREDIT_SHARE."
        )


# How much of the head of the table is checked for churn.
TOP_N = 10


def regime_sensitivity(
    deliveries: pd.DataFrame,
    run_model: RunExpectancy,
    wp_model: WinProbability | None = None,
    *,
    min_balls: int = 600,
    regression_balls: int = 1200,
    top: int = TOP_N,
) -> dict:
    """
    Re-run the whole leaderboard under every regime in REGIMES.

    Returns each regime's fraa_per_100 series, its Spearman rank correlation
    against the baseline regime, its top `top`, and the players who are in the
    top `top` under all of them.

    scripts/export_web.py calls this as well, so the figures published in
    meta.json and the ones this script prints cannot drift apart.
    """
    _assert_baseline_is_the_model()
    boards: dict[str, pd.Series] = {}
    original = dict(fielding.CREDIT_SHARE)
    try:
        for name, shares in REGIMES.items():
            fielding.CREDIT_SHARE.update(original)
            fielding.CREDIT_SHARE.update(shares)
            boards[name] = fielding_leaderboard(
                deliveries,
                run_model,
                wp_model,
                min_balls=min_balls,
                regression_balls=regression_balls,
            ).set_index("fielder")["fraa_per_100"]
    finally:
        # Whatever happens, leave the module's shares as they were found.
        fielding.CREDIT_SHARE.update(original)

    base = boards[BASELINE]
    spearman: dict[str, float] = {}
    for name, s in boards.items():
        joined = pd.concat([base, s], axis=1, keys=["base", "alt"]).dropna()
        spearman[name] = float(spearmanr(joined["base"], joined["alt"]).statistic)

    tops = {
        name: s.sort_values(ascending=False).head(top).index.tolist()
        for name, s in boards.items()
    }
    held = sorted(set.intersection(*[set(t) for t in tops.values()]))
    return {"boards": boards, "spearman": spearman, "tops": tops, "held": held}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--match-type", default="T20")
    p.add_argument("--min-balls", type=int, default=600)
    p.add_argument("--top", type=int, default=TOP_N)
    a = p.parse_args()

    deliveries = load_deliveries(a.data, match_type=a.match_type)
    run_model = RunExpectancy().fit(deliveries)
    try:
        wp_model = WinProbability().fit(deliveries, match_outcomes(a.data, a.match_type))
    except ValueError:
        wp_model = None

    result = regime_sensitivity(
        deliveries, run_model, wp_model, min_balls=a.min_balls, top=a.top
    )

    print(f"\nRank correlation with {BASELINE} (Spearman)\n")
    for name, rho in result["spearman"].items():
        print(f"  {name:<18} rho = {rho:.3f}")

    print(f"\nTop {a.top} under each regime\n")
    top = pd.DataFrame(result["tops"])
    top.index = [f"#{i+1}" for i in range(len(top))]
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(top.to_string())

    always = result["held"]
    print(
        f"\nIn every regime's top {a.top}: "
        f"{', '.join(always) if always else '(nobody -- the ranking is assumption-driven)'}"
    )


if __name__ == "__main__":
    main()
