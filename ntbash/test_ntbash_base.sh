#!/bin/bash
# test_ntbash_base.sh
# Script di esempio per ntbash.py: crea un file, lo copia,
# crea una cartella di test e la elimina.

echo "=== Test ntbash base ==="
echo "Script: $0"
echo "Argomenti: $# -> $@"

# 1. Crea un file
echo "Creo file originale.txt"
echo "contenuto di prova" > originale.txt
echo "File creato:"
cat originale.txt

# 2. Copia il file in un altro
echo "Copio in copia.txt"
cp originale.txt copia.txt
echo "Contenuto copia:"
cat copia.txt

# 3. Crea una cartella di test
echo "Creo cartella test_dir"
mkdir test_dir
echo "Cartella creata:"
ls

# 4. Sposta la copia dentro la cartella
echo "Sposto copia.txt in test_dir"
mv copia.txt test_dir/copia.txt
echo "Contenuto test_dir:"
ls test_dir

# 5. Elimina la cartella di test (ricorsivo)
echo "Elimino test_dir"
rm -r test_dir
echo "Cartella eliminata:"
ls

# 6. Pulizia finale
echo "Elimino originale.txt"
rm originale.txt
echo "=== Fine test ==="
