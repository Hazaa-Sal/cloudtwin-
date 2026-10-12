# Day 1: two local Kubernetes environments

Run from the repository root in PowerShell 7.3 or newer (for reliable native-command argument quoting). Read the explanation and compare the expected output after each command. Stop on failure.

## 1. Start the installed runtime

Open Docker Desktop. Wait for the engine to run. Enable/create the Kubernetes cluster in Docker Desktop's Kubernetes view or Settings > Kubernetes (wording varies by version). Keep it local; do not reset any existing cluster. For the simplest shared-image setup, use the single-node kubeadm provisioner if offered. Docker Desktop's kind provisioner may require containerd image-store configuration for local-image visibility.

```powershell
docker version
kubectl config get-contexts
kubectl --context=docker-desktop get nodes
```

`docker version` must show both Client and Server. The context list must contain `docker-desktop`; the node must be `Ready`. A missing pipe means the Docker engine is unavailable. A missing context means Kubernetes has not been configured. Neither indicates an application defect.

```powershell
./scripts/preflight.ps1
```

Checks installed commands, engine access, Ready nodes and exactly one default StorageClass. Expect `PASS: engine reachable, nodes Ready, default storage available.` Screenshot opportunity: Docker Desktop Kubernetes Running plus the Ready node output.

## 2. Validate and build

```powershell
./scripts/validate.ps1
```

Runs health tests, renders both Kustomize overlays and parses the PowerShell scripts. Expected: tests `OK`, two manifest PASS messages and PowerShell syntax PASS. This is offline validation, not proof of a running cluster. If the Windows Python alias fails, supply your installed interpreter:

```powershell
./scripts/validate.ps1 -Python "$env:LOCALAPPDATA/Python/pythoncore-3.14-64/python.exe"
```

```powershell
./scripts/build.ps1
```

Builds `cloudtwin-api:day1` on the `desktop-linux` Docker engine. The image contains the API and PostgreSQL client library, runs as a non-root user and needs no registry upload. Expect a successful build and a PASS message.

## 3. Deploy and verify primary first

```powershell
./scripts/deploy.ps1 -Site primary
```

Creates `cloudtwin-primary`, generates a random password in a Kubernetes Secret if absent, applies the shared resources with primary configuration, and waits for both workloads. Existing secrets are preserved. Kubernetes Secrets are not encrypted merely because they are base64 encoded; use this only as a local lab.

The script then checks the PVC is Bound, runs `SELECT current_database(), 1 AS sql_ok`, and requests `/readyz` both directly and through Service DNS. Expect `cloudtwin`, `sql_ok = 1`, and JSON with `status: ready`, `site: primary`, `database: reachable`.

If image loading fails (`ErrImageNeverPull`), stop. Inspect your Docker Desktop provisioner and containerd image-store setting; do not change the image to a remote registry or claim deployment succeeded. Build on the same engine used by the local cluster, or explicitly load the image into an already-installed local cluster before proceeding.

## 4. Deploy and verify DR

```powershell
./scripts/deploy.ps1 -Site dr
```

Repeats the same verified deployment in `cloudtwin-dr`, with a separate secret and volume. Expect `site: dr`. This starts an independent database, not a replica. Do not report a successful failover yet.

## 5. View both APIs

In two separate PowerShell windows, from the repository root:

```powershell
kubectl --context=docker-desktop -n cloudtwin-primary port-forward --address=127.0.0.1 svc/api 8081:8080
```

```powershell
kubectl --context=docker-desktop -n cloudtwin-dr port-forward --address=127.0.0.1 svc/api 8082:8080
```

These temporarily expose the internal services only on localhost. Expect `Forwarding from 127.0.0.1:8081 -> 8080` and the equivalent for 8082. Leave the windows running; Ctrl+C stops a tunnel without deleting workloads.

Open http://127.0.0.1:8081/readyz and http://127.0.0.1:8082/readyz. Expected output (illustrative, not captured runtime evidence):

```json
{"status": "ready", "site": "primary", "database": "reachable"}
```

```json
{"status": "ready", "site": "dr", "database": "reachable"}
```

Screenshot opportunity: both responses plus `get pods,services,pvc` for each namespace. Never screenshot Secret contents.

## Troubleshooting and stopping

```powershell
kubectl --context=docker-desktop -n cloudtwin-primary get pods,services,pvc
kubectl --context=docker-desktop -n cloudtwin-primary get events --sort-by=.lastTimestamp
kubectl --context=docker-desktop -n cloudtwin-primary logs deployment/api --tail=50
```

These show workload/storage state, scheduling/image errors and recent API logs. Substitute `cloudtwin-dr` for the other site. Pending PVCs usually need a working default storage provisioner. Do not delete a PVC to fix a password mismatch: preserve its original Secret and investigate.

To pause just this lab without deleting stored data, run the following once for each namespace (replace the namespace for DR):

```powershell
kubectl --context=docker-desktop -n cloudtwin-primary scale deployment/api statefulset/postgres --replicas=0
```

Re-running the site's deployment script restores replicas to one. Namespace/PVC deletion destroys lab data and is intentionally not part of the normal runbook.

## References

- [Docker Desktop Kubernetes](https://docs.docker.com/desktop/use-desktop/kubernetes/)
- [StatefulSets and persistent storage](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Startup, liveness and readiness probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/)
