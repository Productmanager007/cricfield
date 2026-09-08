"""
Value functions: what is a wicket actually worth?

Two currencies, deliberately kept separate rather than converted into
each other:

  RUNS   -- first-innings run expectancy V(balls_remaining, wickets_lost).
            A wicket costs the batting side V(b, w) - V(b, w+1).

  WIN%   -- second-innings win probability WP(balls_remaining, wickets_lost,
            runs_required). A wicket costs WP(b, w, r) - WP(b, w+1, r).

Anyone who tells you a run and a win-probability point are freely
interchangeable is hiding a modelling assumption. In a chase with 4 needed
off 12 balls, a wicket is worth almost nothing in runs and almost
everything in win probability. Report both.

Both models are empirical and binned rather than parametric. With enough
deliveries that beats a fitted curve, and it is auditable -- you can go
and look at the actual balls in any cell.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Deliveries remaining are bucketed; adjacent balls are near-identical states
# and pooling them buys sample size.
BALL_BUCKET = 6  # one over


def _bucket_balls(balls_remaining: pd.Series) -> pd.Series:
    return (balls_remaining // BALL_BUCKET).astype("Int64")


class RunExpectancy:
    """V(balls_remaining, wickets_lost) -> expected additional runs."""

    def __init__(self, min_sample: int = 30):
        self.min_sample = min_sample
        self.table: pd.DataFrame | None = None
        self.max_bucket: int = 0

    @staticmethod
    def _design(b: np.ndarray, w: np.ndarray) -> np.ndarray:
        """
        Polynomial basis in (balls remaining, wickets lost).

        A pure lookup table is honest where the data is thick and useless
        where it is thin -- nobody is 0 down with 12 balls left, so that
        cell is empty, and naive filling drags a full-innings value into it.
        Fitting a smooth surface gives every cell a sane prior, which we then
        override wherever real observations exist.
        """
        b = b.astype(float)
        w = w.astype(float)
        return np.column_stack(
            [np.ones_like(b), b, w, b * w, b**2, w**2, (b**2) * w, b * (w**2), w**3]
        )

    def fit(self, deliveries: pd.DataFrame) -> "RunExpectancy":
        d = deliveries[
            (deliveries["innings"] == 1) & deliveries["balls_remaining"].notna()
        ].copy()
        d["runs_to_come"] = d["innings_total"] - d["runs_before"]
        d["bucket"] = _bucket_balls(d["balls_remaining"])

        # Smooth surface fitted on every delivery.
        X = self._design(
            d["balls_remaining"].to_numpy(), d["wickets_before"].to_numpy()
        )
        self.beta, *_ = np.linalg.lstsq(X, d["runs_to_come"].to_numpy(float), rcond=None)

        grp = (
            d.groupby(["bucket", "wickets_before"])["runs_to_come"]
            .agg(["mean", "size"])
            .reset_index()
            .rename(columns={"mean": "value", "size": "n"})
        )
        self.max_bucket = int(grp["bucket"].max())
        self.table = self._densify(grp)
        return self

    def _densify(self, grp: pd.DataFrame) -> pd.DataFrame:
        """Blend empirical cells with the fitted surface, then constrain."""
        buckets = range(0, self.max_bucket + 1)
        wickets = range(0, 11)
        idx = pd.MultiIndex.from_product([buckets, wickets], names=["bucket", "wickets_before"])
        t = grp.set_index(["bucket", "wickets_before"]).reindex(idx).reset_index()
        t["n"] = t["n"].fillna(0)

        b_mid = (t["bucket"].astype(float) * BALL_BUCKET + BALL_BUCKET / 2).to_numpy()
        model = self._design(b_mid, t["wickets_before"].to_numpy()) @ self.beta
        model = np.clip(model, 0.0, None)

        # Shrink toward the fitted surface in proportion to how little data
        # the cell has. Thick cells keep their empirical value almost intact.
        k = float(self.min_sample)
        emp = t["value"].fillna(0.0).to_numpy()
        n = t["n"].to_numpy(float)
        t["value"] = (emp * n + model * k) / (n + k)

        # All out: nothing left to score.
        t.loc[t["wickets_before"] >= 10, "value"] = 0.0
        t["value"] = t["value"].fillna(0.0).clip(lower=0.0)

        # Monotone decreasing in wickets lost, at fixed balls remaining.
        t["value"] = t.groupby("bucket")["value"].transform(
            lambda s: np.minimum.accumulate(s.values)
        )
        # Monotone increasing in balls remaining, at fixed wickets.
        t["value"] = t.groupby("wickets_before")["value"].transform(
            lambda s: np.maximum.accumulate(s.values)
        )
        return t.set_index(["bucket", "wickets_before"])

    def value(self, balls_remaining: float, wickets_lost: int) -> float:
        if self.table is None:
            raise RuntimeError("Call .fit() first.")
        b = int(min(max(balls_remaining // BALL_BUCKET, 0), self.max_bucket))
        w = int(min(max(wickets_lost, 0), 10))
        return float(self.table.loc[(b, w), "value"])

    def wicket_cost(self, balls_remaining: float, wickets_lost: int) -> float:
        """Runs the batting side forfeits by losing a wicket right now."""
        return max(
            self.value(balls_remaining, wickets_lost)
            - self.value(balls_remaining, wickets_lost + 1),
            0.0,
        )


class WinProbability:
    """WP(balls_remaining, wickets_lost, runs_required) for the chasing side."""

    # Required run rate buckets. Chases live or die on this.
    RRR_EDGES = [-np.inf, 4, 6, 7.5, 9, 10.5, 12, 15, np.inf]

    def __init__(self, min_sample: int = 40):
        self.min_sample = min_sample
        self.table: pd.DataFrame | None = None
        self.max_bucket: int = 0
        self.base_rate: float = 0.5

    @classmethod
    def _rrr_bin(cls, runs_required: float, balls_remaining: float) -> int:
        if balls_remaining is None or balls_remaining <= 0:
            return len(cls.RRR_EDGES) - 2
        rrr = runs_required / balls_remaining * 6
        return int(np.digitize([rrr], cls.RRR_EDGES)[0] - 1)

    def fit(self, deliveries: pd.DataFrame, outcomes: pd.DataFrame) -> "WinProbability":
        d = deliveries[
            (deliveries["innings"] == 2)
            & deliveries["balls_remaining"].notna()
            & deliveries["runs_required"].notna()
        ].merge(outcomes, on="match_id", how="left")
        d = d[d["winner"].notna()]
        if d.empty:
            raise ValueError("No completed chases found -- cannot fit WinProbability.")

        d["chase_won"] = (d["winner"] == d["batting_team"]).astype(float)
        d["bucket"] = _bucket_balls(d["balls_remaining"])
        d["rrr_bin"] = [
            self._rrr_bin(r, b)
            for r, b in zip(d["runs_required"], d["balls_remaining"])
        ]
        self.base_rate = float(d["chase_won"].mean())
        self.max_bucket = int(d["bucket"].max())

        grp = (
            d.groupby(["bucket", "wickets_before", "rrr_bin"])["chase_won"]
            .agg(["mean", "size"])
            .reset_index()
            .rename(columns={"mean": "wp", "size": "n"})
        )
        # Shrink small cells toward the overall chase success rate.
        k = self.min_sample
        grp["wp"] = (grp["wp"] * grp["n"] + self.base_rate * k) / (grp["n"] + k)
        self.table = grp.set_index(["bucket", "wickets_before", "rrr_bin"])
        return self

    def value(
        self, balls_remaining: float, wickets_lost: int, runs_required: float
    ) -> float:
        if self.table is None:
            raise RuntimeError("Call .fit() first.")
        if runs_required is not None and runs_required <= 0:
            return 1.0
        if wickets_lost >= 10:
            return 0.0
        b = int(min(max(balls_remaining // BALL_BUCKET, 0), self.max_bucket))
        w = int(min(max(wickets_lost, 0), 10))
        r = self._rrr_bin(runs_required, balls_remaining)
        try:
            return float(self.table.loc[(b, w, r), "wp"])
        except KeyError:
            return self.base_rate

    def wicket_cost(
        self, balls_remaining: float, wickets_lost: int, runs_required: float
    ) -> float:
        """Win probability the chasing side forfeits by losing a wicket now."""
        return max(
            self.value(balls_remaining, wickets_lost, runs_required)
            - self.value(balls_remaining, wickets_lost + 1, runs_required),
            0.0,
        )
