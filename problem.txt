# Product Requirements Document

## cricfield — an option-value engine for cricket decisions

**Status:** draft for review
**Owner:** Manu S Nair
**Document type:** system-level PRD covering the full build, not a release spec

---

## 1. The problem

Cricket decisions are made on outcome averages that do not condition on context.

A batter's average against left-arm spin is computed across every left-arm spinner he has ever faced, on every surface, at every match state, against every field setting. A bowler's economy in the death overs is computed across every death over he has bowled, regardless of who was batting or what the required rate was. A selector comparing two players compares two numbers that were produced by two different sets of circumstances.

The consequence is that the most consequential decisions in the game — what to bowl next, what shot to play, who to pick, what to pay at auction — are made on evidence that has been averaged past the point of usefulness. Coaches compensate with intuition, which is often excellent and always unauditable.

The gap is not a missing statistic. It is that **no system prices the options that were actually available at the moment a decision was made.**

## 2. Core value proposition

> For any moment in a cricket match, value every option available to both sides, so that decisions can be made on expected value rather than on historical averages.

The unifying object is the **option set**. On every delivery two decisions are made in sequence:

- The bowler chooses a delivery from the set he can bowl.
- The batter, having read that delivery, chooses a shot from the set available to him given his position, technique and the time he has left.

If the system can value the members of both sets, the same model answers questions from both ends:

| Read from | Question | Output |
|---|---|---|
| Bowler's end | What should I bowl to this batter, now? | The delivery that minimises the value of the batter's best available response |
| Batter's end | What should I play to this delivery? | The shot with the highest expected value given what is available |
| Analyst's desk | Where is this player weak? | The regions of the delivery space where his best option is worth less than the population's |
| Selector's desk | Who should play, and what are they worth? | Player value on one scale across all three disciplines |

Weakness and strength analysis is not a separate feature. It falls out of the option-set model as a by-product: a weakness is a region of the delivery space where a player's best available option has low value.

## 3. Users and jobs

### Primary

**Bowling coach / bowling analyst.** Job: decide what a bowler should be aiming at against a specific batter in a specific phase, and diagnose why a plan is not working. Needs the delivery-space response surface per batter, and the ability to filter by phase and match state. Cares about actionability over sophistication; will not use anything that cannot be translated into a target on a length map.

**Batting coach.** Job: identify which shots a batter is under-using, over-using, or playing at the wrong time, and which technical corrections would most change his output. Needs shot-level distributions and the availability model. Highly sceptical of prescriptive single-ball counterfactuals; responds to distributional claims.

**Team analyst / selector.** Job: pick an XI, and justify it. Needs unified player value across batting, bowling and fielding, opposition- and venue-conditioned, with uncertainty. This is the user for whom fielding value on the runs scale is the novel unlock.

**Recruitment / auction strategist.** Job: set a maximum bid per player and identify market mispricing. Needs player value translated to a currency, plus a model of what the market will pay.

### Secondary

**Broadcast and media analyst.** Job: produce a defensible on-air claim quickly. Lower rigour bar, higher volume, faster cycle. Useful as a distribution channel and a revenue line, but not a design constraint.

### Explicit non-users in this scope

Fans, fantasy players, and betting participants. The model could serve all three. Serving them well requires different products, different latency, and different ethical positions. Deferred deliberately, not by oversight.

## 4. Product principles

1. **Price options, not outcomes.** Anything the system reports should be answering "what was this worth, given what else was possible?"
2. **One scale.** Batting, bowling and fielding value are reported in runs above replacement. If two things cannot be compared, the model has failed at its central job.
3. **Uncertainty is a first-class output.** Every headline number ships with an interval. A point estimate presented alone is a defect.
4. **Distributional over prescriptive.** The model states what a player's tendencies cost him, not what he should have done on one ball. This is both more honest and more coachable.
5. **The limitations are in the interface.** What the model cannot see is displayed alongside what it can. This is the single strongest trust-building decision available, and it is cheap.
6. **Auditable by a sceptic.** Any number should be traceable to the deliveries that produced it. No unexplainable outputs in a coaching context.

## 5. Scope

Scope is organised by **data tier**, because data access — not modelling capability — is the binding constraint on this system. Each tier unlocks a specific set of models and cannot be skipped.

### Tier 0 — Public outcome data

