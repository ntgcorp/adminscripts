import sys
import os
import subprocess
import shutil
import datetime
import json
import ftplib
import stat
import tempfile
import glob
import re
import importlib.metadata
import locale
import html as _html

# Importazione opzionale per librerie di terze parti
try:
    import requests
except ImportError:
    requests = None

try:
    import pypandoc
except ImportError:
    pypandoc = None

try:
    import paramiko
except ImportError:
    paramiko = None

try:
    import markdown
except ImportError:
    markdown = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

# ==============================================================================
# VARIABILI GLOBALI E COSTANTI
# ==============================================================================
PYT_VER = "20261118"
QEMU_IMG = r"X:\_Applic\Qemu\qemu-img.exe"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "pyt.log")

# ==============================================================================
# LINGUA E TRADUZIONI (IT/EN)
# Lingua rilevata dal computer: italiano -> messaggi italiani, altrimenti inglese.
# Override manuale: variabile d'ambiente PYT_LANG=it oppure PYT_LANG=en.
# ==============================================================================
def _pyt_DetectLang():
    """Rileva la lingua del computer: 'it' se italiano, 'en' altrimenti."""
    env = os.environ.get("PYT_LANG", "").strip().lower()
    if env in ("it", "ita", "it_it", "it-it", "italian"):
        return "it"
    if env in ("en", "eng", "en_us", "en-us", "english"):
        return "en"
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            loc = locale.getdefaultlocale()[0]
        if loc and str(loc).lower().startswith("it"):
            return "it"
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x00FF
            if lid == 0x10:  # 0x0410 = italiano
                return "it"
        except Exception:
            pass
    return "en"

PYT_LANG = _pyt_DetectLang()

_PYT_MSG_EN = []  # lista di (regex_compilata, template_en)

def _pyt_AddMsg(it_pattern, en_template):
    """Registra una regola di traduzione IT->EN (i valori dinamici diventano {0},{1}...)."""
    try:
        _PYT_MSG_EN.append((re.compile(it_pattern, re.S), en_template))
    except re.error:
        pass

# Tabella di traduzione dei messaggi a schermo (IT -> EN).
# Il pattern matcha il messaggio AL MOMENTO DELLA STAMPA (valori gia' interpolati);
# i gruppi catturati sostituiscono i segnaposto {0},{1},... nel template inglese.
# Ordine: prima i pattern piu' specifici, poi i generici.
_PYT_MSG_LIST = [
    # --- sistemi delle fasi (generico: [ts] Fase N: ...) ---
    (r"^\[([^\]]+)\]\s*Fase (\d+): (.*)$", "[{0}] Phase {1}: {2}"),
    # --- messaggi fatale/parsing ---
    (r"^Errore fatale imprevisto: (.*)$", "Unexpected fatal error: {0}"),
    (r"^Errore fatale: nessuna direttiva valida trovata\.$", "Fatal error: no valid directive found."),
    (r"^Errore: file di direttive (.+?) non trovato\.$", "Error: directive file {0} not found."),
    (r"^Errore: file di direttive non specificato dopo @\.$", "Error: directive file not specified after @."),
    (r"^Errore: direttiva '(.+?)' non riconosciuta\.$", "Error: unknown directive '{0}'."),
    # --- log ---
    (r"^( {0,2})Impossibile scrivere sul log (.+?): (.*)$", "{0}Cannot write to log {1}: {2}"),
    (r"^( {0,2})Impossibile scrivere sul log: (.*)$", "{0}Cannot write to log: {1}"),
    (r"^( {0,2})Attenzione: permessi insufficienti per leggere alcune cartelle\.$", "{0}Warning: insufficient permissions to read some folders."),
    # --- ERRORE generico con direttiva ---
    (r"^ERRORE \[(.+?)\]: (.*)$", "ERROR [{0}]: {1}"),
    (r"^ERRORE nel job '(.+?)': (.*)$", "ERROR in job '{0}': {1}"),
    # --- grep ---
    (r"^GREP\.START: (.*) \((\d+) da cercare\)$", "GREP.START: {0} ({1} to search)"),
    (r"^GREP\.END: (.*) - corrispondenze: (\d+), file con match: (\d+)/(\d+), errori: (\d+)$",
     "GREP.END: {0} - matches: {1}, files with match: {2}/{3}, errors: {4}"),
    (r"^(\d+) corrispondenze in (.+)$", "{0} matches in {1}"),
    (r"^Nessuna corrispondenza trovata$", "No matches found"),
    (r"^Nessun file da cercare: (.*)$", "No files to search: {0}"),
    (r"^Nessun file: indicare i file o -p/--path\.$", "No files: specify files or -p/--path."),
    (r"^Espressione regolare non valida: (.*)$", "Invalid regular expression: {0}"),
    (r"^Pattern vuoto\.$", "Empty pattern."),
    (r"^L'opzione -p richiede il path di ricerca\.$", "Option -p requires the search path."),
    (r"^Opzione sconosciuta: (.*)$", "Unknown option: {0}"),
    # --- conversioni / output file ---
    (r"^Convertito con successo: (.*)$", "Successfully converted: {0}"),
    (r"^Convertito (.+?) in (.+)$", "Converted {0} to {1}"),
    (r"^Markdown scritto in: (.*)$", "Markdown written to: {0}"),
    (r"^Pagina HTML generata con successo: (.*)$", "HTML page successfully generated: {0}"),
    (r"^Lista scritta in: (.*)$", "List written to: {0}"),
    (r"^Creato: (.*)$", "Created: {0}"),
    (r"^Container '(.+?)' esportato in: (.*)$", "Container '{0}' exported to: {1}"),
    (r"^Script batch generato\. Eseguirlo per avviare la sincronizzazione\.$",
     "Batch script generated. Run it to start synchronization."),
    (r"^\[OK\] Script generato con successo in: (.*)$", "[OK] Script successfully generated in: {0}"),
    (r"^\[OK\] Script generato \(sovrascritto\) in: (.*)$", "[OK] Script generated (overwritten) in: {0}"),
    # --- disk_check / riepiloghi ---
    (r"^  Cartelle    : (.+?) \((.*?)\)$", "  Folders     : {0} ({1})"),
    (r"^  Sorgente    : (.*)$", "  Source      : {0}"),
    (r"^  Destinazione: (.*)$", "  Destination : {0}"),
    (r"^  File output : (.*)$", "  Output file : {0}"),
    (r"^WARNING: Spazio usato (.+?)% supera la soglia di (.+?)%$", "WARNING: Used space {0}% exceeds threshold of {1}%"),
    (r"^RIEPILOGO GENERALE$", "GENERAL SUMMARY"),
    (r"^Totale file copiati         : (.*)$", "Total files copied         : {0}"),
    (r"^Totale file aggiornati      : (.*)$", "Total files updated        : {0}"),
    (r"^Totale file rimossi         : (.*)$", "Total files removed        : {0}"),
    (r"^Totale file saltati         : (.*)$", "Total files skipped        : {0}"),
    (r"^Totale errori file          : (.*)$", "Total file errors          : {0}"),
    (r"^Job completati con successo : (.*)$", "Jobs completed successfully: {0}"),
    (r"^Job falliti                 : (.*)$", "Failed jobs                : {0}"),
    (r"^\n\[(.+?)\] RIEPILOGO FINALE$", "\n[{0}] FINAL SUMMARY"),
    (r"^\n\[(.+?)\] SEZIONE: (.*)$", "\n[{0}] SECTION: {1}"),
    (r"^\[(.+?)\] Riepilogo - Documentate: (\d+), arricchite via PyPI: (\d+), senza dati: (\d+), righe saltate: (\d+)$",
     "[{0}] Summary - Documented: {1}, enriched via PyPI: {2}, without data: {3}, skipped lines: {4}"),
    (r"^\[(.+?)\] Riepilogo - File eliminati: (.*),$", "[{0}] Summary - Deleted files: {1},"),
    (r"^\[(.+?)\] Riepilogo - Voci mancanti in sorgente: (.*?) ?$", "[{0}] Summary - Entries missing in source: {1}"),
    (r"^\[(.+?)\] Creati: (.+?), Avviati: (.*),$", "[{0}] Created: {1}, Started: {2},"),
    (r"^\[(.+?)\] JOB (\d+)/(\d+): (.*)$", "[{0}] JOB {1}/{2}: {3}"),
    (r"^\[(.+?)\] Elaboro ID: (.+?), file (.*)$", "[{0}] Processing ID: {1}, file {2}"),
    (r"^\[(.+?)\] WRITE: Report generati con successo$", "[{0}] WRITE: Reports generated successfully"),
    # --- sync / git ---
    (r"^    Job (.+?): (.*)$", "    Job {0}: {1}"),
    (r"^  \[ATTENZIONE\] Commit non eseguito: (.*)$", "  [WARNING] Commit not executed: {0}"),
    (r"^  \[ATTENZIONE\] git add ha restituito: (.*)$", "  [WARNING] git add returned: {0}"),
    (r"^  \[AVVISO\] File esistente rinominato in (.*)$", "  [NOTICE] Existing file renamed to {0}"),
    (r"^  \[ERRORE\] Errore durante commit: (.*)$", "  [ERROR] Error during commit: {0}"),
    (r"^  \[ERRORE\] Impossibile rinominare (.+?): (.*)$", "  [ERROR] Cannot rename {0}: {1}"),
    (r"^  \[ERRORE\] Timeout durante il commit$", "  [ERROR] Timeout during commit"),
    (r"^  \[INFO\] Procedo con il push dei commit esistenti$", "  [INFO] Proceeding with push of existing commits"),
    (r"^  \[OK\] Commit creato: (.*)$", "  [OK] Commit created: {0}"),
    (r"^  \[OK\] Pull completato con successo$", "  [OK] Pull completed successfully"),
    (r"^  \[OK\] Push completato con successo$", "  [OK] Push completed successfully"),
    (r"^  Chiavi trovate nel JSON: (.*)$", "  Keys found in JSON: {0}"),
    (r"^  Nessuna chiave 'jobs' trovata, trattato come singolo job$", "  No 'jobs' key found, treated as single job"),
    (r"^  ATTENZIONE: La chiave 'jobs' non contiene una lista$", "  WARNING: The 'jobs' key does not contain a list"),
    (r"^  Rilevata chiave 'jobs' \(originale: '(.+?)'\)$", "  Detected 'jobs' key (original: '{0}')"),
    (r"^  Trovati (\d+) job da eseguire$", "  Found {0} jobs to run"),
    (r"^  Verifica esistenza cartella repository\.\.\. OK$", "  Checking repository folder exists... OK"),
    (r"^  Verifica presenza file di log\.\.\. OK$", "  Checking log file exists... OK"),
    (r"^  Comando: git (pull|push) (.*)$", "  Command: git {0} {1}"),
    (r"^  Commit: non eseguito \(commit_message non specificato\)$", "  Commit: not executed (commit_message not specified)"),
    (r"^  Esecuzione: git add \.$", "  Running: git add ."),
    # --- rightlist / delfiles / reqdoc ---
    (r"^\[(.+?)\]   (.+?): scansionate (\d+) voci\.\.\.$", "[{0}]   {1}: scanned {2} entries..."),
    (r"^\[(.+?)\]   Trovate (\d+) librerie \((\d+) righe saltate\)$", "[{0}]   Found {1} libraries ({2} lines skipped)"),
    (r"^\[(.+?)\]   Trovate (\d+) voci in lista$", "[{0}]   Found {1} entries in list"),
    (r"^\[(.+?)\]   Trovate (\d+) voci in sorgente$", "[{0}]   Found {1} entries in source"),
    (r"^\[(.+?)\]   Arricchite via PyPI: (.*)$", "[{0}]   Enriched via PyPI: {1}"),
    (r"^\[(.+?)\]   Metadata locali ok, da arricchire online: (.*)$", "[{0}]   Local metadata ok, to enrich online: {1}"),
    (r"^\[(.+?)\]   ATTENZIONE metadata locali per (.+?): (.*)$", "[{0}]   WARNING local metadata for {1}: {2}"),
    (r"^\[(.+?)\]   ATTENZIONE scansione: (.*)$", "[{0}]   WARNING scan: {1}"),
    (r"^\[(.+?)\]   SALTATO \(non trovato\): (.*)$", "[{0}]   SKIPPED (not found): {1}"),
    (r"^\[(.+?)\]   ELIMINATA DIR: (.*)$", "[{0}]   DIR DELETED: {1}"),
    (r"^\[(.+?)\]   ELIMINATO FILE: (.*)$", "[{0}]   FILE DELETED: {1}"),
    # --- podman ---
    (r"^\[(.+?)\]   SALTATO: command '(.+?)' non supportato \(solo cstart per ora\)\.$",
     "[{0}]   SKIPPED: command '{1}' not supported (only cstart for now)."),
    (r"^\[(.+?)\]   SALTATO: container già attivo \((.+?)\)\.$", "[{0}]   SKIPPED: container already running ({1})."),
    (r"^\[(.+?)\]   Container esistente ma fermo, avvio\.\.\.$", "[{0}]   Existing container stopped, starting..."),
    (r"^\[(.+?)\]   AVVIATO: (.*)$", "[{0}]   STARTED: {1}"),
    (r"^\[(.+?)\]   CREATO: (.+?) \((.+?)\)$", "[{0}]   CREATED: {1} ({2})"),
    (r"^\[(.+?)\]   Avvio macchina\.\.\.$", "[{0}]   Starting machine..."),
    (r"^\[(.+?)\]   Macchina avviata\.$", "[{0}]   Machine started."),
    (r"^\[(.+?)\]   Macchina creata e avviata\.$", "[{0}]   Machine created and started."),
    (r"^\[(.+?)\]   Macchina già attiva\.$", "[{0}]   Machine already running."),
    (r"^\[(.+?)\]   Macchina non trovata, creazione\.\.\.$", "[{0}]   Machine not found, creating..."),
    (r"^\[(.+?)\]   ERRORE su (.+?): (.*)$", "[{0}]   ERROR on {1}: {2}"),
    (r"^\[(.+?)\]   ERRORE su sezione '(.+?)': (.*)$", "[{0}]   ERROR on section '{1}': {2}"),
    (r"^\[(.+?)\]   ERRORE: chiave 'image' obbligatoria\.$", "[{0}]   ERROR: required key 'image'."),
    (r"^\[(.+?)\]   ERRORE: chiave 'name' obbligatoria\.$", "[{0}]   ERROR: required key 'name'."),
    (r"^\[(.+?)\]   ERRORE: la sezione deve essere un oggetto JSON\.$", "[{0}]   ERROR: section must be a JSON object."),
    # --- raise: file / cartelle / config ---
    (r"^Sintassi errata\. Uso: rightlist <path_sorgente> <path_verifica> <listfile\.txt> \(su Windows evitare il backslash finale dentro le virgolette: usare h: e non \x22h:\\\x22\)$",
     "Syntax error. Usage: rightlist <path_source> <path_check> <listfile.txt> (on Windows avoid the trailing backslash inside quotes: use h: not \x22h:\x22)"),
    (r"^Sintassi errata\. Uso: (.*)$", "Syntax error. Usage: {0}"),
    (r"^File di configurazione (.+?) non trovato\.$", "Configuration file {0} not found."),
    (r"^File JSON (.+?) non trovato\.$", "JSON file {0} not found."),
    (r"^File lista (.+?) non trovato\.$", "List file {0} not found."),
    (r"^File requirements (.+?) non trovato\.$", "Requirements file {0} not found."),
    (r"^File sorgente (.+?) non trovato\.$", "Source file {0} not found."),
    (r"^File template (.+?) non trovato\.$", "Template file {0} not found."),
    (r"^File form (.+?) non trovato\.$", "Form file {0} not found."),
    (r"^File (.+?) non trovato\.$", "File {0} not found."),
    (r"^Cartella da verificare (.+?) non trovata\.$", "Verification folder {0} not found."),
    (r"^Cartella sorgente (.+?) non trovata\.$", "Source folder {0} not found."),
    (r"^Cartella (.+?) non trovata\.$", "Folder {0} not found."),
    (r"^Sorgente non esistente: (.*)$", "Source does not exist: {0}"),
    (r"^Repository non trovato: (.*)$", "Repository not found: {0}"),
    (r"^Array 'files' vuoto o mancante per azione '(.+?)'$", "Array 'files' empty or missing for action '{0}'"),
    (r"^Chiave obbligatoria mancante nel JSON: (.*)$", "Required key missing in JSON: {0}"),
    (r"^JSON malformato in (.+?): (.*)$", "Malformed JSON in {0}: {1}"),
    (r"^JSON malformato: (.*)$", "Malformed JSON: {0}"),
    (r"^Il JSON deve essere un oggetto con sezioni identificate da id\.$", "JSON must be an object with sections identified by id."),
    (r"^Setting 'log' obbligatorio in 'settings'$", "Setting 'log' required in 'settings'"),
    (r"^Sezione 'actions' obbligatoria nel JSON$", "'actions' section required in JSON"),
    (r"^Sezione 'settings' obbligatoria nel JSON$", "'settings' section required in JSON"),
    (r"^Nessun record trovato nella sezione 'records' del JSON$", "No records found in JSON 'records' section"),
    (r"^Mode '(.+?)' non valido per azione '(.+?)'$", "Invalid mode '{0}' for action '{1}'"),
    (r"^Valore 'mode' non valido\. Usare: mirror, new\.$", "Invalid 'mode' value. Use: mirror, new."),
    (r"^Valore 'type' non valido\. Usare: file, filesync, ftp, ssh\.$", "Invalid 'type' value. Use: file, filesync, ftp, ssh."),
    (r"^path_dest mancante per azione '(.+?)'$", "Missing path_dest for action '{0}'"),
    (r"^path_source mancante per azione '(.+?)'$", "Missing path_source for action '{0}'"),
    (r"^Il parametro 'git_path' deve puntare a un file \.exe su Windows$", "Parameter 'git_path' must point to a .exe file on Windows"),
    (r"^Il parametro 'log' deve essere un percorso assoluto$", "Parameter 'log' must be an absolute path"),
    (r"^Parametro 'git_path' obbligatorio su Windows$", "Parameter 'git_path' required on Windows"),
    (r"^Parametro 'log' obbligatorio$", "Parameter 'log' required"),
    (r"^Parametro 'repo_name' obbligatorio$", "Parameter 'repo_name' required"),
    (r"^Parametro 'repo_path' obbligatorio$", "Parameter 'repo_path' required"),
    (r"^Parametro 'token' obbligatorio$", "Parameter 'token' required"),
    (r"^Parametro 'username' obbligatorio$", "Parameter 'username' required"),
    (r"^Git eseguibile non trovato in: (.*)$", "Git executable not found at: {0}"),
    (r"^Git non installato o non trovato nel PATH$", "Git not installed or not found in PATH"),
    (r"^Errore durante git commit: (.*)$", "Error during git commit: {0}"),
    (r"^Timeout durante git commit$", "Timeout during git commit"),
    (r"^Impossibile creare destinazione (.+?): (.*)$", "Cannot create destination {0}: {1}"),
    (r"^Impossibile creare file di log (.+?): (.*)$", "Cannot create log file {0}: {1}"),
    (r"^Copia fallita: (.*)$", "Copy failed: {0}"),
    (r"^Errore durante copia di (.+?): (.*)$", "Error copying {0}: {1}"),
    (r"^Generazione fallita: (.*)$", "Generation failed: {0}"),
    # --- raise: connessioni / eseguibili / librerie ---
    (r"^Connessione FTP fallita: (.*)$", "FTP connection failed: {0}"),
    (r"^Connessione SSH/SFTP fallita: (.*)$", "SSH/SFTP connection failed: {0}"),
    (r"^Avvio container fallito: (.*)$", "Container start failed: {0}"),
    (r"^Avvio macchina fallito: (.*)$", "Machine start failed: {0}"),
    (r"^Creazione container fallita: (.*)$", "Container creation failed: {0}"),
    (r"^Creazione macchina fallita: (.*)$", "Machine creation failed: {0}"),
    (r"^Container WSL '(.+?)' non trovato\. Container disponibili: (.*)$", "WSL container '{0}' not found. Available containers: {1}"),
    (r"^Errore API OpenRouter: (.+?) - (.*)$", "OpenRouter API error: {0} - {1}"),
    (r"^Errore di connessione API OpenRouter: (.*)$", "OpenRouter API connection error: {0}"),
    (r"^Errore durante la chiamata API: (.*)$", "Error during API call: {0}"),
    (r"^Timeout durante la chiamata API OpenRouter$", "Timeout during OpenRouter API call"),
    (r"^Errore durante la compressione 7z: (.*)$", "Error during 7z compression: {0}"),
    (r"^Errore durante la conversione: (.*)$", "Error during conversion: {0}"),
    (r"^Errore durante la lettura del file: (.*)$", "Error reading file: {0}"),
    (r"^Errore durante la scrittura del file: (.*)$", "Error writing file: {0}"),
    (r"^Eseguibile 7z (.+?) non trovato\.$", "7z executable {0} not found."),
    (r"^Eseguibile 7z non trovato nel sistema\.$", "7z executable not found on system."),
    (r"^qemu-img\.exe non trovato nel percorso: (.*)$", "qemu-img.exe not found at path: {0}"),
    (r"^Libreria markdown non installata\. Installarla con: (.*)$", "markdown library not installed. Install it with: {0}"),
    (r"^Libreria paramiko non installata\.$", "paramiko library not installed."),
    (r"^Libreria pypandoc non installata\. Installarla con: (.*)$", "pypandoc library not installed. Install it with: {0}"),
    (r"^Libreria pyt_form non installata\.$", "pyt_form library not installed."),
    (r"^Libreria pyt_bkh non installata\.$", "pyt_bkh library not installed."),
    (r"^Libreria pyt_report non installata\. Installarla con: (.*)$", "pyt_report library not installed. Install it with: {0}"),
    (r"^Libreria requests non installata\. Installarla con: (.*)$", "requests library not installed. Install it with: {0}"),
    (r"^Variabile d'ambiente (.+?) non impostata o vuota$", "Environment variable {0} not set or empty"),
    (r"^Variabile d'ambiente OPENROUTER_API non impostata\. Impostarla con: (.*)$", "Environment variable OPENROUTER_API not set. Set it with: {0}"),
    (r"^porta_host malformata '(.+?)'\. Uso: host:container \(es\. 8080:80\)\.$", "Malformed porta_host '{0}'. Use: host:container (e.g. 8080:80)."),
    (r"^La direttiva sync_script è utilizzabile solo su Windows \(richiede robocopy\)\.$", "Directive sync_script is only usable on Windows (requires robocopy)."),
    (r"^La direttiva vhdx2vmdk è utilizzabile solo su Windows\.$", "Directive vhdx2vmdk is only usable on Windows."),
    (r"^La direttiva wsl_export è utilizzabile solo su Windows\.$", "Directive wsl_export is only usable on Windows."),
    # --- descrizioni fasi (usate dentro "[ts] Fase N: ..." via traduzione ricorsiva) ---
    (r"^Lettura della lista (.*)$", "Reading list {0}"),
    (r"^Lettura e parsing di (.*)$", "Reading and parsing of {0}"),
    (r"^Lettura e validazione del file di configurazione JSON$", "Reading and validating the JSON configuration file"),
    (r"^Lettura file markdown (.*)$", "Reading markdown file {0}"),
    (r"^Lettura parametri e variabile d'ambiente SYNC_FOLDERS$", "Reading parameters and SYNC_FOLDERS environment variable"),
    (r"^Lettura spazio totale disco e spazio libero$", "Reading total disk space and free space"),
    (r"^Lettura template e file JSON completata\. Trovati (\d+) record\.$", "Reading template and JSON file completed. Found {0} records."),
    (r"^Scansione della cartella sorgente (.*)$", "Scanning source folder {0}"),
    (r"^Verifica parametri e prerequisiti$", "Checking parameters and prerequisites"),
    (r"^Cancellazione di (\d+) FILE$", "Deleting {0} FILEs"),
    (r"^Chiamata API OpenRouter per generare pagina HTML completa$", "Calling OpenRouter API to generate complete HTML page"),
    (r"^Conversione markdown in html$", "Converting markdown to html"),
    (r"^Costruzione dello script batch$", "Building the batch script"),
    (r"^Esecuzione git pull$", "Running git pull"),
    (r"^Esecuzione operazioni preliminari \(commit se richiesto\)$", "Running preliminary operations (commit if requested)"),
    (r"^Lettura metadata locali \(importlib\.metadata\)$", "Reading local metadata (importlib.metadata)"),
    (r"^Lettura spazio occupato per ogni singola cartella$", "Reading space used for each single folder"),
    (r"^Preparazione per git push$", "Preparing for git push"),
    (r"^Scansione di (.+?) e confronto$", "Scanning {0} and comparing"),
    (r"^Verifica macchina '(.+?)'$", "Checking machine '{0}'"),
    (r"^Arricchimento PyPI online per (\d+) librerie$", "Online PyPI enrichment for {0} libraries"),
    (r"^Arricchimento PyPI saltato \(libreria requests non installata\)$", "PyPI enrichment skipped (requests library not installed)"),
    (r"^Cancellazione di (\d+) DIR$", "Deleting {0} DIRs"),
    (r"^Esecuzione git push$", "Running git push"),
    (r"^Genera report$", "Generate report"),
    (r"^Riepilogo finale$", "Final summary"),
    (r"^Scrittura atomica del file di output$", "Atomic write of output file"),
    (r"^Scrittura della lista in (.*)$", "Writing list to {0}"),
    (r"^Scrittura file html (.*)$", "Writing html file {0}"),
    (r"^Volume (.+?):(.+)$", "Volume {0}:{1}"),
    (r"^Check occupazione rispetto a percentuale warning \((\d+)%\)$", "Checking usage against warning percentage ({0}%)"),
    (r"^Porta (.+?):(.+)$", "Port {0}:{1}"),
    (r"^Scrittura del Markdown in (.*)$", "Writing Markdown to {0}"),
    (r"^Verifica container '(.+?)'$", "Checking container '{0}'"),
    (r"^Creazione container '(.+?)' da '(.+?)'$", "Creating container '{0}' from '{1}'"),
    (r"^Lettura elenco modelli OpenRouter$", "Reading OpenRouter model list"),
    (r"^Lettura modelli coding OpenRouter$", "Reading OpenRouter coding models"),
    (r"^Generazione tabella HTML$", "Generating HTML table"),
    (r"^Scrittura file HTML (.*)$", "Writing HTML file {0}"),
    (r"^File HTML generato con successo: (.*)$", "HTML file successfully generated: {0}"),
    (r"^Scrittura file Excel (.*)$", "Writing Excel file {0}"),
    (r"^File Excel generato con successo: (.*)$", "Excel file successfully generated: {0}"),
    (r"^Libreria openpyxl non installata\. Installarla con: (.*)$", "openpyxl library not installed. Install it with: {0}"),
    (r"^Errore durante la scrittura del file Excel: (.*)$", "Error writing Excel file: {0}"),
    (r"^Nessun modello ricevuto dall'API OpenRouter$", "No models received from OpenRouter API"),
    (r"^Sottocomando orouter non riconosciuto: (.*?)\. Uso: orouter models <file\.html>\.$", "Unknown orouter subcommand: {0}. Usage: orouter models <file.html>."),
]

