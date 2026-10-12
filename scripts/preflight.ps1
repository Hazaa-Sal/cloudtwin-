. "$PSScriptRoot/common.ps1"
Write-Host 'Checkpoint 1: tool versions, Docker engine, Kubernetes nodes and storage.'
foreach ($name in @('git', 'docker', 'kubectl')) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "Missing tool: $name" }
}
Invoke-Native git @('--version')
Invoke-Native docker @('version')
Invoke-Native kubectl @('version', '--client')
Assert-LocalCluster
$classes = & kubectl --context=docker-desktop get storageclass -o json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read storage classes.' }
$defaults = @((ConvertFrom-Json ($classes -join "`n")).items | Where-Object {
    $annotations = $_.metadata.PSObject.Properties['annotations']
    if ($annotations) {
        $flag = $annotations.Value.PSObject.Properties['storageclass.kubernetes.io/is-default-class']
        $flag -and $flag.Value -eq 'true'
    }
})
if ($defaults.Count -ne 1) { throw 'Expected exactly one default StorageClass for local PVCs.' }
Write-Host 'PASS: engine reachable, nodes Ready, default storage available.'
