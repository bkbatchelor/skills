"""REPORT.md and a self-contained report.html from decisions.json."""

import html
from collections import Counter
from pathlib import Path

from . import now_iso

KIND_TITLES = {"duplicate": "Duplicates", "revision": "Revision families", "superseded": "Superseded by marker",
               "conflict": "Conflicts"}


def short(fid, width=70):
    return fid if len(fid) <= width else "…" + fid[-(width - 1):]


def proposal_lines(p):
    """Plain-text lines describing one proposal (used by both renderers)."""
    lines = []
    keeper = p.get("keeper")
    for m in p["members"]:
        tag = "keep" if m["file"] == keeper else ("exclude" if m["role"] == "exclude" else "both stay")
        lines.append(f"{tag}: {m['file']} ({m['format']})")
    ev = p["evidence"]
    if p["kind"] == "duplicate":
        bits = [f"cross-format {', '.join(ev.get('formats', []))}" if ev.get("cross_format") else None,
                f"similarity {ev['similarity']}" if ev.get("similarity") else None]
        lines.append("evidence: " + (", ".join(b for b in bits if b) or "identical content"))
    elif p["kind"] == "revision":
        lines.append(f"confidence: {ev['confidence']} (decided by {ev['decided_by']})")
        for r in ev["ranking"]:
            lines.append(f"rank {r['rank']}: {r['file']} version {r['version_key']} date source {r['date_source']}"
                         + (" draft" if r["draft"] else ""))
    elif p["kind"] == "superseded":
        lines.append(f"marker: {ev.get('marker_target') or 'no replacement named'}")
    elif p["method"] == "config_key":
        lines.append(f"{ev['diff_count']} differing keys in {ev['logical_file']} (scope: {', '.join(ev['scope']) or 'none'})"
                     + (" [partial parse]" if ev.get("partial_parse") else ""))
        for d in ev["diffs"][:5]:
            vals = [f"{k}={v}" for k, v in d.items() if k != "key"]
            lines.append(f"  {d['key']}: " + " vs ".join(vals))
    else:
        for cp in ev.get("claim_pairs", [])[:3]:
            lines.append(f"claim A: {cp['a'][:160]}")
            lines.append(f"claim B: {cp['b'][:160]}")
    if p.get("suggested_winner"):
        lines.append(f"suggested winner: {p['suggested_winner']}")
    if p.get("review_reason"):
        lines.append(f"needs review: {p['review_reason']}")
    v = p.get("verdict")
    if v:
        lines.append(f"Claude's verdict: winner {v.get('suggested_winner') or 'n/a'}, conflict {v.get('conflict')}: {v.get('rationale', '')}")
    return lines


def sections(doc, inventory):
    props = doc["proposals"]
    out = []
    counts = Counter((p["kind"], p["status"]) for p in props)
    rows = [f"{KIND_TITLES[k]}: {counts[(k, 'accept')]} accepted, {counts[(k, 'proposed')]} proposed, {counts[(k, 'reject')]} rejected"
            for k in KIND_TITLES if any(c for (kk, _), c in counts.items() if kk == k)]
    stats = inventory["stats"]
    out.append(("Summary", [f"{stats['files']} files in {len(doc['sources'])} sources; {stats['unhandled']} unhandled; "
                            f"{stats['curated_candidates']} convertible or native."] + rows
                + [f"{len(doc['unreviewed'])} proposals need review but are over the packet cap." if doc["unreviewed"] else
                   f"{sum(1 for p in props if p.get('packet'))} review packets in packets/."], []))
    out.append(("Sources", [f"{s['name']} (priority {s['priority']}): {s['location']}" + (f" @ {s['commit'][:10]}" if s.get('commit') else "")
                            for s in doc["sources"]], []))
    for status, title in (("proposed", "Needs your decision"), ("accept", "Accepted (pre-accepted or edited)"), ("reject", "Rejected")):
        group = [p for p in props if p["status"] == status]
        if group:
            out.append((f"{title} ({len(group)})", [], [(f"{p['id']} · {KIND_TITLES[p['kind']]} · {p['method']}", proposal_lines(p)) for p in group]))
    if doc["unreviewed"]:
        out.append(("Unreviewed overflow", ["Over the packet cap; raise DOCS_CURATOR_PACKET_CAP to review them:"] + doc["unreviewed"], []))
    un = inventory["unhandled"]
    if un:
        out.append((f"Unhandled files ({len(un)})", [f"{u['id']}: {u['reason']}" for u in un], []))
    other = [f"{m['id']}: {m['note']}" for m in inventory["notes"]]
    if other:
        out.append(("Parsing notes", other, []))
    return out


def markdown(doc, inventory):
    lines = [f"# docs-curator report", "", f"Generated {now_iso()}. Edit `status` in `decisions.json`, then run `apply`.", ""]
    for title, bullets, items in sections(doc, inventory):
        lines += [f"## {title}", ""]
        lines += [f"- {b}" for b in bullets]
        for head, body in items:
            lines += ["", f"### {head}", ""] + [f"- {b}" for b in body]
        lines.append("")
    return "\n".join(lines)


def html_page(doc, inventory):
    e = html.escape
    parts = ["<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             "<title>docs-curator report</title><style>"
             ":root{--bg:#fff;--fg:#1d2330;--mut:#5b6475;--line:#d9dde6;--card:#f5f7fa}"
             "@media(prefers-color-scheme:dark){:root{--bg:#14171f;--fg:#e4e8f0;--mut:#9aa3b5;--line:#2c3342;--card:#1c212c}}"
             "body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:0 auto;padding:1rem 16px 3rem}"
             "h1,h2{margin-top:1.6em}details{background:var(--card);border:1px solid var(--line);border-radius:6px;margin:.4rem 0;padding:.4rem .8rem}"
             "summary{cursor:pointer;font-weight:600;word-break:break-all}li{margin:.15rem 0;word-break:break-word}.mut{color:var(--mut)}"
             "</style><h1>docs-curator report</h1>",
             f"<p class=mut>Generated {e(now_iso())}. Edit <code>status</code> in <code>decisions.json</code>, then run <code>apply</code>.</p>"]
    for title, bullets, items in sections(doc, inventory):
        parts.append(f"<h2>{e(title)}</h2>")
        if bullets:
            parts.append("<ul>" + "".join(f"<li>{e(b)}</li>" for b in bullets) + "</ul>")
        for head, body in items:
            parts.append(f"<details><summary>{e(head)}</summary><ul>" + "".join(f"<li>{e(b)}</li>" for b in body) + "</ul></details>")
    return "".join(parts)


def write(out_dir, doc, inventory):
    out = Path(out_dir)
    (out / "REPORT.md").write_text(markdown(doc, inventory))
    (out / "report.html").write_text(html_page(doc, inventory))
    return str(out / "REPORT.md"), str(out / "report.html")
