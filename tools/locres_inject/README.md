# 路线 E 全量铺开 —— 全量 locres + 全量 pak 与安装说明

> 生成时间：2026-10-16（Asia/Shanghai）
> 目录：`D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment\`
> 状态：**全量 pak 已生成并通过三重验证，尚未安装**（安装由人工执行，见第 4 节）
> 前置结论（来自前两批实验）：向 `Game.locres` 注入 `(Namespace="", Key=32hex GUID)` 中文条目
> **能覆盖 UI 蓝图内联 FText**（主菜单 New Game / Settings / Lovense / Credits 四个新增条目实测全部变中文）。

---

## 1. 这次做了什么（一句话）

把 `dist.json` **baseline**（= 游戏实际运行的原版 `tolegacy_orig`）里**全部家族 A 内联 FText**
（空 Namespace + 32 位十六进制 GUID Key）提取出来，去重翻译后写进 `Game.locres`，
再按原参数重打包成新的 `pakchunk1013-Windows.pak`。**一个蓝图字节都没碰，只动 .pak。**

```
dist.json (baseline)  →  full_terms.json  →  inject_full.py  →  Game.locres.full  →  repak  →  pakchunk1013-Windows.full.pak
   1246 key / 882 src      1120 terms         locres_lib 注入      2065 条                  V11/Oodle/seed 同原版
```

---

## 2. 覆盖统计

| 项 | 数字 | 说明 |
|---|---|---|
| baseline 家族 A key 总数 | **1246** | `dist.json.baseline.keys` 中 `ns==""` 且 key 为 32hex GUID；与 primary **key 集合完全相同**（147 条仅因 P0/P1 补丁改了源串而不同） |
| 去重后的唯一源串（src） | **882** | 同名英文串被多个 key 复用 |
| 词表命中（直接复用 main.lua 译文） | **740** 个 src | 精确 712 + 归一化匹配 25 + 去首尾空格 2 + 归一化+保留原文换行 1 |
| 本次新翻 | **79** 个 src | 我逐条翻译；落到 **96 条 key** |
| SKIP（不注入） | **63** 个 src / **126** 条 key | 纯数字、纯符号、品牌/缩写（NPC、FXAA、FG、FPS 数值档位、装饰线、占位乱码 `fsdfsfsfsfdfsfsdfdsd` 等），保留内联原文，显示与原文一致 |
| **实际注入 terms** | **1120** 条 key | = 1246 − 126 |
| 注入动作 | **新增 867 / 更新 6 / 保留已有中文 247** | 见第 8 节的口径说明 |
| locres 条目数 | **1198 → 2065**（+867） | 更新不增数；旧条目 **零丢失** |
| locres 大小 | 84,968 → **139,559** 字节 | |
| locres 内中文条目 | **1904 / 2065** | 其余为数字/符号/品牌名（原样保留） |
| pak 大小 | 39,741,474（原版）→ **39,776,355** 字节 | 仍只有 6 个条目 |

> baseline 与 primary 的 key 集合一致、147 条 src 不同 —— 这 147 条正是上一轮 P0/P1 补丁把内联
> `SourceString` 等长替换成中文的那些 key。**游戏运行的是原版，所以本次一律以 baseline 为准**，
> 147 条按原版英文重新翻译（不是拿补丁里的中文）。

---

## 3. 产物与校验值

| 文件 | 说明 |
|---|---|
| `out\pakchunk1013-Windows.full.pak` | **全量 pak（要装的就是它）**，39,776,355 字节 |
| `out\Game.locres.full` | 注入后的全量 locres（2065 条，139,559 字节） |
| `out\full_terms.json` | 1120 条注入清单（key/src/zh/来源/资产） |
| `out\full_srcs.json` | baseline 1246 条逐条明细 + 882 条去重 src 明细 |
| `out\全量翻译对照表.csv` | **审校用**：1246 行（含 126 行 SKIP），UTF-8 BOM |
| `out\overlap_detail.csv` | 注入前已在 locres 的 253 条现状（现值/本次译文/动作） |
| `out\inject_report_full.json` | 注入报告（每条 key 的 hash、动作、资产、export） |
| `out\inject_full.log` / `out\verify_full.log` | 注入与验证的完整输出 |
| `out\repak_list_full.txt` / `out\repak_info_full.txt` | 全量 pak 的清单与参数（与原版一致） |
| `new_translations.json` | 我新翻的 79 条 + SKIP 名单（可复核/覆盖） |
| `full_extract.py` / `build_full_terms.py` / `inject_full.py` / `export_full_csv.py` / `verify_full.py` | 本次全流程脚本（可重跑） |
| `probe_baseline.py` / `probe_overlap.py` / `analyze_kept.py` / `analyze_mixed.py` / `check_translations.py` / `diag_srchash.py` | 本次只读探测/审校脚本（输出见 `out\*.log`） |
| `安装全量pak.ps1` | **一键安装**（新建；不改动上一轮的 `安装实验pak.ps1`） |
| `备份实验前.ps1` / `回退实验pak.ps1` | 沿用上一轮，逻辑不变 |

```
全量 pak       SHA256 = F3631A21CC5FEE80883F7E9AA71C70942680D257FDE1D0765E0EABB121217378
全量 locres    SHA256 = 494C262CDE3F3D80A2B3B19280690317CD211FFCA5B8F319163DAE59B032BB5C
注入前 locres  SHA256 = 666441784AF3F01EDAF195B0B204EC06A756989AD1059165F48D68A2F2D006D3（原版中文框架 locres）
原版 pak       SHA256 = C0AD6FF43BD90E3D714CEF1F35AFDFF78B6AAFDFB3E72CC781B2128144E8B6E6（回退基准）
第二批实验 pak SHA256 = 7AEE8E1E0E0EE08CC995B1E03D9E0FD3CCE6B6B024204E5F061D421D840B9007（已被本全量版取代）
```

**验证结果（`verify_full.py`，可重跑）**

```
[1] terms 1120 条 vs baseline：✓ key/src 逐字一致
[2] 全量 locres 自解析：139559 字节, version=3, 2065 条 → ✓ round-trip 逐字节一致
    旧条目 1198 条 → 丢失 0 条；新增 867 条（预期 867）✓；key hash 复核 0 条不符 ✓
