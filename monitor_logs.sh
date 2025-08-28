#!/bin/bash

echo "=== MTProxy Bot Monitor ==="
echo "Press Ctrl+C to stop"
echo

# Function to show status
show_status() {
    echo "--- Service Status ---"
    systemctl is-active mtproxy-bot && echo "Bot: ✅ Active" || echo "Bot: ❌ Inactive"
    systemctl is-active MTProxy && echo "MTProxy: ✅ Active" || echo "MTProxy: ❌ Inactive"
    echo
}

# Show initial status
show_status

# Follow logs with filtering
journalctl -u mtproxy-bot -u MTProxy -f --since "5 minutes ago" | while read line; do
    # Highlight important messages
    if echo "$line" | grep -qi "error\|failed\|❌"; then
        echo -e "\033[31m$line\033[0m"  # Red for errors
    elif echo "$line" | grep -qi "success\|✅\|active"; then
        echo -e "\033[32m$line\033[0m"  # Green for success
    elif echo "$line" | grep -qi "restart\|pid_max"; then
        echo -e "\033[33m$line\033[0m"  # Yellow for restart operations
    else
        echo "$line"
    fi
done