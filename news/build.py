#!/usr/bin/env python3
"""
News page generator for msolo.me/news
Reads feed.jsonl from Telethon daemon, generates index.html
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

# Europe/Nicosia: UTC+2 (EET). DST starts last Sunday of March.
# March 25 2026 is before March 29 (last Sunday) => still UTC+2.
TZ_OFFSET = timedelta(hours=2)
TZ_NICOSIA = timezone(TZ_OFFSET)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

COLORS = [
    "--c1:#ff6a3d; --c2:#ffd84d",
    "--c1:#41d7ff; --c2:#1A2DC3",
    "--c1:#a3ff6b; --c2:#00c2a8",
    "--c1:#ff4fd8; --c2:#7c3aed",
    "--c1:#6df01e; --c2:#6b5cff",
]

URL_RE = re.compile(r'(https?://[^\s<>&]+)')

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def parse_ts(ts_str):
    """Parse UTC timestamp string to aware datetime."""
    ts_str = ts_str.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        return datetime.now(timezone.utc)


def to_local(dt):
    """Convert to Nicosia local time."""
    return dt.astimezone(TZ_NICOSIA)


def format_time(dt):
    return to_local(dt).strftime("%H:%M")


def format_date_ru(dt):
    local = to_local(dt)
    return f"{local.day} {MONTHS_RU[local.month]} {local.year}"


def format_date_num(dt):
    local = to_local(dt)
    return local.strftime("%d.%m.%Y %H:%M")


def sync_media():
    """Copy media files from daemon output to news/media/."""
    MEDIA_DST.mkdir(exist_ok=True)
    if not os.path.isdir(MEDIA_SRC):
        return
    for f in os.listdir(MEDIA_SRC):
        src = os.path.join(MEDIA_SRC, f)
        dst = MEDIA_DST / f
        if not dst.exists() or os.path.getmtime(src) > os.path.getmtime(str(dst)):
            shutil.copy2(src, dst)


def linkify(text_escaped):
    """Convert URLs in already-escaped text to <a> tags."""
    return URL_RE.sub(
        r'<a href="\1" target="_blank" rel="noopener">\1</a>',
        text_escaped,
    )


def render_text(text):
    """Escape HTML, linkify URLs, convert newlines to <br>."""
    if not text:
        return ""
    escaped = escape(text)
    linked = linkify(escaped)
    return linked.replace('\n', '<br>\n')


def get_title(text):
    """First line of text, up to 150 chars. If no text, return 'Медиа'."""
    t = (text or "").strip()
    if not t:
        return "Медиа"
    first_line = t.split("\n")[0].strip()
    if len(first_line) > 150:
        return first_line[:147] + "..."
    return first_line


def get_preview(text):
    """Flatten text to single line, truncate to ~200 chars."""
    t = (text or "").strip()
    if not t:
        return ""
    flat = " ".join(t.split())
    if len(flat) > 200:
        return flat[:197] + "..."
    return flat


def render_media(post):
    """Render media element."""
    if not post.get('has_media'):
        return ""

    media_path = post.get('media_path')
    if not media_path:
        return '<span class="badge">Медиа (не скачано)</span>\n'

    filename = os.path.basename(media_path)
    local_path = MEDIA_DST / filename
    ext = os.path.splitext(filename)[1].lower()

    if not local_path.exists():
        return '<span class="badge">Медиа (не скачано)</span>\n'

    if ext in IMAGE_EXTS:
        return f'<div class="post-media"><img src="media/{escape(filename)}" alt="" loading="lazy"></div>\n'
    elif ext in VIDEO_EXTS:
        return f'<div class="post-media"><video src="media/{escape(filename)}" controls preload="metadata"></video></div>\n'
    else:
        return f'<div class="post-media"><a href="media/{escape(filename)}">{escape(filename)}</a></div>\n'


def render_forward(forward_from):
    """Render forward/repost info."""
    if not forward_from:
        return ""
    if isinstance(forward_from, dict):
        name = escape(forward_from.get('name', str(forward_from)))
    else:
        name = escape(str(forward_from))
    return f'<p class="forward-info">Переслано из: {name}</p>\n'


def render_links(links):
    """Render links block."""
    if not links:
        return ""
    parts = []
    for link in links:
        url = escape(link.get('url', ''))
        label = escape(link.get('text', '')) or url
        if url:
            parts.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
    if not parts:
        return ""
    return '<div class="post-links">' + ''.join(parts) + '</div>\n'


def render_buttons(buttons):
    """Render inline buttons as chips."""
    if not buttons:
        return ""
    parts = []
    for btn in buttons:
        url = escape(btn.get('url', ''))
        label = escape(btn.get('text', 'Ссылка'))
        if url:
            parts.append(f'<a href="{url}" target="_blank" rel="noopener" class="btn-chip">{label}</a>')
    if not parts:
        return ""
    return '<div class="post-buttons">' + ''.join(parts) + '</div>\n'


def render_post(post, index):
    """Render a single post card."""
    color_style = COLORS[index % len(COLORS)]
    ts = parse_ts(post['ts'])
    time_str = format_time(ts)
    channel = escape(post.get('peer_title', 'Unknown'))
    text = post.get('text', '') or ""

    title = escape(get_title(text))
    preview = escape(get_preview(text))

    # Content blocks
    media_html = render_media(post)
    forward_html = render_forward(post.get('forward_from'))
    links_html = render_links(post.get('links'))
    buttons_html = render_buttons(post.get('buttons'))

    # Text body
    if text.strip():
        body_html = f'<div class="post-text">{render_text(text)}</div>'
    else:
        body_html = '<p class="post-text"><em>[Медиа-пост без текста]</em></p>'

    # Build preview div
    preview_line = f'\n      <div class="preview">{preview}</div>' if preview else ''

    # Build content area
    content_parts = []
    if media_html:
        content_parts.append(media_html)
    if forward_html:
        content_parts.append(forward_html)
    content_parts.append(f'    {body_html}')
    if links_html:
        content_parts.append(links_html)
    if buttons_html:
        content_parts.append(buttons_html)

    content_inner = '\n'.join(content_parts)

    return f'''<details class="post" style="{color_style}">
  <summary>
    <div class="post-summary">
      <div class="sum-top">
        <div class="source">{channel}</div>
        <div class="meta"><span>{time_str}</span></div>
      </div>
      <div class="title">{title}</div>{preview_line}
      <div class="actions">
        <span class="btn">Read</span>
        <span class="btn secondary">Collapse</span>
      </div>
    </div>
  </summary>
  <div class="post-content">
{content_inner}
  </div>
</details>'''


CSS = """\
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
  /* More “designed” look: gradient + bold decorative elements (no page background change) */
  background:
    radial-gradient(900px 520px at 10% 10%, rgba(255,255,255,0.55), rgba(255,255,255,0) 60%),
    linear-gradient(135deg, var(--c1), var(--c2));
  color: rgba(0,0,0,0.88);
  position: relative;
  isolation: isolate;
}

