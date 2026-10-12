# CloudTwin delivery stages

1. Day 1: local prerequisites, repository, two namespace-isolated API/PostgreSQL stacks, persistent volumes, health probes, CI and evidence.
2. Backup/restore: seed timestamped records; pg_dump with integrity checks; restore to DR; prove record contents; keep dumps outside Git.
3. Recovery: explicit primary fencing, a single active writer, routing switch, failback runbook. A second independent writable DB is not a replica.
4. Automation: health monitor with consecutive-failure threshold and hysteresis; promote only after fencing and successful restore; never switch automatically on one failed probe.
5. Experiments: record fault-injection time, first successful recovered request, newest committed record and newest recovered record. RTO = recovery time minus outage start. RPO = latest committed timestamp minus latest recovered timestamp (also report missing IDs). Polling interval contributes timing uncertainty.
6. Separate local clusters to practise cluster loss. A single physical host still cannot prove host-loss or regional resilience.

All infrastructure remains local. No cloud accounts, paid endpoints, registries, or LoadBalancer services are required.
