# Storico delle chat del Tutor AI, visibile allo studente — fattibilità e stima

**Data:** 18 settembre 2026 · **Stato:** analisi conclusa — opzione B approvata · **Branch:** `feature/oslms`

> **Seguito di questo documento.** L'opzione B è stata approvata il 18/09/2026 e tradotta in:
> [specifica di progetto](../superpowers/specs/2026-09-18-tutor-chat-history-design.md) →
> [piano di implementazione](../superpowers/plans/2026-09-18-tutor-chat-history.md).
> Le sette domande del §8 sono state chiuse: le risposte sono nel registro delle decisioni
> della specifica (§2). Questo documento resta la fotografia dell'analisi che ha portato
> alla scelta, non va aggiornato.

**Richiesta di partenza.** Verificare fattibilità, tempistiche e modalità per introdurre
uno storico delle chat del tutor AI visibile agli studenti. Indicazione di Carlo: prendere
spunto dai *progetti* di NotebookLM — creare dei "progetti", cioè i corsi, e dentro
ciascuno tutto lo storico della chat del tutor AI relativo esclusivamente a quel corso.

---

## 1. Risposta in breve

**Fattibile, senza ostacoli tecnici.** Non richiede né un cambio di architettura, né una
libreria nuova, né un intervento sul motore AI: è lavoro di persistenza, permessi e
interfaccia, tutto su schemi già presenti nel progetto.

Due fatti misurati sul codice rendono la stima contenuta e affidabile:

1. **Le conversazioni sono già scritte a database.** Ogni domanda e ogni risposta del
   tutor finiscono su `LMSA Query Log` (corso, lezione, studente, domanda, risposta,
   contesto, esito). Non serve costruire la persistenza: serve raggrupparla in
   conversazioni e mostrarla.
2. **Lo stesso identico problema è già risolto altrove nel prodotto.** Le simulazioni AI
   hanno sessioni persistite, turni ordinati, permessi per studente e un'interfaccia che
   elenca le sessioni passate e ne rilegge la trascrizione. Quel modello si replica sul
   tutor: è un progetto da clonare, non da inventare.

**Stima:** da **24–32 ore** per la versione minima (la chat non si perde più) a
**72–92 ore** per il "progetto corso" completo nello spirito di NotebookLM.
Raccomandazione: consegna in due fasi, la prima utile e visibile dopo circa 4 giorni.

---

## 2. Che cosa esiste oggi — rilevato sul codice

### 2.1 Il tutor salva già tutto

`TutorAi.ask` scrive un record per ogni scambio, dentro un blocco `finally`, quindi anche
quando la chiamata al modello fallisce
([tutor_ai.py](../../apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py) → `_log_query`).
Il doctype `LMSA Query Log` contiene:

| Campo | Contenuto |
| --- | --- |
| `course` | corso (obbligatorio) |
| `lesson` | lezione, opzionale: le domande a livello corso hanno il campo vuoto |
| `member` | studente |
| `question` / `answer` | testo della domanda e della risposta |
| `context` | il system prompt completo usato per quella risposta |
| `status` | `Answered` / `Failed` |

Quindi lo storico, come materia prima, **c'è già**. Manca tutto il resto.

### 2.2 Che cosa manca

- **Nessun concetto di conversazione.** Le righe sono eventi isolati: non esiste un
  identificativo che dica "queste dodici domande sono la stessa chat di martedì". L'unico
  ordinamento possibile oggi è per data di creazione.
- **Nessun titolo, nessuna gestione.** Non si può rinominare, archiviare o cancellare una
  conversazione, perché la conversazione come oggetto non esiste.
- **Nessuna interfaccia per lo studente.** `LMSA Query Log` è visibile solo dal Desk
  (back-office) ai ruoli System Manager, Moderator e Course Creator. Lo studente non ha
  alcun modo di rileggere le proprie chat.
