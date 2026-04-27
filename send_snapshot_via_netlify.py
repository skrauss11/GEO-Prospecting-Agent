#!/usr/bin/env python3
"""
Send GEO Snapshot email via Netlify Function + Resend.

Usage:
    python3 send_snapshot_via_netlify.py --email john@brand.com --name "John Doe" --brand "BrandCo" --pdf ./output/snapshot.pdf

Requires NETLIFY_FUNCTION_URL and RESEND_API_KEY in .env
"""

import argparse
import json
import os
import requests
from pathlib import Path
import base64

def send_snapshot(prospect_email, prospect_name, brand_name, pdf_path, snapshot_score=None):
    netlify_url = os.getenv('NETLIFY_FUNCTION_URL')
    if not netlify_url:
        raise ValueError("NETLIFY_FUNCTION_URL not set in environment")

    pdf_bytes = Path(pdf_path).read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

    payload = {
        "prospect_email": prospect_email,
        "prospect_name": prospect_name,
        "brand_name": brand_name,
        "pdf_base64": pdf_b64,
        "snapshot_score": snapshot_score
    }

    response = requests.post(
        netlify_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    if response.status_code == 200:
        print(f"✓ Snapshot email dispatched to {prospect_email}")
        return response.json()
    else:
        print(f"✗ Failed: {response.status_code} — {response.text}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--brand', required=True)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--score')
    args = parser.parse_args()

    send_snapshot(args.email, args.name, args.brand, args.pdf, args.score)
