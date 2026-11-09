#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ "${PUBLIC_SITE_URL:-}" != "https://relfagent.com" ]]; then
  echo "Set PUBLIC_SITE_URL=https://relfagent.com for production builds." >&2
  exit 1
fi

python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "Website tutorial validation requires Python 3.12"'
# Tutorial and repository-link checks need the original, pinned SDK commit.
if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  git fetch --unshallow origin
fi
RELF_DOCS_SOURCE_REF="$(node --input-type=module -e 'import repo from "./repository.json" with { type: "json" }; console.log(repo.ref)')"
RELF_DOCS_PUBLISHED_REF="$(node --input-type=module -e 'import repo from "./repository.json" with { type: "json" }; console.log(repo.publishedRef ?? "HEAD")')"
bash scripts/ensure-docs-source.sh "$RELF_DOCS_SOURCE_REF" "$RELF_DOCS_PUBLISHED_REF"
npm ci
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -e ..
PYTHON_BIN="$PWD/.venv-build/bin/python" npm run verify:production
