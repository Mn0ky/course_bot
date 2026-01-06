#!/bin/bash

# Activate Virtual Environment
if [ -f "bin/activate" ]; then
    source bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Argument parsing
PASSTHROUGH_ARGS=()
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --webhook) export DISCORD_WEBHOOK_URL="$2"; shift ;;
        --email) export EDGE_PROFILE_EMAIL="$2"; shift ;;
        --discord-user) export DISCORD_USER_ID="$2"; shift ;;
        *) PASSTHROUGH_ARGS+=("$1") ;;
    esac
    shift
done

# Validate required arguments
if [ -z "$DISCORD_WEBHOOK_URL" ]; then
    echo "Error: --webhook <url> is required."
    echo "Usage: ./run_bot.sh --webhook <url> --email <edge_profile_email> [--discord-user <id>] [--debug-port <port>]"
    exit 1
fi

echo "=========================================="
echo "      Starting Course Registration Bot    "
echo "=========================================="

# Step 1: Run Selenium to fetch tokens
echo ""
echo "[Step 1] Fetching SRS Configuration..."
# Pass all script arguments (${PASSTHROUGH_ARGS[@]}) to the python script so --debug-port and others work
python3 fetch_srs_config.py --term "Spring Semester 2026" "${PASSTHROUGH_ARGS[@]}"

# Check if the config file was created
if [ ! -f config_dump.txt ]; then
    echo "Error: config_dump.txt was not created. Aborting."
    exit 1
fi

# Step 2: Run Registration
echo ""
echo "[Step 2] Running Registration Script..."
echo "Target: CRN 18016, Term 202601"
python3 test_registration.py --crn 10961 --term 202601 --auto

echo ""
echo "Done."
