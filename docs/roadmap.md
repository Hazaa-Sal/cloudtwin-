# CloudTwin delivery stages

1. Implemented foundation: local prerequisites, repository, two namespace-isolated API/PostgreSQL stacks, persistent volumes, health probes, CI and evidence.
2. Implemented backup/restore: timestamped sample records; pg_dump with integrity checks; transactional restore to DR; content verification; dumps outside Git.
3. Implemented recovery: explicit primary API/database fencing and gateway routing switch. Manual failback requirements documented; automated failback is future work.
4. Implemented automation: three consecutive failure threshold, reset after success; promote only after fencing and successful restore. One local controller at a time.
5. Implemented experiment: fault-injection to verified gateway recovery RTO; latest known committed versus recovered record RPO; missing IDs and content comparison. Check evidence for actual measurements.
6. Future: scheduled backup retention, restricted database application role, continuous replication, separate local clusters and broader failures. A single physical host cannot prove host-loss or regional resilience.

All infrastructure remains local. No cloud accounts, paid endpoints, registries, or LoadBalancer services are required.
