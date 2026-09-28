#!/usr/bin/env bash
#
# migrate.sh - Script di Backup & Restore per Zorin OS / Ubuntu / Debian
# Uso: ./migrate.sh [backup|restore] /percorso/cartella_destinazione
#

set -euo pipefail

# ------------------------------------------------------------------------------
# 0. PARAMETRI E LOGGING
# ------------------------------------------------------------------------------
ACTION="${1:-}"
TARGET_DIR="${2:-}"

if [[ -z "$ACTION" || -z "$TARGET_DIR" || ( "$ACTION" != "backup" && "$ACTION" != "restore" ) ]]; then
    echo "Uso errato dello script!"
    echo "Sintassi: $0 [backup|restore] /percorso/cartella_salvataggio"
    exit 1
fi

# Normalizzazione del percorso di destinazione/sorgente
TARGET_DIR="$(realpath -m "$TARGET_DIR")"
LOG_FILE="${TARGET_DIR}/migrate_${ACTION}.log"

# Creazione cartella base e log
mkdir -p "$TARGET_DIR"

# Funzione di Logging con Timestamp
log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $msg" | tee -a "$LOG_FILE"
}

log "INFO" "=================================================="
log "INFO" "Avvio procedura di: ${ACTION^^}"
log "INFO" "Cartella target: $TARGET_DIR"
log "INFO" "=================================================="

# Definizione Subfolders
DIR_APT="${TARGET_DIR}/1_apt"
DIR_FLATPAK="${TARGET_DIR}/2_flatpak"
DIR_SNAP="${TARGET_DIR}/3_snap"
DIR_HOME="${TARGET_DIR}/4_home"
DIR_CONFIG="${TARGET_DIR}/5_settings"

# ------------------------------------------------------------------------------
# 1. FUNZIONE DI BACKUP
# ------------------------------------------------------------------------------
do_backup() {
    log "INFO" "Inizio fase di Backup..."

    # 1. Pacchetti APT
    log "INFO" "[1/5] Salvataggio lista pacchetti APT..."
    mkdir -p "$DIR_APT"
    dpkg --get-selections > "${DIR_APT}/package.list"
    apt-mark showmanual > "${DIR_APT}/manual_packages.txt"
    if [ -d /etc/apt/sources.list.d ]; then
        cp -r /etc/apt/sources.list.d "${DIR_APT}/" 2>/dev/null || true
    fi
    if [ -f /etc/apt/sources.list ]; then
        cp /etc/apt/sources.list "${DIR_APT}/" 2>/dev/null || true
    fi
    log "INFO" "[1/5] Backup APT completato."

    # 2. Flatpak
    log "INFO" "[2/5] Salvataggio lista pacchetti Flatpak..."
    mkdir -p "$DIR_FLATPAK"
    if command -v flatpak &>/dev/null; then
        flatpak list --app --columns=application > "${DIR_FLATPAK}/flatpak_apps.txt" || true
        log "INFO" "[2/5] Backup Flatpak completato."
    else
        log "WARN" "[2/5] Flatpak non installato nel sistema. Saltato."
    fi

    # 3. Snap
    log "INFO" "[3/5] Salvataggio lista pacchetti Snap..."
    mkdir -p "$DIR_SNAP"
    if command -v snap &>/dev/null; then
        snap list | awk '{print $1}' | tail -n +2 > "${DIR_SNAP}/snap_apps.txt" || true
        log "INFO" "[3/5] Backup Snap completato."
    else
        log "WARN" "[3/5] Snap non installato nel sistema. Saltato."
    fi

    # 4. Tutte le Home
    log "INFO" "[4/5] Salvataggio delle cartelle Home (/home/*)..."
    mkdir -p "$DIR_HOME"
    # Utilizzo di rsync per mantenere permessi e struttura
    sudo rsync -avhP --exclude='.cache' --exclude='.local/share/Trash' /home/ "$DIR_HOME/" >> "$LOG_FILE" 2>&1
    log "INFO" "[4/5] Backup delle cartelle Home completato."

    # 5. Altre Impostazioni di Sistema
    log "INFO" "[5/5] Salvataggio impostazioni di sistema (/etc, dconf)..."
    mkdir -p "$DIR_CONFIG"
    if command -v dconf &>/dev/null; then
        dconf dump / > "${DIR_CONFIG}/dconf_desktop_settings.ini" || true
    fi
    sudo cp -r /etc/fstab /etc/hosts /etc/environment "${DIR_CONFIG}/" 2>/dev/null || true
    log "INFO" "[5/5] Backup impostazioni completato."

    log "INFO" "=================================================="
    log "INFO" "PROCEDURA DI BACKUP COMPLETATA CON SUCCESSO!"
    log "INFO" "=================================================="
}

