# Carnal Instinct —— UI 蓝图（WB_*）FText 引用分布扫描报告

> 生成时间：2026-10-16 03:24:32（Asia/Shanghai）
> 扫描根：`D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\tolegacy_all`
> 基线对照根（原始未打补丁）：`D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\tolegacy_orig`
> 脚本：`scan_ftext/scan_wb_ftext.py`（纯只读，未改动任何既有文件/游戏文件）

---

## 0. 一句话结论

**WB_* UI 蓝图里的文本是「真内联」的 `FText`（Namespace / Key / SourceString 三段都写在 .uexp 里），不是 StringTable 引用。** 全部 321 个 WB_*.uexp 中 StringTableEntry 引用数 = **0**。

实测到的内联 FText 有两个家族：**家族 A** 1325 条（Namespace 空 + Key 为 32 位 GUID + Source 为英文文案，即控件设计器里手填的可本地化文本）与 **家族 C** 11 条（UMG 模板自身的默认值，不是游戏文案）。

因此「改 StringTable 资产本体」这条已有可行方案，**对 WB_* 蓝图文本不适用**：这些文本不在任何 StringTable 里，正文就写在 .uexp 内联的 FText 载荷中。

置信度：**确认**（结构由实际字节逐段解出，家族 A 的 key→source 零冲突，见第 1 节）。

## 1. 方法与实测确证的字节结构（置信度：确认）

### 1.1 实测布局

对所有 WB_*.uexp 逐偏移做**严格三段校验**，命中率最高且自洽的布局是：

```
FText := u32 Flags | u8 HistoryType | 载荷
  载荷（本库实测只有这一种形状）= FString Namespace | FString Key | FString SourceString
  HistoryType 字节实测取值：1（主体，家族 A）与 0（家族 C，见 1.5）
  HistoryType == 12 (StringTableEntry)：已实现两种变体（FString/FName TableId + FString Key），本库 0 命中
```

FString = `int32 长度` + 数据 + NUL；长度 > 0 为 ANSI（长度含 NUL），< 0 为 UTF-16（长度 = 码元数含 NUL）。

### 1.2 取证过程（关键一条，用于复核）

以 `WB_Stats_Full.uexp` 中 `Cold` 一处为例，实际字节（偏移 33437 起）：

```
33437  00 00 00 00            u32 Flags = 0
33441  01                     u8  HistoryType = 1  （本库主族取值，见 1.5 的枚举歧义）
33442  00 00 00 00            FString Namespace = ""      （长度 0）
33446  21 00 00 00 …          FString Key       = 32 位 hex GUID
33483  05 00 00 00 43 6f 6c 64 00   FString SourceString = "Cold"
```

三段长度前缀、NUL 终止、字符集全部自洽，且下一字节正好接后续结构 —— 无剩余、无越界。
强佐证：全库 1336 条该形态候选中，**同一个 Key 从未对应两个不同的 SourceString**（0 冲突），这排除了偶然字节巧合。

> 更正先前情报：此前记录的「WB_Stats_Full 里 FText 是 StringTable 引用，TableId 是 32 位 hex、key 是 Quests Completed/Cold 这类普通字符串」**是反的**。实际是 **Key = 32 位 hex GUID，SourceString = Quests Completed/Cold/Armour**，而且**没有任何一条是 StringTableEntry**（见 1.5 的家族说明）。

### 1.3 刻意不做的事（方法学红线）

* **不做「位置邻近」式配对**。只接受能完整解出载荷的候选。
* **不统计 HistoryType ∈ {2..11, 13}**（NamedFormat / AsNumber / AsDate / Transform / TextGenerator …）。
  在没有 UClass schema 的前提下，这些载荷（如 AsNumber = int64 [+ 格式化选项]）与普通字节流不可区分。
  实测：宽松规则（int64 + 一个合法 FString）在 `WB_Stats_Full` 单文件上就产出 **346 条**候选，
  其 `Flags` 字段全是 0x0202003F / 0x93071600 这类明显垃圾值 —— 假阳性率约 100%，故整体废弃。
  代价：若某控件确实只含数值型 FText，本报告不会计入；这是**已知的下界**，不是全量。
* 裸 FString（不属于任何已确认 FText 的字符串）单列一类并标「猜测」，不混入 FText 统计。

### 1.4 只靠「三段自洽」不够：两道与内容无关的不变量（重要）

