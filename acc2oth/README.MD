# acc2oth — Access .accdb -> File Singoli

Manuale bilingue / Bilingual manual: **Italiano + English** (stesso file / same file).

- Programma: [`acc2oth.py`](./acc2oth.py) · launcher [`acc2oth.cmd`](./acc2oth.cmd)

---

# PARTE 1 — MANUALE IN ITALIANO

## 1. Cos'è acc2oth

`acc2oth` è un programma CLI Python per Windows che estrae gli oggetti di un database
Microsoft Access (`.accdb`/`.mdb`) in **file singoli** sotto una cartella di output,
pronti per versionamento (git) e transpiling VBA -> Python tramite OpenRouter.

Workflow interno (ogni `app_*` ritorna `sResult`: `""` = ok):

```
app_args(file_ini, cli_key) -> app_verify -> app_export -> app_tables -> app_prompt -> app_python -> app_java -> app_end
```

- `app_args`: carica il file `.ini` alla partenza nel dizionario **`dictConfig`**
  (`dict[str, Any]`, chiavi normalizzate a upper), applica l'override della chiave da CLI.
- `app_verify`: valida i path, crea `OUT.PATH`, risolve `LOG`, verifica `OPENROUTER.*`
  nel `dictConfig` finale quando servono.
- `app_export`: esporta via COM (`SaveAsText`, `QueryDefs.SQL`, `VBE.Export`)
  nell'ordine `FORMS > MODULES > CLASSES > QUERIES > MACROS > REPORTS`.
- `app_tables`: esporta le tabelle in CSV (se `EXP.TABLES=True`).
- `app_prompt` / `app_python` / `app_java`: leggono i `.bas`/`.cls` **già presenti su filesystem**
  in `OUT.PATH/modules/` e `OUT.PATH/classes/` e generano `prompt_*.md` / `*.py` / `*.java` via OpenRouter.
- `app_end`: scrive `index.json` (con merge dello storico).

**Cosa estrae (solo se `EXP.*=True`):** Form (`.txt`), Moduli standard (`.bas`),
Classi (`.cls`), Query (`.sql`), Macro (`.txt`), Report (`.txt`), Tabelle (`.csv`).
**Tabelle: mai esportate di default**, solo log `Skipped table <nome> (type: linked/local)` se `EXP.TABLES=False`.

## 2. Requisiti

- Windows 10/11 con **Microsoft Access installato** (serve per COM automation).
- Python 3.10+ con `pywin32` (`win32com.client`) e `requests`:
  ```powershell
  pip install pywin32 requests
  ```
- Chiave OpenRouter **personale** (solo se `EXP.PROMPT=True` o `EXP.PYTHON=True` o `EXP.JAVA=True`):
  richiedila su `https://openrouter.ai/keys` e usala come `OPENROUTER.KEY` nel
  `.ini` oppure come 2o parametro CLI (mai committare chiavi reali).
  Modello di esempio: `OPENROUTER.MODEL=qwen/qwen-2.5-coder-32b-instruct`.

## 2b. Configurazione del launcher `acc2oth.cmd`

Prima del primo uso, apri `acc2oth.cmd` con un editor di testo e imposta la
variabile `PYN` con il percorso del **proprio launcher Python** (nel file
è preimpostato un esempio `k:\Tools\pyn.cmd` che quasi certamente non
corrisponde al tuo PC):

```bat
REM IMPOSTARE LAUNCHER PYTHON (percorso del proprio python/launcher)
SET "PYN=C:\percorso\del\tuo\python.cmd"
```

Poi verifica dal prompt:

```bat
acc2oth.cmd test_codfiscale.ini sk-or-v1-TUA_CHIAVE_PERSONALE
```

Il 2o parametro è la **tua chiave OpenRouter personale**: si sovrappone a
`OPENROUTER.KEY` del `.ini` e ti evita di salvare il segreto nel file di
configurazione. Senza `EXP.PROMPT`/`EXP.PYTHON` attivi la chiave non serve.

## 3. File di configurazione .INI e `dictConfig`

Il file `.ini` (`utf-8`, una sola sezione `[CONFIG]`) viene **caricato alla partenza
in un dizionario `dictConfig`**. Chiavi normalizzate a upper + trim; valori path
(`IN.ACCDB`, `OUT.PATH`, `LOG`, `OPENROUTER.*`) mai forzati a upper.

