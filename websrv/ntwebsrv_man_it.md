# ntwebsrv - Manuale Utente (Italiano)

## 1. Introduzione

**ntwebsrv** è un **agente di automazione sicuro** (RPC/Command-and-Control) sviluppato in Python con FastAPI. Riceve comandi e chiamate API da client esterni con regole di sicurezza avanzate: autenticazione key/hash, rate limiting per IP, whitelist comandi, validazione sicura file upload.

### Caratteristiche principali
- **3 endpoint**: `/ricevi` (legacy), `/api/command` (comandi JSON), `/api/download` (file)
- **6 comandi**: save, exit, restart, reboot, poweroff, exec (whitelist)
- **Download sicuro**: file/cartella con zip on-the-fly, protezione path traversal
- **Autenticazione doppia**: chiave segreta (`_k`) o hash giornaliero (`_kh`)
- **Rate limiting**: 1 req/30s per IP, max 100/ora per IP
- **BackgroundTasks**: exit/restart/reboot/poweroff rispondono prima di agire
- **Logging completo** con timestamp via `aiSys.py`
- **Help bilingue** (italiano/inglese) per sistema locale

---

## 2. Requisiti

- **Python 3.10+**
- **Dipendenze** (`requirements.txt`):
  ```
  fastapi
  uvicorn[standard]
  python-multipart
  slowapi
  python-magic          # Linux/macOS
  python-magic-bin      # Windows
  pydantic
  requests              # Solo per client Python
  ```
- **Modulo interno**: `aiSys.py` (stessa cartella)

### Installazione ambiente
```bash
python -m venv env
# Windows
env\Scripts\activate
# Linux/macOS
source env/bin/activate

pip install -r requirements.txt
```

---

## 3. Configurazione (parametri.json)

Il file **deve essere specificato** con `-c` all'avvio (nessun default).

### Struttura completa
```json
{
  "config": {
    "path_dest": "G:/dati/ricezioni",        // OBBLIGATORIO
    "path_log": "ntwebsrv.log",              // Opzionale
    "host": "0.0.0.0",                       // Opzionale
    "port": 8000,                            // Opzionale
    "max_file_size_mb": 50,                  // Opzionale
    "download_dir": "condivisi",             // Opzionale (cartella download)
    "exec_timeout_sec": 60,                  // Opzionale (timeout exec)
    "allowed_scripts": {                     // Opzionale (whitelist exec)
      "backup_db": ["bash", "/opt/scripts/backup.sh"],
      "pulisci_log": ["bash", "/opt/scripts/clean_logs.sh"],
      "status_docker": ["docker", "ps"],
      "system_info": ["bash", "-c", "uptime && df -h && free -m"]
    }
  },
  "users": [
    {
      "mail": "user@domain.com",             // OBBLIGATORIO
      "name": "Nome Utente",                 // OBBLIGATORIO
      "key": "chiave_segreta",               // Opzionale (univoca se presente)
      "keyhash": "base_secret_univoco"       // OBBLIGATORIO (univoco per utente)
    }
  ]
}
```

### Sezione `config`

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `path_dest` | *(obbligatorio)* | Cartella base per `json/` e `files/` |
| `path_log` | `ntwebsrv.log` | File di log (relativo a `path_dest` o assoluto) |
| `host` | `0.0.0.0` | Interfaccia di ascolto |
| `port` | `8000` | Porta TCP |
| `max_file_size_mb` | `50` | Limite dimensione singoli file upload |
| `download_dir` | `condivisi` | Sottocartella in `path_dest` per download/get |
| `exec_timeout_sec` | `60` | Timeout esecuzione script (secondi) |
| `allowed_scripts` | `{}` | Whitelist per comando `exec` |

### Sezione `users`

Array di oggetti utente. Campi:

| Campo | Obbligatorio | Descrizione |
|-------|--------------|-------------|
| `mail` | **Sì** | Email univoca (audit/log) |
| `name` | **Sì** | Nome descrittivo |
| `key` | No | Chiave segreta per `_k` (se presente, **deve essere univoca**) |
| `keyhash` | **Sì** | Segreto base per `_kh` (**deve essere univoco per utente**) |

#### Regole di Unicità (CRITICHE)
- **`keyhash`**: Sempre obbligatoria, **univoca** per ogni utente (non può coincidere con altri `keyhash` né con nessuna `key`)
- **`key`**: Opzionale, ma **se presente deve essere univoca** (non può coincidere con altre `key` né con nessun `keyhash`)
- Queste regole garantiscono che `_k` e `_kh` identifichino **univocamente** un singolo utente

