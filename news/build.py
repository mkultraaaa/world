#!/usr/bin/env python3
"""
News page generator for msolo.me/news
Reads feed.jsonl from Telethon daemon, generates index.html
Editorial design — clean, typographic, no AI slop.
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

# Europe/Nicosia: UTC+2 (EET)
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

MONTHS_RU_SHORT = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр",
    5: "май", 6: "июн", 7: "июл", 8: "авг",
    9: "сен", 10: "окт", 11: "ноя", 12: "дек",
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


def format_date_group(dt):
    """Date string for grouping: '28 мар'."""
    local = to_local(dt)
    return f"{local.day} {MONTHS_RU_SHORT[local.month]}"


def format_date_key(dt):
    """Date key for grouping: 'YYYY-MM-DD'."""
    return to_local(dt).strftime("%Y-%m-%d")


def format_date_num(dt):
    return to_local(dt).strftime("%d.%m.%Y %H:%M")


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
    return URL_RE.sub(
        r'<a href="\1" target="_blank" rel="noopener">\1</a>',
        text_escaped,
    )


def render_text(text):
    if not text:
        return ""
    escaped = escape(text)
    linked = linkify(escaped)
    return linked.replace('\n', '<br>\n')


def get_title(text):
    t = (text or "").strip()
    if not t:
        return "Медиа"
    first_line = t.split("\n")[0].strip()
    if len(first_line) > 150:
        return first_line[:147] + "…"
    return first_line


def render_media(post):
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
        return f'<div class="media"><img src="media/{escape(filename)}" alt="" loading="lazy"></div>\n'
    elif ext in VIDEO_EXTS:
        return f'<div class="media"><video src="media/{escape(filename)}" controls preload="metadata"></video></div>\n'
    else:
        return f'<div class="media"><a href="media/{escape(filename)}" class="file-link">{escape(filename)}</a></div>\n'


def render_forward(forward_from):
    if not forward_from:
        return ""
    if isinstance(forward_from, dict):
        raw_name = forward_from.get('name') or str(forward_from)
        name = escape(str(raw_name))
    else:
        name = escape(str(forward_from or ''))
    return f'<span class="repost">via {name}</span>\n'


def render_links(links):
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
    return '<div class="links">' + ' '.join(parts) + '</div>\n'


def render_buttons(buttons):
    if not buttons:
        return ""
    parts = []
    for btn in buttons:
        url = escape(btn.get('url', ''))
        label = escape(btn.get('text', 'Ссылка'))
        if url:
            parts.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
    if not parts:
        return ""
    return '<div class="links">' + ' '.join(parts) + '</div>\n'


def render_post(post):
    ts = parse_ts(post['ts'])
    time_str = format_time(ts)
    channel = escape(post.get('peer_title', ''))
    text = post.get('text', '') or ""
    title = escape(get_title(text))

    media_html = render_media(post)
    forward_html = render_forward(post.get('forward_from'))
    links_html = render_links(post.get('links'))
    buttons_html = render_buttons(post.get('buttons'))

    # Body text (skip first line which is the title)
    lines = text.strip().split('\n')
    body_text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
    body_html = f'<div class="body">{render_text(body_text)}</div>' if body_text else ""

    meta_parts = [f'<span class="channel">{channel}</span>', f'<time>{time_str}</time>']
    if forward_html:
        meta_parts.append(forward_html)
    meta = ' '.join(meta_parts)

    return f'''<article>
  {media_html}<h3>{title}</h3>
  <div class="meta">{meta}</div>
  {body_html}
  {links_html}{buttons_html}</article>'''


CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=Geist:wght@400;500;600&display=swap');

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --ink: #1a1a1a;
  --paper: #faf9f7;
  --mid: #6b6560;
  --rule: #d4d0cb;
  --accent: #c43d2e;
  --serif: 'Newsreader', 'Georgia', serif;
  --sans: 'Geist', 'Helvetica Neue', sans-serif;
}

body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.wrap {
  max-width: 680px;
  margin: 0 auto;
  padding: 48px 20px 80px;
}

/* Header — editorial masthead */
header {
  text-align: center;
  padding-bottom: 32px;
  margin-bottom: 8px;
  border-bottom: 2px solid var(--ink);
}

header::before {
  content: '';
  display: block;
  width: 40px;
  height: 3px;
  background: var(--accent);
  margin: 0 auto 20px;
}

h1 {
  font-family: var(--serif);
  font-size: clamp(2rem, 5vw, 2.8rem);
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin-bottom: 8px;
}

.tagline {
  font-size: 0.9rem;
  color: var(--mid);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 500;
}

/* Date dividers */
.date-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 36px 0 20px;
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--mid);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.date-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--rule);
}

/* Articles */
article {
  padding: 24px 0;
  border-bottom: 1px solid var(--rule);
  animation: fadeUp 0.4s ease both;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

article h3 {
  font-family: var(--serif);
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: -0.01em;
  margin-bottom: 6px;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 12px;
  font-size: 0.82rem;
  color: var(--mid);
  margin-bottom: 12px;
}

.channel {
  font-weight: 600;
  color: var(--ink);
}

.repost {
  font-style: italic;
}

time {
  font-variant-numeric: tabular-nums;
}

.body {
  font-size: 0.95rem;
  line-height: 1.65;
  color: #333;
  max-height: 320px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  transition: max-height 0.35s ease;
}

.body.expanded {
  max-height: none;
}

.body:not(.expanded)::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  background: linear-gradient(transparent, var(--paper));
  pointer-events: none;
}

.body a {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}

.body a:hover {
  border-bottom-color: var(--accent);
}

/* Media */
.media {
  margin: 14px 0;
  border-radius: 6px;
  overflow: hidden;
}

.media img, .media video {
  width: 100%;
  display: block;
}

.file-link {
  display: inline-block;
  padding: 8px 14px;
  background: rgba(0,0,0,0.04);
  border-radius: 6px;
  font-size: 0.85rem;
  color: var(--mid);
  text-decoration: none;
}

/* Links / buttons */
.links {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.links a {
  display: inline-block;
  padding: 5px 12px;
  border: 1px solid var(--rule);
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--ink);
  text-decoration: none;
  transition: border-color 0.2s, color 0.2s;
}

.links a:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* Footer */
footer {
  text-align: center;
  padding-top: 32px;
  margin-top: 16px;
  font-size: 0.82rem;
  color: var(--mid);
  border-top: 1px solid var(--rule);
}

/* Mobile */
@media (max-width: 480px) {
  .wrap { padding: 32px 16px 60px; }
  h1 { font-size: 1.75rem; }
  article h3 { font-size: 1.1rem; }
  .date-divider { margin: 28px 0 16px; }
}
"""

JS = """\
// Expand/collapse long post bodies
document.addEventListener('click', (e) => {
  const body = e.target.closest('.body');
  if (body) body.classList.toggle('expanded');
});

// Stagger fade-in
document.querySelectorAll('article').forEach((el, i) => {
  el.style.animationDelay = Math.min(i * 0.03, 0.6) + 's';
});
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
        label = format_date_group(ts)
        if key not in grouped:
            grouped[key] = {'label': label, 'posts': []}
        grouped[key]['posts'].append(p)

    # Render
    feed_html = []
    for key in sorted(grouped.keys(), reverse=True):
        group = grouped[key]
        feed_html.append(f'<div class="date-divider">{group["label"]}</div>')
        for p in group['posts']:
            feed_html.append(render_post(p))

    cards = '\n'.join(feed_html)

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
<div class="wrap">
  <header>
    <h1>AI News</h1>
    <p class="tagline">{n} posts &middot; Telegram channels &middot; {date_ru}</p>
  </header>
{cards}
  <footer>Collected automatically from 27+ AI/ML Telegram channels &middot; msolo.me</footer>
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
