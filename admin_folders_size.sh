#!/bin/bash

# admin_folders_size.sh
# Lists subfolder sizes in descending order with MB filter
# Usage: ./admin_folders_size.sh <start_folder> <mbfilter>

show_usage() {
    echo "Usage: $0 <start_folder> <mbfilter>"
    echo ""
    echo "Parameters:"
    echo "  start_folder  - Path to the folder to analyze"
    echo "  mbfilter      - Minimum size in MB to include in results"
    echo ""
    echo "Example:"
    echo "  $0 /home/user/data 100"
    echo "  Lists all subfolders of /home/user/data larger than 100 MB"
    echo ""
    echo "Special case:"
    echo "  $0 / 100"
    echo "  Scans predefined system folders: /bin /etc /lib /lost+found /proc"
    echo "  /run /snap /tmp /var /boot /home /lib64 /media /opt /root /sbin /srv /sys /usr"
}

if [ $# -ne 2 ]; then
    show_usage
    exit 1
fi

START_FOLDER="$1"
MBFILTER="$2"

if ! [[ "$MBFILTER" =~ ^[0-9]+$ ]]; then
    echo "Error: mbfilter must be a positive integer"
    exit 1
fi

# Predefined system folders to scan when start_folder is "/"
ROOT_FOLDERS=("/bin" "/etc" "/lib" "/lost+found" "/proc" "/run" "/snap" "/tmp" "/var" "/boot" "/home" "/lib64" "/media" "/opt" "/root" "/sbin" "/srv" "/sys" "/usr")

echo "Starting scan from: $START_FOLDER"
echo "Filter: >= ${MBFILTER} MB"
echo ""

# Create temporary file for results
TMP_FILE=$(mktemp)
trap "rm -f $TMP_FILE" EXIT

scan_folder() {
    local target="$1"
    if [ -d "$target" ]; then
        echo "Checking: $target"
        # Get size of this specific folder (not its subfolders)
        local size=$(du -BM -s "$target" 2>/dev/null | awk '{gsub(/M$/, "", $1); print $1}')
        if [ -n "$size" ] && [ "$size" -ge "$MBFILTER" ]; then
            echo "${size} $target" >> "$TMP_FILE"
        fi
    fi
}

if [ "$START_FOLDER" = "/" ]; then
    # Scan each predefined folder that exists
    for folder in "${ROOT_FOLDERS[@]}"; do
        scan_folder "$folder"
    done
else
    if [ ! -d "$START_FOLDER" ]; then
        echo "Error: '$START_FOLDER' is not a valid directory"
        exit 1
    fi
    # Get first-level subfolders of START_FOLDER
    for subfolder in "$START_FOLDER"/*/; do
        [ -d "$subfolder" ] && scan_folder "$subfolder"
    done
fi

echo ""
echo "Results:"
echo ""

# Sort temp file by size (descending) then format
sort -k1,1nr "$TMP_FILE" | awk '
BEGIN {
    printf "%-15s %s\n", "SIZE", "FOLDER"
    printf "%-15s %s\n", "---------------", "------"
}
{
    printf "%-15s %s\n", $1 " MB", $2
}'