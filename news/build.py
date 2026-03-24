#!/usr/bin/env python3
"""
News page generator for msolo.me/news
Reads feed.jsonl from Telethon daemon, generates index.html
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape

# Paths
FEED_PATH = os.path.expanduser("~/.openclaw/workspace/data/tg-gateway/out/feed.jsonl")
MEDIA_SRC = os.path.expanduser("~/.openclaw/workspace/data/tg-gateway/out/media")
SCRIPT_DIR = Path(__file__).parent
MEDIA_DST = SCRIPT_DIR / "media"
OUTPUT = SCRIPT_DIR / "index.html"

# Timezone: Europe/Nicosia = UTC+2 (winter) / UTC+3 (summer)
# March 2026 = EET+3 (DST active from last Sunday of March)
TZ_OFFSET = timedelta(hours=2)  # EET; adjust if needed

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}


def parse_ts(ts_str):
    """Parse UTC timestamp string to datetime"""
    ts_str = ts_str.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(ts_str)
    except:
        return datetime.now(timezone.utc)


def to_local(dt):
    """Convert UTC datetime to local time"""
    return dt + TZ_OFFSET


def format_time(dt):
    local = to_local(dt)
    return local.strftime("%H:%M")


def format_date(dt):
    local = to_local(dt)
    months_ru = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    return f"{local.day} {months_ru[local.month]} {local.year}"


def sync_media():
    """Copy media files from daemon output to news/media/"""
    MEDIA_DST.mkdir(exist_ok=True)
    if not os.path.isdir(MEDIA_SRC):
        return
    for f in os.listdir(MEDIA_SRC):
        src = os.path.join(MEDIA_SRC, f)
        dst = MEDIA_DST / f
        if not dst.exists() or os.path.getmtime(src) > os.path.getmtime(str(dst)):
            shutil.copy2(src, dst)


def render_text(text):
    """Escape HTML and convert newlines to <br>, preserve URLs as links"""
    if not text:
        return ""
    text = escape(text)
    # Convert URLs to clickable links
    import re
    url_pattern = re.compile(r'(https?://[^\s<>&]+)')
    text = url_pattern.sub(r'<a href="\1" target="_blank" rel="noopener">\1</a>', text)
    text = text.replace('\n', '<br>\n')
    return text


def render_links(links):
    """Render links block"""
    if not links:
        return ""
    html = '<div class="post-links">\n'
    for link in links:
        url = escape(link.get('url', ''))
        label = escape(link.get('text', '')) or url
        if url:
            html += f'  <a href="{url}" target="_blank" rel="noopener">{label}</a>\n'
    html += '</div>\n'
    return html


def render_buttons(buttons):
    """Render inline buttons as chips"""
    if not buttons:
        return ""
    html = '<div class="post-buttons">\n'
    for btn in buttons:
        url = escape(btn.get('url', ''))
        label = escape(btn.get('text', 'Ссылка'))
        if url:
            html += f'  <a href="{url}" target="_blank" rel="noopener" class="btn-chip">{label}</a>\n'
    html += '</div>\n'
    return html


def render_forward(forward_from):
    """Render forward/repost info"""
    if not forward_from:
        return ""
    name = escape(forward_from.get('name', 'Unknown'))
    date = forward_from.get('date', '')
    date_str = ""
    if date:
        dt = parse_ts(date)
        date_str = f" · {format_time(dt)}"
    return f'<div class="forward-info">↪️ репост из <strong>{name}</strong>{date_str}</div>\n'


def render_media(post):
    """Render media element"""
    if not post.get('has_media'):
        return ""

    media_path = post.get('media_path')
    if not media_path:
        return '<span class="media-badge">📎 Медиа (не скачано)</span>\n'

    # media_path is relative like "media/-100xxx_123.jpg"
    filename = os.path.basename(media_path)
    local_path = MEDIA_DST / filename
    ext = os.path.splitext(filename)[1].lower()

    if not local_path.exists():
        return '<span class="media-badge">📎 Медиа (не скачано)</span>\n'

    if ext in IMAGE_EXTS:
        return f'<div class="post-media"><img src="media/{escape(filename)}" alt="" loading="lazy"></div>\n'
    elif ext in VIDEO_EXTS:
        return f'<div class="post-media"><video src="media/{escape(filename)}" controls preload="none"></video></div>\n'
    else:
        return f'<div class="post-media"><a href="media/{escape(filename)}" class="file-link">📄 {escape(filename)}</a></div>\n'


def render_views(views):
    """Render view count"""
    if not views:
        return ""
    if isinstance(views, int):
        if views >= 1000:
            return f'<span class="views">👁 {views/1000:.1f}K</span>'
        return f'<span class="views">👁 {views}</span>'
    return ""


PALETTES = [
    ("#6df01e", "#6b5cff"),  # lime -> purple
    ("#ff6a3d", "#ffd84d"),  # orange -> yellow
    ("#41d7ff", "#1A2DC3"),  # cyan -> blue
    ("#ff4fd8", "#7c3aed"),  # pink -> violet
    ("#a3ff6b", "#00c2a8"),  # green -> teal
]


def pick_palette(seed: str):
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) % 10_000
    c1, c2 = PALETTES[h % len(PALETTES)]
    return c1, c2


def make_summary(text: str, has_media: bool = False) -> str:
    """Heuristic summary for collapsed card."""
    t = (text or "").strip()
    if not t:
        return "Медиа" if has_media else "Пост без текста"

    # Prefer first line
    first_line = t.split("\n", 1)[0].strip()
    base = first_line if len(first_line) >= 18 else t

    # Cut at first sentence boundary if it's long
    cut_points = [base.find(x) for x in [". ", "! ", "? "] if base.find(x) != -1]
    if cut_points:
        idx = min(cut_points) + 1
        if 40 <= idx <= 140:
            base = base[:idx]

    if len(base) > 140:
        base = base[:140].rstrip() + "…"
    return base


def make_preview(text: str) -> str:
    t = (text or "").strip().replace("\n", " ")
    t = " ".join(t.split())
    if len(t) > 220:
        t = t[:220].rstrip() + "…"
    return t


def render_post(post):
    """Render a single post card in expandable format (details/summary)."""
    ts = parse_ts(post['ts'])
    time_str = format_time(ts)
    channel_raw = post.get('peer_title', 'Unknown')
    channel = escape(channel_raw)
    text = post.get('text', '') or ""

    c1, c2 = pick_palette(channel_raw)

    summary_title = escape(make_summary(text, bool(post.get('has_media'))))
    preview = escape(make_preview(text))

    # Content blocks
    forward_html = render_forward(post.get('forward_from'))
    media_html = render_media(post)
    links_html = render_links(post.get('links'))
    buttons_html = render_buttons(post.get('buttons'))

    # Text body
    if text.strip():
        body_html = f'<div class="post-text">{render_text(text)}</div>'
    elif post.get('has_media'):
        body_html = '<p class="post-text"><em>[Медиа-пост без текста]</em></p>'
    else:
        body_html = '<p class="post-text"><em>[Пустой пост]</em></p>'

    views_html = render_views(post.get('views'))
    views_part = views_html if views_html else ""

    parts = []
    parts.append(f'<details class="post" style="--c1:{c1}; --c2:{c2};">')
    parts.append('  <summary>')
    parts.append('    <div class="post-summary">')
    parts.append('      <div class="sum-top">')
    parts.append(f'        <div class="source">{channel}</div>')
    parts.append(f'        <div class="meta">{views_part}<span>{time_str}</span></div>')
    parts.append('      </div>')
    parts.append(f'      <div class="title">{summary_title}</div>')
    if preview:
        parts.append(f'      <div class="preview">{preview}</div>')
    parts.append('      <div class="actions">')
    parts.append('        <span class="btn">Read</span>')
    parts.append('        <span class="btn secondary">Collapse</span>')
    parts.append('      </div>')
    parts.append('    </div>')
    parts.append('  </summary>')

    parts.append('  <div class="post-content">')
    if forward_html:
        parts.append(f'    {forward_html}')
    if media_html:
        # In new CSS we use badge class
        parts.append(str(media_html).replace('media-badge', 'badge'))
    parts.append(f'    {body_html}')
    if links_html:
        parts.append(f'    {links_html}')
    if buttons_html:
        parts.append(f'    {buttons_html}')
    parts.append('  </div>')
    parts.append('</details>')

    return "\n".join(parts)


CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
:root{
  --bg: #f6f7fb;
  --text: #0c0f14;
  --muted: rgba(12, 15, 20, 0.55);
  --cardRadius: 22px;
}
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.35;
  padding: 0 16px;
}
.container {
  max-width: 760px;
  margin: 0 auto;
  padding: 22px 0 56px;
}
header{
  margin-bottom: 18px;
}
h1 {
  font-size: 1.55rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}
.subtitle {
  color: var(--muted);
  font-size: 0.95rem;
}

/* Feed cards (Dribbble-ish) */
.post {
  --c1: #6df01e;
  --c2: #6b5cff;
  --c3: #ff6a3d;
  border-radius: var(--cardRadius);
  overflow: hidden;
  margin-bottom: 14px;
  box-shadow: 0 6px 18px rgba(10, 12, 20, 0.06);
}
.post > summary{
  list-style: none;
  cursor: pointer;
}
.post > summary::-webkit-details-marker{ display:none; }

.post-summary{
  padding: 18px 18px 16px;
  background:
    radial-gradient(1200px 500px at 15% 15%, rgba(255,255,255,0.55), rgba(255,255,255,0) 60%),
    linear-gradient(135deg, var(--c1), var(--c2));
  color: rgba(0,0,0,0.88);
  position: relative;
}

.sum-top{
  display:flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.source{
  font-weight: 700;
  font-size: 0.9rem;
  letter-spacing: -0.01em;
  opacity: 0.9;
}
.meta{
  display:flex;
  align-items:center;
  gap:10px;
  font-size: 0.82rem;
  opacity: 0.8;
  font-variant-numeric: tabular-nums;
}

.title{
  font-size: 1.15rem;
  font-weight: 900;
  line-height: 1.15;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}
.preview{
  font-size: 0.92rem;
  line-height: 1.25;
  opacity: 0.82;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.actions{
  margin-top: 14px;
  display:flex;
  gap:10px;
}
.btn{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 10px 14px;
  border-radius: 16px;
  font-weight: 800;
  font-size: 0.9rem;
  border: 0;
  background: rgba(255,255,255,0.6);
  color: rgba(0,0,0,0.88);
}
.btn.secondary{
  background: rgba(255,255,255,0.25);
  display: none;
}
.post[open] .btn.secondary{ display: inline-flex; }
.post[open] .btn:first-child{ opacity: 0.85; }

/* Expanded content */
.post-content{
  background: white;
  padding: 16px 18px 18px;
}
.post-text{
  font-size: 0.98rem;
  line-height: 1.55;
  color: rgba(12, 15, 20, 0.9);
  word-wrap: break-word;
  overflow-wrap: break-word;
}
.post-text a{ color: #1A2DC3; text-decoration: none; }
.post-text a:hover{ text-decoration: underline; }

.forward-info{
  margin: 0 0 10px;
  color: rgba(12, 15, 20, 0.62);
  font-size: 0.85rem;
}

.post-media{ margin: 12px 0 12px; }
.post-media img,
.post-media video{
  width: 100%;
  border-radius: 16px;
  display:block;
}

.badge{
  display:inline-block;
  margin-top: 10px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(12,15,20,0.06);
  color: rgba(12,15,20,0.7);
  font-size: 0.82rem;
  font-weight: 700;
}

.post-links,
.post-buttons{
  margin-top: 12px;
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
}
.post-links a,
.btn-chip{
  display:inline-flex;
  align-items:center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(26,45,195,0.07);
  border: 1px solid rgba(26,45,195,0.18);
  color: #1A2DC3;
  font-size: 0.86rem;
  font-weight: 700;
  text-decoration:none;
}

footer{
  text-align:center;
  color: rgba(12,15,20,0.45);
  font-size: 0.85rem;
  padding-top: 18px;
  margin-top: 22px;
}

@media (max-width: 480px){
  body{ padding: 0 14px; }
  h1{ font-size: 1.35rem; }
  .post-summary{ padding: 16px; }
  .title{ font-size: 1.05rem; }
}
"""


