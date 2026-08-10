#!/bin/bash

# Funzione per mostrare la guida ai livelli di compressione
mostra_guida_compressione() {
    echo ""
    echo "LIVELLI DI COMPATTAZIONE DISPONIBILI (gzip):"
    echo "  1 : Più veloce in assoluto (bassa compressione, file finale più grande)"
    echo "  2-3: Compressione leggera (veloce, adatta a CPU datate)"
    echo "  4-5: Buon compromesso (velocità discreta, buon risparmio di spazio)"
    echo "  6 : Livello predefinito / standard (ottimo bilanciamento velocità/dimensione)"
    echo "  7-8: Compressione alta (più lento, richiede più CPU)"
    echo "  9 : Massima compressione (molto lento, file finale il più piccolo possibile)"
    echo ""
}

# Controlla che siano stati passati esattamente 3 parametri
if [ "$#" -ne 3 ]; then
    echo "Errore: Parametri non corretti!"
    echo "Uso: $0 <partizione_sorgente> <cartella_destinazione> <livello_compressione>"
    echo "Esempio: $0 /dev/sda1 /media/usb/backup 6"
    mostra_guida_compressione
    exit 1
fi

# Assegnazione delle variabili dai parametri
SORGENTE=$1
DESTINAZIONE=$2
LIVELLO_COMP=$3

# 1. Controlla se la partizione sorgente esiste
if [ ! -b "$SORGENTE" ]; then
    echo "Errore: La partizione sorgente '$SORGENTE' non esiste o non è un dispositivo valido."
    exit 1
fi

# 2. Controlla se la cartella di destinazione esiste
if [ ! -d "$DESTINAZIONE" ]; then
    echo "Errore: La cartella di destinazione '$DESTINAZIONE' non esiste."
    exit 1
fi

# 3. Valida il livello di compressione (deve essere un numero tra 1 e 9)
if [[ ! "$LIVELLO_COMP" =~ ^[1-9]$ ]]; then
    echo "Errore: Il livello di compressione inserito ('$LIVELLO_COMP') non è valido!"
    echo "Deve essere un numero intero compreso tra 1 e 9."
    mostra_guida_compressione
    exit 1
fi

# Rileva automaticamente il file system della partizione (es. ntfs, ext4, fat32)
FSTYPE=$(lsblk -no FSTYPE "$SORGENTE")

if [ -z "$FSTYPE" ]; then
    echo "Errore: Impossibile rilevare il file system di $SORGENTE."
    exit 1
fi

# Costruisce il nome del file di backup finale usando data e ora corrente
DATA_ORA=$(date +"%Y%m%d_%H%M%S")
NOME_FILE="backup_${FSTYPE}_$(basename "$SORGENTE")_${DATA_ORA}.img.gz"
PATH_FINALE="${DESTINAZIONE}/${NOME_FILE}"

echo "=================================================="
echo "      AVVIO PROCESSO DI BACKUP INTELLIGENTE"
echo "=================================================="
echo "Sorgente:      $SORGENTE (File System: $FSTYPE)"
echo "Destinazione:  $PATH_FINALE"
echo "Compressione:  gzip (Livello $LIVELLO_COMP)"
echo "=================================================="

# Registra il tempo di inizio
START_TIME=$(date +%s)

# Esegue partclone specifico per il file system rilevato e lo passa a gzip
if command -v "partclone.${FSTYPE}" &> /dev/null; then
    sudo "partclone.${FSTYPE}" -c -s "$SORGENTE" | gzip -"$LIVELLO_COMP" -c > "$PATH_FINALE"
else
    echo "Avviso: partclone.${FSTYPE} non trovato. Tento l'uso del modulo generico..."
    sudo partclone.dd -c -s "$SORGENTE" | gzip -"$LIVELLO_COMP" -c > "$PATH_FINALE"
fi

# Controlla se il comando precedente è terminato con successo
if [ $? -eq 0 ]; then
    END_TIME=$(date +%s)
    DURATA=$((END_TIME - START_TIME))
    echo "=================================================="
    echo " Backup completato con successo!"
    echo " Tempo impiegato: $((DURATA / 60)) minuti e $((DURATA % 60)) secondi."
    echo "=================================================="
else
    echo "=================================================="
    echo " Errore durante l'esecuzione del backup!"
    echo "=================================================="
    exit 1
fi
