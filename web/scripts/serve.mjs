// Serve the static export in out/ for local checking. `next start` does not
// serve an `output: "export"` build.

import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "out");
const port = Number(process.env.PORT ?? 3000);
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

if (!existsSync(root)) {
  console.error(`serve: ${root} does not exist. Run \`npm run build\` first.`);
  process.exit(1);
}

createServer((req, res) => {
  let file = path.join(root, decodeURIComponent(new URL(req.url, "http://localhost").pathname));
  if (!file.startsWith(root)) return res.writeHead(403).end();
  // /provenance is provenance.html. The export also writes a provenance/
  // directory of RSC payloads beside it, so the .html file is tried first.
  if (!existsSync(file) || statSync(file).isDirectory()) {
    if (existsSync(`${file}.html`)) file = `${file}.html`;
    else file = path.join(file, "index.html");
  }
  if (!existsSync(file)) return res.writeHead(404).end("not found");
  res.writeHead(200, { "Content-Type": types[path.extname(file)] ?? "application/octet-stream" });
  createReadStream(file).pipe(res);
}).listen(port, () => console.log(`serving ${root} at http://localhost:${port}`));
