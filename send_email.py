#!/usr/bin/env python3
"""
Send an email from aarond@wondermill.com via Gmail API.

Usage:
    python3 send_email.py --to "recipient@example.com" --subject "Subject" --body "Body text"
"""

import argparse
import base64
import sys
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
]

SCRIPT_DIR = Path(__file__).parent
TOKEN_FILE = SCRIPT_DIR / 'credentials' / 'token.json'


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    if not TOKEN_FILE.exists():
        print(f"Error: Token file not found at {TOKEN_FILE}")
        print("Run: python3 fetch_email.py --auth")
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Error: Token expired or invalid. Run: python3 fetch_email.py --auth")
            sys.exit(1)

    return build('gmail', 'v1', credentials=creds)


def send_email(to: str, subject: str, body: str):
    """Send an email."""
    service = get_gmail_service()

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    sent = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    print(f"Email sent. Message ID: {sent['id']}")
    return sent


def main():
    parser = argparse.ArgumentParser(description='Send email from aarond@wondermill.com')
    parser.add_argument('--to', required=True, help='Recipient email address')
    parser.add_argument('--subject', required=True, help='Email subject')
    parser.add_argument('--body', required=True, help='Email body text')

    args = parser.parse_args()

    send_email(args.to, args.subject, args.body)


if __name__ == '__main__':
    main()