本库里有好几类字节流会**恰好**满足 `Flags + HistoryType + 三段 FString` 的链式校验。
扫描器因此加了两道不变量，并在扫描时分别计数（`dist.json` 可复核）：

| 不变量 | 判据 | 挡下的候选数 |
|---|---|---|
| **I1** Flags 位域 | `Flags & ~0x1F == 0`（只允许 ETextFlag 的 5 个位） | 238 |
| **I2** 标识字段非空 | `Namespace` 或 `Key` 至少一个非空 | 182 |

被 **I1** 挡下的 238 条，按导出名后缀分：{"INST": 169, "C": 51, "FPSLimit": 5, "Reflections": 2, "VSync": 2, "EnemyName": 1, "Title": 1, "GlobalIllumination": 1, "Selection": 1, "GetAbilityPoints": 1, "CompiledData": 1, "ID": 1, "Name": 1, "ObjectiveName": 1}

按 `SourceString` 分（Top 12）：{"BPTYPE_Normal": 51, "Fade": 25, "ConstructAnim": 13, "Hover": 11, "TextBlockDefaultValue": 6, "A_Show": 4, "UseAnim": 4, "GlobalFade": 3, "Highlight": 3, "fade": 3, "NewAnimation": 3, "HighlightAnim": 3}

读出来是三类互不相同的字节巧合：

1. **控件动画实例的数据段**（占 `_INST` 后缀 169 条）：`FGuid(16B)` 的末 4 字节 + 紧跟的 `0x01` 凑成 header，`Flags` 全部形如 `0x0580xxxx`（明显越界），`Key` 恒空，`SourceString` 是动画名（`Fade`/`ConstructAnim`/`Hover`/`FadeText`/`Ping`…）。
2. **`BPTYPE_Normal` 枚举串**（占 `_C` 后缀 51 条）：`Flags = 0x00000100`（bit 8，越界），`Key` 空，`SourceString = "BPTYPE_Normal"`。
3. **4 字节平移伪解**：把家族 A/C 的真候选向后挪 4 字节读出，例如 `key="UMG", src="TextBlockDefaultValue"`（Flags `0x0309020A`）或 `key="t.MaxFPS 60", src="t.MaxFPS 90"`（Flags `0x00000600`）。

被 **I2** 挡下的 182 条则是 `Namespace` 与 `Key` 皆空、`SourceString` 是单个符号（`&`/`=`/`C`/`J`/`O`…）的偶然串 —— 真 FText 至少有一个非空标识字段。

> 教训：这类假阳性只看「字符串能解出来」是发现不了的，必须引入**与内容无关的独立不变量**
> （这里是 Flags 位域与「标识字段非空」）。接力文档里「误伤非文本字段」的邻近启发式，
> 缺的正是这类不变量。

合法候选（家族 A/C）的 `Flags` 实测只有 `0` 与 `8`(Immutable) 两种取值。

### 1.5 本库实际存在两个内联 FText 家族（重要，影响计数口径）

同一套 `ns/key/src` 三段载荷，在本库里配了**两个不同的 HistoryType 字节**：

| 家族 | HistoryType 字节 | Flags | Namespace | Key | SourceString | 条数 | 置信度 |
|---|---|---|---|---|---|---|---|
| **A**（主体） | 1 | 0 | 空串 | 32 位 hex GUID | 英文显示文本 | 1325 | **确认** |
| **C**（UMG 默认值） | 0 | 0 或 8(Immutable) | `UMG` | 符号名，如 `TextBlockDefaultValue` | 显示文本 | 11 | **确认存在** |
| B（4 字节平移歧义） | 0 | 1 | GUID | 显示文本 | 标识符 | 0（已按重叠丢弃 44 次） | 判定为**伪解** |

**家族 C 是判定 HistoryType 取值的唯一实证锚点**：
`Namespace="UMG" / Key="TextBlockDefaultValue" / Source="Text Block"` 正是 UMG 模块里
`UTextBlock::Text` 的 C++ `LOCTEXT` 默认值（UMG 的 `LOCTEXT_NAMESPACE` 就是 `UMG`），
三段语义完全对上，不可能是巧合 —— 这说明 **HistoryType == 0 也是一条真 FText**。

