# HarmonyDocPilot

HarmonyDocPilot 是一个基于**本地 HarmonyOS Markdown 文档**的检索工具链。它不搬运文档，只读取原文档目录，并把结构化索引保存到本地 SQLite，用于快速召回候选 API/组件与证据链。

## 使用流程（最少步骤）

### 1) 配置文档根目录
编辑：`harmony-doc-pilot/config/harmony-doc-pilot.yaml`

```yaml
docs_root: /你的/鸿蒙/文档/根目录
```

### 2) 初始化索引（安装阶段 / 文档更新时）
```bash
python3 harmony-doc-pilot/tools/hdp_init.py \
  --config harmony-doc-pilot/config/harmony-doc-pilot.yaml
```

### 3) 日常查询（使用阶段）
```bash
python3 harmony-doc-pilot/tools/hdp_query.py \
  --config harmony-doc-pilot/config/harmony-doc-pilot.yaml \
  --q "ForEach 拖拽排序" --topk 25 --final 6 --with-images
```

## 安装方式（可选）
你可以把 `harmony-doc-pilot/` 作为 Codex skill 目录使用：
- 全局：`~/.codex/skills/harmony-doc-pilot`（软链）
- 项目内：`<project>/skills/harmony-doc-pilot`（软链）

## 文档与索引的存储结构
- **文档本体**：保持原目录不动（`docs_root` 指向的目录）
- **索引**：`harmony-doc-pilot/data/catalog.sqlite`
- **查询缓存**：`harmony-doc-pilot/data/cache/*.json`

> 索引只保存结构化信息（路径/章节/行号/符号/图片引用），不保存全文。查询时按行号回读原文片段作为证据。

## 输出说明（JSON）
- `candidates`：候选 API/组件
- `evidence`：证据片段（路径 + 行号 + 原文）
- `assets`：图片路径（可选）
- `stats`：统计信息

