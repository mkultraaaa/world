// Vercel Serverless Function: приём заявок с лендингов msolo → Telegram Максу
// POST /api/lead  { name?, contact, message?, source?, company? (honeypot) }
// env: TELEGRAM_BOT_TOKEN, MAX_CHAT_ID

function json(res, code, obj) {
  res.statusCode = code;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(obj));
}

module.exports = async function handler(req, res) {
  if (req.method === 'OPTIONS') { res.statusCode = 200; return res.end(); }
  if (req.method !== 'POST') return json(res, 405, { error: 'method' });

  let b = req.body;
  if (!b || typeof b !== 'object') {
    try {
      const raw = await new Promise((rs, rj) => {
        let d = ''; req.on('data', c => d += c); req.on('end', () => rs(d)); req.on('error', rj);
      });
      b = raw ? JSON.parse(raw) : {};
    } catch (e) { b = {}; }
  }

  const clip = (s, n) => String(s == null ? '' : s).slice(0, n).trim();
  const name = clip(b.name, 120);
  const contact = clip(b.contact, 200);
  const message = clip(b.message, 2000);
  const source = clip(b.source, 40);

  if (b.company) return json(res, 200, { ok: true });      // honeypot: тихо игнорим ботов
  if (!contact) return json(res, 400, { error: 'contact required' });

  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chat = process.env.MAX_CHAT_ID;
  if (!token || !chat) return json(res, 500, { error: 'not configured' });

  const when = new Date().toLocaleString('ru-RU', { timeZone: 'Europe/Nicosia' });
  const text = '🔔 Заявка с сайта' + (source ? ' (' + source + ')' : '') + '\n\n'
    + (name ? '👤 ' + name + '\n' : '')
    + '📱 Контакт: ' + contact + '\n'
    + (message ? '💬 ' + message + '\n' : '')
    + '\n🕐 ' + when;

  try {
    const r = await fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chat, text: text, disable_web_page_preview: true })
    });
    if (!r.ok) return json(res, 502, { error: 'delivery' });
  } catch (e) {
    return json(res, 502, { error: 'delivery' });
  }
  return json(res, 200, { ok: true });
};
