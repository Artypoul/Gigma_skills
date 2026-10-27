$ErrorActionPreference = 'SilentlyContinue'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

try {
    $offSwitch = if ($env:CODEX_FEATURE_HOOKS_OFF_PATH) { $env:CODEX_FEATURE_HOOKS_OFF_PATH } else { (Join-Path $HOME '.codex\feature-hooks-off') }
    if (Test-Path -LiteralPath $offSwitch) { exit 0 }

    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }

    $j = $raw | ConvertFrom-Json
    $sidCandidates = @(
        [string]$j.session_id,
        [string]$j.thread_id,
        [string]$j.threadId,
        [string]$j.run.threadId
    )
    $promptCandidates = @(
        [string]$j.prompt,
        [string]$j.user_message,
        [string]$j.message,
        [string]$j.input
    )
    $sid = ($sidCandidates | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    $prompt = ($promptCandidates | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    if (-not $sid -or -not $prompt) { exit 0 }

    $dir = if ($env:CODEX_FEATURE_HOOKS_DIR) { [IO.Path]::GetFullPath($env:CODEX_FEATURE_HOOKS_DIR) } else { (Join-Path $HOME '.codex\feature-hooks') }
    $safe = ($sid -replace '[^A-Za-z0-9._-]', '_')
    $pending = Join-Path $dir "$safe.pending"
    if (-not (Test-Path -LiteralPath $pending)) { exit 0 }

    $normalized = $prompt.ToLowerInvariant()
    $shouldStop = $normalized -match '(?i)(^|[^\p{L}\p{N}_])(стоп|оставь|не\s+туда|хватит|пауза|stop|pause)(?=$|[^\p{L}\p{N}_])'

    if (-not $shouldStop) { exit 0 }

    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $stopFlag = Join-Path $dir "$safe.stop"
    New-Item -ItemType File -Path $stopFlag -Force | Out-Null
} catch {
}

exit 0
