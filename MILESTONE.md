# MILESTONE.md

**Current milestone: ship the fielding MVP — leaderboard, player detail, compare.**

This file describes the milestone in progress and nothing else. It is rewritten when the milestone closes, not appended to. The roadmap lives in `PRD.md`; what is true of the repo right now lives in `CONTEXT.md`; why the code is shaped this way lives in `architecture.md` §14 for the web layer specifically.

**Phase 1 is complete; nothing after it is built.** The model and `scripts/export_web.py` are complete and committed; Phases 2–6 are ahead of the work, not behind it.

Phases are ordered by dependency, not by preference or interest. No dates and no estimates: the ordering is the plan.

---

## Phase 1 — Static shell and the data pipeline

**Status.** Complete in `6a8a4fb`.

**Delivers.** A Next.js application under `web/` that builds to a static export, and a build step that copies `web-data/` into `web/public/data/`, served under `/data/` (`architecture.md` §14), and fails loudly when it is absent.

**Done when.** `npm run build` succeeds from a clean checkout after `scripts/export_web.py` has run, and the built site serves a page displaying the match count, delivery count, season range and `git_commit` read from `meta.json`. Deleting `web-data/` and rebuilding fails with a message naming the missing directory, rather than producing a site with an empty table.

**Depends on.** `scripts/export_web.py`, which exists.

## Phase 2 — Leaderboard

**Delivers.** The route reading `players.json`: 528 qualified fielders with rank, name, role, field time, FRAA and FRAA per 100, sortable by column, searchable by name. Also a persistent limitations note, built as a component and shown on every route that displays a number. The methodology page itself stays in Phase 5; this is the always-visible note that points at what that page will explain.

**Done when.** A row picked at random matches the corresponding row of `ipl_fraa.csv` field for field, and the sort order at load matches the exported `rank` without the page computing it. Sorting by a different column reorders the display and leaves every value unchanged. The limitations note is visible without scrolling on both desktop and a 375px viewport, on every route built so far, and names the concrete evidence: RA Jadeja 105th of 528. It is not a modal, not a tooltip, and not behind a link. At 375px the leaderboard collapses to fewer columns rather than scrolling horizontally.

**Why the note is here and not in Phase 5.** Without it, Phases 2–4 produce a demoable leaderboard with no caveat on screen, and that is exactly when a screenshot escapes. The caveat is a component, not documentation. The mobile criterion exists because most traffic will arrive from a link in a post or a DM, which means a phone.

**Depends on.** Phase 1.

## Phase 3 — Player detail

**Delivers.** `/player/<slug>`, reading `seasons/<slug>.json`: the player's career line and his season-by-season rows, with non-qualifying seasons visibly marked rather than hidden.

**Done when.** Every player in `players.json` has a reachable page — 528 of 528, no dead links from the leaderboard — and the season rows shown for a player sum to the career FRAA displayed at the top of the same page. Seasons with `qualifies: false` are distinguishable at a glance, and the page states the 240-ball threshold read from `meta.json` rather than hardcoding it.

**Depends on.** Phase 2, for the navigation into it.

## Phase 4 — Compare

**Delivers.** A route showing two players side by side across their common seasons, with one bar chart.

**Done when.** Selecting two players fetches exactly two season files and nothing else, observable in the browser network panel, and the totals shown for each player match their player-detail pages exactly. A player pair with no overlapping seasons renders a stated "no common seasons" result rather than an empty chart. At 375px the compare view stacks the two players rather than truncating either, because most traffic will arrive from a link in a post or a DM, which means a phone.

**Depends on.** Phase 3, which establishes the season-file read path.

## Phase 5 — Methodology and limitations

**Delivers.** The page that answers "why should I believe any of this", rendering the `assumptions` object and `caveats` array from `meta.json`, and reachable from every page showing a number.

**Done when.** The page lists every assumption in `meta.json` with its current value, states the Tier 0 ceiling in plain terms — that the model sees only fielding ending in a wicket and is blind to ground fielding — and names the concrete evidence: RA Jadeja at 105 and SA Yadav at 161 of 528 despite elite ground-fielding reputations. Changing a constant in `fielding.py`, re-exporting and rebuilding changes the value shown on this page with no edit to the frontend.

**Depends on.** Phase 1 for `meta.json` access. Deliberately placed before deploy: the PRD treats methodology as a product feature and not documentation (PRD §8), and shipping numbers publicly without it is the failure mode the PRD names — being contradicted by a coach and losing the room (PRD §15).

## Phase 6 — Deploy

**Delivers.** The site on a public URL.

**Done when.** The URL serves the leaderboard, and the `git_commit` displayed on the deployed site matches the commit the site was built from. A mismatch between the export's commit and the deployed commit fails the build rather than shipping a page that describes a model version it was not built from.

**Depends on.** Phases 1–5.

---

## Not in this milestone

Named because each is a plausible detour, and one of the PRD's stated failure modes is scope expansion before a single surface has a user (PRD §15).

- **XI Builder.** A separate surface needing M8, which is specified and unbuilt.
- **Auction Board.** Needs M9 and auction price data, which the repo does not have.
- **Charts beyond the single bar chart in Phase 4.** Every additional chart is a design decision plus a rendering dependency, and none of them answers a question the tables do not.
- **Login, accounts, saved comparisons.** Each requires a backend and a database, and the static architecture in `architecture.md` §14 exists precisely because nothing in this milestone needs one. Adding one for saved state is how the FastAPI service arrives before there is anything to serve.
- **Football.** Deferred in the PRD (PRD §5) and still deferred.

Also out, though less likely to creep in: batting and bowling value on the same page, Tier 1 commentary parsing, and any view requiring an aggregate the exporter does not already produce.
