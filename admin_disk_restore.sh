#!/bin/bash
#
# admin_disk_restore.sh
# Script per il ripristino di un'immagine disco compressa (generata da admin_disk_image.sh)
# Richiede 2 parametri posizionali: <file_sorgente> <disco_destinazione>
# Esempio: ./admin_disk_restore.sh /mnt/backup/server_disk_20260802120000.img.gz /dev/sdb
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
    echo -e "Uso corretto: $0 <file_sorgente> <disco_destinazione>"
    echo -e "Esempio: $0 /mnt/backup/disk_image.img.gz /dev/sdb"
    exit 1
}

# ------------------------------
# FASE 1: Verifica parametri obbligatori
# ------------------------------
echo -e "${CYAN}=== FASE 1: Verifica parametri ===${NC}"

if [ $# -ne 2 ]; then
    usage
fi

SOURCE_FILE="$1"
DEST_DISK="$2"

echo -e "${GREEN}✓ Parametri accettati:${NC}"
echo "  File sorgente   : $SOURCE_FILE"
echo "  Disco destinazione: $DEST_DISK"

# ------------------------------
# FASE 2: Controllo prerequisiti
# ------------------------------
echo -e "${CYAN}=== FASE 2: Controllo prerequisiti ===${NC}"

# 2.1 Verifica esistenza e leggibilità del file sorgente
if [ ! -f "$SOURCE_FILE" ]; then
    echo -e "${RED}✗ Errore: il file '$SOURCE_FILE' non esiste.${NC}"
    exit 1
fi
if [ ! -r "$SOURCE_FILE" ]; then
    echo -e "${RED}✗ Errore: il file '$SOURCE_FILE' non è leggibile.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ File sorgente valido: $SOURCE_FILE${NC}"

# 2.2 Verifica che il file sia compresso con gzip (estensione .gz o .img.gz)
#     Se non termina con .gz, avvisiamo ma procediamo lo stesso (potrebbe essere raw)
if [[ ! "$SOURCE_FILE" =~ \.gz$ ]]; then
    echo -e "${YELLOW}⚠ Attenzione: il file non termina con .gz. Verrà usato 'gunzip' che potrebbe fallire.${NC}"
fi

# 2.3 Verifica esistenza e scrivibilità del device di blocco destinazione
if [ ! -b "$DEST_DISK" ]; then
    echo -e "${RED}✗ Errore: '$DEST_DISK' non è un device a blocchi valido.${NC}"
    exit 1
fi

# Controllo se il device è montato (per evitare sovrascrittura accidentale)
# Verifica semplice: se il device appare in /proc/mounts
if grep -q "^$DEST_DISK " /proc/mounts; then
    echo -e "${RED}✗ Errore: il device '$DEST_DISK' è attualmente montato. Smontarlo prima di procedere.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Device destinazione valido e non montato: $DEST_DISK${NC}"

# 2.4 Verifica cartella Log (come per backup)
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

# 2.5 Verifica e installazione automatica di 'pv'
if ! command -v pv &>/dev/null; then
    echo -e "${YELLOW}⚠ 'pv' non trovato, tentativo di installazione via apt...${NC}"
    sudo apt update &>/dev/null && sudo apt install -y pv &>/dev/null
    if ! command -v pv &>/dev/null; then
        echo -e "${RED}✗ Installazione di 'pv' fallita. Impossibile procedere.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ 'pv' installato con successo.${NC}"
else
    echo -e "${GREEN}✓ 'pv' già presente nel sistema.${NC}"
fi

# 2.6 Verifica presenza di gzip (per decompressione)
if ! command -v gzip &>/dev/null; then
    echo -e "${RED}✗ 'gzip' non trovato. Installarlo prima di procedere.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ 'gzip' disponibile.${NC}"
fi

# ------------------------------
# FASE 3: Esecuzione del ripristino
# ------------------------------
echo -e "${CYAN}=== FASE 3: Esecuzione ripristino ===${NC}"

# Ottieni dimensione del file sorgente per pv
FILE_SIZE=$(stat -c %s "$SOURCE_FILE" 2>/dev/null)
if [ -z "$FILE_SIZE" ] || [ "$FILE_SIZE" -eq 0 ]; then
    echo -e "${YELLOW}⚠ Impossibile determinare la dimensione del file. pv procederà senza barra di avanzamento.${NC}"
    PV_OPTS=""
else
    PV_OPTS="-s $FILE_SIZE"
    echo -e "Dimensione file sorgente: ${GREEN}$FILE_SIZE${NC} byte"
fi

echo -e "${YELLOW}Avvio pipeline: gunzip -c | pv | dd of=$DEST_DISK bs=1M ...${NC}"
echo -e "${RED}ATTENZIONE: Questa operazione sovrascriverà completamente il disco '$DEST_DISK'!${NC}"
echo -e "Premere Ctrl+C per annullare (hai 5 secondi)..."
sleep 5

# Avvia cronometro
START_TIME=$(date +%s)

# Esegue la pipeline: decomprimi, mostra progresso, scrivi sul disco
# Nota: usiamo gunzip -c per leggere da stdin (pipe) o direttamente da file
# Per sicurezza, specifichiamo il file come argomento a gunzip -c
gunzip -c "$SOURCE_FILE" 2>/dev/null | pv $PV_OPTS | dd of="$DEST_DISK" bs=1M 2>/dev/null

# Cattura gli stati di uscita
PIPESTATUS_ARRAY=("${PIPESTATUS[@]}")
GUNZIP_EXIT=${PIPESTATUS_ARRAY[0]}
PV_EXIT=${PIPESTATUS_ARRAY[1]}
DD_EXIT=${PIPESTATUS_ARRAY[2]}

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ------------------------------
# FASE 4: Risultati finali
# ------------------------------
echo -e "${CYAN}=== FASE 4: Risultati finali ===${NC}"

echo -e "Durata totale: ${GREEN}${DURATION}${NC} secondi"

if [ $GUNZIP_EXIT -eq 0 ] && [ $PV_EXIT -eq 0 ] && [ $DD_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Ripristino completato con successo!${NC}"
    echo -e "Il disco $DEST_DISK è stato sovrascritto con l'immagine."
    exit 0
else
    echo -e "${RED}✗ Ripristino fallito.${NC}"
    echo -e "Codici di uscita: gunzip=$GUNZIP_EXIT, pv=$PV_EXIT, dd=$DD_EXIT"
    exit 1
fi