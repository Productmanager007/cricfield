# cricfield — Fielding Runs Above Average

A working model that prices cricket fielding in runs and win probability, built on free public ball-by-ball data.

Fielding is the one of the three disciplines with no accepted measure. Batting has average and strike rate. Bowling has average and economy. Fielding has "he's a gun in the ring," which is a vibe, not a number. Selectors trade a batter averaging 31 for one averaging 27 without any way to price the two run-outs and four catches a season the second one brings. That gap is the reason this exists.

## What it does

1. Parses Cricsheet JSON into a tidy ball-by-ball table with the innings state *before* each delivery.
2. Fits two value functions from that data:
   - **Run expectancy** `V(balls_remaining, wickets_lost)` — expected further runs, first innings.
   - **Win probability** `WP(balls_remaining, wickets_lost, runs_required)` — chase success rate.
3. Prices every wicket in both currencies: what the batting side forfeited by losing it.
4. Splits that price between bowler and fielder(s) by dismissal type.
5. Charges every player an **expected** share based on time in the field, and reports the difference.

The output is **FRAA** — Fielding Runs Above Average — plus a per-100-balls rate, regressed for sample size.

Runs and win probability are reported side by side and never converted into each other. With 4 needed off 12, a wicket is worth almost nothing in runs and almost everything in win probability. Anyone who collapses those into one number is hiding an assumption.

## Quick start

```bash
pip install -r requirements.txt

# Smoke test on synthetic data — no downloads needed
python make_sample_data.py --matches 200
python -m cricfield.cli --data sample_data --min-balls 500

# Real data: grab a bundle from https://cricsheet.org/downloads/
# (e.g. "Indian Premier League" JSON, or all T20s)
python -m cricfield.cli --data ipl_json.zip --min-balls 900 --out ipl_fraa.csv

# Check how much of the ranking is data vs. my assumptions
python sensitivity.py --data ipl_json.zip
```

The parser reads the `.zip` directly — no need to unpack it.

## The step most fielding tables skip

Raw credited runs is a playing-time leaderboard. It ranks the player who appeared in 17 matches above the one who appeared in 9, and calls that fielding ability.

So every player is charged an expected credit based on balls spent in the field, and FRAA is the residual. Baselines are computed **separately for keepers and outfielders**, because a keeper standing up gets chances a mid-on never sees; comparing them on one baseline measures position, not skill.

### Role is resolved per innings, not per career

Cricsheet has no fielding positions, so the keeper has to be inferred. Inferring it once per player fails in both directions: an occasional keeper is charged the keeper baseline for every ball he ever fielded, and a specialist keeper who happens not to stump anyone in the sample is charged the outfield baseline while taking chances at the keeper rate.

Role is therefore resolved for each `(match, innings, fielding team)` through five stages, most reliable first. The stage that fired is recorded, so the fallbacks can be audited rather than trusted:

| Stage | Basis | Share of IPL innings |
|---|---|---|
| `stumping` | a stumping was credited — only the keeper can take one | 13.7% |
| `team-season` | the team's modal stumper that season, if he is in this XI | 61.3% |
| `catch-modal` | season catch leader, needing ≥3 catches and a ≥2 lead | 9.4% |
| `same-season` | another keeper identified for this same team-season | 3.4% |
| `adjacent` | as above, from the seasons either side at the same team | 9.0% |
| `unknown` | none applied — left unresolved rather than guessed at | 3.3% |

Each player's field time is then split into `keeper_balls`, `outfield_balls` and `unknown_balls`, and each bucket is charged against its own baseline. `unknown` keeps its own baseline rather than being folded into outfield, which would silently recreate the error the split exists to remove.

### Baselines are conditioned on season as well as role

Pooling nineteen seasons charges a 2009 fielder and a 2026 fielder the same expected rate. Rates are therefore fitted per `(season, role)` and each player's field time in a season is charged at that season's rate, summed across his career. Season cells are thin — a keeper season is around 14,000 balls against 142,000 for outfielders — so each is shrunk toward the all-season rate for its role by `SEASON_BASELINE_SHRINKAGE_BALLS` (10,000 balls of pseudo-data). Outfield cells keep about 93% of their own rate, keeper cells 59%.

**The fitted season rates are not a fielding-standards trend, and must not be quoted as one.** They are U-shaped, not trending: outfield runs-saved per ball goes 7.03 (2008) → 4.10 (2020) → 6.63 (2026). The quantity is credited dismissal value per ball fielded, so it moves with how many wickets fell and what each was worth — 2020 was the low-scoring UAE season, 2024 and 2026 were high-scoring, and the rates follow. It says nothing about how well anyone fielded. Answering that needs chances-created held constant, which needs commentary data this model does not have.

The per-100 rate is shrunk toward zero using `balls / (balls + regression_balls)`. Without that, a lucky run-out in two matches tops the table.

## What this model cannot see

This is the part to read before quoting a number at anyone.

**Cricsheet records dismissals, not fielding events.** There is no misfield, no boundary save, no dropped catch, no diving stop at the rope, no direct hit that missed. The model therefore sees the fraction of fielding that ends in a wicket and is blind to all ground fielding. It is a defensible measure of **chance conversion and run-out threat**. It is not a complete fielding rating.

