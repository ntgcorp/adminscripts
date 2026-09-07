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

from pathlib import Path
from datetime import datetime


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


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


def run_zip(output_archive, source, subdirs, logger):
    file_falliti = []
    file_successo = 0

    source = source.strip().strip('"')

    if not os.path.exists(source):
        logger.warning(f"Source path does not exist: {source}")
        return 1, file_falliti, file_successo

    if os.path.isfile(source):
        try:
            with zipfile.ZipFile(output_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(source, arcname=os.path.basename(source))
            file_successo = 1
            return 0, file_falliti, file_successo
        except Exception as e:
            file_falliti.append({
                "file": source,
                "errore": str(e)
            })
            return 1, file_falliti, file_successo

    if os.path.isdir(source):
        try:
            with zipfile.ZipFile(output_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if subdirs:
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            percorso_assoluto = os.path.join(root, file)
                            percorso_relativo = os.path.relpath(percorso_assoluto, source)

                            try:
                                zipf.write(percorso_assoluto, arcname=percorso_relativo)
                                file_successo += 1
                            except Exception as e:
                                file_falliti.append({
                                    "file": percorso_assoluto,
                                    "errore": str(e)
                                })
                else:
                    for item in os.listdir(source):
                        percorso_assoluto = os.path.join(source, item)
                        if os.path.isfile(percorso_assoluto):
                            try:
                                zipf.write(percorso_assoluto, arcname=item)
                                file_successo += 1
                            except Exception as e:
                                file_falliti.append({
                                    "file": percorso_assoluto,
                                    "errore": str(e)
                                })

            if file_falliti:
                return 1, file_falliti, file_successo
            return 0, file_falliti, file_successo

        except Exception as e:
            logger.error(f"Error creating ZIP archive: {e}")
            return 1, file_falliti, file_successo

    return 1, file_falliti, file_successo


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
                merged_config.set(section_upper, key, value)

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

    log_file = os.path.join(backup_folder, "backup_log.log")
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

                if engine == "7Z":
                    cmd, result = run_7z(archiver, archive_path, source)
                    logger.info("COMMAND    : %s", " ".join(cmd))
                    logger.info("RETURNCODE : %s", result.returncode)

                    if result.stdout:
                        logger.info("STDOUT:\n%s", result.stdout)
                    if result.stderr:
                        logger.warning("STDERR:\n%s", result.stderr)

                    if result.returncode == 0:
                        logger.info("SUCCESS")
                    elif result.returncode == 1:
                        logger.warning("SUCCESS WITH WARNINGS")
                    else:
                        raise RuntimeError(f"7z return code={result.returncode}")

                elif engine == "ZIP":
                    logger.info(f"Creating ZIP archive with subdirs={subdirs}")
                    returncode, file_falliti, file_successo = run_zip(
                        archive_path, source, subdirs, logger
                    )

                    if file_falliti:
                        logger.warning(
                            f"Files failed to archive ({len(file_falliti)}):"
                        )
                        for ff in file_falliti:
                            logger.warning(f"  - {ff['file']}: {ff['errore']}")

                    if returncode == 0:
                        logger.info(f"SUCCESS ({file_successo} files archived)")
                    else:
                        if file_successo > 0:
                            logger.warning(
                                f"PARTIAL SUCCESS ({file_successo} files archived, "
                                f"{len(file_falliti)} failed)"
                            )
                        else:
                            raise RuntimeError("ZIP archive creation failed")

                else:
                    cmd, result = run_tar(archive_path, source)
                    logger.info("COMMAND    : %s", " ".join(cmd))
                    logger.info("RETURNCODE : %s", result.returncode)

                    if result.stdout:
                        logger.info("STDOUT:\n%s", result.stdout)
                    if result.stderr:
                        logger.warning("STDERR:\n%s", result.stderr)

                    if result.returncode == 0:
                        logger.info("SUCCESS")
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
