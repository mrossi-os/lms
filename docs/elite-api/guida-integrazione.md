# Elite API — guida di integrazione

**Versione API:** v1 · **Ultimo aggiornamento:** 30/09/2026

L'Elite API permette a un sistema esterno di leggere da Elite l'elenco dei corsi e delle classi e, per il corso o la classe scelti, gli studenti iscritti con nome, cognome, codice fiscale, email e avanzamento.

L'API è **in sola lettura**: nessuna chiamata modifica dati su Elite.

---

## 1. Accesso

### La chiave

Ogni chiamata deve portare una **chiave API** nell'header `X-Elite-Api-Key`. Una chiave ha questa forma:

```
elite_k7Qm2xPaB9cD_4fJ8sLw0qTzR1vXyN3mE6hG5aKdUo2pYiC7bVnS9tWe
      └── prefisso ─┘ └──────────────── segreto ────────────────┘
```

- La chiave la crea un amministratore o un gestore di Elite, da **Impostazioni → Elite API**, e ve la consegna **su un canale sicuro**.
- La chiave completa viene mostrata **una sola volta**, al momento della creazione, e non si può recuperare: se la perdete, ne serve una nuova.
- Una chiave può avere una **data di scadenza**, ed è valida per tutto quel giorno. Una chiave scaduta o **revocata** non si riattiva: se ne crea un'altra.
- Si possono avere **più chiavi attive** insieme, per esempio una per il collaudo e una per la produzione. Per sostituire una chiave senza interruzioni: fatevene creare una nuova, configuratela, e solo dopo chiedete di revocare la vecchia.

Trattate la chiave come una password: tenetela in un gestore di segreti, non scrivetela nei log e non mettetela negli URL.

### Come si chiama

| Cosa | Valore |
|---|---|
| Indirizzo | `https://<dominio-di-elite>/api/method/os_lms.os_lms.elite_api.v1.<endpoint>` |
| Metodo HTTP | solo **GET** (con qualunque altro metodo la risposta è 403) |
| Header obbligatorio | `X-Elite-Api-Key: <chiave>` |
| Da **non** inviare | l'header `Authorization`, cookie di sessione, il parametro `cmd`: la chiamata viene rifiutata con 400 `invalid_request` |
| Parametri | nella query string, ad esempio `?course=sicurezza-sul-lavoro&page=2` |
| Protocollo | solo HTTPS |

La risposta è in JSON, con il contenuto sotto la chiave `message`:

```json
{ "message": { … } }
```

---

## 2. Il flusso tipico

```
1. ping                       → verificare che la chiave funzioni
2a. list_courses              → scegliere un corso        ┐ uno dei due
2b. list_batches              → scegliere una classe      ┘
3a. get_course_students       → studenti del corso scelto
3b. get_batch_students        → studenti della classe scelta
```

Gli elenchi dei passi 2 servono solo a scegliere **da dove** prendere gli studenti: da un singolo corso oppure da un'intera classe.

### Paginazione

Tutti gli elenchi sono paginati con gli stessi parametri:

| Parametro | Predefinito | Valori ammessi |
|---|---|---|
| `page` | `1` | intero da 1 a 100.000 |
| `page_length` | `100` | intero da 1 a 500 |

Ogni risposta paginata contiene `total` (quanti elementi ci sono in tutto), `page`, `page_length` e `data` (gli elementi della pagina). Per scaricare tutto, aumentate `page` finché `page × page_length ≥ total`. Una pagina oltre la fine restituisce `data: []`.

### Date

Le date sono in formato `AAAA-MM-GG` e i momenti in formato `AAAA-MM-GGThh:mm:ss`, **in ora italiana (Europe/Rome), senza indicazione del fuso**. Esempio: `2026-03-02T09:00:00`.

---

## 3. Endpoint

### 3.1 `ping` — verifica della chiave

```bash
curl -H "X-Elite-Api-Key: $ELITE_API_KEY" \
  "https://<dominio-di-elite>/api/method/os_lms.os_lms.elite_api.v1.ping"
```

```json
{
  "message": {
    "status": "ok",
    "api_version": "v1",
    "key_name": "TrueSkill produzione"
  }
}
```

`key_name` è il nome dato alla chiave quando è stata creata: utile per capire quale chiave state usando.

### 3.2 `list_courses` — elenco dei corsi

Restituisce **tutti** i corsi, pubblicati e non, in ordine di titolo, ciascuno con il riepilogo dei suoi studenti.

| Parametro | Obbligatorio | Descrizione |
|---|---|---|
| `search` | no | testo cercato nel **titolo** del corso, non nell'`id`. I caratteri `%` e `_` sono trattati come testo normale |
| `page`, `page_length` | no | vedi Paginazione |

```bash
curl -H "X-Elite-Api-Key: $ELITE_API_KEY" \
  "https://<dominio-di-elite>/api/method/os_lms.os_lms.elite_api.v1.list_courses?search=sicurezza&page_length=50"
```

