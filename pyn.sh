#!/bin/bash
# pyn.sh - Launcher Linux per Python portable / PODMAN / CHROME / BASH / PANDOC
# VERSIONE 20260911 - Counterpart Linux di pyn.cmd (traduzione bash di pyn.cmd:28-164)
# VERSIONE 20260830 - Accelerazione ricerca PY_PATH con early-exit
# VERSIONE 20260810 - REFACTOR bug critici (delayed expansion, doppia exec, path hardcoded) + uscite OS-specifiche
set -e

PYN_VER="20260911"

# --- SETUP ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_TYPE="${PY_TYPE:-X64}"
PY_ENV="${PY_ENV:-myenv}"
PAR1="$1"
PAR2="$2"

# Dispatch comandi che non richiedono Python (come pyn.cmd:38-43 prima di SETUP)
case "$1" in
    pod)    POD_CMD="$2"; shift 2 || true; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --pod-internal \"$POD_CMD\" \"\$@\"" -- "$@" ;;
    pandoc) PANDOC_CMD="$2"; shift 2 || true; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --pandoc-internal \"\$@\"" -- "$@" ;;
    b)      shift; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --bash-internal \"\$@\"" -- "$@" ;;
    chrome) shift; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --chrome-internal \"\$@\"" -- "$@" ;;
    "")     # help
            cat <<'EOS'
SCRIPT PYN.SH di lancio PYTHON PORTABLE. X64 o X32 / PODMAN / CHROME / BASH / PANDOC - 20260911
Sintassi PYN.SH script.py [parametri] oppure PYN.SH dominio comando parametri
----- Comandi Dominio Python (Dominio Base), x
PYN.SH x [comando esteso]
PYN.SH x script nome_script e parametri successivi
PYN.SH x env ambiente - Cambio o Attivazione Python ENV
PYN.SH x version - Versione Python
PYN.SH x pip richiamo mod pip [comandi]
PYN.SH x pip_check CHECK PIP
PYN.SH x pip_pc CACHE PURGE
PYN.SH x pip_pu Upgrade solo pip
PYN.SH x pip_i install librerie
PYN.SH x pip_u upgrade singolo
PYN.SH x pip_ulist Lista pipupgrade.txt
PYN.SH x pip_uexec Esegue upgrade da pipupgrade.txt
PYN.SH x pip_re Crea requirements_x32/x64.txt
PYN.SH x pip_ri Importa requirements.txt
PYN.SH x mod modulo
----- Comandi POD/PANDOC/BASH/CHROME/PIP
PYN.SH pip [comando pip]
PYN.SH chrome auto
PYN.SH pod comando
PYN.SH pod end/start/opt
PYN.SH pandoc doc2md|docx2md|pdf2md|md2html file
PYN.SH b script.sh parametri
EOS
            exit 0
            ;;
esac

# Se invocato come --xxx-internal (ricorsione), salta setup e vai diretto
if [[ "$1" == --pod-internal ]]; then
    POD_SUB="$2"; shift 2 || true
    case "$POD_SUB" in
        x) echo "Podman Esecuzione Python ntjobsos Script"; exec podman run -it --rm -v "${POD_PATH:-c:\podman}:/app" "${POD_APP:-ntjobsos}:v1" "$@" ;;
        start) echo "Podman Esecuzione motore"; exec podman machine start ;;
        end)
            if ! command -v podman >/dev/null 2>&1; then
                echo "[USCITA OS-SPECIFICA] podman non trovato. Su Linux nativo usa 'systemctl --user stop podman' o 'podman machine stop'." >&2; exit 1
            fi
            echo "Podman Stop"; podman machine stop 2>/dev/null || true
            exit 0
            ;;
        opt)
            echo "[USCITA OS-SPECIFICA] Optimize-VHD è Windows/Hyper-V only. Su Linux usa 'fstrim -av' o 'qemu-img convert'." >&2
            echo "[1/2] fstrim..."; sudo fstrim -av || true
            exit 0
            ;;
        "") echo "[ERRORE] pod richiede sottocomando" >&2; exit 1 ;;
        *) echo "Podman Esecuzione Standard"; exec podman "$POD_SUB" "$@" ;;
    esac
