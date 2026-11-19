#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pyt_bkh.py - Modulo esterno per gestione bookmark Chrome (bkh)
Usa solo standard library. Richiesto da pyt.py direttiva bkh.
"""

import os
import sys
import json
import re
import html
import urllib.request
import urllib.parse
import urllib.error
import mimetypes
import pathlib
import datetime
import concurrent.futures
from html.parser import HTMLParser
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Tuple, Set

# ============================================================================
# Costanti e utility
# ============================================================================

BOOKMARK_TITLE_DEFAULT = "Bookmarks"
BOOKMARK_DOCTYPE = '<!DOCTYPE NETSCAPE-Bookmark-file-1>'
BOOKMARK_META = '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">'
BOOKMARK_TITLE_TAG = f'<TITLE>{BOOKMARK_TITLE_DEFAULT}</TITLE>'
BOOKMARK_H1 = f'<H1>{BOOKMARK_TITLE_DEFAULT}</H1>'
BOOKMARK_DL_START = '<DL><p>'
BOOKMARK_DL_END = '</DL><p>'

# Regex per sanitizzazione nomi file
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"\\|?*\x00-\x1f]')
_URL_NORMALIZE_RE = re.compile(r'^https?://', re.IGNORECASE)

# User-Agent per richieste HTTP
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Magic bytes per validazione immagini
IMAGE_MAGIC = {
    'ico': b'\x00\x00\x01\x00',
    'png': b'\x89PNG\r\n\x1a\n',
    'gif': b'GIF87a',
    'gif89': b'GIF89a',
    'jpg': b'\xff\xd8\xff',
    'svg': b'<svg',
    'svg_xml': b'<?xml',
}

# ============================================================================
# Helper functions
# ============================================================================

def _sanitize_filename(name: str, max_len: int = 150) -> str:
    """Sostituisce caratteri illegali con _, rimuove punti/spazi finali, tronca."""
    name = _INVALID_FILENAME_CHARS.sub('_', name)
    name = name.rstrip('. ')
    if len(name) > max_len:
        name = name[:max_len]
    return name


def _normalize_url(url: str) -> str:
    """Normalizza URL per confronto: scheme/host lowercase, rimuove slash finale e porta default."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        # Rimuovi porta default
        if (scheme == 'http' and netloc.endswith(':80')) or (scheme == 'https' and netloc.endswith(':443')):
            netloc = netloc.rsplit(':', 1)[0]
        path = parsed.path
        if path.endswith('/') and path != '/':
            path = path[:-1]
        normalized = f"{scheme}://{netloc}{path}"
        if parsed.query:
            normalized += '?' + parsed.query
        if parsed.fragment:
            normalized += '#' + parsed.fragment
        return normalized
    except Exception:
        return url.lower().rstrip('/')


def _parse_bool(value: Any, default: bool = False) -> bool:
    """Parse booleano da stringa/valore: true/false, 1/0, yes/no, si/on/off."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ('true', '1', 'yes', 'on', 'si', 's'):
        return True
    if s in ('false', '0', 'no', 'off', 'no', 'n'):
        return False
    return default


def _unique_name(name: str, used_names: Set[str]) -> str:
    """Genera nome univoco aggiungendo suffisso _1, _2, ..."""
    base = name
    i = 1
    while name in used_names:
        name = f"{base}_{i}"
        i += 1
    used_names.add(name)
    return name


def _fetch_favicon(url: str, images_dir: str, name: str, force: bool, log) -> Optional[str]:
    """Scarica favicon, salva in images_dir, restituisce path relativo o None."""
    try:
        os.makedirs(images_dir, exist_ok=True)
        base_name = _sanitize_filename(name)
        url_obj = urlparse(url)
        host = url_obj.netloc.lower()
        
        # Prova varianti icon link
        icon_urls = [
            f"{url_obj.scheme}://{url_obj.netloc}/favicon.ico",
            f"{url_obj.scheme}://{url_obj.netloc}/favicon.png",
        ]
        
        for fav_url in icon_urls:
            if not force:
                # Controlla se già salvato
                for ext in ['.ico', '.png', '.gif', '.jpg', '.svg']:
                    existing = os.path.join(images_dir, base_name + ext)
                    if os.path.exists(existing):
                        return os.path.relpath(existing, start=os.path.dirname(os.path.join(images_dir, '..')))
            
            try:
                req = urllib.request.Request(fav_url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content_type = resp.headers.get('Content-Type', '')
                    data = resp.read(1024 * 1024)  # max 1MB
                    
                    # Determina estensione
                    ext = '.ico'
                    if 'png' in content_type:
                        ext = '.png'
                    elif 'gif' in content_type:
                        ext = '.gif'
                    elif 'jpeg' in content_type or 'jpg' in content_type:
                        ext = '.jpg'
                    elif 'svg' in content_type or 'xml' in content_type:
                        ext = '.svg'
                    elif data.startswith(IMAGE_MAGIC['png']):
                        ext = '.png'
                    elif data.startswith(IMAGE_MAGIC['gif']) or data.startswith(IMAGE_MAGIC['gif89']):
                        ext = '.gif'
                    elif data.startswith(IMAGE_MAGIC['jpg']):
                        ext = '.jpg'
                    elif data.startswith(IMAGE_MAGIC['ico']):
                        ext = '.ico'
                    elif data.startswith(IMAGE_MAGIC['svg']) or data.startswith(IMAGE_MAGIC['svg_xml']):
                        ext = '.svg'
                    
                    fname = _unique_name(base_name + ext, set())
                    fpath = os.path.join(images_dir, fname)
                    with open(fpath, 'wb') as f:
                        f.write(data)
                    return os.path.relpath(fpath, start=os.path.dirname(os.path.join(images_dir, '..')))
            except Exception:
                continue
    except Exception as e:
        log(f"[{datetime.datetime.now().strftime('%Y%m%d:%H%M%S')}] WARNING: favicon per {url}: {e}")
    return None


def _check_url(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Verifica accessibilità URL. Ritorna (accessibile, dettaglio)."""
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400, f"HEAD {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code in (405, 501):
            # Prova GET con Range
            try:
                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Range': 'bytes=0-0'})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status < 400, f"GET {resp.status}"
            except Exception as e2:
                return False, f"GET error: {e2}"
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL error: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


# ============================================================================
# HTML Parser per bookmark
# ============================================================================