| Parametro | Obbligatorio | Default | Note |
|---|---|---|---|
| `IN.ACCDB` | sì | — | Path al `.accdb`/`.mdb` (relativo alla cartella del `.ini` o assoluto). Deve esistere. |
| `OUT.PATH` | sì | — | Cartella output; **creata se non esiste** (ricorsiva). Verificata in scrittura. |
| `LOG` | no | `export.log` | Path **relativo a `OUT.PATH`** (in append). Se assoluto, usato così com'è. |
| `EXP.FORMS/MODULES/CLASSES/QUERIES/MACROS/REPORTS/TABLES` | no | `False` | `True/False` (tollerati `1/0/yes/no/si/on/off`, case-insensitive). Parametro canonico `EXP.QUERIES`; alias storico deprecato `EXP.QUERYES` tollerato (`QUERIES` prevale + warning). Cartella output sempre `queryes/`. `EXP.TABLES` esporta tabelle in `tables/*.csv`. |
| `EXP.PROMPT` / `EXP.PROMPT.LIST` | no | `False` / vuoto | Genera `prompt_<nome>.md` per ogni `.bas`/`.cls`. `LIST` = CSV case-insensitive sugli stem; vuota = tutti. |
| `EXP.PYTHON` / `EXP.PYTHON.LIST` | no | `False` / vuoto | Genera `<nome>.py` per ogni `.bas`/`.cls`. Filtro come sopra. |
| `EXP.JAVA` / `EXP.JAVA.LIST` | no | `False` / vuoto | Genera `<nome>.java` per ogni `.bas`/`.cls` (via OpenRouter). `LIST` = CSV case-insensitive sugli stem; richiede `EXP.JAVA=True`. |
| `EXP.TABLES` / `EXP.TABLES.LIST` | no | `False` / vuoto | Esporta tabelle in `tables/*.csv`. `LIST` = CSV case-insensitive sui nomi tabella; richiede `EXP.TABLES=True`. |
| `OPENROUTER.KEY` | **facoltativa nel `.ini`** | `""` | **Deve essere presente (non vuota) nel `dictConfig` finale se `EXP.PROMPT=True` o `EXP.PYTHON=True` o `EXP.JAVA=True`**: vale il valore `.ini` **oppure** il 2o parametro CLI (che si sovrappone). Se tutti e tre `False`, può mancare. |
| `OPENROUTER.MODEL` | richiesta solo se `EXP.PROMPT/EXP.PYTHON/EXP.JAVA=True` | `""` | Es. `qwen/qwen-2.5-coder-32b-instruct`. Vedi nota privacy sotto. |

Esempio minimo senza LLM (vale anche come schema di esempio: tutti gli `EXP.*`
possono essere `False`; le `LIST` sono facoltative, oggetti separati da `","`):

```ini
[CONFIG]
IN.ACCDB=C:\dati\gestionale.accdb
OUT.PATH=C:\dati\out
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
```

Esempio con LLM e **chiave volutamente assente** (passata da CLI):

```ini
[CONFIG]
IN.ACCDB=NTJOBS_TEST.accdb
OUT.PATH=ntjobs_test
LOG=export.log
EXP.FORMS=False
EXP.TABLES=True
EXP.PROMPT=True
EXP.PROMPT.LIST=ntSys
EXP.PYTHON=True
EXP.JAVA=True
OPENROUTER.MODEL=qwen/qwen-2.5-coder-32b-instruct
; OPENROUTER.KEY omessa: verra passata come 2o parametro CLI
```

## 4. Uso da riga di comando (CLI)

```
usage: acc2oth <file.ini> [openrouter.key]
```

- `file.ini` (posizionale, required): path al file di configurazione.
- `openrouter.key` (posizionale, **facoltativo**): chiave OpenRouter che
  **si sovrappone, se passata** (non vuota dopo `strip`), a `OPENROUTER.KEY`
  del file `.ini` nel `dictConfig` finale. La CLI prevale sempre; nel log compare
  solo `OPENROUTER.KEY da CLI (override...)`, mai il valore.

```powershell
python -m acc2oth ./config/test.ini
python -m acc2oth C:\path\config.ini
python -m acc2oth C:\path\config.ini sk-or-v1-TUA_CHIAVE
python acc2oth.py ./ntjobs_test.ini sk-or-v1-TUA_CHIAVE
```

Launcher batch (già predisposto a inoltrare il 2o parametro):

