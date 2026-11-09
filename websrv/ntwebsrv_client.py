#!/usr/bin/env python3
"""
ntwebsrv_client.py - Client per ntwebsrv (Agente di Automazione)
Autore: ntwebserv project
Versione: 2.0
Richiede: Python 3.10+, requests

Supporta due modalità:
1. LEGACY (multipart): upload file + parametri via POST /ricevi
2. COMANDI (JSON RPC): save, exit, restart, reboot, poweroff, exec via POST /api/command
3. DOWNLOAD: GET /api/download/{target}?zip_mode=true
"""

import os
import sys
import json
import argparse
import locale
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union

try:
    import requests
except ImportError:
    requests = None

sys.path.insert(0, str(Path(__file__).parent))
from aiSys import Timestamp

LANG = "it" if locale.getdefaultlocale()[0] and locale.getdefaultlocale()[0].startswith("it") else "en"

HELP_TEXT = {
    "it": """
ntwebsrv_client.py - Client per ntwebsrv (Automation Agent)

USO:
    python ntwebsrv_client.py FILE_JSON [opzioni]

ARGOMENTI:
    FILE_JSON            File JSON con i dati/comando da inviare (obbligatorio)

OPZIONI:
    -u, --url URL        URL base server (default: http://localhost:8000)
    -k, --key KEY        Chiave segreta per autenticazione (header X-API-Key)
    -kh, --keyhash BASE  Segreto base per _kh (SHA256(base + giorno))
    -t, --timeout SEC    Timeout richiesta in secondi (default: 30)
    -v, --verbose        Output dettagliato
    -h, --help           Mostra questo help

MODALITÀ 1: LEGACY UPLOAD (multipart) - POST /ricevi
    JSON con campi "parametri" e/o "files":
    {
      "parametri": {"campo1": "valore1"},
      "files": {"documento": "percorso/file.pdf"},
      "auth": {"key": "chiave", "keyhash": "base_secret"}
    }

MODALITÀ 2: COMANDI (JSON RPC) - POST /api/command
    JSON con campo "comando":
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "nome_script"}

MODALITÀ 3: DOWNLOAD - GET /api/download/{target}
    Usa --download TARGET [--zip] per scaricare file/cartella
    (Non richiede FILE_JSON, usa -u per URL base)

AUTENTICAZIONE:
    - Header X-API-Key: <key|kh>  (o Authorization: Bearer <key|kh>)
    - "auth.keyhash" nel JSON è il segreto base (NON hash). Client calcola _kh = SHA256(keyhash + giorno_corrente)
    - Opzioni CLI (-k/-kh) sovrascrivono "auth" nel JSON

ESEMPI:
    # Legacy upload
    python ntwebsrv_client.py upload.json -k "mia_chiave" -v
    
    # Comandi
    python ntwebsrv_client.py cmd_save.json -k "mia_chiave" -v
    python ntwebsrv_client.py cmd_exit.json -kh "mio_base_secret"
    
    # Download
    python ntwebsrv_client.py --download report.pdf -k "mia_chiave"
    python ntwebsrv_client.py --download logs --zip -k "mia_chiave"
""",
    "en": """
ntwebsrv_client.py - Client for ntwebsrv (Automation Agent)

USAGE:
    python ntwebsrv_client.py JSON_FILE [options]

ARGUMENTS:
    JSON_FILE            JSON file with data/command to send (required)

OPTIONS:
    -u, --url URL        Base server URL (default: http://localhost:8000)
    -k, --key KEY        Secret key for auth (X-API-Key header)
    -kh, --keyhash BASE  Base secret for _kh (SHA256(base + day))
    -t, --timeout SEC    Request timeout in seconds (default: 30)
    -v, --verbose        Verbose output
    -h, --help           Show this help

MODE 1: LEGACY UPLOAD (multipart) - POST /ricevi
    JSON with "parametri" and/or "files":
    {
      "parametri": {"field1": "value1"},
      "files": {"document": "path/file.pdf"},
      "auth": {"key": "secret", "keyhash": "base_secret"}
    }

MODE 2: COMMANDS (JSON RPC) - POST /api/command
    JSON with "comando" field:
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "script_name"}

MODE 3: DOWNLOAD - GET /api/download/{target}
    Use --download TARGET [--zip] to download file/folder
    (Does not require JSON_FILE, uses -u for base URL)

AUTHENTICATION:
    - Header X-API-Key: <key|kh>  (or Authorization: Bearer <key|kh>)
    - "auth.keyhash" in JSON is base secret (NOT hash). Client calculates _kh = SHA256(keyhash + current_day)
    - CLI options (-k/-kh) override JSON "auth"

EXAMPLES:
    # Legacy upload
    python ntwebsrv_client.py upload.json -k "my_key" -v
    
    # Commands
    python ntwebsrv_client.py cmd_save.json -k "my_key" -v
    python ntwebsrv_client.py cmd_exit.json -kh "my_base_secret"
    
    # Download
    python ntwebsrv_client.py --download report.pdf -k "my_key"
    python ntwebsrv_client.py --download logs --zip -k "my_key"
"""
}


