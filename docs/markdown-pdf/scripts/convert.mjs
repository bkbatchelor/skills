#!/usr/bin/env node
// Convert Markdown to PDF, HTML, PNG or JPEG, with the feature set of the
// VS Code extension "Markdown PDF" (yzane/vscode-markdown-pdf), as a CLI.
//
// Usage: convert.mjs [options] <file.md> [more.md ...]
// Run with --help for the options. Exit codes: 0 ok · 1 conversion failed · 2 usage.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const SKILL_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// ---------------------------------------------------------------- settings --

// Same names and defaults as the extension's "markdown-pdf.*" settings.
export const DEFAULTS = {
  type: ["pdf"],
  outputDirectory: "",
  styles: [],
  includeDefaultStyles: true,
  highlight: true,
  highlightStyle: "",
  breaks: false,
  emoji: true,
  sanitize: "gfm", // gfm | gfm-allow-style | none
  "math.enabled": true,
  "math.katex.macros": {},
  "markdown-it-include.enable": true,
  executablePath: "",
  scale: 1,
  displayHeaderFooter: true,
  headerTemplate:
    "<div style=\"font-size: 9px; margin-left: 1cm;\"><span class='title'></span></div>" +
    "<div style=\"font-size: 9px; margin-left: auto; margin-right: 1cm;\">%%ISO-DATE%%</div>",
  footerTemplate:
    "<div style=\"font-size: 9px; margin: 0 auto;\"><span class='pageNumber'></span> / <span class='totalPages'></span></div>",
  printBackground: true,
  orientation: "portrait",
  pageRanges: "",
  format: "A4",
  width: "",
  height: "",
  "margin.top": "1.5cm",
  "margin.bottom": "1cm",
  "margin.right": "1cm",
  "margin.left": "1cm",
  quality: 100,
  "clip.x": "",
  "clip.y": "",
  "clip.width": "",
  "clip.height": "",
  omitBackground: false,
};

const FORMATS = ["pdf", "html", "png", "jpeg"];
const PAPER = ["Letter", "Legal", "Tabloid", "Ledger", "A0", "A1", "A2", "A3", "A4", "A5", "A6"];

function coerce(key, raw) {
  const d = DEFAULTS[key];
  if (typeof raw !== "string") return raw;
  if (typeof d === "boolean") return /^(1|true|yes|on)$/i.test(raw);
  if (typeof d === "number") return Number(raw);
  if (Array.isArray(d)) return raw.split(",").map((s) => s.trim()).filter(Boolean);
  if (d && typeof d === "object") return JSON.parse(raw);
  return raw;
}

/** Accepts flat keys ("margin.top") or nested objects ({margin:{top}}). Drops a "markdown-pdf." prefix. */
function flatten(obj, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = (prefix + k).replace(/^markdown-pdf\./, "");
    if (v && typeof v === "object" && !Array.isArray(v) && !(key in DEFAULTS)) flatten(v, key + ".", out);
    else out[key] = v;
  }
  return out;
}

export function buildSettings(...layers) {
  const s = { ...DEFAULTS };
  for (const layer of layers) {
    for (const [k, v] of Object.entries(flatten(layer))) {
      if (!(k in DEFAULTS)) throw new UsageError(`Unknown setting "${k}". Run with --help to list them.`);
      s[k] = coerce(k, v);
    }
  }
  if (typeof s.type === "string") s.type = coerce("type", s.type);
  if (s.type.includes("all")) s.type = [...FORMATS];
  for (const t of s.type) if (!FORMATS.includes(t)) throw new UsageError(`Unknown type "${t}". Use pdf, html, png, jpeg or all.`);
  if (!["gfm", "gfm-allow-style", "none"].includes(s.sanitize)) throw new UsageError(`sanitize must be gfm, gfm-allow-style or none.`);
  if (!["portrait", "landscape"].includes(s.orientation)) throw new UsageError(`orientation must be portrait or landscape.`);
  if (!PAPER.includes(s.format)) throw new UsageError(`format must be one of ${PAPER.join(", ")}.`);
  return s;
}

class UsageError extends Error {}

// ------------------------------------------------------------ markdown-it --

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function slugify(text) {
  // GitHub style: lowercase, drop punctuation, spaces to hyphens, keep non-ASCII letters.
  return text.trim().toLowerCase().replace(/[^\p{L}\p{N}\p{M}\s_-]/gu, "").replace(/\s/g, "-");
}

