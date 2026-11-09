# ntwebsrv - Secure Automation Agent (RPC/Command-and-Control)

A Python/FastAPI automation agent for securely receiving API calls and executing commands with file uploads, featuring key/hash authentication, IP-based rate limiting, command whitelist, and automatic JSON/file storage.

**Cross-platform**: Windows 10/11, Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+), macOS

## Quick Start

```bash
# 1. Create virtual environment
python -m venv env
source env/bin/activate  # Linux/macOS
# env\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create configuration (no default - must create parametri.json)
# Edit path_dest, users with unique key/keyhash, and allowed_scripts

# 4. Start server (config REQUIRED via -c)
python ntwebsrv.py -c parametri.json
```

Server runs on `http://localhost:8000` with endpoints:
- `POST /ricevi` - Legacy multipart upload
- `POST /api/command` - JSON RPC commands (save, exit, restart, reboot, poweroff, exec)
- `GET /api/download/{target}` - File/folder download with zip
- `GET /health` - Health check

## Cross-Platform Support

| Feature | Windows | Linux | macOS |
|---------|---------|-------|-------|
| **Exit server** | `taskkill /F /PID` | `SIGTERM` | `SIGTERM` |
| **Restart server** | `os.execv` | `os.execv` | `os.execv` |
| **Reboot host** | `shutdown.exe /r /t 0 /f` | `systemctl reboot` | `sudo shutdown -r now` |
| **Poweroff host** | `shutdown.exe /s /t 0 /f` | `systemctl poweroff` | `sudo shutdown -h now` |
| **Temp directory** | `%TEMP%` / `%TMP%` | `/tmp` | `/tmp` |
| **Path handling** | `pathlib` (auto) | `pathlib` (auto) | `pathlib` (auto) |

> **Note**: On Linux/macOS, `reboot`/`poweroff` prefer `systemctl`; fallback to `sudo` requires `NOPASSWD` in `/etc/sudoers`. On Windows, run as Administrator for host power commands.

## Key Features

- **Secure authentication**: Secret key (`_k`) or daily rotating hash (`_kh = SHA256(keyhash + day)`)
- **Rate limiting**: 1 request/30s per IP, 100/hour per IP
- **Command whitelist**: `exec` only runs predefined scripts (no shell injection)
- **Path traversal protection**: Download restricted to configured directory
- **Background system commands**: exit/restart/reboot/poweroff respond before acting
- **File upload safety**: MIME validation via magic numbers, UUID renaming, size limits
- **Automatic storage**: Each request saved as JSON + files in configured directory
- **Full logging**: Timestamped logs via `aiSys.py` (console + file)
- **Multi-language**: Help in Italian/English based on system locale
- **Unique identification**: `key` and `keyhash` uniquely identify each user (enforced uniqueness)

## Commands (POST /api/command)

| Command | JSON | Description |
|---------|------|-------------|
| `save` | `{"comando": "save", "payload": {...}}` | Save JSON payload to file |
| `exit` | `{"comando": "exit"}` | Terminate server |
| `restart` | `{"comando": "restart"}` | Restart server |
| `reboot` | `{"comando": "reboot"}` | Reboot host PC (requires sudo NOPASSWD) |
| `poweroff` | `{"comando": "poweroff"}` | Poweroff host PC (requires sudo NOPASSWD) |
| `exec` | `{"comando": "exec", "target": "script_name"}` | Execute whitelisted script |

## Clients Included

| Client | Language | Modes | Use Case |
|--------|----------|-------|----------|
| `ntwebsrv_client.py` | Python 3.10+ | Legacy, Command, Download | Full-featured, verifies local files |
| `ntwebsrv_client.sh` | Bash | Legacy, Command, Download | Lightweight, uses `curl` + `jq` |
| `ntwebsrv_client.ps1` | PowerShell 5.1+ | Legacy, Command, Download | Native Windows, no external deps |
| `ntwebsrv_client.java` | Java 11+ | Legacy, Command, Download | Cross-platform, HttpClient + Gson |
| `ntwebsrv_client.bas` | VBA/Access | Legacy, Command, Download | MS Access / Office automation |