```bat
acc2oth.cmd ntjobs_test.ini sk-or-v1-TUA_CHIAVE
acc2oth.cmd ntjobs_test.ini
```

### Esempio concreto: ntjobs_test con Prompt, Python e Java

Il file `ntjobs_test/ntjobs_test.ini` nella repo mostra una configurazione completa che attiva:

- **Export tabelle** (`EXP.TABLES=True`) con filtro su `TabFormats` (`EXP.TABLES.LIST=TabFormats`)
- **Generazione prompt markdown** (`EXP.PROMPT=True`) filtrato su `ntSys` (`EXP.PROMPT.LIST=ntSys`)
- **Generazione Python** (`EXP.PYTHON=True`) 
- **Generazione Java** (`EXP.JAVA=True`) con filtro su `NC_SysInfo, ntSys` (`EXP.JAVA.LIST=NC_SysInfo, ntSys`)

La chiave OpenRouter **non è nel file .ini** (riga commentata `;OPENROUTER.KEY=`) e viene passata **come 2° parametro CLI**, evitando di committare il segreto:

```powershell
# Da radice del progetto:
python -m acc2oth ntjobs_test/ntjobs_test.ini sk-or-v1-TUA_CHIAVE_OPENROUTER
```

oppure usando il launcher batch:

```bat
acc2oth.cmd ntjobs_test/ntjobs_test.ini sk-or-v1-TUA_CHIAVE_OPENROUTER
```

Cosa succede in sequenza:
1. `app_export` — esporta Form/Moduli/Classi/Query/Macro/Report da `NTJOBS_TEST.accdb` in `ntjobs_test/`
2. `app_tables` — esporta `TabFormats` in `ntjobs_test/tables/TabFormats.csv`
3. `app_prompt` — genera `ntjobs_test/modules/prompt_ntSys.md` dal `ntSys.bas` esportato
4. `app_python` — genera `ntjobs_test/modules/ntSys.py` dal `ntSys.bas`
5. `app_java` — genera `ntjobs_test/modules/NC_SysInfo.java` e `ntjobs_test/modules/ntSys.java`
6. `app_end` — aggiorna `ntjobs_test/index.json` con tutti i file generati

La chiave API viene letta dal 2° parametro, sovrascrive quella del `.ini` (vuota), e non viene mai scritta nei log né in `index.json`.

Regola di precedenza:

1. `dictConfig["OPENROUTER.KEY"]` = valore `.ini` (anche vuoto/mancante, è facoltativo lì).
2. Se `openrouter.key` da CLI è non vuota → sovrascrive il punto 1.
3. `app_verify` controlla il risultato: se `EXP.PROMPT`/`EXP.PYTHON=True` e la chiave
   finale è vuota → errore `exit 2` (validazione, prima di aprire Access).

Exit code: `0` successo · `1` errore estrazione/runtime · `2` errore validazione/config
(manca `.ini`, `[CONFIG]` assente, `IN.ACCDB` mancante, `OPENROUTER.*` mancanti quando richiesti).

## 5. Struttura di output

```
<OUT.PATH>/
  export.log
  index.json
  forms/*.txt
  modules/*.bas  +  prompt_*.md (se EXP.PROMPT)  +  *.py (se EXP.PYTHON)
  classes/*.cls  +  prompt_*.md                  +  *.py
  queryes/*.sql
  macros/*.txt
  reports/*.txt
```

- Overwrite dei file esportati sempre implicito; `LOG` in append; `index.json`
  scritto in modo atomico (`tmp` + `replace`) con **merge** dello storico
  (utile per run "solo prompt/python" senza riesportare).
- Sanitizzazione nomi: caratteri `[<>:"/\|?*]` e control → `_`, trim punti/spazi
  finali; collisioni → suffisso `_1`, `_2`; query di sistema (`~*`, `MSys*`) ignorate.

## 6. Casi d'uso

1. **Solo export per versionamento (nessuna chiave).**
   Tutti gli `EXP.*` oggetti a `True`, `EXP.PROMPT/EXP.PYTHON=False`, nessuna
   `OPENROUTER.*` richiesta. Committa `OUT.PATH` in git.
2. **Codice riservato: chiave fuori dal file.**
   Ometti `OPENROUTER.KEY` dal `.ini` (committabile) e passala solo da CLI/CI:
   `python -m acc2oth prod.ini %OPENROUTER_KEY%`. Il `.ini` resta senza segreti.
