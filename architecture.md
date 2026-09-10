# cricfield — architecture

**Sources.** This document elaborates the architecture stated in [PRD.md](PRD.md) §6 and [WORKING-NOTES.md](WORKING-NOTES.md) §5. It adds no requirements. Every statement carries a reference to its source: `PRD §n` for [PRD.md](PRD.md), `ctx §n` for [WORKING-NOTES.md](WORKING-NOTES.md).

**Convention.** Anything not stated in either source is marked **Derived** and is a proposal to confirm, not a decision. Nothing here overrides the PRD.

**Owner:** Manu S Nair · **Status:** partly built. The fielding model (M1, M2, and M3 as FRAA only), the exporter `scripts/export_web.py` and the web shell (§14, MILESTONE Phase 1) exist; M4–M9 and the remaining web views are specification. What is true of the repo right now lives in `CONTEXT.md` §2.

---

## 1. Architectural shape

Four layers, each with a clean interface to the next (PRD §6), with surfaces as the terminal stage (ctx §5):

```
  Ingestion  →  Feature & label store  →  Model layer  →  Decision layer  →  Surfaces
   (parsers)      (versioned, immutable)   (offline-trained)  (assumptions live here)  (web/API/export)
```
*(ctx §5)*

The organising property is that **each layer's output is the next layer's only input**. The strongest form of this is stated for ingestion: every downstream model reads the canonical schema and nothing else, so a new data source is an ingestion problem, never a modelling one (PRD §6, ctx §5).

Two flows cross the layers in opposite directions:

- **Forward — production.** Raw source → canonical ball record → features and labels → model outputs → composed answers → rendered surface.
- **Backward — audit.** Every aggregate on a surface drills down to the deliveries that produced it (PRD §9, ctx §9). Auditability is therefore not a feature bolted onto the surfaces; it is a property every layer must preserve, because a link broken at any layer breaks the chain.

**Derived:** the audit path is the binding architectural constraint on all four layers, since it is the only requirement that must hold *simultaneously* at every one of them. The PRD states the requirement (PRD §9) but does not name it as a cross-layer constraint.

---

## 2. Layer 1 — Ingestion

**Responsibility.** Parsers per source, each producing a canonical ball-level record (PRD §6).

**Contract.**

| Property | Statement | Source |
|---|---|---|
| Granularity | One row per delivery | PRD §6 |
| State convention | Match state as it stood **before** the ball | PRD §6, ctx §2 |
| Consumers | Every downstream model reads this schema and nothing else | PRD §6 |
| Consequence | A new data source is an ingestion problem, never a modelling one | PRD §6 |

**Parsers, one per source, by tier** (PRD §5, ctx §3):

| Tier | Source to parse | Fields it carries in |
|---|---|---|
| 0 | Cricsheet ball-by-ball JSON | batter, bowler, runs, extras, dismissal type, credited fielders, match state |
| 1 | Ball-by-ball commentary text, classified | shot played, fielding event type, approximate delivery description |
| 2 | Ball tracking (Hawk-Eye and equivalents), or a franchise/league partner already licensing it | release point, speed, trajectory, pitch location, deviation off the surface, bounce, impact point, ball flight after contact |
| 3 | Pose tracking, bat sensors, or vendor-provided skeletal data | footwork, trigger movement, weight transfer, bat swing path, face angle at contact, bat speed |

**Explicit absences at Tier 0** — Cricsheet does not contain where the ball pitched, what shot was played, where fielders stood, or any physical measurement (PRD §5). The architecture must represent these as *absent*, not as null-and-forgotten, because what the model cannot see is displayed alongside what it can (PRD §4.5).

**Boundary rule.** "Protect this boundary hard" (ctx §5); "the canonical ball record is sacred… new sources adapt to the schema; the schema does not adapt to sources" (ctx §17).

**The Tier 1 commentary pipeline splits across two layers** (settled — CONTEXT.md §3):

- The **scraper is a parser** and belongs in this layer. It is deterministic, has no training data, and **fails loudly** rather than degrading.
- The **classifier is a model** and belongs in the model layer (§4). It is trained, carries a held-out accuracy figure, and its version is part of the provenance triple (§8).

