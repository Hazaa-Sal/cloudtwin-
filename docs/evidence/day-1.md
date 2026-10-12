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

## Initial Desktop blocker — resolved for CloudTwin through WSL

Docker Desktop startup was attempted. Engine readiness was not observed. GUI launch approval timed out. Owner was asked to open Docker Desktop and enable Kubernetes.

Docker Desktop logs identified a startup failure while accessing `sailor-ingest.sock`. CloudTwin now runs on Ubuntu WSL2 with Ubuntu's Docker Engine 29.1.3, repository-local kind v0.33.0, kubectl v1.36.4 and a digest-pinned Kubernetes v1.36.4 node. The Desktop installation and its stored data were preserved. A temporary WSL session keeper was used after idle-session shutdowns interrupted initial deployment.

## Live local verification completed

- Dedicated `cloudtwin-control-plane` node Ready, default `standard` StorageClass available.
- API image built locally and loaded into kind.
- Primary and DR each reached two pods `1/1 Running`, one 1 GiB PVC `Bound`, successful SQL and Service readiness.
- PostgreSQL custom archive produced with SHA-256 metadata; no backups or secrets committed.
- Controlled primary API scale-down triggered automatic recovery after three consecutive failed checks.
- Primary API/database were stopped before restore and promotion; primary PVC retained.
- DR restored both protected records exactly. The third record, deliberately committed after backup, was identified as lost.
- Gateway `/readyz` returned `{"status":"ready","site":"dr","database":"reachable"}` after recovery.
- Local experiment: **RTO 37.044 seconds; RPO 3.603325 seconds; 3 source records, 2 recovered, missing ID 3**.
- Fault injected at **2026-10-12 12:13:16 Asia/Dubai** (08:13:16 UTC). The full local report is `artifacts/recovery-report.json` (Git-ignored).

The local experiment preceded a review improvement: primary monitoring now probes the Kubernetes Service from DR rather than relying solely on a localhost tunnel. The final version is also exercised by the end-to-end GitHub Actions job. These measurements are one synthetic same-host run, not an availability guarantee. Continuous replication, host-loss resilience and automatic failback are not implemented.

## End-to-end CI and final checks

- [Full recovery CI run 38222512467](https://github.com/Hazaa-Sal/cloudtwin-/actions/runs/38222512467) passed on revision `ff6e43f1ad88bab45b5ed1d6c1e3428337e03ac0`: tests, script parsing, manifest rendering, fresh kind cluster, image build/load, primary/DR verification and the complete automatic recovery experiment with the improved Service probe. Recovery JSON is uploaded as a workflow artifact.
- 13 local tests passed after the gateway lifecycle addition; both overlays render and all PowerShell scripts parse.
- Windows localhost request returned DR ready with database reachable. Managed gateway stop was exercised successfully; it shuts down its own port-forward and retains the Kubernetes workloads/data.
