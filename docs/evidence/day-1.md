# Day 1 evidence — 2026-10-12

## Environment observed

| Check | Observed result |
|---|---|
| Git | 2.56.0.windows.1 |
| Docker CLI | 29.7.2, desktop-linux context |
| Docker engine | Unavailable: dockerDesktopLinuxEngine named pipe missing |
| kubectl | v1.36.1; embedded Kustomize v5.8.1 |
| Kubernetes contexts | None configured |
| Python | Installed Python 3.14.7 works by full path; PATH aliases fail in the restricted session |
| WSL | Ubuntu and docker-desktop installed as WSL2, both Stopped |
| Other cluster tools | kind, minikube and k3d not on PATH |
| GitHub | Public Hazaa-Sal/cloudtwin- created by owner; repository write access connected |

## Verification record

- Health behavior and local HTTP tests: 6 passed using Python 3.12.14 (bundled runtime). Four pure behavior tests also passed on installed Python 3.14.7. Local HTTP probes were initially blocked by sandbox socket permissions, then passed with approved localhost access; no assertions were weakened.
- `kubectl kustomize infra/kubernetes/overlays/primary`: passed.
- `kubectl kustomize infra/kubernetes/overlays/dr`: passed.
- All PowerShell scripts: parser validation passed.
- [GitHub Actions run 38220408808](https://github.com/Hazaa-Sal/cloudtwin-/actions/runs/38220408808): completed successfully for revision `6ef7551f51d9a49efeb0269ed787df8c7d8562a8`, including health tests, script/manifest validation and Docker image build on the hosted runner.
- Source review: credentials excluded from Git; existing secrets preserved; all mutations target docker-desktop and CloudTwin namespaces; no cloud resources created.

## Pending runtime evidence

Docker Desktop startup was attempted. Engine readiness was not observed. GUI launch approval timed out. Owner was asked to open Docker Desktop and enable Kubernetes.

The image build passed in GitHub Actions. A local image build, server-side manifest validation, live PostgreSQL query, PVC binding, and Kubernetes rollout remain unverified. Expected outputs in the runbook are illustrative.

Day 1 does not yet implement replication, backups, failover or measured RTO/RPO. Continue at runbook checkpoint 1 after the Docker engine and Kubernetes are Running.
