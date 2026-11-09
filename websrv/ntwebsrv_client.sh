#!/bin/bash
#
# ntwebsrv_client.sh - Bash client for ntwebsrv (Automation Agent)
# Requires: curl, jq (optional, for pretty JSON output), sha256sum or shasum
#
# Supports:
#   - Legacy upload (multipart) to POST /ricevi
#   - JSON RPC commands to POST /api/command (save, exit, restart, reboot, poweroff, exec)
#   - Download to GET /api/download/{target}?zip_mode=true

set -euo pipefail

# Default values
DEFAULT_BASE_URL="http://localhost:8000"
DEFAULT_TIMEOUT=30
LANG_CODE="${LANG:-en_US}"

# Detect language
if [[ "$LANG_CODE" == it_* ]]; then
    LANG="it"
else
    LANG="en"
fi

# Detect sha256 command
if command -v sha256sum >/dev/null 2>&1; then
    SHA256_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
    SHA256_CMD="shasum -a 256"
else
    SHA256_CMD=""
fi

# Help text
show_help_it() {
    cat << 'EOF'
ntwebsrv_client.sh - Client Bash per ntwebsrv (Automation Agent)

USO:
    ./ntwebsrv_client.sh FILE_JSON [opzioni]           # Upload legacy o Comandi JSON
    ./ntwebsrv_client.sh --download TARGET [opzioni]   # Download file/cartella

ARGOMENTI:
    FILE_JSON            File JSON con i dati/comando (obbligatorio per upload/comandi)
    --download TARGET    Scarica file/cartella (non richiede FILE_JSON)

OPZIONI COMUNI:
    -u, --url URL        URL base server (default: http://localhost:8000)
    -k, --key KEY        Chiave segreta (header X-API-Key)
    -kh, --keyhash BASE  Segreto base per _kh (calcola SHA256(base + giorno))
    -t, --timeout SEC    Timeout in secondi (default: 30)
    -v, --verbose        Output verboso
    -h, --help           Questo help

OPZIONI DOWNLOAD:
    --zip                Zippa cartella al volo (richiede --download)
    -o, --output FILE    Nome file output (default: nome dal server)

MODALITÀ 1: LEGACY UPLOAD (multipart) - POST /ricevi
    JSON con "parametri" e/o "files":
    {
      "parametri": { "campo1": "valore1" },
      "files": { "documento": "/percorso/file.pdf" },
      "auth": { "key": "chiave", "keyhash": "base_secret" }
    }

MODALITÀ 2: COMANDI (JSON RPC) - POST /api/command
    JSON con "comando":
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "nome_script"}

MODALITÀ 3: DOWNLOAD - GET /api/download/{target}
    ./ntwebsrv_client.sh --download report.pdf -k "chiave"
    ./ntwebsrv_client.sh --download logs --zip -k "chiave"

AUTENTICAZIONE:
    - Header X-API-Key: <key|kh>  (o Authorization: Bearer <key|kh>)
    - "auth.keyhash" nel JSON è il segreto base (NON l'hash). Script calcola _kh = SHA256(base + giorno_corrente)
    - Opzioni CLI (-k/-kh) sovrascrivono "auth" nel JSON
    - Richiede sha256sum o shasum per calcolare _kh

ESEMPI:
    # Legacy upload
    ./ntwebsrv_client.sh upload.json -k "mia_chiave" -v
    
    # Comandi
    ./ntwebsrv_client.sh cmd_save.json -k "mia_chiave" -v
    ./ntwebsrv_client.sh cmd_exit.json -kh "mio_base_secret"
    
    # Download
    ./ntwebsrv_client.sh --download report.pdf -k "mia_chiave"
    ./ntwebsrv_client.sh --download logs --zip -k "mia_chiave"
EOF
}

show_help_en() {
    cat << 'EOF'
ntwebsrv_client.sh - Bash client for ntwebsrv (Automation Agent)

USAGE:
    ./ntwebsrv_client.sh JSON_FILE [options]           # Legacy upload or JSON commands
    ./ntwebsrv_client.sh --download TARGET [options]   # Download file/folder

ARGUMENTS:
    JSON_FILE            JSON file with data/command (required for upload/commands)
    --download TARGET    Download file/folder (no JSON_FILE required)

COMMON OPTIONS:
    -u, --url URL        Base server URL (default: http://localhost:8000)
    -k, --key KEY        Secret key (X-API-Key header)
    -kh, --keyhash BASE  Base secret for _kh (calculates SHA256(base + day))
    -t, --timeout SEC    Timeout in seconds (default: 30)
    -v, --verbose        Verbose output
    -h, --help           This help

DOWNLOAD OPTIONS:
    --zip                Zip folder on-the-fly (requires --download)
    -o, --output FILE    Output filename (default: from server)

MODE 1: LEGACY UPLOAD (multipart) - POST /ricevi
    JSON with "parametri" and/or "files":
    {
      "parametri": { "field1": "value1" },
      "files": { "document": "/path/file.pdf" },
      "auth": { "key": "secret", "keyhash": "base_secret" }
    }

MODE 2: COMMANDS (JSON RPC) - POST /api/command
    JSON with "comando":
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "script_name"}

MODE 3: DOWNLOAD - GET /api/download/{target}
    ./ntwebsrv_client.sh --download report.pdf -k "secret"
    ./ntwebsrv_client.sh --download logs --zip -k "secret"

AUTHENTICATION:
    - Header X-API-Key: <key|kh>  (or Authorization: Bearer <key|kh>)
    - "auth.keyhash" in JSON is base secret (NOT hash). Script calculates _kh = SHA256(base + current_day)
    - CLI options (-k/-kh) override JSON "auth"
    - Requires sha256sum or shasum for _kh calculation

EXAMPLES:
    # Legacy upload
    ./ntwebsrv_client.sh upload.json -k "my_key" -v
    
    # Commands
    ./ntwebsrv_client.sh cmd_save.json -k "my_key" -v
    ./ntwebsrv_client.sh cmd_exit.json -kh "my_base_secret"
    
    # Download
    ./ntwebsrv_client.sh --download report.pdf -k "my_key"
    ./ntwebsrv_client.sh --download logs --zip -k "my_key"
EOF
}

# Print error and exit
error_exit() {
    echo "ERROR: $1" >&2
    exit 1
}

# Print info
info() {
    [[ "$VERBOSE" == "true" ]] && echo "[INFO] $1"
}

# Print help and exit
show_help() {
    if [[ "$LANG" == "it" ]]; then
        show_help_it
    else
        show_help_en
    fi
    exit 0
}

# Calculate SHA256
calc_sha256() {
    local input="$1"
    if [[ "$SHA256_CMD" == "sha256sum" ]]; then
        echo -n "$input" | sha256sum | awk '{print $1}'
    elif [[ "$SHA256_CMD" == "shasum -a 256" ]]; then
        echo -n "$input" | shasum -a 256 | awk '{print $1}'
    else
        error_exit "sha256sum or shasum required for _kh calculation"
    fi
}

# Calculate _kh from base secret
calc_kh() {
    local base="$1"
    local day=$(date +%-d)  # day of month without leading zero
    calc_sha256 "${base}${day}"
}

# Parse arguments
JSON_FILE=""
BASE_URL="$DEFAULT_BASE_URL"
CLI_KEY=""
CLI_KH_BASE=""
TIMEOUT="$DEFAULT_TIMEOUT"
VERBOSE="false"
DOWNLOAD_TARGET=""
ZIP_MODE="false"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        -k|--key)
            CLI_KEY="$2"
            shift 2
            ;;
        -kh|--keyhash)
            CLI_KH_BASE="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        -h|--help)
            show_help
            ;;
        --download)
            DOWNLOAD_TARGET="$2"
            shift 2
            ;;
        --zip)
            ZIP_MODE="true"
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -*)
            error_exit "Unknown option: $1"
            ;;
        *)
            if [[ -z "$JSON_FILE" ]]; then
                JSON_FILE="$1"
            else
                error_exit "Multiple JSON files specified"
            fi
            shift
            ;;
    esac
