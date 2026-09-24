# Sistema di configurazioni os_lms — documento di progetto

**Data:** 2026-09-18
**Stato:** progetto approvato, da implementare
**Branch di riferimento:** `feature/oslms`
**Destinatari:** il supervisore del progetto e ogni sessione di sviluppo futura (umana o AI) che debba aggiungere, modificare o rimuovere un parametro.

---

## 1. Obiettivo

Costruire un sistema unico e dichiarativo per i **parametri di configurazione della piattaforma**: valori decisi dall'amministratore che accendono, spengono, mostrano, nascondono o regolano logiche, funzioni ed elementi grafici.

Requisiti espressi dal committente:

1. Tre sezioni nel pannello impostazioni: **Corsi**, **Classi** (già esistenti) e **App** (nuova).
2. Deve reggere **~20 parametri per sezione** (~60 complessivi) senza degradare.
3. Non solo interruttori: qualsiasi tipo di dato (numeri, testi, scelte singole, scelte multiple, strutture).
4. I parametri si dichiarano **sempre lato codice**, mai creati dall'interfaccia.
5. I parametri della sezione App non influenzano il sito; quelli di Corsi e Classi valgono anche per l'app.
6. Documentazione dedicata, da aggiornare a ogni aggiunta o modifica.
7. Le modifiche devono **sopravvivere agli aggiornamenti dell'upstream** (Frappe Learning).
8. Lo sviluppo è affidato ad assistente AI sotto supervisione: la procedura deve essere scritta e ripetibile.

---

## 2. Stato attuale

### 2.1 Come funziona oggi

| Pezzo | Dove | Note |
| --- | --- | --- |
| Definizione UI | `frontend/src/oslms/utils/settings.js` → `buildOslmsSettingsTabs()` | Gruppo "Configurazioni" con voci **Corsi** (`sections: []`, guscio vuoto) e **Classi** (un solo parametro, `enable_live_classes`) |
| Storage | Custom Field sul doctype Single `LMS Settings` | 17 campi os_lms |
| Dichiarazione dei Custom Field | `apps/os_lms/os_lms/fixtures/custom_field.json` **e** `apps/os_lms/os_lms/setup.py` (`CUSTOM_FIELDS`) | **Due meccanismi paralleli**, nessuna fonte di verità unica |
| Lettura lato server (upstream) | `lms/lms/api.py` → `get_lms_settings()` | Whitelist di campi scritta a mano; `enable_live_classes` è stato **aggiunto dentro il file upstream** |
| Lettura lato server (os_lms) | `apps/os_lms/os_lms/os_lms/override_api.py` → `get_lms_settings()` | Sostituisce l'originale via `override_whitelisted_methods` e aggiunge i flag `LMSA Settings` e `Brand Customize` |
| Lettura lato SPA | `settingsStore.settings.data?.<campo>` | 14 punti sparsi, nessuna tipizzazione, nessun controllo sui nomi |
| Superficie App | `apps/os_lms/os_lms/os_lms/app/api.py` → `get_instance_info()` | Bootstrap dell'app mobile: nome, logo, colori |

### 2.2 I tre problemi da risolvere

**Costo per parametro costante e alto.** Aggiungere un parametro richiede oggi quattro modifiche coordinate — fixture, whitelist backend, voce nel pannello, punto di lettura — più una patch di migrazione. A 60 parametri il lavoro si moltiplica per 60.

**Nessuna fonte di verità.** I Custom Field sono dichiarati in due posti (fixture JSON esportata dal database e dizionario Python in `setup.py`) che possono divergere senza che nulla lo segnali. `enable_live_classes` compare inoltre sia nella whitelist upstream di `lms/lms/api.py` sia nell'override os_lms: la riga upstream è ridondante e produce un conflitto a ogni merge.

