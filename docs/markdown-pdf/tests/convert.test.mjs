// Run: node --test docs/markdown-pdf/tests   (HTML tests need no browser; the PDF test skips without one)
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildSettings, convertFile } from "../scripts/convert.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const sample = path.join(here, "sample.md");
const out = () => fs.mkdtempSync(path.join(os.tmpdir(), "mdpdf-test-"));
const quiet = { warn: () => {} };

async function html(overrides = {}) {
  const dir = out();
  const [file] = await convertFile(sample, buildSettings({ type: "html", ...overrides }), { outDir: dir, ...quiet });
  return fs.readFileSync(file, "utf8");
}

test("heading ids are GitHub style and deduplicated", async () => {
  const h = await html();
  assert.match(h, /id="repeat"/);
  assert.match(h, /id="repeat-1"/);
});

test("task list, container, emoji, math, highlight, include", async () => {
  const h = await html();
  assert.match(h, /<input type="checkbox" disabled checked>/);
  assert.match(h, /<div class="warning">/);
  assert.match(h, /😄/);
  assert.match(h, /class="katex"/);
  assert.match(h, /hljs-keyword/);
  assert.match(h, /Included body\./);
  assert.match(h, /Include failed \(nope\.md\)/);
});

test("sanitize gfm removes script; none keeps it", async () => {
  assert.doesNotMatch(await html(), /alert\(1\)/);
  assert.match(await html({ sanitize: "none" }), /alert\(1\)/);
});

test("switches turn features off", async () => {
  const h = await html({ emoji: false, "math.enabled": false, highlight: false, "markdown-it-include.enable": false });
  assert.match(h, /:smile:/);
  assert.doesNotMatch(h, /class="katex"/);
  assert.doesNotMatch(h, /hljs-keyword/);
  assert.doesNotMatch(h, /Included body\./);
});

test("mermaid fence becomes a diagram block and the script is inlined, not fetched", async () => {
  const h = await html();
  assert.match(h, /<pre class="mermaid">graph TD;/);
  assert.doesNotMatch(h, /<script[^>]+src=/);
  assert.doesNotMatch(h, /cdn\.jsdelivr|unpkg|plantuml\.com/);
});

test("plantuml is never sent anywhere: it stays a code block and warns", async () => {
  const dir = out();
  const md = path.join(dir, "p.md");
  fs.writeFileSync(md, "```plantuml\nAlice -> Bob: secret\n```\n\n@startuml\nA -> B\n@enduml\n");
  const warnings = [];
  const [file] = await convertFile(md, buildSettings({ type: "html" }), { outDir: dir, warn: (m) => warnings.push(m) });
  const h = fs.readFileSync(file, "utf8");
  assert.match(h, /secret/);
  assert.doesNotMatch(h, /<img[^>]+plantuml/);
  assert.ok(warnings.some((w) => /PlantUML is not drawn/.test(w)));
  assert.throws(() => buildSettings({ plantumlServer: "http://x" }), /Unknown setting/);
});

test("unknown setting and bad type are usage errors", () => {
  assert.throws(() => buildSettings({ nope: 1 }), /Unknown setting/);
  assert.throws(() => buildSettings({ type: "doc" }), /Unknown type/);
  assert.deepEqual(buildSettings({ type: "all" }).type, ["pdf", "html", "png", "jpeg"]);
  assert.equal(buildSettings({ "markdown-pdf.margin.top": "2cm" })["margin.top"], "2cm");
  assert.equal(buildSettings({ margin: { top: "3cm" } })["margin.top"], "3cm");
});

test("pdf, png and jpeg are written", async (t) => {
  const dir = out();
  let files;
  try {
    files = await convertFile(sample, buildSettings({ type: "pdf,png,jpeg" }), { outDir: dir, ...quiet });
  } catch (e) {
    if (/No Chrome/.test(e.message)) return t.skip("no browser installed");
    throw e;
  }
  assert.equal(fs.readFileSync(files[0]).subarray(0, 4).toString(), "%PDF");
  for (const f of files) assert.ok(fs.statSync(f).size > 1000, f);
});
