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

  // 1. Structured Data (weight 3.0)
  let dim1 = 0;
  if (r.has_schema) {
    const n = r.structured_data_types.length;
    dim1 = n >= 3 ? 9 : n >= 1 ? 6 : 4;
  } else {
    gaps.push('No JSON-LD / Schema.org markup found');
  }

  // 2. AI Bot Access (2.5)
  let dim2 = 10;
  if (r.ai_bots_blocked) {
    dim2 = 2;
    gaps.push(`AI bots blocked: ${r.ai_bots_blocked_list.join(', ')}`);
  }

  // 3. FAQ (2.0)
  const dim3 = r.has_faq ? 10 : 4;
  if (!r.has_faq) gaps.push('No FAQ section detected — LLMs lose Q&A structure');

  // 4. Sitemap (1.5)
  const dim4 = r.has_sitemap ? 10 : 3;
  if (!r.has_sitemap) gaps.push('Missing or incomplete sitemap.xml');

  // 5. Content depth (2.0)
  const wc = r.word_count || 0;
  const dim5 = Math.min(wc / 80, 10);
  if (wc < 300) gaps.push(`Thin homepage content (${wc} words)`);

  // 6. Headings (1.5)
  let dim6;
  if (r.h1_count === 0) dim6 = 2;
  else if (r.h1_count > 1) dim6 = 6;
  else dim6 = Math.min(5 + r.h2_count, 10);
  if (r.h1_count === 0) gaps.push('No H1 heading found');

  // 7. Semantic HTML (1.0)
  let dim7 = 5;
  if (r.img_count > 0 && r.imgs_with_alt < r.img_count * 0.5) {
    dim7 -= 2;
    gaps.push('Images missing alt text');
  }

  // 8. Social meta (1.0)
  const dim8 = r.has_og ? 10 : 3;
  if (!r.has_og) gaps.push('No OpenGraph meta tags');

  const bonus = r.has_llms_txt ? 1 : 0;
  const raw = dim1 + dim2 + dim3 + dim4 + dim5 + dim6 + dim7 + dim8 + bonus;
  const total10 = Math.round((raw / 30) * 10 * 10) / 10;
  const grade = total10 >= 8.5 ? 'A' : total10 >= 7 ? 'B' : total10 >= 5 ? 'C' : total10 >= 3 ? 'D' : 'F';
  const readiness = { A: 'Very High', B: 'High', C: 'Medium', D: 'Low', F: 'Very Low' }[grade] || 'Unknown';

  const dimensions = {
    'Structured Data': { score: dim1 / 3, max: 10, weight: 3.0 },
    'AI Bot Access': { score: dim2 / 2.5, max: 10, weight: 2.5 },
    'FAQ Content': { score: dim3 / 2, max: 10, weight: 2.0 },
    Sitemap: { score: dim4 / 1.5, max: 10, weight: 1.5 },
    'Content Depth': { score: dim5 / 2, max: 10, weight: 2.0 },
    'Heading Structure': { score: dim6 / 1.5, max: 10, weight: 1.5 },
    'Semantic HTML': { score: dim7, max: 10, weight: 1.0 },
    'Social Meta': { score: dim8, max: 10, weight: 1.0 },
  };

  // Dedup gaps
  const seen = new Set();
  const unique = [];
  for (const g of gaps) {
    const k = g.split(' (')[0];
    if (!seen.has(k)) {
      seen.add(k);
      unique.push(g);
    }
  }

  return { total: total10, grade, readiness, dimensions, gaps: unique.slice(0, 5) };
}

