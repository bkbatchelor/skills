#!/usr/bin/env bash
# Build (or rebuild) a code-only Graphify graph for a project: structural AST extraction,
# no LLM, no tokens. Output never goes under --source.
#
# Usage: code_graph.sh --source <src> [--out <dir>] [--paths "<p1> <p2> ..."] [--include-tests] [--labels <file.json>]
#   --out            default ~/curated/<basename of src>-code  (graph lands in <out>/graphify-out)
#   --paths          source-relative folders to scan; default: every git-tracked code file
#   --include-tests  keep test folders (default: test/, tests/, src/test/, __tests__/ are skipped)
#   --labels         JSON {"<community id>": "<name>"} applied on top of carried-over labels.
#                    Clustering is deterministic, so ids printed by one run stay valid for an
#                    immediate re-run with --labels on the same tree.
#
# Community labels are carried over from the previous graph.json where >=50% of a new
# community's members agree; the rest are written as "Community N" and listed on stdout so
# the caller can name them.
set -euo pipefail

SRC="" OUT="" PATHS="" TESTS=0 LABELS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SRC="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --paths) PATHS="$2"; shift 2 ;;
    --include-tests) TESTS=1; shift ;;
    --labels) LABELS=$(cd "$(dirname "$2")" && pwd -P)/$(basename "$2"); shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$SRC" ]] || { echo "--source is required" >&2; exit 2; }
SRC=$(cd "$SRC" && pwd -P)
OUT=$(realpath -m "${OUT:-"$HOME/curated/$(basename "$SRC")-code"}")
case "$OUT/" in "$SRC"/*) echo "--out must be outside --source" >&2; exit 2 ;; esac
mkdir -p "$OUT/graphify-out"
git -C "$SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "--source must be a git work tree" >&2; exit 2; }

cd "$OUT"
if [[ -s graphify-out/.graphify_python ]]; then
  PY=$(cat graphify-out/.graphify_python)
else
  PY=$(uv tool run --from graphifyy python -c 'import sys; print(sys.executable)' 2>/dev/null || true)
  [[ -n "$PY" ]] || { echo "graphify is not installed (uv tool install graphifyy)" >&2; exit 1; }
  printf '%s' "$PY" > graphify-out/.graphify_python
fi
printf '%s' "$SRC" > graphify-out/.graphify_root

"$PY" - "$SRC" "$TESTS" "$LABELS" $PATHS <<'EOF'
import json, re, subprocess, sys, collections
from pathlib import Path
from graphify.extract import extract
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json
from graphify.detect import save_manifest

R = Path(sys.argv[1]); tests = sys.argv[2] == '1'; manual = json.loads(Path(sys.argv[3]).read_text()) if sys.argv[3] else {}; scope = sys.argv[4:]
CODE = ('.py', '.java', '.kt', '.kts', '.scala', '.go', '.rs', '.js', '.jsx', '.ts', '.tsx', '.rb', '.php',
        '.cs', '.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.swift', '.lua', '.sh')
TEST = re.compile(r'(^|/)(test|tests|__tests__|src/test)/')
ls = subprocess.run(['git', '-C', str(R), 'ls-files', '--', *scope], capture_output=True, text=True, check=True).stdout.split('\n')
files = [R / f for f in ls if f.endswith(CODE) and (tests or not TEST.search(f))]
if not files:
    sys.exit('no tracked code files in scope')
ex = extract(files, cache_root=Path('.'), root=R)
ex.setdefault('hyperedges', []); ex['input_tokens'] = 0; ex['output_tokens'] = 0
G = build_from_json(ex, root=str(R), directed=True)
if G.number_of_nodes() == 0:
    sys.exit('extraction produced no nodes')
com = cluster(G); coh = score_all(G, com)

gp = Path('graphify-out/graph.json')
old = {n['id']: n.get('community_name') for n in json.loads(gp.read_text())['nodes'] if n.get('community_name')} if gp.exists() else {}
labels, used = {}, set()
for cid, mem in sorted(com.items(), key=lambda kv: (str(kv[0]) not in manual, -len(kv[1]))):
    if str(cid) in manual:
        lab = manual[str(cid)]
        base, i = lab, 2
        while lab in used:
            lab = f'{base} ({i})'; i += 1
        labels[cid] = lab; used.add(lab); continue
    vals = [old[m] for m in mem if m in old]
    lab = None
    if vals:
        top, cnt = collections.Counter(vals).most_common(1)[0]
        if cnt / len(vals) >= 0.5 and not top.startswith('Community '):
            lab = top
    lab = lab or f'Community {cid}'
    base, i = lab, 2
    while lab in used:
        lab = f'{base} ({i})'; i += 1
    labels[cid] = lab; used.add(lab)

det = {'files': {'code': [str(f) for f in files], 'document': [], 'paper': [], 'image': [], 'video': []},
       'total_files': len(files), 'total_words': 0, 'skipped_sensitive': []}
if not to_json(G, com, str(gp), community_labels=labels):
    to_json(G, com, str(gp), community_labels=labels, force=True)  # full AST rebuild each time; shrinking is legitimate
Path('graphify-out/GRAPH_REPORT.md').write_text(generate(G, com, coh, labels, god_nodes(G), surprising_connections(G, com),
                                                         det, {'input': 0, 'output': 0}, str(R),
                                                         suggested_questions=suggest_questions(G, com, labels)))
Path('graphify-out/.graphify_labels.json').write_text(json.dumps({str(k): v for k, v in labels.items()}))
save_manifest({'code': [str(f) for f in files]}, root=str(R), scan_corpus={str(f) for f in files})
unl = [c for c, v in labels.items() if v.startswith('Community ')]
print(f'{len(files)} files -> {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(com)} communities ({len(unl)} unlabelled)')
for c in unl:
    names = [G.nodes[n].get('label', n) for n in com[c][:8]]
    print(f'  unlabelled {c} ({len(com[c])}): ' + ' | '.join(names))
EOF
graphify export html >/dev/null 2>&1 && echo "graph.html written"
echo "graph: $OUT/graphify-out/graph.json"
echo "query: graphify query \"<question>\" --graph $OUT/graphify-out/graph.json"
