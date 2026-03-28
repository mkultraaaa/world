#!/usr/bin/env python3
"""
News page generator for msolo.me/news
Reads feed.jsonl from Telethon daemon, generates index.html
Clean TLDR/Axios-style: scannable, dense, one accent color.
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
    local = to_local(dt)
    return f"{local.day} {MONTHS_RU[local.month]}"


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
    """Convert bare URLs to <a> tags, skipping URLs already inside href="..."."""
    def _replace(m):
        url = m.group(1)
        # Check if this URL is already inside an href attribute
        start = m.start()
        before = text_escaped[max(0, start - 6):start]
        if 'href="' in before or "href='" in before:
            return m.group(0)
        # Check if already wrapped in <a> tag (url appears as anchor text)
        after_end = text_escaped[m.end():m.end() + 4]
        if after_end.startswith('</a>'):
            return m.group(0)
        return f'<a href="{url}" target="_blank" rel="noopener">{url}</a>'
    return URL_RE.sub(_replace, text_escaped)


def render_text(text, links=None):
    """Escape HTML, embed inline hyperlinks from entities, linkify remaining URLs."""
    if not text:
        return ""
    escaped = escape(text)
    # Embed known links: find escaped anchor text and wrap with <a>
    # Process longer anchors first to avoid partial matches
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
                # Replace only first occurrence
                escaped = escaped.replace(escaped_anchor, a_tag, 1)
                used.add(anchor)
    # Linkify any remaining bare URLs (skip those already inside href="...")
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


def get_summary(text):
    """Get first 2-3 lines after title as summary."""
    t = (text or "").strip()
    if not t:
        return ""
    lines = t.split("\n")
    if len(lines) <= 1:
        return ""
    rest = " ".join(l.strip() for l in lines[1:] if l.strip())
    if len(rest) > 280:
        return rest[:277] + "..."
    return rest


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
        return f'<img class="thumb" src="media/{escape(filename)}" alt="" loading="lazy">\n'
    elif ext in VIDEO_EXTS:
        return f'<video class="thumb" src="media/{escape(filename)}" controls preload="metadata"></video>\n'
    return ""


def render_full_media(post):
    """Full-width media for expanded view."""
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
        return f'<img class="full-media" src="media/{escape(filename)}" alt="" loading="lazy">\n'
    elif ext in VIDEO_EXTS:
        return f'<video class="full-media" src="media/{escape(filename)}" controls preload="metadata"></video>\n'
    return ""


def render_forward(forward_from):
    if not forward_from:
        return ""
    if isinstance(forward_from, dict):
        raw_name = forward_from.get('name') or str(forward_from)
        name = escape(str(raw_name))
    else:
        name = escape(str(forward_from or ''))
    return f' <span class="via">via {name}</span>'


def render_links(links, buttons):
    all_links = []
    for link in (links or []):
        url = escape(link.get('url', ''))
        label = escape(link.get('text', '')) or 'Link'
        if url:
            all_links.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
    for btn in (buttons or []):
        url = escape(btn.get('url', ''))
        label = escape(btn.get('text', 'Link'))
        if url:
            all_links.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
    if not all_links:
        return ""
    return '<span class="item-links">' + ' '.join(all_links) + '</span>'


def render_post(post):
    ts = parse_ts(post['ts'])
    time_str = format_time(ts)
    channel = escape(post.get('peer_title', ''))
    text = post.get('text', '') or ""
    title = escape(get_title(text))
    summary = escape(get_summary(text))
    media_html = render_media(post)
    fwd_html = render_forward(post.get('forward_from'))

    post_links = post.get('links') or []
    post_buttons = post.get('buttons') or []
    all_entity_links = post_links + post_buttons

    # Full text (skip first line = title) with inline links
    lines = text.strip().split('\n')
    body_text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
    body_html = render_text(body_text, all_entity_links) if body_text else ""

    # Full media for expanded view
    full_media = render_full_media(post)

    summary_block = f'\n    <p class="summary">{summary}</p>' if summary else ''

    # Links that weren't embedded inline (no anchor text)
    leftover_links = [l for l in all_entity_links if not l.get('text', '').strip() or l.get('text', '').strip() not in text]
    if leftover_links:
        parts = []
        for l in leftover_links:
            url = escape(l.get('url', ''))
            label = escape(l.get('text', '')) or url
            if url and url.startswith('http'):
                parts.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
        links_block = '\n    <span class="item-links">' + ' '.join(parts) + '</span>' if parts else ''
    else:
        links_block = ''

    # Full body expandable (show if there's text OR full-size media)
    has_expand = body_html or full_media
    if has_expand:
        expand_block = f'''
    <details class="expand">
      <summary>Read more</summary>
      <div class="full-text">{full_media}{body_html}</div>
    </details>'''
    else:
        expand_block = ''

    return f'''<div class="item">
  <div class="item-main">
    <h3>{title}</h3>{summary_block}{expand_block}
    <div class="item-meta"><span class="src">{channel}</span> <span class="time">{time_str}</span>{fwd_html}{links_block}</div>
  </div>
  {media_html}</div>'''


CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #ffffff;
  --surface: #f8f9fa;
  --ink: #111;
  --secondary: #555;
  --muted: #999;
  --border: #e8e8e8;
  --accent: #0066FF;
  --font: 'Inter', -apple-system, system-ui, sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111;
    --surface: #1a1a1a;
    --ink: #eee;
    --secondary: #aaa;
    --muted: #666;
    --border: #2a2a2a;
  }
}

body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.wrap {
  max-width: 700px;
  margin: 0 auto;
  padding: 0 20px;
}

/* ---- Header ---- */
header {
  padding: 48px 0 24px;
  border-bottom: 3px solid var(--ink);
  margin-bottom: 0;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.mark {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}

h1 {
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  text-transform: uppercase;
}

.edition {
  font-size: 0.85rem;
  color: var(--muted);
  font-weight: 400;
}

/* ---- Date section ---- */
.date-bar {
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ---- Items ---- */
.item {
  display: flex;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--border);
  align-items: flex-start;
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item h3 {
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: -0.01em;
  margin-bottom: 4px;
}

.summary {
  font-size: 0.88rem;
  color: var(--secondary);
  line-height: 1.5;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 0.78rem;
  color: var(--muted);
}

.src {
  font-weight: 600;
  color: var(--secondary);
}

.via {
  font-style: italic;
}

.item-links a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.78rem;
}

.item-links a:hover {
  text-decoration: underline;
}

/* Expandable full text */
.expand {
  margin: 6px 0 4px;
}

.expand > summary {
  list-style: none;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--accent);
  user-select: none;
}

.expand > summary::-webkit-details-marker { display: none; }

.expand > summary::before {
  content: '+ ';
}

.expand[open] > summary::before {
  content: '- ';
}

.expand[open] .summary { display: none; }

.full-text {
  font-size: 0.9rem;
  line-height: 1.65;
  color: var(--secondary);
  padding: 8px 0 4px;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.full-text a {
  color: var(--accent);
  text-decoration: none;
}

.full-text a:hover {
  text-decoration: underline;
}

.full-media {
  width: 100%;
  border-radius: 8px;
  margin-bottom: 10px;
  display: block;
}

/* Thumbnail */
.thumb {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--surface);
}

video.thumb {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  object-fit: cover;
}

/* ---- Footer ---- */
footer {
  padding: 28px 0 48px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--muted);
}

/* ---- Counter badge ---- */
.counter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--surface);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--secondary);
}

/* ---- Mobile ---- */
@media (max-width: 480px) {
  header { padding: 32px 0 20px; }
  h1 { font-size: 1rem; }
  .item { gap: 12px; padding: 14px 0; }
  .item h3 { font-size: 0.9rem; }
  .thumb { width: 72px; height: 72px; border-radius: 8px; }
}
"""

JS = r"""
// Nothing fancy — let it be fast and clean
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
        feed_html.append(f'<div class="date-bar">{group["label"]}</div>')
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
    <div class="header-top">
      <div class="mark"></div>
      <h1>AI News</h1>
      <span class="counter">{n} posts</span>
    </div>
    <p class="edition">{date_ru} &middot; 27+ Telegram channels</p>
  </header>
{cards}
  <footer>Collected automatically &middot; msolo.me</footer>
</div>
<script>{JS}</script>
</body>
</html>
'''

    OUTPUT.write_text(html_out, encoding='utf-8')
    media_count = len(list(MEDIA_DST.iterdir())) if MEDIA_DST.exists() else 0
    print(f"Generated {OUTPUT} — {n} posts, date: {date_ru}")
    print(f"Media files: {media_count}")


if __name__ == '__main__':
    build()