**Le letture sono innesti invisibili.** Il caso reale portato dal committente — *nascondere alcuni filtri nell'elenco corsi* — richiede di intervenire in `frontend/src/pages/Courses/Courses.vue` (`courseTabs`, righe 374-400), un file dell'upstream che mescola già logica di ruolo. Oggi nulla registra che quell'innesto esiste: se un aggiornamento lo cancella, nessuno se ne accorge finché non lo segnala un utente.

---

## 3. Decisioni prese

| # | Decisione | Motivazione |
| --- | --- | --- |
| D1 | I parametri si dichiarano in **un unico file Python**; tutto il resto (pannello, validazione, payload web, payload app, documentazione, tipi TS) si genera da lì | Fonte di verità unica; costo marginale del nuovo parametro quasi nullo |
| D2 | I valori vivono in uno storage **chiave → valore** (doctype `OS LMS Config Value`), non in colonne dedicate | Aggiungere un parametro non richiede mai una migrazione di schema. È lo stesso pattern che Frappe usa per i doctype Single (`tabSingles`) |
| D3 | **Scope predisposto, non implementato**: il registry prevede gli ambiti `global`, `course` e `batch`, ma nella prima versione si accetta solo `global` | L'override per singolo corso/classe si aggiungerà senza riscrivere i punti di lettura già scritti |
| D4 | Ogni parametro dichiara **su quali superfici** è visibile (`web`, `app`) | La regola "Corsi/Classi influiscono sull'app ma non viceversa" diventa una conseguenza automatica della dichiarazione, non una logica da mantenere |
| D5 | **I parametri dicono cosa togliere, non cosa tenere** (semantica sottrattiva) | Se l'upstream aggiunge un elemento nuovo, questo appare come previsto invece di sparire silenziosamente |
| D6 | **Il valore di default riproduce sempre il comportamento dell'upstream** | Se un innesto viene perso in un merge o un valore manca, il sistema si comporta come la piattaforma non modificata: nessun guasto silenzioso |
| D7 | Il pannello SPA è l'**unica superficie di modifica supportata**; la list view desk serve a ispezionare e, in emergenza, correggere | Evita di dover costruire form tipizzati nel desk per tipi che Frappe non gestisce nativamente |
| D8 | Gli innesti nei file upstream sono **marcati, censiti e verificati da test** | Non si può evitare che siano sparsi: si può renderli contabili |

### 3.1 Approcci scartati

**Estendere l'esistente** (Custom Field su `LMS Settings` + sezioni scritte a mano). Costo per parametro invariato (~1-2 ore), `settings.js` oltre le 2000 righe a regime, fixture ingestibile. È il percorso che il progetto sta già subendo.

**Registry che genera i Custom Field.** Mantiene form nativi nel desk, ma ogni parametro resta una colonna più una patch, e il vantaggio svanisce proprio sui tipi non booleani: Frappe non ha un fieldtype per "elenco di valori da un insieme chiuso", quindi il caso reale (filtri da nascondere) finirebbe comunque serializzato in `Long Text`. Si paga il prezzo senza incassare il beneficio. In più, l'override per corso richiederebbe di replicare tutte le colonne su `LMS Course`.

Il passaggio da D2 a "Custom Field generati" resta comunque possibile in futuro leggendo il registry; il percorso inverso richiederebbe di migrare 60 colonne. A parità di dubbio si sceglie la direzione reversibile.

---

## 4. Architettura

### 4.1 Struttura dei file

```
apps/os_lms/os_lms/os_lms/config/
├── __init__.py       # API pubblica: cfg(), for_surface(), all_values()
├── types.py          # Tipi di parametro e loro validazione/serializzazione
├── registry.py       # Dataclass Parametro, enum Sezione/Superficie/Scope, registro
├── definitions.py    # >>> LE DICHIARAZIONI: il solo file da toccare per un parametro <<<
├── store.py          # Lettura/scrittura valori, risoluzione, cache
├── api.py            # Endpoint whitelisted: get_config_schema, save_config
└── docgen.py         # Generatore di docs/OS_LMS_CONFIGURAZIONI.md

apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/
└── ...               # Doctype dello storage

frontend/src/oslms/config/
├── useOsConfig.js    # cfg(chiave) e helper sottrattivi per la SPA
└── keys.generated.ts # Costanti e tipi generati dal registry (autocompletamento)

frontend/src/oslms/components/Settings/
└── OsConfigSection.vue   # Renderer generico di una sezione del pannello
```

