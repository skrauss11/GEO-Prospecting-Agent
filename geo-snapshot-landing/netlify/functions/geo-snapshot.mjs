// geo-snapshot Netlify Function (Node.js)
// Receives: POST { name, email, url }
// Action:   Analyzes URL across 8 GEO dimensions and emails HTML report.

// No external email dependency — uses Resend HTTP API via native fetch (Node 18+)

const UA = 'Mozilla/5.0 (compatible; GEO-Snapshot/1.0; +https://madtechgrowth.com/bot)';
const FETCH_TIMEOUT_MS = 15000;
const SIDE_TIMEOUT_MS = 8000;

async function fetchWithTimeout(url, ms) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(url, { headers: { 'User-Agent': UA }, signal: ctrl.signal, redirect: 'follow' });
    const text = await res.text();
    return { status: res.status, headers: res.headers, text };
  } finally {
    clearTimeout(t);
  }
}

function stripTags(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

async function analyzeUrl(rawUrl) {
  let url = rawUrl.trim().replace(/\/$/, '');
  if (!/^https?:\/\//i.test(url)) url = 'https://' + url;

  const result = {
    url,
    domain: '',
    status: 'error',
    error: null,
    word_count: 0,
    has_schema: false,
    has_faq: false,
    has_sitemap: false,
    ai_bots_blocked: false,
    ai_bots_blocked_list: [],
    has_llms_txt: false,
    structured_data_types: [],
    title: '',
    meta_description: '',
    og_tags: {},
    has_og: false,
    h1_count: 0,
    h2_count: 0,
    h1_titles: [],
    img_count: 0,
    imgs_with_alt: 0,
  };

  let parsed;
  try {
    parsed = new URL(url);
  } catch (e) {
    result.error = 'Invalid URL';
    return result;
  }
  result.domain = parsed.hostname;

  let html = '';
  try {
    const r = await fetchWithTimeout(url, FETCH_TIMEOUT_MS);
    result.http_status = r.status;
    const ct = r.headers.get('content-type') || '';
    if (r.status === 200 && !/text\/html/i.test(ct)) {
      result.error = 'Not an HTML page';
      return result;
    }
    html = r.text;
  } catch (e) {
    result.error = `Could not reach site: ${e.message || e}`;
    return result;
  }

  // Text / word count
  const text = stripTags(html);
  result.word_count = text ? text.split(/\s+/).length : 0;

  // Title
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  result.title = titleMatch ? titleMatch[1].trim() : '';

  // Meta description
  let descMatch = html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i);
  if (!descMatch) descMatch = html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']description["']/i);
  result.meta_description = descMatch ? descMatch[1].trim() : '';

  // JSON-LD / Schema
  const schemaRegex = /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  const schemas = [];
  let m;
  while ((m = schemaRegex.exec(html)) !== null) schemas.push(m[1]);
  result.has_schema = schemas.length > 0;
  const typeSet = new Set();
  for (const s of schemas) {
    const tRegex = /"@type"\s*:\s*"([^"]+)"/g;
    let tm;
    while ((tm = tRegex.exec(s)) !== null) typeSet.add(tm[1]);
  }
  result.structured_data_types = Array.from(typeSet);

  // FAQ detection
  const faqPatterns = [
    /<div[^>]+class=["'][^"']*faq[^"']*["'][^>]*>[\s\S]*?<\/div>/i,
    /<section[^>]+class=["'][^"']*faq[^"']*["'][^>]*>[\s\S]*?<\/section>/i,
    /<h[23][^>]*>\s*[^<]*FAQ[^<]*\s*<\/h[23]>/i,
    /"@type"\s*:\s*"FAQPage"/i,
  ];
  result.has_faq = faqPatterns.some((p) => p.test(html));

  // OG tags
  const ogRegex = /<meta[^>]+property=["']og:([^"']+)["'][^>]+content=["']([^"']+)["']/gi;
  const og = {};
  let ogm;
  while ((ogm = ogRegex.exec(html)) !== null) og[ogm[1]] = ogm[2];
  result.og_tags = og;
  result.has_og = Object.keys(og).length > 0;

  // Headings
  const h1s = [...html.matchAll(/<h1[^>]*>([\s\S]*?)<\/h1>/gi)].map((x) => x[1]);
  const h2s = [...html.matchAll(/<h2[^>]*>([\s\S]*?)<\/h2>/gi)].map((x) => x[1]);
  result.h1_count = h1s.length;
  result.h2_count = h2s.length;
  result.h1_titles = h1s.map((h) => h.replace(/<[^>]+>/g, '').trim());

  // Images / alt
  const imgs = [...html.matchAll(/<img[^>]+>/gi)].map((x) => x[0]);
  result.img_count = imgs.length;
  result.imgs_with_alt = imgs.filter((img) => {
    const am = img.match(/alt=["']([^"']*)["']/i);
    return am && am[1].trim();
  }).length;

  // robots.txt + ai-bot checks + sitemap
  let robotsTxt = '';
  try {
    const r = await fetchWithTimeout(`${parsed.protocol}//${parsed.hostname}/robots.txt`, SIDE_TIMEOUT_MS);
    if (r.status === 200) robotsTxt = r.text;
  } catch {}

  const aiBots = ['gptbot', 'chatgpt', 'claudebot', 'perplexitybot', 'anthropic', 'bytespider', 'google-extended'];
  const blocked = [];
  for (const bot of aiBots) {
    const uaRegex = new RegExp(`User-agent:\\s*${bot}`, 'i');
    if (uaRegex.test(robotsTxt)) {
      const blockRegex = new RegExp(`User-agent:\\s*${bot}[\\s\\S]*?(?=User-agent:|$)`, 'i');
      const section = robotsTxt.match(blockRegex);
      if (section && /Disallow:\s*\/\S*/i.test(section[0])) blocked.push(bot);
    }
  }
  result.ai_bots_blocked = blocked.length > 0;
  result.ai_bots_blocked_list = blocked;

  if (/Sitemap:/i.test(robotsTxt)) {
    result.has_sitemap = true;
  } else {
    try {
      const r = await fetchWithTimeout(`${parsed.protocol}//${parsed.hostname}/sitemap.xml`, SIDE_TIMEOUT_MS);
      if (r.status === 200) result.has_sitemap = true;
    } catch {}
  }

  // llms.txt
  try {
    const r = await fetchWithTimeout(`${parsed.protocol}//${parsed.hostname}/llms.txt`, SIDE_TIMEOUT_MS);
    if (r.status === 200) result.has_llms_txt = true;
  } catch {}

  result.status = 'ok';
  return result;
}

function scoreAnalysis(r) {
  if (r.status === 'error') {
    return { total: 0, grade: 'F', readiness: 'Unknown', dimensions: {}, gaps: ['Site could not be reached'] };
  }

  const gaps = [];

  // Each dimension scored 0–10 consistently, then weighted-average
  const dims = {
    'Structured Data': (() => {
      if (!r.has_schema) { gaps.push('No JSON-LD / Schema.org markup found'); return 0; }
      const n = r.structured_data_types.length;
      if (n >= 5) return 10;
      if (n >= 3) return 8;
      if (n >= 2) return 6;
      if (n >= 1) return 4;
      return 2;
    })(),
    'AI Bot Access': (() => {
      if (r.ai_bots_blocked) {
        gaps.push(`AI bots blocked: ${r.ai_bots_blocked_list.join(', ')}`);
        return 2;
      }
      return 10;
    })(),
    'FAQ Content': (() => {
      if (!r.has_faq) { gaps.push('No FAQ section detected — LLMs lose Q&A structure'); return 3; }
      return 10;
    })(),
    'Sitemap': (() => {
      if (!r.has_sitemap) { gaps.push('Missing or incomplete sitemap.xml'); return 3; }
      return 10;
    })(),
    'Content Depth': (() => {
      const wc = r.word_count || 0;
      const score = Math.min(wc / 80, 10);
      if (wc < 300) gaps.push(`Thin homepage content (${wc} words)`);
      return score;
    })(),
    'Heading Structure': (() => {
      if (r.h1_count === 0) { gaps.push('No H1 heading found'); return 2; }
      if (r.h1_count > 1) return 5;
      return Math.min(5 + r.h2_count, 10);
    })(),
    'Semantic HTML': (() => {
      if (r.img_count === 0) return 7;
      if (r.imgs_with_alt >= r.img_count * 0.5) return 9;
      gaps.push('Images missing alt text');
      return 4;
    })(),
    'Social Meta': (() => {
      if (!r.has_og) { gaps.push('No OpenGraph meta tags'); return 3; }
      return 10;
    })(),
  };

  const weights = {
    'Structured Data': 3.0,
    'AI Bot Access': 2.5,
    'FAQ Content': 2.0,
    'Sitemap': 1.5,
    'Content Depth': 2.0,
    'Heading Structure': 1.5,
    'Semantic HTML': 1.0,
    'Social Meta': 1.0,
  };

  const totalWeight = 14.5;
  let weightedSum = 0;
  for (const [dim, score] of Object.entries(dims)) {
    weightedSum += score * weights[dim];
  }

  // llms.txt bonus: +0.3 to final score (capped at 10)
  let total10 = Math.round(((weightedSum / totalWeight) + (r.has_llms_txt ? 0.3 : 0)) * 10) / 10;
  total10 = Math.min(total10, 10);

  const grade = total10 >= 8.5 ? 'A' : total10 >= 7 ? 'B' : total10 >= 5 ? 'C' : total10 >= 3 ? 'D' : 'F';
  const readiness = { A: 'Very High', B: 'High', C: 'Medium', D: 'Low', F: 'Very Low' }[grade] || 'Unknown';

  const dimensions = {};
  for (const [dim, score] of Object.entries(dims)) {
    dimensions[dim] = { score, max: 10, weight: weights[dim], pct: Math.round(score * 10) };
  }

  // Dedup gaps
  const seen = new Set();
  const unique = [];
  for (const g of gaps) {
    const k = g.split(' (')[0];
    if (!seen.has(k)) { seen.add(k); unique.push(g); }
  }

  return { total: total10, grade, readiness, dimensions, gaps: unique.slice(0, 5) };
}

function buildHtmlReport(name, email, url, analysis, scored) {
  const brand = {
    cream: '#FAF7F2',
    card: '#FFFDF8',
    ink: '#1A1D1E',
    inkSoft: '#3B3F42',
    muted: '#7A7568',
    line: '#E6DFD0',
    sage: '#7A9B76',
    sageDeep: '#4A6B46',
    sageSoft: '#E8F0E6',
    clay: '#C45D3E',
    clayDeep: '#9C4527',
    claySoft: '#F5E0DA',
  };

  const gradeMeta = {
    A: { color: brand.sage, bg: brand.sageSoft, label: 'Excellent' },
    B: { color: brand.sageDeep, bg: brand.sageSoft, label: 'Good' },
    C: { color: '#B8941D', bg: '#FDF6D7', label: 'Fair' },
    D: { color: brand.clay, bg: brand.claySoft, label: 'Needs Work' },
    F: { color: '#B91C1C', bg: '#FEE2E2', label: 'Critical' },
  }[scored.grade] || { color: brand.muted, bg: brand.cream, label: 'Unknown' };

  const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  // Dimension bars — full-width, brand-colored
  const dimsHtml = Object.entries(scored.dimensions)
    .map(([dim, d]) => {
      const pct = d.pct;
      const barColor = pct >= 70 ? brand.sage : pct >= 40 ? '#C4A43B' : brand.clay;
      return `<tr>
        <td style="padding:14px 0;font-size:15px;color:${brand.ink};font-weight:500;">${dim}</td>
        <td style="padding:14px 0;" width="60%">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="background:${brand.line};border-radius:4px;height:10px;overflow:hidden;padding:0;">
                <div style="background:${barColor};height:10px;width:${pct}%;border-radius:4px;"></div>
              </td>
            </tr>
          </table>
        </td>
        <td style="padding:14px 0 14px 12px;font-size:15px;font-weight:600;color:${barColor};white-space:nowrap;" width="50">${pct}%</td>
      </tr>`;
    })
    .join('');

  // Gaps
  const gapsHtml = scored.gaps.length
    ? scored.gaps.map((g) => `<tr><td style="padding:10px 0;border-bottom:1px solid ${brand.line};">
      <table cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="color:${brand.clay};font-size:16px;padding-right:10px;vertical-align:top;">⚠</td>
        <td style="font-size:14px;color:${brand.inkSoft};line-height:1.5;">${escapeHtml(g)}</td>
      </tr></table>
    </td></tr>`).join('')
    : `<tr><td style="padding:20px;font-size:14px;color:${brand.sageDeep};text-align:center;background:${brand.sageSoft};border-radius:8px;">
      ✓ No critical gaps detected — solid foundation.
    </td></tr>`;

  // Technical checks
  const checks = [
    ['Structured Data / Schema', !!analysis.has_schema, (analysis.structured_data_types || []).slice(0, 3).join(', ') || 'None'],
    ['AI Bot Access', !analysis.ai_bots_blocked, analysis.ai_bots_blocked ? 'Blocked: ' + analysis.ai_bots_blocked_list.join(', ') : 'All clear'],
    ['FAQ Content', !!analysis.has_faq, ''],
    ['XML Sitemap', !!analysis.has_sitemap, ''],
    ['OpenGraph Meta', !!analysis.has_og, ''],
    ['llms.txt', !!analysis.has_llms_txt, ''],
    ['Homepage Words', (analysis.word_count || 0) > 300, `${analysis.word_count || 0} words`],
  ];
  const checksHtml = checks.map(([label, passed, detail]) => {
    const icon = passed
      ? `<span style="display:inline-block;width:18px;height:18px;background:${brand.sage};color:#fff;border-radius:50%;text-align:center;line-height:18px;font-size:11px;margin-right:8px;">✓</span>`
      : `<span style="display:inline-block;width:18px;height:18px;background:${brand.clay};color:#fff;border-radius:50%;text-align:center;line-height:18px;font-size:11px;margin-right:8px;">✗</span>`;
    const d = detail ? ` <span style="color:${brand.muted};font-size:12px;">(${escapeHtml(detail)})</span>` : '';
    return `<tr><td style="padding:8px 0;font-size:14px;color:${brand.inkSoft};">${icon}${escapeHtml(label)}${d}</td></tr>`;
  }).join('');

  const title = analysis.title || '—';
  let meta = analysis.meta_description || '—';
  if (meta.length > 140) meta = meta.slice(0, 140) + '...';

  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Your GEO Snapshot — MadTech Growth</title></head>
<body style="margin:0;padding:0;background:${brand.cream};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:${brand.ink};">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${brand.cream};">
  <tr><td align="center" style="padding:48px 20px 32px;">
    <table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">
      <!-- Header -->
      <tr><td style="text-align:center;padding-bottom:32px;">
        <p style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:${brand.ink};margin:0;letter-spacing:-0.02em;">MadTech<span style="color:${brand.sageDeep};">Growth</span></p>
        <p style="font-size:11px;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:${brand.sageDeep};margin:8px 0 0;">Free GEO Snapshot</p>
      </td></tr>

      <!-- Hero score card -->
      <tr><td style="background:${brand.card};border:1px solid ${brand.line};border-radius:16px;padding:40px;text-align:center;">
        <p style="font-size:13px;color:${brand.muted};margin:0 0 16px;">For ${escapeHtml(name)} &middot; ${dateStr}</p>
        <h1 style="font-family:Georgia,'Times New Roman',serif;font-size:26px;font-weight:400;color:${brand.ink};margin:0 0 24px;">Your AI Visibility Report</h1>

        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="50%" style="text-align:center;border-right:1px solid ${brand.line};padding:16px 0;">
              <div style="display:inline-block;width:110px;height:110px;border-radius:50%;background:${gradeMeta.bg};border:3px solid ${gradeMeta.color};text-align:center;">
                <div style="padding-top:18px;font-size:42px;font-weight:700;color:${gradeMeta.color};line-height:1;">${scored.total}</div>
                <div style="font-size:11px;color:${brand.muted};margin-top:2px;">out of 10</div>
                <div style="font-size:11px;font-weight:600;color:${gradeMeta.color};margin-top:4px;">${scored.grade}</div>
              </div>
            </td>
            <td width="50%" style="text-align:center;padding:16px 0 16px 20px;vertical-align:middle;">
              <p style="font-size:15px;font-weight:600;color:${gradeMeta.color};margin:0;">${scored.readiness} Readiness</p>
              <p style="font-size:13px;color:${brand.muted};margin:8px 0 0;line-height:1.6;">AI agents can ${scored.grade === 'A' || scored.grade === 'B' ? 'easily find and recommend you' : scored.grade === 'C' ? 'partially understand your site' : 'not yet recommend you with confidence'}.</p>
            </td>
          </tr>
        </table>
      </td></tr>

      <!-- Spacer -->
      <tr><td style="height:24px;"></td></tr>

      <!-- Site analyzed -->
      <tr><td style="background:${brand.card};border:1px solid ${brand.line};border-radius:16px;padding:28px 32px;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:${brand.muted};margin:0 0 14px;">Site Analyzed</p>
        <p style="font-size:16px;font-weight:600;color:${brand.ink};margin:0 0 4px;">${escapeHtml(analysis.domain || '')}</p>
        <p style="font-size:13px;color:${brand.muted};margin:0 0 12px;">${escapeHtml(url)}</p>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${brand.cream};border-radius:8px;">
          <tr><td style="padding:14px 18px;">
            <p style="font-size:12px;color:${brand.muted};margin:0 0 4px;"><strong style="color:${brand.inkSoft};">Title:</strong> ${escapeHtml(title)}</p>
            <p style="font-size:12px;color:${brand.muted};margin:0;"><strong style="color:${brand.inkSoft};">Meta:</strong> ${escapeHtml(meta)}</p>
          </td></tr>
        </table>
      </td></tr>

      <!-- Spacer -->
      <tr><td style="height:24px;"></td></tr>

      <!-- 8 Dimensions -->
      <tr><td style="background:${brand.card};border:1px solid ${brand.line};border-radius:16px;padding:28px 32px;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:${brand.muted};margin:0 0 8px;">8 Dimension Breakdown</p>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">${dimsHtml}</table>
      </td></tr>

      <!-- Spacer -->
      <tr><td style="height:24px;"></td></tr>

      <!-- Technical checks -->
      <tr><td style="background:${brand.card};border:1px solid ${brand.line};border-radius:16px;padding:28px 32px;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:${brand.muted};margin:0 0 14px;">Technical Checks</p>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">${checksHtml}</table>
      </td></tr>

      <!-- Spacer -->
      <tr><td style="height:24px;"></td></tr>

      <!-- Gaps -->
      <tr><td style="background:${brand.card};border:1px solid ${brand.line};border-radius:16px;padding:28px 32px;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:${brand.muted};margin:0 0 14px;">Top Gaps to Fix</p>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">${gapsHtml}</table>
      </td></tr>

      <!-- Spacer -->
      <tr><td style="height:24px;"></td></tr>

      <!-- CTA -->
      <tr><td style="text-align:center;padding:8px 0 32px;">
        <a href="https://madtechgrowth.com" style="display:inline-block;background:${brand.clay};color:#FFF;text-decoration:none;font-size:15px;font-weight:600;padding:14px 36px;border-radius:999px;">Book a Full GEO Audit →</a>
        <p style="font-size:12px;color:${brand.muted};margin-top:14px;line-height:1.6;">A full audit covers all 8 dimensions, competitor benchmarking,<br/>and a prioritized implementation roadmap.</p>
      </td></tr>

      <!-- Footer -->
      <tr><td style="text-align:center;padding:24px 0 0;border-top:1px solid ${brand.line};">
        <p style="font-size:12px;color:${brand.muted};margin:0;">MadTech Growth &middot; Agentic Commerce Advisory &middot; New York, NY<br/><a href="mailto:hello@madtechgrowth.com" style="color:${brand.muted};">hello@madtechgrowth.com</a></p>
        <p style="font-size:11px;color:${brand.muted};margin:10px 0 0;">You requested this free GEO Snapshot.</p>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function sendEmail(name, email, url, analysis, scored) {
  const apiKey = process.env.RESEND_API_KEY;
  const fromEmail = process.env.FROM_EMAIL || 'snapshot@email.madtechgrowth.com';
  const fromName = process.env.FROM_NAME || 'MadTech Growth';

  if (!apiKey) {
    throw new Error('RESEND_API_KEY env var not set in Netlify dashboard.');
  }

  const html = buildHtmlReport(name, email, url, analysis, scored);

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: `${fromName} <${fromEmail}>`,
      to: [email],
      subject: `Your GEO Snapshot for ${analysis.domain || 'your site'}`,
      html,
      text: `GEO Snapshot Report\n\nHi ${name},\n\nYour AI Visibility Score: ${scored.total}/10 (Grade: ${scored.grade})\nReadiness: ${scored.readiness}\n\nSite: ${url}\n\nTop Gaps:\n${scored.gaps.map((g) => '  - ' + g).join('\n')}\n\nGet your full audit at: https://madtechgrowth.com`,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Resend API error ${res.status}: ${body}`);
  }
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Content-Type': 'application/json',
};

export const handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: corsHeaders, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers: corsHeaders, body: JSON.stringify({ error: 'Method not allowed' }) };

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch {
    return { statusCode: 400, headers: corsHeaders, body: JSON.stringify({ error: 'Invalid JSON' }) };
  }

  const name = (body.name || '').trim();
  const email = (body.email || '').trim();
  const url = (body.url || '').trim();

  if (!name || !email || !url) {
    return { statusCode: 400, headers: corsHeaders, body: JSON.stringify({ error: 'name, email, and url are required' }) };
  }
  if (!email.includes('@') || !email.split('@').pop().includes('.')) {
    return { statusCode: 400, headers: corsHeaders, body: JSON.stringify({ error: 'Invalid email address' }) };
  }

  const analysis = await analyzeUrl(url);
  const scored = scoreAnalysis(analysis);

  if (analysis.status === 'error') {
    return {
      statusCode: 200,
      headers: corsHeaders,
      body: JSON.stringify({
        message: "We couldn't reach that URL. Please check it's a public website and try again. If the issue persists, email us at hello@madtechgrowth.com.",
        analysis: { status: 'error', error: analysis.error || 'Unknown error' },
      }),
    };
  }

  let emailOk = false;
  let emailError = null;
  try {
    await sendEmail(name, email, url, analysis, scored);
    emailOk = true;
  } catch (e) {
    console.error('[geo-snapshot] Email send failed:', e);
    emailError = e.message || String(e);
  }

  return {
    statusCode: 200,
    headers: corsHeaders,
    body: JSON.stringify({
      message: emailOk ? `GEO Snapshot sent to ${email}` : `Analysis complete, but email delivery failed: ${emailError}`,
      emailSent: emailOk,
      emailError: emailError,
      score: scored.total,
      grade: scored.grade,
      readiness: scored.readiness,
      gaps: scored.gaps,
    }),
  };
};
