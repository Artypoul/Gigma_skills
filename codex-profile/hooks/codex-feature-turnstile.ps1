$ErrorActionPreference = 'SilentlyContinue'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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

function Remove-SessionMarkers {
    param([Parameter(Mandatory)][string]$Directory, [Parameter(Mandatory)][string]$SafeId)
    foreach ($suffix in @('pending', 'blocks', 'stop')) {
        Remove-Item -LiteralPath (Join-Path $Directory "$SafeId.$suffix") -Force -ErrorAction SilentlyContinue
    }
}

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
    $sid = ($sidCandidates | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    if (-not $sid) { exit 0 }

    $dir = Get-FeatureHooksDir
    $safe = ($sid -replace '[^A-Za-z0-9._-]', '_')
    $pending = Join-Path $dir "$safe.pending"
    $stopFlag = Join-Path $dir "$safe.stop"
    if (Test-Path -LiteralPath $stopFlag) { exit 0 }
    if (-not (Test-Path -LiteralPath $pending)) { exit 0 }

    $qualityState = Get-QualityState -SessionId $sid
    if ($qualityState) {
        $workflow = [string]$qualityState.task.workflowId
        $reviewGate = [string]$qualityState.gates.review
        $status = [string]$qualityState.status
        if ($workflow -notmatch '(?i)(^|[:/>,+\s-])feature($|[:/>,+\s-])' -or $status -in @('ready', 'partial', 'blocked', 'unknown') -or $reviewGate -in @('passed', 'not_required')) {
            Remove-SessionMarkers -Directory $dir -SafeId $safe
            exit 0
        }
    }

    $cmd = ''
    try { $cmd = (Get-Content -LiteralPath $pending -Raw -ErrorAction SilentlyContinue).Trim() } catch { }

    $reason = @"
У этой feature-сессии есть незавершённый review-цикл.

Сейчас нужно продолжить работу:
1. Дождись свежего ревью или проверь его состояние через GitHub/CLI.
2. Разбери замечания и исправь реальные блокеры.
3. После каждого исправления повтори проверки, push и review.
4. Когда блокеров нет, выставь review gate в passed через first-pass quality controller. Turnstile удалит маркер автоматически.

Если пользователь явно сказал "стоп", "оставь" или "не туда", UserPromptSubmit-хук пропустит turnstile.

Маркер был поставлен после команды:
$cmd
"@

    @{ decision = 'block'; reason = $reason } | ConvertTo-Json -Compress | Write-Output
} catch {
}

exit 0