done

# Check dependencies
command -v curl >/dev/null 2>&1 || error_exit "curl not found. Install curl."
HAS_JQ=false
command -v jq >/dev/null 2>&1 && HAS_JQ=true

# Build auth header
AUTH_HEADER=""
if [[ -n "$CLI_KH_BASE" ]]; then
    AUTH_KH=$(calc_kh "$CLI_KH_BASE")
    AUTH_HEADER="X-API-Key: $AUTH_KH"
    info "Using _kh authentication"
elif [[ -n "$CLI_KEY" ]]; then
    AUTH_HEADER="X-API-Key: $CLI_KEY"
    info "Using _k authentication"
fi

# DOWNLOAD MODE
if [[ -n "$DOWNLOAD_TARGET" ]]; then
    DOWNLOAD_URL="${BASE_URL%/}/api/download/${DOWNLOAD_TARGET}"
    [[ "$ZIP_MODE" == "true" ]] && DOWNLOAD_URL="${DOWNLOAD_URL}?zip_mode=true"
    
    info "Downloading from $DOWNLOAD_URL"
    
    CURL_ARGS=(-s -w "\n%{http_code}" --connect-timeout "$TIMEOUT" --max-time "$TIMEOUT")
    [[ -n "$AUTH_HEADER" ]] && CURL_ARGS+=(-H "$AUTH_HEADER")
    [[ -n "$OUTPUT_FILE" ]] && CURL_ARGS+=(-o "$OUTPUT_FILE") || CURL_ARGS+=(-O -J)
    
    RESPONSE=$(curl "${CURL_ARGS[@]}" "$DOWNLOAD_URL" 2>&1) || {
        CURL_EXIT=$?
        if [[ $CURL_EXIT -eq 28 ]]; then
            error_exit "Timeout (${TIMEOUT}s)"
        elif [[ $CURL_EXIT -eq 7 ]]; then
            error_exit "Connection failed (server unreachable)"
        else
            error_exit "curl failed with exit code $CURL_EXIT"
        fi
    }
    
    HTTP_BODY=$(echo "$RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
    
    info "HTTP Status: $HTTP_CODE"
    
    if [[ "$HTTP_CODE" -eq 200 ]]; then
        echo "SUCCESS: Downloaded"
        [[ "$HAS_JQ" == "true" && -n "$HTTP_BODY" ]] && echo "$HTTP_BODY" | jq . 2>/dev/null || true
        exit 0
    else
        echo "FAILED (HTTP $HTTP_CODE)"
        [[ "$HAS_JQ" == "true" && -n "$HTTP_BODY" ]] && echo "$HTTP_BODY" | jq . 2>/dev/null || echo "$HTTP_BODY"
        exit 1
    fi
fi

# REQUIRE JSON FILE for upload/command modes
[[ -z "$JSON_FILE" ]] && { show_help; error_exit "JSON file required (or use --download)"; }
[[ -f "$JSON_FILE" ]] || error_exit "JSON file not found: $JSON_FILE"

info "Reading JSON: $JSON_FILE"
JSON_CONTENT=$(cat "$JSON_FILE") || error_exit "Failed to read JSON file"

# Check if it's a command (has "comando" field)
IS_COMMAND_MODE=false
if [[ "$HAS_JQ" == "true" ]]; then
    if echo "$JSON_CONTENT" | jq -e '.comando' >/dev/null 2>&1; then
        IS_COMMAND_MODE=true
    fi
else
    # Basic check without jq
    if echo "$JSON_CONTENT" | grep -q '"comando"'; then
        IS_COMMAND_MODE=true
    fi
fi

# Build auth header from JSON if not overridden by CLI
if [[ -z "$AUTH_HEADER" ]]; then
    if [[ "$HAS_JQ" == "true" ]]; then
        JSON_KEY=$(echo "$JSON_CONTENT" | jq -r '.auth.key // ""')
        JSON_KH_BASE=$(echo "$JSON_CONTENT" | jq -r '.auth.keyhash // ""')
    else
        JSON_KEY=""
        JSON_KH_BASE=""
    fi
    [[ -n "$JSON_KH_BASE" ]] && AUTH_HEADER="X-API-Key: $(calc_kh "$JSON_KH_BASE")"
    [[ -n "$JSON_KEY" && -z "$AUTH_HEADER" ]] && AUTH_HEADER="X-API-Key: $JSON_KEY"
fi

if [[ "$IS_COMMAND_MODE" == "true" ]]; then
    # COMMAND MODE: POST /api/command with JSON
    COMMAND_URL="${BASE_URL%/}/api/command"
    info "Sending command to $COMMAND_URL"
    
    CURL_ARGS=(-s -w "\n%{http_code}" -X POST --connect-timeout "$TIMEOUT" --max-time "$TIMEOUT")
    [[ -n "$AUTH_HEADER" ]] && CURL_ARGS+=(-H "$AUTH_HEADER")
    CURL_ARGS+=(-H "Content-Type: application/json")
    CURL_ARGS+=(-d "$JSON_CONTENT")
    
    RESPONSE=$(curl "${CURL_ARGS[@]}" "$COMMAND_URL" 2>&1) || {
        CURL_EXIT=$?
        if [[ $CURL_EXIT -eq 28 ]]; then
            error_exit "Timeout (${TIMEOUT}s)"
        elif [[ $CURL_EXIT -eq 7 ]]; then
            error_exit "Connection failed (server unreachable)"
        else
            error_exit "curl failed with exit code $CURL_EXIT"
        fi
    }
    
    HTTP_BODY=$(echo "$RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
    
    info "HTTP Status: $HTTP_CODE"
    
    if [[ "$HTTP_CODE" -eq 200 ]]; then
        echo "SUCCESS"
        [[ "$HAS_JQ" == "true" ]] && echo "$HTTP_BODY" | jq . || echo "$HTTP_BODY"
        exit 0
    else
        echo "FAILED (HTTP $HTTP_CODE)"
        [[ "$HAS_JQ" == "true" ]] && echo "$HTTP_BODY" | jq . 2>/dev/null || echo "$HTTP_BODY"
        exit 1
    fi
else
    # LEGACY MODE: POST /ricevi multipart
    UPLOAD_URL="${BASE_URL%/}/ricevi"
    
    if [[ "$HAS_JQ" == "true" ]]; then
        PARAMETRI=$(echo "$JSON_CONTENT" | jq -c '.parametri // {}')
        FILES_JSON=$(echo "$JSON_CONTENT" | jq -c '.files // {}')
        AUTH_KEY=$(echo "$JSON_CONTENT" | jq -r '.auth.key // ""')
        AUTH_KH_BASE=$(echo "$JSON_CONTENT" | jq -r '.auth.keyhash // ""')
    else
        PARAMETRI="{}"
        FILES_JSON="{}"
        AUTH_KEY=""
        AUTH_KH_BASE=""
        echo "WARNING: jq not found - limited JSON parsing. Install jq for full support." >&2
    fi
    
    # CLI overrides for legacy auth (form fields _k/_kh)
    [[ -n "$CLI_KEY" ]] && AUTH_KEY="$CLI_KEY"
    [[ -n "$CLI_KH_BASE" ]] && AUTH_KH_BASE="$CLI_KH_BASE"
    
    # Calculate _kh for legacy form field
    LEGACY_KH=""
    if [[ -n "$AUTH_KH_BASE" ]]; then
        LEGACY_KH=$(calc_kh "$AUTH_KH_BASE")
    fi
    
    # Verify files exist
    MISSING_FILES=()
    FILE_ARGS=()
    
    if [[ "$HAS_JQ" == "true" ]]; then
        while IFS= read -r field; do
            path=$(echo "$FILES_JSON" | jq -r --arg f "$field" '.[$f]')
            if [[ -f "$path" ]]; then
                FILE_ARGS+=(-F "$field=@$path")
                info "File verified: $field -> $path"
            else
                MISSING_FILES+=("$field: $path")
            fi
        done < <(echo "$FILES_JSON" | jq -r 'keys[]')
    fi
    
    if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
        echo "ERROR: Missing files:" >&2
        for m in "${MISSING_FILES[@]}"; do
            echo "  - $m" >&2
        done
        exit 1
    fi
    
    # Build form data
    FORM_ARGS=()
    
    if [[ "$HAS_JQ" == "true" ]]; then
        while IFS= read -r key; do
            value=$(echo "$PARAMETRI" | jq -r --arg k "$key" '.[$k]')
            FORM_ARGS+=(-F "$key=$value")
        done < <(echo "$PARAMETRI" | jq -r 'keys[]')
    fi
    
    # Add legacy auth as form fields
    if [[ -n "$LEGACY_KH" ]]; then
        FORM_ARGS+=(-F "_kh=$LEGACY_KH")
    elif [[ -n "$AUTH_KEY" ]]; then
        FORM_ARGS+=(-F "_k=$AUTH_KEY")
    fi
    
    FORM_ARGS+=("${FILE_ARGS[@]}")
    
    if [[ ${#FORM_ARGS[@]} -eq 0 && ${#FILE_ARGS[@]} -eq 0 ]]; then
        error_exit "No parameters or files to send"
    fi
    
    info "Uploading to $UPLOAD_URL"
    info "Fields: ${#FORM_ARGS[@]} form, ${#FILE_ARGS[@]} files"
    
    CURL_ARGS=(-s -w "\n%{http_code}" -X POST --connect-timeout "$TIMEOUT" --max-time "$TIMEOUT")
    [[ -n "$AUTH_HEADER" ]] && CURL_ARGS+=(-H "$AUTH_HEADER")
    CURL_ARGS+=("${FORM_ARGS[@]}")
    
    RESPONSE=$(curl "${CURL_ARGS[@]}" "$UPLOAD_URL" 2>&1) || {
        CURL_EXIT=$?
        if [[ $CURL_EXIT -eq 28 ]]; then
            error_exit "Timeout (${TIMEOUT}s)"
        elif [[ $CURL_EXIT -eq 7 ]]; then
            error_exit "Connection failed (server unreachable)"
        else
            error_exit "curl failed with exit code $CURL_EXIT"
        fi
    }
    
    HTTP_BODY=$(echo "$RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
    
    info "HTTP Status: $HTTP_CODE"
    
    if [[ "$HTTP_CODE" -eq 200 ]]; then
        echo "SUCCESS"
        [[ "$HAS_JQ" == "true" ]] && echo "$HTTP_BODY" | jq . || echo "$HTTP_BODY"
        exit 0
    else
        echo "FAILED (HTTP $HTTP_CODE)"
        [[ "$HAS_JQ" == "true" ]] && echo "$HTTP_BODY" | jq . 2>/dev/null || echo "$HTTP_BODY"
        exit 1
    fi
fi