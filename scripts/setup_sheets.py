"""
Populate Google Sheets with sample customer and claims data.
Run once after creating the spreadsheet and sharing with the service account.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CUSTOMERS = [
    ["account_id", "name", "phone", "dob", "last4ssn", "email"],
    ["ACC-001", "John Smith", "5551234567", "03/15/1985", "4532", "john.smith@email.com"],
    ["ACC-002", "Sarah Johnson", "5559876543", "07/22/1990", "8821", "sarah.j@email.com"],
    ["ACC-003", "Michael Chen", "5554567890", "11/03/1978", "1156", "m.chen@email.com"],
    ["ACC-004", "Emily Davis", "5553216549", "01/30/1995", "7743", "emily.d@email.com"],
    ["ACC-005", "Robert Wilson", "5558765432", "09/18/1982", "3309", "r.wilson@email.com"],
]

CLAIMS = [
    ["claim_id", "account_id", "status", "type", "date_filed", "last_updated", "documents_needed", "adjuster_name", "notes"],
    ["CLM-1001", "ACC-001", "Under Review", "Auto - Collision", "2026-01-15", "2026-05-28", "Photos of damage, Police report", "Lisa Martinez", "Awaiting documentation from claimant"],
    ["CLM-1002", "ACC-001", "Approved", "Home - Water Damage", "2025-11-20", "2026-01-10", "", "Tom Richards", "Payment issued 01/12/2026"],
    ["CLM-1003", "ACC-002", "Pending Documentation", "Auto - Theft", "2026-03-05", "2026-06-01", "Police report, Vehicle title copy", "Lisa Martinez", "Follow up needed with claimant"],
    ["CLM-1004", "ACC-003", "In Progress", "Home - Fire", "2026-04-10", "2026-05-15", "Fire department report", "James Brown", "Adjuster site visit scheduled"],
    ["CLM-1005", "ACC-004", "Approved", "Health - Surgery", "2026-02-01", "2026-03-20", "", "Sarah Kim", "Payment processed"],
    ["CLM-1006", "ACC-005", "Denied", "Auto - Collision", "2026-01-08", "2026-02-28", "", "Tom Richards", "Claim outside policy coverage period"],
    ["CLM-1007", "ACC-002", "Under Review", "Home - Theft", "2026-05-20", "2026-06-03", "List of stolen items with values, Photos of break-in damage", "James Brown", "Initial review in progress"],
]


def setup():
    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "./service-account-key.json"),
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    spreadsheet = client.open_by_key(sheet_id)

    # Setup customers sheet
    try:
        ws = spreadsheet.worksheet("customers")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="customers", rows=20, cols=10)
    ws.update(range_name="A1", values=CUSTOMERS)
    print(f"Customers sheet populated with {len(CUSTOMERS) - 1} records")

    # Setup claims sheet
    try:
        ws = spreadsheet.worksheet("claims")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="claims", rows=20, cols=10)
    ws.update(range_name="A1", values=CLAIMS)
    print(f"Claims sheet populated with {len(CLAIMS) - 1} records")


if __name__ == "__main__":
    setup()