但同一批字节里家族 A 的 HistoryType 恒为 1，且它的解析是唯一自洽的（把 ht 换到相邻字节会立刻解不出 FString）。
因此：**UE 的 `ETextHistoryType` 里 Base 究竟是 0 还是 1，本轮无法仅凭字节单方面裁定，标为「未定」。**
本报告因此不依赖该枚举，家族划分直接按 (HistoryType 字节, Namespace, Key) 的实测形态定义。

**4 字节平移歧义**：家族 A 的 `…00 00 00 00 | 01 | 00 00 00 00 | 21…` 这段字节，
向后挪 4 字节也满足「Flags 合法 + ht=0 + 三段 FString」，得到 `ns=GUID / key=显示文本 / src=标识符`（家族 B）。
两种读法只有一种是对的：按家族 C 已确立的语义（Namespace=命名空间名、Key=符号名、Source=显示文本），
**家族 A 的读法语义正确**（Namespace 空、Key=GUID、Source=显示文本），家族 B 把 GUID 放进 Namespace、
把显示文本放进 Key、再吃掉后面一个无关 FString 当 Source，语义不成立。
扫描器按「起点最早优先」保留家族 A，丢弃的 44 次全部计入 `overlaps` 并在此说明。

> 换句话说：**「StringTable 引用还是内联」这个主结论不受上述任何歧义影响** —— 
> 两种读法都是内联的三段字符串，都不含指向 StringTable 资产的外键（FName TableId）。

## 2. 扫描范围与口径

| 项 | 数值 |
|---|---|
| WB_*.uasset / .uexp 对 | 321 |
| 解析成功（导出表链式自洽 + .uexp 存在） | 321 |
| 解析失败（unresolved） | 0 |
| 导出对象（export）总数 | 20389 |
| .uexp 字节总数 | 5,430,692 |
| 内联 FText 条数（家族 A + C） | 1336 |
| StringTableEntry 引用条数 | 0 |
| 4 字节平移歧义被丢弃的候选 | 44（见 1.5） |
| 被 Flags 位域校验排除的假阳性候选 | 238（见 1.4） |

两个统计口径（后文都给出）：

* **文件口径**：含 ≥1 条该类文本的 WB_* 文件数 / 总文件数。
* **词条口径**：该类文本条目总数 / 可识别文本总数。

**可识别文本总数** = 已确认内联 FText 条数（家族 A + C）+ 已确认 StringTableEntry 条数 + 疑似裸展示字符串条数（三类互斥，由扫描器的「已覆盖字节区间」去重保证；另有 44 次 4 字节平移歧义候选按 1.5 的规则丢弃）。

## 3. ① StringTable 引用 vs 真内联：比例

### 3.1 文件口径

| 类别 | 文件数 | 占比 |
|---|---|---|
| 含 **StringTableEntry 引用**（HistoryType=12） | 0 | 0.0% |
| 含 **真内联 FText**（家族 A / C） | 190 | 59.2% |
| 含疑似裸展示字符串（猜测） | 25 | 7.8% |
| 以上都没有（纯布局/样式控件） | 122 | 38.0% |

### 3.2 词条口径

| 类别 | 条目数 | 占可识别文本 |
|---|---|---|
| **StringTableEntry 引用**（HistoryType=12） | 0 | 0.0% |
| **真内联 FText 家族 A**（Namespace 空 + Key=GUID） | 1325 | 92.1% |
| **真内联 FText 家族 C**（UMG 默认值，模板占位文本） | 11 | 0.8% |
| 疑似裸展示字符串（猜测，多词） | 103 | 7.2% |
| 合计（可识别文本总数） | 1439 | 100% |

（另有未被任何 FText 覆盖的单 token 字符串 444 条，形态像标识符而非展示文本，不计入上表。）

## 4. ② StringTable 表清单与 chunk 归属

### 4.1 全库（tolegacy_all，37948 个 .uasset 全扫）按类判定的 UStringTable 资产

判定方法：解析 .uasset 的 NameMap，命中 `Default__StringTable` + `StringTable` 两个名字即为 UStringTable 资产（`Default__StringTable` 是该类 CDO 专名，不会出现在别的资产里）。**不是按文件名猜** —— 文件名法会误判：`ST_FormlessVillager_ST_Test` 名字像 StringTable，实际是 StateTree（NameMap 含 `StateTree`/`MassStateTreeSchema`）。