/* Decorative blobs / circles like in the reference */
.post-summary::before,
.post-summary::after{
  content: "";
  position: absolute;
  inset: -2px;
  pointer-events: none;
  z-index: 0;
  opacity: 0.95;
}

.post-summary::before{
  /* Big “acid” circles */
  background:
    radial-gradient(circle at 82% 30%, rgba(255,255,255,0.25) 0 34%, rgba(255,255,255,0) 35%),
    radial-gradient(circle at 74% 78%, rgba(0,0,0,0.14) 0 22%, rgba(0,0,0,0) 23%),
    radial-gradient(circle at 18% 68%, rgba(255,255,255,0.20) 0 26%, rgba(255,255,255,0) 27%),
    radial-gradient(circle at 48% 118%, rgba(0,0,0,0.10) 0 40%, rgba(0,0,0,0) 41%);
  mix-blend-mode: overlay;
}

.post-summary::after{
  /* Smaller highlight dots */
  background:
    radial-gradient(circle at 92% 18%, rgba(255,255,255,0.30) 0 10%, rgba(255,255,255,0) 11%),
    radial-gradient(circle at 88% 44%, rgba(255,255,255,0.22) 0 12%, rgba(255,255,255,0) 13%),
    radial-gradient(circle at 66% 14%, rgba(0,0,0,0.10) 0 9%, rgba(0,0,0,0) 10%),
    radial-gradient(circle at 38% 28%, rgba(255,255,255,0.18) 0 8%, rgba(255,255,255,0) 9%);
  opacity: 0.9;
}

.post-summary > *{ position: relative; z-index: 1; }

.sum-top{
  display:flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.source{
  font-weight: 900;
  font-size: 0.86rem;
  letter-spacing: -0.01em;
  opacity: 0.95;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.38);
  border: 1px solid rgba(255,255,255,0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.meta{
  display:flex;
  align-items:center;
  gap:10px;
  font-size: 0.82rem;
  opacity: 0.92;
  font-variant-numeric: tabular-nums;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.28);
  border: 1px solid rgba(255,255,255,0.30);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
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
  font-weight: 900;
  font-size: 0.9rem;
  border: 0;
  background: rgba(255,255,255,0.68);
  box-shadow: 0 8px 18px rgba(0,0,0,0.10);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  color: rgba(0,0,0,0.9);
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

JS = """\
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
"""


def build():
    # Sync media files
    sync_media()

    # Read feed
    posts = []
    with open(FEED_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))

    # Sort: newest first
    posts.sort(key=lambda p: p.get('ts', ''), reverse=True)

    n = len(posts)

    # Determine dates
    if posts:
        newest_ts = parse_ts(posts[0]['ts'])
        date_ru = format_date_ru(newest_ts)
        updated_str = format_date_num(newest_ts)
    else:
        date_ru = "—"
        updated_str = "—"

    # Render cards
    cards = '\n'.join(render_post(p, i) for i, p in enumerate(posts))

    html_out = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<base href="/news/">
<title>AI News Digest &mdash; {date_ru}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>AI News Digest &mdash; {date_ru}</h1>
    <p class="subtitle">{n} постов из Telegram-каналов &bull; обновлено {updated_str} &bull; тапни карточку чтобы раскрыть</p>
  </header>
{cards}
  <footer>Собрано автоматически &bull; Telegram Daemon &bull; msolo.me</footer>
</div>

<script>
{JS}
</script>

</body>
</html>
'''

    OUTPUT.write_text(html_out, encoding='utf-8')
    media_count = len(list(MEDIA_DST.iterdir())) if MEDIA_DST.exists() else 0
    print(f"Generated {OUTPUT} — {n} posts, date: {date_ru}")
    print(f"Media files: {media_count}")


if __name__ == '__main__':
    build()