class BookmarkHTMLParser(HTMLParser):
    """Parser HTML per bookmark formato Netscape/Chrome."""
    
    def __init__(self):
        super().__init__()
        self.tree = {'type': 'folder', 'name': 'root', 'children': []}
        self.stack = [self.tree]
        self.current_tag = None
        self.current_attrs = {}
        self.in_a = False
        self.a_href = ''
        self.a_text = ''
    
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()
        self.current_attrs = dict((k.lower(), v) for k, v in attrs)
        
        if self.current_tag == 'a':
            self.in_a = True
            self.a_href = self.current_attrs.get('href', '')
            self.a_text = ''
        elif self.current_tag == 'h3':
            # Inizio cartella
            folder_name = self.current_attrs.get('add_date', '')
    
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'a' and self.in_a:
            self.in_a = False
            if self.a_href and not self.a_href.startswith(('javascript:', 'chrome://', '#', 'mailto:')):
                # Aggiungi link al nodo corrente
                parent = self.stack[-1]
                parent['children'].append({
                    'type': 'url',
                    'name': self.a_text.strip() or self.a_href,
                    'url': self.a_href
                })
            self.a_text = ''
            self.a_href = ''
        elif tag == 'h3':
            pass
        elif tag == 'dl':
            # Fine cartella
            if len(self.stack) > 1:
                self.stack.pop()
    
    def handle_data(self, data):
        if self.in_a:
            self.a_text += data
        elif self.current_tag == 'h3':
            # Nome cartella
            name = data.strip()
            if name:
                new_folder = {'type': 'folder', 'name': name, 'children': []}
                self.stack[-1]['children'].append(new_folder)
                self.stack.append(new_folder)
    
    def handle_entityref(self, name):
        if self.in_a:
            self.a_text += f'&{name};'
    
    def handle_charref(self, name):
        if self.in_a:
            self.a_text += f'&#{name};'


def parse_bookmarks_html(html_path: str) -> Dict:
    """Parsa file HTML bookmark e restituisce albero."""
    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    parser = BookmarkHTMLParser()
    parser.feed(content)
    return parser.tree


# ============================================================================
# Scrittura bookmark HTML
# ============================================================================

def _write_bookmarks_html(path: str, tree: Dict, title: str = BOOKMARK_TITLE_DEFAULT) -> None:
    """Scrive albero bookmark in file HTML formato Netscape/Chrome."""
    lines = [
        BOOKMARK_DOCTYPE,
        BOOKMARK_META,
        f'<TITLE>{html.escape(title)}</TITLE>',
        f'<H1>{html.escape(title)}</H1>',
        BOOKMARK_DL_START
    ]
    
    def write_node(node, indent=0):
        prefix = '    ' * indent
        if node['type'] == 'folder':
            lines.append(f'{prefix}<DT><H3>{html.escape(node["name"])}</H3>')
            lines.append(f'{prefix}{BOOKMARK_DL_START}')
            for child in node.get('children', []):
                write_node(child, indent + 1)
            lines.append(f'{prefix}{BOOKMARK_DL_END}')
        elif node['type'] == 'url':
            name = html.escape(node['name'])
            url = html.escape(node['url'])
            lines.append(f'{prefix}<DT><A HREF="{url}">{name}</A>')
    
    for child in tree.get('children', []):
        write_node(child, 1)
    
    lines.append(BOOKMARK_DL_END)
    
    # Scrittura atomica
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    os.replace(tmp_path, path)


# ============================================================================
# Funzioni core per sottocomandi
# ============================================================================

