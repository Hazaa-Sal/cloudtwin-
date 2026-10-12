"""Local-only Kubernetes recovery lab. Uses only the dedicated kind-cloudtwin context."""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
STATE = LOCAL / 'state.json'
SITES = ('primary', 'dr')
PORTS = {'primary': 8081, 'dr': 8082}


def kubectl(*args, data=None, timeout=180):
    result = subprocess.run(
        [str(LOCAL / 'bin/kubectl'), '--kubeconfig', str(LOCAL / 'kubeconfig'),
         '--context', 'kind-cloudtwin', '--request-timeout=60s', *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout


def namespace(site):
    if site not in SITES:
        raise ValueError('Only CloudTwin primary and dr are allowed')
    return 'cloudtwin-' + site


def sql(site, statement):
    return kubectl('-n', namespace(site), 'exec', '-i', 'postgres-0', '--',
                   'psql', '-X', '-qAt', '-U', 'cloudtwin', '-d', 'cloudtwin',
                   '-v', 'ON_ERROR_STOP=1', data=statement.encode()).decode().strip()


def inventory(site):
    raw = sql(site, "SELECT coalesce(json_agg(row_to_json(t) ORDER BY id),'[]'::json) "
              "FROM (SELECT id, payload, committed_at FROM cloudtwin_events ORDER BY id) t;")
    return json.loads(raw)


def save_state(active):
    LOCAL.mkdir(exist_ok=True)
    temporary = LOCAL / 'state.tmp'
    temporary.write_text(json.dumps({'active': active}), encoding='utf-8')
    temporary.replace(STATE)


def active_site():
    if not STATE.exists():
        raise RuntimeError('Deploy the lab first')
    site = json.loads(STATE.read_text())['active']
    namespace(site)
    return site


def deploy(site):
    if STATE.exists() and active_site() == 'dr':
        raise RuntimeError('DR is active; refusing to restart a fenced primary. See failback runbook.')
    ns = namespace(site)
    overlay = ROOT / 'infra/kubernetes/overlays' / site
    kubectl('apply', '-f', str(overlay / 'namespace.yaml'))
    exists = kubectl('-n', ns, 'get', 'secret', 'postgres-credentials', '--ignore-not-found', '-o', 'name')
    if not exists.strip():
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
            'name': 'postgres-credentials', 'namespace': ns}, 'type': 'Opaque',
            'data': {'password': base64.b64encode(secrets.token_hex(32).encode()).decode()}}
        kubectl('create', '-f', '-', data=json.dumps(secret).encode())
    kubectl('apply', '-k', str(overlay))
    for workload in ('statefulset/postgres', 'deployment/api'):
        print(kubectl('-n', ns, 'rollout', 'status', workload, '--timeout=240s', timeout=270).decode(), flush=True)
    print(kubectl('-n', ns, 'get', 'pods,svc,pvc').decode(), flush=True)
    phase = kubectl('-n', ns, 'get', 'pvc', 'data-postgres-0', '-o', 'jsonpath={.status.phase}').decode()
    if phase != 'Bound' or sql(site, 'SELECT 1;') != '1':
        raise RuntimeError('Storage or SQL verification failed')
    probe = 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://api:8080/readyz",timeout=6)); print(d); assert d["status"]=="ready" and d["site"]=="' + site + '"'
    print(kubectl('-n', ns, 'exec', 'deployment/api', '--', 'python', '-c', probe).decode(), flush=True)
    if not STATE.exists():
        save_state('primary')
    print(f'PASS: {site} storage, SQL and service readiness', flush=True)


def backup():
    site = active_site()
    data = kubectl('-n', namespace(site), 'exec', 'postgres-0', '--', 'pg_dump',
                   '-U', 'cloudtwin', '-d', 'cloudtwin', '-Fc', '--no-owner',
                   '--no-acl', '--table=public.cloudtwin_events')
    if not data.startswith(b'PGDMP'):
        raise RuntimeError('Not a PostgreSQL custom archive')
    directory = ROOT / 'backups'
    directory.mkdir(exist_ok=True)
    path = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dump')
    path.write_bytes(data)
    metadata = {'sha256': hashlib.sha256(data).hexdigest(), 'source': site,
                'created_at': datetime.now(timezone.utc).isoformat()}
    path.with_suffix('.json').write_text(json.dumps(metadata, indent=2))
    print(f'PASS: backup {path.name}, {len(data)} bytes, SHA-256 recorded', flush=True)
    return path