fi

if [[ "$1" == --pandoc-internal ]]; then
    ACTION="$1"; FILE_MD="$2"
    # Ricerca pandoc su Linux
    PANDOC=""
    for p in "/usr/bin/pandoc" "/usr/local/bin/pandoc" "$HOME/_Applic/Pandoc/pandoc" "/opt/pandoc/pandoc"; do
        if [ -x "$p" ]; then PANDOC="$p"; break; fi
    done
    if [ -z "$PANDOC" ] && command -v pandoc >/dev/null 2>&1; then PANDOC="$(command -v pandoc)"; fi
    if [ -z "$PANDOC" ] || [ ! -x "$PANDOC" ]; then echo "[ERRORE] pandoc non trovato" >&2; exit 1; fi
    ACTION="$1"; SRC_FILE="$2"
    if [ -z "$ACTION" ]; then echo "[ERRORE] Manca azione" >&2; exit 1; fi
    case "${ACTION,,}" in
        pdf2md|docx2md|doc2md)
            if [ ! -f "$SRC_FILE" ]; then echo "[ERRORE] File non trovato: $SRC_FILE" >&2; exit 1; fi
            OUT_MD="${SRC_FILE%.*}.md"
            fmt="docx"; [[ "${ACTION,,}" == "pdf2md" ]] && fmt="pdf"
            exec "$PANDOC" "$SRC_FILE" -f "$fmt" -t markdown -o "$OUT_MD"
            ;;
        md2html)
            if [ ! -f "$SRC_FILE" ]; then echo "[ERRORE] File non trovato: $SRC_FILE" >&2; exit 1; fi
            OUT_HTML="${SRC_FILE%.*}.html"
            exec "$PANDOC" "$SRC_FILE" -o "$OUT_HTML"
            ;;
        *) echo "[ERRORE] Azione $ACTION non riconosciuta" >&2; exit 1 ;;
    esac
fi

if [[ "$1" == --bash-internal ]]; then
    SH_NAME="$1"
    if [ -z "$SH_NAME" ]; then echo "[ERRORE] Manca script bash" >&2; exit 1; fi
    SH_EXEC=""
    for b in "/bin/bash" "/usr/bin/bash" "/opt/BASH/bash"; do
        if [ -x "$b" ]; then SH_EXEC="$b"; break; fi
    done
    if [ -z "$SH_EXEC" ]; then echo "[ERRORE] bash non trovato" >&2; exit 1; fi
    echo "Esecuzione: $SH_EXEC $SH_NAME $@"
    exec "$SH_EXEC" "$SH_NAME" "$@"
fi

if [[ "$1" == --chrome-internal ]]; then
    if [ -z "$1" ]; then echo "[ERRORE] chrome richiede 'auto'" >&2; exit 1; fi
    CH_CMD=""
    for c in "/usr/bin/google-chrome" "/usr/bin/google-chrome-stable" "/usr/bin/chromium-browser" "/usr/bin/chromium" "/snap/bin/chromium"; do
        if [ -x "$c" ]; then CH_CMD="$c"; break; fi
    done
    if [ -z "$CH_CMD" ]; then echo "[ERRORE] chrome/chromium non trovato" >&2; exit 1; fi
    if [[ "$1" == "auto" ]]; then
        echo "[INFO] Avvio Chrome debug..."
        exec "$CH_CMD" --remote-debugging-port=9222 --user-data-dir="$HOME/chromedata"
    fi
    exit 0
fi

# --- Calcolo PY_PATH (traduzione pyn.cmd:45-80) ---
PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PATHP_01="$HOME/APPLIC/PYTHON${PY_TYPE}"
PATHP_02="/opt/APPLIC/PYTHON${PY_TYPE}"
PATHP_03="/mnt/k/Tools/Python${PY_TYPE}"
# Fallback legacy Windows mount su Linux
if [ ! -d "$PATHP_03" ] && [ -d "/k/Tools/Python${PY_TYPE}" ]; then PATHP_03="/k/Tools/Python${PY_TYPE}"; fi
PATHP_XX="$PARENT_DIR/TOOLS/PYTHON${PY_TYPE}"

