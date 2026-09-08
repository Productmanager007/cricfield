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

So every player is charged an expected credit based on balls spent in the field, and FRAA is the residual. Baselines are computed **separately for keepers and outfielders**, because a keeper standing up gets chances a mid-on never sees; comparing them on one baseline measures position, not skill. Keepers are identified by having taken a stumping, which is the only positional signal Cricsheet contains.

The per-100 rate is shrunk toward zero using `balls / (balls + regression_balls)`. Without that, a lucky run-out in two matches tops the table.

## What this model cannot see

This is the part to read before quoting a number at anyone.

**Cricsheet records dismissals, not fielding events.** There is no misfield, no boundary save, no dropped catch, no diving stop at the rope, no direct hit that missed. The model therefore sees the fraction of fielding that ends in a wicket and is blind to all ground fielding. It is a defensible measure of **chance conversion and run-out threat**. It is not a complete fielding rating.

**All catches are priced the same.** A regulation waist-high catch at mid-off and a diving one-hander at backward point score identically, because the data contains no difficulty signal. This is the single biggest weakness.

**Credit shares are judgement, not findings.** The 30/70 fielder-bowler split on a catch is an assumption, exposed at the top of `fielding.py` so you can argue with it. `sensitivity.py` re-runs the whole model under five different credit regimes and reports Spearman rank correlation against the baseline. On the synthetic set, correlations run 0.88–0.98 and eight of the top ten hold across all regimes. Run that on real data before briefing anyone, and if the top of the table reshuffles, the honest headline is "we measure run-out involvement."

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
  fielding.py   credit assignment, field time, FRAA leaderboard
  cli.py        command line entrypoint
make_sample_data.py   synthetic Cricsheet-format matches
sensitivity.py        assumption robustness check
```

## Where to take it

The interesting extension is not a better fielding number. It is **selection**: given a squad, a venue and an opposition, which eleven maximises expected runs saved plus expected runs scored plus expected wickets? Fielding value has never been on the same scale as batting and bowling value, which is why it never enters selection arguments. FRAA is on the runs scale. That is the point of building it this way.