| # | 资产（相对 tolegacy_all） | 所属容器(chunk) | 有 .uexp |
|---|---|---|---|
| 1 | `Carnal_Instinct_UE5\Content\RPG_InventorySystem\UI\CommonTermsUI.uasset` | pakchunk1014 | 是 |

### 4.2 被 WB_* 引用的 StringTable（HistoryType=12 的 TableId 去重）

**0 条。** 即：没有任何一个 WB_* 蓝图通过 StringTableEntry 引用字符串表。

（扫描过程中出现过 1 条 HT=12 的形态候选：资产 `WB_EffectSlot`，TableId=`Action Consumables Component`、Key 为单个控制字符 `0x10`。合法 Key 不可能是控制字符，故判为字节巧合并剔除 —— 这一点已写进扫描器的 Key 校验。）

结论：WB_* 的 UI 文本**不经** StringTable 资产，改表本体对它们无效。

## 5. ③ 真内联文本：规模、分布与样例

### 5.1 规模

* 真内联 FText 条目：**1336** 条（家族 A 1325 + 家族 C 11），分布在 **190** 个文件（占 59.2%）
* HistoryType 字节分布：{"1": 1325, "0": 11} （取值歧义见 1.5）
* 去重后的 (Namespace, Key) 组：**1247** 组（见 `dist.json` 的 `primary.keys`）
* 去重后的 SourceString：**894** 条

Namespace 分布（置信度：确认）：{"": 1325, "UMG": 11}

→ 家族 A 的 Namespace **全部为空串**、Key 全部是 32 位十六进制 GUID；家族 C 的 Namespace 为 `UMG`（仅 11 条）。

Flags 分布：{"0x00000000": 1331, "0x00000008": 5}

### 5.2 文本出现最多的导出对象（Top 20）

| 导出对象 | 文本条数 |
|---|---|
| `TextBlock_0` | 23 |
| `TextBlock_1` | 19 |
| `WB_T3_OptionSwitcher_Difficulty` | 14 |
| `AutosaveSlots` | 12 |
| `QuicksaveSlots` | 12 |
| `Default__WB_PlayerInventory_C` | 12 |
| `TextBlock` | 11 |
| `TextBlock_4` | 11 |
| `ColumnDescriptorTestAllToyInfo` | 10 |
| `WB_T3_OptionSwitcher` | 10 |
| `TextBlock_2` | 9 |
| `WB_T3_SubHeadline` | 9 |
| `TextBlock_3` | 8 |
| `TextBlock_5` | 8 |
| `Option_DLSS` | 8 |
| `Option_FrameRateLimit` | 8 |
| `WB_T3_OptionSwitcher_Voice` | 8 |
| `WB_T3_OptionSwitcher_FPSLimit` | 8 |
| `Difficulty` | 7 |
| `Default__WB_Master_OptionSwitcher_C` | 7 |

### 5.3 单文件文本量 Top 15

| 资产 | 内联 FText | 裸串(多词) | 导出数 | .uexp 字节 |
|---|---|---|---|---|
| `WB_T3_SettingsMenu` | 222 | 43 | 296 | 68217 |
| `WB_KeybindingsSwitcher` | 79 | 0 | 1200 | 49407 |
| `WB_Options_Gameplay` | 70 | 0 | 156 | 33337 |
| `WB_CheatMenu` | 58 | 0 | 242 | 80308 |
| `WB_Stats_Full` | 58 | 0 | 496 | 48378 |
| `WB_Options_AdvancedVideo` | 41 | 1 | 218 | 74841 |
| `WB_ProMainMenu` | 33 | 1 | 274 | 110766 |
| `WB_DSS2` | 31 | 0 | 249 | 33629 |
| `WB_v2DSS2` | 31 | 0 | 249 | 33395 |
| `WB_CosmeticsWindow` | 26 | 0 | 252 | 115235 |
| `WB_Options_Lovense` | 24 | 0 | 178 | 29668 |
| `WB_Options_Video` | 23 | 1 | 227 | 80678 |
| `WB_T3_NewGame` | 22 | 0 | 57 | 11684 |
| `WB_T3_Lovense` | 18 | 2 | 91 | 16020 |
| `WB_QuestScreen` | 18 | 0 | 143 | 32927 |

### 5.4 样例（最多 20 条，取自不同文件；按文本长度降序排在 `dist.json` 的 `primary.samples`）

