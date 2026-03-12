// Vercel Serverless Function: proxy Google Sheets CSV export
// GET /api/sheets?url=<encoded-google-sheets-url>
// Returns JSON: { csv: "..." } with CORS headers

module.exports = async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  var url = req.query.url;
  if (!url) {
    return res.status(400).json({ error: 'Missing url parameter' });
  }

  // Only allow Google Sheets URLs
  if (!url.startsWith('https://docs.google.com/spreadsheets/')) {
    return res.status(403).json({ error: 'Only Google Sheets URLs allowed' });
  }

  try {
    var response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 MU-Dashboard-Proxy/1.0'
      },
      redirect: 'follow'
    });

    if (!response.ok) {
      return res.status(response.status).json({ error: 'Google Sheets returned ' + response.status });
    }

    var csv = await response.text();
    
    // Cache for 10 minutes
    res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate=300');
    
    return res.status(200).json({ csv: csv });
  } catch (e) {
    return res.status(500).json({ error: e.message || 'Fetch failed' });
  }
};