The layer boundary therefore falls between retrieving the commentary text and labelling it. What the classifier emits is a label of moderate and uneven reliability (PRD §5), which is exactly why it needs a model's calibration diagnostics rather than a parser's pass/fail.

---

## 3. Layer 2 — Feature and label store

**Responsibility.** Derived per-ball attributes (PRD §6, ctx §5):

- phase
- required rate
- pressure state
- delivery attributes **where available**
- shot label
- fielding event

**Two properties, both hard:**

**Versioned.** (PRD §6)

**Immutable once written.** Corrections create new versions rather than mutating history, *because a model result that cannot be reproduced is not evidence* (PRD §6, ctx §5). Restated as a working rule: "never mutate the feature store — corrections are new versions" (ctx §17).

**"Where available" is the tier seam.** Delivery attributes exist only at Tier 2, shot labels only from Tier 1, biomechanical inputs only at Tier 3 (PRD §5). This layer is therefore where tier availability becomes a per-row, per-column fact rather than a global system mode — which is what makes graceful degradation (PRD §9) implementable downstream.

**Derived:** the store must expose *which* tier populated each attribute, not merely its value, since surfaces must mark reduced capability clearly (PRD §9) and shrinkage strength must be visible (PRD §10, ctx §10). Neither document specifies the mechanism.

---

## 4. Layer 3 — Model layer

**Responsibility.** Independently trained, independently versioned components (PRD §6, PRD §7).

**Three invariants** (PRD §6, ctx §5):

1. Each component **exposes a scoring interface**.
2. Each component **publishes its own calibration diagnostics**.
3. Models are **trained offline; nothing is fitted at request time**.

Invariant 3 is restated as a non-functional requirement: all model outputs precomputed, interactive surfaces read stored results, sub-second response on every view, no request-time fitting (PRD §9, ctx §9, ctx §17).

**Components and their tier gates** (PRD §7, ctx §6):

| ID | Component | Tier | Ship bar (PRD §7) |
|---|---|---|---|
| M1 | Value functions — run expectancy over (balls remaining, wickets lost); win probability over (balls remaining, wickets lost, runs required). Empirical, binned, blended with a fitted surface where cells are sparse, monotonicity enforced | 0 | Calibration holds out of sample **and** the surface is monotone in both arguments across the full grid |
| M2 | Fielding value — prices every credited dismissal, attributes a share to fielders, charges each player an expected share based on field time, reports the residual as runs above average | 0, improved at 1 | Rankings survive sensitivity analysis across credit regimes **and** it beats a catches-per-match baseline out of sample |
| M3 | Batting and bowling value — RAR, phase- and context-adjusted. Implementation, not research; its purpose is to put all three disciplines on one axis | 0 | Reproduces published context-adjusted measures within a defensible tolerance |
| M4 | Delivery response surface — E[runs] and P(wicket) by line, length, speed, deviation, phase, match state. Hierarchical: batter → batter-type prior → league prior, because individual batters have few balls in most cells. **The bowler-side counterfactual:** perturb an input, re-query, compare | 2 | Out-of-sample log loss beats a batter-marginal baseline by a meaningful margin **and** shrinkage behaviour is documented per cell |
| M5 | Shot classification and conditional distribution — P(shot \| delivery, batter), run and wicket distribution per shot per cell | 1 labels, 2 conditioning | Classification accuracy validated against a hand-labelled hold-out **and** per-shot distributions stable under resampling |
| M6 | Shot availability — which shots were on the menu, given footwork, weight transfer and time available | 3 | **Not started until a Tier 3 data source is confirmed** |
| M7 | Option-set solver — composite of M4, M5, M6 | composite | — |
| M8 | Squad value and selection — M2 + M3 into total player value; optimises an XI under constraints with an uncertainty interval on the projected total | 0 | — |
| M9 | Market price model — predicts what the market will pay, making model-value-minus-predicted-price an explicit arbitrage estimate | 0 + auction price data | — |

**Dependency graph** (ctx §6):