def _chrome_bookmarks_path() -> Optional[str]:
    """Trova il file Bookmarks di Chrome più recente."""
    # 1. Variabile d'ambiente
    env_path = os.environ.get('CHROME_BOOKMARKS')
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 2. Auto-rilevamento per OS
    candidates = []
    if sys.platform == 'win32':
        localappdata = os.environ.get('LOCALAPPDATA', '')
        if localappdata:
            chrome_base = os.path.join(localappdata, 'Google', 'Chrome', 'User Data')
            if os.path.exists(chrome_base):
                for entry in os.listdir(chrome_base):
                    if entry == 'Default' or entry.startswith('Profile '):
                        bm_path = os.path.join(chrome_base, entry, 'Bookmarks')
                        if os.path.exists(bm_path):
                            candidates.append(bm_path)
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support/Google/Chrome')
        if os.path.exists(base):
            for entry in os.listdir(base):
                if entry == 'Default' or entry.startswith('Profile '):
                    bm_path = os.path.join(base, entry, 'Bookmarks')
                    if os.path.exists(bm_path):
                        candidates.append(bm_path)
    else:  # Linux
        base = os.path.expanduser('~/.config/google-chrome')
        if os.path.exists(base):
            for entry in os.listdir(base):
                if entry == 'Default' or entry.startswith('Profile '):
                    bm_path = os.path.join(base, entry, 'Bookmarks')
                    if os.path.exists(bm_path):
                        candidates.append(bm_path)
    
    if not candidates:
        return None
    
    # Scegli il più recente per mtime
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _chrome_json_to_tree(json_path: str) -> Dict:
    """Converte JSON Bookmarks di Chrome in albero per HTML."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tree = {'type': 'folder', 'name': 'root', 'children': []}
    
    def convert_node(chrome_node):
        if chrome_node.get('type') == 'url':
            return {
                'type': 'url',
                'name': chrome_node.get('name', ''),
                'url': chrome_node.get('url', '')
            }
        elif chrome_node.get('type') == 'folder':
            folder = {'type': 'folder', 'name': chrome_node.get('name', ''), 'children': []}
            for child in chrome_node.get('children', []):
                converted = convert_node(child)
                if converted:
                    folder['children'].append(converted)
            return folder
        return None
    
    roots = data.get('roots', {})
    for key in ['bookmark_bar', 'other', 'synced']:
        if key in roots:
            node = convert_node(roots[key])
            if node:
                tree['children'].append(node)
    
    return tree


def _sort_tree(tree: Dict, mode: str, firsturl: List[str]) -> None:
    """Ordina ricorsivamente l'albero in-place.
    Ordinamento: prima per categoria (cartelle/H3) in ordine alfabetico,
    poi gli URL all'interno di ogni categoria in ordine alfabetico.
    In modalità 'smart', gli URL in firsturl vengono prima all'interno della loro categoria.
    """
    firsturl_norm = set(_normalize_url(u) for u in firsturl)
    
    def sort_children(node):
        children = node.get('children', [])
        
        # Separa cartelle e URL
        folders = []
        urls = []
        for child in children:
            if child['type'] == 'folder':
                folders.append(child)
            else:
                urls.append(child)
        
        # Ordina cartelle per nome (alfabetico)
        folders.sort(key=lambda c: (c['name'].casefold(), c['name']))
        
        # Per ogni cartella, ordina ricorsivamente i suoi figli
        for folder in folders:
            sort_children(folder)
        
        # Ordina URL in base alla modalità
        if mode == 'smart':
            first = []
            other = []
            for url in urls:
                if _normalize_url(url['url']) in firsturl_norm:
                    first.append(url)
                else:
                    other.append(url)
            first.sort(key=lambda u: (u['name'].casefold(), u['name']))
            other.sort(key=lambda u: (u['name'].casefold(), u['name']))
            sorted_urls = first + other
        else:  # normal
            sorted_urls = sorted(urls, key=lambda u: (u['name'].casefold(), u['name']))
        
        # Ricostruisci children: prima cartelle (già ordinate), poi URL (già ordinati)
        # Ma l'ordine globale deve essere: prima cartelle (ciascuna con i suoi URL), poi URL alla radice
        # Per mantenere la struttura ad albero, mettiamo prima le cartelle con i loro URL,
        # poi gli URL alla radice
        
        # Riorganizza: per ogni cartella, metti la cartella seguita dai suoi URL ordinati
        # Poi gli URL alla radice
        new_children = []
        for folder in folders:
            new_children.append(folder)
        # Gli URL alla radice vanno alla fine
        new_children.extend(sorted_urls)
        
        node['children'] = new_children
    
    sort_children(tree)


def _flatten_ordered(tree: Dict, mode: str, firsturl: List[str]) -> List[Dict]:
    """Restituisce lista piatta di URL e categorie ordinati.
    Include sia URL che titoli di categoria (H3) allo stesso livello.
    Categorie nidificate vengono concatenate come 'Parent: Child'.
    La categoria 'Barra dei preferiti' / 'Bookmarks bar' viene messa per prima.
    """
    firsturl_norm = set(_normalize_url(u) for u in firsturl)
    result = []
    
    def collect(node, current_category=None):
        for child in node.get('children', []):
            if child['type'] == 'url':
                is_first = _normalize_url(child['url']) in firsturl_norm
                result.append({
                    'type': 'url',
                    'entry': child,
                    'category': current_category,
                    'is_first': is_first
                })
            elif child['type'] == 'folder':
                # Concatena nome categoria con parent se nidificato
                if current_category:
                    concat_category = f"{current_category}: {child['name']}"
                else:
                    concat_category = child['name']
                # Aggiungi il titolo della categoria come entry separata
                result.append({
                    'type': 'category',
                    'entry': {'name': concat_category},
                    'category': concat_category,
                    'is_first': False
                })
                # Raccogli URL dentro la cartella con questa categoria concatenata
                collect(child, concat_category)
    
    collect(tree)
    
    # Ordina: prima "Barra dei preferiti" / "Bookmarks bar", poi per categoria (alfabetico), 
    # poi category entries prima delle URL, poi per is_first (smart), poi per nome
    def category_sort_key(cat_name):
        if not cat_name:
            return (2, '')  # Senza categoria (Altri link) in fondo
        cat_lower = cat_name.lower()
        if cat_lower in ('barra dei preferiti', 'bookmarks bar'):
            return (0, '')  # Prima assoluta
        return (1, cat_name)  # Altre categorie alfabeticamente
    
    if mode == 'smart':
        result.sort(key=lambda x: (
            category_sort_key(x['category']),
            0 if x['type'] == 'category' else 1,  # category entries prima
            not x['is_first'],    # firsturl prima
            x['entry']['name'].casefold(),  # poi nome
            x['entry']['name']
        ))
    else:
        result.sort(key=lambda x: (
            category_sort_key(x['category']),
            0 if x['type'] == 'category' else 1,  # category entries prima
            x['entry']['name'].casefold(),  # poi nome
            x['entry']['name']
        ))
    
    return result


def _parse_bookmarks_html(html_path: str) -> Dict:
    """Parsa file HTML bookmark e restituisce albero."""
    return parse_bookmarks_html(html_path)


# ============================================================================
# Sottocomandi run_*
# ============================================================================

def help_text(lang: str = "it") -> str:
    """Restituisce l'aiuto completo in italiano o inglese."""
    if lang == "en":
        return """bkh - Chrome Bookmarks Management
=====================================================

Usage:
  bkh export [file.html]
  bkh url <file.html> <folder>
  bkh order <config.json>
  bkh homepage <config.json>
  bkh check <bookmark_in.html> <bookmark_out.html>
  bkh merge <bookmark_in.html> <bookmark_add.html> <bookmark_new.html>
  bkh delete <bookmark_in.html> <bookmark_del.html> <bookmark_out.html>
  bkh help

SUBCOMMANDS
-----------
export [file.html]
  Exports Chrome bookmarks to an HTML file...
  Parameters: ...
  Example:   pyt.cmd bkh export "D:\\Backup\\bookmarks.html"
  Errors:    ...

url <file.html> <folder>
  Converts all links in the HTML file to .url files in the folder
  Example:   pyt.cmd bkh url bookmarks.html "D:\\Favorites\\url"

order <config.json>
  Sorts bookmarks according to config.mode (normal|smart)...
  Example JSON: { "config": { "bookmark_in": "...", "bookmark_out": "..." } }
  Example:      pyt.cmd bkh order order.json

homepage <config.json>
  Builds a multi-column HTML page with names, icons and URL tooltips
  Example JSON: { "config": { "bookmark_in": "...", "columns": 3, "images_path": "icons", "homepage_out": "homepage.html", "title": "My Favorites", "google": true, "icorefresh": false } }
  Example:      pyt.cmd bkh homepage homepage.json
  Config options: icorefresh (bool, default false) = SKIP icon download, use only existing; force_icons (alias, opposite)

check <bookmark_in.html> <bookmark_out.html>
  Checks URLs and writes unreachable ones to the output file...
  Example:   pyt.cmd bkh check bookmarks.html bookmarks_broken.html
  Errors:    input file missing, no URLs, output not writable

merge <bookmark_in.html> <bookmark_add.html> <bookmark_new.html>
  Merges two bookmarks and renames duplicates with _1, _2, ...
  Example:   pyt.cmd bkh merge bookmarks.html bookmarks_new.html bookmarks_merged.html

delete <bookmark_in.html> <bookmark_del.html> <bookmark_out.html>
  Removes from bookmark_in the URLs found in bookmark_del...
  Example:   pyt.cmd bkh delete bookmarks.html bookmarks_to_remove.html bookmarks_clean.html

For details: bkh help
"""
    return """bkh - Gestione segnalibri (bookmark) di Google Chrome
=====================================================

Uso:
  bkh export [file.html]
  bkh url <file.html> <cartella>
  bkh order <config.json>
  bkh homepage <config.json>
  bkh check <bookmark_in.html> <bookmark_out.html>
  bkh merge <bookmark_in.html> <bookmark_add.html> <bookmark_new.html>
  bkh delete <bookmark_in.html> <bookmark_del.html> <bookmark_out.html>
  bkh help

SOTTOCOMANDI
------------
export [file.html]
  Esporta i segnalibri di Chrome in un file HTML...
  Parametri: ...
  Esempio:   pyt.cmd bkh export "D:\\Backup\\preferiti.html"
  Errori:    ...

url <file.html> <cartella>
  Converte ogni link in un file .url...
  Esempio:   pyt.cmd bkh url bookmarks.html "D:\\Preferiti\\url"

order <config.json>
  Ordina i segnalibri secondo config.mode (normal|smart)...
  Esempio JSON: { "config": { "bookmark_in": "...", "bookmark_out": "..." } }
  Esempio:      pyt.cmd bkh order order.json

homepage <config.json>
  Crea una pagina HTML multicolonne con nomi, icone e tooltip URL
  Esempio JSON: { "config": { "bookmark_in": "...", "columns": 3, "images_path": "icons", "homepage_out": "homepage.html", "title": "I miei preferiti", "google": true, "icorefresh": false } }
  Esempio:      pyt.cmd bkh homepage homepage.json
  Opzioni config: icorefresh (bool, default false) = NON scarica icone, usa solo quelle esistenti; force_icons (alias, opposto)

check <bookmark_in.html> <bookmark_out.html>
  Verifica l'accessibilità degli URL e scrive in output solo quelli non accessibili...
  Esempio:   pyt.cmd bkh check bookmarks.html bookmarks_broken.html
  Errori:    file di input mancante, nessun URL, output non scrivibile

merge <bookmark_in.html> <bookmark_add.html> <bookmark_new.html>
  Unisce due bookmark e rinomina i duplicati con _1, _2, ...
  Esempio:   pyt.cmd bkh merge bookmarks.html bookmarks_new.html bookmarks_merged.html

delete <bookmark_in.html> <bookmark_del.html> <bookmark_out.html>
  Rimuove da bookmark_in gli URL presenti in bookmark_del...
  Esempio:   pyt.cmd bkh delete bookmarks.html bookmarks_to_remove.html bookmarks_clean.html

Per dettagli: bkh help
"""


