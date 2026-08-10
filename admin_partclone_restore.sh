#!/bin/bash

# Funzione per mostrare la guida
mostra_guida() {
    echo ""
    echo "USO: $0 <file_backup> <partizione_destinazione>"
    echo "Esempio: $0 /media/usb/backup/backup_ntfs_sda1_20260609_193000.img.gz /dev/sda1"
    echo ""
    echo "⚠️  ATTENZIONE: Questa operazione SOVRASCRIVE completamente la partizione di destinazione!"
    echo "    Verrà richiesta conferma digitando 'SI' (maiuscolo) prima di procedere."
    echo ""
}

# Controlla che siano stati passati esattamente 2 parametri
if [ "$#" -ne 2 ]; then
    echo "Errore: Parametri non corretti!"
    mostra_guida
    exit 1
fi

# Assegnazione delle variabili dai parametri
FILE_BACKUP=$1
DESTINAZIONE=$2

# 1. Controlla se il file di backup esiste
if [ ! -f "$FILE_BACKUP" ]; then
    echo "Errore: Il file di backup '$FILE_BACKUP' non esiste."
    exit 1
fi

if [ ! -r "$FILE_BACKUP" ]; then
    echo "Errore: Il file di backup '$FILE_BACKUP' non è leggibile."
    exit 1
fi

# 2. Controlla se la partizione di destinazione esiste
if [ ! -b "$DESTINAZIONE" ]; then
    echo "Errore: La partizione di destinazione '$DESTINAZIONE' non esiste o non è un dispositivo valido."
    exit 1
fi

# 3. Verifica che il file sia un archivio gzip
if [[ ! "$FILE_BACKUP" =~ \.gz$ ]]; then
    echo "Avviso: Il file non termina con .gz. Verrà usato 'gunzip' che potrebbe fallire."
fi

# 4. Rileva il file system dalla partizione di destinazione
FSTYPE=$(lsblk -no FSTYPE "$DESTINAZIONE")

if [ -z "$FSTYPE" ]; then
    echo "Avviso: Impossibile rilevare il file system di $DESTINAZIONE."
    echo "Tentativo con partclone.dd (modalità generica)..."
    FSTYPE="dd"
else
    echo "File system rilevato su $DESTINAZIONE: $FSTYPE"
fi

# 5. Controllo sicurezza - richiesta conferma
echo "=================================================="
echo "      ATTENZIONE: OPERAZIONE DISTRUTTIVA"
echo "=================================================="
echo "File backup:   $FILE_BACKUP"
echo "Destinazione:  $DESTINAZIONE (File System: $FSTYPE)"
echo ""
echo "QUESTA OPERAZIONE SOVRASCRIVERÀ COMPLETAMENTE LA PARTIZIONE $DESTINAZIONE"
echo "TUTTI I DATI ESISTENTI SARANNO PERSI IN MODO IRREVERSIBILE!"
echo "=================================================="
echo ""
echo -n "Per confermare, digitare esattamente 'SI' (maiuscolo): "
read CONFERMA

if [ "$CONFERMA" != "SI" ]; then
    echo "Operazione annullata dall'utente."
    exit 1
fi

echo ""
echo "=================================================="
echo "      AVVIO PROCESSO DI RIPRISTINO"
echo "=================================================="

# Registra il tempo di inizio
START_TIME=$(date +%s)

# Esegue partclone specifico per il file system rilevato con gunzip
if [ "$FSTYPE" = "dd" ] || ! command -v "partclone.${FSTYPE}" &> /dev/null; then
    if [ "$FSTYPE" != "dd" ]; then
        echo "Avviso: partclone.${FSTYPE} non trovato. Uso modulo generico partclone.dd..."
    fi
    gunzip -c "$FILE_BACKUP" | sudo partclone.dd -r -o "$DESTINAZIONE"
else
    gunzip -c "$FILE_BACKUP" | sudo "partclone.${FSTYPE}" -r -o "$DESTINAZIONE"
fi

# Controlla se il comando precedente è terminato con successo
if [ $? -eq 0 ]; then
    END_TIME=$(date +%s)
    DURATA=$((END_TIME - START_TIME))
    echo "=================================================="
    echo " Ripristino completato con successo!"
    echo " Tempo impiegato: $((DURATA / 60)) minuti e $((DURATA % 60)) secondi."
    echo "=================================================="
else
    echo "=================================================="
    echo " Errore durante l'esecuzione del ripristino!"
    echo "=================================================="
    exit 1
fi