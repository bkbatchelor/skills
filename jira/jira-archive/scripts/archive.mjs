#!/usr/bin/env node
// Jira issue archive via Playwright + saved browser session. Read-only (GET only).
// Usage: node archive.mjs <KEY> --base <url> [--out <dir>] [--force] [--check] [--state <file>]
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : undefined; };
const KEYS = args.filter((a, i) => !a.startsWith('--') && !['--base', '--out', '--state', '--profile', '--playwright-path'].includes(args[i - 1]))
  .flatMap((a) => a.split(/[\s,]+/)).filter(Boolean).map((k) => k.toUpperCase());
const BASE = (opt('--base') || process.env.JIRA_BASE_URL || '').replace(/\/+$/, '');
const OUT = path.resolve(opt('--out') || '.');
const PWPATH = opt('--playwright-path') || process.env.PLAYWRIGHT_PATH; // folder containing node_modules/playwright, or the playwright folder itself
const STATE = opt('--state') || path.join(os.homedir(), '.config', 'jira-archive', 'state.json');

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
if (!chromium) {
  console.error(`Playwright is not installed. Install it yourself:\n  ${INSTALL}`);
  process.exit(10);
}
if (flag('--check')) { console.log('playwright ok'); process.exit(0); }
if (!KEYS.length || KEYS.some((k) => !/^[A-Z][A-Z0-9_]+-\d+$/.test(k))) { console.error('Need one or more Jira keys like PROJ-123 (space or comma separated)'); process.exit(1); }
if (!/^https:\/\//.test(BASE)) { console.error('Need --base https://<org>.atlassian.net (or JIRA_BASE_URL)'); process.exit(1); }

const results = []; // {key, code}
function summary() {
  const label = { 0: 'ok', 3: 'skipped (exists)', 4: 'not found / no permission', 5: 'API denied (DOM fallback only)', 6: 'fetch failed', 7: 'archived with problems (see validation.md)', 8: 'error' };
  console.log('\nSummary:'); for (const r of results) console.log(`  ${r.key}: ${label[r.code] || r.code}`);
}
const todo = KEYS.filter((k, i) => KEYS.indexOf(k) === i).filter((k) => {
  if (fs.existsSync(path.join(OUT, k)) && !flag('--force')) { console.error(`${path.join(OUT, k)} exists; skipped (use --force to refresh)`); results.push({ key: k, code: 3 }); return false; }
  return true;
});
if (!todo.length) { summary(); process.exit(3); }

// ---------- session ----------
async function apiGet(ctx, p) {
  const r = await ctx.request.get(BASE + p, { headers: { Accept: 'application/json' } });
  return r;
}
async function loggedIn(ctx) { try { return (await apiGet(ctx, '/rest/api/3/myself')).ok(); } catch { return false; } }

// Dedicated persistent Edge profile: conditional access needs a browser profile signed in with the work account.
// Sign in to that profile once (headed); the profile keeps it.
const PROFILE = opt('--profile') || path.join(os.homedir(), '.config', 'jira-archive', 'edge-profile');
fs.mkdirSync(PROFILE, { recursive: true });
async function launch(headless) {
  let last;
  for (const o of [{ channel: 'msedge' }, { channel: 'chrome' }, {}]) {
    try { return await chromium.launchPersistentContext(PROFILE, { headless, ...o }); } catch (e) { last = e; }
  }
  console.error('No usable browser (Edge, Chrome or Chromium) or profile in use: ' + last.message.split(String.fromCharCode(10))[0]);
  process.exit(11);
}
let ctx = await launch(true);
const browser = { close: () => ctx.close(), isConnected: () => { try { return !!ctx.browser()?.isConnected() || ctx.pages().length > 0; } catch { return false; } } };
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
    if (ctx.pages().length === 0) { console.error('Browser was closed before login finished.'); process.exit(2); }
    ok = await loggedIn(ctx);
  }
  if (!ok) { await ctx.close(); console.error('Login not completed.'); process.exit(2); }
  await ctx.close();
  ctx = await launch(true);
}

