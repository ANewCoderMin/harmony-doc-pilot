# HarmonyDocPilot

本项目提供 HarmonyOS 文档本地检索能力：\n
- 扫描 Markdown 文档构建 Catalog  
- 查询候选 API/组件并输出 JSON（含证据与图片路径）  

目标场景：在 Codex 对话中先用脚本召回候选与证据，再由 Codex 完成二次筛选与总结。

## 目录结构
- `harmony-doc-pilot/`：Codex skill 目录  
  - `config/`：配置（设置 docs_root）  
  - `tools/`：扫描与查询脚本  
  - `data/`：运行期数据库与缓存（默认不入库）  

## 快速开始

### 1) 配置文档路径
修改：`harmony-doc-pilot/config/harmony-doc-pilot.yaml`

```yaml
docs_root: /你的/鸿蒙/文档/根目录
```

### 2) 准备依赖（推荐 venv）
```bash
python3 -m venv .venv
.venv/bin/pip install pyyaml
```

### 3) 构建 Catalog
```bash
.venv/bin/python harmony-doc-pilot/tools/hdp_scan.py \
  --config harmony-doc-pilot/config/harmony-doc-pilot.yaml
```

### 4) 查询
```bash
.venv/bin/python harmony-doc-pilot/tools/hdp_query.py \
  --config harmony-doc-pilot/config/harmony-doc-pilot.yaml \
  --q "ForEach 拖拽排序" --topk 25 --final 6 --with-images
```

## 安装到 Codex

### 全局安装（推荐）
```bash
mkdir -p ~/.codex/skills
ln -s /absolute/path/to/harmony-doc-pilot/harmony-doc-pilot ~/.codex/skills/harmony-doc-pilot
```

### 项目内安装
```bash
mkdir -p skills
ln -s /absolute/path/to/harmony-doc-pilot/harmony-doc-pilot skills/harmony-doc-pilot
```

## 运行期产物说明
以下文件会在运行时产生，不建议纳入版本控制（已在 `.gitignore` 排除）：  
- `harmony-doc-pilot/data/catalog.sqlite`  
- `harmony-doc-pilot/data/cache/*.json`  
- `__pycache__/` 与 `*.pyc`  