def run_export(args: List[str], log, ts) -> str:
    """bkh export [file.html]. Ritorna path file HTML generato."""
    if len(args) > 1:
        raise ValueError("Sintassi errata. Uso: bkh export [file.html]")
    
    output_file = args[0].strip('"\'') if args else 'bookmark.html'
    output_file = os.path.abspath(output_file)
    
    log(f"[{ts()}] Fase 1: Ricerca file Bookmarks di Chrome")
    chrome_path = _chrome_bookmarks_path()
    if not chrome_path:
        raise FileNotFoundError("File Bookmarks di Chrome non trovato. Impostare CHROME_BOOKMARKS o chrome_profile.")
    
    log(f"[{ts()}] Trovato: {chrome_path}")
    
    log(f"[{ts()}] Fase 2: Conversione JSON Chrome in albero bookmark")
    tree = _chrome_json_to_tree(chrome_path)
    
    log(f"[{ts()}] Fase 3: Scrittura file HTML {output_file}")
    _write_bookmarks_html(output_file, tree)
    
    log(f"[{ts()}] Export completato: {output_file}")
    return output_file


def run_url(args: List[str], log, ts) -> str:
    """bkh url <file.html> <cartella>. Ritorna cartella di output."""
    if len(args) != 2:
        raise ValueError("Sintassi errata. Uso: bkh url <file.html> <cartella>")
    
    html_file = args[0].strip('"\'')
    output_dir = args[1].strip('"\'')
    
    if not os.path.exists(html_file):
        raise FileNotFoundError(f"File bookmark {html_file} non trovato.")
    
    os.makedirs(output_dir, exist_ok=True)
    
    log(f"[{ts()}] Fase 1: Parsing file HTML {html_file}")
    tree = parse_bookmarks_html(html_file)
    
    # Estrae tutti gli URL
    urls = []
    def collect(node):
        for child in node.get('children', []):
            if child['type'] == 'url':
                urls.append(child)
            elif child['type'] == 'folder':
                collect(child)
    
    for child in tree.get('children', []):
        if child['type'] == 'folder':
            def rec(n):
                for c in n.get('children', []):
                    if c['type'] == 'url':
                        urls.append(c)
                    elif c['type'] == 'folder':
                        rec(c)
        collect(tree)
    
    log(f"[{ts()}] Trovati {len(urls)} link")
    
    created = 0
    skipped = 0
    used_names = set()
    
    for entry in urls:
        url = entry.get('url', '')
        name = entry.get('name', '') or url
        
        if not url or url.startswith(('javascript:', 'chrome://', '#', 'mailto:')):
            skipped += 1
            continue
        
        safe_name = _sanitize_filename(name)
        unique_name = _unique_name(safe_name, used_names)
        fname = unique_name + '.url'
        fpath = os.path.join(output_dir, fname)
        
        content = f"[InternetShortcut]\nURL={url}\n"
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        created += 1
    
    log(f"[{ts()}] Creati {created} file .url in {output_dir} ({skipped} saltati)")
    return output_dir


def run_order(args: List[str], log, ts) -> str:
    """bkh order <config.json>. Ritorna path file HTML ordinato."""
    if len(args) != 1:
        raise ValueError("Sintassi errata. Uso: bkh order <config.json>")
    
    config_file = args[0].strip('"\'')
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"File JSON {config_file} non trovato.")
    
    config = _load_config(config_file)
    cfg = config.get('config', {})
    
    # Validazione
    if 'bookmark_in' not in cfg:
        raise ValueError("Chiave obbligatoria mancante nel JSON: bookmark_in")
    if 'bookmark_out' not in cfg:
        raise ValueError("Chiave obbligatoria mancante nel JSON: bookmark_out")
    
    mode = cfg.get('mode', 'normal')
    if mode not in ('normal', 'smart'):
        raise ValueError("Valore 'mode' non valido. Usare: normal, smart.")
    
    firsturl = cfg.get('firsturl', [])
    bookmark_in = cfg['bookmark_in']
    bookmark_out = cfg['bookmark_out']
    
    # Risolve path relativi
    base_dir = os.path.dirname(os.path.abspath(args[0].strip('"\'')))
    bookmark_in = os.path.join(base_dir, bookmark_in) if not os.path.isabs(bookmark_in) else bookmark_in
    bookmark_out = os.path.join(base_dir, bookmark_out) if not os.path.isabs(bookmark_out) else bookmark_out
    
    if not os.path.exists(bookmark_in):
        raise FileNotFoundError(f"File bookmark di input {bookmark_in} non trovato.")
    
    log(f"[{ts()}] Fase 1: Lettura file {bookmark_in}")
    tree = parse_bookmarks_html(bookmark_in)
    
    log(f"[{ts()}] Fase 2: Ordinamento (mode={mode})")
    _sort_tree(tree, cfg.get('mode', 'normal'), cfg.get('firsturl', []))
    
    log(f"[{ts()}] Fase 3: Scrittura file {bookmark_out}")
    _write_bookmarks_html(bookmark_out, tree)
    
    log(f"[{ts()}] Ordinamento completato: {bookmark_out}")
    return bookmark_out


