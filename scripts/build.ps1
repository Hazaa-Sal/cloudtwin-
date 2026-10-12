. "$PSScriptRoot/common.ps1"
Write-Host 'Checkpoint 2: build the Python API image in the existing local Docker engine.'
Invoke-Native docker @('--context=desktop-linux', 'build', '--tag', 'cloudtwin-api:day1', $RepoRoot)
Write-Host 'PASS: image built. Deploy first to primary; image visibility is verified by rollout.'
