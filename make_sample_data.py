"""
Generate synthetic matches in Cricsheet v1.x JSON format.

This exists so the pipeline can be run end to end before you download
anything. The players are fake and the numbers mean nothing -- it is a
smoke test, not a dataset. Some fielders are given a deliberately elevated
catch and run-out rate so you can check the model finds them.

    python make_sample_data.py --out sample_data --matches 120
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

TEAMS = {
    "Northern Kites": [f"N Player{i:02d}" for i in range(1, 12)],
    "Coastal Mariners": [f"C Player{i:02d}" for i in range(1, 12)],
    "Highland Rangers": [f"H Player{i:02d}" for i in range(1, 12)],
    "Delta Chargers": [f"D Player{i:02d}" for i in range(1, 12)],
}

# Planted "elite fielders" -- the model should surface these near the top.
GIFTED = {"N Player04": 2.4, "C Player07": 2.2, "H Player02": 2.0}
# Planted keepers (index 10 of each squad).
KEEPERS = {t: squad[10] for t, squad in TEAMS.items()}


def _pick_fielder(squad: list[str], keeper: str, rng: random.Random) -> str:
    weights = [GIFTED.get(p, 1.0) for p in squad]
    return rng.choices(squad, weights=weights, k=1)[0]


def _build_innings(batting, fielding, rng, target=None):
    bat_squad = TEAMS[batting]
    field_squad = TEAMS[fielding]
    keeper = KEEPERS[fielding]

    overs, wickets, total, striker_i = [], 0, 0, 0
    next_bat = 2
    for over_no in range(20):
        if wickets >= 10:
            break
        deliveries = []
        legal = 0
        while legal < 6 and wickets < 10:
            batter = bat_squad[min(striker_i, 10)]
            bowler = field_squad[rng.randrange(0, 6)]
            d = {
                "batter": batter,
                "bowler": bowler,
                "non_striker": bat_squad[min(striker_i + 1, 10)],
            }
            if rng.random() < 0.04:
                d["extras"] = {"wides": 1}
                d["runs"] = {"batter": 0, "extras": 1, "total": 1}
                deliveries.append(d)
                total += 1
                continue

            legal += 1
            # Wicket chance rises late in the innings.
            p_wkt = 0.035 + 0.0016 * over_no
            if rng.random() < p_wkt:
                roll = rng.random()
                if roll < 0.55:
                    kind, fielders = "caught", [_pick_fielder(field_squad, keeper, rng)]
                elif roll < 0.72:
                    kind, fielders = "bowled", []
                elif roll < 0.82:
                    kind, fielders = "lbw", []
                elif roll < 0.93:
                    fielders = [_pick_fielder(field_squad, keeper, rng)]
                    if rng.random() < 0.5:
                        fielders.append(keeper)
                    kind = "run out"
                else:
                    kind, fielders = "stumped", [keeper]
                d["runs"] = {"batter": 0, "extras": 0, "total": 0}
                d["wickets"] = [
                    {
                        "player_out": batter,
                        "kind": kind,
                        **({"fielders": [{"name": f} for f in fielders]} if fielders else {}),
                    }
                ]
                wickets += 1
                striker_i = next_bat
                next_bat += 1
            else:
                runs = rng.choices([0, 1, 2, 3, 4, 6], weights=[34, 33, 9, 1, 15, 8])[0]
                d["runs"] = {"batter": runs, "extras": 0, "total": runs}
                total += runs
                if runs % 2 == 1:
                    striker_i, d["non_striker"] = striker_i, d["non_striker"]
            deliveries.append(d)
            if target and total >= target:
                break
        overs.append({"over": over_no, "deliveries": deliveries})
        if target and total >= target:
            break

    inn = {"team": batting, "overs": overs}
    if target:
        inn["target"] = {"runs": target, "overs": 20}
    return inn, total, wickets


def build_match(match_no: int, rng: random.Random) -> dict:
    a, b = rng.sample(list(TEAMS), 2)
    inn1, total1, _ = _build_innings(a, b, rng)
    inn2, total2, wkts2 = _build_innings(b, a, rng, target=total1 + 1)
    winner = b if total2 > total1 else a

    return {
        "meta": {"data_version": "1.1.0", "created": "2026-01-01", "revision": 1},
        "info": {
            "balls_per_over": 6,
            "dates": [f"2026-0{rng.randint(1,9)}-{rng.randint(10,28)}"],
            "event": {"name": "Synthetic Test League", "match_number": match_no},
            "gender": "male",
            "match_type": "T20",
            "outcome": {"winner": winner},
            "overs": 20,
            "players": {a: TEAMS[a], b: TEAMS[b]},
            "teams": [a, b],
            "toss": {"decision": "bat", "winner": a},
            "venue": "Test Ground",
        },
        "innings": [inn1, inn2],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="sample_data")
    p.add_argument("--matches", type=int, default=120)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()

    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i in range(1, a.matches + 1):
        (out / f"{900000 + i}.json").write_text(json.dumps(build_match(i, rng)))
    print(f"Wrote {a.matches} synthetic matches to {out}/")
    print(f"Planted elite fielders: {', '.join(GIFTED)}")


if __name__ == "__main__":
    main()
