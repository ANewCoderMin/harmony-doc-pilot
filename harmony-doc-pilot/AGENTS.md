# HarmonyDocPilot Skill

## Purpose
基于本地鸿蒙（ArkTS/ArkUI）官方文档进行实时检索，输出候选 API/组件列表、证据链与图片路径，供 Codex 在对话中二次筛选与总结。

## Inputs
- 用户问题（中文）
- 可选约束：系统应用/权限/版本/能力集

## Tooling
- `tools/hdp_scan.py`：扫描/增量更新本地文档 Catalog
- `tools/hdp_query.py`：查询候选并输出 JSON（含证据与图片）
- `tools/hdp_open_asset.py`：macOS 打开图片（可选）

## Rules
- 文档只读，严禁修改。
- 默认只检索 `application-dev/reference` 与 `application-dev/ui`。
- 默认排除 `release-notes` 与 `api-diff`。
- 必须给出证据链：文件路径 + 行号 + 原文片段。
- 不得臆造 API；不确定时要求打开对应章节确认。

## Setup
1. 配置文档根目录：`config/harmony-doc-pilot.yaml` 中的 `docs_root`
2. 安装依赖（venv）：`python3 -m venv .venv && .venv/bin/pip install pyyaml`

## Workflow
1. 需要时运行 `hdp_scan.py` 更新 Catalog。
2. 使用 `hdp_query.py` 进行候选召回，输出 JSON。
3. Codex 在对话中进行二次筛选与推荐解释。
4. 如需查看图片，使用 `hdp_open_asset.py` 打开。

## Example
```bash
python3 skills/harmony-doc-pilot/tools/hdp_scan.py --config skills/harmony-doc-pilot/config/harmony-doc-pilot.yaml
python3 skills/harmony-doc-pilot/tools/hdp_query.py --config skills/harmony-doc-pilot/config/harmony-doc-pilot.yaml --q "ForEach 拖拽排序" --topk 25 --final 6 --with-images
```
