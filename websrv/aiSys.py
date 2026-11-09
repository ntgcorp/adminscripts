"""
aiSys.py - Modulo di supporto monolitico per aiJobsOS2
Contiene funzioni di base, timestamp, configurazione, I/O, stringhe, 
conversione dizionari e classe di logging.
Zero dipendenze esterne. Python 3.10+
"""

import os
import sys
import re
import csv
import json
import configparser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

# ============================================================================
# FUNZIONI DI BASE (aiSysBase.py)
# ============================================================================

def ErrorProc(sResult: str, sProc: str) -> str:
    """Restituisce sResult con prefisso di procedura se non vuoto."""
    if sResult:
        return f"{sProc}: Errore {sResult}"
    return sResult

# Alias per compatibilità con specifiche interne
loc_ErrorProc = ErrorProc

def DictMerge(dictSource: Dict, dictAdd: Dict) -> Dict:
    """Unisce dictAdd a dictSource. Priorità a dictAdd."""
    if not dictAdd:
        return dictSource
    if not dictSource:
        return dictAdd.copy()
    for k, v in dictAdd.items():
        dictSource[k] = v
    return dictSource

def DictExist(dictParam: Any, sKey: str, xDefault: Any = None) -> Any:
    """Restituisce valore di chiave o default."""
    if not isinstance(dictParam, dict):
        return xDefault
    return dictParam.get(sKey, xDefault)

# ============================================================================
# FUNZIONI TIMESTAMP (aiSysTimestamp.py)
# ============================================================================

def Timestamp(sPostfix: str = "") -> str:
    """Restituisce timestamp AAAAMMGG:HHMMSS opzionalmente con postfix."""
    sProc = "Timestamp"
    try:
        now = datetime.now()
        sResult = now.strftime("%Y%m%d:%H%M%S")
        if sPostfix:
            sResult = f"{sResult}:{sPostfix.lower()}"
        return sResult
    except Exception:
        return ""

def TimestampConvert(sTimestamp: str, sMode: str = "s") -> Union[int, float, None]:
    """Converte timestamp in secondi o giorni dall'epoch."""
    try:
        if not sTimestamp:
            sTimestamp = Timestamp("")
        if ':' not in sTimestamp:
            return None
        parts = sTimestamp.split(':')
        if len(parts) < 2:
            return None
        date_part, time_part = parts[0], parts[1]
        if len(date_part) != 8 or len(time_part) != 6:
            return None
        dt = datetime(
            int(date_part[0:4]), int(date_part[4:6]), int(date_part[6:8]),
            int(time_part[0:2]), int(time_part[2:4]), int(time_part[4:6])
        )
        epoch = datetime(1970, 1, 1)
        delta = (dt - epoch).total_seconds()
        return delta if sMode.lower() == "s" else delta / 86400.0
    except Exception:
        return None

def TimestampFromSeconds(nSeconds: int, sPostfix: str = "") -> str:
    """Converte secondi epoch in formato Timestamp."""
    try:
        dt = datetime(1970, 1, 1) + timedelta(seconds=nSeconds)
        sTs = dt.strftime("%Y%m%d:%H%M%S")
        return f"{sTs}:{sPostfix.lower()}" if sPostfix else sTs
    except Exception:
        return ""

def TimestampFromDays(nDays: float, sPostfix: str = "") -> str:
    """Converte giorni epoch in formato Timestamp."""
    try:
        return TimestampFromSeconds(int(nDays * 86400.0), sPostfix)
    except Exception:
        return ""