PY_PATH=""

# Caso VDI.MACH0 - priorita assoluta a K: se flag esiste e path valido
if [ -f "/mnt/k/MACH0_PROD.TXT" ] || [ -f "/k/MACH0_PROD.TXT" ] || [ -f "K:/MACH0_PROD.TXT" ]; then
    for cand in "$PATHP_03/bin/python3" "$PATHP_03/bin/python" "$PATHP_03/python3" "$PATHP_03/python"; do
        if [ -x "$cand" ]; then PY_PATH="$PATHP_03"; break; fi
    done
    if [ -z "$PY_PATH" ] && [ -d "$PATHP_03" ]; then PY_PATH="$PATHP_03"; fi
fi

# Override PATHP_ENV se definito
if [ -z "$PY_PATH" ] && [ -n "$PATHP_ENV" ]; then
    for cand in "$PATHP_ENV/bin/python3" "$PATHP_ENV/bin/python" "$PATHP_ENV/python3" "$PATHP_ENV/python"; do
        if [ -x "$cand" ]; then PY_PATH="$PATHP_ENV"; break; fi
    done
    if [ -z "$PY_PATH" ] && [ -d "$PATHP_ENV" ]; then PY_PATH="$PATHP_ENV"; fi
fi

# Ricerca in ordine D:->C:->K:->XX (mappati su Linux)
if [ -z "$PY_PATH" ]; then
    for cand_path in "$PATHP_01" "$PATHP_02" "$PATHP_03" "$PATHP_XX"; do
        for bin in "$cand_path/bin/python3" "$cand_path/bin/python" "$cand_path/python3" "$cand_path/python"; do
            if [ -x "$bin" ]; then PY_PATH="$cand_path"; break 2; fi
        done
        if [ -d "$cand_path" ] && [ -n "$(ls -A "$cand_path" 2>/dev/null)" ]; then PY_PATH="$cand_path"; break; fi
    done
fi

echo "LAUNCHER PYTHON PORTABLE NTGCORP $PYN_VER: Tipo $PY_TYPE: Path: $PY_PATH Env: $PY_ENV"
if [ -n "$PY_PATH" ]; then echo "Python Path: $PY_PATH"; fi
if [ -z "$PY_PATH" ]; then echo "PYN: Attenzione, non esiste la cartella PYTHON${PY_TYPE} richiesta" >&2; exit 1; fi

# PY_CMD su Linux: venv bin/python, non Scripts\PYTHON.EXE
PY_CMD="$PY_PATH/$PY_ENV/bin/python3"
if [ ! -x "$PY_CMD" ]; then PY_CMD="$PY_PATH/$PY_ENV/bin/python"; fi
PY_PIP="$PY_CMD -m pip"

# --- Dispatch Python ---
# pip diretto: pyn.sh pip <args>
if [[ "$1" == "pip" ]]; then
    shift
    exec $PY_CMD -m pip "$@"
fi

# File esistente -> RUN
if [ -f "$1" ]; then
    if [ ! -x "$PY_CMD" ]; then echo "PYN: python venv non trovato: $PY_CMD" >&2; exit 1; fi
    echo "START PYTHON SCRIPT: $0 - $PY_CMD - $PAR1 $PAR2 $3 $4 $5 $6 $7 $8 $9"
    exec "$PY_CMD" "$PAR1" "$PAR2" "$3" "$4" "$5" "$6" "$7" "$8" "$9"
fi

