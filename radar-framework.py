#!/usr/bin/env python3
"""
Radar Framework — enforces consistent structure for daily intelligence radar.
Usage: python3 radar-framework.py validate|fix|template|prompt
"""
import sys, re, json
from datetime import datetime
from pathlib import Path

VAULT = Path.home() / "obsidian-vault"
FRAMEWORK_DIR = Path.home() / ".radar-framework"

# ── Schema definition ───────────────────────────────────

SCHEMA = {
    "今日摘要": {
        "type": "paragraph",
        "min_chars": 200,
        "max_chars": 500,
        "description": "一段话概括今日全球最重要5-7件事"
    },
    "💰 金融研判": {
        "type": "section",
        "subsections": ["NASDAQ/VGT 分析", "估值判断", "今日新金融理念"],
        "description": "VGT/NASDAQ技术面+估值+金融新概念"
    },
    "🤖 AI前沿": {
        "type": "section",
        "subsections": ["评价", "🐦 推特风向"],
        "bullet_min": 3, "bullet_max": 5,
        "description": "AI领域新突破+深度评价+推特风向"
    },
    "🌍 国际地缘": {
        "type": "news",
        "bullet_count": 3,
        "max_len": 30,
        "description": "国际政治/地缘新闻"
    },
    "💻 科技": {
        "type": "news",
        "bullet_count": 3,
        "max_len": 30,
        "description": "科技/互联网新闻"
    },
    "📈 财经": {
        "type": "news",
        "bullet_count": 2,
        "max_len": 30,
        "description": "财经/市场新闻"
    },
    "⚽ 世界杯": {
        "type": "news",
        "bullet_count": 1,
        "max_len": 40,
        "description": "世界杯赛况（赛期外可省略）"
    },
    "🔥 今日最热": {
        "type": "news",
        "bullet_count": 1,
        "max_len": 40,
        "description": "今日最重要的1件事"
    },
    "📌 明日关注": {
        "type": "news",
        "bullet_count": 1,
        "max_len": 40,
        "description": "明天最值得盯的1件事"
    },
}

SECTION_ORDER = list(SCHEMA.keys())  # order as defined above

# ── template generation ─────────────────────────────────

def generate_template(date_str=None):
    """Generate a clean daily note template."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        "tags: [daily]",
        f"created: {date_str}",
        "---",
        "",
        f"# {date_str}",
        "",
        "## 今日摘要",
        "",
        "[400字摘要，覆盖今日最重要5-7件事]",
        "",
        "## 情报雷达（Qwen3.6:27b 生成）",
        "",
    ]
    for section in SECTION_ORDER:
        info = SCHEMA[section]
        lines.append(f"## {section}")
        lines.append("")
        if info["type"] == "section":
            for sub in info.get("subsections", []):
                lines.append(f"### {sub}")
                lines.append("[内容]")
                lines.append("")
        elif info["type"] == "news":
            for _ in range(info.get("bullet_count", 1)):
                lines.append("- [一句话新闻，≤30字。](https://来源URL)")
            lines.append("")
        elif info["type"] == "paragraph":
            lines.append("[段落内容]")
            lines.append("")

    return "\n".join(lines)

# ── validation ──────────────────────────────────────────

def validate_daily(filepath=None):
    """Check daily note against schema. Returns list of issues."""
    if filepath is None:
        filepath = VAULT / "_daily" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    else:
        filepath = Path(filepath)

    if not filepath.exists():
        return [f"File not found: {filepath}"]

    content = filepath.read_text()
    lines = content.split('\n')
    issues = []

    # Check section presence
    for section in SECTION_ORDER:
        if f"## {section}" not in content:
            issues.append(f"Missing section: {section}")

    # Check summary length
    in_summary = False
    summary_text = ""
    for line in lines:
        if line.startswith("## 今日摘要"):
            in_summary = True; continue
        if in_summary:
            if line.startswith("## "):
                break
            summary_text += line.strip()

    summary_len = len(summary_text)
    spec = SCHEMA.get("今日摘要", {})
    if summary_len < spec.get("min_chars", 0):
        issues.append(f"Summary too short: {summary_len} chars (min {spec['min_chars']})")
    elif summary_len > spec.get("max_chars", 999):
        issues.append(f"Summary too long: {summary_len} chars (max {spec['max_chars']})")

    # Check news sections have proper bullet format with links
    for section, info in SCHEMA.items():
        if info["type"] != "news":
            continue
        bullets = extract_section_bullets(lines, section)
        if len(bullets) < info.get("bullet_count", 0):
            issues.append(f"{section}: only {len(bullets)} bullets (need {info['bullet_count']})")
        for b in bullets:
            # Extract just the text part (before URL) for length check
            text_only = re.sub(r'\[([^\]]*)\].*', r'\1', b)
            if len(text_only) > info.get("max_len", 100):
                issues.append(f"{section}: bullet text too long ({len(text_only)} chars, max {info['max_len']}): {text_only[:50]}...")
            if "http" not in b:
                issues.append(f"{section}: bullet missing link: {b[:60]}...")

    # Check blank lines sanity
    blank_count = sum(1 for l in lines if not l.strip())
    if blank_count > 40:
        issues.append(f"Too many blank lines: {blank_count} (target < 40)")

    return issues

def extract_section_bullets(lines, section_name):
    """Extract bullet points from a specific ## section."""
    bullets = []
    in_section = False
    for line in lines:
        if line.startswith(f"## {section_name}"):
            in_section = True; continue
        if in_section:
            if line.startswith("## ") and section_name not in line:
                break
            if line.strip().startswith("- "):
                bullets.append(line.strip()[2:])
    return bullets

