// The deployed site shows the commit its data came from: meta.json's
// git_commit, rendered on /methodology and /provenance. This fails the deploy
// when that commit cannot describe the code being deployed, rather than
// shipping a page that names a model version it was not built from
// (MILESTONE Phase 6, architecture.md §14).
//
// The rule is not equality. The site and the model move at different speeds: a
// frontend commit does not change a single exported number, and requiring a
// fresh export for every CSS tweak would make the check a nuisance to route
// around. What must hold is that the export describes the model being
// deployed:
//
//   1. the export's commit is an ancestor of the commit being deployed, and
//   2. nothing under the model paths changed between the two, and
//   3. the export was taken from a clean tree, so its commit means anything.
//
// Anything else fails, loudly, before the build runs.

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// A change to any of these makes the exported numbers stale.
const MODEL_PATHS = ["cricfield", "scripts/export_web.py", "sensitivity.py", "requirements.txt"];

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
// Not on PATH on the machine this was written on; the runner has it.
const GIT = process.env.GIT ?? "git";

function git(...args) {
  return execFileSync(GIT, args, { cwd: repo, encoding: "utf8" }).trim();
}

function fail(lines) {
  console.error(["", "check-export-commit: FAILED", ...lines.map((l) => `  ${l}`), ""].join("\n"));
  process.exit(1);
}

const short = (sha) => String(sha).slice(0, 7);

const metaPath = [
  path.join(repo, "web-data", "meta.json"),
  path.join(repo, "web", "public", "data", "meta.json"),
].find((p) => existsSync(p));
if (!metaPath) {
  fail([
    "no meta.json found at web-data/ or web/public/data/.",
    "Download the web-data artefact from the newest successful export run first.",
  ]);
}

let meta;
try {
  meta = JSON.parse(readFileSync(metaPath, "utf8"));
} catch (e) {
  fail([`${metaPath} is not valid JSON: ${e.message}`]);
}

const exported = meta.git_commit;
const deployed = process.argv[2] || git("rev-parse", "HEAD");

if (!exported) {
  fail([
    "meta.json has no git_commit, so this export cannot be traced to a model version.",
    "Re-export from CI, which records one.",
  ]);
}

// architecture.md §14: read git_dirty_known before git_dirty. A null dirty
// state means nobody checked, which is not the same as clean.
if (meta.git_dirty_known !== true) {
  fail([
    `the export at ${short(exported)} does not know whether its tree was clean`,
    `(git_dirty_known: ${JSON.stringify(meta.git_dirty_known)}, git_source: ${JSON.stringify(meta.git_source)}).`,
    "Its commit cannot be trusted to describe the code that ran. Re-export from CI.",
  ]);
}
if (meta.git_dirty === true) {
  fail([
    `the export at ${short(exported)} was taken from a modified tree, so that commit`,
    "does not describe the code that produced these numbers. Re-export from CI.",
  ]);
}

try {
  git("cat-file", "-e", `${exported}^{commit}`);
} catch {
  fail([
    `the export's commit ${short(exported)} is not in this repository.`,
    "Either the history is shallow (check out with fetch-depth: 0) or the export came from a fork.",
  ]);
}

try {
  git("merge-base", "--is-ancestor", exported, deployed);
} catch {
  fail([
    `the export's commit ${short(exported)} is not an ancestor of the deployed commit ${short(deployed)}.`,
    "The data was produced by code that is not in what is being deployed.",
    "Re-run the export workflow on this branch and deploy the artefact it publishes.",
  ]);
}

const changed = git("diff", "--name-only", `${exported}..${deployed}`, "--", ...MODEL_PATHS)
  .split("\n")
  .filter(Boolean);
if (changed.length > 0) {
  fail([
    `the model changed between the export at ${short(exported)} and the deployed commit ${short(deployed)}:`,
    ...changed.map((f) => `  ${f}`),
    "The site would show numbers from one model version while naming another.",
    "Re-run the export workflow and deploy the artefact it publishes.",
  ]);
}

console.log(
  `check-export-commit: export ${short(exported)} is an ancestor of ${short(deployed)}, ` +
    "with no model change between them",
);
