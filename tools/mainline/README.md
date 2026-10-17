# 主线脚本（静态汉化）

> 本目录是 2026-10 验证通过的主线方案脚本，取代 `tools/archive/` 下的旧机器路线。
> 全部脚本都只是「读游戏容器 → 改文本 → 重新打包 → 离线复核」，不会在运行时注入任何代码。

## 脚本清单

| 脚本 | 用途 |
|---|---|
| `build_zenmod_safe.py --full-1013` | **对话层**：解包原始 `pakchunk1013` raw chunk，把 MSL 对话文本改成 UTF-16 中文，完整重建容器（保留原 `ContainerHeader`、把 `container_id` 改回原值），产出 `pakchunk1013-Windows.utoc/.ucas` |
| `build_ui_pak.py --locres ... --out-pak ...` | **UI 层**：解包原 `pakchunk0.pak`，替换包内 `Game.locres`，按原参数（V11 / Oodle / seed 0x464517FC / mount `../../../`）重新打包并做四项复核 |
| `build_protected_locres.py` | 从上游全量 locres + 保护清单，生成最终 UI locres（把逻辑键回退英文） |
| `scan_text_logic.py` | 全库扫描：找出「文本参与逻辑比较」的资产（`Conv_TextToString` / `EqualEqual_TextText` / `TextIsEmpty` 等），产出 `scan_report.json` / `asset_ftexts.json` |
| `protect_all_enums.py` | （可选）枚举识别与保护集生成（注意：必须按路径模式匹配 `/Enums/`、`/Enumerations/`、`/09_enums/`、`E_*` 等，不能只匹配 `/Enums/`，否则会漏 100+ 个枚举） |

## 前置

1. **正版游戏**，完全退出；
2. `retoc`（解包/打包 IoStore；读/写 Zen chunk）、`repak`（读写 legacy `.pak`）、`oo2core_9_win64.dll`（Oodle，放 PATH）；仓库工具链在 `tools/`，实际路径按本机调整；
3. 游戏 AES key（社区公开，自行准备）；
4. Python 3.10+，无需第三方库（仅标准库 + 本仓库 `tools/locres_inject/locres_lib.py`）。

## 注意

- `build_zenmod_safe.py` / `build_ui_pak.py` / `scan_text_logic.py` 里的**游戏目录、工作目录是写死的**（本机路径），使用前改脚本顶部的路径常量；
- `build_ui_pak.py` 的 `--locres` 用 `data/Game.locres.mainline`（由 `build_protected_locres.py` 生成）；
- 打包结果非确定（压缩/对齐导致 pak 的 SHA 每次不同），**等价性判断看「解包后 locres 的 SHA256」**，不要看 pak 的 SHA；
- 动手前先备份游戏文件，详见根目录 README「回滚」。
