#!/usr/bin/env python3
"""
ntwebsrv.py - Agente di Automazione Sicuro (RPC/Command-and-Control)
Autore: ntwebserv project
Versione: 2.1
Richiede: Python 3.10+, aiSys.py nella stessa cartella

Cross-platform: Windows & Linux
"""

import os
import sys
import json
import uuid
import hashlib
import argparse
import locale
import signal
import subprocess
import shutil
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

try:
    import magic
except ImportError:
    magic = None

from fastapi import FastAPI, Request, HTTPException, Depends, Form, File, UploadFile, BackgroundTasks, Security, Header
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))
from aiSys import acLog, Timestamp, Config, ConfigDefault, ExpandDict, read_array_file, save_array_file

DEFAULT_LOG_NAME = "ntwebsrv.log"

# Platform detection
IS_WINDOWS = platform.system().lower() == "windows"
IS_LINUX = platform.system().lower() == "linux"

log = acLog()
app = FastAPI(title="ntwebsrv - Automation Agent")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

config_data: Dict[str, Any] = {}
users_data: List[Dict[str, Any]] = []
json_dir: Path
files_dir: Path
download_dir: Path
allowed_scripts: Dict[str, List[str]] = {}


def detect_language() -> str:
    try:
        lang, _ = locale.getdefaultlocale()
        return "it" if lang and lang.startswith("it") else "en"
    except Exception:
        return "en"


LANG = detect_language()

