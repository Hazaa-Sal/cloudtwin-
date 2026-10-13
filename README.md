# CloudTwin

Local-first disaster-recovery engineering lab. Portfolio project two, following CloudPilot.

**Implemented:** Python HTTP API, PostgreSQL, Docker image, primary and DR Kubernetes namespaces, persistent volumes, health probes, backup/restore, controlled failure simulation, automatic failover with primary fencing, RTO/RPO measurements, and GitHub Actions validation.

Recovery uses a selected PostgreSQL backup, not continuous replication. The controller requires a reachable Kubernetes control plane. See [verification evidence](docs/evidence/day-1.md) for executed checks and remaining limits.

```text
Your Windows laptop / Ubuntu WSL2 / Docker Engine / kind
  localhost gateway :8090 -> active API
  cloudtwin-primary                 cloudtwin-dr
    api -> postgres                   api -> postgres
             |                                 |
           1 GiB PVC                          1 GiB PVC
```

Both environments share one host and cluster. This lab cannot survive loss of that host. PostgreSQL uses a database-owner account for this initial isolated lab; add a restricted application role before adding application writes. Secrets are generated at deployment and never committed. Services remain internal; browser access uses localhost port-forwarding.

## Start here

**Already deployed?** Use `./scripts/cloudtwin.ps1 resume` after restarting your computer. This starts the existing lab and gateway while preserving the active site and stored records. Do not repeat the deployment/demo sequence after failover.

Follow the [working WSL recovery runbook](docs/runbooks/wsl-recovery.md), one checkpoint at a time. Docker Desktop on this machine fails during startup, so the working path uses Ubuntu Docker Engine and kind. The [Desktop runbook](docs/runbooks/day-1.md) remains an alternative for a healthy Desktop installation.

```powershell
./scripts/cloudtwin.ps1 setup
./scripts/cloudtwin.ps1 deploy-primary
./scripts/cloudtwin.ps1 deploy-dr
./scripts/cloudtwin.ps1 demo
./scripts/cloudtwin.ps1 serve
```

Do not advance if a checkpoint fails. After the demo, primary remains fenced and DR is active; do not redeploy primary. `serve` opens the active site at http://127.0.0.1:8090/readyz and keeps the WSL session active. Stop it with Ctrl+C or `./scripts/cloudtwin.ps1 stop`. This is a read-only HTTP application with synthetic SQL writes for recovery experiments.

## Repository layout

```text
app/                         Python HTTP service
operations/                  Backup, recovery controller, gateway and measurements
tests/                       Health behavior tests
infra/kubernetes/base/       Shared API, database and services
infra/kubernetes/overlays/   Primary and DR namespaces/configuration
scripts/                     Preflight, build, deployment and verification
docs/runbooks/               Explained commands and troubleshooting
docs/evidence/               Sanitized verification results
experiments/                 Recovery experiment notes
backups/                     Ignored local backup output
artifacts/                   Ignored local reports and screenshots
.github/workflows/           CI validation and image build
```

## Cost boundaries

No cloud resources or paid services are provisioned. The local runtime is Docker Engine inside the existing Ubuntu WSL2 installation. The public repository uses standard GitHub-hosted CI; do not enable paid runners or services. Internet downloads, local disk, CPU and memory are required. The Kubernetes node image is digest-pinned; application/database base tags receive updates, so capture their digests with experiments.
