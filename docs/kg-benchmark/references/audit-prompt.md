# Audit prompt

Give this to a fresh general-purpose agent after `bench audit-prep`. Fill in the angle-bracket parts. Do not tell it which arm each claim came from, and do not give it your own view of the claims.

```text
You are auditing an LLM judge. In a benchmark, coding-agent sessions answered developer questions
about a repository, and a blind judge flagged <N> specific claims in those answers as false or invented.
Judges are often wrong (expect about half of the flags to fail), so verify each one against the
primary sources yourself.

Inputs:
- <bench>/audit/claims.json: one entry per flagged claim (id, qid, question, flagged_claim,
  answer_file relative to <bench>). Read each full answer for context, so you judge what the answer
  actually said, not the judge's paraphrase. Several claims can come from one answer.
- Repositories (read-only): <repo> (at commit <sha>)<, and other folders>.
- Converted copies of binary documents are in <staging>; use them only to read Word, PDF, Excel or
  PowerPoint files. For text files the repository is the authority.
- The answer key is <bench>/questions.json. Form your own view from the sources first; consult the
  key only afterwards, and report if the key itself looks wrong.

Rules: read-only. Do not edit, create or delete anything in the repositories, do not run git
fetch/checkout/commit, do not run graphify, codegraph or any build, and do not read graph folders
(<graph_paths>) or <instructions_dir>. Do not try to work out which setup an answer came from. Do not
modify the benchmark folder except to write your single output file.

For each claim decide one verdict:
- CONFIRMED: the answer states something false or invented (cite the source line that contradicts
  it, or show the thing does not exist).
- JUDGE_WRONG: the claim is true, the answer did not say it, or it is a hedge or opinion rather than
  a factual error (cite the evidence).
- KEY_ISSUE: the judge flagged it because the answer key is wrong or incomplete (say what the key
  should say, with evidence).
- UNCLEAR: you cannot settle it from the sources (say why).

Write <bench>/audit/audit.json as a JSON list of {id, verdict, evidence, note} (evidence = file:line
or a command-output summary, note = one sentence). Reply with counts per verdict and every KEY_ISSUE
in full, in under 300 words.
```

After it finishes, run `bench audit-merge`. Fix each `KEY_ISSUE` in the key and re-judge that question.
