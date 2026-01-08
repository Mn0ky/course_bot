import time
import json
import os
import platform
import argparse
import requests
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# REPLACE WITH YOUR ACTUAL WEBHOOK URL
# Now using environment variable if available
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Log buffer for accumulating messages
LOG_BUFFER = []

def log(message):
    """Accumulates logs in memory and prints to console."""
    print(message)
    LOG_BUFFER.append(message)

def send_discord_buffer():
    """Sends the accumulated logs as a single code block message."""
    if not DISCORD_WEBHOOK_URL or "YOUR_DISCORD_WEBHOOK_URL" in DISCORD_WEBHOOK_URL:
        return
    
    if not LOG_BUFFER:
        return

    full_log_text = "\n".join(LOG_BUFFER)
    # Wrap in code block for better formatting
    content = f"```\n{full_log_text}\n```"
    
    try:
        data = {"content": content}
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Failed to log to Discord: {e}")

def get_edge_user_data_dir():
    home = os.path.expanduser("~")
    system = platform.system()
    # Tries to guess the default location per platform
    if system == "Darwin":
        return os.path.join(home, "Library", "Application Support", "Microsoft Edge")
    elif system == "Windows":
        localappdata = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        return os.path.join(localappdata, "Microsoft", "Edge", "User Data")
    else:
        # Linux or others
        return os.path.join(home, ".config", "microsoft-edge")

def find_profile_directory(user_data_dir, target_email):
    print(f"Searching for profile with email: {target_email} in {user_data_dir}")
    try:
        if not os.path.exists(user_data_dir):
             print(f"User Data Directory not found: {user_data_dir}")
             return "Default"

        for item in os.listdir(user_data_dir):
            if item == "Default" or item.startswith("Profile"):
                pref_path = os.path.join(user_data_dir, item, "Preferences")
                if os.path.exists(pref_path):
                    try:
                        with open(pref_path, 'r', encoding='utf-8') as f:
                            data = f.read()
                            if target_email in data:
                                print(f"Found match in: {item}")
                                return item
                    except:
                        pass
    except Exception as e:
        print(f"Error searching profiles: {e}")
    
    print("Profile not found by email, defaulting to 'Default'")
    return "Default"

