#!/usr/bin/env python3
"""Count em dashes and list ban-list hits in a text file.

Usage: check.py FILE
Exit 0 when there are no em dashes and no ban-list hits, 1 otherwise.
"""
import re
import sys
from pathlib import Path

LIST = Path(__file__).resolve().parent.parent / "banned-words.md"


def banned_terms():
    terms = []
    for line in LIST.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- "):
            continue
        term = line[2:].split("→")[0].strip().strip("`\"'")
        if term and "—" not in term and "(" not in term:
            terms.append(term)
    return terms


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check.py FILE")
    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    dashes = [(n, l) for n, l in enumerate(lines, 1) if "—" in l]
    print(f"em dashes: {sum(l.count('—') for _, l in dashes)}")
    for n, l in dashes:
        print(f"  line {n}: {l.strip()[:100]}")
    hits = 0
    for term in banned_terms():
        pat = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
        for n, l in enumerate(lines, 1):
            if pat.search(l):
                hits += 1
                print(f"ban-list '{term}' line {n}: {l.strip()[:100]}")
    print(f"ban-list hits: {hits}")
    sys.exit(1 if dashes or hits else 0)


if __name__ == "__main__":
    main()
