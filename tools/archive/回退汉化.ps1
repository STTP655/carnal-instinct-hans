<#
.SYNOPSIS
    Carnal Instinct 简体中文汉化 —— 回退（还原游戏原 pak + 关闭/移除 mod）

.DESCRIPTION
    从「一键汉化.ps1」留下的备份（<脚本目录>\backup\<时间戳>\）里选一份还原游戏 pak。
    只有一个备份时自动选用；有多个时列出让你选；也可以 -BackupDir 直接指定。
    随后可选择关闭（默认）或移除 UE4SS 的 UIZh mod。

    只还原 .pak 这 1 个文件；同目录的 .utoc / .ucas 从未被本套脚本改动过。

.PARAMETER GamePath
    游戏目录，指向 Carnal_Instinct_UE5（其下有 Content\Paks）。

.PARAMETER BackupDir
    指定备份目录：可以是某一份备份目录（含 pakchunk1013-Windows.pak），
    也可以是备份根目录（其下有多份时间戳子目录）。不给则默认 <脚本目录>\backup。
    若安装时用过 一键汉化.ps1 -BackupRoot，这里用同样的路径或 -BackupRoot 指定。

.PARAMETER BackupRoot
    与 -BackupDir 含义相同（兼容 一键汉化.ps1 的同名参数）。两者只给一个。

.PARAMETER Latest
    多份备份时不再询问，直接用最新的一份。

.PARAMETER RemoveMod
    把 ue4ss\Mods\UIZh 整个目录移走（Mods\UIZh_removed_<时间戳>）；
    默认只把 enabled.txt 改名为 enabled.txt.off（可逆、不删文件）。

.PARAMETER KeepMod
    完全不动 mod（只还原 pak）。

.PARAMETER DryRun
    干跑：只列出备份并打印将要执行的步骤，不写任何文件（别名 -WhatIf）。

.EXAMPLE
    .\tools\回退汉化.ps1 -GamePath "K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5"

.EXAMPLE
    .\tools\回退汉化.ps1 -GamePath "K:\...\Carnal_Instinct_UE5" -Latest -RemoveMod
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GamePath,
    [string]$BackupDir,
    [string]$BackupRoot,
    [switch]$Latest,
    [switch]$RemoveMod,
    [switch]$KeepMod,
    [Alias('WhatIf', 'NoAction')][switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$PakName   = 'pakchunk1013-Windows.pak'
if ($RemoveMod -and $KeepMod) { throw '-RemoveMod 与 -KeepMod 不能同时使用。' }
if ($BackupDir -and $BackupRoot) { throw '-BackupDir 与 -BackupRoot 只需给一个（两者含义相同：备份目录或备份根目录）。' }

function Section($t) { Write-Host ''; Write-Host ('== ' + $t) -ForegroundColor Cyan }
function Note($m)  { Write-Host ('   ' + $m) }
function Ok($m)    { Write-Host ('   [OK] ' + $m) -ForegroundColor Green }
function Warn($m)  { Write-Host ('   [!] ' + $m) -ForegroundColor Yellow }
function Plan($m)  { Write-Host ('   [DryRun] ' + $m) -ForegroundColor DarkGray }
function Fail($m) {
    Write-Host ''
    Write-Host ('[失败] ' + $m) -ForegroundColor Red
    Write-Host '[中止] 未对游戏文件做任何改动。' -ForegroundColor Red
    exit 1
}
function Get-Sha256([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }

Write-Host ''
Write-Host '==============================================' -ForegroundColor White
Write-Host ' Carnal Instinct 简体中文汉化 —— 回退' -ForegroundColor White
Write-Host '==============================================' -ForegroundColor White
if ($DryRun) { Write-Host ' [DryRun / 干跑] 只列出备份 + 打印步骤，不写任何文件' -ForegroundColor Yellow }
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'

# ---------------------------------------------------------------- 1 游戏目录 + 目标 pak
Section '1/5 定位游戏目录'
$gameRoot = $null
foreach ($cand in @($GamePath, (Join-Path $GamePath 'Carnal_Instinct_UE5'))) {
    if (Test-Path (Join-Path $cand 'Content\Paks')) { $gameRoot = (Resolve-Path -LiteralPath $cand).Path; break }
}
if (-not $gameRoot) { Fail ('在 -GamePath 下找不到 Content\Paks：' + $GamePath) }
$GamePak = Join-Path $gameRoot ('Content\Paks\' + $PakName)
Ok ('游戏目录 : ' + $gameRoot)
Ok ('目标 pak : ' + $GamePak)
if (-not (Test-Path -LiteralPath $GamePak)) { Fail ('找不到 ' + $GamePak) }
if (Test-Path -LiteralPath $GamePak) {
    Note ('当前 pak : {0:N0} 字节  SHA256 {1}' -f (Get-Item -LiteralPath $GamePak).Length, (Get-Sha256 $GamePak))
}

# ---------------------------------------------------------------- 2 找备份
Section '2/5 查找可用备份'
$root = $BackupDir
if (-not $root) { $root = $BackupRoot }
if (-not $root) { $root = Join-Path $ScriptDir 'backup' }
if (-not (Test-Path -LiteralPath $root)) {
    Fail @"
备份目录不存在: $root
没有备份时无法用本脚本回退。可选做法：
  a) 重跑 一键汉化.ps1（它每次都会先备份）；
  b) Steam 库里对游戏执行「验证文件完整性」把 pak 换回官方版（汉化随之消失）；
  c) 从 03_原始备份\pakchunk1013-Windows.pak.locres实验前 之类的手工备份复制回来。
"@
}

