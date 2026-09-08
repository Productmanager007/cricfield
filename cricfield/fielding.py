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

# Role buckets. Field time and credit are both split across these, and each is
# priced against its own baseline.
BUCKETS = ("keeper", "outfield", "unknown")

# Stage 3 evidence bar (see resolve_innings_keeper). A keeper out-catches his
# outfielders comfortably, so a narrow lead is more likely a busy slip fielder.
CATCH_MODAL_MIN = 3
CATCH_MODAL_MARGIN = 2


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


def _innings_roles(deliveries: pd.DataFrame, innings_keeper: pd.DataFrame) -> pd.DataFrame:
    """One row per (innings, fielder) carrying that player's role in it."""
    inn = (
        deliveries.groupby(_INNINGS_KEYS)
        .agg(balls=("is_legal", "size"), fielding_xi=("fielding_xi", "first"))
        .reset_index()
        .merge(innings_keeper, on=_INNINGS_KEYS, how="left")
    )
    inn = inn.explode("fielding_xi").rename(columns={"fielding_xi": "fielder"})
    inn = inn[inn["fielder"].notna()]
    inn["bucket"] = np.where(
        inn["stage"] == "unknown",
        "unknown",
        np.where(inn["fielder"] == inn["keeper"], "keeper", "outfield"),
    )
    return inn


