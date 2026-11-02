"""pyt_form - libreria esterna per la direttiva pyt form.

Implementa Prompt_pyt_form.md: form TUI/GUI/WEB descritti in JSON.
Solo stdlib (json, os, subprocess, shutil? no: json, os, subprocess, shlex,
tkinter e http.server/webbrowser solo per GUI/WEB). Mai shell=True.
"""

import html as _html
import json
import os
import shlex
import subprocess
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

TYPES = ("THEME", "WINDOW", "LAYOUT", "TEXT", "LABEL", "LIST", "BUTTON", "COMMAND")
MODES = ("TUI", "GUI", "WEB")
MODE_ALIASES = {"WEBFORM": "WEB"}
RESERVED_KEYS = ("config",)
DEFAULT_THEME = {"type": "THEME", "fg": "default", "bg": "default", "frame": True}
ANSI_FG = {"black": 30, "red": 31, "green": 32, "yellow": 33, "blue": 34,
           "magenta": 35, "cyan": 36, "white": 37, "default": 39}
ANSI_BG = {"black": 40, "red": 41, "green": 42, "yellow": 43, "blue": 44,
           "magenta": 45, "cyan": 46, "white": 47, "default": 49}


def load_form(json_path):
    """Legge il JSON (utf-8-sig con fallback utf-16). Solleva ValueError se malformato."""
    try:
        with open(json_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except UnicodeDecodeError:
        pass
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato in {json_path}: {e}")
    try:
        with open(json_path, "r", encoding="utf-16") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON malformato in {json_path}: {e}")


def _is_alnum(s):
    return isinstance(s, str) and len(s) > 0 and s.isalnum()


def validate_form(data):
    """Valida §2.2 (10 regole). Solleva ValueError con messaggi chiari."""
    if not isinstance(data, dict) or len(data) == 0:
        raise ValueError("Radice JSON deve essere un oggetto non vuoto.")
    cfg = data.get("config")
    if not isinstance(cfg, dict):
        raise ValueError("Chiave riservata 'config' obbligatoria come dizionario.")
    mode = cfg.get("mode")
    if not isinstance(mode, str) or mode.upper() not in list(MODES) + list(MODE_ALIASES):
        raise ValueError("config.mode obbligatorio tra TUI|GUI|WEB (alias WEBFORM).")
    if "return.file" in cfg and (not isinstance(cfg["return.file"], str) or not cfg["return.file"].strip()):
        raise ValueError("config.return.file deve essere stringa non vuota.")
    objects = {k: v for k, v in data.items() if k != "config"}
    for oid, o in objects.items():
        if not _is_alnum(oid):
            raise ValueError(f"Id non alfanumerico: {oid!r}.")
        if not isinstance(o, dict) or o.get("type") not in TYPES:
            raise ValueError(f"Oggetto {oid!r}: type tra {', '.join(TYPES)}.")
    wins = [k for k, o in objects.items() if o["type"] == "WINDOW"]
    if len(wins) < 1:
        raise ValueError("Serve almeno un oggetto WINDOW.")
    if not any(o.get("type") == "LAYOUT" for o in objects.values()):
        raise ValueError("Serve almeno un oggetto LAYOUT.")
    for oid, o in objects.items():
        t = o["type"]
        if t in ("TEXT", "BUTTON", "LABEL", "LIST"):
            lay = o.get("layout")
            if not (isinstance(lay, str) and lay in objects and objects[lay].get("type") == "LAYOUT"):
                raise ValueError(f"Oggetto {oid!r}: layout mancante o non LAYOUT.")
        if t == "LABEL":
            if not isinstance(o.get("caption"), str):
                raise ValueError(f"LABEL {oid!r}: caption stringa obbligatoria.")
            if not isinstance(o.get("size"), int) or o["size"] <= 0:
                raise ValueError(f"LABEL {oid!r}: size intero >0 obbligatorio.")
            if o.get("position") not in ("LEFT", "RIGHT", "CENTER"):
                raise ValueError(f"LABEL {oid!r}: position tra LEFT|RIGHT|CENTER.")
        if t == "LIST":
            opts = o.get("options")
            if not isinstance(opts, list) or len(opts) == 0 or not all(isinstance(x, str) for x in opts):
                raise ValueError(f"LIST {oid!r}: options array non vuoto di stringhe obbligatorio.")
            if "value" in o and o["value"] != "" and o["value"] not in opts:
                raise ValueError(f"LIST {oid!r}: value iniziale deve essere '' o una delle options.")
        if t == "BUTTON":
            if o.get("action", "EXEC") not in ("EXEC", "EXIT"):
                raise ValueError(f"BUTTON {oid!r}: action solo EXEC|EXIT.")
            if o.get("action", "EXEC") == "EXEC" and "command" in o:
                c = o["command"]
                if not (isinstance(c, str) and c in objects and objects[c].get("type") == "COMMAND"):
                    raise ValueError(f"BUTTON {oid!r}: command mancante o non COMMAND.")
            if o.get("action", "EXEC") == "EXEC" and "command" not in o:
                cfg = data.get("config", {}) if isinstance(data, dict) else {}
                if not (isinstance(cfg.get("cmdline"), str) and cfg["cmdline"].strip()):
                    raise ValueError(f"BUTTON {oid!r}: EXEC senza command e senza config.cmdline di default.")
        if t == "COMMAND":
            if not isinstance(o.get("cmdline"), str) or not o["cmdline"].strip():
                raise ValueError(f"COMMAND {oid!r}: cmdline stringa non vuota obbligatoria.")
            if "wait" in o and not isinstance(o["wait"], bool):
                raise ValueError(f"COMMAND {oid!r}: wait booleano.")
    if not any(o.get("type") == "BUTTON" and o.get("action", "EXEC") == "EXIT" for o in objects.values()):
        raise ValueError("Serve almeno un BUTTON con action EXIT.")


def get_theme(objects):
    """Ritorna (theme_dict, defaulted)."""
    for o in objects.values():
        if isinstance(o, dict) and o.get("type") == "THEME":
            return dict(o), False
    return dict(DEFAULT_THEME), True


def normalize_mode(config):
    """Normalizza mode (upper + alias WEBFORM->WEB)."""
    m = str(config.get("mode", "TUI")).upper()
    return MODE_ALIASES.get(m, m)


def resolve_command(objects, config, button):
    """Ritorna (cmdline, wait): ref esplicita o config.cmdline/wait di default."""
    if "command" in button:
        c = objects[button["command"]]
        return c["cmdline"], c.get("wait", True)
    if isinstance(config.get("cmdline"), str) and config["cmdline"].strip():
        return config["cmdline"], config.get("wait", True)
    raise ValueError("BUTTON EXEC senza command e senza config.cmdline di default.")


def _button_ids(objects):
    return [k for k, o in objects.items() if isinstance(o, dict) and o.get("type") == "BUTTON"]


def _align(text, size, position):
    if position == "RIGHT":
        return text.rjust(size)[:size]
    if position == "CENTER":
        return text.center(size)[:size]
    return text.ljust(size)[:size]


def _ansi_wrap(text, theme, use_color):
    if not use_color:
        return text
    try:
        fg = ANSI_FG.get(str(theme.get("fg", "default")).lower(), 39)
        bg = ANSI_BG.get(str(theme.get("bg", "default")).lower(), 49)
        return f"\033[{fg};{bg}m{text}\033[0m"
    except Exception:
        return text


def render_form(objects, theme, use_color=True):
    """Rende TUI §3 su canvas caratteri. Ritorna stringa (testabile)."""
    wins = [o for o in objects.values() if isinstance(o, dict) and o.get("type") == "WINDOW"]
    win = wins[0]
    try:
        W = max(20, int(win.get("width", 60)))
        H = max(8, int(win.get("height", 16)))
    except (TypeError, ValueError):
        W, H = 60, 16
    grid = [[" "] * W for _ in range(H)]

    def put(x, y, s):
        for i, ch in enumerate(s):
            if 0 <= x + i < W and 0 <= y < H:
                grid[y][x + i] = ch

    def box(x, y, w, h, title=""):
        w = max(4, w)
        h = max(3, h)
        put(x, y, "+" + "-" * (w - 2) + "+")
        put(x, y + h - 1, "+" + "-" * (w - 2) + "+")
        for r in range(1, h - 1):
            put(x, y + r, "|")
            put(x + w - 1, y + r, "|")
        if title:
            put(x + 2, y, f" {title} "[:w - 2])

    title = str(win.get("title", ""))
    box(0, 0, W, H, title)
    frame = bool(theme.get("frame", True))
    btns = _button_ids(objects)
    bnum = {bid: i + 1 for i, bid in enumerate(btns)}
    for o in objects.values():
        if not isinstance(o, dict) or o.get("type") != "LAYOUT":
            continue
        try:
            lx, ly, lw, lh = int(o.get("x", 1)), int(o.get("y", 1)), int(o.get("width", 30)), int(o.get("height", 6))
        except (TypeError, ValueError):
            lx, ly, lw, lh = 1, 1, 30, 6
        if frame:
            box(lx, ly, lw, lh, str(o.get("title", "")))
            cx, cy, cw = lx + 2, ly + 1, lw - 4
        else:
            cx, cy, cw = lx, ly, lw
        for oid, oo in objects.items():
            if not isinstance(oo, dict) or oo.get("layout") != _oid_of(objects, o):
                continue
            t = oo["type"]
            if t == "TEXT":
                put(cx, cy, f"[{oid}] {oo.get('value', '')}"[:cw])
                cy += 1
            elif t == "LABEL":
                try:
                    size = max(1, int(oo.get("size", cw)))
                except (TypeError, ValueError):
                    size = cw
                put(cx, cy, _align(str(oo.get("caption", "")), min(size, cw), oo.get("position", "LEFT")))
                cy += 1
            elif t == "LIST":
                opts = oo.get("options", [])
                cur = oo.get("value", "")
                put(cx, cy, f"[{oid}] {' | '.join(opts)} (scelta: {cur})"[:cw])
                cy += 1
            elif t == "BUTTON":
                put(cx, cy, f"({bnum[oid]}) {oo.get('value', oid)}"[:cw])
                cy += 1
    text = "\n".join("".join(r).rstrip() for r in grid)
    return _ansi_wrap(text, theme, use_color)


def _oid_of(objects, target):
    for k, v in objects.items():
        if v is target:
            return k
    return ""


def _split_cmdline(cmdline):
    return shlex.split(cmdline, posix=(os.name != "nt"))


def _exec_command(cmd_id, cmdline, wait, event_fn):
    """Esegue comando (lista, mai shell). Ritorna None. Logga esiti."""
    event_fn(f"COMMAND_EXEC {cmd_id} [{cmdline}] wait={wait}")
    args = _split_cmdline(cmdline)
    if wait:
        try:
            r = subprocess.run(args, capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            lines = [l for l in out.splitlines() if l.strip()][:20]
            event_fn(f"COMMAND_EXIT_CODE {cmd_id} {r.returncode}")
            for l in lines:
                event_fn(f"COMMAND_OUTPUT {cmd_id} {l[:200]}")
        except Exception as e:
            event_fn(f"COMMAND_ERROR {cmd_id} {e}")
    else:
        try:
            p = subprocess.Popen(args)
            event_fn(f"COMMAND_STARTED {cmd_id} pid={p.pid}")
        except Exception as e:
            event_fn(f"COMMAND_ERROR {cmd_id} {e}")


def run_loop(objects, theme, log_fn, ts_fn, event_fn, input_fn=input):
    """Loop TUI §4. Ritorna {id: valore} (BUTTON mai premuti -> None)."""
    values = {}
    for oid, o in objects.items():
        if not isinstance(o, dict):
            continue
        if o.get("type") == "TEXT":
            values[oid] = str(o.get("value", ""))
        elif o.get("type") == "LIST":
            values[oid] = str(o.get("value", ""))
        elif o.get("type") == "BUTTON":
            values[oid] = None
    btns = _button_ids(objects)
    print(render_form(objects, theme, True))
    while True:
        try:
            choice = input_fn("scelta> ").strip()
        except (EOFError, KeyboardInterrupt):
            event_fn("FORM_END eof")
            break
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(btns):
                bid = btns[idx]
                b = objects[bid]
                values[bid] = str(b.get("value", bid))
                action = b.get("action", "EXEC")
                event_fn(f"BUTTON_PRESSED {bid} [{values[bid]}] {action}")
                if action == "EXIT":
                    event_fn("FORM_END exit")
                    break
                try:
                    cmdline, wait = resolve_command(objects, _config_of(objects), b)
                except ValueError as e:
                    log_fn(f"[{ts_fn()}] ERRORE bottone {bid}: {e}")
                    continue
                _exec_command(bid, cmdline, wait, event_fn)
                print(render_form(objects, theme, True))
            else:
                event_fn(f"INPUT_NON_VALIDO {choice}")
                log_fn(f"[{ts_fn()}] Scelta non valida: {choice}")
            continue
        if "=" in choice:
            oid, _, val = choice.partition("=")
            oid, val = oid.strip(), val.strip()
            o = objects.get(oid)
            if isinstance(o, dict) and o.get("type") == "TEXT":
                old = values.get(oid, "")
                values[oid] = val
                event_fn(f"TEXT_CHANGED {oid} [{old}] -> [{val}]")
            elif isinstance(o, dict) and o.get("type") == "LIST":
                if val in o.get("options", []):
                    old = values.get(oid, "")
                    values[oid] = val
                    event_fn(f"TEXT_CHANGED {oid} [{old}] -> [{val}]")
                else:
                    event_fn(f"INPUT_NON_VALIDO {choice} (opzione non in options)")
                    log_fn(f"[{ts_fn()}] Opzione non valida per {oid}: {val}")
            else:
                event_fn(f"INPUT_NON_VALIDO {choice}")
                log_fn(f"[{ts_fn()}] Id non TEXT/LIST: {oid}")
            continue
        event_fn(f"INPUT_NON_VALIDO {choice}")
        log_fn(f"[{ts_fn()}] Scelta non valida: {choice}")
    return values


def _config_of(objects):
    return {}


def write_results(dest_path, values):
    """Scrive results JSON (None -> null). Ritorna dest_path."""
    d = os.path.dirname(os.path.abspath(dest_path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)
    return dest_path


def _resolve_dest(json_path, config):
    base_dir = os.path.dirname(os.path.abspath(json_path))
    basename = os.path.splitext(os.path.basename(json_path))[0]
    rf = config.get("return.file")
    if isinstance(rf, str) and rf.strip():
        rf = rf.strip()
        return rf if os.path.isabs(rf) else os.path.join(base_dir, rf)
    return os.path.join(base_dir, basename + "_results.json")


def run_gui(objects, theme, event_fn, log_fn, ts_fn):
    """GUI tkinter §4b. Ritorna {id: valore}."""
    try:
        import tkinter as tk
    except ImportError:
        raise ValueError("tkinter non disponibile per mode GUI.")
    try:
        root = tk.Tk()
    except Exception as e:
        raise ValueError(f"Display non disponibile per mode GUI: {e}")
    win = next(o for o in objects.values() if isinstance(o, dict) and o.get("type") == "WINDOW")
    root.title(str(win.get("title", "form")))
    try:
        root.geometry(f"{int(win.get('width', 60)) * 8}x{int(win.get('height', 16)) * 16}")
    except (TypeError, ValueError):
        pass
    fg = str(theme.get("fg", "default"))
    bg = str(theme.get("bg", "default"))
    if fg.lower() == "default":
        fg = "black"
    if bg.lower() == "default":
        bg = "white"
    values = {}
    for oid, o in objects.items():
        if not isinstance(o, dict):
            continue
        if o.get("type") == "TEXT":
            values[oid] = str(o.get("value", ""))
        elif o.get("type") == "LIST":
            values[oid] = str(o.get("value", ""))
        elif o.get("type") == "BUTTON":
            values[oid] = None
    btns = _button_ids(objects)
    entries = {}
    combos = {}

    def do_exec(bid):
        b = objects[bid]
        values[bid] = str(b.get("value", bid))
        event_fn(f"BUTTON_PRESSED {bid} [{values[bid]}] {b.get('action', 'EXEC')}")
        try:
            cmdline, wait = resolve_command(objects, _gui_config, b)
        except ValueError as e:
            log_fn(f"[{ts_fn()}] ERRORE bottone {bid}: {e}")
            return
        _exec_command(bid, cmdline, wait, event_fn)

    def do_exit(bid):
        values[bid] = str(objects[bid].get("value", bid))
        for oid, ent in entries.items():
            try:
                values[oid] = ent.get()
            except Exception:
                pass
        for oid, cb in combos.items():
            try:
                values[oid] = cb.get()
            except Exception:
                pass
        event_fn(f"BUTTON_PRESSED {bid} [{values[bid]}] EXIT")
        event_fn("FORM_END exit")
        root.destroy()

    row = 0
    for oid, o in objects.items():
        if not isinstance(o, dict):
            continue
        t = o.get("type")
        if t == "LABEL":
            anchor = {"LEFT": "w", "CENTER": "center", "RIGHT": "e"}.get(o.get("position", "LEFT"), "w")
            tk.Label(root, text=str(o.get("caption", ""))[:int(o.get("size", 30))],
                     fg=fg, bg=bg, anchor=anchor, width=int(o.get("size", 30))).pack(fill="x")
        elif t == "TEXT":
            f = tk.Frame(root, bg=bg)
            tk.Label(f, text=f"[{oid}]", fg=fg, bg=bg).pack(side="left")
            ent = tk.Entry(f, fg=fg, bg="white")
            ent.insert(0, values[oid])
            ent.pack(side="left", fill="x", expand=True)
            entries[oid] = ent
            f.pack(fill="x")
        elif t == "LIST":
            import tkinter.ttk as ttk
            f = tk.Frame(root, bg=bg)
            tk.Label(f, text=f"[{oid}]", fg=fg, bg=bg).pack(side="left")
            cb = ttk.Combobox(f, values=list(o.get("options", [])), state="readonly")
            if values[oid] in o.get("options", []):
                cb.set(values[oid])
            cb.pack(side="left", fill="x", expand=True)
            combos[oid] = cb
            f.pack(fill="x")
        elif t == "BUTTON":
            act = o.get("action", "EXEC")
            cmd = (lambda b=oid, a=act: do_exit(b) if a == "EXIT" else do_exec(b))
            tk.Button(root, text=str(o.get("value", oid)), fg=fg, bg=bg, command=cmd).pack(fill="x")
        row += 1
    root.mainloop()
    return values


_gui_config = {}


def render_gui(objects, theme, cb):
    """Wrapper §8.2: cb = {"event": fn, "print": fn, "ts": fn}."""
    import copy
    global _gui_config
    _gui_config = dict(cb.get("config", {}))
    event_fn = cb.get("event", lambda m: None)
    log_fn = cb.get("print", lambda m: None)
    ts_fn = cb.get("ts", lambda: "")
    return run_gui(objects, theme, event_fn, log_fn, ts_fn)


def render_web(json_path, objects, theme, cb):
    """WEB §4c: genera HTML, server locale, submit. Ritorna path results."""
    import urllib.parse
    from http.server import BaseHTTPRequestHandler, HTTPServer
    event_fn = cb.get("event", lambda m: None)
    log_fn = cb.get("print", lambda m: None)
    base_dir = os.path.dirname(os.path.abspath(json_path))
    basename = os.path.splitext(os.path.basename(json_path))[0]
    html_path = os.path.join(base_dir, basename + ".html")
    btns = _button_ids(objects)
    outcome = {"msg": ""}
    result = {"values": None}

    def page():
        parts = [f"<html><head><meta charset='utf-8'><title>{_html.escape(str(next(o for o in objects.values() if isinstance(o, dict) and o.get('type') == 'WINDOW').get('title', 'form')))}</title></head><body>",
                 "<form method='post'>"]
        for oid, o in objects.items():
            if not isinstance(o, dict):
                continue
            t = o.get("type")
            if t == "LABEL":
                align = str(o.get("position", "LEFT")).lower()
                if align == "center":
                    align = "center"
                elif align == "right":
                    align = "right"
                else:
                    align = "left"
                parts.append(f"<p style='text-align:{align}'>{_html.escape(str(o.get('caption', '')))}</p>")
            elif t == "TEXT":
                parts.append(f"<p><label>{_html.escape(oid)}: <input type='text' name='{_html.escape(oid)}' value='{_html.escape(str(o.get('value', '')))}'></label></p>")
            elif t == "LIST":
                opts = "".join(f"<option value='{_html.escape(x)}'>{_html.escape(x)}</option>" for x in o.get("options", []))
                parts.append(f"<p><label>{_html.escape(oid)}: <select name='{_html.escape(oid)}'>{opts}</select></label></p>")
        for bid in btns:
            parts.append(f"<p><button type='submit' name='button' value='{_html.escape(bid)}'>{_html.escape(str(objects[bid].get('value', bid)))}</button></p>")
        if outcome["msg"]:
            parts.append(f"<p><b>{_html.escape(outcome['msg'])}</b></p>")
        parts.append("</form></body></html>")
        return "\n".join(parts)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page())
    server_ref = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            vals = {}
            for oid, o in objects.items():
                if not isinstance(o, dict):
                    continue
                if o.get("type") == "TEXT":
                    vals[oid] = fields.get(oid, [str(o.get("value", ""))])[0]
                    if vals[oid] != str(o.get("value", "")):
                        event_fn(f"TEXT_CHANGED {oid} [{o.get('value', '')}] -> [{vals[oid]}]")
                elif o.get("type") == "LIST":
                    vals[oid] = fields.get(oid, [str(o.get("value", ""))])[0]
                    if vals[oid] not in o.get("options", []):
                        vals[oid] = str(o.get("value", ""))
                        event_fn(f"INPUT_NON_VALIDO {oid} opzione non valida")
                elif o.get("type") == "BUTTON":
                    vals[oid] = None
            pressed = (fields.get("button") or [""])[0]
            if pressed in btns:
                b = objects[pressed]
                vals[pressed] = str(b.get("value", pressed))
                event_fn(f"BUTTON_PRESSED {pressed} [{vals[pressed]}] {b.get('action', 'EXEC')}")
                if b.get("action", "EXEC") == "EXIT":
                    event_fn("FORM_END exit")
                    result["values"] = vals
                    body = "<html><body><p>Form chiuso.</p></body></html>".encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    threading.Thread(target=server_ref["srv"].shutdown, daemon=True).start()
                    return
                try:
                    cmdline, wait = resolve_command(objects, _web_config, b)
                except ValueError as e:
                    outcome["msg"] = f"ERRORE bottone {pressed}: {e}"
                    self._rerender()
                    return
                _exec_command(pressed, cmdline, wait, event_fn)
                outcome["msg"] = f"Eseguito {pressed}."
            self._rerender()

        def _rerender(self):
            body = page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server_ref["srv"] = server
    port = server.server_address[1]
    event_fn(f"WEB_SERVE port={port} file={html_path}")
    log_fn(f"Form WEB su http://127.0.0.1:{port} — file {html_path}")
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    except Exception:
        pass
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    thread.join()
    server.server_close()
    return result["values"] if result["values"] is not None else {}


_web_config = {}


def run_form(json_path, log_fn, ts_fn):
    """Entry point §8.2. Ritorna path del results. Solleva ValueError/FileNotFoundError."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"File form {json_path} non trovato.")
    data = load_form(json_path)
    validate_form(data)
    base_dir = os.path.dirname(os.path.abspath(json_path))
    basename = os.path.splitext(os.path.basename(json_path))[0]
    config = data["config"]
    mode = str(config.get("mode", "TUI")).upper()
    mode = MODE_ALIASES.get(mode, mode)
    objects = {k: v for k, v in data.items() if k != "config"}
    theme, defaulted = get_theme(objects)
    log_path = os.path.join(base_dir, basename + ".log")

    def event_fn(msg):
        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{ts_fn()}] {msg}\n")
        except Exception as e:
            log_fn(f"Impossibile scrivere sul log {log_path}: {e}")

    n_types = {}
    for o in objects.values():
        if isinstance(o, dict):
            n_types[o.get("type")] = n_types.get(o.get("type"), 0) + 1
    log_fn(f"[{ts_fn()}] Fase 1: validazione ok ({len(objects)} oggetti: " +
           ", ".join(f"{k}={v}" for k, v in sorted(n_types.items())) + ")")
    event_fn(f"FORM_START {basename} oggetti={len(objects)} mode={mode}")
    if defaulted:
        event_fn("THEME_DEFAULT usato theme di default")
    global _gui_config, _web_config
    _gui_config = dict(config)
    _web_config = dict(config)
    if mode == "GUI":
        log_fn(f"[{ts_fn()}] Fase 2-3: rendering GUI + loop")
        values = render_gui(objects, theme, {"event": event_fn, "print": log_fn, "ts": ts_fn, "config": dict(config)})
    elif mode == "WEB":
        log_fn(f"[{ts_fn()}] Fase 2-3: rendering WEB + submit")
        values = render_web(json_path, objects, theme, {"event": event_fn, "print": log_fn, "ts": ts_fn, "config": dict(config)})
        if not values:
            values = {k: (str(v.get("value", "")) if v.get("type") in ("TEXT", "LIST") else None)
                      for k, v in objects.items() if isinstance(v, dict) and v.get("type") in ("TEXT", "LIST", "BUTTON")}
    else:
        log_fn(f"[{ts_fn()}] Fase 2: rendering TUI")
        values = run_loop(objects, theme, log_fn, ts_fn, event_fn)
    rf = config.get("return.file")
    if isinstance(rf, str) and rf.strip():
        rf = rf.strip()
        dest = rf if os.path.isabs(rf) else os.path.join(base_dir, rf)
    else:
        dest = os.path.join(base_dir, basename + "_results.json")
    log_fn(f"[{ts_fn()}] Fase 4-5: scrittura results in {dest}")
    return write_results(dest, values)
