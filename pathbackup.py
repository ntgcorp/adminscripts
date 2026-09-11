#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import shutil
import logging
import platform
import subprocess
import configparser
import zipfile
import json
import stat

from pathlib import Path
from datetime import datetime


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


# ----------------------------------------------------------------------
# Incremental Backup Utilities
# ----------------------------------------------------------------------

def get_metadata_file(backup_folder, entry_name):
    """Get path to metadata file for tracking incremental backups."""
    safe_name = sanitize_filename(entry_name)
    return os.path.join(backup_folder, f".{safe_name}_metadata.json")


def load_last_backup_time(backup_folder, entry_name):
    """Load the timestamp of the last successful backup for this entry."""
    metadata_file = get_metadata_file(backup_folder, entry_name)
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('last_backup_time', 0)
        except Exception:
            pass
    return 0


def save_last_backup_time(backup_folder, entry_name, timestamp):
    """Save the timestamp of the current backup."""
    metadata_file = get_metadata_file(backup_folder, entry_name)
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump({'last_backup_time': timestamp}, f)
    except Exception as e:
        logging.getLogger("path_backup").warning(f"Failed to save metadata: {e}")


def has_archive_flag(filepath):
    """Check if file has archive attribute set (Windows)."""
    try:
        attrs = os.stat(filepath).st_file_attributes if hasattr(os.stat(filepath), 'st_file_attributes') else 0
        return bool(attrs & 0x20)  # FILE_ATTRIBUTE_ARCHIVE = 0x20
    except Exception:
        return False


