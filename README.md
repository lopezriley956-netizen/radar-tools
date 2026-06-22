# 🛰️ 情报雷达 · Intelligence Radar

AI 驱动的每日情报雷达系统：自动收集新闻 → Qwen3.6:27b 推理 → Obsidian + 网页 + 邮件三渠道发布。

## 组件

| 文件 | 功能 |
|------|------|
| `radar-publish.py` | 主发布系统：Markdown→HTML+侧边栏+邮件 |
| `radar-framework.py` | 内容框架：模板/验证/修复/Prompt生成 |
| `search-proxy.py` | Bing 搜索代理（国内可用） |
| `ollama-skills/` | Qwen3.6 专用 Skill：程序员×3 + 金融分析师×3 |
| `template.md` | 每日笔记模板 |

## 快速开始

```bash
# 1. 发布今日雷达
python3 radar-publish.py publish

# 2. 启动网页服务（含交互式侧边栏）
python3 radar-publish.py serve

# 3. 验证内容规范性
python3 radar-framework.py validate

# 4. 生成空白模板
python3 radar-framework.py template
```

## 依赖

- Python 3.12+
- Ollama + Qwen3.6:27b
- Agent-Reach（多平台搜索）
- QQ邮箱 SMTP（邮件发布）

## 架构

```
WebSearch → Qwen3.6:27b → Obsidian _daily/
                         → radar-site/index.html (localhost:8880)
                         → QQ邮箱
```
