# Agent Performance Report Automation

Automatically fetches the daily Ytel agent performance report from email, processes it into a formatted Excel file, and sends it to a list of recipients every morning at 6am.

---

## How It Works

1. **Email Fetcher** — connects to Rackspace inbox via IMAP, finds today's "Job Confirmation" email from `no-reply@ytel.com`
2. **Ytel Downloader** — uses Selenium (headless Chrome) to log into `app.ytel.com` and download the CSV report via the link in the email
3. **Report Generator** — processes the CSV, calculates percentages (Talk, Pause, Wait, Dispo, Conversion), applies color-coded formatting, and outputs a formatted Excel file
4. **Email Sender** — sends the Excel report to all configured recipients via Rackspace SMTP

---

## Project Structure

```
├── email_fetcher.py       # Main pipeline: fetch email → download CSV → run report → send
├── performancereport.py   # Processes CSV and generates formatted Excel report
├── ytel_downloader.py     # Selenium browser automation to download report from Ytel
├── setup_scheduler.sh     # Linux cron job setup (runs daily at 6am)
├── .env.example           # Template for credentials — copy to .env and fill in
├── .gitignore             # Excludes .env, logs, and output files from git
└── README.md
```

---

## Setup

### 1. Install Dependencies

```bash
pip install pandas openpyxl selenium webdriver-manager python-dotenv requests
```

### 2. Configure Credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
EMAIL_ADDRESS=your_email@example.com
EMAIL_PASSWORD=your_email_password
YTEL_EMAIL=your_ytel_email@example.com
YTEL_PASSWORD=your_ytel_password
REPORT_RECIPIENTS=recipient1@example.com,recipient2@example.com
```

### 3. Run Manually

```bash
python email_fetcher.py
```

Or to just regenerate the report from an existing CSV:

```bash
python performancereport.py
```

### 4. Schedule Daily (Linux)

Run the setup script once to install the cron job:

```bash
chmod +x setup_scheduler.sh
bash setup_scheduler.sh
```

This registers a cron job to run `email_fetcher.py` every day at **6:00 AM**.

Verify it was added:

```bash
crontab -l
```

---

## Report Output

The generated Excel file (`Formatted_Agent_Report.xlsx`) includes:

| Column | Description |
|---|---|
| Agent ID | Ytel agent ID |
| Agent Name | Full name |
| Team | User group |
| Total Calls | Number of calls |
| Talk % | Talk time as % of total time |
| Pause % | Pause time as % of total time |
| Wait % | Wait time as % of total time |
| Dispo Avg % | Disposition average as % of total time |
| Dead Avg % | Dead air average as % of total time |
| Cust Avg % | Customer average as % of total time |
| Sales (AMNVM) | Answering machine, no voicemail |
| AMLVM | Answering machine, left voicemail |
| AMNAVM | Answering machine, no available voicemail |
| Callbacks | Callback dispositions |
| Not Interested | NI dispositions |
| DNC | Do not call dispositions |
| Conversion % | Sales / Total Calls |

**Color coding:**
- 🔴 Red row — Conversion % below 10%
- ⬜ White row — Conversion % at or above 10%
- 🔵 Blue row — Totals (bottom row)

---

## Requirements

- Python 3.8+
- Google Chrome installed
- Rackspace email account
- Ytel account access
