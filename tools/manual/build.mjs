// Builds docs/manual/CutCut-Studio-manual.pdf from docs/manual/README.md (`pnpm manual`).
//
// The Markdown is the source; this adds a cover with the logo, a table of contents with page
// numbers and page footers, and renders it with the same Chromium as the end-to-end tests.
// Page numbers need two passes: render, find on which page each chapter starts, render again.
// Afterwards docs/manual/kilde.sha256 holds a hash of the inputs, and a test fails when the
// Markdown has changed without the PDF being built again (AGENTS.md 8).
import { createHash } from "node:crypto";
import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "@playwright/test";
import { marked } from "marked";
import { PDFDocument } from "pdf-lib";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const DIR = join(ROOT, "docs", "manual");
const SRC = join(DIR, "README.md");
const OUT = join(DIR, "CutCut-Studio-manual.pdf");
const HASH = join(DIR, "kilde.sha256");
const TEMPLATE = join(ROOT, "tools", "manual", "template.html");
const COVER = join(ROOT, "tools", "manual", "cover.html");
export const INPUTS = [SRC, join(DIR, "oppsett.png"), TEMPLATE, COVER];

// Chapters grouped on the contents page; any chapter not listed lands under «Mer».
const GROUPS = [
  [
    "Kom i gang",
    [
      "Hva CutCut Studio er",
      "Fysisk oppsett",
      "Utstyret",
      "Regi-PC: Windows og programvare",
      "Installasjon steg for steg",
      "Første oppsett i appen",
    ],
  ],
  ["Bruk", ["Touch-skjermen: slik bruker du studioet", "Teknikervinduet", "Funksjonene"]],
  [
    "Drift",
    [
      "Daglig drift",
      "Vedlikehold og oppdatering",
      "Tilgang, sikkerhet og personvern",
      "Når noe går galt",
    ],
  ],
  ["Oppslag", ["Adresser, porter og mapper", "Ordliste"]],
];
const NEW_PAGE = new Set(["Installasjon steg for steg", "Touch-skjermen: slik bruker du studioet"]);
const MONTHS = [
  "Januar",
  "Februar",
  "Mars",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Desember",
];

const LOGO = (dark) => {
  const [bars, cut, back, front, frontFill] = dark
    ? ["#7ea6ff", "#ff4d55", "#6b7480", "#7ea6ff", "#1a2844"]
    : ["#2f6fd6", "#d7262e", "#8a93a0", "#2f6fd6", "#e2ebfb"];
  return `<svg class="${dark ? "logo" : "logo-ui"}" viewBox="20 50 190 90" role="img" aria-label="CutCut Studio">
  <g fill="${bars}"><rect x="32" y="90" width="7" height="20" rx="3.5"/><rect x="44" y="78" width="7" height="44" rx="3.5"/><rect x="56" y="68" width="7" height="64" rx="3.5"/><rect x="68" y="82" width="7" height="36" rx="3.5"/><rect x="80" y="92" width="7" height="16" rx="3.5"/></g>
  <g stroke="${cut}" stroke-width="6" stroke-linecap="round"><line x1="100" y1="128" x2="114" y2="72"/><line x1="116" y1="128" x2="130" y2="72"/></g>
  <rect x="158" y="56" width="44" height="30" rx="5" fill="none" stroke="${back}" stroke-width="1.5"/><rect x="151" y="72" width="44" height="30" rx="5" fill="none" stroke="${back}" stroke-width="1.5"/>
  <rect x="144" y="88" width="48" height="34" rx="5" fill="${frontFill}" stroke="${front}" stroke-width="2.5"/><circle cx="182" cy="97" r="4" fill="${cut}"/></svg>`;
};

export function inputsHash() {
  const h = createHash("sha256");
  for (const f of INPUTS) h.update(readFileSync(f));
  return h.digest("hex");
}

