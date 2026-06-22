#!/usr/bin/env python3
"""Daily Intelligence Radar — generates interactive HTML with sidebar archive (delete/modify/favorite)."""
import sys, json, smtplib, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

VAULT = Path.home() / "obsidian-vault"
SITE = Path.home() / "radar-site"
CONFIG = Path.home() / ".radar-config.json"
STATE_FILE = SITE / ".state.json"
RADAR_EMOJIS = ('🌍','💻','📈','⚽','🔥','📌','🤖','💰')

SECTION_CLASS = {'最热':'hot','关注':'watch','AI':'ai','前沿':'ai','金融':'finance','研判':'finance','摘要':'summary'}

def load_config():
    if CONFIG.exists(): return json.loads(CONFIG.read_text())
    CONFIG.write_text(json.dumps({"email":{"smtp_host":"","smtp_port":587,"username":"","password":"","from_addr":"","to_addr":""},"site":{"serve_port":8880}}, indent=2))
    return json.loads(CONFIG.read_text())

def load_state():
    if STATE_FILE.exists(): return json.loads(STATE_FILE.read_text())
    return {"favorites": [], "hidden": [], "notes": {}}

def save_state(state):
    SITE.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def linkify(text):
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)

def section_class(name):
    for kw, cls in SECTION_CLASS.items():
        if kw in name: return cls
    return 'category'

# ── content extraction ───────────────────────────────────

def get_today_radar():
    today = datetime.now().strftime("%Y-%m-%d")
    daily = VAULT / "_daily" / f"{today}.md"
    if not daily.exists(): return None, today, ""

    lines = daily.read_text().split('\n')
    summary, radar_start = "", None

    for i, line in enumerate(lines):
        if line.startswith('## 今日摘要') and not summary:
            for nl in lines[i+1:]:
                if nl.strip() and not nl.startswith('#'): summary = nl.strip(); break
        if line.startswith('## 情报雷达'):
            if 'Qwen' in line: radar_start = i
            elif radar_start is None: radar_start = i

    if radar_start is None:
        radar_start = next((i+1 for i, l in enumerate(lines) if l.startswith('## 今日摘要')), 0)

    radar_lines = []
    for line in lines[radar_start:]:
        if line.startswith('## ') and '情报雷达' in line: continue
        if line.startswith('## ') and '情报雷达' not in line:
            if not any(e in line for e in RADAR_EMOJIS): break
        radar_lines.append(line)
    return '\n'.join(radar_lines).strip(), today, summary

def discover_dates():
    dates = set()
    for f in (VAULT / "_daily").glob("*.md"):
        if '情报雷达' in f.read_text(): dates.add(f.stem)
    for f in SITE.glob("*.html"):
        if f.stem not in ("index", "archive"): dates.add(f.stem)
    return sorted(dates, reverse=True)

def get_article_id(date_str):
    """Extract or generate article ID from daily note."""
    daily = VAULT / "_daily" / f"{date_str}.md"
    if daily.exists():
        for line in daily.read_text().split('\n'):
            m = re.match(r'^id:\s*(\S+)', line)
            if m: return m.group(1)
    return date_str  # fallback: use date as ID

def get_article_title(date_str):
    daily = VAULT / "_daily" / f"{date_str}.md"
    if daily.exists():
        for line in daily.read_text().split('\n'):
            if line.strip().startswith('- ') and 'http' in line and len(line) > 10:
                return line.strip()[2:80].split('。')[0] + '。'
    return ""

# ── HTML generation ──────────────────────────────────────