[3] 逐条读回：add 867 / kept 247 / update 6；失败 0 条 ✓
[4] pak 解出的 locres SHA256 == 注入产物 SHA256 ✓；5 个 ufont 与原版逐字节一致 ✓
[5] pak 39,776,355 字节；repak list 6 条目、info = V11 / Oodle / seed 3E7ADF21 / mount ../../../ ✓
```

---

## 4. 安装步骤（照做即可）

> ⚠️ 先**完全退出游戏**（Steam 也建议退出）。脚本会检测 `Carnal*` 进程，运行中直接拒绝执行。

```powershell
powershell -File "D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment\安装全量pak.ps1"
```

脚本流程：

1. 校验 `out\pakchunk1013-Windows.full.pak` 的 SHA256 必须等于 `F3631A21…7378`（不符则中止）；
2. 调用 `备份实验前.ps1`（幂等）→ `03_原始备份\pakchunk1013-Windows.pak.locres实验前`；
3. 检测游戏进程；
4. 把 **`out\pakchunk1013-Windows.full.pak`** 复制成
   **`K:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5\Content\Paks\pakchunk1013-Windows.pak`**；
5. 复制后重新校验 SHA256 一致，并写 `out\installed.sha256`。

**只覆盖 `.pak` 这一个文件，绝不碰 `.utoc` / `.ucas`**（那是对话汉化容器，动了会毁掉 247 个文件的对话汉化）。

> 当前 K 盘状态（2026-10-16 03:49 只读核查）：游戏里那份 pak 是**第一批实验 pak**
> （39,741,510 字节，`A870A43D…5549`），备份是**原版**（`C0AD6FF4…B6E6`，有效未被覆盖）。
> 装全量版会直接覆盖第一批实验 pak——这是预期的，备份不受影响。

---

## 5. 进游戏看什么（抽查点）

全量铺开的意义就是"以前是英文的地方现在应该都是中文"。建议抽这几处（都来自 baseline 内联 FText）：

| 界面 | 资产 | 以前（英文） | 现在应显示 |
|---|---|---|---|
| 新游戏 · 难度 | `WB_T3_NewGame` | `Hard` | 困难 |
| 新游戏 · 开始 | `WB_T3_NewGame` | `Play` | 开始游戏 |
| 属性界面 | `WB_Stats_Main` | `Attribute Points` | 属性点 |
| 设置 · 色盲辅助 | `WB_T3_SettingsMenu` | `Deuteranopia` | 绿色盲 |
| 设置 · 各项说明 | `WB_T3_SettingsMenu` | `Adjusts the volume of the game's music.` | 调整游戏音乐的音量。 |
| 照片模式 | `WB_PhotoMode` | `TIME OF DAY` / `Save Screenshot` | 时间 / 保存截图 |
| 作弊菜单 | `WB_CheatMenu` | `TYPE ITEM FILTER` | 输入物品筛选 |
| 背包 | `WB_PlayerInventory` | `TORSO` / `OFFHANDS` | 躯干 / 副手 |
| 生殖器定制屏 | `WB_GenitalScreen` | `Aroused/Flaccid` / `Skin Select` | 勃起 / 疲软 / 皮肤选择 |
| 制作列表分类 | `WB_CraftingList` | `Swords` / `Hammers` / `Chestplates` | 剑 / 锤 / 胸甲 |
| 补丁说明 | `WB_PatchNotes` | `VERSION 2.5.5  /  FEBRUARY 2021` | 版本 2.5.5  /  2021年2月 |

