# CloudTwin

Local-first disaster-recovery engineering lab. Portfolio project two, following CloudPilot.

**Day 1 foundation:** Python HTTP API, PostgreSQL, Docker image, primary and DR Kubernetes namespaces, persistent volumes, health probes, staged PowerShell scripts, and GitHub Actions validation.

**Not yet implemented:** database replication, backup/restore, automated failover, failure injection, or measured RTO/RPO. See [roadmap](docs/roadmap.md). Two independent databases are not a synchronized DR system.

```text
Your Windows laptop / Docker Desktop Kubernetes
  cloudtwin-primary                 cloudtwin-dr
    api -> postgres                   api -> postgres
             |                                 |
           1 GiB PVC                          1 GiB PVC
```

Both environments share one host and cluster. This lab cannot survive loss of that host. PostgreSQL uses a database-owner account for this initial isolated lab; add a restricted application role before adding application writes. Secrets are generated at deployment and never committed. Services remain internal; browser access uses localhost port-forwarding.

## Start here

Follow the [Day 1 runbook](docs/runbooks/day-1.md), one checkpoint at a time. Each script stops on failed checks. [Verification evidence](docs/evidence/day-1.md) distinguishes completed checks from blocked runtime checks.

```powershell
./scripts/preflight.ps1
./scripts/validate.ps1
./scripts/build.ps1
./scripts/deploy.ps1 -Site primary
./scripts/deploy.ps1 -Site dr
```

Do not advance to the next command if the current checkpoint fails.

## Repository layout

```text
app/                         Python HTTP service
tests/                       Health behavior tests
infra/kubernetes/base/       Shared API, database and services
infra/kubernetes/overlays/   Primary and DR namespaces/configuration
scripts/                     Preflight, build, deployment and verification
docs/runbooks/               Explained commands and troubleshooting
docs/evidence/               Sanitized verification results
experiments/                 Recovery experiments (planned)
backups/                     Ignored local backup output
artifacts/                   Ignored local reports and screenshots
.github/workflows/           CI validation and image build
```

## Cost boundaries

No cloud resources or paid services are provisioned. Docker Desktop is already installed; its license eligibility depends on your usage. The public repository uses standard GitHub-hosted CI; do not enable paid runners or services. Internet downloads, local disk, CPU and memory are required. Image base tags receive updates; capture image digests with each experiment for reproducibility.
