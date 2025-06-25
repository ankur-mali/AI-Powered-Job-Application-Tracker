import imaplib
import email
import re
import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime

import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, GEMINI_API_KEY, SHEET_ID

# ──────────────────────────────────────────────────────────────────────────────
# Settings & Initialization
# ──────────────────────────────────────────────────────────────────────────────

# 1️⃣ Gmail → IMAP
IMAP_SERVER = "imap.gmail.com"
MAILBOX     = "inbox"

# 2️⃣ Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash")

# 3️⃣ Google Sheets
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds  = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(creds)
sheet  = client.open_by_key(SHEET_ID).sheet1

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_recent_unseen_query(days=3):
    """Gmail IMAP query for UNSEEN emails since N days ago."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    return f'(UNSEEN SINCE {since})'

def connect_gmail():
    """Connect & login to Gmail IMAP, select mailbox."""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    mail.select(MAILBOX)
    return mail

def get_body(msg):
    """Extract plaintext body from email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    else:
        return msg.get_payload(decode=True).decode(errors="ignore")
    return ""

def parse_email_date(raw_bytes):
    """Read the 'Date' header and return YYYY-MM-DD."""
    msg = email.message_from_bytes(raw_bytes)
    date_str = msg.get("Date", "")
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

def extract_job_data(email_body, subject_fallback=""):
    """Call Gemini to extract job info. Fallback to subject if no title."""
    prompt = f"""
You are reading an email from a job portal or recruiter.

Extract the following information in clear format:
- Job Title otherwise try to get Job Title from subject of mail
- Company Name
- Application Status (Submitted, Interview, Rejected, Offer, Other)
- Date (if mentioned) or get date of email received

Only respond like:
Job Title: ...
Company Name: ...
Application Status: ...
Date: ...
"""
    try:
        resp = model.generate_content(prompt + "\n\nEMAIL:\n" + email_body)
        return resp.text.strip()
    except Exception as e:
        return f"Error: {e}"

def parse_gemini_output(output):
    """Turn Gemini's lines into a dict."""
    data = {}
    for line in output.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip().lower()] = val.strip()
    return data

def find_existing_row(company, title, sender_email):
    """Look for a row matching company+title+sender."""
    records = sheet.get_all_records()
    for idx, row in enumerate(records, start=2):
        if (row.get("Company Name","").lower() == company.lower()
        and row.get("Job Title","").lower()      == title.lower()
        and row.get("Sender Email","").lower()   == sender_email.lower()):
            return idx
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Main Logic
# ──────────────────────────────────────────────────────────────────────────────

def scan_emails(days=3):
    mail   = connect_gmail()
    query  = build_recent_unseen_query(days)
    status, data = mail.search(None, query)

    if status != "OK":
        print("❌ No unread emails.")
        return

    ids = data[0].split()
    print(f"📨 Found {len(ids)} unread emails since {days} days ago.")

    for email_id in ids:
        # 👀 Peek without marking as read
        res, msg_parts = mail.fetch(email_id, "(BODY.PEEK[])")
        if res != "OK":
            continue

        raw_bytes = msg_parts[0][1]
        msg       = email.message_from_bytes(raw_bytes)

        # Subject + Sender
        subj_raw = decode_header(msg.get("Subject",""))[0][0]
        subject  = subj_raw.decode() if isinstance(subj_raw, bytes) else subj_raw
        sender   = msg.get("From","")
        sender_email = re.search(r"[\w\.-]+@[\w\.-]+", sender)
        sender_email = sender_email.group(0) if sender_email else ""

        # Basic job-filter
        if not any(k in subject.lower() for k in
            ["job","application","career","hiring","interview","rejected","position","role"]):
            continue

        body   = get_body(msg)
        if not body.strip():
            print(f"⚠️ Empty body: {subject}")
            continue

        print(f"\n📤 From: {sender_email} | Subject: {subject}")

        # 🧠 Gemini extraction
        gem_out = extract_job_data(body)
        print(f"🔍 Gemini:\n{gem_out}")

        parsed  = parse_gemini_output(gem_out)
        company = parsed.get("company name","")
        title   = parsed.get("job title","")
        status_ = parsed.get("application status","")
        date_   = parsed.get("date","")

        # If Gemini didn't give date, use real received date
        if not date_:
            date_ = parse_email_date(raw_bytes)

        # Must have at least company & title
        if not company or not title:
            print("⚠️ Skipping: missing company/title")
            continue

        row = [company, title, date_, sender_email, status_]
        existing = find_existing_row(company, title, sender_email)

        if existing:
            # Update entire row A–E
            sheet.update(f"A{existing}:E{existing}", [row])
            print(f"🔄 Updated row {existing}: {title} @ {company}")
        else:
            sheet.append_row(row)
            print(f"➕ Added: {title} @ {company}")

if __name__ == "__main__":
    scan_emails(days=3)
