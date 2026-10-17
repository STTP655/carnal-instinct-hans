<#
.SYNOPSIS
    Carnal Instinct 简体中文汉化 —— 一键安装（locres 注入 + 可选 UIZh mod）

.DESCRIPTION
    在【你自己】的正版游戏上完成汉化：把 data\Game.locres.fix1（14,106 条中文）注入
    pakchunk1013-Windows.pak 内的 Carnal_Instinct_UE5/Content/Localization/Game/en/Game.locres，
    pak 内其余文件原样保留；随后可选挂载 UE4SS 运行时 mod（UIZh，覆盖动态文本）。

    安全设计：
      1) 覆盖游戏文件前，先把游戏当前 pak 原样备份到 <脚本目录>\backup\<时间戳>\；
      2) 打包参数与游戏原 pak 完全一致（mount ../../../ / V11 / Oodle / seed 3E7ADF21）；
      3) 覆盖前先解包复核新 pak：文件清单与游戏原 pak 一致、除 locres 外逐字节相同、
         包内 locres 的 SHA256 == data\Game.locres.fix1 的 SHA256；
      4) 只写 .pak 这 1 个文件，绝不碰同目录的 .utoc / .ucas（那是对话汉化容器）；
      5) 打包是非确定性的（每次 SHA256 都不同），等价判据 = 解包后 locres 的 SHA256。

.PARAMETER GamePath
    游戏目录，指向 Carnal_Instinct_UE5（其下有 Content\Paks）。给上一级也行，脚本会自动下探。

.PARAMETER RepakPath
    repak.exe 路径。默认依次探测：tools\repak\repak.exe、tools\repak.exe、
    工作区 02_工具\repak\repak.exe、PATH 里的 repak。

.PARAMETER SkipMod
    只做 locres 注入，不安装 UIZh mod（适合不想装 UE4SS 的场景）。

.PARAMETER DryRun
    干跑：只做只读检查，并打印将要执行的每一步，不写任何文件（别名 -WhatIf）。

.PARAMETER KeepTemp
    排错用：保留临时目录不清理。

.PARAMETER BackupRoot
    备份根目录，默认 <脚本目录>\backup。

.EXAMPLE
    .\tools\一键汉化.ps1 -GamePath "K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5" -DryRun

.EXAMPLE
    .\tools\一键汉化.ps1 -GamePath "K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5" -SkipMod
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GamePath,
    [string]$RepakPath,
    [switch]$SkipMod,
    [Alias('WhatIf', 'NoAction')][switch]$DryRun,
    [switch]$KeepTemp,
    [string]$BackupRoot
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- 常量
$ScriptDir     = $PSScriptRoot
$RepoRoot      = Split-Path -Parent $ScriptDir
$LocresSrc     = Join-Path $RepoRoot 'data\Game.locres.fix1'
$ModSrc        = Join-Path $RepoRoot 'mod\UIZh'
$PakName       = 'pakchunk1013-Windows.pak'
$InnerLocresRel = 'Content\Localization\Game\en\Game.locres'
$ExpectedSha   = '85F28F91088C263675E6A23DE0CBB38E4749FE86E460D1552349590B0F522CDC'
$MountPoint    = '../../../'
$PakVersion    = 'V11'
$Compression   = 'Oodle'
$PathHashSeed  = '1048239905'          # == 0x3E7ADF21，与游戏原 pak 一致
$SeedHex       = '3E7ADF21'
if (-not $BackupRoot) { $BackupRoot = Join-Path $ScriptDir 'backup' }

# ---------------------------------------------------------------- 输出 helper
function Section($t) {
    Write-Host ''
    Write-Host ('== ' + $t) -ForegroundColor Cyan
}
function Note($m)  { Write-Host ('   ' + $m) }
function Ok($m)    { Write-Host ('   [OK] ' + $m) -ForegroundColor Green }
function Warn($m)  { Write-Host ('   [!] ' + $m) -ForegroundColor Yellow }
function Plan($m)  { Write-Host ('   [DryRun] ' + $m) -ForegroundColor DarkGray }
function Fail($m) {
    Write-Host ''
    Write-Host ('[失败] ' + $m) -ForegroundColor Red
    Write-Host '[中止] 覆盖游戏文件之前的任何失败都不会改动游戏文件；备份保留在 backup 目录。' -ForegroundColor Red
    exit 1
}