$cands = @()
if (Test-Path -LiteralPath (Join-Path $root $PakName)) {
    $cands += (Resolve-Path -LiteralPath $root).Path          # -BackupDir 直接指向一份备份
} else {
    foreach ($d in @(Get-ChildItem -LiteralPath $root -Force | Where-Object { $_.PSIsContainer })) {
        if (Test-Path -LiteralPath (Join-Path $d.FullName $PakName)) { $cands += $d.FullName }
    }
    $cands = @($cands | Sort-Object -Descending)
}
if ($cands.Count -eq 0) { Fail ('在 ' + $root + ' 下找不到含 ' + $PakName + ' 的备份目录。') }

Note ('找到 ' + $cands.Count + ' 份备份:')
$i = 0
foreach ($c in $cands) {
    $i++
    $p = Join-Path $c $PakName
    $t = (Get-Item -LiteralPath $p).LastWriteTime.ToString('yyyy-MM-dd HH:mm')
    Note ('  [' + $i + '] ' + $c)
    Note ('      {0:N0} 字节  文件时间 {1}  SHA256 {2}' -f (Get-Item -LiteralPath $p).Length, $t, (Get-Sha256 $p).Substring(0, 16))
}

$chosen = $null
if ($cands.Count -eq 1) { $chosen = $cands[0]; Ok '只有一份备份，自动选用。' }
elseif ($Latest)        { $chosen = $cands[0]; Ok '按 -Latest 选用最新一份。' }
else {
    $sel = $null
    try {
        $sel = Read-Host ('请选择要还原的备份序号 1..' + $cands.Count + '（回车=1 最新，q=取消）')
    } catch {
        Fail ('当前环境无法交互输入。请改用 -Latest（最新一份）或 -BackupDir / -BackupRoot 指定要还原的备份。候选：' + ($cands -join ' | '))
    }
    if ($sel -eq 'q' -or $sel -eq 'Q') { Write-Host '已取消，未做任何改动。'; exit 0 }
    if (-not $sel) { $sel = '1' }
    $n = 0
    if (-not [int]::TryParse($sel, [ref]$n)) { Fail ('无效序号: ' + $sel + '（候选: ' + ($cands -join ' | ') + '）') }
    if ($n -lt 1 -or $n -gt $cands.Count) { Fail ('序号超出范围: ' + $sel) }
    $chosen = $cands[$n - 1]
}

$bakPak = Join-Path $chosen $PakName
Section '3/5 待还原的备份'
Ok ('备份目录 : ' + $chosen)
Ok ('备份 pak : ' + $bakPak)
$bakSha = Get-Sha256 $bakPak
Note ('大小     : {0:N0} 字节' -f (Get-Item -LiteralPath $bakPak).Length)
Note ('SHA256   : ' + $bakSha)
$metaPath = Join-Path $chosen 'backup.json'
if (Test-Path -LiteralPath $metaPath) {
    try {
        $meta = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Note ('备份时间 : ' + $meta.'时间')
        Note ('备份来源 : ' + $meta.'游戏目录')
        if ($meta.'原始pakSHA256' -and $meta.'原始pakSHA256' -ne $bakSha) {
            Warn ('backup.json 记录的 SHA256（' + $meta.'原始pakSHA256' + '）与本文件不符，备份可能被改动过。')
        } else {
            Ok 'backup.json 记录与文件一致。'
        }
    } catch {
        Warn ('backup.json 解析失败（忽略）: ' + $_.Exception.Message)
    }
} else {
    Warn '该备份目录没有 backup.json（手工放入的备份？），将按文件本身还原。'
}

