# Catalogo delle funzionalita

Una scheda TOML per funzionalita, nel file `<id>.toml` di questa cartella. File separati
evitano i conflitti fra branch paralleli. Le voci di `../spa-grafts.toml` si collegano alla
scheda con il campo `feature = "<id>"`: le ancore restano l'allarme veloce sulle righe
critiche, la scheda porta il significato.

| Campo | Obbl. | Contenuto |
| --- | --- | --- |
| `id` | si | kebab-case, uguale al nome del file, unico |
| `title` | si | titolo in italiano, come lo direbbe un utente |
| `status` | si | `active`, `retired` (rimossa da noi), `replaced-by-upstream` (sostituita, con riferimento alla release e alla decisione) |
| `summary` | si | cosa fa, per chi, in 2-5 frasi di linguaggio non tecnico |
| `why` | si | perche esiste: esigenza del cliente o lacuna upstream che colma |
| `roles` | no | ruoli coinvolti (`Gestore`, `Docente`, `Valutatore`, `Student`, ...) |
| `behaviour` | si | elenco di regole osservabili, una per riga, verificabili da fuori ("una classe live nuova nasce in bozza"). E la base del confronto con l'upstream |
| `areas` | si | percorsi o glob del codice che le appartiene per intero (moduli os_lms, componenti nostri) |
| `upstream_watch` | si | indizi da cercare nelle release upstream: parole chiave, doctype, campi, endpoint, nomi di pagina |
| `data` | no | dati che la funzionalita possiede (custom field, doctype, impostazioni): servono a stimare la migrazione se si adotta l'upstream |
| `tests` | no | test che ne verificano il comportamento |
| `notes` | no | conoscenza operativa: insidie, cosa riverificare dopo i merge |
| `history` | si | eventi (array di tabelle): creazione, cambi di comportamento rilevanti, decisioni di confronto con l'upstream (data, commit o release, sintesi) |

Il caricamento (`scripts/customizations/features.py`) valida: campi obbligatori, `id` uguale
al nome del file, stato ammesso. Il controllo C8 verifica che ogni voce punti a una scheda
esistente; e un avviso finche non esiste il file `.strict` in questa cartella, un errore dopo.

Esempio minimo:

```toml
id = "live-class-draft-publish"
title = "Classi live in bozza"
status = "active"
summary = "Una classe live nasce in bozza e si pubblica a parte."
why = "Il cliente vuole preparare le classi prima di invitare i partecipanti."
roles = ["Gestore"]
behaviour = ["una classe live nuova nasce in bozza", "gli inviti partono solo alla pubblicazione"]
areas = ["apps/os_lms/os_lms/os_lms/live_class_*.py"]
upstream_watch = ["live class", "draft", "publish"]
history = [
	{ date = "2026-11-01", ref = "abc1234", summary = "creazione" },
]
```