HELP_TEXT = {
    "it": """
ntwebsrv.py - Agente di Automazione Sicuro (RPC/Command-and-Control)

USO:
    python ntwebsrv.py -c CONFIG_FILE [opzioni]

OPZIONI:
    -c, --config FILE    File di configurazione (OBBLIGATORIO)
    -h, --help           Mostra questo help

CONFIGURAZIONE (parametri.json):
    {
      "config": {
        "path_dest": "percorso/cartella/dati",        # OBBLIGATORIO
        "path_log": "nome_file.log",                  # Opzionale (default: ntwebsrv.log)
        "host": "0.0.0.0",                            # Opzionale (default: 0.0.0.0)
        "port": 8000,                                 # Opzionale (default: 8000)
        "max_file_size_mb": 50,                       # Opzionale (default: 50)
        "download_dir": "condivisi",                  # Opzionale (cartella per download/get)
        "allowed_scripts": {                          # Opzionale (whitelist per exec)
          "backup_db": ["bash", "/opt/scripts/backup.sh"],
          "status_docker": ["docker", "ps"]
        }
      },
      "users": [
        {
          "mail": "user@domain.com",                  # OBBLIGATORIO
          "name": "Nome Utente",                      # OBBLIGATORIO
          "key": "chiave_segreta",                    # Opzionale (se presente, deve essere unica)
          "keyhash": "base_secret_per_utente"         # OBBLIGATORIO (deve essere unica per ogni utente)
        }
      ]
    }

AUTENTICAZIONE:
    Il client deve inviare UNO tra:
    - Header X-API-Key: <key> (chiave segreta in chiaro, solo se utente ha 'key')
    - Header X-API-Key: <kh>  (SHA256(keyhash + giorno_mese_corrente) es. SHA256("base_secret" + "8"))
    - Header Authorization: Bearer <key|kh>
    
    Se l'utente non ha 'key' valorizzata, accetta SOLO _kh.
    key e keyhash identificano univocamente l'utente: devono essere uniche tra tutti gli utenti.

ENDPOINT:
    POST /ricevi           - Riceve parametri e file (multipart/form-data) - LEGACY
    POST /api/command      - Esegue comandi (JSON) - NUOVO
    GET  /api/download/... - Scarica file/cartella zip - NUOVO
    Rate limit: 1 req/30s per IP, max 100/ora per IP

COMANDI (inviare come JSON a POST /api/command):
    {"comando": "save", "payload": {...}}           - Salva dati JSON
    {"comando": "exit"}                             - Termina server
    {"comando": "restart"}                          - Riavvia server
    {"comando": "reboot"}                           - Riavvia PC host
    {"comando": "poweroff"}                         - Spegne PC host
    {"comando": "exec", "target": "nome_script"}    - Esegue script whitelist

DOWNLOAD (GET /api/download/{target}?zip_mode=true):
    - target: nome file o cartella in download_dir
    - zip_mode=true: zippa cartella al volo

ESEMPIO AVVIO:
    python ntwebsrv.py -c parametri.json
""",
    "en": """
ntwebsrv.py - Secure Automation Agent (RPC/Command-and-Control)

USAGE:
    python ntwebsrv.py -c CONFIG_FILE [options]

OPTIONS:
    -c, --config FILE    Configuration file (REQUIRED)
    -h, --help           Show this help

CONFIGURATION (parametri.json):
    {
      "config": {
        "path_dest": "path/to/data/folder",           # REQUIRED
        "path_log": "log_file.log",                   # Optional (default: ntwebsrv.log)
        "host": "0.0.0.0",                            # Optional (default: 0.0.0.0)
        "port": 8000,                                 # Optional (default: 8000)
        "max_file_size_mb": 50,                       # Optional (default: 50)
        "download_dir": "shared",                     # Optional (folder for download/get)
        "allowed_scripts": {                          # Optional (whitelist for exec)
          "backup_db": ["bash", "/opt/scripts/backup.sh"],
          "status_docker": ["docker", "ps"]
        }
      },
      "users": [
        {
          "mail": "user@domain.com",                  # REQUIRED
          "name": "User Name",                        # REQUIRED
          "key": "secret_key",                        # Optional (if present, must be unique)
          "keyhash": "base_secret_per_user"           # REQUIRED (must be unique per user)
        }
      ]
    }

AUTHENTICATION:
    Client must send ONE of:
    - Header X-API-Key: <key> (secret key in clear, only if user has 'key')
    - Header X-API-Key: <kh>  (SHA256(keyhash + current_day_of_month) e.g. SHA256("base_secret" + "8"))
    - Header Authorization: Bearer <key|kh>
    
    If user has no 'key', ONLY _kh is accepted.
    key and keyhash uniquely identify the user: must be unique across all users.

ENDPOINTS:
    POST /ricevi           - Receives parameters and files (multipart/form-data) - LEGACY
    POST /api/command      - Executes commands (JSON) - NEW
    GET  /api/download/... - Downloads file/folder zip - NEW
    Rate limit: 1 req/30s per IP, max 100/hour per IP

COMMANDS (send as JSON to POST /api/command):
    {"comando": "save", "payload": {...}}           - Save JSON data
    {"comando": "exit"}                             - Terminate server
    {"comando": "restart"}                          - Restart server
    {"comando": "reboot"}                           - Reboot host PC
    {"comando": "poweroff"}                         - Poweroff host PC
    {"comando": "exec", "target": "script_name"}    - Execute whitelisted script

DOWNLOAD (GET /api/download/{target}?zip_mode=true):
    - target: file or folder name in download_dir
    - zip_mode=true: zip folder on-the-fly

EXAMPLE START:
    python ntwebsrv.py -c parametri.json
"""
}


def print_help():
    print(HELP_TEXT[LANG])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CommandPayload(BaseModel):
    comando: str = Field(..., description="Comando da eseguire: save, exit, restart, reboot, poweroff, exec")
    target: Optional[str] = Field(None, description="Target per exec (nome script) o get")
    payload: Optional[Dict[str, Any]] = Field(None, description="Payload JSON per save")


# ============================================================================
# CROSS-PLATFORM SYSTEM OPERATIONS
# ============================================================================

def get_temp_dir() -> Path:
    """Restituisce la directory temporanea cross-platform."""
    if IS_WINDOWS:
        temp = os.environ.get("TEMP") or os.environ.get("TMP") or "C:\\Windows\\Temp"
        return Path(temp)
    return Path("/tmp")


