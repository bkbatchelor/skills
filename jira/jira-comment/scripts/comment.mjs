#!/usr/bin/env node
// Add a comment to a Jira Cloud issue via Playwright + the saved jira-archive browser session.
// Usage:
//   node comment.mjs --check
//   node comment.mjs verify <KEY|URL> --base <url> [--expect "<text in summary>"]
//   node comment.mjs post   <KEY|URL> --base <url> --file <comment.md> [--expect "<text in summary>"]
// `verify` is read-only (GET). `post` re-verifies the issue, POSTs one comment, re-reads and compares.
// Exit codes: 0 ok | 1 bad input | 2 login not completed | 4 issue not found / no permission
//   5 verification mismatch (nothing posted) | 6 fetch failed | 9 post failed (NOT posted)
//   10 Playwright missing | 11 no usable browser/profile | 12 posted but read-back check failed
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : undefined; };
const VALUE_OPTS = ['--base', '--file', '--expect', '--profile', '--playwright-path'];
const positional = args.filter((a, i) => !a.startsWith('--') && !VALUE_OPTS.includes(args[i - 1]));
const MODE = positional[0];
const TARGET = positional[1] || '';
const PWPATH = opt('--playwright-path') || process.env.PLAYWRIGHT_PATH;
// Same profile as jira-archive: one saved login for both skills.
const PROFILE = opt('--profile') || path.join(os.homedir(), '.config', 'jira-archive', 'edge-profile');

const INSTALL = 'npm i -g playwright && npx playwright install chromium';
let chromium;
try { ({ chromium } = await import('playwright')); }
catch {
  try {
    const { execSync } = await import('node:child_process');
    const { pathToFileURL } = await import('node:url');
    const root = execSync('npm root -g', { encoding: 'utf8' }).trim();
    ({ chromium } = await import(pathToFileURL(path.join(root, 'playwright', 'index.mjs')).href));
  } catch {}
}
if (!chromium && PWPATH) {
  try {
    const { createRequire } = await import('node:module');
    const base = fs.existsSync(path.join(PWPATH, 'node_modules', 'playwright')) ? path.join(PWPATH, 'node_modules') : path.dirname(PWPATH);
    ({ chromium } = createRequire(path.join(base, 'x.js'))('playwright'));
  } catch {}
}
if (!chromium) { console.error(`Playwright is not installed. Install it yourself:\n  ${INSTALL}`); process.exit(10); }
if (flag('--check')) { console.log('playwright ok'); process.exit(0); }

const die = (code, msg) => { console.error(msg); process.exit(code); };

