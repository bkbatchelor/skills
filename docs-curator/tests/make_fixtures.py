#!/usr/bin/env python3
"""Generate the docs-curator smoke-test corpus: three sources.

    make_fixtures.py DEST

DEST/notes          plain folder, priority 10
DEST/official       local git repo with several commits, priority 100
DEST/shared-origin  git repo served as a file:// remote and cloned, priority 50
DEST/sources.toml   declares the three

pptx, docx and xlsx are built with the standard library zip and XML writers.
The pdf is made from the pptx with soffice. Standard library only.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def log(msg):
    print(f"make_fixtures: {msg}", file=sys.stderr)


# --- office builders -------------------------------------------------------------

def rels_xml(items):
    body = "".join(f'<Relationship Id="{i}" Type="{t}" Target="{g}"/>' for i, t, g in items)
    return f'{HEAD}<Relationships xmlns="{PKG_REL}">{body}</Relationships>'


def content_types(overrides):
    body = "".join(f'<Override PartName="{p}" ContentType="{c}"/>' for p, c in overrides)
    return (f'{HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            f'<Default Extension="xml" ContentType="application/xml"/>{body}</Types>')


def core_xml(title, modified):
    return (f'{HEAD}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{escape(title)}</dc:title>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{modified}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{modified}</dcterms:modified></cp:coreProperties>')


def zip_write(path, parts):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)


def theme_xml():
    fills = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3
    lines = '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>' * 3
    effects = '<a:effectStyle><a:effectLst/></a:effectStyle>' * 3
    clr = "".join(f'<a:{n}><a:srgbClr val="{v}"/></a:{n}>' for n, v in [
        ("dk1", "000000"), ("lt1", "FFFFFF"), ("dk2", "1F2937"), ("lt2", "F3F4F6"), ("accent1", "2563EB"),
        ("accent2", "DC2626"), ("accent3", "16A34A"), ("accent4", "CA8A04"), ("accent5", "9333EA"),
        ("accent6", "0891B2"), ("hlink", "2563EB"), ("folHlink", "7C3AED")])
    font = '<a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/>'
    return (f'{HEAD}<a:theme xmlns:a="{NS_A}" name="Fixture"><a:themeElements><a:clrScheme name="c">{clr}</a:clrScheme>'
            f'<a:fontScheme name="f"><a:majorFont>{font}</a:majorFont><a:minorFont>{font}</a:minorFont></a:fontScheme>'
            f'<a:fmtScheme name="x"><a:fillStyleLst>{fills}</a:fillStyleLst><a:lnStyleLst>{lines}</a:lnStyleLst>'
            f'<a:effectStyleLst>{effects}</a:effectStyleLst><a:bgFillStyleLst>{fills}</a:bgFillStyleLst></a:fmtScheme>'
            '</a:themeElements></a:theme>')


def textbox(sid, name, y, h, paras, size):
    body = "".join(f'<a:p><a:r><a:rPr lang="en-US" sz="{size}"/><a:t>{escape(t)}</a:t></a:r></a:p>' for t in paras)
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="457200" y="{y}"/><a:ext cx="8229600" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{body}</p:txBody></p:sp>')


def build_pptx(path, slides, title, modified="2026-02-01T09:00:00Z"):
    """slides: list of (title, [bullets])."""
    tree = ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>')
    parts = {
        "[Content_Types].xml": content_types(
            [("/ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
             ("/ppt/slideMasters/slideMaster1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"),
             ("/ppt/slideLayouts/slideLayout1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"),
             ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
             ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml")]
            + [(f"/ppt/slides/slide{i}.xml", "application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
               for i in range(1, len(slides) + 1)]),
        "_rels/.rels": rels_xml([("rId1", f"{REL}/officeDocument", "ppt/presentation.xml"),
                                 ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml")]),
        "docProps/core.xml": core_xml(title, modified),
        "ppt/presentation.xml": (
            f'{HEAD}<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>'
            + "".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, len(slides) + 1))
            + '</p:sldIdLst><p:sldSz cx="9144000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'),
        "ppt/_rels/presentation.xml.rels": rels_xml(
            [("rId1", f"{REL}/slideMaster", "slideMasters/slideMaster1.xml")]
            + [(f"rId{i + 1}", f"{REL}/slide", f"slides/slide{i}.xml") for i in range(1, len(slides) + 1)]
            + [(f"rId{len(slides) + 2}", f"{REL}/theme", "theme/theme1.xml")]),
        "ppt/slideMasters/slideMaster1.xml": (
            f'{HEAD}<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}"><p:cSld><p:spTree>{tree}</p:spTree></p:cSld>'
            '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
            'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
            '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": rels_xml(
            [("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml"), ("rId2", f"{REL}/theme", "../theme/theme1.xml")]),
        "ppt/slideLayouts/slideLayout1.xml": (
            f'{HEAD}<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" type="blank">'
            f'<p:cSld><p:spTree>{tree}</p:spTree></p:cSld></p:sldLayout>'),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": rels_xml([("rId1", f"{REL}/slideMaster", "../slideMasters/slideMaster1.xml")]),
        "ppt/theme/theme1.xml": theme_xml(),
    }
    for i, (head, bullets) in enumerate(slides, 1):
        parts[f"ppt/slides/slide{i}.xml"] = (
            f'{HEAD}<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}"><p:cSld><p:spTree>{tree}'
            + textbox(2, "Title", 274638, 800000, [head], 3200)
            + textbox(3, "Body", 1300000, 4500000, bullets, 2000)
            + '</p:spTree></p:cSld></p:sld>')
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = rels_xml([("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml")])
    zip_write(path, parts)


def build_docx(path, title, paras, table):
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{escape(title)}</w:t></w:r></w:p>'
    body += "".join(f"<w:p><w:r><w:t>{escape(t)}</w:t></w:r></w:p>" for t in paras)
    body += "<w:tbl>" + "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{escape(c)}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>"
        for row in table) + "</w:tbl>"
    zip_write(path, {
        "[Content_Types].xml": content_types([("/word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
                                              ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml")]),
        "_rels/.rels": rels_xml([("rId1", f"{REL}/officeDocument", "word/document.xml"),
                                 ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml")]),
        "docProps/core.xml": core_xml(title, "2026-04-10T12:00:00Z"),
        "word/document.xml": f'{HEAD}<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
    })


def build_xlsx(path, rows):
    S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    strings = []
    def sidx(t):
        if t not in strings:
            strings.append(t)
        return strings.index(t)
    sheet_rows = ""
    for r, row in enumerate(rows, 1):
        cells = ""
        for c, v in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            cells += f'<c r="{ref}" t="s"><v>{sidx(v)}</v></c>' if isinstance(v, str) else f'<c r="{ref}"><v>{v}</v></c>'
        sheet_rows += f'<row r="{r}">{cells}</row>'
    zip_write(path, {
        "[Content_Types].xml": content_types([("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
                                              ("/xl/worksheets/sheet1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
                                              ("/xl/sharedStrings.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")]),
        "_rels/.rels": rels_xml([("rId1", f"{REL}/officeDocument", "xl/workbook.xml")]),
        "xl/workbook.xml": f'{HEAD}<workbook xmlns="{S}" xmlns:r="{NS_R}"><sheets><sheet name="Budget" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": rels_xml([("rId1", f"{REL}/worksheet", "worksheets/sheet1.xml"),
                                                ("rId2", f"{REL}/sharedStrings", "sharedStrings.xml")]),
        "xl/worksheets/sheet1.xml": f'{HEAD}<worksheet xmlns="{S}"><sheetData>{sheet_rows}</sheetData></worksheet>',
        "xl/sharedStrings.xml": f'{HEAD}<sst xmlns="{S}">' + "".join(f"<si><t>{escape(t)}</t></si>" for t in strings) + "</sst>",
    })


def soffice_pdf(src, dest_dir):
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(["soffice", f"-env:UserInstallation=file://{td}/profile", "--headless", "--convert-to", "pdf",
                            "--outdir", td, str(src)], capture_output=True, text=True, timeout=120)
        out = Path(td) / (Path(src).stem + ".pdf")
        if not out.exists():
            sys.exit(f"make_fixtures: soffice could not make a pdf from {src}:\n{r.stdout}{r.stderr}")
        shutil.copy(out, Path(dest_dir) / out.name)


# --- text content ----------------------------------------------------------------------

SPEC_V1 = """# Payment Service Specification