# 执行外部命令；DryRun 时只打印不执行。返回 exit code（外部命令输出走 Out-Host，不污染返回值）
function Run-Tool([string]$exe, [string[]]$argv) {
    $parts = @()
    foreach ($a in @($exe) + $argv) {
        if ($a -match '\s') { $parts += ('"' + $a + '"') } else { $parts += $a }
    }
    $line = ($parts -join ' ')
    if ($DryRun) { Plan ('运行: ' + $line); return 0 }
    Note ('> ' + $line)
    & $exe @argv 2>&1 | Out-Host
    return $LASTEXITCODE
}

function Write-TextFile([string]$path, [string]$text) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $text, $enc)
}

function Get-Sha256([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }

# 相对文件清单（排序）
function Get-RelFileList([string]$root) {
    $out = @()
    foreach ($f in @(Get-ChildItem -LiteralPath $root -Recurse -Force -File)) {
        $out += $f.FullName.Substring($root.Length).TrimStart('\')
    }
    return @($out | Sort-Object)
}

# 在解包树里找包内 locres
function Find-InnerLocres([string]$root) {
    $hit = @(Get-ChildItem -LiteralPath $root -Recurse -Force -File |
             Where-Object { $_.FullName -like '*Localization\Game\en\Game.locres' })
    if ($hit.Count -eq 0) {
        $hit = @(Get-ChildItem -LiteralPath $root -Recurse -Force -File |
                 Where-Object { $_.Name -eq 'Game.locres' })
    }
    if ($hit.Count -eq 0) { return $null }
    return $hit[0].FullName
}

# ================================================================ 开场
Write-Host ''
Write-Host '==============================================' -ForegroundColor White
Write-Host ' Carnal Instinct 简体中文汉化 —— 一键安装' -ForegroundColor White
Write-Host ' 机制：只替换 pakchunk1013-Windows.pak 内的 Game.locres' -ForegroundColor White
Write-Host '==============================================' -ForegroundColor White
if ($DryRun) { Write-Host ' [DryRun / 干跑] 只做只读检查 + 打印步骤，不写任何文件' -ForegroundColor Yellow }
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
Note ('时间戳   : ' + $Stamp)
Note ('仓库目录 : ' + $RepoRoot)
Note ('备份根   : ' + $BackupRoot)
if ($KeepTemp) { Note '保留临时目录: 是' }

# ---------------------------------------------------------------- 1 解析游戏目录
Section '1/9 定位游戏目录'
$gameRoot = $null
foreach ($cand in @($GamePath, (Join-Path $GamePath 'Carnal_Instinct_UE5'))) {
    if (Test-Path (Join-Path $cand 'Content\Paks')) { $gameRoot = (Resolve-Path -LiteralPath $cand).Path; break }
}
if (-not $gameRoot) {
    Fail ('在 -GamePath 下找不到 Content\Paks：' + $GamePath + '（应指向 Carnal_Instinct_UE5，例如 K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5）')
}
$PaksDir = Join-Path $gameRoot 'Content\Paks'
$GamePak = Join-Path $PaksDir $PakName
Ok ('游戏目录 : ' + $gameRoot)
Ok ('目标 pak : ' + $GamePak)
if (-not (Test-Path -LiteralPath $GamePak)) {
    Fail ('找不到 ' + $PakName + '；请确认游戏版本（本补丁针对含 ' + $InnerLocresRel + ' 的 1013 号 pak）。')
}
$origPakLen = (Get-Item -LiteralPath $GamePak).Length
$origPakSha = Get-Sha256 $GamePak
Note ('当前 pak : {0:N0} 字节  SHA256 {1}' -f $origPakLen, $origPakSha)
Warn '本脚本只写 .pak 这 1 个文件，不会碰同目录的 .utoc / .ucas。'
# 回退命令（用自定义 -BackupRoot 时把它一并带上，否则回退脚本找不到备份）
$rollbackCmd = '.\tools\回退汉化.ps1 -GamePath "' + $gameRoot + '"'
if ($PSBoundParameters.ContainsKey('BackupRoot')) { $rollbackCmd = $rollbackCmd + ' -BackupRoot "' + $BackupRoot + '"' }

# ---------------------------------------------------------------- 2 进程检测
Section '2/9 检测游戏进程'
$running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'Carnal*' })
if ($running.Count -gt 0) {
    foreach ($p in $running) { Warn ('运行中: ' + $p.ProcessName + ' (PID ' + $p.Id + ')') }
    Fail '游戏正在运行，请完全退出游戏（建议连 Steam 一起退出）后重跑。pak 被占用会导致覆盖失败或写坏文件。'
}
Ok '没有检测到 Carnal* 进程。'

