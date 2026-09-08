# CONTEXT.md

## 1. What this repo is

cricfield is an option-value engine for cricket decisions: it prices the deliveries and shots available at each moment instead of averaging outcomes. The repo holds design documents only — no code has been written.

## 2. Current state

State as of 2026-09-08.

- **Runs today:** nothing. No `.py` files, no `cricfield/` package, no dependency manifest.
- **Present:** `problem.txt` (this *is* the PRD), `architecture.md`, `CONTEXT.md`.
- **Referenced but absent:** `PRD.md`, `README.md`, `MILESTONE.md`, `cricfield/*.py`.
- **Stubbed:** nothing — no scaffolding exists.
- **Untested:** everything. No test framework, no CI.
- **Not under version control** — git is not initialised.
- **Data:** none ingested. No Cricsheet download, Parquet store or DuckDB file.
- M1–M9 are specifications; none is implemented.

## 3. Settled decisions

- **Credit shares are decision-layer parameters, never constants** — M2 rankings must survive sensitivity analysis across credit regimes.
- **Value functions blend empirical bins with a fitted surface where cells are sparse, monotonicity enforced** — raw bins are too noisy in thin cells to be evidence.
- **Provenance is the triple (dataset version, model version, assumption set)** — assumptions change a published number without changing data or model. [inferred — architecture.md §8; the PRD requires only the first two]
- **The Tier 1 commentary classifier is a model, not a parser** — its output is a learned label needing its own calibration and version. Supersedes architecture.md §13, which lists this open.
- **All value reports in runs above replacement** — one axis, or cross-discipline comparison fails.
- **Nothing is fitted at request time** — outputs precomputed, surfaces read them.

## 4. Known problems

- No architectural claim is verified by execution.
- Filename drift: the PRD is `problem.txt`, not `PRD.md`.
- architecture.md §13 contradicts the classifier decision above.
- No version control, so the reproducibility requirement cannot be met.
- Case-insensitive filesystem: `CONTEXT.md` and `context.md` are one path; an earlier `context.md` was replaced by this file.
- M2 at Tier 0 sees only fielding that ends in a wicket — a ceiling, not a bug.
- Tier 2–3 data is unsecured, so M4–M7 are unbuildable, not merely unbuilt.

## 5. Conventions

- Match state is always **pre-ball**; one row per delivery; sources adapt to the schema, never the reverse.
- The feature store is immutable — corrections create new versions.
- Every number ships with an interval **and** a drill-down to its deliveries, or it is not done.
- Credit share, replacement level, shrinkage strength and phase boundaries are configurable and exported.
- Check the tier before building; never build Tier 2/3 models against unsecured data.
- British spelling.