- **Il frontend tiene la conversazione solo in memoria.** Lo store
  [stores/aiChat.js](../../frontend/src/stores/aiChat.js) è un array Pinia: si svuota al
  cambio di corso e **si perde a ogni ricaricamento della pagina**. Il pulsante cestino in
  [AiChatButton.vue](../../frontend/src/oslms/components/ai/AiChatButton.vue) svuota quella
  memoria, non cancella nulla a database. È esattamente il comportamento che lo studente
  percepisce come "la chat è sparita".

### 2.3 Il modello già esistente da riusare: le simulazioni

| Elemento | Simulazioni (esiste) | Tutor (da fare) |
| --- | --- | --- |
| Contenitore della sessione | `LMSA Simulation Session` (studente, corso, stato, inizio, fine, n° turni) | `LMSA Tutor Conversation` |
| Turni ordinati | `LMSA Simulation Turn` (`turn_index`, `role`, `text_content`, modello usato, latenza, token) | `LMSA Tutor Message` |
| Permessi per studente | `permission_query_conditions` + `has_permission` registrati in `hooks.py` per tutti e quattro i doctype | stessi hook, stesso schema |
| Elenco delle sessioni dell'utente | `list_my_sessions(course, scenario)`, filtrato su `frappe.session.user` | `list_my_conversations(course)` |
| Interfaccia di lettura | [SimulationLauncher.vue](../../frontend/src/oslms/components/simulations/SimulationLauncher.vue) (elenco) + [TranscriptDrawer.vue](../../frontend/src/oslms/components/simulations/TranscriptDrawer.vue) (trascrizione) | pannello storico + pagina corso |

Questa colonna di sinistra è codice scritto, testato e in produzione. È la ragione
principale per cui questo intervento ha rischio tecnico basso.

---

## 3. Il modello "progetti" di NotebookLM tradotto su OS LMS

In NotebookLM un *notebook* (o progetto) è un contenitore con tre cose dentro: **le fonti**,
**le conversazioni** e **le note salvate**. La richiesta di Carlo riguarda esplicitamente la
seconda. Vale però la pena sapere dove sta il prodotto rispetto alle altre due, perché
determina quanto la cosa somiglierà davvero a NotebookLM.

| Elemento NotebookLM | Corrispondenza su OS LMS | Stato |
| --- | --- | --- |
| Il progetto | Il corso | Già esiste: il tutor è **già** vincolato a un corso, sia nel prompt sia nei permessi |
| Le fonti | Lezioni indicizzate + allegati dei badge | Già esistono come dati (pipeline di ingestion), **non sono mostrate** allo studente |
| Le conversazioni | Chat del tutor | Dati salvati, **struttura e interfaccia da costruire** ← è la richiesta |
| Le citazioni alla fonte | Il tutor già etichetta ogni brano con la lezione di origine (`_label_chunks`), ma l'etichetta resta interna e non arriva al client: nella UI il campo `sources` è **sempre vuoto** | Da esporre, costo contenuto |
| Le note salvate | Esiste un sistema di note dello studente sulle lezioni, **scollegato** dal tutor | Non previsto, fuori richiesta |

Il punto da mettere sul tavolo: **il tratto più riconoscibile di NotebookLM sono le
citazioni cliccabili alla fonte**, non l'archivio delle chat. Se l'aspettativa del cliente
è "come NotebookLM", conviene chiarire subito se le citazioni fanno parte della richiesta:
tecnicamente sono a portata di mano (il dato di provenienza è già calcolato e poi
scartato), ma sono lavoro aggiuntivo rispetto al solo storico.

---

## 4. Tre livelli di intervento

### Opzione A — Lo storico minimo: la chat non si perde più

Una sola conversazione continua per coppia (studente, corso), salvata e ripresa
automaticamente. Riaprendo il pannello, anche dopo giorni e da un altro dispositivo, lo
studente ritrova la sua conversazione sul corso. Nessun elenco, nessuna pagina nuova.

- Risolve il fastidio concreto di oggi (la chat sparisce al refresh) con l'intervento più
  piccolo possibile.
- **Non** realizza il modello "progetti": non ci sono conversazioni distinte da sfogliare.
- **24–32 ore** → 3–4 giorni uomo.

