# 主线方案：静态对话 + UI 汉化（完整技术细节）

> 2026-10 实机验证通过：普通攻击 / 跑动攻击 / 环形菜单功能全部正常，对话与 UI 均为中文。
> 本文是主线的权威技术文档；旧机器路线与旧结论见 `docs/archive/`（其中「变长必卡死」已被证伪）。

---

## 0. 一句话结论

- **对话层**：MSL 资产可以**变长**改写（UTF-16），只要（a）保留原 Zen 头只改导出长度 int32、（b）用 `zh_safe.json` 安全译文集、（c）**完整重建容器并带回原 ContainerHeader + container_id**。
- **UI 层**：locres 注入（`(空ns, GUID) → 中文`）即可覆盖 UMG 内联 FText，蓝图零改动；**但 1,422 条逻辑键必须保持英文**，否则攻击/环形菜单/存档等功能会坏。
- **静态边界**：无本地化键的字面量 FText（`Points Available:`、物品提示属性名、解锁形态弹窗等）locres 覆盖不到，需控件资产补丁或运行时钩子。

---

## 1. 环境事实（本 build）

| 项 | 值 |
|---|---|
| 游戏 | Carnal Instinct，Steam appid 1495320，UE 5.5 Shipping，buildid 25690079 |
| 对话文本 | 游戏自研 MSL_Toolkit：`Content/MSL_Toolkit/localization_system/language_data/en/`（249 对话资产） |
| 对话容器 | `Content\Paks\pakchunk1013-Windows.utoc/.ucas`（AES-256-ECB + Oodle） |
| UI locres | **`pakchunk0-Windows.pak`** 内 `Carnal_Instinct_UE5/Content/Localization/Game/en/Game.locres`（原版 1,198 条） |
| UI 字体 | `pakchunk1009-Windows.pak` 内 HQUI 字体族；中文靠引擎 CJK 回退，实测正常 |
| MSL 字体 | `pakchunk1013-Windows.pak` 内 5 个 roboto `.ufont`（原版，未动） |
| 工具 | `retoc`（IoStore/Zen）、`repak`（legacy pak）、`oo2core_9_win64.dll`；Python 3.10+ |

> ⚠️ 旧机器 build 的 locres 在 `pakchunk1013.pak`（39MB，含字体），本机在 `pakchunk0.pak`（13.8MB，1013.pak 只有 343KB 字体）。**不能假设 build 相同**。

### 1.1 容器结构要点

- `.utoc` 头部 144B；段序：chunk_ids → chunk_offset_lengths → perfect_hash → compression_blocks → compression_methods → signatures → directory_index → chunk_metas(24B/条)
- 块压缩：读 align16(csz) → AES-256-ECB 解密 → 取前 csz → Oodle 解压（out_size 必须恰等于 usz）
- `chunk_metas` 20B 哈希 = blake3(chunk 解压后完整内容)[:20]
- **重建容器必须保留原 `ContainerHeader` chunk，并把 TOC 的 `container_id` 改回原值**（ContainerHeader chunk id = container_id + `0000` + type `06`）；否则 `packages:0`，引擎不会加载补丁容器

### 1.2 chunk 与 uexp

```
chunk = [Zen 头 H 字节][导出数据 uexp][4 字节 PACKAGE_FILE_TAG = C1 83 2A 9E]
H = chunk[4:8]（小端 int32）
头部里恰好有一个 4 字节对齐的 int32 == len(导出数据)（即 SerialSize），改长度时只改它
```

### 1.3 字符串编码

- **负长度前缀 = UTF-16LE**：中文唯一正确写法；
- 正长度前缀 = ANSI：引擎实际按 UTF-8 解码，写 CP936 必乱码（旧版踩过）。

---

## 2. 对话方案（pakchunk1013 完整重建）

### 2.1 步骤

1. `retoc -a <key> unpack-raw pakchunk1013-Windows.utoc build/zenmod-work/pakchunk1013-Windows`（293 个 raw chunk）；
2. 用 `data/dialogue_zh_safe.json`（249 资产 / 9,092 条）定位每条文本 FString，改写为 UTF-16（负长度前缀）；
   - 只改 **inline FText 文本值**（该串后紧跟 32 位 hex GUID 键）与**三段式表格的文本段**（前串以 `_line_text` 结尾）；
   - 排除 sheet 名/内部查找键（`Mehlva_+_Havar_-_Sheet1`、`dynsex_reply_1_line_text` 等）和二进制误判条目；
3. 每个改写 chunk：只更新头部里那个 `int32 == len(导出数据)`，其余头部字节逐字节保留；
4. 未改写的 44 个 chunk 逐字节复制；
5. `retoc pack-raw` 重建**完整容器**（293 chunk，含原 ContainerHeader），再把容器 TOC `container_id` 改回 `0xf7353bd047c79eb2`；
6. 离线复核：
   - `chunk 文件 293（应为 293）`；
   - 249 个改写 chunk 的头部差异**只允许 1 个 int32**；
   - 未改写 chunk 与原包逐字节相同；
   - 回读中文串 ≈ 9,092 条、chunk ID 与原包一致；
   - `retoc verify` 通过。

