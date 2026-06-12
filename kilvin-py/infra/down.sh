#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose down -v
rm -f .kubeconfig/kubeconfig.yaml
echo "kilvin infra down (volumes removed; allocator ledger and registry reset)"