The payment service accepts card and bank transfer requests from the checkout application.
Each request carries an order identifier, an amount in cents and a currency code.
The service validates the request, contacts the payment provider and stores the result.
Failed requests are retried three times with a short delay between attempts.
Receipts are emailed to the customer after a successful payment.
Refunds are handled by the support team using the admin console.
All amounts are stored as integers to avoid rounding errors.
"""

SPEC_V2 = SPEC_V1.replace("an amount in cents and a currency code.", "an amount in cents, a currency code and an idempotency key.") + \
    "Webhooks notify the checkout application when the final state of a payment changes.\n"

SPEC_FINAL = SPEC_V2.replace("Failed requests are retried three times with a short delay", "Failed requests are retried five times with an exponential delay") \
    .replace("after a successful payment.", "after a successful payment and kept for seven years.") + \
    "Every webhook is signed so that the checkout application can verify the sender.\n"

GUIDE = """# Engineering Onboarding Guide

Welcome to the engineering team. This guide explains how to set up your laptop and get access to the tools you need.
Request your accounts from the platform team on your first day. Install the standard toolchain from the internal package list.
Clone the main repositories and run the local environment script to check that everything builds.
Your buddy will walk you through the review process and the release calendar during the first week.
Ask questions in the engineering channel, nobody expects you to know the system on day one.
"""

GUIDE_V2 = """# Engineering Onboarding Guide