### 4.2 Il registry (D1)

Ogni parametro è una dichiarazione con questi attributi:

| Attributo | Obbligatorio | Descrizione |
| --- | --- | --- |
| `chiave` | sì | Identificatore `sezione.nome`, minuscolo, con underscore. Il prefisso **deve** corrispondere alla sezione |
| `sezione` | sì | `CORSI` / `CLASSI` / `APP` |
| `tipo` | sì | Istanza di un tipo (§4.3) |
| `default` | sì | Valore che riproduce il comportamento upstream (D6) |
| `etichetta` | sì | Testo mostrato nel pannello |
| `descrizione` | no | Testo esplicativo sotto l'etichetta |
| `superfici` | sì | Lista fra `WEB` e `APP` (D4) |
| `scope` | sì | `GLOBAL` (unico valore accettato nella v1) |
| `ruoli` | no | Chi può modificarlo nel pannello; default `["System Manager"]` |
| `innesti` | no | Elenco dei file upstream in cui il parametro è letto (§4.8) |
| `introdotto_il` | sì | Data, per la documentazione generata |

Esempio, il caso reale dei filtri corsi:

```python
Parametro(
    chiave="corsi.filtri_nascosti",
    sezione=Sezione.CORSI,
    tipo=ScelteMultiple(
        opzioni=[
            ("live", "Pubblicato"),
            ("upcoming", "In arrivo"),
            ("created", "Creato"),
            ("unpublished", "Non pubblicato"),
        ]
    ),
    default=[],                       # di serie non si nasconde nulla (D5 + D6)
    etichetta="Filtri da nascondere nell'elenco corsi",
    descrizione="I filtri selezionati non compaiono nella barra dei corsi.",
    superfici=[Superficie.WEB, Superficie.APP],
    scope=Scope.GLOBAL,
    innesti=["frontend/src/pages/Courses/Courses.vue"],
    introdotto_il="2026-09-18",
)
```

Il registro si autopopola all'import di `definitions.py`; l'inserimento di una chiave duplicata o di un prefisso incoerente con la sezione solleva un errore all'avvio.

### 4.3 Tipi supportati

| Tipo | Valore Python | Controllo nel pannello | Note |
| --- | --- | --- | --- |
| `Booleano` | `bool` | interruttore | |
| `Intero(min, max)` | `int` | campo numerico | validazione degli estremi |
| `Decimale(min, max)` | `float` | campo numerico | |
| `Testo(max_len)` | `str` | campo di testo | |
| `TestoLungo` | `str` | area di testo | |
| `SceltaSingola(opzioni)` | `str` | tendina | valore fuori elenco rifiutato |
| `ScelteMultiple(opzioni)` | `list[str]` | elenco di caselle | **nessuna dipendenza nuova**: si disegna come gruppo di caselle, non serve un componente multiselect |
| `Json(schema)` | `dict`/`list` | area di testo con validazione | via d'uscita per casi non previsti |

Ogni tipo espone `valida(valore)`, `normalizza(valore)`, `serializza`, `deserializza` e il nome del controllo da usare nel pannello. Aggiungere un tipo nuovo è l'unico caso in cui serve toccare sia il backend sia il renderer della SPA.

### 4.4 Storage (D2)

Doctype **`OS LMS Config Value`** (normale, non Single):

| Campo | Tipo | Note |
| --- | --- | --- |
| `chiave` | Data | chiave del registry |
| `scope_type` | Select | `Global` / `LMS Course` / `LMS Batch` — nella v1 solo `Global` |
| `scope_name` | Data | vuoto per `Global`, nome del documento negli altri casi |
| `valore` | Long Text | JSON serializzato |
| `lookup_key` | Data, unique | `{scope_type}::{scope_name}::{chiave}`, calcolato in `before_save`; usato come `autoname` |