def TimestampValidate(sTimestamp: str) -> bool:
    """Valida formato timestamp."""
    try:
        if not sTimestamp or ':' not in sTimestamp:
            return False
        parts = sTimestamp.split(':')
        if len(parts) < 2:
            return False
        d, t = parts[0], parts[1]
        if len(d) != 8 or len(t) != 6:
            return False
        y, m, day = int(d[:4]), int(d[4:6]), int(d[6:8])
        h, mi, s = int(t[:2]), int(t[2:4]), int(t[4:6])
        if not (1 <= m <= 12 and 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s <= 59):
            return False
        days_in_month = [31, 29 if (y%4==0 and (y%100!=0 or y%400==0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return 1 <= day <= days_in_month[m-1]
    except Exception:
        return False

def TimestampDiff(sTimestamp1: str, sTimestamp2: str, sMode: str = "s") -> Union[int, float, None]:
    """Differenza tra due timestamp."""
    try:
        if not (TimestampValidate(sTimestamp1) and TimestampValidate(sTimestamp2)):
            return None
        sec1, sec2 = TimestampConvert(sTimestamp1, "s"), TimestampConvert(sTimestamp2, "s")
        if sec1 is None or sec2 is None:
            return None
        diff = abs(sec1 - sec2)
        return diff if sMode.lower() == "s" else diff / 86400.0
    except Exception:
        return None

def TimestampAdd(sTimestamp: str, nValue: Union[int, float], sUnit: str = "s") -> str:
    """Aggiunge tempo a un timestamp."""
    try:
        if not TimestampValidate(sTimestamp):
            return ""
        sec = TimestampConvert(sTimestamp, "s")
        if sec is None:
            return ""
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(sUnit.lower())
        if mult is None:
            return ""
        return TimestampFromSeconds(int(sec + nValue * mult))
    except Exception:
        return ""

def TimestampIsoFrom(ts: str, milliseconds: str = "000", tz: str = "Z") -> str:
    """Converte 'AAAAMMGG:HHMMSS' in ISO 8601."""
    date_part, time_part = ts.split(":")
    return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}T{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}.{milliseconds}{tz}"

def TimestampIsoTo(iso_ts: str) -> str:
    """Converte ISO 8601 in 'AAAAMMGG:HHMMSS'."""
    if iso_ts.endswith("Z"):
        iso_ts = iso_ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso_ts)
    return dt.strftime("%Y%m%d:%H%M%S")

# ============================================================================
# FUNZIONI CONFIGURAZIONE & ESPANSIONE (aiSysConfig.py)
# ============================================================================

def Expand(sText: str, dictConfig: Dict[str, str]) -> str:
    """Espande variabili e sequenze di escape."""
    sProc = "Expand"
    try:
        # Fase 1: Escape (ordine critico)
        sText = sText.replace('%##', '#')
        sText = sText.replace('%#', '"')
        sText = sText.replace('%%', '%')
        sText = sText.replace('%n', '\n')
        sText = sText.replace('%$', '$')
        
        # Fase 2: $SYS. e $ENV.
        def repl_sys_env(match):
            prefix = match.group(1)
            varname = match.group(2)
            if prefix == "ENV.":
                return os.environ.get(varname, "")
            elif prefix == "SYS.":
                sys_vars = {
                    "OS": os.name.upper(), "OS2": sys.platform,
                    "USER": os.environ.get("USERNAME", os.environ.get("USER", "")),
                    "COMPUTER": os.environ.get("COMPUTERNAME", ""),
                    "CD": os.getcwd(), "TEMP": os.environ.get("TEMP", ""),
                    "YYYYMMDD": datetime.now().strftime("%Y%m%d"),
                    "NOW": Timestamp()
                }
                return sys_vars.get(varname, "NOTFOUND")
            return match.group(0)
        sText = re.sub(r'\$(SYS\.|ENV\.)([A-Za-z0-9_]+)', repl_sys_env, sText)
        
        # Fase 3: $NOMEVAR da dictConfig
        def repl_config(match):
            varname = match.group(1)
            return dictConfig.get(varname, match.group(0))
        sText = re.sub(r'\$([A-Za-z0-9_]+)', repl_config, sText)
        
        return sText
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def ExpandConvert(sString: str) -> str:
    """Converte caratteri speciali in formato escape inverso."""
    sProc = "ExpandConvert"
    try:
        mapping = {'"': '%#', '#': '%##', '\n': '%n', '$': '%$', '\\': '%\\', '%': '%%'}
        res = []
        for ch in sString:
            res.append(mapping.get(ch, ch))
        return "".join(res)
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def ExpandDict(dictExpand: Dict, dictParam: Dict) -> Dict:
    """Espande valori di un dizionario usando Expand(). Max 1 livello."""
    sProc = "ExpandDict"
    try:
        result = dictExpand.copy()
        for k, v in result.items():
            if isinstance(v, dict):
                result[k] = {sk: Expand(sv, dictParam) for sk, sv in v.items()}
            elif isinstance(v, str):
                result[k] = Expand(v, dictParam)
        return result
    except Exception as e:
        print(f"{sProc}: {e}")
        return dictExpand

def isGroups(asGroups1: List[str], asGroups2: List[str]) -> bool:
    """True se almeno un elemento di asGroups1 è in asGroups2."""
    sProc = "isGroups"
    try:
        return bool(set(asGroups1) & set(asGroups2))
    except Exception as e:
        print(f"{sProc}: {e}")
        return False

def Config(dictConfig: Optional[Dict], sKey: str) -> str:
    """Legge chiave da dizionario config."""
    if not dictConfig or not isinstance(dictConfig, dict):
        return ""
    return dictConfig.get(sKey, "")

def ConfigDefault(dictConfig: Dict, sKey: str, xValue: Any) -> None:
    """Imposta default solo se chiave assente o vuota/None."""
    if not isinstance(dictConfig, dict):
        return
    curr = dictConfig.get(sKey)
    if curr is None or curr == "":
        dictConfig[sKey] = xValue

def SplitSettings(sString: str, dictConfig: Optional[Dict] = None) -> Dict[str, str]:
    """Parsa stringa CHIAVE=VALORE multipli."""
    sProc = "SplitSettings"
    try:
        sString = sString.replace('%n', '\n')
        items = re.split(r'[\s\n]+', sString.strip())
        result = {}
        for item in items:
            if '=' in item:
                k, v = item.split('=', 1)
                result[k.strip()] = v.strip()
        if dictConfig:
            result = ExpandDict(result, dictConfig)
        return result
    except Exception as e:
        print(f"{sProc}: {e}")
        return {}

def ConfigSet(dictConfig: Dict, sKey: str, xValue: Any = "") -> None:
    """Imposta o sostituisce chiave nel dizionario."""
    if isinstance(dictConfig, dict):
        dictConfig[sKey] = xValue

# ============================================================================
# FUNZIONI FILE I/O (aiSysFileio.py)
# ============================================================================

def NormalizePath(sPath: str) -> str:
    if not sPath: return ""
    if sys.platform == "win32":
        return os.path.normpath(sPath.replace("/", "\\"))
    return os.path.normpath(sPath.replace("\\", "/"))

def FileExists(sFile: str) -> bool:
    return os.path.isfile(sFile)

def FileDelete(sFile: str) -> str:
    sProc = "FileDelete"
    try:
        os.remove(sFile)
        return ""
    except Exception as e:
        return loc_ErrorProc(f"Cancellazione {sFile}: {e}", sProc)

def read_csv_to_dict(csv_file_path: str, asHeader: Optional[List[str]] = None, delimiter: str = ';') -> Tuple[str, Dict[str, Dict[str, str]]]:
    sProc = "read_csv_to_dict"
    try:
        if not FileExists(csv_file_path):
            return (f"File non valido {csv_file_path}", {})
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader, None)
            if not header:
                return ("File vuoto o non Valido", {})
            if asHeader and len(asHeader) > 0:
                if [h.strip() for h in header] != [h.strip() for h in asHeader]:
                    return ("Header non corrispondente", {})
            
            result = {}
            for i, row in enumerate(reader, start=2):
                if not row: continue
                key = row[0].strip()
                if not key:
                    return ("Errore chiavi nulle", {})
                if key in result:
                    return (f"Errore chiave duplicata riga {i}", {})
                row_dict = {header[j].strip(): row[j].strip() for j in range(len(header)) if j < len(row)}
                result[key] = row_dict
        return ("", result)
    except Exception as e:
        return (loc_ErrorProc(str(e), sProc), {})