Welcome to the engineering team. This guide explains how to set up your laptop and get access to the tools you need.
Request your accounts from the platform team on your first day. Install the standard toolchain from the internal package list.
Clone the main repositories and run the local environment script to check that everything builds.
Your buddy will walk you through the review process and the release calendar during the first week.
Ask questions in the engineering channel, nobody expects you to know the system on day one.
Security training must be completed within the first two weeks.
"""

ONBOARDING_GUIDE = """# Engineering Onboarding Guide

Welcome to the engineering team. This guide explains how to set up your laptop and get access to the tools you need.
Request your accounts from the platform team on your first day. Install the standard toolchain from the internal package list.
Clone the main repositories and run the local environment script to check that everything builds.
Your buddy will walk you through the review process and the release calendar during the first week.
Ask questions in the engineering channel, nobody expects you to know the system on day one.
Security training must be completed within the first two weeks, and the on-call primer within the first month.
"""

ROADMAP = """# Product Roadmap

The roadmap lists the themes the product team will work on during the year.
In the first quarter we focus on the checkout experience and payment reliability.
In the second quarter we add wallet payments and a self service refund flow.
In the third quarter we open the public API to selected partners.
In the fourth quarter we concentrate on performance work and the mobile applications.
Priorities are reviewed every quarter by the product council.
"""

ROADMAP_DRAFT = """# Product Roadmap

The roadmap lists the themes the product team will work on during the year.
In the first quarter we focus on the checkout experience and payment reliability.
In the second quarter we add wallet payments and a self service refund flow.
In the third quarter we open the public API to every customer after a closed beta.
In the fourth quarter we concentrate on performance work and the mobile applications.
Priorities are reviewed every month by the product council. This draft is not approved.
"""

GLOSSARY = """# Glossary

Account: a customer organisation with one or more users.
Order: a request to buy one or more items, identified by an order number.
Settlement: the transfer of funds from the payment provider to our bank account.
Chargeback: a payment reversal initiated by the cardholder bank.
Idempotency key: a client supplied value that makes a repeated request safe.
"""

OLD_PROCESS = """# Release Process

> DEPRECATED — replaced by new-process.md

Releases are cut every month by the release manager on the last Friday.
"""

NEW_PROCESS = """# Release Process

Releases are cut every two weeks by the on-call engineer. Each release is tagged, announced in the engineering channel
and deployed first to staging, then to production after a smoke test passes.
"""

MEETING = """# Weekly Sync