Esistono righe **solo per i parametri effettivamente modificati**: un parametro mai toccato non occupa spazio e usa il default del registry. Conseguenza utile: azzerare un parametro significa cancellare la riga, e il sistema torna al comportamento upstream.

**Cache.** La risoluzione per scope viene memorizzata in Redis (`frappe.cache()`), invalidata negli hook `on_update` e `on_trash` del doctype, più una cache per richiesta in `frappe.local`. Il costo di lettura a regime è quello di una singola `hget`.

### 4.5 Risoluzione e lettura lato server

```python
from os_lms.os_lms.config import cfg

cfg("corsi.filtri_nascosti")       # -> ["created"]  (già tipizzato)
```

Regole:

- una chiave non dichiarata nel registry solleva **sempre** un errore, non restituisce `None`. Un refuso deve essere rumoroso;
- se non esiste una riga nello storage si applica il default del registry;
- il valore letto dallo storage viene validato contro il tipo: un valore corrotto (modifica manuale dal desk) viene scartato con un log e si ricade sul default (D6).

Predisposizione allo scope (D3): la firma è già `cfg(chiave, scope_type=None, scope_name=None)`; nella v1 qualsiasi valore diverso da `Global` solleva `NotImplementedError`. La catena di risoluzione futura sarà *entità → globale → default*.

### 4.6 Esposizione al sito e all'app (D4)

Nessun file upstream viene toccato, perché entrambe le porte d'ingresso sono già codice os_lms:

| Superficie | Endpoint | Intervento |
| --- | --- | --- |
| Sito (SPA) | `lms.lms.api.get_lms_settings`, già sostituito da `override_api.get_lms_settings` | aggiunge `result["config"] = for_surface(WEB)` |
| App mobile | `os_lms.os_lms.app.api.get_instance_info` (codice nostro) | aggiunge `"config": for_surface(APP)` |

`for_surface(WEB)` restituisce i parametri con `WEB` fra le superfici; `for_surface(APP)` quelli con `APP`. Poiché i parametri di Corsi e Classi si dichiarano `[WEB, APP]` e quelli della sezione App si dichiarano `[APP]`, la direzione unica richiesta è garantita dalla dichiarazione stessa: non esiste codice che possa sbagliarla.

Lo store SPA carica già `get_lms_settings` all'avvio (`frontend/src/stores/settings.js`), quindi non si aggiunge nessuna chiamata di rete.

### 4.7 Lettura nella SPA

```js
import { cfg, nascondi } from '@/oslms/config/useOsConfig'
```

Caso "nascondi una sola scritta":

```vue
<span v-if="cfg('corsi.mostra_durata')">{{ durata }}</span>
```

Caso "nascondi alcune voci di un elenco costruito dall'upstream", senza riscrivere l'elenco:

```js
// os-config: corsi.filtri_nascosti
tabs = nascondi('corsi.filtri_nascosti', tabs)
```

`nascondi(chiave, lista, campo = 'value')` rimuove dalla lista le voci il cui campo compare fra i valori del parametro. È sottrattivo per costruzione (D5): non può aggiungere né riordinare.

Se una chiave non è presente nel payload, in sviluppo viene emesso un avviso in console e si restituisce `undefined`; il codice chiamante non deve mai dipendere da un valore assente perché il server applica sempre i default.

### 4.8 Innesti nei file upstream (D8)

Un innesto è una riga che legge un parametro **dentro un file dell'upstream**. È l'unico punto del sistema che gli aggiornamenti possono cancellare. Tre difese, in ordine:

**Primo: evitarlo.** Prima di scrivere in un file upstream si verifica se l'elemento da governare vive già in un componente os_lms. Se sì, non c'è nessun innesto.

**Secondo: marcarlo.** Ogni innesto porta immediatamente sopra il commento `// os-config: <chiave>` (o `# os-config: <chiave>` in Python). Il marcatore è cercabile con un solo `grep`.