for _it, _en in _PYT_MSG_LIST:
    _pyt_AddMsg(_it, _en)
del _PYT_MSG_LIST

def pyt_Translate(msg):
    """Se la lingua rilevata non e' italiano, traduce il messaggio IT->EN; altrimenti lo restituisce invariato."""
    if PYT_LANG == "it" or not isinstance(msg, str) or not msg:
        return msg
    for rx, en in _PYT_MSG_EN:
        m = rx.match(msg)
        if m:
            # traduce anche i valori dinamici catturati (es. messaggi di errore annidati)
            groups = tuple(pyt_Translate(g) for g in m.groups())
            try:
                return en.format(*groups)
            except Exception:
                return en
    return msg

# ==============================================================================
# FUNZIONI INTERNE
# ==============================================================================
def pyt_Timestamp():
    """Restituisce una stringa nel formato YYYYMMDD:HHMMSS (ora locale)."""
    return datetime.datetime.now().strftime("%Y%m%d:%H%M%S")

def pyt_Print(stringa):
    """Stampa la stringa su console (tradotta IT/EN) e la aggiunge in coda al file pyt.log."""
    stringa = pyt_Translate(stringa)
    print(stringa)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(stringa + "\n")
    except Exception as e:
        print(f"Impossibile scrivere sul log: {e}")

def pyt_End():
    """Chiama pyt_Print con il messaggio di END."""
    pyt_Print("END: " + pyt_Timestamp())

# ==============================================================================
# PARSING ARGOMENTI
# ==============================================================================
def parse_argv(argv):
    """Analizza sys.argv e restituisce una lista di tuple (direttiva, [parametri])."""
    args = argv[1:]
    
    # 1. Nessun argomento
    if not args:
        return [(None, [])]
    
    # 2. File di direttive (@)
    if args[0] == "@":
        if len(args) < 2:
            pyt_Print("Errore: file di direttive non specificato dopo @.")
            sys.exit(1)
        fname = args[1].strip('"\'')
        if not os.path.exists(fname):
            pyt_Print(f"Errore: file di direttive {fname} non trovato.")
            sys.exit(1)
        directives = []
        with open(fname, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                parts = line.split()
                # Converte i punti in underscore per compatibilità con i nomi funzione
                directives.append((parts[0].lower().replace(".", "_"), parts[1:]))
        return directives
    
# 3. Singola direttiva - filtra stringhe vuote dai parametri
    filtered_params = [p for p in args[1:] if p and p.strip()]
    # Direttiva vuota (es. chiamata da wrapper senza comando) -> help
    if not args[0] or not args[0].strip():
        return [(None, filtered_params)]
    # Converte i punti in underscore per compatibilit�� con i nomi funzione
    directive_name = args[0].lower().replace(".", "_")
    return [(directive_name, filtered_params)]

# ==============================================================================
# FUNZIONI DIRETTIVE (app_*)
# ==============================================================================
def app_help():
    """Stampa l'help nella lingua rilevata (it/en). Non usa pyt_Print e non genera log START/END."""
    if PYT_LANG == "it":
        help_text = f"""pyt v{PYT_VER} - Tool Python per eseguire comandi via command line

DIRETTIVE DISPONIBILI:
help, h
   Mostra questo help. Non richiede parametri.
7z_ts <pathsource> [path7z]
   Comprime la cartella pathsource in un archivio .7z con timestamp (solo data)
bkh <sottocomando> [parametri]
   Gestisce i segnalibri (bookmark) di Chrome tramite la libreria esterna pyt_bkh.
   Sottocomandi: export, url, order, homepage, check, merge, delete, help.
   Esempi: bkh homepage examples/pyt_bkh_homepage.json; bkh help
@ <nome_file>
   Esegue le direttive contenute nel file specificato
delfiles <listfile.txt>
   Cancella i file e le cartelle elencati in listfile.txt (output di rightlist),
   usando i path assoluti scritti nelle voci. Prima i FILE, poi le DIR.
   Le righe senza prefisso FILE/DIR vengono interpretate dal disco.
   Funziona su Windows e Linux.
disk_check <disk_name> <disk_report> <warning_pct>
   Verifica spazio disco e occupazione cartelle, genera report ed eventuale flag di warning
doc2md <f1>
   Converte da docx a md il file f1, salvando file multimediali in resources/
form <fileform.json>
   Mostra un form interattivo descritto nel JSON (libreria pyt_form).
   Oggetti: THEME, WINDOW, LAYOUT, TEXT, LABEL, LIST, BUTTON, COMMAND.
   Modalit\u00e0 config.mode: TUI (console), GUI (tkinter), WEB (pagina+browser).
   Log in <fileform>.log, valori in <fileform>_results.json (o config.return.file).
git.pull <config.json>
   Esegue git pull da GitHub autenticato con token.
   JSON: repo_path, username, token, repo_name, branch, git_path, log.
   Supporta variabili d'ambiente: "$VAR_NAME" per token/username.
git.push <config.json>
   Esegue git push su GitHub autenticato con token.
   JSON: repo_path, username, token, repo_name, branch, git_path, log, commit_message (opz), commit_all (opz).
   Supporta variabili d'ambiente: "$VAR_NAME" per token/username.
   Windows: git_path obbligatorio (es. "X:\\_Applic\\Bash\\bin\\git.exe").
   Se commit_message \u00e8 presente, esegue git add e git commit prima del push.
grep [-i] [-v] [-r] [-p <path>] [-s <REPLo>] [-sx <REPLo>] <pattern> [file|dir...]
   Cerca un pattern (regex) in uno o piu' file o cartelle.
   -i ignora maiuscole/minuscole; -v seleziona le righe NON corrispondenti;
   -r ricerca ricorsiva nelle cartelle; -p <path> cartella base di ricerca
   -s <REPLo> / --replace=<REPLo> sostituisce il pattern (REPLo fisso, niente regex)
     con <REPLo> in tutti i file dove viene trovato; attende 1s dopo ogni file modificato.
   -sx <REPLo> / --simulate=<REPLo> simula la sostituzione (dry-run): mostra cosa cambierebbe
     senza modificare i file; attende 1s dopo ogni file simulato.
   (senza file elencati cerca tutti i file di <path>, con file relativi li
   risolve da l\u00ec; con -r scansiona anche le sottocartelle). Espande wildcard.
   Stampa sopra i risultati il file di provenienza. Log GREP.START/GREP.END.
   Funziona su Windows e Linux (spec: Prompt_pyt_grep.md).
md2html <f1> <f2>
   Converte un file markdown f1 in html f2
md2page <f1> <f2>
   Converte un file markdown f1 in una pagina html completa f2 usando OpenRouter API
orouter models <file.html>
   Genera un report HTML del catalogo modelli OpenRouter:
   id, free, input, output, architecture, pricing, coding, moderated,
   nome, costo input/output, context window (migliaia di token),
   parametri (miliardi) e data di creazione.
   Crea anche un file Excel (.xlsx) con lo stesso nome e le stesse colonne.
   Scarica l'elenco da OpenRouter (richiede la libreria requests).
podman <config.json>
   Gestisce container podman da JSON a sezioni con id.
   Ogni sezione: command (solo cstart), volume (opz, creato se manca),
   image, name, porta_host host:container (opz), machine (opz, avviata o creata).
   Funziona su Windows e Linux (richiede podman installato).
report <file_template> <file_json> <file_out_base>
   Genera report da template e dati JSON (libreria pyt_report).
   file_template: file template con segnaposto
   file_json: file JSON con sezione "records" contenente ID e campi
   file_out_base: base nome file output (verr\u00e0 aggiunto ID + estensione)
reqdoc <requirements.txt>
   Genera file Markdown con stesso nome che documenta le librerie:
   nome, versione, scopo, dipendenze, home-page.
   Dati locali (importlib.metadata) + arricchimento PyPI online se disponibile.
   Funziona su Windows e Linux.
rightlist <path_sorgente> <path_verifica> <listfile.txt>
   Elenca in listfile.txt (con path assoluti) i file e le cartelle
   presenti in path_verifica ma assenti in path_sorgente.
   Funziona su Windows e Linux.
robocopy <config.json>
   Copia file specificati da sorgente a destinazione secondo JSON.
   Supporta settings globali (log, err.exit) e actions multiple con path_source, path_dest, mode (overwrite|old),
   files[].
   Funziona su Windows e Linux (usa shutil, non robocopy.exe).
sync <config.json>
   Sincronizza cartelle secondo un file di configurazione JSON.
   Supporta type: file, filesync, ftp, ssh.
   Supporta sia JSON con singolo job sia JSON "catalogo" con array "jobs".
sync_script [path_source] [path_dest] [file_output]
   Genera uno script batch per sincronizzazione mirror con robocopy (solo Windows).
   Parametri opzionali: sorgente (default \\ntgdsnas), dest (default n:), output (default admin_sync_script.cmd).
   Usa variabile d'ambiente SYNC_FOLDERS per lista cartelle.
vhdx2vmdk <f1> <f2>
   Converte file vhdx in vmdk usando qemu-img (solo Windows)
wsl_export <f1> <f2>
   Esporta il container WSL f1 nel file f2 (solo Windows)

help bkh
   Mostra l'help dettagliato per la direttiva bkh (gestione bookmark Chrome)
"""
    else:
        help_text = f"""pyt v{PYT_VER} - Python tool to run commands via command line

AVAILABLE DIRECTIVES:
help, h
   Shows this help. No parameters required.
7z_ts <pathsource> [path7z]
   Compresses the pathsource folder into a .7z archive with timestamp (date only)
bkh <subcommand> [parameters]
   Manages Chrome bookmarks through the external pyt_bkh library.
   Subcommands: export, url, order, homepage, check, merge, delete, help.
   Examples: bkh homepage examples/pyt_bkh_homepage.json; bkh help
@ <file_name>
   Runs the directives contained in the specified file
delfiles <listfile.txt>
   Deletes files and folders listed in listfile.txt (rightlist output),
   using the absolute paths written in the entries. FILEs first, then DIRs.
   Lines without FILE/DIR prefix are detected from the drive.
   Works on Windows and Linux.
disk_check <disk_name> <disk_report> <warning_pct>
   Checks disk space and folder usage, generates report and optional warning flag
doc2md <f1>
   Converts file f1 from docx to md, saving media files in resources/
form <fileform.json>
   Shows an interactive form described in the JSON (pyt_form library).
   Objects: THEME, WINDOW, LAYOUT, TEXT, LABEL, LIST, BUTTON, COMMAND.
   config.mode modes: TUI (console), GUI (tkinter), WEB (page+browser).
   Log in <fileform>.log, values in <fileform>_results.json (or config.return.file).
git.pull <config.json>
   Performs git pull from GitHub authenticated with token.
   JSON: repo_path, username, token, repo_name, branch, git_path, log.
   Supports environment variables: "$VAR_NAME" for token/username.
git.push <config.json>
   Performs git push to GitHub authenticated with token.
   JSON: repo_path, username, token, repo_name, branch, git_path, log, commit_message (opt), commit_all (opt).
   Supports environment variables: "$VAR_NAME" for token/username.
   Windows: git_path required (e.g. "X:\\_Applic\\Bash\\bin\\git.exe").
   If commit_message is present, runs git add and git commit before the push.
grep [-i] [-v] [-r] [-p <path>] [-s <text>] [-sx <text>] <pattern> [file|dir...]
   Searches a pattern (regex) in one or more files or folders.
   -i ignores case; -v selects NON matching lines;
   -r recursive search in folders; -p <path> base search folder
   -s <text> / --replace=<text> replaces the pattern (fixed text, no regex)
     with <text> in all files where found; waits 1s after each modified file.
   -sx <text> / --simulate=<text> simulates replacement (dry-run): shows what would change
     without modifying files; waits 1s after each simulated file.
   (without listed files searches all files of <path>, relative files are
   resolved from there; with -r also scans subfolders). Expands wildcards.
   Prints the source file above the results. Logs GREP.START/GREP.END.
   Works on Windows and Linux (spec: Prompt_pyt_grep.md).
   resolved from there; with -r also scans subfolders). Expands wildcards.
   Prints the source file above the results. Logs GREP.START/GREP.END.
   Works on Windows and Linux (spec: Prompt_pyt_grep.md).
md2html <f1> <f2>
   Converts markdown file f1 into html file f2
md2page <f1> <f2>
   Converts markdown file f1 into a complete html page f2 using OpenRouter API
orouter models <file.html>
   Generates an HTML report of the OpenRouter model catalog:
   id, free, input, output, architecture, pricing, coding, moderated,
   name, input/output cost, context window (thousands of tokens),
   parameters (billions) and creation date.
   Also creates an Excel file (.xlsx) with the same name and columns.
   Downloads the list from OpenRouter (requires the requests library).
podman <config.json>
   Manages podman containers from JSON with sections keyed by id.
   Each section: command (cstart only), volume (opt, created if missing),
   image, name, porta_host host:container (opt), machine (opt, started or created).
   Works on Windows and Linux (requires podman installed).
report <file_template> <file_json> <file_out_base>
   Generates reports from template and JSON data (pyt_report library).
   file_template: template file with placeholders
   file_json: JSON file with "records" section containing ID and fields
   file_out_base: output file name base (ID + extension will be added)
reqdoc <requirements.txt>
   Generates a Markdown file with the same name documenting the libraries:
   name, version, purpose, dependencies, home-page.
   Local data (importlib.metadata) + online PyPI enrichment if available.
   Works on Windows and Linux.
rightlist <path_source> <path_check> <listfile.txt>
   Lists in listfile.txt (absolute paths) the files and folders
   present in path_check but missing in path_source.
   Works on Windows and Linux.
robocopy <config.json>
   Copies files specified from source to destination according to JSON.
   Supports global settings (log, err.exit) and multiple actions with path_source, path_dest, mode (overwrite|old),
   files[].
   Works on Windows and Linux (uses shutil, not robocopy.exe).
sync <config.json>
   Synchronizes folders according to a JSON configuration file.
   Supports type: file, filesync, ftp, ssh.
   Supports both single-job JSON and "catalog" JSON with "jobs" array.
sync_script [path_source] [path_dest] [file_output]
   Generates a batch script for mirror synchronization with robocopy (Windows only).
   Optional parameters: source (default \\ntgdsnas), dest (default n:), output (default admin_sync_script.cmd).
   Uses SYNC_FOLDERS environment variable for the folder list.
vhdx2vmdk <f1> <f2>
   Converts vhdx file into vmdk using qemu-img (Windows only)
wsl_export <f1> <f2>
   Exports WSL container f1 into file f2 (Windows only)

help bkh
   Shows detailed help for the bkh directive (Chrome bookmarks management)
"""
    print(help_text)

def app_doc2md(params):
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: doc2md <f1>")
    
    f1 = params[0].strip('"\'')
    
    if not os.path.exists(f1):
        raise FileNotFoundError(f"File {f1} non trovato.")
    
    if pypandoc is None:
        raise ImportError("Libreria pypandoc non installata. Installarla con: pip install pypandoc")
    
    out_dir = os.path.dirname(os.path.abspath(f1))
    out_file = os.path.splitext(f1)[0] + ".md"
    res_dir = os.path.join(out_dir, "resources")
    
    pypandoc.convert_file(f1, 'md', outputfile=out_file, extra_args=[f'--extract-media={res_dir}'])
    pyt_Print(f"Convertito con successo: {out_file}")

def app_md2html(params):
    """Converte un file markdown in html."""
    if len(params) != 2:
        raise ValueError("Sintassi errata. Uso: md2html <f1> <f2>")
    
    f1 = params[0].strip('"\'')
    f2 = params[1].strip('"\'')
    
    if not os.path.exists(f1):
        raise FileNotFoundError(f"File sorgente {f1} non trovato.")
    
    if markdown is None:
        raise ImportError("Libreria markdown non installata. Installarla con: pip install markdown")
    
    # Fase 1: Lettura file markdown
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura file markdown {f1}")
    try:
        with open(f1, "r", encoding="utf-8") as f:
            md_content = f.read()
    except Exception as e:
        raise RuntimeError(f"Errore durante la lettura del file: {e}")
    
    # Fase 2: Conversione markdown in html
    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Conversione markdown in html")
    try:
        html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'codehilite'])
    except Exception as e:
        raise RuntimeError(f"Errore durante la conversione: {e}")
    
    # Fase 3: Scrittura file html
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Scrittura file html {f2}")
    try:
        with open(f2, "w", encoding="utf-8") as f:
            f.write(html_content)
        pyt_Print(f"Convertito con successo: {f2}")
    except Exception as e:
        raise RuntimeError(f"Errore durante la scrittura del file: {e}")