# ---------------------------------------------------------------- 4 进程检测
Section '4/5 检测游戏进程'
$running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'Carnal*' })
if ($running.Count -gt 0) {
    foreach ($p in $running) { Warn ('运行中: ' + $p.ProcessName + ' (PID ' + $p.Id + ')') }
    Fail '游戏正在运行，请完全退出游戏后重跑。'
}
Ok '没有检测到 Carnal* 进程。'

# ---------------------------------------------------------------- 5 还原
Section ('5/5 还原游戏 pak' + $(if ($KeepMod) { '（-KeepMod：不动 mod）' } else { ' + 处理 mod' }))
Note '即将执行（危险步骤：覆盖游戏文件）：'
Note ('  ' + $bakPak)
Note ('  -> ' + $GamePak)
if ($DryRun) {
    Plan ('复制 ' + $bakPak + ' -> ' + $GamePak + '（覆盖）')
    Plan '复制后校验游戏 pak 的 SHA256 == 备份 pak 的 SHA256'
} else {
    Copy-Item -LiteralPath $bakPak -Destination $GamePak -Force
    $now = Get-Sha256 $GamePak
    if ($now -ne $bakSha) { Fail ('还原后校验失败：' + $now + ' != ' + $bakSha + '。请重试或改用手工复制。') }
    Ok ('已还原并校验一致: {0:N0} 字节  SHA256 {1}' -f (Get-Item -LiteralPath $GamePak).Length, $now)
}

# ---- mod
$ue4ss  = Join-Path $gameRoot 'Binaries\Win64\ue4ss'
$modDst = Join-Path $ue4ss 'Mods\UIZh'
if ($KeepMod) {
    Warn '已按 -KeepMod 保留 mod（动态文本仍为中文；locres 部分已还原为英文）。'
} elseif (-not (Test-Path -LiteralPath $modDst)) {
    Note ('未发现 mod 目录，无需处理: ' + $modDst)
} elseif ($RemoveMod) {
    Note ('将移走整个 mod 目录 -> ' + (Join-Path (Split-Path -Parent $modDst) ('UIZh_removed_' + $Stamp)))
    if ($DryRun) {
        Plan ('移动 ' + $modDst + ' -> ' + (Join-Path (Split-Path -Parent $modDst) ('UIZh_removed_' + $Stamp)))
    } else {
        $dst = Join-Path (Split-Path -Parent $modDst) ('UIZh_removed_' + $Stamp)
        Move-Item -LiteralPath $modDst -Destination $dst -Force
        Ok ('mod 已移走（保留备份）-> ' + $dst)
    }
} else {
    $on = Join-Path $modDst 'enabled.txt'
    $off = Join-Path $modDst 'enabled.txt.off'
    if (Test-Path -LiteralPath $on) {
        if ($DryRun) {
            Plan ('改名 ' + $on + ' -> ' + $off + '（UE4SS 只加载 enabled.txt，改名即关闭）')
        } else {
            if (Test-Path -LiteralPath $off) { Remove-Item -LiteralPath $off -Force }
            Rename-Item -LiteralPath $on -NewName 'enabled.txt.off' -Force
            Ok 'mod 已关闭（enabled.txt -> enabled.txt.off）'
        }
    } elseif (Test-Path -LiteralPath $off) {
        Note 'mod 本来就是关闭状态（enabled.txt.off）。'
    } else {
        Warn ('mod 目录里既没有 enabled.txt 也没有 enabled.txt.off: ' + $modDst)
    }
    Note ('想彻底删除 mod：删除目录 ' + $modDst + '，或用 -RemoveMod 重跑本脚本。')
    Note ('想恢复 mod：把 enabled.txt.off 改回 enabled.txt，或重跑 一键汉化.ps1。')
}

Write-Host ''
Write-Host '================ 完成 ================' -ForegroundColor Green
if ($DryRun) {
    Write-Host ' [DryRun] 以上为将要执行的步骤，未写任何文件。去掉 -DryRun 即正式回退。' -ForegroundColor Yellow
} else {
    Note ('游戏 pak   : ' + $GamePak)
    Note ('已还原到   : ' + $chosen)
    Note '说明       : 本次只还原 .pak；.utoc / .ucas（对话汉化容器）本套脚本从未改动过。'
    Warn '不要跑 Steam「验证文件完整性」，否则会把 pak 换回官方版——本备份仍然可用，重跑本脚本即可再还原一次。'
}
Write-Host '=====================================' -ForegroundColor Green
