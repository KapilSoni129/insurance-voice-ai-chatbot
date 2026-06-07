"""
Create Airtable base and 'Call Logs' table via API.
Requires AIRTABLE_API_KEY in .env (Personal Access Token with schema.bases:write scope).

Usage: python scripts/setup_airtable.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from dotenv import load_dotenv

load_dotenv()


def setup():
    token = os.getenv("AIRTABLE_API_KEY")
    if not token:
        print("Error: AIRTABLE_API_KEY not set in .env")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Step 1: Create a new base with the Call Logs table
    print("Creating Airtable base 'Observe Insurance'...")

    payload = {
        "name": "Observe Insurance",
        "tables": [
            {
                "name": "Call Logs",
                "fields": [
                    {"name": "caller_name", "type": "singleLineText"},
                    {"name": "phone", "type": "singleLineText"},
                    {"name": "call_summary", "type": "multilineText"},
                    {
                        "name": "sentiment",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "positive", "color": "greenLight2"},
                                {"name": "neutral", "color": "yellowLight2"},
                                {"name": "negative", "color": "redLight2"},
                            ]
                        },
                    },
                    {"name": "timestamp", "type": "singleLineText"},
                    {
                        "name": "resolution",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "resolved", "color": "greenLight2"},
                                {"name": "escalated", "color": "orangeLight2"},
                                {"name": "unresolved", "color": "redLight2"},
                            ]
                        },
                    },
                    {"name": "agent_types_used", "type": "singleLineText"},
                    {"name": "call_id", "type": "singleLineText"},
                    {"name": "duration_seconds", "type": "number", "options": {"precision": 0}},
                ],
            }
        ],
    }

    with httpx.Client() as client:
        response = client.post(
            "https://api.airtable.com/v0/meta/bases",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            base_id = data["id"]
            print(f"Base created successfully!")
            print(f"  Base ID: {base_id}")
            print(f"  Name: {data['name']}")
            print(f"  Table: Call Logs")
            print()
            print(f"Add this to your .env:")
            print(f"  AIRTABLE_BASE_ID={base_id}")
            print(f"  AIRTABLE_TABLE_NAME=Call Logs")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            print()
            if response.status_code == 422:
                print("Hint: Your token may need the 'schema.bases:write' scope.")
                print("Go to https://airtable.com/create/tokens and edit your token to add this scope.")
            elif response.status_code == 403:
                print("Hint: Your token doesn't have permission. Check scopes:")
                print("  Required: schema.bases:write, data.records:read, data.records:write")


if __name__ == "__main__":
    setup()
