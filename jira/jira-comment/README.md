# jira-comment

Adds one comment to a Jira Cloud issue. It checks the issue first, asks you to confirm the exact text, posts it, then reads the comment back to make sure Jira stored what was sent. It uses Playwright, a tool that controls a web browser from a script, and the same saved login as `jira-archive`. You do not need a Jira API token.

## Install

You need Node.js and Playwright. Run these in a terminal from the root of this repo. The first line creates a symlink, a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. Skip the second line if Playwright is already installed.

```bash
ln -s "$PWD/jira/jira-comment" ~/.claude/skills/jira-comment
npm i -g playwright && npx playwright install chromium
```

The skill also uses `plain-english-docs` to write the comment text.

## Use

Check the issue (read-only):

```bash
node ~/.claude/skills/jira-comment/scripts/comment.mjs verify PROJ-123 --base https://<org>.atlassian.net
```

Post a comment written to a file:

```bash
node ~/.claude/skills/jira-comment/scripts/comment.mjs post PROJ-123 --base https://<org>.atlassian.net --file comment.md
```

- You can pass a `https://<org>.atlassian.net/browse/<KEY>` link instead of a key.
- `--expect "<text>"` stops the post unless the issue title contains that text.
- The comment can use headings, lists, code blocks, bold, italic, inline code and links.
- For a comment that explains how a bug was fixed, follow `templates/bug-resolution.md`.

The first time, or when the login has expired, a browser window opens so you can sign in by hand. The login is kept at `~/.config/jira-archive/edge-profile`. Treat that folder like a password: never share or commit it.

## If it fails

The script says plainly when a comment was not posted. Exit code 12 is the only uncertain case: Jira accepted the post but the read-back did not match. Open the issue and check by hand before trying again, so the comment is not posted twice.
