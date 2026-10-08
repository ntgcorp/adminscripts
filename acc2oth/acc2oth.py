"""acc2oth — Access .accdb -> File Singoli.

Eseguibile single-file conforme a prompt_acc2oth.md capp. 1-8 + appendici.

Uso:
    python acc2oth.py <file.ini> [openrouter.key]
    python -m acc2oth <file.ini> [openrouter.key]   (se installato come package con __main__ che riusa questo file)

    file.ini ......... Path al file INI [CONFIG] (required).
    openrouter.key ... Chiave OpenRouter (facoltativa): se passata, si sovrappone
                       a OPENROUTER.KEY del .ini nel dictConfig finale.
                       Serve quando EXP.PROMPT=True o EXP.PYTHON=True o EXP.JAVA=True
                       e il .ini non contiene la chiave (OPENROUTER.KEY facoltativa nel .ini).

Workflow: app_args -> app_verify -> app_export -> app_tables -> app_prompt -> app_python -> app_java -> app_end.
Ogni app_* ritorna sResult ("" = ok, altrimenti messaggio di errore).
Exit code: 0 ok, 1 errore estrazione, 2 errore validazione/config.
"""

from __future__ import annotations

import argparse
import configparser
import datetime
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Costanti Access (SaveAsText) — cfr. prompt cap. 4.1
AC_FORM = 2
AC_REPORT = 3
AC_MACRO = 4
AC_MODULE = 5
AC_QUERY = 1
AC_DATA_ACCESS_PAGE = 6

# Tipi VBComponent (VBE) — per distinguere moduli standard da classi
VBEXT_CT_STDMODULE = 1
VBEXT_CT_CLASSMODULE = 2

EXPORT_ORDER = ("FORMS", "MODULES", "CLASSES", "QUERYES", "MACROS", "REPORTS", "TABLES")
SUBDIR = {
    "FORMS": "forms",
    "MODULES": "modules",
    "CLASSES": "classes",
    "QUERYES": "queryes",
    "MACROS": "macros",
    "REPORTS": "reports",
    "TABLES": "tables",
}
EXT = {
    "FORMS": ".txt",
    "MODULES": ".bas",
    "CLASSES": ".cls",
    "QUERYES": ".sql",
    "MACROS": ".txt",
    "REPORTS": ".txt",
    "TABLES": ".csv",
}

