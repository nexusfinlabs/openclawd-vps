import os
import sys
import argparse
import imaplib
import email
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import pytz
import logging
from icalendar import Calendar, Event, vCalAddress, vText

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env(path='.env'):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"\'')
                except ValueError:
                    continue

# Try to load env
load_env('/home/albi_agent/openclawd_stack/.env')
load_env()

def get_google_calendar_service():
    """Builds and returns the Google Calendar API service using a Service Account."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    
    # Normally the credentials are at ~/.secrets/google/credentials.json or similar
    # Let's check a few common locations
    possible_paths = [
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
        "/home/albi_agent/.secrets/google/credentials.json",
        "./credentials.json"
    ]
    
    creds_path = None
    for path in possible_paths:
        if path and os.path.exists(path):
            creds_path = path
            break
            
    if not creds_path:
        logger.error("Could not find Google Service Account credentials.json")
        sys.exit(1)
        
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service

def parse_ics_and_add_to_calendar(ics_path, calendar_id="alebronlobo81@gmail.com"):
    """Reads an ICS file and inserts it into the specified Google Calendar."""
    if not os.path.exists(ics_path):
        logger.error(f"ICS file not found: {ics_path}")
        return False
        
    logger.info(f"Parsing ICS file: {ics_path}...")
    try:
        with open(ics_path, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            
        service = get_google_calendar_service()
        
        events_added = 0
        for component in cal.walk():
            if component.name == "VEVENT":
                summary = str(component.get('summary', 'Sin Título'))
                description = str(component.get('description', ''))
                location = str(component.get('location', ''))
                
                # Handling DTSTART and DTEND
                start = component.get('dtstart').dt
                end = component.get('dtend')
                end = end.dt if end else start + timedelta(hours=1)
                
                # Format for Google Calendar API
                event_body = {
                    'summary': summary,
                    'location': location,
                    'description': description,
                }
                
                if isinstance(start, datetime):
                    event_body['start'] = {'dateTime': start.isoformat(), 'timeZone': 'UTC'}
                    event_body['end'] = {'dateTime': end.isoformat(), 'timeZone': 'UTC'}
                else: # Date only (All day event)
                    event_body['start'] = {'date': start.isoformat()}
                    event_body['end'] = {'date': end.isoformat()}
                    
                logger.info(f"Adding event to Calendar: {summary}")
                try:
                    event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
                    logger.info(f"✅ Event created successfully: {event.get('htmlLink')}")
                    events_added += 1
                except Exception as e:
                    logger.error(f"Failed to insert event into Google Calendar: {e}")
                    
        return events_added > 0
    except Exception as e:
        logger.error(f"Error parsing ICS: {e}")
        return False

def search_inbox_and_add(query_term):
    """Searches predefined IMAP inboxes for an email containing an ICS file, and adds it to Calendar."""
    import quopri
    
    accounts = [
        {
            "email": "alebronlobo81@gmail.com", 
            "password": os.environ.get("GMAIL_APP_PASSWORD_ALEBRON"),
            "imap_server": "imap.gmail.com"
        },
        {
            "email": "dealflow@nexusfinlabs.com", 
            "password": os.environ.get("EMAIL_PASSWORD", ""),
            "imap_server": "imap.ionos.es"
        }
    ]
    
    found_ics = False
    
    for acc in accounts:
        if not acc["password"]:
            logger.warning(f"Skipping {acc['email']} - No Password configured")
            continue
            
        logger.info(f"Connecting to IMAP {acc['imap_server']} for {acc['email']}...")
        try:
            mail = imaplib.IMAP4_SSL(acc["imap_server"])
            mail.login(acc["email"], acc["password"])
            mail.select("inbox")
            
            # Search by generic term (FROM, SUBJECT, or BODY)
            logger.info(f"Searching for '{query_term}'...")
            _, message_numbers_raw = mail.search(None, f'(OR OR FROM "{query_term}" SUBJECT "{query_term}" BODY "{query_term}")')
            
            # Just take the last 5 matching emails (most recent)
            message_numbers = message_numbers_raw[0].split()[-5:]
            
            for num in reversed(message_numbers):
                _, data = mail.fetch(num, '(RFC822)')
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = msg["subject"]
                # Decode subject
                from email.header import decode_header
                subject = "".join([str(t[0], t[1] or 'utf-8') if isinstance(t[0], bytes) else t[0] for t in decode_header(subject)])
                
                logger.info(f"Checking email: {subject[:50]}...")
                
                for part in msg.walk():
                    content_type = part.get_content_type()
                    disposition = str(part.get("Content-Disposition"))
                    
                    if "text/calendar" in content_type or "attachment" in disposition and part.get_filename() and part.get_filename().endswith('.ics'):
                        logger.info(f"Found Calendar attachment in email from {msg['from']}!")
                        ics_data = part.get_payload(decode=True)
                        
                        ics_path = f"/tmp/extracted_event_{num.decode()}.ics"
                        with open(ics_path, "wb") as f:
                            f.write(ics_data)
                            
                        # Add to calendar
                        success = parse_ics_and_add_to_calendar(ics_path)
                        if success:
                            found_ics = True
                            logger.info(f"✅ Successfully extracted and added event from email: {subject}")
                
            mail.close()
            mail.logout()
            
            if found_ics:
                return # Stop searching other inboxes if we found it
                
        except Exception as e:
            logger.error(f"Error checking {acc['email']}: {e}")
            
    if not found_ics:
        logger.warning(f"No ICS events found matching '{query_term}'.")

def generate_and_send_ics(title, start_datetime_iso, to_emails_str):
    """Generates an ICS file from params and sends it via SMTP."""
    start_dt = datetime.fromisoformat(start_datetime_iso.replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(minutes=30)
    
    cal = Calendar()
    cal.add('prodid', '-//OpenClaw Agent//nexusfinlabs.com//')
    cal.add('version', '2.0')
    
    event = Event()
    event.add('summary', title)
    event.add('dtstart', start_dt)
    event.add('dtend', end_dt)
    event.add('dtstamp', datetime.now(pytz.utc))
    
    organizer = vCalAddress('MAILTO:alebronlobo81@gmail.com')
    organizer.params['cn'] = vText('Alberto Lebron')
    event['organizer'] = organizer
    
    to_emails = [e.strip() for e in to_emails_str.split(',') if e.strip()]
    for em in to_emails:
        attendee = vCalAddress(f'MAILTO:{em}')
        attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
        attendee.params['PARTSTAT'] = vText('NEEDS-ACTION')
        attendee.params['RSVP'] = vText('TRUE')
        event.add('attendee', attendee, encode=0)
        
    cal.add_component(event)
    
    ics_path = "/tmp/generated_event.ics"
    with open(ics_path, 'wb') as f:
        f.write(cal.to_ical())
        
    logger.info(f"Generated ICS at {ics_path}")
    
    # Send Email
    sender_email = "dealflow@nexusfinlabs.com"
    email_password = os.environ.get("EMAIL_PASSWORD", "")
    smtp_server = "smtp.ionos.es"
    
    if not email_password:
        logger.error("Missing EMAIL_PASSWORD. Cannot send email.")
        return
        
    for recipient in to_emails:
        msg = EmailMessage()
        msg['Subject'] = f"Invitación: {title}"
        msg['From'] = f"Alberto Lebron <{sender_email}>"
        msg['To'] = recipient
        msg['Bcc'] = "dealflow@nexusfinlabs.com"
        msg.set_content(f"Hola,\n\nTe adjunto la invitación para '{title}' programado para {start_dt.strftime('%d/%m/%Y %H:%M')}.\n\nSaludos,\nAlberto L. - Tech Advisor")
        
        with open(ics_path, 'rb') as f:
            ics_data = f.read()
        msg.add_attachment(ics_data, maintype='text', subtype='calendar', filename='invite.ics')
        
        try:
            with smtplib.SMTP_SSL(smtp_server, 465) as smtp:
                smtp.login(sender_email, email_password)
                smtp.send_message(msg)
            logger.info(f"✅ Invite sent to {recipient}")
        except Exception as e:
            logger.error(f"Failed to send invite to {recipient}: {e}")

    # --- NEW: Also add to YOUR Google Calendar so it shows up ---
    try:
        service = get_google_calendar_service()
        # NOTE: Service Accounts on personal calendars CANNOT invite attendees via API 
        # (reason: forbiddenForServiceAccounts). 
        # We handle invitations via the ICS file sent through SMTP above.
        event_body = {
            'summary': title,
            'description': f"Invitación enviada a: {to_emails_str}\n\nGenerado por OpenClaw",
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'}
        }
        event = service.events().insert(calendarId="alebronlobo81@gmail.com", body=event_body).execute()
        logger.info(f"✅ Event created in your Google Calendar (without API attendees): {event.get('htmlLink')}")
    except Exception as e:
        logger.error(f"Failed to insert created event into your Google Calendar: {e}")

def check_attendee_status(query_term):
    """Checks the status of attendees for events matching the query."""
    service = get_google_calendar_service()
    now = datetime.utcnow().isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId="alebronlobo81@gmail.com", 
        timeMin=now,
        maxResults=10, 
        singleEvents=True,
        orderBy='startTime',
        q=query_term
    ).execute()
    
    events = events_result.get('items', [])
    if not events:
        print(f"No se encontraron eventos futuros con el término '{query_term}'.")
        return

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f"\n📅 Evento: {event['summary']} ({start})")
        attendees = event.get('attendees', [])
        if not attendees:
            print("  - No hay invitados externos.")
            continue
            
        for attendee in attendees:
            status = attendee.get('responseStatus', 'needsAction')
            status_map = {
                'accepted': '✅ Aceptado',
                'declined': '❌ Rechazado',
                'tentative': '❓ Provisional',
                'needsAction': '⏳ Pendiente'
            }
            print(f"  - {attendee.get('email')}: {status_map.get(status, status)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Calendar ICS Manager")
    parser.add_argument("--action", required=True, choices=["add_file", "fetch_inbox", "create", "status"], help="Action to perform")
    parser.add_argument("--file", help="Path to ICS file (for add_file)")
    parser.add_argument("--query", help="Search string for emails or event status")
    parser.add_argument("--title", help="Event title (for create)")
    parser.add_argument("--datetime", help="Start datetime ISO format (for create)")
    parser.add_argument("--emails", help="Comma-separated emails to send to (for create)")
    
    args = parser.parse_args()
    
    if args.action == "add_file":
        if not args.file:
            logger.error("--file is required for add_file")
            sys.exit(1)
        parse_ics_and_add_to_calendar(args.file)
        
    elif args.action == "fetch_inbox":
        if not args.query:
            logger.error("--query is required for fetch_inbox")
            sys.exit(1)
        search_inbox_and_add(args.query)
        
    elif args.action == "create":
        if not (args.title and args.datetime and args.emails):
            logger.error("--title, --datetime, and --emails are required for create")
            sys.exit(1)
        generate_and_send_ics(args.title, args.datetime, args.emails)
        
    elif args.action == "status":
        if not args.query:
            logger.error("--query is required for status")
            sys.exit(1)
        check_attendee_status(args.query)
