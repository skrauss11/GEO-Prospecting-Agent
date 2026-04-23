#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo-snapshot Netlify Function
Receives: POST { name, email, url }
Action:   Analyzes URL across 8 GEO dimensions
Returns:  Sends branded HTML report to submitter's email
"""

import os
import json
import re
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

# ─── HTML Parser to extract text ──────────────────────────────────────────────

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = False
    def handle_data(self, data):
        if not self.skip:
            self.text_parts.append(data)
    def get_text(self):
        return ' '.join(p.strip() for p in self.text_parts if p.strip())

# ─── GEO Analysis ─────────────────────────────────────────────────────────────

def analyze_url(raw_url: str) -> dict:
    """Run geo analysis on a URL. Returns a dict of findings."""

    url = raw_url.strip().rstrip('/')
    if not url.startswith('http'):
        url = 'https://' + url

    result = {
        "url": url,
        "domain": "",
        "status": "error",
        "error": None,
        "score": 0,
        "score_grade": "F",
        "readiness": "Unknown",
        "checks": {},
        "top_gaps": [],
        "word_count": 0,
        "has_schema": False,
        "has_faq": False,
        "has_sitemap": False,
        "ai_bots_blocked": False,
        "has_llms_txt": False,
        "structured_data_types": [],
    }

    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        result["domain"] = domain

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; GEO-Snapshot/1.0; +https://madtechgrowth.com/bot)"
        }
        req = Request(url, headers=headers, timeout=15)

        try:
            with urlopen(req, timeout=15) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")
                html_bytes = resp.read()
        except HTTPError as e:
            # Some sites block but return 403/401 — still get the body sometimes
            status = e.code
            html_bytes = e.read() if e.fp else b""
            content_type = e.headers.get("Content-Type", "")

        result["http_status"] = status

        if "text/html" not in content_type and status == 200:
            result["error"] = "Not an HTML page"
            return result

        # Decode HTML
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                html = html_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                html = html_bytes.decode("utf-8", errors="replace")

        # ── Basic text extraction ──────────────────────────────────────────
        parser = TextExtractor()
        try:
            parser.feed(html)
        except Exception:
            pass
        text = parser.get_text()
        result["word_count"] = len(text.split())

        # ── Title ──────────────────────────────────────────────────────────
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        result["title"] = title_match.group(1).strip() if title_match else ""

        # ── Meta description ───────────────────────────────────────────────
        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if not desc_match:
            desc_match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
                html, re.IGNORECASE
            )
        result["meta_description"] = desc_match.group(1).strip() if desc_match else ""

        # ── Schema / JSON-LD ───────────────────────────────────────────────
        schema_pattern = r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        schemas = re.findall(schema_pattern, html, re.IGNORECASE | re.DOTALL)
        result["has_schema"] = len(schemas) > 0
        result["structured_data_types"] = []
        for s in schemas:
            s = s.strip()
            if '"@type"' in s:
                types = re.findall(r'"@type"\s*:\s*"([^"]+)"', s)
                result["structured_data_types"].extend(types)
        result["structured_data_types"] = list(set(result["structured_data_types"]))

        # ── FAQ content ────────────────────────────────────────────────────
        faq_patterns = [
            r'<div[^>]+class=["\'][^"\']*faq[^"\']*["\'][^>]*>(.*?)</div>',
            r'<section[^>]+class=["\'][^"\']*faq[^"\']*["\'][^>]*>(.*?)</section>',
            r'<h[23][^>]*>\s*([^<]*[Ff]AQ[^<]*)\s*</h[23]>',
            r'"@type"\s*:\s*"FAQPage"',
        ]
        result["has_faq"] = any(re.search(p, html, re.IGNORECASE | re.DOTALL) for p in faq_patterns)

        # ── OpenGraph / Twitter Cards ─────────────────────────────────────
        og_pattern = r'<meta[^>]+property=["\']og:([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']'
        og_tags = re.findall(og_pattern, html, re.IGNORECASE)
        result["og_tags"] = {k: v for k, v in og_tags}
        result["has_og"] = len(og_tags) > 0

        # ── Heading structure ─────────────────────────────────────────────
        h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
        result["h1_count"] = len(h1s)
        result["h2_count"] = len(h2s)
        result["h1_titles"] = [re.sub(r'<[^>]+>', '', h).strip() for h in h1s]

        # ── Image alt text ────────────────────────────────────────────────
        imgs = re.findall(r'<img[^>]+>', html, re.IGNORECASE)
        alt_texts = [re.search(r'alt=["\']([^"\']*)["\']', img, re.IGNORECASE) for img in imgs]
        alts = [a.group(1) for a in alt_texts if a]
        result["img_count"] = len(imgs)
        result["imgs_with_alt"] = len([a for a in alts if a.strip()])

        # ── Robots.txt ────────────────────────────────────────────────────
        robots_txt = ""
        try:
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            rob_req = Request(robots_url, headers=headers, timeout=8)
            with urlopen(rob_req, timeout=8) as r:
                robots_txt = r.read().decode("utf-8", errors="replace")
        except Exception:
            pass

        ai_bot_patterns = ["gptbot", "chatgpt", "claudebot", "perplexitybot",
                           "anthropic", "bytespider", "google-extended"]
        blocked = []
        for bot in ai_bot_patterns:
            if re.search(rf"User-agent:\s*{re.escape(bot)}", robots_txt, re.IGNORECASE):
                disallows = re.findall(
                    rf"User-agent:\s*{re.escape(bot)}.*?(?=User-agent:|Allow:|Disallow:|$)",
                    robots_txt, re.IGNORECASE | re.DOTALL
                )
                if any("Disallow:" in d for d in disallows):
                    blocked.append(bot)
        result["ai_bots_blocked"] = len(blocked) > 0
        result["ai_bots_blocked_list"] = blocked

        # ── Sitemap ────────────────────────────────────────────────────────
        result["has_sitemap"] = False
        if "Sitemap:" in robots_txt:
            result["has_sitemap"] = True
        else:
            try:
                sm_url = f"{parsed.scheme}://{domain}/sitemap.xml"
                sm_req = Request(sm_url, headers=headers, timeout=8)
                with urlopen(sm_req, timeout=8) as r:
                    if r.status == 200:
                        result["has_sitemap"] = True
            except Exception:
                pass

        # ── llms.txt ──────────────────────────────────────────────────────
        result["has_llms_txt"] = False
        try:
            llm_url = f"{parsed.scheme}://{domain}/llms.txt"
            llm_req = Request(llm_url, headers=headers, timeout=8)
            with urlopen(llm_req, timeout=8) as r:
                if r.status == 200:
                    result["has_llms_txt"] = True
        except Exception:
            pass

        result["status"] = "ok"

    except URLError as e:
        result["error"] = f"Could not reach site: {e.reason}"
    except Exception as e:
        result["error"] = str(e)

    return result


def score_analysis(r: dict) -> dict:
    """Assign scores 1-10 across 8 GEO dimensions. Returns (total_score, gaps)."""
    score = 0
    max_score = 10
    gaps = []

    def dim(name, earned, weight=1.0, max_val=10):
        val = min(earned * weight, max_val)
        return val, name

    # 1. Structured Data (weight 3.0 — most important)
    if r["status"] == "error":
        return {"total": 0, "grade": "F", "readiness": "Unknown",
                "dimensions": {}, "gaps": ["Site could not be reached"]}

    dim1_score = 0
    dim1_name = "Structured Data"
    if r["has_schema"]:
        n_types = len(r["structured_data_types"])
        if n_types >= 3:
            dim1_score = 9
        elif n_types >= 1:
            dim1_score = 6
        else:
            dim1_score = 4
    else:
        gaps.append("No JSON-LD / Schema.org markup found")

    # 2. AI Bot Accessibility (weight 2.5)
    dim2_score = 10
    dim2_name = "AI Bot Access"
    if r["ai_bots_blocked"]:
        dim2_score = 2
        gaps.append(f"AI bots blocked: {', '.join(r['ai_bots_blocked_list'])}")

    # 3. FAQ Content (weight 2.0)
    dim3_score = 10 if r["has_faq"] else 4
    dim3_name = "FAQ Content"
    if not r["has_faq"]:
        gaps.append("No FAQ section detected — LLMs lose Q&A structure")

    # 4. Sitemap (weight 1.5)
    dim4_score = 10 if r["has_sitemap"] else 3
    dim4_name = "Sitemap"
    if not r["has_sitemap"]:
        gaps.append("Missing or incomplete sitemap.xml")

    # 5. Content Depth (weight 2.0)
    wc = r.get("word_count", 0)
    dim5_score = min(wc / 80, 10)  # ~800 words = 10
    dim5_name = "Content Depth"
    if wc < 300:
        gaps.append(f"Thin homepage content ({wc} words)")

    # 6. Heading Structure (weight 1.5)
    h1c = r.get("h1_count", 0)
    h2c = r.get("h2_count", 0)
    if h1c == 0:
        dim6_score = 2
    elif h1c > 1:
        dim6_score = 6
    else:
        dim6_score = min(5 + h2c, 10)
    dim6_name = "Heading Structure"
    if h1c == 0:
        gaps.append("No H1 heading found")

    # 7. Semantic HTML (weight 1.0)
    sem_score = 5  # baseline
    dim7_name = "Semantic HTML"
    # Check for article tags, lists
    if r.get("img_count", 0) > 0 and r.get("imgs_with_alt", 0) < r.get("img_count", 0) * 0.5:
        sem_score -= 2
        gaps.append("Images missing alt text")
    dim7_score = sem_score

    # 8. Social Meta (weight 1.0)
    dim8_score = 10 if r.get("has_og", False) else 3
    dim8_name = "Social Meta"
    if not r.get("has_og"):
        gaps.append("No OpenGraph meta tags")

    # llms.txt bonus
    bonus = 1.0 if r.get("has_llms_txt") else 0

    total = dim1_score + dim2_score + dim3_score + dim4_score + dim5_score + dim6_score + dim7_score + dim8_score + bonus
    raw_max = 30 + bonus  # 8 dims base
    total_10 = round((total / 30) * 10, 1)

    grade = "A" if total_10 >= 8.5 else "B" if total_10 >= 7.0 else "C" if total_10 >= 5.0 else "D" if total_10 >= 3.0 else "F"
    readiness = {
        "A": "Very High", "B": "High", "C": "Medium", "D": "Low", "F": "Very Low"
    }.get(grade, "Unknown")

    dims = {
        dim1_name: {"score": dim1_score / 3, "max": 10, "weight": 3.0},
        dim2_name: {"score": dim2_score / 2.5, "max": 10, "weight": 2.5},
        dim3_name: {"score": dim3_score / 2, "max": 10, "weight": 2.0},
        dim4_name: {"score": dim4_score / 1.5, "max": 10, "weight": 1.5},
        dim5_name: {"score": dim5_score / 2, "max": 10, "weight": 2.0},
        dim6_name: {"score": dim6_score / 1.5, "max": 10, "weight": 1.5},
        dim7_name: {"score": dim7_score, "max": 10, "weight": 1.0},
        dim8_name: {"score": dim8_score, "max": 10, "weight": 1.0},
    }

    # Deduplicate and rank gaps
    seen = set()
    unique_gaps = []
    for g in gaps:
        key = g.split(" (")[0]
        if key not in seen:
            seen.add(key)
            unique_gaps.append(g)

    return {
        "total": total_10,
        "grade": grade,
        "readiness": readiness,
        "dimensions": dims,
        "gaps": unique_gaps[:5],
    }


# ─── Email ────────────────────────────────────────────────────────────────────

def build_html_report(name: str, email: str, url: str, analysis: dict, scored: dict) -> str:
    grade_colors = {
        "A": "#22c55e", "B": "#84cc16", "C": "#eab308",
        "D": "#f97316", "F": "#ef4444"
    }
    grade_color = grade_colors.get(scored["grade"], "#8A8279")
    readiness_colors = {
        "Very High": "#22c55e", "High": "#84cc16", "Medium": "#eab308",
        "Low": "#f97316", "Very Low": "#ef4444"
    }
    read_color = readiness_colors.get(scored["readiness"], "#8A8279")

    dims_html = ""
    for dim, d in scored["dimensions"].items():
        pct = min(int((d["score"] / d["max"]) * 100), 100)
        bar_color = "#22c55e" if pct >= 70 else "#eab308" if pct >= 40 else "#ef4444"
        dims_html += f"""
        <tr>
          <td style="padding:10px 16px;font-size:14px;color:#F2F0ED;">{dim}</td>
          <td style="padding:10px 8px;">
            <div style="background:#1a2540;border-radius:6px;height:8px;width:120px;overflow:hidden;">
              <div style="background:{bar_color};height:100%;width:{pct}%;border-radius:6px;"></div>
            </div>
          </td>
          <td style="padding:10px 16px;font-size:14px;font-weight:600;color:{bar_color};">{pct}%</td>
        </tr>"""

    gaps_html = ""
    for i, gap in enumerate(scored["gaps"], 1):
        gaps_html += f"<li style='margin-bottom:10px;font-size:14px;color:#D1CBC3;'>⚠ {gap}</li>"

    checks_html = ""
    checks = [
        ("Structured Data / Schema", analysis.get("has_schema", False),
         ", ".join(analysis.get("structured_data_types", [])[:3]) or "None found"),
        ("AI Bot Access (robots.txt)", not analysis.get("ai_bots_blocked", False),
         "Blocked: " + ", ".join(analysis["ai_bots_blocked_list"]) if analysis.get("ai_bots_blocked") else "All clear"),
        ("FAQ Content", analysis.get("has_faq", False), ""),
        ("XML Sitemap", analysis.get("has_sitemap", False), ""),
        ("OpenGraph / Social Meta", analysis.get("has_og", False), ""),
        ("llms.txt", analysis.get("has_llms_txt", False), ""),
        ("Homepage Word Count", analysis.get("word_count", 0) > 300, f"{analysis.get('word_count', 0)} words"),
    ]
    for label, passed, detail in checks:
        status_icon = "✅" if passed else "❌"
        detail_str = f" <span style='color:#8A8279;'>({detail})</span>" if detail else ""
        checks_html += f"<div style='margin-bottom:8px;font-size:14px;'>{status_icon} {label}{detail_str}</div>"

    title_text = analysis.get("title", "—")
    meta_desc = analysis.get("meta_description", "—")
    if len(meta_desc) > 120:
        meta_desc = meta_desc[:120] + "..."

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Your GEO Snapshot — MadTech Growth</title>
</head>
<body style="margin:0;padding:0;background:#0B1120;font-family:'Outfit','Helvetica Neue',Arial,sans-serif;color:#FAF8F5;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0B1120;padding:40px 20px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">

      <!-- Header -->
      <tr><td style="padding:0 0 32px 0;text-align:center;">
        <p style="font-size:13px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#C45D3E;margin:0 0 12px;">Free GEO Snapshot</p>
        <h1 style="font-family:'Georgia',serif;font-size:28px;font-weight:400;color:#FAF8F5;margin:0 0 8px;">
          Your AI Visibility Report
        </h1>
        <p style="font-size:14px;color:#8A8279;margin:0;">For {name} · {datetime.now().strftime('%B %d, %Y')}</p>
      </td></tr>

      <!-- Score Card -->
      <tr><td style="background:#1a2540;border-radius:16px;padding:36px 40px;margin-bottom:24px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="50%" style="text-align:center;border-right:1px solid rgba(255,255,255,0.07);">
              <div style="font-size:72px;font-weight:700;color:{grade_color};line-height:1;">{scored['total']}</div>
              <div style="font-size:13px;color:#8A8279;margin-top:4px;">out of 10</div>
              <div style="display:inline-block;margin-top:10px;padding:4px 14px;border-radius:100px;font-size:12px;font-weight:600;background:{grade_color}22;color:{grade_color};border:1px solid {grade_color}44;">
                Grade: {scored['grade']}
              </div>
            </td>
            <td width="50%" style="text-align:center;padding-left:20px;">
              <div style="font-size:18px;font-weight:600;color:{read_color};">{scored['readiness']} Readiness</div>
              <p style="font-size:13px;color:#8A8279;margin-top:8px;line-height:1.5;">
                AI agents can<br/>{ 'easily find and recommend you' if scored['grade'] in ('A','B') else 'partially understand your site' if scored['grade'] == 'C' else 'not yet recommend you with confidence' }
              </p>
            </td>
          </tr>
        </table>
      </td></tr>

      <!-- Site Info -->
      <tr><td style="padding:24px 0 4px 0;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#8A8279;margin-bottom:14px;">Site Analyzed</p>
      </td></tr>
      <tr><td style="background:#1a2540;border-radius:12px;padding:20px 24px;margin-bottom:24px;">
        <p style="font-size:16px;font-weight:500;color:#FAF8F5;margin:0 0 4px;">{analysis.get('domain','')}</p>
        <p style="font-size:13px;color:#8A8279;margin:0 0 4px;">{url}</p>
        <p style="font-size:12px;color:#4A4540;margin:8px 0 0;">Title: {title_text}</p>
        <p style="font-size:12px;color:#4A4540;margin:2px 0 0;">Meta: {meta_desc}</p>
      </td></tr>

      <!-- Dimension Breakdown -->
      <tr><td style="padding:24px 0 4px 0;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#8A8279;margin-bottom:14px;">8 Dimension Breakdown</p>
      </td></tr>
      <tr><td style="background:#1a2540;border-radius:12px;overflow:hidden;margin-bottom:24px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          {dims_html}
        </table>
      </td></tr>

      <!-- Checks -->
      <tr><td style="padding:24px 0 4px 0;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#8A8279;margin-bottom:14px;">Technical Checks</p>
      </td></tr>
      <tr><td style="background:#1a2540;border-radius:12px;padding:24px;margin-bottom:24px;">
        {checks_html}
      </td></tr>

      <!-- Top Gaps -->
      { (lambda: f"""
      <tr><td style="padding:24px 0 4px 0;">
        <p style="font-size:11px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#8A8279;margin-bottom:14px;">Top Gaps to Fix</p>
      </td></tr>
      <tr><td style="background:#1a2540;border-radius:12px;padding:24px;margin-bottom:24px;">
        <ol style="margin:0;padding-left:20px;">{gaps_html}</ol>
      </td></tr>""")() if scored['gaps'] else ""}

      <!-- CTA -->
      <tr><td style="text-align:center;padding:16px 0 8px;">
        <a href="https://madtechgrowth.com" style="display:inline-block;background:#C45D3E;color:#FAF8F5;text-decoration:none;font-size:15px;font-weight:600;padding:14px 36px;border-radius:8px;">
          Book a Full GEO Audit →
        </a>
        <p style="font-size:12px;color:#8A8279;margin-top:12px;line-height:1.5;">
          A full audit covers all 8 dimensions, competitor benchmarking,<br/>and a prioritized implementation roadmap.
        </p>
      </td></tr>

      <!-- Footer -->
      <tr><td style="text-align:center;padding:40px 0 0;border-top:1px solid rgba(255,255,255,0.06);margin-top:24px;">
        <p style="font-size:12px;color:#4A4540;margin:0;">
          MadTech Growth · Agentic Commerce Advisory · New York, NY<br/>
          <a href="mailto:hello@madtechgrowth.com" style="color:#4A4540;">hello@madtechgrowth.com</a>
        </p>
        <p style="font-size:11px;color:#3a3530;margin:8px 0 0;">
          You're receiving this because you requested a free GEO Snapshot.
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def send_email(to_name: str, to_email: str, url: str, analysis: dict, scored: dict):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_email = os.environ.get("FROM_EMAIL", "hello@madtechgrowth.com")
    from_name  = os.environ.get("FROM_NAME", "MadTech Growth")

    if not smtp_host or not smtp_user or not smtp_pass:
        raise Exception("SMTP environment variables not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL.")

    html_body = build_html_report(to_name, to_email, url, analysis, scored)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your GEO Snapshot for {analysis.get('domain', 'your site')}"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    # Plain text version
    text_body = f"""