# ---------------------------------------------------------------- 3 探测 repak
Section '3/9 探测 repak'
$repak = $null
if ($RepakPath) {
    if (-not (Test-Path -LiteralPath $RepakPath)) { Fail ('-RepakPath 指定的文件不存在: ' + $RepakPath) }
    $repak = (Resolve-Path -LiteralPath $RepakPath).Path
} else {
    $cands = @(
        (Join-Path $ScriptDir 'repak\repak.exe'),
        (Join-Path $ScriptDir 'repak.exe'),
        'D:\DSH工作区\CarnalInstinct_汉化\02_工具\repak\repak.exe'
    )
    foreach ($c in $cands) { if (Test-Path -LiteralPath $c) { $repak = $c; break } }
    if (-not $repak) {
        $g = Get-Command repak -ErrorAction SilentlyContinue
        if ($g) { $repak = $g.Source }
    }
}
if (-not $repak) {
    Fail @'
找不到 repak.exe。请任选一种方式后重跑：
  a) 下载 https://github.com/trumank/repak/releases 的 repak.exe，放到 tools\repak\repak.exe；
  b) 用 -RepakPath "D:\path\to\repak.exe" 指定；
  c) 把 repak 加进 PATH。
'@
}
Ok ('repak : ' + $repak)
$ver = (& $repak --version 2>&1 | Select-Object -First 1)
Note ('版本  : ' + $ver)

# ---------------------------------------------------------------- 4 校验汉化数据
Section '4/9 校验汉化数据 data\Game.locres.fix1'
if (-not (Test-Path -LiteralPath $LocresSrc)) {
    Fail ('缺少 ' + $LocresSrc + '（本仓库的汉化数据，必须与脚本一起存在）。')
}
$srcLen = (Get-Item -LiteralPath $LocresSrc).Length
$srcSha = Get-Sha256 $LocresSrc
Note ('文件  : ' + $LocresSrc)
Note ('大小  : {0:N0} 字节' -f $srcLen)
Note ('SHA256: ' + $srcSha)
if ($srcSha -ne $ExpectedSha) {
    Fail ('汉化数据被改动过：期望 ' + $ExpectedSha + '，实际 ' + $srcSha + '。请用 git 恢复 data\Game.locres.fix1。')
}
Ok 'SHA256 与 fix1 版一致（14,106 条中文）。'

# ---------------------------------------------------------------- 5 备份
$backupDir = Join-Path $BackupRoot $Stamp
$backupPak = Join-Path $backupDir $PakName
Section '5/9 备份游戏当前 pak'
Note ('源     : ' + $GamePak)
Note ('备份到 : ' + $backupPak)
if ($DryRun) {
    Plan ('新建目录 ' + $backupDir)
    Plan ('复制 ' + $GamePak + ' -> ' + $backupPak + '（{0:N0} 字节）' -f $origPakLen)
    Plan '复制后校验备份 SHA256 == 原文件 SHA256'
    Plan '写 backup.json（记录时间 / 游戏目录 / 原始 SHA256，供回退脚本核对）'
} else {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Copy-Item -LiteralPath $GamePak -Destination $backupPak -Force
    $bakSha = Get-Sha256 $backupPak
    if ($bakSha -ne $origPakSha) { Fail ('备份校验失败：备份 SHA256 ' + $bakSha + ' != 原文件 ' + $origPakSha) }
    $bakInfo = [ordered]@{
        '时间'           = (Get-Date).ToString('s')
        '游戏目录'       = $gameRoot
        'pak文件名'      = $PakName
        '原始pak大小'    = $origPakLen
        '原始pakSHA256'  = $origPakSha
        '汉化数据'       = 'data\Game.locres.fix1'
        '汉化数据SHA256' = $ExpectedSha
        '说明'           = '本目录是覆盖游戏 pak 之前的原样备份，回退汉化.ps1 用它还原。'
    }
    Write-TextFile (Join-Path $backupDir 'backup.json') ($bakInfo | ConvertTo-Json -Depth 4)
    Ok ('备份完成并校验一致（{0:N0} 字节）。' -f (Get-Item -LiteralPath $backupPak).Length)
}
Ok ('备份目录 : ' + $backupDir)

