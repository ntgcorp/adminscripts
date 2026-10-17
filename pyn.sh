#!/bin/bash
# pyn.sh - Launcher Linux per Python portable / PODMAN / CHROME / BASH / PANDOC
# VERSIONE 20261011 - podman export <image> <file.tar> (save) e import <file.tar> (load)
# VERSIONE 20261015 - podman stop (tutti) e reset (rm -f tutti); help mirato pip-podman-pandoc
# VERSIONE 20261014 - podman list image rinominato images
# VERSIONE 20261011 - Direttiva pod rinominata podman: machine start|stop, crun, cstop, image set (export POD_IMAGE), list; tolti x/end/start; stub pod
# VERSIONE 20261010 - Convenzione CLI: rimossa riga Python Path; ogni esecuzione stampa CLI: + stringa comando
# VERSIONE 20261009 - pys: esegue script python (nomi semplici in SCRIPT_DIR) col python calcolato
# VERSIONE 20260911 - Counterpart Linux di pyn.cmd (traduzione bash di pyn.cmd:28-164)
# VERSIONE 20260830 - Accelerazione ricerca PY_PATH con early-exit
# VERSIONE 20260810 - REFACTOR bug critici (delayed expansion, doppia exec, path hardcoded) + uscite OS-specifiche
set -e

PYN_VER="20261015"

# --- SETUP ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_TYPE="${PY_TYPE:-X64}"
PY_ENV="${PY_ENV:-myenv}"
PATH_SCRIPTS="${PATH_SCRIPTS:-/mnt/gdrive/Scripts}"
# Normalizza: senza slash finale (tranne radice /)
if [ "$PATH_SCRIPTS" != "/" ]; then PATH_SCRIPTS="${PATH_SCRIPTS%/}"; fi
PAR1="$1"
PAR2="$2"

# Dispatch comandi che non richiedono Python (come pyn.cmd:38-43 prima di SETUP)
case "$1" in
    podman) POD_CMD="$2"; shift 2 || true; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --pod-internal \"$POD_CMD\" \"\$@\"" -- "$@" ;;
    pandoc) PANDOC_CMD="$2"; shift 2 || true; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --pandoc-internal \"\$@\"" -- "$@" ;;
    b)      shift; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --bash-internal \"\$@\"" -- "$@" ;;
    chrome) shift; exec bash -c "source \"$SCRIPT_DIR/pyn.sh\" --chrome-internal \"\$@\"" -- "$@" ;;
    help)
        case "$2" in
            pip)
                cat <<'EOS'
PYN.SH pip check CHECK PIP
PYN.SH pip pc CACHE PURGE
PYN.SH pip dna RIMUOVE dna precedente installa errato
PYN.SH pip pu Upgrade solo pip
PYN.SH pip i install librerie (solo binari)
PYN.SH pip u upgrade singolo (dry-run, solo binari)
PYN.SH pip ulist Lista pipupgrade.txt
PYN.SH pip uexec Esegue upgrade da pipupgrade.txt
PYN.SH pip re Crea requirements_x32/x64.txt
PYN.SH pip ri Importa requirements.txt
EOS
                exit 0
                ;;
            podman)
                cat <<'EOS'
PYN.SH podman machine start-stop. Gestione macchina podman
PYN.SH podman crun nome_container nome_immagine [args]. Esegue container con nome
PYN.SH podman cstop nome_container. Ferma il container
PYN.SH podman stop. Ferma tutti i container attivi
PYN.SH podman reset. Rimuove tutti i container (anche fermi)
PYN.SH podman image set nome_immagine. Imposta POD_IMAGE
PYN.SH podman list machines-images-containers. Elenca oggetti podman
PYN.SH podman export nome_immagine file.tar. Esporta immagine in file tar
PYN.SH podman import file.tar. Importa immagine da file tar
EOS
                exit 0
                ;;
            pandoc)
                cat <<'EOS'
PYN.SH pandoc doc2md|docx2md|pdf2md|md2html file
EOS
                exit 0
                ;;
            "") exec "$SCRIPT_DIR/pyn.sh" ;;
            *) echo "[ERRORE] help: sotto-parametri validi pip-podman-pandoc." >&2; exec "$SCRIPT_DIR/pyn.sh" ;;
        esac
        ;;
    "")     # help
            echo "Launcher: PYTHON PIP/PODMAN/CHROME/BASH/PANDOC. R: $PYN_VER"
            cat <<'EOS'