async function archiveOne(KEY) {
const dir = path.join(OUT, KEY);
const missing = [];
const note = (s) => missing.push(s);
// ---------- fetch ----------
const raw = {};
let usedDom = false;
const ir = await apiGet(ctx, `/rest/api/3/issue/${KEY}?expand=names,renderedFields,changelog,schema`);
let issue;
if (ir.status() === 404) { console.error(`${KEY} not found or no permission`); return 4; }
if (ir.ok()) { issue = await ir.json(); raw.issue = issue; }
else if (ir.status() === 401 || ir.status() === 403) {
  usedDom = true;
  const page = await ctx.newPage();
  await page.goto(`${BASE}/browse/${KEY}`, { waitUntil: 'networkidle' });
  const text = await page.innerText('body');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'issue.md'), `# ${KEY} (DOM fallback: API returned ${ir.status()})\n\n${text}\n`);
  fs.writeFileSync(path.join(dir, 'validation.md'), `# Validation\n\nAPI denied (${ir.status()}). Only page text was captured; fields, comments, history and attachments are NOT archived.\n`);
  console.error('API denied; DOM fallback written. See validation.md');
  return 5;
} else { console.error(`Issue fetch failed: HTTP ${ir.status()}`); return 6; }

const f = issue.fields || {};
const names = issue.names || {};

async function paged(p, listKey, pageSize = 100) {
  const all = []; let start = 0, total = Infinity;
  while (start < total) {
    const r = await apiGet(ctx, `${p}${p.includes('?') ? '&' : '?'}startAt=${start}&maxResults=${pageSize}`);
    if (!r.ok()) { note(`${p}: HTTP ${r.status()} after ${all.length} items`); break; }
    const j = await r.json();
    const items = j[listKey] || j.values || [];
    all.push(...items); total = j.total ?? j.startAt + items.length;
    if (!items.length) break; start += items.length;
    if (j.isLast) break;
  }
  return all;
}
const comments = await paged(`/rest/api/3/issue/${KEY}/comment?expand=renderedBody`, 'comments');
raw.comments = comments;
const declaredComments = f.comment?.total;
if (declaredComments != null && declaredComments !== comments.length) note(`Comments: expected ${declaredComments}, got ${comments.length}`);
let histories = await paged(`/rest/api/3/issue/${KEY}/changelog`, 'values');
if (!histories.length) histories = issue.changelog?.histories || [];
raw.changelog = histories;

// ---------- ADF -> Markdown ----------
const unknownNodes = new Set();
function adf(n, ctxo = {}) {
  if (n == null) return '';
  if (typeof n === 'string') return n;
  const kids = (sep = '') => (n.content || []).map((c) => adf(c, ctxo)).join(sep);
  switch (n.type) {
    case 'doc': return kids('\n\n').trim();
    case 'paragraph': return kids();
    case 'text': {
      let t = n.text || '';
      for (const m of n.marks || []) {
        if (m.type === 'strong') t = `**${t}**`;
        else if (m.type === 'em') t = `*${t}*`;
        else if (m.type === 'code') t = '`' + t + '`';
        else if (m.type === 'strike') t = `~~${t}~~`;
        else if (m.type === 'link') t = `[${t}](${m.attrs?.href})`;
      }
      return t;
    }
    case 'hardBreak': return '  \n';
    case 'heading': return '#'.repeat(n.attrs?.level || 1) + ' ' + kids();
    case 'bulletList': return (n.content || []).map((li) => '- ' + adf(li, ctxo).replace(/\n/g, '\n  ')).join('\n');
    case 'orderedList': return (n.content || []).map((li, i) => `${i + 1}. ` + adf(li, ctxo).replace(/\n/g, '\n   ')).join('\n');
    case 'listItem': return kids('\n');
    case 'blockquote': return kids('\n\n').split('\n').map((l) => '> ' + l).join('\n');
    case 'codeBlock': return '```' + (n.attrs?.language || '') + '\n' + kids() + '\n```';
    case 'rule': return '---';
    case 'mention': return n.attrs?.text || '@user';
    case 'emoji': return n.attrs?.text || n.attrs?.shortName || '';
    case 'inlineCard': case 'blockCard': return n.attrs?.url ? `<${n.attrs.url}>` : '';
    case 'status': return `[${n.attrs?.text}]`;
    case 'date': return n.attrs?.timestamp ? new Date(+n.attrs.timestamp).toISOString().slice(0, 10) : '';
    case 'panel': return kids('\n\n').split('\n').map((l) => '> ' + l).join('\n');
    case 'mediaSingle': case 'mediaGroup': return kids('\n');
    case 'media': return `[attachment: ${n.attrs?.alt || n.attrs?.id || 'media'}]`;
    case 'table': return (n.content || []).map((r, i) => {
      const cells = (r.content || []).map((c) => adf(c, ctxo).replace(/\n+/g, ' ').replace(/\|/g, '\\|'));
      const line = '| ' + cells.join(' | ') + ' |';
      return i === 0 ? line + '\n|' + cells.map(() => ' --- |').join('') : line;
    }).join('\n');
    case 'tableRow': case 'tableCell': case 'tableHeader': return kids(' ');
    default: unknownNodes.add(n.type); return kids('\n');
  }
}

