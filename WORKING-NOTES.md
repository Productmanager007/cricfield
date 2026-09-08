# cricfield — working context

**Purpose of this file.** Orientation for anyone (human or agent) picking up work on cricfield. It distils [PRD.md](PRD.md) — the system-level PRD — into the things you need in working memory: what the system is, what the words mean, what the data contract is, what depends on what, what order to build in, and which decisions are settled versus open.

The PRD is the source of truth for intent. This file is the source of truth for *how the work is organised*. Where they disagree, the PRD wins on "what" and this file wins on "how" — and the disagreement should be resolved rather than left standing.

**Owner:** Manu S Nair · **Status:** pre-build (repo contains the PRD only) · **Last aligned to PRD:** draft-for-review revision

---

## 1. One-paragraph statement

cricfield prices the *options* available at each moment of a cricket match rather than reporting averages of what happened. On every delivery the bowler picks from a set of deliveries he can bowl and the batter, having read it, picks from a set of shots available given his position, technique and remaining time. If both sets can be valued, one model serves the bowling coach ("what do I bowl here?"), the batting coach ("what was on the menu and what did the choice cost?"), the analyst ("where is this player weak?") and the selector ("who plays, and what are they worth?"). Weakness analysis is not a separate feature — a weakness *is* a region of the delivery space where a player's best available option is worth less than the population's.

Everything is reported in **runs above replacement**, so batting, bowling and fielding sit on one axis, and every headline number carries an interval.

---

## 2. Vocabulary

These terms are used precisely throughout the codebase. Use them consistently in code, column names and UI copy.

| Term | Meaning |
|---|---|
| **Option set** | The choices genuinely available to a decision-maker at a moment. Two per delivery: the bowler's deliveries, the batter's shots. The unifying object of the whole system. |
| **Delivery space** | The multidimensional space a delivery occupies — line, length, speed, deviation, bounce — conditioned on phase and match state. |
| **Response surface** | E[runs] and P(wicket) as a function of position in delivery space, for a given batter. Model M4. |
| **Availability** | Whether a shot was physically on the menu given footwork, weight transfer, and time. Model M6; the hardest and most valuable piece. |
| **Match state** | Balls remaining, wickets lost, runs required (chases), as they stood **before** the ball. Never after. |
| **Value function** | Run expectancy (1st innings) or win probability (chase) over match state. Model M1; every other value number is denominated against it. |
| **RAR** | Runs above replacement. The single scale. |
| **Credit share** | The configurable assumption splitting a dismissal's value across contributing fielders. A decision-layer parameter, never hardcoded. |
| **Shrinkage** | Pulling a sparse individual estimate toward a batter-type prior, then a league prior. A requirement, not an optimisation — and its strength must be visible to the user. |
| **Tier** | Data access level (0–3). Gates which models can exist at all. |
| **Phase** | Powerplay / middle / death, with configurable boundaries. |

---

## 3. The tier structure — the spine of the project

Data access, not modelling skill, is the binding constraint. Scope is organised by tier because tiers cannot be skipped.

| Tier | Source | Gives you | Access reality |
|---|---|---|---|
| **0** | Cricsheet ball-by-ball JSON | batter, bowler, runs, extras, dismissal type, credited fielders, match state | Free, open, available today |
| **1** | Ball-by-ball commentary text, classified | shot played, fielding event type (clean stop, misfield, boundary save, drop, direct hit), rough delivery description | Scrapeable; reliability moderate and uneven — commentary is written for readers, not models |
| **2** | Ball tracking (Hawk-Eye and equivalents) | release point, speed, trajectory, pitch location, deviation, bounce, impact point, post-contact flight | **Gated.** Not purchasable by an individual. Requires a partner |
| **3** | Biomechanics (pose, bat sensors, vendor skeletal data) | footwork, trigger movement, weight transfer, swing path, face angle, bat speed | Gated, and in several cases not systematically captured at all |

**What this means operationally:**

- Tier 0 and 1 work is *unblocked and should be shipped complete*. A finished Tier 0 product beats a partial spread across four tiers — especially with one builder.
- Tier 2 unlocks roughly **half the core value proposition** (the bowler-side counterfactual). It is unlocked by business development, not engineering.
- Tier 3 models are **specified but not started** until a confirmed data source exists.
- Every surface must render at every tier, with reduced capability *clearly marked in the interface*, never silently degraded.

**The dominant failure mode of this project is building Tier 2/3 models before securing Tier 2/3 data and having nothing shippable.** Treat any drift toward that as a red flag.

---

## 4. Scope boundaries

**In:** Everything buildable at Tiers 0–1 on public data. Tier 2 models conditional on a partnership. Tier 3 specified only. Men's and women's **T20** primary; **ODI** secondary, sharing the same value-function machinery.