```
        M1 value functions (T0)
             │
     ┌───────┼─────────────┐
     │       │             │
 M2 fielding  M3 bat/bowl   M4 response surface (T2)
  (T0→T1)      (T0)              │
     └───┬───────┘               │      M5 shot dist. (T1 labels, T2 conditioning)
         │                       │           │
      M8 squad & XI (T0)         └─────┬─────┘         M6 availability (T3, not started)
         │                             │                     │
      M9 market price (T0 + auction)   └────────── M7 option-set solver ──┘
```

**M1 is the denominator.** Every other value number is denominated against the value functions (ctx §2). Architecturally this makes M1 the one component whose version change invalidates the outputs of the components above it in the graph.

**M2's known ceiling at Tier 0** — it sees only the fraction of fielding that ends in a wicket (PRD §7). This must be stated in the UI, not in a footnote (ctx §6).

**Where hierarchy lives.** Shrinkage is a requirement, not an optimisation, and the amount applied must be visible to the user (PRD §10). M4 is explicitly hierarchical (PRD §7). PyMC or NumPyro is designated for hierarchical models where interval quality matters, because shrinkage and uncertainty are product requirements, not decorations (PRD §12).

---

## 5. Layer 4 — Decision layer

**Responsibility.** Where models compose into answers (PRD §6).

**Residents** (PRD §6, ctx §5):

- the **option-set solver** (M7)
- the **selection optimiser** (M8)
- the **auction valuer** (M9)

**What this layer owns that no other layer may.** The assumptions that turn model outputs into recommendations — credit shares, replacement level, constraint definitions — and every one of them is configurable and surfaced in the interface (PRD §6). The non-functional requirement names the full set: credit shares, replacement level, shrinkage strength and phase boundaries, configurable, visible in the interface, and included in every export (PRD §9, ctx §9). Working rule: "assumptions are parameters, not constants" (ctx §17).

**M7's graceful degradation is a decision-layer behaviour** (PRD §7): without M6, it treats the menu as a function of the delivery and the batter's general profile, which is an approximation and **must be labelled as one in the interface**. Restated in ctx §6 and again as a working convention (ctx §17). This is the mechanism that guards against the stated failure mode of presenting single-ball counterfactuals prescriptively, being contradicted by a coach in a meeting, and losing the room permanently (PRD §15, ctx §16).

**Causal validity is a decision-layer design constraint, not a caveat** (PRD §10): a shot the model says was available may not have been available *to that batter, on that ball, having already committed*; the mitigation is distributional framing. This layer is where prescriptive framing could enter the system, so it is where the mitigation must be enforced.

**Derived:** the two-sided output of M7 — the delivery that minimises the value of the batter's best available response, and the shot with the highest expected value given what is available (PRD §2) — is a single computation read from two ends, not two features. The PRD states the symmetry; it does not state the implementation consequence.

---

## 6. Layer 5 — Surfaces

**Responsibility.** Web application, exports, and an API (PRD §6).

**Stated position:** "The interface is not a view onto the models; it is where the assumptions become visible and arguable" (PRD §6, ctx §5).

| Surface | Primary user | Core question answered | Tier |
|---|---|---|---|
| Leaderboard | Analyst | Who is good at this, adjusted for opportunity? | 0 |
| Player 360 | Coach, analyst | What is this player worth, and where does it come from? | 0 |
| Matchup Explorer | Bowling coach | Where do I bowl to this batter, and why? | 2 |
| Shot Menu | Batting coach | What was available, what was chosen, what did the gap cost? | 2–3 |
| XI Builder | Selector | Which eleven, and what does the model say it is worth? | 0 |
| Auction Board | Recruitment | What is my maximum bid, and where is the market wrong? | 0 |
| Methodology | Everyone | Why should I believe any of this? | — |

*(PRD §8)*

**Methodology is not documentation. It is a product feature, and in a market where the buyer is a professional sceptic it may be the most important one** (PRD §8, ctx §7).

**Surface-to-model mapping** — **Derived** from the tier column (PRD §8) and the dependency graph (ctx §6); the PRD does not tabulate this:

| Surface | Reads from |
|---|---|
| Leaderboard | M2, M3 |
| Player 360 | M2, M3 (Tier 0 floor); M4, M5 where tier allows |
| Matchup Explorer | M4, via M7 |
| Shot Menu | M5, M6, via M7 |
| XI Builder | M8 |
| Auction Board | M9 |
| Methodology | Every model's published calibration diagnostics (PRD §6) and the decision layer's assumption set (PRD §9) |

**Actionability constraint on Matchup Explorer.** The bowling coach cares about actionability over sophistication and will not use anything that cannot be translated into a target on a length map (PRD §3, ctx §8). This is a hard requirement on the surface, not a presentation preference.

---

## 7. Cross-cutting — tier gating and graceful degradation

**The rule:** every surface must render, with clearly marked reduced capability, when a higher-tier data source is unavailable (PRD §9, ctx §9).

Tier is therefore not a deployment configuration; it propagates through all five stages:

| Layer | How tier manifests |
|---|---|
| Ingestion | Which parsers exist and run (PRD §5) |
| Feature store | Which per-ball attributes are populated — "delivery attributes **where available**" (PRD §6) |
| Model layer | Which components can exist at all — "each tier unlocks a specific set of models and cannot be skipped" (PRD §5); M6 not started until a Tier 3 source is confirmed (PRD §7) |
| Decision layer | M7 degrades to a labelled approximation without M6 (PRD §7) |
| Surfaces | Render with clearly marked reduced capability (PRD §9) |

**What each tier unlocks** (PRD §5):

- **Tier 0** — value functions, fielding value from dismissals, batting and bowling RAR, squad selection, auction valuation.
- **Tier 1** — complete fielding value, first-pass shot distributions, bootstrap labels for later supervised models.
- **Tier 2** — the delivery response surface, conditional shot distributions, the bowler-side counterfactual: **approximately half the core value proposition**.
- **Tier 3** — the shot availability model, the part that explains *why* an option was or was not on the menu.

**Access reality constrains the build, not just the roadmap.** Tiers 2 and 3 cannot be bought by an individual; they are unlocked by partnership with a league, franchise, vendor or academy — a business-development problem wearing a technical costume (PRD §10, ctx §10). The tier structure exists partly so that a single builder can ship something complete at Tier 0 rather than something partial across all four (PRD §10). The first-listed failure mode is building Tier 2 and 3 models before securing Tier 2 and 3 data, and having nothing shippable (PRD §15).

**Working rule:** check tier before proposing work; if a task needs Tier 2 or 3 data that is not secured, say so rather than building toward it (ctx §17).

---

## 8. Cross-cutting — reproducibility and versioning

**Requirement.** Any published number must be regenerable from a versioned dataset and a versioned model. *This is the difference between a research product and an opinion* (PRD §9).

**Versioning obligations by layer:**

| Layer | Obligation | Source |
|---|---|---|
| Feature store | Versioned; immutable once written; corrections create new versions | PRD §6 |
| Model layer | Independently versioned components; model artifacts versioned and tagged | PRD §6, §12 |
| All | Every published figure traceable to a tag | PRD §12 |

**Mechanisms** (PRD §12, ctx §12): Git for code, DVC or content-addressed Parquet for data, a lightweight experiment log for model runs.

**Derived:** a published number's provenance is the tuple (dataset version, model version, assumption set), because the decision layer's configurable assumptions (PRD §9) change outputs without changing either data or model. The PRD requires reproducibility from a versioned dataset and a versioned model and separately requires assumptions in every export; it does not join the two into a single provenance record.

---

## 9. Cross-cutting — uncertainty, auditability, transparency

These three are product principles (PRD §4) with non-functional teeth (PRD §9), and they constrain the architecture rather than the presentation.

**Uncertainty.** Every headline number ships with an interval. **A point estimate presented alone is a defect** (PRD §4.3, ctx §9). M8 carries an uncertainty interval on the projected total (PRD §7). Interval quality is why Bayesian machinery is designated for hierarchical models (PRD §12).