```json
{
  "message": {
    "total": 1,
    "page": 1,
    "page_length": 50,
    "data": [
      {
        "id": "sicurezza-sul-lavoro",
        "title": "Sicurezza sul lavoro",
        "published": true,
        "trueskills_certificate_enabled": true,
        "students": {
          "total": 118,
          "completed": 74,
          "in_progress": 30,
          "not_started": 14
        }
      }
    ]
  }
}
```

| Campo | Significato |
|---|---|
| `id` | identificativo del corso, da passare a `get_course_students` |
| `published` | se il corso è pubblicato su Elite |
| `trueskills_certificate_enabled` | se per quel corso **Elite emette già** il badge TrueSkill al completamento. Tenetene conto per non emettere due volte |
| `students` | riepilogo degli studenti: vedi § 4 |

### 3.3 `list_batches` — elenco delle classi

Restituisce tutte le classi, dalla data di inizio più recente, con i corsi di ciascuna e il riepilogo degli studenti.

Parametri: gli stessi di `list_courses` (`search` cerca nel titolo della classe).

```bash
curl -H "X-Elite-Api-Key: $ELITE_API_KEY" \
  "https://<dominio-di-elite>/api/method/os_lms.os_lms.elite_api.v1.list_batches"
```

```json
{
  "message": {
    "total": 1,
    "page": 1,
    "page_length": 100,
    "data": [
      {
        "id": "classe-ottobre-2026",
        "title": "Classe Ottobre 2026",
        "start_date": "2026-10-01",
        "end_date": "2026-12-15",
        "published": true,
        "courses": [
          { "id": "sicurezza-sul-lavoro", "title": "Sicurezza sul lavoro" },
          { "id": "primo-soccorso", "title": "Primo soccorso" }
        ],
        "students": {
          "total": 25,
          "completed_all": 9,
          "partial": 12,
          "not_started": 4
        }
      }
    ]
  }
}
```

`courses` è nell'ordine in cui i corsi compaiono nella classe. `students` è spiegato al § 4.

### 3.4 `get_course_students` — studenti di un corso

| Parametro | Obbligatorio | Descrizione |
|---|---|---|
| `course` | **sì** | `id` del corso (da `list_courses`) |
| `status` | no | solo gli studenti in questo stato: `completed`, `in_progress`, `not_started` |
| `page`, `page_length` | no | vedi Paginazione |

```bash
curl -H "X-Elite-Api-Key: $ELITE_API_KEY" \
  "https://<dominio-di-elite>/api/method/os_lms.os_lms.elite_api.v1.get_course_students?course=sicurezza-sul-lavoro&status=completed"
```

```json
{
  "message": {
    "course": { "id": "sicurezza-sul-lavoro", "title": "Sicurezza sul lavoro" },
    "summary": { "total": 118, "completed": 74, "in_progress": 30, "not_started": 14 },
    "total": 74,
    "page": 1,
    "page_length": 100,
    "data": [
      {
        "first_name": "Anna",
        "last_name": "Bianchi",
        "fiscal_code": "BNCNNA80A41H501X",
        "email": "anna.bianchi@example.com",
        "enrolled_on": "2026-03-02T09:00:00",
        "progress": 100.0,
        "status": "completed"
      }
    ]
  }
}
```

- `summary` riguarda **sempre l'intero corso**, qualunque filtro usiate; `total` conta solo gli studenti che rispettano `status`, ed è il numero da usare per la paginazione.
- `progress` è la percentuale di completamento (da 0 a 100, due decimali).
- `enrolled_on` è la data di iscrizione al corso.

### 3.5 `get_batch_students` — studenti di una classe

| Parametro | Obbligatorio | Descrizione |
|---|---|---|
| `batch` | **sì** | `id` della classe (da `list_batches`) |
| `status` | no | `completed_all`, `partial`, `not_started` |
| `page`, `page_length` | no | vedi Paginazione |

```bash
curl -H "X-Elite-Api-Key: $ELITE_API_KEY" \
  "https://<dominio-di-elite>/api/method/os_lms.os_lms.elite_api.v1.get_batch_students?batch=classe-ottobre-2026"
```

```json
{
  "message": {
    "batch": {
      "id": "classe-ottobre-2026",
      "title": "Classe Ottobre 2026",
      "courses": [
        { "id": "sicurezza-sul-lavoro", "title": "Sicurezza sul lavoro" },
        { "id": "primo-soccorso", "title": "Primo soccorso" }
      ]
    },
    "summary": { "total": 25, "completed_all": 9, "partial": 12, "not_started": 4 },
    "total": 25,
    "page": 1,
    "page_length": 100,
    "data": [
      {
        "first_name": "Carlo",
        "last_name": "Rossi",
        "fiscal_code": null,
        "email": "carlo.rossi@example.com",
        "enrolled_on": "2026-01-06T10:00:00",
        "courses_completed": 1,
        "courses_total": 2,
        "status": "partial",
        "courses": [
          { "id": "sicurezza-sul-lavoro", "progress": 100.0, "status": "completed" },
          { "id": "primo-soccorso", "progress": 0.0, "status": "not_started" }
        ]
      }
    ]
  }
}
```

