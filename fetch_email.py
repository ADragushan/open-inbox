#!/usr/bin/env python3
"""
Fetch emails from Gmail and create memos in Memos.

First run will open a browser for OAuth authorization.
Subsequent runs use the saved token.

Usage:
    python3 fetch_email.py           # Fetch unread emails, create memos
    python3 fetch_email.py --auth    # Just do the OAuth flow, don't fetch
"""

import os
import sys
import json
import base64
import requests
from pathlib import Path
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes we requested
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
]

# Paths
SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials' / 'gmail_credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'credentials' / 'token.json'

# Memos config from environment
MEMOS_API_TOKEN = os.environ.get('MEMOS_API_TOKEN')
MEMOS_BASE_URL = os.environ.get('MEMOS_BASE_URL', 'http://localhost:5230')


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None

    # Load existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"Error: Credentials file not found at {CREDENTIALS_FILE}")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")

    return build('gmail', 'v1', credentials=creds)


def get_unread_emails(service, max_results=10):
    """Fetch unread emails from inbox."""
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX', 'UNREAD'],
        maxResults=max_results
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}

        # Get body
        body = ''
        if 'parts' in msg_data['payload']:
            for part in msg_data['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8', errors='ignore')
                    break
        elif 'body' in msg_data['payload'] and 'data' in msg_data['payload']['body']:
            body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8', errors='ignore')

        emails.append({
            'id': msg['id'],
            'subject': headers.get('Subject', '(no subject)'),
            'from': headers.get('From', '(unknown sender)'),
            'date': headers.get('Date', ''),
            'body': body[:5000],  # Truncate very long bodies
        })

    return emails


def mark_as_read(service, msg_id):
    """Remove UNREAD label from a message."""
    service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


def create_memo(content):
    """Create a memo in Memos via API."""
    if not MEMOS_API_TOKEN:
        print("Error: MEMOS_API_TOKEN not set")
        return False

    response = requests.post(
        f"{MEMOS_BASE_URL}/api/v1/memos",
        headers={
            'Authorization': f'Bearer {MEMOS_API_TOKEN}',
            'Content-Type': 'application/json',
        },
        json={'content': content}
    )

    if response.status_code == 200:
        return True
    else:
        print(f"Error creating memo: {response.status_code} {response.text}")
        return False


def email_to_memo_content(email):
    """Format an email as memo content."""
    content = f"""#inbox #email

**From:** {email['from']}
**Subject:** {email['subject']}
**Date:** {email['date']}

---

{email['body']}
"""
    return content


def main():
    # Auth-only mode
    if '--auth' in sys.argv:
        print("Running OAuth flow...")
        service = get_gmail_service()
        print("Authentication successful!")
        return

    # Check Memos is configured
    if not MEMOS_API_TOKEN:
        print("Error: MEMOS_API_TOKEN environment variable not set")
        print("Run: source ~/.zshrc")
        sys.exit(1)

    print("Connecting to Gmail...")
    service = get_gmail_service()

    print("Fetching unread emails...")
    emails = get_unread_emails(service)

    if not emails:
        print("No unread emails.")
        return

    print(f"Found {len(emails)} unread email(s)")

    for email in emails:
        print(f"  Processing: {email['subject'][:50]}...")

        content = email_to_memo_content(email)
        if create_memo(content):
            mark_as_read(service, email['id'])
            print(f"    ✓ Created memo, marked as read")
        else:
            print(f"    ✗ Failed to create memo")

    print("Done!")


if __name__ == '__main__':
    main()