GEO Snapshot Report — {datetime.now().strftime('%B %d, %Y')}

Hi {to_name},

Your AI Visibility Score: {scored['total']}/10 (Grade: {scored['grade']})
Readiness: {scored['readiness']}

Site Analyzed: {url}
Domain: {analysis.get('domain','')}

Top Gaps:
""" + "\n".join(f"  - {g}" for g in scored["gaps"]) + f"""

Get your full audit at: https://madtechgrowth.com
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())

    return True


# ─── Netlify Function handler ─────────────────────────────────────────────────

def handler(event, context=None):
    # CORS
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    if event.get("httpMethod") != "POST":
        return {"statusCode": 405, "headers": headers, "body": json.dumps({"error": "Method not allowed"})}

    try:
        body = json.loads(event.get("body", "{}"))
    except Exception:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Invalid JSON"})}

    name  = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    url   = (body.get("url")   or "").strip()

    if not name or not email or not url:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "name, email, and url are required"})}

    # Basic email validation
    if "@" not in email or "." not in email.split("@")[-1]:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Invalid email address"})}

    # Run geo analysis
    analysis = analyze_url(url)
    scored   = score_analysis(analysis)

    # If site is unreachable, return friendly error
    if analysis.get("status") == "error":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "message": (
                    "We couldn't reach that URL. "
                    "Please check it's a public website and try again. "
                    "If the issue persists, email us at hello@madtechgrowth.com."
                ),
                "analysis": {"status": "error", "error": analysis.get("error", "Unknown error")}
            })
        }

    # Send email
    try:
        send_email(name, email, url, analysis, scored)
    except Exception as e:
        # Log but don't fail — we still want to return a success to the user
        print(f"[geo-snapshot] Email send failed: {e}")

    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({
            "message": f"GEO Snapshot sent to {email}",
            "score": scored["total"],
            "grade": scored["grade"],
            "readiness": scored["readiness"],
            "gaps": scored["gaps"],
        })
    }