3. **Rigenerazione prompt senza riaprire Access.**
   `EXP.MODULES/EXP.CLASSES=False`, `EXP.PROMPT=True` (+ eventuale `LIST`):
   `app_prompt` scansiona i `.bas`/`.cls` già presenti e rigenera solo i `.md`.
4. **Transpiling VBA → Python.**
   `EXP.PYTHON=True` + `EXP.PYTHON.LIST=modFatture,clsGestore` per convertire solo
   due moduli; output `.py` accanto ai sorgenti, con diagnostica token/costo nel log.
5. **Filtro mirato su un modulo.**
   `EXP.PROMPT.LIST=ntSys` genera `prompt_ntSys.md` soltanto (come in `ntjobs_test.ini`).
6. **Batch multi-database.**
   Un `.ini` per DB + loop PowerShell; chiave unica passata da variabile d'ambiente:
   ```powershell
   foreach ($f in Get-ChildItem .\cfg\*.ini) { python -m acc2oth $f.FullName $env:OPENROUTER_KEY }
   ```
7. **Diagnostica costi LLM.**
   Ogni chiamata logga `OpenRouter PROMPT/PYTHON start ...` (model, src, chars)
   e `... done ... in Xm SSs | tokens prompt/completion/total | cost=$...`.

## 7. Errori comuni

- `OPENROUTER.KEY richiesta nel dictConfig finale...` → o la aggiungi al `.ini`
  o la passi come 2o parametro CLI.
- `404 ... Paid model training violation` (model `*-contributor`) → vai su
  `https://openrouter.ai/settings/privacy`, abilita *"Allow training on paid models"*,
  oppure usa `OPENROUTER.MODEL=meta/muse-spark-1.3`. Il programma tenta comunque
  un fallback automatico togliendo il suffisso `-contributor`.
- `Microsoft Access COM automation non disponibile` → installa Access + `pywin32`.
- `Database bloccato/in uso` → chiudi Access / elimina lock `.laccdb`.
- `OUT.PATH non scrivibile` → verifica permessi/cartella di rete.

## 8. Sicurezza

- Non committare chiavi reali nei `.ini` di esempio; preferisci il 2o parametro CLI
  o variabili d'ambiente. La chiave non viene mai scritta in `index.json` né
  stampata nel log (solo la *fonte*: `cli`/`ini`).
- Il DB è aperto in sola lettura logica (`Exclusive=False`, `AutomationSecurity=1`)
  e richiuso con `CloseCurrentDatabase()` + `Quit()` in `finally`.

## 9. Divergenze documentate rispetto a bozze storiche

Nessun `export_mode/naming/overwrite/include_properties/manifest.json/logs/`;
sostituiti da `EXP.*`, `LOG`, `index.json`, sottocartelle fisse. `EXP.QUERIES` è il nome
canonico; `EXP.QUERYES` (typo storico) resta solo come alias deprecato.
Correzioni COM documentate: `SaveAsText` è metodo di `Application`
(`app.SaveAsText`, non `DoCmd`), enumerazione `VBE.VBComponents` 1-based,
deduplica del fallback `AllModules` (nomi unici per progetto). Novità di questa revisione: `OPENROUTER.KEY`
facoltativa nel `.ini` + 2o parametro CLI in override.

---

# PART 2 — ENGLISH MANUAL

## 1. What acc2oth is

`acc2oth` is a Windows Python CLI that extracts objects from a Microsoft Access
database (`.accdb`/`.mdb`) into **single files** under an output folder, ready for
versioning (git) and VBA → Python transpiling via OpenRouter.

Internal pipeline (each `app_*` returns `sResult`: `""` = ok):

```
app_args(file_ini, cli_key) -> app_verify -> app_export -> app_prompt -> app_python -> app_end
```

- `app_args`: loads the `.ini` file at startup into a **`dictConfig`** dictionary
  (`dict[str, Any]`, upper-normalized keys), then applies the CLI key override.
- `app_verify`: validates paths, creates `OUT.PATH`, resolves `LOG`, checks
  `OPENROUTER.*` in the final `dictConfig` when needed.
- `app_export`: exports via COM (`SaveAsText`, `QueryDefs.SQL`, `VBE.Export`) in
  `FORMS > MODULES > CLASSES > QUERIES > MACROS > REPORTS` order.
