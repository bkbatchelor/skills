---
name: html-artifacts
description: "Renders dense or visual output (plans, reports, research explainers, review summaries, comparisons, timelines, diagrams, walkthroughs, dashboards) as one self-contained, offline HTML file in the user's house style, then screenshots it to verify it renders. Use whenever the user asks for a plan, report, comparison, review summary, explainer, diagram, walkthrough, or dashboard, or when a chat answer would run past roughly 40 lines or hold a table wider than 3 columns: produce on explicit request, offer in one line otherwise. Also use when the result is worth keeping or sharing. Not for short answers, code edits, numeric charts that need a charting library, or Mermaid-to-SVG file conversion (use mermaid-to-svg)."
metadata:
  version: 1.0.0
---

# HTML Artifacts

Put dense or visual output in one HTML file instead of a long chat reply. The chat gets a short summary and the file path.

## Triggers

- **Produce** the artifact when the user explicitly asks for a plan, report, research explainer, review summary, comparison, timeline, diagram, walkthrough, or dashboard.
- **Offer** it in one line ("Want this as an HTML artifact?") when a chat answer would exceed about 40 lines, hold a table with more than 3 columns, need a diagram, be interactive, or be worth keeping or sharing. Do not write it until they say yes.
- **Skip** for short answers, code edits, quick lookups, and anything the user wants as a different file type (.docx, .pptx, PDF, SVG).

## Hard rules

1. **One file.** A single `.html`; no sidecar CSS, JS, images, or fonts.
2. **Inline everything.** CSS in one `<style>`, JS in one `<script>`; images are inline SVG or `data:` URIs.
3. **No external dependencies.** No CDN, web font, `@import`, remote image, or fetch. It must work offline, opened from `file://`.
4. **Works with JS off.** All content is readable without JS; JS only adds the theme toggle, tabs, sorting, collapsing, and copy buttons.
5. **Accessible basics.** `lang`, a viewport meta, semantic headings, real `<table>` markup, sufficient contrast, and `alt`/`aria-label` on SVG.
6. **No heavy motion.** Only subtle hover and 150ms transitions; respect `prefers-reduced-motion`.
7. **Real content only.** Never invent numbers or sources to fill a layout.

## Where files go

- Default: `~/artifacts/<YYYY-MM-DD>-<slug>.html` (create the folder if needed).
- Clearly project-specific work: `./artifacts/` in the project instead.
- Always print the absolute path at the end.

## House style tokens

Define these once in `:root` at the top of the `<style>` block, and use only `var(--…)` after that. Dark is designed first; light is the alternative. The theme follows the OS and a toggle overrides it with `data-theme` on `<html>`. `references/template.html` already contains this block; keep the two identical.

```css
:root {
  /* type */
  --font-sans: Inter, system-ui, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --fs-sm: 0.875rem; --fs-base: 1rem; --fs-lg: 1.25rem; --fs-xl: 1.75rem; --fs-2xl: 2.5rem;
  --lh-body: 1.6; --lh-tight: 1.2;
  /* space (4px base) */
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 40px; --s7: 64px;
  --radius: 10px; --radius-sm: 6px;
  --w-prose: 72ch; --w-wide: 1100px;
  /* color: dark (default) */
  --bg: #0b1220; --surface: #121a2b; --surface-2: #19233a; --border: #26324a;
  --text: #e6ebf5; --muted: #93a0b8;
  --accent: #2dd4bf; --accent-ink: #04201c;
  --ok: #4ade80; --warn: #fbbf24; --bad: #f87171; --info: #60a5fa;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --bg: #f6f8fb; --surface: #ffffff; --surface-2: #eef2f7; --border: #d8e0ea;
    --text: #0f172a; --muted: #536179;
    --accent: #0f766e; --accent-ink: #ffffff;
    --ok: #15803d; --warn: #b45309; --bad: #b91c1c; --info: #1d4ed8;
  }
}
:root[data-theme="light"] {
  --bg: #f6f8fb; --surface: #ffffff; --surface-2: #eef2f7; --border: #d8e0ea;
  --text: #0f172a; --muted: #536179;
  --accent: #0f766e; --accent-ink: #ffffff;
  --ok: #15803d; --warn: #b45309; --bad: #b91c1c; --info: #1d4ed8;
}
```

Style rules that go with the tokens:

- Sans for text and headings (headings slightly tight, `--lh-tight`); mono for code, numbers in tables, paths, and IDs.
- One accent (teal) for links, active states, and key emphasis. Status colors carry meaning only (ok, warn, bad, info) and always come with a text label or icon, never color alone.
- 1px `--border` borders instead of shadows. Cards are `--surface` with `--radius`.
- Prose is capped at `--w-prose`; tables, dashboards, and diagrams may use `--w-wide`. Page gutter 16px on mobile, 24px or more on desktop.
- Include a `@media print` block: light colors, hide the toggle, no page-breaking inside cards or table rows.

## Layout patterns

Start from `references/template.html`, which has the head, theme toggle, base components, and a short example of each pattern. Keep only what the content needs.

Every artifact opens with the same header: title, one-line summary, date, and (when useful) a status chip. Then a "TL;DR" card of 3 to 5 bullets before any detail.

| Pattern | Structure |
|---|---|
| **Report** | Header, TL;DR card, optional sticky table of contents (collapses on mobile), then numbered sections (`h2`) with prose at `--w-prose`. Callouts (`info`, `warn`) for caveats; footnote-style sources at the end. |
| **Comparison table** | Real `<table>` in a horizontally scrollable wrapper, sticky first column and header, options as columns and criteria as rows. Winner or recommendation column highlighted with `--accent` border; cells use status chips with text. Sortable via inline JS when rows exceed 6. Ends with a one-line verdict. |
| **Timeline** | Vertical ordered list with a left rail line, a dot per event, date in mono, title, and short body. Status color on the dot (done, now, next). Horizontal layouts are only for 6 or fewer events and fall back to vertical on mobile. |
| **Diagram** | Inline SVG using `currentColor` and token variables so it themes automatically; `viewBox` set, `width: 100%`, and a `min-width` of about 640px inside an `overflow-x: auto` wrapper so labels stay legible on mobile; boxes with `--surface-2` fill, `--border` stroke, mono labels; arrows with markers; a legend if more than one edge style. Never rasterize. For complex graphs, keep to roughly 12 nodes or split into several diagrams. |
| **Dashboard** | A grid of stat tiles (label, large mono value, delta chip), followed by panels with inline SVG charts or tables. Auto-fit grid (`repeat(auto-fit, minmax(220px, 1fr))`). State the data's date and source on the page. Use the `dataviz` skill for chart color and form choices if it is available. |
| **Walkthrough** | Numbered steps as cards: step number, what happens, a code block with a copy button, expected result. Collapsible "why" detail per step. |

## Verify before declaring done

Never say the artifact is finished until it has been rendered and checked:

1. Run `scripts/verify.sh <file>`. It full-height screenshots at 1280px and 390px with headless Chromium, collects console errors, and fails on any external URL.
2. **Read both screenshots** and check for: blank or unstyled page, horizontal overflow at 390px, clipped or overlapping text, unreadable contrast, a diagram that is empty or cut off, and broken tables.
3. Fix and re-run until clean. If Chromium is missing, say that the render could not be verified; do not claim success.
4. Only then run `xdg-open <file>` and report: the absolute path, a one or two sentence summary, and what the check covered.

Screenshots go to a `.shots/` folder beside the file; delete them afterwards unless the user wants them.
