import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import curate  # noqa: E402
import make_corpus  # noqa: E402

FIXTURES = HERE / "fixtures" / "verdicts"
EXPECTED = HERE / "corpus_expected.yaml"


def run(*argv):
    curate.main(list(argv))


def checksums(root):
    import hashlib

    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def decisions(out):
    import json

    rows = [json.loads(line) for line in (Path(out) / ".docs-curator" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    return {r["path"]: (r["action"], r["reason"], r["kept_instead"]) for r in rows}


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("corpus_root") / "corpus"
    make_corpus.build(root)
    return root


@pytest.fixture(scope="session")
def pipeline(corpus, tmp_path_factory):
    """Full run on the synthetic corpus with fixture verdicts. Returns (source, out, before checksums)."""
    out = tmp_path_factory.mktemp("pipeline_out")
    before = checksums(corpus)
    run("analyze", "--source", str(corpus), "--out", str(out))
    vdir = out / ".docs-curator" / "work" / "verdicts"
    for f in FIXTURES.glob("*.json"):
        shutil.copy(f, vdir / f.name)
    run("apply", "--source", str(corpus), "--out", str(out))
    return corpus, out, before


@pytest.fixture()
def fresh_out(tmp_path):
    return tmp_path / "out"