#### Calcolo `_kh` (lato client)
```
SHA256(keyhash + giorno_mese_corrente)
```
`giorno_mese_corrente` = giorno del mese (1-31) **senza zeri iniziali**.

**Esempio** (giorno 8, `keyhash = "mio_base_secret"`):
```
_kh = SHA256("mio_base_secret8")
```

> **Nota**: Server ricalcola hash con proprio orologio locale. Client e server devono avere data sincronizzata (NTP).

#### Utenti senza `key`
Se `key` vuota/assente → autenticazione **solo** con `_kh`. Permette distribuire solo `keyhash` (canale sicuro) senza esporre chiave master.

---

## 4. Avvio del Server

```bash
# Help (lingua automatica)
python ntwebsrv.py -h

# Avvio standard (config OBBLIGATORIA)
python ntwebsrv.py -c parametri.json

# Config personalizzato
python ntwebsrv.py -c /percorso/parametri.json
```

### Output avvio tipico
```
20261108:143022:INFO: Avvio ntwebsrv - Config: parametri.json
20261108:143022:INFO: Cartella dati: G:\dati\ricezioni
20261108:143022:INFO: Cartella download: G:\dati\ricezioni\condivisi
20261108:143022:INFO: Utenti configurati: 2
20261108:143022:INFO: Server in ascolto su 0.0.0.0:8000
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 5. Endpoint API

### 5.1 `POST /ricevi` (Legacy - multipart/form-data)
Mantiene compatibilità con client esistenti.

**Parametri form-data:**
- Campi testuali illimitati → salvati in `parametri`
- File illimitati → salvati su disco, metadati in `files_allegati`
- **Autenticazione**: inviare **uno** tra `_k` o `_kh` come campi form

**Risposta Successo (200):**
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

### 5.2 `POST /api/command` (Nuovo - JSON RPC) ⭐
Endpoint principale per automazione. **Content-Type: application/json**

**Autenticazione**: Header `X-API-Key` o `Authorization: Bearer` con `<key|kh>`

#### Comandi supportati

| Comando | JSON | Descrizione |
|---------|------|-------------|
| **save** | `{"comando": "save", "payload": {...}}` | Salva payload JSON su file |
| **exit** | `{"comando": "exit"}` | Termina server (background) |
| **restart** | `{"comando": "restart"}` | Riavvia server (background) |
| **reboot** | `{"comando": "reboot"}` | Riavvia PC host (background, sudo) |
| **poweroff** | `{"comando": "poweroff"}` | Spegne PC host (background, sudo) |
| **exec** | `{"comando": "exec", "target": "nome_script"}` | Esegue script whitelist |

#### Dettaglio comandi

**save** - Salva dati strutturati
```json
{"comando": "save", "payload": {"sensore": "temp1", "valore": 23.5, "unita": "C"}}
```
Crea file `json/{uuid}_{timestamp}_cmd_save.json` con metadata + payload.

**exit** - Termina processo server
```json
{"comando": "exit"}
```
Usa `BackgroundTasks` → risponde `200 OK` poi invia `SIGTERM`.

**restart** - Riavvia server
```json
{"comando": "restart"}
```
Usa `BackgroundTasks` → risponde `200 OK` poi `os.execv()`.

**reboot / poweroff** - Controllo host
```json
{"comando": "reboot"}
{"comando": "poweroff"}
```
Usa `BackgroundTasks` → risponde `200 OK` poi `sudo reboot` / `sudo poweroff`.

> **⚠️ Prerequisito sudo**: L'utente che esegue lo script deve avere in `/etc/sudoers`:
> ```
> tuo_utente ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff
> ```
> Altrimenti il comando resta in attesa password in background.

**exec** - Esegue script whitelist
```json
{"comando": "exec", "target": "backup_db"}
```
- `target` deve esistere in `config.allowed_scripts`
- Esecuzione bloccante con timeout (`exec_timeout_sec`, default 60s)
- Restituisce: `return_code`, `stdout`, `stderr`
- **Sicurezza**: Solo script in whitelist. No shell injection.

#### Risposta Successo (200)
```json
{
  "status": "ok",
  "msg": "Dati salvati",
  "file": "a1b2c3d4_20261108_143022_cmd_save.json"
}
```
Per `exec`:
```json
{
  "status": "ok",
  "task": "backup_db",
  "return_code": 0,
  "stdout": "Backup completato",
  "stderr": ""
}
```

#### Codici Errore
| Codice | Significato |
|--------|-------------|
| 400 | JSON non valido / payload mancante / comando sconosciuto |
| 401 | Autenticazione fallita (token mancante/non valido) |
| 403 | Task `exec` non in whitelist |
| 429 | Rate limit superato |
| 500 | Errore interno / timeout script |
| 504 | Timeout esecuzione script |

---

### 5.3 `GET /api/download/{target}` (Nuovo - Download) ⭐

Scarica file o cartella dalla `download_dir` (configurabile).

**URL:** `/api/download/{target}?zip_mode=true`

**Parametri:**
- `target`: nome file o cartella in `download_dir`
- `zip_mode=true`: zippa cartella al volo (richiede directory)

**Autenticazione**: Header `X-API-Key` o `Authorization: Bearer`

**Protezione Path Traversal:**
- Risolve percorso assoluto: `(download_dir / target).resolve()`
- Verifica: `str(target_path).startswith(str(download_dir))`
- Blocca accessi fuori directory consentita

**Esempi curl:**
```bash
# File singolo
curl -O -J -H "X-API-Key: mia_chiave" \
  http://localhost:8000/api/download/report.pdf