| 资产 | 导出对象 | Key(32hex) | SourceString | 编码 |
|---|---|---|---|---|
| `WB_T3_SettingsMenu` | `WB_T3_OptionSwitcher_QualityDLSS` | `2A25070D449A7D147B92DE8C6228318E` | `Native AA acts as a premium Anti-Aliasing mode, rendering at full resolution to provide the sharpest image possible without shimmering. The quality presets render the game at lower internal resolutions and use AI to reconstruct the detail, significantly boosting your frame rate while maintaining high visual fidelity.` | ascii |
| `WB_DemoTutNoti1_300x400` | `TextBlock_77` | `2A4E7AFE42DECC14254DD79C31053B9B` | `This is a tutorial text which takes place inside of a custom widget. To display icons together with text - or use different text styles within a text - you can use a Rich Text Block.` | ascii |
| `WB_DemoTutNoti2_300x400` | `TextBlock_77` | `5A28D26C4E6672AF1CFDBA908460531F` | `This is a tutorial text which takes place inside of a custom widget. To display icons together with text - or use different text styles within a text - you can use a Rich Text Block.` | ascii |
| `WB_T3_NewGame` | `WB_T3_OptionSwitcher_Gender` | `B5B7BA094DD750E0B368129987C850C9` | `Sets your initial Formless body type, you can change this later in the story when you unlock full Character Customization.` | ascii |
| `WB_Options_Gameplay` | `NonCon` | `E8D0ECB441777DAEFC259693A98A8270` | `Disables Con-Non-Con scenes, if this is on you will still have dialog choices and lead-in to these scenarious` | ascii |
| `WB_ProMainMenu` | `WB_PlayButton_SelectMode_VoiceB` | `C29B16754DC23A23F01D4EBFD3FA0FC9` | `Choose your voice and confirm to start the game. This can be changed at any time in the settings` | ascii |
| `WB_Options_AdvancedVideo` | `Option_DLSS_ONOFF` | `5E7C61334FCA2252D6E59197501BF674` | `When using DLSS, we highly recommend a Resolution Scale of 65-70%. And 100% when using DLAA.` | ascii |
| `WB_Options_Video` | `Option_ResolutionScale` | `AA5CEAA14907C8E31F571296CED631A8` | `For best performance/quality - we recommend a maximum of 70% resolution scale.` | ascii |
| `WB_T3_Lovense` | `WB_T3_Toggler_LovenseHTTPS` | `5316E6C243BAA5E571CCB3B73EF32DBC` | `Use a secure HTTPS connection when communicating with the Lovense service.` | ascii |
| `WB_KeybindingsSwitcher` | `TextBlock_32` | `26EE653F4962A21224382F844D6EDC0C` | `Purchase Sorcery / Drag Sorcery into hotbar to use with the radial menu` | ascii |
| `WB_Stats_Main` | `TP_Strength` | `22718BC841F17BC7CE4E86AA5A0E256C` | `Increases melee damage, critical damage, and armor` | ascii |
| `WB_Options_Lovense` | `StartLovensRunning` | `86D7FE5E4DC3243ECEF3BF8A6BAACE7A` | `Start with Lovense Running?` | ascii |
| `WB_CheatMenu` | `Button_23` | `84A2D1464F9B8DA8298A6C91A2104A48` | `unreal trace: screenshot` | ascii |
| `WB_Stats_Full` | `TextBlock_67` | `D3A8797D4C998AB127AAABAEB350AE0B` | `Gilded Fold Reputation` | ascii |
| `WB_DSS2` | `Btn_CamControls` | `EDC10CF5478DA39D1A5458992FFC00A5` | `Toggle Camera Controls` | ascii |
| `WB_v2DSS2` | `Btn_CamControls` | `C14D8D464B9CFC23B1CBA4B29B11FD18` | `Toggle Camera Controls` | ascii |
| `WB_Options_Audio` | `Option_EffectsVolume` | `943609C54E1CB3A9B31C91BC8040422D` | `Sound Effects Volume` | ascii |
| `WB_SelectChapter` | `TextBlock_156` | `D0A681934B5B30B7C13D4EB00381541D` | `Save Game Infomation` | ascii |
| `WB_SelectChapter_Manual_Save_v3` | `TextBlock_156` | `3D639E164A1E741A973321A07DC52C60` | `Save Game Infomation` | ascii |
| `WB_CosmeticsWindow` | `Txt_SkinColor` | `13DD723E4B89658DBFECF981A9A661F1` | `CANON SKIN COLOURS` | ascii |