def terminate_process(pid: int) -> None:
    """Termina un processo in modo cross-platform."""
    if IS_WINDOWS:
        # Su Windows usa taskkill
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        # Su Linux/Unix usa SIGTERM
        os.kill(pid, signal.SIGTERM)


def restart_server() -> None:
    """Riavvia il server in modo cross-platform."""
    # os.execv funziona su entrambi, ma su Windows l'eseguibile è python.exe
    executable = sys.executable
    args = [executable] + sys.argv
    if IS_WINDOWS:
        # Su Windows passa attraverso cmd per gestire correttamente i path
        os.execv(executable, args)
    else:
        os.execv(executable, args)


def reboot_host() -> None:
    """Riavvia l'host in modo cross-platform."""
    if IS_WINDOWS:
        # Windows: shutdown.exe /r /t 0 (riavvio immediato)
        cmd = ["shutdown.exe", "/r", "/t", "0", "/f"]
    else:
        # Linux: systemctl reboot (preferito) o sudo reboot
        # Prova prima systemctl (non richiede sudo se l'utente ha i permessi)
        cmd = ["systemctl", "reboot"]
        # Fallback a sudo reboot se systemctl non disponibile
        try:
            subprocess.run(["which", "systemctl"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            cmd = ["sudo", "reboot"]
    subprocess.run(cmd, check=False, capture_output=True, timeout=30)


def poweroff_host() -> None:
    """Spegne l'host in modo cross-platform."""
    if IS_WINDOWS:
        # Windows: shutdown.exe /s /t 0 (spegnimento immediato)
        cmd = ["shutdown.exe", "/s", "/t", "0", "/f"]
    else:
        # Linux: systemctl poweroff
        cmd = ["systemctl", "poweroff"]
        try:
            subprocess.run(["which", "systemctl"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            cmd = ["sudo", "poweroff"]
    subprocess.run(cmd, check=False, capture_output=True, timeout=30)


# ============================================================================
# SYSTEM COMMANDS (Background Tasks)
# ============================================================================

def esegui_exit():
    log.Log1("Comando exit ricevuto: terminazione server")
    terminate_process(os.getpid())


def esegui_restart():
    log.Log1("Comando restart ricevuto: riavvio server")
    restart_server()


def esegui_reboot_poweroff(azione: str):
    log.Log1(f"Comando {azione} ricevuto: esecuzione su host")
    try:
        if azione == "reboot":
            reboot_host()
        else:
            poweroff_host()
    except subprocess.TimeoutExpired:
        log.Log0(f"Timeout comando {azione}")
    except Exception as e:
        log.Log0(f"Errore comando {azione}: {e}")


# ============================================================================
# CONFIG LOADING
# ============================================================================

def load_config(config_path: str) -> tuple[str, bool]:
    global config_data, users_data, json_dir, files_dir, download_dir, allowed_scripts
    sProc = "load_config"
    try:
        if not os.path.isfile(config_path):
            return f"{sProc}: File configurazione non trovato: {config_path}", False
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        config_data = data.get("config", {})
        users_data = data.get("users", [])
        if not config_data.get("path_dest"):
            return f"{sProc}: 'config.path_dest' obbligatorio", False
        if not users_data:
            return f"{sProc}: Almeno un utente in 'users' è obbligatorio", False
        
        # Validate uniqueness of key and keyhash
        seen_keys = set()
        seen_keyhashes = set()
        for i, user in enumerate(users_data):
            mail = user.get("mail", "").strip()
            name = user.get("name", "").strip()
            key = user.get("key", "").strip()
            keyhash = user.get("keyhash", "").strip()
            
            if not mail:
                return f"{sProc}: Utente {i}: 'mail' obbligatoria", False
            if not name:
                return f"{sProc}: Utente {i}: 'name' obbligatorio", False
            if not keyhash:
                return f"{sProc}: Utente {i}: 'keyhash' obbligatorio", False
            if keyhash in seen_keyhashes:
                return f"{sProc}: 'keyhash' duplicato per utente {i} (deve essere univoco)", False
            seen_keyhashes.add(keyhash)
            
            if key:
                if key in seen_keys:
                    return f"{sProc}: 'key' duplicata per utente {i} (deve essere univoca)", False
                seen_keys.add(key)
                if key in seen_keyhashes:
                    return f"{sProc}: 'key' utente {i} coincide con un 'keyhash' esistente", False
            if keyhash in seen_keys:
                return f"{sProc}: 'keyhash' utente {i} coincide con una 'key' esistente", False
        
        path_dest = Path(config_data["path_dest"]).expanduser().resolve()
        json_dir = path_dest / "json"
        files_dir = path_dest / "files"
        json_dir.mkdir(parents=True, exist_ok=True)
        files_dir.mkdir(parents=True, exist_ok=True)
        
        # Download directory (for get command)
        download_dir_name = config_data.get("download_dir", "condivisi")
        download_dir = (path_dest / download_dir_name).resolve()
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Allowed scripts whitelist (for exec command)
        allowed_scripts = config_data.get("allowed_scripts", {})
        if allowed_scripts:
            log.Log1(f"Script whitelist caricati: {list(allowed_scripts.keys())}")
        
        ConfigDefault(config_data, "path_log", DEFAULT_LOG_NAME)
        ConfigDefault(config_data, "host", "0.0.0.0")
        ConfigDefault(config_data, "port", 8000)
        ConfigDefault(config_data, "max_file_size_mb", 50)
        log_path = config_data["path_log"]
        if not os.path.isabs(log_path):
            log_path = str(path_dest / log_path)
        log.Start(log_path, str(path_dest))
        log.Log1(f"Avvio ntwebsrv - Config: {config_path}")
        log.Log1(f"Cartella dati: {path_dest}")
        log.Log1(f"Cartella download: {download_dir}")
        log.Log1(f"Sistema: {platform.system()} {platform.release()}")
        log.Log1(f"Utenti configurati: {len(users_data)}")
        return "", True
    except json.JSONDecodeError as e:
        return f"{sProc}: JSON non valido: {e}", False
    except Exception as e:
        return f"{sProc}: {e}", False


# ============================================================================
# AUTHENTICATION
# ============================================================================

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_token(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Verifica autenticazione da:
    - Header X-API-Key: <key|kh>
    - Header Authorization: Bearer <key|kh>
    """
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()
    
    if not token:
        raise HTTPException(status_code=401, detail="Autenticazione richiesta: header X-API-Key o Authorization: Bearer")
    
    today_day = str(datetime.now().day)
    
    for user in users_data:
        user_key = user.get("key", "").strip()
        user_keyhash = user.get("keyhash", "").strip()
        
        # Check _k (clear key)
        if user_key and token == user_key:
            return user
        
        # Check _kh (SHA256(keyhash + day))
        if user_keyhash:
            expected = hashlib.sha256((user_keyhash + today_day).encode()).hexdigest()
            if token.lower() == expected.lower():
                return user
    
    raise HTTPException(status_code=401, detail="Token non valido o scaduto")


# ============================================================================
# ENDPOINTS
# ============================================================================

# Legacy endpoint (multipart/form-data) - mantiene compatibilità
@app.post("/ricevi")
@limiter.limit("1/30second;100/hour")
async def ricevi_dati(request: Request):
    sProc = "ricevi_dati"
    client_ip = request.client.host if request.client else "unknown"
    log.Log1(f"Richiesta legacy da {client_ip}")
    try:
        form = await request.form()
    except Exception as e:
        log.Log0(f"{sProc}: Payload non valido", str(e))
        raise HTTPException(status_code=400, detail="Payload non valido, atteso multipart/form-data")
    
    # Auth from form data (_k or _kh)
    form_dict = {}
    for key, value in form.multi_items():
        if hasattr(value, "filename") and value.filename:
            form_dict[key] = f"[FILE:{value.filename}]"
        else:
            form_dict[key] = value
    
    k = form_dict.get("_k", "").strip()
    kh = form_dict.get("_kh", "").strip()
    today_day = str(datetime.now().day)
    
    user = None
    for u in users_data:
        user_key = u.get("key", "").strip()
        user_keyhash = u.get("keyhash", "").strip()
        if k and user_key and k == user_key:
            user = u
            break
        if kh and user_keyhash:
            expected = hashlib.sha256((user_keyhash + today_day).encode()).hexdigest()
            if kh.lower() == expected.lower():
                user = u
                break
    
    if not user:
        log.Log0(f"{sProc}: Auth fallita da {client_ip}", "_k/_kh mancanti o non validi")
        raise HTTPException(status_code=401, detail="Autenticazione fallita: _k o _kh non validi")
    
    log.Log1(f"Autenticato (legacy): {user.get('mail', 'sconosciuto')}")
    max_size = config_data.get("max_file_size_mb", 50) * 1024 * 1024
    parametri = {}
    metadati_file = []
    for key, value in form.multi_items():
        if hasattr(value, "filename") and value.filename:
            content = await value.read()
            if len(content) > max_size:
                raise HTTPException(status_code=400, detail=f"File troppo grande: max {max_size//1024//1024}MB")
            mime_reale = "application/octet-stream"
            if magic:
                try:
                    mime_reale = magic.from_buffer(content, mime=True)
                except Exception:
                    pass
            safe_name = f"{uuid.uuid4().hex}_{value.filename}"
            file_path = files_dir / safe_name
            with open(file_path, "wb") as f:
                f.write(content)
            metadati_file.append({
                "campo_form": key,
                "nome_originale": value.filename,
                "nome_salvato": safe_name,
                "mime_reale": mime_reale,
                "dimensione_byte": len(content),
                "percorso": str(file_path)
            })
        else:
            parametri[key] = value
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = uuid.uuid4().hex[:8]
    json_name = f"{prefix}_{timestamp_str}.json"
    json_path = json_dir / json_name
    payload = {
        "metadata_richiesta": {
            "timestamp": datetime.now().isoformat(),
            "ip_client": client_ip,
            "metodo": request.method,
            "utente_autenticato": user.get("mail", "")
        },
        "parametri": parametri,
        "files_allegati": metadati_file
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)
    log.Log1(f"Salvato (legacy): {json_name} ({len(metadati_file)} file, {len(parametri)} parametri)")
    return {
        "status": "success",
        "messaggio": "Dati elaborati e salvati correttamente",
        "dettagli_salvataggio": {
            "file_json": json_name,
            "files_ricevuti": len(metadati_file),
            "parametri_ricevuti": len(parametri)
        }
    }


# NEW: Command endpoint (JSON RPC style)
@app.post("/api/command")
@limiter.limit("1/30second;100/hour")
async def api_command(
    request: CommandPayload,
    bg_tasks: BackgroundTasks,
    user: Dict = Depends(verify_token)
):
    sProc = "api_command"
    cmd = request.comando.lower().strip()
    log.Log1(f"Comando API '{cmd}' da {user.get('mail', 'sconosciuto')}")
    
    if cmd == "save":
        if not request.payload:
            raise HTTPException(status_code=400, detail="Manca il payload JSON per 'save'")
        # Save JSON payload to file
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = uuid.uuid4().hex[:8]
        json_name = f"{prefix}_{timestamp_str}_cmd_save.json"
        json_path = json_dir / json_name
        payload = {
            "metadata_richiesta": {
                "timestamp": datetime.now().isoformat(),
                "comando": "save",
                "utente_autenticato": user.get("mail", "")
            },
            "payload": request.payload
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        log.Log1(f"Save comando: {json_name}")
        return {"status": "ok", "msg": "Dati salvati", "file": json_name}
    
    elif cmd == "exit":
        bg_tasks.add_task(esegui_exit)
        return {"status": "ok", "msg": "Server in fase di spegnimento..."}
    
    elif cmd == "restart":
        bg_tasks.add_task(esegui_restart)
        return {"status": "ok", "msg": "Riavvio del servizio in corso..."}
    
    elif cmd == "reboot":
        bg_tasks.add_task(esegui_reboot_poweroff, "reboot")
        return {"status": "ok", "msg": "Sistema host in riavvio..."}
    
    elif cmd == "poweroff":
        bg_tasks.add_task(esegui_reboot_poweroff, "poweroff")
        return {"status": "ok", "msg": "Sistema host in spegnimento..."}
    
    elif cmd == "exec":
        task_name = request.target
        if not task_name:
            raise HTTPException(status_code=400, detail="Manca 'target' per exec (nome script)")
        if task_name not in allowed_scripts:
            raise HTTPException(status_code=403, detail=f"Task '{task_name}' non consentito o inesistente. Disponibili: {list(allowed_scripts.keys())}")
        
        script_cmd = allowed_scripts[task_name]
        log.Log1(f"Esecuzione script whitelist: {task_name} -> {script_cmd}")
        
        try:
            processo = subprocess.run(
                script_cmd,
                capture_output=True,
                text=True,
                timeout=config_data.get("exec_timeout_sec", 60)
            )
            return {
                "status": "ok",
                "task": task_name,
                "return_code": processo.returncode,
                "stdout": processo.stdout.strip(),
                "stderr": processo.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"Script '{task_name}' timeout")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore esecuzione script: {e}")
    
    else:
        raise HTTPException(status_code=400, detail=f"Comando '{cmd}' sconosciuto. Comandi validi: save, exit, restart, reboot, poweroff, exec")


# NEW: Download endpoint (GET file/folder)
@app.get("/api/download/{target}")
@limiter.limit("1/30second;100/hour")
async def api_download(
    target: str,
    zip_mode: bool = False,
    user: Dict = Depends(verify_token)
):
    sProc = "api_download"
    log.Log1(f"Download '{target}' (zip={zip_mode}) da {user.get('mail', 'sconosciuto')}")
    
    # Security: resolve path and prevent path traversal
    target_path = (download_dir / target).resolve()
    
    if not str(target_path).startswith(str(download_dir)):
        log.Log0(f"{sProc}: Path traversal attempt", target)
        raise HTTPException(status_code=403, detail="Accesso fuori dalla directory consentita")
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File o cartella non trovata")
    
    # Zip mode: create zip on-the-fly
    if zip_mode:
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="zip_mode=true richiede una directory come target")
        
        temp_dir = get_temp_dir()
        zip_base = temp_dir / f"{target}_export_{uuid.uuid4().hex[:8]}"
        try:
            zip_file = shutil.make_archive(str(zip_base), 'zip', target_path)
            return FileResponse(
                path=zip_file,
                filename=f"{target}.zip",
                media_type='application/zip'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore creazione zip: {e}")
    
    # Single file
    if target_path.is_file():
        return FileResponse(
            path=target_path,
            filename=target_path.name
        )
    else:
        raise HTTPException(status_code=400, detail="Il target è una directory. Usa ?zip_mode=true per scaricarla come zip")


# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "service": "ntwebsrv", 
        "version": "2.1",
        "platform": platform.system()
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-c", "--config", required=True)
    parser.add_argument("-h", "--help", action="store_true")
    args, _ = parser.parse_known_args()
    if args.help:
        print_help()
        return 0
    err, ok = load_config(args.config)
    if not ok:
        print(f"ERRORE: {err}")
        return 1
    log.Log1(f"Server in ascolto su {config_data['host']}:{config_data['port']}")
    uvicorn.run(app, host=config_data["host"], port=config_data["port"], log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())