### 2.2 失败路线为何失败（旧结论纠正）

| 旧做法 | 失败原因 |
|---|---|
| 变长后重排容器块表 | 块表/偏移不一致，引擎读取越界 → 卡死 |
| 只改 chunk 长度数值（v7） | 容器本身还是旧布局、且没重建 ContainerHeader → 引擎不可见/崩溃 |
| 全量 zh.json | 含二进制误判条目（如 sarratu@8934）→ 改坏非文本结构 → 崩溃 |
| ANSI/CP936 写中文 | 引擎按 UTF-8 解码 → 乱码 |

### 2.3 产物

`pakchunk1013-Windows.utoc`（30,276 B）/ `.ucas`（3,742,023 B），替换游戏同名文件。

---

## 3. UI 方案（locres 注入 pakchunk0.pak）

### 3.1 原理

UMG 蓝图里的内联 FText = `(空 namespace + 32 位 hex GUID key + 英文原文)`。
运行时 FText **先查 locres**、查不到才回落内联英文。因此注入 `(空ns, GUID) → 中文` 即可覆盖 UI 文本，蓝图零改动。

### 3.2 数据源与保护

- 上游：`data/Game.locres.fix1`（14,106 条，第三方社区成品，SHA256 `85F28F91…2CDC`）；
- 保护：`data/protect_list.json`（1,422 条逻辑键，见 §4）——生成时把这些键的值回退英文；
- 产物：`data/Game.locres.v7b_save_stat`（14,106 条：中文 12,632 条 + 英文 1,472 条[含数字/符号与保护键]）。

生成命令：

```powershell
python tools\mainline\build_protected_locres.py `
  --fix1 data\Game.locres.fix1 --protect data\protect_list.json `
  --out data\Game.locres.mainline
```

### 3.3 注入 pak

```powershell
python tools\mainline\build_ui_pak.py `
  --locres data\Game.locres.mainline --out-pak work\pakchunk0-Windows.mainline.pak