**mod 要不要关？** 本次不必关：740 条与 `main.lua` 词表重合的文本已按词表译文写入 locres，
两者一致、不会互相打架。**只有想单独验证"locres 生效"时才需要关 mod**（`UIZh\enabled.txt` → `enabled.txt.off`）。

---

## 6. 回退步骤

```powershell
powershell -File "D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment\回退实验pak.ps1"
```

从 `03_原始备份\pakchunk1013-Windows.pak.locres实验前` 还原，并校验还原后 SHA256
（应为 `C0AD6FF43BD90E3D714CEF1F35AFDFF78B6AAFDFB3E72CC781B2128144E8B6E6`）。

`03_原始备份\pakchunk1013-Windows.pak.locres实验前` **不要删**，它是唯一退路。

---

## 7. 想重跑 / 改译文（复现命令）

```powershell
$py = "C:\Users\LY\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$EXP = "D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment"

# 1) 提取 + 统计（只读 dist.json / main.lua）
& $py "$EXP\full_extract.py"
# 2) 组装 terms（改 new_translations.json 里的译文后重跑即可）
& $py "$EXP\build_full_terms.py"
# 3) 注入（--overwrite-existing 可切换成"连已有中文也覆盖"）
& $py "$EXP\inject_full.py"
# 4) 生成对照表
& $py "$EXP\export_full_csv.py"
# 5) 放进打包源并重新打包（参数与原版 pak 完全一致）
Copy-Item -Force "$EXP\out\Game.locres.full" "$EXP\work\new_pak_src\Carnal_Instinct_UE5\Content\Localization\Game\en\Game.locres"
& "D:\DSH工作区\CarnalInstinct_汉化\02_工具\repak\repak.exe" pack "$EXP\work\new_pak_src" "$EXP\out\pakchunk1013-Windows.full.pak" -m "../../../" --version V11 --compression Oodle -p 1048239905
# 6) 解包 + 验证
& "D:\DSH工作区\CarnalInstinct_汉化\02_工具\repak\repak.exe" unpack "$EXP\out\pakchunk1013-Windows.full.pak" --output "$EXP\work\verify_unpack_full"
& $py "$EXP\verify_full.py"
```

---

## 8. 翻译口径与已知取舍（审校重点）