function tokensText(inline) {
  return (inline.children || []).map((t) => (t.type === "text" || t.type === "code_inline" ? t.content : "")).join("");
}

const SANITIZE_BASE = () => {
  const sanitizeHtml = require("sanitize-html");
  return {
    allowedTags: [...sanitizeHtml.defaults.allowedTags, "img", "details", "summary", "del", "ins", "sub", "sup", "kbd", "mark", "figure", "figcaption", "input", "section", "span", "div", "u", "abbr", "center", "font"],
    allowedAttributes: {
      "*": ["class", "id", "align", "title", "lang", "dir"],
      a: ["href", "name", "target", "rel"],
      img: ["src", "alt", "width", "height"],
      input: ["type", "checked", "disabled"],
      td: ["colspan", "rowspan", "align"],
      th: ["colspan", "rowspan", "align"],
      details: ["open"],
    },
    allowedSchemes: ["http", "https", "mailto", "file", "data", "tel"],
    allowedSchemesAppliedToAttributes: ["href", "src"],
    disallowedTagsMode: "discard",
    // Remove these with their content, not just the tags.
    nonTextTags: ["style", "script", "textarea", "option", "noscript", "iframe", "object", "embed"],
  };
};

function sanitizeFragment(html, mode) {
  if (mode === "none") return html;
  const sanitizeHtml = require("sanitize-html");
  const opts = SANITIZE_BASE();
  if (mode === "gfm-allow-style") {
    opts.allowedTags.push("style");
    opts.nonTextTags = opts.nonTextTags.filter((t) => t !== "style");
    opts.allowVulnerableTags = true; // sanitize-html warns when style is allowed; this is the explicit opt-in
  }
  return sanitizeHtml(html, opts);
}

