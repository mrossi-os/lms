# Inventario delle personalizzazioni

Questa cartella è la **fonte di verità unica** di tutte le personalizzazioni che questo
fork applica sopra Frappe Learning (upstream `frappe/lms`). Ogni voce dice **dove** vive
una personalizzazione, **perché** esiste e **come** si verifica. Dopo ogni merge
dell'upstream il rilevatore di scostamento confronta l'albero con l'inventario e dice in
meno di un secondo quali innesti sono stati ripuliti.

Motivazioni e disegno complessivo: [spec](../superpowers/specs/2026-09-18-upstream-regression-harness-design.md).
Piano della Fase 0: [piano](../superpowers/plans/2026-09-18-upstream-regression-harness-fase-0.md).
Catalogo delle funzionalità, mappa e controllo al commit: [spec del tracciamento](../superpowers/specs/2026-11-23-tracciamento-personalizzazioni-design.md).

Cosa contiene la cartella:

| File | Contenuto |
| --- | --- |
| `*.toml` (es. `spa-grafts.toml`) | le voci di inventario: dove vive una regola e come si verifica |
| `features/<id>.toml` | il catalogo: una scheda per funzionalità, con il suo significato (vedi [features/README.md](features/README.md)) |
| `legacy-attribution.toml` | mappa della storia passata: file upstream → funzionalità, per le modifiche anteriori alla riga `Oslms-Feature`; e il residuo approvato (`[[residue]]`) |
| `translations-it.toml` | registro generato delle nostre traduzioni italiane: non si scrive a mano |

## Comandi

Dalla root del repository, senza Docker né bench:

```bash
python3 scripts/check_customizations.py              # rapporto leggibile
python3 scripts/check_customizations.py --json       # per la skill /upstream-check
python3 scripts/check_customizations.py --list-files # file censiti, uno per riga
python3 scripts/check_customizations.py --base v2.66.0 # confronta C5 con una release precisa
python3 scripts/check_customizations.py --no-base    # salta C5 (nessun avviso C0)
python3 scripts/customization_map.py                 # mappa per funzionalità (sotto)
python3 scripts/customization_translations.py --check  # solo C7
python3 scripts/customization_translations.py --write  # rigenera translations-it.toml
python3 scripts/frozen_diff.py --entry <id> --to <ref> # cosa ha perso una copia congelata
python3 -m unittest discover -s scripts/tests -t . -v  # test degli script
```

Codici di uscita: `0` intatto (avvisi ammessi), `1` scostamento, `2` inventario malformato.

| Controllo | Significato | Gravità |
| --- | --- | --- |
| `C0` | la base upstream (ultima release fusa in `HEAD`) non è calcolabile, di solito per i tag mancanti (`git fetch upstream --tags`): `C5` è stato saltato | avviso |
| `C1` | l'ancora non compare più nel file | errore |
| `C2` | il file non esiste più | errore |
| `C3` | un file porta il marcatore `OSLMS-CUSTOM` ma nessuna voce lo censisce | errore |
| `C4` | la voce non ha test collegati, o il test dichiarato non esiste | avviso |
| `C5` | l'ancora compare anche nel file della base upstream: non distingue la nostra versione da quella upstream, quindi non prova che la regola ci sia | avviso |
| `C6` | l'ancora compare più di una volta nel file | errore |
| `C7` | una traduzione registrata in `translations-it.toml` non c'è più in `lms/locale/it.po`, o è cambiata | errore |
| `C8` | la voce non ha il campo `feature`, o punta a una scheda inesistente | avviso; errore quando esiste `features/.strict` |
| `C8` | una scheda `active` non ha `areas` né voci collegate (`feature = "<id>"`) | errore |
| `C9` | una voce con una copia congelata in `frontend/src/overrides/` non ha `frozen_from` | avviso |
| `C10` | un glob di `areas` di una scheda `active` non corrisponde a nessun file tracciato da git (refuso, o codice spostato) | avviso |

`C5` ha bisogno della base upstream, cioè della storia completa e dei tag di `frappe/lms`;
lo stesso vale per la rigenerazione di `translations-it.toml` (`--write`). `C7` invece
confronta solo il registro con `it.po`, e si salta in silenzio finché il registro non esiste.

## Schema di una voce

Ogni file `*.toml` di questa cartella può dichiarare un array `[[entries]]`. I file senza
`entries` vengono letti e ignorati.

