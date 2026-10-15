# 一键安装 UI 汉化 mod（运行时）
# 用法: .\install_mod.ps1 -GamePath "K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5"
param(
    [Parameter(Mandatory = $true)][string]$GamePath
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $PSScriptRoot

$ue4ss = Join-Path $GamePath 'Binaries\Win64\ue4ss'
if (-not (Test-Path $ue4ss)) {
    Write-Error ('找不到 UE4SS 目录: ' + $ue4ss + '  —— 请先安装 UE4SS（dwmapi.dll 与 ue4ss/ 放到 Binaries\Win64\ 下）')
}
$modDst = Join-Path $ue4ss 'Mods\UIZh'
$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'

if (Test-Path $modDst) {
    $bk = Join-Path (Split-Path -Parent $modDst) ('UIZh_backup_' + $stamp)
    Copy-Item $modDst $bk -Recurse -Force
    Write-Host ('已备份原 mod -> ' + $bk) -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force -Path (Join-Path $modDst 'scripts') | Out-Null
Copy-Item (Join-Path $here 'mod\UIZh\scripts\main.lua') (Join-Path $modDst 'scripts\main.lua') -Force
Copy-Item (Join-Path $here 'mod\UIZh\enabled.txt')       (Join-Path $modDst 'enabled.txt') -Force

Write-Host ('安装完成: ' + $modDst) -ForegroundColor Green
Write-Host '启动游戏后在日志确认（应出现「UI 汉化 mod 已加载」）:'
Write-Host ('  ' + (Join-Path $ue4ss 'UE4SS.log'))