function createMarkdown(s, state) {
  const MarkdownIt = require("markdown-it");
  const hljs = require("highlight.js");

  const md = new MarkdownIt({
    html: true,
    breaks: s.breaks,
    linkify: true,
    typographer: false,
    highlight(code, lang) {
      if (lang === "mermaid") return "";
      if (s.highlight && lang && hljs.getLanguage(lang)) {
        try {
          return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang, ignoreIllegals: true }).value}</code></pre>`;
        } catch { /* fall through */ }
      }
      if (s.highlight) {
        return `<pre class="hljs"><code>${hljs.highlightAuto(code).value}</code></pre>`;
      }
      return `<pre class="hljs"><code>${esc(code)}</code></pre>`;
    },
  });

  // Raw HTML goes through the sanitizer; generated HTML (math, diagrams) does not.
  for (const rule of ["html_block", "html_inline"]) {
    md.renderer.rules[rule] = (tokens, idx) => sanitizeFragment(tokens[idx].content, s.sanitize);
  }

  // Fences: mermaid becomes a diagram block, drawn in the browser from the bundled copy.
  const defaultFence = md.renderer.rules.fence;
  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const tok = tokens[idx];
    const lang = (tok.info || "").trim().split(/\s+/)[0];
    if (lang === "mermaid") {
      state.hasMermaid = true;
      return `<pre class="mermaid">${esc(tok.content)}</pre>\n`;
    }
    if (lang === "plantuml") state.hasPlantuml = true; // shown as a plain code block: drawing it needs a remote server
    return defaultFence(tokens, idx, options, env, self);
  };

  if (s.emoji) {
    const { full } = require("markdown-it-emoji");
    md.use(full);
  }

  if (s["math.enabled"]) {
    const katexPlugin = require("@vscode/markdown-it-katex");
    md.use(katexPlugin.default ?? katexPlugin, { macros: s["math.katex.macros"], throwOnError: false });
  }

  // ::: name ... ::: becomes <div class="name">
  const container = require("markdown-it-container");
  md.use(container.default ?? container, "any", {
    validate: (params) => /^[A-Za-z][\w-]*(\s|$)/.test(params.trim()),
    render(tokens, idx) {
      const t = tokens[idx];
      if (t.nesting === 1) return `<div class="${esc(t.info.trim().split(/\s+/)[0])}">\n`;
      return "</div>\n";
    },
  });

  // Task list checkboxes: "- [ ] x" and "- [x] x".
  md.core.ruler.after("inline", "task-checkbox", (st) => {
    const toks = st.tokens;
    for (let i = 2; i < toks.length; i++) {
      if (toks[i].type !== "inline" || toks[i - 1].type !== "paragraph_open" || toks[i - 2].type !== "list_item_open") continue;
      const first = toks[i].children?.[0];
      const m = first?.type === "text" && /^\[([ xX])\]\s+/.exec(first.content);
      if (!m) continue;
      first.content = first.content.slice(m[0].length);
      const box = new st.Token("task_box", "", 0);
      box.content = `<input type="checkbox" disabled${m[1] === " " ? "" : " checked"}> `;
      toks[i].children.unshift(box);
      toks[i - 2].attrJoin("class", "task-list-item");
    }
  });

  md.renderer.rules.task_box = (tokens, idx) => tokens[idx].content;

  // Heading ids, GitHub style, with -1, -2 suffixes on repeats.
  md.core.ruler.push("heading-ids", (st) => {
    const seen = new Map();
    for (let i = 0; i < st.tokens.length; i++) {
      const t = st.tokens[i];
      if (t.type !== "heading_open") continue;
      const base = slugify(tokensText(st.tokens[i + 1])) || "section";
      const n = seen.get(base) ?? 0;
      seen.set(base, n + 1);
      t.attrSet("id", n === 0 ? base : `${base}-${n}`);
    }
  });

  return md;
}

// ------------------------------------------------------------- preprocess --

/** Inline `:[label](path.md)` includes. Errors become a visible note and the export continues. */
function expandIncludes(text, baseDir, stack, warn) {
  const lines = text.split("\n");
  let fence = null;
  return lines.map((line) => {
    const f = /^\s*(`{3,}|~{3,})/.exec(line);
    if (f) {
      if (!fence) fence = f[1][0];
      else if (f[1][0] === fence) fence = null;
      return line;
    }
    if (fence) return line;
    const m = /^:\[([^\]]*)\]\(([^)]+)\)\s*$/.exec(line);
    if (!m) return line;
    const file = path.resolve(baseDir, m[2].trim());
    const fail = (why) => {
      warn(`include ${m[2]}: ${why}`);
      return `<p class="include-error">Include failed (${esc(m[2])}): ${esc(why)}</p>`;
    };
    if (stack.includes(file)) return fail("circular include");
    if (stack.length >= 8) return fail("includes nested too deeply");
    let body;
    try {
      body = fs.readFileSync(file, "utf8");
    } catch (e) {
      return fail(e.code === "ENOENT" ? "file not found" : e.message);
    }
    return expandIncludes(stripFrontMatter(body).body, path.dirname(file), [...stack, file], warn);
  }).join("\n");
}

function stripFrontMatter(text) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(text);
  if (!m) return { body: text, meta: {} };
  try {
    const meta = require("js-yaml").load(m[1]);
    if (meta && typeof meta === "object" && !Array.isArray(meta)) return { body: text.slice(m[0].length), meta };
  } catch { /* not YAML: leave the text alone */ }
  return { body: text, meta: {} };
}

// ----------------------------------------------------------------- styles --

function readStyles(s, srcDir, forBrowser) {
  const css = [];
  if (s.highlight) {
    const name = (s.highlightStyle || "github.css").replace(/\.css$/, "") + ".css";
    const p = path.join(SKILL_DIR, "node_modules", "highlight.js", "styles", name);
    css.push(fs.existsSync(p) ? fs.readFileSync(p, "utf8") : fs.readFileSync(path.join(SKILL_DIR, "node_modules", "highlight.js", "styles", "github.css"), "utf8"));
  }
  if (s.includeDefaultStyles) css.push(fs.readFileSync(path.join(SKILL_DIR, "styles", "default.css"), "utf8"));
  for (const entry of s.styles) {
    if (/^https?:\/\//.test(entry)) {
      css.push(`@import url("${entry}");`);
      continue;
    }
    const p = path.resolve(entry.startsWith("~") ? path.join(os.homedir(), entry.slice(1)) : path.isAbsolute(entry) ? entry : path.join(srcDir, entry));
    if (!fs.existsSync(p)) throw new Error(`Style file not found: ${p}`);
    css.push(fs.readFileSync(p, "utf8"));
  }
  return css.join("\n");
}