| Campo | Obbligatorio | Contenuto |
| --- | --- | --- |
| `id` | sì | identificatore kebab-case, unico in tutta la cartella |
| `title` | sì | titolo breve, in italiano |
| `layer` | sì | `spa-graft`, `override-file`, `os-lms-api`, `fixture`, `flow` |
| `confidence` | sì | `high` se la motivazione è evidente dal codice o dal commento, `low` se dedotta |
| `intent` | sì | **perché** esiste la personalizzazione, non cosa fa il codice |
| `sites` | sì, tranne `flow` | array di `{ file, anchor, symbol?, marker? }` |
| `visibility` | no | `{ subject, allow, deny }` per le regole di visibilità per ruolo |
| `contract` | no | contratto di un endpoint (fasi successive) |
| `checks` | no | `{ unit = "...", e2e = "..." }` percorsi dei test collegati |
| `feature` | sì (C8) | `id` della scheda del catalogo a cui la voce appartiene |
| `frozen_from` | per le copie congelate | tag upstream (es. `v2.58.0`) o versione frappe-ui (es. `1.0.0-beta.7`; la `v` iniziale è ammessa) da cui è stata fatta la copia in `frontend/src/overrides/` (C9) |
| `status` | no | `accepted-drift` esclude la voce da C1, C2, C4, C5, C6, C8 e C9 |

L'`intent` è il campo più importante: è quello che permette di **riapplicare** la regola
in un file che l'upstream ha riscritto da capo.

## Come scegliere il `layer`

- `spa-graft` — almeno un sito sta in un file che appartiene all'upstream, quindi esposto
  al merge (`frontend/src/components/`, `frontend/src/pages/`, `frontend/src/types/`…).
- `override-file` — tutti i siti stanno in file nostri: `frontend/src/overrides/`,
  `frontend/src/oslms/`, e i file che abbiamo creato noi dentro cartelle upstream
  (es. `frontend/src/stores/mobileCta.js`).
- `os-lms-api`, `fixture`, `flow` — arrivano con le fasi successive.

## Come scegliere una buona `anchor`

1. Scegli l'espressione che **porta la regola**, non la riga del commento `OSLMS-CUSTOM`:
   l'upstream può conservare il commento e riscrivere il codice sotto.
   Buona: `Boolean(props.course.data?.is_valutatore)`. Cattiva: `// OSLMS-CUSTOM: a "Valutatore"…`.
2. Eccezione: se la personalizzazione **consiste** nel commentare un blocco upstream
   (es. recensioni rimosse), il commento è la modifica e l'ancora va sul commento.
3. Deve essere **unica** nel file: verificalo con `grep -cF '<anchor>' <file>` (atteso `1`).
4. Il confronto è testuale e letterale: niente espressioni regolari. In TOML le virgolette
   doppie dentro l'ancora vanno scritte `\"`.

## Una voce per personalizzazione, non per marcatore

Più marcatori nello stesso file appartengono spesso alla stessa regola, e una stessa
regola può toccare più file (es. `course-mobile-cta-bar` vive in quattro file). Si scrive
**una** voce con più `sites`. Un file con marcatori deve comparire in almeno un sito,
altrimenti C3 lo segnala.

## Catalogo delle funzionalità

Le voci dicono **dove** vive una regola; le schede di `features/` dicono **quale
funzionalità** serve e **cosa fa**, in regole osservabili (`behaviour`). Una scheda per
funzionalità, nel file `features/<id>.toml`; schema ed esempio in
[features/README.md](features/README.md). Ogni voce punta alla sua scheda con
`feature = "<id>"` (C8).

Le schede non si cancellano: una funzionalità tolta da noi passa a `status = "retired"`,
una sostituita da una release upstream a `status = "replaced-by-upstream"`, sempre con una
riga in `history`. Sono la base del confronto con l'upstream che `/upstream-upgrade` fa
release per release (fermata F5): quando una novità upstream potrebbe sostituire una nostra
funzionalità, la skill confronta le regole di `behaviour` con il codice upstream, raccomanda
e chiede **sempre** al committente cosa fare.

## Mappa delle personalizzazioni

```bash
python3 scripts/customization_map.py                 # tabella per funzionalità
python3 scripts/customization_map.py --json          # per le skill
python3 scripts/customization_map.py --feature <id>  # una sola funzionalità
python3 scripts/customization_map.py --unattributed  # blocchi senza funzionalità, file nostri non coperti, residuo
python3 scripts/customization_map.py --ref <branch>  # un altro ref (default HEAD)
```

