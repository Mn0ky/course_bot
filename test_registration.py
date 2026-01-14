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

    def _chunk_text(text: str, max_len: int) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_len, len(text))
            chunks.append(text[start:end])
            start = end
        return chunks

    full_log_text = "\n".join(LOG_BUFFER)
    # Discord message limit is ~2000 chars; reserve room for code block and ping
    reserve = 10
    if ping_user and DISCORD_USER_ID:
        reserve += len(DISCORD_USER_ID) + 5
    max_body = max(1, 2000 - reserve)

    try:
        chunks = _chunk_text(full_log_text, max_body)
        for i, chunk in enumerate(chunks):
            content = f"```\n{chunk}\n```"
            # Only ping on the final chunk
            if ping_user and DISCORD_USER_ID and i == len(chunks) - 1:
                content += f"\n<@{DISCORD_USER_ID}>"
            requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
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
    parser.add_argument("--crn", help="Single CRN to register (or use --crns for multiple)")
    parser.add_argument("--crns", help="Comma-separated list of CRNs (e.g. 10961,11038)")
    parser.add_argument("--term", help="Term code (e.g. 202601)")
    parser.add_argument("--webhook", help="Override Discord webhook URL (otherwise uses bot_config.json)")
    parser.add_argument("--discord-user", help="Override Discord user ID to ping (otherwise uses bot_config.json)")
    parser.add_argument("--verbose", action="store_true", help="Print full batch response JSON for debugging")
    args = parser.parse_args()

    global DISCORD_WEBHOOK_URL
    global DISCORD_USER_ID
    cfg = load_bot_config()
    DISCORD_WEBHOOK_URL = args.webhook or _cfg_get(cfg, "webhook_url", "webhook", default="")
    DISCORD_USER_ID = args.discord_user or _cfg_get(cfg, "discord_user_id", "discord_user", default="")

    # Build CRN list from args or config
    crn_list = []
    if args.crns:
        crn_list = [c.strip() for c in args.crns.split(",") if c.strip()]
    elif args.crn:
        crn_list = [args.crn.strip()]
    else:
        # Fall back to config
        cfg_crns = cfg.get("crn_list", [])
        if isinstance(cfg_crns, list):
            crn_list = [str(c).strip() for c in cfg_crns if c]
    
    term = args.term or _cfg_get(cfg, "term", default="")

    if crn_list and term:
        print(f"Using CRNs: {crn_list}, Term: {term}")
    
    if not crn_list or not term:
        print("CRN list and Term are required.")
        print("Provide via --crn/--crns and --term, or configure in bot_config.json")
        return

    log(f"[Step 2] Running Registration Script...\nTarget CRNs: {', '.join(crn_list)}, Term: {term}")

    # =============================================
    # Process each CRN individually (add to cart → submit → next)
    # This prevents "duplicate section" errors when trying alternate CRNs
    # =============================================
    any_success = False
    
    for crn in crn_list:
        print(f"\n{'='*50}")
        print(f"Processing CRN {crn}")
        print(f"{'='*50}")
        log(f"\n--- Processing CRN {crn} ---")
        
        # Step 1: Add CRN to cart
        add_url = f"{BASE_URL}/classRegistration/addCRNRegistrationItems"
        payload = {
            'crnList': crn,
            'term': term
        }
        
        print(f"POST URL: {add_url}")
        print(f"Payload: {payload}")
        
        try:
            response = requests.post(add_url, headers=HEADERS, data=payload)
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                print(f"\nCRITICAL ERROR: Server did not return JSON for CRN {crn}.")
                print(f"Status Code: {response.status_code}")
                print(f"Response Content (First 500 chars):\n{response.text[:500]}")
                log(f"[ERROR] CRN {crn}: Server did not return JSON")
                continue

            response.raise_for_status()
            
            items = data.get('aaData', [])
            if not items:
                msg = f"No data returned in aaData for CRN {crn}."
                print(json.dumps(data, indent=2))
                log(msg)
                continue

            item = items[0]
            
            if not item.get('success'):
                msg = f"CRN {crn}: {item.get('message', 'Unknown error')}"
                log(msg)
                print(f"[!] {msg}")
                if not item.get('model'):
                    continue

            model = item.get('model')
            
            if not model:
                log(f"CRN {crn}: Model missing, skipping")
                continue

            course_title = model.get('courseTitle', 'Unknown')
            log(f"Got model: {course_title} ({crn})")

            # Find the "Web Registered" action
            valid_actions = model.get('registrationActions', [])
            target_action_code = None
            
            print(f"Available Actions for CRN {crn}:")
            for action in valid_actions:
                code = action.get('courseRegistrationStatus')
                desc = action.get('description')
                print(f" - {desc} (Code: {code})")
                
                if desc and ("Web Registered" in desc or "Register" in desc):
                    target_action_code = code

            if not target_action_code:
                target_action_code = "RW"
                print(f"[!] Could not auto-detect register action for CRN {crn}, defaulting to 'RW'")
            
            model['selectedAction'] = target_action_code
            
            # Step 2: Immediately batch submit this single CRN
            print(f"\n--- Submitting CRN {crn} ---")
            log(f"Submitting {course_title} ({crn})...")

            batch_payload = {
                "uniqueSessionId": UNIQUE_SESSION_ID,
                "create": [],
                "update": [model],
                "destroy": []
            }
            
            submit_url = f"{BASE_URL}/classRegistration/submitRegistration/batch"
            
            batch_headers = HEADERS.copy()
            batch_headers['Content-Type'] = 'application/json'

            submit_resp = requests.post(submit_url, headers=batch_headers, json=batch_payload)
            submit_resp.raise_for_status()
            
            result_data = submit_resp.json()

            # Debug: print full response when --verbose is set
            if args.verbose:
                print("\n[DEBUG] Full batch response:")
                print(json.dumps(result_data, indent=2))

            success = result_data.get('success', False)
            message = result_data.get('message', 'No message provided')
            print(f"Global Message: {message}")
            print(f"Success Flag: {success}")

            # Check for CRN specific errors - only look at the item matching our CRN
            updates = result_data.get('data', {}).get('update', [])
            found_errors = False
            found_success = False
            
            for update_item in updates:
                item_crn = update_item.get('courseReferenceNumber', '')
                # Only process the update_item for the CRN we just submitted
                if str(item_crn) != str(crn):
                    continue
                
                crn_errors = update_item.get('crnErrors', [])
                has_crn_errors = bool(crn_errors)

                # Always log/print crnErrors if present
                if has_crn_errors:
                    found_errors = True
                    for err in crn_errors:
                        err_msg = f"{crn}: {err.get('message')}"
                        print(f"[!] {err_msg}")
                        log(f"[ERROR] {err_msg}")

                # Process messages: if there are crnErrors, do NOT print/log success messages
                msgs = update_item.get('messages', [])
                for msg in msgs:
                    msg_type = msg.get('type')
                    msg_text = msg.get('message')
                    if msg_type == 'error':
                        found_errors = True
                        print(f"[!] {course_title} ({crn}): {msg_text}")
                        log(f"[ERROR] {crn}: {msg_text}")
                    elif msg_type == 'success':
                        if has_crn_errors:
                            # Skip success messages when crnErrors exist (avoid misleading output)
                            continue
                        found_success = True
                        print(f"[+] {course_title} ({crn}): {msg_text}")
                        log(f"[SUCCESS] {course_title} ({crn}): {msg_text}")

            if not found_errors and success:
                print(f"\n[SUCCESS] CRN {crn} registered successfully!")
                any_success = True
            else:
                print(f"\n[FAILED] CRN {crn} registration failed. Trying next CRN...")
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed for CRN {crn}: {e}")
            log(f"[ERROR] CRN {crn}: Request failed - {e}")
            continue
        except Exception as e:
            print(f"An error occurred for CRN {crn}: {e}")
            log(f"[ERROR] CRN {crn}: {e}")
            continue

    # Final summary
    print(f"\n{'='*50}")
    print("Registration Complete")
    print(f"{'='*50}")
    
    if any_success:
        log("\n[DONE] At least one course registered successfully!")
        send_discord_buffer(ping_user=True)  # Only ping on success
    else:
        log("\n[DONE] No courses were successfully registered.")
        send_discord_buffer(ping_user=False)  # No ping on failure
        
        # Print full dump for debugging if needed
        # print(json.dumps(result_data, indent=2))

if __name__ == "__main__":
    test_add_course()
