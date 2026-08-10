# admin_scripts - Agent Instructions

## Repository Overview
Collection of system administration scripts for backup/restore, disk imaging, Google Drive mounting, and Windows display management. No build system, tests, or package manager - just executable scripts.

## Script Categories

### Linux Backup/Restore (partclone)
- `ntjobs_partclone_backup.sh` - Smart partition backup using partclone + gzip (skips free space)
  - Usage: `sudo ./ntjobs_partclone_backup.sh <partition> <dest_folder> <compression_1-9>`
  - Requires: partclone, gzip, lsblk
- `ntjobs_partclone_restore.sh` - Restore backup to partition (destructive, requires "SI" confirmation)
  - Usage: `sudo ./ntjobs_partclone_restore.sh <backup_file> <target_partition>`

### Linux Disk Imaging (dd/pv/gzip)
- `admin_disk_image.sh` - Full disk image via `dd | pv | gzip`
  - Usage: `./admin_disk_image.sh <source_disk> <dest_folder> <base_name>`
  - Requires: dd, pv, gzip, blockdev (auto-installs pv via apt)
  - Log dir: `/home/ntjobsos/Log` (auto-created)
- `admin_disk_restore.sh` - Restore disk image via `gunzip | pv | dd`
  - Usage: `./admin_disk_restore.sh <image_file> <target_disk>`
  - Safety: checks target not mounted, 5s cancel window

### Google Drive (rclone)
- `admin_gdrive_mount.sh` - Mounts `gdrive` remote to `/mnt/gdrive` (daemon, --allow-other, vfs-cache-mode writes)
- `admin_gdrive_umount.sh` - Unmounts via `fusermount -u /mnt/gdrive`

### Windows Display Management
- `ntsetres.ps1` - Sets screen resolution via Win32 API (P/Invoke)
  - Supported: 1024x768, 1280x800, 1366x768, 1440x900, 1600x900, 1680x1050, 1920x1080
  - Usage: `.\ntsetres.ps1 <resolution>`
- `admin_setres_*.cmd` - Wrapper CMD files calling ntsetres.ps1

### Linux Utilities
- `admin_keybit.sh` - Sets Italian keyboard layout: `setxkbmap it`
- `admin_light_max.sh` - Sets max brightness: `echo 6000 | sudo tee /sys/class/backlight/*/brightness`

## Key Conventions
- All shell scripts use `#!/bin/bash` and Italian messages
- Scripts require `sudo` for device operations
- No linting, formatting, or testing infrastructure exists
- Scripts are designed for GParted Live / Debian-based live environments

## Common Gotchas
- `ntjobs_partclone_restore.sh` is empty (0 bytes) - needs implementation
- `admin_disk_*.sh` hardcodes log directory `/home/ntjobsos/Log`
- `admin_disk_*.sh` assumes Debian/Ubuntu (uses apt for pv install)
- Google Drive scripts assume rclone remote named "gdrive" is pre-configured
- Windows scripts use P/Invoke - may need adjustment for multi-monitor setups

## OpenCode Integration
- `opencode_start.cmd` launches opencode from V:\tools or X:\_applic with OPENROUTER_API_KEY
- No opencode.json or project-specific config exists