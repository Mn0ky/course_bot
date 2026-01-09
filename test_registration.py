import requests
import json
import sys
import os
import argparse

# Configured via CLI args
DISCORD_WEBHOOK_URL = ""
DISCORD_USER_ID = ""

# Log buffer for accumulating messages
LOG_BUFFER = []

def _get_bot_config_path() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "bot_config.json")

def load_bot_config() -> dict:
    """Loads shared bot_config.json. Missing/invalid config yields empty dict."""
    path = _get_bot_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Warning: Failed to read bot_config.json ({e}).")
        return {}
    return {}

def _cfg_get(cfg: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = cfg.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default

def log(message):
    """Accumulates logs in memory and prints to console."""
    print(message)
    LOG_BUFFER.append(message)

def send_discord_buffer(ping_user=False):
    """Sends the accumulated logs as a single code block message.
       If ping_user is True, appends the ping OUTSIDE the code block.
    """
    if not DISCORD_WEBHOOK_URL or "YOUR_DISCORD_WEBHOOK_URL" in DISCORD_WEBHOOK_URL:
        return
    
    if not LOG_BUFFER:
        return

    full_log_text = "\n".join(LOG_BUFFER)
    # Wrap in code block for better formatting
    content = f"```\n{full_log_text}\n```"
    
    if ping_user and DISCORD_USER_ID:
        content += f"\n<@{DISCORD_USER_ID}>"

    try:
        data = {"content": content}
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Failed to log to Discord: {e}")

# ==========================================
# CONFIGURATION
# ==========================================
def load_config():
    config = {}
    try:
        with open('config_dump.txt', 'r') as f:
            content = f.read()
            
        # Parse simple key=value format from dump
        # The dump format implies keys are followed by values on newlines
        lines = content.split('\n')
        current_key = None
        for line in lines:
            if line.strip() in ['COOKIE=', 'TOKEN=', 'SESSION_ID=']:
                current_key = line.strip().replace('=', '')
            elif current_key and line.strip():
                config[current_key] = line.strip()
                current_key = None # Reset after reading value
                
        return config
    except FileNotFoundError:
        print("Error: config_dump.txt not found. Please run fetch_srs_config.py first.")
        sys.exit(1)

config = load_config()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'X-Synchronizer-Token': config.get('TOKEN', 'REPLACE_WITH_YOUR_TOKEN'),
    'Cookie': config.get('COOKIE', 'REPLACE_WITH_YOUR_FULL_COOKIE_STRING'),
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://srs-owlexpress.kennesaw.edu/StudentRegistrationSsb/ssb/classRegistration/classRegistration',
    'Origin': 'https://srs-owlexpress.kennesaw.edu'
}

UNIQUE_SESSION_ID = config.get('SESSION_ID', 'REPLACE_WITH_UNIQUE_SESSION_ID')

BASE_URL = "https://srs-owlexpress.kennesaw.edu/StudentRegistrationSsb/ssb"

