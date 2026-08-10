This suite consists of system administration scripts for backup/restore, disk imaging, Google Drive mounting, Windows display management, and Python-based automation tools. Designed for Live Linux environments (such as GParted Live) and Windows systems.

Official documentation and updates: [http://ntgcorp.it/admin_scripts](https://github.com/ntgcorp/admin_scripts/)

---

## 💾 1. Partition Backup: `admin_partclone_backup.sh`

This script analyzes the file system of the specified partition, backs up only the used data blocks (ignoring the empty space on the disk), compresses the data stream on the fly, and saves it into an image file inside the destination folder.

### Execution Syntax
```bash
sudo ./admin_partclone_backup.sh <source_partition> <destination_folder> <compression_level>
```

### Practical Example
```bash
sudo ./admin_partclone_backup.sh /dev/sda1 /mnt/usb_storage 6
```

### 📊 Compression Levels Guide (gzip)
The script strictly requires an integer from **1 to 9** as the third parameter:
* **`1`** : Fastest speed, lowest compression (largest final file size).
* **`2 - 3`** : Light compression. Ideal for older or low-spec processors.
* **`4 - 5`** : Balanced compromise between CPU load and saved storage space.
* **`6`** : **[Recommended]** Default standard. Offers the best speed-to-size ratio.
* **`7 - 8`** : High compression. Demands more computing resources and time.
* **`9`** : Maximum compression. Generates the smallest possible file, but the process is very slow.

### Output Naming Convention
The final file is automatically named using the following schema:  
`backup_[FSTYPE]_[PARTITION_NAME]_[DATE_TIME].img.gz`  
*(Example: `backup_ntfs_sda1_20260609_193000.img.gz`)*

---

## 🔄 2. Partition Restore: `admin_partclone_restore.sh`

This script performs the reverse process. It decompresses the generated backup file on the fly and streams it directly to the target partition, overwriting and formatting it completely.

### ⚠️ Critical Safety Warning
Restoration is a **highly destructive operation**. The script includes a security prompt that strictly requires the user to type **`SI`** (in uppercase) before proceeding with the target disk overwrite.

### Execution Syntax
```bash
sudo ./admin_partclone_restore.sh <compressed_backup_file> <target_partition>
```

### Practical Example
```bash
sudo ./admin_partclone_restore.sh /mnt/usb_storage/backup_ntfs_sda1_20260609_193000.img.gz /dev/sda1
```

---

## 💿 3. Full Disk Image Backup: `admin_disk_image.sh`

Creates a complete disk image using a `dd | pv | gzip` pipeline. Unlike partition backup, this captures the entire disk including partition table, boot sectors, and all partitions.

### Requirements
- `dd`, `pv`, `gzip`, `blockdev` (standard on Linux)
- `pv` is auto-installed via `apt` if missing (assumes Debian/Ubuntu-based live environment)
- Log directory: `/home/ntjobsos/Log` (auto-created)

### Execution Syntax
```bash
sudo ./admin_disk_image.sh <source_disk> <dest_folder> <base_name>
```

### Practical Example
```bash
sudo ./admin_disk_image.sh /dev/sda /mnt/backup server_disk
```

### Output
File named: `<base_name>_<TIMESTAMP>.img.gz` (e.g., `server_disk_20260802120000.img.gz`)

---

## 🔁 4. Full Disk Image Restore: `admin_disk_restore.sh`

Restores a disk image created by `admin_disk_image.sh` using a `gunzip | pv | dd` pipeline.

### Safety Features
- Verifies target disk is not mounted
- 5-second cancellation window (Ctrl+C) before write begins
- Log directory: `/home/ntjobsos/Log` (auto-created)

### Execution Syntax
```bash
sudo ./admin_disk_restore.sh <image_file> <target_disk>
```

### Practical Example
```bash
sudo ./admin_disk_restore.sh /mnt/backup/server_disk_20260802120000.img.gz /dev/sdb
```

---

## ☁️ 5. Google Drive Mount: `admin_gdrive_mount.sh`

Mounts a pre-configured rclone remote named `gdrive` to `/mnt/gdrive` as a daemon.

### Prerequisites
- rclone installed and configured with a remote named `gdrive`
- fusermount available

### Execution Syntax
```bash
./admin_gdrive_mount.sh
```

### Mount Options
- `--daemon` - runs in background
- `--allow-other` - allows other users to access the mount
- `--vfs-cache-mode writes` - recommended for better compatibility

---

## ☁️ 6. Google Drive Unmount: `admin_gdrive_umount.sh`

Unmounts the Google Drive mount point.

### Execution Syntax
```bash
./admin_gdrive_umount.sh
```

---

## ⌨️ 7. Italian Keyboard Layout: `admin_keybit.sh`

Sets the keyboard layout to Italian.

### Execution Syntax
```bash
sudo ./admin_keybit.sh
```

### What it does
```bash
setxkbmap it
```

---

## 🔆 8. Maximum Brightness: `admin_light_max.sh`

Sets display brightness to maximum value (6000).

### Execution Syntax
```bash
sudo ./admin_light_max.sh
```

### What it does
```bash
echo 6000 | sudo tee /sys/class/backlight/*/brightness
```

---

## 🖥️ 9. Windows Screen Resolution: `ntsetres.ps1`

Sets screen resolution via Win32 API (P/Invoke). Supports common resolutions.

### Supported Resolutions
- 1024x768
- 1280x800
- 1366x768
- 1440x900
- 1600x900
- 1680x1050
- 1920x1080

### Execution Syntax
```powershell
.\ntsetres.ps1 <resolution>
```

### Practical Example
```powershell
.\ntsetres.ps1 1920x1080
```

### Wrapper CMD Files
Pre-configured wrapper scripts are included for common resolutions:
- `admin_setres_1368x768.cmd` (runs `ntsetres.ps1 1366x768`)
- `admin_setres_1600x900.cmd` (runs `ntsetres.ps1 1600x900`)

---

## 🐍 10. Python Automation Toolkit: `pyt.py`

A versatile Python command-line tool for executing various administrative directives. Features logging, directive file execution (`@`), and cross-platform support (Windows/Linux).

### Purpose
`pyt.py` is a multi-purpose administrative toolkit that provides a unified command interface for common system administration tasks including document conversion, disk imaging, folder synchronization, WSL/VM management, and archive operations. It is designed to be invoked through the `pyt.cmd` wrapper (which delegates to `pyn.cmd` for Python environment management) or directly via `pyn.cmd`.

### Files
- `pyt.py` - Main Python script containing all directive implementations
- `pyt.cmd` - Windows wrapper that locates `pyn.cmd` (default: `k:\tools\pyn.cmd`) and passes all arguments to it with `pyt.py` as the script to execute
- `pyn.cmd` - Universal Python launcher (manages virtual envs, pip, pandoc, podman, bash, chrome)

### Prerequisites
- Python 3.x (managed via `pyn.cmd` portable environments)
- Optional dependencies per directive: `pypandoc`, `paramiko`, `markdown`, `requests`, `7-Zip`, `qemu-img`, `pandoc`

### Execution Syntax
Via `pyt.cmd` (recommended, auto-resolves Python environment):
```cmd
pyt.cmd <directive> [parameters...]
```
Or via directive file:
```cmd
pyt.cmd @ <directive_file>
```
Directly via `pyn.cmd` (explicit control over Python environment):
```cmd
pyn.cmd pyt.py <directive> [parameters...]
pyn.cmd pyt.py @ <directive_file>
```

### Available Directives (from `pyt.py` help)

| Directive | Syntax | Description |
|-----------|--------|-------------|
| `help`, `h` | `pyt.cmd help` | Shows this help |
| `doc2md` | `pyt.cmd doc2md <file.docx>` | Converts DOCX to Markdown, extracts media to `resources/` (requires `pypandoc`) |
| `md2html` | `pyt.cmd md2html <file.md> <file.html>` | Converts Markdown to HTML (requires `markdown` lib) |
| `md2page` | `pyt.cmd md2page <file.md> <file.html>` | Converts Markdown to complete HTML page via OpenRouter API (requires `OPENROUTER_API` env var) |
| `wsl_export` | `pyt.cmd wsl_export <container> <output.tar>` | Exports WSL container to tar file (Windows only) |
| `vhdx2vmdk` | `pyt.cmd vhdx2vmdk <file.vhdx> <file.vmdk>` | Converts VHDX to VMDK using qemu-img (Windows only, requires `QEMU_IMG` path) |
| `7z_ts` | `pyt.cmd 7z_ts <folder> [7z_path]` | Creates timestamped `.7z` archive with max compression (requires 7-Zip) |
| `disk_check` | `pyt.cmd disk_check <disk> <report_file> <warning_pct>` | Checks disk space, folder sizes, generates report, creates warning flag if threshold exceeded |
| `sync` | `pyt.cmd sync <config.json>` | Synchronizes folders per JSON config. Supports `file`, `filesync`, `ftp`, `ssh` types. Single job or catalog with `jobs` array. |
| `sync_script` | `pyt.cmd sync_script [src] [dest] [output.cmd]` | Generates robocopy mirror batch script. Uses `SYNC_FOLDERS` env var or defaults (Windows only) |
| `robocopy` | `pyt.cmd robocopy <config.json>` | Copies specific files per JSON with `settings` (log, err.exit) and `actions` (path_source, path_dest, mode: overwrite/old, files[]). Cross-platform (uses shutil). |

### Directive File Format (`@`)
Create a text file with one directive per line. Lines starting with `;` are comments.
```
doc2md "report.docx"
md2html "report.md" "report.html"
sync "sync_config.json"
```

### Example Usage
```cmd
REM Single directive
pyt.cmd 7z_ts "C:\Data\Projects"

REM With explicit 7z path
pyt.cmd 7z_ts "C:\Data\Projects" "C:\Program Files\7-Zip\7z.exe"

REM Directive file
pyt.cmd @ my_directives.txt

REM Disk check with 85% warning threshold
pyt.cmd disk_check "C:" "disk_report.txt" 85

REM Sync with JSON catalog
pyt.cmd sync "sync_jobs.json"
```

---

## 🚀 11. Python Launcher: `pyn.cmd`

Universal portable Python environment launcher for Windows. Manages multiple Python versions (X32/X64/W64), virtual environments, pip operations, and external tools.

### Purpose
`pyn.cmd` is a **global Python launcher** that provides a single entry point to run Python scripts, manage virtual environments, and access external tools (Pandoc, Podman, Git-Bash, Chrome) without requiring Python to be in the system PATH. It auto-detects portable Python installations in standard locations and can be customized by:

- **Editing the script**: Modify the hardcoded paths (`PATHP_01`, `PATHP_02`, `PATHP_03`, `PATHP_XX`) to point to your Python installation directories
- **Environment variable `PATHP_ENV`**: Set `PATHP_ENV` to a custom path containing your Python installation (e.g., `SET PATHP_ENV=D:\MyPython`). This takes highest priority in the search order.

### Key Features
- **Portable Python**: Auto-detects Python installations in standard locations (D:\APPLIC, C:\APPLIC, K:\Tools, parent folder)
- **Virtual Environments**: Create/switch via `x env <name>`
- **Pip Management**: Install, upgrade, list, cache purge, requirements export/import
- **External Tools**: Pandoc (docx2md, pdf2md, md2html), Podman, Git-Bash, Chrome debug mode

### Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `PY_TYPE` | Python architecture: X32, X64, W64 | X64 |
| `PY_ENV` | Virtual environment name | myenv |
| `PY_PATH` | Override Python root path | auto-detect |
| `POD_PATH` | Podman data path | c:\podman |
| `POD_APP` | Podman container image | ntjobsos |

### Commands
| Command | Description |
|---------|-------------|
| `pyn.cmd <script.py> [args]` | Run Python script with active env |
| `pyn.cmd x version` | Show Python version |
| `pyn.cmd x env <name>` | Create/activate virtual environment |
| `pyn.cmd x pip <cmd>` | Run pip command in active env |
| `pyn.cmd x pip_check` | Verify installed packages |
| `pyn.cmd x pip_pc` | Purge pip cache |
| `pyn.cmd x pip_i <pkg...>` | Install packages (--only-binary) |
| `pyn.cmd x pip_u <pkg>` | Dry-run upgrade single package |
| `pyn.cmd x pip_ulist` | Generate `pipupgrade.txt` with outdated packages |
| `pyn.cmd x pip_uexec` | Execute upgrades from `pipupgrade.txt` (logs to `pipupgrade.log`) |
| `pyn.cmd x pip_re` | Export `requirements_<TYPE>.txt` and light version |
| `pyn.cmd x pip_ri` | Import/install from `requirements_<TYPE>.txt` |
| `pyn.cmd x mod <module> [args]` | Run Python module (`-m`) |
| `pyn.cmd x script <script.exe> [args]` | Run script from env's Scripts folder |
| `pyn.cmd pandoc doc2md\|pdf2md\|docx2md <file>` | Convert to Markdown via Pandoc |
| `pyn.cmd pandoc md2html <file.md>` | Convert Markdown to HTML via Pandoc |
| `pyn.cmd b <script.sh> [args]` | Run Bash script via Git-Bash |
| `pyn.cmd chrome auto` | Launch Chrome with remote debugging (port 9222) |
| `pyn.cmd pod <cmd>` | Podman wrapper (start, end, opt, run) |

### Example Usage
```cmd
REM Run pyt.py via pyn (pyt.cmd does this automatically)
pyn.cmd pyt.py 7z_ts "C:\Projects"

REM Direct pyn usage
pyn.cmd x env myproject
pyn.cmd x pip_i requests paramiko pypandoc
pyn.cmd x pip_ulist
pyn.cmd x pip_uexec

REM Pandoc conversion
pyn.cmd pandoc doc2md "document.docx"

REM Bash script
pyn.cmd b "deploy.sh" arg1 arg2
```

---

## 🚀 12. How to Create the Bootable USB Drive

You can easily build a minimal, dedicated live USB environment using Rufus and GParted Live (which natively includes `partclone`, `gzip`, and full exFAT/FAT32 support).

### Step-by-Step Guide
1. **Download GParted Live**: Download the stable `.iso` file from the official GParted website (choose the **amd64** version for modern 64-bit PCs).
2. **Configure Rufus**: Insert your USB flash drive into a Windows PC and open Rufus.
   * **Device**: Select your USB flash drive.
   * **Boot selection**: Click *Select* and choose the downloaded GParted Live ISO file.
   * **Partition scheme**: Choose **MBR** (for maximum universal compatibility with older BIOS and newer UEFI systems) or **GPT** (for modern UEFI-only setups).
   * **File system**: Select **exFAT**. This allows you to store backup files larger than 4GB directly on the same bootable USB drive (if it has enough capacity).
3. **Flash the Drive**: Click **Start**. If prompted by Rufus, select **Write in ISO Image mode (Recommended)**. Confirm formatting and wait for completion.

### Adding the Scripts to the USB
Once Rufus finishes, the USB drive remains accessible as a standard external drive in Windows:
1. Create a folder named `ntjobs` in the root of the USB drive.
2. Copy all `.sh`, `.ps1`, `.py`, and `.cmd` files into that folder.

---

## 📋 Running the Scripts in the Live Environment

1. Boot the target PC from the created USB drive (usually by pressing F12, F11, or F8 at startup to open the Boot Menu).
2. Once GParted Live loads, open the terminal window.
3. Access your scripts folder. In GParted Live, the bootable USB drive is automatically mounted. You can navigate to it by running:
   ```bash
   cd /lib/live/mount/medium/ntjobs/
   ```
   *(Note: If not found there, check `/run/live/medium/ntjobs/`)*
4. Make sure the scripts have execution privileges:
   ```bash
   chmod +x *.sh
   ```
5. Run your desired script using `sudo`.

---

## 💡 Pro-Tip for Windows (NTFS) Backups
To maximize compression efficiency and speed, boot into Windows before running the backup script. Open a Command Prompt as Administrator and use the official Microsoft **SDelete** utility to zero out deleted file fragments:
```cmd
sdelete64.exe -z C:
```

For more info, troubleshooting, and updates, visit: http://www.ntgcorp.it