All clients support:
- Auto-calculation of `_kh = SHA256(keyhash + day_of_month)`
- Both `-k` (key) and `-kh` (keyhash base) authentication
- Download mode (`--download` / `-Download`)
- Bilingual help (Italian/English)

## Documentation

- **[Italian Manual](ntwebsrv_man_it.md)** - Complete guide in Italian
- **[English Manual](ntwebsrv_man_en.md)** - Complete guide in English
- **[Technical Specs](prompt_ntwebserv.md)** - Architecture & API reference

## Package Files Overview

```
ntwebsrv/
├── Server
│   ├── ntwebsrv.py              # Main FastAPI automation agent
│   ├── aiSys.py                 # Internal logging/timestamp/config module
│   └── parametri.json           # Configuration (create your own, no default)
│
├── Clients
│   ├── ntwebsrv_client.py       # Python client (requests)
│   ├── ntwebsrv_client.sh       # Bash client (curl + jq + sha256sum)
│   ├── ntwebsrv_client.ps1      # PowerShell client (Invoke-RestMethod)
│   ├── ntwebsrv_client.java     # Java client (HttpClient + Gson)
│   └── ntwebsrv_client.bas      # VBA/Access module (WinHttp + CryptoAPI)
│
├── Documentation
│   ├── prompt_ntwebserv.md      # Technical reference
│   ├── ntwebsrv_man_it.md       # Italian manual
│   ├── ntwebsrv_man_en.md       # English manual
│   └── README.MD                # This file
│
├── Config Example
│   └── parametri.json           # Example with unique key/keyhash & allowed_scripts
│
└── Requirements
    ├── requirements.txt         # Python dependencies
    └── (Java: Gson library)     # For Java client
```

## Configuration Example

```json
{
  "config": {
    "path_dest": "./data",
    "path_log": "ntwebsrv.log",
    "host": "0.0.0.0",
    "port": 8000,
    "max_file_size_mb": 100,
    "download_dir": "condivisi",
    "exec_timeout_sec": 60,
    "allowed_scripts": {
      "backup_db": ["bash", "/opt/scripts/backup.sh"],
      "clean_logs": ["bash", "/opt/scripts/clean_logs.sh"],
      "status_docker": ["docker", "ps"],
      "system_info": ["bash", "-c", "uptime && df -h && free -m"]
    }
  },
  "users": [
    {
      "mail": "admin@example.com",
      "name": "Administrator",
      "key": "MySecretKey123",
      "keyhash": "admin_base_secret_unique_1"
    },
    {
      "mail": "partner@example.com",
      "name": "Partner Client",
      "key": "",
      "keyhash": "partner_base_secret_unique_2"
    }
  ]
}
```

**Critical**: `keyhash` is always required and must be unique per user. `key` is optional but if present must be unique (cannot match any other `key` or `keyhash`).

## Client Usage Examples

### Python
```bash
# Legacy upload
python ntwebsrv_client.py upload.json -k "MySecretKey123" -v

# JSON RPC command
python ntwebsrv_client.py cmd_save.json -k "MySecretKey123" -v
python ntwebsrv_client.py cmd_exit.json -kh "admin_base_secret_unique_1"

# Download
python ntwebsrv_client.py --download report.pdf -k "MySecretKey123"
python ntwebsrv_client.py --download logs --zip -k "MySecretKey123"
```

### Bash
```bash
# Legacy upload
./ntwebsrv_client.sh upload.json -k "MySecretKey123" -v

# JSON RPC command
./ntwebsrv_client.sh cmd_save.json -k "MySecretKey123" -v
./ntwebsrv_client.sh cmd_exit.json -kh "admin_base_secret_unique_1"

# Download
./ntwebsrv_client.sh --download report.pdf -k "MySecretKey123"
./ntwebsrv_client.sh --download logs --zip -k "MySecretKey123"
```