**Auditability.** Every aggregate drills down to the deliveries that produced it. *A coach who cannot see the balls behind a number will not trust it, and should not* (PRD §9). No unexplainable outputs in a coaching context (PRD §4.6). Working rule: every number ships with an interval **and** a drill-down; if you cannot provide both, the feature is not done (ctx §17).

**Assumption transparency.** Credit shares, replacement level, shrinkage strength and phase boundaries — configurable, visible in the interface, and included in every export (PRD §9).

**Limitations in the interface.** What the model cannot see is displayed alongside what it can — *the single strongest trust-building decision available, and it is cheap* (PRD §4.5).

**One scale.** Batting, bowling and fielding value are reported in runs above replacement; if two things cannot be compared, the model has failed at its central job (PRD §4.2). Architecturally this is why M3's purpose is stated as putting all three disciplines on one axis (PRD §7) and why M8 can compose M2 and M3 at all.

---

## 10. Tooling by layer

Mapping of the settled tooling (PRD §12, ctx §12) onto the layers. **Derived** as a mapping; each individual choice is from the PRD.

| Layer | Tooling |
|---|---|
| Ingestion | Python; pandas or polars for ball-level work, **polars once volumes reach tracking scale** |
| Feature store | **Parquet** for the ball store; **DuckDB** for analytical queries |
| Model layer | scikit-learn and gradient boosting for classification and response surfaces; **PyMC or NumPyro** for hierarchical models where interval quality matters |
| Decision layer | (not specified in either source) |
| Surfaces | **FastAPI** backend on Render, **Next.js** frontend on Vercel — both already in use; neither is the interesting part of this system |
| Application state | **Postgres** |
| Reproducibility | Git; DVC or content-addressed Parquet; lightweight experiment log |
| Tier 3 CV, only if building rather than buying | MediaPipe or MMPose — **prefer vendor-supplied data over in-house CV in almost every case; the CV problem is a company on its own** |

**No warehouse until there is a reason for one** (PRD §12).

**Development.** Claude Code for the iterative, messy work — parsers, scrapers, feature engineering. **Least useful for the statistical design decisions, which need to be reasoned about rather than generated** (PRD §12, ctx §12).

---

## 11. Architectural invariants

Consolidated from PRD §6, §9 and ctx §17. These are the rules a change must not break.

1. **One row per delivery; match state always pre-ball.** New sources adapt to the schema; the schema does not adapt to sources.
2. **Downstream reads the canonical schema and nothing else.** A new data source is an ingestion problem, never a modelling one.
3. **The feature store is never mutated.** Corrections are new versions.
4. **Nothing is fitted at request time.** All model outputs precomputed; surfaces read stored results; sub-second response on every view.
5. **Every model publishes its own calibration diagnostics**, and reports its margin over a *named* naive baseline (PRD §13).
6. **Every number ships with an interval and a drill-down to its deliveries.**
7. **Assumptions are decision-layer parameters** — configurable, surfaced, and included in every export.
8. **Approximations are labelled in the interface**, M7-without-M6 above all.
9. **Every surface renders at every tier**, with reduced capability clearly marked.
10. **Check the tier before building.** Do not build Tier 2/3 models against unsecured Tier 2/3 data.

---

## 12. What this architecture deliberately does not include

From PRD §5 and ctx §4:

- **Football** — the architecture generalises and the eventual ambition is real, but explicitly deferred.
- **Live in-match automation** — latency, integration and governance requirements disproportionate at this stage. **The system is a preparation and review tool.** This is the single largest architectural simplification available and it should not be quietly given up.
- **Betting or odds products.**
- **Fan-facing consumer app** — fans, fantasy players and betting participants are explicit non-users (PRD §3).
- **Test cricket in the first architecture** — the value functions differ structurally enough (no fixed resource limit) to warrant separate treatment.

---

## 13. Unresolved, where it touches architecture

From PRD §14, restricted to the questions with architectural consequences:

- **Which data partner, and what do they get?** Each option implies a different product and a different set of restrictions (PRD §14.1). Vendor tracking data will come with redistribution restrictions that constrain what can be shown publicly (PRD §10) — a surfaces-layer and export-layer constraint whose shape is not yet known.
- **Business model** — different implications for how much of the system needs to be self-serve (PRD §14.2).
- **Public model versus proprietary** — working assumption is that the moat is data relationships and domain trust, not code, but this should be a decision, not a default (PRD §14.5).
- **Test cricket** — whether the value-function architecture extends or needs replacing (PRD §14.6). This is a question about M1, and therefore about the denominator of every other number in the system.

**Settled at this level** (CONTEXT.md §3):

- **The commentary scraper is a parser; the commentary classifier is a model.** The scraper is deterministic, has no training data and fails loudly, so it belongs in ingestion (§2). The classifier is trained and has a held-out accuracy figure, so it belongs in the model layer (§4) and its version enters the provenance triple (§8). The Tier 1 pipeline crosses a layer boundary between fetching the text and labelling it.

**Open at this level and not settled by either document** (**Derived**):

- How the feature store records *which tier* populated an attribute, given that surfaces must mark reduced capability — §3 above.
- The decision layer's tooling, which neither document specifies — §10 above.

---

## 14. The web layer

**Only the shell is built.** `web/` exists as of `6a8a4fb` (MILESTONE Phase 1): a Next.js app that builds to a static export, the build step described below, and a single provenance page reading `meta.json`. The leaderboard, player detail, compare and methodology views are not built; where this section describes them, it is written in the present tense about the design rather than about the repository as it stands. `scripts/export_web.py` exists and produces the data described below.

The PRD places the web application in the surfaces layer (PRD §6, §8) and specifies Next.js on Vercel (PRD §12). This section says how that surface attaches to the rest of the system.

### Position and the one-way dependency

`web/` sits downstream of everything in §1's chain, reading the model's output and never its code:

```
  Model layer  →  Decision layer  →  scripts/export_web.py  →  web-data/  →  web/
                                        (Python, offline)      (JSON)      (Next.js)
```

**The frontend never imports Python and never calls it.** The only interface between the two halves of the system is a directory of JSON files with a fixed shape. This is the ingestion rule (PRD §6) applied at the other end of the pipeline: as a new data source is an ingestion problem and never a modelling one, a new view is a frontend problem and never a modelling one. If a page needs a number that is not in the JSON, the fix is a change to the exporter and a re-export, never a calculation in the browser.

**Derived:** the exporter, not the frontend, is the boundary object. The PRD names the web application as a surface and requires precomputed outputs (PRD §9), but does not name an export step; that step is what makes the no-Python rule enforceable rather than aspirational.

### The data contract

What `scripts/export_web.py` actually writes into `web-data/`, as observed on the IPL run:

| File | Contains | Read by |
|---|---|---|
| `players.json` | A JSON array of 528 objects, one per qualified fielder: `fielder`, `slug`, `role`, `rank`, `balls_in_field`, `keeper_balls`, `outfield_balls`, `catches`, `run_outs`, `stumpings`, `runs_saved`, `expected_runs_saved`, `fraa`, `fraa_per_100`, `wpa` | Leaderboard; the search index behind player and compare routes |
| `seasons/<slug>.json` | One file per player, 528 of them. An object with `fielder`, `slug` and `seasons`, the last being that player's rows carrying the career fields plus `season`, `innings_fielded`, `unknown_balls`, `fraa_per_100_raw`, `wpaa` and `qualifies` | Player detail; compare, which reads exactly two of these |
| `seasons/index.json` | An object mapping display name to slug, 528 entries | Name lookup without loading `players.json` |
| `meta.json` | Provenance and assumptions — see below | The methodology page, and the footer of every page |

**The site serves every file under `/data/`**, at the path it has inside `web-data/`: `/data/players.json`, `/data/seasons/<slug>.json`, `/data/seasons/index.json`, `/data/meta.json` (`web/scripts/copy-data.mjs`, `web/lib/meta.ts`).

**Derived, and settled by the Phase 1 build:** generated data is namespaced under one directory rather than written into the site root, which keeps the root available for static assets and means no exported filename can collide with one. It also makes the copy a single directory the build can delete and replace wholesale, which is what lets a failed build remove a stale copy instead of leaving one behind.

