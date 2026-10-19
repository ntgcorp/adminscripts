import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

/**
 * ntbash.java - Interprete Bash portabile in Java (solo JDK standard).
 * Porting di ntbash.py: builtin, parametri posizionali, sottoprocessi,
 * pipeline, redirezioni, strutture di controllo, espansioni.
 */
public class ntbash {

    // --- Ambiente globale ---
    static Map<String, String> env = new HashMap<>();
    static String currentDir = System.getProperty("user.dir");
    static List<String> positional = new ArrayList<>();
    static int lastExit = 0;
    static int lastBg = 0;
    static Map<String, Node> functions = new HashMap<>();
    static int funcDepth = 0;
    static PrintStream out = System.out;
    static BufferedReader in = new BufferedReader(new InputStreamReader(System.in));

    static final Map<String, String> DOCS = new LinkedHashMap<>();
    static {
        DOCS.put("echo [-e] [-n] testo", "Stampa testo; -e interpreta \\n, \\t; -n senza newline.");
        DOCS.put("pwd", "Mostra la cartella corrente.");
        DOCS.put("cd [dir]", "Cambia directory (senza argomenti -> $HOME).");
        DOCS.put("ls [-l] [-a] [dir...]", "Elenca file e cartelle.");
        DOCS.put("mkdir [-p] dir", "Crea directory.");
        DOCS.put("cp src dst", "Copia file.");
        DOCS.put("mv src dst", "Sposta/rinomina.");
        DOCS.put("rm [-r] [-f] file", "Elimina file/directory.");
        DOCS.put("cat file", "Stampa il contenuto di un file.");
        DOCS.put("export VAR[=val]", "Esporta una variabile.");
        DOCS.put("unset VAR", "Rimuove una variabile.");
        DOCS.put("read var", "Legge una riga da stdin.");
        DOCS.put("exit [N]", "Termina lo script con exit code N.");
        DOCS.put("source file", "Esegue un altro script nello stesso ambiente.");
        DOCS.put("test / [ ] / [[ ]]", "Confronti e test su file.");
        DOCS.put("$((math))", "Espansione aritmetica, es: $((10/2)).");
        DOCS.put("$(comando)", "Sostituzione di comando.");
        DOCS.put("pipe (|)", "Collega l'output di un comando all'input del successivo.");
        DOCS.put("redirezione (>)", "> sovrascrive, >> accoda, < legge, 2> stderr.");
        DOCS.put("#", "Commento fino a fine riga.");
        DOCS.put("{...}", "Blocco di comandi.");
        DOCS.put("if/for/while/case", "Strutture di controllo.");
        DOCS.put("funzioni nome() { ... }", "Definizione di funzioni.");
    }

    static String showHelp() {
        StringBuilder sb = new StringBuilder("--- HELP NTBASH ---\n");
        for (Map.Entry<String, String> e : DOCS.entrySet())
            sb.append(" ").append(e.getKey()).append(": ").append(e.getValue()).append("\n");
        return sb.toString();
    }

    // --- Segnali di controllo ---
    static class ExitSignal extends RuntimeException { int code; ExitSignal(int c) { code = c; } }
    static class ReturnSignal extends RuntimeException { int code; ReturnSignal(int c) { code = c; } }
    static class BreakSignal extends RuntimeException {}
    static class ContinueSignal extends RuntimeException {}

    // --- Segmenti di parola ---
    static class Seg { char kind; String val; Seg(char k, String v) { kind = k; val = v; } }

    // --- AST ---
    static abstract class Node {}
    static class Assign { String name; List<Seg> value; Assign(String n, List<Seg> v) { name = n; value = v; } }
    static class Redir { String op; Object target; Redir(String o, Object t) { op = o; target = t; } }
    static class Cmd extends Node { List<List<Seg>> words = new ArrayList<>(); List<Redir> redirs = new ArrayList<>(); boolean background; List<Assign> assigns = new ArrayList<>(); }
    static class Pipeline extends Node { List<Node> cmds = new ArrayList<>(); }
    static class AndOr extends Node { List<String> ops = new ArrayList<>(); List<Node> parts = new ArrayList<>(); }
    static class ListN extends Node { List<String> ops = new ArrayList<>(); List<Node> parts = new ArrayList<>(); }
    static class IfN extends Node { Node cond, thenBody, elseBody; List<Node> elifConds = new ArrayList<>(); List<Node> elifBodies = new ArrayList<>(); }
    static class ForN extends Node { String var; List<List<Seg>> items; Node body; }
    static class WhileN extends Node { Node cond, body; boolean until; }
    static class CaseN extends Node { List<Seg> word; List<List<List<Seg>>> patterns = new ArrayList<>(); List<Node> bodies = new ArrayList<>(); }
    static class FuncN extends Node { String name; Node body; }
    static class BlockN extends Node { Node body; }
    static class SubshellN extends Node { Node body; }

    // --- Accesso alle variabili ---
    static String getVar(String name) { return env.getOrDefault(name, ""); }

    static String getPositional(int n) {
        if (n == 0) return env.getOrDefault("0", "");
        if (n <= positional.size()) return positional.get(n - 1);
        return "";
    }

    static String getSpecial(char ch) {
        switch (ch) {
            case '?': return String.valueOf(lastExit);
            case '$': return String.valueOf(currentPid());
            case '!': return String.valueOf(lastBg);
            case '#': return String.valueOf(positional.size());
            case '@': return String.join(" ", positional);
            case '*': return String.join(" ", positional);
        }
        return "";
    }

    // --- Aritmetica sicura (parser ricorsivo, niente eval) ---
    static int evalArith(String expr) {
        expr = expr.trim();
        if (expr.isEmpty()) return 0;
        try { return new Arith(expr).parse(); } catch (Exception e) { return 0; }
    }