# ------------------------------------------------------------------------------
# 2. FUNZIONE DI RESTORE
# ------------------------------------------------------------------------------
do_restore() {
    log "INFO" "Inizio fase di Ripristino (Restore)..."

    # Verifica presenza cartelle
    if [ ! -d "$TARGET_DIR" ]; then
        log "ERROR" "La cartella $TARGET_DIR non esiste! Impossibile proseguire."
        exit 1
    fi

    # 1. Ripristino APT
    log "INFO" "[1/5] Ripristino pacchetti APT..."
    if [ -f "${DIR_APT}/manual_packages.txt" ]; then
        sudo apt update >> "$LOG_FILE" 2>&1
        xargs -a "${DIR_APT}/manual_packages.txt" sudo apt install -y >> "$LOG_FILE" 2>&1 || true
        log "INFO" "[1/5] Ripristino APT completato."
    else
        log "WARN" "[1/5] File lista APT non trovato. Saltato."
    fi

    # 2. Ripristino Flatpak
    log "INFO" "[2/5] Ripristino pacchetti Flatpak..."
    if [ -f "${DIR_FLATPAK}/flatpak_apps.txt" ] && command -v flatpak &>/dev/null; then
        while read -r app; do
            if [ -n "$app" ]; then
                flatpak install flathub "$app" -y >> "$LOG_FILE" 2>&1 || true
            fi
        done < "${DIR_FLATPAK}/flatpak_apps.txt"
        log "INFO" "[2/5] Ripristino Flatpak completato."
    else
        log "WARN" "[2/5] Lista Flatpak o comando Flatpak non presente. Saltato."
    fi

    # 3. Ripristino Snap
    log "INFO" "[3/5] Ripristino pacchetti Snap..."
    if [ -f "${DIR_SNAP}/snap_apps.txt" ] && command -v snap &>/dev/null; then
        while read -r app; do
            if [ -n "$app" ]; then
                sudo snap install "$app" >> "$LOG_FILE" 2>&1 || true
            fi
        done < "${DIR_SNAP}/snap_apps.txt"
        log "INFO" "[3/5] Ripristino Snap completato."
    else
        log "WARN" "[3/5] Lista Snap o comando Snap non presente. Saltato."
    fi

    # 4. Ripristino Home
    log "INFO" "[4/5] Ripristino cartelle Home (/home/*)..."
    if [ -d "$DIR_HOME" ]; then
        sudo rsync -avhP "$DIR_HOME/" /home/ >> "$LOG_FILE" 2>&1
        log "INFO" "[4/5] Ripristino Home completato."
    else
        log "WARN" "[4/5] Cartella backup Home non trovata. Saltato."
    fi

    # 5. Ripristino Impostazioni
    log "INFO" "[5/5] Ripristino impostazioni (dconf / configurazioni)..."
    if [ -f "${DIR_CONFIG}/dconf_desktop_settings.ini" ] && command -v dconf &>/dev/null; then
        dconf load / < "${DIR_CONFIG}/dconf_desktop_settings.ini" || true
        log "INFO" "[5/5] Ripristino dconf completato."
    else
        log "WARN" "[5/5] File dconf non trovato. Saltato."
    fi

    log "INFO" "=================================================="
    log "INFO" "PROCEDURA DI RESTORE COMPLETATA CON SUCCESSO!"
    log "INFO" "=================================================="
}

# ------------------------------------------------------------------------------
# 3. ESECUZIONE
# ------------------------------------------------------------------------------
if [ "$ACTION" == "backup" ]; then
    do_backup
elif [ "$ACTION" == "restore" ]; then
    do_restore
fi