#!/usr/bin/env python3
"""
Create Google Calendar events.

First run will open a browser for OAuth authorization if token doesn't have calendar scope.

Usage:
    python3 create_calendar_event.py --title "Meeting" --start "2026-02-10 14:00" --end "2026-02-10 15:00"
    python3 create_calendar_event.py --title "All day event" --date "2026-02-10"
    python3 create_calendar_event.py --auth    # Just do the OAuth flow
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes - includes both Gmail and Calendar
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
]

# Paths
SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials' / 'gmail_credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'credentials' / 'token.json'


def get_calendar_service():
    """Authenticate and return Calendar API service."""
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

    return build('calendar', 'v3', credentials=creds)


def create_event(service, title, start, end, description=None, location=None, reminder_minutes=30):
    """Create a calendar event."""
    event = {
        'summary': title,
        'start': start,
        'end': end,
    }

    if description:
        event['description'] = description

    if location:
        event['location'] = location

    if reminder_minutes:
        event['reminders'] = {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': reminder_minutes},
            ],
        }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event


def parse_datetime(dt_str):
    """Parse a datetime string into a Google Calendar format."""
    # Try various formats
    formats = [
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M',
        '%Y-%m-%dT%H:%M:%S',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return {
                'dateTime': dt.isoformat(),
                'timeZone': 'America/Phoenix',  # Default timezone
            }
        except ValueError:
            continue

    raise ValueError(f"Could not parse datetime: {dt_str}")


def parse_date(date_str):
    """Parse a date string for all-day events."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return {'date': dt.strftime('%Y-%m-%d')}


def main():
    parser = argparse.ArgumentParser(description='Create Google Calendar events')
    parser.add_argument('--auth', action='store_true', help='Just run OAuth flow')
    parser.add_argument('--title', '-t', help='Event title')
    parser.add_argument('--start', '-s', help='Start datetime (YYYY-MM-DD HH:MM)')
    parser.add_argument('--end', '-e', help='End datetime (YYYY-MM-DD HH:MM)')
    parser.add_argument('--date', '-d', help='Date for all-day event (YYYY-MM-DD)')
    parser.add_argument('--description', help='Event description')
    parser.add_argument('--location', '-l', help='Event location')
    parser.add_argument('--reminder', '-r', type=int, default=30, help='Reminder minutes before (default: 30)')
    parser.add_argument('--timezone', '-tz', default='America/Phoenix', help='Timezone (default: America/Phoenix)')

    args = parser.parse_args()

    # Auth-only mode
    if args.auth:
        print("Running OAuth flow...")
        service = get_calendar_service()
        print("Authentication successful!")
        return

    # Validate required args
    if not args.title:
        parser.error("--title is required")

    if not args.date and not args.start:
        parser.error("Either --date (all-day) or --start/--end (timed) is required")

    print("Connecting to Google Calendar...")
    service = get_calendar_service()

    # Build start/end
    if args.date:
        # All-day event
        start = parse_date(args.date)
        # All-day events need end date to be the next day
        end_dt = datetime.strptime(args.date, '%Y-%m-%d') + timedelta(days=1)
        end = {'date': end_dt.strftime('%Y-%m-%d')}
    else:
        # Timed event
        start = parse_datetime(args.start)
        start['timeZone'] = args.timezone

        if args.end:
            end = parse_datetime(args.end)
        else:
            # Default to 1 hour duration
            start_dt = datetime.strptime(args.start.replace('T', ' ').split('.')[0], '%Y-%m-%d %H:%M')
            end_dt = start_dt + timedelta(hours=1)
            end = {
                'dateTime': end_dt.isoformat(),
                'timeZone': args.timezone,
            }
        end['timeZone'] = args.timezone

    event = create_event(
        service,
        title=args.title,
        start=start,
        end=end,
        description=args.description,
        location=args.location,
        reminder_minutes=args.reminder,
    )

    print(f"✓ Created event: {event['summary']}")
    print(f"  Link: {event.get('htmlLink', 'N/A')}")


if __name__ == '__main__':
    main()