```

重打包参数必须与原 pak 一致：`mount point = ../../../`、`--version V11`、`--compression Oodle`、
`-p <原 pak 的 path hash seed>`（本 build 为 `0x464517FC` = 1178933244）。
repak 产物是**未加密 index**，实测引擎可正常加载。

四项离线复核全部通过才部署：
1. 解包后文件清单一致（1,715 个）；
2. 除 locres 外 1,714 个文件逐字节相同；
3. 包内 locres SHA256 == 输入 locres；
4. `repak info` 的版本/压缩/seed 与原 pak 一致。

> 打包非确定性：等价性判断看「包内 locres 的 SHA256」，不要看 pak 的 SHA。

---

## 4. 禁翻规则（1,422 条保护，翻必坏功能）

**原则：显示文本可能被代码反读回来当逻辑键/做字符串比较的，必须保持英文。**

| 类别 | 规模 | 失效表现 | 证据 |
|---|---|---|---|
| 全部 UserDefinedEnum 显示名 | 189 资产 / 1,189 条 | 站定普通攻击失效（跑动攻击正常） | `E_InputBufferKey.LightAttack`、`E_MontageAction.LightAttack`、`E_CombatType.Melee/Unarmed`、`E_State` 等被翻后攻击判定链断 |
| 环形菜单 `DT_Menu` + `E_Menus` | 138 + 3 条 | 环形菜单失效 | `AC_RadialMenu`/`W_Menu`/`W_MenuItem` 内有 `Conv_TextToString` + `EqualEqual_StrStr` + `SwitchString` |
| 文本逻辑资产内文本 | 80 资产 / 92 条 | 不定（取决于资产） | 资产 Zen 头部出现 `Conv_TextToString` / `EqualEqual_TextText` / `NotEqual_TextText` / `TextIsEmpty` / `GetDisplayNameTextByValue`；典型 `W_MenuItem` 的 `Display Name`/`Description` 占位文本 |

**注意：显示型枚举可以翻**——`E_SaveType`（手动存档/自动保存/快速保存/检查点）、`E_StatType`（活力/耐久/力量…）实测放开后功能正常，已包含在主线 locres 中。

### 4.1 识别方法（可复现）

1. 全库解包：`retoc -a <key> unpack-raw` 全部 12 个容器（约 13.4GB，56,943 资产）；
2. `tools/mainline/scan_text_logic.py`：遍历 raw chunk，检查 Zen 头部是否含文本比较函数名 → `scan_report.json`（逻辑资产清单 + extra 建议保护键）+ `asset_ftexts.json`（FText 键→资产映射）；
3. `tools/mainline/protect_all_enums.py`：按路径模式识别枚举资产（`/Enums/`、`/Enumerations/`、`/09_enums/`、`E_*`、`enum_*`）→ `enum_all.json`；
   - **不能只匹配 `/Enums/`**：实测会漏 100+ 个枚举（`/Enumerations/`、`/09_enums/` 等），本项目曾因此漏掉战斗枚举、多排查一轮；
4. 合并保护集 → `protect_list.json` → `build_protected_locres.py` 应用到 locres。

### 4.2 实测失效顺序（排错记录）

| 版本 | 内容 | 结果 |
|---|---|---|
| route-E（`Game.locres.full`，2,065 条） | 仓库实测安全集 | ✅ 功能正常，UI 部分中文 |
| fix1 全量（14,106 条） | 第三方成品 | ❌ 环形菜单 + 普通攻击失效 |
| V1：保护 `E_Menus` 3 条 | | ❌ 仍失效 |
| V4：+ 81 个 `/Enums/` 枚举 + `DT_Menu` | | ⚠️ 环形菜单恢复；攻击仍失效 |
| V5：+ 80 个逻辑资产内 92 条 | | ⚠️ 攻击仍失效 |
| V6：+ 补齐 `/Enumerations/`、`/09_enums/` 等 108 个漏掉的枚举（共 1,472 条保护） | | ✅ 功能全部正常 |
| V7：再放开 `DT_Menu`(138) + `E_SaveType`(4) + `E_StatType`(46) | | ❌ 环形菜单失效（`DT_Menu` 确认是逻辑键） |
| **V7b（主线）**：V6 + 放开 `E_SaveType`/`E_StatType`，`DT_Menu` 继续保护 | | ✅ **功能全部正常**（1,422 条保护） |

---

## 5. 静态方案的边界（已知未覆盖）

| 类型 | 例子 | 为什么静态 locres 覆盖不到 | 可行后续 |
|---|---|---|---|
| 字面量 FText | `Points Available:`、物品提示属性名（`Physical Damage`/`Critical Damage Multiplier`）、解锁形态弹窗（`UNLOCK "{0}" FORM?`） | flags `0x1FF`、history=0、**没有 namespace/GUID 键**，是控件里的字面量/非本地化文本 | 控件资产字面量补丁（改 FString 长度 + 重建对应容器，风险中等）；或 UE4SS SetText 钩子 |
| 环形菜单标签/描述 | `SORCERY`/`FISHING`/`TORCH` 等 | `DT_Menu` 是逻辑键（§4） | 只能用运行时钩子翻显示层 |
| Slate 渲染层 | 属性页部分标签 | 不经 UMG SetText、不在 FText 属性里 | C++/UE4SS Slate 钩子 |
| 形态种族描述 | `pakchunk1014` DataTable 约 10 段 | 待补 | 同 locres 注入或容器补丁 |

---

## 6. 部署与回滚

部署文件（游戏 `Content\Paks\`）：

| 文件 | 说明 |
|---|---|
| `pakchunk0-Windows.pak` | UI locres 汉化版 |
| `pakchunk1013-Windows.utoc` / `.ucas` | 对话汉化容器 |

回滚：恢复同名备份文件即可。
Steam「验证文件完整性」会还原官方文件（汉化消失，重跑构建即可恢复）。

---

## 7. 复现清单（命令汇总）

```powershell
# 0) 备份游戏 Paks 下 3 个文件；确保游戏完全退出

# 1) 全库解包（扫描/枚举识别需要；一次性）
foreach ($n in @('pakchunk0','pakchunk1001',...)) { retoc -a <key> unpack-raw "<Paks>\$n-Windows.utoc" "asset-scan\$n" }

# 2) 扫描 + 枚举识别
python tools\mainline\scan_text_logic.py   # 产出 scan_report.json / asset_ftexts.json
python tools\mainline\protect_all_enums.py --scan-dir asset-scan --out-json enum_all.json

# 3) 生成 UI locres（用仓库已整理好的 protect_list.json 可直接跳过 2）
python tools\mainline\build_protected_locres.py --fix1 data\Game.locres.fix1 --protect data\protect_list.json --out data\Game.locres.mainline
python tools\mainline\build_ui_pak.py --locres data\Game.locres.mainline --out-pak work\pakchunk0-Windows.mainline.pak

# 4) 对话容器
python tools\mainline\build_zenmod_safe.py --full-1013

# 5) 覆盖部署 + 进游戏验证（攻击 / 跑动攻击 / 环形菜单 / 存档 / 属性 / 对话）
```

---

## 8. 统计与校验值

| 项 | 值 |
|---|---|
| UI locres 条目 | 14,106（中文 12,632 + 英文 1,472，其中保护键 1,422） |
| 保护键分类 | 枚举显示名 1,189 / `DT_Menu`+`E_Menus` 141 / 文本逻辑资产 92 |
| 对话译文 | 249 资产 / 9,092 条（`data/dialogue_zh_safe.json`） |
| 扫描规模 | 12 容器 / 56,943 资产 / 9,730 个含文本 / 80 个逻辑资产 / 189 个枚举资产 |
| 上游 locres SHA256 | `85F28F91088C263675E6A23DE0CBB38E4749FE86E460D1552349590B0F522CDC` |
