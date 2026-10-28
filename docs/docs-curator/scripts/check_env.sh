#!/usr/bin/env bash
# Verify the docs-curator runtime. Exit 0 when ready; otherwise exit 1 and name what is missing.
#   check_env.sh          runtime dependencies
#   check_env.sh --dev    also the test and corpus dependencies (pytest, reportlab, graphifyy)
# Run it through the same interpreter as curate.py, e.g.
#   uv run --no-project --with-requirements requirements.txt bash scripts/check_env.sh
set -u

dev=0
[ "${1:-}" = "--dev" ] && dev=1
py="${PYTHON:-python3}"
missing=()

if ! command -v "$py" >/dev/null 2>&1; then
  echo "missing: $py (python 3.10+)" >&2
  exit 1
fi
"$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || missing+=("python>=3.10 (found $("$py" -V 2>&1))")

command -v soffice >/dev/null 2>&1 || command -v libreoffice >/dev/null 2>&1 || missing+=("soffice (LibreOffice, for pptx to pdf)")

# module:pip-name
mods="markitdown:markitdown pptx:python-pptx docx:python-docx openpyxl:openpyxl pypdf:pypdf rapidfuzz:rapidfuzz datasketch:datasketch fastembed:fastembed sklearn:scikit-learn numpy:numpy yaml:pyyaml"
[ "$dev" = 1 ] && mods="$mods pytest:pytest reportlab:reportlab graphify:graphifyy"
for entry in $mods; do
  mod="${entry%%:*}"
  pkg="${entry##*:}"
  "$py" -c "import $mod" >/dev/null 2>&1 || missing+=("python package $pkg")
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "docs-curator environment is not ready. Missing:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi
echo "docs-curator environment OK ($("$py" -V 2>&1))"