def verified_archive(path):
    path = Path(path).resolve()
    if path.parent != (ROOT / 'backups').resolve():
        raise ValueError('Only archives in this repository backups directory are accepted')
    data = path.read_bytes()
    metadata = json.loads(path.with_suffix('.json').read_text())
    if hashlib.sha256(data).hexdigest() != metadata['sha256'] or not data.startswith(b'PGDMP'):
        raise ValueError('Backup integrity check failed')
    return data


def restore_dr(path):
    data = verified_archive(path)
    # This lab archive contains only the explicitly disposable cloudtwin_events table.
    kubectl('-n', namespace('dr'), 'exec', '-i', 'postgres-0', '--', 'pg_restore',
            '-U', 'cloudtwin', '-d', 'cloudtwin', '--clean', '--if-exists',
            '--no-owner', '--no-acl', '--exit-on-error', '--single-transaction', data=data)
    return inventory('dr')


def fetch(url):
    # Never route localhost probes through host proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as result:
        return json.load(result)


def ready(site):
    try:
        data = fetch(f'http://127.0.0.1:{PORTS[site]}/readyz')
        return data.get('status') == 'ready' and data.get('site') == site
    except (OSError, ValueError):
        return False


def primary_service_ready():
    """Probe in-cluster Service routing so a lost local tunnel is not an outage."""
    probe = ('import json,urllib.request; '
             'd=json.load(urllib.request.urlopen("http://api.cloudtwin-primary.svc.cluster.local:8080/readyz",timeout=3)); '
             'assert d.get("status")=="ready" and d.get("site")=="primary"')
    try:
        kubectl('-n', namespace('dr'), 'exec', 'deployment/api', '--', 'python', '-c', probe, timeout=15)
        return True
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


@contextmanager
def forwards(sites=SITES):
    processes = []
    handles = []
    try:
        for site in sites:
            log = open(LOCAL / f'forward-{site}.log', 'ab')
            handles.append(log)
            process = subprocess.Popen([str(LOCAL / 'bin/kubectl'), '--kubeconfig', str(LOCAL / 'kubeconfig'),
                '--context', 'kind-cloudtwin', '-n', namespace(site), 'port-forward', '--address=127.0.0.1',
                'svc/api', f'{PORTS[site]}:8080'], stdout=log, stderr=log)
            processes.append(process)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Port-forward exited; inspect .local/forward-*.log')
            if all(ready(site) for site in sites):
                yield
                return
            time.sleep(1)
        raise RuntimeError('Port-forwards did not become ready')
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in handles:
            log.close()


