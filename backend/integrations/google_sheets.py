import logging
import gspread
from google.oauth2.service_account import Credentials
from backend.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheets_client():
    creds = Credentials.from_service_account_file(
        settings.google_service_account_key_path, scopes=SCOPES
    )
    return gspread.authorize(creds)


def normalize_phone(phone: str) -> str:
    """Strip all non-digit characters and leading country code."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return digits


def lookup_customer_by_phone(phone: str) -> dict | None:
    try:
        client = get_sheets_client()
        sheet = client.open_by_key(settings.google_sheet_id).worksheet("customers")
        records = sheet.get_all_records()

        normalized = normalize_phone(phone)
        logger.info(f"[SHEETS] Lookup phone: '{normalized}'")

        # Exact match first
        for row in records:
            row_phone = normalize_phone(str(row["phone"]))
            if row_phone == normalized:
                logger.info(f"[SHEETS] Match: {row['name']} ({row['account_id']})")
                return row

        # Suffix match: handle cases where caller gives partial number
        # e.g. caller says "5551234567" but STT captures "551234567"
        if len(normalized) >= 8:
            for row in records:
                row_phone = normalize_phone(str(row["phone"]))
                if row_phone.endswith(normalized) or normalized.endswith(row_phone):
                    logger.info(f"[SHEETS] Partial match: {row['name']} ({row['account_id']})")
                    return row

        logger.info(f"[SHEETS] No match for '{normalized}'")
        return None

    except Exception as e:
        logger.error(f"[SHEETS] Lookup error: {str(e)}")
        raise


def verify_customer_identity(customer: dict, verification_value: str) -> bool:
    normalized = verification_value.strip().replace("/", "").replace("-", "")
    dob_normalized = customer.get("dob", "").replace("/", "").replace("-", "")
    last4 = str(customer.get("last4ssn", ""))

    match = normalized == dob_normalized or normalized == last4
    logger.info(f"[SHEETS] Verify {customer['name']}: {'pass' if match else 'fail'}")
    return match


def get_claims_for_account(account_id: str) -> list[dict]:
    try:
        client = get_sheets_client()
        sheet = client.open_by_key(settings.google_sheet_id).worksheet("claims")
        records = sheet.get_all_records()
        claims = [r for r in records if r["account_id"] == account_id]
        logger.info(f"[SHEETS] Claims for {account_id}: {len(claims)} found")
        return claims

    except Exception as e:
        logger.error(f"[SHEETS] Claims lookup error: {str(e)}")
        raise