# ── auto-fix ────────────────────────────────────────────

def fix_daily(filepath=None):
    """Auto-fix common formatting issues."""
    if filepath is None:
        filepath = VAULT / "_daily" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    else:
        filepath = Path(filepath)

    content = filepath.read_text()
    lines = content.split('\n')
    fixes = []

    # Fix 1: Remove consecutive blank lines
    cleaned = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            fixes.append("removed consecutive blank")
            continue
        cleaned.append(line)
        prev_blank = is_blank

    # Fix 2: Ensure single blank around ## headings
    fixed = []
    for i, line in enumerate(cleaned):
        if line.startswith("## "):
            # ensure blank before (unless first content line)
            if fixed and fixed[-1].strip():
                fixed.append("")
                fixes.append("added blank before heading")
            fixed.append(line)
            # ensure blank after
            if i + 1 < len(cleaned) and cleaned[i+1].strip() and not cleaned[i+1].startswith("#"):
                fixed.append("")
        else:
            fixed.append(line)

    # Fix 3: Ensure radar header is present
    if "## 情报雷达（Qwen3.6:27b 生成）" not in content:
        # Find summary section and insert radar header after it
        for i, line in enumerate(fixed):
            if line.startswith("## 今日摘要"):
                # Find next ## section
                for j in range(i+1, len(fixed)):
                    if fixed[j].startswith("## "):
                        fixed.insert(j, "")
                        fixed.insert(j+1, "## 情报雷达（Qwen3.6:27b 生成）")
                        fixes.append("inserted radar header")
                        break
                break

    result = "\n".join(fixed)
    filepath.write_text(result)
    return len(fixes), fixes[:10]

# ── Qwen prompt template ────────────────────────────────

PROMPT_TEMPLATE = """你是资深情报分析官。基于以下实时新闻数据，生成一份结构严谨的情报雷达日报。

**严格要求：**
1. 直接输出，不要思考过程
2. 每个 ## 栏目严格按指定数量输出
3. 每条新闻必须附带原始来源URL markdown链接格式
4. 新闻条目 ≤{max_news_len}字，信息密集

**输出格式（不可修改）：**

## 今日摘要
[一段话，{summary_min}-{summary_max}字，覆盖今日全球最重要5-7件事，信息密集]

## 情报雷达（Qwen3.6:27b 生成）

{sections_format}

---
实时新闻数据：
{news_data}
"""

def generate_prompt(news_bullets, sections=None):
    """Generate a standardized Qwen prompt from news items."""
    if sections is None:
        sections = [s for s in SECTION_ORDER if s not in ("今日摘要",)]

    sections_format = ""
    for section in sections:
        info = SCHEMA[section]
        sections_format += f"## {section}\n"
        if info["type"] == "news":
            for _ in range(info.get("bullet_count", 1)):
                sections_format += f"- [一句话，≤{info['max_len']}字。](URL)\n"
        elif info["type"] == "section":
            for sub in info.get("subsections", []):
                sections_format += f"### {sub}\n[内容]\n"
        sections_format += "\n"

    summary_spec = SCHEMA["今日摘要"]
    return PROMPT_TEMPLATE.format(
        max_news_len=30,
        summary_min=summary_spec["min_chars"],
        summary_max=summary_spec["max_chars"],
        sections_format=sections_format,
        news_data="\n".join(f"- {b}" for b in news_bullets)
    )

# ── template save/load ──────────────────────────────────

def save_template():
    tpl = generate_template()
    (FRAMEWORK_DIR / "daily-template.md").write_text(tpl)
    (VAULT / "_templates" / "daily-radar.md").write_text(tpl)
    print(f"Template saved to {VAULT}/_templates/daily-radar.md")
    return tpl

# ── CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    FRAMEWORK_DIR.mkdir(exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    target = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "validate":
        issues = validate_daily(target)
        if issues:
            print(f"⚠ {len(issues)} issues:")
            for i in issues: print(f"  - {i}")
        else:
            print("✅ All checks passed")

    elif cmd == "fix":
        n, fixes = fix_daily(target)
        print(f"Fixed {n} issues: {fixes}")

    elif cmd == "template":
        save_template()

    elif cmd == "prompt":
        # Generate prompt from a news file or stdin
        news = sys.stdin.read().strip().split('\n') if not sys.stdin.isatty() else []
        print(generate_prompt(news))

    elif cmd == "schema":
        print(json.dumps(SCHEMA, indent=2, ensure_ascii=False))
