name: harmony-doc-pilot
description: Use when 需要在本地 HarmonyOS Markdown 文档中检索候选 API/组件并输出证据链，再在对话中完成二次筛选与总结时

# HarmonyDocPilot

## Overview
本技能规定“本地鸿蒙文档检索 + 证据链输出”的使用流程：脚本负责候选召回与证据，Codex 负责二次筛选与解释。

## When to Use
- 需要从本地 HarmonyOS 文档中定位候选 API/组件
- 需要输出可追溯证据（文件路径 + 行号 + 原文片段）
- 需要联动文档图片路径

不要用于：
- 仅需要在线文档检索
- 不要求证据链或本地文档路径

## Core Pattern
**原则：脚本只做检索与证据，LLM 不进入脚本。**
- 安装阶段：运行 `hdp_init.py` 生成/更新索引
- 使用阶段：运行 `hdp_query.py` 输出 JSON（candidates/evidence/assets）
- 对话阶段：在 Codex 中完成二次筛选与总结

## Quick Reference
- 配置：`config/harmony-doc-pilot.yaml` 的 `docs_root`
- 初始化：`python3 tools/hdp_init.py --config config/harmony-doc-pilot.yaml`
- 查询：`python3 tools/hdp_query.py --config config/harmony-doc-pilot.yaml --q "..." --topk 25 --final 6 --with-images`

## Implementation
**最小使用示例：**
```bash
python3 tools/hdp_init.py --config config/harmony-doc-pilot.yaml
python3 tools/hdp_query.py --config config/harmony-doc-pilot.yaml --q "ForEach 拖拽排序" --topk 25 --final 6 --with-images
```

## Common Mistakes
- 忘记设置 `docs_root`
- 未运行初始化就直接查询
- 直接给出推荐而不提供证据链

## Rationalization Table
| Excuse | Reality |
|--------|---------|
| “先不用证据链，直接推荐” | 无证据无法溯源，结果不可复查 |
| “脚本里加 LLM 更方便” | 检索与评分耦合，维护成本高 |
| “不建索引也行” | 全量 `rg` 会变慢且不稳定 |

## Red Flags
- 直接给出推荐而不提供文件路径与行号
- 未初始化就开始查询
- 输出不包含 evidence/assets
