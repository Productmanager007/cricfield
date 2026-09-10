# CONTEXT.md

## 0. Read order

- `MILESTONE.md` — what is being built right now, and what "done" means for it.
- `PRD.md` — what we are building and why. Holds the roadmap.
- `architecture.md` — why the code is shaped this way. §14 covers the web layer.
- `CONTEXT.md` — this file: what is true of the repo right now.
- `WORKING-NOTES.md` — the long-form distillation of the PRD, cited as `ctx §n`.

## 1. What this repo is

cricfield is an option-value engine for cricket decisions: it prices the deliveries and shots available at each moment instead of averaging outcomes. The fielding model is built and runs on real data, and a static web shell reads its export; the rest is specification.

## 2. Current state

State as of 2026-09-10.

- **Runs today:** the fielding pipeline end to end. `python -m cricfield.cli --data ipl_json.zip --min-balls 900` produces a 528-player leaderboard from 1,243 IPL matches (295,557 deliveries, 2008–2026).
- **Builds today:** `web/`, MILESTONE Phase 1 (`6a8a4fb`). `npm run build` in `web/` produces a static export in `web/out/`. Its only page is a provenance page that fetches `/data/meta.json` at runtime and renders match count, delivery count, season range and `git_commit`. The build runs `web/scripts/copy-data.mjs` first, which copies `web-data/` into `web/public/data/` and fails loudly — exit 1, naming the missing directory — when `web-data/` is absent.
- **Implemented:** M1 value functions, M2 fielding value, M3 partially (FRAA only, no batting/bowling RAR). M4–M9 are specifications; none is implemented.
- **Present:** `PRD.md`, `MILESTONE.md`, `architecture.md`, `CONTEXT.md`, `WORKING-NOTES.md`, `README.md`, `cricfield/`, `scripts/`, `web/`, `make_sample_data.py`, `sensitivity.py`, `baselines/`.
- **Absent:** the leaderboard, player detail, compare, methodology page and deploy — MILESTONE Phases 2–6, designed in `architecture.md` §14 and not started.
- **Untested:** everything. No test framework, no CI. The only standing checks are `scripts/data_quality.py` and the reconciliation built into `scripts/export_web.py`.
- **Under git** since 2026-09-08, root commit `82136bf`, remote `github.com/Productmanager007/cricfield` (private). `git` is *not* on PATH; it lives at `%LOCALAPPDATA%\Programs\Git\cmd\git.exe`, and `python` on PATH is the Microsoft Store stub — the real one is at `%LOCALAPPDATA%\Programs\Python\Python313\python.exe`. Node 24.21.0 is installed and also *not* on PATH: it lives at `%LOCALAPPDATA%\Programs\nodejs` (portable install), so prepend that directory to `PATH` before running `npm` in `web/`.
- **Repo path:** `C:\Users\Amber user\dev\Cricfield`. Moved off OneDrive on 2026-09-09.
- **Data:** not in the repo. `ipl_json.zip` is fetched from Cricsheet and lives outside it; `web-data/` is generated and gitignored.

## 3. Settled decisions

- **Credit shares are decision-layer parameters, never constants** — M2 rankings must survive sensitivity analysis across credit regimes.
- **Value functions blend empirical bins with a fitted surface where cells are sparse, monotonicity enforced** — raw bins are too noisy in thin cells to be evidence.
- **Provenance is the triple (dataset version, model version, assumption set)** — assumptions change a published number without changing data or model. [inferred — architecture.md §8; the PRD requires only the first two]
- **The commentary scraper is a parser; the commentary classifier is a model** — the scraper is deterministic and fails loudly with no training data; the classifier is trained, has held-out accuracy, and its version belongs in the provenance triple.
- **All value reports in runs above replacement** — one axis, or cross-discipline comparison fails.
- **Nothing is fitted at request time** — outputs precomputed, surfaces read them.

## 4. Known problems

### Settled by measurement

- **The shrink is not too weak — `regression_balls` stays at 1200.** Spearman(`fraa_per_100`, `balls_in_field`) = 0.057, p = 0.19 across 533 qualified fielders. Quintile means are flat and non-monotone (−0.017, −0.039, −0.028, −0.027, −0.023); what moves is the SD, falling 0.258 (Q1) to 0.192 (Q5). Low-volume players are **more dispersed, not better rated**, so they occupy both tails. `regression_balls=3500` was tested: it swaps 3 of the top 20 and lands the bottom-quartile share on its 25% null, but corrects variance rather than bias. Rejected as a presentation change with no correctness basis.
- **Supersedes the `57dfd0c` commit-message claim** that top-10 churn across credit regimes indicated a small-sample problem. It is the same variance effect, not bias.

