# Carnal Instinct 简体中文汉化补丁（静态主线）

> 目标游戏：**Carnal Instinct**（Steam appid `1495320`，Unreal Engine 5.5）
> 验证环境：Steam 正版 buildid `25690079`（2026-10 实测）
> 方案性质：**纯静态**——只替换游戏容器/pak 内的文本资源，不依赖 UE4SS、不注入任何运行时代码。
> 仓库不含游戏原始资产，只包含**翻译成果、逻辑键保护清单与可复现脚本**；使用者需自备正版游戏。

---

## 一、这套方案做了什么（2026-10 主线）

两条静态通道：

| 层 | 做法 | 规模 | 产物 |
|---|---|---|---|
| **NPC 对话**（MSL_Toolkit） | 解包 `pakchunk1013` 的 raw Zen chunk → 文本改 UTF-16 中文（允许变长）→ 完整重建容器（保留原 `ContainerHeader`、`container_id` 改回原值）→ 替换 `.utoc/.ucas` | 249 资产 / **9,092 条** | `pakchunk1013-Windows.utoc/.ucas` |
| **UI 文本**（UMG 内联 FText） | 向 `pakchunk0.pak` 内的 `Game.locres` 注入 `(空ns, 32hex GUID) → 中文`；脚本按原参数重打包 | 14,106 条中 **12,632 条中文**；**1,422 条逻辑键保持英文** | `pakchunk0-Windows.pak` |

字体：**不替换**，依赖引擎自带 CJK 回退（实测正常）。

> ⚠️ 不同 build 的容器布局可能不同：本 build 的 `Game.locres` 在 **`pakchunk0.pak`**；
> 旧机器（另一 build）在 `pakchunk1013.pak`。使用前先确认自己游戏里 locres 的实际位置。
> repak 重打包的 path hash seed 也**必须与你本机 pak 一致**（`repak info` 可读；本 build 为 `0x464517FC`）。

---

## 二、覆盖情况

**已汉化**：NPC 对话/任务对话、主菜单、设置菜单、按键设置、背包、物品名与描述、技能/法术、属性界面（属性名）、HUD、提示与通知、教程、存档界面（存档类型标签）、大部分物品提示文本。

**保持英文（有意为之，翻必坏）**：

- 全部 **UserDefinedEnum 显示名**（189 个枚举资产 / 1,189 条）——枚举显示名会被代码反读当逻辑键，典型：`E_InputBufferKey.LightAttack`、`E_CombatType.Melee`（翻了 → 站定普通攻击失效）；
- **环形菜单数据 `DT_Menu`**（138 条）+ `E_Menus`（3 条）——翻了 → 环形菜单失效（实测确认）；
- **80 个「文本参与逻辑比较」资产内的 92 条文本**（`Conv_TextToString` / `EqualEqual_TextText` 等，含 `W_MenuItem` 占位文本）。

完整名单见 [`data/protect_list.json`](data/protect_list.json)（1,422 条，含英文原文/分类/所属资产）。

**静态方案覆盖不到的（已知边界）**：

- **字面量 FText**（无本地化键、flags `0x1FF`）：如 `Points Available:`、物品提示属性名（`Physical Damage` 等）、解锁形态弹窗（`UNLOCK "{0}" FORM?`）。旧机器是靠 UE4SS 运行时 SetText 钩子翻的；纯静态需「控件资产字面量补丁」（可做，风险中等，尚未实施）；
- **Slate 渲染层文本**：角色属性页部分标签等，需 C++/运行时钩子；
- 形态界面约 10 段种族描述（`pakchunk1014` 的 DataTable，待补）。

---

## 三、安装

> 通用前提：**完全退出游戏**；先备份下面列出的文件；只替换列出的文件，不要动同目录其他容器。

### 方式 A：使用本地构建产物（推荐）

1. 备份游戏 `Content\Paks\` 下的：
   - `pakchunk0-Windows.pak`（UI）
   - `pakchunk1013-Windows.utoc` / `pakchunk1013-Windows.ucas`（对话）
2. 用本仓库脚本本地构建（见「四、自建」），得到：
   - `pakchunk0-Windows.pak`（UI 中文）
   - `pakchunk1013-Windows.utoc/.ucas`（对话中文）
3. 覆盖进游戏 `Paks` 目录，启动游戏验证。

### 方式 B：仓库维护者发布的 Release 补丁包（若提供）

按 Release 说明覆盖同样 3 个文件即可（非官方分发时请遵守游戏 EULA）。

### 回滚

把备份的 3 个文件复制回 `Paks` 目录即可恢复英文原版。
Steam「验证文件完整性」也会还原官方文件（汉化随之消失，重跑构建即可恢复）。

---

## 四、自建（从零复现）

前置：正版游戏、完全退出；`retoc`、`repak`、`oo2core_9_win64.dll`（Oodle，加入 PATH）、游戏 AES key、Python 3.10+。

### 1) 对话层

```powershell
# 解包原始 1013 容器（只需一次；输出 build/zenmod-work/pakchunk1013-Windows）
retoc -a <AES_KEY> unpack-raw <Paks>\pakchunk1013-Windows.utoc work\zen1013

