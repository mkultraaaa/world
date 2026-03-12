// Vercel Serverless Function: proxy Google Sheets CSV export
// GET /api/sheets?url=<encoded-google-sheets-url>
// Returns JSON: { csv: "..." } with CORS headers

function sendJson(res, statusCode, obj) {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(obj));
}

module.exports = async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.statusCode = 200;
    return res.end();
  }

  // Vercel provides req.query; fall back to parsing URL
  var url = (req.query && req.query.url) || null;
  if (!url) {
    try {
      var u = new URL(req.url, 'http://localhost');
      url = u.searchParams.get('url');
    } catch (e) {}
  }

  if (!url) {
    return sendJson(res, 400, { error: 'Missing url parameter' });
  }

  // Only allow Google Sheets URLs
  if (typeof url !== 'string' || !url.startsWith('https://docs.google.com/spreadsheets/')) {
    return sendJson(res, 403, { error: 'Only Google Sheets URLs allowed' });
  }

  try {
    var response = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 MU-Dashboard-Proxy/1.0' },
      redirect: 'follow'
    });

    var csv = await response.text();

    if (!response.ok) {
      return sendJson(res, response.status, { error: 'Google Sheets returned ' + response.status, csv: csv });
    }

    // Cache for 10 minutes
    res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate=300');

    return sendJson(res, 200, { csv: csv });
  } catch (e) {
    return sendJson(res, 500, { error: e && e.message ? e.message : 'Fetch failed' });
  }
};
