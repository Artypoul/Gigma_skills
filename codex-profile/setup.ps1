[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$CodexHome = (Join-Path $HOME '.codex'),
    [switch]$InstallHooks,
    [switch]$AdoptGlobalAgents,
    [switch]$AdoptHooks
)

$ErrorActionPreference = 'Stop'
$profileRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $profileRoot
$codexHome = [IO.Path]::GetFullPath($CodexHome)
$skillsDest = Join-Path $codexHome 'skills'
$manifestPath = Join-Path $codexHome '.gigma-skills-profile-manifest'
$agentsSource = Join-Path $profileRoot 'global-AGENTS.md'
$agentsDest = Join-Path $codexHome 'AGENTS.md'

New-Item -ItemType Directory -Force $codexHome, $skillsDest | Out-Null

$sourceMap = @{}
$duplicateNames = @()
$pluginDirs = Get-ChildItem -Directory (Join-Path $repoRoot 'plugins')
foreach ($plugin in $pluginDirs) {
    $skillsRoot = Join-Path $plugin.FullName 'skills'
    if (-not (Test-Path -LiteralPath $skillsRoot)) { continue }
    foreach ($skill in Get-ChildItem -Directory $skillsRoot) {
        if (-not (Test-Path -LiteralPath (Join-Path $skill.FullName 'SKILL.md'))) { continue }
        if ($sourceMap.ContainsKey($skill.Name)) { $duplicateNames += $skill.Name }
        else { $sourceMap[$skill.Name] = $skill.FullName }
    }
}
$personalRoot = Join-Path $profileRoot 'personal-skills'
if (Test-Path -LiteralPath $personalRoot) {
    foreach ($skill in Get-ChildItem -Directory $personalRoot) {
        if (-not (Test-Path -LiteralPath (Join-Path $skill.FullName 'SKILL.md'))) { continue }
        if ($sourceMap.ContainsKey($skill.Name)) { $duplicateNames += $skill.Name }
        else { $sourceMap[$skill.Name] = $skill.FullName }
    }
}
if ($duplicateNames.Count -gt 0) {
    throw "Duplicate skill names in profile: $($duplicateNames -join ', ')"
}

$managed = @()
if (Test-Path -LiteralPath $manifestPath) {
    $managed = @(Get-Content -LiteralPath $manifestPath | Where-Object { $_.Trim() })
}

$conflicts = @()
foreach ($name in $sourceMap.Keys) {
    $destination = Join-Path $skillsDest $name
    if ((Test-Path -LiteralPath $destination) -and ($managed -notcontains $name)) {
        $conflicts += $name
    }
}
if ($conflicts.Count -gt 0) {
    Write-Warning ("ОТКАЗ: уже существуют неуправляемые скиллы: " + ($conflicts -join ', ') + ". Переименование/удаление не выполняется. Если это ваши копии, добавьте их в manifest вручную только после проверки.")
    exit 2
}

foreach ($name in ($sourceMap.Keys | Sort-Object)) {
    $source = $sourceMap[$name]
    $destination = Join-Path $skillsDest $name
    if ($PSCmdlet.ShouldProcess($destination, "Install skill $name")) {
        if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
        Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
    }
}
if ($PSCmdlet.ShouldProcess($manifestPath, 'Write managed skill manifest')) {
    $sourceMap.Keys | Sort-Object | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

if (Test-Path -LiteralPath $agentsSource) {
    $agentsDiffer = (Test-Path -LiteralPath $agentsDest) -and ((Get-FileHash -LiteralPath $agentsSource).Hash -ne (Get-FileHash -LiteralPath $agentsDest).Hash)
    if (-not (Test-Path -LiteralPath $agentsDest) -or (-not $agentsDiffer)) {
        if ($PSCmdlet.ShouldProcess($agentsDest, 'Install global AGENTS.md')) {
            Copy-Item -LiteralPath $agentsSource -Destination $agentsDest -Force
        }
    } elseif ($AdoptGlobalAgents) {
        $backup = "$agentsDest.gigma-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        if ($PSCmdlet.ShouldProcess($agentsDest, 'Backup and replace global AGENTS.md')) {
            Copy-Item -LiteralPath $agentsDest -Destination $backup -Force
            Copy-Item -LiteralPath $agentsSource -Destination $agentsDest -Force
            Write-Output "Global AGENTS replaced; backup: $backup"
        }
    } else {
        Write-Warning "Глобальный AGENTS.md уже существует и отличается; оставлен без изменений. Для замены: -AdoptGlobalAgents"
    }
}

if ($InstallHooks) {
    $hookDest = Join-Path $codexHome 'profile-hooks'
    $hookSource = Join-Path $profileRoot 'hooks'
    $hooksJson = Join-Path $codexHome 'hooks.json'
    $hooksBackup = "$hooksJson.gigma-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    if ((Test-Path -LiteralPath $hooksJson) -and -not $AdoptHooks) {
        Write-Warning "hooks.json уже существует; хуки не заменены. Для замены: -InstallHooks -AdoptHooks"
    } else {
        if ((Test-Path -LiteralPath $hooksJson) -and $AdoptHooks -and $PSCmdlet.ShouldProcess($hooksJson, 'Backup existing hooks.json')) {
            Copy-Item -LiteralPath $hooksJson -Destination $hooksBackup -Force
            Write-Output "Existing hooks backed up: $hooksBackup"
        }
        if ($PSCmdlet.ShouldProcess($hookDest, 'Install profile hook scripts')) {
            New-Item -ItemType Directory -Force $hookDest | Out-Null
            Copy-Item -Path (Join-Path $hookSource '*.ps1') -Destination $hookDest -Force
        }
        $shortTask = Join-Path $skillsDest 'self-review-report\scripts\short-task-stop.ps1'
        $hookConfig = [ordered]@{
            hooks = [ordered]@{
                PostToolUse = @(@{ hooks = @(@{ type='command'; command="pwsh -NoProfile -File `"$(Join-Path $hookDest 'codex-feature-watch.ps1')`""; timeout=15; statusMessage='feature: watch PR push' }) })
                UserPromptSubmit = @(@{ hooks = @(@{ type='command'; command="pwsh -NoProfile -File `"$(Join-Path $hookDest 'codex-feature-user-prompt.ps1')`""; timeout=10; statusMessage='feature: detect stop override' }) })
                Stop = @(
                    @{ hooks = @(@{ type='command'; command="pwsh -NoProfile -File `"$(Join-Path $hookDest 'codex-feature-turnstile.ps1')`""; timeout=20; statusMessage='feature: review turnstile' }) }
                    @{ hooks = @(@{ type='command'; command='powershell -NoProfile -Command "[System.Media.SystemSounds]::Exclamation.Play(); Start-Sleep -Milliseconds 400"'; timeout=5 }) }
                    @{ hooks = @(@{ type='command'; command="powershell.exe -NoProfile -NonInteractive -File `"$shortTask`""; timeout=5; statusMessage='Второй проход короткой задачи' }) }
                )
            }
        }
        if ($PSCmdlet.ShouldProcess($hooksJson, 'Install hooks.json')) {
            $hookConfig | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $hooksJson -Encoding UTF8
        }
    }
}

Write-Output "Codex profile installed: $($sourceMap.Count) skills -> $skillsDest"
