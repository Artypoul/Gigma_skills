$ErrorActionPreference = 'SilentlyContinue'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

function Get-FeatureHooksDir {
    if ($env:CODEX_FEATURE_HOOKS_DIR) { return [IO.Path]::GetFullPath($env:CODEX_FEATURE_HOOKS_DIR) }
    (Join-Path $HOME '.codex\feature-hooks')
}

function Get-QualityState {
    param([Parameter(Mandatory)][string]$SessionId)
    $pointer = if ($env:FIRST_PASS_QUALITY_POINTER) { $env:FIRST_PASS_QUALITY_POINTER } else { Join-Path $HOME '.codex\first-pass-quality-pointer.json' }
    if (-not (Test-Path -LiteralPath $pointer)) { return $null }
    try {
        $root = [string]((Get-Content -LiteralPath $pointer -Raw | ConvertFrom-Json).dataRoot)
        if (-not $root) { return $null }
        $safe = [regex]::Replace($SessionId, '[^A-Za-z0-9._-]', '_')
        $path = Join-Path (Join-Path $root 'sessions') ($safe + '.json')
        if (-not (Test-Path -LiteralPath $path)) { return $null }
        Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    } catch { $null }
}

function Test-ToolSucceeded {
    param($Response)
    if ($null -eq $Response) { return $false }
    foreach ($name in @('exit_code', 'exitCode')) {
        $property = $Response.PSObject.Properties[$name]
        if ($property) { return ([int]$property.Value -eq 0) }
    }
    $success = $Response.PSObject.Properties['success']
    if ($success) { return [bool]$success.Value }
    $isError = $Response.PSObject.Properties['is_error']
    if ($isError) { return -not [bool]$isError.Value }
    if ($Response -is [string] -and $Response -match '(?i)Exit\s+code:\s*(-?\d+)') { return ([int]$Matches[1] -eq 0) }
    $false
}

function Test-FeatureFallbackBranch {
    param([string]$Cwd)
    if (-not $Cwd -or -not (Test-Path -LiteralPath $Cwd)) { return $false }
    try {
        $branch = (& git -C $Cwd branch --show-current 2>$null | Select-Object -First 1)
        $LASTEXITCODE -eq 0 -and [string]$branch -match '^(?i)(feature|feat)/'
    } catch { $false }
}

try {
    $offSwitch = if ($env:CODEX_FEATURE_HOOKS_OFF_PATH) { $env:CODEX_FEATURE_HOOKS_OFF_PATH } else { (Join-Path $HOME '.codex\feature-hooks-off') }
    if (Test-Path -LiteralPath $offSwitch) { exit 0 }

    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }

    $j = $raw | ConvertFrom-Json
    if (-not (Test-ToolSucceeded $j.tool_response)) { exit 0 }
    $cmdCandidates = @(
        [string]$j.tool_input.command,
        [string]$j.tool_input.arguments.command,
        [string]$j.arguments.command,
        [string]$j.command
    )
    $sidCandidates = @(
        [string]$j.session_id,
        [string]$j.thread_id,
        [string]$j.threadId,
        [string]$j.run.threadId
    )
    $cwdCandidates = @([string]$j.cwd, [string]$j.tool_input.workdir, [string]$j.tool_input.cwd)
    $cmd = ($cmdCandidates | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    $sid = ($sidCandidates | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    $cwd = ($cwdCandidates | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    if (-not $cmd -or -not $sid) { exit 0 }

    if (($cmd -notmatch '(^|\s)git\s+.*\bpush\b' -and $cmd -notmatch '(^|\s)gh\s+pr\s+create\b') -or $cmd -match '(?i)--dry-run\b') {
        exit 0
    }

    $qualityState = Get-QualityState -SessionId $sid
    if ($qualityState) {
        $workflow = [string]$qualityState.task.workflowId
        if ($workflow -notmatch '(?i)(^|[:/>,+\s-])feature($|[:/>,+\s-])' -or [string]$qualityState.status -notin @('active')) { exit 0 }
    } elseif (-not (Test-FeatureFallbackBranch -Cwd $cwd)) {
        exit 0
    }

    $dir = Get-FeatureHooksDir
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $safe = ($sid -replace '[^A-Za-z0-9._-]', '_')
    $pending = Join-Path $dir "$safe.pending"
    $blocks = Join-Path $dir "$safe.blocks"
    $stopFlag = Join-Path $dir "$safe.stop"

    Set-Content -LiteralPath $pending -Value $cmd -Encoding UTF8
    Set-Content -LiteralPath $blocks -Value '0' -Encoding UTF8
    Remove-Item -LiteralPath $stopFlag -Force -ErrorAction SilentlyContinue
} catch {
}

exit 0
