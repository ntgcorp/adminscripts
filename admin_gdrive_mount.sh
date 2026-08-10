#!/bin/bash

# Configurazione
REMOTE_NAME="gdrive"
# Solitamente i mount condivisi in Linux si mettono in /media o /mnt
MOUNT_POINT="/mnt/gdrive"

# Verifica se il punto di montaggio esiste
if [ ! -d "$MOUNT_POINT" ]; then
    echo "Creazione cartella $MOUNT_POINT..."
    sudo mkdir -p "$MOUNT_POINT"
    # Diamo permessi globali sulla cartella di mount
    sudo chmod 755 "$MOUNT_POINT"
fi

# Montaggio
# --allow-other: permette agli altri utenti di accedere al mount
# --vfs-cache-mode writes: raccomandato per una migliore compatibilità
echo "Montaggio di $REMOTE_NAME in $MOUNT_POINT..."

rclone mount "$REMOTE_NAME": "$MOUNT_POINT" \
    --daemon \
    --allow-other \
    --vfs-cache-mode writes

if [ $? -eq 0 ]; then
    echo "Montaggio riuscito correttamente."
else
    echo "Errore durante il montaggio."
fi