- `enrolled_on` è la data di iscrizione **alla classe**.
- `courses` riporta lo stato dello studente in ogni corso della classe, nello stesso ordine di `batch.courses`.

---

## 4. Come si calcola l'avanzamento

**Corso**

| Stato | Condizione |
|---|---|
| `completed` | avanzamento = 100 |
| `in_progress` | avanzamento tra 0 e 100, estremi esclusi |
| `not_started` | avanzamento = 0 |

**Classe**, calcolata **solo sui corsi della classe**. Quiz ed elaborati assegnati alla classe non contano, quindi i numeri possono differire dalla percentuale mostrata nella dashboard della classe su Elite.

| Stato | Condizione |
|---|---|
| `completed_all` | tutti i corsi della classe completati |
| `partial` | almeno un corso iniziato, ma non tutti completati |
| `not_started` | nessun corso iniziato (anche quando la classe non ha corsi) |

Un corso della classe che lo studente non ha **mai aperto** conta come avanzamento 0.

---

## 5. I dati degli studenti

- **Chi compare:** solo gli iscritti come **studenti**, con un account **attivo**. Tutor e staff non compaiono, e nemmeno gli account disattivati o cancellati. Ogni studente compare una sola volta per corso.
- **Ordine:** per cognome, poi nome, poi email.
- **`fiscal_code`:** in maiuscolo e senza spazi, oppure `null` se lo studente non l'ha inserito. Elite **non ne controlla il formato**: i controlli spettano a voi.
- **`first_name` / `last_name`:** restituiti come sono salvati su Elite. Il cognome può essere vuoto (`""`); in alcuni casi nome e cognome sono stati scritti entrambi nel campo nome. Elite non prova a dividerli.
- **`email`:** l'indirizzo con cui lo studente accede a Elite.

---

## 6. Errori

Negli errori generati dall'Elite API il corpo contiene sempre il campo **`error`**, un codice stabile da usare nel vostro codice. Negli errori sui parametri c'è anche **`parameter`**, il nome del parametro. Gli altri campi eventualmente presenti (`exc_type`, …) sono tecnici e possono cambiare: non basatevi su quelli.

| HTTP | `error` | Causa | Cosa fare |
|---|---|---|---|
| 400 | `invalid_parameter` | parametro obbligatorio mancante, oppure valore non valido (`page`, `page_length`, `status`); `parameter` dice quale | correggere la richiesta |
| 400 | `invalid_request` | la chiamata porta anche l'header `Authorization`, un cookie di sessione o il parametro `cmd` | inviare solo `X-Elite-Api-Key` e i parametri documentati |
| 401 | `invalid_api_key` | chiave errata, revocata o scaduta: la risposta è la stessa per tutti e tre i casi | verificare la chiave; se è stata revocata o è scaduta, farsene creare una nuova |
| 403 | — (manca `error`) | header `X-Elite-Api-Key` assente, oppure metodo diverso da GET | aggiungere l'header / usare GET |
| 404 | `not_found` | il corso o la classe indicati non esistono; `parameter` dice quale | ricaricare l'elenco da `list_courses` / `list_batches` |
| 429 | `too_many_failed_attempts` | oltre 20 tentativi con chiave non valida dallo stesso indirizzo IP in 10 minuti. Riguarda **solo le chiavi non valide**: una chiave corretta non viene mai bloccata | correggere la chiave |
| 5xx | — | errore interno di Elite | riprovare più tardi con attese crescenti; le chiamate sono in sola lettura, quindi ripeterle non ha effetti collaterali |

Esempio di errore:

```json
{ "error": "invalid_parameter", "parameter": "page_length", "exc_type": "EliteAPIBadRequest" }
```

---

## 7. Buone pratiche

- Scaricate gli studenti **quando vi servono** (ad esempio al momento dell'emissione dei certificati), non a intervalli fissi: i dati cambiano con l'avanzamento degli studenti.
- Non c'è un limite al numero di chiamate per chiave. Usate comunque pagine grandi (fino a 500) invece di molte chiamate piccole.
- Ogni chiamata viene registrata su Elite (chiave usata, endpoint, parametri, numero di righe restituite, indirizzo IP). I dati degli studenti **non** vengono registrati.
- Per i corsi con `trueskills_certificate_enabled: true`, Elite emette già il badge TrueSkill quando lo studente completa il corso. Coordinatevi con Elite per non emetterlo due volte.

---

## 8. Riferimento rapido

| Endpoint | Parametri | Restituisce |
|---|---|---|
| `v1.ping` | — | stato e nome della chiave |
| `v1.list_courses` | `search`, `page`, `page_length` | corsi con riepilogo studenti |
| `v1.list_batches` | `search`, `page`, `page_length` | classi con corsi e riepilogo studenti |
| `v1.get_course_students` | **`course`**, `status`, `page`, `page_length` | studenti del corso con avanzamento |
| `v1.get_batch_students` | **`batch`**, `status`, `page`, `page_length` | studenti della classe con avanzamento per corso |

Prefisso di tutti gli endpoint: `/api/method/os_lms.os_lms.elite_api.`