**Terzo: verificarlo con un test.** Il parametro dichiara nel registry i file in cui è innestato (`innesti=[...]`). Un test automatico itera il registry e verifica che in ciascuno di quei file esista il marcatore con quella chiave. Se un merge dall'upstream riscrive il file e perde la riga, **il test diventa rosso**, prima che il problema arrivi in produzione.

Per i parametri il cui comportamento merita una verifica funzionale si aggiunge in più un test di comportamento (esempio: "con `corsi.filtri_nascosti = ['created']`, la barra dei filtri non contiene 'Creato'"). Il progetto ha già l'attrezzatura: 31 test frontend con Vitest e i test Python di Frappe.

### 4.9 Il pannello

Il pannello smette di essere scritto a mano. Le voci **Corsi**, **Classi** e **App** in `buildOslmsSettingsTabs()` usano tutte lo stesso componente `OsConfigSection.vue`, che riceve solo il nome della sezione, chiede al server lo schema (`get_config_schema`), disegna i controlli in base al tipo e salva con `save_config`.

**Aggiungere un parametro non comporta quindi nessuna modifica al frontend.**

Il salvataggio passa da un endpoint dedicato che valida ogni valore contro il registry, rifiuta le chiavi sconosciute, verifica i ruoli dichiarati sul parametro e invalida la cache. Non si usa più il salvataggio dell'intero documento `LMS Settings`.

`buildOslmsSettingsTabs()` vive già in `frontend/src/oslms/`: la modifica al pannello non tocca file upstream.

### 4.10 Documentazione (requisito 6)

Due file con ruoli distinti:

**`docs/OS_LMS_CONFIGURAZIONI.md` — generato.** Prodotto da `docgen.py` a partire dal registry: una tabella per sezione con chiave, tipo, opzioni, default, superfici, descrizione, file innestati e data di introduzione. Non si scrive a mano, quindi non può disallinearsi. Un test lo rigenera e fallisce se il file in repository è diverso.

**`docs/OS_LMS_CONFIGURAZIONI-RICETTA.md` — scritto a mano.** La procedura per aggiungere un parametro: dove dichiararlo, come scegliere il tipo, la regola del default (D6), la regola sottrattiva (D5), come scrivere l'innesto e marcarlo, quale test aggiungere, come rigenerare la documentazione, come verificare il risultato.

**Rimando in `CLAUDE.md`** alla ricetta, perché sia la prima cosa che una sessione futura trova quando viene chiesto un parametro nuovo. Dato che lo sviluppo è affidato ad assistente AI (requisito 8), la ricetta non è documentazione accessoria: è l'interfaccia operativa del sistema.

---

## 5. Cosa serve per aggiungere un parametro, a regime

1. Aggiungere la dichiarazione in `definitions.py`.
2. Scrivere il punto di lettura (una riga). Se cade in un file upstream, marcarlo e aggiungerlo a `innesti`.
3. Aggiungere il test dell'innesto se pertinente.
4. Rigenerare la documentazione.

Nessuna migrazione, nessuna fixture, nessuna modifica al pannello, nessun endpoint nuovo.

---

## 6. Stima

Lo sviluppo è affidato ad assistente AI sotto supervisione. La stima è quindi espressa in **sessioni di lavoro**, con indicato dove serve una revisione del supervisore.