### Opzione B — Il "progetto corso" *(consigliata)*

Più conversazioni distinte per corso, con titolo automatico, rinomina e cancellazione, e
una pagina dedicata per corso che le elenca e ne permette la rilettura e la ripresa. È la
traduzione fedele della richiesta: il corso è il progetto, dentro c'è tutto e solo lo
storico del tutor di quel corso.

- Include tutto il contenuto dell'opzione A.
- **72–92 ore** → 10–12 giorni uomo.

### Opzione C — Estensione in stile NotebookLM

Da valutare in un secondo momento, sopra l'opzione B:

- citazioni cliccabili che riportano alla lezione o all'allegato di origine;
- pannello "fonti del corso" (che cosa il tutor ha effettivamente letto);
- ricerca testuale dentro lo storico e conversazioni preferite;
- esportazione della conversazione in PDF o testo;
- vista del docente sullo storico del proprio corso (richiede una decisione sulla privacy,
  vedi §6.3).

- **+44–60 ore** → +6–8 giorni uomo, da sommare a B.

---

## 5. Architettura proposta per l'opzione B

### 5.1 Dati

Due nuovi doctype, modellati su quelli delle simulazioni:

- **`LMSA Tutor Conversation`** — `course`, `member`, `title`, `started_at`,
  `last_message_at`, `message_count`, `status`.
- **`LMSA Tutor Message`** — `conversation`, `turn_index`, `role` (`user` / `assistant`),
  `content`, `lesson` (la lezione da cui la domanda è stata posta), `model_used`,
  `created_at`.

**`LMSA Query Log` resta com'è, con la sua funzione di audit.** È una scelta deliberata:
mescolare l'archivio consultabile dallo studente con il registro di controllo significa
che cancellare una conversazione (diritto dello studente) distrugge la tracciabilità, e
che ogni lettura dello storico si trascina dietro il campo `context`, che contiene il
system prompt completo — con i parametri attuali (6 brani da 1.000 caratteri) sono
**8–15 KB per riga**. La tabella dei messaggi resta invece leggera, 1–2 KB per turno.

### 5.2 Permessi

Gli stessi due hook già usati per le simulazioni, registrati in
[hooks.py](../../apps/os_lms/os_lms/hooks.py): `permission_query_conditions` per filtrare
gli elenchi e `has_permission` per bloccare l'accesso diretto per nome. Attenzione a un
comportamento noto di Frappe, già documentato nel progetto: un hook `has_permission` che
restituisce `None` oggi vale **diniego**, quindi il caso "consentito" deve restituire
`True` esplicitamente.

### 5.3 Backend

`TutorAi.ask` riceve l'identificativo della conversazione, la crea al primo messaggio,
scrive i due turni e aggiorna il contatore. La stessa modifica copre anche il percorso
audio (`ask_audio`), che passa dallo stesso metodo. Nuovi endpoint per la SPA:
elenco per corso, lettura, creazione, rinomina, cancellazione.

**Una modifica necessaria e non ovvia:** oggi la cronologia inviata al modello non ha
alcun troncamento — `_build_messages` mette nel prompt tutti i turni ricevuti dal client,
e la documentazione affida al frontend il compito di limitarli. Finché la chat si perdeva
al refresh il problema non si vedeva; con le conversazioni persistite una chat lunga
farebbe crescere il costo di *ogni* domanda successiva. Va introdotta una finestra
scorrevole sugli ultimi N turni (o un riassunto dei precedenti). È dentro la stima.

### 5.4 Frontend

- `stores/aiChat.js` diventa consapevole della conversazione: carica, salva, cambia.
- Il pannello flottante guadagna un selettore delle conversazioni e un pulsante "nuova
  chat"; il cestino passa da "svuota la memoria" a "cancella la conversazione", con
  conferma.
- Nuova pagina "Tutor AI del corso": elenco a sinistra, trascrizione a destra, possibilità
  di riprendere la conversazione. Riusa `ChatBot.vue` per la parte conversazionale.
