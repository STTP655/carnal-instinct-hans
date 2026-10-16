# Carnal Instinct 简体中文汉化补丁

> 三条通道并行：**locres 注入**（UI 蓝图内联文本，不依赖 mod）+ 运行时 UE4SS Lua mod + 数据表补丁，覆盖游戏内**绝大部分界面文本**。
> 本仓库**不包含任何游戏原始资产**，只包含翻译成果与可复现脚本 —— 使用者需自备正版游戏。

---

## 一、当前汉化覆盖

| 内容 | 机制 | 表现 |
|---|---|---|
| 主菜单、设置菜单、按钮、提示、通知等「主动设置文本」的控件 | **UE4SS Lua SetText hook** | 直接中文、**不闪烁**、零性能开销、**实测稳定** |
| 对话、任务文本、部分界面 | MSL 文本表（游戏自研本地化系统） | 中文 |
| 物品 / 技能 / 属性 / 术语 | DataTable 容器补丁 | 中文 |
| 中文字形 | 字体包 | 正常 |
| 蓝图内联文本 + 菜单/框架级文本（**14,106 条**：主菜单 / 设置 / 背包 / 属性等） | **locres 注入**（`data/Game.locres.fix1`，蓝图零改动） | 中文 |

**尚未覆盖**（原因已定位，详见 `docs/技术报告.md` 与 `docs/路线E_UI扫描报告.md`）：

- **Slate 渲染层文本**：角色属性页标签（`Arcana` / `Presence` / `Crit Damage` …）、物品提示里的属性名（`Fire Resistance`）与部分物品名/品类。它们既不经过 UMG 的 `TextBlock:SetText`，也不存在于 UMG 的 FText 属性中，需写 UE4SS **Slate 层 C++ mod**（hook `STextBlock::SetText`），属工程级投入；
- 形态界面约 10 段种族描述（位于 pakchunk1014 的 DataTable，待确认是否同样可走 locres 注入）；
- 103 条疑似裸展示字符串（多在未挂载的旧模板里，待人工确认）。

---

## 二、快速安装

> 汉化机制 = 把 `data\Game.locres.fix1`（14,106 条中文）注入你自己游戏的
> `pakchunk1013-Windows.pak` 内的 `Carnal_Instinct_UE5/Content/Localization/Game/en/Game.locres`，
> pak 内其余文件原样保留；**只写 `.pak` 这一个文件，绝不碰同目录的 `.utoc` / `.ucas`**。

### 方式一：一键脚本（推荐）

