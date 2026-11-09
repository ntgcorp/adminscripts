# ntwebsrv - User Manual (English)

## 1. Introduction

**ntwebsrv** is a **secure automation agent** (RPC/Command-and-Control) developed in Python with FastAPI. It receives commands and API calls from external clients with advanced security rules: key/hash authentication, IP-based rate limiting, command whitelist, secure file upload validation.

### Key Features
- **3 endpoints**: `/ricevi` (legacy), `/api/command` (JSON commands), `/api/download` (files)
- **6 commands**: save, exit, restart, reboot, poweroff, exec (whitelist)
- **Secure download**: files/folders with on-the-fly zip, path traversal protection
- **Dual authentication**: secret key (`_k`) or daily hash (`_kh`)
- **Rate limiting**: 1 req/30s per IP, max 100/hour per IP
- **BackgroundTasks**: exit/restart/reboot/poweroff respond before acting
- **Complete logging** with timestamps via `aiSys.py`
- **Bilingual help** (Italian/English) based on system locale

---

## 2. Requirements

- **Python 3.10+**
- **Dependencies** (`requirements.txt`):
  ```
  fastapi
  uvicorn[standard]
  python-multipart
  slowapi
  python-magic          # Linux/macOS
  python-magic-bin      # Windows
  pydantic
  requests              # Only for Python client
  ```
- **Internal module**: `aiSys.py` (same folder)

### Environment Setup
```bash
python -m venv env
# Windows
env\Scripts\activate
# Linux/macOS
source env/bin/activate

pip install -r requirements.txt
```

---

## 3. Configuration (parametri.json)

The configuration file **must be specified** with `-c` at startup (no default).

### Complete Structure
```json
{
  "config": {
    "path_dest": "G:/data/receptions",       // REQUIRED
    "path_log": "ntwebsrv.log",              // Optional
    "host": "0.0.0.0",                       // Optional
    "port": 8000,                            // Optional
    "max_file_size_mb": 50,                  // Optional
    "download_dir": "shared",                // Optional (download folder)
    "exec_timeout_sec": 60,                  // Optional (exec timeout)
    "allowed_scripts": {                     // Optional (exec whitelist)
      "backup_db": ["bash", "/opt/scripts/backup.sh"],
      "clean_logs": ["bash", "/opt/scripts/clean_logs.sh"],
      "status_docker": ["docker", "ps"],
      "system_info": ["bash", "-c", "uptime && df -h && free -m"]
    }
  },
  "users": [
    {
      "mail": "user@domain.com",             // REQUIRED
      "name": "User Name",                   // REQUIRED
      "key": "secret_key",                   // Optional (must be unique if present)
      "keyhash": "base_secret_unique"        // REQUIRED (must be unique per user)
    }
  ]
}
```

### `config` Section

| Parameter | Default | Description |
|-----------|---------|-------------|
| `path_dest` | *(required)* | Base folder for `json/` and `files/` |
| `path_log` | `ntwebsrv.log` | Log file (relative to `path_dest` or absolute) |
| `host` | `0.0.0.0` | Listening interface |
| `port` | `8000` | TCP port |
| `max_file_size_mb` | `50` | Max single file upload size |
| `download_dir` | `shared` | Subfolder in `path_dest` for download/get |
| `exec_timeout_sec` | `60` | Script execution timeout (seconds) |
| `allowed_scripts` | `{}` | Whitelist for `exec` command |

### `users` Section

Array of user objects. Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `mail` | **Yes** | Unique email (audit/log) |
| `name` | **Yes** | Descriptive name |
| `key` | No | Secret key for `_k` (if present, **must be unique**) |
| `keyhash` | **Yes** | Base secret for `_kh` (**must be unique per user**) |

#### Uniqueness Rules (CRITICAL)
- **`keyhash`**: Always required, **unique** for each user (cannot match any other `keyhash` or any `key`)
- **`key`**: Optional, but **if present must be unique** (cannot match any other `key` or any `keyhash`)
- These rules ensure `_k` and `_kh` **uniquely identify** a single user

#### Calculating `_kh` (client-side)
```
SHA256(keyhash + current_day_of_month)
```
`current_day_of_month` = day number (1-31) **without leading zeros**.

**Example** (day = 8, `keyhash = "my_base_secret"`):
```
_kh = SHA256("my_base_secret8")
```

> **Note**: Server recalculates hash using its own local clock. Client and server must have synchronized date (use NTP).

