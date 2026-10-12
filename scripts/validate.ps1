param([string]$Python = 'python')
. "$PSScriptRoot/common.ps1"
Push-Location $RepoRoot
try {
    Invoke-Native $Python @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
    foreach ($site in @('primary', 'dr')) {
        $rendered = & kubectl kustomize "infra/kubernetes/overlays/$site"
        if ($LASTEXITCODE -ne 0 -or -not $rendered) { throw "Cannot render $site" }
        Write-Host "PASS: $site manifests render (offline; not server validation)."
    }
    Get-ChildItem $PSScriptRoot -Filter '*.ps1' | ForEach-Object {
        $tokens = $null; $parseErrors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$parseErrors)
        if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
    }
    Write-Host 'PASS: PowerShell syntax.'
} finally { Pop-Location }
