# Troubleshooting Colima For Kilvin

The Kilvin live path depends on Docker, compose, a local registry, k3s, and host-side Python tools. On macOS, most failures are environment failures rather than workflow bugs.

## Homebrew PATH

If `colima` cannot find `limactl`, or Docker tools differ between shells:

```bash
export PATH=/opt/homebrew/bin:$PATH
```

Then check:

```bash
docker context show
docker info --format '{{.OperatingSystem}} | {{.Architecture}} | CgroupDriver={{.CgroupDriver}}'
```

## Docker Context And Architecture

Kilvin's trainer and infra images are exercised as `linux/amd64`.

```bash
docker context use colima
docker run --rm --platform linux/amd64 alpine:3.20 uname -m
```

Expected:

```text
x86_64
```

Start Colima with enough resources:

```bash
colima start --runtime docker --arch x86_64 --cpu 4 --memory 8 --disk 50
```

Use a larger disk for repeated large image builds.

## Docker Socket Permissions

If a command fails with:

```text
permission denied while trying to connect to the docker API
```

run it from a shell that can reach the Colima Docker socket, or rerun through the approved escalated command path. The workflow worker must be able to call Docker.

## Colima DNS And Python Packages

If macOS can resolve package hosts but containers get `NXDOMAIN`, Colima's resolver is not seeing the same network path.

Common failing hosts:

```text
pypi.org
files.pythonhosted.org
download.pytorch.org
```

Use a host-local proxy and expose it inside Colima:

```bash
python3 /path/to/http_connect_proxy.py --host 127.0.0.1 --port 3128
ssh -F ~/.colima/ssh_config -fN -R 127.0.0.1:3128:127.0.0.1:3128 colima
```

Then pass proxy values explicitly to Docker builds:

```bash
docker compose build \
  --build-arg HTTP_PROXY=http://host.lima.internal:3128 \
  --build-arg HTTPS_PROXY=http://host.lima.internal:3128 \
  --build-arg http_proxy=http://host.lima.internal:3128 \
  --build-arg https_proxy=http://host.lima.internal:3128 \
  allocator
```

Set localhost bypasses for host-side checks:

```bash
export NO_PROXY=localhost,127.0.0.1,::1
export no_proxy=localhost,127.0.0.1,::1
```

## k3s Registry Mirror

k3s pulls `localhost:5001/...` images through the compose registry mirror configured in:

```text
kilvin-py/infra/k3s/registries.yaml
```

If Jobs fail with image pull errors:

```bash
docker compose -f kilvin-py/infra/docker-compose.yml ps registry k3s
kubectl --kubeconfig kilvin-py/infra/.kubeconfig/kubeconfig.yaml -n kilvin-training describe pods
```

Check that `concretize_dependencies/out.yaml` contains the digest-pinned image reference the Job used.

## First Response

When in doubt:

```bash
make kilvin-doctor
```

Fix the first `FAIL` row before chasing deeper symptoms.