#### Users without `key`
If `key` is empty/absent → authentication **only** with `_kh`. Allows distributing only `keyhash` (secure channel) without exposing master key.

---

## 4. Starting the Server

```bash
# Help (auto language)
python ntwebsrv.py -h

# Standard start (config REQUIRED)
python ntwebsrv.py -c parametri.json

# Custom config
python ntwebsrv.py -c /path/parametri.json
```

### Typical Startup Output
```
20261108:143022:INFO: Avvio ntwebsrv - Config: parametri.json
20261108:143022:INFO: Cartella dati: G:\dati\ricezioni
20261108:143022:INFO: Cartella download: G:\dati\ricezioni\condivisi
20261108:143022:INFO: Utenti configurati: 2
20261108:143022:INFO: Server in ascolto su 0.0.0.0:8000
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 5. API Endpoints

### 5.1 `POST /ricevi` (Legacy - multipart/form-data)
Maintains compatibility with existing clients.

**Form-data parameters:**
- Unlimited text fields → saved in `parametri`
- Unlimited files → saved to disk, metadata in `files_allegati`
- **Authentication**: send **one** of `_k` or `_kh` as form fields

**Success Response (200):**
```json
{
  "status": "success",
  "messaggio": "Dati elaborati e salvati correttamente",
  "dettagli_salvataggio": {
    "file_json": "a1b2c3d4_20261108_143022.json",
    "files_ricevuti": 2,
    "parametri_ricevuti": 5
  }
}
```

---

### 5.2 `POST /api/command` (New - JSON RPC) ⭐
Main endpoint for automation. **Content-Type: application/json**

**Authentication**: Header `X-API-Key` or `Authorization: Bearer` with `<key|kh>`

#### Supported Commands

| Command | JSON | Description |
|---------|------|-------------|
| **save** | `{"comando": "save", "payload": {...}}` | Save payload JSON to file |
| **exit** | `{"comando": "exit"}` | Terminate server (background) |
| **restart** | `{"comando": "restart"}` | Restart server (background) |
| **reboot** | `{"comando": "reboot"}` | Reboot host PC (background, sudo) |
| **poweroff** | `{"comando": "poweroff"}` | Poweroff host PC (background, sudo) |
| **exec** | `{"comando": "exec", "target": "script_name"}` | Execute whitelisted script |

#### Command Details

**save** - Save structured data
```json
{"comando": "save", "payload": {"sensor": "temp1", "value": 25.5, "unit": "C"}}
```
Creates `json/{uuid}_{timestamp}_cmd_save.json` with metadata + payload.

**exit** - Terminate server process
```json
{"comando": "exit"}
```
Uses `BackgroundTasks` → responds `200 OK` then sends `SIGTERM`.

**restart** - Restart server
```json
{"comando": "restart"}
```
Uses `BackgroundTasks` → responds `200 OK` then `os.execv()`.

**reboot / poweroff** - Host control
```json
{"comando": "reboot"}
{"comando": "poweroff"}
```
Uses `BackgroundTasks` → responds `200 OK` then `sudo reboot` / `sudo poweroff`.

> **⚠️ Sudo Prerequisite**: User running script must have in `/etc/sudoers`:
> ```
> your_user ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff
> ```
> Otherwise command waits for password in background.

**exec** - Execute whitelisted script
```json
{"comando": "exec", "target": "backup_db"}
```
- `target` must exist in `config.allowed_scripts`
- Blocking execution with timeout (`exec_timeout_sec`, default 60s)
- Returns: `return_code`, `stdout`, `stderr`
- **Security**: Only scripts in whitelist. No shell injection.

#### Success Response (200)
```json
{
  "status": "ok",
  "msg": "Dati salvati",
  "file": "a1b2c3d4_20261108_143022_cmd_save.json"
}
```
For `exec`:
```json
{
  "status": "ok",
  "task": "backup_db",
  "return_code": 0,
  "stdout": "Backup completed",
  "stderr": ""
}
```

#### Error Codes
| Code | Meaning |
|------|---------|
| 400 | Invalid JSON / missing payload / unknown command |
| 401 | Authentication failed (missing/invalid token) |
| 403 | `exec` task not in whitelist |
| 429 | Rate limit exceeded |
| 500 | Internal error / script timeout |
| 504 | Script execution timeout |

---

### 5.3 `GET /api/download/{target}` (New - Download) ⭐

Downloads file or folder from `download_dir` (configurable).

**URL:** `/api/download/{target}?zip_mode=true`

**Parameters:**
- `target`: file or folder name in `download_dir`
- `zip_mode=true`: zip folder on-the-fly (requires directory)

**Authentication**: Header `X-API-Key` or `Authorization: Bearer`

**Path Traversal Protection:**
- Resolves absolute path: `(download_dir / target).resolve()`
- Verifies: `str(target_path).startswith(str(download_dir))`
- Blocks access outside allowed directory

**curl Examples:**
```bash
# Single file
curl -O -J -H "X-API-Key: my_key" \
  http://localhost:8000/api/download/report.pdf

