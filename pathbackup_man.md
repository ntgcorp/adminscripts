# pathbackup User Manual

## Overview

**pathbackup** is a cross-platform Python backup utility that reads INI configuration files and creates compressed archives using one of three compression engines:

- **7Z** (7-Zip) — Fast, high compression ratio. Requires 7-Zip installed.
- **TAR** (TAR.GZ) — Unix standard, maximum gzip compression. Requires `tar` and `gzip`.
- **ZIP** — Native Python `zipfile` module. No external dependencies.

Supported platforms: **Windows** and **Linux**.

---

## Quick Start

### Single INI file
```bash
python path_backup.py backup_config.ini
```

### Multiple INI files (later files override earlier entries)
```bash
python path_backup.py base.ini override.ini
```

### Command Syntax
```bash
python path_backup.py <ini_file1> [<ini_file2> ...]
```

All parameters are read from the INI file(s) — no command-line arguments for paths or sections.

---

## Configuration File (INI)

### Section `[CONFIG]` — Global Settings

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `ENGINE` | No | `7Z` | Compression engine: `7Z`, `TAR`, or `ZIP` |
| `EXIT_ON_ERROR` | No | `false` | `true` = abort on first fatal error; `false` = continue processing |
| `PATH_DEST` | **Yes** | — | Output directory for archives (must exist) |
| `SECTIONS` | No | All sections | Comma-separated list of sections to process (uppercased) |
| `MODE` | No | `TOTAL` | `TOTAL` (full backup) or `INCREMENTAL` |
| `SUBDIRS` | No | `false` | `true` = include subdirectories (ZIP engine only) |

### Other Sections — Backup Entries

Each section (except `[CONFIG]`) defines a group of files/folders to archive. Each line is `KEY=VALUE` where:
- **KEY** = entry name (used in archive filename)
- **VALUE** = source path (file, folder, or wildcard pattern)

```ini
[MENSILE]
DATABASE="K:\Data\database.accdb"
LOGS="K:\Logs\*.log"
FOLDER="K:\Projects\MyApp"
```

#### Supported Path Formats
- Absolute paths: `K:\Data\file.txt` (Windows) or `/home/user/data/file.txt` (Linux)
- Wildcards: `*.accdb`, `*.*`, `DB_*.MDB`
- Quoted paths with spaces: `"K:\My Data\file.txt"`
- HTML `<br>` tags auto-converted to newlines

---

## Example Configurations

### Basic Configuration (`backup.ini`)
```ini
[CONFIG]
ENGINE=7Z
EXIT_ON_ERROR=false
PATH_DEST=K:\_BACKUP\
SECTIONS=MENSILE

[MENSILE]
DB_MAIN="K:\Database\main.accdb"
LOGS="K:\Logs\*.log"
```

### ZIP Engine with Subdirectories
```ini
[CONFIG]
ENGINE=ZIP
EXIT_ON_ERROR=false
PATH_DEST=K:\_BACKUP\
SUBDIRS=TRUE
SECTIONS=PROJECTS

[PROJECTS]
MYAPP="K:\Projects\MyApp"
```

### Multiple INI Files — Layered Config
**base.ini**
```ini
[CONFIG]
ENGINE=7Z
PATH_DEST=K:\_BACKUP\
EXIT_ON_ERROR=false

[COMMON]
SHARED="K:\Shared\config.ini"
```

**override.ini** (merges with base, entries override)
```ini
[CONFIG]
SECTIONS=MENSILE

[MENSILE]
DB="K:\Database\prod.accdb"
```

Run: `python path_backup.py base.ini override.ini`

---

## Archive Naming

Each entry creates a separate archive in a daily subfolder:

```
{OUTPUT_ROOT}\{YYYYMMDD}\{ENTRY_NAME}_{YYYYMMDDHHMM}.{EXT}
```

| Engine | Extension |
|--------|-----------|
| 7Z     | `.7z`     |
| TAR    | `.tar.gz` |
| ZIP    | `.zip`    |

**Example:** `DATABASE_202609011430.7z`

---

## Logging

### Console Output
Real-time progress: section, entry, source, archive path, command, result.

### Log File
Daily log at:
```
{OUTPUT_ROOT}\{YYYYMMDD}\backup_log.log
```

Contains:
- Timestamp
- Configuration summary (OS, engine, INI files, mode)
- Each entry processed
- Command executed
- Return codes
- Stdout/stderr from compression tools
- Errors and exceptions
- Final summary

