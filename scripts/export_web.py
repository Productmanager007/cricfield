"""
Export the leaderboard as JSON for the web MVP. Read-only: it reads match data
and the committed model, and writes only into the output directory.

Three files, into web-data/ by default:

  players.json         one entry per qualified fielder -- the career table
  player_seasons.json  one entry per (qualified fielder, season), with FRAA
                       computed within that season against that season's
                       baseline. The career CSV cannot answer "was he better
                       in 2019 than in 2024", and a comparison view needs it.
  meta.json            dataset provenance and the assumption values the
                       numbers were produced under

meta.json is the point of the exercise as much as the data is. Any number
shown on a web page has to be traceable to the model version that produced
it, which is the reproducibility rule the PRD already sets: a published figure
must be regenerable from a versioned dataset and a versioned model. A JSON
blob on a CDN with no provenance is an opinion.

    python scripts/export_web.py --data ipl_json.zip --min-balls 900

NO PER-SEASON MINIMUM IS APPLIED. A player-season can be a handful of balls,
and a rate computed on it is noise. The script reports the distribution so a
threshold can be chosen on evidence; it does not pick one. For the same
reason the per-season rate is published unshrunk as `fraa_per_100_raw`:
shrinking it would need a constant, and that constant is the same open
decision.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cricfield import fielding  # noqa: E402
from cricfield.fielding import (_innings_roles, credit_dismissals,  # noqa: E402
                                fielding_leaderboard, resolve_innings_keeper,
                                season_bucket_baselines)
from cricfield.parse import load_deliveries, match_outcomes  # noqa: E402
from cricfield.value import RunExpectancy, WinProbability  # noqa: E402

_INNINGS_KEYS = ["match_id", "innings", "fielding_team"]

PLAYER_COLS = [
    "fielder", "role", "rank", "balls_in_field", "keeper_balls",
    "outfield_balls", "catches", "run_outs", "stumpings", "runs_saved",
    "expected_runs_saved", "fraa", "fraa_per_100", "wpa",
]


def git_commit() -> dict:
    """
    The commit this export was produced from.

    Tried via git first, then by reading .git directly, because git is not
    always on PATH and an export with no provenance is worse than a slow one.
    """
    out = {"commit": None, "dirty": None, "source": None}
    try:
        sha = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15,
        )
        if sha.returncode == 0:
            out["commit"] = sha.stdout.strip()
            status = subprocess.run(
                ["git", "-C", str(ROOT), "status", "--porcelain"],
                capture_output=True, text=True, timeout=15,
            )
            out["dirty"] = bool(status.stdout.strip())
            out["source"] = "git"
            return out
    except (OSError, subprocess.SubprocessError):
        pass

    # Fallback: read the ref out of .git ourselves.
    try:
        head = (ROOT / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            ref_file = ROOT / ".git" / ref
            if ref_file.exists():
                out["commit"] = ref_file.read_text().strip()
            else:  # packed-refs
                packed = (ROOT / ".git" / "packed-refs")
                if packed.exists():
                    for line in packed.read_text().splitlines():
                        if line.endswith(f" {ref}"):
                            out["commit"] = line.split(" ", 1)[0]
                            break
        else:
            out["commit"] = head
        out["source"] = "read .git"
    except OSError:
        pass
    return out


def _clean(df: pd.DataFrame) -> list[dict]:
    """Records with NaN turned into null, so the JSON is valid."""
    return json.loads(df.replace({np.nan: None}).to_json(orient="records"))


def build_player_seasons(
    roles: pd.DataFrame, cr: pd.DataFrame, cells: pd.DataFrame, keep: set[str]
) -> pd.DataFrame:
    """
    One row per (fielder, season), charged against that season's baselines.

    Same arithmetic as the career table, partitioned by season instead of
    summed over it: field time per bucket, credit earned per bucket, expected
    credit at the (season, bucket) rate, FRAA as the residual.
    """
    r = roles[roles["fielder"].isin(keep)]
    c = cr[cr["fielder"].isin(keep)]

    balls = (
        r.pivot_table(index=["fielder", "season"], columns="bucket",
                      values="balls", aggfunc="sum", fill_value=0.0)
        .reset_index()
    )
    for b in fielding.BUCKETS:
        if b not in balls.columns:
            balls[b] = 0.0
    balls = balls.rename(columns={b: f"{b}_balls" for b in fielding.BUCKETS})
    balls["balls_in_field"] = sum(balls[f"{b}_balls"] for b in fielding.BUCKETS)

    innings = (
        r.groupby(["fielder", "season"]).size().reset_index(name="innings_fielded")
    )

    counts = (
        c.assign(one=1)
        .pivot_table(index=["fielder", "season"], columns="dismissal_kind",
                     values="one", aggfunc="sum", fill_value=0)
        .reset_index()
    )
    for col in ("caught", "run out", "stumped"):
        if col not in counts.columns:
            counts[col] = 0
    counts = counts.rename(columns={"caught": "catches", "run out": "run_outs",
                                    "stumped": "stumpings"})
    counts = counts[["fielder", "season", "catches", "run_outs", "stumpings"]]

    earned = (
        c.groupby(["fielder", "season"])
        .agg(runs_saved=("runs_saved", "sum"), wpa=("wpa", "sum"))
        .reset_index()
    )

    # Expected credit: field time in each bucket at that season's rate.
    long = r.groupby(["fielder", "season", "bucket"])["balls"].sum().reset_index()
    long = long.merge(cells[["season", "bucket", "runs_rate", "wpa_rate"]],
                      on=["season", "bucket"], how="left")
    long["exp_runs"] = long["balls"] * long["runs_rate"]
    long["exp_wpa"] = long["balls"] * long["wpa_rate"]
    expected = (
        long.groupby(["fielder", "season"])
        .agg(expected_runs_saved=("exp_runs", "sum"),
             expected_wpa=("exp_wpa", "sum"))
        .reset_index()
    )

    # The key set is the UNION of "fielded this season" and "earned credit this
    # season". They are not the same: a fielder credited on a dismissal while
    # acting as a substitute is not in that innings' XI and has no field time
    # for it, but the career table counts his credit. Merging onto field time
    # alone silently dropped those rows and the seasons stopped summing to the
    # career total -- 86 qualified players and 257.6 runs of credit.
    keys = (
        pd.concat([r[["fielder", "season"]], c[["fielder", "season"]]])
        .drop_duplicates()
        .reset_index(drop=True)
    )

    df = (
        keys.merge(balls, on=["fielder", "season"], how="left")
        .merge(innings, on=["fielder", "season"], how="left")
        .merge(counts, on=["fielder", "season"], how="left")
        .merge(earned, on=["fielder", "season"], how="left")
        .merge(expected, on=["fielder", "season"], how="left")
    )
    fills = {"runs_saved": 0.0, "wpa": 0.0, "catches": 0, "run_outs": 0,
             "stumpings": 0, "expected_runs_saved": 0.0, "expected_wpa": 0.0,
             "balls_in_field": 0.0, "innings_fielded": 0}
    fills.update({f"{b}_balls": 0.0 for b in fielding.BUCKETS})
    df = df.fillna(fills)

    df["fraa"] = df["runs_saved"] - df["expected_runs_saved"]
    df["wpaa"] = df["wpa"] - df["expected_wpa"]
    # Unshrunk on purpose -- see the module docstring.
    df["fraa_per_100_raw"] = np.where(
        df["balls_in_field"] > 0, df["fraa"] / df["balls_in_field"] * 100, np.nan
    )
    # A substitute-only season has no field time, so it has no role.
    df["role"] = (
        df[[f"{b}_balls" for b in fielding.BUCKETS]]
        .idxmax(axis=1).str.replace("_balls", "", regex=False)
    )
    df.loc[df["balls_in_field"] <= 0, "role"] = None
    return df.sort_values(["fielder", "season"]).round(4)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export leaderboard JSON for the web MVP.")
    p.add_argument("--data", required=True)
    p.add_argument("--match-type", default="T20")
    p.add_argument("--gender", default=None)
    p.add_argument("--min-balls", type=int, default=900)
    p.add_argument("--regression-balls", type=int, default=1200)
    p.add_argument("--out", default=str(ROOT / "web-data"))
    a = p.parse_args(argv)

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    match_type = None if a.match_type.upper() == "ALL" else a.match_type

    print(f"Parsing {a.data} ...", file=sys.stderr)
    d = load_deliveries(a.data, match_type=match_type, gender=a.gender)
    run_model = RunExpectancy().fit(d)
    wp_model = None
    try:
        wp_model = WinProbability().fit(d, match_outcomes(a.data, match_type))
    except ValueError as e:
        print(f"  win probability skipped: {e}", file=sys.stderr)

    print("Scoring ...", file=sys.stderr)
    board = fielding_leaderboard(
        d, run_model, wp_model,
        min_balls=a.min_balls, regression_balls=a.regression_balls,
    ).reset_index(drop=True)
    board["rank"] = board.index + 1

    # Rebuild the intermediates the per-season table needs. Same calls the
    # leaderboard makes, so the two cannot disagree.
    credits = credit_dismissals(d, run_model, wp_model)
    ik = resolve_innings_keeper(d, credits)
    roles = _innings_roles(d, ik)
    cr = credits.merge(ik[_INNINGS_KEYS + ["season", "keeper", "stage"]],
                       on=_INNINGS_KEYS, how="left")
    cr["bucket"] = np.where(
        cr["stage"] == "unknown", "unknown",
        np.where(cr["fielder"] == cr["keeper"], "keeper", "outfield"),
    )
    cells = season_bucket_baselines(roles, cr)

    keep = set(board["fielder"])
    seasons = build_player_seasons(roles, cr, cells, keep)

    # --- write ---------------------------------------------------------
    players_path = outdir / "players.json"
    seasons_path = outdir / "player_seasons.json"
    meta_path = outdir / "meta.json"

    players_path.write_text(json.dumps(_clean(board[PLAYER_COLS]), indent=None))
    seasons_path.write_text(json.dumps(_clean(seasons), indent=None))

    git = git_commit()
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(a.data),
        "match_type": match_type or "ALL",
        "gender": a.gender or "all",
        "matches": int(d["match_id"].nunique()),
        "deliveries": int(len(d)),
        "legal_deliveries": int(d["is_legal"].sum()),
        "season_min": int(pd.to_datetime(d["date"]).dt.year.min()),
        "season_max": int(pd.to_datetime(d["date"]).dt.year.max()),
        "qualified_fielders": int(len(board)),
        "player_seasons": int(len(seasons)),
        "git_commit": git["commit"],
        "git_dirty": git["dirty"],
        "git_source": git["source"],
        "assumptions": {
            "CREDIT_SHARE": dict(fielding.CREDIT_SHARE),
            "RUN_OUT_PRIMARY_SHARE": fielding.RUN_OUT_PRIMARY_SHARE,
            "FIELD_TIME_NORMALISATION": fielding.FIELD_TIME_NORMALISATION,
            "FIELDERS_PER_SIDE": fielding.FIELDERS_PER_SIDE,
            "CATCH_MODAL_MIN": fielding.CATCH_MODAL_MIN,
            "CATCH_MODAL_MARGIN": fielding.CATCH_MODAL_MARGIN,
            "SEASON_BASELINE_SHRINKAGE_BALLS": fielding.SEASON_BASELINE_SHRINKAGE_BALLS,
            "regression_balls": a.regression_balls,
            "min_balls": a.min_balls,
        },
        "caveats": [
            "Ground fielding is not observed: Cricsheet records dismissals, "
            "not fielding events. Elite ground fielders rank low.",
            "player_seasons has NO minimum applied and its rate is unshrunk; "
            "small player-seasons are noise.",
            "Season baseline rates track the scoring environment, not "
            "fielding standards.",
        ],
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    # --- report --------------------------------------------------------
    print(f"\n=== written to {outdir} ===\n")
    for f in (players_path, seasons_path, meta_path):
        print(f"  {f.name:<22} {f.stat().st_size:>10,} bytes  "
              f"({f.stat().st_size/1024:.1f} KB)")

    print(f"\n=== player_seasons ===\n")
    print(f"  rows            : {len(seasons):,}")
    print(f"  players         : {seasons['fielder'].nunique():,}")
    print(f"  seasons         : {seasons['season'].nunique()}")
    print(f"  rows per player : {len(seasons)/seasons['fielder'].nunique():.1f} mean")

    b = seasons["balls_in_field"]
    print(f"\n  balls_in_field per player-season:")
    for q in (0, 5, 10, 25, 50, 75, 90, 100):
        print(f"    p{q:<3} {b.quantile(q/100):>10,.0f}")
    print(f"    mean {b.mean():>9,.0f}")

    print(f"\n  rows at or below a candidate minimum:")
    for thr in (60, 120, 240, 360, 600, 900):
        n = int((b < thr).sum())
        print(f"    < {thr:>4} balls : {n:>6,}  ({n/len(seasons):>6.1%} of rows)")
    print("\n  No minimum is applied. Pick one from the distribution above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