# Folder as zip
curl -O -J -H "X-API-Key: my_key" \
  "http://localhost:8000/api/download/logs?zip_mode=true"
```

**Responses:**
- File: `FileResponse` with original name
- Folder + `zip_mode=true`: streaming zip from `/tmp/`
- Errors: 403 (path traversal), 404 (not found), 400 (dir without zip_mode)

---

### 5.4 `GET /health`
Simple health check:
```json
{"status": "ok", "service": "ntwebsrv", "version": "2.0"}
```

---

## 6. Data Storage Structure

```
path_dest/
├── json/                    # JSON request files
│   ├── {uuid8}_{YYYYMMDD_HHMMSS}.json           # Legacy /ricevi
│   └── {uuid8}_{YYYYMMDD_HHMMSS}_cmd_save.json  # Command save
├── files/                   # Legacy attached files
│   └── {uuid}_{original_name}.ext
└── shared/                  # Download directory (configurable)
    ├── report.pdf
    └── logs/
```

### JSON File Format (legacy /ricevi)
```json
{
  "metadata_richiesta": {
    "timestamp": "2026-11-08T14:30:22.123456",
    "ip_client": "192.168.1.100",
    "metodo": "POST",
    "utente_autenticato": "admin@azienda.it"
  },
  "parametri": {"campo1": "valore1", "_k": "K7x9mP2qR4"},
  "files_allegati": [...]
}
```

### JSON File Format (command save)
```json
{
  "metadata_richiesta": {
    "timestamp": "2026-11-08T14:30:22.123456",
    "comando": "save",
    "utente_autenticato": "admin@azienda.it"
  },
  "payload": {"sensor": "temp1", "value": 25.5}
}
```

---

## 7. Implemented Security

### Authentication
- Verifies `_k` against `users[].key` (exact match)
- Verifies `_kh` by recalculating `SHA256(keyhash + current_day)`
- Header `X-API-Key` or `Authorization: Bearer`
- Failure → HTTP 401, `ERR` log

### Rate Limiting (SlowAPI)
- Sliding window per IP (`get_remote_address`)
- Limits: `1/30second; 100/hour`
- In-process memory (not shared across workers)

### Command Whitelist (exec)
- Only scripts in `config.allowed_scripts`
- Execution via argument list (no shell)
- Configurable timeout

### Path Traversal Protection (download)
- `resolve()` + prefix check `download_dir`
- Blocks `../` and symlinks outside directory

### File Upload (Legacy)
- Real MIME type via `python-magic`
- UUID renaming
- Size limit
- Isolated `files/` folder

### BackgroundTasks for System Commands
- `exit`, `restart`, `reboot`, `poweroff` → background tasks
- Immediate `200 OK` response → then action
- Avoids connection error on client

### Logging (aiSys.acLog)
- Timestamp: `YYYYMMDD:HHMMSS:TYPE`
- Levels: `INFO`, `ERR`, `WARN`
- Output: console + file
- Events: startup, requests, auth, commands, download, errors, rate limit

---

## 8. Available Clients

| Client | Language | Modes Supported |
|--------|----------|-----------------|
| `ntwebsrv_client.py` | Python 3.10+ | Legacy, Commands, Download |
| `ntwebsrv_client.sh` | Bash (curl/jq) | Legacy, Commands, Download |
| `ntwebsrv_client.ps1` | PowerShell 5.1+ | Legacy, Commands, Download |
| `ntwebsrv_client.java` | Java 11+ (HttpClient+Gson) | Legacy, Commands, Download |
| `ntwebsrv_client.bas` | VBA/Access (WinHttp) | Legacy, Commands, Download |

All clients:
- Auto-calculate `_kh = SHA256(keyhash + day)`
- Support `-k` (key) and `-kh` (keyhash base)
- Download mode with `--download` / `-Download`
- Bilingual help (Italian/English)

---

## 9. Practical Examples

### Generate `_kh` for Testing
```python
import hashlib
from datetime import datetime

