[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }),
    [string]$MarketplaceRoot,
    [switch]$AdoptMarketplace
)

$ErrorActionPreference = 'Stop'
$taskHome = [IO.Path]::GetFullPath($CodexHome)
$taskBundledPython = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$taskPythonCandidates = @($taskBundledPython)
foreach ($taskName in @('python', 'python3')) {
    $taskCommand = Get-Command $taskName -ErrorAction SilentlyContinue
    if ($taskCommand -and $taskCommand.Source -notlike '*WindowsApps*') { $taskPythonCandidates += $taskCommand.Source }
}
$taskPython = $null
foreach ($taskCandidate in ($taskPythonCandidates | Select-Object -Unique)) {
    if ($taskCandidate -and (Test-Path -LiteralPath $taskCandidate -PathType Leaf)) {
        & $taskCandidate -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' *> $null
        if ($LASTEXITCODE -eq 0) { $taskPython = $taskCandidate; break }
    }
}
if (-not $taskPython) { throw 'Python 3.11 or newer is required; no interpreter was installed automatically.' }

$taskAction = 'plan'
if (-not $WhatIfPreference) {
    if (-not $PSCmdlet.ShouldProcess($taskHome, 'Install and verify Fable 5 + Superpowers')) { return }
    $taskAction = 'install'
}
$taskArguments = @('-B', (Join-Path $PSScriptRoot 'bootstrap.py'), $taskAction, '--home', $taskHome)
if ($MarketplaceRoot) { $taskArguments += @('--marketplace-root', [IO.Path]::GetFullPath($MarketplaceRoot)) }
if ($AdoptMarketplace) { $taskArguments += '--adopt-marketplace' }
& $taskPython @taskArguments
exit $LASTEXITCODE