def clear_archive_flag(filepath):
    """Clear the archive attribute on Windows after backup."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        FILE_ATTRIBUTE_ARCHIVE = 0x20
        attrs = kernel32.GetFileAttributesW(filepath)
        if attrs != -1 and (attrs & FILE_ATTRIBUTE_ARCHIVE):
            kernel32.SetFileAttributesW(filepath, attrs & ~FILE_ATTRIBUTE_ARCHIVE)
    except Exception:
        pass


def should_backup_file(filepath, last_backup_time):
    """Determine if a file should be backed up in incremental mode."""
    system = platform.system()
    
    if system == "Windows":
        # On Windows, use archive flag: back up if flag is set
        return has_archive_flag(filepath)
    else:
        # On Linux/Unix, use mtime: back up if modified since last backup
        try:
            mtime = os.path.getmtime(filepath)
            return mtime > last_backup_time
        except Exception:
            return True  # If we can't determine, back it up to be safe


def find_7z():
    system = platform.system()

    if system == "Windows":
        candidates = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]

        for p in candidates:
            if os.path.exists(p):
                return p

        exe = shutil.which("7z")
        if exe:
            return exe

        return None

    return shutil.which("7z")


def verify_engine(engine):
    if engine == "7Z":
        exe = find_7z()
        if not exe:
            raise RuntimeError(
                "7z not found. Install p7zip-full (Linux) or 7-Zip (Windows)"
            )
        return exe

    elif engine == "TAR":
        tar_exe = shutil.which("tar")
        gzip_exe = shutil.which("gzip")
        if not tar_exe or not gzip_exe:
            raise RuntimeError(
                "tar or gzip not found. TAR engine not available on this system"
            )
        return tar_exe

    elif engine == "ZIP":
        return "zipfile"

    raise RuntimeError(f"Unsupported ENGINE={engine}")


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

def setup_logger(log_file):
    logger = logging.getLogger("path_backup")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(sh)

    return logger


# ----------------------------------------------------------------------
# Compressione
# ----------------------------------------------------------------------

def run_7z(archiver, output_archive, source):
    cmd = [
        archiver,
        "a",
        "-t7z",
        output_archive,
        source
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    return cmd, result


def run_tar(output_archive, source):
    cmd = [
        "tar",
        "-czf",
        output_archive,
        source
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    return cmd, result


def run_zip(output_archive, source, subdirs, logger, incremental=False, last_backup_time=0):
    import glob
    file_falliti = []
    file_successo = 0
    files_backed_up = []  # Track files that were backed up to clear archive flag

    source = source.strip().strip('"')

    has_wildcard = '*' in source or '?' in source

    def should_include(filepath):
        if not incremental:
            return True
        return should_backup_file(filepath, last_backup_time)

    def process_file(filepath, arcname):
        nonlocal file_successo
        try:
            zipf.write(filepath, arcname=arcname)
            file_successo += 1
            files_backed_up.append(filepath)
        except Exception as e:
            file_falliti.append({
                "file": filepath,
                "errore": str(e)
            })

    def clear_flags_and_return(code):
        """Clear archive flags on Windows for successfully backed up files, then return."""
        if incremental and platform.system() == "Windows":
            for f in files_backed_up:
                clear_archive_flag(f)
        return code, file_falliti, file_successo

    if has_wildcard:
        matches = glob.glob(source)
        if not matches:
            logger.warning(f"No files matched wildcard pattern: {source}")
            return clear_flags_and_return(1)

        try:
            with zipfile.ZipFile(output_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for match in matches:
                    match = match.strip().strip('"')
                    if os.path.isfile(match):
                        if should_include(match):
                            process_file(match, os.path.basename(match))
                    elif os.path.isdir(match):
                        folder_name = os.path.basename(match.rstrip(os.sep))
                        if subdirs:
                            for root, dirs, files in os.walk(match):
                                for file in files:
                                    percorso_assoluto = os.path.join(root, file)
                                    percorso_relativo = os.path.relpath(percorso_assoluto, match)
                                    arcname = os.path.join(folder_name, percorso_relativo)
                                    if should_include(percorso_assoluto):
                                        process_file(percorso_assoluto, arcname)
                        else:
                            for item in os.listdir(match):
                                percorso_assoluto = os.path.join(match, item)
                                if os.path.isfile(percorso_assoluto) and should_include(percorso_assoluto):
                                    arcname = os.path.join(folder_name, item)
                                    process_file(percorso_assoluto, arcname)

        except Exception as e:
            logger.error(f"Error creating ZIP archive: {e}")
            return clear_flags_and_return(1)

        if file_falliti:
            return clear_flags_and_return(1)
        return clear_flags_and_return(0)

    if not os.path.exists(source):
        logger.warning(f"Source path does not exist: {source}")
        return clear_flags_and_return(1)

    if os.path.isfile(source):
        if not should_include(source):
            logger.info(f"Skipping unchanged file: {source}")
            return clear_flags_and_return(0)
        try:
            with zipfile.ZipFile(output_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(source, arcname=os.path.basename(source))
            file_successo = 1
            files_backed_up.append(source)
            return clear_flags_and_return(0)
        except Exception as e:
            file_falliti.append({
                "file": source,
                "errore": str(e)
            })
            return clear_flags_and_return(1)

    if os.path.isdir(source):
        try:
            with zipfile.ZipFile(output_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                folder_name = os.path.basename(source.rstrip(os.sep))
                if subdirs:
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            percorso_assoluto = os.path.join(root, file)
                            percorso_relativo = os.path.relpath(percorso_assoluto, source)
                            arcname = os.path.join(folder_name, percorso_relativo)
                            if should_include(percorso_assoluto):
                                process_file(percorso_assoluto, arcname)
                else:
                    for item in os.listdir(source):
                        percorso_assoluto = os.path.join(source, item)
                        if os.path.isfile(percorso_assoluto) and should_include(percorso_assoluto):
                            arcname = os.path.join(folder_name, item)
                            process_file(percorso_assoluto, arcname)

            if file_falliti:
                return clear_flags_and_return(1)
            return clear_flags_and_return(0)

        except Exception as e:
            logger.error(f"Error creating ZIP archive: {e}")
            return clear_flags_and_return(1)

    return clear_flags_and_return(1)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def parse_args():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python path_backup.py <ini_file1> [<ini_file2> ...]\n"
            "Example:\n"
            "  python path_backup.py backup_config.ini backup_sezioni.ini"
        )
        sys.exit(1)

    ini_files = []
    for f in sys.argv[1:]:
        stripped = f.strip()
        if not stripped:
            continue
        if stripped in ('"', "'"):
            continue
        if set(stripped) <= {'\\', ' ', '"', "'"}:
            continue
        ini_files.append(f)

    if not ini_files:
        print("ERROR: No INI files specified (all arguments were empty)")
        sys.exit(1)
    return ini_files


def merge_ini_files(ini_files):
    merged_config = configparser.ConfigParser(interpolation=None)
    merged_config.optionxform = str

    for ini_file in ini_files:
        abs_path = os.path.abspath(ini_file)
        if not os.path.isfile(abs_path):
            print(f"ERROR: INI file not found: {ini_file}")
            print(f"       Resolved path: {abs_path}")
            sys.exit(1)

        with open(ini_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        content = content.replace("<br>", "\n").replace("<BR>", "\n")

        temp_config = configparser.ConfigParser(interpolation=None)
        temp_config.optionxform = str
        temp_config.read_string(content)

        for section in temp_config.sections():
            section_upper = section.upper().strip()
            if not merged_config.has_section(section_upper):
                merged_config.add_section(section_upper)
            for key, value in temp_config.items(section):
                merged_config.set(section_upper, key, value.strip().strip('"'))

    return merged_config


def main():
    ini_files = parse_args()

    config = merge_ini_files(ini_files)

    if not config.has_section("CONFIG"):
        print("ERROR: [CONFIG] section not found in INI files")
        sys.exit(1)

    engine = config.get("CONFIG", "ENGINE", fallback="7Z").upper()
    exit_on_error = config.getboolean("CONFIG", "EXIT_ON_ERROR", fallback=False)

    if not config.has_option("CONFIG", "PATH_DEST"):
        print("ERROR: PATH_DEST not specified in [CONFIG] section")
        sys.exit(1)

    output_root = config.get("CONFIG", "PATH_DEST").strip().strip('"')
    if not os.path.isdir(output_root):
        print(f"ERROR: PATH_DEST directory not found: {output_root}")
        sys.exit(1)

    mode = config.get("CONFIG", "MODE", fallback="TOTAL").upper()
    subdirs = config.getboolean("CONFIG", "SUBDIRS", fallback=False)

    if config.has_option("CONFIG", "SECTIONS"):
        sections_str = config.get("CONFIG", "SECTIONS")
        sections = [s.strip().upper() for s in sections_str.split(",") if s.strip()]
    else:
        sections = [s for s in config.sections() if s != "CONFIG"]

    try:
        archiver = verify_engine(engine)
    except Exception as ex:
        print(f"ERROR: {ex}")
        sys.exit(1)

    day_folder = datetime.now().strftime("%Y%m%d")
    backup_folder = os.path.join(output_root, day_folder)
    os.makedirs(backup_folder, exist_ok=True)

    log_file = os.path.join(backup_folder, f"backup_{day_folder}.log")
    logger = setup_logger(log_file)

    logger.info("====================================================")
    logger.info("Backup started")
    logger.info(f"OS={platform.system()}")
    logger.info(f"ENGINE={engine}")
    logger.info(f"INI FILES={', '.join(ini_files)}")
    logger.info(f"MODE={mode}")
    logger.info(f"SUBDIRS={subdirs}")
    logger.info("====================================================")

    sections_to_process = sections if sections else [s for s in config.sections() if s != "CONFIG"]

    for current_section in sections_to_process:
        if not config.has_section(current_section):
            logger.error(f"Section [{current_section}] not found in INI files")
            if exit_on_error:
                sys.exit(1)
            continue

        logger.info(f"Processing section: [{current_section}]")

        for entry_name, source in config.items(current_section):
            try:
                source = source.strip().strip('"')
                safe_name = sanitize_filename(entry_name)
                timestamp = datetime.now().strftime("%Y%m%d%H%M")
                current_time = datetime.now().timestamp()

                if engine == "7Z":
                    archive_name = f"{safe_name}_{timestamp}.7z"
                elif engine == "ZIP":
                    archive_name = f"{safe_name}_{timestamp}.zip"
                else:
                    archive_name = f"{safe_name}_{timestamp}.tar.gz"

                archive_path = os.path.join(backup_folder, archive_name)

                logger.info("--------------------------------------")
                logger.info(f"ENTRY      : {entry_name}")
                logger.info(f"SOURCE     : {source}")
                logger.info(f"ARCHIVE    : {archive_path}")

                is_incremental = (mode == "INCREMENTAL")
                last_backup_time = 0
                if is_incremental:
                    last_backup_time = load_last_backup_time(backup_folder, entry_name)
                    logger.info(f"MODE       : INCREMENTAL (last backup: {datetime.fromtimestamp(last_backup_time) if last_backup_time else 'never'})")

                if engine == "7Z":
                    if is_incremental:
                        logger.warning("Incremental mode not fully supported for 7Z engine, falling back to full backup")
                    cmd, result = run_7z(archiver, archive_path, source)
                    logger.info("COMMAND    : %s", " ".join(cmd))
                    logger.info("RETURNCODE : %s", result.returncode)

                    if result.stdout:
                        logger.info("STDOUT:\n%s", result.stdout)
                    if result.stderr:
                        logger.warning("STDERR:\n%s", result.stderr)

                    if result.returncode == 0:
                        logger.info("SUCCESS")
                        if is_incremental:
                            save_last_backup_time(backup_folder, entry_name, current_time)
                    elif result.returncode == 1:
                        logger.warning("SUCCESS WITH WARNINGS")
                        if is_incremental:
                            save_last_backup_time(backup_folder, entry_name, current_time)
                    else:
                        raise RuntimeError(f"7z return code={result.returncode}")

                elif engine == "ZIP":
                    logger.info(f"Creating ZIP archive with subdirs={subdirs}" + (" (INCREMENTAL)" if is_incremental else ""))
                    returncode, file_falliti, file_successo = run_zip(
                        archive_path, source, subdirs, logger,
                        incremental=is_incremental, last_backup_time=last_backup_time
                    )

                    if file_falliti:
                        logger.warning(
                            f"Files failed to archive ({len(file_falliti)}):"
                        )
                        for ff in file_falliti:
                            logger.warning(f"  - {ff['file']}: {ff['errore']}")

                    if returncode == 0:
                        logger.info(f"SUCCESS ({file_successo} files archived)")
                        if is_incremental:
                            save_last_backup_time(backup_folder, entry_name, current_time)
                    else:
                        if file_successo > 0:
                            logger.warning(
                                f"PARTIAL SUCCESS ({file_successo} files archived, "
                                f"{len(file_falliti)} failed)"
                            )
                            if is_incremental:
                                save_last_backup_time(backup_folder, entry_name, current_time)
                        else:
                            raise RuntimeError("ZIP archive creation failed")

                else:
                    if is_incremental:
                        logger.warning("Incremental mode not fully supported for TAR engine, falling back to full backup")
                    cmd, result = run_tar(archive_path, source)
                    logger.info("COMMAND    : %s", " ".join(cmd))
                    logger.info("RETURNCODE : %s", result.returncode)

                    if result.stdout:
                        logger.info("STDOUT:\n%s", result.stdout)
                    if result.stderr:
                        logger.warning("STDERR:\n%s", result.stderr)

                    if result.returncode == 0:
                        logger.info("SUCCESS")
                        if is_incremental:
                            save_last_backup_time(backup_folder, entry_name, current_time)
                    else:
                        raise RuntimeError(f"TAR return code={result.returncode}")

            except Exception as ex:
                logger.exception(f"ERROR processing [{entry_name}]")

                if exit_on_error:
                    logger.error("EXIT_ON_ERROR=true -> aborting")
                    sys.exit(1)

    logger.info("====================================================")
    logger.info("Backup completed")
    logger.info("====================================================")


if __name__ == "__main__":
    main()
