# Carnal Instinct 简体中文汉化补丁

> 运行时（UE4SS Lua mod）+ 数据表补丁，覆盖游戏内**大部分界面文本**。
> 本仓库**不包含任何游戏原始资产**，只包含翻译成果与可复现脚本 —— 使用者需自备正版游戏。

---

## 一、当前汉化覆盖

| 内容 | 机制 | 表现 |
|---|---|---|
| 主菜单、设置菜单、按钮、提示、通知等「主动设置文本」的控件 | **UE4SS Lua SetText hook** | 直接中文、**不闪烁**、零性能开销 |
| 对话、任务文本、部分界面 | MSL 文本表（游戏自研本地化系统） | 中文 |
| 物品 / 技能 / 属性 / 术语 | DataTable 容器补丁 | 中文 |
| 中文字形 | 字体包 | 正常 |

**尚未覆盖**（原因已定位，详见 `docs/技术报告.md`）：

- 角色属性页标签（`Arcana` / `Presence` / `Crit Damage` …）
- 物品提示里的属性名（`Fire Resistance`）与物品名/品类（`SOBEK STATUETTE` / `Junk`）

这两类文本**只存在于 Slate 渲染层**：既不经过 UMG 的 `TextBlock:SetText`，也不存在于 UMG 的 FText 属性中。
要覆盖它们必须写 UE4SS 的 **Slate 层 C++ mod**（hook `STextBlock::SetText`），属工程级投入。

---

## 二、快速安装（3 步）

前置：游戏已装好 UE4SS（注入代理 `dwmapi.dll` 与 `ue4ss/` 目录位于 `Binaries/Win64/`）。

```powershell
# 1) 安装（会自动备份已有 mod）
.\tools\install_mod.ps1 -GamePath "K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5"

# 2) 启动游戏，日志出现「UI 汉化 mod 已加载」即成功
#    日志位置：<游戏>\Binaries\Win64\ue4ss\UE4SS.log

# 3) 回退
.\tools\uninstall_mod.ps1 -GamePath "<同上>"
```

---

## 三、目录结构

```
mod/UIZh/                  运行时可挂载的 mod（scripts/main.lua + enabled.txt）
data/glossary.csv          词条表（原文,译文）—— 2107 条，可复用于其他工具
data/dt_jobs.json          数据表补丁替换数据（英文→中文，按资产分组）
data/meta.json             本包统计与校验值
tools/install_mod.ps1      一键安装 / 备份
tools/uninstall_mod.ps1    一键回退
tools/patch_containers.py  在**你自己的**游戏容器上原地打数据表补丁
docs/技术报告.md            技术结论与实证（含已证伪路线，避免重复踩坑）
docs/复现指南.md            从零复现当前汉化状态的完整步骤
```

---

## 四、关键依赖

| 依赖 | 版本 / 说明 |
|---|---|
| UE4SS | `v3.0.1-1176-g1ba38db4`（官方最新 experimental，已实测可在 UE5.5 Shipping 注入） |
| 游戏 | Carnal Instinct（UE 5.5 Shipping） |
| Python | 3.10+（容器补丁脚本） |
| retoc / repak | 容器解包与打包（仅打数据表补丁时需要） |

---

## 五、合规声明

- 本仓库**不含**任何游戏原始文件（`.ucas` / `.utoc` / `.pak` / 游戏资产）。
- 所有脚本都在**使用者本地的正版游戏文件**上运行，产物仅供个人使用。
- 翻译成果为本项目所有；若分发字体请遵循其原始许可（如 Noto Sans SC，SIL OFL 1.1）。
- 请勿将本仓库与游戏本体打包分发。

---

## 六、许可

本仓库的**脚本与翻译文本**采用 MIT 许可（见 `LICENSE`）。
游戏《Carnal Instinct》的一切权利归其开发者所有。
