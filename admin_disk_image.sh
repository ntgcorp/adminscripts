#!/bin/bash
#
# admin_disk_image.sh
# Script per il backup di un'immagine disco compressa tramite pipeline dd | pv | gzip
# Richiede 3 parametri posizionali: <disco_sorgente> <cartella_destinazione> <nome_file_base>
#

# ------------------------------
# Colori ANSI per output console
# ------------------------------
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ------------------------------
# Funzione di uso / help
# ------------------------------
usage() {
    echo -e "${RED}ERRORE:${NC} Numero di parametri errato."
    echo -e "Uso corretto: $0 <disco_sorgente> <cartella_destinazione> <nome_file_base>"
    echo -e "Esempio: $0 /dev/sda /mnt/backup server_disk"
    exit 1
}

# ------------------------------
# FASE 1: Verifica parametri obbligatori
# ------------------------------
echo -e "${CYAN}=== FASE 1: Verifica parametri ===${NC}"

if [ $# -ne 3 ]; then
    usage
fi

SOURCE_DISK="$1"
DEST_DIR="$2"
BASE_NAME="$3"

echo -e "${GREEN}✓ Parametri accettati:${NC}"
echo "  Sorgente   : $SOURCE_DISK"
echo "  Destinazione: $DEST_DIR"
echo "  Nome base  : $BASE_NAME"

# ------------------------------
# FASE 2: Sanificazione percorso destinazione
# ------------------------------
echo -e "${CYAN}=== FASE 2: Sanificazione percorso destinazione ===${NC}"

# Rimuovi eventuali slash o backslash finali
DEST_DIR_CLEAN="$(echo "$DEST_DIR" | sed 's/[\/\\]$//')"

if [ "$DEST_DIR" != "$DEST_DIR_CLEAN" ]; then
    echo -e "${YELLOW}⚠ Percorso originale conteneva caratteri finali indesiderati.${NC}"
    echo -e "  Pulito: ${GREEN}$DEST_DIR_CLEAN${NC}"
else
    echo -e "${GREEN}✓ Percorso destinazione già pulito: $DEST_DIR_CLEAN${NC}"
fi

DEST_DIR="$DEST_DIR_CLEAN"  # aggiorniamo la variabile

# ------------------------------
# FASE 3: Controllo prerequisiti
# ------------------------------
echo -e "${CYAN}=== FASE 3: Controllo prerequisiti ===${NC}"

# 3.1 Verifica esistenza e integrità del device di blocco sorgente
if [ ! -b "$SOURCE_DISK" ]; then
    echo -e "${RED}✗ Errore: '$SOURCE_DISK' non è un device a blocchi valido.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Device sorgente valido: $SOURCE_DISK${NC}"
fi

# 3.2 Verifica / creazione della cartella di destinazione
if [ ! -d "$DEST_DIR" ]; then
    echo -e "${YELLOW}⚠ La cartella di destinazione non esiste, verrà creata...${NC}"
    mkdir -p "$DEST_DIR" || {
        echo -e "${RED}✗ Impossibile creare la cartella '$DEST_DIR'.${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Cartella creata: $DEST_DIR${NC}"
else
    echo -e "${GREEN}✓ Cartella di destinazione esistente: $DEST_DIR${NC}"
fi

# Verifica che la cartella sia scrivibile
if [ ! -w "$DEST_DIR" ]; then
    echo -e "${RED}✗ Errore: la cartella '$DEST_DIR' non è scrivibile.${NC}"
    exit 1
fi

# 3.3 Verifica cartella Log (come da specifica originale)
LOG_DIR="/home/ntjobsos/Log"
if [ ! -d "$LOG_DIR" ]; then
    echo -e "${YELLOW}⚠ La cartella Log '$LOG_DIR' non esiste, verrà creata...${NC}"
    mkdir -p "$LOG_DIR" || {
        echo -e "${RED}✗ Impossibile creare la cartella Log '$LOG_DIR'.${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Cartella Log creata: $LOG_DIR${NC}"
else
    echo -e "${GREEN}✓ Cartella Log esistente: $LOG_DIR${NC}"
fi

# 3.4 Verifica e installazione automatica di 'pv'
if ! command -v pv &>/dev/null; then
    echo -e "${YELLOW}⚠ 'pv' non trovato, tentativo di installazione via apt...${NC}"
    # Si assume che apt sia disponibile (Debian/Ubuntu)
    sudo apt update &>/dev/null && sudo apt install -y pv &>/dev/null
    if ! command -v pv &>/dev/null; then
        echo -e "${RED}✗ Installazione di 'pv' fallita. Impossibile procedere.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ 'pv' installato con successo.${NC}"
else
    echo -e "${GREEN}✓ 'pv' già presente nel sistema.${NC}"
fi

# 3.5 Verifica presenza di gzip (normalmente sempre presente)
if ! command -v gzip &>/dev/null; then
    echo -e "${RED}✗ 'gzip' non trovato. Installarlo prima di procedere.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ 'gzip' disponibile.${NC}"
fi

# ------------------------------
# FASE 4: Preparazione ed esecuzione del backup
# ------------------------------
echo -e "${CYAN}=== FASE 4: Esecuzione backup ===${NC}"

# Ottieni dimensione del disco in byte
DISK_SIZE=$(blockdev --getsize64 "$SOURCE_DISK" 2>/dev/null)
if [ -z "$DISK_SIZE" ] || [ "$DISK_SIZE" -eq 0 ]; then
    echo -e "${RED}✗ Impossibile determinare la dimensione del disco.${NC}"
    exit 1
fi
echo -e "Dimensione disco: ${GREEN}$DISK_SIZE${NC} byte"

# Genera nome file con timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)
OUTPUT_FILE="${DEST_DIR}/${BASE_NAME}_${TIMESTAMP}.img.gz"
echo -e "File di output: ${GREEN}$OUTPUT_FILE${NC}"

# Avvia cronometro
START_TIME=$(date +%s)

echo -e "${YELLOW}Avvio pipeline: dd | pv | gzip ...${NC}"
echo -e "Premere Ctrl+C per interrompere."

# Esegue la pipeline; utilizziamo bs=1M per prestazioni migliori
# Nota: gli errori di dd vengono silenziati (2>/dev/null) per non intasare l'output,
# ma eventuali problemi verranno rilevati tramite PIPESTATUS.
dd if="$SOURCE_DISK" bs=1M 2>/dev/null | pv -s "$DISK_SIZE" | gzip -c > "$OUTPUT_FILE"

# Cattura lo stato di uscita di ogni comando nella pipeline
PIPESTATUS_ARRAY=("${PIPESTATUS[@]}")
DD_EXIT=${PIPESTATUS_ARRAY[0]}
PV_EXIT=${PIPESTATUS_ARRAY[1]}
GZIP_EXIT=${PIPESTATUS_ARRAY[2]}

# Calcola durata
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ------------------------------
# FASE 5: Elaborazione risultati finali
# ------------------------------
echo -e "${CYAN}=== FASE 5: Risultati finali ===${NC}"

echo -e "Durata totale: ${GREEN}${DURATION}${NC} secondi"

# Verifica il codice di uscita del comando dd (PIPESTATUS[0])
if [ $DD_EXIT -eq 0 ] && [ $GZIP_EXIT -eq 0 ] && [ $PV_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Backup completato con successo!${NC}"
    echo -e "File creato: $OUTPUT_FILE"
    # Opzionale: calcola e mostra la dimensione del file generato
    if [ -f "$OUTPUT_FILE" ]; then
        FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo -e "Dimensione file compresso: ${GREEN}$FILE_SIZE${NC}"
    fi
    exit 0
else
    echo -e "${RED}✗ Backup fallito.${NC}"
    echo -e "Codici di uscita: dd=$DD_EXIT, pv=$PV_EXIT, gzip=$GZIP_EXIT"
    # Rimuovere eventuale file parziale?
    if [ -f "$OUTPUT_FILE" ]; then
        echo -e "${YELLOW}⚠ Il file di output potrebbe essere incompleto.${NC}"
    fi
    exit 1
fi