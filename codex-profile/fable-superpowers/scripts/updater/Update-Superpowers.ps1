param(
    [ValidateSet('run','check','recover')][string]$Action='run',
    [string]$CodexHome,
    [switch]$Retry
)
$ErrorActionPreference='Stop'
$taskProfileRoot=[Environment]::GetFolderPath('UserProfile')
$bundledPython=Join-Path $taskProfileRoot '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$taskPythonCandidates=@($bundledPython)
foreach ($taskPythonName in @('python','python3')) {
    $taskPythonCommand=Get-Command $taskPythonName -ErrorAction SilentlyContinue
    if ($taskPythonCommand -and $taskPythonCommand.Source -notlike '*WindowsApps*') { $taskPythonCandidates+=$taskPythonCommand.Source }
}
$taskPython=$null
foreach ($taskPythonCandidate in ($taskPythonCandidates | Select-Object -Unique)) {
    if ($taskPythonCandidate -and (Test-Path -LiteralPath $taskPythonCandidate -PathType Leaf)) {
        & $taskPythonCandidate -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' *> $null
        if ($LASTEXITCODE -eq 0) { $taskPython=$taskPythonCandidate; break }
    }
}
if (-not $taskPython) { throw 'Python 3.11 or newer is required; no interpreter was installed automatically.' }
$taskArguments=@('-B',(Join-Path $PSScriptRoot 'update.py'),$Action)
if ($CodexHome) { $taskArguments+=@('--home',[IO.Path]::GetFullPath($CodexHome)) }
if ($Retry) { $taskArguments+='--retry' }
& $taskPython @taskArguments
exit $LASTEXITCODE
