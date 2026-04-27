#!/usr/bin/env python3
"""
Resend email sender — zero external dependencies (uses stdlib urllib).

Usage:
    python resend_mailer.py --to user@example.com --subject "Test" --html "<p>Hello</p>"
    python resend_mailer.py --to user@example.com --subject "Test" --text "Hello plain"
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Load from Hermes .env (shared with the web-research-agent)
HERMES_ENV = Path.home() / '.hermes' / '.env'


def load_env() -> dict[str, str]:
    """Parse key=value pairs from .env, ignoring comments."""
    env: dict[str, str] = {}
    if HERMES_ENV.exists():
        for line in HERMES_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def send_email(to_addr: str, subject: str, html_content: str = None,
               text_content: str = None, from_override: tuple[str, str] = None) -> dict:
    """
    Send an email via Resend API.

    Args:
        to_addr: Recipient email address
        subject: Email subject line
        html_content: HTML body (preferred)
        text_content: Plain-text fallback (optional but recommended)
        from_override: Optional (email, name) tuple to override .env FROM settings

    Returns:
        Resend API response dict
    """
    env = load_env()
    api_key = env.get('RESEND_API_KEY')
    from_email = env.get('RESEND_FROM_EMAIL', 'noreply@resendmail.com')
    from_name = env.get('RESEND_FROM_NAME', 'MadTech Growth')

    if from_override:
        from_email, from_name = from_override

    if not api_key:
        raise RuntimeError('RESEND_API_KEY not found in ~/.hermes/.env')

    # Build payload
    payload = {
        "from": f"{from_name} <{from_email}>",
        "to": [to_addr],
        "subject": subject,
    }
    if html_content:
        payload["html"] = html_content
    if text_content:
        payload["text"] = text_content

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Hermes-Resend-Mailer/1.0'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode('utf-8')
            result = json.loads(response_body)
            return {"success": True, "id": result.get('id'), "data": result}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return {
            "success": False,
            "error": f"HTTP {e.code}",
            "details": error_body
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Send email via Resend')
    parser.add_argument('--to', required=True, help='Recipient email')
    parser.add_argument('--subject', required=True, help='Email subject')
    parser.add_argument('--html', help='HTML body')
    parser.add_argument('--text', help='Text body')
    parser.add_argument('--from-email', help='Override sender email')
    parser.add_argument('--from-name', help='Override sender name')
    args = parser.parse_args()

    from_override = None
    if args.from_email:
        from_override = (args.from_email, args.from_name or 'MadTech Growth')

    result = send_email(
        to_addr=args.to,
        subject=args.subject,
        html_content=args.html,
        text_content=args.text,
        from_override=from_override
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