---

## Compression Engines

### 7Z Engine (Default)
- **Windows:** Searches `C:\Program Files\7-Zip\7z.exe`, then `PATH`
- **Linux:** Uses `7z` from `PATH` (install `p7zip-full`)
- **Command:** `7z a -t7z OUTPUT.7z SOURCE`
- **Return codes:** `0`=success, `1`=warnings, `2+`=fatal error

### TAR Engine
- **Linux:** Native `tar` + `gzip` (default)
- **Windows:** Requires WSL, Git Bash, or Cygwin
- **Command:** `tar -czf OUTPUT.tar.gz SOURCE`
- **Compression:** Maximum gzip level (9)

### ZIP Engine
- **Cross-platform:** Native Python `zipfile` module
- **Compression:** `ZIP_DEFLATED` (maximum)
- **Error handling:** Files that fail (locked, permissions) are logged individually; backup continues
- **SUBDIRS:** `true` = recursive (`os.walk`); `false` = top-level only

---

## Dependencies

| Engine | Windows | Linux |
|--------|---------|-------|
| 7Z     | [7-Zip](https://www.7-zip.org/) | `sudo apt install p7zip-full` |
| TAR    | WSL / Git Bash / Cygwin | Native (`tar`, `gzip`) |
| ZIP    | Built-in Python | Built-in Python |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Fatal error (missing INI, missing PATH_DEST, engine not found, etc.) |

With `EXIT_ON_ERROR=true`, any entry failure aborts with code 1.

---

## Cross-Platform Notes

| Aspect | Windows | Linux |
|--------|---------|-------|
| Path separator | `\` | `/` |
| INI paths | `K:\Data\...` | `/mnt/data/...` or `/home/...` |
| TAR engine | Not native (use 7Z or ZIP) | Native |
| 7Z engine | Install 7-Zip | Install `p7zip-full` |
| ZIP engine | Native Python | Native Python |

**Recommendation:** Use **7Z on Windows**, **TAR on Linux**, **ZIP for maximum portability**.

---

## Complete Example

### File: `backup_config.ini`
```ini
; ============================================================
; Global Configuration
; ============================================================
[CONFIG]
; Exit on first fatal error (true/false)
EXIT_ON_ERROR=false

; Compression engine: 7Z, TAR, ZIP
ENGINE=7Z

; Output directory (MUST EXIST)
PATH_DEST=K:\_BACKUP\

; Sections to process (comma-separated, optional)
SECTIONS=MENSILE,SETTIMANALE

; Backup mode: TOTAL or INCREMENTAL
MODE=TOTAL

; Include subdirectories (ZIP engine only)
SUBDIRS=false

; ============================================================
; Monthly Backups
; ============================================================
[MENSILE]
DATABASE="K:\Database\main.accdb"
LOGS="K:\Logs\*.log"
CONFIG="K:\Config\settings.ini"

; ============================================================
; Weekly Backups
; ============================================================
[SETTIMANALE]
PROJECTS="K:\Projects\MyApp"
DOCS="K:\Documents\*.pdf"
```

### Run
```bash
python path_backup.py backup_config.ini
```

### Output Structure
```
K:\_BACKUP\
└── 20260901\
    ├── backup_log.log
    ├── DATABASE_202609011430.7z
    ├── LOGS_202609011430.7z
    ├── CONFIG_202609011430.7z
    ├── PROJECTS_202609011431.7z
    └── DOCS_202609011431.7z
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `7z not found` | Install 7-Zip (Windows) or `p7zip-full` (Linux) |
| `tar or gzip not found` | Use WSL/Git Bash on Windows; TAR is native on Linux |
| `PATH_DEST not specified` | Add `PATH_DEST` to `[CONFIG]` section |
| `PATH_DEST directory not found` | Ensure output directory exists |
| `[CONFIG] section not found` | Add `[CONFIG]` section to INI |
| Files locked/in use | Use ZIP engine (logs failures per-file, continues) |
| Wildcards not working | Ensure engine supports them (7Z, TAR pass to tool; ZIP expands via `os.walk`) |

---

## Python Environment

Default interpreter path (Windows):
```
C:\Applic\PythonX64\myenv\Scripts\python.exe
```

Add to PATH or use full path:
```cmd
C:\Applic\PythonX64\myenv\Scripts\python.exe path_backup.py backup.ini
```

---

## License

MIT License — Free to use, modify, and distribute.