Sintassi PYN.SH script.py [parametri] oppure PYN.SH dominio comando parametri
----- Comandi Estesi. Sintassi pyn dominio parametri_aggiuntivi
PYN.SH py [comando esteso]
PYN.SH py script nome_script e parametri successivi
PYN.SH py env ambiente - Cambio o Attivazione Python ENV
PYN.SH py version - Versione Python
PYN.SH py mod modulo [args] (python -m modulo)
PYN.SH py test esegue test_python.py da PATH_SCRIPTS con parametri successivi
PYN.SH help pip-podman-pandoc. Help mirato per direttiva
PYN.SH chrome auto
PYN.SH b script.sh parametri (esegue uno script bash su Linux)
EOS
            exit 0
            ;;
esac

# Se invocato come --xxx-internal (ricorsione), salta setup e vai diretto
if [[ "$1" == --pod-internal ]]; then
    POD_SUB="$2"; shift 2 || true
    case "$POD_SUB" in
        machine)
            case "$1" in
                start) echo "CLI: podman machine start"; exec podman machine start ;;
                stop) echo "CLI: podman machine stop"; exec podman machine stop ;;
                *) echo "[ERRORE] podman machine richiede start o stop." >&2; exit 1 ;;
            esac
            ;;
        crun)
            if [ -z "$1" ] || [ -z "$2" ]; then echo "[ERRORE] uso: podman crun <container_name> <image_name> [args]" >&2; exit 1; fi
            echo "CLI: podman run -it --rm --name $1 $2 ${*:3}"
            exec podman run -it --rm --name "$1" "$2" "${@:3}"
            ;;
        cstop)
            if [ -z "$1" ]; then echo "[ERRORE] uso: podman cstop <container_name>" >&2; exit 1; fi
            echo "CLI: podman stop $1"
            exec podman stop "$1"
            ;;
        stop)
            IDS=$(podman ps -q)
            if [ -z "$IDS" ]; then echo "Nessun container attivo."; exit 0; fi
            echo "CLI: podman stop $IDS"
            # shellcheck disable=SC2086
            exec podman stop $IDS
            ;;
        reset)
            IDS=$(podman ps -a -q)
            if [ -z "$IDS" ]; then echo "Nessun container da rimuovere."; exit 0; fi
            echo "CLI: podman rm -f $IDS"
            exec podman rm -f $IDS
            ;;
        image)
            if [[ "$1" == "set" ]]; then
                shift || true
                if [ -z "$1" ]; then echo "[ERRORE] uso: podman image set <image_name>" >&2; exit 1; fi
                export POD_IMAGE="$1"
                echo "POD_IMAGE=$POD_IMAGE"
                exit 0
            fi
            echo "[ERRORE] podman image richiede set <image_name>." >&2; exit 1
            ;;
        list)
            case "$1" in
                machines) echo "CLI: podman machine list"; exec podman machine list ;;
                images) echo "CLI: podman images"; exec podman images ;;
                containers) echo "CLI: podman ps -a"; exec podman ps -a ;;
                all)
                    echo "CLI: podman machine list"; podman machine list
                    echo "CLI: podman images"; podman images
                    echo "CLI: podman ps -a"; podman ps -a
                    exit 0
                    ;;
                *) echo "[ERRORE] podman list richiede machines|images|containers|all." >&2; exit 1 ;;
            esac
            ;;
        export)
            if [ -z "$1" ] || [ -z "$2" ]; then echo "[ERRORE] uso: podman export <image_name> <file.tar>" >&2; exit 1; fi
            echo "CLI: podman save --output $2 $1"
            exec podman save --output "$2" "$1"
            ;;
        import)
            if [ -z "$1" ]; then echo "[ERRORE] uso: podman import <file.tar>" >&2; exit 1; fi
            if [ ! -f "$1" ]; then echo "[ERRORE] File tar non trovato: $1" >&2; exit 1; fi
            echo "CLI: podman load --input $1"
            exec podman load --input "$1"
            ;;
        opt)
            echo "[USCITA OS-SPECIFICA] Optimize-VHD è Windows/Hyper-V only. Su Linux usa 'fstrim -av' o 'qemu-img convert'." >&2
            echo "[1/2] fstrim..."; sudo fstrim -av || true
            exit 0
            ;;
        "") echo "[ERRORE] podman richiede sottocomando" >&2; exit 1 ;;
        *) echo "CLI: podman $POD_SUB $*"; exec podman "$POD_SUB" "$@" ;;
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
            echo "CLI: $PANDOC $SRC_FILE -f $fmt -t markdown -o $OUT_MD"
            exec "$PANDOC" "$SRC_FILE" -f "$fmt" -t markdown -o "$OUT_MD"
            ;;
        md2html)
            if [ ! -f "$SRC_FILE" ]; then echo "[ERRORE] File non trovato: $SRC_FILE" >&2; exit 1; fi
            OUT_HTML="${SRC_FILE%.*}.html"
            echo "CLI: $PANDOC $SRC_FILE -o $OUT_HTML"
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
    echo "CLI: $SH_EXEC $SH_NAME $*"
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
        echo "CLI: $CH_CMD --remote-debugging-port=9222 --user-data-dir=$HOME/chromedata"
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
if [ -z "$PY_PATH" ]; then echo "PYN: Attenzione, non esiste la cartella PYTHON${PY_TYPE} richiesta" >&2; exit 1; fi