// ---------- value formatting ----------
const iso = (s) => (s ? s.replace('T', ' ').replace(/\.\d+/, '') : '');
function val(v) {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return v.map(val).filter(Boolean).join(', ');
  if (v.type === 'doc') return adf(v);
  if (v.displayName) return v.displayName;
  if (v.value != null) return String(v.value) + (v.child ? ` > ${val(v.child)}` : '');
  if (v.name != null) return v.name;
  if (v.key && v.fields?.summary) return `${v.key} ${v.fields.summary}`;
  return '`' + JSON.stringify(v) + '`';
}
const empty = (v) => v == null || v === '' || (Array.isArray(v) && !v.length) || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length);

// ---------- issue.md ----------
fs.mkdirSync(path.join(dir, 'attachments'), { recursive: true });
const L = [];
L.push(`# ${issue.key}: ${f.summary || ''}`, '');
L.push('| Field | Value |', '| --- | --- |');
const row = (k, v) => L.push(`| ${k} | ${String(v ?? '').replace(/\n/g, ' ').replace(/\|/g, '\\|')} |`);
row('Key', issue.key); row('URL', `${BASE}/browse/${issue.key}`);
row('Type', f.issuetype?.name); row('Status', f.status?.name);
row('Priority', f.priority?.name); row('Assignee', f.assignee?.displayName || 'Unassigned');
row('Reporter', f.reporter?.displayName); row('Labels', (f.labels || []).join(', '));
row('Components', (f.components || []).map((c) => c.name).join(', '));
row('Created', iso(f.created)); row('Updated', iso(f.updated));
row('Resolution', f.resolution?.name || 'Unresolved'); row('Resolution date', iso(f.resolutiondate));
row('Fix versions', (f.fixVersions || []).map((v) => v.name).join(', '));
row('Affects versions', (f.versions || []).map((v) => v.name).join(', '));
row('Project', f.project ? `${f.project.key} ${f.project.name}` : '');
L.push('', '## Parent / epic / sub-tasks', '');
if (f.parent) L.push(`- Parent: ${f.parent.key} (${f.parent.fields?.issuetype?.name}) ${f.parent.fields?.summary} [${f.parent.fields?.status?.name}]`);
for (const s of f.subtasks || []) L.push(`- Sub-task: ${s.key} ${s.fields?.summary} [${s.fields?.status?.name}]`);
if (!f.parent && !(f.subtasks || []).length) L.push('- none');
L.push('', '## Linked issues', '');
for (const l of f.issuelinks || []) {
  const o = l.outwardIssue || l.inwardIssue; const rel = l.outwardIssue ? l.type.outward : l.type.inward;
  L.push(`- ${rel}: ${o.key} (${o.fields?.issuetype?.name}) ${o.fields?.summary} [${o.fields?.status?.name}]`);
}
if (!(f.issuelinks || []).length) L.push('- none');