| # | Fase | Contenuto | Sessioni | Revisione |
| --- | --- | --- | --- | --- |
| 1 | Fondamenta backend | registry, tipi, doctype `OS LMS Config Value`, store, cache, `cfg()`, test unitari | 1 lunga | ✅ checkpoint |
| 2 | Esposizione | iniezione in `get_lms_settings` e `get_instance_info`, `get_config_schema`, `save_config` con validazione e ruoli | 0,5 | |
| 3 | Pannello generico | `OsConfigSection.vue`, controlli per tutti i tipi, `useOsConfig`, aggancio delle tre sezioni | 1 | ✅ checkpoint |
| 4 | Tenuta upstream | convenzione marcatori, test di presenza degli innesti, comando di elenco | 0,5 | |
| 5 | Documentazione | generatore, documento generato, ricetta, rimando in `CLAUDE.md` | 0,5 | ✅ checkpoint |
| 6 | Primo parametro reale | `corsi.filtri_nascosti` end-to-end, innesto marcato in `Courses.vue`, test di comportamento | 0,5 | ✅ verifica funzionale |
| 7 | Altri 4-5 parametri | dichiarazione + innesto + test ciascuno | 0,5 | |
| 8 | Verifica finale | build, test completi, prova manuale su tutte e tre le sezioni, correzioni | 0,5 | ✅ collaudo |

**Totale: ~5 sessioni di lavoro**, equivalenti a circa **2,5-3 giornate effettive**, distribuite su 4-6 interazioni con 5 punti di revisione.

**Costo a regime del parametro successivo: 15-45 minuti**, a seconda che serva solo la dichiarazione o anche un innesto con test.

### 6.1 Rischi e margini

| Rischio | Probabilità | Impatto | Mitigazione |
| --- | --- | --- | --- |
| Il renderer generico non copre bene un tipo (scelte multiple) | media | basso | Le scelte multiple si disegnano come gruppo di caselle: nessun componente nuovo, nessuna dipendenza |
| L'innesto in `Courses.vue` interferisce con la logica di ruolo esistente | media | medio | L'innesto è sottrattivo e applicato **dopo** la costruzione dei tab: non può alterare le regole di ruolo, solo togliere voci |
| Traduzione delle etichette dichiarate in Python | media | basso | Etichette in italiano nel registry; se servirà il multilingua si passa a `_()` lato server, che in contesto di richiesta funziona correttamente |
| Un parametro futuro richiede lo scope per singolo corso prima del previsto | bassa | medio | Firma e storage già predisposti (D3): si implementa la catena di risoluzione senza toccare i punti di lettura |

### 6.2 Attività correlate, stimate a parte

**Migrazione di `enable_live_classes` nel nuovo sistema** — 0,5 sessioni. Elimina la riga innestata in `lms/lms/api.py` (oggi ridondante e causa di conflitto a ogni merge) e verifica il sistema su un parametro reale già in produzione. Da fare dopo il collaudo, non durante.

**Riconciliazione dei due meccanismi di Custom Field** (`fixtures/custom_field.json` contro `setup.py`) — 0,5 sessioni. Non è richiesto da questa feature, ma è debito adiacente che la tocca. Da valutare separatamente.

---

## 7. Fuori ambito

- Implementazione effettiva dell'override per singolo corso o classe (solo predisposto, D3).
- Migrazione degli altri 16 Custom Field esistenti su `LMS Settings`.
- Form tipizzati nel desk Frappe (D7: la list view basta per ispezione ed emergenze).
- Versionamento o storico delle modifiche ai parametri.
- Parametri per singolo utente o per ruolo.

---

## 8. Criteri di accettazione

1. Aggiungere un parametro nuovo richiede la modifica di **un solo file** (più l'eventuale innesto e il suo test).
2. Le tre sezioni Corsi, Classi e App compaiono nel pannello e salvano correttamente.
3. Un parametro dichiarato `[APP]` **non compare** nel payload del sito; un parametro `[WEB, APP]` compare in entrambi.
4. Il parametro `corsi.filtri_nascosti` nasconde effettivamente i filtri selezionati, senza alterare le regole di visibilità per ruolo esistenti.
5. Con lo storage vuoto la piattaforma si comporta esattamente come oggi (D6).
6. Una chiave non dichiarata solleva un errore, sia in lettura sia in salvataggio.
7. `docs/OS_LMS_CONFIGURAZIONI.md` è generato e un test ne verifica l'allineamento con il registry.
8. Un test fallisce se un innesto dichiarato non è più presente nel file indicato.