- `app_tables`: exports tables to CSV (if `EXP.TABLES=True`).
- `app_prompt` / `app_python` / `app_java`: scan existing `.bas`/`.cls` files on the filesystem
  under `OUT.PATH/modules/` and `OUT.PATH/classes/` and generate `prompt_*.md` / `*.py` / `*.java` via OpenRouter.
- `app_end`: writes `index.json` (merged with history).

**Extracted (only when `EXP.*=True`):** Forms (`.txt`), Standard modules (`.bas`),
Classes (`.cls`), Queries (`.sql`), Macros (`.txt`), Reports (`.txt`), Tables (`.csv`).
**Tables are never exported by default**, only `Skipped table <name> (type: linked/local)` logs if `EXP.TABLES=False`.

## 2. Requirements

- Windows 10/11 with **Microsoft Access installed** (COM automation required).
- Python 3.10+ with `pywin32` and `requests`:
  ```powershell
  pip install pywin32 requests
  ```
- Personal OpenRouter key (only when `EXP.PROMPT=True` or `EXP.PYTHON=True` or `EXP.JAVA=True`):
  get one at `https://openrouter.ai/keys` and use it as `OPENROUTER.KEY` in the
  `.ini` or as the 2nd CLI parameter (never commit real keys).
  Example model: `OPENROUTER.MODEL=qwen/qwen-2.5-coder-32b-instruct`.

## 2b. Configuring the `acc2oth.cmd` launcher

Before first use, open `acc2oth.cmd` in a text editor and set the `PYN` variable
to the path of **your own Python launcher** (the file ships with a sample
`k:\Tools\pyn.cmd` that will almost certainly not match your PC):

```bat
REM SET PYTHON LAUNCHER (path to your own python/launcher)
SET "PYN=C:\path\to\your\python.cmd"
```

Then test from the prompt:

```bat
acc2oth.cmd test_codfiscale.ini sk-or-v1-YOUR_PERSONAL_KEY
```

The 2nd parameter is **your personal OpenRouter key**: it overrides
`OPENROUTER.KEY` from the `.ini` so you don't have to store the secret in the
configuration file. Without active `EXP.PROMPT`/`EXP.PYTHON` no key is needed.

## 3. INI configuration file and `dictConfig`

The `.ini` file (`utf-8`, single `[CONFIG]` section) is **loaded at startup into a
`dictConfig` dictionary**. Keys are upper/trim-normalized; path values
(`IN.ACCDB`, `OUT.PATH`, `LOG`, `OPENROUTER.*`) are never upper-cased.

| Parameter | Required | Default | Notes |
|---|---|---|---|
| `IN.ACCDB` | yes | — | Path to `.accdb`/`.mdb` (relative to the `.ini` folder or absolute). Must exist. |
| `OUT.PATH` | yes | — | Output folder; **created if missing** (recursive). Write-checked. |
| `LOG` | no | `export.log` | Path **relative to `OUT.PATH`** (append mode). Absolute paths honored. |
| `EXP.FORMS/MODULES/CLASSES/QUERIES/MACROS/REPORTS/TABLES` | no | `False` | `True/False` (`1/0/yes/no/si/on/off` tolerated, case-insensitive). Canonical `EXP.QUERIES`; historic deprecated alias `EXP.QUERYES` tolerated (`QUERIES` wins + warning). Output folder always `queryes/`. `EXP.TABLES` exports tables to `tables/*.csv`. |
| `EXP.PROMPT` / `EXP.PROMPT.LIST` | no | `False` / empty | Generates `prompt_<name>.md` per `.bas`/`.cls`. `LIST` = case-insensitive CSV of stems; empty = all. |
| `EXP.PYTHON` / `EXP.PYTHON.LIST` | no | `False` / empty | Generates `<name>.py` per `.bas`/`.cls`. Same filter. |
| `EXP.JAVA` / `EXP.JAVA.LIST` | no | `False` / empty | Generates `<name>.java` per `.bas`/`.cls` (via OpenRouter). `LIST` = case-insensitive CSV of stems; requires `EXP.JAVA=True`. |
| `EXP.TABLES` / `EXP.TABLES.LIST` | no | `False` / empty | Exports tables to `tables/*.csv`. `LIST` = case-insensitive CSV of table names; requires `EXP.TABLES=True`. |
| `OPENROUTER.KEY` | **optional in `.ini`** | `""` | **Must be present (non-empty) in the final `dictConfig` when `EXP.PROMPT=True` or `EXP.PYTHON=True` or `EXP.JAVA=True`**: either from the `.ini` **or** the 2nd CLI parameter (which overrides). May be missing when all three are `False`. |
| `OPENROUTER.MODEL` | required only when `EXP.PROMPT/EXP.PYTHON/EXP.JAVA=True` | `""` | E.g. `qwen/qwen-2.5-coder-32b-instruct`. See privacy note below. |

