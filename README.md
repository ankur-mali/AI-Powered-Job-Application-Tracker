📬 AI-Powered Job Application Tracker
-------------------------------------

Automatically extract job application details from your Gmail inbox using **Gemini AI** and log them into **Google Sheets** for seamless tracking.

* * * * *

### 📌 Features

-   ✅ Fetches **unread** job-related emails from the last 7 days using Gmail IMAP

-   🤖 Uses **Google Gemini (LLM)** to extract:

    -   Job Title

    -   Company Name

    -   Application Status (e.g., Submitted, Interview, Rejected)

    -   Date (from content or header)

-   📄 Logs each unique application into **Google Sheets**

-   🔁 Prevents duplicate entries & updates status if already present

-   📊 Clean structure: `Company | Job Title | Date | Sender Email | Application Status`

-   🟥 Automatically highlights "Rejected" rows in red (using Google Sheet conditional formatting)

* * * * *

### 📂 Tech Stack

| Tool/Library | Purpose |
| --- | --- |
| Python 3.10+ | Scripting & Automation |
| IMAP + `email` | Gmail email fetching & parsing |
| Google Gemini API | LLM-based text extraction |
| `gspread` + Google Sheets API | Spreadsheet handling |
| `oauth2client` | Google Sheets API Auth |
| Regex | Email content filtering |

* * * * *

### 📁 Setup Instructions

1.  **Clone the repository**

    bash

    CopyEdit
   

    `git clone https://github.com/ankur-mali/AI-Powered-Job-Application-Tracker.git
    cd AI-Powered-Job-Application-Tracker`

3.  **Install requirements**

    bash

    CopyEdit

    `pip install -r requirements.txt`

4.  **Create `.env` or `config.py`**\
    Add your credentials:

    python

    CopyEdit

    `GMAIL_ADDRESS = "your.email@gmail.com"
    GMAIL_APP_PASSWORD = "your-app-password"
    GEMINI_API_KEY = "your-gemini-api-key"
    SHEET_ID = "your-google-sheet-id"`

5.  **Add your Google Service Account JSON file**

    -   Save it as `credentials.json` in the root directory.

    -   Share your Google Sheet with the service account email (`xyz@project.iam.gserviceaccount.com`).

6.  **Run the script**

    bash

    CopyEdit

    `python job_tracker.py`

* * * * *

### 🖼️ Example Output

plaintext

CopyEdit

`📤 Reading from: jobs-noreply@linkedin.com | Subject: Your application was submitted
🔍 Gemini response:
Job Title: Full Stack Intern
Company Name: Example Inc.
Application Status: Submitted
Date: June 18, 2025
➕ Added new job entry: Full Stack Intern at Example Inc.`


### 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.

* * * * *

### 💡 Inspiration

Built to help job seekers like me track applications easily and keep inboxes clean --- while using the power of AI to reduce manual work.