    static class Arith {
        String s; int p = 0;
        Arith(String s) { this.s = s; }
        int peek() { while (p < s.length() && Character.isWhitespace(s.charAt(p))) p++; return p < s.length() ? s.charAt(p) : -1; }
        void next() { if (p < s.length()) p++; }
        int parse() { return orExpr(); }
        int orExpr() {
            int v = andExpr();
            while (peek() == '|' && p + 1 < s.length() && s.charAt(p + 1) == '|') { next(); next(); int r = andExpr(); v = (v != 0 || r != 0) ? 1 : 0; }
            return v;
        }
        int andExpr() {
            int v = eqExpr();
            while (peek() == '&' && p + 1 < s.length() && s.charAt(p + 1) == '&') { next(); next(); int r = eqExpr(); v = (v != 0 && r != 0) ? 1 : 0; }
            return v;
        }
        int eqExpr() {
            int v = relExpr();
            while (true) {
                int c = peek();
                if (c == '=' && p + 1 < s.length() && s.charAt(p + 1) == '=') { next(); next(); int r = relExpr(); v = (v == r) ? 1 : 0; }
                else if (c == '!' && p + 1 < s.length() && s.charAt(p + 1) == '=') { next(); next(); int r = relExpr(); v = (v != r) ? 1 : 0; }
                else break;
            }
            return v;
        }
        int relExpr() {
            int v = addExpr();
            while (true) {
                int c = peek();
                if (c == '<') { next(); if (peek() == '=') { next(); int r = addExpr(); v = (v <= r) ? 1 : 0; } else { int r = addExpr(); v = (v < r) ? 1 : 0; } }
                else if (c == '>') { next(); if (peek() == '=') { next(); int r = addExpr(); v = (v >= r) ? 1 : 0; } else { int r = addExpr(); v = (v > r) ? 1 : 0; } }
                else break;
            }
            return v;
        }
        int addExpr() {
            int v = mulExpr();
            while (true) {
                int c = peek();
                if (c == '+') { next(); v += mulExpr(); }
                else if (c == '-') { next(); v -= mulExpr(); }
                else break;
            }
            return v;
        }
        int mulExpr() {
            int v = unary();
            while (true) {
                int c = peek();
                if (c == '*') { next(); v *= unary(); }
                else if (c == '/') { next(); int r = unary(); v = (r != 0) ? v / r : 0; }
                else if (c == '%') { next(); int r = unary(); v = (r != 0) ? v % r : 0; }
                else break;
            }
            return v;
        }
        int unary() {
            int c = peek();
            if (c == '-') { next(); return -unary(); }
            if (c == '+') { next(); return unary(); }
            return primary();
        }
        int primary() {
            int c = peek();
            if (c == '(') { next(); int v = orExpr(); if (peek() == ')') next(); return v; }
            if (c >= '0' && c <= '9') { int v = 0; while (peek() >= '0' && peek() <= '9') { v = v * 10 + (peek() - '0'); next(); } return v; }
            if (Character.isLetter(c) || c == '_') {
                StringBuilder b = new StringBuilder();
                while (Character.isLetterOrDigit(peek()) || peek() == '_') { b.append((char) peek()); next(); }
                try { return Integer.parseInt(getVar(b.toString())); } catch (NumberFormatException e) { return 0; }
            }
            return 0;
        }
    }

    // --- Espansioni ---
    static boolean hasGlobChars(String s) { return s.indexOf('*') >= 0 || s.indexOf('?') >= 0 || s.indexOf('[') >= 0; }