def save_dict_to_csv(csv_file_name: str, asHeader: List[str], dictData: Dict, sMode: str = 'w', sDelimiter: str = ';') -> str:
    sProc = "save_dict_to_csv"
    try:
        exists = os.path.exists(csv_file_name)
        if not exists or sMode == 'w':
            with open(csv_file_name, 'w', encoding='utf-8') as hFile:
                hFile.write(sDelimiter.join(asHeader) + '\n')
        
        if sMode == 'a' and exists:
            with open(csv_file_name, 'a', encoding='utf-8') as hFile:
                for key, record in dictData.items():
                    if not isinstance(record, dict): continue
                    line = []
                    for h in asHeader:
                        val = StringWash(str(record.get(h, "")))
                        if ' ' in val:
                            val = f'"{val}"'
                        line.append(val)
                    hFile.write(sDelimiter.join(line) + '\n')
        return ""
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def read_ini_to_dict(ini_file_path: str) -> Tuple[str, Dict[str, Dict[str, str]]]:
    sProc = "read_ini_to_dict"
    try:
        if not FileExists(ini_file_path):
            return (f"File non esistente: {ini_file_path}", {})
        config = configparser.ConfigParser(interpolation=None, comment_prefixes=(";",), inline_comment_prefixes=())
        config.optionxform = str
        config.read(ini_file_path, encoding='utf-8')
        result = {section: dict(config[section]) for section in config.sections()}
        print(f"Letto file .ini {ini_file_path}, Numero Sezioni: {len(result)}")
        return ("", result)
    except Exception as e:
        return (loc_ErrorProc(str(e), sProc), {})