# PY_CMD su Linux: venv bin/python, non Scripts\PYTHON.EXE
PY_CMD="$PY_PATH/$PY_ENV/bin/python3"
if [ ! -x "$PY_CMD" ]; then PY_CMD="$PY_PATH/$PY_ENV/bin/python"; fi
PY_PIP="$PY_CMD -m pip"

# --- Dispatch Python ---
# pip: direttiva con sub-direttive (check|pc|dna|pu|i|u|ulist|uexec|re|ri) + passthrough
if [[ "$1" == "pip" ]]; then
    shift
    SUB="$1"
    case "$SUB" in
        check) exec $PY_CMD -m pip check ;;
        dna) rm -rf "$PY_PATH/lib/python"*/site-packages/~dna 2>/dev/null; rm -rf "$PY_PATH/$PY_ENV/lib/python"*/site-packages/~dna 2>/dev/null; exit 0 ;;
        pc) exec $PY_CMD -m pip cache purge ;;
        pu) exec $PY_CMD -m pip install --upgrade pip ;;
        i) shift; exec $PY_CMD -m pip install --upgrade --only-binary=:all: "$@" ;;
        u) shift; exec $PY_CMD -m pip install "$1" --upgrade --dry-run --only-binary=:all: ;;
        ulist)
            echo "Raccolta pacchetti obsoleti..."
            $PY_CMD -m pip list --outdated > /tmp/pip_raw.txt
            echo "Generazione pipupgrade.txt..."
            rm -f pipupgrade.txt
            awk 'NR>2 {print $1}' /tmp/pip_raw.txt >> pipupgrade.txt
            rm -f /tmp/pip_raw.txt
            echo "Operazione completata! Trovi elenco in: pipupgrade.txt"
            exit 0
            ;;
        uexec)
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
        re)
            $PY_CMD -m pip freeze > "requirements_${PY_TYPE}.txt"
            awk -F== '{print $1}' "requirements_${PY_TYPE}.txt" > "requirements_${PY_TYPE}_LIGHT.txt"
            exit 0
            ;;
        ri)
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
        "") echo "[ERRORE] pip richiede sub-direttiva" >&2; exit 1 ;;
        *) exec $PY_CMD -m pip "$SUB" "$@" ;;
    esac
fi

# pymod spostato in py: usa py mod <modulo>
if [[ "$1" == "pymod" ]]; then
    echo "[ERRORE] pymod spostato in py: usa py mod <modulo> [args]" >&2; exit 1
fi

# x rinominata in py
if [[ "$1" == "x" ]]; then
    echo "[ERRORE] direttiva x rinominata in py: usa py <comando>" >&2; exit 1
fi

# File esistente -> RUN
if [ -f "$1" ]; then
    if [ ! -x "$PY_CMD" ]; then echo "PYN: python venv non trovato: $PY_CMD" >&2; exit 1; fi
    echo "CLI: $PY_CMD $PAR1 $PAR2 $3 $4 $5 $6 $7 $8 $9"
    exec "$PY_CMD" "$PAR1" "$PAR2" "$3" "$4" "$5" "$6" "$7" "$8" "$9"
fi

# py subcommands (ex x)
if [[ "$1" == "py" ]]; then
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
        pip|pip_*) echo "[ERRORE] py $SUB spostato in pip: usa pip <sub> (es. pip check)" >&2; exit 1 ;;
        test)
            shift 2
            PYTEST_SCRIPT="$PATH_SCRIPTS/test_python.py"
            if [ ! -f "$PYTEST_SCRIPT" ]; then echo "[ERRORE] test_python.py non trovato in: $PATH_SCRIPTS" >&2; exit 1; fi
            echo "CLI: $PY_CMD $PYTEST_SCRIPT $*"
            exec "$PY_CMD" "$PYTEST_SCRIPT" "$@"
            ;;
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
        "") echo "COMANDO ESTESO (py) NON INSERITO" >&2; exit 1 ;;
        *) echo "[ERRORE] py sottocomando $SUB non riconosciuto" >&2; exit 1 ;;
    esac
fi

echo "PYN: comando non riconosciuto: $1" >&2
exit 1