def app_md2page(params):
    """Converte un file markdown in una pagina html completa usando OpenRouter API."""
    if len(params) != 2:
        raise ValueError("Sintassi errata. Uso: md2page <f1> <f2>")
    
    f1 = params[0].strip('"\'')
    f2 = params[1].strip('"\'')
    
    if not os.path.exists(f1):
        raise FileNotFoundError(f"File sorgente {f1} non trovato.")
    
    # Verifica variabile d'ambiente
    api_key = os.environ.get("OPENROUTER_API")
    if not api_key:
        raise EnvironmentError("Variabile d'ambiente OPENROUTER_API non impostata. Impostarla con: export OPENROUTER_API=your_key (Linux) o set OPENROUTER_API=your_key (Windows)")
    
    # Fase 1: Lettura file markdown
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura file markdown {f1}")
    try:
        with open(f1, "r", encoding="utf-8") as f:
            md_content = f.read()
    except Exception as e:
        raise RuntimeError(f"Errore durante la lettura del file: {e}")
    
    # Fase 2: Chiamata API OpenRouter
    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Chiamata API OpenRouter per generare pagina HTML completa")
    if requests is None:
        raise ImportError("Libreria requests non installata. Installarla con: pip install requests")
    prompt = f"""Converti il seguente contenuto markdown in una pagina HTML completa e ben strutturata.
La pagina deve includere:
- DOCTYPE HTML5
- Meta tag appropriati (charset, viewport)
- Titolo derivato dal contenuto
- CSS inline moderno e responsive per una buona leggibilità
- Struttura semantica HTML5 (header, main, footer se appropriato)
- Supporto per codice con syntax highlighting
- Design pulito e professionale

Contenuto markdown da convertire:
{md_content}

Restituisci SOLO il codice HTML completo, senza spiegazioni o REPLo aggiuntivo."""
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=60
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Errore API OpenRouter: {response.status_code} - {response.text}")
        
        result = response.json()
        html_content = result["choices"][0]["message"]["content"].strip()
        
        # Rimuovi eventuali markdown code block wrappers
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.startswith("```"):
            html_content = html_content[3:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
        html_content = html_content.strip()
        
    except requests.exceptions.Timeout:
        raise RuntimeError("Timeout durante la chiamata API OpenRouter")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Errore di connessione API OpenRouter: {e}")
    except Exception as e:
        raise RuntimeError(f"Errore durante la chiamata API: {e}")
    
    # Fase 3: Scrittura file html
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Scrittura file html {f2}")
    try:
        with open(f2, "w", encoding="utf-8") as f:
            f.write(html_content)
        pyt_Print(f"Pagina HTML generata con successo: {f2}")
    except Exception as e:
        raise RuntimeError(f"Errore durante la scrittura del file: {e}")

def _orouter_price_value(pricing, key):
    """Restituisce il prezzo per token come float, oppure None se non disponibile."""
    try:
        return float(pricing.get(key))
    except (TypeError, ValueError):
        return None

def _orouter_price_per_million(value):
    """Formatta un prezzo per token come stringa USD per 1M di token."""
    if value is None:
        return "N/D"
    if value < 0:
        return "Dinamico"
    return f"${value * 1_000_000:.2f}"

def _orouter_pricing_mode(price_in, price_out):
    """Classifica la modalita' di pricing: Gratis, Per token, Dinamico o N/D."""
    if price_in is None or price_out is None:
        return "N/D"
    if price_in < 0 or price_out < 0:
        return "Dinamico"
    if price_in == 0 and price_out == 0:
        return "Gratis"
    return "Per token"

def _orouter_params_from_text(text):
    """Estrae i miliardi di parametri da una stringa (es. 70b, 8x7b)."""
    moe = re.search(r"(\d+(?:\.\d+)?)\s*[x\u00d7]\s*(\d+(?:\.\d+)?)\s*b\b", text, re.IGNORECASE)
    if moe:
        try:
            return float(moe.group(1)) * float(moe.group(2))
        except (TypeError, ValueError):
            pass
    single = re.search(r"(\d+(?:\.\d+)?)\s*b\b", text, re.IGNORECASE)
    if single:
        try:
            return float(single.group(1))
        except (TypeError, ValueError):
            pass
    return None

def _orouter_params_billions(model):
    """Stima i parametri in miliardi da hugging_face_id/id/name, oppure 'N/D'."""
    for key in ("hugging_face_id", "id", "name"):
        text = model.get(key)
        if not text:
            continue
        value = _orouter_params_from_text(str(text))
        if value is not None:
            return f"{value:g}"
    return "N/D"

def _orouter_context_thousands(model):
    """Restituisce la context window in migliaia di token, oppure 'N/D'."""
    value = model.get("context_length")
    if value is None:
        top = model.get("top_provider") or {}
        value = top.get("context_length")
    try:
        value = int(value)
    except (TypeError, ValueError):
        return "N/D"
    if value <= 0:
        return "N/D"
    return f"{round(value / 1000):d}"

def _orouter_created_date(value):
    """Converte il timestamp Unix 'created' in data gg/mm/aaaa, oppure 'N/D'."""
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return "N/D"
    if timestamp <= 0:
        return "N/D"
    return datetime.datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y")

def _orouter_build_html(models, coding_ids):
    """Costruisce il documento HTML e restituisce (documento, righe) del report."""
    updated = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    free_count = sum(
        1 for m in models
        if (_orouter_price_value(m.get("pricing") or {}, "prompt") == 0
            and _orouter_price_value(m.get("pricing") or {}, "completion") == 0)
    )

    rows = []
    for m in models:
        model_id = str(m.get("id", ""))
        name = str(m.get("name", model_id))
        arch = m.get("architecture") or {}
        in_mod = ", ".join(arch.get("input_modalities") or ["text"])
        out_mod = ", ".join(arch.get("output_modalities") or ["text"])
        modality = str(arch.get("modality") or "") or "N/D"
        top = m.get("top_provider") or {}
        moderated = top.get("is_moderated")
        pricing = m.get("pricing") or {}
        price_in = _orouter_price_value(pricing, "prompt")
        price_out = _orouter_price_value(pricing, "completion")
        is_free = price_in == 0 and price_out == 0
        is_coding = model_id in coding_ids
        rows.append({
            "model_id": model_id,
            "name": name,
            "in_mod": in_mod,
            "out_mod": out_mod,
            "architecture": modality,
            "moderated": moderated,
            "created": _orouter_created_date(m.get("created")),
            "pricing": _orouter_pricing_mode(price_in, price_out),
            "coding": is_coding,
            "free": is_free,
            "cost_in": _orouter_price_per_million(price_in),
            "cost_out": _orouter_price_per_million(price_out),
            "context": _orouter_context_thousands(m),
            "parb": _orouter_params_billions(m),
        })

    rows.sort(key=lambda r: (0 if r["free"] else 1, r["name"].lower(), r["model_id"].lower()))

    body_rows = []
    for r in rows:
        free_badge = '<span class="badge badge-free">Si</span>' if r["free"] else '<span class="badge badge-no">No</span>'
        coding_badge = '<span class="badge badge-coding">Si</span>' if r["coding"] else '<span class="badge badge-no">No</span>'
        if r["moderated"] is True:
            moderated_badge = '<span class="badge badge-coding">Si</span>'
        elif r["moderated"] is False:
            moderated_badge = '<span class="badge badge-no">No</span>'
        else:
            moderated_badge = '<span class="badge badge-no">N/D</span>'
        body_rows.append(
            "<tr>"
            f"<td class=\"modelid\"><code title=\"{_html.escape(r['model_id'])}\">{_html.escape(r['model_id'])}</code></td>"
            f"<td>{free_badge}</td>"
            f"<td>{_html.escape(r['in_mod'])}</td>"
            f"<td>{_html.escape(r['out_mod'])}</td>"
            f"<td class=\"arch\">{_html.escape(r['architecture'])}</td>"
            f"<td>{_html.escape(r['pricing'])}</td>"
            f"<td>{coding_badge}</td>"
            f"<td>{moderated_badge}</td>"
            f"<td>{_html.escape(r['name'])}</td>"
            f"<td class=\"num\">{_html.escape(r['cost_in'])}</td>"
            f"<td class=\"num\">{_html.escape(r['cost_out'])}</td>"
            f"<td class=\"num\">{_html.escape(r['context'])}</td>"
            f"<td class=\"num\">{_html.escape(r['parb'])}</td>"
            f"<td class=\"created\">{_html.escape(r['created'])}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Catalogo Modelli OpenRouter</title>
<style>
:root {{
  --bg: #f6f8fb;
  --panel: #ffffff;
  --ink: #1b2430;
  --muted: #5b6b7c;
  --line: #dbe3ec;
  --accent: #1f6feb;
  --free-bg: #d8f5e3;
  --free-ink: #116329;
  --code-bg: #eef2f7;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 32px 20px;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.45;
}}
header {{ max-width: 1400px; margin: 0 auto 20px; }}
h1 {{ margin: 0 0 6px; font-size: 1.7rem; letter-spacing: -0.02em; }}
.meta {{ margin: 0 0 4px; color: var(--muted); font-size: 0.95rem; }}
.meta strong {{ color: var(--ink); }}
.made {{ margin: 0 0 8px; color: var(--muted); font-size: 0.85rem; }}
.made a {{ color: var(--accent); text-decoration: none; }}
.made a:hover {{ text-decoration: underline; }}
.note {{ margin: 8px 0 0; color: var(--muted); font-size: 0.86rem; }}
main {{ max-width: 1400px; margin: 0 auto; }}
.table-wrap {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: auto;
  box-shadow: 0 6px 22px rgba(20, 40, 70, 0.06);
}}
table {{ width: 100%; border-collapse: collapse; font-size: 0.89rem; }}
thead th {{
  position: sticky;
  top: 0;
  z-index: 1;
  background: #eef3f9;
  color: #28384a;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}}
tbody td {{ padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
tbody tr:nth-child(even) {{ background: #fbfcfe; }}
tbody tr:hover {{ background: #eff6ff; }}
tbody tr:last-child td {{ border-bottom: 0; }}
code {{
  background: var(--code-bg);
  border-radius: 5px;
  padding: 1px 5px;
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 0.84rem;
  white-space: nowrap;
}}
.badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
}}
.badge-free {{ background: var(--free-bg); color: var(--free-ink); }}
.badge-coding {{ background: #e4ecff; color: #1c4fd8; }}
.badge-no {{ background: #eef1f5; color: #6b7785; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
th.modelid, td.modelid {{ width: 130px; max-width: 130px; padding-left: 8px; padding-right: 8px; }}
td.modelid code {{ white-space: normal; overflow-wrap: anywhere; word-break: break-word; }}
td.arch {{ max-width: 200px; overflow-wrap: anywhere; word-break: break-word; }}
td.created {{ white-space: nowrap; }}
footer {{ max-width: 1400px; margin: 18px auto 0; color: var(--muted); font-size: 0.8rem; }}
@media (max-width: 720px) {{
  body {{ padding: 18px 10px; }}
  h1 {{ font-size: 1.35rem; }}
  table {{ font-size: 0.82rem; }}
}}
</style>
</head>
<body>
<header>
  <h1>Catalogo Modelli OpenRouter</h1>
  <p class="made">Made from <a href="https://github.com/ntgcorp/adminscripts" target="_blank" rel="noopener">ntgcorp\\adminscripts\\pyt</a></p>
  <p class="meta">Aggiornato il <strong>{updated}</strong> &middot; Totale modelli: <strong>{len(models)}</strong> &middot; Gratuiti: <strong>{free_count}</strong></p>
  <p class="note">Prezzi in USD per 1 milione di token (Input / Output). La colonna <strong>Pricing</strong> indica la modalita' tariffaria; <strong>Coding</strong> segnala i modelli della categoria Programming di OpenRouter; <strong>Architecture</strong> riporta la modalita' I/O compatta; <strong>Moderated</strong> il flag del provider; <strong>Created</strong> la data di inserimento in OpenRouter. <strong>Context</strong> = context window in migliaia di token; <strong>Parb</strong> = parametri in miliardi (dedotti da nome/id quando non forniti dall'API).</p>
</header>
<main>
<div class="table-wrap">
<table>
<thead>
<tr>
<th class="modelid">ModelId</th>
<th>Free</th>
<th>Input</th>
<th>Output</th>
<th>Architecture</th>
<th>Pricing</th>
<th>Coding</th>
<th>Moderated</th>
<th>Model Name</th>
<th>Costo Input (/1M)</th>
<th>Costo Output (/1M)</th>
<th>Context (k)</th>
<th>Parb (B)</th>
<th>Created</th>
</tr>
</thead>
<tbody>
{chr(10).join(body_rows)}
</tbody>
</table>
</div>
</main>
<footer>Report generato da pyt orouter models &middot; {updated}</footer>
</body>
</html>
""", rows

def _orouter_write_xlsx(rows, xlsx_file):
    """Scrive le righe del report in un file XLSX (solo tabella, senza intestazioni)."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Modelli"
    sheet.append([
        "ModelId", "Free", "Input", "Output", "Architecture", "Pricing",
        "Coding", "Moderated", "Model Name", "Costo Input (/1M)",
        "Costo Output (/1M)", "Context (k)", "Parb (B)", "Created",
    ])
    for r in rows:
        if r["moderated"] is True:
            moderated = "Si"
        elif r["moderated"] is False:
            moderated = "No"
        else:
            moderated = "N/D"
        sheet.append([
            r["model_id"],
            "Si" if r["free"] else "No",
            r["in_mod"],
            r["out_mod"],
            r["architecture"],
            r["pricing"],
            "Si" if r["coding"] else "No",
            moderated,
            r["name"],
            r["cost_in"],
            r["cost_out"],
            r["context"],
            r["parb"],
            r["created"],
        ])
    workbook.save(xlsx_file)

def app_orouter(params):
    """Genera un report HTML e un file Excel del catalogo modelli OpenRouter (sottocomando models)."""
    if len(params) != 2:
        raise ValueError("Sintassi errata. Uso: orouter models <file.html>")

    subcommand = params[0].strip('"\'').lower()
    if subcommand != "models":
        raise ValueError(f"Sottocomando orouter non riconosciuto: {subcommand}. Uso: orouter models <file.html>.")

    out_file = params[1].strip('"\'')
    if not out_file:
        raise ValueError("Sintassi errata. Uso: orouter models <file.html>")

    if requests is None:
        raise ImportError("Libreria requests non installata. Installarla con: pip install requests")
    if openpyxl is None:
        raise ImportError("Libreria openpyxl non installata. Installarla con: pip install openpyxl")

    # Fase 1: elenco completo dei modelli (testo, immagini, audio, ecc.)
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura elenco modelli OpenRouter")
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models?output_modalities=all",
            timeout=30
        )
        if response.status_code != 200:
            raise RuntimeError(f"Errore API OpenRouter: {response.status_code} - {response.text}")
        models = response.json().get("data", [])
    except requests.exceptions.Timeout:
        raise RuntimeError("Timeout durante la chiamata API OpenRouter")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Errore di connessione API OpenRouter: {e}")
    except (ValueError, AttributeError) as e:
        raise RuntimeError(f"Risposta API OpenRouter non valida: {e}")

    if not models:
        raise RuntimeError("Nessun modello ricevuto dall'API OpenRouter")

    # Fase 2: modelli della categoria programming (facoltativa)
    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Lettura modelli coding OpenRouter")
    coding_ids = set()
    try:
        coding_response = requests.get(
            "https://openrouter.ai/api/v1/models?category=programming",
            timeout=30
        )
        if coding_response.status_code == 200:
            coding_ids = {m.get("id") for m in coding_response.json().get("data", [])}
    except requests.exceptions.RequestException:
        # La colonna Coding e' informativa: un errore non blocca il report.
        coding_ids = set()

    # Fase 3: costruzione tabella HTML
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Generazione tabella HTML")
    document, rows = _orouter_build_html(models, coding_ids)
    xlsx_file = os.path.splitext(out_file)[0] + ".xlsx"

    # Fase 4: scrittura file
    pyt_Print(f"[{pyt_Timestamp()}] Fase 4: Scrittura file HTML {out_file}")
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(document)
    except Exception as e:
        raise RuntimeError(f"Errore durante la scrittura del file: {e}")

    # Fase 5: scrittura file Excel
    pyt_Print(f"[{pyt_Timestamp()}] Fase 5: Scrittura file Excel {xlsx_file}")
    try:
        _orouter_write_xlsx(rows, xlsx_file)
    except Exception as e:
        raise RuntimeError(f"Errore durante la scrittura del file Excel: {e}")

    pyt_Print(f"File HTML generato con successo: {out_file} ({len(models)} modelli)")
    pyt_Print(f"File Excel generato con successo: {xlsx_file} ({len(models)} modelli)")

def _bkh_fallback_help():
    """Help essenziale di bkh quando la libreria pyt_bkh non e' disponibile."""
    if PYT_LANG == "it":
        return (
            "bkh <sottocomando> [parametri]\n"
            "  export [file.html]           esporta i bookmark di Chrome in HTML\n"
            "  url <file.html> <cartella>   converte i link in file .url\n"
            "  order <config.json>          ordina i bookmark (normal/smart)\n"
            "  homepage <config.json>       pagina HTML multicolonne con icone\n"
            "  check <in.html> <out.html>   verifica URL e scrive i non accessibili\n"
            "  merge <in> <add> <new>       unisce bookmark rinominando i duplicati\n"
            "  delete <in> <del> <out>      rimuove da <in> gli URL presenti in <del>\n"
            "  help                         questo aiuto\n"
            "  (richiede la libreria esterna pyt_bkh.py)"
        )
    return (
        "bkh <subcommand> [parameters]\n"
        "  export [file.html]           export Chrome bookmarks to HTML\n"
        "  url <file.html> <folder>     convert links to .url files\n"
        "  order <config.json>          sort bookmarks (normal/smart)\n"
        "  homepage <config.json>       multi-column HTML page with icons\n"
        "  check <in.html> <out.html>   check URLs and write unreachable ones\n"
        "  merge <in> <add> <new>       merge bookmarks, renaming duplicates\n"
        "  delete <in> <del> <out>      remove from <in> the URLs in <del>\n"
        "  help                         this help\n"
        "  (requires the external pyt_bkh.py library)"
    )

def app_bkh(params):
    """Gestisce i segnalibri (bookmark) di Chrome tramite la libreria esterna pyt_bkh.

    Sottocomandi:
      bkh export [file.html]          esporta i bookmark Chrome in un file HTML
      bkh url <file.html> <cartella>  converte i link in file .url nella cartella
      bkh order <config.json>         ordina i bookmark (normal/smart)
      bkh homepage <config.json>      crea una pagina HTML multicolonne con icone
      bkh check <in.html> <out.html>  verifica gli URL e scrive i non accessibili
      bkh merge <in> <add> <new>      unisce 2 bookmark rinominando i duplicati
      bkh delete <in> <del> <out>     rimuove da <in> gli URL presenti in <del>
      bkh help                        aiuto dettagliato con esempi
    """
    if not params:
        raise ValueError(
            "Sintassi errata. Uso: bkh <sottocomando> [parametri]. "
            "Sottocomandi: export, url, order, homepage, check, merge, delete, help"
        )

    subcmd = params[0].strip('"\'').lower()

    if subcmd in ("help", "h", "-h", "--help"):
        try:
            import pyt_bkh
        except ImportError:
            print(_bkh_fallback_help())
            return
        print(pyt_bkh.help_text(PYT_LANG))
        return

    try:
        import pyt_bkh
    except ImportError:
        raise ImportError("Libreria pyt_bkh non installata.")

    if subcmd not in ("export", "url", "order", "homepage", "check", "merge", "delete"):
        raise ValueError(
            f"Sottocomando bkh sconosciuto: {subcmd}. "
            "Usare: export, url, order, homepage, check, merge, delete, help"
        )

    pyt_Print(f"[{pyt_Timestamp()}] START: bkh {subcmd}")
    pyt_Print(f"[{pyt_Timestamp()}] ARGS: {' '.join(params[1:])}")

    if subcmd == "export":
        result = pyt_bkh.run_export(params[1:], pyt_Print, pyt_Timestamp)
    elif subcmd == "url":
        result = pyt_bkh.run_url(params[1:], pyt_Print, pyt_Timestamp)
    elif subcmd == "order":
        result = pyt_bkh.run_order(params[1:], pyt_Print, pyt_Timestamp)
    elif subcmd == "homepage":
        result = pyt_bkh.run_homepage(params[1:], pyt_Print, pyt_Timestamp)
    elif subcmd == "check":
        result = pyt_bkh.run_check(params[1:], pyt_Print, pyt_Timestamp)
    elif subcmd == "merge":
        result = pyt_bkh.run_merge(params[1:], pyt_Print, pyt_Timestamp)
    else:
        result = pyt_bkh.run_delete(params[1:], pyt_Print, pyt_Timestamp)

    if result:
        pyt_Print(f"[{pyt_Timestamp()}] WRITE: {result}")

def app_wsl_export(params):
    if os.name != 'nt':
        raise OSError("La direttiva wsl_export è utilizzabile solo su Windows.")
    
    if len(params) != 2:
        raise ValueError("Sintassi errata. Uso: wsl_export <f1> <f2>")
    
    f1 = params[0].strip('"\'')
    f2 = params[1].strip('"\'')
    
    res = subprocess.run(["wsl", "--list", "--quiet"], capture_output=True, text=True)
    
    # Pulizia output WSL (rimuove caratteri nulli e spazi)
    containers = [c.strip().replace('\x00', '') for c in res.stdout.splitlines() if c.strip()]
    
    if f1 not in containers:
        raise ValueError(f"Container WSL '{f1}' non trovato. Container disponibili: {', '.join(containers)}")
    
    subprocess.run(["wsl", "--export", f1, f2], check=True, capture_output=True, text=True)
    pyt_Print(f"Container '{f1}' esportato in: {f2}")

def app_vhdx2vmdk(params):
    if os.name != 'nt':
        raise OSError("La direttiva vhdx2vmdk è utilizzabile solo su Windows.")
    
    if len(params) != 2:
        raise ValueError("Sintassi errata. Uso: vhdx2vmdk <f1> <f2>")
    
    f1 = params[0].strip('"\'')
    f2 = params[1].strip('"\'')
    
    if not os.path.exists(f1):
        raise FileNotFoundError(f"File sorgente {f1} non trovato.")
    
    if not os.path.exists(QEMU_IMG):
        raise FileNotFoundError(f"qemu-img.exe non trovato nel percorso: {QEMU_IMG}")
    
    cmd = [QEMU_IMG, "convert", "-f", "vhdx", "-O", "vmdk", f1, f2]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    pyt_Print(f"Convertito {f1} in {f2}")

def app_disk_check(params):
    if len(params) != 3:
        raise ValueError("Sintassi errata. Uso: disk_check <disk_name> <disk_report> <warning_pct>")
    
    disk_name = params[0].strip('"\'')
    disk_report = params[1].strip('"\'')
    warning_pct = float(params[2])
    
    flg_file = os.path.join(SCRIPT_DIR, "disk_warning.flg")
    if os.path.exists(flg_file):
        os.remove(flg_file)
    
    # Fase 1
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura spazio totale disco e spazio libero")
    usage = shutil.disk_usage(disk_name)
    total_gb = usage.total / (1024**3)
    free_gb = usage.free / (1024**3)
    used_gb = usage.used / (1024**3)
    used_pct = (usage.used / usage.total) * 100
    
    # Fase 2
    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Lettura spazio occupato per ogni singola cartella")
    folder_sizes = {}
    try:
        for item in os.listdir(disk_name):
            item_path = os.path.join(disk_name, item)
            if os.path.isdir(item_path):
                size = 0
                for root, dirs, files in os.walk(item_path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            size += os.path.getsize(fp)
                        except OSError:
                            pass
                folder_sizes[item] = size
                pyt_Print(f"  {item}: {size / (1024**3):.2f} GB")
    except PermissionError:
        pyt_Print("  Attenzione: permessi insufficienti per leggere alcune cartelle.")
    
    # Fase 3
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Genera report")
    with open(disk_report, "w", encoding="utf-8") as f:
        f.write(f"Report Disco: {disk_name}\n")
        f.write(f"Totale: {total_gb:.2f} GB\n")
        f.write(f"Usato: {used_gb:.2f} GB ({used_pct:.2f}%)\n")
        f.write(f"Libero: {free_gb:.2f} GB\n\n")
        f.write("Occupazione cartelle principali:\n")
        for k, v in folder_sizes.items():
            f.write(f"  {k}: {v / (1024**3):.2f} GB\n")
    
    # Fase 4
    pyt_Print(f"[{pyt_Timestamp()}] Fase 4: Check occupazione rispetto a percentuale warning ({warning_pct}%)")
    if used_pct >= warning_pct:
        with open(flg_file, "w", encoding="utf-8") as f:
            f.write(f"Warning: spazio usato {used_pct:.2f}% >= soglia {warning_pct}%\n")
        pyt_Print(f"WARNING: Spazio usato {used_pct:.2f}% supera la soglia di {warning_pct}%")

# ==============================================================================
# FUNZIONE SYNC - VERSIONE CON SUPPORTO filesync
# ==============================================================================
def _normalize_path(p):
    r"""Normalizza un percorso: converte // in \ su Windows per i percorsi UNC."""
    if not isinstance(p, str):
        return p
    # Se inizia con // (UNC style), su Windows lo converte in \
    if p.startswith("//") and os.name == 'nt':
        p = "\\" + p[1:]  # //server/share -> \\server\share
    # Normalizza eventuali slash misti
    p = p.replace("/", "\\") if os.name == 'nt' else p.replace("\\", "/")
    return p

def app_sync(params):
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: sync <config.json>")
    
    f1 = params[0].strip('"\'')
    
    if not os.path.exists(f1):
        raise FileNotFoundError(f"File di configurazione {f1} non trovato.")
    
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura e validazione del file di configurazione JSON")
    try:
        with open(f1, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato: {e}")
    
    # Debug: mostra le chiavi trovate nel JSON
    pyt_Print(f"  Chiavi trovate nel JSON: {list(data.keys())}")
    
    # Rileva se il JSON è un "catalogo" (con chiave jobs) o un singolo job
    jobs_key = next((k for k in data.keys() if k.strip().lower() == "jobs"), None)
    if jobs_key:
        pyt_Print(f"  Rilevata chiave 'jobs' (originale: '{jobs_key}')")
        if isinstance(data[jobs_key], list):
            jobs_list = data[jobs_key]
            pyt_Print(f"  Trovati {len(jobs_list)} job da eseguire")
            # Mostra i nomi dei job
            for idx, job in enumerate(jobs_list, 1):
                job_name = job.get("name", job.get("name ", f"job_{idx}"))
                if isinstance(job_name, str):
                    job_name = job_name.strip()
                pyt_Print(f"    Job {idx}: {job_name}")
        else:
            pyt_Print(f"  ATTENZIONE: La chiave 'jobs' non contiene una lista")
            jobs_list = [data]
    else:
        pyt_Print(f"  Nessuna chiave 'jobs' trovata, trattato come singolo job")
        jobs_list = [data]
    
    # Statistiche globali
    global_stats = {
        "jobs_ok": 0, "jobs_ko": 0,
        "total_copied": 0, "total_updated": 0,
        "total_removed": 0, "total_errors": 0,
        "total_skipped": 0
    }
    
    # Ciclo su tutti i job
    for idx, cfg_raw in enumerate(jobs_list, 1):
        # Pulizia automatica degli spazi finali da chiavi e valori stringa
        cfg = {}
        for k, v in cfg_raw.items():
            k_clean = k.strip() if isinstance(k, str) else k
            v_clean = v.strip() if isinstance(v, str) else v
            cfg[k_clean] = v_clean
        
        job_name = cfg.get("name", f"job_{idx}")
        pyt_Print(f"\n{'='*60}")
        pyt_Print(f"[{pyt_Timestamp()}] JOB {idx}/{len(jobs_list)}: {job_name}")
        pyt_Print(f"{'='*60}")
        
        try:
            _execute_single_sync(cfg, global_stats)
            global_stats["jobs_ok"] += 1
        except Exception as e:
            pyt_Print(f"ERRORE nel job '{job_name}': {str(e)}")
            global_stats["jobs_ko"] += 1
    
    # Riepilogo finale
    pyt_Print(f"\n{'='*60}")
    pyt_Print(f"RIEPILOGO GENERALE")
    pyt_Print(f"{'='*60}")
    pyt_Print(f"Job completati con successo : {global_stats['jobs_ok']}")
    pyt_Print(f"Job falliti                 : {global_stats['jobs_ko']}")
    pyt_Print(f"Totale file copiati         : {global_stats['total_copied']}")
    pyt_Print(f"Totale file aggiornati      : {global_stats['total_updated']}")
    pyt_Print(f"Totale file rimossi         : {global_stats['total_removed']}")
    pyt_Print(f"Totale file saltati         : {global_stats['total_skipped']}")
    pyt_Print(f"Totale errori file          : {global_stats['total_errors']}")

def _execute_single_sync(cfg, global_stats):
    """Esegue un singolo job di sincronizzazione."""
    # Validazione
    req_keys = ["type", "source", "dest", "log"]
    if cfg.get("type") in ["ftp", "ssh"]:
        req_keys.extend(["user", "pwd", "host"])
    if cfg.get("type") in ["file"]:
        req_keys.append("mode")
    
    for k in req_keys:
        if k not in cfg:
            raise ValueError(f"Chiave obbligatoria mancante nel JSON: {k}")
    
    if cfg["type"] not in ["file", "filesync", "ftp", "ssh"]:
        raise ValueError("Valore 'type' non valido. Usare: file, filesync, ftp, ssh.")
    
    if cfg["type"] in ["file"]:
        if cfg.get("mode") not in ["mirror", "new"]:
            raise ValueError("Valore 'mode' non valido. Usare: mirror, new.")
    
    # filesync è implicitamente mirror (cancella sempre i file non presenti in source)
    mode = "mirror" if cfg["type"] == "filesync" else cfg.get("mode", "mirror")
    
    # Normalizzazione percorsi (gestisce // -> \\ per UNC su Windows)
    source = _normalize_path(cfg["source"])
    dest = _normalize_path(cfg["dest"])
    log_file = cfg["log"]
    
    # Se il log non ha un percorso assoluto, lo metto nella cartella dello script
    if not os.path.isabs(log_file):
        log_file = os.path.join(SCRIPT_DIR, log_file)
    
    def sync_log(msg):
        ts = pyt_Timestamp()
        full_msg = f"[{ts}] {msg}"
        pyt_Print(full_msg)
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(full_msg + "\n")
        except Exception as e:
            pyt_Print(f"  Impossibile scrivere sul log {log_file}: {e}")
    
    def _tolerant_copy(src_file, dest_file):
        """Copia src su dest. Se la destinazione e' read-only (tipico dei file
        con attributi strani, es. i ._* su Windows), la rende scrivibile e
        riprova. Ritorna None se ok, altrimenti l'eccezione."""
        try:
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            shutil.copy2(src_file, dest_file)
            return None
        except PermissionError as e:
            try:
                if os.path.exists(dest_file):
                    os.chmod(dest_file, stat.S_IWRITE)
                else:
                    parent = os.path.dirname(dest_file)
                    if parent:
                        os.chmod(parent, stat.S_IWRITE)
                shutil.copyfile(src_file, dest_file)
                try:
                    shutil.copystat(src_file, dest_file)
                except OSError:
                    pass
                return None
            except Exception as e2:
                return e2
        except Exception as e:
            return e

    def _tolerant_remove_file(dest_file):
        """Rimuove un file, rendendolo scrivibile in caso di PermissionError."""
        try:
            os.remove(dest_file)
            return None
        except PermissionError:
            try:
                os.chmod(dest_file, stat.S_IWRITE)
                os.remove(dest_file)
                return None
            except Exception as e2:
                return e2
        except Exception as e:
            return e

    def _rmtree_onerror(func, path, _exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    def _tolerant_rmtree(dest_dir):
        """Rimuove una cartella (anche con file read-only dentro).
        Ritorna None se ok, altrimenti l'eccezione."""
        try:
            shutil.rmtree(dest_dir, onerror=_rmtree_onerror)
            if os.path.exists(dest_dir):
                return OSError(f"impossibile rimuovere {dest_dir}")
            return None
        except Exception as e:
            return e

    stype = cfg["type"]
    conn = None
    sftp = None
    base_dir = None
    
    try:
        sync_log("Fase 2: Verifica esistenza della cartella source")
        if not os.path.exists(source):
            raise FileNotFoundError(f"Cartella sorgente {source} non trovata.")
        
        sync_log("Fase 3: Verifica raggiungibilità di dest")
        if stype in ["file", "filesync"]:
            if not os.path.exists(dest):
                os.makedirs(dest)
        elif stype == "ftp":
            try:
                conn = ftplib.FTP(cfg["host"], cfg["user"], cfg["pwd"])
                conn.cwd(dest)
                base_dir = conn.pwd()
            except Exception as e:
                raise ConnectionError(f"Connessione FTP fallita: {e}")
        elif stype == "ssh":
            if paramiko is None:
                raise ImportError("Libreria paramiko non installata.")
            try:
                conn = paramiko.SSHClient()
                conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                conn.connect(cfg["host"], username=cfg["user"], password=cfg["pwd"])
                sftp = conn.open_sftp()
                sftp.stat(dest)
                base_dir = sftp.normalize(dest)
            except Exception as e:
                raise ConnectionError(f"Connessione SSH/SFTP fallita: {e}")
        
        stats = {"copied": 0, "updated": 0, "removed": 0, "errors": 0, "skipped": 0}

        def _walk_error(err):
            stats["errors"] += 1
            sync_log(f"ERROR scansione: {err}")

        sync_log("Fase 4: Sincronizzazione file")
        verified_dirs = set()

        for root, dirs, files in os.walk(source, onerror=_walk_error):
            rel_root = os.path.relpath(root, source)
            if rel_root == ".": rel_root = ""
            
            if rel_root:
                if stype == "ftp":
                    ftp_dir = rel_root.replace("\\", "/")
                    if ftp_dir not in verified_dirs:
                        parts = ftp_dir.split("/")
                        curr_path = base_dir
                        for p in parts:
                            curr_path += "/" + p
                            try:
                                conn.cwd(curr_path)
                            except ftplib.error_perm:
                                try: conn.mkd(curr_path)
                                except: pass
                        conn.cwd(base_dir)
                        verified_dirs.add(ftp_dir)
                elif stype == "ssh":
                    ssh_dir = rel_root.replace("\\", "/")
                    if ssh_dir not in verified_dirs:
                        parts = ssh_dir.split("/")
                        curr_path = base_dir
                        for p in parts:
                            curr_path += "/" + p
                            try: sftp.stat(curr_path)
                            except FileNotFoundError:
                                try: sftp.mkdir(curr_path)
                                except: pass
                        verified_dirs.add(ssh_dir)
            
            for file in files:
                src_file = os.path.join(root, file)
                rel_file = os.path.join(rel_root, file) if rel_root else file

                try:
                    # os.stat dentro il try: nomi non validi su Windows
                    # (es. con "|", WinError 123) o permessi negati diventano
                    # ERROR sul singolo file invece di far fallire l'intero job
                    src_stat = os.stat(src_file)
                    src_size = src_stat.st_size
                    src_mtime = src_stat.st_mtime

                    needs_copy = False
                    action = "copied"
                    
                    if stype in ["file", "filesync"]:
                        dest_file = os.path.join(dest, rel_file)
                        if not os.path.exists(dest_file):
                            needs_copy = True
                        else:
                            dest_stat = os.stat(dest_file)
                            if dest_stat.st_size != src_size or dest_stat.st_mtime < src_mtime:
                                needs_copy = True
                                action = "updated"
                        
                        if needs_copy:
                            err = _tolerant_copy(src_file, dest_file)
                            if err is not None:
                                raise err
                    
                    elif stype == "ftp":
                        ftp_file = rel_file.replace("\\", "/")
                        full_ftp_path = base_dir + "/" + ftp_file
                        try:
                            dest_size = conn.size(full_ftp_path)
                            if dest_size != src_size:
                                needs_copy = True
                                action = "updated"
                        except ftplib.error_perm:
                            needs_copy = True
                        
                        if needs_copy:
                            with open(src_file, 'rb') as f:
                                conn.storbinary(f'STOR {full_ftp_path}', f)
                    
                    elif stype == "ssh":
                        ssh_file = rel_file.replace("\\", "/")
                        full_ssh_path = base_dir + "/" + ssh_file
                        try:
                            dest_stat = sftp.stat(full_ssh_path)
                            if dest_stat.st_size != src_size or dest_stat.st_mtime < src_mtime:
                                needs_copy = True
                                action = "updated"
                        except FileNotFoundError:
                            needs_copy = True
                        
                        if needs_copy:
                            sftp.put(src_file, full_ssh_path)
                    
                    if needs_copy:
                        stats[action] += 1
                        sync_log(f"{action.upper()}: {rel_file}")
                
                except Exception as e:
                    stats["errors"] += 1
                    sync_log(f"ERROR su {rel_file}: {str(e)}")
        
        # filesync cancella SEMPRE i file non presenti in source (implicitamente mirror)
        if mode == "mirror" or stype == "filesync":
            sync_log("Fase 5: Rimozione da dest dei file non presenti in source")
            
            if stype in ["file", "filesync"]:
                for root, dirs, files in os.walk(dest, topdown=False, onerror=_walk_error):
                    rel_root = os.path.relpath(root, dest)
                    if rel_root == ".": rel_root = ""
                    src_root = os.path.join(source, rel_root) if rel_root else source

                    for file in files:
                        dest_file = os.path.join(root, file)
                        src_file = os.path.join(src_root, file)
                        if not os.path.exists(src_file):
                            err = _tolerant_remove_file(dest_file)
                            if err is None:
                                stats["removed"] += 1
                                sync_log(f"REMOVED: {os.path.relpath(dest_file, dest)}")
                            else:
                                stats["errors"] += 1
                                sync_log(f"ERROR removing {os.path.relpath(dest_file, dest)}: {str(err)}")

                    for d in dirs:
                        dest_dir = os.path.join(root, d)
                        src_dir = os.path.join(src_root, d)
                        if not os.path.exists(src_dir):
                            err = _tolerant_rmtree(dest_dir)
                            if err is None:
                                stats["removed"] += 1
                                sync_log(f"REMOVED DIR: {os.path.relpath(dest_dir, dest)}")
                            else:
                                stats["errors"] += 1
                                sync_log(f"ERROR removing dir {os.path.relpath(dest_dir, dest)}: {str(err)}")
            
            elif stype == "ftp":
                def ftp_walk_remover(ftp, remote_dir, local_dir):
                    try:
                        ftp.cwd(remote_dir)
                        items = ftp.nlst()
                    except ftplib.error_perm:
                        return
                    
                    for item_name in items:
                        if item_name in ['.', '..']: continue
                        remote_item_path = remote_dir + "/" + item_name
                        local_item_path = os.path.join(local_dir, item_name) if local_dir else item_name
                        
                        try:
                            ftp.cwd(remote_item_path)
                            ftp.cwd(remote_dir)
                            ftp_walk_remover(ftp, remote_item_path, local_item_path)
                            
                            if not os.path.exists(os.path.join(source, local_item_path)):
                                try:
                                    ftp.rmd(remote_item_path)
                                    sync_log(f"REMOVED DIR: {local_item_path}")
                                except: pass
                        except ftplib.error_perm:
                            if not os.path.exists(os.path.join(source, local_item_path)):
                                try:
                                    ftp.delete(remote_item_path)
                                    stats["removed"] += 1
                                    sync_log(f"REMOVED: {local_item_path}")
                                except Exception as e:
                                    stats["errors"] += 1
                                    sync_log(f"ERROR removing {local_item_path}: {str(e)}")
                
                ftp_walk_remover(conn, base_dir, "")
            
            elif stype == "ssh":
                def ssh_walk_remover(sftp, remote_dir, local_dir):
                    try:
                        items = sftp.listdir_attr(remote_dir)
                    except FileNotFoundError:
                        return
                    
                    for item in items:
                        item_name = item.filename
                        remote_item_path = remote_dir + "/" + item_name
                        local_item_path = os.path.join(local_dir, item_name) if local_dir else item_name
                        
                        if stat.S_ISDIR(item.st_mode):
                            ssh_walk_remover(sftp, remote_item_path, local_item_path)
                            if not os.path.exists(os.path.join(source, local_item_path)):
                                try:
                                    sftp.rmdir(remote_item_path)
                                    sync_log(f"REMOVED DIR: {local_item_path}")
                                except: pass
                        else:
                            if not os.path.exists(os.path.join(source, local_item_path)):
                                try:
                                    sftp.remove(remote_item_path)
                                    stats["removed"] += 1
                                    sync_log(f"REMOVED: {local_item_path}")
                                except Exception as e:
                                    stats["errors"] += 1
                                    sync_log(f"ERROR removing {local_item_path}: {str(e)}")
                
                ssh_walk_remover(sftp, base_dir, "")
        
        sync_log("Fase 6: Scrittura del riepilogo")
        summary = f"Riepilogo - Copiati: {stats['copied']}, Aggiornati: {stats['updated']}, Rimossi: {stats['removed']}, Saltati: {stats['skipped']}, Errori: {stats['errors']}"
        sync_log(summary)

        # Aggiorno le statistiche globali
        global_stats["total_copied"] += stats["copied"]
        global_stats["total_updated"] += stats["updated"]
        global_stats["total_removed"] += stats["removed"]
        global_stats["total_errors"] += stats["errors"]
        global_stats["total_skipped"] += stats["skipped"]
    
    finally:
        # Chiusura sicura delle connessioni
        try:
            if stype == "ftp" and conn:
                conn.quit()
        except: pass
        
        try:
            if stype == "ssh" and sftp:
                sftp.close()
            if stype == "ssh" and conn:
                conn.close()
        except: pass

def app_sync_script(params):
    """Genera uno script batch per la sincronizzazione mirror con robocopy."""
    if len(params) > 3:
        raise ValueError("Sintassi errata. Uso: sync_script [path_source] [path_dest] [file_output]")
    
    if os.name != 'nt':
        raise OSError("La direttiva sync_script è utilizzabile solo su Windows (richiede robocopy).")
    
    # Rimozione virgolette e applicazione default
    path_source = params[0].strip('"\'') if len(params) > 0 else r"\\ntgdsnas"
    path_dest = params[1].strip('"\'') if len(params) > 1 else "n:"
    file_output = params[2].strip('"\'') if len(params) > 2 else "admin_sync_script.cmd"
    
    # Rimuove backslash finali
    path_source = path_source.rstrip('\\')
    path_dest = path_dest.rstrip('\\')
    
    log_file = "sync_log.txt"
    
    # Lettura lista cartelle da variabile d'ambiente o default
    sync_folders_env = os.environ.get("SYNC_FOLDERS")
    if sync_folders_env and sync_folders_env.strip():
        folders = sync_folders_env.strip().split()
    else:
        default_folders = "alias areefile Backup clouddrive falcricrv home homes music NetBackup ntrobot photo temp video web web_packages"
        folders = default_folders.split()
    
    # Se il file output non è assoluto, lo metto nella cartella dello script
    if not os.path.isabs(file_output):
        file_output = os.path.join(SCRIPT_DIR, file_output)
    
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura parametri e variabile d'ambiente SYNC_FOLDERS")
    pyt_Print(f"  Sorgente    : {path_source}")
    pyt_Print(f"  Destinazione: {path_dest}")
    pyt_Print(f"  File output : {file_output}")
    pyt_Print(f"  Cartelle    : {len(folders)} ({', '.join(folders[:3])}{'...' if len(folders)>3 else ''})")
    
    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Costruzione dello script batch")
    lines = []
    lines.append("@echo off")
    lines.append("setlocal enabledelayedexpansion")
    lines.append("")
    lines.append(f'set "PATH_SOURCE={path_source}"')
    lines.append(f'set "PATH_DEST={path_dest}"')
    lines.append(f'set "LOG_FILE={log_file}"')
    lines.append("")
    lines.append("echo ===================================================================")
    lines.append("echo                    SINCRONIZZAZIONE MIRROR CON ROBOCOPY")
    lines.append("echo ===================================================================")
    lines.append("echo.")
    lines.append("echo [INFO] Sorgente   : %PATH_SOURCE%")
    lines.append("echo [INFO] Destinazione: %PATH_DEST%")
    lines.append("echo [INFO] File di log: %LOG_FILE%")
    lines.append("echo [INFO] Modalita'  : Mirror (sorgente -> destinazione)")
    lines.append("echo [INFO] Opzioni    : /MIR (speculare), /R:3 (3 tentativi), /W:10 (attesa 10s)")
    lines.append("echo [INFO] Verbosita' : Dettaglio file copiati/cancellati/saltati")
    lines.append("echo ===================================================================")
    lines.append("echo.")
    lines.append(f'echo %DATE% %TIME% - === INIZIO SINCRONIZZAZIONE === >> "%LOG_FILE%"')
    lines.append("echo.")
    
    for idx, folder in enumerate(folders, 1):
        total = len(folders)
        lines.append(f'echo.')
        lines.append(f'echo ===================================================================')
        lines.append(f'echo [PROGRESSO] Cartella {idx}/{total} : {folder}')
        lines.append(f'echo ===================================================================')
        lines.append(f'echo [INFO] Sorgente: %PATH_SOURCE%\\{folder}')
        lines.append(f'echo [INFO] Destinaz: %PATH_DEST%\\{folder}')
        lines.append(f'echo [INFO] Avvio robocopy con opzioni: /MIR /R:3 /W:10 /V /TS /FP /ETA')
        lines.append("echo.")
        lines.append(f'echo [LOG] --- INIZIO {folder} --- >> "%LOG_FILE%"')
        
        # Comando robocopy
        lines.append(f'robocopy "%PATH_SOURCE%\\{folder}" "%PATH_DEST%\\{folder}" /MIR /R:3 /W:10 /V /TS /FP /ETA /NP /NDL /NJH /NJS /TEE /LOG+:"%LOG_FILE%"')
        
        # Controllo codice di uscita
        lines.append("set ROBOCODE=%errorlevel%")
        lines.append("echo.")
        lines.append("echo [RIEPILOGO] Risultato per %folder%:")
        lines.append("if %ROBOCODE% EQU 0 (")
        lines.append('    echo   [OK] Nessun cambiamento (sorgente e destinazione identici)')
        lines.append(") else if %ROBOCODE% EQU 1 (")
        lines.append('    echo   [OK] Copia completata con successo (file copiati)')
        lines.append(") else if %ROBOCODE% EQU 2 (")
        lines.append('    echo   [OK] File extra cancellati nella destinazione')
        lines.append(") else if %ROBOCODE% EQU 3 (")
        lines.append('    echo   [OK] Copia e cancellazioni effettuate (2+1)')
        lines.append(") else if %ROBOCODE% EQU 4 (")
        lines.append('    echo   [ATTENZIONE] Alcuni file non corrispondono (mismatch)')
        lines.append(") else if %ROBOCODE% EQU 5 (")
        lines.append('    echo   [ATTENZIONE] Copia + mismatch (1+4)')
        lines.append(") else if %ROBOCODE% EQU 6 (")
        lines.append('    echo   [ATTENZIONE] Cancellazioni + mismatch (2+4)')
        lines.append(") else if %ROBOCODE% EQU 7 (")
        lines.append('    echo   [ATTENZIONE] Copia + cancellazioni + mismatch (1+2+4)')
        lines.append(") else if %ROBOCODE% GEQ 8 (")
        lines.append('    echo   [ERRORE] Operazione fallita (codice %ROBOCODE%)')
        lines.append('    echo   [ERRORE] Verificare il log per dettagli')
        lines.append(") else (")
        lines.append('    echo   [INFO] Codice di uscita: %ROBOCODE%')
        lines.append(")")
        
        lines.append("echo.")
        lines.append(f'echo [LOG] --- FINE {folder} - codice %ROBOCODE% --- >> "%LOG_FILE%"')
        lines.append("echo.")
        lines.append("echo ===================================================================")
        lines.append("echo.")
    
    lines.append("echo ===================================================================")
    lines.append("echo [COMPLETATO] Tutte le cartelle sono state elaborate")
    lines.append("echo [INFO] Log completo disponibile in: %LOG_FILE%")
    lines.append("echo ===================================================================")
    lines.append(f'echo %DATE% %TIME% - === FINE SINCRONIZZAZIONE === >> "%LOG_FILE%"')
    lines.append("echo.")
    lines.append("pause")
    
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Scrittura atomica del file di output")
    temp_dir = os.path.dirname(file_output) or "."
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, dir=temp_dir, suffix='.tmp', encoding='utf-8')
    
    try:
        temp_file.write("\n".join(lines))
        temp_file.close()
        
        if os.path.exists(file_output):
            try:
                os.remove(file_output)
            except PermissionError:
                backup = file_output + ".old"
                try:
                    shutil.move(file_output, backup)
                    pyt_Print(f"  [AVVISO] File esistente rinominato in {backup}")
                except Exception as e:
                    pyt_Print(f"  [ERRORE] Impossibile rinominare {file_output}: {e}")
                    try:
                        shutil.copy2(temp_file.name, file_output)
                        os.remove(temp_file.name)
                        pyt_Print(f"  [OK] Script generato (sovrascritto) in: {file_output}")
                        pyt_Print(f"Script batch generato. Eseguirlo per avviare la sincronizzazione.")
                        return
                    except Exception as e2:
                        raise RuntimeError(f"Copia fallita: {e2}")
        
        shutil.move(temp_file.name, file_output)
        pyt_Print(f"  [OK] Script generato con successo in: {file_output}")
        pyt_Print(f"Script batch generato. Eseguirlo per avviare la sincronizzazione.")
        
    except Exception as e:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)
        raise RuntimeError(f"Generazione fallita: {e}")

def app_robocopy(params):
    """Copia file specificati da sorgente a destinazione secondo JSON.
    Funziona su Windows e Linux (usa shutil, non robocopy.exe).
    
    JSON structure:
    {
        "settings": {
            "log": "percorso/file.log",      # file di log da creare nuovo ogni volta
            "err.exit": true|false           # esci in caso di errore
        },
        "actions": {
            "action_name": {
                "path_source": "percorso/sorgente",
                "path_dest": "percorso/destinazione",
                "mode": "overwrite|old",     # default: overwrite
                "files": ["file1.txt", "file2.txt"]
            }
        }
    }
    """
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: robocopy <config.json>")
    
    config_file = params[0].strip('"\'')
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"File di configurazione {config_file} non trovato.")
    
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura e validazione del file di configurazione JSON")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato: {e}")
    
    # Pulizia spazi da chiavi e valori stringa
    def clean_dict(d):
        if not isinstance(d, dict):
            return d
        result = {}
        for k, v in d.items():
            k_clean = k.strip() if isinstance(k, str) else k
            if isinstance(v, dict):
                v_clean = clean_dict(v)
            elif isinstance(v, list):
                v_clean = [item.strip() if isinstance(item, str) else item for item in v]
            elif isinstance(v, str):
                v_clean = v.strip()
            else:
                v_clean = v
            result[k_clean] = v_clean
        return result
    
    cfg = clean_dict(cfg)
    
    # Validazione struttura base
    if "settings" not in cfg:
        raise ValueError("Sezione 'settings' obbligatoria nel JSON")
    if "actions" not in cfg:
        raise ValueError("Sezione 'actions' obbligatoria nel JSON")
    
    settings = cfg["settings"]
    actions = cfg["actions"]
    
    # Validazione settings
    log_file = settings.get("log")
    if not log_file:
        raise ValueError("Setting 'log' obbligatorio in 'settings'")
    err_exit = settings.get("err.exit", False)
    if isinstance(err_exit, str):
        err_exit = err_exit.lower() == "true"
    
    # Se log non è assoluto, mettilo in SCRIPT_DIR
    if not os.path.isabs(log_file):
        log_file = os.path.join(SCRIPT_DIR, log_file)
    
    # Crea/Rigenera file di log
    try:
        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] AVVIO ROBOCOPY SYNC\n")
    except Exception as e:
        raise RuntimeError(f"Impossibile creare file di log {log_file}: {e}")
    
    def robocopy_log(msg):
        ts = pyt_Timestamp()
        full_msg = f"[{ts}] {msg}"
        pyt_Print(full_msg)
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(full_msg + "\n")
        except Exception as e:
            pyt_Print(f"  Impossibile scrivere sul log {log_file}: {e}")
    
    robocopy_log(f"Configurazione letta: {len(actions)} action(s) trovate")
    
    # Normalizzazione percorsi per compatibilità Windows/Linux
    def normalize(p):
        if not isinstance(p, str):
            return p
        if os.name == 'nt':
            return p.replace("/", "\\")
        else:
            return p.replace("\\", "/")
    
    total_stats = {"copied": 0, "updated": 0, "skipped": 0, "errors": 0}
    
    # Processa ogni action
    for action_name, action_cfg in actions.items():
        robocopy_log(f"\n{'='*60}")
        robocopy_log(f"AZIONE: {action_name}")
        robocopy_log(f"{'='*60}")
        
        # Validazione action
        path_source = action_cfg.get("path_source")
        path_dest = action_cfg.get("path_dest")
        mode = action_cfg.get("mode", "overwrite")
        files = action_cfg.get("files", [])
        
        if not path_source:
            robocopy_log(f"ERRORE: path_source mancante per azione '{action_name}'")
            total_stats["errors"] += 1
            if err_exit:
                raise ValueError(f"path_source mancante per azione '{action_name}'")
            continue
        
        if not path_dest:
            robocopy_log(f"ERRORE: path_dest mancante per azione '{action_name}'")
            total_stats["errors"] += 1
            if err_exit:
                raise ValueError(f"path_dest mancante per azione '{action_name}'")
            continue
        
        if not isinstance(files, list) or len(files) == 0:
            robocopy_log(f"ERRORE: array 'files' vuoto o mancante per azione '{action_name}'")
            total_stats["errors"] += 1
            if err_exit:
                raise ValueError(f"Array 'files' vuoto o mancante per azione '{action_name}'")
            continue
        
        if mode not in ["overwrite", "old"]:
            robocopy_log(f"ERRORE: mode '{mode}' non valido per azione '{action_name}' (usa 'overwrite' o 'old')")
            total_stats["errors"] += 1
            if err_exit:
                raise ValueError(f"Mode '{mode}' non valido per azione '{action_name}'")
            continue
        
        # Normalizza percorsi
        path_source = normalize(path_source)
        path_dest = normalize(path_dest)
        
        robocopy_log(f"  path_source: {path_source}")
        robocopy_log(f"  path_dest:   {path_dest}")
        robocopy_log(f"  mode:        {mode}")
        robocopy_log(f"  files:       {len(files)} file(s)")
        
        # Verifica esistenza sorgente
        if not os.path.exists(path_source):
            robocopy_log(f"ERRORE: Sorgente non esistente: {path_source}")
            total_stats["errors"] += 1
            if err_exit:
                raise FileNotFoundError(f"Sorgente non esistente: {path_source}")
            continue
        
        # Crea destinazione se non esiste
        try:
            os.makedirs(path_dest, exist_ok=True)
        except Exception as e:
            robocopy_log(f"ERRORE: Impossibile creare destinazione {path_dest}: {e}")
            total_stats["errors"] += 1
            if err_exit:
                raise RuntimeError(f"Impossibile creare destinazione {path_dest}: {e}")
            continue
        
        # Processa ogni file
        for file_name in files:
            robocopy_log(f"  Elaborazione: {file_name}")
            
            # Controlla se il pattern contiene wildcard
            has_wildcard = any(c in file_name for c in "*?[")
            
            if has_wildcard:
                # Usa glob per trovare tutti i file che corrispondono al pattern
                pattern = os.path.join(path_source, file_name)
                matched_files = glob.glob(pattern)
                
                if not matched_files:
                    robocopy_log(f"    SALTATO (nessun file corrispondente al pattern): {file_name}")
                    total_stats["skipped"] += 1
                    continue
                
                robocopy_log(f"    Trovati {len(matched_files)} file(s) per pattern: {file_name}")
                
                for src_file in matched_files:
                    # Calcola il percorso relativo rispetto a path_source
                    try:
                        rel_path = os.path.relpath(src_file, path_source)
                    except ValueError:
                        # Su Windows può fallire se path_source è su drive diverso
                        rel_path = os.path.basename(src_file)
                    
                    dest_file = os.path.join(path_dest, rel_path)
                    
                    robocopy_log(f"    Elaborazione: {rel_path}")
                    
                    try:
                        # Se mode == "old" e il file di destinazione esiste, rinominalo in .old
                        if mode == "old" and os.path.exists(dest_file):
                            old_file = dest_file + ".old"
                            # Rimuovi eventuale .old precedente
                            if os.path.exists(old_file):
                                os.remove(old_file)
                                robocopy_log(f"      Rimosso vecchio .old: {old_file}")
                            os.rename(dest_file, old_file)
                            robocopy_log(f"      RINOMINATO in .old: {dest_file} -> {old_file}")
                        
                        # Crea directory di destinazione se non esiste
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        
                        # Copia il file
                        shutil.copy2(src_file, dest_file)
                        
                        if os.path.exists(dest_file):
                            src_stat = os.stat(src_file)
                            dest_stat = os.stat(dest_file)
                            if src_stat.st_size == dest_stat.st_size and abs(src_stat.st_mtime - dest_stat.st_mtime) < 2:
                                robocopy_log(f"      COPIATO: {rel_path}")
                                total_stats["copied"] += 1
                            else:
                                robocopy_log(f"      AGGIORNATO: {rel_path}")
                                total_stats["updated"] += 1
                        else:
                            robocopy_log(f"      ERRORE: File non copiato: {rel_path}")
                            total_stats["errors"] += 1
                            
                    except Exception as e:
                        robocopy_log(f"      ERRORE su {rel_path}: {e}")
                        total_stats["errors"] += 1
                        if err_exit:
                            raise RuntimeError(f"Errore durante copia di {rel_path}: {e}")
            else:
                # Comportamento originale per file singoli (senza wildcard)
                src_file = os.path.join(path_source, file_name)
                dest_file = os.path.join(path_dest, file_name)
                
                if not os.path.exists(src_file):
                    robocopy_log(f"    SALTATO (non trovato in sorgente): {src_file}")
                    total_stats["skipped"] += 1
                    continue
                
                try:
                    # Se mode == "old" e il file di destinazione esiste, rinominalo in .old
                    if mode == "old" and os.path.exists(dest_file):
                        old_file = dest_file + ".old"
                        # Rimuovi eventuale .old precedente
                        if os.path.exists(old_file):
                            os.remove(old_file)
                            robocopy_log(f"    Rimosso vecchio .old: {old_file}")
                        os.rename(dest_file, old_file)
                        robocopy_log(f"    RINOMINATO in .old: {dest_file} -> {old_file}")
                    
                    # Copia il file
                    shutil.copy2(src_file, dest_file)
                    
                    if os.path.exists(dest_file):
                        src_stat = os.stat(src_file)
                        dest_stat = os.stat(dest_file)
                        if src_stat.st_size == dest_stat.st_size and abs(src_stat.st_mtime - dest_stat.st_mtime) < 2:
                            robocopy_log(f"    COPIATO: {file_name}")
                            total_stats["copied"] += 1
                        else:
                            robocopy_log(f"    AGGIORNATO: {file_name}")
                            total_stats["updated"] += 1
                    else:
                        robocopy_log(f"    ERRORE: File non copiato: {file_name}")
                        total_stats["errors"] += 1
                        
                except Exception as e:
                    robocopy_log(f"    ERRORE su {file_name}: {e}")
                    total_stats["errors"] += 1
                    if err_exit:
                        raise RuntimeError(f"Errore durante copia di {file_name}: {e}")
    
    # Riepilogo finale
    robocopy_log(f"\n{'='*60}")
    robocopy_log("RIEPILOGO FINALE")
    robocopy_log(f"{'='*60}")
    robocopy_log(f"File copiati   : {total_stats['copied']}")
    robocopy_log(f"File aggiornati: {total_stats['updated']}")
    robocopy_log(f"File saltati   : {total_stats['skipped']}")
    robocopy_log(f"Errori         : {total_stats['errors']}")
    
    if total_stats["errors"] > 0:
        robocopy_log("ATTENZIONE: Sono presenti errori. Controlla il log per dettagli.")
    else:
        robocopy_log("Operazione completata senza errori.")


def _resolve_env_value(value):
    """Se un valore inizia con $, lo risolve come variabile d'ambiente."""
    if not isinstance(value, str):
        return value
    if value.startswith("$"):
        var_name = value[1:]
        env_value = os.environ.get(var_name)
        if env_value is None or env_value == "":
            raise ValueError(f"Variabile d'ambiente {var_name} non impostata o vuota")
        return env_value
    return value

def _mask_token(token):
    """Maschera il token per sicurezza."""
    if not token:
        return "***"
    return "***"

def app_git_push(params):
    """Esegue un git push su GitHub autenticandosi tramite token personali."""
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: git.push <config.json>")
    
    config_file = params[0].strip('"\'')
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"File di configurazione {config_file} non trovato.")
    
    # Fase 1: Verifica parametri e prerequisiti
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Verifica parametri e prerequisiti")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato: {e}")
    
    # Estrai parametri
    repo_path = cfg.get("repo_path", "").strip()
    username = _resolve_env_value(cfg.get("username", ""))
    token = _resolve_env_value(cfg.get("token", ""))
    repo_name = cfg.get("repo_name", "").strip()
    branch = cfg.get("branch", "main").strip()
    log_file = cfg.get("log", "").strip()
    owner = cfg.get("owner", username).strip()
    git_path = cfg.get("git_path", "").strip()
    commit_message = cfg.get("commit_message", "").strip()
    commit_all = cfg.get("commit_all", True)
    
    # Validazione parametri obbligatori
    if not repo_path:
        raise ValueError("Parametro 'repo_path' obbligatorio")
    if not username:
        raise ValueError("Parametro 'username' obbligatorio")
    if not token:
        raise ValueError("Parametro 'token' obbligatorio")
    if not repo_name:
        raise ValueError("Parametro 'repo_name' obbligatorio")
    if not log_file:
        raise ValueError("Parametro 'log' obbligatorio")
    if not os.path.isabs(log_file):
        raise ValueError("Il parametro 'log' deve essere un percorso assoluto")
    
    # Verifica git_path su Windows (obbligatorio) vs Linux (opzionale)
    if os.name == 'nt':
        # Windows: git_path è obbligatorio
        if not git_path:
            raise ValueError("Parametro 'git_path' obbligatorio su Windows")
        if not os.path.exists(git_path):
            raise FileNotFoundError(f"Git eseguibile non trovato in: {git_path}")
        if not git_path.lower().endswith(".exe"):
            raise ValueError(f"Il parametro 'git_path' deve puntare a un file .exe su Windows")
        git_exe = git_path
    else:
        # Linux: git_path è opzionale, cerca nel PATH se non specificato
        if git_path:
            if not os.path.exists(git_path):
                raise FileNotFoundError(f"Git eseguibile non trovato in: {git_path}")
            git_exe = git_path
        else:
            git_exe = shutil.which("git")
            if not git_exe:
                raise FileNotFoundError("Git non installato o non trovato nel PATH")
    
    # Verifica esistenza repository
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repository non trovato: {repo_path}")
    
    # Verifica esistenza file di log (crea directory se necessario)
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Stampa informazioni
    pyt_Print(f"  Repository path: {repo_path}")
    pyt_Print(f"  Username: {username}")
    pyt_Print(f"  Repository: {owner}/{repo_name}")
    pyt_Print(f"  Branch: {branch}")
    pyt_Print(f"  Log file: {log_file}")
    pyt_Print(f"  Git executable: {git_exe}")
    if commit_message:
        pyt_Print(f"  Commit message: {commit_message}")
        pyt_Print(f"  Commit all: {commit_all}")
    else:
        pyt_Print(f"  Commit: non eseguito (commit_message non specificato)")
    pyt_Print(f"  Verifica esistenza cartella repository... OK")
    pyt_Print(f"  Verifica presenza file di log... OK")
    
    # Fase 2: Esecuzione operazioni preliminari (commit se richiesto)
    commit_executed = False
    commit_hash = None
    if commit_message:
        pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Esecuzione operazioni preliminari (commit se richiesto)")
        try:
            os.chdir(repo_path)
            
            # git add . se commit_all è True
            if commit_all:
                pyt_Print(f"  Esecuzione: git add .")
                cmd = [git_exe, "add", "."]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode != 0:
                    pyt_Print(f"  [ATTENZIONE] git add ha restituito: {res.stderr.strip()}")
            
            # git commit
            pyt_Print(f'  Esecuzione: git commit -m "{commit_message}"')
            cmd = [git_exe, "commit", "-m", commit_message]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if res.returncode == 0:
                commit_executed = True
                # Estrai l'hash del commit (prima riga dell'output)
                output_lines = res.stdout.strip().split('\n')
                if output_lines:
                    first_line = output_lines[0]
                    if '[' in first_line and ']' in first_line:
                        hash_start = first_line.index('[') + 1
                        hash_end = first_line.index(']')
                        commit_hash = first_line[hash_start:hash_end][:7]
                pyt_Print(f"  [OK] Commit creato: {commit_hash if commit_hash else 'N/A'}")
            else:
                # Commit fallito (es. nessun cambiamento)
                pyt_Print(f"  [ATTENZIONE] Commit non eseguito: {res.stderr.strip()}")
                pyt_Print(f"  [INFO] Procedo con il push dei commit esistenti")
                
        except subprocess.TimeoutExpired:
            pyt_Print(f"  [ERRORE] Timeout durante il commit")
            raise RuntimeError("Timeout durante git commit")
        except Exception as e:
            pyt_Print(f"  [ERRORE] Errore durante commit: {str(e)}")
            raise RuntimeError(f"Errore durante git commit: {str(e)}")
    else:
        pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Preparazione per git push")
    
    # Fase 3: Esecuzione git push
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Esecuzione git push")
    
    remote_url = f"https://{username}:{token}@github.com/{owner}/{repo_name}.git"
    masked_url = f"https://{username}:{_mask_token(token)}@github.com/{owner}/{repo_name}.git"
    
    pyt_Print(f"  Comando: git push {masked_url} {branch}")
    
    # Scrivi log
    try:
        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] AVVIO GIT PUSH\n")
            lf.write(f"Repository: {owner}/{repo_name}\n")
            lf.write(f"Branch: {branch}\n")
            lf.write(f"Remote: {masked_url}\n")
            lf.write(f"Git executable: {git_exe}\n")
            if commit_message:
                lf.write(f"Commit message: {commit_message}\n")
                lf.write(f"Commit all: {commit_all}\n")
                lf.write(f"Commit eseguito: {'SI' if commit_executed else 'NO'}\n")
                if commit_hash:
                    lf.write(f"Commit hash: {commit_hash}\n")
    except Exception as e:
        raise RuntimeError(f"Impossibile creare file di log {log_file}: {e}")
    
    # Esegui git push
    try:
        os.chdir(repo_path)
        cmd = [git_exe, "push", remote_url, branch]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if res.returncode != 0:
            error_msg = f"Git push fallito: {res.stderr.strip()}"
            pyt_Print(f"  [ERRORE] {error_msg}")
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"[{pyt_Timestamp()}] ERRORE: {error_msg}\n")
            raise RuntimeError(error_msg)
        
        pyt_Print(f"  [OK] Push completato con successo")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] SUCCESSO: Push completato\n")
            
    except subprocess.TimeoutExpired:
        error_msg = "Timeout durante git push (120 secondi)"
        pyt_Print(f"  [ERRORE] {error_msg}")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] ERRORE: {error_msg}\n")
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Errore durante git push: {str(e)}"
        pyt_Print(f"  [ERRORE] {error_msg}")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] ERRORE: {error_msg}\n")
        raise RuntimeError(error_msg)
    
    # Fase 4: Riepilogo finale
    pyt_Print(f"[{pyt_Timestamp()}] Fase 4: Riepilogo finale")
    summary = f"""  Operazione: PUSH
  Repository: {owner}/{repo_name}
  Branch: {branch}
  Commit eseguito: {'SI' if commit_executed else 'NO'}{f' ({commit_hash})' if commit_hash else ''}
  Esito: SUCCESSO
  Log file: {log_file}"""
    pyt_Print(summary)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[{pyt_Timestamp()}] {summary}\n")

def app_git_pull(params):
    """Esegue un git pull da GitHub autenticandosi tramite token personali."""
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: git.pull <config.json>")
    
    config_file = params[0].strip('"\'')
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"File di configurazione {config_file} non trovato.")
    
    # Fase 1: Verifica parametri e prerequisiti
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Verifica parametri e prerequisiti")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato: {e}")
    
    # Estrai parametri
    repo_path = cfg.get("repo_path", "").strip()
    username = _resolve_env_value(cfg.get("username", ""))
    token = _resolve_env_value(cfg.get("token", ""))
    repo_name = cfg.get("repo_name", "").strip()
    branch = cfg.get("branch", "main").strip()
    log_file = cfg.get("log", "").strip()
    owner = cfg.get("owner", username).strip()
    git_path = cfg.get("git_path", "").strip()
    
    # Validazione parametri obbligatori
    if not repo_path:
        raise ValueError("Parametro 'repo_path' obbligatorio")
    if not username:
        raise ValueError("Parametro 'username' obbligatorio")
    if not token:
        raise ValueError("Parametro 'token' obbligatorio")
    if not repo_name:
        raise ValueError("Parametro 'repo_name' obbligatorio")
    if not log_file:
        raise ValueError("Parametro 'log' obbligatorio")
    if not os.path.isabs(log_file):
        raise ValueError("Il parametro 'log' deve essere un percorso assoluto")
    
    # Verifica git_path su Windows (obbligatorio) vs Linux (opzionale)
    if os.name == 'nt':
        # Windows: git_path è obbligatorio
        if not git_path:
            raise ValueError("Parametro 'git_path' obbligatorio su Windows")
        if not os.path.exists(git_path):
            raise FileNotFoundError(f"Git eseguibile non trovato in: {git_path}")
        if not git_path.lower().endswith(".exe"):
            raise ValueError(f"Il parametro 'git_path' deve puntare a un file .exe su Windows")
        git_exe = git_path
    else:
        # Linux: git_path è opzionale, cerca nel PATH se non specificato
        if git_path:
            if not os.path.exists(git_path):
                raise FileNotFoundError(f"Git eseguibile non trovato in: {git_path}")
            git_exe = git_path
        else:
            git_exe = shutil.which("git")
            if not git_exe:
                raise FileNotFoundError("Git non installato o non trovato nel PATH")
    
    # Verifica esistenza repository
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repository non trovato: {repo_path}")
    
    # Verifica esistenza file di log (crea directory se necessario)
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Stampa informazioni
    pyt_Print(f"  Repository path: {repo_path}")
    pyt_Print(f"  Username: {username}")
    pyt_Print(f"  Repository: {owner}/{repo_name}")
    pyt_Print(f"  Branch: {branch}")
    pyt_Print(f"  Log file: {log_file}")
    pyt_Print(f"  Git executable: {git_exe}")
    pyt_Print(f"  Verifica esistenza cartella repository... OK")
    pyt_Print(f"  Verifica presenza file di log... OK")
    
    # Fase 2: Esecuzione git pull
    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Esecuzione git pull")
    
    remote_url = f"https://{username}:{token}@github.com/{owner}/{repo_name}.git"
    masked_url = f"https://{username}:{_mask_token(token)}@github.com/{owner}/{repo_name}.git"
    
    pyt_Print(f"  Comando: git pull {masked_url} {branch}")
    
    # Scrivi log
    try:
        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] AVVIO GIT PULL\n")
            lf.write(f"Repository: {owner}/{repo_name}\n")
            lf.write(f"Branch: {branch}\n")
            lf.write(f"Remote: {masked_url}\n")
            lf.write(f"Git executable: {git_exe}\n")
    except Exception as e:
        raise RuntimeError(f"Impossibile creare file di log {log_file}: {e}")
    
    # Esegui git pull
    try:
        os.chdir(repo_path)
        cmd = [git_exe, "pull", remote_url, branch]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if res.returncode != 0:
            error_msg = f"Git pull fallito: {res.stderr.strip()}"
            if "conflict" in error_msg.lower() or "merge conflict" in error_msg.lower():
                error_msg = "Conflitti durante il merge. Risolvere i conflitti manualmente."
            pyt_Print(f"  [ERRORE] {error_msg}")
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"[{pyt_Timestamp()}] ERRORE: {error_msg}\n")
            raise RuntimeError(error_msg)
        
        output = res.stdout.strip()
        if output:
            pyt_Print(f"  {output}")
        else:
            pyt_Print(f"  [OK] Pull completato con successo")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] SUCCESSO: Pull completato\n")
            if output:
                lf.write(f"Output: {output}\n")
            
    except subprocess.TimeoutExpired:
        error_msg = "Timeout durante git pull (300 secondi)"
        pyt_Print(f"  [ERRORE] {error_msg}")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] ERRORE: {error_msg}\n")
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Errore durante git pull: {str(e)}"
        pyt_Print(f"  [ERRORE] {error_msg}")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{pyt_Timestamp()}] ERRORE: {error_msg}\n")
        raise RuntimeError(error_msg)
    
    # Fase 3: Riepilogo finale
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Riepilogo finale")
    summary = f"""  Operazione: PULL
  Repository: {owner}/{repo_name}
  Branch: {branch}
  Esito: SUCCESSO
  Log file: {log_file}"""
    pyt_Print(summary)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[{pyt_Timestamp()}] {summary}\n")