**Source:** Cricsheet ball-by-ball JSON. Free, comprehensive, machine-readable.
**Contains:** batter, bowler, runs, extras, dismissal type, credited fielders, match state.
**Does not contain:** where the ball pitched, what shot was played, where fielders stood, any physical measurement.

**Unlocks:** value functions, fielding value from dismissals, batting and bowling RAR, squad selection, auction valuation.

### Tier 1 — Derived event enrichment

**Source:** ball-by-ball commentary text, classified.
**Contains (after processing):** shot played, fielding event type (clean stop, misfield, boundary save, drop, direct hit), approximate delivery description.
**Reliability:** moderate and uneven; commentary is written for readers, not for models.

**Unlocks:** complete fielding value, first-pass shot distributions, bootstrap labels for later supervised models.

### Tier 2 — Ball tracking

**Source:** commercial vendors (Hawk-Eye and equivalents), or a franchise/league partner who already licenses it.
**Contains:** release point, speed, trajectory, pitch location, deviation off the surface, bounce, impact point, ball flight after contact.
**Access:** gated. Not purchasable by an individual at realistic cost.

**Unlocks:** the delivery response surface, conditional shot distributions, the bowler-side counterfactual — approximately half the core value proposition.

### Tier 3 — Biomechanical

**Source:** pose tracking, bat sensors, or vendor-provided skeletal data.
**Contains:** footwork, trigger movement, weight transfer, bat swing path, face angle at contact, bat speed.
**Access:** gated and, in several cases, not systematically captured at all.

**Unlocks:** the shot availability model — the part that explains *why* an option was or was not on the menu.

### In scope

- All models and surfaces buildable at Tiers 0 and 1, on public data.
- All models and surfaces at Tier 2, conditional on a data partnership.
- Tier 3 models specified but built only against a confirmed data source.
- Men's and women's T20 as the primary format. ODI as a secondary target sharing the same value-function machinery.

### Out of scope

- **Football.** The architecture generalises and the eventual ambition is real, but every hour spent on it before cricket ships is an hour that produces nothing sellable. Explicitly deferred.
- **Live in-match automation.** Recommending deliveries in real time during play introduces latency, integration and governance requirements that are disproportionate at this stage. The system is a preparation and review tool.
- **Betting or odds products.** Technically adjacent, strategically and ethically a different company.
- **Fan-facing consumer app.**
- **Test cricket** in the first architecture. The value functions differ structurally enough (no fixed resource limit) to warrant separate treatment.

## 6. System architecture

Four layers, each with a clean interface to the next.

### Ingestion
Parsers per source, each producing a canonical ball-level record. One row per delivery, with match state as it stood *before* the ball. Every downstream model reads this schema and nothing else, so a new data source is an ingestion problem, never a modelling one.

### Feature and label store
Derived per-ball attributes: phase, required rate, pressure state, delivery attributes where available, shot label, fielding event. Versioned. Immutable once written — corrections create new versions rather than mutating history, because a model result that cannot be reproduced is not evidence.

### Model layer
Independently trained, independently versioned components (Section 7). Each exposes a scoring interface and publishes its own calibration diagnostics. Models are trained offline; nothing is fitted at request time.

### Decision layer
Where models compose into answers. The option-set solver, the selection optimiser and the auction valuer all live here. This layer holds the assumptions that turn model outputs into recommendations — credit shares, replacement level, constraint definitions — and every one of them is configurable and surfaced in the interface.

### Surfaces
Web application, exports, and an API. The interface is not a view onto the models; it is where the assumptions become visible and arguable.

## 7. Models

Each model is specified by inputs, outputs, tier requirement, and the bar it must clear to ship.

### M1 — Value functions
**Tier 0.** Run expectancy over (balls remaining, wickets lost) for the first innings; win probability over (balls remaining, wickets lost, runs required) for the chase. Empirical, binned, blended with a fitted surface where cells are sparse, with monotonicity enforced.
**Ships when:** calibration holds out of sample and the surface is monotone in both arguments across the full grid.

### M2 — Fielding value
**Tier 0, improved at Tier 1.** Prices every credited dismissal, attributes a share to fielders, charges each player an expected share based on field time, reports the residual as runs above average.
**Known ceiling at Tier 0:** sees only the fraction of fielding that ends in a wicket.
**Ships when:** rankings survive sensitivity analysis across credit regimes, and it beats a catches-per-match baseline out of sample.

