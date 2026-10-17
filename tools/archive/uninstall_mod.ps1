# 回退 UI 汉化 mod
param([Parameter(Mandatory = $true)][string]$GamePath)
$ErrorActionPreference = 'Stop'
$modDst = Join-Path $GamePath 'Binaries\Win64\ue4ss\Mods\UIZh'
if (-not (Test-Path $modDst)) { Write-Host ('不存在，无需回退: ' + $modDst); exit 0 }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$bk = Join-Path (Split-Path -Parent $modDst) ('UIZh_removed_' + $stamp)
Move-Item $modDst $bk -Force
Write-Host ('已移除（保留备份）-> ' + $bk) -ForegroundColor Green
