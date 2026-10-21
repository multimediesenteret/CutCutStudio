// Put together what Vercel publishes (docs/publishing.md): the GUI concept at /concept/ (kept as
// an archive) and the web simulator at /sim/. Nothing else from the repo is published.
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const out = resolve(root, ".vercel-out");
const sim = resolve(root, "ui/dist/simulator");
if (!existsSync(resolve(sim, "index.html"))) {
  console.error("ui/dist/simulator mangler: kjør bygget for @cutcut/simulator først");
  process.exit(1);
}
rmSync(out, { recursive: true, force: true });
mkdirSync(out);
cpSync(resolve(root, "concept"), resolve(out, "concept"), { recursive: true });
cpSync(sim, resolve(out, "sim"), { recursive: true });
console.log("Vercel: .vercel-out/concept og .vercel-out/sim");
