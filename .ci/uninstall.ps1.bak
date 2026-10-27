# =============================================================================
# uninstall.ps1 -- 卸载由 install.ps1 安装的文件（依据 .ci/.install-manifest）
# 用法:
#   .\uninstall.ps1 -Target "D:\Git\your-project"
#   .\uninstall.ps1 -Target "D:\Git\your-project" -DryRun
#   .\uninstall.ps1 -Target "D:\Git\your-project" -PurgeConfig
# =============================================================================
param(
    [string]$Target = ".",
    [switch]$DryRun,
    [switch]$PurgeConfig
)

$Target = (Resolve-Path $Target).Path
$M = Join-Path $Target '.ci/.install-manifest'

if (-not (Test-Path $M)) {
    Write-Host "未找到安装清单：$M" -ForegroundColor Red
    Write-Host "无法安全卸载（可能是旧版安装或并非由本模板安装）。"
    exit 1
}

Write-Host "从 $Target 卸载（依据 .ci/.install-manifest）"
if ($DryRun) { Write-Host "*** DRY-RUN：不会删除任何文件 ***" }
Write-Host ("-" * 60)

$removed = 0; $kept = 0
Get-Content $M | ForEach-Object {
    $rel = $_.Trim()
    if ([string]::IsNullOrWhiteSpace($rel) -or $rel.StartsWith('#')) { return }

    if ($rel -eq '.ci/project.config.yaml' -and -not $PurgeConfig) {
        Write-Host "KEEP   $rel  (默认保留，用 -PurgeConfig 一并删除)"
        $script:kept++
        return
    }
    $p = Join-Path $Target ($rel -replace '/', '\')
    if (Test-Path $p) {
        if ($DryRun) { Write-Host "REMOVE $rel" }
        else { Remove-Item $p -Force; Write-Host "REMOVE $rel" }
        $script:removed++
    }
}

if (-not $DryRun) {
    $cfg = Join-Path $Target '.ci/project.config.yaml'
    if (-not (Test-Path $cfg)) { Remove-Item $M -Force -ErrorAction SilentlyContinue }

    # 删除空目录（仅 .ci 与 .github 下）
    $ci = Join-Path $Target '.ci'
    if (Test-Path $ci) {
        Get-ChildItem $ci -Recurse -Directory | Sort-Object FullName -Descending | ForEach-Object {
            if (-not (Get-ChildItem $_.FullName -Force)) { Remove-Item $_.FullName -Force }
        }
        if (-not (Get-ChildItem $ci -Force)) { Remove-Item $ci -Force }
    }
    foreach ($d in @('.github/workflows', '.github')) {
        $p = Join-Path $Target $d
        if ((Test-Path $p) -and -not (Get-ChildItem $p -Force)) { Remove-Item $p -Force }
    }
}

Write-Host ("-" * 60)
Write-Host "完成：删除 $removed 项，保留 $kept 项。"
if ($kept -gt 0) { Write-Host "提示：配置仍在 .ci/project.config.yaml；如需彻底删除，请加 -PurgeConfig。" }