- Punto d'ingresso dalla pagina del corso, rotta dedicata, adattamento mobile
  (il pannello convive già con la barra CTA fissa del mobile).
- Etichette tradotte IT/EN.

### 5.5 Configurazione

Interruttore `tutor_history_enabled` in `LMSA Settings`, esposto alla SPA dalla stessa
funzione che già espone `ai_enabled` e `simulations_enabled`
([override_api.py](../../apps/os_lms/os_lms/os_lms/override_api.py)), più un parametro di
conservazione con attività pianificata di pulizia.

---

## 6. Punti di attenzione

### 6.1 Costo per domanda
Vedi §5.3: senza troncamento della cronologia, conversazioni lunghe fanno crescere il costo
di ogni domanda. Mitigazione già inclusa nella stima.

### 6.2 Spazio occupato
La nuova tabella dei messaggi è leggera. Il problema semmai è preesistente: `LMSA Query Log`
cresce di 8–15 KB per scambio a causa del campo `context`. Su 200 studenti con 30 domande
ciascuno sono circa 70 MB di audit contro ~10 MB di storico consultabile. Va deciso per
quanto tempo conservare l'uno e l'altro.

### 6.3 Privacy — la decisione che va presa esplicitamente
Le conversazioni contengono dati personali, e spesso rivelano che cosa lo studente non ha
capito. Oggi Moderator e Course Creator possono già leggerle dal Desk, ma è una possibilità
tecnica poco visibile; renderla un'interfaccia di prodotto la trasforma in una funzione, ed
è un fatto diverso, anche verso gli studenti. Servono tre risposte dal cliente: chi può
leggere le chat altrui, se lo studente può cancellare le proprie, per quanto tempo si
conservano. Questa decisione va presa **prima** di scrivere codice, perché cambia lo schema
dei permessi.

### 6.4 Risposte che invecchiano
Il tutor risponde solo sulle lezioni che lo studente ha già completato (protezione
anti-spoiler già attiva nel retrieval), quindi lo storico non espone mai contenuti non
ancora visti: da questo lato è sicuro. Resta però che, se il corso viene aggiornato, una
vecchia risposta può non essere più corretta. Mitigazione minima e a costo quasi nullo:
mostrare la data di generazione accanto a ogni risposta archiviata.

### 6.5 Indici di database
La lista dello storico filtra su studente e corso e ordina per data. Da verificare in fase
di implementazione che i campi di filtro abbiano un indice, per non degradare con la
crescita della tabella.

### 6.6 Nota a margine
In [stores/aiContext.js](../../frontend/src/stores/aiContext.js) la funzione `setLesson`
contiene un `console.log` di debug dimenticato. Estraneo a questo intervento, si segnala
soltanto: va rimosso quando si tocca quel file.

---

## 7. Tempistiche

### Dettaglio dell'opzione B

| # | Voce | Ore |
| --- | --- | ---: |
| **Backend** | | **33–41** |
| 1 | Doctype `LMSA Tutor Conversation` (campi, permessi, indici) | 4 |
| 2 | Doctype `LMSA Tutor Message` | 3 |
| 3 | Hook dei permessi (elenco + accesso diretto), sul modello simulazioni | 4–5 |
| 4 | Persistenza dei turni in `TutorAi.ask` e nel percorso audio, apertura e ripresa | 6–8 |
| 5 | Titolo automatico della conversazione (prima domanda, troncata) | 1 |
| 6 | Endpoint SPA: elenco, lettura, creazione, rinomina, cancellazione | 6–8 |
| 7 | Finestra scorrevole sulla cronologia inviata al modello | 3 |
| 8 | Test backend (logica + permessi) | 6–9 |
| **Frontend** | | **29–37** |
| 9 | Store consapevole della conversazione | 5–7 |
| 10 | Pannello flottante: selettore, "nuova chat", cancellazione con conferma | 7–9 |
| 11 | Pagina "Tutor AI del corso" (elenco + trascrizione + ripresa) | 10–14 |
| 12 | Rotta, punto d'ingresso dal corso, adattamento mobile | 5 |
| 13 | Traduzioni IT/EN | 2 |
| **Configurazione e consegna** | | **10–14** |
| 14 | Interruttore in `LMSA Settings` + esposizione SPA + pannello impostazioni | 3 |
| 15 | Conservazione configurabile + attività pianificata di pulizia | 3–4 |
| 16 | Aggiornamento di `docs/ai/TUTOR.md` | 2 |
| 17 | Collaudo, UAT e giro di correzioni | 4–7 |
| | **Totale** | **72–92** |