Two properties of that table are load-bearing. The season files are split per player because a comparison view opens two players and not all 528: the split turns a 1.1 MB fetch into about 3.8 KB. And `players.json` deliberately omits `unknown_balls`, which the season files carry, so the two files are not interchangeable — a view needing the unknown-bucket split must read the season file.

**The frontend computes nothing.** Every displayed number is a field read from the JSON as exported. `fraa_per_100` is not derived in the browser from `fraa` and `balls_in_field`; it is read. This follows from the requirement that nothing is fitted at request time and interactive surfaces read stored results (PRD §9, ctx §9), and it extends that rule from fitting to arithmetic: a browser that recomputes a figure has forked the model, and the fork will drift.

Sorting, filtering to a search string, and paging are presentation and belong in the frontend. Anything that changes what a number means does not.

### Provenance

`meta.json` carries the dataset facts (`matches`, `deliveries`, `season_min`, `season_max`), the export identity (`generated_at`, `git_commit`, `git_dirty`, `git_source`), the full `assumptions` object — `CREDIT_SHARE`, `RUN_OUT_PRIMARY_SHARE`, `FIELD_TIME_NORMALISATION`, `FIELDERS_PER_SIDE`, `CATCH_MODAL_MIN`, `CATCH_MODAL_MARGIN`, `SEASON_BASELINE_SHRINKAGE_BALLS`, `regression_balls`, `min_balls`, `season_qualify_balls` — and a `caveats` array.

This is what makes a number on a page traceable. A figure shown in the browser came from a named field, in a named file, produced by a named commit, under a named set of assumptions. That chain satisfies the reproducibility requirement (PRD §9) and the assumption-transparency requirement that credit shares, replacement level, shrinkage strength and phase boundaries are visible in the interface and included in every export (PRD §9, ctx §9). Because the assumptions travel inside the export rather than being written into the page, a page cannot describe a model version it was not built from.

**What breaks when the export and the deploy come from different commits.** The failure is silent, which is what makes it worth designing against. The page renders, every number displays, and the methodology page states assumptions that were not the ones used. Two concrete cases have occurred in this repository:

- A local `web-data/meta.json` recorded `git_commit: f3e0a79` while `HEAD` was `788685e`. The export ran before the commit that changed the exporter. Nothing about the artefact announces this; only comparing the two reveals it.
- That same file recorded `git_dirty: null`, not `false`. `git_commit()` falls back to reading `.git` directly when no git executable can be found, and the fallback can recover the commit but cannot tell whether the tree was clean. A null there means the dirty state is unknown, not that the tree was clean.

**Three provenance states, and the interface must distinguish them.** `meta.json` carries `git_dirty` alongside `git_dirty_known` precisely so that null cannot be misread:

| `git_dirty_known` | `git_dirty` | Meaning | How the methodology page renders it |
|---|---|---|---|
| `true` | `false` | Tracked files match the recorded commit; it describes the code that ran | the commit, plainly |
| `true` | `true` | Tracked files were modified; the commit does **not** describe the code that ran | the commit, marked as modified |
| `false` | `null` | No git executable was found; nobody checked | "unknown", never "clean" |

`git_dirty` reports **tracked** modifications only (`git status --porcelain --untracked-files=no`). Untracked files are deliberately excluded, because an export always runs beside things that are not in the repository — a downloaded `ipl_json.zip`, its own `web-data/` output — and none of them says anything about whether the code that ran matches the commit being reported. The first CI export got this wrong and reported `git_dirty: true` on a pinned checkout into an empty directory, where a tracked file could not possibly have been modified.

**A consumer must read `git_dirty_known` before `git_dirty`.** Treating the null as falsy renders the third row as the first, which states on a methodology page that a number came from an unmodified commit when nothing verified that. This is the same class of error as displaying a point estimate without its interval (PRD §4.3): the number is not wrong, the confidence attached to it is invented. The exporter also prints a warning at export time for all three failing cases rather than recording them silently (`scripts/export_web.py`).