def save_dict_to_ini(data_dict: Dict[str, Dict[str, str]], ini_file_path: str) -> str:
    sProc = "save_dict_to_ini"
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        for section, items in data_dict.items():
            if not config.has_section(section):
                config.add_section(section)
            for k, v in items.items():
                config.set(section, k, str(v))
        os.makedirs(os.path.dirname(ini_file_path), exist_ok=True)
        with open(ini_file_path, 'w', encoding='utf-8') as f:
            config.write(f)
        return ""
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def save_array_file(sFile: str, asLines: List[str], sMode: str = '') -> str:
    sProc = "save_array_file"
    try:
        mode = 'a' if sMode == 'a' else 'w'
        with open(sFile, mode, encoding='utf-8') as f:
            f.write('\n'.join(asLines) + '\n')
        return ""
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def read_array_file(sFile: str) -> Tuple[str, List[str]]:
    sProc = "read_array_file"
    try:
        with open(sFile, 'r', encoding='utf-8') as f:
            return ("", f.read().splitlines())
    except Exception as e:
        return (loc_ErrorProc(str(e), sProc), [])

def isValidPath(sPath: str) -> bool:
    return os.path.isdir(sPath)

def isFilename(sFilename: str) -> bool:
    sProc = "isFilename"
    try:
        if not sFilename: return False
        parts = sFilename.split('.')
        if len(parts) < 2: return False
        name, ext = '.'.join(parts[:-1]), parts[-1]
        if not re.match(r'^[A-Za-z0-9_]+$', name): return False
        if not re.match(r'^[A-Za-z0-9_.]+$', ext): return False
        return True
    except: return False

def PathMake(sPath: Optional[str] = None, sFile: str = "", sExt: Optional[str] = None) -> str:
    sProc = "PathMake"
    try:
        if not sFile: return ""
        if not sPath: sPath = os.getcwd()
        sPath = os.path.normpath(sPath)
        if not sPath.endswith(os.sep): sPath += os.sep
        full_file = sFile
        if sExt:
            sExt = sExt.lstrip('.')
            full_file = f"{sFile}.{sExt}"
        sFullPath = os.path.normpath(os.path.join(sPath, full_file))
        return "" if sys.platform == "win32" and ':' in sFullPath.replace(':\\', '') else sFullPath
    except Exception as e:
        print(f"{sProc}: {e}")
        return ""

# ============================================================================
# FUNZIONI STRINGHE (aiSysStrings.py)
# ============================================================================

def StringAppend(sSource: str, sAppend: str, sDelimiter: str = ",") -> str:
    sProc = "StringAppend"
    try:
        if sSource: sSource += sDelimiter
        return sSource + sAppend
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def StringBool(sText: str) -> bool:
    return sText.strip().lower() == "true"

def isValidPassword(sText: str) -> bool:
    return bool(re.match(r'^[A-Za-z0-9_.!]+$', sText)) if sText else False

def isLettersOnly(sText: str) -> bool:
    return bool(re.match(r'^[A-Za-z ]+$', sText)) if sText else False

def isBool(sValue: str) -> bool:
    sProc = "isBool"
    try:
        return str(sValue).strip().lower() in ["true", "false", "1", "0"]
    except: return False

def isEmail(sMail: str) -> bool:
    if not sMail or '@' not in sMail or '.' not in sMail: return False
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', sMail): return False
    domain_parts = sMail.split('@')[1].split('.')
    return len(domain_parts) >= 2 and len(domain_parts[-1]) >= 2

def StringToArray(sText: str, delimiter: str = ',') -> List[str]:
    if not sText: return []
    return [x.strip() for x in sText.split(delimiter) if x.strip()]

def StringToNum(sNumber: str) -> Union[int, float]:
    try:
        sNumber = sNumber.replace(',', '.')
        return float(sNumber) if '.' in sNumber else int(sNumber)
    except: return 0

def StringWash(sText: str) -> str:
    return sText.encode("ascii", "ignore").decode().replace('"', '')

# ============================================================================
# CONVERSIONE DIZIONARI (aiSysDictToString.py)
# ============================================================================

