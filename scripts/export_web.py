"""
Export the leaderboard as JSON for the web MVP. Read-only: it reads match data
and the committed model, and writes only into the output directory.

Into web-data/ by default:

  players.json          one entry per qualified fielder -- the career table,
                        each carrying the `slug` needed to build the path below
  seasons/<slug>.json   that player's seasons, with FRAA computed within each
                        season against that season's baseline. The career table
                        cannot answer "was he better in 2019 than in 2024", and
                        a comparison view needs it.
  seasons/index.json    display name -> slug, for lookup without loading
                        players.json
  meta.json             dataset provenance and the assumption values the
                        numbers were produced under

The per-player split is a load-time decision, not a tidiness one. A comparison
view opens two players, not 528, so it should fetch a few KB rather than the
1.1MB a single combined file costs.

meta.json is the point of the exercise as much as the data is. Any number
shown on a web page has to be traceable to the model version that produced
it, which is the reproducibility rule the PRD already sets: a published figure
must be regenerable from a versioned dataset and a versioned model. A JSON
blob on a CDN with no provenance is an opinion.

    python scripts/export_web.py --data ipl_json.zip --min-balls 900

NO ROWS ARE FILTERED OUT. Every player-season is exported, including the tiny
ones, and each carries a `qualifies` boolean set at SEASON_QUALIFY_BALLS. The
web layer decides what to do with it; the exporter does not decide on its
behalf. The threshold is recorded in meta.json so it is traceable like every
other assumption. For the same reason the per-season rate is published
unshrunk as `fraa_per_100_raw`: shrinking it would need a constant, and that
constant is a separate open decision.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
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
    "fielder", "slug", "role", "rank", "balls_in_field", "keeper_balls",
    "outfield_balls", "catches", "run_outs", "stumpings", "runs_saved",
    "expected_runs_saved", "fraa", "fraa_per_100", "wpa",
]

# A player-season below this is too thin to read a rate from. Two matches'
# worth of field time. It removes the noisiest ~11% of rows while keeping
# genuine partial seasons -- a 600- or 900-ball cut would delete those, and
# a player who was injured in May is not the same thing as a player with
# eleven balls of substitute fielding.
#
# Rows are NOT filtered. Every season is exported with a `qualifies` flag and
# the web layer decides.
SEASON_QUALIFY_BALLS = 240

# Windows will not create a file with these names, whatever the extension.
_RESERVED = {
    "con", "prn", "aux", "nul", "com0", "com1", "com2", "com3", "com4",
    "com5", "com6", "com7", "com8", "com9", "lpt0", "lpt1", "lpt2", "lpt3",
    "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}


def slugify(name: str) -> str:
    """
    A filesystem- and URL-safe stem for a player name.

    Accents are folded rather than dropped, so Mendis and Méndez do not
    collide by accident, and anything left that is not alphanumeric becomes a
    single hyphen.
    """
    folded = unicodedata.normalize("NFKD", str(name))
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    if not slug:
        slug = "player"
    if slug in _RESERVED:
        slug = f"{slug}-x"
    return slug


def build_slugs(names) -> dict[str, str]:
    """
    Name -> slug, with collisions resolved deterministically.

    Two different players can fold to the same slug. Silently overwriting one
    file with another player's seasons would be invisible on the page and
    wrong, so collisions get a numeric suffix, assigned in sorted name order
    so the mapping is stable across runs.
    """
    out: dict[str, str] = {}
    used: dict[str, int] = {}
    for name in sorted(names):
        base = slugify(name)
        if base in used:
            used[base] += 1
            out[name] = f"{base}-{used[base]}"
        else:
            used[base] = 1
            out[name] = base
    return out


def _git_candidates() -> list[str]:
    """
    Where to look for a git executable.

    PATH first. The extra locations exist because git is genuinely not on PATH
    on the machine this is developed on, and falling through to the .git reader
    costs the dirty state, which is the part that matters.
    """
    local = Path.home() / "AppData" / "Local" / "Programs" / "Git" / "cmd" / "git.exe"
    return [
        "git",
        str(local),
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ]


def git_commit() -> dict:
    """
    The commit this export was produced from, and whether the tree was clean.

    Tried via a git executable first, then by reading .git directly, because an
    export with no provenance is worse than a slow one.

    `dirty_known` matters as much as `dirty`. The .git fallback can recover the
    commit but cannot tell whether the working tree was modified, so it reports
    dirty=None. A consumer that reads that null as "clean" would state, on a
    methodology page, that a number came from an unmodified commit when nobody
    checked. The boolean makes that distinction impossible to miss.
    """
    out = {"commit": None, "dirty": None, "dirty_known": False, "source": None}

    for exe in _git_candidates():
        try:
            sha = subprocess.run(
                [exe, "-C", str(ROOT), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=15,
            )
            if sha.returncode != 0:
                continue
            out["commit"] = sha.stdout.strip()
            status = subprocess.run(
                [exe, "-C", str(ROOT), "status", "--porcelain"],
                capture_output=True, text=True, timeout=15,
            )
            if status.returncode == 0:
                out["dirty"] = bool(status.stdout.strip())
                out["dirty_known"] = True
            out["source"] = "git" if exe == "git" else f"git ({exe})"
            return out
        except (OSError, subprocess.SubprocessError):
            continue

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
    df["qualifies"] = df["balls_in_field"] >= SEASON_QUALIFY_BALLS
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

    slugs = build_slugs(board["fielder"])
    board["slug"] = board["fielder"].map(slugs)
    seasons["slug"] = seasons["fielder"].map(slugs)

    # --- reconciliation: seasons must sum back to the career row ---------
    # Cheap, and it has already caught one real bug: merging the per-season
    # table onto field time alone dropped seasons where a qualified player
    # earned credit only as a substitute fielder. If this ever fails, the two
    # views on the page will disagree and the page is the last place to find
    # that out.
    recon = (
        seasons.groupby("fielder")
        .agg(s_fraa=("fraa", "sum"), s_runs=("runs_saved", "sum"),
             s_catches=("catches", "sum"))
        .reset_index()
        .merge(board[["fielder", "fraa", "runs_saved", "catches"]], on="fielder")
    )
    recon["d_fraa"] = (recon["fraa"] - recon["s_fraa"]).abs()
    recon["d_catches"] = (recon["catches"] - recon["s_catches"]).abs()
    bad = recon[(recon["d_fraa"] > 0.01) | (recon["d_catches"] > 0.5)]

    # --- write ---------------------------------------------------------
    players_path = outdir / "players.json"
    meta_path = outdir / "meta.json"
    seasons_dir = outdir / "seasons"
    seasons_dir.mkdir(parents=True, exist_ok=True)

    # Drop a previous run's combined file so nothing stale is served.
    legacy = outdir / "player_seasons.json"
    if legacy.exists():
        legacy.unlink()

    players_path.write_text(json.dumps(_clean(board[PLAYER_COLS]), indent=None))

    season_cols = [c for c in seasons.columns if c != "slug"]
    written = 0
    for name, grp in seasons.groupby("fielder"):
        payload = {
            "fielder": name,
            "slug": slugs[name],
            "seasons": _clean(grp[season_cols].drop(columns=["fielder"])),
        }
        (seasons_dir / f"{slugs[name]}.json").write_text(json.dumps(payload, indent=None))
        written += 1

    (seasons_dir / "index.json").write_text(
        json.dumps({name: slug for name, slug in sorted(slugs.items())}, indent=None)
    )

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
        # null in git_dirty means UNKNOWN, not clean. Check this first.
        "git_dirty_known": git["dirty_known"],
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
            "season_qualify_balls": SEASON_QUALIFY_BALLS,
        },
        "season_qualify_balls": SEASON_QUALIFY_BALLS,
        "season_qualify_rationale": (
            "A player-season below this is too thin to read a rate from. 240 "
            "balls is two matches' worth of field time: it flags the noisiest "
            "~11% of rows while keeping genuine partial seasons, which a 600- "
            "or 900-ball cut would delete. No rows are filtered out of the "
            "export -- every season carries a `qualifies` boolean and the web "
            "layer decides what to show."
        ),
        "seasons_qualifying": int(seasons["qualifies"].sum()),
        "reconciled_players": int(len(recon) - len(bad)),
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

    # --- provenance warning ----------------------------------------------
    # Say it out loud at export time. A commit recorded in a JSON file that
    # does not describe the code which produced it is a silent failure: the
    # page renders, every number displays, and the methodology page states a
    # model version that was never run. The export still succeeds -- a dirty
    # tree during development is normal and blocking it would be tiresome --
    # but it does not get to be quiet about it.
    short = (git["commit"] or "unknown")[:7]
    if git["commit"] is None:
        print("\n  ** PROVENANCE: commit UNKNOWN. This export cannot be traced "
              "to a model version.", file=sys.stderr)
        print("     Do not publish it. Check that .git is readable.", file=sys.stderr)
    elif not git["dirty_known"]:
        print(f"\n  ** PROVENANCE: recorded commit {short}, but the working tree "
              "state is UNKNOWN.", file=sys.stderr)
        print(f"     Read via '{git['source']}' -- no git executable was "
              "found, so uncommitted", file=sys.stderr)
        print("     changes cannot be detected. git_dirty is null, which means "
              "unknown, NOT clean.", file=sys.stderr)
    elif git["dirty"]:
        print(f"\n  ** PROVENANCE: exported from a DIRTY tree at {short}.",
              file=sys.stderr)
        print("     The recorded commit does not describe the files that "
              "produced this export.", file=sys.stderr)
        print("     Commit before publishing, then re-run.", file=sys.stderr)
    else:
        print(f"\n  provenance: clean tree at {short}", file=sys.stderr)

    # --- report --------------------------------------------------------
    per_player = sorted(seasons_dir.glob("*.json"))
    sizes = {f: f.stat().st_size for f in per_player}
    index_size = (seasons_dir / "index.json").stat().st_size
    total = players_path.stat().st_size + meta_path.stat().st_size + sum(sizes.values())

    print(f"\n=== written to {outdir} ===\n")
    for f in (players_path, meta_path):
        print(f"  {f.name:<24} {f.stat().st_size:>10,} bytes  "
              f"({f.stat().st_size/1024:.1f} KB)")
    print(f"  seasons/index.json       {index_size:>10,} bytes  "
          f"({index_size/1024:.1f} KB)")
    print(f"  seasons/*.json           {written:>10,} files")
    print(f"\n  total on disk            {total:>10,} bytes  ({total/1024:.1f} KB)")

    player_only = {f: s for f, s in sizes.items() if f.name != "index.json"}
    biggest = max(player_only, key=player_only.get)
    vals = sorted(player_only.values())
    print(f"\n  per-player files:")
    print(f"    largest  {biggest.name:<28} {player_only[biggest]:>7,} bytes "
          f"({player_only[biggest]/1024:.1f} KB)")
    print(f"    median   {vals[len(vals)//2]:>7,} bytes")
    print(f"    smallest {vals[0]:>7,} bytes")
    print(f"    a two-player comparison fetches about "
          f"{2*vals[len(vals)//2]/1024:.1f} KB")

    print(f"\n=== reconciliation (seasons sum to career) ===\n")
    print(f"  players reconciled : {len(recon) - len(bad)} / {len(recon)}")
    print(f"  max |d_fraa|       : {recon['d_fraa'].max():.6f}")
    if len(bad):
        print("  MISMATCHES:")
        print(bad[["fielder", "fraa", "s_fraa", "d_fraa"]].to_string(index=False))

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
        mark = "  <- SEASON_QUALIFY_BALLS" if thr == SEASON_QUALIFY_BALLS else ""
        print(f"    < {thr:>4} balls : {n:>6,}  ({n/len(seasons):>6.1%} of rows){mark}")

    q = int(seasons["qualifies"].sum())
    print(f"\n  qualifies=true : {q:,} of {len(seasons):,} ({q/len(seasons):.1%})")
    print("  No rows are filtered. The flag is advisory; the web layer decides.")
    return 1 if len(bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