按出现次数排序的全部 (Key, SourceString) 见 `dist.json` → `primary.keys`（共 1247 组）。

**家族 C（UMG 默认值）全部样例**（这些是 UMG 模板占位文本，不是游戏自己的文案，翻译时通常应忽略）：

| 资产 | 导出对象 | Namespace | Key | SourceString |
|---|---|---|---|---|
| `WB_AIStatBars` | `Text_EnemyName` | `UMG` | `TextBlockDefaultValue` | `Text Block` |
| `WB_AIStatBars_Boss` | `Text_EnemyName` | `UMG` | `TextBlockDefaultValue` | `Text Block` |
| `WB_State` | `Text_State` | `UMG` | `TextBlockDefaultValue` | `Text Block` |
| `WB_NSM_CustomInputKeySelector` | `T_WhileSelectingText` | `UMG` | `TextBlockDefaultValue` | `Text Block` |
| `WB_T3_OptionSwitcher` | `T_Selection` | `UMG` | `TextBlockDefaultValue` | `Text Block` |
| `WB_T3_SettingsCategoryButton` | `T_Title` | `UMG` | `TextBlockDefaultValue` | `Text Block` |

### 5.5 裸 FString 线索（置信度：**猜测**，启发式）

未被任何 FText 覆盖的 FString 中，像多词展示文本的有 **103** 条，分布在 25 个文件；另有 444 条单 token 字符串（形态像标识符/枚举名，例如 `VoidResistance`、`BleedChance`），很可能是 key/ID 而不是要翻译的显示文本。

多词裸串样例（前 20）：

* `GAME MODE NAME` ← WB_Text01
* `GAME MODE TYPE` ← WB_Text01
* `GAME MODE NAME` ← WB_Text02
* `GAME MODE TYPE` ← WB_Text02
* `64 PLAYERS` ← WB_Text02
* `Current Quest Name` ← WB_ChapterButton
* `Current Quest Name` ← WB_ChapterForSave
* `GAME MODE TYPE` ← WB_HomeButton_Small
* `GAME MODE HEAD` ← WB_HomeButton_Small
* `Input Event` ← WB_KeybindingButton
* `GAME MODE TYPE` ← WB_PlayButton
* `GAME MODE HEAD` ← WB_PlayButton
* `64 PLAYERS` ← WB_PlayButton
* `GAME MODE TYPE` ← WB_PlayButton_SelectMode
* `GAME MODE HEAD` ← WB_PlayButton_SelectMode
* `64 PLAYERS` ← WB_PlayButton_SelectMode
* `GAME MODE TYPE` ← WB_SettingsButton01
* `GAME MODE HEAD` ← WB_SettingsButton01
* `GAME MODE TYPE` ← WB_SlotButton
* `GAME MODE HEAD` ← WB_SlotButton

> 注意：这一类的假阳性风险高于前两类 —— 单看字节无法区分「要翻译的裸文本」和「程序内部用的字符串常量」。需要翻译时建议逐条人工确认。

## 6. ④ unresolved 清单与原因

**0 个文件解析失败。** 321 个 WB_* 全部成功解析（导出表链式自洽校验通过 + .uexp 存在）。

原因归类：{}

## 7. 附加发现（影响路线判断，务必看）

### 7.1 `tolegacy_all` 不是原始版，已被上一轮 P0/P1 补丁改过（置信度：确认）

`tolegacy_all` 与 `tolegacy_orig` 的 .uexp 存在字节差异；实测差异形态：
英文 ASCII 源串被原地换成**等长 UTF-16 中文 + 尾随空格**（正是 `odd_patch.py` 的
`ascii-to-utf16` / `add-tailspace` 手法），文件长度不变。

WB_* 中已是中文的 FText 条目 **147** 条：