def build():
    # Sync media
    sync_media()
    
    # Read feed
    posts = []
    with open(FEED_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))
    
    # Sort: newest first
    posts.sort(key=lambda p: p.get('ts', ''), reverse=True)
    
    # Determine date from newest post
    if posts:
        newest_ts = parse_ts(posts[0]['ts'])
        date_str = format_date(newest_ts)
    else:
        date_str = "—"
    
    # Generate HTML
    cards = '\n'.join(render_post(p) for p in posts)
    
    JS = """
<script>
// Mobile-friendly accordion: keep only one post expanded
document.addEventListener('toggle', (e) => {
  const el = e.target;
  if (!el || el.tagName !== 'DETAILS') return;
  if (el.open) {
    document.querySelectorAll('details.post[open]').forEach(d => {
      if (d !== el) d.removeAttribute('open');
    });
  }
}, true);
</script>
"""

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<base href="/news/">
<title>AI News Digest — {date_str}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>AI News Digest — {date_str}</h1>
    <p class="subtitle">{len(posts)} постов из Telegram-каналов • тапни карточку чтобы раскрыть</p>
  </header>
{cards}
  <footer>Собрано автоматически • Telegram Daemon • msolo.me</footer>
</div>
{JS}
</body>
</html>
"""
    
    OUTPUT.write_text(html, encoding='utf-8')
    print(f"✅ Generated {OUTPUT} — {len(posts)} posts, date: {date_str}")
    print(f"   Media files: {len(list(MEDIA_DST.iterdir())) if MEDIA_DST.exists() else 0}")


if __name__ == '__main__':
    build()