// ---------- inputs ----------
if (!['verify', 'post'].includes(MODE)) die(1, 'Usage: comment.mjs verify|post <KEY|URL> --base <url> [--file comment.md] [--expect text]');
let KEY = '';
let BASE = (opt('--base') || process.env.JIRA_BASE_URL || '').replace(/\/+$/, '');
const urlMatch = TARGET.match(/^(https:\/\/[^/]+)\/(?:browse|issues?)\/([A-Za-z][A-Za-z0-9_]+-\d+)/);
if (urlMatch) { KEY = urlMatch[2].toUpperCase(); if (!BASE) BASE = urlMatch[1]; }
else KEY = TARGET.toUpperCase();
if (!/^[A-Z][A-Z0-9_]+-\d+$/.test(KEY)) die(1, 'Need a Jira key like PROJ-123 or a /browse/<KEY> URL');
if (!/^https:\/\//.test(BASE)) die(1, 'Need --base https://<org>.atlassian.net (or JIRA_BASE_URL)');
if (urlMatch && urlMatch[1] !== BASE) die(1, `URL host ${urlMatch[1]} differs from --base ${BASE}`);
const EXPECT = opt('--expect');

let markdown = '';
if (MODE === 'post') {
  const file = opt('--file');
  if (!file) die(1, 'post needs --file <comment.md>');
  try { markdown = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n').trim(); } catch (e) { die(1, `Cannot read ${file}: ${e.message}`); }
  if (!markdown) die(1, 'Comment is empty; nothing to post');
}

// ---------- Markdown -> ADF (headings, lists, code blocks, bold/italic/code/links, paragraphs) ----------
function inline(text) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|(?<![*\w])\*[^*\s][^*]*\*(?!\w)|https?:\/\/[^\s<>)]+)/g;
  let last = 0, m;
  const push = (t, marks) => { if (t) out.push(marks ? { type: 'text', text: t, marks } : { type: 'text', text: t }); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const s = m[0];
    if (s.startsWith('**')) push(s.slice(2, -2), [{ type: 'strong' }]);
    else if (s.startsWith('`')) push(s.slice(1, -1), [{ type: 'code' }]);
    else if (s.startsWith('[')) { const mm = s.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/); push(mm[1], [{ type: 'link', attrs: { href: mm[2] } }]); }
    else if (s.startsWith('*')) push(s.slice(1, -1), [{ type: 'em' }]);
    else push(s, [{ type: 'link', attrs: { href: s } }]);
    last = m.index + s.length;
  }
  push(text.slice(last));
  return out;
}
function toAdf(md) {
  const lines = md.split('\n');
  const content = [];
  let i = 0;
  const para = (buf) => {
    const nodes = [];
    buf.forEach((l, idx) => { if (idx) nodes.push({ type: 'hardBreak' }); nodes.push(...inline(l)); });
    return { type: 'paragraph', content: nodes };
  };
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const fence = line.match(/^```(\w*)\s*$/);
    if (fence) {
      const code = []; i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) code.push(lines[i++]);
      i++;
      const node = { type: 'codeBlock', content: code.length ? [{ type: 'text', text: code.join('\n') }] : [] };
      if (fence[1]) node.attrs = { language: fence[1] };
      content.push(node); continue;
    }
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { content.push({ type: 'heading', attrs: { level: h[1].length }, content: inline(h[2]) }); i++; continue; }
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const re = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-*]\s+(.*)$/;
      const items = [];
      while (i < lines.length && re.test(lines[i])) { items.push({ type: 'listItem', content: [{ type: 'paragraph', content: inline(lines[i].match(re)[1]) }] }); i++; }
      content.push({ type: ordered ? 'orderedList' : 'bulletList', content: items }); continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^```/.test(lines[i]) && !/^#{1,6}\s/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) buf.push(lines[i++]);
    content.push(para(buf));
  }
  return { type: 'doc', version: 1, content };
}
// plain text of an ADF doc, whitespace-normalised, used for the read-back comparison
function adfText(n) {
  if (n == null) return '';
  if (n.type === 'text') return n.text || '';
  if (n.type === 'hardBreak') return ' ';
  const kids = (n.content || []).map(adfText);
  return ['doc', 'bulletList', 'orderedList', 'listItem', 'codeBlock', 'blockquote'].includes(n.type) || n.type === 'paragraph' || n.type === 'heading' ? kids.join(' ') : kids.join('');
}
const norm = (s) => s.replace(/\s+/g, ' ').trim();

// ---------- session (same flow as jira-archive) ----------
async function apiGet(ctx, p) { return ctx.request.get(BASE + p, { headers: { Accept: 'application/json' } }); }
async function loggedIn(ctx) { try { return (await apiGet(ctx, '/rest/api/3/myself')).ok(); } catch { return false; } }
fs.mkdirSync(PROFILE, { recursive: true });
async function launch(headless) {
  let last;
  for (const o of [{ channel: 'msedge' }, { channel: 'chrome' }, {}]) {
    try { return await chromium.launchPersistentContext(PROFILE, { headless, ...o }); } catch (e) { last = e; }
  }
  die(11, 'No usable browser (Edge, Chrome or Chromium) or profile in use: ' + last.message.split('\n')[0]);
}
let ctx = await launch(true);
if (!(await loggedIn(ctx))) {
  await ctx.close();
  console.error('No valid Jira session: opening Edge. Sign in to Jira; if Edge asks, sign in to the browser profile with your work account (5 min).');
  ctx = await launch(false);
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(BASE).catch(() => {});
  let ok = false;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 100 && !ok; i++) {
    await sleep(3000);
    if (ctx.pages().length === 0) die(2, 'Browser was closed before login finished. Comment NOT posted.');
    ok = await loggedIn(ctx);
  }
  if (!ok) { await ctx.close(); die(2, 'Login not completed. Comment NOT posted.'); }
  await ctx.close();
  ctx = await launch(true);
}
const finish = async (code, msg) => { if (msg) console.error(msg); await ctx.close(); process.exit(code); };

