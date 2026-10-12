# Running CloudTwin on this machine

The working runtime is Ubuntu WSL2 + Docker Engine + a dedicated kind cluster named `cloudtwin`. Docker Desktop has a separate startup/socket failure. Do not mix the two Docker engines. CloudTwin uses a private, Git-ignored `.local/kubeconfig` and explicit `kind-cloudtwin` context. Desktop data is untouched.

From this repository in **PowerShell 7.3+**, run the commands below one at a time. The wrapper invokes Ubuntu and stops on error.

| Command | What it does | Expected checkpoint |
|---|---|---|
| `./scripts/cloudtwin.ps1 setup` | Checksums official kind/kubectl downloads, creates/reuses the dedicated cluster, builds/loads the API image | Ready node and image loaded |
| `./scripts/cloudtwin.ps1 deploy-primary` | Creates primary secret, API, PostgreSQL and PVC; waits and runs SQL/HTTP checks | Primary PASS, both pods 1/1, PVC Bound |
| `./scripts/cloudtwin.ps1 deploy-dr` | Creates the separate DR stack and verifies it | DR PASS, both pods 1/1, PVC Bound |
| `./scripts/cloudtwin.ps1 demo` | Creates sample records, backs them up, adds a later record, stops primary API, detects failure, fences primary, restores DR and switches gateway | Recovery report and PASS |
| `./scripts/cloudtwin.ps1 serve` | Serves the active site through a local gateway | Open http://127.0.0.1:8090/readyz |
| `./scripts/cloudtwin.ps1 status` | Prints active site and workloads/storage | After demo: DR active, primary pods stopped, both PVCs retained |

Only one controller command runs at a time; read-only `status` can run while serving. Stop `serve` with Ctrl+C before another modifying command. `setup` does not reset the lab. Re-running deployment after promotion is refused to avoid reviving the old primary accidentally. Keep an Ubuntu terminal or `serve` open while working: WSL can stop when its user sessions end, even though system services are enabled.

## Backup and automatic monitoring

`demo` is a real local recovery exercise. The gateway starts on primary, then serves DR only after three consecutive failed readiness checks, confirmed primary shutdown, successful restore and DR readiness. The monitor probes the primary Service from inside the DR API pod, so a broken localhost tunnel alone does not cause promotion. Checks are separated by two seconds; probe duration adds to this interval. DR is checked before fencing and after restore. The controller stops on ambiguous failures rather than promoting anyway.

The API is read-only. The demo writes timestamped sample rows through PostgreSQL. The archive contains only the lab's `cloudtwin_events` table; restoration replaces only that disposable table. The demo verifies every restored row against the pre-backup inventory. It deliberately leaves one post-backup record unrecovered so measured RPO is meaningful.

```powershell
./scripts/cloudtwin.ps1 backup
./scripts/cloudtwin.ps1 monitor -Backup 'backups/<printed-archive-name>.dump'
```

`backup` archives the active site's sample table and records SHA-256. It requires the table to exist. `monitor` is for primary-active operation after both stacks are ready; it runs up to 24 hours and serves the gateway. It requires a selected backup, and never automatically creates or silently selects one. After promotion it keeps serving DR until Ctrl+C. It is a local foreground controller, not a highly available operator or scheduled background service.

## Evidence and interpretation

- `artifacts/recovery-report.json`: measured RTO, RPO, missing record IDs and verified gateway response.
- `backups/*.dump` and companion JSON: binary PostgreSQL archive and integrity metadata; ignored by Git.
- RTO starts immediately before the injected scale-down request and ends at the first verified gateway response from DR. It includes failure detection, fencing and restore.
- RPO compares the newest known source record timestamp with the newest recovered timestamp. Missing IDs are also reported. These are sample workload measurements, not a service guarantee.
- Screenshot checkpoints: Ready node; primary and DR pods/PVCs; recovery report; browser JSON showing `site: dr`.

Both databases, backups and the controller share one physical computer. This demonstrates namespace/application recovery, not host-loss, regional resilience, continuous replication or point-in-time recovery. The controller requires a reachable Kubernetes control plane to prove fencing. It cannot safely promote during a control-plane outage.

## Failback and stopping

After a successful demo, keep the primary fenced. DR is authoritative. A failback implementation must back up DR, stop writes, restore primary, verify every record, fence DR and only then change routing. Automatic failback is intentionally not implemented.

Ctrl+C stops the gateway and its own tunnels; Kubernetes workloads continue. To pause the entire dedicated lab without deleting volumes, from Ubuntu at the repository root:

```bash
docker stop cloudtwin-control-plane
```

Resume with `docker start cloudtwin-control-plane`, wait for nodes Ready, then run `serve`. Do not delete the kind cluster or PVCs unless you intend to discard the lab's stored data. Do not use factory reset or Docker prune as troubleshooting steps.

## Runtime installation performed

Ubuntu's signed `docker.io` package was installed because the existing Ubuntu CLI was only a broken Desktop integration link. This installed Docker Engine, containerd and their dependencies inside Ubuntu. No cloud resources were created. A repository-local kind v0.33.0 and kubectl v1.36.4 were downloaded and verified; the pre-existing global kind v0.24.0 was left in place. The cluster node image is pinned by digest in the bootstrap script.

Sources: [kind quick start](https://kind.sigs.k8s.io/docs/user/quick-start/), [kind v0.33.0 release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0), [similar Docker Desktop startup failure](https://github.com/docker/desktop-feedback/issues/666).