function buildHtmlReport(name, email, url, analysis, scored) {
  const gradeColors = { A: '#22c55e', B: '#84cc16', C: '#eab308', D: '#f97316', F: '#ef4444' };
  const readinessColors = { 'Very High': '#22c55e', High: '#84cc16', Medium: '#eab308', Low: '#f97316', 'Very Low': '#ef4444' };
  const gradeColor = gradeColors[scored.grade] || '#7A7568';
  const readColor = readinessColors[scored.readiness] || '#7A7568';
  const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const dimsHtml = Object.entries(scored.dimensions)
    .map(([dim, d]) => {
      const pct = Math.min(Math.round((d.score / d.max) * 100), 100);
      const bar = pct >= 70 ? '#22c55e' : pct >= 40 ? '#eab308' : '#ef4444';
      return `<tr>
        <td style="padding:10px 16px;font-size:14px;color:#1A1D1E;">${dim}</td>
        <td style="padding:10px 8px;">
          <div style="background:#FAF7F2;border-radius:6px;height:8px;width:120px;overflow:hidden;">
            <div style="background:${bar};height:100%;width:${pct}%;border-radius:6px;"></div>
          </div>
        </td>
        <td style="padding:10px 16px;font-size:14px;font-weight:600;color:${bar};">${pct}%</td>
      </tr>`;
    })
    .join('');

  const gapsHtml = scored.gaps
    .map((g) => `<li style="margin-bottom:10px;font-size:14px;color:#3B3F42;">⚠ ${escapeHtml(g)}</li>`)
    .join('');

  const checks = [
    ['Structured Data / Schema', !!analysis.has_schema, (analysis.structured_data_types || []).slice(0, 3).join(', ') || 'None found'],
    ['AI Bot Access (robots.txt)', !analysis.ai_bots_blocked, analysis.ai_bots_blocked ? 'Blocked: ' + analysis.ai_bots_blocked_list.join(', ') : 'All clear'],
    ['FAQ Content', !!analysis.has_faq, ''],
    ['XML Sitemap', !!analysis.has_sitemap, ''],
    ['OpenGraph / Social Meta', !!analysis.has_og, ''],
    ['llms.txt', !!analysis.has_llms_txt, ''],
    ['Homepage Word Count', (analysis.word_count || 0) > 300, `${analysis.word_count || 0} words`],
  ];
  const checksHtml = checks
    .map(([label, passed, detail]) => {
      const icon = passed ? '✅' : '❌';
      const d = detail ? ` <span style="color:#7A7568;">(${escapeHtml(detail)})</span>` : '';
      return `<div style="margin-bottom:8px;font-size:14px;">${icon} ${escapeHtml(label)}${d}</div>`;
    })
    .join('');

  const title = analysis.title || '—';
  let meta = analysis.meta_description || '—';
  if (meta.length > 120) meta = meta.slice(0, 120) + '...';

  const gapsSection = scored.gaps.length
    ? `<tr><td style="padding:24px 0 4px 0;">
         <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#7A7568;margin-bottom:14px;">Top Gaps to Fix</p>
       </td></tr>
       <tr><td style="background:#F3EEE4;border-radius:12px;padding:24px;margin-bottom:24px;">
         <ol style="margin:0;padding-left:20px;">${gapsHtml}</ol>
       </td></tr>`
    : '';

  const readinessBlurb =
    scored.grade === 'A' || scored.grade === 'B'
      ? 'easily find and recommend you'
      : scored.grade === 'C'
      ? 'partially understand your site'
      : 'not yet recommend you with confidence';

  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Your GEO Snapshot — MadTech Growth</title></head>
<body style="margin:0;padding:0;background:#FAF7F2;font-family:'Outfit','Helvetica Neue',Arial,sans-serif;color:#1A1D1E;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#FAF7F2;padding:40px 20px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">
      <tr><td style="padding:0 0 32px 0;text-align:center;">
        <p style="font-size:13px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#4A6B46;margin:0 0 12px;">Free GEO Snapshot</p>
        <h1 style="font-family:Georgia,serif;font-size:28px;font-weight:400;color:#1A1D1E;margin:0 0 8px;">Your AI Visibility Report</h1>
        <p style="font-size:14px;color:#7A7568;margin:0;">For ${escapeHtml(name)} · ${dateStr}</p>
      </td></tr>
      <tr><td style="background:#F3EEE4;border-radius:16px;padding:36px 40px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td width="50%" style="text-align:center;border-right:1px solid rgba(0,0,0,0.07);">
            <div style="font-size:72px;font-weight:700;color:${gradeColor};line-height:1;">${scored.total}</div>
            <div style="font-size:13px;color:#7A7568;margin-top:4px;">out of 10</div>
            <div style="display:inline-block;margin-top:10px;padding:4px 14px;border-radius:100px;font-size:12px;font-weight:600;background:${gradeColor}22;color:${gradeColor};border:1px solid ${gradeColor}44;">Grade: ${scored.grade}</div>
          </td>
          <td width="50%" style="text-align:center;padding-left:20px;">
            <div style="font-size:18px;font-weight:600;color:${readColor};">${scored.readiness} Readiness</div>
            <p style="font-size:13px;color:#7A7568;margin-top:8px;line-height:1.5;">AI agents can<br/>${readinessBlurb}</p>
          </td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:24px 0 4px 0;"><p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#7A7568;margin-bottom:14px;">Site Analyzed</p></td></tr>
      <tr><td style="background:#F3EEE4;border-radius:12px;padding:20px 24px;">
        <p style="font-size:16px;font-weight:500;color:#1A1D1E;margin:0 0 4px;">${escapeHtml(analysis.domain || '')}</p>
        <p style="font-size:13px;color:#7A7568;margin:0 0 4px;">${escapeHtml(url)}</p>
        <p style="font-size:12px;color:#7A7568;margin:8px 0 0;">Title: ${escapeHtml(title)}</p>
        <p style="font-size:12px;color:#7A7568;margin:2px 0 0;">Meta: ${escapeHtml(meta)}</p>
      </td></tr>
      <tr><td style="padding:24px 0 4px 0;"><p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#7A7568;margin-bottom:14px;">8 Dimension Breakdown</p></td></tr>
      <tr><td style="background:#F3EEE4;border-radius:12px;overflow:hidden;"><table width="100%" cellpadding="0" cellspacing="0" border="0">${dimsHtml}</table></td></tr>
      <tr><td style="padding:24px 0 4px 0;"><p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#7A7568;margin-bottom:14px;">Technical Checks</p></td></tr>
      <tr><td style="background:#F3EEE4;border-radius:12px;padding:24px;">${checksHtml}</td></tr>
      ${gapsSection}
      <tr><td style="text-align:center;padding:16px 0 8px;">
        <a href="https://madtechgrowth.com" style="display:inline-block;background:#C45D3E;color:#FFF;text-decoration:none;font-size:15px;font-weight:600;padding:14px 36px;border-radius:8px;">Book a Full GEO Audit →</a>
        <p style="font-size:12px;color:#7A7568;margin-top:12px;line-height:1.5;">A full audit covers all 8 dimensions, competitor benchmarking,<br/>and a prioritized implementation roadmap.</p>
      </td></tr>
      <tr><td style="text-align:center;padding:40px 0 0;border-top:1px solid rgba(0,0,0,0.06);">
        <p style="font-size:12px;color:#7A7568;margin:0;">MadTech Growth · Agentic Commerce Advisory · New York, NY<br/><a href="mailto:hello@madtechgrowth.com" style="color:#7A7568;">hello@madtechgrowth.com</a></p>
        <p style="font-size:11px;color:#3a3530;margin:8px 0 0;">You're receiving this because you requested a free GEO Snapshot.</p>
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

  try {
    await sendEmail(name, email, url, analysis, scored);
  } catch (e) {
    console.error('[geo-snapshot] Email send failed:', e);
  }

  return {
    statusCode: 200,
    headers: corsHeaders,
    body: JSON.stringify({
      message: `GEO Snapshot sent to ${email}`,
      score: scored.total,
      grade: scored.grade,
      readiness: scored.readiness,
      gaps: scored.gaps,
    }),
  };
};