def fetch_config():
    parser = argparse.ArgumentParser(description="SRS Config Fetcher")
    parser.add_argument("--term", help="Term to select (e.g., 'Spring 2026')")
    parser.add_argument("--debug-port", help="Port of existing Edge instance (e.g. 9222)")
    parser.add_argument("--head", action="store_true", help="Launch browser in visible (non-headless) mode")
    parser.add_argument("--edge-driver", help="Path to msedgedriver executable (e.g. 'D:\\path\\msedgedriver.exe')")
    args = parser.parse_args()
    
    # If no term is provided via args, ask for it
    target_term = args.term
    if not target_term:
        target_term = input("Enter Term to select (e.g. 'Spring 2026'): ").strip()

    log("[Step 1] Fetching SRS Configuration...")
    print("--- Fetching SRS Configuration ---")
    
    user_data_dir = get_edge_user_data_dir()
    # Find the correct profile using EDGE_PROFILE_EMAIL env var, or fallback to Default
    profile_email = os.environ.get("EDGE_PROFILE_EMAIL", "")
    profile_dir = find_profile_directory(user_data_dir, profile_email) if profile_email else "Default"
    
    options = EdgeOptions()
    
    if args.debug_port:
        print(f"Connecting to existing Edge instance on port {args.debug_port}...")
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{args.debug_port}")
    else:
        print("NOTE: Please ensure all Microsoft Edge windows are CLOSED before proceeding, or the driver may fail to launch with your profile.")
        print("\n[TIP] To run this bot alongside your personal browsing (examples):")
        print("1. Close ALL Microsoft Edge windows.")
        print("2. Launch Edge with remote debugging enabled (examples):")
        print("   macOS: '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge' --remote-debugging-port=9222 --user-data-dir='~/Library/Application Support/Microsoft Edge' --profile-directory='Default'")
        print("   Windows: \"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe\" --remote-debugging-port=9222 --user-data-dir=\"%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\" --profile-directory=\"Default\"")
        print("   Linux: /usr/bin/microsoft-edge --remote-debugging-port=9222 --user-data-dir=\"$HOME/.config/microsoft-edge\" --profile-directory=\"Default\"")
        print("3. Run this bot again with: ./run_bot.sh --debug-port 9222")
        print("4. Then start the bot with: ./run_bot.sh --webhook <webhook_url> --email <email> --discord-user \"<user_id>\"")
        print("-" * 60 + "\n")
        
        # Default to headless unless user explicitly requested visible browser
        if not args.head:
            print('Launching browser in headless mode (no GUI). To see the browser, use the "--head" option.')
            options.add_argument("--headless=new")
        else:
            print("Launching browser in visible (non-headless) mode as requested (--head).")
        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument(f"profile-directory={profile_dir}") 
    
    # Try to launch Edge 
    
    # Try to launch Edge
    driver_path = None
    service = None

    # If user passed a driver path, try to use it first
    if args.edge_driver:
        if os.path.exists(args.edge_driver):
            print(f"Using Edge driver provided at: {args.edge_driver}")
            service = EdgeService(args.edge_driver)
        else:
            print(f"Warning: Specified Edge driver not found: {args.edge_driver}. Falling back to auto-download or PATH.")

    if service is None:
        try:
            print("Attempting to download/update Edge Driver...")
            driver_path = EdgeChromiumDriverManager().install()
            service = EdgeService(driver_path)
        except Exception as e:
            print(f"Warning: Automated driver download failed ({e}).")
            print("Attempting to use system-installed 'msedgedriver'...")
            service = EdgeService() # Falls back to PATH

    try:
        driver = webdriver.Edge(service=service, options=options)
    except Exception as e:
        print(f"\nCRITICAL ERROR launching Edge: {e}")
        print("-" * 60)
        print("TROUBLESHOOTING:")
        print("1. Ensure Microsoft Edge is COMPLETELY closed (close all windows).")
        print("2. If you got a 'driver not found' error above, try installing it manually:")
        print("   macOS (brew): brew install --cask msedgedriver")
        print("   Windows: download msedgedriver from https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
        print("   Or specify an existing driver with: --edge-driver \"C:\\path\\to\\msedgedriver.exe\"")
        print("-" * 60)
        return

    try:
        # 1. Navigate to Main Menu first (Login landing)
        print("Navigating to Owl Express Main Menu...")
        driver.get("https://owlexpress.kennesaw.edu/prodban/twbkwbis.P_GenMenu?name=bmenu.P_MainMnu")
        
        # Allow time for manual login if needed
        print("Waiting for page load. If login is required, please log in manually in the browser window.")
        WebDriverWait(driver, 300).until(
             EC.url_contains("P_MainMnu")
        )
        print("Main Menu detected.")
        time.sleep(2)

        # 2. Navigate to Registration Menu
        print("Navigating to Registration Menu...")
        driver.get("https://owlexpress.kennesaw.edu/prodban/twbkwbis.P_GenMenu?name=HTML_Registration_SubMenu")
        WebDriverWait(driver, 30).until(
             EC.url_contains("HTML_Registration_SubMenu")
        )
        print("Registration Menu detected.")
        time.sleep(2)

        # 3. Click "Register for Classes" / Navigate to SRS App
        print("Navigating to Class Registration App...")
        # Updated URL to match the HAR file activity
        
        # AUTOMATED NAVIGATION STEPS
        try:
             # A. Click "Register for Classes"
             # Typically it is an anchor or div with text "Register for Classes"
             # Banner 9 tiles often have IDs like 'registerLink' or class 'register'
             # We try a few strategies
             print("Attempting to click 'Register for Classes'...")
             
             # Targeting the text specifically to avoid clicking "Prepare for Registration"
             register_link = WebDriverWait(driver, 15).until(
                 EC.element_to_be_clickable((By.XPATH, "//a[.//span[contains(text(), 'Register for Classes')] or contains(text(), 'Register for Classes')]"))
             )
             
             # Handle potential new tab opening
             original_window = driver.current_window_handle
             windows_before = driver.window_handles
             
             register_link.click()
             
             # Wait for new window if one opened
             time.sleep(2)
             windows_after = driver.window_handles
             if len(windows_after) > len(windows_before):
                 print("New tab detected. Switching to new tab...")
                 new_window = [w for w in windows_after if w != original_window][0]
                 driver.switch_to.window(new_window)
             
             # B. Select Term
             # The Select2 container ID is 's2id_txt_term' based on your snippet
             print(f"Waiting for Term Selection page. Selecting: {target_term}")
             
             # Locate the container and anchor
             container_id = "s2id_txt_term"
             print(f"Looking for element with ID: {container_id}")
             container = WebDriverWait(driver, 15).until(
                 EC.presence_of_element_located((By.ID, container_id))
             )
             
             # Updated per Selenium IDE recording: Click the arrow specifically
             print("Opening dropdown via arrow click (.select2-arrow > b)...")
             try:
                 arrow = container.find_element(By.CSS_SELECTOR, ".select2-arrow > b")
                 arrow.click()
             except Exception as arrow_err:
                 print(f"Standard click failed ({arrow_err}), trying JS...")
                 anchor = container.find_element(By.CSS_SELECTOR, "a.select2-choice")
                 driver.execute_script("arguments[0].click();", anchor)
             time.sleep(1)

             # 2. Find the visible search input.
             # In Select2, when opened, the input inside 'select2-drop' becomes visible.
             # We target it specifically.
             search_input = WebDriverWait(driver, 10).until(
                 EC.visibility_of_element_located((By.CSS_SELECTOR, "#s2id_autogen1_search, .select2-input"))
             )
             search_input.clear()
             search_input.send_keys(target_term)
             time.sleep(2) # Wait for filtering
             search_input.send_keys(Keys.ENTER)
             
             # C. Click Continue
             print("Clicking Continue...")
             try:
                 # Ensure button is present first
                 continue_btn = WebDriverWait(driver, 10).until(
                     EC.presence_of_element_located((By.ID, "term-go"))
                 )
                 
                 # Attempt standard click
                 try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "term-go"))).click()
                 except:
                    # Fallback to JS click if specific clickable check fails or click is intercepted
                    print("Standard click failed/timed out. forcing click via JS...")
                    driver.execute_script("arguments[0].click();", continue_btn)
                    
             except Exception as btn_err:
                 print(f"Failed to find or click Continue button: {btn_err}")
                 # Last resort attempt by text
                 try:
                     print("Trying to find Continue button by text...")
                     btn_by_text = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                     driver.execute_script("arguments[0].click();", btn_by_text)
                 except:
                     pass
             
             # Wait for search panels to appear (indicates session is fully initialized)
             print("Waiting for Registration Workspace...")
             WebDriverWait(driver, 20).until(
                 EC.presence_of_element_located((By.CSS_SELECTOR, ".search-panel, #search-go"))
             )
             print("Workspace loaded! Session should be primed.")

        except Exception as NavError:
             print(f"WARNING: Automated navigation failed: {NavError}")
             print("Please perform the navigation manually now.")
             input("Press ENTER when ready...")


        # 4. Extract Headers/Tokens
        
        # A. Cookies
        # Selenium get_cookies returns a list of dictionaries. We need to format the string "Name=Value; Name2=Value2"
        cookies = driver.get_cookies()
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        # B. Synchronizer Token
        # Often stored in <meta name="synchronizerToken"> or in JS variable window.synchronizerToken
        sync_token = None
        try:
            meta_tag = driver.find_element(By.CSS_SELECTOR, "meta[name='synchronizerToken']")
            sync_token = meta_tag.get_attribute("content")
        except:
            # Try JS execution fallback
            try:
                sync_token = driver.execute_script("return window.synchronizerToken || (window.checkCookie && window.checkCookie.token);")
            except:
                pass
        
        # C. Unique Session ID
        session_id = None
        print("Scanning Storage for Session ID...")
        try:
            # Simplified scan for the known key
            scan_script = "return sessionStorage.getItem('xe.unique.session.storage.id');"
            session_id = driver.execute_script(scan_script)
            
            if session_id:
                 print(f"Found uniqueSessionId: {session_id}")
            else:
                 print("xe.unique.session.storage.id NOT found in sessionStorage.")
                 
        except Exception as e:
            print(f"Error scanning storage: {e}")

        print("\n" + "="*50)
        print("EXTRACTED CONFIGURATION")
        print("="*50)
        
        print("\n[Cookie String Length]: " + str(len(cookie_string)))
        print(f"[X-Synchronizer-Token]: {sync_token}")
        print(f"[Unique Session ID]: {session_id}")
        
        print("\n" + "="*50)
        
        # Save to file for easy usage
        with open("config_dump.txt", "w") as f:
            f.write(f"COOKIE=\n{cookie_string}\n\n")
            f.write(f"TOKEN=\n{sync_token}\n\n")
            f.write(f"SESSION_ID=\n{session_id}\n")
            
        log("Successfully extracted SRS configuration info.")
        
        # Close automatically now that we are automated
        print("Closing browser...")
        send_discord_buffer()

    except Exception as e:
        error_msg = f"RUNTIME ERROR in fetch_srs_config: {e} <@480476543735431181>"
        log(error_msg)
        send_discord_buffer() # Send immediately on error
    finally:
        # If we attached to an existing window, we might not want to close it?
        # But usually 'quit' is safe.
        try:
            if not args.debug_port:
                driver.quit()
            else:
                print("Detaching from existing browser session (window left open).")
        except:
             pass

if __name__ == "__main__":
    fetch_config()
