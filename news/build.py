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


def render_post(post):
    """Render a single post card"""
    ts = parse_ts(post['ts'])
    time_str = format_time(ts)
    channel = escape(post.get('peer_title', 'Unknown'))
    text = post.get('text', '')
    
    parts = []
    parts.append('<article class="card">')
    parts.append('  <div class="card-header">')
    parts.append(f'    <span class="channel">{channel}</span>')
    
    # Right side: views + time
    right_parts = []
    views_html = render_views(post.get('views'))
    if views_html:
        right_parts.append(views_html)
    right_parts.append(f'<span class="time">{time_str}</span>')
    parts.append(f'    <div class="card-meta">{" ".join(right_parts)}</div>')
    parts.append('  </div>')
    
    # Forward info
    forward_html = render_forward(post.get('forward_from'))
    if forward_html:
        parts.append(f'  {forward_html}')
    
    # Media
    media_html = render_media(post)
    if media_html:
        parts.append(f'  {media_html}')
    
    # Text
    if text.strip():
        parts.append(f'  <div class="post-text">{render_text(text)}</div>')
    elif post.get('has_media'):
        parts.append('  <p class="empty-post">[Медиа-пост без текста]</p>')
    
    # Links
    links_html = render_links(post.get('links'))
    if links_html:
        parts.append(f'  {links_html}')
    
    # Buttons
    buttons_html = render_buttons(post.get('buttons'))
    if buttons_html:
        parts.append(f'  {buttons_html}')
    
    parts.append('</article>')
    return '\n'.join(parts)


CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #0d1117;
  color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.6;
  padding: 0 16px;
}
.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 0 60px;
}
h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin-bottom: 8px;
  color: #f0f6fc;
}
.subtitle {
  color: #8b949e;
  font-size: 0.95rem;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid #21262d;
}
.card {
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 16px;
  transition: border-color 0.15s;
}
.card:hover {
  border-color: #30363d;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.channel {
  font-weight: 600;
  font-size: 0.9rem;
  color: #58a6ff;
}
.time {
  font-size: 0.8rem;
  color: #8b949e;
  font-variant-numeric: tabular-nums;
}
.views {
  font-size: 0.75rem;
  color: #8b949e;
}
.media-badge {
  display: inline-block;
  font-size: 0.75rem;
  color: #d2a8ff;
  background: rgba(210,168,255,0.1);
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 10px;
}
.post-text {
  font-size: 0.92rem;
  color: #c9d1d9;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
.post-text a {
  color: #58a6ff;
  text-decoration: none;
  word-break: break-all;
}
.post-text a:hover {
  text-decoration: underline;
}
.empty-post {
  font-style: italic;
  color: #8b949e;
  font-size: 0.9rem;
}
.forward-info {
  font-size: 0.82rem;
  color: #8b949e;
  margin-bottom: 10px;
  padding: 6px 10px;
  background: rgba(88,166,255,0.06);
  border-left: 3px solid #58a6ff;
  border-radius: 4px;
}
.post-media {
  margin-bottom: 12px;
}
.post-media img {
  max-width: 100%;
  border-radius: 8px;
  display: block;
}
.post-media video {
  max-width: 100%;
  border-radius: 8px;
  display: block;
}
.file-link {
  color: #58a6ff;
  text-decoration: none;
  font-size: 0.9rem;
}
.post-links {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.post-links a {
  color: #58a6ff;
  font-size: 0.85rem;
  text-decoration: none;
}
.post-links a:hover {
  text-decoration: underline;
}
.post-buttons {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.btn-chip {
  display: inline-block;
  padding: 6px 14px;
  background: rgba(88,166,255,0.1);
  color: #58a6ff;
  border: 1px solid rgba(88,166,255,0.3);
  border-radius: 20px;
  font-size: 0.82rem;
  text-decoration: none;
  transition: background 0.15s;
}
.btn-chip:hover {
  background: rgba(88,166,255,0.2);
}
footer {
  text-align: center;
  color: #484f58;
  font-size: 0.8rem;
  padding: 32px 0 24px;
  border-top: 1px solid #21262d;
}
@media (max-width: 480px) {
  h1 { font-size: 1.35rem; }
  .card { padding: 16px; }
  .container { padding: 24px 0 40px; }
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
  <h1>AI News Digest — {date_str}</h1>
  <p class="subtitle">{len(posts)} постов из Telegram-каналов</p>
{cards}
  <footer>Собрано автоматически &bull; Telegram Daemon &bull; msolo.me</footer>
</div>
</body>
</html>
"""
    
    OUTPUT.write_text(html, encoding='utf-8')
    print(f"✅ Generated {OUTPUT} — {len(posts)} posts, date: {date_str}")
    print(f"   Media files: {len(list(MEDIA_DST.iterdir())) if MEDIA_DST.exists() else 0}")


if __name__ == '__main__':
    build()