def field_time(deliveries: pd.DataFrame, innings_keeper: pd.DataFrame) -> pd.DataFrame:
    """
    Balls each player spent in the field, split by the role he held.

    Every member of the fielding XI is on the park for every delivery of that
    innings, so field time is the innings length repeated across the XI. What
    changes here is that the same player accrues keeper balls in the innings he
    kept and outfield balls in the innings he did not, instead of one career
    role being applied to all of it.

    `unknown_balls` covers innings where the keeper could not be resolved. It
    is kept as its own bucket and priced against its own baseline rather than
    folded into outfield, because folding it in would silently recreate the
    error this split exists to remove.
    """
    inn = _innings_roles(deliveries, innings_keeper)

    wide = (
        inn.pivot_table(
            index="fielder",
            columns="bucket",
            values="balls",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    for b in BUCKETS:
        if b not in wide.columns:
            wide[b] = 0
    wide = wide.rename(columns={b: f"{b}_balls" for b in BUCKETS})

    totals = (
        inn.groupby("fielder")
        .agg(
            balls_in_field=("balls", "sum"),
            innings_fielded=("balls", "size"),
        )
        .reset_index()
    )
    return totals.merge(wide, on="fielder", how="left")


_INNINGS_KEYS = ["match_id", "innings", "fielding_team"]


def _modal(s: pd.Series) -> str | None:
    """Most frequent value, or None if there is nothing to pick from."""
    vc = s.dropna().value_counts()
    return None if vc.empty else vc.index[0]


def resolve_innings_keeper(
    deliveries: pd.DataFrame, credits: pd.DataFrame
) -> pd.DataFrame:
    """
    Who kept wicket in each (match, innings, fielding team)?

    Role is a property of an innings, not of a career. Assigning it per player
    fails in both directions: an occasional keeper is charged the keeper
    baseline for every ball he ever fielded, and a specialist keeper who
    happens not to stump anyone in the sample is charged the outfield baseline
    while taking chances at the keeper rate.

    Four stages, most reliable first, then unknown. The `stage` column records
    which one fired, so each fallback can be audited rather than trusted:

      1. `stumping`    -- a stumping was credited in this innings. Only the
                          keeper can take one, so this is direct evidence.
      2. `team-season` -- no stumping here, but this team has a modal stumper
                          in this calendar year and he is in this XI. IPL
                          seasons do not straddle years, so the calendar year
                          from `date` is a safe proxy for season.
      3. `catch-modal` -- the team-season contains no stumping at all, so
                          stage 2 has nothing to work from. The player with the
                          most credited catches for that team that season is
                          taken as the keeper, but only on strong evidence:
                          at least CATCH_MODAL_MIN catches AND a lead of at
                          least CATCH_MODAL_MARGIN over the next-highest.
                          Ties, or a one-catch edge, resolve to nothing -- a
                          keeper out-catches his outfielders comfortably, so a
                          narrow lead is more likely a busy slip than a keeper.
      4. `same-season` -- still unresolved, but some player in this XI was
                          identified as a keeper for THIS team in THIS season
                          by stages 1-3. This catches the second keeper of a
                          split season, whom stage 2's modal pick misses.
                          Deliberately bounded to the same team-season: a
                          player who kept in one season is not thereby a keeper
                          for the rest of his career, and carrying identity
                          across a whole career reintroduces the global-label
                          bug through the back door.
      5. `adjacent`    -- as stage 4, but drawing on the seasons either side at
                          the same team. Kept separate so its contribution
                          stays visible. Note this matches on the team string,
                          so a franchise rename (Delhi Daredevils -> Delhi
                          Capitals) breaks adjacency and costs recall here.
      -  `unknown`     -- none applied. Left unresolved rather than guessed at.

    In stages 4 and 5, where more than one candidate is in the XI, the one with
    the most established keeper innings wins; ties break on total credited
    catches, then on name, so the result is deterministic.

    Returns one row per innings with `keeper` (may be None) and `stage`.
    """
    inn = (
        deliveries.groupby(_INNINGS_KEYS)
        .agg(date=("date", "first"), fielding_xi=("fielding_xi", "first"))
        .reset_index()
    )
    inn["season"] = pd.to_datetime(inn["date"]).dt.year

    # --- stage 1: a stumping names the keeper outright ---
    stumpings = credits[credits["dismissal_kind"] == "stumped"]
    if len(stumpings):
        direct = (
            stumpings.groupby(_INNINGS_KEYS)["fielder"]
            .agg(_modal)
            .reset_index()
            .rename(columns={"fielder": "keeper"})
        )
        inn = inn.merge(direct, on=_INNINGS_KEYS, how="left")
    else:
        inn["keeper"] = None
    inn["stage"] = np.where(inn["keeper"].notna(), "stumping", None)

    # --- stage 2: this team's modal stumper that season, if he is in the XI ---
    known = inn[inn["keeper"].notna()]
    if len(known):
        modal = (
            known.groupby(["fielding_team", "season"])["keeper"]
            .agg(_modal)
            .reset_index()
            .rename(columns={"keeper": "season_keeper"})
        )
        inn = inn.merge(modal, on=["fielding_team", "season"], how="left")
    else:
        inn["season_keeper"] = None

    def _in_xi(row) -> bool:
        xi = row["fielding_xi"]
        return bool(xi is not None and row["season_keeper"] in list(xi))

    fillable = inn["keeper"].isna() & inn["season_keeper"].notna()
    if fillable.any():
        # Only credit the season keeper to innings he actually played in.
        in_xi = inn.loc[fillable].apply(_in_xi, axis=1)
        take = fillable & fillable.index.isin(in_xi[in_xi].index)
        inn.loc[take, "keeper"] = inn.loc[take, "season_keeper"]
        inn.loc[take, "stage"] = "team-season"

    # --- stage 3: catch-modal, for team-seasons with no stumping at all ---
    season_of = inn.set_index(_INNINGS_KEYS)["season"]
    cr = credits.join(season_of, on=_INNINGS_KEYS)
    catches = (
        cr[cr["dismissal_kind"] == "caught"]
        .groupby(["fielding_team", "season", "fielder"])
        .size()
        .reset_index(name="catches")
    )

    stumper_seasons = set(
        map(tuple, inn.loc[inn["stage"] == "stumping", ["fielding_team", "season"]].values)
    )
    catch_keeper: dict[tuple, str] = {}
    for (team, season), grp in catches.groupby(["fielding_team", "season"]):
        if (team, season) in stumper_seasons:
            continue
        grp = grp.sort_values(["catches", "fielder"], ascending=[False, True])
        top = grp.iloc[0]
        runner_up = int(grp.iloc[1]["catches"]) if len(grp) > 1 else 0
        if top["catches"] >= CATCH_MODAL_MIN and (
            top["catches"] - runner_up >= CATCH_MODAL_MARGIN
        ):
            catch_keeper[(team, season)] = top["fielder"]

    if catch_keeper:
        cand = inn.apply(
            lambda r: catch_keeper.get((r["fielding_team"], r["season"])), axis=1
        )
        fillable = inn["keeper"].isna() & cand.notna()
        if fillable.any():
            in_xi = inn.loc[fillable].apply(
                lambda r: bool(
                    r["fielding_xi"] is not None
                    and cand[r.name] in list(r["fielding_xi"])
                ),
                axis=1,
            )
            take = fillable & fillable.index.isin(in_xi[in_xi].index)
            inn.loc[take, "keeper"] = cand[take]
            inn.loc[take, "stage"] = "catch-modal"

    # --- stages 4 and 5: carry keeper identity, bounded by team and season ---
    # Built once, from stages 1-3 only, so later stages cannot feed themselves.
    established = inn.loc[inn["keeper"].notna()]
    ts_keepers: dict[tuple, dict[str, int]] = {
        key: grp["keeper"].value_counts().to_dict()
        for key, grp in established.groupby(["fielding_team", "season"])
    }
    total_catches = (
        cr[cr["dismissal_kind"] == "caught"].groupby("fielder").size().to_dict()
    )

    def _pick(counts: dict[str, int], xi) -> str | None:
        cands = [p for p in list(xi) if p in counts]
        if not cands:
            return None
        return sorted(
            cands, key=lambda p: (-counts[p], -total_catches.get(p, 0), p)
        )[0]

    def _same_season(row):
        xi = row["fielding_xi"]
        if xi is None:
            return None
        return _pick(ts_keepers.get((row["fielding_team"], row["season"]), {}), xi)

    def _adjacent(row):
        xi = row["fielding_xi"]
        if xi is None:
            return None
        merged: dict[str, int] = {}
        for s in (row["season"] - 1, row["season"] + 1):
            for p, c in ts_keepers.get((row["fielding_team"], s), {}).items():
                merged[p] = merged.get(p, 0) + c
        return _pick(merged, xi)

    for fn, label in ((_same_season, "same-season"), (_adjacent, "adjacent")):
        unresolved = inn["keeper"].isna()
        if not unresolved.any():
            break
        got = inn.loc[unresolved].apply(fn, axis=1)
        take = got[got.notna()]
        inn.loc[take.index, "keeper"] = take
        inn.loc[take.index, "stage"] = label

    inn["stage"] = inn["stage"].fillna("unknown")
    return inn[_INNINGS_KEYS + ["season", "keeper", "stage"]]


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
    innings_keeper = resolve_innings_keeper(deliveries, credits)
    time_df = field_time(deliveries, innings_keeper)

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

    # A player's headline role is wherever he spent most of his field time.
    # It is a label for the reader; the arithmetic below uses the split, not this.
    ball_cols = [f"{b}_balls" for b in BUCKETS]
    df["role"] = (
        df[ball_cols].idxmax(axis=1).str.replace("_balls", "", regex=False)
    )
    df["keeper_share"] = df["keeper_balls"] / df["balls_in_field"]

    # Separate baselines: a keeper standing up gets chances a mid-on never sees.
    # Comparing them on one baseline measures position, not skill. Credit is
    # attributed to the bucket the player occupied when he earned it, so the
    # rates below are per-role league averages, not per-player.
    cr = credits.merge(
        innings_keeper[_INNINGS_KEYS + ["keeper", "stage"]],
        on=_INNINGS_KEYS,
        how="left",
    )
    cr["bucket"] = np.where(
        cr["stage"] == "unknown",
        "unknown",
        np.where(cr["fielder"] == cr["keeper"], "keeper", "outfield"),
    )

    bucket_runs = cr.groupby("bucket")["runs_saved"].sum()
    bucket_wpa = cr.groupby("bucket")["wpa"].sum()

    df["expected_runs_saved"] = 0.0
    df["expected_wpa"] = 0.0
    for b in BUCKETS:
        balls = df[f"{b}_balls"].sum()
        runs_rate = (bucket_runs.get(b, 0.0) / balls) if balls else 0.0
        wpa_rate = (np.nan_to_num(bucket_wpa.get(b, 0.0)) / balls) if balls else 0.0
        df["expected_runs_saved"] += runs_rate * df[f"{b}_balls"]
        df["expected_wpa"] += wpa_rate * df[f"{b}_balls"]

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
        "keeper_balls",
        "outfield_balls",
        "unknown_balls",
        "keeper_share",
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