# 用译文重建完整容器（脚本内路径按本机修改）
python tools\mainline\build_zenmod_safe.py --full-1013
# 产物：pakchunk1013-Windows.utoc/.ucas（已离线复核：chunk 293 / 头部保真 / retoc verify）
```

关键点：保留原 Zen 头、只改「导出数据长度」一个 int32；中文写 UTF-16；**必须带上原 `ContainerHeader` chunk，并把 TOC `container_id` 改回原值**（否则引擎 `packages:0` 看不见容器）。

### 2) UI 层

```powershell
# 生成最终 locres（把保护清单里的 1,422 条回退英文）
python tools\mainline\build_protected_locres.py `
  --fix1 data\Game.locres.fix1 --protect data\protect_list.json `
  --out data\Game.locres.mainline

# 注入 pakchunk0.pak（脚本内路径按本机修改）
python tools\mainline\build_ui_pak.py `
  --locres data\Game.locres.mainline --out-pak work\pakchunk0-Windows.mainline.pak
```

`build_ui_pak.py` 会做四项离线复核（文件清单一致 / 除 locres 外逐字节相同 / 包内 locres SHA 一致 / pak 参数一致），全部通过才建议部署。
注意：打包是**非确定性**的——判断等价性看「包内 locres 的 SHA256」，不要看 pak 的 SHA256。

---

## 五、禁翻规则（重要，翻必坏功能）

**原则：显示文本可能被代码反读回来当逻辑键/做字符串比较的，必须保持英文。**

| 类别 | 规模 | 证据 |
|---|---|---|
| UserDefinedEnum 显示名 | 189 资产 / 1,189 条 | 翻了 → 站定普通攻击失效（`E_InputBufferKey.LightAttack`、`E_MontageAction`、`E_CombatType`、`E_State` 等） |
| 环形菜单 `DT_Menu` + `E_Menus` | 141 条 | `AC_RadialMenu`/`W_Menu`/`W_MenuItem` 内有 `Conv_TextToString`+`EqualEqual_StrStr`+`SwitchString`；翻了 → 环形菜单失效 |
| 文本逻辑资产内文本 | 80 资产 / 92 条 | 全库扫描：头部出现 `Conv_TextToString` / `EqualEqual_TextText` / `NotEqual_TextText` / `TextIsEmpty` / `GetDisplayNameTextByValue` |

识别脚本：`tools/mainline/scan_text_logic.py`（全库 raw chunk 扫描）+ `tools/mainline/protect_all_enums.py`（枚举识别）。

**坑**：枚举识别不能只匹配路径 `/Enums/`——`/Enumerations/`、`/09_enums/`、`ENUMS` 等目录同样有枚举（本项目曾漏 108 个，导致攻击 bug 多排查一轮）。

---

## 六、仓库结构

```
data/
  Game.locres.v7b_save_stat   最终主线 UI locres（14,106 条；12,632 中文 + 1,422 英文保护）
  dialogue_zh_safe.json       对话译文（249 资产 / 9,092 条，UTF-16 注入用）
  protect_list.json           1,422 条逻辑键保护清单（键/英文原文/分类/资产）
  Game.locres.fix1            上游第三方全量 locres（数据源，SHA256 85F28F91…2CDC）
  Game.locres.full            最保守安全基线（2,065 条，实测功能正常）
  glossary.csv / locres_…csv  术语表与对照表
docs/
  archive/                    历史文档（旧机器路线/旧结论，已标注归档）
  主线_对话+UI汉化方案.md       完整技术细节：原理/步骤/失效顺序/验证
  经验总结.md                  本次踩坑与排查方法论
tools/
  mainline/                   主线脚本（见该目录 README）
  archive/                    旧机器脚本（一键汉化/回退/UE4SS mod 等）
  locres_inject/              locres 读写库（v3 CityHash64_UTF16）
mod/UIZh/                     旧路线的 UE4SS Lua mod（历史，保留参考）
```

---

## 七、历史与致谢

- `docs/archive/` 保存了旧机器时期的全部结论与工具（等长路线、UE4SS 运行时 mod、`pakchunk1013.pak` 一键替换等）。其中「变长必卡死」等结论**已被证伪**，真实原因是：容器重建缺少 `ContainerHeader`、译文混入二进制误判条目、编码错误三条（详见主线文档）。
- UI locres 数据源来自社区第三方 locres（`data/Game.locres.fix1`）；本仓库在其基础上修复了逻辑键保护，并把方案整理为可复现脚本。
- 本项目仅包含翻译文本与工具，**不包含游戏原始资产**。请支持正版。

## 八、合规声明与许可

- 本仓库**不含**任何未修改的游戏原始文件（`.ucas` / `.utoc` / `.pak` / 原始游戏资产）。
  `data/Game.locres.*` 是本项目修改过的本地化数据（翻译成果），不含游戏其他内容。
- 所有脚本都在**使用者本地的正版游戏文件**上运行，产物仅供个人使用；请勿将本仓库与游戏本体打包分发。
- 脚本与翻译文本采用 MIT 许可（见 [LICENSE](LICENSE) / [NOTICE.md](NOTICE.md)）；游戏《Carnal Instinct》的一切权利归其开发者所有。
