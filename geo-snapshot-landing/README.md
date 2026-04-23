# GEO Snapshot — Lead Magnet Landing Page

## Project Structure

```
geo-snapshot-landing/
├── index.html                          ← Landing page (served at root)
├── netlify.toml                        ← Netlify config
├── netlify/
│   └── functions/
│       └── geo-snapshot.py            ← Python function: analyzes URL + emails report
└── README.md
```

## Deploy to Netlify

1. Push this folder to a GitHub repo
2. Connect the repo to Netlify (netlify.com → New site → Import from Git)
3. Add environment variables in Netlify dashboard → Site Settings → Environment Variables:

```
SMTP_HOST     = smtp.yourprovider.com
SMTP_PORT     = 587
SMTP_USER     = your@email.com
SMTP_PASS     = your_password_or_app_password
FROM_EMAIL    = hello@madtechgrowth.com
FROM_NAME     = MadTech Growth
```

4. Deploy — Netlify auto-detects Python functions in `netlify/functions/`

## Email Provider Options

**Gmail / Google Workspace:**
- Generate an App Password: myaccount.google.com/apppasswords
- SMTP_HOST = smtp.gmail.com, SMTP_PORT = 587

**SendGrid (recommended — free tier: 100/day):**
- SMTP_HOST = smtp.sendgrid.net, SMTP_PORT = 587, SMTP_USER = apikey, SMTP_PASS = your SendGrid API key

**Postmark, Mailgun, AWS SES** — all work the same way

## Local Testing

```bash
# Test the Python function locally
cd netlify/functions
python3 geo-snapshot.py

# Or test with Netlify CLI
npm install -g netlify-cli
netlify functions:serve
```

## What It Does

1. Visitor submits URL via the landing page form
2. Netlify Function fetches and analyzes the URL:
   - JSON-LD / Schema.org detection
   - AI bot accessibility (robots.txt)
   - FAQ content detection
   - Sitemap presence
   - OpenGraph / social meta
   - Heading structure
   - llms.txt presence
   - Content depth
3. Generates a branded HTML report scored across 8 GEO dimensions
4. Emails the report to the submitter

## Custom Domain

Set `Domain = get.madtechgrowth.com` in Netlify → Domain Settings, then add a CNAME pointing to your Netlify site URL.