// attachments
const atts = f.attachment || [];
raw.attachments = atts;
L.push('', '## Attachments', '');
const used = new Map(); const attRows = [];
const safe = (n) => { let s = path.basename(String(n).replace(/\\/g, '/')).replace(/[<>:"|?*\x00-\x1f]/g, '_').replace(/^\.+/, '_'); return s || 'file'; };
for (const a of atts) {
  let name = safe(a.filename); const base = path.parse(name);
  let k = 2; while (used.has(name.toLowerCase())) name = `${base.name} (${k++})${base.ext}`;
  used.set(name.toLowerCase(), 1);
  const target = path.join(dir, 'attachments', name);
  let status = 'ok';
  try {
    if (fs.existsSync(target) && fs.statSync(target).size === a.size) status = 'skipped (identical)';
    else {
      const r = await ctx.request.get(a.content);
      if (!r.ok()) throw new Error(`HTTP ${r.status()}`);
      const buf = await r.body();
      fs.writeFileSync(target, buf);
      if (a.size != null && buf.length !== a.size) { status = `size mismatch (${buf.length}/${a.size})`; note(`Attachment ${a.filename}: ${status}`); }
    }
  } catch (e) { status = `FAILED: ${e.message}`; note(`Attachment ${a.filename} (${a.id}): ${e.message}`); }
  attRows.push({ a, name, status });
}
if (attRows.length) {
  L.push('| Saved as | Original | Id | Size | Author | Created | MIME | Status |', '| --- | --- | --- | --- | --- | --- | --- | --- |');
  for (const { a, name, status } of attRows) L.push(`| ${name} | ${a.filename} | ${a.id} | ${a.size} | ${a.author?.displayName || ''} | ${iso(a.created)} | ${a.mimeType} | ${status} |`);
} else L.push('none');

L.push('', '## Description', '', f.description ? adf(f.description) : '_empty_');

// custom + remaining fields
const core = new Set(['summary', 'description', 'issuetype', 'status', 'priority', 'assignee', 'reporter', 'labels', 'components', 'created', 'updated', 'resolution', 'resolutiondate', 'fixVersions', 'versions', 'project', 'parent', 'subtasks', 'issuelinks', 'attachment', 'comment', 'worklog', 'watches', 'votes', 'lastViewed', 'statuscategorychangedate', 'timetracking', 'aggregatetimespent', 'aggregatetimeoriginalestimate', 'aggregatetimeestimate', 'aggregateprogress', 'progress', 'workratio', 'timespent', 'timeestimate', 'timeoriginalestimate', 'creator', 'security', 'environment']);
L.push('', '## Other fields (non-empty)', '');
let nOther = 0;
for (const [id, v] of Object.entries(f)) {
  if (core.has(id) || empty(v)) continue;
  const label = names[id] || id;
  const text = val(v);
  if (!text) continue;
  nOther++;
  L.push(text.includes('\n') ? `### ${label} (\`${id}\`)\n\n${text}\n` : `- **${label}** (\`${id}\`): ${text}`);
}
if (!nOther) L.push('none');
if (f.environment && !empty(f.environment)) L.push('', '## Environment', '', val(f.environment));
fs.writeFileSync(path.join(dir, 'issue.md'), L.join('\n') + '\n');

// ---------- comments.md ----------
const C = [`# Comments on ${KEY} (${comments.length})`, ''];
for (const c of comments) {
  C.push(`## ${c.author?.displayName || 'unknown'}, ${iso(c.created)}${c.updated && c.updated !== c.created ? ` (updated ${iso(c.updated)})` : ''}`, '', adf(c.body), '');
}
if (!comments.length) C.push('_no comments_');
fs.writeFileSync(path.join(dir, 'comments.md'), C.join('\n') + '\n');

// ---------- history.md ----------
const H = [`# History of ${KEY}`, ''];
for (const h of [...histories].sort((a, b) => (a.created < b.created ? -1 : 1))) {
  for (const it of h.items || []) H.push(`- ${iso(h.created)} ${h.author?.displayName || 'unknown'}: **${it.field}** ${it.fromString ?? ''} -> ${it.toString ?? ''}`);
}
if (!histories.length) H.push('_no history_');
fs.writeFileSync(path.join(dir, 'history.md'), H.join('\n') + '\n');

// ---------- issue.json + validation.md ----------
fs.writeFileSync(path.join(dir, 'issue.json'), JSON.stringify(raw, null, 2));
const okAtt = attRows.filter((r) => !r.status.startsWith('FAILED') && !r.status.startsWith('size')).length;
const V = [`# Validation for ${KEY}`, '', `- Retrieved: ${new Date().toISOString()}`, `- Source: ${BASE} (REST API via browser session${usedDom ? ', DOM fallback' : ''})`,
  `- Fields returned: ${Object.keys(f).length}; non-empty extra fields written: ${nOther}`,
  `- Comments: ${comments.length}${declaredComments != null ? ` of ${declaredComments}` : ''}`,
  `- History entries: ${histories.length}`,
  `- Attachments: ${okAtt} of ${atts.length} saved`,
  `- Unknown rich-text nodes (kept as plain text): ${unknownNodes.size ? [...unknownNodes].join(', ') : 'none'}`, '',
  '## Could not be retrieved', '', ...(missing.length ? missing.map((m) => `- ${m}`) : ['- nothing']), ''];
fs.writeFileSync(path.join(dir, 'validation.md'), V.join('\n'));

console.log(`Archived ${KEY} to ${dir}: ${comments.length} comments, ${okAtt}/${atts.length} attachments, ${missing.length} problem(s). See validation.md`);
return missing.length ? 7 : 0;

}

for (const k of todo) {
  let code;
  try { code = await archiveOne(k); } catch (e) { console.error(`${k}: ${e.message}`); code = 8; }
  results.push({ key: k, code });
}
await ctx.close();
summary();
process.exit(results.some((r) => r.code !== 0 && r.code !== 3) ? 7 : 0);