### PowerShell
```powershell
# Legacy upload
.\ntwebsrv_client.ps1 -JsonFile upload.json -Key "MySecretKey123" -Verbose

# JSON RPC command
.\ntwebsrv_client.ps1 -JsonFile cmd_save.json -Key "MySecretKey123" -Verbose
.\ntwebsrv_client.ps1 -JsonFile cmd_exit.json -KeyHash "admin_base_secret_unique_1"

# Download
.\ntwebsrv_client.ps1 -Download "report.pdf" -Key "MySecretKey123"
.\ntwebsrv_client.ps1 -Download "logs" -Zip -Key "MySecretKey123"
```

### Java
```bash
# Compile (requires gson-2.10.1.jar in classpath)
javac -cp gson-2.10.1.jar ntwebsrv_client.java

# Legacy upload
java -cp .:gson-2.10.1.jar ntwebsrv_client upload.json -k "MySecretKey123" -v

# JSON RPC command
java -cp .:gson-2.10.1.jar ntwebsrv_client cmd_save.json -k "MySecretKey123" -v
java -cp .:gson-2.10.1.jar ntwebsrv_client cmd_exit.json -kh "admin_base_secret_unique_1"

# Download
java -cp .:gson-2.10.1.jar ntwebsrv_client --download report.pdf -k "MySecretKey123"
java -cp .:gson-2.10.1.jar ntwebsrv_client --download logs --zip -k "MySecretKey123"
```

### VBA / Access
```vba
' Import ntwebsrv_client.bas into your VBA project
' Legacy upload
ok = ntwebsrv_SendJson("C:\path\upload.json", "http://localhost:8000", "MySecretKey123")

' JSON RPC command
ok = ntwebsrv_SendCommand("C:\path\cmd_exit.json", "http://localhost:8000", , "admin_base_secret_unique_1")

' Download file
ok = ntwebsrv_Download("report.pdf", "http://localhost:8000", "C:\downloads\report.pdf", False, , "admin_base_secret_unique_1")

' Download folder as zip
ok = ntwebsrv_Download("logs", "http://localhost:8000", "C:\downloads\logs.zip", True, , "admin_base_secret_unique_1")
```

## Test with curl

### Legacy Upload (multipart)
```bash
curl -X POST http://localhost:8000/ricevi \
  -F "_k=MySecretKey123" \
  -F "field1=value1" \
  -F "document=@./test.pdf"
```

### JSON RPC Commands
```bash
# Save
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: MySecretKey123" \
  -H "Content-Type: application/json" \
  -d '{"comando": "save", "payload": {"temp": 25.5}}'

# Exit
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: MySecretKey123" \
  -H "Content-Type: application/json" \
  -d '{"comando": "exit"}'

# Exec (whitelisted script)
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: MySecretKey123" \
  -H "Content-Type: application/json" \
  -d '{"comando": "exec", "target": "status_docker"}'
```

### Download
```bash
# File
curl -O -J -H "X-API-Key: MySecretKey123" \
  http://localhost:8000/api/download/report.pdf

# Folder as zip
curl -O -J -H "X-API-Key: MySecretKey123" \
  "http://localhost:8000/api/download/logs?zip_mode=true"
```

### Generate `_kh` for Daily Auth
```python
import hashlib, datetime
keyhash = "admin_base_secret_unique_1"
day = str(datetime.datetime.now().day)
print(hashlib.sha256((keyhash + day).encode()).hexdigest())
```

## Requirements

### Server (Python)
- Python 3.10+
- `python-magic-bin` (Windows) or `python-magic` (Linux/macOS) - auto-installed via platform markers
- See `requirements.txt` for full list

### Clients
| Client | Requirements |
|--------|--------------|
| Python | `requests` library |
| Bash | `curl`, `jq` (optional), `sha256sum` or `shasum` |
| PowerShell | Windows 7+ / PowerShell 5.1+ (built-in) |
| Java | Java 11+, Gson library (`gson-2.10.1.jar`) |
| VBA | MS Access 2010+, `WinHttp.WinHttpRequest.5.1`, Windows CryptoAPI |

### Host Commands (reboot/poweroff)
| OS | Requirement |
|----|-------------|
| Windows | Run as Administrator |
| Linux | `systemctl` (preferred) or `sudo NOPASSWD: /sbin/reboot, /sbin/poweroff` |
| macOS | `sudo shutdown` (requires admin) |

## License

Internal project - ntwebserv