def run_homepage(args: List[str], log, ts) -> str:
    """bkh homepage <config.json>. Ritorna path homepage generata."""
    if len(args) != 1:
        raise ValueError("Sintassi errata. Uso: bkh homepage <config.json>")
    
    config_file = args[0].strip('"\'')
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"File JSON {config_file} non trovato.")
    
    config = _load_config(config_file)
    cfg = config.get('config', {})
    # alias e icons possono essere a livello root nel JSON O dentro a 'config'
    alias_cfg = config.get('alias', {}) or cfg.get('alias', {})
    icons_cfg = config.get('icons', {}) or cfg.get('icons', {})
    
    # Validazioni
    required = ['columns', 'images_path', 'homepage_out']
    for key in required:
        if key not in cfg:
            raise ValueError(f"Chiave obbligatoria mancante nel JSON: {key}")
    
    try:
        columns = int(cfg['columns'])
        if columns < 1 or columns > 5:
            raise ValueError("Valore 'columns' non valido: usare un intero da 1 a 5")
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("Valore 'columns' non valido: usare un intero da 1 a 5")
        raise
    
    if _parse_bool(cfg.get('google', False)) not in (True, False):
        raise ValueError("Valore 'google' non valido. Usare: true, false.")
    
    # Risolve path
    base_dir = os.path.dirname(os.path.abspath(args[0].strip('"\'')))
    bookmark_in = os.path.join(base_dir, cfg['bookmark_in']) if not os.path.isabs(cfg.get('bookmark_in', '')) else cfg.get('bookmark_in', '')
    homepage_out = os.path.join(base_dir, cfg['homepage_out']) if not os.path.isabs(cfg['homepage_out']) else cfg['homepage_out']
    images_path = os.path.join(base_dir, cfg['images_path']) if not os.path.isabs(cfg['images_path']) else cfg['images_path']
    
    if not os.path.exists(bookmark_in):
        raise FileNotFoundError(f"File bookmark di input {bookmark_in} non trovato.")
    
    # Gestisci icons config (opzionale): dizionario URL -> path icona
    icons_config = {}
    if icons_cfg and isinstance(icons_cfg, dict):
        for k, v in icons_cfg.items():
            if isinstance(k, str) and isinstance(v, str):
                # Normalizza URL come chiave
                icons_config[_normalize_url(k)] = v
    
    # Gestisci alias config (opzionale): dizionario nome_url -> nome_alias
    alias_dict = {}
    if alias_cfg and isinstance(alias_cfg, dict):
        for k, v in alias_cfg.items():
            if isinstance(k, str) and isinstance(v, str):
                alias_dict[k.lower()] = v
    
    # Gestisci icona generica (opzionale)
    icogeneric = cfg.get('icogeneric', '')
    if icogeneric and not os.path.isabs(icogeneric):
        icogeneric = os.path.join(images_path, icogeneric)
    icogeneric_abs = os.path.abspath(icogeneric) if icogeneric else None
    
    os.makedirs(images_path, exist_ok=True)
    
    log(f"[{ts()}] Fase 1: Lettura bookmark")
    tree = parse_bookmarks_html(bookmark_in)
    
    log(f"[{ts()}] Fase 2: Ordinamento bookmark (mode={cfg.get('mode', 'normal')})")
    _sort_tree(tree, cfg.get('mode', 'normal'), cfg.get('firsturl', []))
    entries = _flatten_ordered(tree, cfg.get('mode', 'normal'), cfg.get('firsturl', []))
    
    # Calcola path relativo delle icone rispetto alla directory dell'HTML output
    homepage_dir = os.path.dirname(os.path.abspath(homepage_out))
    images_path_abs = os.path.abspath(images_path)
    
    def get_icon_relpath(icon_abs_path):
        """Restituisce path relativo da homepage_dir a icon_abs_path"""
        if not icon_abs_path:
            return None
        try:
            return os.path.relpath(icon_abs_path, start=homepage_dir)
        except ValueError:
            # Su Windows, drive diversi: usa path assoluto
            return icon_abs_path
    
    # Fase Icons - assegnazione icone PRIMA degli alias (usa nomi originali)
    msg_icons = f"Fase Icons: Associazione icone ({len(entries)} voci)"
    log(f"[{ts()}] {msg_icons}")
    print(msg_icons)
    os.makedirs(images_path, exist_ok=True)
    
    # icorefresh: 
    #   true  = FORZA il re-download anche se in cache
    #   false = usa cache se esiste, altrimenti scarica (default)
    icorefresh = _parse_bool(cfg.get('icorefresh', False))
    
    def download_icons_for_entries(entry_list, label):
        result = []
        for entry in entry_list:
            if entry['type'] == 'category':
                result.append({**entry, 'icon': None})
                continue
            
            url_norm = _normalize_url(entry['entry']['url'])
            original_name = entry['entry']['name']  # Nome ORIGINALE prima alias
            base_name = _sanitize_filename(original_name)
            icon_abs_path = None
            icon_source = ''
            
            # 1. Prima: icons config (URL-specific icon) - usa URL normalizzato
            if url_norm in icons_config:
                icon_cfg = icons_config[url_norm]
                if not os.path.isabs(icon_cfg):
                    icon_cfg = os.path.join(images_path_abs, icon_cfg)
                if os.path.exists(icon_cfg):
                    icon_abs_path = icon_cfg
                    icon_source = 'icons config (URL)'
            
            # 2. Seconda: icons config per nome originale (se presente come chiave nome)
            if icon_abs_path is None and original_name in icons_config:
                icon_cfg = icons_config[original_name]
                if not os.path.isabs(icon_cfg):
                    icon_cfg = os.path.join(images_path_abs, icon_cfg)
                if os.path.exists(icon_cfg):
                    icon_abs_path = icon_cfg
                    icon_source = 'icons config (nome)'
            
            # 3. Terza: cerca in cache per nome originale
            if icon_abs_path is None:
                for ext in ['.ico', '.png', '.gif', '.jpg', '.svg']:
                    existing = os.path.join(images_path_abs, base_name + ext)
                    if os.path.exists(existing):
                        icon_abs_path = existing
                        icon_source = 'cache'
                        break
            
            # 4. Quarta: icorefresh=true -> scarica favicon
            if icon_abs_path is None and icorefresh:
                icon_abs_path = _fetch_favicon(entry['entry']['url'], images_path_abs, original_name, True, lambda m: log(f"[{ts()}] ICONA (forzata): {m}"))
                if icon_abs_path:
                    icon_source = 'download'
                else:
                    icon_source = 'not found'
            
            # 5. Quinta: icogeneric se specificata
            if icon_abs_path is None and icogeneric_abs and os.path.exists(icogeneric_abs):
                icon_abs_path = icogeneric_abs
                icon_source = 'icogeneric'
            
            # 6. Sesta: placeholder (nessuna icona)
            if icon_abs_path is None:
                icon_source = 'placeholder'
            
            if icon_abs_path:
                icon_rel = get_icon_relpath(icon_abs_path)
                log(f"[{ts()}] ICONA ({icon_source}): {original_name} -> {icon_rel}")
            else:
                log(f"[{ts()}] ICONA ({icon_source}): {original_name}")
            
            icon_rel = get_icon_relpath(icon_abs_path) if icon_abs_path else None
            
            result.append({
                'type': entry['type'],
                'entry': entry['entry'],
                'category': entry['category'],
                'icon': icon_rel,
                'original_name': original_name  # Memorizza nome originale per riferimento
            })
        return result
    
    entry_data = download_icons_for_entries(entries, "principali")
    
    # ORA applica alias ai nomi (dopo aver assegnato le icone)
    if alias_dict:
        def apply_alias_to_entries(entry_list):
            for entry in entry_list:
                if entry['type'] == 'url':
                    name_lower = entry['entry']['name'].lower()
                    if name_lower in alias_dict:
                        log(f"[{ts()}] Alias: '{entry['entry']['name']}' -> '{alias_dict[name_lower]}'")
                        entry['entry']['name'] = alias_dict[name_lower]
        apply_alias_to_entries(entry_data)
        log(f"[{ts()}] Alias applicati: {len(alias_dict)} regole")
    
    log(f"[{ts()}] Fase 3: Generazione HTML homepage")
    msg_gen = "Fase 3: Generazione HTML homepage"
    log(f"[{ts()}] {msg_gen}")
    print(msg_gen)
    html = _build_homepage_html(
        entry_data,
        int(cfg['columns']),
        cfg.get('title', 'Bookmarks'),
        images_path,
        _parse_bool(cfg.get('google', False)),
        datetime.datetime.now(),
    )
    
    tmp_path = homepage_out + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(html)
    os.replace(tmp_path, homepage_out)
    
    msg_done = f"Homepage generata: {homepage_out}"
    log(f"[{ts()}] {msg_done}")
    print(msg_done)
    return homepage_out