function katexCss(embed) {
  const dir = path.join(SKILL_DIR, "node_modules", "katex", "dist");
  let css = fs.readFileSync(path.join(dir, "katex.min.css"), "utf8");
  css = css.replace(/,url\([^)]*\.(woff|ttf)\)\s*format\("[^"]*"\)/g, "");
  return css.replace(/url\((fonts\/[^)]+\.woff2)\)/g, (_m, rel) => {
    const file = path.join(dir, rel);
    if (!embed) return `url(${pathToFileURL(file).href})`;
    return `url(data:font/woff2;base64,${fs.readFileSync(file).toString("base64")})`;
  });
}

// -------------------------------------------------------- images and html --

const MIME = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp", ".bmp": "image/bmp" };

/** Rewrite relative <img src> to file:// URLs (browser output) or data: URIs (HTML output). */
function resolveImages(html, srcDir, mode, warn) {
  return html.replace(/(<img\b[^>]*?\ssrc=")([^"]+)(")/gi, (m, a, src, b) => {
    if (/^(https?:|data:|file:|\/\/)/i.test(src)) return m;
    let decoded = src.replace(/&amp;/g, "&");
    try { decoded = decodeURIComponent(decoded); } catch { /* keep as is */ }
    const file = path.resolve(srcDir, decoded.split(/[?#]/)[0]);
    if (!fs.existsSync(file)) { warn(`image not found: ${src}`); return m; }
    if (mode === "file") return `${a}${pathToFileURL(file).href}${b}`;
    const mime = MIME[path.extname(file).toLowerCase()];
    if (!mime) return m;
    return `${a}data:${mime};base64,${fs.readFileSync(file).toString("base64")}${b}`;
  });
}

let mermaidCache;
/** The mermaid bundle from node_modules, inlined so no diagram or script ever comes from the network. */
function mermaidSource() {
  mermaidCache ??= fs.readFileSync(path.join(SKILL_DIR, "node_modules", "mermaid", "dist", "mermaid.min.js"), "utf8").replace(/<\/script/gi, "<\\/script");
  return mermaidCache;
}

function buildHtml({ body, title, css, hasMath, hasMermaid, mode }) {
  const extra = hasMath ? katexCss(mode === "html") : "";
  const mermaid = hasMermaid
    ? `<script>${mermaidSource()}</script>\n<script>mermaid.initialize({startOnLoad:false,theme:"default"});window.__mermaidDone=mermaid.run({querySelector:"pre.mermaid"}).then(()=>true,e=>{console.error("mermaid: "+e);return false;});</script>`
    : "";
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>${esc(title)}</title>
<style>
${extra}
${css}
</style>
</head>
<body class="markdown-body">
${body}
${mermaid}
</body>
</html>
`;
}

// ---------------------------------------------------------------- browser --

function findChrome(s) {
  const candidates = [];
  if (s.executablePath) candidates.push(s.executablePath);
  if (process.env.PUPPETEER_EXECUTABLE_PATH) candidates.push(process.env.PUPPETEER_EXECUTABLE_PATH);
  for (const name of ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "microsoft-edge-stable", "microsoft-edge", "chrome"]) {
    for (const dir of (process.env.PATH || "").split(path.delimiter)) if (dir) candidates.push(path.join(dir, name));
  }
  candidates.push(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  );
  for (const c of candidates) {
    try { fs.accessSync(c, fs.constants.X_OK); if (fs.statSync(c).isFile()) return c; } catch { /* next */ }
  }
  // Browsers puppeteer cached earlier.
  const cache = path.join(os.homedir(), ".cache", "puppeteer", "chrome");
  try {
    for (const v of fs.readdirSync(cache).sort().reverse()) {
      const p = path.join(cache, v, "chrome-linux64", "chrome");
      if (fs.existsSync(p)) return p;
    }
  } catch { /* none */ }
  return null;
}

function isoStamps(str) {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  const date = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  const time = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  return str.replace(/%%ISO-DATETIME%%/g, `${date} ${time}`).replace(/%%ISO-DATE%%/g, date).replace(/%%ISO-TIME%%/g, time);
}

const unitOrNull = (v) => (v === "" || v == null ? undefined : v);
const numOrUndef = (v) => (v === "" || v == null || Number.isNaN(Number(v)) ? undefined : Number(v));

async function renderWithBrowser(browserHtml, outputs, s, warn) {
  const puppeteer = require("puppeteer-core");
  const exe = findChrome(s);
  if (!exe) {
    throw new Error("No Chrome, Chromium or Edge found. Install one, or pass --chrome /path/to/browser (PDF, PNG and JPEG need a browser; HTML does not).");
  }
  const args = ["--disable-gpu"];
  if (process.getuid?.() === 0 || process.env.MD_NO_SANDBOX === "1") args.push("--no-sandbox");
  const browser = await puppeteer.launch({ executablePath: exe, args, headless: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "md-pdf-"));
  try {
    const htmlFile = path.join(tmp, "page.html");
    fs.writeFileSync(htmlFile, browserHtml);
    const page = await browser.newPage();
    page.on("pageerror", (e) => warn(`page error: ${e.message}`));
    await page.goto(pathToFileURL(htmlFile).href, { waitUntil: "networkidle0", timeout: 60000 });
    if (await page.evaluate(() => typeof window.__mermaidDone !== "undefined")) {
      const ok = await page.evaluate(() => window.__mermaidDone);
      if (!ok) warn("a Mermaid diagram failed to render; see the page error above");
    }
    await page.evaluate(() => document.fonts && document.fonts.ready);

    for (const { type, file } of outputs) {
      if (type === "pdf") {
        const opts = {
          path: file,
          scale: s.scale,
          displayHeaderFooter: s.displayHeaderFooter,
          headerTemplate: isoStamps(s.displayHeaderFooter ? s.headerTemplate : ""),
          footerTemplate: isoStamps(s.displayHeaderFooter ? s.footerTemplate : ""),
          printBackground: s.printBackground,
          landscape: s.orientation === "landscape",
          pageRanges: s.pageRanges || "",
          margin: { top: s["margin.top"], bottom: s["margin.bottom"], right: s["margin.right"], left: s["margin.left"] },
        };
        if (unitOrNull(s.width) || unitOrNull(s.height)) {
          if (s.width) opts.width = s.width;
          if (s.height) opts.height = s.height;
        } else {
          opts.format = s.format;
        }
        await page.pdf(opts);
      } else {
        const opts = { path: file, type, fullPage: true, omitBackground: s.omitBackground };
        if (type === "jpeg") { opts.quality = s.quality; opts.omitBackground = false; }
        const clip = { x: numOrUndef(s["clip.x"]), y: numOrUndef(s["clip.y"]), width: numOrUndef(s["clip.width"]), height: numOrUndef(s["clip.height"]) };
        if (Object.values(clip).every((v) => v !== undefined)) { opts.clip = clip; opts.fullPage = false; }
        await page.screenshot(opts);
      }
    }
  } finally {
    await browser.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

// ------------------------------------------------------------- conversion --

export async function convertFile(input, s, { outDir, warn = (m) => console.error(`warning: ${m}`) } = {}) {
  const abs = path.resolve(input);
  const srcDir = path.dirname(abs);
  const stem = path.basename(abs, path.extname(abs));
  const raw = fs.readFileSync(abs, "utf8");
  const { body: md0, meta } = stripFrontMatter(raw);

  const state = { hasMermaid: false, hasPlantuml: false };
  let text = md0;
  if (s["markdown-it-include.enable"]) text = expandIncludes(text, srcDir, [abs], warn);
  text = text.replace(/<div\s+class=["']page["']\s*\/>/g, '<div class="page"></div>');
  if (/^\s*@startuml/m.test(text)) state.hasPlantuml = true;

  const md = createMarkdown(s, state);
  const body = md.render(text);
  const hasMath = s["math.enabled"] && /class="katex/.test(body);
  const title = String(meta.title ?? stem);
  const css = readStyles(s, srcDir, true);

  const dir = path.resolve(outDir ?? (s.outputDirectory ? s.outputDirectory.replace(/^~/, os.homedir()) : srcDir));
  fs.mkdirSync(dir, { recursive: true });

  const written = [];
  const needBrowser = s.type.filter((t) => t !== "html");

  if (s.type.includes("html")) {
    const html = buildHtml({ body: resolveImages(body, srcDir, "data", warn), title, css, hasMath, hasMermaid: state.hasMermaid, mode: "html" });
    const file = path.join(dir, `${stem}.html`);
    fs.writeFileSync(file, html);
    written.push(file);
  }
  if (state.hasPlantuml) warn("PlantUML is not drawn: it needs a remote server, and this tool never sends text off your machine. It is shown as a code block. Use a ```mermaid diagram instead.");

  if (needBrowser.length) {
    const html = buildHtml({ body: resolveImages(body, srcDir, "file", warn), title, css, hasMath, hasMermaid: state.hasMermaid, mode: "browser" });
    const outputs = needBrowser.map((t) => ({ type: t, file: path.join(dir, `${stem}.${t === "jpeg" ? "jpg" : t}`) }));
    await renderWithBrowser(html, outputs, s, warn);
    written.push(...outputs.map((o) => o.file));
  }
  return written;
}

// -------------------------------------------------------------------- cli --

const HELP = `Convert Markdown to PDF, HTML, PNG or JPEG (feature set of the VS Code extension "Markdown PDF").

Usage: convert.mjs [options] <file.md> [more.md ...]

Options:
  -t, --type LIST        pdf, html, png, jpeg (comma list) or all. Default: pdf
  -o, --out-dir DIR      Where to write. Default: beside each source file
  -c, --config FILE      JSON file of settings (default: .markdown-pdf.json beside the source or in the current folder)
      --set KEY=VALUE    Any setting below, repeatable. Example: --set margin.top=2cm --set sanitize=none
      --format NAME      Paper size: ${PAPER.join(", ")}
      --landscape        Same as --set orientation=landscape
      --chrome PATH      Chrome, Chromium or Edge binary (else found on PATH)
      --style FILE       Extra stylesheet, repeatable
      --no-header-footer Same as --set displayHeaderFooter=false
  -h, --help

Settings (same names and defaults as the extension's markdown-pdf.* settings):
${Object.entries(DEFAULTS).map(([k, v]) => `  ${k} = ${JSON.stringify(v).slice(0, 70)}`).join("\n")}

Notes: pdf, png and jpeg need a Chromium-based browser. html needs none.
Mermaid diagrams are drawn locally. PlantUML is not drawn (it needs a remote server) and shows as a code block.
`;

function parseArgs(argv) {
  const o = { files: [], set: {}, styles: [], config: null, outDir: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => { if (i + 1 >= argv.length) throw new UsageError(`${a} needs a value`); return argv[++i]; };
    if (a === "-h" || a === "--help") { o.help = true; }
    else if (a === "-t" || a === "--type") o.set.type = next();
    else if (a === "-o" || a === "--out-dir") o.outDir = next();
    else if (a === "-c" || a === "--config") o.config = next();
    else if (a === "--set") { const kv = next(); const eq = kv.indexOf("="); if (eq < 1) throw new UsageError(`--set needs KEY=VALUE, got "${kv}"`); o.set[kv.slice(0, eq)] = kv.slice(eq + 1); }
    else if (a === "--format") o.set.format = next();
    else if (a === "--landscape") o.set.orientation = "landscape";
    else if (a === "--chrome") o.set.executablePath = next();
    else if (a === "--style") o.styles.push(next());
    else if (a === "--no-header-footer") o.set.displayHeaderFooter = "false";
    else if (a.startsWith("-") && a !== "-") throw new UsageError(`Unknown option ${a}`);
    else o.files.push(a);
  }
  return o;
}

async function main() {
  let o;
  try { o = parseArgs(process.argv.slice(2)); } catch (e) { console.error(e.message); process.exit(2); }
  if (o.help || o.files.length === 0) { process.stdout.write(HELP); process.exit(o.help ? 0 : 2); }

  let failed = 0;
  for (const f of o.files) {
    try {
      if (!fs.existsSync(f)) throw new UsageError(`File not found: ${f}`);
      const cfgPath = o.config ?? [path.join(path.dirname(path.resolve(f)), ".markdown-pdf.json"), path.join(process.cwd(), ".markdown-pdf.json")].find((p) => fs.existsSync(p));
      if (o.config && !fs.existsSync(o.config)) throw new UsageError(`Config file not found: ${o.config}`);
      const fileCfg = cfgPath ? JSON.parse(fs.readFileSync(cfgPath, "utf8")) : {};
      const layers = [fileCfg, o.set];
      if (o.styles.length) layers.push({ styles: o.styles.map((p) => path.resolve(p)) });
      const s = buildSettings(...layers);
      for (const out of await convertFile(f, s, { outDir: o.outDir })) console.log(out);
    } catch (e) {
      failed++;
      console.error(`${f}: ${e.message}`);
      if (e instanceof UsageError) process.exitCode = 2;
    }
  }
  if (failed && !process.exitCode) process.exitCode = 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