This is not a theoretical limitation, and the output now shows exactly where it bites. On nineteen seasons of IPL data, **RA Jadeja ranks 105th and SA Yadav 161st of 528 qualified fielders.** Both are elite ground fielders by any professional assessment, and the model cannot see why: their value is in boundary saves, diving stops and direct hits that miss — the 80% of fielding Cricsheet does not record. If a ranking disagrees with an informed observer about a player like Jadeja, the model is usually the one that is wrong, and it is wrong for a reason that is known and stated here rather than discovered in a meeting.

**All catches are priced the same.** A regulation waist-high catch at mid-off and a diving one-hander at backward point score identically, because the data contains no difficulty signal. This is the single biggest weakness.

**Credit shares are judgement, not findings.** The 30/70 fielder-bowler split on a catch is an assumption, exposed at the top of `fielding.py` so you can argue with it. `sensitivity.py` re-runs the whole model under five different credit regimes and reports Spearman rank correlation against the baseline.

On the real IPL data — 1,243 matches, 2008–2026 — whole-table correlations run **0.963 to 0.989** across the five regimes, but **only 4 of the top 10 hold in every regime**. Those two numbers point in opposite directions and both are true. The aggregate ordering is robust; the head of the table is the least stable part of it, because a top-20 place rests on a handful of credited events and a nudge to the run-out share reorders them. That matters more than the aggregate, because the top is the part anyone actually reads. Treat individual top-10 placings as provisional and quote the band, not the rank.

**Which eleven fielded is unknown from 2023 onward.** The Impact Player rule lets a side use a twelfth player, and Cricsheet lists all twelve — occasionally thirteen — in `info.players` with no marker for which eleven started. There is no `playing_xi` key, and the `substitute` flag that appears on dismissal fielders is unrelated: 197 of its 199 occurrences name players who are not in `info.players` at all. Role appearance does not separate them either, because both players usually take part, one batting and the other bowling.

`FIELD_TIME_NORMALISATION` handles this in two steps: drop squad members who never appear in any role that match, bounded by the surplus so no innings is left asserting fewer than eleven fielders; then scale the remainder by `11 / len(XI)`. Per-innings player-time then totals exactly `11 × balls`, which is a hard physical constraint. **Per-player attribution inside the 470 scaled innings remains wrong by up to 8.3%**, and that residual falls entirely on post-2023 careers. This is an approximation, not a fix, and only team-sheet data resolves it.

**Sparse states are modelled, not observed.** Nobody is nought down with twelve balls left, so that cell is empty. Rather than let a full-innings value leak into it, a smooth polynomial surface in (balls, wickets) is fitted across all deliveries and blended with the empirical cells in proportion to sample size. Monotonicity is then enforced: value falls as wickets are lost, rises as balls remain.

## Roadmap — in order of value added

1. **Commentary parsing for ground fielding.** ESPNcricinfo ball-by-ball commentary describes misfields, saves and drops in free text. Classifying it turns the blind 80% into data. This is the single change that would take the model from partial to complete.
2. **Catch difficulty.** Even a crude three-tier classifier (regulation / awkward / exceptional) from commentary text would fix the largest current distortion.
3. **Dropped catches.** Currently invisible, and a dropped catch is the most expensive thing a fielder can do. Commentary again.
4. **Batter-quality-adjusted wicket cost.** Dismissing a set number four is worth more than dismissing the same batter first ball. Replace the generic value function with one conditioned on who was actually removed and who walks in.
5. **Position inference.** Where fielders stand drives their opportunity rate more than skill does. Without it, the keeper-vs-outfield split is a blunt proxy.
6. **Ageing curves.** Fielding is the first thing to go. A model that projects decline is worth more to a selector than one that describes the past.

## Layout

```
cricfield/
  parse.py      Cricsheet JSON -> ball-by-ball DataFrame
  value.py      RunExpectancy and WinProbability
  fielding.py   credit assignment, role resolution, field time, FRAA leaderboard
  cli.py        command line entrypoint
scripts/
  data_quality.py       standing data-quality sweep, read-only
  diagnose_baseline.py  does FRAA carry residual team structure?
  era_effect.py         does a model change load on the era axis?
make_sample_data.py   synthetic Cricsheet-format matches
sensitivity.py        assumption robustness check
baselines/            leaderboard snapshots a change was measured against
```

The `scripts/` tools report and never repair, and each exists because it caught something real:

```bash
# Before trusting a leaderboard built from a new dataset
python scripts/data_quality.py --data ipl_json.zip

# After any model change, against a snapshot taken before it
python scripts/era_effect.py --before baselines/ipl_fraa_ccfebce.csv \
    --after ipl_fraa.csv --data ipl_json.zip
```

`era_effect.py` is worth explaining. A change can look inert in aggregate and still move a whole era: the season-baseline change scored Spearman 0.985 old-vs-new, which reads as "nothing happened", while players grouped by era moved by up to 44 ranks in opposite directions. It reports the monotone correlation, an eta-squared across era bands, and movement broken out by rank band — because the headline mean is dominated by the tail, where FRAA sits near zero and rank ordering is mostly noise.

## Where to take it

The interesting extension is not a better fielding number. It is **selection**: given a squad, a venue and an opposition, which eleven maximises expected runs saved plus expected runs scored plus expected wickets? Fielding value has never been on the same scale as batting and bowling value, which is why it never enters selection arguments. FRAA is on the runs scale. That is the point of building it this way.
