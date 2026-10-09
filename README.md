# NTG AdminScripts

**Practical system administration, backup and automation tools for Linux and Windows.**

`adminscripts` is the system administration toolkit of the [NTG Python Automation Ecosystem](https://github.com/ntgcorp).

It provides independent scripts and command-line utilities for disk imaging, partition recovery, system migration, network storage, Windows configuration and everyday administrative tasks. It also includes Python automation helpers for file processing, synchronization and repetitive operations.

Designed for system administrators, developers and advanced users, the repository is particularly useful in Linux live environments, workstation maintenance and technical automation workflows.

## Features at a glance

| Category | What you can do |
|---|---|
| 💾 Backup & recovery | Create compressed partition backups and full-disk images; restore them when needed. |
| 🔄 System migration | Back up and restore selected system configuration, packages and home directories on supported Linux distributions. |
| 🌐 Network storage | Mount SMB, NFS and FTP shares, or connect to a configured Google Drive remote. |
| 🐧 Linux administration | Configure keyboard layout and display brightness; analyze folder sizes. |
| 🪟 Windows administration | Change display resolution and prepare SeleniumBasic/ChromeDriver components. |
| 🐍 Python automation | Run utility commands, synchronize files, manage archives and automate common administrative operations. |
| 🧰 Portable tooling | Use Python launchers, configuration examples and backup utilities. |

## Contents

- [1. Backup and recovery](#1-backup-and-recovery)
- [2. Linux system migration](#2-linux-system-migration)
- [3. Network and cloud storage](#3-network-and-cloud-storage)
- [4. Linux utilities](#4-linux-utilities)
- [5. Windows administration](#5-windows-administration)
- [6. Python automation tools](#6-python-automation-tools)
- [7. Configuration examples](#7-configuration-examples)
- [8. Live USB environment](#8-live-usb-environment)
- [Requirements and safety](#requirements-and-safety)
- [NTG ecosystem](#ntg-ecosystem)

---

## 1. Backup and recovery

### Partition backup and restore

Scripts: `admin_partclone_backup.sh` and `admin_partclone_restore.sh`

Create compressed partition images using Partclone and gzip. Partclone can skip unused filesystem blocks when the filesystem is supported, reducing backup size compared with a raw partition copy.

**Create a backup:**

```bash
sudo ./admin_partclone_backup.sh /dev/sda1 /mnt/usb_storage 6
```

Arguments:

- Source partition, for example `/dev/sda1`
- Destination directory
- Compression level from 1 to 9

**Restore a backup:**

```bash
sudo ./admin_partclone_restore.sh /mnt/usb_storage/backup.img.gz /dev/sda1
```

The restore script requires an explicit confirmation before proceeding.

### Full-disk imaging

Scripts: `admin_disk_image.sh` and `admin_disk_restore.sh`

Create and restore compressed images of entire disks, including partition tables, boot sectors and partition contents.

**Create an image:**

```bash
sudo ./admin_disk_image.sh /dev/sda /mnt/backup server_disk
```

**Restore an image:**

```bash
sudo ./admin_disk_restore.sh /mnt/backup/server_disk_20260802120000.img.gz /dev/sdb
```

The backup and restore workflows use `dd`, `pv` and gzip pipelines. The scripts include progress reporting and logging; the backup script can install `pv` automatically through APT in supported Debian/Ubuntu environments.

**Important:** Restoring an image overwrites the target disk. Verify the source, destination and backup integrity before proceeding.

### Folder size analysis

Script: `admin_folders_size.sh`

List first-level subfolder sizes in descending order, filtering results by a minimum size in megabytes.

```bash
./admin_folders_size.sh /home/user/data 100
```

A special mode for `/` scans a predefined set of system directories, excluding `/mnt`.

### NTFS preparation for compression

On Windows, the repository documents the use of Microsoft's SDelete to zero free space before imaging:

```cmd
sdelete64.exe -z C:
```

This can improve compression of subsequent disk images. Use it only when appropriate and after understanding its impact on the target volume.

---

## 2. Linux system migration

Script: `admin_migrate.sh`

Back up or restore selected components of Zorin OS, Ubuntu and Debian installations.

The workflow can include:

- APT package lists and package information
- Flatpak applications
- Snap packages
- Home directories
- Selected system configuration and desktop settings

**Create a backup:**

```bash
./admin_migrate.sh backup /mnt/backup/destination
```

**Restore a backup:**

```bash
./admin_migrate.sh restore /mnt/backup/source
```

The generated backup structure separates package information, home-directory data and system settings into dedicated directories. Timestamped logs record progress, warnings and errors.

Review the generated files and the script's restore behavior before migrating a production system. Restoring configuration across different installations can require manual adjustments.

---

## 3. Network and cloud storage

### NAS mounting

Script: `admin_nas_mount.sh`

Mount network shares under `/mnt/` with automatic mount-point creation.

**SMB:**

```bash
./admin_nas_mount.sh smb ntgdsnas temp
```

**NFS:**

```bash
./admin_nas_mount.sh nfs 192.168.1.100 backup
```

**FTP:**

```bash
./admin_nas_mount.sh ftp ftp.example.com data user pass
```

The script supports SMB, NFS and FTP using their respective system utilities. NFS paths follow the script's configured export-path convention, while FTP mounting requires `curlftpfs`.

Avoid passing real passwords in shell history or publicly shared command examples.

### Google Drive mounting

Scripts: `admin_gdrive_mount.sh` and `admin_gdrive_umount.sh`

Mount and unmount a Google Drive remote configured in `rclone` under the name `gdrive`.

```bash
./admin_gdrive_mount.sh
./admin_gdrive_umount.sh
```

The mount workflow uses a configured mount point at `/mnt/gdrive` and background operation. It requires a working `rclone` configuration and appropriate FUSE permissions.

---

## 4. Linux utilities

| Script | Purpose |
|---|---|
| `admin_keybit.sh` | Set the keyboard layout to Italian using `setxkbmap`. |
| `admin_light_max.sh` | Set display brightness to the configured maximum value. |

**Set the keyboard layout:**

```bash
sudo ./admin_keybit.sh
```

**Set maximum brightness:**

```bash
sudo ./admin_light_max.sh
```

Hardware support for brightness control depends on the available backlight interface. Check the script and device configuration if the command is not supported by your system.

---

## 5. Windows administration

### Display resolution

Scripts: `ntsetres.ps1` and `admin_setres_*.cmd`

Change the display resolution using the Windows API.

```powershell
.\ntsetres.ps1 1920x1080
```

The documented resolutions include:

`1024x768`, `1280x800`, `1366x768`, `1440x900`, `1600x900`, `1680x1050` and `1920x1080`.

Convenience wrappers are also provided:

- `admin_setres_1368x768.cmd`
- `admin_setres_1600x900.cmd`

Check the actual resolution selected by each wrapper before using it in an automated deployment.

### SeleniumBasic and ChromeDriver

Scripts: `selenium_driver_download.ps1`, `selenium_driver_download.cmd` and `ps_start.cmd`

Download and extract SeleniumBasic components and ChromeDriver to a configured directory, defaulting to `C:\seleniumbasic`.

```cmd
selenium_driver_download.cmd
```

Alternatively, run the PowerShell script directly:

```powershell
powershell -ExecutionPolicy Bypass -File selenium_driver_download.ps1 "C:\seleniumbasic" 146
```

The script verifies the presence of expected files after extraction. Confirm that the selected ChromeDriver version is compatible with the installed browser and that downloaded components come from trusted sources.

`ps_start.cmd` is a generic CMD wrapper for invoking PowerShell scripts with parameter forwarding.

---

## 6. Python automation tools

This repository also distributes Python utilities and launchers that support administrative workflows. Some components originate from separate projects and have their own maintenance and documentation requirements.

### Python launchers

| Component | Purpose |
|---|---|
| `pyn.cmd` | Windows Python launcher and command helper. |
| `pyn.sh` | Linux counterpart for supported launcher operations. |
| `pyt.py` | Multi-purpose command-line toolkit. |
| `pyt.cmd` | Windows wrapper for `pyt.py`. |

The launchers provide shortcuts for supported Python environments, package management and selected external tools. Their exact capabilities depend on the operating system and local configuration.

### `pyt.py`: command-line utilities

The toolkit includes operations for document conversion, synchronization, archive creation, disk reporting, WSL/VM workflows, Git-related tasks and other administrative jobs.

Examples of supported directives documented in this repository include:

| Directive | Purpose |
|---|---|
| `doc2md` | Convert DOCX documents to Markdown. |
| `md2html` | Convert Markdown to HTML. |
| `md2page` | Generate an HTML page from Markdown using the configured OpenRouter API. |
| `wsl_export` | Export a WSL environment to a TAR archive. |
| `vhdx2vmdk` | Convert VHDX images to VMDK using `qemu-img`. |
| `7z_ts` | Create timestamped 7-Zip archives. |
| `disk_check` | Report disk usage and apply a configured threshold. |
| `sync` | Synchronize folders using JSON configuration. |
| `sync_script` | Generate a Robocopy mirror batch script. |
| `robocopy` | Execute configured file-copy operations. |

For example, a synchronization operation can be invoked through the Windows wrapper:

```cmd
pyt.cmd sync "sync_jobs.json"
```

Consult the actual command implementation and configuration examples for the required arguments and behavior.

### `pathbackup.py`: configurable backups

`pathbackup.py` provides an INI-driven backup workflow with support for 7-Zip, TAR and ZIP engines and incremental backup options.

Related files:

- `pathbackup_man.md` — user manual and configuration reference
- `test_pathbackup.ini` — sample configuration
- `test_pathbackup.cmd` — test wrapper

Use the manual as the primary reference for configuration syntax and supported operations.

### Other helpers

- `opencode_start.cmd` — launches OpenCode from configured locations and uses `OPENROUTER_API_KEY`.
- `ps_start.cmd` — PowerShell launcher.
- `examples/` — sample JSON configurations for selected automation workflows.

Some Python components are distributed here for convenience rather than maintained as standalone projects in this repository. Refer to the corresponding source-project documentation where applicable.

---

## 7. Configuration examples

The `examples/` directory contains sample configurations for selected workflows.

| File | Purpose |
|---|---|
| `pyt_robocopy_template.json` | Template for Robocopy actions, including wildcard-based operations. |
| `pyt_sync_ntgcorp.json` | Example FTP synchronization configuration for NTG website deployment. |
| `pyt_github.json` | Example configuration for synchronizing a local repository copy to GitHub. |

Review and adapt these files before execution. Example configurations may contain environment-specific paths, hostnames or settings that are not suitable for your system.

---

## 8. Live USB environment

The Linux utilities can be used in a live environment for system maintenance, disk backup and recovery.

A possible workflow is:

1. Download a suitable live Linux image from its official source.
2. Create a bootable USB using a compatible imaging tool.
3. Copy the required scripts and dependencies onto accessible storage.
4. Boot the target computer from the live environment.
5. Identify the source and destination devices.
6. Run the selected script with the necessary permissions.

For example, after navigating to the directory containing the scripts:

```bash
chmod +x *.sh
sudo ./admin_partclone_backup.sh /dev/sda1 /mnt/usb_storage 6
```

The location of the USB drive and the availability of utilities vary by live distribution. Check the mounted paths and installed packages before executing commands.

---

## Requirements and safety

Requirements vary by script and operating system. Common dependencies include:

- Linux utilities such as `partclone`, `dd`, `pv`, `gzip`, `rsync` and `rclone`
- Filesystem and network-mount utilities, including FUSE and `curlftpfs` where applicable
- Python 3 and any dependencies required by the selected Python command
- Windows PowerShell, a compatible Python installation and any required external tools

Before using any script:

- Read the source code and verify its parameters.
- Run administrative commands with elevated privileges only when required.
- Verify backup integrity and restore destinations.
- Test on non-production data or virtual machines whenever possible.
- Protect passwords, API keys and other credentials.
- Check the license and third-party requirements before redistributing components.

**Disk restore, migration and synchronization operations can overwrite or remove data. Always verify the selected source, destination and configuration before proceeding.**

## NTG ecosystem

`adminscripts` is the system administration component of the NTG ecosystem: a collection of independent, complementary tools for system automation, file operations and data processing.

Explore related projects:

- [ntJobsApp](https://github.com/ntgcorp/ntJobsApp) — job automation.
- [ntJobsOS](https://github.com/ntgcorp/ntJobsOS) — operating-system-related tools.
- [ntj_fact](https://github.com/ntgcorp/ntj_fact) — structured-data processing.

Visit [github.com/ntgcorp](https://github.com/ntgcorp) to discover the other public repositories.

## License

See [`LICENSE`](LICENSE) for the applicable license.