1. **词表优先**：882 条唯一 src 里 740 条命中 `main.lua`（2624 条词表），直接复用其译文
   （含大小写/空格归一化命中；归一化命中已逐条人工确认过，如 `ACCEPT→接受`、`OFF→关`、`rarity→稀有度`；
   仅 `○ Change 1\r\n○ Nice Change` 一条因为是双行格式，保留原文换行改成 `○ 变化 1\r\n○ 不错的变化`）。
2. **已有中文一律不覆盖（247 条）**：这些 key 在注入前就已经是中文（如 `Enabled→已启用`、
   `Quicksort Inventory→整理背包`、`Interact→互动`），说明它们本来就被汉化过，覆盖只会改动已有成果、
   没有收益，因此**保留原值**（`out\overlap_detail.csv` 列出全部 253 条现状）。
   若你希望"全部按本次译文统一覆盖"，跑一次
   `& $py "$EXP\inject_full.py" --overwrite-existing` 再重新打包即可（会多改 247 条）。
3. **只更新英文残留（6 条）**：注入前已在 locres 但仍是英文/非中文的 6 条（含 `PATREON`）已更新为中文。
4. **SKIP 126 条**：纯数字/符号/品牌缩写/占位乱码，翻译没有意义，保留内联原文；
   在对照表里来源标为 `SKIP`、动作为 `未注入`，可筛出来核对。
5. **147 条 P0/P1 补丁产物**：baseline 的 src 是原版英文，本次按 baseline 重新翻译，
   不复用补丁里那批"等长替换"的中文（那批不在游戏运行时生效）。

### 我最不确定译法的 15 条（请抽查）

| # | key 所属资产 | src 英文 | 本次译文 | 疑点 |
|---|---|---|---|---|
| 1 | `WB_GoldWeightBar` | `Gold Nubs` | 金币 | Nubs 直译"小块"，也可能是某种代币单位 |
| 2 | `WB_PhotoMode` | `TIME OF DAY` | 时间 | 照片模式惯用"一天中的时间" |
| 3 | `WB_T3_SettingsMenu` | `Release` | 松开 | 也可能是"发布版"或按键动作"释放" |
| 4 | `WB_GenitalScreen` | `Aroused/Flaccid` | 勃起 / 疲软 | 也可作"兴奋 / 疲软" |
| 5 | `WB_GenitalScreen` | `Arousal State` | 兴奋状态 | 与上条术语需统一 |
| 6 | `WB_PlayerInventory` | `OFFHANDS` | 副手 | 装备栏位"副手武器"的简写 |
| 7 | `WB_PlayerInventory` | `FEATURES` | 特性 | 也可能是"面部特征" |
| 8 | `WB_InputKeySelector` | `Selecting` | 选择中 | 也可能是"正在选择" |
| 9 | `WB_LoreScreen` | `Ahmes` | 阿赫梅斯 | 人名音译，需与对话汉化统一 |
| 10 | `WB_T3_SettingsMenu` | `Deuteranopia` / `Protanopia` / `Tritanopia` | 绿色盲 / 红色盲 / 蓝色盲 | 也可作"绿色弱/红色弱/蓝色弱" |
| 11 | `WB_DemoTutNoti*` | `and` | 和 | 单独一条，实际上下文可能是"以及" |
| 12 | `WB_FormScreen` | `These Cat Like People were the most` | 这些像猫一样的种族曾是最…… | 原文被截断，语义不完整 |
| 13 | `WB_CheatMenu` | `TYPE ITEM FILTER` / `TYPE QUEST FILTER TEXT` | 输入物品筛选 / 输入任务筛选文本 | 输入框占位提示，可能应作"输入…筛选关键词" |
| 14 | `WB_HUD` | `Patreon Build - Version ` | 赞助版 - 版本  | 原文尾部带空格，是拼接版本号的前缀 |
| 15 | `WB_T3_SettingsMenu` | `REPLACED by WB_Master_SettingsMenu` | 已由 WB_Master_SettingsMenu 替代 | 开发者占位说明，理论上不会显示 |

另有批量类不确定：制作/装备分类 `Axes/Swords/Hammers/Chestplates/Helmets` → 斧/剑/锤/胸甲/头盔（复数英文按中文习惯取单数）。

