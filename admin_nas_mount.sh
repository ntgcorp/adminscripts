#!/bin/bash

# admin_nas_mount.sh
# Mounts a remote share (SMB/NFS/FTP) to /mnt/<folder>
# Usage: 
#   ./admin_nas_mount.sh smb <server> <folder>
#   ./admin_nas_mount.sh nfs <server> <folder>
#   ./admin_nas_mount.sh ftp <server> <folder> <user> <password>

show_usage() {
    echo "Usage: $0 <protocol> <server> <folder> [user] [password]"
    echo ""
    echo "Parameters:"
    echo "  protocol  - Mount protocol (smb, nfs, ftp)"
    echo "  server    - Remote server hostname or IP"
    echo "  folder    - Share/folder name (used for both remote path and local mount point)"
    echo "  user      - Username (required for ftp, optional for smb)"
    echo "  password  - Password (required for ftp, optional for smb)"
    echo ""
    echo "Examples:"
    echo "  $0 smb ntgdsnas temp"
    echo "    Mounts smb://ntgdsnas/temp to /mnt/temp"
    echo "  $0 nfs 192.168.1.100 backup"
    echo "    Mounts 192.168.1.100:/volume1/backup to /mnt/backup"
    echo "  $0 ftp ftp.example.com data user pass"
    echo "    Mounts ftp://user:pass@ftp.example.com/data to /mnt/data"
}

# Validate parameter count based on protocol
if [ $# -lt 3 ]; then
    show_usage
    exit 1
fi

PROTOCOL="$1"
SERVER="$2"
FOLDER="$3"

# FTP requires 5 parameters
if [ "$PROTOCOL" = "ftp" ] && [ $# -ne 5 ]; then
    echo "Error: FTP protocol requires 5 parameters: protocol server folder user password"
    echo ""
    show_usage
    exit 1
fi

# SMB/NFS require 3 parameters
if [ "$PROTOCOL" != "ftp" ] && [ $# -ne 3 ]; then
    show_usage
    exit 1
fi

# Extract user/password for FTP
if [ "$PROTOCOL" = "ftp" ]; then
    FTP_USER="$4"
    FTP_PASS="$5"
fi

MOUNT_POINT="/mnt/$FOLDER"

# Validate protocol and set remote path
case "$PROTOCOL" in
    smb)
        REMOTE_PATH="//$SERVER/$FOLDER"
        MOUNT_OPTS="-t cifs"
        ;;
    nfs)
        REMOTE_PATH="$SERVER:/volume1/$FOLDER"
        MOUNT_OPTS="-t nfs"
        ;;
    ftp)
        REMOTE_PATH="ftp://$FTP_USER:$FTP_PASS@$SERVER/$FOLDER"
        MOUNT_OPTS="-t fuse.curlftpfs"
        ;;
    *)
        echo "Error: Unsupported protocol '$PROTOCOL'. Use: smb, nfs, or ftp"
        echo ""
        show_usage
        exit 1
        ;;
esac

echo "Mounting: $REMOTE_PATH -> $MOUNT_POINT"
echo "Protocol: $PROTOCOL"

# Create mount point if it doesn't exist
if [ ! -d "$MOUNT_POINT" ]; then
    echo "Creating mount point: $MOUNT_POINT"
    sudo mkdir -p "$MOUNT_POINT"
    sudo chmod 755 "$MOUNT_POINT"
    echo "Mount point created with permissions 755"
fi

# Check if already mounted
if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    echo "Already mounted at $MOUNT_POINT"
    exit 0
fi

# Attempt mount based on protocol
echo "Attempting mount..."
case "$PROTOCOL" in
    smb)
        # SMB mount - try guest first, then with credentials if provided
        if [ -n "$FTP_USER" ] && [ -n "$FTP_PASS" ]; then
            sudo mount $MOUNT_OPTS "$REMOTE_PATH" "$MOUNT_POINT" -o username="$FTP_USER",password="$FTP_PASS",iocharset=utf8,file_mode=0755,dir_mode=0755,vers=3.0
        else
            sudo mount $MOUNT_OPTS "$REMOTE_PATH" "$MOUNT_POINT" -o username=guest,iocharset=utf8,file_mode=0755,dir_mode=0755,vers=3.0 2>/dev/null || \
            sudo mount $MOUNT_OPTS "$REMOTE_PATH" "$MOUNT_POINT" -o iocharset=utf8,file_mode=0755,dir_mode=0755,vers=3.0 2>/dev/null || \
            sudo mount $MOUNT_OPTS "$REMOTE_PATH" "$MOUNT_POINT"
        fi
        ;;
    nfs)
        # NFS mount
        sudo mount $MOUNT_OPTS "$REMOTE_PATH" "$MOUNT_POINT"
        ;;
    ftp)
        # FTP mount via curlftpfs (FUSE)
        sudo mount $MOUNT_OPTS "$REMOTE_PATH" "$MOUNT_POINT" -o allow_other,uid=$(id -u),gid=$(id -g)
        ;;
esac

if [ $? -eq 0 ]; then
    echo "OK: $MOUNT_POINT mounted correctly."
    mount | grep "$MOUNT_POINT"
else
    echo "ERROR: Failed to mount $REMOTE_PATH to $MOUNT_POINT"
    echo "Check: server reachable, share exists, permissions, firewall"
    echo "For FTP: ensure curlftpfs is installed (sudo apt install curlftpfs)"
    exit 1
fi