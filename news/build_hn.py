#!/usr/bin/env python3
"""
News page generator — Hacker News style.
Numbered list, title-only with expandable content, ultra-dense.
"""
import json
import os
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape

# Paths
FEED_PATH = os.path.expanduser("~/.openclaw/workspace/data/tg-gateway/out/feed.jsonl")
MEDIA_SRC = os.path.expanduser("~/.openclaw/workspace/data/tg-gateway/out/media")
SCRIPT_DIR = Path(__file__).parent
MEDIA_DST = SCRIPT_DIR / "media"
OUTPUT = SCRIPT_DIR / "index.html"

TZ_OFFSET = timedelta(hours=2)
TZ_NICOSIA = timezone(TZ_OFFSET)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

URL_RE = re.compile(r'(https?://[^\s<>&]+)')

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def parse_ts(ts_str):
    ts_str = ts_str.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        return datetime.now(timezone.utc)


def to_local(dt):
    return dt.astimezone(TZ_NICOSIA)


def format_time(dt):
    return to_local(dt).strftime("%H:%M")


def format_date_ru(dt):
    local = to_local(dt)
    return f"{local.day} {MONTHS_RU[local.month]} {local.year}"


def format_date_key(dt):
    return to_local(dt).strftime("%Y-%m-%d")


def ago(dt):
    """Time ago string."""
    now = datetime.now(timezone.utc)
    delta = now - dt
    mins = int(delta.total_seconds() / 60)
    if mins < 60:
        return f"{mins} min ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def sync_media():
    MEDIA_DST.mkdir(exist_ok=True)
    if not os.path.isdir(MEDIA_SRC):
        return
    for f in os.listdir(MEDIA_SRC):
        src = os.path.join(MEDIA_SRC, f)
        dst = MEDIA_DST / f
        if not dst.exists() or os.path.getmtime(src) > os.path.getmtime(str(dst)):
            shutil.copy2(src, dst)


def linkify(text_escaped):
    def _replace(m):
        url = m.group(1)
        start = m.start()
        before = text_escaped[max(0, start - 6):start]
        if 'href="' in before or "href='" in before:
            return m.group(0)
        after_end = text_escaped[m.end():m.end() + 4]
        if after_end.startswith('</a>'):
            return m.group(0)
        return f'<a href="{url}" target="_blank" rel="noopener">{url}</a>'
    return URL_RE.sub(_replace, text_escaped)


def render_text(text, links=None):
    if not text:
        return ""
    escaped = escape(text)
    if links:
        used = set()
        sorted_links = sorted(links, key=lambda l: len(l.get('text', '')), reverse=True)
        for link in sorted_links:
            anchor = link.get('text', '').strip()
            url = link.get('url', '')
            if not anchor or not url or anchor in used:
                continue
            escaped_anchor = escape(anchor)
            if escaped_anchor in escaped:
                a_tag = f'<a href="{escape(url)}" target="_blank" rel="noopener">{escaped_anchor}</a>'
                escaped = escaped.replace(escaped_anchor, a_tag, 1)
                used.add(anchor)
    linked = linkify(escaped)
    return linked.replace('\n', '<br>\n')


def get_title(text):
    t = (text or "").strip()
    if not t:
        return "Media"
    first_line = t.split("\n")[0].strip()
    if len(first_line) > 140:
        return first_line[:137] + "..."
    return first_line


def get_domain(links):
    """Extract first link domain for display."""
    if not links:
        return ""
    for l in links:
        url = l.get('url', '')
        if url.startswith('http'):
            try:
                from urllib.parse import urlparse
                host = urlparse(url).hostname or ''
                host = host.replace('www.', '')
                return host
            except:
                pass
    return ""


def render_media_full(post):
    if not post.get('has_media'):
        return ""
    media_path = post.get('media_path')
    if not media_path:
        return ""
    filename = os.path.basename(media_path)
    local_path = MEDIA_DST / filename
    ext = os.path.splitext(filename)[1].lower()
    if not local_path.exists():
        return ""
    if ext in IMAGE_EXTS:
        return f'<img class="full-img" src="media/{escape(filename)}" alt="" loading="lazy">\n'
    elif ext in VIDEO_EXTS:
        return f'<video class="full-img" src="media/{escape(filename)}" controls preload="metadata"></video>\n'
    return ""


def render_post(post, num):
    ts = parse_ts(post['ts'])
    channel = escape(post.get('peer_title', ''))
    text = post.get('text', '') or ""
    title = escape(get_title(text))
    time_ago = ago(ts)
    time_str = format_time(ts)

    all_links = (post.get('links') or []) + (post.get('buttons') or [])
    domain = get_domain(all_links)
    domain_html = f' <span class="domain">({domain})</span>' if domain else ''

    # First link URL for title
    first_url = ""
    for l in all_links:
        u = l.get('url', '')
        if u.startswith('http'):
            first_url = escape(u)
            break

    if first_url:
        title_html = f'<a href="{first_url}" target="_blank" rel="noopener" class="title-link">{title}</a>'
    else:
        title_html = f'<span class="title-text">{title}</span>'

    # Full body for expand
    lines = text.strip().split('\n')
    body_text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
    body_html = render_text(body_text, all_links) if body_text else ""
    media_html = render_media_full(post)

    has_expand = body_html or media_html
    if has_expand:
        expand = f'''<details class="expand"><summary class="expand-btn">[+]</summary><div class="expand-body">{media_html}{body_html}</div></details>'''
    else:
        expand = ''

    # Forward info
    fwd = ""
    fwd_from = post.get('forward_from')
    if fwd_from:
        if isinstance(fwd_from, dict):
            fname = escape(str(fwd_from.get('name') or ''))
        else:
            fname = escape(str(fwd_from or ''))
        if fname:
            fwd = f' | via {fname}'

    return f'''<tr class="item">
  <td class="num">{num}.</td>
  <td class="content">
    <div class="title-row">{title_html}{domain_html}</div>
    <div class="sub">{channel} | {time_str} ({time_ago}){fwd} {expand}</div>
  </td>
</tr>'''


CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0a0a1a;
  --surface: #12122a;
  --header-bg: #7C3AED;
  --accent: #A78BFA;
  --accent-dim: rgba(167,139,250,0.15);
  --ink: #e0e0e0;
  --link: #e8e8e8;
  --visited: #888;
  --meta: #6b6b8a;
  --border: #1e1e3a;
  --font: 'Inter', -apple-system, system-ui, sans-serif;
  --mono: 'JetBrains Mono', monospace;
}

body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.4;
  -webkit-font-smoothing: antialiased;
}

/* Header bar */
.header {
  background: linear-gradient(135deg, #7C3AED, #60a5fa);
  padding: 6px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header .logo {
  font-weight: 800;
  font-size: 14px;
  color: #fff;
  text-decoration: none;
  background: rgba(255,255,255,0.2);
  border-radius: 6px;
  padding: 2px 8px;
  letter-spacing: -0.02em;
}

.header .site-name {
  font-weight: 700;
  font-size: 14px;
  color: #fff;
  text-decoration: none;
}

.header .nav {
  font-size: 13px;
  color: rgba(255,255,255,0.7);
  margin-left: auto;
}

/* Date divider */
.date-row td {
  padding: 18px 0 8px 36px;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-family: var(--mono);
  border-bottom: 1px solid var(--border);
}

/* Main table */
.feed {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  border-collapse: collapse;
}

.item td {
  padding: 5px 0;
  vertical-align: top;
}

.item:hover {
  background: var(--accent-dim);
}

.item {
  transition: background 0.15s ease;
}

.num {
  width: 36px;
  text-align: right;
  padding-right: 10px !important;
  color: var(--meta);
  font-size: 12px;
  font-family: var(--mono);
  font-weight: 500;
}

.title-row {
  font-size: 15px;
  line-height: 1.4;
}

.title-link {
  color: var(--link);
  text-decoration: none;
  font-weight: 500;
}

.title-link:visited {
  color: var(--visited);
}

.title-link:hover {
  color: var(--accent);
}

.title-text {
  color: var(--ink);
  font-weight: 500;
}

.domain {
  font-size: 11px;
  color: var(--meta);
  font-family: var(--mono);
}

.sub {
  font-size: 12px;
  color: var(--meta);
  padding-top: 2px;
  padding-bottom: 6px;
}

/* Expandable */
.expand {
  display: inline;
}

.expand-btn {
  display: inline;
  cursor: pointer;
  list-style: none;
  color: var(--accent);
  font-weight: 500;
  font-size: 12px;
}

.expand-btn::-webkit-details-marker { display: none; }

.expand-btn:hover {
  text-decoration: underline;
}

.expand-body {
  margin: 10px 0 8px;
  padding: 14px 16px;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--border);
  font-size: 13.5px;
  line-height: 1.65;
  color: #bbb;
  max-width: 700px;
}

.expand-body a {
  color: var(--accent);
  text-decoration: none;
}

.expand-body a:hover {
  text-decoration: underline;
}

.full-img {
  max-width: 100%;
  border-radius: 6px;
  margin-bottom: 10px;
  display: block;
}

/* Footer */
.footer {
  text-align: center;
  padding: 20px;
  font-size: 12px;
  color: var(--meta);
  border-top: 1px solid var(--border);
  max-width: 800px;
  margin: 12px auto 0;
}

/* Scrollbar */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--meta); }

/* Mobile */
@media (max-width: 480px) {
  .header { padding: 6px 8px; }
  .feed { font-size: 13px; }
  .title-row { font-size: 14px; }
  .num { width: 30px; font-size: 11px; }
  .date-row td { padding-left: 30px; }
}
"""


def build():
    sync_media()

    posts = []
    with open(FEED_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))

    posts.sort(key=lambda p: p.get('ts', ''), reverse=True)
    n = len(posts)

    if posts:
        newest_ts = parse_ts(posts[0]['ts'])
        date_ru = format_date_ru(newest_ts)
    else:
        date_ru = "—"

    # Group by date
    grouped = {}
    for p in posts:
        ts = parse_ts(p['ts'])
        key = format_date_key(ts)
        local = to_local(ts)
        label = f"{local.day} {MONTHS_RU[local.month]}"
        if key not in grouped:
            grouped[key] = {'label': label, 'posts': []}
        grouped[key]['posts'].append(p)

    rows = []
    num = 1
    for key in sorted(grouped.keys(), reverse=True):
        group = grouped[key]
        rows.append(f'<tr class="date-row"><td colspan="2">{group["label"]}</td></tr>')
        for p in group['posts']:
            rows.append(render_post(p, num))
            num += 1

    table = '\n'.join(rows)

    html_out = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<base href="/news/">
<title>AI News — {date_ru}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="header">
  <a href="/news/" class="logo">N</a>
  <a href="/news/" class="site-name">AI News</a>
  <span class="nav">{n} posts | {date_ru}</span>
</div>
<table class="feed">
{table}
</table>
<div class="footer">Collected from 27+ AI/ML Telegram channels &middot; msolo.me</div>
</body>
</html>
'''

    OUTPUT.write_text(html_out, encoding='utf-8')
    media_count = len(list(MEDIA_DST.iterdir())) if MEDIA_DST.exists() else 0
    print(f"Generated {OUTPUT} — {n} posts, date: {date_ru}")
    print(f"Media files: {media_count}")


if __name__ == '__main__':
    build()
