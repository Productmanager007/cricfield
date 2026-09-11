// Work around a Next.js 16.3.4 static-export bug that only shows on Windows.
//
// The exporter names each segment-prefetch file with
// convertSegmentPathToStaticExportFilename(), which turns "/" into "." so the
// segment path /provenance/__PAGE__ becomes one flat file,
// __next.provenance.__PAGE__.txt. That is the name the client router requests.
// But the exporter builds the segment path with path.relative(), which on
// Windows separates with "\". The backslash survives the "/"-only replace, and
// path.join() then reads it as a directory, so a Windows build writes
// provenance/__next.provenance/__PAGE__.txt and every prefetch of it is a 404.
// (next/dist/export/index.js, collectSegmentPathsImpl.)
//
// This renames each such file to the flat name a Linux build writes. On Linux
// there is nothing nested and it changes nothing. Delete it once Next
// normalises the separator.

import { existsSync, readdirSync, renameSync, rmdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "out");
if (!existsSync(out)) {
  console.error(`flatten-segments: FAILED. ${out} does not exist; run next build first.`);
  process.exit(1);
}

const filesUnder = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? filesUnder(path.join(dir, e.name)) : [path.join(dir, e.name)]));

function removeEmpty(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) if (e.isDirectory()) removeEmpty(path.join(dir, e.name));
  rmdirSync(dir);
}

let renamed = 0;
function visit(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const full = path.join(dir, entry.name);
    if (!entry.name.startsWith("__next.")) {
      visit(full);
      continue;
    }
    for (const file of filesUnder(full)) {
      const dest = path.join(dir, `${entry.name}.${path.relative(full, file).split(path.sep).join(".")}`);
      if (existsSync(dest)) {
        console.error(`flatten-segments: FAILED. ${dest} already exists.`);
        process.exit(1);
      }
      renameSync(file, dest);
      renamed++;
    }
    removeEmpty(full);
  }
}

visit(out);
console.log(
  renamed > 0
    ? `flatten-segments: renamed ${renamed} nested segment files to the flat names the router requests`
    : "flatten-segments: nothing nested (expected on Linux)",
);
