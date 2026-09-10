// Copy web-data/ (the exporter's output, published by CI) into public/data/.
//
// Fails the build when the export is absent or incomplete. A site that renders
// an empty table because its data is missing is indistinguishable from one
// whose data is wrong (architecture.md §14, "The build step").

import { cpSync, existsSync, readFileSync, rmSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.resolve(webDir, "..", "web-data");
const target = path.join(webDir, "public", "data");

function fail(lines) {
  // Remove any earlier copy, so a failed build leaves nothing stale for `next dev` to serve.
  rmSync(target, { recursive: true, force: true });
  console.error(["", "copy-data: FAILED", ...lines.map((l) => `  ${l}`), ""].join("\n"));
  process.exit(1);
}

if (!existsSync(source) || !statSync(source).isDirectory()) {
  fail([
    `web-data/ is missing. Expected it at ${source}`,
    "The site is not built without its data. Download the `web-data` artefact from the",
    "latest successful `export` workflow run and unpack it at the repository root.",
  ]);
}

const required = ["meta.json", "players.json", "seasons/index.json"];
const missing = required.filter((f) => !existsSync(path.join(source, f)));
if (missing.length) fail([`web-data/ is incomplete. Missing: ${missing.join(", ")}`]);

function readJson(file) {
  try {
    return JSON.parse(readFileSync(path.join(source, file), "utf8"));
  } catch (e) {
    fail([`web-data/${file} is not valid JSON: ${e.message}`]);
  }
}

const meta = readJson("meta.json");
const fields = ["matches", "deliveries", "season_min", "season_max", "git_commit"];
const absent = fields.filter((f) => meta[f] === undefined || meta[f] === null);
if (absent.length) fail([`web-data/meta.json lacks required fields: ${absent.join(", ")}`]);

const players = readJson("players.json");
if (!Array.isArray(players) || players.length === 0) fail(["web-data/players.json holds no players."]);

rmSync(target, { recursive: true, force: true });
cpSync(source, target, { recursive: true });
console.log(`copy-data: web-data/ -> public/data/ (export commit ${meta.git_commit})`);
