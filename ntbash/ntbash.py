import sys, os, shutil, subprocess, re, glob as globmod, fnmatch, io, threading, ast

# --- Ambiente globale ---
env = {'0': 'script.sh'}
current_dir = os.getcwd()
positional = []
last_exit = 0
last_bg = 0
functions = {}
func_depth = 0
out = sys.stdout

DOCS = {
    "echo [-e] [-n] testo": "Stampa testo; -e interpreta \\n, \\t; -n senza newline.",
    "pwd": "Mostra la cartella corrente.",
    "cd [dir]": "Cambia directory (senza argomenti -> $HOME).",
    "ls [-l] [-a] [dir...]": "Elenca file e cartelle.",
    "mkdir [-p] dir": "Crea directory.",
    "cp src dst": "Copia file.",
    "mv src dst": "Sposta/rinomina.",
    "rm [-r] [-f] file": "Elimina file/directory.",
    "cat file": "Stampa il contenuto di un file.",
    "export VAR[=val]": "Esporta una variabile.",
    "unset VAR": "Rimuove una variabile.",
    "read var": "Legge una riga da stdin.",
    "exit [N]": "Termina lo script con exit code N.",
    "source file": "Esegue un altro script nello stesso ambiente.",
    "test / [ ] / [[ ]]": "Confronti e test su file.",
    "$((math))": "Espansione aritmetica, es: $((10/2)).",
    "$(comando)": "Sostituzione di comando.",
    "pipe (|)": "Collega l'output di un comando all'input del successivo.",
    "redirezione (>)": "> sovrascrive, >> accoda, < legge, 2> stderr.",
    "#": "Commento fino a fine riga.",
    "{...}": "Blocco di comandi.",
    "if/for/while/case": "Strutture di controllo.",
    "funzioni nome() { ... }": "Definizione di funzioni."
}

def show_help():
    return "--- HELP NTBASH ---\n" + "\n".join(f" {k}: {v}" for k, v in DOCS.items())

# --- Segnali di controllo ---
class ExitSignal(Exception):
    def __init__(self, code=0):
        self.code = code

class ReturnSignal(Exception):
    def __init__(self, code=0):
        self.code = code

class BreakSignal(Exception):
    pass

class ContinueSignal(Exception):
    pass

# --- Accesso alle variabili ---
def get_var(name):
    return env.get(name, '')

def get_positional(n):
    if n == 0:
        return env.get('0', '')
    if n <= len(positional):
        return positional[n - 1]
    return ''

def get_special(ch):
    if ch == '?': return str(last_exit)
    if ch == '$': return str(os.getpid())
    if ch == '!': return str(last_bg)
    if ch == '#': return str(len(positional))
    if ch == '@': return ' '.join(positional)
    if ch == '*': return ' '.join(positional)
    return ''

# --- Aritmetica sicura (ast, niente eval nudo) ---
def eval_arith(expr):
    expr = expr.strip()
    if not expr:
        return 0
    try:
        return int(eval_arith_node(ast.parse(expr, mode='eval').body))
    except Exception:
        return 0