# x subcommands
if [[ "$1" == "x" ]]; then
    SUB="$2"
    case "$SUB" in
        env)
            if [ -z "$3" ]; then echo "Manca nome ambiente" >&2; exit 1; fi
            PY_ENV="$3"
            if [ -d "$PY_PATH/$PY_ENV" ]; then echo "Ambiente $PY_ENV trovato."; exit 0; fi
            echo "Ambiente $PY_ENV non trovato. Creazione in corso..."
            PY_BASE="$PY_PATH/bin/python3"
            [ -x "$PY_BASE" ] || PY_BASE="$PY_PATH/bin/python"
            [ -x "$PY_BASE" ] || PY_BASE="python3"
            exec "$PY_BASE" -m venv "$PY_PATH/$PY_ENV"
            ;;
        script)
            shift 2
            EXE="$1"; shift || true
            if [ -z "$EXE" ]; then echo "Manca exe" >&2; exit 1; fi
            exec "$PY_PATH/$PY_ENV/bin/$EXE" "$@"
            ;;
        mod) shift 2; exec $PY_CMD -m "$@" ;;
        pip) shift 2; exec $PY_CMD -m pip "$@" ;;
        version) exec $PY_CMD --version ;;
        pip_check) exec $PY_CMD -m pip check ;;
        pip_dna) rm -rf "$PY_PATH/lib/python"*/site-packages/~dna 2>/dev/null; rm -rf "$PY_PATH/$PY_ENV/lib/python"*/site-packages/~dna 2>/dev/null; exit 0 ;;
        pip_pc) exec $PY_CMD -m pip cache purge ;;
        pip_pu) exec $PY_CMD -m pip install --upgrade pip ;;
        pip_i) shift 2; exec $PY_CMD -m pip install --upgrade --only-binary=:all: "$@" ;;
        pip_u) shift 2; exec $PY_CMD -m pip install "$1" --upgrade --dry-run --only-binary=:all: ;;
        pip_ulist)
            echo "Raccolta pacchetti obsoleti..."
            $PY_CMD -m pip list --outdated > /tmp/pip_raw.txt
            echo "Generazione pipupgrade.txt..."
            rm -f pipupgrade.txt
            awk 'NR>2 {print $1}' /tmp/pip_raw.txt >> pipupgrade.txt
            rm -f /tmp/pip_raw.txt
            echo "Operazione completata! Trovi elenco in: pipupgrade.txt"
            exit 0
            ;;
        pip_uexec)
            LOGFILE="pipupgrade.log"
            echo "Inizio aggiornamento: $(date)" > "$LOGFILE"
            while IFS= read -r p || [ -n "$p" ]; do
                [ -z "$p" ] && continue
                echo "------------------------------------------"
                echo "Aggiornamento: $p"
                echo "------------------------------------------"
                if $PY_CMD -m pip install --upgrade "$p" >> "$LOGFILE" 2>&1; then
                    echo "[OK] $p aggiornato" >> "$LOGFILE"
                else
                    echo "[ERRORE] $p non aggiornato" >> "$LOGFILE"
                fi
            done < pipupgrade.txt
            echo "Processo terminato. Controlla $LOGFILE"
            exit 0
            ;;
        pip_re)
            $PY_CMD -m pip freeze > "requirements_${PY_TYPE}.txt"
            awk -F== '{print $1}' "requirements_${PY_TYPE}.txt" > "requirements_${PY_TYPE}_LIGHT.txt"
            exit 0
            ;;
        pip_ri)
            REQ_FILE="requirements_${PY_TYPE}.txt"
            SKIPPED=""
            while IFS= read -r line || [ -n "$line" ]; do
                [[ "$line" =~ ^#.* ]] && continue
                [[ -z "$line" ]] && continue
                echo "Installando $line..."
                if $PY_CMD -m pip install --upgrade --only-binary=:all: "$line" >/dev/null 2>&1; then
                    echo "  OK: $line"
                else
                    echo "  SALTATO: $line"
                    SKIPPED="$SKIPPED $line"
                fi
            done < "$REQ_FILE"
            echo "--- Pacchetti saltati ---"
            if [ -z "$SKIPPED" ]; then echo "  Nessuno"; else for p in $SKIPPED; do echo "  - $p"; done; fi
            exit 0
            ;;
        upgrade)
            $PY_CMD -m pip install --upgrade pip
            $PY_CMD -m pip list --outdated
            exit 0
            ;;
        "") echo "COMANDO ESTESO (x) NON INSERITO" >&2; exit 1 ;;
        *) echo "[ERRORE] x sottocomando $SUB non riconosciuto" >&2; exit 1 ;;
    esac
fi

echo "PYN: comando non riconosciuto: $1" >&2
exit 1