Minimal example without LLM: same schema as the Italian section above.
Example with the key intentionally missing from the `.ini` (passed via CLI): set
`EXP.PROMPT=True` + `OPENROUTER.MODEL=...` and omit `OPENROUTER.KEY`.

## 4. Command-line usage (CLI)

```
usage: acc2oth <file.ini> [openrouter.key]
```

- `file.ini` (positional, required): configuration file path.
- `openrouter.key` (positional, **optional**): OpenRouter key that **overlaps /
  overrides**, when passed (non-empty after `strip`), the `OPENROUTER.KEY` from the
  `.ini` in the final `dictConfig`. CLI always wins; the log records only
  `OPENROUTER.KEY from CLI (override...)`, never the value.

```powershell
python -m acc2oth ./config/test.ini
python -m acc2oth C:\path\config.ini sk-or-v1-YOUR_KEY
python acc2oth.py ./ntjobs_test.ini sk-or-v1-YOUR_KEY
```

Batch launcher (already forwards the 2nd parameter):

```bat
acc2oth.cmd ntjobs_test.ini sk-or-v1-YOUR_KEY
```

### Concrete example: ntjobs_test with Prompt, Python and Java

The file `ntjobs_test/ntjobs_test.ini` in the repo shows a complete configuration that enables:

- **Table export** (`EXP.TABLES=True`) filtered on `TabFormats` (`EXP.TABLES.LIST=TabFormats`)
- **Prompt markdown generation** (`EXP.PROMPT=True`) filtered on `ntSys` (`EXP.PROMPT.LIST=ntSys`)
- **Python generation** (`EXP.PYTHON=True`)
- **Java generation** (`EXP.JAVA=True`) filtered on `NC_SysInfo, ntSys` (`EXP.JAVA.LIST=NC_SysInfo, ntSys`)

The OpenRouter key is **not in the .ini file** (line commented as `;OPENROUTER.KEY=`) and is passed **as the 2nd CLI parameter**, avoiding committing the secret:

```powershell
# From project root:
python -m acc2oth ntjobs_test/ntjobs_test.ini sk-or-v1-YOUR_OPENROUTER_KEY
```

Or using the batch launcher:

```bat
acc2oth.cmd ntjobs_test/ntjobs_test.ini sk-or-v1-YOUR_OPENROUTER_KEY
```

What happens in sequence:
1. `app_export` — exports Forms/Modules/Classes/Queries/Macros/Reports from `NTJOBS_TEST.accdb` to `ntjobs_test/`
2. `app_tables` — exports `TabFormats` to `ntjobs_test/tables/TabFormats.csv`
3. `app_prompt` — generates `ntjobs_test/modules/prompt_ntSys.md` from exported `ntSys.bas`
4. `app_python` — generates `ntjobs_test/modules/ntSys.py` from `ntSys.bas`
5. `app_java` — generates `ntjobs_test/modules/NC_SysInfo.java` and `ntjobs_test/modules/ntSys.java`
6. `app_end` — updates `ntjobs_test/index.json` with all generated files

The API key is read from the 2nd parameter, overrides the empty one in the `.ini`, and is never written to logs or `index.json`.

Precedence:

1. `dictConfig["OPENROUTER.KEY"]` = `.ini` value (may be empty/missing — optional there).
2. A non-empty CLI `openrouter.key` overwrites step 1.
3. `app_verify` checks the result: if `EXP.PROMPT`/`EXP.PYTHON=True` and the final
   key is empty → validation error, `exit 2` (before opening Access).

Exit codes: `0` success · `1` extraction/runtime error · `2` validation/config error
(missing `.ini`, missing `[CONFIG]`, missing `IN.ACCDB`, missing `OPENROUTER.*` when required).

## 5. Output layout

```
<OUT.PATH>/
  export.log
  index.json
  forms/*.txt
  modules/*.bas  +  prompt_*.md (if EXP.PROMPT)  +  *.py (if EXP.PYTHON)  +  *.java (if EXP.JAVA)
  classes/*.cls  +  prompt_*.md                  +  *.py                  +  *.java
  queryes/*.sql
  macros/*.txt
  reports/*.txt
  tables/*.csv
```