def app_report(params):
    """Genera report da template e dati JSON usando la libreria esterna pyt_report."""
    if len(params) != 3:
        raise ValueError("Sintassi errata. Uso: report <file_template> <file_json> <file_out_base>")
    
    file_template = params[0].strip('"\'')
    file_json = params[1].strip('"\'')
    file_out_base = params[2].strip('"\'')
    
    pyt_Print(f"[{pyt_Timestamp()}] START: report")
    pyt_Print(f"[{pyt_Timestamp()}] ARGS: template={file_template}, json={file_json}, out_base={file_out_base}")
    
    if not os.path.exists(file_template):
        raise FileNotFoundError(f"File template {file_template} non trovato.")
    if not os.path.exists(file_json):
        raise FileNotFoundError(f"File JSON {file_json} non trovato.")
    
    try:
        import pyt_report
    except ImportError:
        raise ImportError("Libreria pyt_report non installata. Installarla con: pip install pyt_report")
    
    try:
        with open(file_json, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato in {file_json}: {e}")
    
    records = json_data.get("records", {})
    if not records:
        raise ValueError("Nessun record trovato nella sezione 'records' del JSON")
    
    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura template e file JSON completata. Trovati {len(records)} record.")
    
    for record_id, record_data in records.items():
        outfile = f"{file_out_base}{record_id}{os.path.splitext(file_template)[1]}"
        pyt_Print(f"[{pyt_Timestamp()}] Elaboro ID: {record_id}, file {outfile}")
        pyt_report.process_record(file_template, record_data, outfile)
    
    pyt_Print(f"[{pyt_Timestamp()}] WRITE: Report generati con successo")

def app_7z_ts(params):
    if len(params) < 1 or len(params) > 2:
        raise ValueError("Sintassi errata. Uso: 7z_ts <pathsource> [path7z]")
    
    pathsource = params[0].strip('"\'')
    
    # Normalizzazione backslash doppi (preservando UNC)
    if pathsource.startswith("\\\\"):
        pathsource = "\\\\" + pathsource[2:].replace("\\\\", "\\")
    else:
        pathsource = pathsource.replace("\\\\", "\\")
    
    if not os.path.exists(pathsource) or not os.path.isdir(pathsource):
        raise FileNotFoundError(f"Cartella {pathsource} non trovata.")
    
    path7z = None
    if len(params) == 2:
        path7z = params[1].strip('"\'')
        if not os.path.exists(path7z):
            raise FileNotFoundError(f"Eseguibile 7z {path7z} non trovato.")
    else:
        if os.name == 'nt':
            pf = os.environ.get("ProgramFiles")
            pf86 = os.environ.get("ProgramFiles(x86)")
            candidates = []
            if pf: candidates.append(os.path.join(pf, "7-Zip", "7z.exe"))
            if pf86: candidates.append(os.path.join(pf86, "7-Zip", "7z.exe"))
            for c in candidates:
                if os.path.exists(c):
                    path7z = c
                    break
        
        if not path7z:
            path7z = shutil.which("7z")
        
        if not path7z:
            raise FileNotFoundError("Eseguibile 7z non trovato nel sistema.")
    
    data_timestamp = pyt_Timestamp().split(":")[0]
    folder_name = os.path.basename(os.path.normpath(pathsource))
    archive_name = f"{folder_name}_{data_timestamp}.7z"
    
    cmd = [path7z, "a", "-t7z", "-mx9", archive_name, pathsource]
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if res.returncode != 0:
        raise RuntimeError(f"Errore durante la compressione 7z: {res.stderr}")
    
    pyt_Print(f"Creato: {archive_name}")

def app_rightlist(params):
    """Elenca in listfile.txt i file e le cartelle presenti in path_verifica
    (destra) ma assenti in path_sorgente. Il confronto avviene per percorso
    relativo, ma nella lista vengono scritti i path assoluti (di path_verifica).
    Funziona su Windows e Linux (solo stdlib: os)."""
    if len(params) != 3:
        raise ValueError('Sintassi errata. Uso: rightlist <path_sorgente> <path_verifica> <listfile.txt> (su Windows evitare il backslash finale dentro le virgolette: usare h: e non "h:\\")')

    path_source = params[0].strip('"\'')
    path_check = params[1].strip('"\'')
    list_file = params[2].strip('"\'')

    if not os.path.isdir(path_source):
        raise FileNotFoundError(f"Cartella sorgente {path_source} non trovata.")
    if not os.path.isdir(path_check):
        raise FileNotFoundError(f"Cartella da verificare {path_check} non trovata.")

    walk_errors = []
    _PROGRESS_EVERY = 50000

    def _on_walk_error(err):
        walk_errors.append(str(err))
        pyt_Print(f"[{pyt_Timestamp()}]   ATTENZIONE scansione: {err}")

    def _rel(base, full, fallback):
        try:
            return os.path.relpath(full, base)
        except ValueError:
            return fallback

    def _walk_entries(base, label):
        """Yield (kind, relpath) con potatura dei cicli (junction/symlink,
        tipici nelle scansioni di interi dischi) e avanzamento periodico."""
        seen = set()
        try:
            st = os.stat(base)
            seen.add((st.st_dev, st.st_ino))
        except OSError:
            pass
        count = 0
        next_mark = _PROGRESS_EVERY
        for root, dirs, files in os.walk(base, onerror=_on_walk_error):
            keep = []
            for d in dirs:
                full = os.path.join(root, d)
                try:
                    st = os.stat(full)
                    key = (st.st_dev, st.st_ino)
                except OSError as e:
                    walk_errors.append(f"{full}: {e}")
                    continue
                if key in seen:
                    continue
                seen.add(key)
                keep.append(d)
            dirs[:] = keep
            for d in dirs:
                yield ("DIR", _rel(base, os.path.join(root, d), d))
            for f in files:
                yield ("FILE", _rel(base, os.path.join(root, f), f))
            count += len(dirs) + len(files)
            if count >= next_mark:
                pyt_Print(f"[{pyt_Timestamp()}]   {label}: scansionate {count} voci...")
                next_mark += _PROGRESS_EVERY

    def _collect_entries(base):
        """Raccoglie i percorsi relativi di file e cartelle sotto base."""
        return set(_walk_entries(base, f"Scansione {base}"))

    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Scansione della cartella sorgente {path_source}")
    source_entries = _collect_entries(path_source)
    pyt_Print(f"[{pyt_Timestamp()}]   Trovate {len(source_entries)} voci in sorgente")

    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Scansione di {path_check} e confronto")
    source_rel = {rel for (_kind, rel) in source_entries}
    check_abs = os.path.abspath(path_check)
    missing = []
    for (kind, rel) in _walk_entries(path_check, f"Scansione {path_check}"):
        if rel not in source_rel:
            missing.append((kind, os.path.join(check_abs, rel)))

    missing.sort(key=lambda item: (item[1].lower(), item[0]))

    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Scrittura della lista in {list_file}")
    list_dir = os.path.dirname(os.path.abspath(list_file))
    if list_dir and not os.path.exists(list_dir):
        os.makedirs(list_dir)
    n_dir = sum(1 for (kind, _rel) in missing if kind == "DIR")
    n_file = len(missing) - n_dir
    with open(list_file, "w", encoding="utf-8") as lf:
        for (kind, full) in missing:
            lf.write(f"{kind} {full}\n")

    pyt_Print(f"[{pyt_Timestamp()}] Riepilogo - Voci mancanti in sorgente: {len(missing)} "
              f"(cartelle: {n_dir}, file: {n_file}), errori scansione: {len(walk_errors)}")
    pyt_Print(f"Lista scritta in: {list_file}")

def app_delfiles(params):
    """Cancella i file e le cartelle elencati in listfile (output di rightlist),
    usando i path assoluti scritti nelle voci. Le voci relative (formato
    precedente) sono risolte rispetto alla directory corrente.
    Ordine: prima i FILE, poi le DIR (dalle piu' profonde).
    Le righe senza prefisso FILE/DIR come prima parola vengono interpretate
    in base a cio' che si trova su disco. Funziona su Windows e Linux."""
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: delfiles <listfile.txt>")

    list_file = params[0].strip('"\'')

    if not os.path.isfile(list_file):
        raise FileNotFoundError(f"File lista {list_file} non trovato.")

    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura della lista {list_file}")
    raw_entries = []
    with open(list_file, "r", encoding="utf-8") as lf:
        for line in lf:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] in ("FILE", "DIR"):
                raw_entries.append((parts[0], parts[1]))
            else:
                raw_entries.append((None, line))
    pyt_Print(f"[{pyt_Timestamp()}]   Trovate {len(raw_entries)} voci in lista")

    files, dirs = [], []
    skipped = 0
    errors = 0
    for (kind, entry) in raw_entries:
        full = os.path.abspath(entry)
        if not os.path.lexists(full):
            skipped += 1
            pyt_Print(f"[{pyt_Timestamp()}]   SALTATO (non trovato): {entry}")
            continue
        if kind is None:
            # Interpreta dal disco: link/dir/file
            kind = "DIR" if (os.path.isdir(full) and not os.path.islink(full)) else "FILE"
        if kind == "DIR":
            dirs.append((entry, full))
        else:
            files.append((entry, full))

    def _delete_file(rel, full):
        try:
            if os.path.islink(full) or os.path.isfile(full):
                os.unlink(full)
            elif os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
            pyt_Print(f"[{pyt_Timestamp()}]   ELIMINATO FILE: {rel}")
            return True
        except Exception as e:
            pyt_Print(f"[{pyt_Timestamp()}]   ERRORE su {rel}: {e}")
            return False

    def _delete_dir(rel, full):
        try:
            if os.path.islink(full):
                os.unlink(full)
            else:
                shutil.rmtree(full, ignore_errors=False)
            pyt_Print(f"[{pyt_Timestamp()}]   ELIMINATA DIR: {rel}")
            return True
        except Exception as e:
            pyt_Print(f"[{pyt_Timestamp()}]   ERRORE su {rel}: {e}")
            return False

    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Cancellazione di {len(files)} FILE")
    n_files = 0
    for (rel, full) in files:
        if _delete_file(rel, full):
            n_files += 1
        else:
            errors += 1

    # Dir dalle piu' profonde verso la radice
    dirs.sort(key=lambda item: (item[0].count(os.sep) + item[0].count("/"), item[0].lower()), reverse=True)
    pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Cancellazione di {len(dirs)} DIR")
    n_dirs = 0
    for (rel, full) in dirs:
        if not os.path.lexists(full):
            skipped += 1
            pyt_Print(f"[{pyt_Timestamp()}]   SALTATO (non trovato): {rel}")
            continue
        if _delete_dir(rel, full):
            n_dirs += 1
        else:
            errors += 1

    pyt_Print(f"[{pyt_Timestamp()}] Riepilogo - File eliminati: {n_files}, "
              f"Cartelle eliminate: {n_dirs}, Saltati: {skipped}, Errori: {errors}")