| 文件 | 导出对象 | SourceString（现状） |
|---|---|---|
| `WB_RadialAbilityBar` | `TextBlock_0` | `技能名称 ` |
| `WB_RadialAbilityBar` | `TextBlock_1` | `描述   ` |
| `WB_ToolTipAbilities` | `APText` | `所需技能点      ` |
| `WB_Campfire` | `Button_FastTravel` | `快速旅行 ` |
| `WB_Campfire` | `Button_Resume` | `离开` |
| `WB_MorphSlider` | `Reset` | `重置` |
| `WB_CosmeticsWindow` | `TextBlock_0` | `形态` |
| `WB_CosmeticsWindow` | `Txt_HairColor_1` | `妆容颜色  ` |
| `WB_CosmeticsWindow` | `Txt_SkinColor_3` | `原生瞳色    ` |
| `WB_CosmeticsWindow` | `Txt_SkinColor_7` | `体毛颜色    ` |
| `WB_CosmeticsWindow` | `Txt_TattooColor` | `纹身颜色  ` |
| `WB_CosmeticsWindow` | `BodyHair_Category` | `体毛样式   ` |
| `WB_CosmeticsWindow` | `Complexion_HideClothes` | `隐藏衣物？ ` |
| `WB_CosmeticsWindow` | `Complexion_HideClothes` | `是` |
| `WB_CosmeticsWindow` | `HairHorn_Ornament` | `关` |
| `WB_CraftingList` | `WB_T3_OptionSwitcher` | `武器 ` |
| `WB_CraftingList` | `WB_T3_SubHeadline` | `制作列表  ` |
| `WB_CraftingWindow` | `TextBlock_138` | `制作` |
| `WB_CheatMenu` | `TextBlock_3` | `武器 ` |
| `WB_CheatMenu` | `TextBlock_31` | `形态` |
| `WB_CheatMenu` | `TextBlock_4` | `任务物品 ` |
| `WB_CheatMenu` | `TextBlock_5` | `消耗品  ` |
| `WB_CheatMenu` | `TextBlock_59` | `关键物品` |
| `WB_CheatMenu` | `TextBlock_6` | `其他物品 ` |
| `WB_CheatMenu` | `Button_11` | `添加 1 点技能点` |
| `WB_CheatMenu` | `Button_12` | `形态神殿 ` |
| `WB_CheatMenu` | `Button_13` | `外观  ` |
| `WB_CheatMenu` | `Button_14` | `提升存在感属性  ` |
| `WB_CheatMenu` | `Button_16` | `批量消耗品   ` |
| `WB_CheatMenu` | `Button_19` | `统计内存 ` |
| … | | 共 147 条 |

**影响**：做「词条覆盖率」类统计时必须以 `tolegacy_orig` 为基线，否则会把已改的条目当成已覆盖。
结构统计不受影响（见 7.4 基线对照：两类文本计数一致）。

### 7.2 Namespace 为空 + Key 为 GUID 的含义（置信度：**推断**）

这是 UE 里「蓝图/控件里手填的可本地化文本」被 cooker 自动分配 Key 后的典型形态：
文本本体内联在包里（SourceString），(Namespace, Key) 只作为本地化查找键。
Namespace 为空串意味着查找落在「默认命名空间」。

由此可推出两条（**推断，未在本轮做游戏内验证**）：

1. 这类文本在运行时是**先查本地化表、查不到再回落到内联 SourceString**。若该假设成立，则理论上存在「不动蓝图、只补本地化表（locres / StringTable）里(空 Namespace, GUID Key) 条目」的覆盖路线。**但前提是该查找键真的被注册进本地化表**，需要实验验证；本报告只给结构事实，不背书这条路线。
2. 反过来，若走「改蓝图内联 SourceString」的老路，就必须处理长度变化 —— 这与接力文档第五节记录的两条失败打法（换 uexp 不同步长度 / 等长替换）是同一个坑。

### 7.3 与现有运行时 mod 词表的交叉（召回验证）（置信度：确认）

现有 `main.lua` 词表 2218 条；本轮从 WB_* 提取出去重 SourceString 894 条，其中 **595 条（66.6%）在词表里已有现成译文**。

这既说明提取结果与既有工作**对得上**（召回可信），也说明尚有 299 条 WB_* 内联文本不在现有词表内 —— 若走外挂式 mod 路线，这些是需要补翻的部分。

词表未覆盖样例（前 25，按长度降序）：