### M3 — Batting and bowling value
**Tier 0.** Runs above replacement, phase- and context-adjusted. Well-trodden territory; this is implementation, not research. Its purpose is to put all three disciplines on one axis.
**Ships when:** it reproduces published context-adjusted measures within a defensible tolerance.

### M4 — Delivery response surface
**Tier 2.** For a given batter: E[runs] and P(wicket) as a function of line, length, speed, deviation, phase and match state. Hierarchical, shrinking each batter toward a batter-type prior and then a league prior, because individual batters have few balls in most cells.
**This is the bowler-side counterfactual.** Perturb an input, re-query, compare.
**Ships when:** out-of-sample log loss beats a batter-marginal baseline by a meaningful margin, and shrinkage behaviour is documented per cell.

### M5 — Shot classification and conditional distribution
**Tier 1 for labels, Tier 2 for conditioning.** P(shot | delivery, batter) and the run and wicket distribution per shot per cell.
**Ships when:** classification accuracy is validated against a hand-labelled hold-out, and per-shot distributions are stable under resampling.

### M6 — Shot availability
**Tier 3.** Which shots were actually on the menu, given footwork, weight transfer and the time available. The hardest component and the one that carries the deepest coaching insight.
**Not started until a Tier 3 data source is confirmed.**

### M7 — Option-set solver
**Composite.** Combines M4, M5 and M6 into the two-sided output: the bowler's value-minimising delivery and the batter's value-maximising shot.
**Degrades gracefully:** without M6, it treats the menu as a function of the delivery and the batter's general profile, which is an approximation and must be labelled as one in the interface.

### M8 — Squad value and selection
**Tier 0.** Combines M2 and M3 into total player value; optimises an XI under constraints (overseas slots, role balance, venue) with an uncertainty interval on the projected total.

### M9 — Market price model
**Tier 0 plus auction price data.** Predicts what the market will pay, so the gap between model value and predicted price becomes an explicit arbitrage estimate.

## 8. Surfaces

| Surface | Primary user | Core question answered | Tier |
|---|---|---|---|
| Leaderboard | Analyst | Who is good at this, adjusted for opportunity? | 0 |
| Player 360 | Coach, analyst | What is this player worth, and where does it come from? | 0 |
| Matchup Explorer | Bowling coach | Where do I bowl to this batter, and why? | 2 |
| Shot Menu | Batting coach | What was available, what was chosen, what did the gap cost? | 2–3 |
| XI Builder | Selector | Which eleven, and what does the model say it is worth? | 0 |
| Auction Board | Recruitment | What is my maximum bid, and where is the market wrong? | 0 |
| Methodology | Everyone | Why should I believe any of this? | — |

The Methodology surface is not documentation. It is a product feature, and in a market where the buyer is a professional sceptic it may be the most important one.

## 9. Non-functional requirements

**Reproducibility.** Any published number must be regenerable from a versioned dataset and a versioned model. This is the difference between a research product and an opinion.

**Auditability.** Every aggregate drills down to the deliveries that produced it. A coach who cannot see the balls behind a number will not trust it, and should not.

**Latency.** All model outputs precomputed. Interactive surfaces read stored results. Sub-second response on every view; no request-time fitting.

**Assumption transparency.** Credit shares, replacement level, shrinkage strength and phase boundaries are configurable, visible in the interface, and included in every export.

**Graceful degradation by tier.** Every surface must render, with clearly marked reduced capability, when a higher-tier data source is unavailable.

## 10. Constraints

**Data access is the binding constraint.** Tiers 2 and 3 cannot be bought by an individual. They are unlocked by partnership with a league, franchise, vendor or academy. This is a business-development problem wearing a technical costume, and no amount of modelling skill substitutes for it.

**Sparsity.** The delivery space is large and individual batters occupy few cells. Hierarchical shrinkage is not an optimisation, it is a requirement, and the amount of shrinkage applied must be visible to the user.

**Causal validity.** Counterfactual outputs are the product's most attractive and most fragile claims. A shot the model says was available may not have been available *to that batter, on that ball, having already committed*. The mitigation is distributional framing, and it is a design constraint rather than a caveat.

**Licensing.** Cricsheet is under the Open Database Licence, carrying attribution and share-alike obligations. Commentary scraping sits under separate and less favourable terms. Vendor tracking data will come with redistribution restrictions that constrain what can be shown publicly. Data rights must be resolved before anything is sold, not during diligence.

**Team capacity.** This is specified as a system, but is being built by one person alongside a full-time role and a graduate application. The tier structure exists partly so that a single builder can ship something complete at Tier 0 rather than something partial across all four.