Attendees: platform and product leads.
Decisions: freeze the checkout changes until the audit finishes, move the demo to Thursday.
Actions: update the runbook, book the audit review room, send the minutes.
"""

FAQ = """# FAQ

## How do I reset my password?
Use the reset link on the sign in page. The link expires after one hour.

## Who approves access requests?
Your manager approves them and the platform team grants them.
"""

FAQ_FORMATTED = """FAQ
===

**How do I reset my password?**

use the Reset Link on the sign in page.  The link EXPIRES after one hour!

**Who approves access requests?**

Your manager approves them, and the platform team grants them.
"""

CHECKLIST = """# Onboarding Checklist

Before the first day: order the laptop, create the email account, add the new hire to the team channel and calendar, and
ask the facilities team to prepare a desk close to the rest of the team.
On the first day: hand over the equipment, introduce the buddy, review the security policy, schedule the one to one meetings,
and walk through the office so the new hire knows where to find the kitchen, the meeting rooms and the quiet area.
During the first week: finish the toolchain setup, read the architecture overview, shadow a deployment, join the standup,
and meet the product manager to learn how requests reach the engineering backlog.
At the end of the first month: collect feedback from the new hire and the buddy, review the goals, plan the training for the
next quarter, and confirm that every account and permission has been granted.
Remember to close every item in the tracker so the hiring manager can see that the process was completed on time.
"""
NEW_HIRE_CHECKLIST = CHECKLIST.replace("hand over the equipment", "hand over the hardware")

RETENTION_NOTES = """# Retention Policy

Customer data is retained for 30 days after account closure. After that period the records are deleted from the primary database.
Backups containing customer data are kept for 90 days. Deletion requests from customers must be completed within 14 days.
The security team reviews the retention schedule every year and reports exceptions to the compliance officer.
"""

RETENTION_SHARED = """# Data Retention

Customer data is retained for 365 days after account closure so that disputes and audits can be answered.
Backups containing customer data are kept for 90 days. Deletion requests from customers are handled by the support desk.
Legal holds override every retention period listed in this document until the case is closed.
"""

ARCH = """# Architecture Overview

The platform is made of a web frontend, an API gateway and a set of backend services.
Services communicate over HTTP and publish events to a message broker.
Every service owns its database and exposes metrics for the monitoring stack.
"""

SECURITY = """# Security Notes

Secrets live in the vault and are never committed to repositories.
Production access requires a hardware key and is reviewed every quarter.
Incidents are reported to the security channel and tracked until a post mortem is written.
"""

RUNBOOK = """# Runbook

