# jira-archive

Saves one or more Jira Cloud issues to local folders, one folder per issue key. Each folder holds the issue fields, comments, change history, the raw API data and the original attachments. It uses Playwright, a tool that controls a web browser from a script, and your own browser login. You do not need a Jira API token, and the script never sees your password.

## Install

You need Node.js and Playwright. Run these in a terminal from the root of this repo. The first line creates a symlink, a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. Skip the second line if Playwright is already installed.

```bash
ln -s "$PWD/jira/jira-archive" ~/.claude/skills/jira-archive
npm i -g playwright && npx playwright install chromium
```

If Chromium is not downloaded, the script uses Microsoft Edge, then Google Chrome, if one is installed.

## Use

```bash
node ~/.claude/skills/jira-archive/scripts/archive.mjs PROJ-123 --base https://<org>.atlassian.net --out ~/jira
```

- Give several keys separated by spaces or commas to archive a batch.
- `--force` refreshes a folder that already exists. Attachments with the same id and size are not downloaded again.
- You can set `JIRA_BASE_URL` instead of passing `--base`.

The first time, or when the login has expired, a browser window opens. Sign in to Jira by hand (single sign-on and multi-factor prompts work as usual). The login is kept in a browser profile at `~/.config/jira-archive/edge-profile`, so later runs do not open a window. Treat that folder like a password: never share or commit it.

## What you get

```text
PROJ-123/
├── issue.md         fields, links, attachment table, description, custom fields
├── comments.md      every comment with author and dates
├── history.md       status and field changes
├── issue.json       raw API responses
├── validation.md    what was saved and what could not be
└── attachments/     original files
```

The script only reads from Jira. It does not follow linked issues; run it again on any key you need.
