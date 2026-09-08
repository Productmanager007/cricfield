"""
Cricsheet JSON -> tidy ball-by-ball DataFrame.

Handles the Cricsheet v1.x JSON schema (the `*_json.zip` bundles from
https://cricsheet.org/downloads/). Works on a directory of .json files
or directly on a .zip.

One row per legal *and* illegal delivery, with the innings state as it
stood BEFORE the ball was bowled. State-before is what the value
function needs -- crediting a wicket requires knowing the situation the
batting side was in when they lost it.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Iterator

import pandas as pd

# Extras that do not consume a legal delivery.
_ILLEGAL = ("wides", "noballs")

# Dismissals the fielding side cannot be credited for at all.
_NON_FIELDING_DISMISSALS = {
    "retired hurt",
    "retired out",
    "retired not out",
    "timed out",
    "handled the ball",
    "obstructing the field",
}


def _iter_match_json(path: Path) -> Iterator[tuple[str, dict]]:
    """Yield (match_id, parsed_json) from a directory of .json or a .zip."""
    if path.is_dir():
        for f in sorted(path.glob("*.json")):
            if f.name in ("README.txt", "people.json"):
                continue
            with f.open() as fh:
                try:
                    yield f.stem, json.load(fh)
                except json.JSONDecodeError:
                    continue
    elif path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            for name in sorted(z.namelist()):
                if not name.endswith(".json"):
                    continue
                with z.open(name) as fh:
                    try:
                        yield Path(name).stem, json.load(fh)
                    except json.JSONDecodeError:
                        continue
    else:
        raise ValueError(f"Expected a directory or a .zip, got: {path}")


def _fielding_xi(info: dict, batting_team: str) -> list[str]:
    """The XI that is in the field for this innings."""
    players = info.get("players", {})
    for team, squad in players.items():
        if team != batting_team:
            return list(squad)
    return []


def load_deliveries(
    path: str | Path,
    match_type: str | None = "T20",
    gender: str | None = None,
    max_matches: int | None = None,
) -> pd.DataFrame:
    """
    Parse Cricsheet data into one row per delivery.

    Parameters
    ----------
    path
        Directory of Cricsheet .json files, or the .zip you downloaded.
    match_type
        Filter on info.match_type ("T20", "ODI", "Test", "IT20", "MDM"...).
        Pass None to keep everything. Mixing formats will corrupt the
        value function, so only do that deliberately.
    gender
        "male" / "female" / None for both. Separate value functions per
        gender are usually correct; scoring environments differ.
    max_matches
        Stop after N matches. Useful for a fast smoke test.

    Returns
    -------
    DataFrame with one row per delivery.
    """
    path = Path(path)
    rows: list[dict] = []
    kept = 0

    for match_id, m in _iter_match_json(path):
        info = m.get("info", {})
        if match_type and info.get("match_type") != match_type:
            continue
        if gender and info.get("gender") != gender:
            continue

        balls_per_over = info.get("balls_per_over", 6)
        max_overs = info.get("overs")  # None for Tests
        venue = info.get("venue")
        date = (info.get("dates") or [None])[0]
        event = (info.get("event") or {}).get("name")

        for inn_no, inn in enumerate(m.get("innings", []), start=1):
            # Super overs are a different game state entirely.
            if inn.get("super_over"):
                continue

            batting_team = inn.get("team")
            fielding_xi = _fielding_xi(info, batting_team)
            fielding_team = next(
                (t for t in info.get("teams", []) if t != batting_team), None
            )

            # Target for a chase, if the innings declares one.
            target_runs = (inn.get("target") or {}).get("runs")

            runs_so_far = 0
            wickets_so_far = 0
            legal_balls = 0

            for over in inn.get("overs", []):
                over_no = over.get("over", 0)
                for ball_idx, d in enumerate(over.get("deliveries", [])):
                    extras = d.get("extras", {}) or {}
                    is_legal = not any(k in extras for k in _ILLEGAL)

                    total = (d.get("runs", {}) or {}).get("total", 0)
                    wkts = d.get("wickets", []) or []

                    balls_remaining = (
                        max_overs * balls_per_over - legal_balls
                        if max_overs
                        else None
                    )

                    row = {
                        "match_id": match_id,
                        "date": date,
                        "event": event,
                        "venue": venue,
                        "innings": inn_no,
                        "batting_team": batting_team,
                        "fielding_team": fielding_team,
                        "over": over_no,
                        "ball_in_over": ball_idx + 1,
                        "batter": d.get("batter"),
                        "bowler": d.get("bowler"),
                        "non_striker": d.get("non_striker"),
                        "runs_total": total,
                        "runs_batter": (d.get("runs", {}) or {}).get("batter", 0),
                        "is_legal": is_legal,
                        # --- state BEFORE this ball ---
                        "runs_before": runs_so_far,
                        "wickets_before": wickets_so_far,
                        "legal_balls_before": legal_balls,
                        "balls_remaining": balls_remaining,
                        "target_runs": target_runs,
                        "runs_required": (
                            target_runs - runs_so_far if target_runs else None
                        ),
                        "fielding_xi": fielding_xi,
                        # --- dismissal ---
                        "wicket": bool(wkts),
                        "dismissal_kind": wkts[0]["kind"] if wkts else None,
                        "player_out": wkts[0].get("player_out") if wkts else None,
                        "fielders": (
                            [
                                f.get("name")
                                for f in (wkts[0].get("fielders") or [])
                                if f.get("name")
                            ]
                            if wkts
                            else []
                        ),
                        "fielder_is_sub": (
                            [
                                bool(f.get("substitute"))
                                for f in (wkts[0].get("fielders") or [])
                                if f.get("name")
                            ]
                            if wkts
                            else []
                        ),
                    }
                    rows.append(row)

                    runs_so_far += total
                    if is_legal:
                        legal_balls += 1
                    # Only wickets that cost the batting side a batter count.
                    wickets_so_far += sum(
                        1
                        for w in wkts
                        if w.get("kind") not in _NON_FIELDING_DISMISSALS
                        or w.get("kind") == "retired out"
                    )

            # Attach the innings total to every ball of that innings, so the
            # run-expectancy fit can look forward without a second pass.
            for r in rows[::-1]:
                if r["match_id"] == match_id and r["innings"] == inn_no:
                    r["innings_total"] = runs_so_far
                    r["innings_wickets"] = wickets_so_far
                else:
                    break

        kept += 1
        if max_matches and kept >= max_matches:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(
            "No deliveries parsed. Check the path, and that match_type "
            "matches the files you downloaded."
        )
    return df


def match_outcomes(path: str | Path, match_type: str | None = "T20") -> pd.DataFrame:
    """Winner per match -- needed to fit the win-probability model."""
    path = Path(path)
    out = []
    for match_id, m in _iter_match_json(path):
        info = m.get("info", {})
        if match_type and info.get("match_type") != match_type:
            continue
        outcome = info.get("outcome", {}) or {}
        out.append(
            {
                "match_id": match_id,
                "winner": outcome.get("winner"),
                "result": outcome.get("result"),  # "tie", "no result", None
            }
        )
    return pd.DataFrame(out)