// ---------- verify the ticket ----------
const ir = await apiGet(ctx, `/rest/api/3/issue/${KEY}?fields=summary,status,project,issuetype`);
if (ir.status() === 404) await finish(4, `${KEY} not found or no permission. Comment NOT posted.`);
if (!ir.ok()) await finish(6, `Issue fetch failed: HTTP ${ir.status()} ${(await ir.text()).slice(0, 300)}. Comment NOT posted.`);
const issue = await ir.json();
const f = issue.fields || {};
if ((issue.key || '').toUpperCase() !== KEY) await finish(5, `Verification FAILED: asked for ${KEY}, Jira returned ${issue.key}. Comment NOT posted.`);
if (EXPECT && !(f.summary || '').toLowerCase().includes(EXPECT.toLowerCase())) {
  await finish(5, `Verification FAILED: summary "${f.summary}" does not contain expected text "${EXPECT}". Comment NOT posted.`);
}
console.log(`Verified ${issue.key}: ${f.summary}`);
console.log(`  Project: ${f.project?.key} ${f.project?.name} | Type: ${f.issuetype?.name} | Status: ${f.status?.name}`);
console.log(`  URL: ${BASE}/browse/${issue.key}`);
if (MODE === 'verify') await finish(0);

// ---------- post ----------
const body = toAdf(markdown);
// The POST is sent from a page on the Jira origin (same-origin fetch): Jira Cloud's XSRF check rejects
// cookie-authenticated POSTs made through the bare request context (HTTP 403 "XSRF check failed").
const postPage = ctx.pages()[0] || await ctx.newPage();
try { await postPage.goto(`${BASE}/browse/${KEY}`, { waitUntil: 'domcontentloaded' }); } catch (e) { await finish(9, `Could not open ${KEY} in the browser: ${e.message.split('\n')[0]}. Comment NOT posted.`); }
const pr = await postPage.evaluate(async ({ url, body }) => {
  try {
    const r = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Atlassian-Token': 'no-check' },
      body: JSON.stringify({ body }),
    });
    return { ok: r.ok, status: r.status, text: await r.text() };
  } catch (e) { return { ok: false, status: 0, text: String(e) }; }
}, { url: `${BASE}/rest/api/3/issue/${KEY}/comment`, body });
if (!pr.ok) {
  const why = pr.status === 401 || pr.status === 403 ? 'not authenticated or no permission to comment' : pr.status === 400 ? 'Jira rejected the comment body' : 'unexpected response';
  await finish(9, `Post FAILED (${why}): HTTP ${pr.status} ${pr.text.slice(0, 500)}. Comment NOT posted.`);
}
let posted;
try { posted = JSON.parse(pr.text); } catch { await finish(12, 'Jira answered OK but the response had no JSON body. Check the ticket by hand; the comment may be posted.'); }
const id = posted.id;
if (!id) await finish(12, 'Jira answered OK but returned no comment id. Check the ticket by hand; the comment may be posted.');

// ---------- confirm: re-read the comment by id and compare ----------
const rr = await apiGet(ctx, `/rest/api/3/issue/${KEY}/comment/${id}`);
if (!rr.ok()) await finish(12, `Posted comment ${id} but the read-back failed: HTTP ${rr.status()}. Check ${BASE}/browse/${KEY} by hand.`);
const back = await rr.json();
const want = norm(adfText(body));
const got = norm(adfText(back.body));
if (want !== got) await finish(12, `Posted comment ${id} but the stored text differs from what was sent.\n  sent: ${want.slice(0, 300)}\n  read: ${got.slice(0, 300)}`);
console.log(`Comment ${id} posted and confirmed on ${KEY} by ${back.author?.displayName || 'unknown'} at ${back.created}`);
console.log(`  Link: ${BASE}/browse/${KEY}?focusedCommentId=${id}`);
await ctx.close();