def print_help():
    print(HELP_TEXT[LANG])


def load_json_file(filepath: str) -> Tuple[Optional[Dict], str]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f), ""
    except json.JSONDecodeError as e:
        return None, f"JSON non valido: {e}"
    except Exception as e:
        return None, f"Errore lettura file: {e}"


def verify_files(files_dict: Dict[str, str]) -> Tuple[List[Tuple[str, str]], List[str]]:
    missing = []
    verified = []
    for field, path in files_dict.items():
        p = Path(path).expanduser().resolve()
        if p.is_file():
            verified.append((field, str(p)))
        else:
            missing.append(f"{field}: {path}")
    return verified, missing


def calc_kh(base_secret: str) -> str:
    """Calcola _kh = SHA256(base_secret + giorno_corrente)"""
    today_day = str(datetime.now().day)
    return hashlib.sha256((base_secret + today_day).encode()).hexdigest()


def get_auth_headers(key: str, kh_base: str) -> Dict[str, str]:
    """Genera header di autenticazione"""
    headers = {}
    if kh_base:
        headers["X-API-Key"] = calc_kh(kh_base)
    elif key:
        headers["X-API-Key"] = key
    return headers


def send_multipart(url: str, form_data: Dict, files: Dict, headers: Dict, timeout: int, verbose: bool) -> Tuple[bool, Dict, str]:
    if not requests:
        return False, {}, "Modulo 'requests' non installato (pip install requests)"
    try:
        if verbose:
            print(f"[INFO] Upload multipart a {url}")
            print(f"[INFO] Campi: {list(form_data.keys())}, File: {list(files.keys())}")
        resp = requests.post(url, data=form_data, files=files, headers=headers, timeout=timeout)
        if verbose:
            print(f"[INFO] Status: {resp.status_code}")
        try:
            result = resp.json()
        except Exception:
            result = {"raw": resp.text}
        return resp.status_code == 200, result, "" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, {}, f"Timeout ({timeout}s)"
    except requests.exceptions.ConnectionError:
        return False, {}, "Connessione fallita (server irraggiungibile)"
    except Exception as e:
        return False, {}, f"Errore: {e}"


def send_json_command(url: str, command: Dict, headers: Dict, timeout: int, verbose: bool) -> Tuple[bool, Dict, str]:
    if not requests:
        return False, {}, "Modulo 'requests' non installato (pip install requests)"
    try:
        if verbose:
            print(f"[INFO] Comando JSON a {url}: {command.get('comando')}")
        resp = requests.post(url, json=command, headers=headers, timeout=timeout)
        if verbose:
            print(f"[INFO] Status: {resp.status_code}")
        try:
            result = resp.json()
        except Exception:
            result = {"raw": resp.text}
        return resp.status_code == 200, result, "" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, {}, f"Timeout ({timeout}s)"
    except requests.exceptions.ConnectionError:
        return False, {}, "Connessione fallita (server irraggiungibile)"
    except Exception as e:
        return False, {}, f"Errore: {e}"


