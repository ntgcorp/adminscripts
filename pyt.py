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
import importlib.metadata

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

# ==============================================================================
# VARIABILI GLOBALI E COSTANTI
# ==============================================================================
PYT_VER = "20261008"
QEMU_IMG = r"X:\_Applic\Qemu\qemu-img.exe"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "pyt.log")

# ==============================================================================
# FUNZIONI INTERNE
# ==============================================================================
def pyt_Timestamp():
    """Restituisce una stringa nel formato YYYYMMDD:HHMMSS (ora locale)."""
    return datetime.datetime.now().strftime("%Y%m%d:%H%M%S")

def pyt_Print(stringa):
    """Stampa la stringa su console e la aggiunge in coda al file pyt.log."""
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
    # Converte i punti in underscore per compatibilità con i nomi funzione
    directive_name = args[0].lower().replace(".", "_")
    return [(directive_name, filtered_params)]

# ==============================================================================
# FUNZIONI DIRETTIVE (app_*)
# ==============================================================================
def app_help():
    """Stampa l'help. Non usa pyt_Print e non genera log START/END."""
    help_text = f"""pyt v{PYT_VER} - Tool Python per eseguire comandi via command line

DIRETTIVE DISPONIBILI:
    help, h
       Mostra questo help. Non richiede parametri.
    doc2md <f1>
       Converte da docx a md il file f1, salvando file multimediali in resources/
    md2html <f1> <f2>
       Converte un file markdown f1 in html f2
    md2page <f1> <f2>
       Converte un file markdown f1 in una pagina html completa f2 usando OpenRouter API
    wsl_export <f1> <f2>
       Esporta il container WSL f1 nel file f2 (solo Windows)
    vhdx2vmdk <f1> <f2>
       Converte file vhdx in vmdk usando qemu-img (solo Windows)
    7z_ts <pathsource> [path7z]
       Comprime la cartella pathsource in un archivio .7z con timestamp (solo data)
    disk_check <disk_name> <disk_report> <warning_pct>
       Verifica spazio disco e occupazione cartelle, genera report ed eventuale flag di warning
    sync <config.json>
       Sincronizza cartelle secondo un file di configurazione JSON.
       Supporta type: file, filesync, ftp, ssh.
       Supporta sia JSON con singolo job sia JSON "catalogo" con array "jobs".
    sync_script [path_source] [path_dest] [file_output]
       Genera uno script batch per sincronizzazione mirror con robocopy (solo Windows).
       Parametri opzionali: sorgente (default \\ntgdsnas), dest (default n:), output (default admin_sync_script.cmd).
       Usa variabile d'ambiente SYNC_FOLDERS per lista cartelle.
    robocopy <config.json>
       Copia file specificati da sorgente a destinazione secondo JSON.
       Supporta settings globali (log, err.exit) e actions multiple con path_source, path_dest, mode (overwrite|old),
       files[].
       Funziona su Windows e Linux (usa shutil, non robocopy.exe).
     rightlist <path_sorgente> <path_verifica> <listfile.txt>
        Elenca in listfile.txt (con path assoluti) i file e le cartelle
        presenti in path_verifica ma assenti in path_sorgente.
        Funziona su Windows e Linux.
     delfiles <listfile.txt>
        Cancella i file e le cartelle elencati in listfile.txt (output di rightlist),
        usando i path assoluti scritti nelle voci. Prima i FILE, poi le DIR.
        Le righe senza prefisso FILE/DIR vengono interpretate dal disco.
        Funziona su Windows e Linux.
    git.push <config.json>
       Esegue git push su GitHub autenticato con token.
       JSON: repo_path, username, token, repo_name, branch, git_path, log, commit_message (opz), commit_all (opz).
       Supporta variabili d'ambiente: "$VAR_NAME" per token/username.
       Windows: git_path obbligatorio (es. "X:\\_Applic\\Bash\\bin\\git.exe").
       Se commit_message è presente, esegue git add e git commit prima del push.
git.pull <config.json>
       Esegue git pull da GitHub autenticato con token.
       JSON: repo_path, username, token, repo_name, branch, git_path, log.
       Supporta variabili d'ambiente: "$VAR_NAME" per token/username.
     report <file_template> <file_json> <file_out_base>
        Genera report da template e dati JSON (libreria pyt_report).
        file_template: file template con segnaposto
        file_json: file JSON con sezione "records" contenente ID e campi
        file_out_base: base nome file output (verrà aggiunto ID + estensione)
     reqdoc <requirements.txt>
        Genera file Markdown con stesso nome che documenta le librerie:
        nome, versione, scopo, dipendenze, home-page.
        Dati locali (importlib.metadata) + arricchimento PyPI online se disponibile.
        Funziona su Windows e Linux.
    @ <nome_file>
       Esegue le direttive contenute nel file specificato
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

Restituisci SOLO il codice HTML completo, senza spiegazioni o testo aggiuntivo."""
    
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
        """Pulisce un testo per l'uso in cella di tabella Markdown."""
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