**Market size.** The number of organisations that will pay for this is in the low hundreds globally. This shapes the model as a consulting or licensing business rather than a venture-scale one, and that should be a deliberate choice rather than a discovery.

## 11. Required capabilities

The roles the system needs, independent of how many people fill them.

| Capability | What it covers | Build, buy or partner |
|---|---|---|
| Data engineering | Ingestion, schema, versioning, pipelines | Build |
| Statistical modelling | Hierarchical models, calibration, causal hygiene | Build; seek review |
| Domain validation | Does this match what a coach sees? | **Partner** — non-negotiable |
| Front end | Interactive surfaces, exports | Build |
| Data partnerships | Tier 2 and 3 access | **Partner** — the critical path |
| Commercial | Pricing, pilots, contracts | Build initially |

The domain validation role is the one most often skipped by technical founders and the one that most reliably kills sports analytics products. A model that no coach recognises is not a product regardless of its statistical quality. Find a former player or a working analyst who will tell you when the output is wrong.

## 12. Tooling

**Data and modelling.** Python. pandas or polars for ball-level work; polars once volumes reach tracking scale. scikit-learn and gradient boosting for classification and response surfaces. PyMC or NumPyro for hierarchical models where interval quality matters — this is the right place for Bayesian machinery, because shrinkage and uncertainty are product requirements, not decorations.

**Storage.** Parquet for the ball store, DuckDB for analytical queries, Postgres for application state. No warehouse until there is a reason for one.

**Reproducibility.** Git for code, DVC or content-addressed Parquet for data, a lightweight experiment log for model runs. Model artifacts versioned and tagged; every published figure traceable to a tag.

**Application.** FastAPI backend on Render, Next.js frontend on Vercel. Both already in use; neither is the interesting part of this system.

**Computer vision (Tier 3 only, and only if building rather than buying).** MediaPipe or MMPose for skeletal extraction. Prefer vendor-supplied data over in-house CV in almost every case — the CV problem is a company on its own.

**Development.** Claude Code inside the existing IDE for the iterative, messy work: parsers, scrapers, feature engineering. Least useful for the statistical design decisions, which need to be reasoned about rather than generated.

## 13. Success metrics

**Model quality.** Out-of-sample calibration on every probabilistic output. Margin over a named naive baseline for every model — a sophisticated model that barely beats a counting stat is a finding, and needs to be known internally before it is discovered externally. Rank stability under assumption perturbation.

**Product usage.** Number of distinct decisions the tool was consulted for. Whether a user returns unprompted before the next fixture. Whether outputs appear in someone else's team meeting without you in the room.

**Commercial.** Paid pilots initiated. Pilot-to-renewal conversion — the only metric that genuinely separates a useful tool from an interesting one.

**Credibility.** Published analyses and their reception among practitioners. Inbound enquiries from organisations rather than outbound. Tier 2 data access secured, which is both a metric and the gate on half the roadmap.

## 14. Open questions

1. **Which data partner, and what do they get?** The single highest-leverage unresolved question. Options include a franchise analytics team, a second-tier league, a vendor seeking differentiation, or an academy. Each implies a different product and a different set of restrictions.
2. **Business model.** Consulting, licensed tool, or embedded analyst. These have different margins, different scaling properties, and different implications for how much of the system needs to be self-serve.
3. **Whether to serve broadcast.** It funds the work and creates distribution, at the cost of pulling the product toward speed over rigour.
4. **Women's cricket as a wedge.** Less analytical coverage, less entrenched incumbency, growing budgets. Potentially a faster route to a first paying partner than competing for attention in the men's game.
5. **Public model versus proprietary.** Open methodology builds the credibility that unlocks data access; it also removes any technical moat. The current working assumption is that the moat is data relationships and domain trust, not code — but this should be a decision, not a default.
6. **Test cricket.** Whether the value-function architecture extends or needs replacing.

## 15. What would make this fail

Stated plainly, because a PRD that omits this is marketing.

- Building Tier 2 and 3 models before securing Tier 2 and 3 data, and having nothing shippable.
- Presenting single-ball counterfactuals prescriptively, being contradicted by a coach in a meeting, and losing the room permanently.
- Solving the modelling problem and never solving the access problem.
- Scope expansion into football, or fan products, before one cricket surface has a paying user.
- Building for eighteen months without a domain expert telling you when the output is wrong.