def download_file(url: str, headers: Dict, timeout: int, verbose: bool, output_path: Optional[str] = None) -> Tuple[bool, str, str]:
    if not requests:
        return False, "", "Modulo 'requests' non installato"
    try:
        if verbose:
            print(f"[INFO] Download da {url}")
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if verbose:
            print(f"[INFO] Status: {resp.status_code}")
        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            return False, "", f"HTTP {resp.status_code}: {err}"
        
        # Determina nome file
        filename = output_path
        if not filename:
            cd = resp.headers.get("Content-Disposition", "")
            if "filename=" in cd:
                filename = cd.split("filename=")[1].strip('"')
            else:
                filename = "download_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with open(filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True, filename, ""
    except requests.exceptions.Timeout:
        return False, "", f"Timeout ({timeout}s)"
    except requests.exceptions.ConnectionError:
        return False, "", "Connessione fallita (server irraggiungibile)"
    except Exception as e:
        return False, "", f"Errore: {e}"


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("json_file", nargs="?")
    parser.add_argument("-u", "--url", default="http://localhost:8000")
    parser.add_argument("-k", "--key", default="")
    parser.add_argument("-kh", "--keyhash", default="")
    parser.add_argument("-t", "--timeout", type=int, default=30)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    # Download mode
    parser.add_argument("--download", dest="download_target", default="")
    parser.add_argument("--zip", dest="zip_mode", action="store_true")
    parser.add_argument("-o", "--output", dest="output_file", default="")
    args = parser.parse_args()

    if args.help:
        print_help()
        return 0

    base_url = args.url.rstrip("/")
    headers = get_auth_headers(args.key, args.keyhash)
    if not headers and not args.download_target:
        print("AVVISO: Nessuna autenticazione specificata (-k o -kh)")

    # DOWNLOAD MODE
    if args.download_target:
        target = args.download_target
        download_url = f"{base_url}/api/download/{target}"
        if args.zip_mode:
            download_url += "?zip_mode=true"
        success, filename, err = download_file(download_url, headers, args.timeout, args.verbose, args.output_file)
        if success:
            print(f"SUCCESSO: Scaricato come {filename}")
            return 0
        else:
            print(f"FALLITO: {err}")
            return 1

    # REQUIRE JSON FILE for other modes
    if not args.json_file:
        print_help()
        print("ERRORE: FILE_JSON richiesto (usa --download per scaricare senza JSON)")
        return 1

    data, err = load_json_file(args.json_file)
    if err:
        print(f"ERRORE: {err}")
        return 1

    # Detect mode: if has "comando" -> JSON RPC, else -> Legacy multipart
    is_command_mode = "comando" in data

    if is_command_mode:
        # COMMAND MODE: POST /api/command
        command_url = f"{base_url}/api/command"
        success, result, err = send_json_command(command_url, data, headers, args.timeout, args.verbose)
        if success:
            print("SUCCESSO:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        else:
            print(f"FALLITO: {err}")
            if result:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1
    else:
        # LEGACY MODE: POST /ricevi (multipart)
        if not data.get("parametri") and not data.get("files"):
            print("ERRORE: JSON deve contenere almeno 'parametri' o 'files' (o 'comando' per modalità comando)")
            return 1
        
        files_dict = data.get("files", {})
        verified, missing = verify_files(files_dict)
        if missing:
            print("ERRORE: File mancanti:")
            for m in missing:
                print(f"  - {m}")
            return 1
        if verified:
            print(f"[OK] {len(verified)} file verificati")
        
        # Build multipart
        form_data = {}
        files = {}
        parametri = data.get("parametri", {})
        auth = data.get("auth", {})
        key = args.key or auth.get("key", "")
        kh_base = args.keyhash or auth.get("keyhash", "")
        
        for k, v in parametri.items():
            form_data[k] = v
        if key and not kh_base:
            form_data["_k"] = key
        if kh_base:
            form_data["_kh"] = calc_kh(kh_base)
        
        for field, path in files_dict.items():
            p = Path(path)
            files[field] = (p.name, open(p, 'rb'), 'application/octet-stream')
        
        legacy_url = f"{base_url}/ricevi"
        success, result, err = send_multipart(legacy_url, form_data, files, headers, args.timeout, args.verbose)
        for f in files.values():
            f[1].close()
        
        if success:
            print("SUCCESSO:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        else:
            print(f"FALLITO: {err}")
            if result:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1


if __name__ == "__main__":
    sys.exit(main())