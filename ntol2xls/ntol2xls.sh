#!/bin/bash
# Recupera il nome del file Python a partire dal nome dello script bash
# Rimuove percorso e qualsiasi estensione (es. .sh, .bash)
script_name=$(basename "$0" | sed 's/\.[^.]*$//')
PYSCRIPT="${script_name}.py"

PYN="python3"

echo "\"$PYN\" \"$PYSCRIPT\" $@"
exec "$PYN" "$PYSCRIPT" "$@"