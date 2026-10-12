#requires -Version 7.3
param(
    [Parameter(Mandatory)]
    [ValidateSet('setup', 'deploy-primary', 'deploy-dr', 'backup', 'demo', 'serve', 'stop', 'status', 'monitor')]
    [string]$Command,
    [string]$Backup
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$linuxRoot = & wsl -d Ubuntu --exec wslpath -a $root.Replace('\', '/')
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the repository path inside Ubuntu.' }
if ($Command -eq 'setup') {
    & wsl -d Ubuntu --cd $linuxRoot -- bash scripts/bootstrap-wsl.sh
} else {
    $arguments = @('-d', 'Ubuntu', '--cd', $linuxRoot, '--', 'python3', '-m', 'operations.lab', $Command)
    if ($Backup) { $arguments += @('--backup', $Backup) }
    & wsl @arguments
}
if ($LASTEXITCODE -ne 0) { throw "CloudTwin $Command failed. Resolve the error before continuing." }
