#!/usr/bin/env bash
set -euo pipefail

RELF_DOCS_SOURCE_REF="${1:-}"
RELF_DOCS_PUBLISHED_REF="${2:-HEAD}"
if [[ ! "$RELF_DOCS_SOURCE_REF" =~ ^[a-f0-9]{40}$ ]]; then
  echo "Documentation source requires an immutable full commit SHA." >&2
  exit 2
fi
if [[ "$RELF_DOCS_PUBLISHED_REF" != HEAD ]]; then
  if [[ "$RELF_DOCS_PUBLISHED_REF" != refs/heads/* ]] || ! git check-ref-format "$RELF_DOCS_PUBLISHED_REF"; then
    echo "Documentation source requires HEAD or an explicit public branch ref." >&2
    exit 2
  fi
fi

# A main-only checkout can omit the documentation's development-source objects.
# Fetch the advertised branch too, so the later ancestry check has its current tip.
git fetch --no-tags origin "$RELF_DOCS_PUBLISHED_REF"
git cat-file -e "${RELF_DOCS_SOURCE_REF}^{commit}"