def DictPrint(dictParam: Dict, sFile: Optional[str] = None) -> str:
    sProc = "DictPrint"
    try:
        if not isinstance(dictParam, dict): dictParam = {}
        sText = DictToString(dictParam, "json")[1]
        print(sText)
        if sFile:
            with open(sFile, 'a', encoding='utf-8') as f:
                f.write(sText + '\n')
        return ""
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def DictToXml(dictParam: Dict, **xml_options) -> str:
    sProc = "DictToXml"
    try:
        if not isinstance(dictParam, dict): return ""
        root_tag = xml_options.get("root_tag", "root")
        attr_prefix = xml_options.get("attr_prefix", "@")
        text_key = xml_options.get("text_key", "#text")
        cdata_key = xml_options.get("cdata_key", "#cdata")
        item_name = xml_options.get("item_name", "item")
        
        def build_xml(d, tag=None):
            if isinstance(d, dict):
                attrs = " ".join(f'{k[1:]}="{v}"' for k, v in d.items() if k.startswith(attr_prefix))
                attr_str = f" {attrs}" if attrs else ""
                text = d.get(text_key, "")
                cdata = d.get(cdata_key, "")
                children = []
                for k, v in d.items():
                    if not (k.startswith(attr_prefix) or k in (text_key, cdata_key)):
                        children.append(build_xml(v, k))
                inner = "".join(children)
                if cdata: inner += f"<![CDATA[{cdata}]]>"
                if text and not inner: return f"<{tag}{attr_str}>{text}</{tag}>"
                return f"<{tag}{attr_str}>{inner}</{tag}>" if inner else f"<{tag}{attr_str}/>"
            elif isinstance(d, list):
                return "".join(build_xml(item, tag or item_name) for item in d)
            else:
                val = str(d).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                return f"<{tag}>{val}</{tag}>"
        return f"<{root_tag}>{build_xml(dictParam, root_tag)}</{root_tag}>"
    except Exception as e:
        return loc_ErrorProc(str(e), sProc)

def DictToString(dictParam: Dict, sFormat: str = "json") -> Tuple[str, str]:
    sProc = "DictToString"
    try:
        if not isinstance(dictParam, dict): dictParam = {}
        sOut = ""
        if sFormat == "json":
            sOut = json.dumps(dictParam, indent=2, ensure_ascii=True)
        elif sFormat == "ini":
            lines = []
            for k, v in dictParam.items():
                if isinstance(v, dict): continue
                val = v if isinstance(v, str) else ("true" if v is True else "false" if v is False else "" if v is None else str(v))
                val = val.replace(';', '').replace('#', '').replace('=', '').replace('\n', ' ')
                lines.append(f"{k}={val}")
            sOut = "\n".join(lines)
        elif sFormat == "ini.sect":
            sections = []
            top = []
            for k, v in dictParam.items():
                if isinstance(v, dict):
                    sect_lines = []
                    for sk, sv in v.items():
                        val = sv if isinstance(sv, str) else ("true" if sv is True else "false" if sv is False else "" if sv is None else str(sv))
                        sect_lines.append(f"{sk}={val}")
                    sections.append(f"[{k}]\n" + "\n".join(sect_lines))
                else:
                    val = v if isinstance(v, str) else str(v)
                    top.append(f"{k}={val}")
            sOut = "\n".join(top + sections)
        else:
            sOut = ""
        return ("", sOut)
    except Exception as e:
        return (loc_ErrorProc(str(e), sProc), "")

# ============================================================================
# CLASSE DI LOGGING (aiSysLog.py)
# ============================================================================

class acLog:
    def __init__(self):
        self.sLog = ""

    def Start(self, sLogfile: Optional[str] = None, sLogFolder: Optional[str] = None) -> str:
        sProc = "Start"
        try:
            if not sLogFolder or sLogFolder == "":
                sLogFolder = os.path.dirname(os.path.abspath(sys.argv[0]))
            sAppName = os.path.splitext(os.path.basename(sys.argv[0]))[0]
            if not sLogfile or sLogfile == "":
                sLogfile = sAppName
            self.sLog = os.path.join(sLogFolder, f"{sLogfile}.log")
            return ""
        except Exception as e:
            return loc_ErrorProc(str(e), sProc)

    def Log(self, sType: str, sValue: str = "") -> None:
        if not self.sLog: return
        sLine = f"{Timestamp(sType)}: {sValue}"
        print(sLine)
        try:
            with open(self.sLog, 'a', encoding='utf-8') as f:
                f.write(sLine + '\n')
        except: pass

    def Log0(self, sResult: str, sValue: str = "") -> None:
        if sResult:
            self.Log("ERR", f"{sResult}: {sValue}")
        else:
            self.Log("INFO", sValue)

    def Log1(self, sValue: str = "") -> None:
        self.Log("INFO", sValue)

# ============================================================================
# MAIN (Vuoto come da specifica)
# ============================================================================

if __name__ == "__main__":
    pass