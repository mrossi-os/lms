# Inventario delle personalizzazioni

Questa cartella è la **fonte di verità unica** di tutte le personalizzazioni che questo
fork applica sopra Frappe Learning (upstream `frappe/lms`). Ogni voce dice **dove** vive
una personalizzazione, **perché** esiste e **come** si verifica. Dopo ogni merge
dell'upstream il rilevatore di scostamento confronta l'albero con l'inventario e dice in
meno di un secondo quali innesti sono stati ripuliti.

Motivazioni e disegno complessivo: [spec](../superpowers/specs/2026-09-18-upstream-regression-harness-design.md).
Piano della Fase 0: [piano](../superpowers/plans/2026-09-18-upstream-regression-harness-fase-0.md).

## Comandi

Dalla root del repository, senza Docker né bench:

```bash
python3 scripts/check_customizations.py              # rapporto leggibile
python3 scripts/check_customizations.py --json       # per la skill /upstream-check
python3 scripts/check_customizations.py --list-files # file censiti, uno per riga
python3 -m unittest discover -s scripts/tests -t . -v  # test del rilevatore
```

Codici di uscita: `0` intatto (avvisi ammessi), `1` scostamento, `2` inventario malformato.

| Controllo | Significato | Gravità |
| --- | --- | --- |
| `C1` | l'ancora non compare più nel file | errore |
| `C2` | il file non esiste più | errore |
| `C3` | un file porta il marcatore `OSLMS-CUSTOM` ma nessuna voce lo censisce | errore |
| `C4` | la voce non ha test collegati, o il test dichiarato non esiste | avviso |

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
| `status` | no | `accepted-drift` esclude la voce da C1, C2 e C4 |

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

## Regola di manutenzione

**Chi aggiunge una personalizzazione aggiunge la voce nella stessa sessione.** La guardia
dell'hook `Stop` (`scripts/inventory_guard.py`) lo ricorda a fine turno se trova un
marcatore `OSLMS-CUSTOM` non censito.

Mai cancellare una voce, né modificare un test, per far tornare verde il rilevatore: se la
regola è cambiata si aggiorna prima l'`intent` della voce, e poi il resto discende da lì.
