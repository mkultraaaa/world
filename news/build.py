#!/usr/bin/env python3
"""
News page generator for msolo.me/news
Reads feed.jsonl from Telethon daemon, generates index.html
Vibrant card-based design inspired by Purnweb streaming app redesign.
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

# Card color palettes: (bg, text, accent-btn-bg, accent-btn-text)
CARD_PALETTES = [
    ("#FF6B35", "#1a1a1a", "#1a1a1a", "#ffffff"),   # warm orange
    ("#FFD23F", "#1a1a1a", "#1a1a1a", "#FFD23F"),   # bold yellow
    ("#7B2D8E", "#ffffff", "#ffffff", "#7B2D8E"),    # deep purple
    ("#23C16B", "#1a1a1a", "#1a1a1a", "#ffffff"),    # vivid green
    ("#FF4F8B", "#1a1a1a", "#1a1a1a", "#ffffff"),    # hot pink
    ("#2D9CDB", "#ffffff", "#ffffff", "#2D9CDB"),    # sky blue
    ("#1a1a1a", "#ffffff", "#FF6B35", "#1a1a1a"),    # dark card
    ("#F25C54", "#ffffff", "#ffffff", "#F25C54"),     # coral red
]


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
    local = to_local(dt)
    return f"{local.day} {MONTHS_RU_SHORT[local.month]}"


def format_date_key(dt):
    return to_local(dt).strftime("%Y-%m-%d")


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
        return "Media"
    first_line = t.split("\n")[0].strip()
    if len(first_line) > 120:
        return first_line[:117] + "..."
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
    return f'<span class="repost">via {name}</span>'


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
    return '<div class="card-links">' + ''.join(parts) + '</div>\n'


def render_buttons(buttons):
    if not buttons:
        return ""
    parts = []
    for btn in buttons:
        url = escape(btn.get('url', ''))
        label = escape(btn.get('text', 'Link'))
        if url:
            parts.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
    if not parts:
        return ""
    return '<div class="card-links">' + ''.join(parts) + '</div>\n'


def render_post(post, index):
    ts = parse_ts(post['ts'])
    time_str = format_time(ts)
    channel = escape(post.get('peer_title', ''))
    text = post.get('text', '') or ""
    title = escape(get_title(text))
    palette = CARD_PALETTES[index % len(CARD_PALETTES)]
    bg, fg, btn_bg, btn_fg = palette

    media_html = render_media(post)
    forward_html = render_forward(post.get('forward_from'))
    links_html = render_links(post.get('links'))
    buttons_html = render_buttons(post.get('buttons'))

    # Body text (skip first line = title)
    lines = text.strip().split('\n')
    body_text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
    body_html = f'<div class="card-body">{render_text(body_text)}</div>' if body_text else ""

    fwd = f' {forward_html}' if forward_html else ''

    return f'''<article class="card" style="--card-bg:{bg};--card-fg:{fg};--btn-bg:{btn_bg};--btn-fg:{btn_fg}">
  <div class="card-top">
    <span class="card-channel">{channel}</span>
    <time>{time_str}</time>
  </div>
  <h3>{title}</h3>
  {media_html}{body_html}
  <div class="card-footer">
    {links_html}{buttons_html}<span class="card-meta">{fwd}</span>
  </div>
</article>'''


CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&display=swap');

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #F4F0EB;
  --ink: #1a1a1a;
  --mid: #888;
  --radius: 24px;
  --head: 'Space Grotesk', sans-serif;
  --body: 'DM Sans', sans-serif;
}

body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--body);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 40px 16px 80px;
}

/* ---- Header ---- */
header {
  text-align: center;
  margin-bottom: 36px;
}

.logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: var(--ink);
  color: #fff;
  font-family: var(--head);
  font-weight: 700;
  font-size: 1.4rem;
  margin-bottom: 16px;
}

h1 {
  font-family: var(--head);
  font-size: clamp(2.2rem, 6vw, 3.2rem);
  font-weight: 700;
  letter-spacing: -0.04em;
  line-height: 1.05;
  margin-bottom: 10px;
}

.tagline {
  font-size: 0.95rem;
  color: var(--mid);
  font-weight: 400;
}

/* ---- Date group ---- */
.date-group {
  font-family: var(--head);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--mid);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 32px 0 14px;
  padding-left: 4px;
}

/* ---- Cards ---- */
.card {
  background: var(--card-bg);
  color: var(--card-fg);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.12);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  font-size: 0.82rem;
  opacity: 0.7;
}

.card-channel {
  font-weight: 700;
  font-family: var(--head);
  letter-spacing: -0.01em;
  opacity: 1;
}

.card h3 {
  font-family: var(--head);
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
  margin-bottom: 12px;
}

.card-body {
  font-size: 0.92rem;
  line-height: 1.6;
  opacity: 0.85;
  max-height: 200px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  transition: max-height 0.35s ease;
}

.card-body.expanded {
  max-height: none;
  opacity: 1;
}

.card-body:not(.expanded)::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 60px;
  background: linear-gradient(transparent, var(--card-bg));
  pointer-events: none;
}

.card-body a {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* Media inside cards */
.media {
  margin: 14px -24px;
  overflow: hidden;
}

.media img, .media video {
  width: 100%;
  display: block;
}

.file-link {
  display: inline-block;
  margin: 0 24px;
  padding: 8px 16px;
  background: rgba(255,255,255,0.15);
  border-radius: 12px;
  font-size: 0.85rem;
  text-decoration: none;
  color: inherit;
}

/* Footer of card */
.card-footer {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.card-meta {
  font-size: 0.8rem;
  opacity: 0.6;
  margin-left: auto;
}

.repost {
  font-style: italic;
}

/* Links as pill buttons */
.card-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.card-links a {
  display: inline-block;
  padding: 8px 18px;
  border-radius: 999px;
  background: var(--btn-bg);
  color: var(--btn-fg);
  font-family: var(--head);
  font-size: 0.82rem;
  font-weight: 600;
  text-decoration: none;
  transition: opacity 0.2s;
}

.card-links a:hover {
  opacity: 0.8;
}

/* ---- Footer ---- */
footer {
  text-align: center;
  padding-top: 32px;
  font-size: 0.82rem;
  color: var(--mid);
}

/* ---- Animations ---- */
.card {
  animation: popIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes popIn {
  from { opacity: 0; transform: scale(0.95) translateY(16px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* ---- Mobile ---- */
@media (max-width: 480px) {
  .wrap { padding: 28px 12px 60px; }
  h1 { font-size: 2rem; }
  .card { padding: 20px; border-radius: 20px; }
  .card h3 { font-size: 1.15rem; }
  .media { margin: 12px -20px; }
}
"""

JS = r"""
// Expand/collapse card bodies
document.addEventListener('click', (e) => {
  const body = e.target.closest('.card-body');
  if (body) body.classList.toggle('expanded');
});

// Stagger card animations
document.querySelectorAll('.card').forEach((el, i) => {
  el.style.animationDelay = Math.min(i * 0.04, 0.8) + 's';
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
    card_idx = 0
    for key in sorted(grouped.keys(), reverse=True):
        group = grouped[key]
        feed_html.append(f'<div class="date-group">{group["label"]}</div>')
        for p in group['posts']:
            feed_html.append(render_post(p, card_idx))
            card_idx += 1

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
    <div class="logo">N</div>
    <h1>AI News</h1>
    <p class="tagline">{n} posts from 27+ Telegram channels &middot; {date_ru}</p>
  </header>
{cards}
  <footer>Collected automatically &middot; msolo.me</footer>
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
