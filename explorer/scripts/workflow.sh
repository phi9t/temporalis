#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXPLORER="$ROOT/explorer"
PYTHON="${PYTHON:-$(command -v python3 || command -v python || true)}"

if [[ -z "$PYTHON" ]]; then
  echo "python3 or python is required" >&2
  exit 127
fi

case "${1:-all}" in
  doctor)
    cd "$ROOT"
    ./.monorepo/monoctl doctor
    ;;
  gen-data)
    cd "$ROOT"
    ./.monorepo/monoctl doctor
    "$PYTHON" explorer/scripts/build_lifecycle_data.py --repo-root .
    ;;
  install)
    cd "$EXPLORER"
    npm install
    ;;
  build)
    cd "$ROOT"
    ./.monorepo/monoctl doctor
    "$PYTHON" explorer/scripts/build_lifecycle_data.py --repo-root .
    cd "$EXPLORER"
    npm run build
    ;;
  dev)
    cd "$EXPLORER"
    npm run dev
    ;;
  all)
    "$0" gen-data
    "$0" install
    "$0" build
    ;;
  *)
    echo "usage: $0 [doctor|gen-data|install|build|dev|all]" >&2
    exit 2
    ;;
esac