function escape(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function parts() {
  let md = readFileSync(SRC, "utf8").replace(
    /<!-- pdf:skip -->[\s\S]*?<!-- \/pdf:skip -->\n?/g,
    "",
  );
  md = md.replace(/^# .*\n+/, ""); // the title is on the cover
  const lead = md.slice(0, md.indexOf("\n## ")).trim();
  const body = md.slice(md.indexOf("## "));
  const chapters = [...body.matchAll(/^## (.+)$/gm)].map((m) => m[1].trim());
  return { lead, body, chapters };
}

function html({ lead, body, chapters }, pages) {
  const id = (i) => `kap-${i + 1}`;
  let n = 0;
  const renderer = new marked.Renderer();
  renderer.heading = ({ tokens, depth }) => {
    const text = marked.Parser.parseInline(tokens);
    if (depth !== 2) return `<h${depth}>${text}</h${depth}>`;
    const i = n++;
    const cls = NEW_PAGE.has(chapters[i]) ? ' class="newpage"' : "";
    return `<h2 id="${id(i)}"${cls}><span class="mark">KAPMERKE${i + 1}X</span><span class="no">${i + 1}</span>${text}</h2>`;
  };
  const bodyHtml = marked.parse(body, { renderer });
  const listed = new Set(GROUPS.flatMap(([, c]) => c));
  const groups = [...GROUPS, ["Mer", chapters.filter((c) => !listed.has(c))]];
  const toc = groups
    .map(([g, items]) => {
      const rows = items
        .filter((c) => chapters.includes(c))
        .map((c) => {
          const i = chapters.indexOf(c);
          return `<li value="${i + 1}"><a href="#${id(i)}">${escape(c)}</a><span class="dots"></span><span class="n">${pages[c] ?? ""}</span></li>`;
        });
      return rows.length ? `<div class="group">${g}</div>\n${rows.join("\n")}` : "";
    })
    .join("\n");
  return readFileSync(TEMPLATE, "utf8")
    .replace("__LOGO_LIGHT__", LOGO(false))
    .replace("__LEAD__", marked.parseInline(lead))
    .replace("__TOC__", toc)
    .replace("__BODY__", bodyHtml);
}

function coverHtml(version) {
  const now = new Date();
  return readFileSync(COVER, "utf8")
    .replace("__LOGO_DARK__", LOGO(true))
    .replace("__DATE__", `${MONTHS.at(now.getMonth())} ${now.getFullYear()}`)
    .replace("__VERSION__", version);
}

async function render(page, text, path, footer = true) {
  const tmp = join(DIR, ".manual.tmp.html");
  writeFileSync(tmp, text);
  await page.goto(pathToFileURL(tmp).href, { waitUntil: "load" });
  await page.pdf({
    path,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: footer,
    headerTemplate: "<span></span>",
    footerTemplate:
      '<div style="width:100%;font:8pt Inter,sans-serif;color:#8a93a0;padding:0 18mm;display:flex;justify-content:space-between"><span>CutCut Studio – manual</span><span>Side <span class="pageNumber"></span> av <span class="totalPages"></span></span></div>',
  });
}

async function chapterPages(path, chapters) {
  const pdf = await getDocument({ data: new Uint8Array(readFileSync(path)), verbosity: 0 }).promise;
  const found = {};
  for (let p = 1; p <= pdf.numPages; p++) {
    const content = await (await pdf.getPage(p)).getTextContent();
    // each chapter heading carries an invisible marker, so the search does not depend on
    // how the PDF splits words into pieces
    const text = content.items
      .map((i) => ("str" in i ? i.str : ""))
      .join("")
      .replace(/\s+/g, "");
    chapters.forEach((c, i) => {
      if (found[c] === undefined && text.includes(`KAPMERKE${i + 1}X`)) found[c] = p;
    });
  }
  return found;
}

async function main() {
  const version =
    /^version\s*=\s*"([^"]+)"/m.exec(readFileSync(join(ROOT, "pyproject.toml"), "utf8"))?.[1] ??
    "?";
  const p = parts();
  const browser = await chromium.launch(
    process.env.CUTCUT_CHROMIUM ? { executablePath: process.env.CUTCUT_CHROMIUM } : {},
  );
  const page = await browser.newPage();
  const body = join(DIR, ".manual.body.pdf"),
    front = join(DIR, ".manual.cover.pdf");
  await render(page, html(p, {}), body);
  const pages = await chapterPages(body, p.chapters);
  const missing = p.chapters.filter((c) => pages[c] === undefined);
  if (missing.length) console.warn(`Fant ikke sidetall for: ${missing.join(", ")}`);
  await render(page, html(p, pages), body);
  await render(page, coverHtml(version), front, false);
  // the cover has no page number; the numbers in the contents count from the contents page
  const out = await PDFDocument.create();
  out.setTitle("CutCut Studio – manual");
  out.setAuthor("Multimediesenteret");
  for (const f of [front, body]) {
    const src = await PDFDocument.load(readFileSync(f));
    for (const pg of await out.copyPages(src, src.getPageIndices())) out.addPage(pg);
  }
  writeFileSync(OUT, await out.save());
  for (const f of [front, body]) rmSync(f, { force: true });
  await browser.close();
  rmSync(join(DIR, ".manual.tmp.html"), { force: true });
  writeFileSync(HASH, `${inputsHash()}\n`);
  console.log(`Skrev ${OUT}`);
}

await main();