When an alert fires, acknowledge it, open the dashboard for the affected service and check recent deployments.
Roll back the last deployment if error rates doubled after it. Write down what you did in the incident channel.
"""

Q3_SLIDES = [("Q3 Review", ["Revenue grew twelve percent over Q2", "Churn fell below two percent"]),
             ("Risks", ["Provider outage in August", "Hiring is behind plan"])]
Q3_MD = "## Q3 Review\n- Revenue grew twelve percent over Q2\n- Churn fell below two percent\n## Risks\n- Provider outage in August\n- Hiring is behind plan\n"
KICKOFF_SLIDES = [("Project Kickoff", ["Goals and scope", "Team and roles"]), ("Timeline", ["Design in March", "Launch in June"])]

APP_DEV = "server.port=8080\nlogging.level=DEBUG\ndb.url=jdbc:postgresql://localhost/app\n"
APP_PROD = "server.port=443\nlogging.level=WARN\ndb.url=jdbc:postgresql://db.internal/app\n"
SERVICE_A = "server.port=8080\nservice.name=billing\nservice.timeout=30\n"
SERVICE_B = "server.port=9090\nservice.name=catalog\nservice.timeout=30\n"
SETTINGS_OFFICIAL = "limits:\n  max_users: 100\n  timeout: 30\nfeatures:\n  beta: false\n"
SETTINGS_SHARED = "limits:\n  max_users: 250\n  timeout: 30\nfeatures:\n  beta: false\n"
ANCHORS = "defaults: &defaults\n  retries: 3\n  timeout: 10\nservice:\n  <<: *defaults\n  name: billing\n"


# --- repos ------------------------------------------------------------------------------------

def git(repo, *args, date=None):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    r = subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                       cwd=repo, env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"make_fixtures: git {' '.join(args)} failed: {r.stderr}")


def write(root, files):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def commit(repo, message, date):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, date=date)


def make_official(root):
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    write(root, {"docs/spec_v1.md": SPEC_V1, "docs/guide.md": GUIDE, "docs/roadmap.md": ROADMAP,
                 "docs/glossary.md": GLOSSARY, "docs/old-process.md": OLD_PROCESS, "docs/new-process.md": NEW_PROCESS,
                 "config/application-dev.properties": APP_DEV, "config/application-prod.properties": APP_PROD,
                 "services/a/application.properties": SERVICE_A, "services/b/application.properties": SERVICE_B,
                 "config/settings.yaml": SETTINGS_OFFICIAL, "config/anchors.yaml": ANCHORS,
                 "docs/architecture.md": ARCH})
    commit(root, "initial docs", "2026-01-10T10:00:00+00:00")
    write(root, {"docs/spec_v2.md": SPEC_V2, "docs/guide_v2.md": GUIDE_V2})
    commit(root, "second revisions", "2026-03-05T10:00:00+00:00")
    git(root, "mv", "docs/guide.md", "docs/onboarding-guide.md")
    write(root, {"docs/onboarding-guide.md": ONBOARDING_GUIDE, "docs/spec_final.md": SPEC_FINAL})
    commit(root, "final spec, rename guide", "2026-06-15T10:00:00+00:00")


def make_shared(root):
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    write(root, {"config/settings.yaml": SETTINGS_SHARED, "docs/runbook.md": RUNBOOK})
    commit(root, "shared config", "2026-02-02T10:00:00+00:00")
    write(root, {"docs/data-retention.md": RETENTION_SHARED})
    commit(root, "retention doc", "2026-05-20T10:00:00+00:00")


def make_notes(root):
    root.mkdir(parents=True)
    write(root, {"meeting-notes.md": MEETING, "meeting-notes-backup.md": MEETING, "faq.md": FAQ,
                 "faq-formatted.md": FAQ_FORMATTED, "onboarding-checklist.md": CHECKLIST,
                 "new-hire-checklist.md": NEW_HIRE_CHECKLIST, "terms.md": GLOSSARY, "roadmap_draft.md": ROADMAP_DRAFT,
                 "retention-policy.md": RETENTION_NOTES, "security-notes.md": SECURITY,
                 "decks/q3-review.md": Q3_MD, "data/model.xyz": "binary-ish content that no extractor understands\n"})
    (root / "decks").mkdir(exist_ok=True)
    build_pptx(root / "decks/q3-review.pptx", Q3_SLIDES, "Q3 Review")
    soffice_pdf(root / "decks/q3-review.pptx", root / "decks")
    build_pptx(root / "decks/kickoff.pptx", KICKOFF_SLIDES, "Project Kickoff", "2026-03-01T09:00:00Z")
    (root / "reports").mkdir()
    build_docx(root / "reports/policy.docx", "Travel Policy", ["Book flights at least two weeks ahead.", "Keep every receipt."],
               [["Item", "Limit"], ["Hotel", "150 dollars"]])
    build_xlsx(root / "reports/budget.xlsx", [["Team", "Budget"], ["Platform", 120000], ["Product", 90000]])
    now = time.time()
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (now, now))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1]).resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"make_fixtures: {dest} is not empty")
    dest.mkdir(parents=True, exist_ok=True)
    make_notes(dest / "notes")
    make_official(dest / "official")
    make_shared(dest / "shared-origin")
    (dest / "sources.toml").write_text(
        f'[[source]]\nname = "notes"\npath = "{dest}/notes"\npriority = 10\n\n'
        f'[[source]]\nname = "official"\npath = "{dest}/official"\npriority = 100\n\n'
        f'[[source]]\nname = "shared"\nurl = "file://{dest}/shared-origin"\npriority = 50\n')
    log(f"wrote corpus to {dest}")


if __name__ == "__main__":
    main()