**Out, deliberately:**

- **Football** — the architecture generalises and the ambition is real, but every hour before cricket ships produces nothing sellable.
- **Live in-match automation** — latency, integration and governance costs are disproportionate now. This is a *preparation and review* tool.
- **Betting / odds products** — adjacent technically, a different company ethically and strategically.
- **Fan-facing consumer app**; fans, fantasy and betting users are explicit non-users.
- **Test cricket** in the first architecture — no fixed resource limit means the value functions differ structurally.

---

## 5. Architecture — four layers, clean interfaces

```
  Ingestion  →  Feature & label store  →  Model layer  →  Decision layer  →  Surfaces
   (parsers)      (versioned, immutable)   (offline-trained)  (assumptions live here)  (web/API/export)
```

**Ingestion.** One parser per source, each emitting the *same* canonical ball-level record: one row per delivery, match state as it stood before the ball. Every downstream model reads this schema and nothing else. Consequence: a new data source is an ingestion problem, never a modelling one. Protect this boundary hard.

**Feature and label store.** Derived per-ball attributes — phase, required rate, pressure state, delivery attributes where available, shot label, fielding event. Versioned and **immutable**: corrections create new versions rather than mutating history, because a model result that cannot be reproduced is not evidence.

**Model layer.** Components trained and versioned independently (§6). Each exposes a scoring interface and publishes its own calibration diagnostics. **Nothing is fitted at request time.**

**Decision layer.** Where models compose into answers: the option-set solver, the selection optimiser, the auction valuer. This layer holds the assumptions that turn outputs into recommendations — credit shares, replacement level, constraint definitions — and **every one is configurable and surfaced in the UI**.

**Surfaces.** Web app, exports, API. The interface is not a view onto the models; it is where the assumptions become visible and arguable.

---

## 6. Model inventory and dependency graph

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

| ID | Model | Tier | Ships when |
|---|---|---|---|
| **M1** | Value functions — run expectancy over (balls, wickets); win probability over (balls, wickets, runs required). Empirical + binned, blended with a fitted surface where cells are sparse, monotonicity enforced | 0 | Calibration holds out of sample **and** the surface is monotone in both arguments across the full grid |
| **M2** | Fielding value — prices credited dismissals, attributes a share to fielders, charges each an expected share by field time, reports residual as runs above average | 0 (better at 1) | Rankings survive sensitivity analysis across credit regimes **and** beat a catches-per-match baseline out of sample |
| **M3** | Batting & bowling RAR, phase- and context-adjusted. Well-trodden; implementation, not research. Its job is putting three disciplines on one axis | 0 | Reproduces published context-adjusted measures within a defensible tolerance |
| **M4** | Delivery response surface — E[runs], P(wicket) by line, length, speed, deviation, phase, state. Hierarchical: batter → batter-type prior → league prior. **This is the bowler-side counterfactual** | 2 | Out-of-sample log loss beats a batter-marginal baseline by a meaningful margin **and** shrinkage behaviour is documented per cell |
| **M5** | Shot classification + conditional distribution — P(shot \| delivery, batter), run/wicket distribution per shot per cell | 1 labels, 2 conditioning | Classification validated against a hand-labelled hold-out **and** per-shot distributions stable under resampling |
| **M6** | Shot availability — what was actually on the menu. Deepest coaching insight, hardest component | 3 | **Not started until a Tier 3 source is confirmed** |
| **M7** | Option-set solver — composes M4+M5+M6 into the two-sided answer. **Degrades gracefully:** without M6 it treats the menu as a function of delivery + general batter profile, an approximation that **must be labelled as one in the interface** | composite | — |
| **M8** | Squad value & selection — M2+M3 into total player value; optimises an XI under constraints (overseas slots, role balance, venue) with an interval on the projected total | 0 | — |
| **M9** | Market price model — predicts what the market pays, so model value minus predicted price is an explicit arbitrage estimate | 0 + auction price data | — |

**M2 known ceiling at Tier 0:** it sees only the fraction of fielding that ends in a wicket. State this in the UI, not in a footnote.

---

## 7. Surfaces

| Surface | Primary user | Question answered | Tier |
|---|---|---|---|
| Leaderboard | Analyst | Who is good at this, adjusted for opportunity? | 0 |
| Player 360 | Coach, analyst | What is this player worth, and where does it come from? | 0 |
| Matchup Explorer | Bowling coach | Where do I bowl to this batter, and why? | 2 |
| Shot Menu | Batting coach | What was available, what was chosen, what did the gap cost? | 2–3 |
| XI Builder | Selector | Which eleven, and what is it worth? | 0 |
| Auction Board | Recruitment | What is my maximum bid, and where is the market wrong? | 0 |
| **Methodology** | Everyone | Why should I believe any of this? | — |