CSS = """\
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Noto Sans SC",sans-serif;background:#0f172a;color:#e2e8f0;line-height:1.8;display:flex;min-height:100vh}
nav{width:180px;background:#0c1322;padding:20px 8px;position:fixed;left:0;top:0;bottom:0;overflow-y:auto;border-right:1px solid #1e293b;display:flex;flex-direction:column;gap:1px;z-index:10}
nav h3{color:#64748b;font-size:.7em;text-transform:uppercase;letter-spacing:1px;margin:12px 4px 6px;padding:0 4px}
nav a.sideline{display:flex;align-items:center;gap:6px;padding:7px 8px;color:#94a3b8;text-decoration:none;border-radius:6px;font-size:.8em;transition:all .15s;position:relative}
nav a.sideline:hover{background:#1e293b;color:#e2e8f0}
nav a.sideline.active{background:#1e3a5f;color:#38bdf8;font-weight:600}
nav a.sideline .date-tag{color:#38bdf8;font-weight:600;min-width:42px;font-size:.9em}
nav a.sideline .title-preview{color:#64748b;font-size:.75em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
nav a.all{color:#64748b;font-size:.75em;margin:12px 4px;padding:4px 8px}
/* sidebar action buttons */
.side-actions{display:none;gap:2px;margin-left:auto}
nav a.sideline:hover .side-actions{display:flex}
.side-actions button{background:none;border:none;color:#64748b;cursor:pointer;font-size:.7em;padding:2px 4px;border-radius:3px;transition:all .15s}
.side-actions button:hover{color:#e2e8f0;background:#334155}
.side-actions .fav{color:#fbbf24}.side-actions .fav.active{color:#f59e0b}
.side-actions .del:hover{color:#ef4444}
.side-actions .edit:hover{color:#38bdf8}
nav a.sideline.hidden-entry{opacity:.3}
nav a.sideline.favorite{border-left:2px solid #fbbf24}
/* main */
main{margin-left:180px;padding:40px 32px;max-width:780px;flex:1}
h1{font-size:2em;margin-bottom:4px;color:#f8fafc}
.date{color:#64748b;font-size:.9em;margin-bottom:8px}
.article-id{color:#334155;font-size:.7em;margin-bottom:24px;font-family:monospace}
.card{background:#1e293b;border-radius:12px;padding:20px 24px;margin-bottom:16px;border-left:4px solid #38bdf8}
.card h2{font-size:1.1em;margin-bottom:12px;color:#38bdf8}
.card h3{color:#fcd34d;margin-top:12px}
.card ul{list-style:none;padding:0}
.card li{padding:4px 0;color:#cbd5e1}
.card li::before{content:"▸ ";color:#38bdf8}
.card a{color:#38bdf8;text-decoration:none}
.card a:hover{text-decoration:underline}
.card p{color:#cbd5e1}
.card.hot{border-left-color:#f97316}.card.hot h2{color:#f97316}.card.hot p{color:#fdba74}
.card.watch{border-left-color:#a78bfa}.card.watch h2{color:#a78bfa}
.card.ai{border-left-color:#22d3ee}.card.ai h2{color:#22d3ee}.card.ai li::before{color:#22d3ee}
.card.finance{border-left-color:#fbbf24}.card.finance h2{color:#fbbf24}.card.finance li::before{color:#fbbf24}
.card.summary{border-left-color:#22c55e}.card.summary h2{color:#22c55e}
.footer{margin-top:40px;padding-top:20px;border-top:1px solid #334155;color:#475569;font-size:.8em}
.footer a{color:#64748b}
/* archive page */
body.arch{display:block;max-width:720px;margin:0 auto;padding:40px 24px}
.archive-item{display:flex;align-items:center;gap:16px;padding:12px 16px;background:#1e293b;border-radius:8px;margin-bottom:8px;text-decoration:none;color:#cbd5e1;transition:background .2s}
.archive-item:hover{background:#334155}
.archive-date{font-weight:600;color:#38bdf8;min-width:50px;font-size:.95em}
.archive-snippet{color:#94a3b8;font-size:.9em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.archive-item.today{border:1px solid #38bdf8}
a.back{color:#64748b;display:inline-block;margin-top:32px}
"""
JS = r"""
<script>
const STATE = {hidden: [], favorites: [], notes: {}};

function api(action, id, val) {
  return fetch('/api', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, id, value: val})
  }).then(r => r.json());
}

function initSidebar() {
  api('load').then(s => {
    Object.assign(STATE, s);
    document.querySelectorAll('a.sideline').forEach(el => {
      const id = el.dataset.id;
      if (STATE.hidden.includes(id)) el.classList.add('hidden-entry');
      if (STATE.favorites.includes(id)) {
        el.classList.add('favorite');
        const btn = el.querySelector('.fav');
        if (btn) { btn.textContent = '★'; btn.classList.add('active'); }
      }
    });
  });
}

function toggleFav(id, btn) {
  const isFav = STATE.favorites.includes(id);
  api(isFav ? 'unfav' : 'fav', id).then(s => {
    STATE.favorites = s.favorites;
    const el = document.querySelector(`a.sideline[data-id="${id}"]`);
    if (isFav) {
      el.classList.remove('favorite');
      btn.textContent = '☆'; btn.classList.remove('active');
    } else {
      el.classList.add('favorite');
      btn.textContent = '★'; btn.classList.add('active');
    }
  });
}

function hideEntry(id, btn) {
  if (!confirm('隐藏这条雷达？可通过归档页恢复。')) return;
  api('hide', id).then(s => {
    STATE.hidden = s.hidden;
    document.querySelector(`a.sideline[data-id="${id}"]`).classList.add('hidden-entry');
  });
}

function editEntry(id) {
  window.open('/edit/' + id, '_blank');
}

document.addEventListener('DOMContentLoaded', initSidebar);
</script>
"""

