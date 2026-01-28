import json
import os
from slack_sdk.signature import SignatureVerifier
from googleapiclient.discovery import build
from google.oauth2 import service_account
import emoji

# Env Vars
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDS = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

def verify_slack_signature(headers, body):
    """Verify Slack Request Signature"""
    if not SLACK_SIGNING_SECRET:
        print("Warning: SLACK_SIGNING_SECRET not set. Skipping verification (unsafe).")
        return True # For local testing? No, unsafe.

    verifier = SignatureVerifier(SLACK_SIGNING_SECRET)
    
    # Getting headers. API Gateway headers might be dict or list.
    timestamp = headers.get("x-slack-request-timestamp") or headers.get("X-Slack-Request-Timestamp")
    signature = headers.get("x-slack-signature") or headers.get("X-Slack-Signature")

    if not timestamp or not signature:
         print("Missing timestamp or signature headers.")
         return False

    return verifier.is_valid(
        body=body,
        timestamp=timestamp,
        signature=signature
    )

def update_reaction_in_sheets(slack_ts, reaction):
    """Update Google Sheets for the matching message timestamp"""
    if not GOOGLE_CREDS or not SPREADSHEET_ID:
        print("Missing Google credentials.")
        return False

    try:
        creds_info = json.loads(GOOGLE_CREDS)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)

        # 1. Search for the row with this slack_ts (Column G)
        # Using a simple scan for now. 
        # Ideally, we read Column G (A1 notation G:G) and find the index.
        range_name = "G:G" 
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        rows = result.get('values', [])
        
        target_row_index = -1
        # rows is list of lists [['ts1'], ['ts2'], ...]
        # Note: 1-based index. 
        for i, row in enumerate(rows):
            if row and row[0] == slack_ts:
                target_row_index = i + 1 # 1-based
                break
        
        if target_row_index == -1:
            print(f"Timestamp {slack_ts} not found in sheet.")
            return False

        # 2. Update Column H (Reactions) at that row
        # We append the reaction. First read existing? Or just append to a list string?
        # Let's read H match.
        h_range = f"H{target_row_index}"
        h_result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=h_range).execute()
        current_val = h_result.get('values', [[]])[0]
        current_text = current_val[0] if current_val else ""
        
        # Avoid duplicate reaction logging?
        # Slack sends event for every user.
        # Maybe format: "thumbsup(user1), heart(user2)" or just "thumbsup, heart"
        # User requested: "Append the emoji name."
        
        new_text = f"{current_text}, {reaction}" if current_text else reaction
        
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=h_range,
            valueInputOption="RAW",
            body={'values': [[new_text]]}
        ).execute()
        
        print(f"Updated row {target_row_index} with reaction: {reaction}")
        return True

    except Exception as e:
        print(f"Error updating sheet: {e}")
        return False

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    # 1. Parse body and headers
    # API Gateway Proxy Integration wraps real request.
    headers = event.get("headers", {})
    body = event.get("body", "")
    
    # 2. Verify Signature
    if not verify_slack_signature(headers, body):
        return {
            'statusCode': 401,
            'body': 'Invalid signature'
        }
    
    # 3. Parse JSON Body
    try:
        data = json.loads(body)
    except ValueError:
        return {'statusCode': 400, 'body': 'Bad JSON'}

    # 4. URL Verification (Slack Challenge)
    if data.get("type") == "url_verification":
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/plain'},
            'body': data.get("challenge")
        }

    # 5. Handle Events
    if "event" in data:
        slack_event = data["event"]
        event_type = slack_event.get("type")
        
        if event_type == "reaction_added":
            # https://api.slack.com/events/reaction_added
            # { "type": "reaction_added", "user": "U123", "reaction": "thumbsup", "item": { "type": "message", "channel": "C123", "ts": "123.456" } ... }
            reaction = slack_event.get("reaction")
            item = slack_event.get("item", {})
            ts = item.get("ts")
            
            if ts and reaction:
                # Convert Slack reaction name (e.g. "tada") to Unicode Emoji (🎉)
                # language='alias' supports Slack/GitHub style codes
                try:
                    # emoji.emojize needs colons, e.g. :tada:
                    # But custom emojis won't convert and just stay as text (which is desired fallback)
                    reaction_emoji = emoji.emojize(f":{reaction}:", language='alias')
                    # If conversion failed (returned same string with colons), strip colons to keep original text
                    # Wait, emojize returns the string with colons if not found? No, it returns strictly what was passed if not found (v2 behavior might vary).
                    # Actually, if it fails, it returns the input string ":reaction:".
                    # Let's check if it starts and ends with colon, if so, revert to raw name?
                    # Or just save the unicode if successful, else raw name.
                    if reaction_emoji == f":{reaction}:":
                         reaction_display = reaction
                    else:
                         reaction_display = reaction_emoji
                except Exception as e:
                    print(f"Emoji conversion failed: {e}")
                    reaction_display = reaction

                print(f"Reaction added: {reaction} (Display: {reaction_display}) to message {ts}")
                update_reaction_in_sheets(ts, reaction_display)
        
    return {
        'statusCode': 200,
        'body': 'OK'
    }