def run_check(args: List[str], log, ts) -> str:
    """bkh check <bookmark_in.html> <bookmark_out.html>. Ritorna path output."""
    if len(args) != 2:
        raise ValueError("Sintassi errata. Uso: bkh check <bookmark_in.html> <bookmark_out.html>")
    
    in_file = args[0].strip('"\'')
    out_file = args[1].strip('"\'')
    
    if not os.path.exists(in_file):
        raise FileNotFoundError(f"File bookmark di input {in_file} non trovato.")
    
    log(f"[{ts()}] Fase 1: Parsing file {in_file}")
    tree = parse_bookmarks_html(in_file)
    
    # Estrae tutti gli URL
    urls = []
    def collect(node):
        for child in node.get('children', []):
            if child['type'] == 'url':
                urls.append(child)
            elif child['type'] == 'folder':
                def rec(n):
                    for c in n.get('children', []):
                        if c['type'] == 'url':
                            urls.append(c)
                        elif c['type'] == 'folder':
                            rec(c)
                rec(child)
    
    for child in tree.get('children', []):
        if child['type'] == 'folder':
            def rec(n):
                for c in n.get('children', []):
                    if c['type'] == 'url':
                        urls.append(c)
                    elif c['type'] == 'folder':
                        rec(c)
            rec(child)
        elif child['type'] == 'url':
            urls.append(child)
    
    # Deduplica
    seen = set()
    unique_urls = []
    for entry in urls:
        norm = _normalize_url(entry['url'])
        if norm not in seen:
            seen.add(norm)
            unique_urls.append(entry)
    
    log(f"[{ts()}] Fase 2: Verifica {len(unique_urls)} URL unici")
    
    # Controlla con ThreadPoolExecutor
    unreachable = []
    max_workers = min(8, len(unique_urls))
    
    def check_one(entry):
        accessible, detail = _check_url(entry['url'])
        return (entry, accessible, detail)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_one, entry): entry for entry in unique_urls}
        for future in concurrent.futures.as_completed(futures):
            entry, accessible, detail = future.result()
            if not accessible:
                unreachable.append(entry)
            log(f"[{ts()}]   {entry['url']}: {'OK' if accessible else 'FAIL'} ({detail})")
    
    log(f"[{ts()}] Fase 3: Scrittura file {args[1]}")
    # Crea albero solo con unreachable
    unreachable_tree = {'type': 'folder', 'name': 'root', 'children': [{'type': 'url', 'name': e['name'], 'url': e['url']} for e in unreachable]}
    _write_bookmarks_html(out_file, unreachable_tree)
    
    log(f"[{ts()}] Completato: {len(unreachable)} non accessibili su {len(unique_urls)} totali")
    return out_file


