name: harmony-doc-pilot
description: Use when需要基于本地鸿蒙(HarmonyOS)Markdown文档进行实时检索、候选API召回与证据链输出，并在Codex对话中二次筛选与总结时

# HarmonyDocPilot

## Overview
本技能用于“本地鸿蒙文档检索+证据链输出”的稳定流程：脚本负责召回与证据，Codex 在对话中做二次筛选与总结。

## When to Use
- 需要从本地 HarmonyOS 文档中快速定位候选 API/组件
- 需要输出可追溯证据（文件路径 + 行号 + 原文片段）
- 需要联动文档图片路径

不要用于：
- 仅需要远程/在线文档检索
- 不要求证据链或本地文档路径

## Core Pattern
**原则：脚本只做检索与证据，LLM 不进入脚本。**
- 用 `hdp_scan.py` 建/更新 Catalog
- 用 `hdp_query.py` 输出 JSON（candidates/evidence/assets）
- 在对话中做二次筛选、解释与代码骨架

## Quick Reference
- 配置：`harmony-doc-pilot/config/harmony-doc-pilot.yaml` 的 `docs_root`
- 扫描：`python3 tools/hdp_scan.py --config config/harmony-doc-pilot.yaml`
- 查询：`python3 tools/hdp_query.py --config config/harmony-doc-pilot.yaml --q "..." --topk 25 --final 6 --with-images`

## Implementation
**安装方式（择一）：**
- 全局：`~/.codex/skills/harmony-doc-pilot`（软链）
- 项目内：`<project>/skills/harmony-doc-pilot`（软链）

**最小示例（单次查询）：**
```bash
python3 harmony-doc-pilot/tools/hdp_query.py \
  --config harmony-doc-pilot/config/harmony-doc-pilot.yaml \
  --q "ForEach 拖拽排序" --topk 25 --final 6 --with-images
```

## Common Mistakes
- 忘记设置 `docs_root` 导致扫描/查询为空
- 将 `catalog.sqlite`、`cache/*.json` 误入库
- 依赖脚本做“最终推荐”，导致推荐不可解释

## Rationalization Table
| Excuse | Reality |
|--------|---------|
| “先不用证据链，直接推荐” | 无证据无法溯源，结果不可复查 |
| “脚本里加 LLM 更方便” | 本地检索与评分耦合，维护成本高 |
| “不建 Catalog 也行” | 频繁全量 `rg` 会变慢且不稳定 |

## Red Flags
- 直接给出推荐而不提供文件路径与行号
- 扫描未更新就开始查询
- 把生成的 `catalog.sqlite` 提交到仓库

