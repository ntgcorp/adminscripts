This suite consists of system administration scripts for backup/restore, disk imaging, Google Drive mounting, and Windows display management. Designed for Live Linux environments (such as GParted Live) and Windows systems.

Official documentation and updates: [http://ntgcorp.it/admin_scripts](https://github.com/ntgcorp/admin_scripts/)

---

## 💾 1. Partition Backup: `ntjobs_partclone_backup.sh`

This script analyzes the file system of the specified partition, backs up only the used data blocks (ignoring the empty space on the disk), compresses the data stream on the fly, and saves it into an image file inside the destination folder.

### Execution Syntax
```bash
sudo ./ntjobs_partclone_backup.sh <source_partition> <destination_folder> <compression_level>
```

### Practical Example
```bash
sudo ./ntjobs_partclone_backup.sh /dev/sda1 /mnt/usb_storage 6
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

## 🔄 2. Partition Restore: `ntjobs_partclone_restore.sh`

This script performs the reverse process. It decompresses the generated backup file on the fly and streams it directly to the target partition, overwriting and formatting it completely.

### ⚠️ Critical Safety Warning
Restoration is a **highly destructive operation**. The script includes a security prompt that strictly requires the user to type **`SI`** (in uppercase) before proceeding with the target disk overwrite.

### Execution Syntax
```bash
sudo ./ntjobs_partclone_restore.sh <compressed_backup_file> <target_partition>
```

### Practical Example
```bash
sudo ./ntjobs_partclone_restore.sh /mnt/usb_storage/backup_ntfs_sda1_20260609_193000.img.gz /dev/sda1
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

## 🚀 10. How to Create the Bootable USB Drive

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
2. Copy all `.sh` and `.ps1` files into that folder.

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