def test_add_course():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Course Registration Bot")
    parser.add_argument("--crn", help="CRN to register")
    parser.add_argument("--term", help="Term code (e.g. 202601)")
    parser.add_argument("--webhook", help="Override Discord webhook URL (otherwise uses bot_config.json)")
    parser.add_argument("--discord-user", help="Override Discord user ID to ping (otherwise uses bot_config.json)")
    args = parser.parse_args()

    global DISCORD_WEBHOOK_URL
    global DISCORD_USER_ID
    cfg = load_bot_config()
    DISCORD_WEBHOOK_URL = args.webhook or _cfg_get(cfg, "webhook_url", "webhook", default="")
    DISCORD_USER_ID = args.discord_user or _cfg_get(cfg, "discord_user_id", "discord_user", default="")

    # 1. Need crn and term
    crn = args.crn or ""
    term = args.term or ""
    if crn and term:
        print(f"Using CLI args - CRN: {crn}, Term: {term}")

    if not crn or not term:
        print("CRN and Term are required.")
        return

    log(f"[Step 2] Running Registration Script...\nTarget: CRN {crn}, Term {term}")

    print(f"\n--- Step 1: Add CRN {crn} to Cart (Summary) ---")
    log(f"Add CRN {crn} to Cart...")
    
    add_url = f"{BASE_URL}/classRegistration/addCRNRegistrationItems"
    payload = {
        'crnList': crn,
        'term': term
    }
    
    print(f"POST URL: {add_url}")
    print(f"Payload: {payload}")
    
    try:
        response = requests.post(add_url, headers=HEADERS, data=payload)
        
        # Debugging: Print response content if it fails to parse
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("\nCRITICAL ERROR: Server did not return JSON.")
            print(f"Status Code: {response.status_code}")
            print(f"Response Content (First 500 chars):\n{response.text[:500]}")
            return

        response.raise_for_status()
        
        print("Response received.")
        
        # Check for success in aaData
        # Expected structure: {"aaData": [ { "success": boolean, "model": {...}, "message": ... } ] }
        
        items = data.get('aaData', [])
        if not items:
            msg = "No data returned in aaData."
            print(json.dumps(data, indent=2))
            log(msg)
            send_discord_buffer()
            return

        item = items[0]
        
        # Check for non-success status
        if not item.get('success'):
             msg = f"Add to Cart Status: Failed/Warning. Message: {item.get('message')}"
             log(msg)
             send_discord_buffer()
             
             # If no model is returned, we definitely cannot proceed
             if not item.get('model'):
                 return

        model = item.get('model')
        
        if not model:
            msg = f"Action failed or model is missing. Cannot proceed to batch submit.\nMessage: {item.get('message')}"
            log(msg)
            send_discord_buffer()
            return

        log("Successfully received registration model.")
        log(f"Got model for course: {model.get('courseTitle')} ({model.get('courseReferenceNumber')})")

        # 2. Find the "Web Registered" action
        # The model contains a list of allowed actions. We need to find the one for "Register".
        # codes are usually "RW" (Web Registered) or "RE".
        
        valid_actions = model.get('registrationActions', [])
        target_action_code = None
        
        print("Available Actions:")
        for action in valid_actions:
            code = action.get('courseRegistrationStatus')
            desc = action.get('description')
            print(f" - {desc} (Code: {code})")
            
            # Heuristic to find the "Register" action
            if "Web Registered" in desc or "Register" in desc:
                 target_action_code = code

        # If we couldn't find one, ask user or default to RW
        if not target_action_code:
            target_action_code = input("\nCould not auto-detect 'Register' action. Enter code manually (e.g. RW): ").strip()
        
        if not target_action_code:
            print("No action selected. Aborting.")
            return

        print("\n--- Step 2: Preparing Batch Submit ---")
        log("Preparing for Batch Submit...")

        # 3. Modify model for submission
        model['selectedAction'] = target_action_code
        
        # 4. Batch Submit
        # Payload structure: { "uniqueSessionId": "...", "create": [], "update": [ model ] }
        # Note: Added items are usually passed in 'update' if they came from addCRNRegistrationItems (which creates a temp view)
        
        batch_payload = {
            "uniqueSessionId": UNIQUE_SESSION_ID,
            "create": [],
            "update": [model],
            "destroy": []
        }
        
        submit_url = f"{BASE_URL}/classRegistration/submitRegistration/batch"
        
        # Need to switch content type for this request to JSON
        batch_headers = HEADERS.copy()
        batch_headers['Content-Type'] = 'application/json'

        print(f"\nAuto-confirming submission for {crn}...")

        submit_resp = requests.post(submit_url, headers=batch_headers, json=batch_payload)
        submit_resp.raise_for_status()
        
        result_data = submit_resp.json()
        print("\n--- Registration Result ---")
        
        # Parse response for errors
        success = result_data.get('success', False)
        message = result_data.get('message', 'No message provided')
        print(f"Global Message: {message}")
        print(f"Success Flag: {success}")

        # Deep check for CRN specific errors
        updates = result_data.get('data', {}).get('update', [])
        found_errors = False
        discord_error_log = ""
        
        for update_item in updates:
            # Check crnErrors list
            crn_errors = update_item.get('crnErrors', [])
            if crn_errors:
                found_errors = True
                print(f"\n[!] Errors for CRN {update_item.get('courseReferenceNumber', 'Unknown')}:")
                for err in crn_errors:
                    msg = f"    - {err.get('message')} (Flag: {err.get('errorFlag')})"
                    print(msg)
                    discord_error_log += f"\nCRN Error: {err.get('message')}"
            
            # Check execution message
            msgs = update_item.get('messages', [])
            for msg in msgs:
                msg_type = msg.get('type')
                msg_text = msg.get('message')
                if msg_type == 'error':
                    found_errors = True
                    print(f"\n[!] Error Message: {msg_text}")
                    discord_error_log += f"\nError Msg: {msg_text}"
                elif msg_type == 'success':
                     print(f"\n[+] Success Message: {msg_text}")

        discord_msg = f"--- Registration Result ---\nGlobal Message: {message}\nSuccess Flag: {success}"
        log(discord_msg)

        if not found_errors and success:
            print("\n[SUCCESS] Registration submitted successfully with no reported errors.")
            log("[SUCCESS] Registration submitted successfully with no reported errors.")
            send_discord_buffer(ping_user=True)
        else:
             print("\n[FAILURE] The batch submission returned 'success': false or contained errors.")
             log(f"[FAILURE] Registration Errors:{discord_error_log}")
             send_discord_buffer() # No ping on failure as requested
        
        # Print full dump for debugging if needed
        # print(json.dumps(result_data, indent=2))

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        log(f"RUNTIME ERROR (RequestException) in test_registration: {e}")
        send_discord_buffer(ping_user=True)
        if e.response:
            print(f"Status Code: {e.response.status_code}")
            print(f"Response: {e.response.text[:500]}")
    except Exception as e:
        print(f"An error occurred: {e}")
        log(f"RUNTIME ERROR in test_registration: {e}")
        send_discord_buffer(ping_user=True)

if __name__ == "__main__":
    test_add_course()