def app_reqdoc(params):
    """Genera un file Markdown che documenta le librerie di un requirements.txt.
    Output: stesso percorso del requirements con estensione .md.
    Dati locali via importlib.metadata + arricchimento PyPI online (se requests disponibile).
    Funziona su Windows e Linux (solo stdlib + requests opzionale)."""
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: reqdoc <requirements.txt>")

    req_file = params[0].strip('"\'')

    if not os.path.isfile(req_file):
        raise FileNotFoundError(f"File requirements {req_file} non trovato.")

    out_file = os.path.splitext(req_file)[0] + ".md"

    def _md_cell(text):
        """Pulisce un REPLo per l'uso in cella di tabella Markdown."""
        if not text:
            return ""
        return " ".join(str(text).split()).replace("|", "\\|")

    def _clean_requires(requires):
        """Rimuove i marker d'ambiente (dopo ;) e le voci vuote."""
        cleaned = []
        for req in requires or []:
            req = req.split(";")[0].strip()
            if req:
                cleaned.append(req)
        return cleaned

    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura e parsing di {req_file}")
    entries = []
    skipped_lines = 0
    try:
        with open(req_file, "r", encoding="utf-8-sig") as f:
            req_text = f.read()
    except (UnicodeDecodeError, UnicodeError):
        # pip freeze su Windows redireziona spesso in UTF-16
        with open(req_file, "r", encoding="utf-16") as f:
            req_text = f.read()
    for raw in req_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-") or "://" in line:
            skipped_lines += 1
            continue
        name = line
        pinned = ""
        for i, ch in enumerate(line):
            if ch in "=<>!~[; ":
                name = line[:i].strip()
                rest = line[i:].strip()
                if rest.startswith("=="):
                    pinned = rest[2:].strip().split()[0].split(";")[0].strip()
                break
        if not name:
            skipped_lines += 1
            continue
        entries.append((name, pinned))
    pyt_Print(f"[{pyt_Timestamp()}]   Trovate {len(entries)} librerie ({skipped_lines} righe saltate)")

    pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Lettura metadata locali (importlib.metadata)")
    rows = []
    need_online = []
    for (name, pinned) in entries:
        version = pinned
        summary = ""
        home = ""
        requires = []
        try:
            dist = importlib.metadata.distribution(name)
            version = dist.version or pinned
            meta = dist.metadata
            summary = (meta.get("Summary") or "").strip()
            home = (meta.get("Home-page") or "").strip()
            if not home:
                for url in (meta.get_all("Project-URL") or []):
                    parts = url.split(",", 1)
                    if len(parts) == 2 and parts[1].strip():
                        home = parts[1].strip()
                        break
            requires = _clean_requires(dist.requires)
        except importlib.metadata.PackageNotFoundError:
            pass
        except Exception as e:
            pyt_Print(f"[{pyt_Timestamp()}]   ATTENZIONE metadata locali per {name}: {e}")
        rows.append({"name": name, "version": version or "n/d",
                     "summary": summary, "home": home, "requires": requires,
                     "from_pypi": False})
        if not summary and not requires:
            need_online.append(len(rows) - 1)
    pyt_Print(f"[{pyt_Timestamp()}]   Metadata locali ok, da arricchire online: {len(need_online)}")

    n_pypi = 0
    if need_online:
        if requests is None:
            pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Arricchimento PyPI saltato (libreria requests non installata)")
        else:
            pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Arricchimento PyPI online per {len(need_online)} librerie")
            for idx in need_online:
                name = rows[idx]["name"]
                try:
                    resp = requests.get(f"https://pypi.org/pypi/{name}/json", timeout=10)
                    if resp.status_code != 200:
                        pyt_Print(f"[{pyt_Timestamp()}]   PyPI {name}: HTTP {resp.status_code}")
                        continue
                    info = resp.json().get("info", {})
                    if not rows[idx]["summary"]:
                        rows[idx]["summary"] = (info.get("summary") or "").strip()
                    if not rows[idx]["home"]:
                        rows[idx]["home"] = (info.get("home_page") or "").strip()
                    if not rows[idx]["requires"]:
                        rows[idx]["requires"] = _clean_requires(info.get("requires_dist"))
                    if not rows[idx]["version"] or rows[idx]["version"] == "n/d":
                        rows[idx]["version"] = (info.get("version") or "n/d").strip()
                    rows[idx]["from_pypi"] = True
                    n_pypi += 1
                except Exception as e:
                    pyt_Print(f"[{pyt_Timestamp()}]   PyPI {name}: {e}")
                    continue
            pyt_Print(f"[{pyt_Timestamp()}]   Arricchite via PyPI: {n_pypi}")

    pyt_Print(f"[{pyt_Timestamp()}] Fase 4: Scrittura del Markdown in {out_file}")
    rows.sort(key=lambda r: r["name"].lower())
    n_missing = 0
    with open(out_file, "w", encoding="utf-8") as out:
        out.write(f"# Librerie Python — {os.path.basename(req_file)}\n\n")
        out.write(f"Generato: {pyt_Timestamp()} con `pyt reqdoc`\n\n")
        out.write(f"Librerie in elenco: {len(rows)}\n\n")
        out.write("| Libreria | Versione | Scopo | Dipendenze | Home-page |\n")
        out.write("|---|---|---|---|---|\n")
        for r in rows:
            deps = ", ".join(r["requires"]) if r["requires"] else "-"
            if not r["summary"] and not r["requires"]:
                n_missing += 1
            out.write(f"| {_md_cell(r['name'])} | {_md_cell(r['version'])} | "
                      f"{_md_cell(r['summary']) if r['summary'] else 'n/d'} | "
                      f"{_md_cell(deps) if deps != '-' else '-'} | "
                      f"{_md_cell(r['home']) if r['home'] else '-'} |\n")

    pyt_Print(f"[{pyt_Timestamp()}] Riepilogo - Documentate: {len(rows)}, "
              f"arricchite via PyPI: {n_pypi}, senza dati: {n_missing}, righe saltate: {skipped_lines}")
    pyt_Print(f"Markdown scritto in: {out_file}")