前置：**完全退出游戏**（脚本会检测 `Carnal*` 进程）；备好 [repak](https://github.com/trumank/repak)
（放到 `tools\repak\repak.exe`，或用 `-RepakPath` 指定）。

```powershell
$G = "K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5"

# 1) 先干跑：只做只读检查并打印将要执行的每一步，不写任何文件
.\tools\一键汉化.ps1 -GamePath $G -DryRun

# 2) 正式安装：备份 -> 注入 locres -> 复核 -> 覆盖 -> 可选装 mod
.\tools\一键汉化.ps1 -GamePath $G

# 3) 回退：从 tools\backup\<时间戳>\ 还原原版 pak（多个备份时按提示选序号）
.\tools\回退汉化.ps1 -GamePath $G
```

脚本做的事：检测游戏进程 → 探测 repak → 校验 `data\Game.locres.fix1` 的 SHA256 →
备份当前 pak 到 `tools\backup\<时间戳>\`（含 `backup.json`）→ 解包游戏 pak → **只**替换其中的
`Game.locres` → 按原参数重新打包（`-m "../../../" --version V11 --compression Oodle -p 1048239905`）→
解包复核新 pak（文件清单与游戏原 pak 一致 / 除 locres 外逐字节相同 / 包内 locres SHA256 相符）→
覆盖游戏 pak → 可选安装 `UIZh` mod（没装 UE4SS 则跳过并提示）→ 清理临时目录。

常用参数：`-SkipMod`（只注 locres、不装 mod）、`-RepakPath`、`-BackupRoot`、`-KeepTemp`；
回退脚本：`-Latest`（直接用最新备份）、`-RemoveMod`（移走 mod 目录，默认只把 `enabled.txt` 改名关闭）。

> 打包是**非确定性**的（每次 pak 的 SHA256 都不同），所以校验口径是**解包后 locres 的 SHA256**
> 必须等于 `85F28F91…2CDC`，不要拿 pak 的哈希判等。

### 方式二：手动（简述）

不跑脚本、自己动手时，核心只有一步：用 repak 把 `data\Game.locres.fix1` 替换进
`pakchunk1013-Windows.pak` 内的 `Carnal_Instinct_UE5/Content/Localization/Game/en/Game.locres`，
再用原参数打包回去（完整命令见 `tools\locres_inject\README.md`）。这样**不装任何 mod**，
全部静态 UI 文本（菜单 / 设置 / 背包 / 属性等）即为中文——即纯净版。想再覆盖运行时动态文本，
装好 UE4SS（`Binaries/Win64/` 下放注入代理 `dwmapi.dll` 与 `ue4ss/`）后跑：

```powershell
.\tools\install_mod.ps1   -GamePath $G   # 装 mod（自动备份已有 mod）
.\tools\uninstall_mod.ps1 -GamePath $G   # 撤 mod
```

启动游戏后看日志确认出现「UI 汉化 mod 已加载」：`<游戏>\Binaries\Win64\ue4ss\UE4SS.log`。

---

## 三、目录结构

```
mod/UIZh/                  运行时可挂载的 mod（scripts/main.lua + enabled.txt）
data/glossary.csv          词条表（原文,译文）—— 2107 条，可复用于其他工具
data/dt_jobs.json          数据表补丁替换数据（英文→中文，按资产分组）
data/meta.json             本包统计与校验值
data/Game.locres.fix1      一键脚本用的 locres 注入成品（14,106 条；环形菜单修复版）
data/Game.locres.full      上一代 locres 注入成品（2065 条，留档）
data/locres_全量翻译对照表.csv  全部注入条目的 key/原文/译文对照（审校用）
tools/一键汉化.ps1          一键安装（备份 → 注入 locres → 复核 → 覆盖 → 可选装 mod，支持 -DryRun）
tools/回退汉化.ps1          一键回退（从 tools/backup/<时间戳>/ 还原原版 pak、关闭/移除 mod）
tools/install_mod.ps1       只装 mod / 备份（手动模式用）
tools/uninstall_mod.ps1     只撤 mod（手动模式用）
tools/patch_containers.py  在**你自己的**游戏容器上原地打数据表补丁
tools/locres_inject/       路线 E 工具链：locres 读写 / 注入 / 验证 + 复现说明
汉化操作速查.md             AI agent 速查：两处目录 / 三条通道 / 证伪清单 / 常见任务 / 铁律
docs/技术报告.md            技术结论与实证（含已证伪路线，避免重复踩坑）
docs/路线E_UI扫描报告.md     WB_* 蓝图文本全解析报告（结构、假阳性规避、基线）
docs/复现指南.md            从零复现当前汉化状态的完整步骤
接力文档.md                项目交接文档（新会话先读这一份）
```

---

## 四、关键依赖

| 依赖 | 版本 / 说明 |
|---|---|
| UE4SS | `v3.0.1-1176-g1ba38db4`（官方最新 experimental，已实测可在 UE5.5 Shipping 注入） |
| 游戏 | Carnal Instinct（UE 5.5 Shipping） |
| Python | 3.10+（容器补丁脚本） |
| retoc / repak | 容器 / pak 解包与打包（打数据表补丁、注入 locres 时需要） |

---

## 稳定性（重要）

本补丁**只使用 SetText hook 通道**。

- ✅ hook 改参数：实测 16000+ 次调用零崩溃，属性绑定也生效；
- ❌ 轮询批量写入：实测会导致 `EXCEPTION_ACCESS_VIOLATION`（三次对照实验），已永久关闭；
- ❌ 用 Lua 遍历/写入 UObject 属性：会导致崩溃，**任何扩展都不要这样做**。

详见 `docs/技术报告.md` 第七节。

---

## 五、合规声明

- 本仓库**不含**任何未修改的游戏原始文件（`.ucas` / `.utoc` / `.pak` / 原始游戏资产）。
  `data/Game.locres.fix1`、`data/Game.locres.full` 是本项目修改过的本地化数据（翻译成果），不包含游戏其他内容。
- 所有脚本都在**使用者本地的正版游戏文件**上运行，产物仅供个人使用。
- 翻译成果为本项目所有；若分发字体请遵循其原始许可（如 Noto Sans SC，SIL OFL 1.1）。
- 请勿将本仓库与游戏本体打包分发。

---

## 六、许可

本仓库的**脚本与翻译文本**采用 MIT 许可（见 `LICENSE`）。
游戏《Carnal Instinct》的一切权利归其开发者所有。