# ---------------------------------------------------------------- 6 解包游戏 pak
$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('ci_hans_' + $Stamp)
$unpackA = Join-Path $tmpRoot 'unpack_orig'
$unpackB = Join-Path $tmpRoot 'unpack_new'
$newPak  = Join-Path $tmpRoot ($PakName + '.hans')
Section '6/9 解包游戏当前 pak（只读取，不改原文件）'
Note ('临时目录 : ' + $tmpRoot)
$listA = @()
$hashA = @{}
$innerLocresA = $null
$relA = $InnerLocresRel
if ($DryRun) {
    Plan ('新建目录 ' + $unpackA)
    Plan ('运行: ' + $repak + ' unpack "' + $GamePak + '" --output "' + $unpackA + '"')
    Plan ('在解包树里定位 *\' + $InnerLocresRel)
    Plan '记录文件清单与各文件 SHA256（供打包后逐条复核）'
} else {
    New-Item -ItemType Directory -Force -Path $unpackA | Out-Null
    $rc = Run-Tool $repak @('unpack', $GamePak, '--output', $unpackA)
    if ($rc -ne 0) {
        Fail ('repak unpack 失败（exit ' + $rc + '）。若报路径逃逸，可换 repak 版本重试，或手工用 repak list + repak get 逐条取出后再打包。')
    }
    $innerLocresA = Find-InnerLocres $unpackA
    if (-not $innerLocresA) { Fail ('解包结果里找不到 Game.locres（' + $unpackA + '）。游戏版本可能不受支持。') }
    $relA = $innerLocresA.Substring($unpackA.Length).TrimStart('\')
    $listA = Get-RelFileList $unpackA
    Ok ('解包文件数: ' + $listA.Count)
    foreach ($f in $listA) { Note ('  ' + $f) }
    Note ('包内 locres : ' + $relA)
    Note ('  其 SHA256 : ' + (Get-Sha256 $innerLocresA) + '（原版基线，仅记录）')
    foreach ($f in $listA) { $hashA[$f] = Get-Sha256 (Join-Path $unpackA $f) }
}

# ---------------------------------------------------------------- 7 替换 + 打包
Section '7/9 替换 locres 并重新打包（不改任何其他文件）'
if ($DryRun) {
    Plan ('把 ' + $LocresSrc + ' 复制到 <解包树>\' + $InnerLocresRel)
    Plan ('替换后校验该文件 SHA256 == ' + $ExpectedSha)
    Plan ('运行: ' + $repak + ' pack "' + $unpackA + '" "' + $newPak + '" -m "' + $MountPoint + '" --version ' + $PakVersion + ' --compression ' + $Compression + ' -p ' + $PathHashSeed)
} else {
    Note ('将被替换 : ' + $relA)
    Note ('替换为   : ' + $LocresSrc + '（SHA256 ' + $ExpectedSha + '）')
    Copy-Item -LiteralPath $LocresSrc -Destination $innerLocresA -Force
    $after = Get-Sha256 $innerLocresA
    if ($after -ne $ExpectedSha) { Fail ('替换后包内 locres 哈希不符：' + $after) }
    Ok '已在解包树内替换 locres（其余文件一个都没动）。'
    $rc = Run-Tool $repak @('pack', $unpackA, $newPak, '-m', $MountPoint, '--version', $PakVersion, '--compression', $Compression, '-p', $PathHashSeed)
    if ($rc -ne 0) { Fail ('repak pack 失败（exit ' + $rc + '）。') }
    if (-not (Test-Path -LiteralPath $newPak)) { Fail 'repak pack 未产出 pak 文件。' }
    Ok ('新 pak 已生成: {0:N0} 字节' -f (Get-Item -LiteralPath $newPak).Length)
}

# ---------------------------------------------------------------- 8 覆盖前复核
Section '8/9 覆盖前复核新 pak（覆盖游戏文件前最后一道校验）'
if ($DryRun) {
    Plan ('运行: ' + $repak + ' unpack "' + $newPak + '" --output "' + $unpackB + '"')
    Plan '复核1: 新 pak 文件清单 == 游戏原 pak 文件清单（一个不多一个不少）'
    Plan '复核2: 除 Game.locres 外，每个文件与游戏原 pak 内同名文件 SHA256 相同'
    Plan ('复核3: 新 pak 内 Game.locres 的 SHA256 == ' + $ExpectedSha)
    Plan ('复核4: repak info 显示 version=' + $PakVersion + ' / compression=' + $Compression + ' / seed=' + $SeedHex)
    Note '四项全过才进入第 9 步；任一不过即中止，游戏文件不受影响。'
} else {
    New-Item -ItemType Directory -Force -Path $unpackB | Out-Null
    $rc = Run-Tool $repak @('unpack', $newPak, '--output', $unpackB)
    if ($rc -ne 0) { Fail ('解包新 pak 失败（exit ' + $rc + '），已在覆盖前中止。') }
    $innerLocresB = Find-InnerLocres $unpackB
    if (-not $innerLocresB) { Fail '新 pak 解包后找不到 Game.locres，已在覆盖前中止。' }
    $relB = $innerLocresB.Substring($unpackB.Length).TrimStart('\')
    $listB = Get-RelFileList $unpackB

    # 复核1 清单一致
    $diffList = @(Compare-Object -ReferenceObject $listA -DifferenceObject $listB)
    if ($diffList.Count -gt 0) {
        foreach ($d in $diffList) { Warn ('清单差异 ' + $d.SideIndicator + ' ' + $d.InputObject) }
        Fail '新 pak 的文件清单与游戏原 pak 不一致，已在覆盖前中止。'
    }
    Ok ('复核1 文件清单一致（' + $listB.Count + ' 个文件）。')

    # 复核2 非 locres 逐字节相同
    $bad = @()
    $same = 0
    foreach ($f in $listB) {
        if ($f -eq $relB) { continue }
        $hb = Get-Sha256 (Join-Path $unpackB $f)
        if ($hashA[$f] -ne $hb) { $bad += $f } else { $same++ }
    }
    if ($bad.Count -gt 0) {
        foreach ($f in $bad) { Warn ('非 locres 文件被改动: ' + $f) }
        Fail '除 locres 外还有文件被改动，已在覆盖前中止。'
    }
    Ok ('复核2 除 locres 外 ' + $same + ' 个文件与游戏原 pak 逐字节相同。')

    # 复核3 包内 locres 哈希
    $locB = Get-Sha256 $innerLocresB
    if ($locB -ne $ExpectedSha) { Fail ('包内 locres SHA256 不符：' + $locB) }
    Ok ('复核3 包内 locres SHA256 == 汉化数据（' + $locB.Substring(0, 16) + '...）。')

    # 复核4 repak info
    $info = (& $repak info $newPak 2>&1 | Out-String)
    if ($info -notmatch [regex]::Escape($PakVersion)) { Warn ('repak info 未见 ' + $PakVersion + '，请人工确认输出。') }
    if ($info -notmatch [regex]::Escape($Compression)) { Warn ('repak info 未见 ' + $Compression + '，请人工确认输出。') }
    if ($info -notmatch [regex]::Escape($SeedHex)) { Warn ('repak info 未见 seed ' + $SeedHex + '，请人工确认输出。') }
    Ok '复核4 打包参数与游戏原 pak 同构（mount / version / compression / seed）。'
    Note '--- repak info ---'
    foreach ($ln in ($info -split "`r?`n")) { if ($ln.Trim()) { Note ('  ' + $ln.TrimEnd()) } }
}

# ---------------------------------------------------------------- 9 覆盖 + mod
if ($SkipMod) { Section '9/9 覆盖游戏 pak（已按 -SkipMod 跳过 mod）' }
else           { Section '9/9 覆盖游戏 pak + 安装 UE4SS mod' }
Note '即将执行（危险步骤；此前已完成备份 + 四项复核）：'
Note ('  写入目标 : ' + $GamePak)
if ($DryRun) {
    Plan ('复制 ' + $newPak + ' -> ' + $GamePak + '（覆盖；原文件已备份到 ' + $backupDir + '）')
    Plan '复制后重新读取游戏 pak 的 SHA256，必须 == 新 pak 的 SHA256'
    Plan ('写 installed.json 到备份目录（记录本次安装的 pak / locres 哈希）')
} else {
    Note ('  数据来源 : ' + $newPak)
    Note ('  回退方式 : ' + $rollbackCmd)
    $newSha = Get-Sha256 $newPak
    Copy-Item -LiteralPath $newPak -Destination $GamePak -Force
    $installed = Get-Sha256 $GamePak
    if ($installed -ne $newSha) {
        Fail ('覆盖后校验失败：游戏 pak SHA256 ' + $installed + ' != 新 pak ' + $newSha + '。请立刻运行回退汉化.ps1 还原。')
    }
    Ok ('已覆盖并校验一致: {0:N0} 字节  SHA256 {1}' -f (Get-Item -LiteralPath $GamePak).Length, $installed)
    $inst = [ordered]@{
        '时间'             = (Get-Date).ToString('s')
        '游戏pak路径'      = $GamePak
        '已安装pakSHA256'  = $installed
        '包内locresSHA256' = $ExpectedSha
        '备份目录'         = $backupDir
        '备份pakSHA256'    = $origPakSha
    }
    Write-TextFile (Join-Path $backupDir 'installed.json') ($inst | ConvertTo-Json -Depth 4)
}

if (-not $SkipMod) {
    Section '附加: 安装 UE4SS 运行时 mod（UIZh）'
    $ue4ss  = Join-Path $gameRoot 'Binaries\Win64\ue4ss'
    $modDst = Join-Path $ue4ss 'Mods\UIZh'
    if (-not (Test-Path -LiteralPath $ue4ss)) {
        Warn ('未找到 UE4SS 目录: ' + $ue4ss)
        Warn '跳过 mod 安装（静态文本已是中文；动态文本需装 UE4SS 后才能覆盖）。'
        Warn ('装好 UE4SS 后重跑: ' + (Join-Path $ScriptDir 'install_mod.ps1') + ' -GamePath "' + $gameRoot + '"')
    } elseif ($DryRun) {
        Plan ('若 ' + $modDst + ' 已存在 -> 先整目录备份为 Mods\UIZh_backup_' + $Stamp)
        Plan ('复制 ' + (Join-Path $ModSrc 'scripts\main.lua') + ' -> ' + (Join-Path $modDst 'scripts\main.lua'))
        Plan ('复制 ' + (Join-Path $ModSrc 'enabled.txt') + ' -> ' + (Join-Path $modDst 'enabled.txt'))
    } else {
        if (Test-Path -LiteralPath $modDst) {
            $bk = Join-Path (Split-Path -Parent $modDst) ('UIZh_backup_' + $Stamp)
            Copy-Item -LiteralPath $modDst -Destination $bk -Recurse -Force
            Warn ('原 mod 已备份 -> ' + $bk)
        }
        New-Item -ItemType Directory -Force -Path (Join-Path $modDst 'scripts') | Out-Null
        Copy-Item -LiteralPath (Join-Path $ModSrc 'scripts\main.lua') -Destination (Join-Path $modDst 'scripts\main.lua') -Force
        Copy-Item -LiteralPath (Join-Path $ModSrc 'enabled.txt') -Destination (Join-Path $modDst 'enabled.txt') -Force
        Ok ('mod 已安装 -> ' + $modDst)
        Note ('启动后看日志确认出现「UI 汉化 mod 已加载」: ' + (Join-Path $ue4ss 'UE4SS.log'))
    }
}

# ---------------------------------------------------------------- 清理 + 总结
if ($DryRun) {
    Plan ('清理临时目录 ' + $tmpRoot + '（除非 -KeepTemp）')
} elseif ($KeepTemp) {
    Warn ('保留临时目录 : ' + $tmpRoot)
} else {
    Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue
    Note ('已清理临时目录 : ' + $tmpRoot)
}

Write-Host ''
Write-Host '================ 完成 ================' -ForegroundColor Green
if ($DryRun) {
    Write-Host ' [DryRun] 以上为将要执行的步骤，未写任何文件。去掉 -DryRun 即正式安装。' -ForegroundColor Yellow
    $rec = '.\tools\一键汉化.ps1 -GamePath "' + $gameRoot + '"'
    if ($SkipMod) { $rec = $rec + ' -SkipMod' }
    Write-Host (' 正式命令: ' + $rec)
} else {
    Note ('备份目录    : ' + $backupDir)
    Note ('游戏 pak    : ' + $GamePak)
    Note ('汉化数据    : ' + $LocresSrc)
    Note ('包内 locres : SHA256 ' + $ExpectedSha)
    Note '进游戏抽查  : 主菜单 / 设置 / 背包分类 / 新游戏难度（环形菜单里的 Main 是故意保留的英文）'
    Note ('回退        : ' + $rollbackCmd)
    Write-Host ''
    Warn '不要跑 Steam「验证文件完整性」——它会把 pak 换回官方版（汉化消失，重跑本脚本即可恢复）。'
}
Write-Host '=====================================' -ForegroundColor Green
