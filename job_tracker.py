import email
import imaplib
import re
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime

import google.generativeai as genai
import gspread

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, GEMINI_API_KEY, SHEET_ID

# ──────────────────────────────────────────────────────────────────────────────
# Settings & Initialization
# ──────────────────────────────────────────────────────────────────────────────

# 1️⃣ Gmail IMAP Configuration
IMAP_SERVER = "imap.gmail.com"
MAILBOX = "inbox"

# 2️⃣ Gemini AI Configuration
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash")

# 3️⃣ Google Sheets Configuration
# Note: Ensure your 'credentials.json' is for a service account.
gc = gspread.service_account(filename="credentials.json")
spreadsheet = gc.open_by_key(SHEET_ID)
sheet = spreadsheet.sheet1


# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def build_recent_unseen_query(days=3):
    """Builds a Gmail IMAP query for unseen emails from the last N days."""
    since_date = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    return f'(UNSEEN SINCE {since_date})'


def connect_to_gmail():
    """Connects and logs in to the Gmail IMAP server."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select(MAILBOX)
        return mail
    except Exception as e:
        print(f"❌ Error connecting to Gmail: {e}")
        return None


def get_email_body(msg):
    """Extracts the plaintext body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    else:
        return msg.get_payload(decode=True).decode(errors="ignore")
    return ""


def extract_job_data_with_gemini(email_body):
    """Uses Gemini to extract structured job information from an email body."""
    prompt = f"""
    You are an intelligent assistant reading an email about a job application.
    Extract the following details:
    - Job Title
    - Company Name
    - Application Status (e.g., Submitted, Interview, Offer, Rejected, Other)

    Respond only with the following format:
    Job Title: [The Job Title]
    Company Name: [The Company Name]
    Application Status: [The Application Status]
    """
    try:
        response = model.generate_content(prompt + "\n\nEMAIL BODY:\n" + email_body)
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return ""


def parse_gemini_output(output):
    """Parses the key-value response from Gemini into a dictionary."""
    data = {}
    for line in output.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            # Normalize key: 'Job Title' -> 'job_title'
            normalized_key = key.strip().lower().replace(" ", "_")
            data[normalized_key] = val.strip()
    return data


def find_existing_row_index(company, title, sender):
    """Finds a row index matching Company, Job Title, and Sender."""
    # This is a simple implementation. For very large sheets, consider a more
    # efficient lookup method or a local cache.
    records = sheet.get_all_records()
    for i, record in enumerate(records, start=2):  # start=2 for 1-based index + header
        if (record.get("Company Name", "").lower() == company.lower() and
                record.get("Job Title", "").lower() == title.lower() and
                record.get("Sender Email", "").lower() == sender.lower()):
            return i
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main Logic
# ──────────────────────────────────────────────────────────────────────────────

def scan_and_process_emails(days=3):
    """Scans for unread job-related emails and updates the Google Sheet."""
    mail = connect_to_gmail()
    if not mail:
        return

    query = build_recent_unseen_query(days)
    status, data = mail.search(None, query)

    if status != "OK" or not data[0]:
        print("✅ No new unread job-related emails found.")
        return

    email_ids = data[0].split()
    print(f"📨 Found {len(email_ids)} unread emails to process from the last {days} days.")

    for email_id in email_ids:
        try:
            # Fetch email without marking it as read (using BODY.PEEK)
            res, msg_data = mail.fetch(email_id, "(BODY.PEEK[])")
            if res != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Decode subject and sender
            subject_header = decode_header(msg.get("Subject", "No Subject"))[0]
            subject = subject_header[0].decode() if isinstance(subject_header[0], bytes) else subject_header[0]

            sender = msg.get("From", "")
            sender_email_match = re.search(r"[\w\.-]+@[\w\.-]+", sender)
            sender_email = sender_email_match.group(0) if sender_email_match else ""

            # Basic keyword filter to identify job-related emails
            keywords = ["job", "application", "career", "hiring", "interview", "position", "offer"]
            if not any(keyword in subject.lower() for keyword in keywords):
                continue

            body = get_email_body(msg)
            if not body.strip():
                print(f"⚠️ Skipping email with empty body. Subject: {subject}")
                continue

            print(f"\nProcessing Email | From: {sender_email} | Subject: {subject}")

            # Extract data using Gemini
            gemini_output = extract_job_data_with_gemini(body)
            if not gemini_output:
                continue

            print(f"🔍 Gemini Output:\n{gemini_output}")
            parsed_data = parse_gemini_output(gemini_output)

            company = parsed_data.get("company_name", "")
            title = parsed_data.get("job_title", "")
            app_status = parsed_data.get("application_status", "Other")

            # Get the email's received date
            date_tuple = parsedate_to_datetime(msg.get("Date"))
            received_date = date_tuple.strftime("%Y-%m-%d")

            # Skip if essential information is missing
            if not company or not title:
                print("⚠️ Skipping due to missing Company or Job Title.")
                continue

            # Prepare row for Google Sheet
            row_data = [company, title, received_date, sender_email, app_status]

            existing_row_index = find_existing_row_index(company, title, sender_email)

            if existing_row_index:
                sheet.update(f"A{existing_row_index}:E{existing_row_index}", [row_data])
                print(f"🔄 Updated row {existing_row_index} for {title} at {company}")
            else:
                sheet.append_row(row_data)
                print(f"➕ Added new entry for {title} at {company}")

        except Exception as e:
            print(f"❗️ An error occurred while processing an email: {e}")
        finally:
            # Respect API rate limits
            print("--- Sleeping for 5 seconds ---")
            time.sleep(5)

    mail.logout()


if __name__ == "__main__":
    scan_and_process_emails(days=3)
