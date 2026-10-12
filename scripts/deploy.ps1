param([Parameter(Mandatory)][ValidateSet('primary', 'dr')][string]$Site)
. "$PSScriptRoot/common.ps1"
Assert-LocalCluster
$namespace = "cloudtwin-$Site"
$overlay = Join-Path $RepoRoot "infra/kubernetes/overlays/$Site"
Write-Host "Checkpoint 3 ($Site): namespace, generated database secret, PostgreSQL and API."
Invoke-Native kubectl @('--context=docker-desktop', 'apply', '-f', "$overlay/namespace.yaml")
$existing = & kubectl --context=docker-desktop -n $namespace get secret postgres-credentials --ignore-not-found -o name
if ($LASTEXITCODE -ne 0) { throw 'Secret lookup failed; refusing to replace credentials.' }
if (-not $existing) {
    # Feed a random credential through stdin: do not save it or print it to the terminal.
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $secret = @{
        apiVersion = 'v1'; kind = 'Secret'; type = 'Opaque'
        metadata = @{ name = 'postgres-credentials'; namespace = $namespace }
        data = @{ password = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([Convert]::ToBase64String($bytes))) }
    } | ConvertTo-Json -Depth 6 -Compress
    $secret | & kubectl --context=docker-desktop create -f -
    if ($LASTEXITCODE -ne 0) { throw 'Secret creation failed.' }
    $secret = $null
}
Invoke-Native kubectl @('--context=docker-desktop', 'apply', '-k', $overlay)
Invoke-Native kubectl @('--context=docker-desktop', '-n', $namespace, 'rollout', 'status', 'statefulset/postgres', '--timeout=240s')
Invoke-Native kubectl @('--context=docker-desktop', '-n', $namespace, 'rollout', 'status', 'deployment/api', '--timeout=180s')
& "$PSScriptRoot/verify.ps1" -Site $Site
