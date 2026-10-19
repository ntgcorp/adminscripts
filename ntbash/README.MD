# ntbash.py — Mini interprete Bash in Python

Interprete Bash portabile scritto in solo Python stdlib, pensato per ambienti Windows aziendali bloccati (niente JDK, compilatori o tool Unix).

> Nota: il documento di design è `Prompt_ntbash.md`. `ntbash.py` implementa il sottoinsieme di Bash descritto lì; per i dettagli interni consulta `AGENTS.md`.

## Uso

```sh
python ntbash.py <script.sh> [argomenti...]
```

- Gli argomenti dopo lo script diventano `$1..$n`, `$#`, `$@`, `$*`.
- `python ntbash.py --help` stampa l'help dei builtin.
- Nessuna installazione, nessuna dipendenza esterna. Solo stdlib (`sys, os, shutil, subprocess, re, glob, fnmatch, io, threading, ast`).

Su Windows aziendale è disponibile anche `ntbash.cmd`, ma punta a un path hardcoded (`k:\tools\pyn.cmd`): fuori da quella macchina usa `python` direttamente.

## Cosa fa

| Funzione | Sintassi | Esempio |
|---|---|---|
| Variabili | `NOME=valore`, `$NOME`, `${NOME}` | `NOME=Mondo` → `echo Ciao $NOME` |
| Operatori variabile | `${VAR:-def}`, `${#VAR}`, `${VAR:off:len}`, `${VAR#pat}` | `echo ${NOME:-anonimo}` |
| Aritmetica intera | `$((espressione))` | `echo $((10/2))` → `5` |
| Sostituzione comando | `$(comando)` | `echo $(pwd)` |
| Glob | `* ? [...]` | `ls *.py` |
| Builtin | `echo, pwd, cd, ls, mkdir, cp, mv, rm, cat, export, unset, read, help, source, test/[ /[[, true, false` | `mkdir -p a/b` |
| Controllo | `if/elif/else/fi`, `for`, `while`, `until`, `case`, funzioni `nome() { }` | vedi sotto |
| Pipeline | `a \| b` (chaining reale) | `pwd \| cat` |
| Redirezioni | `> >> < 2> 2>> 2>&1 &> <<` | `echo ciao > out.txt` |
| Background | `comando &` (`$!`) | `sleep 1 &` |
| Commenti | `#` a inizio parola | `echo ciao # saluto` |
| Sottoprocessi | qualsiasi comando esterno | `python --version` |

Script di esempio:

```sh
# demo.sh
NOME=Mondo
echo Ciao $NOME
echo Risultato: $((10/2))
if [ -f ntbash.py ]; then
    echo "ntbash.py esiste"
fi
for i in a b c; do
    echo "item: $i"
done
saluta() {
    echo "ciao $1"
}
saluta mondo
pwd | cat
echo ciao > out.txt
```

```sh
python ntbash.py demo.sh uno due
```

## Come è fatto

Tutto in un file (`ntbash.py`):

- `env` (dizionario variabili), `positional` (`$1..$n`), `functions`, `current_dir`, `out` (stream di output corrente).
- `tokenize` → parole come liste di segmenti `lit`/`dq`/`sq`; `Parser` ricorsivo → AST (`Cmd/Pipeline/AndOr/List/If/For/While/Case/Func/Block/Subshell`); `execute_node` esegue.
- `expand_word` → per segmento: `sq` letterale, `dq` espande variabili/aritmetica/comando ma non i glob, `lit` espande + glob.
- Aritmetica con `ast` (whitelist di operatori), **mai** `eval` nudo.
- `run_command` → builtin, altrimenti `subprocess.run([name]+args, shell=False, cwd=current_dir)`.
- Pipeline: l'output di ogni stadio passa come `input_data` allo stadio successivo.
- Controllo di flusso via eccezioni: `ExitSignal`, `ReturnSignal`, `BreakSignal`, `ContinueSignal`.

Per aggiungere un builtin: definisci `builtin_xxx(args)` e registralo nel dict `builtins` + voce in `DOCS`.

## Limiti noti

- `$@`/`$*` si espandono in un'unica stringa separata da spazi (niente quoting per-argomento).
- Heredoc `<<` supporta solo delimitatori semplici non quotati.
- Le variabili esportate con `export` non vengono propagate ai sottoprocessi esterni (solo all'ambiente interno).
- `case` usa `fnmatch` per i pattern.

## File del repo

- `ntbash.py` — l'interprete (unico codice reale).
- `Prompt_ntbash.md` — documento di design / specifica del linguaggio.
- `test_ntbash_base.sh` — smoke test: crea/copia/sposta/elimina file e cartelle.
- `ntbash.cmd` — wrapper Windows legato a `k:\tools\`.
- `opencode_start_pyn.cmd` — avvia `ocode start`, non c'entra con ntbash.
- `AGENTS.md` — istruzioni per sessioni agentiche future.