* `Are you sure to quit the game? Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?`
* `This is a tutorial text which takes place inside of a custom widget. To display icons together with text - or use different text styles within a text - you can use a Rich Text Block.`
* `Fixed a bug that caused the slider button text to be displayed incorrectly`
* `Fixed an issue where Localization was not possible with the State Buttons`
* `Optimized the Sensitivities in the Demo ThirdPersonCharacter`
* `Fixed an issue where Intro Videos did not played properly`
* `◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈━◈`
* `Lumen Quality (Lighting/Relection Quality)`
* `Adjusts the volume of the game’s music.`
* `THIS IS A OPTIONAL CHAPTER DESCRIPTION.`
* `Locked. Requires FIreball - Rank 1 `
* `These Cat Like People were the most`
* `REPLACED by WB_Master_SettingsMenu`
* `Open the Radial Menu [TAB] to view`
* `VERSION 2.5.5  /  FEBRUARY 2021`
* `Locked. Required previous Rank.`
* `○ Change 1
○ Nice Change`
* `Invert Mouse / Gamepad X`
* `to open your inventory. `
* `Invert Mouse / Gamepad Y`
* `提升耐力并降低攻击耐力消耗           `
* `Patreon Build - Version `
* `会影响与其他角色的互动           `
* `TYPE QUEST FILTER TEXT`
* `RETURN TO MISSION AREA`

### 7.4 基线对照（`tolegacy_orig`，未打补丁）

| 指标 | tolegacy_all | tolegacy_orig |
|---|---|---|
| 解析成功文件数 | 321 | 321 |
| 内联 FText 条数 | 1336 | 1336 |
| StringTableEntry 条数 | 0 | 0 |
| 裸串(多词)条数 | 103 | 117 |
| 裸串(单词)条数 | 444 | 457 |
| 含内联 FText 的文件数 | 190 | 190 |
| unresolved | 0 | 0 |

（两边的 FText 结构计数完全一致（1336 / 1336），差异只在被 P1 改过的那 147 条 SourceString 的内容上；裸串计数的小幅差异也是同一个原因 —— 被改成 UTF-16 中文后不再匹配「多词/单词」的启发式规则。）

### 7.5 WB_* 的容器分布（chunk 归属）

| 容器 | WB_* 资产数 |
|---|---|
| pakchunk1014 | 140 |
| pakchunk1009 | 107 |
| pakchunk0 | 53 |
| pakchunk1003 | 7 |
| pakchunk1006 | 7 |
| pakchunk1005 | 3 |
| pakchunk1002 | 2 |
| pakchunk1007 | 2 |
| 未见于任何 manifest | 0 |

> 同一资产可能同时出现在多个 manifest 中（见 `dist.json` → `primary.wb_containers`）。

## 8. 置信度汇总

| 结论 | 置信度 | 依据 |
|---|---|---|
| WB_* FText 的字节布局 = `u32 flags + u8 ht + ns/key/src 三段 FString` | **确认** | 逐偏移严格解出，长度/NUL/字符集全自洽；合法候选 1336 条的 (ns,key)→src 零冲突 |
| WB_* 内 StringTableEntry 引用数 = 0 | **确认** | HistoryType=12 两种变体全库 0 命中（唯一候选 Key 为控制字符 `0x10`，已判伪） |
| WB_* 文本主体（1325 条）是真内联 FText 家族 A | **确认** | HistoryType=1，Namespace 空 + Key 为 32 位 GUID + 内联 SourceString |
| 存在第二个内联家族 C（Namespace=`UMG`，11 条） | **确认存在** | 三段与 UMG 的 `TextBlockDefaultValue` 默认值完全对上 |
| `ETextHistoryType` 里 Base 究竟是 0 还是 1 | **未定** | 本库同形载荷配了 ht=1（A）与 ht=0（C）两种字节；不影响主结论（见 1.5） |
| 全库 UStringTable 资产 = 1 个，清单见 4.1 | **确认** | NameMap 命中 `Default__StringTable` 专名 |
| 控件动画段 / 枚举串 / 平移伪解会被误判成 FText | **确认** | 被 I1+I2 挡下共 420 条，分类见 1.4 |
| 裸 FString 里有多词展示文本 | **猜测** | 纯启发式字符集/词形规则，未做语义确认 |
| 空 Namespace+GUID Key 可通过补本地化表覆盖 | **推断** | 依据 UE 中 FText 的本地化查找语义，未做游戏内实验 |
| HistoryType 2..11,13 的文本量 | **未知（下界）** | 无 schema 不可靠识别，已刻意放弃 |

---

数据文件：`scan_ftext/dist.json`（本报告所有数字的唯一来源，可直接复核）。

