# pyt_form_man.md — Manuale del file JSON per `pyt form`

Comando:

```cmd
pyt.cmd form fileform.json
```

Il file JSON descrive un form interattivo. Struttura: dizionario piatto,
chiave = `id` univoco **alfanumerico** → oggetto con `type`.

## Sezione `config` (obbligatoria, non è un oggetto)

```json
"config": { "mode": "TUI", "return.file": "risultati.json" }
```

| Parametro | Obbligo | Valori |
|---|---|---|
| `mode` | obbligatorio | `TUI` (console) \| `GUI` (finestra tkinter) \| `WEB` (`WEBFORM` accettato come alias, pagina + browser) |
| `return.file` | opzionale | path del file risultati; se relativo, cartella del JSON; se assente, `<basename>_results.json` |
| `cmdline`, `wait` | opzionali | comando di default per i BUTTON `EXEC` senza `command` |

## Oggetti

### WINDOW (almeno uno; il primo è la finestra principale)

```json
"win": { "type": "WINDOW", "title": "Titolo", "width": 60, "height": 16 }
```

`title` testo in alto, `width`/`height` dimensioni (caratteri in TUI, ×8/×16 pixel in GUI).

### THEME (opzionale; se assente vale il default)

```json
"th": { "type": "THEME", "fg": "white", "bg": "blue", "frame": true }
```

`fg`/`bg`: `black red green yellow blue magenta cyan white default`.
`frame`: `true` = bordi ASCII. Default automatico: `{fg: default, bg: default, frame: true}`.

### LAYOUT (almeno uno)

```json
"lay": { "type": "LAYOUT", "title": "Dati", "x": 1, "y": 1, "width": 50, "height": 10 }
```

Area contenitore. `x`,`y` posizione in WINDOW (0 dal bordo), `width`,`height`
dimensioni. TEXT, LABEL, LIST e BUTTON **devono** indicare `layout` esistente.

### TEXT (testo modificabile, salvato in results)

```json
"txt1": { "type": "TEXT", "layout": "lay", "value": "Nome:" }
```

Si modifica digitando `txt1=Nuovo testo`. Il valore finale finisce in results.

### LABEL (etichetta fissa: mostrata, mai salvata)

```json
"lbl1": { "type": "LABEL", "layout": "lay", "caption": "Inserire i dati:",
          "size": 30, "position": "LEFT" }
```

`caption` = testo; `size` = larghezza in caratteri (>0); `position` =
`LEFT` | `RIGHT` | `CENTER` (allineamento nella sua area).

### LIST (scelta da elenco, salvata in results)

```json
"lst1": { "type": "LIST", "layout": "lay",
          "options": ["piccolo", "medio", "grande"], "value": "" }
```

`options` = array non vuoto di stringhe; `value` = scelta attuale (`""` o una
delle options). Si imposta con `lst1=medio` (solo valori in lista, altrimenti
errore). In GUI è un menu a tendina, in WEB un `<select>`.

### BUTTON (almeno uno con `EXIT`)

```json
"btn1": { "type": "BUTTON", "layout": "lay", "value": "Esegui",
          "command": "cmd1", "action": "EXEC" },
"btn2": { "type": "BUTTON", "layout": "lay", "value": "Esci", "action": "EXIT" }
```

`value` = etichetta (nel TUI i bottoni sono numerati `(1)`, `(2)`... in ordine
di definizione). `command` = id del COMMAND (se manca si usa
`config.cmdline`, che allora diventa obbligatorio). `action`: `EXEC`
(default, esegue) oppure `EXIT` (chiude il form; ne serve almeno uno).

### COMMAND

```json
"cmd1": { "type": "COMMAND", "cmdline": "python backup.py --full", "wait": true }
```

`cmdline` = comando (stringa non vuota, eseguito come lista, mai shell).
`wait: true` = attendi la fine (log exit code); `false` = avvia e continua
(il form può chiudersi mentre gira).

## Interazione (TUI)

```
scelta> 1            → preme il bottone 1
scelta> txt1=Mario   → modifica il testo
scelta> lst1=medio   → sceglie dalla lista
scelta> 2            → preme Esci → scrive results e chiude
```

## File generati (stessa cartella del JSON)

- `<basename>.log` — una riga `[YYYYMMDD:HHMMSS] EVENTO ...` per:
  `FORM_START`, `TEXT_CHANGED`, `BUTTON_PRESSED`, `COMMAND_EXEC`,
  `COMMAND_EXIT_CODE` / `COMMAND_STARTED`, `INPUT_NON_VALIDO`, `FORM_END`
  (più `THEME_DEFAULT` se manca il THEME).
- `<basename>_results.json` (o `config.return.file`) — valori finali:
  TEXT e LIST con il loro valore, BUTTON con l'ultima etichetta premuta
  (`null` se mai premuto). LABEL/THEME/WINDOW/LAYOUT/COMMAND esclusi.

## Esempi pronti

- `Examples/pyt_form_sample1.json` (`mode: TUI`)
- `Examples/pyt_form_sample2.json` (`mode: GUI`)
- `Examples/pyt_form_sample3.json` (`mode: WEBFORM`, alias di WEB)

Tutti validi e completi: WINDOW+THEME+LAYOUT+LABEL+TEXT+LIST+2 BUTTON+COMMAND.
Prova non interattiva: `echo 2 | pyt.cmd form Examples\pyt_form_sample1.json`
(preme subito Esci).
