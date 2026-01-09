#!/bin/bash

# Activate Virtual Environment
if [ -f "bin/activate" ]; then
    source bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "(Config) Using ./bot_config.json for webhook/user/email/edge_driver."

# Pass-through args for python scripts (e.g. --debug-port, --head)
PASSTHROUGH_ARGS=("$@")

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
python3 test_registration.py --crn 10961 --term 202601

echo ""
echo "Done."