def eval_arith_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return int(node.value)
        return 0
    if isinstance(node, ast.BinOp):
        left = eval_arith_node(node.left)
        right = eval_arith_node(node.right)
        op = node.op
        if isinstance(op, ast.Add): return left + right
        if isinstance(op, ast.Sub): return left - right
        if isinstance(op, ast.Mult): return left * right
        if isinstance(op, ast.Div): return int(left / right) if right else 0
        if isinstance(op, ast.FloorDiv): return left // right if right else 0
        if isinstance(op, ast.Mod): return left % right if right else 0
        if isinstance(op, ast.Pow): return int(left ** right)
        return 0
    if isinstance(node, ast.UnaryOp):
        v = eval_arith_node(node.operand)
        if isinstance(node.op, ast.USub): return -v
        if isinstance(node.op, ast.UAdd): return v
        return v
    if isinstance(node, ast.Name):
        try:
            return int(env.get(node.id, '0') or 0)
        except ValueError:
            return 0
    if isinstance(node, ast.Compare):
        left = eval_arith_node(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = eval_arith_node(comp)
            if isinstance(op, ast.Lt): left = 1 if left < right else 0
            elif isinstance(op, ast.LtE): left = 1 if left <= right else 0
            elif isinstance(op, ast.Gt): left = 1 if left > right else 0
            elif isinstance(op, ast.GtE): left = 1 if left >= right else 0
            elif isinstance(op, ast.Eq): left = 1 if left == right else 0
            elif isinstance(op, ast.NotEq): left = 1 if left != right else 0
        return left
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not eval_arith_node(v):
                    return 0
            return 1
        for v in node.values:
            if eval_arith_node(v):
                return 1
        return 0
    return 0

# --- Espansioni ---
def has_glob_chars(s):
    return any(ch in s for ch in '*?[')

def expand_arith(text):
    result = ''
    i = 0
    n = len(text)
    while i < n:
        if text[i:i+3] == '$((':
            depth = 1
            j = i + 3
            while j < n:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            expr = text[i+3:j]
            expr = expand_vars(expr)
            result += str(eval_arith(expr))
            i = j + 2
        else:
            result += text[i]
            i += 1
    return result

def expand_vars(text):
    result = ''
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '$' and i + 1 < n:
            nxt = text[i+1]
            if nxt == '{':
                j = text.find('}', i + 2)
                if j != -1:
                    inner = text[i+2:j]
                    result += expand_braced(inner)
                    i = j + 1
                    continue
                result += c
                i += 1
            elif nxt == '(':
                result += c
                i += 1
            elif nxt.isalpha() or nxt == '_':
                j = i + 1
                while j < n and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                result += get_var(text[i+1:j])
                i = j
            elif nxt.isdigit():
                j = i + 1
                while j < n and text[j].isdigit():
                    j += 1
                result += get_positional(int(text[i+1:j]))
                i = j
            elif nxt in '?$!#@*':
                result += get_special(nxt)
                i += 2
            else:
                result += c
                i += 1
        else:
            result += c
            i += 1
    return result

def expand_braced(inner):
    if inner.startswith('#'):
        return str(len(get_var(inner[1:])))
    for op in (':-', ':=', ':+'):
        if op in inner:
            name, default = inner.split(op, 1)
            val = get_var(name)
            if op == ':-':
                return default if not val else val
            if op == ':=':
                if not val:
                    env[name] = default
                    return default
                return val
            if op == ':+':
                return default if val else ''
    if '##' in inner:
        name, pat = inner.split('##', 1)
        val = get_var(name)
        m = re.match(r'^.*' + pat, val)
        return val[m.end():] if m else val
    if '%%' in inner:
        name, pat = inner.split('%%', 1)
        val = get_var(name)
        m = re.search(r'.*' + pat + r'$', val)
        return val[:m.start()] if m else val
    if '#' in inner:
        name, pat = inner.split('#', 1)
        val = get_var(name)
        m = re.match(r'^.*?' + pat, val)
        return val[m.end():] if m else val
    if '%' in inner:
        name, pat = inner.split('%', 1)
        val = get_var(name)
        m = re.search(pat + r'$', val)
        return val[:m.start()] if m else val
    m = re.match(r'([A-Za-z_][A-Za-z0-9_]*):(-?\d+)(?::(-?\d+))?', inner)
    if m:
        name, off, ln = m.group(1), int(m.group(2)), m.group(3)
        val = get_var(name)
        if ln is None:
            return val[off:]
        return val[off:off + int(ln)]
    return get_var(inner)

def run_cmdsubst(cmd):
    global out
    old_out = out
    buf = io.StringIO()
    out = buf
    try:
        execute_script_text(cmd)
    finally:
        out = old_out
    return buf.getvalue().rstrip('\n')

def expand_cmdsubst(text):
    result = ''
    i = 0
    n = len(text)
    while i < n:
        if text[i:i+2] == '$(' and text[i+2:i+3] != '(':
            depth = 1
            j = i + 2
            while j < n:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            result += run_cmdsubst(text[i+2:j])
            i = j + 1
        elif text[i] == '`':
            j = text.find('`', i + 1)
            if j != -1:
                result += run_cmdsubst(text[i+1:j])
                i = j + 1
            else:
                result += text[i]
                i += 1
        else:
            result += text[i]
            i += 1
    return result

def expand_text(text):
    text = expand_arith(text)
    text = expand_vars(text)
    text = expand_cmdsubst(text)
    return text

def expand_word(segs):
    text = ''
    glob_allowed = False
    for kind, val in segs:
        if kind == 'sq':
            text += val
        elif kind == 'dq':
            text += expand_text(val)
        else:
            text += expand_text(val)
            if has_glob_chars(val):
                glob_allowed = True
    if glob_allowed:
        matches = globmod.glob(text)
        if matches:
            return matches
    return [text]

def split_assignment(segs):
    if not segs:
        return None
    kind, val = segs[0]
    if kind != 'lit':
        return None
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', val)
    if not m:
        return None
    name = m.group(1)
    rest = m.group(2)
    value_segs = [('lit', rest)] if rest else []
    value_segs.extend(segs[1:])
    return name, value_segs

# --- Tokenizer ---
def tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r':
            i += 1
            continue
        if c == '\n':
            tokens.append(('NL',))
            i += 1
            continue
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if text[i:i+4] == '2>&1':
            tokens.append(('OP', '2>&1'))
            i += 4
            continue
        if text[i:i+3] == '2>>':
            tokens.append(('OP', '2>>'))
            i += 3
            continue
        two = text[i:i+2]
        if two in ('&&', '||', '>>', '<<', ';;', ';&', '|&', '&>', '2>'):
            tokens.append(('OP', two))
            i += 2
            continue
        if c in ';|&(){}<>':
            tokens.append(('OP', c))
            i += 1
            continue
        segs = []
        while i < n:
            c = text[i]
            if c in ' \t\r\n;|&(){}<>':
                break
            if c == '#' and not segs:
                break
            if c == "'":
                j = text.find("'", i + 1)
                if j == -1:
                    segs.append(('sq', text[i+1:]))
                    i = n
                else:
                    segs.append(('sq', text[i+1:j]))
                    i = j + 1
                continue
            if c == '"':
                j = i + 1
                buf = ''
                while j < n and text[j] != '"':
                    if text[j] == '\\' and j + 1 < n and text[j+1] in '"\\$`':
                        buf += text[j+1]
                        j += 2
                        continue
                    buf += text[j]
                    j += 1
                segs.append(('dq', buf))
                i = j + 1
                continue
            if c == '\\':
                if i + 1 < n:
                    segs.append(('lit', text[i+1]))
                    i += 2
                else:
                    i += 1
                continue
            if c == '$' and i + 1 < n and text[i+1] == '(':
                depth = 1
                j = i + 2
                while j < n:
                    if text[j] == '(':
                        depth += 1
                    elif text[j] == ')':
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                segs.append(('lit', text[i:j+1]))
                i = j + 1
                continue
            if c == '$' and i + 1 < n and text[i+1] == '{':
                j = text.find('}', i + 2)
                if j != -1:
                    segs.append(('lit', text[i:j+1]))
                    i = j + 1
                    continue
            j = i
            buf = ''
            while j < n and text[j] not in ' \t\r\n;|&(){}<>\'"\\':
                if text[j] == '$' and j + 1 < n and text[j+1] in '({':
                    break
                buf += text[j]
                j += 1
            segs.append(('lit', buf))
            i = j
        tokens.append(('WORD', segs))
    tokens.append(('EOF',))
    return tokens

# --- Heredoc ---
def preprocess_heredocs(text):
    heredocs = []
    lines = text.split('\n')
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.search(r'<<\s*([A-Za-z_][A-Za-z0-9_]*)', line)
        if m:
            delim = m.group(1)
            j = i + 1
            content = []
            while j < len(lines):
                if lines[j].strip() == delim:
                    break
                content.append(lines[j])
                j += 1
            heredocs.append('\n'.join(content))
            line = line[:m.start()] + '<< HEREDOC%d' % (len(heredocs) - 1) + line[m.end():]
            out.append(line)
            i = j + 1
        else:
            out.append(line)
            i += 1
    return '\n'.join(out), heredocs

# --- AST ---
class Cmd:
    def __init__(self, words, redirs, background=False, assigns=None):
        self.words = words
        self.redirs = redirs
        self.background = background
        self.assigns = assigns or []

class Pipeline:
    def __init__(self, cmds):
        self.cmds = cmds

class AndOr:
    def __init__(self, parts):
        self.parts = parts

class List:
    def __init__(self, parts):
        self.parts = parts

class If:
    def __init__(self, cond, then_body, elifs, else_body):
        self.cond = cond
        self.then_body = then_body
        self.elifs = elifs
        self.else_body = else_body

class For:
    def __init__(self, var, items, body):
        self.var = var
        self.items = items
        self.body = body

class While:
    def __init__(self, cond, body, until=False):
        self.cond = cond
        self.body = body
        self.until = until

class Case:
    def __init__(self, word, branches):
        self.word = word
        self.branches = branches

class Func:
    def __init__(self, name, body):
        self.name = name
        self.body = body

class Block:
    def __init__(self, body):
        self.body = body

class Subshell:
    def __init__(self, body):
        self.body = body

# --- Parser ---
class Parser:
    def __init__(self, tokens, heredocs):
        self.tokens = tokens
        self.heredocs = heredocs
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def next(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def word_text(self, t):
        return ''.join(seg for _, seg in t[1])

    def is_op(self, op):
        t = self.peek()
        return t[0] == 'OP' and t[1] == op

    def expect_op(self, op):
        if self.is_op(op):
            self.next()
            return True
        return False

    def expect_keyword(self, kw):
        t = self.peek()
        if t[0] == 'WORD' and self.word_text(t) == kw:
            self.next()
            return True
        return False

    def parse_program(self):
        return self.parse_list(stop=set())

    def parse_list(self, stop=None):
        stop = stop or set()
        parts = []
        while True:
            t = self.peek()
            if t[0] == 'EOF':
                break
            if t[0] == 'OP' and t[1] in ('}', ')', ';;', ';&'):
                break
            if t[0] == 'WORD' and self.word_text(t) in stop:
                break
            if t[0] == 'NL':
                self.next()
                continue
            node = self.parse_and_or()
            if node is None:
                self.next()
                continue
            parts.append((None, node))
            t = self.peek()
            if t[0] == 'OP' and t[1] in (';', '&'):
                op = self.next()[1]
                parts[-1] = (op, node)
            elif t[0] == 'NL':
                self.next()
            elif t[0] == 'EOF':
                break
            elif t[0] == 'OP' and t[1] in ('}', ')', ';;', ';&'):
                break
            elif t[0] == 'WORD' and self.word_text(t) in stop:
                break
            else:
                break
        return List(parts)

    def parse_and_or(self):
        first = self.parse_pipeline()
        if first is None:
            return None
        parts = [(None, first)]
        while True:
            t = self.peek()
            if t[0] == 'OP' and t[1] in ('&&', '||'):
                op = self.next()[1]
                node = self.parse_pipeline()
                if node is None:
                    break
                parts.append((op, node))
            else:
                break
        if len(parts) == 1:
            return parts[0][1]
        return AndOr(parts)

    def parse_pipeline(self):
        cmds = []
        first = self.parse_command()
        if first is not None:
            cmds.append(first)
        while True:
            t = self.peek()
            if t[0] == 'OP' and t[1] in ('|', '|&'):
                self.next()
                c = self.parse_command()
                if c is not None:
                    cmds.append(c)
            else:
                break
        if not cmds:
            return None
        if len(cmds) == 1:
            return cmds[0]
        return Pipeline(cmds)

    def parse_command(self):
        t = self.peek()
        if t[0] == 'OP' and t[1] == '{':
            self.next()
            return self.parse_block()
        if t[0] == 'OP' and t[1] == '(':
            self.next()
            return self.parse_subshell()
        if t[0] == 'WORD':
            text = self.word_text(t)
            if text in ('if', 'for', 'while', 'until', 'case', 'function'):
                self.next()
                return self.parse_compound(text)
            if self.pos + 2 < len(self.tokens):
                t1 = self.tokens[self.pos + 1]
                t2 = self.tokens[self.pos + 2]
                if t1[0] == 'OP' and t1[1] == '(' and t2[0] == 'OP' and t2[1] == ')':
                    name = text
                    self.next()
                    self.next()
                    self.next()
                    if self.is_op('{'):
                        self.next()
                        body = self.parse_list(stop={'}'})
                        self.expect_op('}')
                        return Func(name, body)
                    body = self.parse_list(stop=set())
                    return Func(name, body)
        words = []
        assigns = []
        redirs = []
        background = False
        while True:
            t = self.peek()
            if t[0] == 'WORD':
                segs = self.next()[1]
                if not words:
                    asg = split_assignment(segs)
                    if asg:
                        assigns.append(asg)
                        continue
                words.append(segs)
            elif t[0] == 'OP' and t[1] in ('>', '>>', '<', '2>', '2>>', '2>&1', '&>', '<<'):
                op = self.next()[1]
                if op == '<<':
                    tt = self.peek()
                    if tt[0] == 'WORD':
                        marker = self.word_text(tt)
                        self.next()
                        if marker.startswith('HEREDOC') and marker[7:].isdigit():
                            idx = int(marker[7:])
                            content = self.heredocs[idx] if idx < len(self.heredocs) else ''
                            redirs.append(('<<', content))
                        else:
                            redirs.append(('<<', ''))
                    else:
                        redirs.append(('<<', ''))
                else:
                    tt = self.peek()
                    if tt[0] == 'WORD':
                        target = self.next()[1]
                    else:
                        target = [('lit', '')]
                    redirs.append((op, target))
            elif t[0] == 'OP' and t[1] == '&':
                self.next()
                background = True
                break
            else:
                break
        if not words and not redirs and not assigns:
            return None
        return Cmd(words, redirs, background, assigns)

    def parse_compound(self, kw):
        if kw == 'if':
            return self.parse_if()
        if kw == 'for':
            return self.parse_for()
        if kw == 'while':
            return self.parse_while(False)
        if kw == 'until':
            return self.parse_while(True)
        if kw == 'case':
            return self.parse_case()
        if kw == 'function':
            return self.parse_function()
        return None

    def parse_if(self):
        cond = self.parse_list(stop={'then'})
        self.expect_keyword('then')
        then_body = self.parse_list(stop={'elif', 'else', 'fi'})
        elifs = []
        else_body = None
        while True:
            t = self.peek()
            if t[0] == 'WORD' and self.word_text(t) == 'elif':
                self.next()
                c = self.parse_list(stop={'then'})
                self.expect_keyword('then')
                b = self.parse_list(stop={'elif', 'else', 'fi'})
                elifs.append((c, b))
            elif t[0] == 'WORD' and self.word_text(t) == 'else':
                self.next()
                else_body = self.parse_list(stop={'fi'})
            elif t[0] == 'WORD' and self.word_text(t) == 'fi':
                self.next()
                break
            else:
                break
        return If(cond, then_body, elifs, else_body)

    def parse_for(self):
        t = self.next()
        var = self.word_text(t)
        items = None
        t = self.peek()
        if t[0] == 'WORD' and self.word_text(t) == 'in':
            self.next()
            items = []
            while True:
                t = self.peek()
                if t[0] == 'WORD':
                    items.append(self.next()[1])
                elif t[0] == 'OP' and t[1] in (';', '&'):
                    self.next()
                    break
                elif t[0] == 'NL':
                    self.next()
                    break
                else:
                    break
        else:
            while True:
                t = self.peek()
                if t[0] == 'OP' and t[1] in (';', '&'):
                    self.next()
                    break
                if t[0] == 'NL':
                    self.next()
                    break
                if t[0] == 'EOF':
                    break
                self.next()
        self.expect_keyword('do')
        body = self.parse_list(stop={'done'})
        self.expect_keyword('done')
        return For(var, items, body)

    def parse_while(self, until):
        cond = self.parse_list(stop={'do'})
        self.expect_keyword('do')
        body = self.parse_list(stop={'done'})
        self.expect_keyword('done')
        return While(cond, body, until)

    def parse_case(self):
        t = self.next()
        word = t[1]
        self.expect_keyword('in')
        branches = []
        while True:
            t = self.peek()
            if t[0] == 'WORD' and self.word_text(t) == 'esac':
                self.next()
                break
            if t[0] == 'NL':
                self.next()
                continue
            if t[0] == 'EOF':
                break
            patterns = []
            while True:
                t = self.peek()
                if t[0] == 'OP' and t[1] == ')':
                    self.next()
                    break
                if t[0] == 'WORD':
                    patterns.append(self.next()[1])
                elif t[0] == 'OP' and t[1] == '|':
                    self.next()
                else:
                    break
            body = self.parse_list(stop={'esac'})
            t = self.peek()
            if t[0] == 'OP' and t[1] in (';;', ';&'):
                self.next()
            branches.append((patterns, body))
        return Case(word, branches)

    def parse_function(self):
        t = self.next()
        name = self.word_text(t)
        if self.is_op('('):
            self.next()
            self.expect_op(')')
        if self.is_op('{'):
            self.next()
            body = self.parse_list(stop={'}'})
            self.expect_op('}')
            return Func(name, body)
        body = self.parse_list(stop=set())
        return Func(name, body)

    def parse_block(self):
        body = self.parse_list(stop={'}'})
        self.expect_op('}')
        return Block(body)

    def parse_subshell(self):
        body = self.parse_list(stop={')'})
        self.expect_op(')')
        return Subshell(body)

# --- Redirezioni ---
def setup_redirs(redirs):
    to_close = []
    stdin = stdout = stderr = None
    for op, target in redirs:
        if op == '<<':
            stdin = io.StringIO(target)
            continue
        if isinstance(target, list):
            target = expand_word(target)[0]
        path = target if os.path.isabs(target) else os.path.join(current_dir, target)
        if op == '>':
            f = open(path, 'w', encoding='utf-8')
            to_close.append(f)
            stdout = f
        elif op == '>>':
            f = open(path, 'a', encoding='utf-8')
            to_close.append(f)
            stdout = f
        elif op == '<':
            f = open(path, 'r', encoding='utf-8')
            to_close.append(f)
            stdin = f
        elif op == '2>':
            f = open(path, 'w', encoding='utf-8')
            to_close.append(f)
            stderr = f
        elif op == '2>>':
            f = open(path, 'a', encoding='utf-8')
            to_close.append(f)
            stderr = f
        elif op == '2>&1':
            stderr = stdout
        elif op == '&>':
            f = open(path, 'w', encoding='utf-8')
            to_close.append(f)
            stdout = f
            stderr = f
    return stdin, stdout, stderr, to_close

# --- Esecuzione comandi esterni ---
def run_external(name, args, stdin, stdout, stderr, input_data, capture):
    kwargs = dict(cwd=current_dir, text=True)
    if input_data is not None:
        kwargs['input'] = input_data
    elif stdin is not None:
        kwargs['stdin'] = stdin
    if capture:
        kwargs['stdout'] = subprocess.PIPE
        if stderr is None:
            kwargs['stderr'] = subprocess.PIPE
        else:
            kwargs['stderr'] = stderr
    elif stdout is None:
        kwargs['capture_output'] = True
        if stderr is not None:
            kwargs['stderr'] = stderr
    else:
        kwargs['stdout'] = stdout
        if stderr is not None:
            kwargs['stderr'] = stderr
    try:
        proc = subprocess.run([name] + args, **kwargs)
    except FileNotFoundError:
        print(f"ntbash: {name}: comando non trovato", file=sys.stderr)
        return 127, ''
    except Exception as e:
        print(f"ntbash: {name}: {e}", file=sys.stderr)
        return 1, ''
    if capture:
        return proc.returncode, proc.stdout or ''
    if stdout is None and proc.stdout:
        out.write(proc.stdout)
    return proc.returncode, ''

# --- Esecuzione comando semplice ---
def run_command(cmd, input_data=None, capture=False):
    global out, last_exit, last_bg
    for name, value_segs in cmd.assigns:
        env[name] = expand_word(value_segs)[0]
    words = []
    for segs in cmd.words:
        words.extend(expand_word(segs))
    if not words:
        return 0, ''
    name = words[0]
    args = words[1:]
    if name == 'break':
        raise BreakSignal()
    if name == 'continue':
        raise ContinueSignal()
    if name == 'return':
        code = int(args[0]) if args else last_exit
        if func_depth > 0:
            raise ReturnSignal(code)
        raise ExitSignal(code)
    if name == 'exit':
        code = int(args[0]) if args else last_exit
        raise ExitSignal(code)
    stdin, stdout, stderr, to_close = setup_redirs(cmd.redirs)
    try:
        if name in functions:
            code = execute_function_call(name, args, input_data, capture, stdout)
            last_exit = code
            return code, ''
        if name in builtins:
            old_in, old_out = sys.stdin, out
            if input_data is not None:
                sys.stdin = io.StringIO(input_data)
            elif stdin is not None:
                sys.stdin = stdin
            if capture:
                buf = io.StringIO()
                out = buf
            elif stdout is not None:
                out = stdout
            old_err = None
            if stderr is not None:
                old_err = sys.stderr
                sys.stderr = stderr
            try:
                code = builtins[name](args)
            finally:
                sys.stdin = old_in
                out = old_out
                if old_err is not None:
                    sys.stderr = old_err
            last_exit = code
            return code, (buf.getvalue() if capture else '')
        code, output = run_external(name, args, stdin, stdout, stderr, input_data, capture)
        last_exit = code
        return code, output
    finally:
        for f in to_close:
            f.close()

def execute_function_call(name, args, input_data=None, capture=False, stdout=None):
    global out, positional, func_depth
    if name not in functions:
        return 127
    old_pos = positional
    positional = args
    old_in, old_out = sys.stdin, out
    if input_data is not None:
        sys.stdin = io.StringIO(input_data)
    if capture:
        buf = io.StringIO()
        out = buf
    elif stdout is not None:
        out = stdout
    func_depth += 1
    try:
        try:
            code = execute_node(functions[name])
        except ReturnSignal as e:
            code = e.code
    finally:
        func_depth -= 1
        positional = old_pos
        sys.stdin = old_in
        out = old_out
    return code

# --- Esecuzione strutture ---
def execute_pipeline(pipeline):
    cmds = pipeline.cmds
    input_data = None
    last_code = 0
    for idx, cmd in enumerate(cmds):
        is_last = (idx == len(cmds) - 1)
        code, output = run_command(cmd, input_data=input_data, capture=not is_last)
        last_code = code
        input_data = output
    return last_code

def execute_if(node):
    code = execute_node(node.cond)
    if code == 0:
        return execute_node(node.then_body)
    for cond, body in node.elifs:
        code = execute_node(cond)
        if code == 0:
            return execute_node(body)
    if node.else_body is not None:
        return execute_node(node.else_body)
    return 0

def execute_for(node):
    if node.items is None:
        items = list(positional)
    else:
        items = []
        for segs in node.items:
            items.extend(expand_word(segs))
    for item in items:
        env[node.var] = item
        try:
            execute_node(node.body)
        except ContinueSignal:
            continue
        except BreakSignal:
            break
    return 0

def execute_while(node):
    while True:
        code = execute_node(node.cond)
        if node.until:
            if code == 0:
                break
        else:
            if code != 0:
                break
        try:
            execute_node(node.body)
        except ContinueSignal:
            continue
        except BreakSignal:
            break
    return 0

def execute_case(node):
    word = expand_word(node.word)[0]
    for patterns, body in node.branches:
        for pat_segs in patterns:
            pat = expand_word(pat_segs)[0]
            if fnmatch.fnmatch(word, pat):
                return execute_node(body)
    return 0

def execute_background(node):
    global last_bg
    if isinstance(node, Cmd):
        words = []
        for segs in node.words:
            words.extend(expand_word(segs))
        if words and words[0] not in builtins and words[0] not in functions:
            try:
                p = subprocess.Popen(words, cwd=current_dir, shell=False)
                last_bg = p.pid
                return 0
            except Exception:
                pass
    t = threading.Thread(target=lambda: execute_node(node))
    t.start()
    last_bg = t.ident or 0
    return 0

def execute_node(node):
    if node is None:
        return 0
    if isinstance(node, Cmd):
        code, _ = run_command(node)
        return code
    if isinstance(node, Pipeline):
        return execute_pipeline(node)
    if isinstance(node, AndOr):
        code = 0
        for i, (op, part) in enumerate(node.parts):
            if i == 0:
                code = execute_node(part)
            elif op == '&&':
                if code == 0:
                    code = execute_node(part)
            elif op == '||':
                if code != 0:
                    code = execute_node(part)
        return code
    if isinstance(node, List):
        code = 0
        for op, part in node.parts:
            if op == '&':
                execute_background(part)
                code = 0
            else:
                code = execute_node(part)
        return code
    if isinstance(node, If):
        return execute_if(node)
    if isinstance(node, For):
        return execute_for(node)
    if isinstance(node, While):
        return execute_while(node)
    if isinstance(node, Case):
        return execute_case(node)
    if isinstance(node, Block):
        return execute_node(node.body)
    if isinstance(node, Subshell):
        return execute_node(node.body)
    if isinstance(node, Func):
        functions[node.name] = node.body
        return 0
    return 0

# --- Builtin ---
def builtin_echo(args):
    newline = True
    escapes = False
    i = 0
    while i < len(args) and args[i].startswith('-') and len(args[i]) > 1 and all(ch in 'en' for ch in args[i][1:]):
        if 'e' in args[i]:
            escapes = True
        if 'n' in args[i]:
            newline = False
        i += 1
    msg = ' '.join(args[i:])
    if escapes:
        msg = msg.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r').replace('\\\\', '\\')
    out.write(msg)
    if newline:
        out.write('\n')
    return 0

def builtin_pwd(args):
    out.write(current_dir + '\n')
    return 0

def builtin_cd(args):
    global current_dir
    target = args[0] if args else env.get('HOME', '')
    if not target:
        return 0
    path = target if os.path.isabs(target) else os.path.join(current_dir, target)
    if os.path.isdir(path):
        current_dir = os.path.normpath(path)
        return 0
    print(f"ntbash: cd: {target}: nessuna directory", file=sys.stderr)
    return 1

def builtin_ls(args):
    long = False
    all_ = False
    targets = []
    for a in args:
        if a.startswith('-') and len(a) > 1:
            if 'l' in a:
                long = True
            if 'a' in a:
                all_ = True
        else:
            targets.append(a)
    if not targets:
        targets = ['.']
    for t in targets:
        path = t if os.path.isabs(t) else os.path.join(current_dir, t)
        if os.path.isdir(path):
            entries = sorted(os.listdir(path))
            if not all_:
                entries = [e for e in entries if not e.startswith('.')]
            if long:
                for e in entries:
                    ep = os.path.join(path, e)
                    try:
                        st = os.stat(ep)
                    except OSError:
                        continue
                    mode = 'd' if os.path.isdir(ep) else '-'
                    out.write(f"{mode} {st.st_size:>8} {e}\n")
            else:
                out.write('  '.join(entries) + '\n')
        elif os.path.exists(path):
            out.write(t + '\n')
        else:
            print(f"ntbash: ls: {t}: nessun file o directory", file=sys.stderr)
            return 2
    return 0

def builtin_mkdir(args):
    parents = False
    targets = []
    for a in args:
        if a == '-p':
            parents = True
        else:
            targets.append(a)
    for t in targets:
        path = t if os.path.isabs(t) else os.path.join(current_dir, t)
        try:
            if parents:
                os.makedirs(path, exist_ok=True)
            else:
                os.mkdir(path)
        except OSError as e:
            print(f"ntbash: mkdir: {t}: {e.strerror}", file=sys.stderr)
            return 1
    return 0

def builtin_cp(args):
    if len(args) < 2:
        print("ntbash: cp: argomenti mancanti", file=sys.stderr)
        return 1
    src = args[0] if os.path.isabs(args[0]) else os.path.join(current_dir, args[0])
    dst = args[-1] if os.path.isabs(args[-1]) else os.path.join(current_dir, args[-1])
    try:
        if os.path.isdir(dst):
            shutil.copy(src, dst)
        else:
            shutil.copy(src, dst)
        return 0
    except OSError as e:
        print(f"ntbash: cp: {e}", file=sys.stderr)
        return 1

def builtin_mv(args):
    if len(args) < 2:
        print("ntbash: mv: argomenti mancanti", file=sys.stderr)
        return 1
    src = args[0] if os.path.isabs(args[0]) else os.path.join(current_dir, args[0])
    dst = args[-1] if os.path.isabs(args[-1]) else os.path.join(current_dir, args[-1])
    try:
        shutil.move(src, dst)
        return 0
    except OSError as e:
        print(f"ntbash: mv: {e}", file=sys.stderr)
        return 1

def builtin_rm(args):
    recursive = False
    force = False
    targets = []
    for a in args:
        if a in ('-r', '-R'):
            recursive = True
        elif a == '-f':
            force = True
        else:
            targets.append(a)
    for t in targets:
        path = t if os.path.isabs(t) else os.path.join(current_dir, t)
        try:
            if os.path.isdir(path) and not recursive:
                print(f"ntbash: rm: {t}: è una directory", file=sys.stderr)
                return 1
            if recursive:
                shutil.rmtree(path, ignore_errors=force)
            else:
                os.remove(path)
        except OSError as e:
            if not force:
                print(f"ntbash: rm: {t}: {e.strerror}", file=sys.stderr)
                return 1
    return 0

def builtin_cat(args):
    if not args:
        data = sys.stdin.read()
        out.write(data)
        return 0
    for a in args:
        path = a if os.path.isabs(a) else os.path.join(current_dir, a)
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                out.write(f.read())
        except OSError as e:
            print(f"ntbash: cat: {a}: {e.strerror}", file=sys.stderr)
            return 1
    return 0

def builtin_export(args):
    for a in args:
        if '=' in a:
            k, v = a.split('=', 1)
            env[k] = v
        elif a not in env:
            env[a] = ''
    return 0

def builtin_unset(args):
    for a in args:
        env.pop(a, None)
    return 0

def builtin_read(args):
    if not args:
        return 1
    line = sys.stdin.readline()
    if not line:
        return 1
    line = line.rstrip('\n')
    if len(args) == 1:
        env[args[0]] = line
    else:
        parts = line.split(None, len(args) - 1)
        for i, v in enumerate(args):
            env[v] = parts[i] if i < len(parts) else ''
    return 0

def builtin_help(args):
    out.write(show_help())
    return 0

def builtin_source(args):
    if not args:
        return 1
    path = args[0] if os.path.isabs(args[0]) else os.path.join(current_dir, args[0])
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError as e:
        print(f"ntbash: source: {args[0]}: {e.strerror}", file=sys.stderr)
        return 1
    return execute_script_text(text)

def builtin_test(args):
    if args and args[-1] in (']', ']]'):
        args = args[:-1]
    if not args:
        return 1
    if args[0] == '!':
        return 0 if builtin_test(args[1:]) != 0 else 1
    if len(args) == 1:
        return 0 if args[0] else 1
    if len(args) == 2:
        op, val = args
        path = val if os.path.isabs(val) else os.path.join(current_dir, val)
        if op == '-f': return 0 if os.path.isfile(path) else 1
        if op == '-d': return 0 if os.path.isdir(path) else 1
        if op == '-e': return 0 if os.path.exists(path) else 1
        if op == '-z': return 0 if not val else 1
        if op == '-n': return 0 if val else 1
        return 1
    if len(args) == 3:
        a, op, b = args
        if op in ('=', '=='):
            if has_glob_chars(b):
                return 0 if fnmatch.fnmatch(a, b) else 1
            return 0 if a == b else 1
        if op == '!=':
            return 0 if a != b else 1
        if op in ('-eq', '-ne', '-lt', '-le', '-gt', '-ge'):
            try:
                x, y = int(a), int(b)
            except ValueError:
                return 2
            if op == '-eq': return 0 if x == y else 1
            if op == '-ne': return 0 if x != y else 1
            if op == '-lt': return 0 if x < y else 1
            if op == '-le': return 0 if x <= y else 1
            if op == '-gt': return 0 if x > y else 1
            if op == '-ge': return 0 if x >= y else 1
        return 1
    return 1

def builtin_true(args):
    return 0

def builtin_false(args):
    return 1

builtins = {
    'echo': builtin_echo,
    'pwd': builtin_pwd,
    'cd': builtin_cd,
    'ls': builtin_ls,
    'mkdir': builtin_mkdir,
    'cp': builtin_cp,
    'mv': builtin_mv,
    'rm': builtin_rm,
    'cat': builtin_cat,
    'export': builtin_export,
    'unset': builtin_unset,
    'read': builtin_read,
    'help': builtin_help,
    'source': builtin_source,
    '.': builtin_source,
    'test': builtin_test,
    '[': builtin_test,
    '[[': builtin_test,
    'true': builtin_true,
    'false': builtin_false,
}

# --- Esecuzione script ---
def execute_script_text(text):
    global last_exit
    text, heredocs = preprocess_heredocs(text)
    tokens = tokenize(text)
    parser = Parser(tokens, heredocs)
    program = parser.parse_program()
    try:
        return execute_node(program)
    except ExitSignal as e:
        return e.code
    except BreakSignal:
        return 0
    except ContinueSignal:
        return 0

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] in ('--help', '-h', 'help'):
            print(show_help())
            sys.exit(0)
        env['0'] = sys.argv[1]
        positional = sys.argv[2:]
        try:
            with open(sys.argv[1], encoding='utf-8', errors='replace') as f:
                text = f.read()
        except OSError as e:
            print(f"ntbash: {sys.argv[1]}: {e.strerror}", file=sys.stderr)
            sys.exit(1)
        code = execute_script_text(text)
        sys.exit(code)
    else:
        print("Uso: python ntbash.py <script.sh> [argomenti...]")
        print("Digita 'help' all'interno dello script per info.")
