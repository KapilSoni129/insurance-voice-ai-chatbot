"""
Create or update the Vapi assistant using the Vapi Server SDK.
If VAPI_ASSISTANT_ID is set in .env, updates the existing assistant.
Otherwise, creates a new one.

Usage: python scripts/create_vapi_assistant.py --server-url https://your-ngrok-url.ngrok.io
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi import Vapi
from dotenv import load_dotenv
import httpx

load_dotenv()

SYSTEM_PROMPT = """You are Ava, a friendly and professional AI claims support assistant for Observe Insurance. Your role is to help callers check on their insurance claim status.

## Your Conversation Flow

1. Greet the caller warmly. You can see their caller ID phone number ({{customer.number}}). Ask them to confirm: "I can see you're calling from {{customer.number}} — is this the phone number associated with your account?"
2. If they confirm, use that number. If they say no, ask for their full 10-digit account phone number.
3. If the caller gives fewer than 10 digits, ask them to repeat the full number including area code.
4. Once you have their phone number confirmed, ask for verification: their date of birth (MM/DD/YYYY) or last 4 digits of their SSN.
5. Call the authenticate_customer tool with both values.
6. If authenticated successfully, ask if they'd like to check their claim status.
7. Call get_claim_status with their account_id from the authentication result.
8. Communicate the claim status clearly. If documents are needed, explain how to submit them.
9. Ask if there's anything else you can help with. If not hangup the call after saying thank you note
10. For general questions, use search_faq to find answers.
11. End the call politely when the caller is done.

## Rules

- Be calm, supportive, and conversational. Speak naturally as if on a phone call.
- Keep responses concise — this is a voice call, not a text chat. 1-3 sentences per turn.
- Never reveal internal system details, account IDs, or technical information to the caller.
- If authentication fails, let the caller retry. After 2 failed attempts, use escalate_call.
- If the phone number is not found, inform the caller and offer to connect with a representative.
- If the caller asks to speak to a person at any point, or if authentication fails, you need to escalate. Before escalating:
  1. Ask for their name if you don't already have it.
  2. Confirm their phone number.
  3. Ask them to briefly describe the issue or reason they need help (use this as the escalation reason).
  4. Then call escalate_call with the reason.