### Open, unfixed

- **MISINTERPRETATION RISK — the season rate table is not a fielding-standards trend.** `season_bucket_baselines` fits an expected-credit rate per (season, role), and those rates are U-shaped: outfield runs-saved per ball ×1000 goes 7.03 (2008) → 4.10 (2020) → 6.63 (2026). It is tempting, and wrong, to read this as IPL fielding declining then improving. The quantity is *credited dismissal value per ball fielded*, so it moves with how many wickets fell and what each was worth in run-expectancy terms — 2020 was the low-scoring UAE season, 2024 and 2026 were high-scoring, and the rates follow the scoring environment. It says nothing about how well anyone fielded. Answering the fielding-standards question needs chances-created held constant, which is Tier 1. **Do not quote this table as evidence of changing fielding quality**; it is exactly the claim someone will reach for.
- **The Tier 0 ceiling is now visible in the output.** RA Jadeja ranks 105/528 and SA Yadav 161/528 despite elite ground-fielding reputations. Both are known for boundary saves and direct hits, which Tier 0 cannot observe — `fielding.py` sees only the fraction of fielding that ends in a wicket. This is the ceiling appearing exactly where the README predicts, and it is **the strongest single argument for the Tier 1 commentary layer**.
- FRAA may carry residual team structure: the expected-credit baseline in `fielding.py` assumes chances arrive uniformly per ball in field, so a team with a better attack may hand its fielders unearned credit. Measured by `scripts/diagnose_baseline.py`; unfixed.
- **Residual 8.3% per-player field-time error in 470 post-2023 innings.** The Impact Player rule means Cricsheet lists 12 names with no marker for which 11 started, so `field_time` scales those innings by `11/len(XI)`. Per-innings player-time is now exactly `11 × balls` (verified across all 2,480 innings), but *within* a scaled innings a player who actually fielded throughout is under-credited by up to 1/12. This is concentrated in exactly the careers that moved most when the normalisation landed — mostly-post-2023 players gained 15.6 ranks on average, pre-2023-only players lost 2.6 — so the residual error and the largest correction sit on the same players. Only Tier 1+ team-sheet data resolves it. Re-measured on the committed code via `scripts/era_effect.py`; the correlations are unchanged from the pre-commit figures (ρ = −0.78 on rank change, +0.85 on rate change), the band means slightly attenuated from +17.8 / −3.4 because bounding step-1 removal cut the maximum rank movement from 102 to 55.
- **`web-data/` on disk can be a stale local export rather than the current CI artefact.** It is gitignored and nothing refreshes it automatically, so whatever was last exported or unpacked stays there. Phase 1 found exactly this: the local copy was an `f3e0a79` export with `git_dirty: null` read from `.git`, not the `b7457aa` CI artefact. The provenance page now makes it visible by rendering the export commit and dirty state, but nothing prevents a build from using stale data — `web/scripts/copy-data.mjs` checks that the data is present and well-formed, not that it is current. The canonical source is the `web-data` artefact of the newest successful `export` workflow run (`.github/workflows/export.yml`).
- Harmeet Singh appears for two franchises in 2013 — most likely a Cricsheet name collision merging two careers, silently. Detected by `scripts/data_quality.py`.
- No architectural claim is verified by execution beyond M1–M3.
- Case-insensitive filesystem: `CONTEXT.md` and `context.md` are one path. Never create a name differing only in case.
- M2 at Tier 0 sees only fielding that ends in a wicket — a ceiling, not a bug.
- Tier 2–3 data is unsecured, so M4–M7 are unbuildable, not merely unbuilt.

## 5. Conventions

- Match state is always **pre-ball**; one row per delivery; sources adapt to the schema, never the reverse.
- The feature store is immutable — corrections create new versions.
- Every number ships with an interval **and** a drill-down to its deliveries, or it is not done.
- Credit share, replacement level, shrinkage strength and phase boundaries are configurable and exported.
- Check the tier before building; never build Tier 2/3 models against unsecured data.
- British spelling.