Methodology is **not documentation — it is a product feature**, and in a market whose buyer is a professional sceptic it may be the most important one.

---

## 8. Users, and what each will reject

Design decisions should be checkable against these.

- **Bowling coach / bowling analyst** — needs the delivery-space response surface per batter, filterable by phase and match state. Cares about actionability over sophistication. **Will not use anything that cannot be translated into a target on a length map.**
- **Batting coach** — needs shot-level distributions and the availability model. **Highly sceptical of prescriptive single-ball counterfactuals**; responds to distributional claims.
- **Team analyst / selector** — needs unified value across all three disciplines, opposition- and venue-conditioned, with uncertainty. This is the user for whom **fielding value on the runs scale is the novel unlock**.
- **Recruitment / auction strategist** — needs value in a currency plus a model of what the market will pay.
- **Broadcast/media analyst (secondary)** — lower rigour bar, higher volume, faster cycle. A distribution and revenue channel, **not a design constraint**.

---

## 9. Principles — the tests to apply to any change

1. **Price options, not outcomes.** Everything reported answers "what was this worth, given what else was possible?"
2. **One scale.** Batting, bowling, fielding in RAR. If two things cannot be compared, the model has failed at its central job.
3. **Uncertainty is a first-class output.** A point estimate presented alone is a **defect**.
4. **Distributional over prescriptive.** State what a player's tendencies cost him, not what he should have done on one ball. More honest *and* more coachable.
5. **The limitations are in the interface.** What the model cannot see is shown next to what it can. The strongest trust-building move available, and cheap.
6. **Auditable by a sceptic.** Every number traces to the deliveries that produced it. No unexplainable outputs in a coaching context.

**Non-functional requirements** are the same principles with teeth: reproducibility (any published number regenerable from a versioned dataset + versioned model), auditability (every aggregate drills to deliveries), latency (all outputs precomputed, sub-second reads, no request-time fitting), assumption transparency (credit shares, replacement level, shrinkage strength, phase boundaries — configurable, visible, and included in every export), and graceful degradation by tier.

---

## 10. Constraints to hold in mind

- **Data access is the binding constraint.** Tiers 2 and 3 are unlocked by partnership with a league, franchise, vendor or academy. This is a business-development problem wearing a technical costume; no amount of modelling skill substitutes for it.
- **Sparsity.** The delivery space is large and individual batters occupy few cells. Hierarchical shrinkage is a requirement, and its strength must be visible.
- **Causal validity.** Counterfactuals are the most attractive and most fragile claims here. A shot the model says was available may not have been available *to that batter, on that ball, having already committed*. Distributional framing is the mitigation — a **design constraint, not a caveat**.
- **Licensing.** Cricsheet is under the **Open Database Licence** — attribution and share-alike obligations. Commentary scraping sits under separate, less favourable terms. Vendor tracking data will carry redistribution restrictions constraining what can be shown publicly. **Resolve data rights before anything is sold, not during diligence.**
- **Team capacity.** One person, alongside a full-time role and a graduate application. The tier structure exists partly so a single builder ships something *complete at Tier 0* rather than something partial across four tiers.
- **Market size.** Low hundreds of organisations globally will pay for this. That shapes it as a consulting or licensing business rather than a venture-scale one — and that should be a **deliberate choice, not a discovery**.

---

## 11. Capabilities needed

| Capability | Build / buy / partner |
|---|---|
| Data engineering — ingestion, schema, versioning, pipelines | Build |
| Statistical modelling — hierarchical models, calibration, causal hygiene | Build; seek review |
| **Domain validation** — does this match what a coach sees? | **Partner — non-negotiable** |
| Front end — interactive surfaces, exports | Build |
| **Data partnerships** — Tier 2/3 access | **Partner — the critical path** |
| Commercial — pricing, pilots, contracts | Build initially |

Domain validation is the role most often skipped by technical founders and the one that most reliably kills sports analytics products. **A model no coach recognises is not a product regardless of its statistical quality.** Find a former player or working analyst who will say when the output is wrong.

---

## 12. Tooling decisions (settled)