- Exported files are always overwritten; `LOG` is appended; `index.json` is written
  atomically (`tmp` + `replace`) **merged** with history (supports "prompt/python
  only" runs without re-exporting).
- Name sanitizing: `[<>:"/\|?*]` and control chars → `_`, trim trailing dots/spaces;
  collisions → `_1`, `_2` suffix; system queries (`~*`, `MSys*`) skipped.

## 6. Use cases

1. **Export-only for versioning (no key).** All object `EXP.*=True`,
   `EXP.PROMPT/EXP.PYTHON=False`; no `OPENROUTER.*` needed. Commit `OUT.PATH` to git.
2. **Keep secrets out of the file.** Omit `OPENROUTER.KEY` from the (committable)
   `.ini` and pass it via CLI/CI only: `python -m acc2oth prod.ini %OPENROUTER_KEY%`.
3. **Regenerate prompts without reopening Access.**
   `EXP.MODULES/EXP.CLASSES=False`, `EXP.PROMPT=True` (+ optional `LIST`):
   scans existing `.bas`/`.cls` and regenerates only the `.md` files.
4. **VBA → Python transpiling.**
   `EXP.PYTHON=True` + `EXP.PYTHON.LIST=modInvoices,clsManager` converts only two
   modules; `.py` next to sources, token/cost diagnostics in the log.
5. **VBA → Java transpiling.**
   `EXP.JAVA=True` + `EXP.JAVA.LIST=modInvoices,clsManager` converts only two
   modules; `.java` next to sources, token/cost diagnostics in the log.
6. **Single-module filter.** `EXP.PROMPT.LIST=ntSys` generates only `prompt_ntSys.md`.
7. **Table export to CSV.**
   `EXP.TABLES=True` + `EXP.TABLES.LIST=Customers,Orders` exports only those tables to `tables/*.csv`.
8. **Multi-database batch.** One `.ini` per DB + PowerShell loop with a single key
   from an environment variable (see Italian snippet above).
9. **LLM cost diagnostics.** Each call logs `OpenRouter PROMPT/PYTHON/JAVA start ...`
   (model, src, chars) and `... done ... in Xm SSs | tokens prompt/completion/total | cost=$...`.

## 7. Common errors

- `OPENROUTER.KEY required in final dictConfig...` → add it to the `.ini` or pass
  it as the 2nd CLI parameter.
- `404 ... Paid model training violation` (`*-contributor` model) → open
  `https://openrouter.ai/settings/privacy`, enable *"Allow training on paid models"*,
  or use `OPENROUTER.MODEL=meta/muse-spark-1.3`. The program still attempts an
  automatic fallback by stripping `-contributor`.
- `Microsoft Access COM automation not available` → install Access + `pywin32`.
- `Database locked/in use` → close Access / remove `.laccdb` lock.
- `OUT.PATH not writable` → check permissions/network folder.
- `EXP.TABLES.LIST specified but EXP.TABLES=False` → set `EXP.TABLES=True` in the `.ini`.
- `EXP.JAVA.LIST specified but EXP.JAVA=False` → set `EXP.JAVA=True` in the `.ini`.

## 8. Security

- Do not commit real keys in sample `.ini` files; prefer the 2nd CLI parameter or
  environment variables. The key is never written to `index.json` nor printed in
  logs (only its *source*: `cli`/`ini`).
- The DB is opened logically read-only (`Exclusive=False`, `AutomationSecurity=1`)
  and always closed with `CloseCurrentDatabase()` + `Quit()` in `finally`.

## 9. Documented divergences from early drafts

No `export_mode/naming/overwrite/include_properties/manifest.json/logs/`; replaced by
`EXP.*`, `LOG`, `index.json`, fixed subfolders. `EXP.QUERIES` is the canonical name;
historic `EXP.QUERYES` (typo) remains only as a deprecated alias. Documented COM
fixes: `SaveAsText` is an `Application` method (`app.SaveAsText`, not `DoCmd`),
1-based `VBE.VBComponents` enumeration, `AllModules`-fallback dedup (unique names). New in this revision: optional
`OPENROUTER.KEY` in the `.ini` + 2nd overriding CLI parameter. New parameters: `EXP.TABLES`/`EXP.TABLES.LIST` (CSV export), `EXP.JAVA`/`EXP.JAVA.LIST` (Java transpiling via OpenRouter).
