// Vercel Serverless Function (plain Node): proxy Google Sheets CSV export
// GET /api/sheets?url=<encoded-google-sheets-url>
// Returns: JSON { csv: "..." } with CORS headers

module.exports = async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.statusCode = 200;
    return res.end();
  }

  const url = (req.query && req.query.url) || null;
  if (!url) {
    res.statusCode = 400;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ error: 'Missing url parameter' }));
  }

  if (!String(url).startsWith('https://docs.google.com/spreadsheets/')) {
    res.statusCode = 403;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ error: 'Only Google Sheets URLs allowed' }));
  }

  try {
    const response = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 MU-Dashboard-Proxy/1.0' },
      redirect: 'follow',
    });

    if (!response.ok) {
      res.statusCode = response.status;
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      return res.end(JSON.stringify({ error: 'Google Sheets returned ' + response.status }));
    }

    const csv = await response.text();

    // Cache at edge (Vercel)
    res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate=300');
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ csv }));
  } catch (e) {
    res.statusCode = 500;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ error: e && e.message ? e.message : 'Fetch failed' }));
  }
};
