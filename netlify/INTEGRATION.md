# Netlify + Resend Integration — Automated GEO Snapshot Delivery

## Overview

This integration allows you to send GEO Snapshot PDFs to prospects automatically via email, without manual intervention. The flow:

```
Snapshot PDF Generated
        ↓
  Call Netlify Function
        ↓
  Resend API delivers email
        ↓
  Log sent → Discord notification
```

---

## Files

```
netlify/
├── functions/
│   ├── package.json          ← Resend dependency
│   └── send-snapshot.js      ← Main email function
└── netlify.toml              ← Netlify build config

~/Desktop/Claude Code Test/web-research-agent/
├── send_snapshot_via_netlify.py  ← Python wrapper to call function
└── (to be integrated into) geo_snapshot_generator.py
```

---

## Setup Steps

### 1. Get Resend API Key

```bash
# Sign up at https://resend.com (free tier: 3,000 emails/month)
# Create API key in dashboard → API Keys → Create Key
```

Add to your `.env`:
```bash
RESEND_API_KEY=re_XXXXXXXXXXXXXXXXXXXX
```

### 2. Deploy Netlify Function

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Initialize site in project folder
cd ~/Desktop/Claude\ Code\ Test/web-research-agent/netlify
netlify init
# Follow prompts — create new site, link to existing repo

# Test locally
netlify functions:log  # watch logs
netlify dev             # runs functions locally on :8888
```

### 3. Configure Environment on Netlify

In Netlify dashboard → Site Settings → Build & Deploy → Environment:

```
RESEND_API_KEY = re_XXXXXXXXXXXXXXXXXXXX
```

### 4. Set NETLIFY_FUNCTION_URL

Once deployed, your function URL will be:
```
https://your-site-name.netlify.app/.netlify/functions/send-snapshot
```

Add to `.env`:
```bash
NETLIFY_FUNCTION_URL=https://your-site-name.netlify.app/.netlify/functions/send-snapshot
```

---

## How It Works

### Netlify Function (`send-snapshot.js`)

Receives a POST request with:
- `prospect_email` — recipient address
- `prospect_name` — first name for personalization
- `brand_name` — company name
- `pdf_base64` — the PDF file as base64 string (or S3 URL alternative)
- `snapshot_score` — overall 1–10 score

The function:
1. Decodes PDF
2. Constructs HTML email using MadTech Growth brand template
3. Attaches PDF
4. Sends via Resend API
5. Returns success/failure

### Python Wrapper (`send_snapshot_via_netlify.py`)

Command-line tool for ad-hoc sends:
```bash
python3 send_snapshot_via_netlify.py \
  --email john@brand.com \
  --name "John" \
  --brand "BrandCo" \
  --pdf ./output/BrandCo_Snapshot.pdf \
  --score 4.2
```

---

## Integration Into Snapshot Generator

Modify `geo_snapshot_generator.py` (or your snapshot script) to call this after PDF generation:

```python
import subprocess

def dispatch_snapshot_email(prospect, pdf_path, score):
    cmd = [
        'python3', 'send_snapshot_via_netlify.py',
        '--email', prospect['email'],
        '--name', prospect['first_name'],
        '--brand', prospect['company'],
        '--pdf', pdf_path,
        '--score', str(score)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ Email failed: {result.stderr}")
    else:
        print(f"✓ Email sent to {prospect['email']}")
```

Log outcome to:
`~/Desktop/ScottOS/Cron Outputs/snapshot_deliveries_YYYY-MM-DD.csv`

Columns: `timestamp, brand, email, success, error_message`

---

## Fallback Strategy (Resend Quota Exceeded)

If Resend hits free tier limit (3K emails/month):

1. **Switch to local SMTP** (existing Resend SMTP config probably works)
2. **Priority queue:** Only send to top-tier prospects (>$200M revenue)
3. **Manual override:** Save email draft to `~/Desktop/ScottOS/Drafts/` for manual send

---

## Next Steps

- [ ] Create Resend account + get API key
- [ ] Deploy Netlify function (test locally first with `netlify dev`)
- [ ] Set environment variables (RESEND_API_KEY)
- [ ] Integrate `send_snapshot_via_netlify.py` into snapshot generator
- [ ] Test with a single prospect email
- [ ] Add delivery logging (CSV append) to track sent/delivered/bounced
- [ ] Add bounce handling webhook (Resend sends events → parse and flag invalid emails)

---

## Cost

- Netlify Functions: Free tier includes 125K requests/month (more than enough)
- Resend: Free tier 3,000 emails/month. Paid from $20/mo for 50K.

You're looking at ~$20–40/month total to automate full pipeline.