# Cartella come zip
curl -O -J -H "X-API-Key: mia_chiave" \
  "http://localhost:8000/api/download/logs?zip_mode=true"
```

**Risposte:**
- File: `FileResponse` con nome originale
- Cartella + `zip_mode=true`: stream zip generato in `/tmp/`
- Errori: 403 (path traversal), 404 (non trovato), 400 (dir senza zip_mode)

---

### 5.4 `GET /health`
Health check semplice:
```json
{"status": "ok", "service": "ntwebsrv", "version": "2.0"}
```

---

## 6. Struttura Salvataggio Dati

```
path_dest/
├── json/                    # File JSON richieste
│   ├── {uuid8}_{YYYYMMDD_HHMMSS}.json           # Legacy /ricevi
│   └── {uuid8}_{YYYYMMDD_HHMMSS}_cmd_save.json  # Comando save
├── files/                   # File allegati legacy
│   └── {uuid}_{nome_originale}.ext
└── condivisi/               # Download directory (configurabile)
    ├── report.pdf
    └── logs/
```

### Formato file JSON (legacy /ricevi)
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

### Formato file JSON (comando save)
```json
{
  "metadata_richiesta": {
    "timestamp": "2026-11-08T14:30:22.123456",
    "comando": "save",
    "utente_autenticato": "admin@azienda.it"
  },
  "payload": {"sensore": "temp1", "valore": 23.5}
}
```

---

## 7. Sicurezza Implementata

### Autenticazione
- Verifica `_k` contro `users[].key` (match esatto)
- Verifica `_kh` ricalcolando `SHA256(keyhash + giorno_corrente)`
- Header `X-API-Key` o `Authorization: Bearer`
- Fallimento → HTTP 401, log `ERR`

### Rate Limiting (SlowAPI)
- Finestra scorrevole per IP (`get_remote_address`)
- Limiti: `1/30second; 100/hour`
- Memoria in-process (non condiviso tra worker)

### Whitelist Comandi (exec)
- Solo script in `config.allowed_scripts`
- Esecuzione via lista argomenti (no shell)
- Timeout configurabile

### Path Traversal Protection (download)
- `resolve()` + verifica prefisso `download_dir`
- Blocca `../` e symlink fuori directory

### Upload File (Legacy)
- MIME type reale via `python-magic`
- Rinominazione UUID
- Limite dimensione
- Cartella `files/` isolata

### BackgroundTasks per System Commands
- `exit`, `restart`, `reboot`, `poweroff` → task in background
- Risposta `200 OK` immediata → poi azione
- Evita errori connessione interrotta su client

### Logging (aiSys.acLog)
- Timestamp: `AAAAMMGG:HHMMSS:TIPO`
- Livelli: `INFO`, `ERR`, `WARN`
- Output: console + file
- Eventi: avvio, richieste, auth, comandi, download, errori, rate limit

---

## 8. Client Disponibili

| Client | Linguaggio | Modalità supportate |
|--------|------------|---------------------|
| `ntwebsrv_client.py` | Python 3.10+ | Legacy, Comandi, Download |
| `ntwebsrv_client.sh` | Bash (curl/jq) | Legacy, Comandi, Download |
| `ntwebsrv_client.ps1` | PowerShell 5.1+ | Legacy, Comandi, Download |
| `ntwebsrv_client.java` | Java 11+ (HttpClient+Gson) | Legacy, Comandi, Download |
| `ntwebsrv_client.bas` | VBA/Access (WinHttp) | Legacy, Comandi, Download |

Tutti i client:
- Calcolano `_kh = SHA256(keyhash + giorno)` automaticamente
- Supportano `-k` (key) e `-kh` (keyhash base)
- Modalità download con `--download` / `-Download`
- Help bilingue (italiano/inglese)

---

## 9. Esempi Pratici

### Generare `_kh` per test
```python
import hashlib
from datetime import datetime