def run_merge(args: List[str], log, ts) -> str:
    """bkh merge <in> <add> <out>. Ritorna path output."""
    if len(args) != 3:
        raise ValueError("Sintassi errata. Uso: bkh merge <bookmark_in.html> <bookmark_add.html> <bookmark_new.html>")
    
    in_file = args[0].strip('"\'')
    add_file = args[1].strip('"\'')
    out_file = args[2].strip('"\'')
    
    for f in [in_file, add_file]:
        if not os.path.exists(f):
            raise FileNotFoundError(f"File bookmark {f} non trovato.")
    
    log(f"[{ts()}] Fase 1: Lettura file base {in_file}")
    tree_base = parse_bookmarks_html(in_file)
    
    log(f"[{ts()}] Fase 2: Lettura file da aggiungere {add_file}")
    tree_add = parse_bookmarks_html(add_file)
    
    # Normalizza URL base per dedup
    base_urls = set()
    def collect_urls(node):
        for child in node.get('children', []):
            if child['type'] == 'url':
                base_urls.add(_normalize_url(child['url']))
            elif child['type'] == 'folder':
                def rec(n):
                    for c in n.get('children', []):
                        if c['type'] == 'url':
                            base_urls.add(_normalize_url(c['url']))
                        elif c['type'] == 'folder':
                            rec(c)
                rec(child)
    
    for child in tree_base.get('children', []):
        if child['type'] == 'folder':
            def rec(n):
                for c in n.get('children', []):
                    if c['type'] == 'url':
                        base_urls.add(_normalize_url(c['url']))
                    elif c['type'] == 'folder':
                        rec(c)
            rec(child)
        elif child['type'] == 'url':
            base_urls.add(_normalize_url(child['url']))
    
    # Raccoglie nomi usati
    used_names = set()
    def collect_names(node):
        for child in node.get('children', []):
            if child['type'] == 'url':
                used_names.add(child['name'].casefold())
            elif child['type'] == 'folder':
                def rec(n):
                    for c in n.get('children', []):
                        if c['type'] == 'url':
                            used_names.add(c['name'].casefold())
                        elif c['type'] == 'folder':
                            rec(c)
                rec(child)
    
    for child in tree_base.get('children', []):
        if child['type'] == 'folder':
            def rec(n):
                for c in n.get('children', []):
                    if c['type'] == 'url':
                        used_names.add(c['name'].casefold())
                    elif c['type'] == 'folder':
                        rec(c)
            rec(child)
        elif child['type'] == 'url':
            used_names.add(child['name'].casefold())
    
    # Unisce tree_add in tree_base
    log(f"[{ts()}] Fase 3: Unione alberi")
    merged_count = 0
    renamed_count = 0
    
    def merge_node(target_node, source_node):
        nonlocal merged_count, renamed_count
        for child in source_node.get('children', []):
            if child['type'] == 'url':
                norm_url = _normalize_url(child['url'])
                if norm_url in base_urls:
                    # Duplicato: rinomina
                    new_name = _unique_name(child['name'], set(n.casefold() for n in used_names))
                    log(f"[{ts()}] Duplicato rinominato: {child['name']} -> {new_name}")
                    target_node['children'].append({'type': 'url', 'name': new_name, 'url': child['url']})
                    renamed_count += 1
                else:
                    target_node['children'].append(child)
                    base_urls.add(norm_url)
                    used_names.add(child['name'].casefold())
                    merged_count += 1
            elif child['type'] == 'folder':
                # Cerca cartella esistente
                existing = None
                for t in target_node.get('children', []):
                    if t['type'] == 'folder' and t['name'].casefold() == child['name'].casefold():
                        existing = t
                        break
                if existing:
                    merge_node(existing, child)
                else:
                    target_node['children'].append(child)
    
    merge_node(tree_base, tree_add)
    
    log(f"[{ts()}] Fase 4: Scrittura file {args[2]}")
    _write_bookmarks_html(out_file, tree_base)
    
    log(f"[{ts()}] Merge completato: {merged_count} aggiunte, {renamed_count} rinominate")
    return out_file


def run_delete(args: List[str], log, ts) -> str:
    """bkh delete <in> <del> <out>. Ritorna path output."""
    if len(args) != 3:
        raise ValueError("Sintassi errata. Uso: bkh delete <bookmark_in.html> <bookmark_del.html> <bookmark_out.html>")
    
    in_file = args[0].strip('"\'')
    del_file = args[1].strip('"\'')
    out_file = args[2].strip('"\'')
    
    for f in [in_file, del_file]:
        if not os.path.exists(f):
            raise FileNotFoundError(f"File bookmark {f} non trovato.")
    
    log(f"[{ts()}] Fase 1: Lettura file base {in_file}")
    tree_base = parse_bookmarks_html(in_file)
    
    log(f"[{ts()}] Fase 2: Lettura file da eliminare {del_file}")
    tree_del = parse_bookmarks_html(del_file)
    
    # Raccoglie URL da eliminare (normalizzati)
    del_urls = set()
    def collect_del(node):
        for child in node.get('children', []):
            if child['type'] == 'url':
                del_urls.add(_normalize_url(child['url']))
            elif child['type'] == 'folder':
                def rec(n):
                    for c in n.get('children', []):
                        if c['type'] == 'url':
                            del_urls.add(_normalize_url(c['url']))
                        elif c['type'] == 'folder':
                            rec(c)
                rec(child)
    
    for child in tree_del.get('children', []):
        if child['type'] == 'folder':
            def rec(n):
                for c in n.get('children', []):
                    if c['type'] == 'url':
                        del_urls.add(_normalize_url(c['url']))
                    elif c['type'] == 'folder':
                        rec(c)
            rec(child)
        elif child['type'] == 'url':
            del_urls.add(_normalize_url(child['url']))
    
    log(f"[{ts()}] Trovati {len(del_urls)} URL da eliminare")
    
    # Rimuove da tree_base
    def remove_from_tree(node):
        new_children = []
        for child in node.get('children', []):
            if child['type'] == 'url':
                if _normalize_url(child['url']) not in del_urls:
                    new_children.append(child)
            elif child['type'] == 'folder':
                remove_from_tree(child)
                if child.get('children'):
                    new_children.append(child)
        node['children'] = new_children
    
    log(f"[{ts()}] Fase 3: Rimozione URL")
    remove_from_tree(tree_base)
    
    log(f"[{ts()}] Fase 4: Scrittura file {out_file}")
    _write_bookmarks_html(out_file, tree_base)
    
    log(f"[{ts()}] Delete completato")
    return out_file


# ============================================================================
# Helper functions
# ============================================================================

def _load_config(json_path: str) -> Dict:
    """Carica e valida file JSON configurazione."""
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    if 'config' not in config:
        raise ValueError("Sezione 'config' obbligatoria nel file JSON")
    return config


# ============================================================================
# Costruzione HTML Homepage
# ============================================================================