TRUE_SET = {"true", "1", "yes", "si", "sì", "y", "on"}
FALSE_SET = {"false", "0", "no", "n", "off"}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SANITIZE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Sanitizza un nome oggetto Access per uso come nome file."""
    cleaned = _SANITIZE_RE.sub("_", name).strip().rstrip(". ")
    return cleaned if cleaned else "unnamed"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    raise ValueError(f"Valore booleano non riconosciuto: {value!r}")


def parse_csv_upper(value: Any) -> list[str]:
    """Split su ',', strip, upper, rimuovi vuoti, dedup mantenendo ordine."""
    if value is None:
        return []
    items: list[str] = []
    seen: set[str] = set()
    for part in str(value).split(","):
        p = part.strip().upper()
        if p and p not in seen:
            seen.add(p)
            items.append(p)
    return items


def _err_text(e: Exception) -> str:
    """Testo errore leggibile anche per com_error/AttributeError COM (str vuoto)."""
    s = str(e).strip()
    return s if s else repr(e)


def new_state() -> dict:
    return {
        "files": {k.lower(): [] for k in EXPORT_ORDER},
        "counts": {k.lower(): 0 for k in EXPORT_ORDER} | {"skipped_tables": 0},
        "errors": [],
        "_fallback_seen": set(),  # nomi upper gia tentati via fallback AllModules
    }


# ---------------------------------------------------------------------------
# app_args — lettura INI -> dict
# ---------------------------------------------------------------------------

def app_args(file_ini: str | Path, cli_key: str = "") -> tuple[dict, str]:
    """Legge il .ini e lo carica nel dictConfig. Ritorna (config, sResult).

    Il file .ini viene caricato alla partenza in un dizionario dictConfig.
    OPENROUTER.KEY e facoltativa nel .ini; se `cli_key` (2o parametro CLI)
    e non vuota, si sovrappone a dictConfig["OPENROUTER.KEY"].
    La presenza obbligatoria della chiave e verificata in app_verify()
    solo quando EXP.PROMPT=True o EXP.PYTHON=True.
    """
    ini_path = Path(str(file_ini))
    if not ini_path.is_file():
        return {}, f"File INI non trovato: {ini_path}"
    parser = configparser.ConfigParser(strict=True)
    parser.optionxform = str  # normalizziamo manualmente
    try:
        with open(ini_path, "r", encoding="utf-8") as f:
            parser.read_file(f)
    except (configparser.Error, OSError, UnicodeDecodeError) as e:
        return {}, f"INI malformato o illeggibile ({ini_path}): {e}"
    if "CONFIG" not in parser:
        return {}, "Sezione [CONFIG] mancante nel file INI"

    raw = dict(parser["CONFIG"])
    # Normalizza solo le chiavi (upper + trim); valori path invariati (solo strip laterale).
    norm: dict[str, str] = {}
    for k, v in raw.items():
        norm[k.strip().upper()] = v.strip() if isinstance(v, str) else v

    config: dict[str, Any] = {
        "INI_PATH": str(ini_path.resolve()),
        "INI_DIR": str(ini_path.resolve().parent),
        "IN.ACCDB": norm.get("IN.ACCDB", ""),
        "OUT.PATH": norm.get("OUT.PATH", ""),
        "LOG": norm.get("LOG", "export.log"),
        "OPENROUTER.KEY": norm.get("OPENROUTER.KEY", ""),
        "OPENROUTER.MODEL": norm.get("OPENROUTER.MODEL", ""),
        "EXP.PROMPT.LIST": parse_csv_upper(norm.get("EXP.PROMPT.LIST", "")),
        "EXP.PYTHON.LIST": parse_csv_upper(norm.get("EXP.PYTHON.LIST", "")),
        "EXP.JAVA.LIST": parse_csv_upper(norm.get("EXP.JAVA.LIST", "")),
        "EXP.TABLES.LIST": parse_csv_upper(norm.get("EXP.TABLES.LIST", "")),
    }
    # Flag EXP.* (default False); QUERIES e canonico, QUERYES alias storico deprecato.
    for cat in EXPORT_ORDER:
        key = f"EXP.{cat}"
        raw_val = norm.get(key, None)
        if cat == "QUERYES":
            # Parametro canonico EXP.QUERIES; EXP.QUERYES tollerato come deprecato.
            canon = norm.get("EXP.QUERIES", None)
            legacy = norm.get("EXP.QUERYES", None)
            if canon is not None and legacy is not None and canon != legacy:
                config["_QUERIES_ALIAS_WARNING"] = "both"
            elif legacy is not None and canon is None:
                config["_QUERIES_ALIAS_WARNING"] = "legacy"
            raw_val = canon if canon is not None else legacy
            key = "EXP.QUERIES"
        try:
            val = parse_bool(raw_val) if raw_val not in (None, "") else False
        except ValueError:
            return {}, f"Flag {key} non booleano: {raw_val!r} (usare True/False)"
        config[f"EXP.{cat}"] = val
        if cat == "QUERYES":
            config["EXP.QUERIES"] = val  # alias canonico sullo stesso valore
    if "_QUERIES_ALIAS_WARNING" not in config and "EXP.QUERIES" in norm and "EXP.QUERYES" in norm:
        config["_QUERIES_ALIAS_WARNING"] = "both"
    for extra in ("EXP.PROMPT", "EXP.PYTHON", "EXP.JAVA", "EXP.TABLES"):
        try:
            config[extra] = parse_bool(norm.get(extra, "False"))
        except ValueError:
            return {}, f"Flag {extra} non booleano: {norm.get(extra)!r}"

    # Validazione LIST: se LIST presente ma flag False -> errore
    for flag, list_key in (("EXP.TABLES", "EXP.TABLES.LIST"), ("EXP.JAVA", "EXP.JAVA.LIST"),
                           ("EXP.PROMPT", "EXP.PROMPT.LIST"), ("EXP.PYTHON", "EXP.PYTHON.LIST")):
        if config.get(list_key) and not config.get(flag):
            return {}, f"{list_key} specificata ma {flag}=False (deve essere True)"

    # Override OPENROUTER.KEY da 2o parametro CLI (se passato e non vuoto).
    # OPENROUTER.KEY e facoltativa nel .ini: il dictConfig finale deve
    # contenerla (non vuota) solo se EXP.PROMPT=True o EXP.PYTHON=True o EXP.JAVA=True.
    cli_key = (cli_key or "").strip()
    if cli_key:
        config["OPENROUTER.KEY"] = cli_key
        config["_KEY_SOURCE"] = "cli"
    else:
        config["_KEY_SOURCE"] = "ini"

    if not config["IN.ACCDB"]:
        return {}, "Parametro IN.ACCDB mancante o vuoto"
    if not config["OUT.PATH"]:
        return {}, "Parametro OUT.PATH mancante o vuoto"
    return config, ""


# ---------------------------------------------------------------------------
# app_verify — verifica parametri, crea OUT.PATH, risolve LOG
# ---------------------------------------------------------------------------

def _resolve(p: str, base: Path) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (base / path)


def app_verify(config: dict) -> str:
    """Verifica parametri e prepara path. Ritorna sResult."""
    ini_dir = Path(config["INI_DIR"])
    accdb = _resolve(config["IN.ACCDB"], ini_dir)
    if not accdb.is_file():
        return f"IN.ACCDB non trovato o non leggibile: {accdb}"
    if accdb.suffix.lower() not in (".accdb", ".mdb"):
        return f"IN.ACCDB deve avere estensione .accdb/.mdb: {accdb}"
    config["_ACCDB"] = str(accdb.resolve())

    out = _resolve(config["OUT.PATH"], ini_dir)
    try:
        ensure_dir(out)
    except OSError as e:
        return f"OUT.PATH non creabile: {out} ({e})"
    # Verifica scrivibilita con file probe.
    try:
        probe = out / ".acc2oth_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as e:
        return f"OUT.PATH non scrivibile: {out} ({e})"
    config["_OUT"] = str(out.resolve())

    log_raw = config.get("LOG", "export.log") or "export.log"
    log_path = Path(log_raw)
    if not log_path.is_absolute():
        log_path = out / log_path
    try:
        ensure_dir(log_path.parent)
    except OSError as e:
        return f"Directory di LOG non creabile: {log_path.parent} ({e})"
    config["_LOG"] = str(log_path.resolve())

    if config.get("EXP.PROMPT") or config.get("EXP.PYTHON") or config.get("EXP.JAVA"):
        if not (config.get("OPENROUTER.KEY") or "").strip():
            return ("OPENROUTER.KEY richiesta nel dictConfig finale quando "
                    "EXP.PROMPT=True o EXP.PYTHON=True o EXP.JAVA=True: impostarla nel .ini "
                    "oppure passarla come 2o parametro CLI "
                    "(python -m acc2oth <file.ini> <openrouter.key>)")
        if not config.get("OPENROUTER.MODEL"):
            return "OPENROUTER.MODEL richiesto quando EXP.PROMPT=True o EXP.PYTHON=True o EXP.JAVA=True"
    return ""


def setup_logger(log_path: str | Path) -> logging.Logger:
    logger = logging.getLogger("acc2oth")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    try:
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning("Impossibile aprire LOG %s in append: %s", log_path, e)
    return logger


# ---------------------------------------------------------------------------
# COM helpers
# ---------------------------------------------------------------------------

def _collection_names(coll: Any) -> list[str]:
    """Estrae i nomi da una collezione COM Access (AllForms, AllReports, ...)."""
    names: list[str] = []
    try:
        count = int(coll.Count)
        for i in range(count):
            try:
                names.append(str(coll.Item(i).Name))
            except Exception:
                continue
        return names
    except Exception:
        pass
    try:
        for item in coll:
            try:
                names.append(str(item.Name))
            except Exception:
                continue
    except Exception:
        pass
    return names


def _unique_path(directory: Path, base: str, ext: str, used: set[str]) -> Path:
    """Ritorna un path univoco gestendo collisioni post-sanitizzazione."""
    candidate = directory / f"{base}{ext}"
    n = 1
    while candidate.name.lower() in used or candidate.exists() and candidate.name.lower() in used:
        # Nota: overwrite implicito sui file esportati (spec cap. 3.1), ma
        # collisioni tra nomi diversi sanitizzati uguali prendono suffisso.
        n += 1
        candidate = directory / f"{base}_{n}{ext}"
        if n > 999:
            break
    used.add(candidate.name.lower())
    return candidate


# ---------------------------------------------------------------------------
# app_export
# ---------------------------------------------------------------------------

def app_export(config: dict, logger: logging.Logger, state: dict) -> str:
    """Esporta oggetti Access via COM. Errori su singolo oggetto non abortiscono."""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return "Microsoft Access COM automation non disponibile: installare Access/pywin32 (win32com.client)"

    out = Path(config["_OUT"])
    accdb = config["_ACCDB"]
    errors: list[dict] = state["errors"]
    used: dict[str, set[str]] = {k.lower(): set() for k in EXPORT_ORDER}

    try:
        app = win32com.client.Dispatch("Access.Application")
    except Exception as e:
        return f"Impossibile avviare Access.Application (Access installato?): {e}"

    def record(cat: str, name: str, file_object: str) -> None:
        entry = {"name": name, "file_object": file_object,
                 "file_prompt": None, "file_python": None}
        state["files"][cat.lower()].append(entry)
        state["counts"][cat.lower()] += 1

    try:
        try:
            app.AutomationSecurity = 1
        except Exception as e:
            logger.warning("AutomationSecurity=1 non impostabile: %s", e)
        # Fase specifica di apertura database (log + console): esito sempre registrato.
        logger.info("Fase apertura database: %s (sola lettura, Exclusive=False)...", accdb)
        try:
            app.OpenCurrentDatabase(os_path(accdb), Exclusive=False)
        except Exception as e:
            logger.error("Fase apertura database FALLITA: %s", _err_text(e))
            msg = str(e)
            if "already in use" in msg or "Could not use" in msg or "bloccato" in msg.lower():
                return f"Database bloccato/in uso (chiudere Access e riprovare): {_err_text(e)}"
            return f"Impossibile aprire IN.ACCDB {accdb}: {_err_text(e)}"
        logger.info("Fase apertura database OK: %s", accdb)

        wanted = [c for c in EXPORT_ORDER if config.get(f"EXP.{c}")]
        if not wanted:
            logger.warning("Nessun flag EXP.*=True: nessuna esportazione richiesta")

        # Tabelle: solo conteggio/skip, mai export.
        try:
            tables = list(app.CurrentDb().TableDefs)
            skipped = 0
            for t in tables:
                try:
                    tname = str(t.Name)
                except Exception:
                    continue
                if tname.startswith("MSys"):
                    continue
                skipped += 1
                try:
                    attrs = int(t.Attributes)
                    kind = "linked" if (attrs & 0x40000000 or attrs & 0x20000000) else "local"
                except Exception:
                    kind = "local"
                logger.info("Skipped table %s (type: %s)", tname, kind)
            state["counts"]["skipped_tables"] = skipped
        except Exception as e:
            logger.warning("Conteggio tabelle non riuscito: %s", e)

        if config.get("EXP.FORMS"):
            export_saveastext(app, logger, state, record, used, out,
                              "FORMS", AC_FORM, lambda: app.CurrentProject.AllForms, errors)
        if config.get("EXP.REPORTS_PLACEHOLDER"):
            pass  # mai usato; REPORTS gestito sotto nell'ordine corretto
        if config.get("EXP.MODULES"):
            export_modules_classes(app, logger, state, record, used, out,
                                   "MODULES", VBEXT_CT_STDMODULE, errors)
        if config.get("EXP.CLASSES"):
            export_modules_classes(app, logger, state, record, used, out,
                                   "CLASSES", VBEXT_CT_CLASSMODULE, errors)
        if config.get("EXP.QUERYES"):
            export_queries(app, logger, state, record, used, out, errors)
        if config.get("EXP.MACROS"):
            export_saveastext(app, logger, state, record, used, out,
                              "MACROS", AC_MACRO, lambda: app.CurrentProject.AllMacros, errors)
        if config.get("EXP.REPORTS"):
            export_saveastext(app, logger, state, record, used, out,
                              "REPORTS", AC_REPORT, lambda: app.CurrentProject.AllReports, errors)
    finally:
        try:
            try:
                app.CloseCurrentDatabase()
            except Exception:
                pass
            app.Quit()
        except Exception as e:
            logger.warning("Quit Access non riuscito: %s", e)
    if config.get("_QUERIES_ALIAS_WARNING") == "both":
        logger.warning("Alias: EXP.QUERIES prevale su EXP.QUERYES deprecato (usare QUERIES)")
    elif config.get("_QUERIES_ALIAS_WARNING") == "legacy":
        logger.warning("Alias deprecato EXP.QUERYES in uso: usare EXP.QUERIES")
    return ""


# ---------------------------------------------------------------------------
# app_tables — esporta tabelle in CSV
# ---------------------------------------------------------------------------

def app_tables(config: dict, logger: logging.Logger, state: dict) -> str:
    """Esporta tabelle Access in file CSV. Errori su singola tabella non abortiscono."""
    if not config.get("EXP.TABLES"):
        return ""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return "Microsoft Access COM automation non disponibile: installare Access/pywin32 (win32com.client)"

    out = Path(config["_OUT"])
    accdb = config["_ACCDB"]
    errors: list[dict] = state["errors"]
    wanted: set[str] = set(config.get("EXP.TABLES.LIST", []))

    try:
        app = win32com.client.Dispatch("Access.Application")
    except Exception as e:
        return f"Impossibile avviare Access.Application (Access installato?): {e}"

    def record_tables(name: str, file_object: str) -> None:
        entry = {"name": name, "file_object": file_object,
                 "file_prompt": None, "file_python": None, "file_java": None}
        state["files"]["tables"].append(entry)
        state["counts"]["tables"] += 1

    try:
        try:
            app.AutomationSecurity = 1
        except Exception as e:
            logger.warning("AutomationSecurity=1 non impostabile: %s", e)
        logger.info("Fase apertura database: %s (sola lettura, Exclusive=False)...", accdb)
        try:
            app.OpenCurrentDatabase(os_path(accdb), Exclusive=False)
        except Exception as e:
            logger.error("Fase apertura database FALLITA: %s", _err_text(e))
            msg = str(e)
            if "already in use" in msg or "Could not use" in msg or "bloccato" in msg.lower():
                return f"Database bloccato/in uso (chiudere Access e riprovare): {_err_text(e)}"
            return f"Impossibile aprire IN.ACCDB {accdb}: {_err_text(e)}"
        logger.info("Fase apertura database OK: %s", accdb)

        try:
            # Iterazione corretta della collezione TableDefs (COM è 1-based)
            db = app.CurrentDb()
            tdefs = []
            for i in range(1, db.TableDefs.Count + 1):
                try:
                    tdefs.append(db.TableDefs(i))
                except Exception:
                    continue
        except Exception as e:
            logger.error("Lettura TableDefs fallita: %s", _err_text(e))
            errors.append({"object_type": "Table", "object_name": "", "error": _err_text(e)})
            return ""

        names: list[str] = []
        user_tables: list[str] = []
        for t in tdefs:
            try:
                tname = str(t.Name)
            except Exception:
                continue
            if not tname.startswith("MSys"):
                user_tables.append(tname)
            if tname.startswith("MSys"):
                continue  # salta tabelle di sistema
            if wanted and tname.upper() not in wanted:
                continue
            names.append(tname)

        logger.info("Exporting TABLES (%d)", len(names))
        if wanted:
            logger.info("Filtro EXP.TABLES.LIST: %s. Tabelle utente nel DB: %s",
                        ", ".join(sorted(wanted)), ", ".join(user_tables))
        if wanted and not names:
            logger.warning("EXP.TABLES.LIST specificata (%s) ma nessuna tabella corrisponde. Tabelle disponibili: %s",
                           ", ".join(sorted(wanted)), ", ".join(user_tables) if user_tables else "(nessuna)")

        subdir = out / SUBDIR["TABLES"]
        ensure_dir(subdir)
        used_tables: set[str] = set()

        for tname in names:
            safe = sanitize_filename(tname)
            dest = _unique_path(subdir, safe, EXT["TABLES"], used_tables)
            try:
                rs = app.CurrentDb().OpenRecordset(f"SELECT * FROM [{tname}]")
                # Scrive CSV con intestazione
                fields = [f.Name for f in rs.Fields]
                lines = [",".join(fields)]
                while not rs.EOF:
                    row = []
                    for f in rs.Fields:
                        val = f.Value
                        if val is None:
                            row.append("")
                        else:
                            s = str(val).replace('"', '""')
                            if "," in s or '"' in s or "\n" in s:
                                s = f'"{s}"'
                            row.append(s)
                    lines.append(",".join(row))
                    rs.MoveNext()
                rs.Close()
                dest.write_text("\n".join(lines), encoding="utf-8")
                rel = dest.relative_to(out).as_posix()
                logger.info("Exported %s -> %s", tname, rel)
                record_tables(tname, rel)
            except Exception as e:
                logger.error("Export TABLE %r fallito: %s", tname, _err_text(e))
                errors.append({"object_type": "Table", "object_name": tname,
                               "error": f"CSV export failed: {_err_text(e)}"})
    finally:
        try:
            try:
                app.CloseCurrentDatabase()
            except Exception:
                pass
            app.Quit()
        except Exception as e:
            logger.warning("Quit Access non riuscito: %s", e)
    return ""


# ---------------------------------------------------------------------------
# app_java — genera file Java da moduli/classe VBA via OpenRouter
# ---------------------------------------------------------------------------

JAVA_SYSTEM = (
    "Sei un transpiler VBA->Java. Traduci il modulo .bas/.cls in Java 17+ idiomatico, "
    "preservando la logica: classi, metodi, cicli, condizioni, gestione errori. "
    "Usa record/optional/stream dove appropriato. "
    "Sostituisci DAO/ADODB con JDBC/Hibernate e MsgBox/InputBox con logging/exceptions. "
    "Restituisci SOLO codice Java, senza spiegazioni."
)


def app_java(config: dict, logger: logging.Logger, state: dict) -> str:
    if not config.get("EXP.JAVA"):
        return ""
    out = Path(config["_OUT"])
    api_key = config.get("OPENROUTER.KEY", "")
    model = config.get("OPENROUTER.MODEL", "")
    wanted: set[str] = set(config.get("EXP.JAVA.LIST", []))
    sources = _scan_vba_sources(out, wanted)
    if not sources:
        if wanted:
            logger.warning("EXP.JAVA=True ma nessun .bas/.cls corrisponde a EXP.JAVA.LIST=%s", sorted(wanted))
        else:
            logger.warning("EXP.JAVA=True ma nessun sorgente .bas/.cls trovato in modules/classes")
        return ""
    logger.info("Generating JAVA (%d) da modules/classes", len(sources))
    for src in sources:
        cat_key = "modules" if src.parent.name.lower() == "modules" else "classes"
        entry = _ensure_entry(state, cat_key, src, out)
        dest = src.parent / (src.stem + ".java")
        try:
            vba_code = src.read_text(encoding="utf-8", errors="ignore")
            rel_src = src.relative_to(out).as_posix()
            logger.info("OpenRouter JAVA start: %s (model=%s, src=%s, %d chars) -> %s",
                        entry["name"], model, rel_src, len(vba_code), dest.relative_to(out).as_posix())
            t0 = time.monotonic()
            content, usage = _openrouter_chat(api_key, model, JAVA_SYSTEM,
                                              f"Ecco il codice VBA (.bas/.cls):\n\n```vba\n{vba_code}\n```")
            dt = time.monotonic() - t0
            dest.write_text(content, encoding="utf-8")
            entry["file_java"] = dest.relative_to(out).as_posix()
            logger.info("OpenRouter JAVA done: %s in %s | model=%s | tokens prompt=%s completion=%s total=%s | cost=$%.6f | -> %s",
                        entry["name"], _fmt_elapsed(dt), usage.get("model", model),
                        usage.get("prompt_tokens"), usage.get("completion_tokens"),
                        usage.get("total_tokens"), usage.get("cost", 0.0), entry["file_java"])
        except Exception as e:
            logger.error("Java %r fallito: %s", entry["name"], e)
            state["errors"].append({"object_type": "Java", "object_name": entry["name"],
                                    "error": str(e)})
    return ""


def os_path(p: str) -> str:
    return str(Path(p))


def export_saveastext(app: Any, logger: logging.Logger, state: dict,
                      record: Any, used: dict, out: Path,
                      cat: str, ac_type: int, get_coll: Any,
                      errors: list[dict]) -> None:
    subdir = out / SUBDIR[cat]
    ensure_dir(subdir)
    try:
        names = _collection_names(get_coll())
    except Exception as e:
        logger.error("Lettura collezione %s fallita: %s", cat, e)
        errors.append({"object_type": cat.title(), "object_name": "", "error": str(e)})
        return
    logger.info("Exporting %s (%d)", cat, len(names))
    for name in names:
        safe = sanitize_filename(name)
        dest = _unique_path(subdir, safe, EXT[cat], used[cat.lower()])
        try:
            # SaveAsText e un metodo di Application, NON di DoCmd.
            app.SaveAsText(ac_type, name, str(dest))
            rel = dest.relative_to(out).as_posix()
            logger.info("Exported %s -> %s", name, rel)
            record(cat, name, rel)
        except Exception as e:
            logger.error("Export %s %r fallito: %s", cat, name, _err_text(e))
            errors.append({"object_type": cat.title(), "object_name": name,
                           "error": f"SaveAsText failed: {_err_text(e)}"})


def export_modules_classes(app: Any, logger: logging.Logger, state: dict,
                           record: Any, used: dict, out: Path,
                           cat: str, vb_type: int, errors: list[dict]) -> None:
    """Esporta moduli standard (type 1) o classi (type 2) via VBE.Export, fallback SaveAsText."""
    subdir = out / SUBDIR[cat]
    ensure_dir(subdir)
    comps: list[tuple[str, int, Any]] = []
    try:
        vbproj = app.VBE.ActiveVBProject
        count = int(vbproj.VBComponents.Count)
        # VBComponents e 1-based (Item(1)..Item(Count)).
        for i in range(1, count + 1):
            try:
                comp = vbproj.VBComponents.Item(i)
                comps.append((str(comp.Name), int(comp.Type), comp))
            except Exception:
                continue
    except Exception as e:
        logger.warning("VBE non accessibile (abilitare trust VBA?), fallback SaveAsText acModule: %s", _err_text(e))
        comps = []
    if not comps:
        # Fallback: AllModules via SaveAsText (non distingue classi; usato solo se VBE chiuso).
        try:
            names = _collection_names(app.CurrentProject.AllModules)
        except Exception as e:
            logger.error("Lettura AllModules fallita: %s", _err_text(e))
            errors.append({"object_type": cat.title(), "object_name": "", "error": _err_text(e)})
            return
        # I nomi componente VBA sono unici per progetto: evita di tentare due volte
        # lo stesso oggetto quando sia MODULES che CLASSES usano il fallback.
        seen: set[str] = state.setdefault("_fallback_seen", set())
        logger.info("Exporting %s (%d) via SaveAsText-fallback", cat, len(names))
        for name in names:
            if name.upper() in seen:
                logger.info("Skip %s (gia tentato via fallback)", name)
                continue
            seen.add(name.upper())
            safe = sanitize_filename(name)
            dest = _unique_path(subdir, safe, EXT[cat], used[cat.lower()])
            try:
                app.SaveAsText(AC_MODULE, name, str(dest))
                rel = dest.relative_to(out).as_posix()
                logger.info("Exported %s -> %s", name, rel)
                record(cat, name, rel)
            except Exception as e:
                logger.error("Export %s %r fallito: %s", cat, name, _err_text(e))
                errors.append({"object_type": cat.title(), "object_name": name,
                               "error": f"SaveAsText failed: {_err_text(e)}"})
        return
    selected = [(n, c) for (n, t, c) in comps if t == vb_type]
    logger.info("Exporting %s (%d)", cat, len(selected))
    for name, comp in selected:
        safe = sanitize_filename(name)
        dest = _unique_path(subdir, safe, EXT[cat], used[cat.lower()])
        try:
            comp.Export(str(dest))
            rel = dest.relative_to(out).as_posix()
            logger.info("Exported %s -> %s", name, rel)
            record(cat, name, rel)
        except Exception as e:
            # Ultimo fallback: SaveAsText su Application (non DoCmd).
            try:
                app.SaveAsText(AC_MODULE, name, str(dest))
                rel = dest.relative_to(out).as_posix()
                logger.info("Exported %s -> %s (SaveAsText)", name, rel)
                record(cat, name, rel)
            except Exception as e2:
                logger.error("Export %s %r fallito: %s / %s", cat, name, _err_text(e), _err_text(e2))
                errors.append({"object_type": cat.title(), "object_name": name,
                               "error": f"Export failed: {_err_text(e)} / {_err_text(e2)}"})


def export_queries(app: Any, logger: logging.Logger, state: dict,
                   record: Any, used: dict, out: Path, errors: list[dict]) -> None:
    subdir = out / SUBDIR["QUERYES"]
    ensure_dir(subdir)
    try:
        qdefs = list(app.CurrentDb().QueryDefs)
    except Exception as e:
        logger.error("Lettura QueryDefs fallita: %s", _err_text(e))
        errors.append({"object_type": "Query", "object_name": "", "error": _err_text(e)})
        return
    names: list[tuple[str, Any]] = []
    for q in qdefs:
        try:
            qname = str(q.Name)
        except Exception:
            continue
        if qname.startswith("~") or qname.startswith("MSys"):
            continue
        names.append((qname, q))
    logger.info("Exporting QUERYES (%d)", len(names))
    for qname, q in names:
        safe = sanitize_filename(qname)
        dest = _unique_path(subdir, safe, EXT["QUERYES"], used["queryes"])
        try:
            sql = str(q.SQL)
            dest.write_text(sql, encoding="utf-8")
            rel = dest.relative_to(out).as_posix()
            logger.info("Exported %s -> %s", qname, rel)
            record("QUERYES", qname, rel)
        except Exception as e:
            logger.error("Export Query %r fallito: %s", qname, _err_text(e))
            errors.append({"object_type": "Query", "object_name": qname, "error": _err_text(e)})


# ---------------------------------------------------------------------------
# OpenRouter (app_prompt / app_python)
# ---------------------------------------------------------------------------

PROMPT_SYSTEM = (
    "Sei uno specialista in refactoring da VBA/Access a Python. "
    "Analizza il codice del modulo .bas/.cls fornitoti. NON generare codice Python. "
    "Il tuo compito e creare un PROMPT DI GENERAZIONE (System Prompt / Specifica Tecnica) "
    "estremamente dettagliato che permettera a uno sviluppatore o a un altro LLM di riscrivere "
    "da zero la logica in Python.\n\n"
    "Il prompt prodotto deve definire:\n"
    "1. Scopo e workflow del modulo.\n"
    "2. Input/Output (tabelle, query, file esterni gestiti).\n"
    "3. Regole di business, formule, cicli e gestione eccezioni.\n"
    "4. Librerie e architettura Python suggerite (es. pandas, openpyxl, sqlalchemy)."
)

PYTHON_SYSTEM = (
    "Sei un transpiler VBA->Python. Traduci il modulo .bas/.cls in Python 3.10+ idiomatico, "
    "preservando la logica: funzioni, cicli, condizioni, gestione errori. Usa type hints, "
    "logging, pathlib. Sostituisci DAO/ADODB con sqlalchemy/pandas e MsgBox/InputBox con "
    "logging/exceptions. Restituisci SOLO codice Python, senza spiegazioni."
)


def _fmt_elapsed(seconds: float) -> str:
    """Formatta durata in 'Xm SSs' (es. 1m 48s)."""
    total = int(seconds)
    mm, ss = divmod(total, 60)
    return f"{mm}m {ss:02d}s"


def _extract_usage(data: dict) -> dict:
    """Estrae {prompt_tokens, completion_tokens, total_tokens, cost} dalla risposta OpenRouter."""
    usage = data.get("usage", {}) or {}
    try:
        cost = float(usage.get("cost", 0.0) or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    return {
        "prompt_tokens": usage.get("prompt_tokens", "?"),
        "completion_tokens": usage.get("completion_tokens", "?"),
        "total_tokens": usage.get("total_tokens", "?"),
        "cost": cost,
    }


def _openrouter_chat(api_key: str, model: str, system: str, user_content: str) -> tuple[str, dict]:
    try:
        import requests  # type: ignore
    except ImportError as e:
        raise RuntimeError("Dipendenza 'requests' mancante: pip install requests") from e
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err: Optional[Exception] = None
    last_body: str = ""
    tried_fallback = False
    effective_model = model
    for attempt in (1, 2):  # retry singolo su 429/5xx
        try:
            # payload usa sempre il model effettivo (con eventuale fallback)
            payload["model"] = effective_model
            resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
            if resp.status_code in (429, 500, 502, 503) and attempt == 1:
                time.sleep(3)
                continue
            if not resp.ok:
                try:
                    j = resp.json()
                    last_body = str(j.get("error", {}).get("message") or j)[:1500]
                except Exception:
                    last_body = (resp.text or "")[:1500]
                lb = last_body.lower()
                if resp.status_code == 404 and "paid" in lb and "training" in lb:
                    hint = " | Azione: https://openrouter.ai/settings/privacy -> abilita 'Allow training on paid models', oppure imposta OPENROUTER.MODEL=meta/muse-spark-1.3"
                    if hint not in last_body:
                        last_body += hint
                    if not tried_fallback and effective_model.endswith("-contributor"):
                        tried_fallback = True
                        base = effective_model[: -len("-contributor")]
                        last_body += f" | Fallback automatico su {base}..."
                        effective_model = base
                        payload["model"] = effective_model
                        try:
                            resp2 = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
                            if resp2.ok:
                                data2 = resp2.json()
                                content2 = str(data2["choices"][0]["message"]["content"])
                                usage2 = _extract_usage(data2)
                                usage2["model"] = effective_model
                                return content2, usage2
                            try:
                                j2 = resp2.json()
                                last_body = str(j2.get("error", {}).get("message") or j2)[:1500]
                            except Exception:
                                last_body = (resp2.text or "")[:1500]
                            resp2.raise_for_status()
                        except Exception as e2:
                            if last_body and last_body not in str(e2):
                                e2 = RuntimeError(f"{e2} | OpenRouter: {last_body}")
                            raise e2
                resp.raise_for_status()
            data = resp.json()
            usage = _extract_usage(data)
            usage["model"] = effective_model
            return str(data["choices"][0]["message"]["content"]), usage
        except Exception as e:
            if last_body and last_body not in str(e):
                e = RuntimeError(f"{e} | OpenRouter: {last_body}")
            last_err = e
            if attempt == 1 and "404" not in str(e):
                time.sleep(3)
                continue
            raise
    raise RuntimeError(f"OpenRouter fallito: {last_err}")


def _scan_vba_sources(out: Path, wanted: set[str]) -> list[Path]:
    """Scansiona OUT.PATH/modules/*.bas e OUT.PATH/classes/*.cls sul filesystem.
    Ignora i file prompt_*.md e filtra su stem upper se wanted non vuoto."""
    result: list[Path] = []
    for sub, ext in (("modules", ".bas"), ("classes", ".cls")):
        d = out / sub
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() != ext:
                continue
            if p.name.lower().startswith("prompt_"):
                continue
            if wanted and p.stem.upper() not in wanted:
                continue
            result.append(p)
    result.sort(key=lambda p: (p.parent.name.lower(), p.name.lower()))
    return result


def _ensure_entry(state: dict, cat_key: str, src: Path, out: Path) -> dict:
    """Trova o crea l'entry di index per il sorgente filesystem."""
    rel_src = src.relative_to(out).as_posix()
    entry = next(
        (e for e in state["files"][cat_key]
         if e.get("file_object") == rel_src or str(e.get("name", "")).upper() == src.stem.upper()),
        None,
    )
    if entry is None:
        entry = {"name": src.stem, "file_object": rel_src, "file_prompt": None, "file_python": None, "file_java": None}
        state["files"][cat_key].append(entry)
        state["counts"][cat_key] = state["counts"].get(cat_key, 0) + 1
    else:
        # Aggiorna file_object se era None o diverso (caso entry legacy)
        if not entry.get("file_object"):
            entry["file_object"] = rel_src
    return entry


def _iter_vba_entries(config: dict, state: dict, list_key: str) -> list[tuple[str, dict]]:
    """DEPRECATO: ora app_prompt/python scansionano il filesystem (cfr. prompt 3.2).
    Mantenuto per compatibilita esterna."""
    wanted: set[str] = set(config.get(list_key, []))
    out: list[tuple[str, dict]] = []
    for cat in ("modules", "classes"):
        for entry in state["files"].get(cat, []):
            if wanted and str(entry["name"]).upper() not in wanted:
                continue
            out.append((cat, entry))
    return out


def app_prompt(config: dict, logger: logging.Logger, state: dict) -> str:
    if not config.get("EXP.PROMPT"):
        return ""
    out = Path(config["_OUT"])
    api_key = config.get("OPENROUTER.KEY", "")
    model = config.get("OPENROUTER.MODEL", "")
    wanted: set[str] = set(config.get("EXP.PROMPT.LIST", []))
    sources = _scan_vba_sources(out, wanted)
    if not sources:
        if not (out / "modules").is_dir() and not (out / "classes").is_dir():
            logger.warning("EXP.PROMPT=True ma nessuna cartella modules/classes in %s", out)
        elif wanted:
            logger.warning("EXP.PROMPT=True ma nessun .bas/.cls corrisponde a EXP.PROMPT.LIST=%s", sorted(wanted))
        else:
            logger.warning("EXP.PROMPT=True ma nessun sorgente .bas/.cls trovato in modules/classes")
        return ""
    logger.info("Generating PROMPT (%d) da modules/classes", len(sources))
    for src in sources:
        cat_key = "modules" if src.parent.name.lower() == "modules" else "classes"
        entry = _ensure_entry(state, cat_key, src, out)
        prompt_name = f"prompt_{src.stem}.md"
        dest = src.parent / prompt_name
        try:
            vba_code = src.read_text(encoding="utf-8", errors="ignore")
            rel_src = src.relative_to(out).as_posix()
            logger.info("OpenRouter PROMPT start: %s (model=%s, src=%s, %d chars) -> %s",
                        entry["name"], model, rel_src, len(vba_code), dest.relative_to(out).as_posix())
            t0 = time.monotonic()
            content, usage = _openrouter_chat(api_key, model, PROMPT_SYSTEM,
                                              f"Ecco il codice VBA (.bas/.cls):\n\n```vba\n{vba_code}\n```")
            dt = time.monotonic() - t0
            dest.write_text(content, encoding="utf-8")
            entry["file_prompt"] = dest.relative_to(out).as_posix()
            logger.info("OpenRouter PROMPT done: %s in %s | model=%s | tokens prompt=%s completion=%s total=%s | cost=$%.6f | -> %s",
                        entry["name"], _fmt_elapsed(dt), usage.get("model", model),
                        usage.get("prompt_tokens"), usage.get("completion_tokens"),
                        usage.get("total_tokens"), usage.get("cost", 0.0), entry["file_prompt"])
        except Exception as e:
            logger.error("Prompt %r fallito: %s", entry["name"], e)
            state["errors"].append({"object_type": "Prompt", "object_name": entry["name"],
                                    "error": str(e)})
    return ""


def app_python(config: dict, logger: logging.Logger, state: dict) -> str:
    if not config.get("EXP.PYTHON"):
        return ""
    out = Path(config["_OUT"])
    api_key = config.get("OPENROUTER.KEY", "")
    model = config.get("OPENROUTER.MODEL", "")
    wanted: set[str] = set(config.get("EXP.PYTHON.LIST", []))
    sources = _scan_vba_sources(out, wanted)
    if not sources:
        if wanted:
            logger.warning("EXP.PYTHON=True ma nessun .bas/.cls corrisponde a EXP.PYTHON.LIST=%s", sorted(wanted))
        else:
            logger.warning("EXP.PYTHON=True ma nessun sorgente .bas/.cls trovato in modules/classes")
        return ""
    logger.info("Generating PYTHON (%d) da modules/classes", len(sources))
    for src in sources:
        cat_key = "modules" if src.parent.name.lower() == "modules" else "classes"
        entry = _ensure_entry(state, cat_key, src, out)
        dest = src.parent / (src.stem + ".py")
        try:
            vba_code = src.read_text(encoding="utf-8", errors="ignore")
            rel_src = src.relative_to(out).as_posix()
            logger.info("OpenRouter PYTHON start: %s (model=%s, src=%s, %d chars) -> %s",
                        entry["name"], model, rel_src, len(vba_code), dest.relative_to(out).as_posix())
            t0 = time.monotonic()
            content, usage = _openrouter_chat(api_key, model, PYTHON_SYSTEM,
                                              f"Ecco il codice VBA (.bas/.cls):\n\n```vba\n{vba_code}\n```")
            dt = time.monotonic() - t0
            dest.write_text(content, encoding="utf-8")
            entry["file_python"] = dest.relative_to(out).as_posix()
            logger.info("OpenRouter PYTHON done: %s in %s | model=%s | tokens prompt=%s completion=%s total=%s | cost=$%.6f | -> %s",
                        entry["name"], _fmt_elapsed(dt), usage.get("model", model),
                        usage.get("prompt_tokens"), usage.get("completion_tokens"),
                        usage.get("total_tokens"), usage.get("cost", 0.0), entry["file_python"])
        except Exception as e:
            logger.error("Python %r fallito: %s", entry["name"], e)
            state["errors"].append({"object_type": "Python", "object_name": entry["name"],
                                    "error": str(e)})
    return ""


# ---------------------------------------------------------------------------
# app_end — index.json
# ---------------------------------------------------------------------------

def app_end(config: dict, state: dict, logger: logging.Logger) -> str:
    out = Path(config["_OUT"])
    dest = out / "index.json"
    # Merge con index.json precedente: se il run corrente non ha esportato
    # (tutti EXP.*=False), state contiene solo le entry toccate da
    # app_prompt/app_python/app_java via _ensure_entry; senza merge si perderebbe
    # lo storico delle esportazioni precedenti.
    merged_files: dict[str, list[dict]] = {k.lower(): [] for k in EXPORT_ORDER}
    try:
        if dest.is_file():
            prev = json.loads(dest.read_text(encoding="utf-8"))
            for cat in merged_files:
                for e in (prev.get("files", {}).get(cat, []) or []):
                    if isinstance(e, dict) and e.get("name"):
                        merged_files[cat].append(dict(e))
    except Exception as e:
        logger.warning("Lettura index.json precedente fallita (ricreo): %s", e)
    for cat in merged_files:
        by_name: dict[str, dict] = {str(e["name"]).upper(): e for e in merged_files[cat]}
        for e in state["files"].get(cat, []):
            key = str(e.get("name", "")).upper()
            if not key:
                continue
            if key in by_name:
                cur = by_name[key]
                for f in ("file_object", "file_prompt", "file_python", "file_java"):
                    if e.get(f):
                        cur[f] = e[f]
                if not cur.get("file_object") and e.get("file_object"):
                    cur["file_object"] = e["file_object"]
            else:
                by_name[key] = dict(e)
        merged_files[cat] = sorted(by_name.values(), key=lambda x: str(x.get("name", "")).lower())
    counts = {cat: len(merged_files[cat]) for cat in merged_files}
    # skipped_tables: vale solo se export ha girato in questo run, altrimenti tieni lo storico
    try:
        prev_counts: dict = {}
        if dest.is_file():
            prev_counts = json.loads(dest.read_text(encoding="utf-8")).get("counts", {}) or {}
    except Exception:
        prev_counts = {}
    counts["skipped_tables"] = state["counts"].get("skipped_tables", 0) or prev_counts.get("skipped_tables", 0)
    index = {
        "source": Path(config["_ACCDB"]).as_posix(),
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config_ini": Path(config["INI_PATH"]).as_posix(),
        "counts": counts,
        "files": merged_files,
        "errors": state["errors"],
    }
    tmp = out / "index.json.tmp"
    try:
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(dest)
        logger.info("Wrote index.json (%d errors)", len(state["errors"]))
    except OSError as e:
        logger.error("Scrittura index.json fallita: %s", e)
        return f"Scrittura index.json fallita: {e}"
    return ""


# ---------------------------------------------------------------------------
# main / CLI
# ---------------------------------------------------------------------------

HELP_EPILOG = r"""\
esempi:
  python acc2oth.py ./config/test.ini
  python acc2oth.py C:\\path\\config.ini
  python acc2oth.py C:\\path\\config.ini sk-or-v1-TUA_CHIAVE
  python -m acc2oth ./config/test.ini
  python -m acc2oth ./config/test.ini sk-or-v1-TUA_CHIAVE

  Il 2o parametro (openrouter.key) e facoltativo e, se passato,
  si sovrappone a OPENROUTER.KEY del file .ini (utile per non
  salvare la chiave nel file di configurazione).

schema INI minimo = schema di esempio (sezione [CONFIG]):
  tutti i parametri EXP possono essere False (nessuna esportazione/generazione).
  EXP.PROMPT.LIST / EXP.PYTHON.LIST / EXP.JAVA.LIST / EXP.TABLES.LIST sono facoltativi:
  nomi oggetto separati da "," (case-insensitive); se assenti o vuoti = tutti i .bas/.cls trovati.
  EXP.TABLES.LIST richiede EXP.TABLES=True; EXP.JAVA.LIST richiede EXP.JAVA=True.
  [CONFIG]
  IN.ACCDB=C:\path\db.accdb
  OUT.PATH=C:\path\out
  LOG=export.log
  EXP.FORMS=False
  EXP.MODULES=False
  EXP.CLASSES=False
  EXP.QUERIES=False
  EXP.MACROS=False
  EXP.REPORTS=False
  EXP.TABLES=False
  EXP.TABLES.LIST=Tabella1, Tabella2
  EXP.PROMPT=False
  EXP.PROMPT.LIST=Modulo1, Classe1
  EXP.PYTHON=False
  EXP.PYTHON.LIST=Modulo1, Classe1
  EXP.JAVA=False
  EXP.JAVA.LIST=Modulo1, Classe1
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="acc2oth",
        description="Access .accdb -> File Singoli (cfr. prompt_acc2oth.md). "
                    "Estrae Form/Moduli/Classi/Query/Macro/Report/Tabelle in file singoli sotto OUT.PATH.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # nargs="?" per gestire manualmente il caso "nessun parametro" con help completo (exit 2).
    p.add_argument("file_ini", nargs="?", default=None,
                   help="Path al file INI di configurazione ([CONFIG])")
    p.add_argument("openrouter_key", nargs="?", default=None,
                   help="Chiave OpenRouter (facoltativa): se passata, si sovrappone "
                        "a OPENROUTER.KEY del file .ini")
    return p


def show_help(parser: argparse.ArgumentParser) -> None:
    """Stampa help completo (usage + esempi + schema INI minimo)."""
    parser.print_help(sys.stderr)


def main(argv: Optional[list[str]] = None) -> int:
    # Filtra stringhe vuote: il launcher k:\Tools\pyn.cmd passa "%3" "%4"... anche
    # quando vuoti, producendo argv ["...", "ini", "", "", ...] -> "unrecognized arguments: "
    if argv is None:
        argv = [a for a in sys.argv[1:] if a != ""]
    else:
        argv = [a for a in argv if a != ""]
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.file_ini:
        print("ERRORE: manca il parametro <file.ini>.", file=sys.stderr)
        show_help(parser)
        return 2
    config, s = app_args(args.file_ini, args.openrouter_key or "")
    if s:
        print(f"ERRORE config: {s}", file=sys.stderr)
        if "non trovato" in s.lower() or "manca" in s.lower():
            show_help(parser)
        return 2
    s = app_verify(config)
    if s:
        print(f"ERRORE verifica: {s}", file=sys.stderr)
        return 2
    if config.get("_QUERIES_ALIAS_WARNING") == "both":
        print("WARNING: EXP.QUERIES prevale su EXP.QUERYES deprecato", file=sys.stderr)
    elif config.get("_QUERIES_ALIAS_WARNING") == "legacy":
        print("WARNING: EXP.QUERYES e deprecato, usare EXP.QUERIES", file=sys.stderr)
    logger = setup_logger(config["_LOG"])
    state = new_state()
    logger.info("acc2oth start: accdb=%s out=%s", config["_ACCDB"], config["_OUT"])
    if (config.get("EXP.PROMPT") or config.get("EXP.PYTHON") or config.get("EXP.JAVA")) and config.get("_KEY_SOURCE") == "cli":
        logger.info("OPENROUTER.KEY da CLI (override del valore .ini; valore non mostrato)")

    s = app_export(config, logger, state)
    if s:
        logger.error("app_export: %s", s)
        print(f"ERRORE estrazione: {s}", file=sys.stderr)
        try:
            app_end(config, state, logger)
        except Exception:
            pass
        return 1
    s = app_tables(config, logger, state)
    if s:
        logger.error("app_tables: %s", s)
        print(f"ERRORE export tabelle: {s}", file=sys.stderr)
        try:
            app_end(config, state, logger)
        except Exception:
            pass
        return 1
    s = app_prompt(config, logger, state)
    if s:
        logger.error("app_prompt: %s", s)
        return 1
    s = app_python(config, logger, state)
    if s:
        logger.error("app_python: %s", s)
        return 1
    s = app_java(config, logger, state)
    if s:
        logger.error("app_java: %s", s)
        return 1
    s = app_end(config, state, logger)
    if s:
        print(f"ERRORE finale: {s}", file=sys.stderr)
        return 1
    logger.info("acc2oth done: %s", json.dumps(state["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