Facoltativo, non incluso: **recupero dello storico già presente** in `LMSA Query Log`
(raggruppando le righe esistenti per corso e giornata, così che gli studenti trovino
popolato il proprio archivio fin dal primo giorno) — **+4–6 ore**.

### Sequenza di consegna consigliata

| Fase | Contenuto | Ore | Giorni | Risultato visibile |
| --- | --- | ---: | ---: | --- |
| 1 | Opzione A: persistenza e ripresa della conversazione | 24–32 | 3–4 | La chat non si perde più, su qualsiasi dispositivo |
| 2 | Completamento all'opzione B: conversazioni multiple, pagina del corso, gestione | 48–60 | 6–8 | Il "progetto corso" con tutto lo storico |
| 3 | Opzione C, se richiesta | 44–60 | 6–8 | Citazioni alle fonti, ricerca, esportazione |

Consegnare in due fasi costa 4–6 ore in più rispetto a fare tutto in un blocco (lo store
del frontend viene toccato due volte), ma mette in mano agli studenti il beneficio
principale dopo la prima settimana e permette di raccogliere riscontri prima di costruire
la pagina dedicata. È la sequenza che consiglio.

I giorni indicati sono giornate uomo di sviluppo effettivo (7,5 ore), al netto di attese
per decisioni del cliente, revisioni grafiche e finestre di rilascio.

---

## 8. Decisioni necessarie prima di partire

Sono le domande le cui risposte cambiano la stima o lo schema dati. Le prime tre sono
bloccanti.

1. **Privacy** — il docente (o il moderatore) deve vedere le chat dei propri studenti? E lo
   studente può cancellare le proprie? Per quanto tempo si conservano? *(cambia lo schema
   dei permessi: va deciso prima di scrivere codice)*
2. **Una conversazione o molte per corso?** Una sola continua è l'opzione A; più
   conversazioni distinte, come in NotebookLM, è l'opzione B.
3. **Le citazioni alle fonti fanno parte della richiesta?** Se "come NotebookLM" include le
   citazioni cliccabili, l'opzione C non è facoltativa e va messa a preventivo.
4. **Lo storico è solo del corso o anche della singola lezione?** Oggi il pannello è
   contestuale alla lezione: va deciso se, dentro il progetto-corso, le conversazioni
   mostrano da quale lezione sono nate (proposta: sì, come etichetta, costo trascurabile).
5. **Il "progetto" deve contenere anche le simulazioni e le sessioni vocali?** Sono già
   persistite e già consultabili altrove: unificarle nella stessa pagina è possibile e
   sensato, ma è lavoro aggiuntivo non ancora stimato.
6. **Serve l'esportazione** della conversazione (PDF o testo)?
7. **Si recupera lo storico già registrato** nei log esistenti, o si parte da archivio vuoto?

---

## 9. Raccomandazione

Procedere con l'**opzione B, consegnata in due fasi**, e portare le domande del §8 al
cliente prima di aprire il codice — in particolare le tre bloccanti sulla privacy, perché
determinano lo schema dei permessi e rifarlo dopo costa più che deciderlo ora.

Il rischio tecnico è basso: nessun componente nuovo, nessuna dipendenza nuova, nessuna
modifica al motore AI, e un sistema gemello già in produzione da cui copiare struttura,
permessi e interfaccia. Il rischio vero è di aspettativa: "come NotebookLM" evoca le
citazioni alle fonti, che sono l'opzione C. Meglio chiarirlo adesso che a consegna fatta.