def _build_homepage_html(entries: List[Dict], columns: int, title: str, images_path: str, google: bool, now: datetime.datetime) -> str:
    """Costruisce HTML della homepage.
    
    entries: lista di dict con chiavi: type ('url' o 'category'), entry (dict), category (str), icon (str|None)
    """
    
    # CSS principale (sempre incluso)
    css = """
    <style>
        body { font-family: system-ui, sans-serif; margin: 20px; }
        h1 { text-align: center; }
        table.home { border-collapse: collapse; width: 100%; margin-top: 20px; border: 1px solid #ddd; }
        table.home td { border: 1px solid #ddd; vertical-align: top; padding: 8px 12px; }
        table.home tr.category td { background-color: #fffde7; font-weight: bold; padding: 6px 12px; }
        a.bmk { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; color: #0645ad; }
        a.bmk:hover { text-decoration: underline; }
        a.bmk img { width: 1em; height: 1em; border: 0; vertical-align: middle; }
        #tip { position: fixed; display: none; padding: 6px 10px; background: #222; color: #fff; border-radius: 4px; font-size: 12px; pointer-events: none; z-index: 9999; white-space: nowrap; }
        .header-info { margin-top: 10px; text-align: center; color: #666; font-size: 12px; }
        .made-with { text-align: center; color: #999; font-size: 11px; margin-top: 20px; }
        .made-with a { color: #999; text-decoration: none; }
        .made-with a:hover { text-decoration: underline; }
        .first-title { color: #0066cc; margin-top: 20px; margin-bottom: 10px; }
        .category-title { color: #333; margin: 20px 0 10px 0; }
        .indice { text-align: center; font-size: 10px; color: #666; margin: 15px 0 10px 0; }
        .indice a { color: #0645ad; text-decoration: none; margin: 0 8px; }
        .indice a:hover { text-decoration: underline; }
        .home-link { text-align: left; font-size: 11px; color: #999; margin-top: 5px; }
        .home-link a { color: #999; text-decoration: none; }
        .home-link a:hover { text-decoration: underline; }
    </style>
    """
    
    # Google CSS (solo se google=true) - semplificato
    google_css = ""
    if google:
        google_css = """
    <style>
        .google-wrap { display: flex; justify-content: center; margin: 16px 0 24px; }
        .google-bar { display: flex; align-items: center; background: #fff; border-radius: 999px; padding: 8px 16px; width: 90%; max-width: 680px; box-shadow: 0 2px 8px rgba(0,0,0,0.18); }
        .search-input { flex: 1; border: none; outline: none; font-size: 16px; padding: 0 12px; color: #1f1f1f; background: transparent; }
        .search-input::placeholder { color: #80868b; }
        .search-btn { background: #1a73e8; color: #fff; border: none; border-radius: 999px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: background 0.2s; margin-left: 8px; }
        .search-btn:hover { background: #1557b0; }
    </style>
    """
    
    # Google search bar - link diretto per aprire in AI mode senza conferma
    google_html = ""
    if google:
        google_html = '''
    <div class="google-wrap">
      <form id="searchForm" class="google-bar" action="https://www.google.com/search" method="GET" target="_blank">
        <input type="hidden" name="udm" value="50">
        <input type="text" id="searchInput" name="q" class="search-input" placeholder="Cerca con Google AI Mode" autocomplete="off" required>
        <button type="submit" class="search-btn">Cerca</button>
      </form>
    </div>
        '''
    
    # Raggruppa entries per categoria per generare tabelle separate
    category_groups = []  # lista di (category_name, [entries])
    current_category = None
    current_entries = []
    
    for entry in entries:
        if entry['type'] == 'category':
            # Salva gruppo precedente se esiste
            if current_category is not None or current_entries:
                category_groups.append((current_category, current_entries))
            # Nuovo gruppo
            current_category = entry['entry']['name']
            current_entries = []
        else:
            current_entries.append(entry)
    
    # Ultimo gruppo
    if current_category is not None or current_entries:
        category_groups.append((current_category, current_entries))
    
    # Genera HTML per ogni categoria (tabella separata)
    tables_html = []
    
    # Costruisci l'indice (lista di nomi categoria per i link)
    category_names_for_index = [cat_name for cat_name, _ in category_groups if cat_name]
    
    for idx, (cat_name, cat_entries) in enumerate(category_groups):
        # Indice prima di "Barra dei preferiti" / "Bookmarks bar"
        if cat_name and cat_name.lower() in ('barra dei preferiti', 'bookmarks bar') and category_names_for_index:
            indice_links = ' | '.join(f'<a href="#cat-{html.escape(cn).replace(" ", "-").replace(":", "")}">{html.escape(cn)}</a>' for cn in category_names_for_index)
            tables_html.append(f'<p class="indice">Indice: {indice_links}</p>')
        
        if cat_name:
            tables_html.append(f'<h3 id="cat-{html.escape(cat_name).replace(" ", "-").replace(":", "")}" class="category-title" style="color:#0066cc;">{html.escape(cat_name)}</h3>')
        else:
            tables_html.append('<h3 id="cat-altri-link" class="category-title" style="color:#666;">Altri link</h3>')
        
        # Distribuisci in colonne per questa categoria
        rows = (len(cat_entries) + columns - 1) // columns
        cols_data = [[] for _ in range(columns)]
        for i, entry in enumerate(cat_entries):
            col_idx = i % columns
            cols_data[col_idx].append(entry)
        
        table_rows = []
        max_rows = max((len(col) for col in cols_data), default=0)
        for row_idx in range(max_rows):
            row_cells = []
            for col_idx in range(columns):
                if row_idx < len(cols_data[col_idx]):
                    item = cols_data[col_idx][row_idx]
                    e = item['entry']
                    icon_html = ''
                    if item.get('icon'):
                        icon_html = f'<img src="{item["icon"]}" alt="" style="width:1em;height:1em;vertical-align:middle;">'
                    else:
                        icon_html = '<span style="width:1em;height:1em;display:inline-block;"></span>'
                    row_cells.append(f'<td><a class="bmk" href="{html.escape(e["url"])}" title="{html.escape(e["url"])}" target="_blank">{icon_html} {html.escape(e["name"])}</a></td>')
                else:
                    row_cells.append('<td></td>')
            table_rows.append(f'<tr>{"".join(row_cells)}</tr>')
        
        table_html = f'<table class="home" style="border:1px solid #ddd;border-collapse:collapse;width:100%;margin-bottom:5px;">\n{"".join(f"<tr>{r}</tr>" for r in table_rows)}</table>'
        tables_html.append(table_html)
        
        # Link Home alla fine di ogni categoria
        tables_html.append('<p class="home-link"><a href="#top">↑ Home</a></p>')
    
    table_html = "\n".join(tables_html)
    
    # JS per tooltip
    js = '''
    <script>
        const tip = document.getElementById('tip');
        document.querySelectorAll('a.bmk').forEach(a => {
            a.addEventListener('mousemove', e => {
                tip.textContent = a.href;
                tip.style.display = 'block';
                tip.style.left = (e.clientX + 12) + 'px';
                tip.style.top = (e.clientY + 12) + 'px';
            });
            a.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
        });
    </script>
    '''
    
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    output_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <title>{html.escape(title)}</title>
    {css}
    {google_css}
</head>
<body>
    <h1 id="top">{html.escape(title)}</h1>
    <div class="header-info">Last Update: {now_str} | Now: {now_str}</div>
    {google_html}
    {table_html}
    <div class="made-with">Made with <a href="https://github.com/ntgcorp/adminscripts" target="_blank">ntgcorp/adminiscripts/pyt</a></div>
    <div id="tip"></div>
    {js}
</body>
</html>"""
    return output_html
# ============================================================================
# Main (per testing standalone)
# ============================================================================

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'help':
        print(help_text('it'))
    else:
        print("Modulo pyt_bkh - usa tramite pyt.py bkh <sottocomando>")