- For emergencies (medical, fire, immediate danger), use escalate_call with is_emergency=true and advise them to call 911.
- When reporting claim status, be clear and empathetic, especially for denied claims.
- If the customer has multiple claims, briefly list them and ask which one they want details on.
- When the caller says closing phrases with a brief goodbye and do not have any other requests and use the endCall tool to hang up. Do not continue asking questions after the caller is satisfied.
- If you've completed the caller's request and they confirm they don't need anything else, say goodbye and use the endCall tool.
- If the caller goes silent or doesn't respond, say "Are you still there?" and wait. If they still don't respond after that, say "It seems like you may have stepped away. I'll go ahead and end our call. Feel free to call back anytime!" and use the endCall tool.
- After escalation, tell the caller "I'm going to end this call now, and you'll receive a call back from our escalation team shortly. Goodbye!" then use the endCall tool.
"""


def get_tools(webhook_url: str) -> list:
    return [
        {
            "type": "endCall",
            "messages": [
                {
                    "type": "request-complete",
                    "content": "Thank you for calling Observe Insurance. Have a wonderful day!",
                }
            ],
        },
        {
            "type": "function",
            "function": {
                "name": "authenticate_customer",
                "description": "Look up and verify a customer by their full 10-digit phone number and identity verification (DOB as MM/DD/YYYY or last 4 SSN digits). Only call once you have confirmed the caller provided all 10 digits.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {
                            "type": "string",
                            "description": "The caller's full 10-digit phone number, digits only (e.g., 5551234567). Must be exactly 10 digits.",
                        },
                        "verification_value": {
                            "type": "string",
                            "description": "Date of birth in MM/DD/YYYY format OR last 4 digits of SSN",
                        },
                    },
                    "required": ["phone_number", "verification_value"],
                },
            },
            "server": {"url": webhook_url},
        },
        {
            "type": "function",
            "function": {
                "name": "get_claim_status",
                "description": "Retrieve claim status for an authenticated customer. Only call after successful authentication.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "string",
                            "description": "The customer's account ID (from authenticate_customer result)",
                        },
                    },
                    "required": ["account_id"],
                },
            },
            "server": {"url": webhook_url},
        },
        {
            "type": "function",
            "function": {
                "name": "search_faq",
                "description": "Search knowledge base for answers about office hours, mailing address, new claims, claims process, document submission, or processing times.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The caller's question",
                        },
                    },
                    "required": ["question"],
                },
            },
            "server": {"url": webhook_url},
        },
        {
            "type": "function",
            "function": {
                "name": "escalate_call",
                "description": "Escalate to a human representative. Use when: caller requests a person, question is outside scope, authentication failed twice, or emergency. Always collect caller_name and phone before calling.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caller_name": {
                            "type": "string",
                            "description": "The caller's name",
                        },
                        "phone": {
                            "type": "string",
                            "description": "The caller's phone number",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for escalation (from caller's description of their issue)",
                        },
                        "is_emergency": {
                            "type": "boolean",
                            "description": "Whether this is an emergency",
                        },
                    },
                    "required": ["caller_name", "phone", "reason"],
                },
            },
            "server": {"url": webhook_url},
        },
    ]


def apply_hooks(token: str, assistant_id: str):
    """Apply hooks via raw API (SDK serializes 'on' field incorrectly)."""
    resp = httpx.patch(
        f"https://api.vapi.ai/assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "hooks": [
                {
                    "on": "customer.speech.timeout",
                    "do": [
                        {
                            "type": "say",
                            "exact": "Are you still there? I'm here if you need anything.",
                        }
                    ],
                    "options": {
                        "timeoutSeconds": 15,
                        "triggerMaxCount": 1,
                    },
                }
            ]
        },
    )
    if resp.status_code == 200:
        print("  Hooks applied (silence timeout: 15s, max 1 prompts)")
    else:
        print(f"  Warning: hooks failed ({resp.status_code}): {resp.text[:200]}")


def run(server_url: str):
    token = os.getenv("VAPI_PRIVATE_KEY")
    if not token:
        print("Error: VAPI_PRIVATE_KEY not set in .env")
        sys.exit(1)

    client = Vapi(token=token)
    webhook_url = f"{server_url}/webhook/vapi"
    assistant_id = os.getenv("VAPI_ASSISTANT_ID", "").strip()

    tools = get_tools(webhook_url)

    if assistant_id:
        # Update existing assistant
        print(f"Updating existing assistant: {assistant_id}")
        assistant = client.assistants.update(
            id=assistant_id,
            name="Observe Insurance Claims Agent",
            model={
                "provider": "openai",
                "model": "gpt-5.4",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                "tools": tools,
            },
            voice={"provider": "11labs", "voiceId": "sarah"},
            first_message="Hello! Thank you for calling Observe Insurance. My name is Ava, and I'm here to help you with your claim. I can see the number you're calling from — is this the phone number associated with your account?",
            server={"url": webhook_url},
            end_call_message="Thank you for calling Observe Insurance. Have a wonderful day!",
            max_duration_seconds=600,
        )
        apply_hooks(token, assistant.id)
        print(f"Assistant UPDATED!")
    else:
        # Create new assistant
        print("Creating new assistant...")
        assistant = client.assistants.create(
            name="Observe Insurance Claims Agent",
            model={
                "provider": "openai",
                "model": "gpt-5.4",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                "tools": tools,
            },
            voice={"provider": "11labs", "voiceId": "sarah"},
            first_message="Hello! Thank you for calling Observe Insurance. My name is Ava, and I'm here to help you with your claim. I can see the number you're calling from — is this the phone number associated with your account?",
            server={"url": webhook_url},
            end_call_message="Thank you for calling Observe Insurance. Have a wonderful day!",
            max_duration_seconds=600,
        )
        apply_hooks(token, assistant.id)
        print(f"Assistant CREATED!")
        print(f"  Add to .env: VAPI_ASSISTANT_ID={assistant.id}")

    print(f"  ID: {assistant.id}")
    print(f"  Name: {assistant.name}")
    print(f"  Webhook: {webhook_url}")
    print(f"  Model: GPT-5.4")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", required=True, help="Your ngrok or deployed URL (e.g., https://abc123.ngrok.io)")
    args = parser.parse_args()
    run(args.server_url)