def _split_volume_spec(spec):
    """Divide "host[:container]" rispettando la lettera drive Windows.
    Ritorna (host, container_ou_None). Esempi:
    "C:\\dir" -> ("C:\\dir", None); "C:\\dir:/data" -> ("C:\\dir", "/data");
    "./rel:/data" -> ("./rel", "/data")."""
    spec = spec.strip()
    if len(spec) >= 2 and spec[1] == ":" and spec[0].isalpha():
        rest = spec[2:]
        idx = rest.find(":")
        if idx == -1:
            return (spec, None)
        host = spec[:2 + idx]
        cont = rest[idx + 1:].strip()
        return (host, cont if cont else None)
    if ":" in spec:
        host, _, cont = spec.partition(":")
        cont = cont.strip()
        return (host.strip(), cont if cont else None)
    return (spec, None)

def _parse_port_spec(spec):
    """Valida "host:container" con porte numeriche. Ritorna (host, container).
    Solleva ValueError se malformato."""
    parts = spec.strip().split(":")
    if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        raise ValueError(f"porta_host malformata '{spec}'. Uso: host:container (es. 8080:80).")
    return (parts[0].strip(), parts[1].strip())

def _podman_run(args):
    """Esegue podman con lista argomenti (mai shell=True). Ritorna CompletedProcess."""
    return subprocess.run(["podman"] + args, capture_output=True, text=True)