**Derived:** the build should therefore compare `meta.json`'s `git_commit` against the commit being deployed and fail when they differ, rather than trusting them to match. The PRD requires reproducibility but does not specify an enforcement point; without one, the requirement holds only by convention.

### The build step

`web-data/` is generated and gitignored, so it is absent from a fresh clone. The build copies it into `web/public/data/` — the frontend fetches `/data/players.json` and `/data/seasons/<slug>.json` as static assets from its own origin, so no CORS configuration and no asset host is involved (`web/scripts/copy-data.mjs`).

**If `web-data/` is missing at build time, the build fails loudly and does not produce a site.** A frontend that renders an empty leaderboard when its data is absent is indistinguishable from one whose data is wrong, and the second is far more expensive. This is the same reasoning that makes the commentary scraper a parser rather than a model in §2: a deterministic step with no data should stop, not degrade. `npm run build` runs `web/scripts/copy-data.mjs` ahead of `next build`; it exits 1 naming the missing directory, and deletes any earlier `web/public/data/` so that a failed build leaves nothing stale to serve.

**Settled: CI is the canonical producer of `web-data/`** (`.github/workflows/export.yml`). The workflow runs the exporter on `ubuntu-latest` against a freshly downloaded Cricsheet bundle and publishes the result as a build artefact. A local export remains useful during development; it is not the thing that gets published.

The reason is provenance rather than convenience. A CI job runs on a clean checkout of a pushed commit, so `git rev-parse` returns exactly the commit the code came from and `git status` is empty — `meta.json` records `git_commit` accurately, `git_dirty` false and `git_dirty_known` true, which is the top row of the table above. A local export can promise none of that: it runs against whatever is in the working tree, usually dirty mid-development, on a machine where `git` may not be on PATH at all, in which case the exporter falls back to reading `.git` and lands in the third row. The mismatch documented above — `meta.json` recording `f3e0a79` while `HEAD` was `788685e` — is a local export, and it is exactly the failure CI removes by construction.

Two properties of that workflow are load-bearing. The downloaded bundle is checked for the PK magic number, zip integrity and a plausible entry count before the export runs, because an error page served with a 200 is indistinguishable from a bundle until something looks at the bytes. And the artefact upload deliberately omits `if: always()`: the reconciliation check runs before the files are written, so a failed export still leaves `web-data/` on disk, and uploading it regardless would publish an artefact the job had already judged wrong.

**Derived, still open:** whether the artefact is consumed by the deploy directly, promoted to a release, or committed. Publishing also interacts with §13's unresolved question about vendor redistribution restrictions — Tier 2 data will carry limits on what can be shown publicly, and the export is where those limits bite.

### Rendering strategy

Static export. The site is a set of prebuilt HTML, JS and JSON assets; the browser fetches JSON and renders. **No API routes, no backend service, no database.**

This is not minimalism for its own sake — it is the architecture the model already forces. All model outputs are precomputed, interactive surfaces read stored results, and nothing is fitted at request time (PRD §9). A system whose data changes only when a Python job is re-run has nothing for a server to do at request time. Adding one would introduce a component that can disagree with the export, and the PRD's latency requirement (sub-second on every view) is met by static assets without further engineering.

The FastAPI backend named in the PRD's tooling (PRD §12) is therefore **not** part of this milestone. It becomes necessary when something must happen per-request — user accounts, saved state, a query too large to ship as a static file — and none of those is in the fielding MVP.

### What is deliberately not in the web layer

- **No model logic.** No credit shares, no baselines, no shrinkage, no role resolution. Those live in `cricfield/fielding.py` and reach the browser only as numbers.
- **No recomputation.** Not even arithmetic that looks safe. A rate is read, never divided out.
- **No filtering that changes what a metric means.** Hiding rows below a threshold is presentation; recomputing a rank or a baseline over the filtered subset is modelling. The `qualifies` flag exists precisely so the frontend can hide thin player-seasons without recomputing anything: the exporter sets it at 240 balls, records the threshold in `meta.json`, and exports every row regardless (`scripts/export_web.py`).
- **No new aggregates.** A page that needs a total, a mean or a rank computes it in the exporter and reads it, or it does not show it.
