"""
Fielding value: turning credited dismissals into runs and win probability.

The chain is:

  1. A wicket falls in a known match state.
  2. The value functions price that wicket (runs forfeited / win% forfeited).
  3. A share of that price goes to the fielder(s), the rest to the bowler.
  4. Every player is charged an EXPECTED share based on time in the field.
  5. Value above average = what they actually took minus what a league-average
     fielder would have taken in the same amount of field time.

Step 4 is the part most fielding tables skip, and it is the part that makes
the number mean anything. Raw credited runs is a playing-time leaderboard;
it will rank the guy who played 17 matches above the guy who played 9.

KNOWN CEILING ON THIS VERSION
-----------------------------
Cricsheet records dismissals, not fielding events. There is no misfield, no
boundary save, no dropped catch, no dive stopped at the rope. So this model
sees roughly the 20% of fielding that ends in a wicket and is blind to the
80% that is ground fielding. It is a real, defensible measure of
*chance conversion and run-out threat*. It is not a complete fielding rating,
and the README says so in the same words.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .value import RunExpectancy, WinProbability

# --------------------------------------------------------------------------
# Credit shares. These are assumptions, not findings. They are exposed here
# so you can argue with them, and so a reviewer can see exactly what drives
# the leaderboard. Sensitivity-test them before you brief anyone on the output.
# --------------------------------------------------------------------------
CREDIT_SHARE: dict[str, float] = {
    "caught": 0.30,          # bowler created it; fielder still has to take it
    "caught and bowled": 0.0,  # already the bowler's
    "stumped": 0.40,         # keeper's execution, bowler's beat
    "run out": 0.90,         # bowler contributes essentially nothing
    "bowled": 0.0,
    "lbw": 0.0,
    "hit wicket": 0.0,
}

# Cricsheet lists run-out fielders in involvement order. First named is
# usually the one who hit the stumps or made the stop; give them the larger
# share and split the remainder evenly.
RUN_OUT_PRIMARY_SHARE = 0.60


def _split_credit(kind: str, fielders: list[str]) -> dict[str, float]:
    """Fraction of the total wicket value going to each named fielder."""
    share = CREDIT_SHARE.get(kind, 0.0)
    if share <= 0 or not fielders:
        return {}

    if kind == "run out" and len(fielders) > 1:
        primary, rest = fielders[0], fielders[1:]
        out = {primary: share * RUN_OUT_PRIMARY_SHARE}
        each = share * (1 - RUN_OUT_PRIMARY_SHARE) / len(rest)
        for f in rest:
            out[f] = out.get(f, 0.0) + each
        return out

    each = share / len(fielders)
    return {f: each for f in fielders}


def credit_dismissals(
    deliveries: pd.DataFrame,
    run_model: RunExpectancy,
    wp_model: WinProbability | None = None,
) -> pd.DataFrame:
    """One row per (dismissal, credited fielder)."""
    wickets = deliveries[deliveries["wicket"]].copy()
    rows = []

    for r in wickets.itertuples(index=False):
        kind = r.dismissal_kind
        credit = _split_credit(kind, list(r.fielders))
        if not credit:
            continue

        balls_rem = r.balls_remaining
        if balls_rem is None or pd.isna(balls_rem):
            continue

        runs_cost = run_model.wicket_cost(balls_rem, r.wickets_before)

        wp_cost = np.nan
        if wp_model is not None and r.innings == 2 and pd.notna(r.runs_required):
            wp_cost = wp_model.wicket_cost(
                balls_rem, r.wickets_before, r.runs_required
            )

        subs = dict(zip(r.fielders, r.fielder_is_sub)) if r.fielders else {}

        for fielder, frac in credit.items():
            rows.append(
                {
                    "match_id": r.match_id,
                    "innings": r.innings,
                    "fielding_team": r.fielding_team,
                    "fielder": fielder,
                    "is_substitute": bool(subs.get(fielder, False)),
                    "dismissal_kind": kind,
                    "credit_fraction": frac,
                    "wicket_runs_value": runs_cost,
                    "runs_saved": runs_cost * frac,
                    "wicket_wp_value": wp_cost,
                    "wpa": wp_cost * frac if pd.notna(wp_cost) else np.nan,
                }
            )

    return pd.DataFrame(rows)


def field_time(deliveries: pd.DataFrame) -> pd.DataFrame:
    """
    Balls each player spent in the field.

    Every member of the fielding XI is on the park for every delivery of that
    innings, so field time is just the innings length repeated across the XI.
    This is the denominator that turns a counting stat into a rate.
    """
    inn = (
        deliveries.groupby(["match_id", "innings", "fielding_team"])
        .agg(balls=("is_legal", "size"), fielding_xi=("fielding_xi", "first"))
        .reset_index()
    )
    inn = inn.explode("fielding_xi").rename(columns={"fielding_xi": "fielder"})
    inn = inn[inn["fielder"].notna()]
    return (
        inn.groupby("fielder")
        .agg(
            balls_in_field=("balls", "sum"),
            innings_fielded=("balls", "size"),
        )
        .reset_index()
    )


def _infer_keepers(credits: pd.DataFrame) -> set[str]:
    """
    Cricsheet has no fielding positions. A stumping can only be taken by the
    wicketkeeper, so anyone with a stumping is a keeper. Imperfect -- a keeper
    who never stumps in the sample is missed -- but it separates the two
    populations well enough to stop keepers dominating the table on volume.
    """
    return set(credits.loc[credits["dismissal_kind"] == "stumped", "fielder"].unique())


def fielding_leaderboard(
    deliveries: pd.DataFrame,
    run_model: RunExpectancy,
    wp_model: WinProbability | None = None,
    min_balls: int = 600,
    regression_balls: int = 1200,
) -> pd.DataFrame:
    """
    Fielding Runs Above Average (FRAA), per player.

    Parameters
    ----------
    min_balls
        Minimum field time to appear. 600 balls is roughly 5 full T20 innings.
    regression_balls
        Strength of the shrink toward league average for the per-100 rate.
        A player with `regression_balls` of field time is credited with half
        their observed rate; below that, more of the rate is pulled to zero.
        This is what stops a fluke run-out in two matches topping the table.
    """
    credits = credit_dismissals(deliveries, run_model, wp_model)
    time_df = field_time(deliveries)

    counts = (
        credits.assign(one=1)
        .pivot_table(
            index="fielder",
            columns="dismissal_kind",
            values="one",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    for col in ("caught", "run out", "stumped"):
        if col not in counts.columns:
            counts[col] = 0
    counts = counts.rename(
        columns={"caught": "catches", "run out": "run_outs", "stumped": "stumpings"}
    )[["fielder", "catches", "run_outs", "stumpings"]]

    totals = (
        credits.groupby("fielder")
        .agg(runs_saved=("runs_saved", "sum"), wpa=("wpa", "sum"))
        .reset_index()
    )

    df = (
        time_df.merge(totals, on="fielder", how="left")
        .merge(counts, on="fielder", how="left")
        .fillna({"runs_saved": 0.0, "wpa": 0.0, "catches": 0, "run_outs": 0, "stumpings": 0})
    )
    df = df[df["balls_in_field"] >= min_balls].copy()
    if df.empty:
        raise ValueError(
            f"No player reached min_balls={min_balls}. Lower it or add more matches."
        )

    keepers = _infer_keepers(credits)
    df["role"] = np.where(df["fielder"].isin(keepers), "keeper", "outfield")

    # Separate baselines: a keeper standing up gets chances a mid-on never sees.
    # Comparing them on one baseline measures position, not skill.
    baselines = (
        df.groupby("role")
        .apply(
            lambda g: pd.Series(
                {
                    "runs_per_ball": g["runs_saved"].sum() / g["balls_in_field"].sum(),
                    "wpa_per_ball": g["wpa"].sum() / g["balls_in_field"].sum(),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    df = df.merge(baselines, on="role", how="left")

    df["expected_runs_saved"] = df["runs_per_ball"] * df["balls_in_field"]
    df["expected_wpa"] = df["wpa_per_ball"] * df["balls_in_field"]
    df["fraa"] = df["runs_saved"] - df["expected_runs_saved"]
    df["wpaa"] = df["wpa"] - df["expected_wpa"]

    raw_rate = df["fraa"] / df["balls_in_field"] * 100
    shrink = df["balls_in_field"] / (df["balls_in_field"] + regression_balls)
    df["fraa_per_100"] = raw_rate * shrink
    df["fraa_per_100_raw"] = raw_rate

    cols = [
        "fielder",
        "role",
        "innings_fielded",
        "balls_in_field",
        "catches",
        "run_outs",
        "stumpings",
        "runs_saved",
        "expected_runs_saved",
        "fraa",
        "fraa_per_100",
        "fraa_per_100_raw",
        "wpa",
        "wpaa",
    ]
    return (
        df[cols]
        .sort_values("fraa_per_100", ascending=False)
        .round(3)
        .reset_index(drop=True)
    )