- **Data & modelling:** Python. pandas or polars for ball-level work; **polars once volumes reach tracking scale**. scikit-learn / gradient boosting for classification and response surfaces. **PyMC or NumPyro** for hierarchical models where interval quality matters — the right place for Bayesian machinery, because shrinkage and uncertainty are product requirements, not decorations.
- **Storage:** **Parquet** ball store, **DuckDB** analytical queries, **Postgres** application state. No warehouse until there is a reason for one.
- **Reproducibility:** Git for code; **DVC or content-addressed Parquet** for data; a lightweight experiment log for model runs. Model artifacts versioned and tagged; every published figure traceable to a tag.
- **Application:** **FastAPI** backend on Render, **Next.js** frontend on Vercel. Both already in use; neither is the interesting part.
- **CV (Tier 3 only, and only if building rather than buying):** MediaPipe or MMPose. **Prefer vendor-supplied data over in-house CV in almost every case** — the CV problem is a company on its own.
- **Development:** Claude Code for the iterative, messy work — parsers, scrapers, feature engineering. **Least useful for statistical design decisions**, which need to be reasoned about rather than generated.

---

## 13. Suggested build order

Derived from the tier gating and the dependency graph; not stated as a sequence in the PRD, so treat as a proposal to confirm.

1. **Ingestion + canonical ball schema** on Cricsheet. Nail the record and the pre-ball state convention before anything reads it.
2. **Feature store** with versioning and immutability, plus phase / required rate / pressure derivations.
3. **M1 value functions** — everything downstream is denominated against these. Gate on the monotonicity + calibration bar.
4. **M3 batting & bowling RAR** — known territory, establishes the shared axis.
5. **M2 fielding value at Tier 0** — the novel unlock for the selector, and the first genuinely differentiated output.
6. **Leaderboard + Player 360 + Methodology surfaces.** Methodology ships *with* the first numbers, not after.
7. **M8 XI Builder**, then **M9 Auction Board** (needs auction price data).
8. **Tier 1 enrichment** — commentary classification, improving M2 and bootstrapping M5 labels.
9. **Tier 2 work only once data access is secured** — M4, then M5 conditioning, then M7.
10. **Tier 3 / M6** only against a confirmed source.

Steps 1–8 are unblocked today. Steps 9–10 are gated on business development that should run **in parallel from day one**.

---

## 14. Success metrics

- **Model quality:** out-of-sample calibration on every probabilistic output; margin over a *named* naive baseline for every model — a sophisticated model that barely beats a counting stat is a finding, and must be known internally before it is discovered externally; rank stability under assumption perturbation.
- **Product usage:** distinct decisions the tool was consulted for; whether a user returns unprompted before the next fixture; **whether outputs appear in someone else's team meeting without you in the room**.
- **Commercial:** paid pilots initiated; pilot-to-renewal conversion — the only metric that genuinely separates a useful tool from an interesting one.
- **Credibility:** published analyses and their reception among practitioners; inbound enquiries from organisations rather than outbound; **Tier 2 access secured** — both a metric and the gate on half the roadmap.

---

## 15. Open questions

Unresolved. Do not let code silently decide these.

1. **Which data partner, and what do they get?** Highest-leverage unresolved question. Franchise analytics team / second-tier league / vendor seeking differentiation / academy — each implies a different product and different restrictions.
2. **Business model** — consulting, licensed tool, or embedded analyst. Different margins, scaling, and implications for how much must be self-serve.
3. **Whether to serve broadcast** — funds the work and creates distribution, at the cost of pulling toward speed over rigour.
4. **Women's cricket as a wedge** — less coverage, less entrenched incumbency, growing budgets. Possibly the faster route to a first paying partner.
5. **Public model vs proprietary** — open methodology builds the credibility that unlocks data access, and removes any technical moat. Working assumption: the moat is data relationships and domain trust, not code. **Should be a decision, not a default.**
6. **Test cricket** — does the value-function architecture extend, or need replacing?

---

## 16. What would make this fail

Stated plainly, because a PRD that omits this is marketing.

- Building Tier 2 and 3 models before securing Tier 2 and 3 data, and having nothing shippable.
- Presenting single-ball counterfactuals prescriptively, being contradicted by a coach in a meeting, and losing the room permanently.
- Solving the modelling problem and never solving the access problem.
- Scope expansion into football, or fan products, before one cricket surface has a paying user.
- Building for eighteen months without a domain expert telling you when the output is wrong.

---

## 17. Working conventions for contributors and agents

- **The canonical ball record is sacred.** Match state is always *pre-ball*. New sources adapt to the schema; the schema does not adapt to sources.
- **Never mutate the feature store.** Corrections are new versions.
- **No fitting at request time.** If a surface needs a number, it was precomputed.
- **Every number ships with an interval and a drill-down** to its deliveries. If you cannot provide both, the feature is not done.
- **Assumptions are parameters, not constants.** Credit share, replacement level, shrinkage strength, phase boundaries — configurable, surfaced, and exported.
- **Label approximations in the interface**, especially M7 running without M6.
- **Name the baseline.** Every model reports its margin over a stated naive alternative.
- **Check tier before proposing work.** If a task needs Tier 2 or 3 data that is not secured, say so rather than building toward it.
