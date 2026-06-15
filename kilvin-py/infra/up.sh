#!/usr/bin/env bash
# Bring up the kilvin control plane: temporal + allocator + registry + k3s.
set -euo pipefail
export PATH="/opt/homebrew/bin:$PATH"
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not running; starting colima (cpu 4, memory 8)"
  colima start --cpu 4 --memory 8
fi

allocator_build_hosts=(
  "files.pythonhosted.org"
  "download.pytorch.org"
  "download-r2.pytorch.org"
  "pypi.org"
)
allocator_add_hosts=()
for host in "${allocator_build_hosts[@]}"; do
  if address="$(python3 -c 'import socket, sys; print(socket.gethostbyname(sys.argv[1]))' "$host" 2>/dev/null)"; then
    allocator_add_hosts+=(--add-host "$host:$address")
  fi
done

mkdir -p .kubeconfig
docker build "${allocator_add_hosts[@]}" -t kilvin-infra-allocator ./allocator
docker compose up -d --no-build

echo -n "waiting for temporal :7233 "
for _ in $(seq 1 60); do nc -z localhost 7233 && break; echo -n .; sleep 2; done; echo
nc -z localhost 7233

echo -n "waiting for allocator /healthz "
for _ in $(seq 1 30); do curl -fsS localhost:7070/healthz >/dev/null 2>&1 && break; echo -n .; sleep 2; done; echo
curl -fsS localhost:7070/healthz >/dev/null

export KUBECONFIG="$PWD/.kubeconfig/kubeconfig.yaml"
echo -n "waiting for k3s node Ready "
for _ in $(seq 1 60); do
  [ -f "$KUBECONFIG" ] && kubectl get nodes 2>/dev/null | grep -q ' Ready ' && break
  echo -n .; sleep 2
done; echo
kubectl get nodes | grep -q ' Ready '

kubectl create namespace kilvin-training --dry-run=client -o yaml | kubectl apply -f -
echo "kilvin infra up:"
echo "  temporal grpc  localhost:7233   ui http://localhost:8080"
echo "  allocator      http://localhost:7070/healthz"
echo "  registry       localhost:5001"
echo "  kubeconfig     $KUBECONFIG"
