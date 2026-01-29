name: harmony-doc-pilot
description: Use when 需要在本地 HarmonyOS Markdown 文档中进行检索、生成候选与证据链，并在对话中完成二次筛选与总结时

# HarmonyDocPilot

## Overview
本技能定义“本地鸿蒙文档检索 + 证据链输出”的使用流程：脚本负责召回与证据，Codex 负责二次筛选与解释。

## When to Use
- 需要从本地 HarmonyOS 文档中定位候选 API/组件
- 需要输出可追溯证据（文件路径 + 行号 + 原文片段）
- 需要联动文档图片路径

不要用于：
- 仅需要在线文档检索
- 不要求证据链或本地文档路径

## Core Pattern
**原则：脚本只做检索与证据，LLM 不进入脚本。**
- 先扫描：`hdp_scan.py` 生成/更新 Catalog
- 再查询：`hdp_query.py` 输出 JSON（candidates/evidence/assets）
- 最后在对话中做二次筛选与总结

## Quick Reference
- 配置：`config/harmony-doc-pilot.yaml` 的 `docs_root`
- 扫描：`python3 tools/hdp_scan.py --config config/harmony-doc-pilot.yaml`
- 查询：`python3 tools/hdp_query.py --config config/harmony-doc-pilot.yaml --q "..." --topk 25 --final 6 --with-images`

## Implementation
**最小使用示例（单次查询）：**
```bash
python3 tools/hdp_query.py \
  --config config/harmony-doc-pilot.yaml \
  --q "ForEach 拖拽排序" --topk 25 --final 6 --with-images
```

## Common Mistakes
- 忘记设置 `docs_root` 导致扫描/查询为空
- 扫描未更新就直接查询
- 直接给出推荐而不提供证据链

## Rationalization Table
| Excuse | Reality |
|--------|---------|
| “先不用证据链，直接推荐” | 无证据无法溯源，结果不可复查 |
| “脚本里加 LLM 更方便” | 检索与评分耦合，维护成本高 |
| “不建 Catalog 也行” | 频繁全量 `rg` 变慢且不稳定 |

## Red Flags
- 直接给出推荐而不提供文件路径与行号
- 扫描未更新就开始查询
- 输出不包含 evidence/assets