def _podman_machine_state(name):
    """Ritorna True (attiva), False (esiste, ferma) o None (mancante/sconosciuta)."""
    r = _podman_run(["machine", "list", "--format", "json"])
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
        items = data if isinstance(data, list) else [data]
        for m in items:
            if isinstance(m, dict) and m.get("Name") == name:
                return bool(m.get("Running", False))
        return None
    except ValueError:
        found = False
        running = False
        for line in r.stdout.splitlines():
            if name in line:
                found = True
                if "running" in line.lower():
                    running = True
        return running if found else None

def _podman_container_status(name):
    """Ritorna la stringa di stato del container o None se non esiste."""
    r = _podman_run(["ps", "-a", "--format", "{{.Names}} {{.Status}}"])
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if parts and parts[0] == name:
            return parts[1] if len(parts) > 1 else ""
    return None

def app_podman(params):
    """Gestisce container podman da file JSON a sezioni con id.
    Ogni sezione: command (solo cstart per ora), volume (opz, creato se manca),
    image (obbl), name (obbl), porta_host (opz, formato host:container),
    machine (opz, avviata o creata se manca).
    Funziona su Windows e Linux (richiede podman installato)."""
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: podman <config.json>")

    config_file = params[0].strip('"\'')

    if not os.path.exists(config_file):
        raise FileNotFoundError(f"File di configurazione {config_file} non trovato.")

    pyt_Print(f"[{pyt_Timestamp()}] Fase 1: Lettura e validazione del file di configurazione JSON")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato: {e}")
    except UnicodeDecodeError:
        with open(config_file, "r", encoding="utf-16") as f:
            try:
                cfg = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON malformato: {e}")

    if not isinstance(cfg, dict):
        raise ValueError("Il JSON deve essere un oggetto con sezioni identificate da id.")

    stats = {"created": 0, "started": 0, "skipped": 0, "errors": 0}

    for section_id, section in cfg.items():
        pyt_Print(f"\n[{pyt_Timestamp()}] SEZIONE: {section_id}")
        if not isinstance(section, dict):
            pyt_Print(f"[{pyt_Timestamp()}]   ERRORE: la sezione deve essere un oggetto JSON.")
            stats["errors"] += 1
            continue

        command = str(section.get("command", "")).strip().lower()
        image = str(section.get("image", "")).strip()
        name = str(section.get("name", "")).strip()
        volume = section.get("volume")
        porta_host = section.get("porta_host")
        machine = section.get("machine")

        if command != "cstart":
            pyt_Print(f"[{pyt_Timestamp()}]   SALTATO: command '{command}' non supportato (solo cstart per ora).")
            stats["skipped"] += 1
            continue
        if not image:
            pyt_Print(f"[{pyt_Timestamp()}]   ERRORE: chiave 'image' obbligatoria.")
            stats["errors"] += 1
            continue
        if not name:
            pyt_Print(f"[{pyt_Timestamp()}]   ERRORE: chiave 'name' obbligatoria.")
            stats["errors"] += 1
            continue

        try:
            # Fase 2: macchina virtuale (opzionale)
            if machine:
                machine = str(machine).strip()
                pyt_Print(f"[{pyt_Timestamp()}] Fase 2: Verifica macchina '{machine}'")
                state = _podman_machine_state(machine)
                if state is True:
                    pyt_Print(f"[{pyt_Timestamp()}]   Macchina già attiva.")
                elif state is False:
                    pyt_Print(f"[{pyt_Timestamp()}]   Avvio macchina...")
                    r = _podman_run(["machine", "start", machine])
                    if r.returncode != 0:
                        raise RuntimeError(f"Avvio macchina fallito: {r.stderr.strip()}")
                    pyt_Print(f"[{pyt_Timestamp()}]   Macchina avviata.")
                else:
                    pyt_Print(f"[{pyt_Timestamp()}]   Macchina non trovata, creazione...")
                    r = _podman_run(["machine", "init", machine])
                    if r.returncode != 0:
                        raise RuntimeError(f"Creazione macchina fallita: {r.stderr.strip()}")
                    r = _podman_run(["machine", "start", machine])
                    if r.returncode != 0:
                        raise RuntimeError(f"Avvio macchina fallito: {r.stderr.strip()}")
                    pyt_Print(f"[{pyt_Timestamp()}]   Macchina creata e avviata.")

            # Fase 3: volume (opzionale, creato se manca)
            volumes = []
            if volume:
                host, cont = _split_volume_spec(str(volume))
                host_abs = os.path.abspath(host)
                os.makedirs(host_abs, exist_ok=True)
                target = cont if cont else "/data"
                volumes = ["-v", f"{host_abs}:{target}"]
                pyt_Print(f"[{pyt_Timestamp()}] Fase 3: Volume {host_abs}:{target}")

            # Fase 4: porte (opzionale)
            ports = []
            if porta_host:
                hp, cp = _parse_port_spec(str(porta_host))
                ports = ["-p", f"{hp}:{cp}"]
                pyt_Print(f"[{pyt_Timestamp()}] Fase 4: Porta {hp}:{cp}")

            # Fase 5: container esistente?
            pyt_Print(f"[{pyt_Timestamp()}] Fase 5: Verifica container '{name}'")
            status = _podman_container_status(name)
            if status is not None and "up" in status.lower():
                pyt_Print(f"[{pyt_Timestamp()}]   SALTATO: container già attivo ({status}).")
                stats["skipped"] += 1
                continue
            if status is not None:
                pyt_Print(f"[{pyt_Timestamp()}]   Container esistente ma fermo, avvio...")
                r = _podman_run(["start", name])
                if r.returncode != 0:
                    raise RuntimeError(f"Avvio container fallito: {r.stderr.strip()}")
                pyt_Print(f"[{pyt_Timestamp()}]   AVVIATO: {name}")
                stats["started"] += 1
                continue

            # Fase 6: creazione
            pyt_Print(f"[{pyt_Timestamp()}] Fase 6: Creazione container '{name}' da '{image}'")
            cmd = ["run", "-d", "--name", name] + volumes + ports + [image]
            r = _podman_run(cmd)
            if r.returncode != 0:
                raise RuntimeError(f"Creazione container fallita: {r.stderr.strip()}")
            pyt_Print(f"[{pyt_Timestamp()}]   CREATO: {name} ({r.stdout.strip()[:12]})")
            stats["created"] += 1

        except Exception as e:
            pyt_Print(f"[{pyt_Timestamp()}]   ERRORE su sezione '{section_id}': {e}")
            stats["errors"] += 1

    pyt_Print(f"\n[{pyt_Timestamp()}] RIEPILOGO FINALE")
    pyt_Print(f"[{pyt_Timestamp()}] Creati: {stats['created']}, Avviati: {stats['started']}, "
              f"Saltati: {stats['skipped']}, Errori: {stats['errors']}")