Sola lettura. Confronta il ref con l'ultima release upstream fusa in esso e divide ogni
file upstream che differisce in blocchi (test upstream modificati compresi); ogni blocco va
a una o più funzionalità, commit per commit:

1. le righe `Oslms-Feature` dei commit che hanno scritto le sue righe;
2. per le righe scritte da commit senza la riga, in quest'ordine: l'ancora di una voce che
   quelle righe contengono o toccano → `feature` della voce; il file ricade nelle `areas` di
   una scheda; il file compare in `legacy-attribution.toml` (modifiche anteriori alla regola);
3. le ancore delle voci che il blocco contiene o tocca si aggiungono **sempre**.

Un blocco nessuno rivendica è **non attribuito**. I file nostri (quelli per cui il controllo
al commit chiede la riga) che nessuna `areas`, nessuna voce `[[files]]` e nessun residuo
coprono sono **file non coperti**. Blocchi non attribuiti e file non coperti sono i numeri da
portare a zero: `/upstream-upgrade` ne fa una fermata (F9) prima di creare il branch del
percorso. Fa eccezione il **residuo approvato**: le voci `[[residue]]` di
`legacy-attribution.toml` (`path` esatto o glob, `reason`, `approved` con la data dell'ok del
committente, tutti obbligatori) tolgono quei blocchi e file dai due conteggi e li mostrano a
parte. Con `--ref` schede, voci e mappa storica si leggono a quel ref. Il JSON ha `base`,
`ref`, `features` (per id: `title`, `summary`, `files`, `hunks` con la fonte di ciascuna
funzionalità, `commits`), `unattributed`, `uncovered_files`, `residue` (blocchi con `reason` e
`approved`), `residue_files` e `totals`.

## Controllo al commit

Ogni commit che tocca file upstream o codice nostro deve dire a quale funzionalità serve,
con una riga `Oslms-Feature: <id>` nell'ultimo paragrafo del messaggio, sopra
`Co-Authored-By:`. Lo verifica `scripts/commit_guard.py`, eseguito dall'hook
`.githooks/commit-msg`; si attiva una volta per clone con:

```bash
git config core.hooksPath .githooks
```

Serve python3 3.11 o successivo nel PATH di git. Il controllo rifiuta il commit quando:

- tocca file upstream o codice nostro senza una riga `Oslms-Feature` valida, o con un `id`
  che non ha scheda;
- è un `feat` e non mette in stage la scheda di almeno una funzionalità citata;
- lascia un'ancora orfana o non unica, o un marcatore non censito (C1, C2, C3 e C6 sui file
  del commit), o aggiunge o cambia una voce con un'ancora presente anche nella base (C5);
- usa la deroga `Oslms-Feature: none (<motivo>)` senza motivo, o in un `feat`/`fix`.

Sono esenti i commit di soli documenti, script e traduzioni, i merge fra branch nostri,
i `git revert` e i merge di release upstream **senza conflitti**. Un merge di release upstream
**con conflitti** porta una riga per ogni funzionalità riapplicata nella risoluzione.
Regole complete e percorsi esenti: `CLAUDE.md`, sezione «Customization tracking».
Dopo la migrazione del catalogo (quando esiste `features/.strict`) l'hook `Stop` segnala
che il controllo è spento se `core.hooksPath` non è `.githooks`, e chiede a Claude di
chiedere l'ok al committente prima di attivarlo: è una modifica alla configurazione.
Se un commit mette in stage `lms/locale/it.po` senza `translations-it.toml`, il controllo
ricorda (senza bloccare) di rigenerare il registro con
`python3 scripts/customization_translations.py --write`.

## Regola di manutenzione

**Chi aggiunge una personalizzazione aggiunge la voce nella stessa sessione**, collegata
alla scheda della sua funzionalità (nuova o aggiornata). La guardia
dell'hook `Stop` (`scripts/inventory_guard.py`) lo ricorda a fine turno se trova un
marcatore `OSLMS-CUSTOM` non censito.

Mai cancellare una voce, né modificare un test, per far tornare verde il rilevatore: se la
regola è cambiata si aggiorna prima l'`intent` della voce, e poi il resto discende da lì.