    static String globToRegex(String glob) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < glob.length(); i++) {
            char c = glob.charAt(i);
            if (c == '*') sb.append(".*");
            else if (c == '?') sb.append('.');
            else if (c == '[') {
                int j = i + 1;
                StringBuilder cls = new StringBuilder();
                if (j < glob.length() && glob.charAt(j) == '!') { cls.append('^'); j++; }
                while (j < glob.length() && glob.charAt(j) != ']') { cls.append(glob.charAt(j)); j++; }
                if (j < glob.length()) {
                    sb.append('[').append(cls).append(']');
                    i = j;
                } else {
                    sb.append("\\[");
                }
            } else if (".+()^${}|\\".indexOf(c) >= 0) sb.append('\\').append(c);
            else sb.append(c);
        }
        return sb.toString();
    }

    static List<String> glob(String pattern) {
        List<String> result = new ArrayList<>();
        File dir = new File(currentDir);
        Pattern p;
        try { p = Pattern.compile(globToRegex(pattern)); }
        catch (Exception e) { return result; }
        File[] files = dir.listFiles();
        if (files != null) for (File f : files) if (p.matcher(f.getName()).matches()) result.add(f.getName());
        Collections.sort(result);
        return result;
    }

    static boolean fnmatch(String s, String pattern) {
        return Pattern.compile(globToRegex(pattern)).matcher(s).matches();
    }

    static String expandArith(String text) {
        StringBuilder result = new StringBuilder();
        int i = 0, n = text.length();
        while (i < n) {
            if (text.startsWith("$((", i)) {
                int depth = 1, j = i + 3;
                while (j < n) {
                    if (text.charAt(j) == '(') depth++;
                    else if (text.charAt(j) == ')') { depth--; if (depth == 0) break; }
                    j++;
                }
                String expr = expandVars(text.substring(i + 3, j));
                result.append(evalArith(expr));
                i = j + 2;
            } else { result.append(text.charAt(i)); i++; }
        }
        return result.toString();
    }

    static String expandVars(String text) {
        StringBuilder result = new StringBuilder();
        int i = 0, n = text.length();
        while (i < n) {
            char c = text.charAt(i);
            if (c == '$' && i + 1 < n) {
                char nxt = text.charAt(i + 1);
                if (nxt == '{') {
                    int j = text.indexOf('}', i + 2);
                    if (j >= 0) { result.append(expandBraced(text.substring(i + 2, j))); i = j + 1; continue; }
                    result.append(c); i++;
                } else if (nxt == '(') { result.append(c); i++; }
                else if (Character.isLetter(nxt) || nxt == '_') {
                    int j = i + 1;
                    while (j < n && (Character.isLetterOrDigit(text.charAt(j)) || text.charAt(j) == '_')) j++;
                    result.append(getVar(text.substring(i + 1, j))); i = j;
                } else if (Character.isDigit(nxt)) {
                    int j = i + 1;
                    while (j < n && Character.isDigit(text.charAt(j))) j++;
                    result.append(getPositional(Integer.parseInt(text.substring(i + 1, j)))); i = j;
                } else if ("?$!#@*".indexOf(nxt) >= 0) { result.append(getSpecial(nxt)); i += 2; }
                else { result.append(c); i++; }
            } else { result.append(c); i++; }
        }
        return result.toString();
    }

    static String expandBraced(String inner) {
        if (inner.startsWith("#")) return String.valueOf(getVar(inner.substring(1)).length());
        for (String op : new String[]{":-", ":=", ":+"}) {
            int idx = inner.indexOf(op);
            if (idx >= 0) {
                String name = inner.substring(0, idx);
                String def = inner.substring(idx + op.length());
                String val = getVar(name);
                if (op.equals(":-")) return val.isEmpty() ? def : val;
                if (op.equals(":=")) { if (val.isEmpty()) { env.put(name, def); return def; } return val; }
                if (op.equals(":+")) return val.isEmpty() ? "" : def;
            }
        }
        if (inner.contains("##")) {
            String[] p = inner.split("##", 2);
            String val = getVar(p[0]);
            Matcher m = Pattern.compile("^.*" + p[1]).matcher(val);
            if (m.find()) return val.substring(m.end());
            return val;
        }
        if (inner.contains("%%")) {
            String[] p = inner.split("%%", 2);
            String val = getVar(p[0]);
            Matcher m = Pattern.compile(".*" + p[1] + "$").matcher(val);
            if (m.find()) return val.substring(0, m.start());
            return val;
        }
        if (inner.contains("#")) {
            String[] p = inner.split("#", 2);
            String val = getVar(p[0]);
            Matcher m = Pattern.compile("^.*?" + p[1]).matcher(val);
            if (m.find()) return val.substring(m.end());
            return val;
        }
        if (inner.contains("%")) {
            String[] p = inner.split("%", 2);
            String val = getVar(p[0]);
            Matcher m = Pattern.compile(p[1] + "$").matcher(val);
            if (m.find()) return val.substring(0, m.start());
            return val;
        }
        Matcher m = Pattern.compile("([A-Za-z_][A-Za-z0-9_]*):(-?\\d+)(?::(-?\\d+))?").matcher(inner);
        if (m.matches()) {
            String name = m.group(1);
            int off = Integer.parseInt(m.group(2));
            String val = getVar(name);
            if (m.group(3) == null) return (off >= 0 && off < val.length()) ? val.substring(off) : "";
            int len = Integer.parseInt(m.group(3));
            if (off < 0 || off >= val.length()) return "";
            return val.substring(off, Math.min(val.length(), off + len));
        }
        return getVar(inner);
    }

    static String runCmdsubst(String cmd) {
        PrintStream oldOut = out;
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        out = new PrintStream(baos);
        try { executeScriptText(cmd); } finally { out = oldOut; }
        String s = baos.toString(StandardCharsets.UTF_8);
        while (s.endsWith("\n")) s = s.substring(0, s.length() - 1);
        return s;
    }

    static String expandCmdsubst(String text) {
        StringBuilder result = new StringBuilder();
        int i = 0, n = text.length();
        while (i < n) {
            if (text.startsWith("$(", i) && (i + 2 >= n || text.charAt(i + 2) != '(')) {
                int depth = 1, j = i + 2;
                while (j < n) {
                    if (text.charAt(j) == '(') depth++;
                    else if (text.charAt(j) == ')') { depth--; if (depth == 0) break; }
                    j++;
                }
                result.append(runCmdsubst(text.substring(i + 2, j)));
                i = j + 1;
            } else if (text.charAt(i) == '`') {
                int j = text.indexOf('`', i + 1);
                if (j >= 0) { result.append(runCmdsubst(text.substring(i + 1, j))); i = j + 1; }
                else { result.append(text.charAt(i)); i++; }
            } else { result.append(text.charAt(i)); i++; }
        }
        return result.toString();
    }

    static String expandText(String text) {
        text = expandArith(text);
        text = expandVars(text);
        text = expandCmdsubst(text);
        return text;
    }

    static List<String> expandWord(List<Seg> segs) {
        StringBuilder text = new StringBuilder();
        boolean globAllowed = false;
        for (Seg s : segs) {
            if (s.kind == 's') text.append(s.val);
            else if (s.kind == 'd') text.append(expandText(s.val));
            else {
                text.append(expandText(s.val));
                if (hasGlobChars(s.val)) globAllowed = true;
            }
        }
        if (globAllowed) {
            List<String> matches = glob(text.toString());
            if (!matches.isEmpty()) return matches;
        }
        List<String> r = new ArrayList<>();
        r.add(text.toString());
        return r;
    }

    static Assign splitAssignment(List<Seg> segs) {
        if (segs.isEmpty()) return null;
        Seg first = segs.get(0);
        if (first.kind != 'l') return null;
        Matcher m = Pattern.compile("^([A-Za-z_][A-Za-z0-9_]*)=(.*)$").matcher(first.val);
        if (!m.matches()) return null;
        String name = m.group(1);
        String rest = m.group(2);
        List<Seg> value = new ArrayList<>();
        if (!rest.isEmpty()) value.add(new Seg('l', rest));
        for (int i = 1; i < segs.size(); i++) value.add(segs.get(i));
        return new Assign(name, value);
    }

    // --- Tokenizer ---
    static List<Object> tokenize(String text) {
        List<Object> tokens = new ArrayList<>();
        int i = 0, n = text.length();
        while (i < n) {
            char c = text.charAt(i);
            if (c == ' ' || c == '\t' || c == '\r') { i++; continue; }
            if (c == '\n') { tokens.add("NL"); i++; continue; }
            if (c == '#') { while (i < n && text.charAt(i) != '\n') i++; continue; }
            if (text.startsWith("2>&1", i)) { tokens.add("OP:2>&1"); i += 4; continue; }
            if (text.startsWith("2>>", i)) { tokens.add("OP:2>>"); i += 3; continue; }
            if (i + 1 < n) {
                String two = text.substring(i, i + 2);
                if (two.equals("&&") || two.equals("||") || two.equals(">>") || two.equals("<<") || two.equals(";;") || two.equals(";&") || two.equals("|&") || two.equals("&>") || two.equals("2>")) {
                    tokens.add("OP:" + two); i += 2; continue;
                }
            }
            if (";|&(){}<>".indexOf(c) >= 0) { tokens.add("OP:" + c); i++; continue; }
            List<Seg> segs = new ArrayList<>();
            while (i < n) {
                c = text.charAt(i);
                if (" \t\r\n;|&(){}<>".indexOf(c) >= 0) break;
                if (c == '#' && segs.isEmpty()) break;
                if (c == '\'') {
                    int j = text.indexOf('\'', i + 1);
                    if (j < 0) { segs.add(new Seg('s', text.substring(i + 1))); i = n; }
                    else { segs.add(new Seg('s', text.substring(i + 1, j))); i = j + 1; }
                    continue;
                }
                if (c == '"') {
                    int j = i + 1;
                    StringBuilder buf = new StringBuilder();
                    while (j < n && text.charAt(j) != '"') {
                        if (text.charAt(j) == '\\' && j + 1 < n && "\"\\$`".indexOf(text.charAt(j + 1)) >= 0) { buf.append(text.charAt(j + 1)); j += 2; continue; }
                        buf.append(text.charAt(j)); j++;
                    }
                    segs.add(new Seg('d', buf.toString())); i = j + 1; continue;
                }
                if (c == '\\') { if (i + 1 < n) { segs.add(new Seg('l', String.valueOf(text.charAt(i + 1)))); i += 2; } else i++; continue; }
                if (c == '$' && i + 1 < n && text.charAt(i + 1) == '(') {
                    int depth = 1, j = i + 2;
                    while (j < n) {
                        if (text.charAt(j) == '(') depth++;
                        else if (text.charAt(j) == ')') { depth--; if (depth == 0) break; }
                        j++;
                    }
                    segs.add(new Seg('l', text.substring(i, j + 1))); i = j + 1; continue;
                }
                if (c == '$' && i + 1 < n && text.charAt(i + 1) == '{') {
                    int j = text.indexOf('}', i + 2);
                    if (j >= 0) { segs.add(new Seg('l', text.substring(i, j + 1))); i = j + 1; continue; }
                }
                int j = i;
                StringBuilder buf = new StringBuilder();
                while (j < n && " \t\r\n;|&(){}<>'\"\\".indexOf(text.charAt(j)) < 0) {
                    if (text.charAt(j) == '$' && j + 1 < n && (text.charAt(j + 1) == '(' || text.charAt(j + 1) == '{')) break;
                    buf.append(text.charAt(j)); j++;
                }
                segs.add(new Seg('l', buf.toString())); i = j;
            }
            tokens.add(segs);
        }
        tokens.add("EOF");
        return tokens;
    }

    // --- Heredoc ---
    static String preprocessHeredocs(String text, List<String> heredocs) {
        String[] lines = text.split("\n", -1);
        StringBuilder out = new StringBuilder();
        int i = 0;
        while (i < lines.length) {
            String line = lines[i];
            Matcher m = Pattern.compile("<<\\s*([A-Za-z_][A-Za-z0-9_]*)").matcher(line);
            if (m.find()) {
                String delim = m.group(1);
                int j = i + 1;
                StringBuilder content = new StringBuilder();
                while (j < lines.length) {
                    if (lines[j].trim().equals(delim)) break;
                    if (content.length() > 0) content.append("\n");
                    content.append(lines[j]);
                    j++;
                }
                heredocs.add(content.toString());
                line = line.substring(0, m.start()) + "<< HEREDOC" + (heredocs.size() - 1) + line.substring(m.end());
                out.append(line).append("\n");
                i = j + 1;
            } else {
                out.append(line).append("\n");
                i++;
            }
        }
        return out.toString();
    }

    // --- Parser ---
    static class Parser {
        List<Object> tokens;
        List<String> heredocs;
        int pos = 0;
        Parser(List<Object> t, List<String> h) { tokens = t; heredocs = h; }
        Object peek() { return tokens.get(pos); }
        Object next() { return tokens.get(pos++); }
        boolean isOp(String op) { Object t = peek(); return t instanceof String && ((String) t).equals("OP:" + op); }
        boolean expectOp(String op) { if (isOp(op)) { next(); return true; } return false; }
        boolean isWord() { return peek() instanceof List; }
        String wordText(List<Seg> segs) { StringBuilder b = new StringBuilder(); for (Seg s : segs) b.append(s.val); return b.toString(); }
        boolean expectKeyword(String kw) { if (isWord() && wordText((List<Seg>) peek()).equals(kw)) { next(); return true; } return false; }

        static boolean isRedirOp(String op) {
            return op.equals(">") || op.equals(">>") || op.equals("<") || op.equals("2>") || op.equals("2>>") || op.equals("2>&1") || op.equals("&>") || op.equals("<<");
        }

        Node parseList(Set<String> stop) {
            ListN node = new ListN();
            while (true) {
                Object t = peek();
                if (t.equals("EOF")) break;
                if (t instanceof String && ((String) t).startsWith("OP:")) {
                    String op = ((String) t).substring(3);
                    if (op.equals("}") || op.equals(")") || op.equals(";;") || op.equals(";&")) break;
                }
                if (t instanceof List && stop.contains(wordText((List<Seg>) t))) break;
                if (t.equals("NL")) { next(); continue; }
                Node n = parseAndOr();
                if (n == null) { next(); continue; }
                node.parts.add(n); node.ops.add(";");
                t = peek();
                if (t instanceof String && ((String) t).startsWith("OP:")) {
                    String op = ((String) t).substring(3);
                    if (op.equals(";") || op.equals("&")) { next(); node.ops.set(node.ops.size() - 1, op); }
                    else if (op.equals("}") || op.equals(")") || op.equals(";;") || op.equals(";&")) break;
                    else break;
                } else if (t.equals("NL")) { next(); }
                else if (t.equals("EOF")) break;
                else if (t instanceof List && stop.contains(wordText((List<Seg>) t))) break;
                else break;
            }
            return node;
        }

        Node parseAndOr() {
            Node first = parsePipeline();
            if (first == null) return null;
            AndOr node = new AndOr();
            node.parts.add(first); node.ops.add("");
            while (true) {
                Object t = peek();
                if (t instanceof String && ((String) t).startsWith("OP:")) {
                    String op = ((String) t).substring(3);
                    if (op.equals("&&") || op.equals("||")) {
                        next();
                        Node n = parsePipeline();
                        if (n == null) break;
                        node.parts.add(n); node.ops.add(op);
                    } else break;
                } else break;
            }
            if (node.parts.size() == 1) return node.parts.get(0);
            return node;
        }

        Node parsePipeline() {
            List<Node> cmds = new ArrayList<>();
            Node first = parseCommand();
            if (first != null) cmds.add(first);
            while (true) {
                Object t = peek();
                if (t instanceof String && ((String) t).startsWith("OP:")) {
                    String op = ((String) t).substring(3);
                    if (op.equals("|") || op.equals("|&")) {
                        next();
                        Node c = parseCommand();
                        if (c != null) cmds.add(c);
                    } else break;
                } else break;
            }
            if (cmds.isEmpty()) return null;
            if (cmds.size() == 1) return cmds.get(0);
            Pipeline p = new Pipeline();
            p.cmds = cmds;
            return p;
        }

        Node parseCommand() {
            Object t = peek();
            if (t instanceof String && ((String) t).equals("OP:{")) { next(); return parseBlock(); }
            if (t instanceof String && ((String) t).equals("OP:(")) { next(); return parseSubshell(); }
            if (t instanceof List) {
                String text = wordText((List<Seg>) t);
                if (text.equals("if") || text.equals("for") || text.equals("while") || text.equals("until") || text.equals("case") || text.equals("function")) {
                    next();
                    return parseCompound(text);
                }
                if (pos + 2 < tokens.size()) {
                    Object t1 = tokens.get(pos + 1);
                    Object t2 = tokens.get(pos + 2);
                    if (t1 instanceof String && ((String) t1).equals("OP:(") && t2 instanceof String && ((String) t2).equals("OP:)")) {
                        String name = text;
                        next(); next(); next();
                        if (isOp("{")) {
                            next();
                            Node body = parseList(new HashSet<>(Arrays.asList("}")));
                            expectOp("}");
                            FuncN f = new FuncN(); f.name = name; f.body = body; return f;
                        }
                        Node body = parseList(new HashSet<>());
                        FuncN f = new FuncN(); f.name = name; f.body = body; return f;
                    }
                }
            }
            Cmd cmd = new Cmd();
            while (true) {
                t = peek();
                if (t instanceof List) {
                    List<Seg> segs = (List<Seg>) next();
                    if (cmd.words.isEmpty()) {
                        Assign a = splitAssignment(segs);
                        if (a != null) { cmd.assigns.add(a); continue; }
                    }
                    cmd.words.add(segs);
                } else if (t instanceof String && ((String) t).startsWith("OP:") && isRedirOp(((String) t).substring(3))) {
                    String op = ((String) next()).substring(3);
                    if (op.equals("<<")) {
                        Object tt = peek();
                        if (tt instanceof List) {
                            String marker = wordText((List<Seg>) tt);
                            next();
                            if (marker.startsWith("HEREDOC") && marker.substring(7).matches("\\d+")) {
                                int idx = Integer.parseInt(marker.substring(7));
                                cmd.redirs.add(new Redir("<<", idx < heredocs.size() ? heredocs.get(idx) : ""));
                            } else cmd.redirs.add(new Redir("<<", ""));
                        } else cmd.redirs.add(new Redir("<<", ""));
                    } else {
                        Object tt = peek();
                        if (tt instanceof List) cmd.redirs.add(new Redir(op, next()));
                        else cmd.redirs.add(new Redir(op, new ArrayList<Seg>()));
                    }
                } else if (t instanceof String && ((String) t).equals("OP:&")) {
                    next(); cmd.background = true; break;
                } else break;
            }
            if (cmd.words.isEmpty() && cmd.redirs.isEmpty() && cmd.assigns.isEmpty()) return null;
            return cmd;
        }

        Node parseCompound(String kw) {
            if (kw.equals("if")) return parseIf();
            if (kw.equals("for")) return parseFor();
            if (kw.equals("while")) return parseWhile(false);
            if (kw.equals("until")) return parseWhile(true);
            if (kw.equals("case")) return parseCase();
            if (kw.equals("function")) return parseFunction();
            return null;
        }

        Node parseIf() {
            Node cond = parseList(new HashSet<>(Arrays.asList("then")));
            expectKeyword("then");
            Node thenBody = parseList(new HashSet<>(Arrays.asList("elif", "else", "fi")));
            IfN node = new IfN();
            node.cond = cond; node.thenBody = thenBody;
            while (true) {
                Object t = peek();
                if (t instanceof List && wordText((List<Seg>) t).equals("elif")) {
                    next();
                    Node c = parseList(new HashSet<>(Arrays.asList("then")));
                    expectKeyword("then");
                    Node b = parseList(new HashSet<>(Arrays.asList("elif", "else", "fi")));
                    node.elifConds.add(c); node.elifBodies.add(b);
                } else if (t instanceof List && wordText((List<Seg>) t).equals("else")) {
                    next();
                    node.elseBody = parseList(new HashSet<>(Arrays.asList("fi")));
                } else if (t instanceof List && wordText((List<Seg>) t).equals("fi")) {
                    next(); break;
                } else break;
            }
            return node;
        }

        Node parseFor() {
            Object t = next();
            ForN node = new ForN();
            node.var = wordText((List<Seg>) t);
            t = peek();
            if (t instanceof List && wordText((List<Seg>) t).equals("in")) {
                next();
                node.items = new ArrayList<>();
                while (true) {
                    t = peek();
                    if (t instanceof List) node.items.add((List<Seg>) next());
                    else if (t instanceof String && ((String) t).startsWith("OP:") && (((String) t).substring(3).equals(";") || ((String) t).substring(3).equals("&"))) { next(); break; }
                    else if (t.equals("NL")) { next(); break; }
                    else break;
                }
            } else {
                while (true) {
                    t = peek();
                    if (t instanceof String && ((String) t).startsWith("OP:") && (((String) t).substring(3).equals(";") || ((String) t).substring(3).equals("&"))) { next(); break; }
                    if (t.equals("NL")) { next(); break; }
                    if (t.equals("EOF")) break;
                    next();
                }
            }
            expectKeyword("do");
            node.body = parseList(new HashSet<>(Arrays.asList("done")));
            expectKeyword("done");
            return node;
        }

        Node parseWhile(boolean until) {
            Node cond = parseList(new HashSet<>(Arrays.asList("do")));
            expectKeyword("do");
            Node body = parseList(new HashSet<>(Arrays.asList("done")));
            expectKeyword("done");
            WhileN node = new WhileN();
            node.cond = cond; node.body = body; node.until = until;
            return node;
        }

        Node parseCase() {
            Object t = next();
            CaseN node = new CaseN();
            node.word = (List<Seg>) t;
            expectKeyword("in");
            while (true) {
                t = peek();
                if (t instanceof List && wordText((List<Seg>) t).equals("esac")) { next(); break; }
                if (t.equals("NL")) { next(); continue; }
                if (t.equals("EOF")) break;
                List<List<Seg>> patterns = new ArrayList<>();
                while (true) {
                    t = peek();
                    if (t instanceof String && ((String) t).equals("OP:)")) { next(); break; }
                    if (t instanceof List) patterns.add((List<Seg>) next());
                    else if (t instanceof String && ((String) t).equals("OP:|")) next();
                    else break;
                }
                Node body = parseList(new HashSet<>(Arrays.asList("esac")));
                t = peek();
                if (t instanceof String && ((String) t).startsWith("OP:") && (((String) t).substring(3).equals(";;") || ((String) t).substring(3).equals(";&"))) next();
                node.patterns.add(patterns); node.bodies.add(body);
            }
            return node;
        }

        Node parseFunction() {
            Object t = next();
            String name = wordText((List<Seg>) t);
            if (isOp("(")) { next(); expectOp(")"); }
            if (isOp("{")) {
                next();
                Node body = parseList(new HashSet<>(Arrays.asList("}")));
                expectOp("}");
                FuncN f = new FuncN(); f.name = name; f.body = body; return f;
            }
            Node body = parseList(new HashSet<>());
            FuncN f = new FuncN(); f.name = name; f.body = body; return f;
        }

        Node parseBlock() {
            Node body = parseList(new HashSet<>(Arrays.asList("}")));
            expectOp("}");
            BlockN b = new BlockN(); b.body = body; return b;
        }

        Node parseSubshell() {
            Node body = parseList(new HashSet<>(Arrays.asList(")")));
            expectOp(")");
            SubshellN s = new SubshellN(); s.body = body; return s;
        }
    }

    // --- Redirezioni ---
    static class RedirSet {
        InputStream stdin;
        PrintStream stdout;
        PrintStream stderr;
        List<Closeable> toClose = new ArrayList<>();
    }

    static RedirSet setupRedirs(List<Redir> redirs) {
        RedirSet rs = new RedirSet();
        for (Redir r : redirs) {
            if (r.op.equals("<<")) {
                rs.stdin = new ByteArrayInputStream(((String) r.target).getBytes(StandardCharsets.UTF_8));
                continue;
            }
            String target;
            if (r.target instanceof List) target = expandWord((List<Seg>) r.target).get(0);
            else target = (String) r.target;
            Path path = new File(target).isAbsolute() ? Paths.get(target) : Paths.get(currentDir, target);
            try {
                if (r.op.equals(">")) { PrintStream ps = new PrintStream(Files.newOutputStream(path)); rs.stdout = ps; rs.toClose.add(ps); }
                else if (r.op.equals(">>")) { PrintStream ps = new PrintStream(Files.newOutputStream(path, StandardOpenOption.APPEND, StandardOpenOption.CREATE)); rs.stdout = ps; rs.toClose.add(ps); }
                else if (r.op.equals("<")) { InputStream is = Files.newInputStream(path); rs.stdin = is; rs.toClose.add(is); }
                else if (r.op.equals("2>")) { PrintStream ps = new PrintStream(Files.newOutputStream(path)); rs.stderr = ps; rs.toClose.add(ps); }
                else if (r.op.equals("2>>")) { PrintStream ps = new PrintStream(Files.newOutputStream(path, StandardOpenOption.APPEND, StandardOpenOption.CREATE)); rs.stderr = ps; rs.toClose.add(ps); }
                else if (r.op.equals("2>&1")) { rs.stderr = rs.stdout; }
                else if (r.op.equals("&>")) { PrintStream ps = new PrintStream(Files.newOutputStream(path)); rs.stdout = ps; rs.stderr = ps; rs.toClose.add(ps); }
            } catch (IOException e) {
                System.err.println("ntbash: redirezione: " + e.getMessage());
            }
        }
        return rs;
    }

    // --- Esecuzione ---
    static class Result { int code; String output; Result(int c, String o) { code = c; output = o; } }

    static byte[] readAll(InputStream is) throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int r;
        while ((r = is.read(buf)) >= 0) baos.write(buf, 0, r);
        return baos.toByteArray();
    }

    static void copyTo(InputStream is, OutputStream os) throws IOException {
        byte[] buf = new byte[8192];
        int r;
        while ((r = is.read(buf)) >= 0) os.write(buf, 0, r);
    }

    static int processPid(Process p) {
        try {
            java.lang.reflect.Method m = Process.class.getMethod("pid");
            return ((Long) m.invoke(p)).intValue();
        } catch (Throwable t) {
            return 0;
        }
    }

    static long currentPid() {
        try {
            Object ph = Class.forName("java.lang.ProcessHandle").getMethod("current").invoke(null);
            return (Long) ph.getClass().getMethod("pid").invoke(ph);
        } catch (Throwable t) {
            return 0;
        }
    }

    static Result runExternal(String name, List<String> args, RedirSet rs, String inputData, boolean capture) {
        List<String> cmdline = new ArrayList<>();
        cmdline.add(name); cmdline.addAll(args);
        try {
            ProcessBuilder pb = new ProcessBuilder(cmdline);
            pb.directory(new File(currentDir));
            pb.redirectInput(ProcessBuilder.Redirect.PIPE);
            pb.redirectOutput(ProcessBuilder.Redirect.PIPE);
            pb.redirectError(ProcessBuilder.Redirect.PIPE);
            Process proc = pb.start();
            if (inputData != null) {
                proc.getOutputStream().write(inputData.getBytes(StandardCharsets.UTF_8));
            } else if (rs.stdin != null) {
                copyTo(rs.stdin, proc.getOutputStream());
            }
            proc.getOutputStream().close();
            final StringBuilder errBuf = new StringBuilder();
            Thread errThread = new Thread(() -> {
                try { errBuf.append(new String(readAll(proc.getErrorStream()), StandardCharsets.UTF_8)); } catch (IOException e) {}
            });
            errThread.start();
            String output = new String(readAll(proc.getInputStream()), StandardCharsets.UTF_8);
            errThread.join();
            int code = proc.waitFor();
            String err = errBuf.toString();
            if (capture) return new Result(code, output);
            if (rs.stdout != null) rs.stdout.print(output);
            else out.print(output);
            if (rs.stderr != null) rs.stderr.print(err);
            else if (!err.isEmpty()) System.err.print(err);
            return new Result(code, "");
        } catch (IOException e) {
            System.err.println("ntbash: " + name + ": comando non trovato");
            return new Result(127, "");
        } catch (Exception e) {
            System.err.println("ntbash: " + name + ": " + e.getMessage());
            return new Result(1, "");
        }
    }

    static Result runCommand(Cmd cmd, String inputData, boolean capture) {
        for (Assign a : cmd.assigns) env.put(a.name, expandWord(a.value).get(0));
        List<String> words = new ArrayList<>();
        for (List<Seg> segs : cmd.words) words.addAll(expandWord(segs));
        if (words.isEmpty()) return new Result(0, "");
        String name = words.get(0);
        List<String> args = new ArrayList<>(words.subList(1, words.size()));
        if (name.equals("break")) throw new BreakSignal();
        if (name.equals("continue")) throw new ContinueSignal();
        if (name.equals("return")) {
            int code = args.isEmpty() ? lastExit : Integer.parseInt(args.get(0));
            if (funcDepth > 0) throw new ReturnSignal(code);
            throw new ExitSignal(code);
        }
        if (name.equals("exit")) {
            int code = args.isEmpty() ? lastExit : Integer.parseInt(args.get(0));
            throw new ExitSignal(code);
        }
        RedirSet rs = setupRedirs(cmd.redirs);
        try {
            if (functions.containsKey(name)) {
                Result r = executeFunctionCall(name, args, inputData, capture, rs.stdout);
                lastExit = r.code;
                return r;
            }
            if (builtins.containsKey(name)) {
                BufferedReader oldIn = in;
                PrintStream oldOut = out;
                if (inputData != null) in = new BufferedReader(new StringReader(inputData));
                else if (rs.stdin != null) in = new BufferedReader(new InputStreamReader(rs.stdin));
                ByteArrayOutputStream baos = null;
                if (capture) { baos = new ByteArrayOutputStream(); out = new PrintStream(baos); }
                else if (rs.stdout != null) out = rs.stdout;
                PrintStream oldErr = System.err;
                if (rs.stderr != null) System.setErr(rs.stderr);
                int code;
                try { code = builtins.get(name).apply(args); }
                finally {
                    in = oldIn; out = oldOut;
                    if (rs.stderr != null) System.setErr(oldErr);
                }
                lastExit = code;
                if (capture) return new Result(code, baos.toString(StandardCharsets.UTF_8));
                return new Result(code, "");
            }
            Result r = runExternal(name, args, rs, inputData, capture);
            lastExit = r.code;
            return r;
        } finally {
            for (Closeable c : rs.toClose) try { c.close(); } catch (Exception e) {}
        }
    }

    static Result runStage(Node node, String inputData, boolean capture) {
        if (node instanceof Cmd) return runCommand((Cmd) node, inputData, capture);
        PrintStream oldOut = out;
        BufferedReader oldIn = in;
        if (inputData != null) in = new BufferedReader(new StringReader(inputData));
        ByteArrayOutputStream baos = null;
        if (capture) { baos = new ByteArrayOutputStream(); out = new PrintStream(baos); }
        int code;
        try { code = executeNode(node); }
        finally { in = oldIn; out = oldOut; }
        return new Result(code, capture ? baos.toString(StandardCharsets.UTF_8) : "");
    }

    static Result executeFunctionCall(String name, List<String> args, String inputData, boolean capture, PrintStream stdout) {
        if (!functions.containsKey(name)) return new Result(127, "");
        List<String> oldPos = positional;
        positional = new ArrayList<>(args);
        BufferedReader oldIn = in;
        PrintStream oldOut = out;
        if (inputData != null) in = new BufferedReader(new StringReader(inputData));
        ByteArrayOutputStream baos = null;
        if (capture) { baos = new ByteArrayOutputStream(); out = new PrintStream(baos); }
        else if (stdout != null) out = stdout;
        funcDepth++;
        int code;
        try {
            try { code = executeNode(functions.get(name)); }
            catch (ReturnSignal e) { code = e.code; }
        } finally {
            funcDepth--;
            positional = oldPos;
            in = oldIn;
            out = oldOut;
        }
        return new Result(code, capture ? baos.toString(StandardCharsets.UTF_8) : "");
    }

    static int executePipeline(Pipeline pipe) {
        String inputData = null;
        int lastCode = 0;
        for (int i = 0; i < pipe.cmds.size(); i++) {
            boolean isLast = (i == pipe.cmds.size() - 1);
            Result r = runStage(pipe.cmds.get(i), inputData, !isLast);
            lastCode = r.code;
            inputData = r.output;
        }
        return lastCode;
    }

    static int executeIf(IfN node) {
        int code = executeNode(node.cond);
        if (code == 0) return executeNode(node.thenBody);
        for (int i = 0; i < node.elifConds.size(); i++) {
            code = executeNode(node.elifConds.get(i));
            if (code == 0) return executeNode(node.elifBodies.get(i));
        }
        if (node.elseBody != null) return executeNode(node.elseBody);
        return 0;
    }

    static int executeFor(ForN node) {
        List<String> items;
        if (node.items == null) items = new ArrayList<>(positional);
        else {
            items = new ArrayList<>();
            for (List<Seg> segs : node.items) items.addAll(expandWord(segs));
        }
        for (String item : items) {
            env.put(node.var, item);
            try { executeNode(node.body); }
            catch (ContinueSignal e) { continue; }
            catch (BreakSignal e) { break; }
        }
        return 0;
    }

    static int executeWhile(WhileN node) {
        while (true) {
            int code = executeNode(node.cond);
            if (node.until) { if (code == 0) break; }
            else { if (code != 0) break; }
            try { executeNode(node.body); }
            catch (ContinueSignal e) { continue; }
            catch (BreakSignal e) { break; }
        }
        return 0;
    }

    static int executeCase(CaseN node) {
        String word = expandWord(node.word).get(0);
        for (int i = 0; i < node.patterns.size(); i++) {
            for (List<Seg> patSegs : node.patterns.get(i)) {
                String pat = expandWord(patSegs).get(0);
                if (fnmatch(word, pat)) return executeNode(node.bodies.get(i));
            }
        }
        return 0;
    }

    static void executeBackground(Node node) {
        if (node instanceof Cmd) {
            Cmd cmd = (Cmd) node;
            List<String> words = new ArrayList<>();
            for (List<Seg> segs : cmd.words) words.addAll(expandWord(segs));
            if (!words.isEmpty() && !builtins.containsKey(words.get(0)) && !functions.containsKey(words.get(0))) {
                try {
                    ProcessBuilder pb = new ProcessBuilder(words);
                    pb.directory(new File(currentDir));
                    Process p = pb.start();
                    lastBg = processPid(p);
                    return;
                } catch (Exception e) {}
            }
        }
        Thread t = new Thread(() -> { try { executeNode(node); } catch (Exception e) {} });
        t.start();
        lastBg = (int) t.getId();
    }

    static int executeNode(Node node) {
        if (node == null) return 0;
        if (node instanceof Cmd) return runCommand((Cmd) node, null, false).code;
        if (node instanceof Pipeline) return executePipeline((Pipeline) node);
        if (node instanceof AndOr) {
            AndOr a = (AndOr) node;
            int code = 0;
            for (int i = 0; i < a.parts.size(); i++) {
                String op = a.ops.get(i);
                if (i == 0) code = executeNode(a.parts.get(i));
                else if (op.equals("&&")) { if (code == 0) code = executeNode(a.parts.get(i)); }
                else if (op.equals("||")) { if (code != 0) code = executeNode(a.parts.get(i)); }
            }
            return code;
        }
        if (node instanceof ListN) {
            ListN l = (ListN) node;
            int code = 0;
            for (int i = 0; i < l.parts.size(); i++) {
                if (l.ops.get(i).equals("&")) { executeBackground(l.parts.get(i)); code = 0; }
                else code = executeNode(l.parts.get(i));
            }
            return code;
        }
        if (node instanceof IfN) return executeIf((IfN) node);
        if (node instanceof ForN) return executeFor((ForN) node);
        if (node instanceof WhileN) return executeWhile((WhileN) node);
        if (node instanceof CaseN) return executeCase((CaseN) node);
        if (node instanceof BlockN) return executeNode(((BlockN) node).body);
        if (node instanceof SubshellN) return executeNode(((SubshellN) node).body);
        if (node instanceof FuncN) { functions.put(((FuncN) node).name, ((FuncN) node).body); return 0; }
        return 0;
    }

    // --- Builtin ---
    interface Builtin { int apply(List<String> args); }

    static int builtinEcho(List<String> args) {
        boolean newline = true, escapes = false;
        int i = 0;
        while (i < args.size() && args.get(i).startsWith("-") && args.get(i).length() > 1) {
            boolean ok = true;
            for (int k = 1; k < args.get(i).length(); k++) { char c = args.get(i).charAt(k); if (c != 'e' && c != 'n') { ok = false; break; } }
            if (!ok) break;
            if (args.get(i).indexOf('e') >= 0) escapes = true;
            if (args.get(i).indexOf('n') >= 0) newline = false;
            i++;
        }
        String msg = String.join(" ", args.subList(i, args.size()));
        if (escapes) msg = msg.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace("\\\\", "\\");
        out.print(msg);
        if (newline) out.print("\n");
        return 0;
    }

    static int builtinPwd(List<String> args) { out.println(currentDir); return 0; }

    static int builtinCd(List<String> args) {
        String target = args.isEmpty() ? env.getOrDefault("HOME", "") : args.get(0);
        if (target.isEmpty()) return 0;
        File path = new File(target).isAbsolute() ? new File(target) : new File(currentDir, target);
        if (path.isDirectory()) { currentDir = path.getAbsolutePath(); return 0; }
        System.err.println("ntbash: cd: " + target + ": nessuna directory");
        return 1;
    }

    static int builtinLs(List<String> args) {
        boolean long_ = false, all_ = false;
        List<String> targets = new ArrayList<>();
        for (String a : args) {
            if (a.startsWith("-") && a.length() > 1) {
                if (a.indexOf('l') >= 0) long_ = true;
                if (a.indexOf('a') >= 0) all_ = true;
            } else targets.add(a);
        }
        if (targets.isEmpty()) targets.add(".");
        for (String t : targets) {
            File path = new File(t).isAbsolute() ? new File(t) : new File(currentDir, t);
            if (path.isDirectory()) {
                String[] entries = path.list();
                if (entries == null) continue;
                List<String> list = new ArrayList<>(Arrays.asList(entries));
                Collections.sort(list);
                if (!all_) list.removeIf(e -> e.startsWith("."));
                if (long_) {
                    for (String e : list) {
                        File f = new File(path, e);
                        out.printf("%s %8d %s%n", f.isDirectory() ? "d" : "-", f.length(), e);
                    }
                } else out.println(String.join("  ", list));
            } else if (path.exists()) out.println(t);
            else { System.err.println("ntbash: ls: " + t + ": nessun file o directory"); return 2; }
        }
        return 0;
    }

    static int builtinMkdir(List<String> args) {
        boolean parents = false;
        List<String> targets = new ArrayList<>();
        for (String a : args) { if (a.equals("-p")) parents = true; else targets.add(a); }
        for (String t : targets) {
            Path path = new File(t).isAbsolute() ? Paths.get(t) : Paths.get(currentDir, t);
            try {
                if (parents) Files.createDirectories(path);
                else Files.createDirectory(path);
            } catch (IOException e) { System.err.println("ntbash: mkdir: " + t + ": " + e.getMessage()); return 1; }
        }
        return 0;
    }

    static int builtinCp(List<String> args) {
        if (args.size() < 2) { System.err.println("ntbash: cp: argomenti mancanti"); return 1; }
        Path src = new File(args.get(0)).isAbsolute() ? Paths.get(args.get(0)) : Paths.get(currentDir, args.get(0));
        Path dst = new File(args.get(args.size() - 1)).isAbsolute() ? Paths.get(args.get(args.size() - 1)) : Paths.get(currentDir, args.get(args.size() - 1));
        try {
            if (Files.isDirectory(dst)) Files.copy(src, dst.resolve(src.getFileName()), StandardCopyOption.REPLACE_EXISTING);
            else Files.copy(src, dst, StandardCopyOption.REPLACE_EXISTING);
            return 0;
        } catch (IOException e) { System.err.println("ntbash: cp: " + e.getMessage()); return 1; }
    }

    static int builtinMv(List<String> args) {
        if (args.size() < 2) { System.err.println("ntbash: mv: argomenti mancanti"); return 1; }
        Path src = new File(args.get(0)).isAbsolute() ? Paths.get(args.get(0)) : Paths.get(currentDir, args.get(0));
        Path dst = new File(args.get(args.size() - 1)).isAbsolute() ? Paths.get(args.get(args.size() - 1)) : Paths.get(currentDir, args.get(args.size() - 1));
        try {
            if (Files.isDirectory(dst)) Files.move(src, dst.resolve(src.getFileName()), StandardCopyOption.REPLACE_EXISTING);
            else Files.move(src, dst, StandardCopyOption.REPLACE_EXISTING);
            return 0;
        } catch (IOException e) { System.err.println("ntbash: mv: " + e.getMessage()); return 1; }
    }

    static void deleteRecursive(Path path) throws IOException {
        if (Files.isDirectory(path)) {
            try (DirectoryStream<Path> ds = Files.newDirectoryStream(path)) {
                for (Path p : ds) deleteRecursive(p);
            }
        }
        Files.deleteIfExists(path);
    }

    static int builtinRm(List<String> args) {
        boolean recursive = false, force = false;
        List<String> targets = new ArrayList<>();
        for (String a : args) { if (a.equals("-r") || a.equals("-R")) recursive = true; else if (a.equals("-f")) force = true; else targets.add(a); }
        for (String t : targets) {
            Path path = new File(t).isAbsolute() ? Paths.get(t) : Paths.get(currentDir, t);
            try {
                if (Files.isDirectory(path) && !recursive) { System.err.println("ntbash: rm: " + t + ": è una directory"); return 1; }
                if (recursive) deleteRecursive(path);
                else Files.delete(path);
            } catch (IOException e) { if (!force) { System.err.println("ntbash: rm: " + t + ": " + e.getMessage()); return 1; } }
        }
        return 0;
    }

    static int builtinCat(List<String> args) {
        if (args.isEmpty()) {
            try { char[] buf = new char[4096]; int r; while ((r = in.read(buf)) >= 0) out.print(new String(buf, 0, r)); } catch (IOException e) {}
            return 0;
        }
        for (String a : args) {
            Path path = new File(a).isAbsolute() ? Paths.get(a) : Paths.get(currentDir, a);
            try { out.print(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)); }
            catch (IOException e) { System.err.println("ntbash: cat: " + a + ": " + e.getMessage()); return 1; }
        }
        return 0;
    }

    static int builtinExport(List<String> args) {
        for (String a : args) {
            int eq = a.indexOf('=');
            if (eq >= 0) env.put(a.substring(0, eq), a.substring(eq + 1));
            else if (!env.containsKey(a)) env.put(a, "");
        }
        return 0;
    }

    static int builtinUnset(List<String> args) {
        for (String a : args) env.remove(a);
        return 0;
    }

    static int builtinRead(List<String> args) {
        if (args.isEmpty()) return 1;
        String line;
        try { line = in.readLine(); } catch (IOException e) { return 1; }
        if (line == null) return 1;
        if (args.size() == 1) env.put(args.get(0), line);
        else {
            String[] parts = line.split("\\s+", args.size());
            for (int i = 0; i < args.size(); i++) env.put(args.get(i), i < parts.length ? parts[i] : "");
        }
        return 0;
    }

    static int builtinHelp(List<String> args) { out.print(showHelp()); return 0; }

    static int builtinSource(List<String> args) {
        if (args.isEmpty()) return 1;
        String path = args.get(0);
        if (!new File(path).isAbsolute()) path = currentDir + File.separator + path;
        try {
            String text = new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8);
            return executeScriptText(text);
        } catch (IOException e) { System.err.println("ntbash: source: " + args.get(0) + ": " + e.getMessage()); return 1; }
    }

    static int builtinTest(List<String> args) {
        List<String> a = new ArrayList<>(args);
        if (!a.isEmpty() && (a.get(a.size() - 1).equals("]") || a.get(a.size() - 1).equals("]]"))) a.remove(a.size() - 1);
        if (a.isEmpty()) return 1;
        if (a.get(0).equals("!")) return builtinTest(a.subList(1, a.size())) != 0 ? 0 : 1;
        if (a.size() == 1) return a.get(0).isEmpty() ? 1 : 0;
        if (a.size() == 2) {
            String op = a.get(0), val = a.get(1);
            File path = new File(val).isAbsolute() ? new File(val) : new File(currentDir, val);
            if (op.equals("-f")) return path.isFile() ? 0 : 1;
            if (op.equals("-d")) return path.isDirectory() ? 0 : 1;
            if (op.equals("-e")) return path.exists() ? 0 : 1;
            if (op.equals("-z")) return val.isEmpty() ? 0 : 1;
            if (op.equals("-n")) return val.isEmpty() ? 1 : 0;
            return 1;
        }
        if (a.size() == 3) {
            String x = a.get(0), op = a.get(1), y = a.get(2);
            if (op.equals("=") || op.equals("==")) {
                if (hasGlobChars(y)) return fnmatch(x, y) ? 0 : 1;
                return x.equals(y) ? 0 : 1;
            }
            if (op.equals("!=")) return x.equals(y) ? 1 : 0;
            if (op.equals("-eq") || op.equals("-ne") || op.equals("-lt") || op.equals("-le") || op.equals("-gt") || op.equals("-ge")) {
                int xi, yi;
                try { xi = Integer.parseInt(x); yi = Integer.parseInt(y); } catch (NumberFormatException e) { return 2; }
                if (op.equals("-eq")) return xi == yi ? 0 : 1;
                if (op.equals("-ne")) return xi != yi ? 0 : 1;
                if (op.equals("-lt")) return xi < yi ? 0 : 1;
                if (op.equals("-le")) return xi <= yi ? 0 : 1;
                if (op.equals("-gt")) return xi > yi ? 0 : 1;
                if (op.equals("-ge")) return xi >= yi ? 0 : 1;
            }
            return 1;
        }
        return 1;
    }

    static int builtinTrue(List<String> args) { return 0; }
    static int builtinFalse(List<String> args) { return 1; }

    static final Map<String, Builtin> builtins = new HashMap<>();
    static {
        builtins.put("echo", ntbash::builtinEcho);
        builtins.put("pwd", ntbash::builtinPwd);
        builtins.put("cd", ntbash::builtinCd);
        builtins.put("ls", ntbash::builtinLs);
        builtins.put("mkdir", ntbash::builtinMkdir);
        builtins.put("cp", ntbash::builtinCp);
        builtins.put("mv", ntbash::builtinMv);
        builtins.put("rm", ntbash::builtinRm);
        builtins.put("cat", ntbash::builtinCat);
        builtins.put("export", ntbash::builtinExport);
        builtins.put("unset", ntbash::builtinUnset);
        builtins.put("read", ntbash::builtinRead);
        builtins.put("help", ntbash::builtinHelp);
        builtins.put("source", ntbash::builtinSource);
        builtins.put(".", ntbash::builtinSource);
        builtins.put("test", ntbash::builtinTest);
        builtins.put("[", ntbash::builtinTest);
        builtins.put("[[", ntbash::builtinTest);
        builtins.put("true", ntbash::builtinTrue);
        builtins.put("false", ntbash::builtinFalse);
    }

    // --- Esecuzione script ---
    static int executeScriptText(String text) {
        List<String> heredocs = new ArrayList<>();
        text = preprocessHeredocs(text, heredocs);
        List<Object> tokens = tokenize(text);
        Parser parser = new Parser(tokens, heredocs);
        Node program = parser.parseList(new HashSet<>());
        try { return executeNode(program); }
        catch (ExitSignal e) { return e.code; }
        catch (BreakSignal e) { return 0; }
        catch (ContinueSignal e) { return 0; }
    }

    public static void main(String[] args) {
        if (args.length > 0) {
            if (args[0].equals("--help") || args[0].equals("-h") || args[0].equals("help")) {
                System.out.print(showHelp());
                System.exit(0);
            }
            env.put("0", args[0]);
            positional = new ArrayList<>(Arrays.asList(args).subList(1, args.length));
            String text;
            try { text = new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8); }
            catch (IOException e) { System.err.println("ntbash: " + args[0] + ": " + e.getMessage()); System.exit(1); return; }
            int code = executeScriptText(text);
            System.exit(code);
        } else {
            System.out.println("Uso: java ntbash <script.sh> [argomenti...]");
            System.out.println("Digita 'help' all'interno dello script per info.");
        }
    }
}
