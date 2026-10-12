Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
function Invoke-Native {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" }
}
function Assert-LocalCluster {
    Invoke-Native kubectl @('--context=docker-desktop', '--request-timeout=15s', 'get', 'nodes')
    Invoke-Native kubectl @('--context=docker-desktop', 'wait', '--for=condition=Ready', 'nodes', '--all', '--timeout=60s')
}