def render_card(emoji, name, items):
    cls = section_class(name)
    html = f'<div class="card {cls}"><h2>{emoji} {name}</h2>'
    if items:
        has_custom = any(it.startswith('<h3>') or it.startswith('<p>') for it in items)
        if not has_custom: html += '<ul>'
        for item in items:
            html += item if has_custom else f'<li>{item}</li>'
        if not has_custom: html += '</ul>'
    return html + '</div>\n'

def parse_md_body(md_text):
    sections = []
    cur_emoji, cur_name, cur_items = "", "", []
    for line in md_text.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('## '):
            if cur_name: sections.append((cur_emoji, cur_name, cur_items))
            parts = line[3:].split(' ', 1)
            cur_emoji, cur_name = (parts[0], parts[1]) if len(parts) == 2 else ("", line[3:])
            cur_items = []
        elif line.startswith('- '): cur_items.append(f'<li>{linkify(line[2:])}</li>')
        elif line.startswith('### '): cur_items.append(f'<h3>{linkify(line[4:])}</h3>')
        elif line: cur_items.append(f'<p>{linkify(line)}</p>')
    if cur_name: sections.append((cur_emoji, cur_name, cur_items))
    return sections

def build_sidebar(dates, today, state):
    items = ""
    for d in dates:
        aid = get_article_id(d)
        title = get_article_title(d)
        hidden = 'hidden-entry' if aid in state.get('hidden', []) else ''
        fav = 'favorite' if aid in state.get('favorites', []) else ''
        active = 'active' if d == today else ''
        items += f"""<a href="{d}.html" class="sideline {active} {hidden} {fav}" data-id="{aid}">
  <span class="date-tag">{d[-5:]}</span>
  <span class="title-preview" title="{title}">{title[:20] or '📡'}</span>
  <span class="side-actions">
    <button class="fav" onclick="event.preventDefault();toggleFav('{aid}',this)" title="收藏">☆</button>
    <button class="edit" onclick="event.preventDefault();editEntry('{aid}')" title="修改">✎</button>
    <button class="del" onclick="event.preventDefault();hideEntry('{aid}',this)" title="隐藏">✕</button>
  </span>
</a>\n"""
    return items