def app_form(params):
    """Mostra un form interattivo descritto nel JSON usando la libreria esterna pyt_form."""
    if len(params) != 1:
        raise ValueError("Sintassi errata. Uso: form <fileform.json>")

    fileform = params[0].strip('"\'')

    if not os.path.exists(fileform):
        raise FileNotFoundError(f"File form {fileform} non trovato.")

    try:
        import pyt_form
    except ImportError:
        raise ImportError("Libreria pyt_form non installata.")

    pyt_Print(f"[{pyt_Timestamp()}] START: form")
    pyt_Print(f"[{pyt_Timestamp()}] ARGS: fileform={fileform}")
    results_path = pyt_form.run_form(fileform, pyt_Print, pyt_Timestamp)
    pyt_Print(f"[{pyt_Timestamp()}] WRITE: {results_path}")

def app_grep(params):
    """Cerca un pattern (regex) in uno o piu' file o cartelle.
    Opzioni: -i/--ignore-case (ignora maiuscole), -v/--invert-match (righe NON
    corrispondenti), -r/--recursive (scansione ricorsiva delle cartelle),
    -p <path>/--path=<path> (cartella base di ricerca: senza file elencati cerca
    tutti i file di <path>, con file relativi li' risolve da <path>).
    -s <REPLo>/--replace=<REPLo> Sostituisce il pattern (REPLo fisso) con <REPLo>
    in tutti i file dove viene trovato. Attende 1 secondo dopo ogni file modificato.
    Espande le wildcard (*, ?, [..]). Stampa sopra i risultati il file di
    provenienza. Log GREP.START (con i file da cercare) e GREP.END.
    Solo stdlib (os, glob, re, time). Funziona su Windows e Linux."""
    ignore_case = False
    invert = False
    recursive = False
    base_path = None
    replace_text = None
    simulate = False
    positional = []
    i = 0
    while i < len(params):
        arg = params[i].strip('"\'')
        low = arg.lower()
        if low in ("-i", "--ignore-case"):
            ignore_case = True
        elif low in ("-v", "--invert-match"):
            invert = True
        elif low in ("-r", "--recursive"):
            recursive = True
        elif low in ("-p", "--path"):
            i += 1
            if i >= len(params):
                raise ValueError("L'opzione -p richiede il path di ricerca.")
            base_path = params[i].strip('"\'')
        elif low.startswith("--path="):
            base_path = low.split("=", 1)[1]
        elif low in ("-s", "--replace"):
            i += 1
            if i >= len(params):
                raise ValueError("L'opzione -s/--replace richiede il testo di sostituzione.")
            replace_text = params[i].strip('"\'')
        elif low in ("-sx", "--simulate"):
            i += 1
            if i >= len(params):
                raise ValueError("L'opzione -sx/--simulate richiede il testo di sostituzione.")
            replace_text = params[i].strip('"\'')
            simulate = True
        elif low.startswith("--replace="):
            replace_text = low.split("=", 1)[1]
        elif low.startswith("--simulate="):
            replace_text = low.split("=", 1)[1]
            simulate = True
        elif arg.startswith("-") and len(arg) > 1:
            raise ValueError(f"Opzione sconosciuta: {arg}")
            replace_text = params[i].strip('"\'')
            simulate = True
        elif low.startswith("--replace="):
            replace_text = low.split("=", 1)[1]
        elif low.startswith("--simulate="):
            replace_text = low.split("=", 1)[1]
            simulate = True
        elif arg.startswith("-") and len(arg) > 1:
            raise ValueError(f"Opzione sconosciuta: {arg}")
        else:
            positional.append(arg)
        i += 1

    if not positional:
        raise ValueError("Sintassi errata. Uso: grep [-i] [-v] [-r] [-p <path>] [-s <REPLo>] <pattern> [file|dir...]")
    pattern = positional[0]
    file_args = positional[1:]

    if not pattern:
        raise ValueError("Pattern vuoto.")
    if not file_args and base_path is None:
        raise ValueError("Nessun file: indicare i file o -p/--path.")

    # Se c'è -s o -sx, il pattern DEVE essere REPLo fisso (niente regex speciali)
    if replace_text is not None:
        import re as _re
        # Verifica che il pattern non contenga caratteri regex speciali
        if any(ch in pattern for ch in r".^$*+?{}[]\|()"):
            raise ValueError("Con -s/--replace/-sx/--simulate il pattern deve essere REPLo fisso (niente metacaratteri regex: .^$*+?{}[]\\|()).")

    try:
        flags = re.IGNORECASE if ignore_case else 0
        # Se -s: pattern letterale (escape), altrimenti regex
        if replace_text is not None:
            regex = re.compile(re.escape(pattern), flags)
        else:
            regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Espressione regolare non valida: {e}")

    base_abs = os.path.abspath(base_path) if base_path else None
    files = []
    seen = set()
    errors = []

    def _add_file(fpath):
        fpath_abs = os.path.abspath(fpath)
        if fpath_abs not in seen:
            seen.add(fpath_abs)
            files.append(fpath_abs)

    def _scan_dir(dpath):
        if recursive:
            for root, _dirs, fnames in os.walk(dpath):
                for fn in fnames:
                    _add_file(os.path.join(root, fn))
        else:
            for fn in os.listdir(dpath):
                fpath_abs = os.path.join(dpath, fn)
                if os.path.isfile(fpath_abs):
                    _add_file(fpath_abs)

    if file_args:
        for fa in file_args:
            target = fa if (not base_abs or os.path.isabs(fa)) else os.path.join(base_abs, fa)
            if any(ch in target for ch in "*?["):
                matched = glob.glob(target, recursive=True)
                if matched:
                    for m in sorted(matched):
                        if os.path.isfile(m):
                            _add_file(m)
                        elif os.path.isdir(m):
                            _scan_dir(m)
                else:
                    errors.append(f"{target}: maschera senza corrispondenze")
            elif os.path.isdir(target):
                _scan_dir(target)
            elif os.path.isfile(target):
                _add_file(target)
            else:
                errors.append(f"{target}: non trovato")
    else:
        if not os.path.isdir(base_abs):
            raise FileNotFoundError(f"Cartella {base_abs} non trovata.")
        for fn in os.listdir(base_abs):
            fpath_abs = os.path.join(base_abs, fn)
            if os.path.isfile(fpath_abs):
                _add_file(fpath_abs)
            elif os.path.isdir(fpath_abs) and recursive:
                _scan_dir(fpath_abs)

    if not files and errors:
        raise FileNotFoundError("Nessun file da cercare: " + "; ".join(errors))

    opts = ""
    if ignore_case:
        opts += " -i"
    if invert:
        opts += " -v"
    if recursive:
        opts += " -r"
    if base_abs:
        opts += f" -p \"{base_abs}\""
    if replace_text is not None:
        opts += f" -s \"{replace_text}\""
    spec_files = " ".join(file_args) if file_args else "*"
    pyt_Print(f"GREP.START: {pyt_Timestamp()} grep{opts} pattern=\"{pattern}\" file: {spec_files} ({len(files)} da cercare)")

    def _is_binary(fpath):
        try:
            with open(fpath, "rb") as bf:
                return b"\x00" in bf.read(8192)
        except OSError as e:
            errors.append(f"{fpath}: {e}")
            return True

    total_matches = 0
    files_out = 0
    modified_files = 0
    import time
    for fpath_abs in files:
        if _is_binary(fpath_abs):
            continue
        count_file = 0
        try:
            with open(fpath_abs, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
            # Conta le occorrenze
            matches = list(regex.finditer(content))
            count_file = len(matches)
            if count_file == 0:
                continue
            total_matches += count_file
            files_out += 1
            if replace_text is not None:
                # Modalità sostituzione o simulazione
                new_content = regex.sub(replace_text, content)
                if simulate:
                    # Dry-run: mostra cosa cambierebbe senza scrivere
                    modified_files += 1
                    pyt_Print(f"SIMULAZIONE: {fpath_abs} - {count_file} sostituzioni")
                    # Mostra anteprima diff (prime 3 righe modificate)
                    old_lines = content.splitlines()
                    new_lines = new_content.splitlines()
                    diff_count = 0
                    for i, (old, new) in enumerate(zip(old_lines, new_lines)):
                        if old != new and diff_count < 3:
                            pyt_Print(f"  - {old}")
                            pyt_Print(f"  + {new}")
                            diff_count += 1
                    if diff_count == 3:
                        pyt_Print(f"  ... e altre {count_file - 3} modifiche")
                else:
                    # Scrive realmente
                    with open(fpath_abs, "w", encoding="utf-8-sig", errors="replace") as f:
                        f.write(new_content)
                    modified_files += 1
                    pyt_Print(f"MODIFICATO: {fpath_abs} - {count_file} sostituzioni")
                    time.sleep(1)  # Attende 1 secondo dopo ogni file modificato
            else:
                # Modalità ricerca: stampa le righe con match
                pyt_Print(f"FILE: {fpath_abs}")
                lines = content.splitlines()
                for line_num, line in enumerate(lines, 1):
                    if bool(regex.search(line)) != invert:
                        pyt_Print(f"{line_num}: {line.rstrip()}")
                pyt_Print(f"{count_file} corrispondenze in {os.path.basename(fpath_abs)}")
        except OSError as e:
            errors.append(f"{fpath_abs}: {e}")
            continue

    if total_matches == 0:
        if replace_text is not None:
            if simulate:
                pyt_Print("Nessuna sostituzione simulata")
            else:
                pyt_Print("Nessuna sostituzione effettuata")
        else:
            pyt_Print("Nessuna corrispondenza trovata")
    for err in errors:
        pyt_Print(f"grep: {err}")
    if replace_text is not None:
        if simulate:
            pyt_Print(f"GREP.END: {pyt_Timestamp()} - SIMULAZIONE: file da modificare: {modified_files}, sostituzioni totali: {total_matches}, file con match: {files_out}/{len(files)}, errori: {len(errors)}")
        else:
            pyt_Print(f"GREP.END: {pyt_Timestamp()} - file modificati: {modified_files}, sostituzioni totali: {total_matches}, file con match: {files_out}/{len(files)}, errori: {len(errors)}")
    else:
        pyt_Print(f"GREP.END: {pyt_Timestamp()} - corrispondenze: {total_matches}, "
                  f"file con match: {files_out}/{len(files)}, errori: {len(errors)}")

# ==============================================================================
# MOTORE DI ESECUZIONE
# ==============================================================================
def esegui_direttive(directives):
    """Cicla sulle direttive, gestisce i log di START/END e le eccezioni."""
    for direttiva, params in directives:
        # Help / Nessuna direttiva
        if direttiva in [None, "h", "help"]:
            app_help()
            continue
        
        # Converti underscore in punto per il display (es. git_push -> git.push)
        display_name = direttiva.replace("_", ".")
        pyt_Print(f"PYT.START: {display_name.upper()} {pyt_Timestamp()}")
        
        try:
            func_name = f"app_{direttiva}"
            if func_name in globals():
                globals()[func_name](params)
            else:
                pyt_Print(f"Errore: direttiva '{display_name}' non riconosciuta.")
                app_help()
        except Exception as e:
            pyt_Print(f"ERRORE [{display_name}]: {str(e)}")
        finally:
            pyt_Print(f"PYT.END: {display_name.upper()} {pyt_Timestamp()}")

def main():
    # Console senza codifica corrispondente: sostituisce i caratteri non
    # stampabili (BOM, unicode) con '?' invece di bloccare la direttiva
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    pyt_Print(f"PYT.START: {PYT_VER} {pyt_Timestamp()}")
    try:
        directives = parse_argv(sys.argv)
        if not directives:
            pyt_Print("Errore fatale: nessuna direttiva valida trovata.")
            sys.exit(1)
        esegui_direttive(directives)
    except SystemExit:
        pass
    except Exception as e:
        pyt_Print(f"Errore fatale imprevisto: {str(e)}")
    finally:
        pyt_End()

if __name__ == "__main__":
    main()
