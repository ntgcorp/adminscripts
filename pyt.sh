#!/bin/bash
# pyt.sh - Launcher Linux per pyt.py (counterpart di pyt.cmd)
# VERSIONE 20261007

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Path assoluto come pyt.cmd (%~dp0): funziona da qualsiasi directory di lavoro
PYSCRIPT="$SCRIPT_DIR/pyt.py"

# Check if first parameter is a path to pyn.sh
if [ -f "$1" ]; then
    PYN="$1"
    shift
else
    PYN="$SCRIPT_DIR/pyn.sh"
fi

# Execute passing all parameters
exec "$PYN" "$PYSCRIPT" "$@"