keyhash = "my_base_secret_unique"
day = str(datetime.now().day)  # e.g., "8"
kh = hashlib.sha256((keyhash + day).encode()).hexdigest()
print(f"_kh={kh}")
```

### Quick curl Tests

**Legacy upload:**
```bash
curl -X POST http://localhost:8000/ricevi \
  -F "_k=K7x9mP2qR4" \
  -F "field1=value1" \
  -F "document=@/path/file.pdf"
```

**Command save:**
```bash
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: K7x9mP2qR4" \
  -H "Content-Type: application/json" \
  -d '{"comando": "save", "payload": {"temp": 25.5}}'
```

**Command exit:**
```bash
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: K7x9mP2qR4" \
  -H "Content-Type: application/json" \
  -d '{"comando": "exit"}'
```

**Command exec (whitelist):**
```bash
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: K7x9mP2qR4" \
  -H "Content-Type: application/json" \
  -d '{"comando": "exec", "target": "status_docker"}'
```

**Download file:**
```bash
curl -O -J -H "X-API-Key: K7x9mP2qR4" \
  http://localhost:8000/api/download/report.pdf
```

**Download folder as zip:**
```bash
curl -O -J -H "X-API-Key: K7x9mP2qR4" \
  "http://localhost:8000/api/download/logs?zip_mode=true"
```

**Verify rate limit:**
```bash
for i in {1..5}; do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/command -H "X-API-Key: K7x9mP2qR4" -H "Content-Type: application/json" -d '{"comando": "save", "payload": {}}'; done
# Output: 200, 429, 429, 429, 429
```

### Sudo Configuration for reboot/poweroff
```bash
# /etc/sudoers (visudo)
your_user ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff
```

---

## 10. Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError: magic` | python-magic not installed | `pip install python-magic-bin` (Win) / `python-magic` (Linux) |
| `ModuleNotFoundError: pydantic` | pydantic not installed | `pip install pydantic` |
| `401 Unauthorized` | Wrong key/hash or day mismatch | Verify `key`/`keyhash` in `parametri.json`, sync clock (NTP) |
| `403 Forbidden` on exec | Task not in whitelist | Add task to `config.allowed_scripts` |
| `403 Forbidden` on download | Path traversal detected | Verify target in `download_dir` |
| `429 Too Many Requests` | Rate limit exceeded | Wait 30s or configure different limits |
| `500/504` on exec | Script timeout or error | Increase `exec_timeout_sec`, check script |
| Files not saved | `path_dest` permissions | Verify write access to `path_dest/json`, `files`, `shared` |
| `parametri.json` not found | Missing `-c` option | Use `-c /full/path/parametri.json` |
| Uniqueness error key/keyhash | Duplicate values in users | Fix `parametri.json`: key/keyhash must be unique |
| Reboot/poweroff fails | sudo requires password | Configure NOPASSWD in `/etc/sudoers` |

---

## 11. Known Limitations

1. **Single worker**: Rate limiting in memory not shared with `gunicorn -w N`
2. **HTTPS**: Uvicorn doesn't terminate TLS; use reverse proxy (Nginx/Caddy) in production
3. **Rate limit persistence**: Restart resets counters
4. **Clock dependency**: `_kh` depends on server local date; use NTP
5. **Config required**: `-c` must always be specified at startup
6. **sudo NOPASSWD**: Required for reboot/poweroff on Linux
7. **Exec whitelist**: Only predefined scripts; no arbitrary commands

---

## 12. Project Files

```
ntwebsrv/
├── ntwebsrv.py              # Main server (Automation Agent)
├── ntwebsrv_client.py       # Python client (3 modes)
├── ntwebsrv_client.sh       # Bash client
├── ntwebsrv_client.ps1      # PowerShell client
├── ntwebsrv_client.java     # Java client
├── ntwebsrv_client.bas      # VBA/Access client
├── aiSys.py                 # Logging/timestamp module (internal)
├── parametri.json           # Configuration (create your own, no default)
├── prompt_ntwebserv.md      # Technical documentation
├── ntwebsrv_man_it.md       # Italian manual
├── ntwebsrv_man_en.md       # This manual
├── README.MD                # Quick overview
└── requirements.txt         # Python dependencies
```

---

## 13. License and Authors

**ntwebserv** project - Secure automation agent for RPC/Command-and-Control.
Logging module `aiSys.py` derived from aiJobsOS2.