param([Parameter(Mandatory)][ValidateSet('primary', 'dr')][string]$Site)
. "$PSScriptRoot/common.ps1"
$namespace = "cloudtwin-$Site"
Write-Host "Checkpoint 4 ($Site): storage, SQL and HTTP readiness."
Invoke-Native kubectl @('--context=docker-desktop', '-n', $namespace, 'get', 'pods,services,pvc')
$pvc = & kubectl --context=docker-desktop -n $namespace get pvc data-postgres-0 -o jsonpath='{.status.phase}'
if ($LASTEXITCODE -ne 0 -or $pvc -ne 'Bound') { throw 'Database PVC is not Bound.' }
Invoke-Native kubectl @('--context=docker-desktop', '-n', $namespace, 'exec', 'postgres-0', '--', 'psql', '-U', 'cloudtwin', '-d', 'cloudtwin', '-v', 'ON_ERROR_STOP=1', '-c', 'SELECT current_database(), 1 AS sql_ok;')
$probe = 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://127.0.0.1:8080/readyz",timeout=6)); print(json.dumps(d)); assert d["status"]=="ready" and d["site"]=="' + $Site + '"'
Invoke-Native kubectl @('--context=docker-desktop', '-n', $namespace, 'exec', 'deployment/api', '--', 'python', '-c', $probe)
# Also exercise Service DNS/routing, rather than only the pod loopback endpoint.
$serviceProbe = $probe.Replace('127.0.0.1', 'api')
Invoke-Native kubectl @('--context=docker-desktop', '-n', $namespace, 'exec', 'deployment/api', '--', 'python', '-c', $serviceProbe)
Write-Host "PASS: $Site SQL, pod readiness, Service routing and persistent storage."