### 保留已有中文的 34 条差异（决定是否开覆盖模式的依据）

那 247 条"保留已有中文"里，**213 条与本次译文完全相同**，只有 **34 条**不同。逐条看下来两个方向都有：

* **现值明显更优/更贴合游戏**（覆盖会变差）：
  `YOU DIED` 现值"你的旅程已结束"（词表是"你死了"）、
  `Gold Nubs` 现值"你的金币"（我译"金币"）、
  `These Cat Like People were the most` 现值"这些猫一样的人是萨布最"（原文被截断，现值补出了人名）、
  `Manually load a save file.` 现值"像个极限流大佬那样手动载入存档"（风格化，词表是"手动读取存档。"）。
* **现值是错译**（覆盖会变好）：
  `GENERAL` 现值"将军"（应为"通用"）、
  `Start your journey.` 现值"我相信你"（应为"开始你的旅程。"）、
  `Clothing` 现值"形态"（应为"服装"）、
  `MERCHANT` 现值"购买"（应为"商人"）、
  `Tome of the Ancients` 现值"埃科斯：《沙漠王国指南》"（疑似串位）。

> 结论：两边各有优劣、数量都不多（34 条），**默认保留现值**（不破坏已有可用汉化）。
> 若你希望统一口径，用第 7 节的 `--overwrite-existing` 重跑即可，影响面就是这 34 条 + 其余 213 条无变化。

### 已知的轻微不一致（2 组）

同一句英文因 key 归属不同，会出现两种中文：

| src | 一处显示 | 另一处显示 | 资产 |
|---|---|---|---|
| `Clothing` | 形态（保留的现值，疑为错译） | 服装（本次新增） | `WB_CheatMenu` / `WB_DSS2`、`WB_v2DSS2` |
| `LOADING WORLD` | 正在载入游戏（保留的现值） | 正在载入世界（本次新增） | `WB_LoadingScreen` / `WB_LoadingScreen-Fake`、`WB_T3_LoadingScreen` |

### 译文质量自检结果（`check_translations.py`）

* 实际写入 locres 的 873 条译文里，**"译文==原文" 9 条**，全部是刻意保留的品牌/缩写
  （`Lumen` / `TAA` / `NVIDIA DLSS` / `NVIDIA DLSS 4` / `Carnal Instinct` / `CARNAL` / `LOVENSE` / `Lovense` / `JIMMY`），
  与词表口径一致；
* **无** 反斜杠/字面转义残留、**无** 格式化符（`{0}`、`%s`）不匹配、**无** TODO/待译占位；
* 新翻条目里没有长度异常压缩（<原文 20%）的条目。

---

## 9. 风险与注意事项

1. **游戏必须完全退出**才覆盖 pak（脚本已做进程检测）。
2. **只动 `.pak`**，不要动 `pakchunk1013-Windows.utoc/.ucas`。
3. **备份是唯一退路**：`03_原始备份\pakchunk1013-Windows.pak.locres实验前` 不要删。
4. 实验期间**不要跑 Steam「验证文件完整性」**——它会把 pak 换回官方版。
5. 若游戏启动崩溃/卡加载 → 立即跑 `回退实验pak.ps1`，游戏本体不受影响。
6. 本次注入把 locres 从 84,968 加到 139,559 字节，pak 从 39,741,474 加到 39,776,355 字节（+34,881），
   容器结构、压缩方式、seed、mount 与 mount 路径全部与原版一致。
7. 未安装：本文档生成时全量 pak 仍在 `out\` 里等人工安装；K 盘内容未被本次改动。

---

## 10. 本次明确没有做的事

* 没有写入游戏目录（K 盘只做只读核查；安装/回退由人工跑第 4、6 节脚本）；
* 没有碰任何 `.utoc` / `.ucas`，没有碰蓝图/`tolegacy_all` 字节；
* 没有改 `dist.json`、`main.lua`、`scan_ftext` 下任何文件；
* 没有改动上一轮已有的 `安装实验pak.ps1` / `实验说明.md` 等文件，只新增本次全量脚本与产物；
* 没有把纯数字/符号条目（126 条）硬翻成中文。