keyhash = "mio_base_secret_univoco"
day = str(datetime.now().day)  # es. "8"
kh = hashlib.sha256((keyhash + day).encode()).hexdigest()
print(f"_kh={kh}")
```

### Test rapido con curl

**Legacy upload:**
```bash
curl -X POST http://localhost:8000/ricevi \
  -F "_k=K7x9mP2qR4" \
  -F "campo1=valore1" \
  -F "documento=@/percorso/file.pdf"
```

**Comando save:**
```bash
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: K7x9mP2qR4" \
  -H "Content-Type: application/json" \
  -d '{"comando": "save", "payload": {"temp": 25.5}}'
```

**Comando exit:**
```bash
curl -X POST http://localhost:8000/api/command \
  -H "X-API-Key: K7x9mP2qR4" \
  -H "Content-Type: application/json" \
  -d '{"comando": "exit"}'
```

**Comando exec (whitelist):**
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

**Download cartella zip:**
```bash
curl -O -J -H "X-API-Key: K7x9mP2qR4" \
  "http://localhost:8000/api/download/logs?zip_mode=true"
```

**Verifica rate limit:**
```bash
for i in {1..5}; do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/command -H "X-API-Key: K7x9mP2qR4" -H "Content-Type: application/json" -d '{"comando": "save", "payload": {}}'; done
# Output: 200, 429, 429, 429, 429
```

### Configurazione sudo per reboot/poweroff
```bash
# /etc/sudoers (visudo)
tuo_utente ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff
```

---

## 10. Risoluzione Problemi

| Problema | Causa | Soluzione |
|----------|-------|-----------|
| `ModuleNotFoundError: magic` | python-magic non installato | `pip install python-magic-bin` (Win) / `python-magic` (Linux) |
| `ModuleNotFoundError: pydantic` | pydantic non installato | `pip install pydantic` |
| `401 Unauthorized` | Key/hash errati o giorno diverso | Verificare `key`/`keyhash` in `parametri.json`, sincronizzare orologio (NTP) |
| `403 Forbidden` su exec | Task non in whitelist | Aggiungere task a `config.allowed_scripts` |
| `403 Forbidden` su download | Path traversal rilevato | Verificare target in `download_dir` |
| `429 Too Many Requests` | Rate limit superato | Attendere 30s o configurare limiti diversi |
| `500/504` su exec | Script timeout o errore | Aumentare `exec_timeout_sec`, controllare script |
| File non salvati | Permessi `path_dest` | Verificare scrittura su `path_dest/json`, `files`, `condivisi` |
| `parametri.json` non trovato | Opzione `-c` mancante | Usare `-c /percorso/completo/parametri.json` |
| Errore unicità key/keyhash | Valori duplicati in users | Correggere `parametri.json`: key e keyhash univoci |
| Reboot/poweroff non funziona | sudo richiede password | Configurare NOPASSWD in `/etc/sudoers` |

---

## 11. Limitazioni Note

1. **Single worker**: Rate limiting in memoria non condiviso con `gunicorn -w N`
2. **HTTPS**: Uvicorn non termina TLS; usare reverse proxy (Nginx/Caddy) in produzione
3. **Persistenza rate limit**: Riavvio azzera contatori
4. **Orologio**: `_kh` dipende da data locale server; usare NTP
5. **Config obbligatoria**: `-c` sempre richiesto all'avvio
6. **sudo NOPASSWD**: Necessario per reboot/poweroff su Linux
7. **Whitelist exec**: Solo script predefiniti; no comandi arbitrari

---

## 12. File del Progetto

```
ntwebsrv/
├── ntwebsrv.py              # Server principale (Agente Automazione)
├── ntwebsrv_client.py       # Client Python (3 modalità)
├── ntwebsrv_client.sh       # Client Bash
├── ntwebsrv_client.ps1      # Client PowerShell
├── ntwebsrv_client.java     # Client Java
├── ntwebsrv_client.bas      # Client VBA/Access
├── aiSys.py                 # Modulo logging/timestamp (interno)
├── parametri.json           # Configurazione (da creare, nessun default)
├── prompt_ntwebserv.md      # Documentazione tecnica
├── ntwebsrv_man_it.md       # Questo manuale
├── ntwebsrv_man_en.md       # Manuale inglese
├── README.MD                # Panoramica rapida
└── requirements.txt         # Dipendenze Python
```

---

## 13. Licenza e Autori

Progetto **ntwebserv** - Agente di automazione sicuro per RPC/Command-and-Control.
Modulo di logging `aiSys.py` derivato da aiJobsOS2.