def build_archive(dates, today, state):
    items = ""
    for d in dates:
        aid = get_article_id(d)
        if aid in state.get('hidden', []): continue
        preview = ""
        daily_f = VAULT / "_daily" / f"{d}.md"
        if daily_f.exists():
            for line in daily_f.read_text().split('\n'):
                if line.strip().startswith('- ') and len(line) > 5: preview = line.strip()[2:100]; break
        hl = "today" if d == today else ""
        items += f'<a href="{d}.html" class="archive-item {hl}"><span class="archive-date">{d[-5:]}</span><span class="archive-snippet">{preview[:60]}</span></a>\n'
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>历史记录</title><style>{CSS}</style></head><body class="arch"><h1>📋 历史记录</h1><div class="archive-list">{items}</div><a href="/" class="back">← 返回最新</a></body></html>"""

def build_page(today, article_id, summary, sections, sidebar_html):
    cards = ''.join(render_card(emoji, name, items) for emoji, name, items in sections)
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>情报雷达 · {today}</title><style>{CSS}</style></head><body><nav><h3>📡 情报雷达</h3>{sidebar_html}<a href="/archive.html" class="all">查看全部 →</a></nav><main><h1>🛰️ 情报雷达</h1><div class="date">{today}</div><div class="article-id">#{article_id}</div><div class="card summary"><h2>📝 今日摘要</h2><p>{summary}</p></div>{cards}<div class="footer">Generated by Claude Code + Qwen3.6:27b · <a href="/archive.html">全部历史</a></div></main>{JS}</body></html>"""

# ── API handler ──────────────────────────────────────────

def handle_api(post_data):
    state = load_state()
    data = json.loads(post_data) if isinstance(post_data, str) else post_data
    action = data.get('action', '')
    aid = data.get('id', '')

    if action == 'load': return state
    elif action == 'fav' and aid not in state['favorites']:
        state['favorites'].append(aid)
    elif action == 'unfav' and aid in state['favorites']:
        state['favorites'].remove(aid)
    elif action == 'hide' and aid not in state['hidden']:
        state['hidden'].append(aid)
    elif action == 'unhide' and aid in state['hidden']:
        state['hidden'].remove(aid)
    elif action == 'note':
        state['notes'][aid] = data.get('value', '')

    save_state(state)
    return state

# ── actions ──────────────────────────────────────────────

def publish(config):
    radar, today, summary = get_today_radar()
    if not radar: print(f"No radar for {today}"); sys.exit(1)

    dates = discover_dates()
    state = load_state()
    sections = parse_md_body(radar)
    article_id = get_article_id(today)

    sidebar = build_sidebar(dates, today, state)

    html = build_page(today, article_id, summary, sections, sidebar)
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html)
    (SITE / f"{today}.html").write_text(html)
    (SITE / "archive.html").write_text(build_archive(dates, today, state))

    # Email
    cfg = config.get("email", {})
    if cfg.get("smtp_host"):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"情报雷达 · #{article_id}"
        msg["From"] = cfg["from_addr"]; msg["To"] = cfg["to_addr"]
        msg.attach(MIMEText(html, "html", "utf-8"))
        try:
            with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as s:
                s.starttls(); s.login(cfg["username"], cfg["password"]); s.send_message(msg)
            print(f"Email → {cfg['to_addr']}")
        except Exception as e: print(f"Email: {e}")
    else: print("Email: not configured")

    print(f"Published #{article_id} → Obsidian + site + archive")

def serve(port):
    import os, http.server
    from urllib.parse import urlparse

    class RadarHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(SITE), **kwargs)

        def do_POST(self):
            if self.path == '/api':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode()
                result = handle_api(body)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_error(404)

        def do_GET(self):
            if self.path.startswith('/edit/'):
                aid = self.path.split('/edit/')[1]
                # Find the daily file by ID
                daily_file = None
                for f in (VAULT / "_daily").glob("*.md"):
                    content = f.read_text()
                    if f'id: {aid}' in content or f.stem == aid:
                        daily_file = f; break
                if daily_file:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(daily_file.read_text().encode())
                else:
                    self.send_error(404, f"Article {aid} not found")
            elif self.path == '/api':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(load_state()).encode())
            else:
                super().do_GET()

    os.chdir(SITE)
    print(f"Serving http://localhost:{port}")
    http.server.HTTPServer(('127.0.0.1', port), RadarHandler).serve_forever()

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "publish"
    cfg = load_config()

    if action == "publish": publish(cfg)
    elif action == "serve": serve(cfg.get("site", {}).get("serve_port", 8880))
    elif action == "config": print(json.dumps(cfg, indent=2, ensure_ascii=False))