class Gateway(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/', '/healthz', '/readyz'):
            self.send_error(404)
            return
        try:
            payload = fetch(f'http://127.0.0.1:{PORTS[active_site()]}{self.path}')
            status = 200
        except (OSError, ValueError, RuntimeError):
            payload, status = {'status': 'unavailable'}, 503
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def gateway():
    server = ThreadingHTTPServer(('127.0.0.1', 8090), Gateway)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def fence_primary():
    ns = namespace('primary')
    kubectl('-n', ns, 'scale', 'deployment/api', 'statefulset/postgres', '--replicas=0')
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        pods = json.loads(kubectl('-n', ns, 'get', 'pods', '-o', 'json'))['items']
        if not pods:
            return
        time.sleep(1)
    raise RuntimeError('Cannot prove primary is fenced; refusing DR promotion')


def failover(path):
    if active_site() != 'primary':
        raise RuntimeError('Failover requires primary active')
    verified_archive(path)  # Fail before fencing if backup is damaged.
    if not ready('dr'):
        raise RuntimeError('DR unavailable before fencing; refusing recovery')
    fence_primary()
    rows = restore_dr(path)
    if not ready('dr'):
        raise RuntimeError('DR not ready after restore; routing remains unchanged')
    save_state('dr')
    return rows


def wait_and_failover(path, interval=2, threshold=3, timeout=120):
    failures = 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        failures = 0 if primary_service_ready() else failures + 1
        if failures >= threshold:
            print(f'Primary failed {threshold} consecutive checks; fencing then restoring DR.', flush=True)
            return failover(path)
        time.sleep(interval)
    raise TimeoutError('No sustained primary failure detected')


def metrics(before, recovered, rto):
    if not before or not recovered:
        raise ValueError('RPO requires timestamped source and recovered records')
    old = {row['id']: row for row in before}
    new = {row['id']: row for row in recovered}
    for key in new:
        if key not in old or new[key] != old[key]:
            raise ValueError('Recovered record contents do not match source')
    latest_source = max(datetime.fromisoformat(r['committed_at']) for r in before)
    latest_recovered = max(datetime.fromisoformat(r['committed_at']) for r in recovered)
    return {'rto_seconds': round(rto, 3),
            'rpo_seconds': max(0, (latest_source - latest_recovered).total_seconds()),
            'source_records': len(before), 'recovered_records': len(recovered),
            'missing_ids': sorted(old.keys() - new.keys()), 'poll_interval_seconds': 2,
            'failure_threshold': 3}


def demo():
    if active_site() != 'primary':
        raise RuntimeError('Demo requires primary active; repeated failover is not a safe reset')
    sql('primary', 'CREATE TABLE IF NOT EXISTS cloudtwin_events (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, payload text NOT NULL, committed_at timestamptz NOT NULL DEFAULT clock_timestamp());')
    sql('primary', "INSERT INTO cloudtwin_events(payload) VALUES ('protected-record-a'),('protected-record-b');")
    snapshot = inventory('primary')
    path = backup()
    time.sleep(2)
    sql('primary', "INSERT INTO cloudtwin_events(payload) VALUES ('after-backup-record');")
    before = inventory('primary')
    with forwards(), gateway():
        assert fetch('http://127.0.0.1:8090/readyz')['site'] == 'primary'
        fault_at = time.monotonic()
        fault_utc = datetime.now(timezone.utc).isoformat()
        kubectl('-n', namespace('primary'), 'scale', 'deployment/api', '--replicas=0')
        recovered = wait_and_failover(path)
        result = fetch('http://127.0.0.1:8090/readyz')
        if result.get('site') != 'dr' or recovered != snapshot:
            raise RuntimeError('Recovered contents or gateway route failed verification')
        report = metrics(before, recovered, time.monotonic() - fault_at)
        report.update({'fault_at': fault_utc, 'active_site': 'dr', 'backup': path.name,
                       'gateway_verified': result, 'recovered_contents_match_backup': True,
                       'scope': 'API outage, fenced primary DB, same-host namespace recovery'})
        output = ROOT / 'artifacts/recovery-report.json'
        output.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
    print('PASS: recovery experiment. Primary remains fenced; DR active. Use serve to open the gateway.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('deploy-primary', 'deploy-dr', 'backup', 'demo', 'serve', 'stop', 'status', 'monitor'))
    parser.add_argument('--backup', type=Path, help='Verified archive to restore when monitoring detects failure')
    args = parser.parse_args()
    if args.command.startswith('deploy-'):
        deploy(args.command.split('-')[1])
    elif args.command == 'backup':
        backup()
    elif args.command == 'demo':
        demo()
    elif args.command == 'status':
        print(json.dumps({'active': active_site()}))
        for site in SITES:
            print(kubectl('-n', namespace(site), 'get', 'pods,svc,pvc').decode())
    elif args.command == 'serve':
        pidfile = LOCAL / 'server.pid'
        pidfile.write_text(str(os.getpid()))
        try:
            with forwards((active_site(),)), gateway():
                print('Gateway listening at http://127.0.0.1:8090/readyz', flush=True)
                threading.Event().wait()
        finally:
            pidfile.unlink(missing_ok=True)
    elif args.command == 'stop':
        pidfile = LOCAL / 'server.pid'
        if not pidfile.exists():
            print('No managed gateway is running.')
            return
        pid = int(pidfile.read_text())
        process = Path('/proc') / str(pid)
        command = (process / 'cmdline').read_bytes().split(b'\0')
        if b'operations.lab' not in command or b'serve' not in command or (process / 'cwd').resolve() != ROOT:
            raise RuntimeError('Recorded PID does not belong to this CloudTwin gateway; refusing to stop it')
        os.kill(pid, signal.SIGTERM)
        print('Graceful gateway stop requested. Kubernetes data and workloads are retained.')
    elif args.command == 'monitor':
        if not args.backup:
            parser.error('monitor requires --backup')
        verified_archive(args.backup)
        with forwards(), gateway():
            wait_and_failover(args.backup, timeout=86400)
            print('DR active; gateway remains available until Ctrl+C.', flush=True)
            threading.Event().wait()


if __name__ == '__main__':
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    if len(sys.argv) > 1 and sys.argv[1] in ('status', 'stop'):
        main()
        raise SystemExit(0)
    # WSL/Linux: one controller at a time, released even after a process crash.
    import fcntl
    LOCAL.mkdir(exist_ok=True)
    with open(LOCAL / 'controller.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another CloudTwin operation is running. Stop it before starting another.')
        main()
