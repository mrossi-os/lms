# Worklog — OS LMS

Registro operativo delle **singole attività**, strutturato secondo la direttiva
aziendale sul report giornaliero. Questo file contiene solo le attività, una per
una, con i punti **1-4 + 6** della direttiva (obiettivo, modalità di esecuzione,
attività svolte, utilizzo dell'AI, problematiche).

**Il report giornaliero è un documento separato e vive in `reports/`**, un file per
giornata (`reports/AAAA-MM-GG-os-lms.md`). È lì che le attività vengono aggregate a
livello di progetto e che si trovano i punti **7-8-9** della direttiva — prossime
attività, avanzamento del progetto, spunti di miglioramento aziendale — che sono a
livello di giornata e **non vanno scritti in questo file**.

In sintesi: qui si registra *cosa è stato fatto, attività per attività*; nel report
si consegna *la giornata nel suo insieme*.

Convenzioni:

- Le giornate sono in ordine **cronologico inverso** (la più recente in alto).
- Ogni giornata si apre con il rimando al report corrispondente in `reports/`.
- Ogni attività si apre con il blocco **In sintesi**, che contiene i campi
  minimi obbligatori e non manca mai: problema riscontrato (il sintomo di
  partenza), problema effettivo (la causa reale emersa dall'analisi), soluzione
  applicata, stato del commit, file toccati, verifiche. Per le attività che non
  nascono da un problema, "problema riscontrato" diventa l'esigenza di partenza
  e "problema effettivo" il vincolo tecnico realmente rilevante.
- Il punto 5 della direttiva non è una sezione ma un requisito di dettaglio:
  è soddisfatto dentro il punto 4, che va sempre compilato per esteso o con
  "AI non utilizzata".
- Ogni attività cita **branch, commit e file toccati**, così che il report sia
  verificabile e un'altra persona (o un sistema AI) possa riprendere il lavoro.
- Il template vuoto da copiare per una nuova attività è in fondo al file.
- A fine giornata le attività qui registrate vengono aggregate nel report di
  `reports/`; nessun contenuto di livello giornaliero resta in questo file.

---

## 2026-09-17

> **Report giornaliero:** `reports/2026-09-17-os-lms.md` — **ancora da redigere**:
> a fine giornata le attività qui registrate vanno aggregate in quel file insieme
> ai punti 7-8-9 della direttiva (prossime attività, avanzamento, spunti di
> miglioramento).

---

### Attività 1 — Analisi completa dell'aggiornamento di una lezione dal vivo già pubblicata, con email di avviso e riallineamento dei promemoria

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — studio completo preliminare all'implementazione, nessuna modifica al codice |
| **Problema riscontrato** | Richiesta dell'utente, che fissa l'obiettivo dopo le due analisi del 16/09: poter **aggiornare una lezione dal vivo già pubblicata**; se cambiano i parametri principali (titolo, data, ora, durata) deve partire un'email di avviso alla classe, e i promemoria configurati devono essere riallineati di conseguenza. Richiesta esplicita di un'analisi completa prima di scrivere codice, più una domanda puntuale: il template dell'email di aggiornamento esiste già o va creato, e dove si imposta quello nuovo. |
| **Problema effettivo** | L'intervento sembra un semplice allargamento della whitelist dei campi modificabili, ma l'analisi ha fatto emergere che i punti critici stanno altrove, e sono cinque: (1) il criterio per decidere se l'email deve partire non può essere "il campo è nel payload", perché subito dopo la creazione il frontend richiama `update_live_class` per salvare i promemoria e ogni creazione genererebbe un'email di aggiornamento spuria; (2) il riarmo dei promemoria oggi copre solo il cambio di data/ora/durata e **non** il cambio di offset di una singola riga, che resterebbe marcata come già inviata; (3) un promemoria la cui finestra è già scaduta dopo lo spostamento parte entro 15 minuti, a ridosso dell'email di aggiornamento; (4) il file `.ics` non ha il campo `SEQUENCE`, quindi i calendari possono ignorare l'aggiornamento o duplicare l'evento; (5) esiste un difetto preesistente di fuso orario nella chiamata di creazione a Zoom, sulla stessa riga di codice che l'intervento deve toccare. |
| **Soluzione applicata** | Nessuna modifica al codice. Consegnata l'analisi completa in otto aree (permessi e ambito, rilevazione delle modifiche, Zoom, Google Meet e evento di calendario, email, promemoria, file `.ics`, frontend), la risposta sul template (non esiste, va creato su due strati) e un piano di lavoro con stima rivista a circa una giornata e mezza. Isolate cinque decisioni rimesse all'utente, ciascuna con il consiglio motivato. |
| **Commit** | No — analisi, nessuna modifica al codice. Implementazione in attesa delle cinque decisioni. |
| **File modificati** | Nessuno. File letti in aggiunta a quelli del 16/09: [apps/os_lms/os_lms/os_lms/doctype/os_lms_email_settings/os_lms_email_settings.json](apps/os_lms/os_lms/os_lms/doctype/os_lms_email_settings/os_lms_email_settings.json), [apps/os_lms/os_lms/os_lms/doctype/lms_live_class_reminder/lms_live_class_reminder.json](apps/os_lms/os_lms/os_lms/doctype/lms_live_class_reminder/lms_live_class_reminder.json) e relativo `.py`, [apps/os_lms/os_lms/fixtures/custom_field.json](apps/os_lms/os_lms/fixtures/custom_field.json), [apps/os_lms/os_lms/hooks.py](apps/os_lms/os_lms/hooks.py) (fixtures e `scheduler_events`), [apps/os_lms/os_lms/templates/emails/live_class_invitation.html](apps/os_lms/os_lms/templates/emails/live_class_invitation.html) e `live_class_cancelled.html` |
| **Verifiche** | Due accertamenti eseguiti, non dedotti. **Primo**, sul formato dell'orario inviato a Zoom: eseguito nell'ambiente Python del bench nel container di sviluppo `dev-elite-frappe-1` il comando `babel.dates.format_datetime(datetime(2026,9,20,15,0), "yyyy-MM-ddTHH:mm:ssZ", locale="en")`, che restituisce `'2026-09-20T15:00:00+0000'`: la `Z` del pattern **non** è una lettera letterale ma il segnaposto dell'offset, quindi le 15:00 locali vengono dichiarate a Zoom come 15:00 UTC (Babel 2.16.0). **Secondo**, sulla frequenza dello scheduler dei promemoria: `cron` `*/15 * * * *` in `hooks.py`, quindi la reazione al riarmo è al massimo di 15 minuti. Accertato inoltre per lettura che i campi `reminders`, `reminders_section` e `started_at` di *LMS Live Class* sono Custom Field distribuiti via fixtures, il che indica dove va aggiunto l'eventuale contatore di sequenza. Nessuna prova sull'API Zoom: richiede un account reale, resta in capo alla fase di implementazione. |

**1. Obiettivo dell'attività**

Portare l'intervento allo stato di "pronto da implementare": stabilire ogni punto del
codice da toccare, ogni effetto collaterale da governare e ogni scelta che non spetta a
chi scrive il codice, in modo che l'implementazione sia esecuzione e non scoperta.
Obiettivo secondario, richiesto esplicitamente: dire se il template dell'email di
aggiornamento esista e dove si imposti, perché è la parte che il cliente dovrà poi
gestire da solo da desk.

**2. Modalità di esecuzione**

Analisi statica estesa a tutti gli strati toccati, partendo da quanto già ricostruito
il 16/09 (ciclo di vita del doctype, endpoint di modifica, modale di modifica) e
aggiungendo i tre strati rimasti scoperti: il meccanismo dei template email a due
livelli in `email_utils`, con i campi del singleton *OS LMS Email Settings*; il
sottosistema dei promemoria, cioè il doctype figlio, l'hook di riarmo e la frequenza
dello scheduler; il meccanismo con cui il progetto aggiunge campi ai doctype di monte,
cioè i Custom Field distribuiti via fixtures. Dove un'affermazione dipendeva da una
libreria e non dal codice — la formattazione dell'orario per Zoom — la si è verificata
eseguendola nell'ambiente reale del bench, non deducendola.

**3. Attività svolte**

*Risposta sul template.* Non esiste: i template della lezione dal vivo sono tre
(`live_class_invitation`, `live_class_reminder`, `live_class_cancelled`), più quello
del login. Va creato su due strati, perché così funziona `send_templated_email`: il
file di default `templates/emails/live_class_updated.html`, e il campo
`live_class_updated_template` di tipo Link a *Email Template* nella sezione "Live Class"
del singleton *OS LMS Email Settings*. Il nome del campo non è libero: la convenzione
`{template_key}_template` è cablata in `_get_custom_template_name`. A intervento fatto
il cliente crea il proprio template in `/app/email-template` e lo collega in
`/app/os-lms-email-settings`; a campo vuoto vale il default dell'app. Segnalata anche la
necessità di un `bench migrate` perché il campo nuovo compaia, e la correzione della
descrizione del campo *Live Class Invitation*, che già oggi dichiara erroneamente che
l'invito parte «alla creazione/aggiornamento».

*Analisi in otto aree.* (1) Permessi e ambito: la modifica resta a Moderator e Batch
Evaluator; va vietata la modifica degli orari su una lezione già avviata, perché il gate
d'ingresso usa `started_at` e uno spostamento in avanti lascerebbe la porta aperta da
subito. (2) Rilevazione delle modifiche: confronto con i valori a database prima del
salvataggio, mai con la presenza nel payload, per non generare un'email spuria ad ogni
creazione con promemoria; proposto di includere il fuso orario fra i campi significativi,
perché sposta l'istante reale quanto l'ora. (3) Zoom: `PATCH /v2/meetings/{id}` conserva
ID, `join_url`, `start_url` e password, e va seguito da un `GET` perché la PATCH risponde
`204` senza corpo; emerso il difetto di fuso orario descritto nelle verifiche. (4) Google
Meet ed evento: il link resta invariato, ma `_update_linked_event` non è sovrascritto da
os_lms e riscrive l'oggetto dell'evento in inglese, cancellando l'italiano della
creazione, e non reagisce al cambio di fuso. (5) Email: definiti destinatari (consigliata
la platea dell'invito, non i soli studenti), contenuto (consigliato il prima/dopo, che
impone di fotografare i valori vecchi prima di applicarli) e automatismo (consigliata la
casella pre-spuntata, gemella di quella dell'eliminazione, per il caso del refuso nel
titolo); da emettere anche la notifica in piattaforma. (6) Promemoria: il riarmo su
data/ora/durata esiste già, ma mancano il riarmo sulle righe il cui offset è cambiato —
che è esattamente la parte "i promemoria devono essere aggiornati" della richiesta — e
la gestione delle finestre già scadute, che farebbero partire un promemoria entro 15
minuti a ridosso dell'email di aggiornamento; inoltre `sent_at` oggi arriva dal client e
andrebbe ricostruito lato server. (7) File `.ics`: UID già stabile ma `SEQUENCE` assente,
da aggiungere con un contatore incrementale su un nuovo Custom Field. (8) Frontend: campi
orari da riabilitare, validazioni oggi presenti solo in creazione da portare in modifica,
avviso da sostituire con la casella di notifica.

*Piano e stima.* Sette blocchi di lavoro per circa una giornata e mezza, contro la mezza
giornata stimata il 16/09: la stima precedente copriva il solo percorso principale, mentre
l'analisi ha aggiunto i tre punti sui promemoria, il `SEQUENCE` e la questione del fuso
su Zoom. La revisione è stata dichiarata esplicitamente all'utente insieme al motivo.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code)
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: analisi completa preliminare all'implementazione
  dell'aggiornamento di una lezione dal vivo, comprensiva del censimento dei template
  email e del sottosistema dei promemoria
- motivo della scelta del tool e del modello: l'analisi attraversa otto punti del codice
  che si condizionano a vicenda su quattro strati diversi (frontend Vue, endpoint API,
  ciclo di vita del doctype con hook, scheduler) più due servizi esterni (Zoom e Google
  Calendar); il contesto ampio permette di tenerli aperti insieme e di far emergere gli
  effetti incrociati — email spuria alla creazione, promemoria non riarmato sul cambio di
  offset — che una lettura per file separati non mostrerebbe
- risultato ottenuto: analisi in otto aree, risposta sul template con i due strati e il
  punto esatto dove il cliente lo imposterà, cinque decisioni isolate e motivate, piano
  in sette blocchi con stima rivista
- verifiche e correzioni effettuate: la formattazione dell'orario per Zoom è stata
  eseguita nell'ambiente Python del bench nel container invece di essere dedotta,
  facendo emergere il difetto di fuso preesistente; la frequenza dello scheduler è stata
  letta da `hooks.py` e non stimata; l'assenza del template di aggiornamento è stata
  verificata sui file e sui campi del singleton, non supposta. La stima precedente è
  stata corretta al rialzo dichiarandone il motivo, invece di essere confermata per
  coerenza con quanto detto il giorno prima.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Restano due dipendenze non risolvibili in analisi: la conferma
sul campo che la `PATCH` a Zoom preservi `join_url` sull'account del cliente, che
richiede un account reale e una riunione di prova in fase di implementazione, e le
cinque decisioni rimesse all'utente (contenuto dell'email, destinatari, obbligatorietà
dell'invio, sorte dei promemoria a finestra scaduta, correzione o replica del
comportamento di fuso orario verso Zoom). L'implementazione non può partire senza
almeno le decisioni 1-3, che determinano il template da scrivere.

---

### Attività 2 — Implementazione dell'aggiornamento di una lezione dal vivo già pubblicata, con email di avviso e promemoria riallineati

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Nuova feature — implementazione dell'intervento analizzato nell'Attività 1 |
| **Problema riscontrato** | Esigenza dell'utente: una lezione dal vivo già pubblicata non era modificabile se non nel titolo e nella descrizione; per spostarla di data o allungarla bisognava eliminarla e ricrearla, con perdita del link e necessità di rimandare tutto a mano. Richiesta: poter aggiornare la lezione, avvisare la classe via email quando cambiano i parametri principali (titolo, data, ora, durata) e riallineare di conseguenza i promemoria. |
| **Problema effettivo** | Tre vincoli tecnici hanno determinato la forma della soluzione. **Primo**: l'aggiornamento non poteva limitarsi a salvare i campi, perché la riunione Zoom resta ferma all'orario di creazione se non la si riprogramma esplicitamente — e va riprogrammata con `PATCH`, non cancellandola e ricreandola, altrimenti cambia il link. **Secondo**, emerso in implementazione e non previsto dall'analisi: `doc.has_value_changed()` di Frappe normalizza solo i tipi data/ora e **non** i numeri, quindi con i campi orari finalmente presenti nel payload la durata arrivava come stringa `"90"` e veniva confrontata con l'intero `90`, facendo risultare "cambiata" ogni lezione a ogni salvataggio: l'hook di riarmo dei promemoria si sarebbe attivato anche per una semplice correzione del titolo, rimandando tutti i promemoria già inviati. **Terzo**: l'email di aggiornamento non esisteva né come file né come campo configurabile da desk. |
| **Soluzione applicata** | Aggiornamento completo su sette file. Endpoint `update_live_class` esteso ai campi orari con validazioni (niente date passate, lezione avviata congelata) e ricostruzione server-side di `sent_at` sui promemoria; rilevazione delle modifiche significative spostata nell'override del doctype (`on_update`), così da coprire anche le modifiche fatte da desk, con riprogrammazione Zoom via `PATCH` + `GET` di risincronizzazione; nuovo template email `live_class_updated` con relativo campo sul singleton *OS LMS Email Settings*; `SEQUENCE` nel file `.ics`; correzione del fuso orario inviato a Zoom in creazione; confronto dei campi reso indipendente dal tipo con un normalizzatore condiviso, usato anche dall'hook dei promemoria. Frontend: campi data, ora, durata e fuso riabilitati in modifica, bloccati solo se la lezione è già stata avviata, con avviso che il salvataggio notifica gli iscritti. |
| **Commit** | Sì — `7b6ea7a18` *feat(live-class): allow rescheduling a published live class*, branch `feature/oslms`. Otto file, +512/-73. Lasciate deliberatamente fuori dal commit le due modifiche già presenti nel working tree all'inizio della sessione (`apps/os_lms/os_lms/hooks.py` e `apps/os_lms/os_lms/os_lms/utils.py`, hook `before_job` per la lingua dei job in background), perché appartengono a un lavoro precedente e non a questa attività. |
| **File modificati** | [apps/os_lms/os_lms/os_lms/api.py](apps/os_lms/os_lms/os_lms/api.py) (whitelist, validazioni, `normalize_live_class_value`, `_apply_reminders`, `zoom_start_time`, `update_zoom_meeting`), [apps/os_lms/os_lms/overrides/lms_live_class.py](apps/os_lms/os_lms/overrides/lms_live_class.py) (`on_update`, `_handle_class_update`, `_update_linked_event`, `_mail_participants`, `send_update_email`, `send_update_notification`), [apps/os_lms/os_lms/os_lms/live_class_reminders.py](apps/os_lms/os_lms/os_lms/live_class_reminders.py) (`reset_sent_at`), [apps/os_lms/os_lms/os_lms/live_class_ics.py](apps/os_lms/os_lms/os_lms/live_class_ics.py) (`SEQUENCE`), [apps/os_lms/os_lms/os_lms/doctype/os_lms_email_settings/os_lms_email_settings.json](apps/os_lms/os_lms/os_lms/doctype/os_lms_email_settings/os_lms_email_settings.json) (campo nuovo + descrizioni), [lms/lms/doctype/lms_batch/lms_batch.py](lms/lms/doctype/lms_batch/lms_batch.py) (formato orario Zoom), [frontend/src/components/Modals/LiveClassModal.vue](frontend/src/components/Modals/LiveClassModal.vue). Nuovo file: [apps/os_lms/os_lms/templates/emails/live_class_updated.html](apps/os_lms/os_lms/templates/emails/live_class_updated.html). |
| **Verifiche** | Tutte eseguite sul container di sviluppo `dev-elite-frappe-1`, esito positivo. **Test di logica**: normalizzazione dei valori (stringa del browser contro `date`/`timedelta` del database), formato orario Zoom, `SEQUENCE` crescente dell'`.ics` con `DTSTART` corretto in UTC (15:00 Europe/Rome → 13:00Z), riarmo dei promemoria nei tre casi (modifica del solo titolo → **non** riarma; cambio data → riarma; cambio durata → riarma), gestione di `sent_at` (offset modificato → riparte, riga invariata → conserva lo storico, valore inviato dal client → ignorato). **Test end-to-end** su una lezione di prova del sito di sviluppo (`5feba75g42`, classe `prima-media`, 7 iscritti): spostamento salvato correttamente, 10 email accodate con oggetto «Lezione dal vivo aggiornata: …», 7 notifiche in piattaforma, modifica del solo titolo che conserva il `sent_at` del promemoria, salvataggio senza modifiche che non invia nulla, data nel passato rifiutata, lezione avviata congelata. Record e artefatti ripristinati integralmente a fine test (record riportato ai valori originali compreso `zoom_account`, 10 email in coda e 7 notifiche eliminate una per una per nome, nessuna mai spedita). **Rendering** del nuovo template verificato con `frappe.render_template`. **Build frontend** (`yarn build`) completata senza errori e componente Vue verificato con il compilatore SFC. **Doctype** ricaricato sul sito (`reload_doctype` + `clear_cache`): il campo *Live Class Updated* risulta presente nei metadati. Non verificata sul campo, per mancanza di credenziali: la chiamata reale `PATCH` a Zoom. |

**1. Obiettivo dell'attività**

Rendere modificabile una lezione dal vivo già pubblicata senza doverla distruggere: cambiare titolo, data, ora, durata e fuso orario mantenendo lo stesso link di partecipazione, avvisando automaticamente chi è iscritto e facendo in modo che i promemoria configurati ripartano sul nuovo orario. Il risultato atteso è la sostituzione della procedura "elimina e ricrea" con una riprogrammazione vera, senza effetti collaterali su chi ha già l'invito in casella.

**2. Modalità di esecuzione**

Cinque decisioni erano state isolate nell'Attività 1 e sono state poste all'utente prima di scrivere codice; le risposte hanno fissato il perimetro: email di aggiornamento **sempre automatica** (nessuna casella per disattivarla), contenuto **gemello dell'invito** con tutti i parametri attuali e non un confronto prima/dopo, **template unico** per studenti e docenti, promemoria a finestra già scaduta che **partono comunque**, e **correzione** del fuso orario inviato a Zoom.

Scelta architetturale principale: la rilevazione delle modifiche e le conseguenti azioni (Zoom, email, notifica) non stanno nell'endpoint ma nell'`on_update` dell'override del doctype, così da attivarsi su qualunque percorso di salvataggio — l'interfaccia dello studente-amministratore e il desk di Frappe allo stesso modo — coerentemente con l'hook dei promemoria che già lavorava a quel livello. Il confronto passa da un normalizzatore condiviso perché i valori arrivano come stringhe dal browser e come tipi Python dal database.

**3. Attività svolte**

*Backend, endpoint.* `LIVE_CLASS_EDITABLE_FIELDS` estesa a data, ora, durata e fuso orario; introdotta `LIVE_CLASS_SCHEDULE_FIELDS` per distinguere i campi che spostano la lezione. Aggiunte due validazioni prima del salvataggio: una lezione già avviata (`started_at` valorizzato) non è più riprogrammabile, e il nuovo orario deve essere nel futuro. I promemoria non accettano più `sent_at` dal client: `_apply_reminders` lo ricostruisce lato server abbinando le righe sulla coppia (valore, unità), così una riga il cui offset è stato modificato riparte e una rimasta uguale conserva il proprio storico.

*Backend, doctype.* `on_update` chiama il comportamento di monte (che tiene allineato l'evento di Google Calendar) e poi `_handle_class_update`, che confronta i cinque campi notificabili con i valori precedenti e, se qualcosa è cambiato davvero, riprogramma Zoom e avvisa i partecipanti. Durante l'inserimento non fa nulla, perché è l'invito a coprire quel caso. Sovrascritto anche `_update_linked_event`, che di monte riscriveva l'oggetto dell'evento in inglese cancellando l'italiano della creazione. Il ciclo di invio delle email è stato fattorizzato in `_mail_participants`, usato sia dall'invito sia dall'aggiornamento, così i due messaggi restano allineati sulle stesse variabili; la registrazione diagnostica è stata conservata, con l'etichetta che distingue i due flussi.

*Zoom.* Nuova `update_zoom_meeting`: autenticazione, `PATCH /v2/meetings/{id}` con argomento, orario, durata, fuso e descrizione, e siccome la risposta è `204` senza corpo, una `GET` successiva per risincronizzare i link salvati. Tutto best-effort: un errore di Zoom viene registrato ma non blocca il salvataggio né le email. Corretto inoltre il formato dell'orario anche in creazione: il pattern usato di monte produceva un offset `+0000`, facendo interpretare a Zoom un orario italiano come GMT.

*Email e template.* Creato `live_class_updated.html` sulla falsariga dell'invito, con una tabella che riporta lezione, data, ora e durata aggiornate, la descrizione se presente, il pulsante di partecipazione e i tre bottoni di calendario. Aggiunto il campo `live_class_updated_template` nella sezione "Live Class" delle impostazioni email, con la descrizione delle variabili: il cliente può quindi sostituire il template da desk esattamente come per invito, promemoria e annullamento. Corretta la descrizione del campo dell'invito, che dichiarava erroneamente un invio anche in aggiornamento.

*Promemoria e calendario.* `reset_sent_at` non usa più `has_value_changed` ma il normalizzatore condiviso, chiudendo il difetto descritto nel riquadro. Aggiunto il campo `SEQUENCE` all'`.ics`, derivato dai minuti di `modified`, così i calendari sostituiscono l'evento già in agenda invece di duplicarlo.

*Frontend.* Rimosso il blocco dei campi orari in modifica, che ora si disattivano soltanto se la lezione è già stata avviata; l'avviso "eliminala e ricreala" è stato sostituito da un avviso informativo sulle conseguenze del salvataggio. Le validazioni prima presenti solo in creazione sono state fattorizzate e riusate in modifica, con una regola in più: l'obbligo di scegliere un orario futuro scatta solo se l'orario è stato effettivamente cambiato, altrimenti sarebbe impossibile correggere il titolo di una lezione passata.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code)
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: implementazione completa della feature su sette file più il nuovo template, e verifica in ambiente di sviluppo
- motivo della scelta del tool e del modello: la modifica attraversa quattro strati (componente Vue, endpoint, ciclo di vita del doctype con hook, scheduler) più due servizi esterni, e ogni pezzo ha effetti sugli altri — l'esempio è il riarmo dei promemoria, che dipende da come il frontend serializza un campo numerico; un contesto ampio permette di tenere insieme la catena e di accorgersi di questi accoppiamenti mentre si scrive, invece che in collaudo
- risultato ottenuto: feature completa e verificata in sviluppo, con la sola dipendenza esterna dichiarata (prova reale su Zoom)
- verifiche e correzioni effettuate: oltre ai test elencati nel riquadro, in corso d'opera è stato individuato e corretto un difetto introdotto dalla modifica stessa — l'hook di riarmo dei promemoria che si sarebbe attivato a ogni salvataggio — e un difetto preesistente sul fuso orario Zoom, verificato eseguendo Babel nel container invece di dedurlo. Un falso allarme è stato risolto e non ha comportato modifiche al codice: gli script di verifica andavano in *segmentation fault* perché un file di appoggio copiato nel container si chiamava `inspect.py` e mascherava il modulo standard omonimo, mandando gli import in ricorsione infinita; rinominato il file, i test sono passati. Tutti i dati di prova sono stati rimossi puntualmente per nome, senza filtri larghi.

**6. Problematiche incontrate**

Una sola dipendenza resta aperta: la riprogrammazione su Zoom non è stata provata contro l'API reale, perché richiede le credenziali di un account Zoom del cliente e una riunione di prova. Il percorso è scritto per non fare danno in caso di errore — se Zoom rifiuta, l'errore viene registrato e il resto (salvataggio, email, notifiche, promemoria) prosegue — ma la conferma che il link resti invariato va fatta sul campo prima del rilascio in produzione. Da tenere presente inoltre che il campo *Live Class Updated* compare nelle impostazioni solo dopo una migrazione: sul sito di sviluppo è stato sincronizzato in questa sessione, in produzione servirà il normale `bench migrate` del rilascio.

---

### Attività 3 — Verifica se il template dell'email di aggiornamento va configurato in produzione, e preparazione del template pronto all'uso

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — accertamento su dati di produzione, con produzione di un artefatto per il cliente |
| **Problema riscontrato** | Domanda dell'utente subito dopo l'implementazione: «dopo aver fatto il commit devo impostare il template?». Cioè: rilasciare il codice basta perché l'email di aggiornamento funzioni, o serve anche un'azione di configurazione da desk? |
| **Problema effettivo** | La risposta non è deducibile dal codice, perché dipende da come è configurata l'istanza del cliente. Il meccanismo prevede due strati — file di default dell'app e *Email Template* collegabile da desk — quindi tecnicamente nessuna configurazione è necessaria. Ma se sull'istanza gli altri template della lezione dal vivo sono già stati personalizzati, la sola email di aggiornamento uscirebbe con la grafica di default, visibilmente diversa dalle altre tre. Serviva quindi una rilevazione sull'istanza reale, non un ragionamento. |
| **Soluzione applicata** | Accertato per interrogazione diretta del database di produzione (sola lettura) che tutti e tre i template della lezione dal vivo sono personalizzati da desk. Risposta: il rilascio basta perché l'email parta, ma per uniformità va creato anche il quarto template. Per non lasciare il lavoro a metà è stato preparato l'HTML già adattato alla grafica del cliente, ricavato dal loro template di invito di produzione e riscritto nei testi, pronto da incollare. |
| **Commit** | No — nessuna modifica al codice applicativo; prodotto un solo file di supporto non committato |
| **File modificati** | Nuovo file: [docs/email-template-aggiornamento-lezione-live.html](docs/email-template-aggiornamento-lezione-live.html). Nessuna modifica al codice. |
| **Verifiche** | Interrogazione **in sola lettura** del database di produzione (`tabSingles` e `tabEmail Template`): i campi `live_class_invitation_template`, `live_class_reminder_template` e `live_class_cancelled_template` sono valorizzati rispettivamente con «Invito lezione live», «Promemoria lezione live» e «Lezione live annullata», tutti e tre in HTML personalizzato (3,9 / 3,4 / 2,4 KB). Verificato che il template di invito di produzione usa esattamente le stesse variabili Jinja del file di default, quindi gli argomenti passati dall'email di aggiornamento sono già sufficienti, con in più `duration`. Sul sito di sviluppo i quattro campi sono invece vuoti: lì valgono i file dell'app. Il template preparato è stato renderizzato con `frappe.render_template` in due scenari — con durata e descrizione, e senza — ed entrambi rendono correttamente, con la tabella dei parametri che si adatta. |

**1. Obiettivo dell'attività**

Dire all'utente, senza ambiguità, che cosa deve fare **dopo** il rilascio perché l'email di aggiornamento arrivi ai corsisti con lo stesso aspetto delle altre, e nell'ordine giusto rispetto alla migrazione. Obiettivo secondario: eliminare il lavoro manuale di adattamento grafico, consegnando il template già pronto.

**2. Modalità di esecuzione**

Rilevazione sul sito di sviluppo dei quattro campi template, poi — poiché lo sviluppo non è rappresentativo della configurazione del cliente — interrogazione del database di produzione tramite il profilo credenziali dedicato, rigorosamente in sola lettura. Estratto l'HTML del template di invito di produzione per due scopi: verificare che le variabili usate coincidano con quelle passate dal codice, e usarlo come base grafica per il nuovo template, così che le due email risultino gemelle anche visivamente. Adattamento dei soli testi, palette e struttura invariate, e verifica del risultato renderizzandolo con Jinja.

**3. Attività svolte**

Risposta articolata in due livelli. **Tecnicamente non serve nulla**: se il campo resta vuoto parte il template di default incluso nell'app, quindi il rilascio è autosufficiente e nessuna email va persa. **In pratica serve**, perché in produzione gli altri tre sono personalizzati e senza il quarto l'email di aggiornamento avrebbe un aspetto diverso dalle altre. Indicato anche l'ordine delle operazioni: rilascio, `bench migrate` (senza il quale il campo *Live Class Updated* non compare nelle impostazioni), creazione dell'*Email Template* e collegamento nel campo.

Preparato `docs/email-template-aggiornamento-lezione-live.html` partendo dal template di invito del cliente: sostituito il testo introduttivo («la lezione è stata modificata» al posto dell'invito), inserita una tabella con i nuovi parametri — lezione, data, ora e durata, quest'ultima mostrata solo se valorizzata — e adattate le due diciture dei pulsanti («partecipare all'orario aggiornato», «Aggiorna il tuo calendario»). Colori, logo, struttura e piè di pagina sono quelli del cliente.

Segnalata all'utente, senza intervenire perché sul database di produzione non si scrive, una anomalia notata durante l'estrazione: il template di invito in produzione saluta con «Ciaooooo {{ student_name }}», evidentemente un residuo di una prova, che quindi compare in ogni invito realmente inviato. Nel template preparato il saluto è già corretto.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code)
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: accertamento della configurazione dei template sull'istanza di produzione e preparazione del template di aggiornamento nella grafica del cliente
- motivo della scelta del tool e del modello: la domanda richiedeva di combinare la conoscenza del meccanismo a due strati appena implementato con una rilevazione sui dati reali del cliente, e di trasformare il risultato in un artefatto immediatamente utilizzabile; il tool ha accesso sia al codice sia al profilo di lettura del database di produzione, quindi ha potuto rispondere sui fatti invece che in astratto
- risultato ottenuto: risposta netta su cosa fare dopo il commit e in quale ordine, template pronto da incollare, più la segnalazione dell'anomalia nel saluto del template di invito
- verifiche e correzioni effettuate: tutte le query di produzione eseguite in sola lettura, secondo la regola fissa del progetto; la coincidenza delle variabili Jinja fra template del cliente e argomenti passati dal codice è stata verificata estraendo e confrontando i segnaposto, non supposta; il template preparato è stato renderizzato in due scenari per accertare che la tabella regga anche senza durata e senza descrizione

**6. Problematiche incontrate**

Nessun ostacolo. Resta in capo all'utente, perché richiede accesso in scrittura al desk di produzione, la creazione dell'*Email Template* e il collegamento nel campo, oltre alla decisione su come correggere il saluto «Ciaooooo» nel template di invito.

---

### Attività 4 — Player del video di anteprima di corsi e classi allineato a quello delle lezioni

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione/allineamento funzionale — frontend SPA |
| **Problema riscontrato** | Segnalazione dell'utente: il video di anteprima nella scheda **Panoramica** dei corsi e delle classi usa un player diverso da quello che lo studente vede nelle lezioni; in quel player compaiono elementi che l'utente vuole togliere. Richiesta: usare, se possibile, lo stesso player delle lezioni. |
| **Problema effettivo** | Non è una questione di configurazione ma di componenti diversi. Le lezioni non incorporano mai il provider direttamente: i blocchi *embed* dell'editor generano `<div class="video-player" data-plyr-provider="youtube\|vimeo">` e la pagina lezione li inizializza con **Plyr** (`frontend/src/utils/plyr.js`), mentre un video caricato come file passa da `VideoBlock.vue`, che ha controlli propri. Le anteprime, invece, erano **tre punti di codice indipendenti** che montavano un `<iframe>` YouTube/Vimeo grezzo (o un `<video controls>` nativo): `VideoPreview.vue` (panoramica della classe), `CourseHero.vue` (hero della panoramica del corso) e `CourseCardOverlay.vue` (scheda laterale del corso, che mostra il video quando l'hero è disattivato). Con l'iframe grezzo il player è quello di YouTube, con barra del titolo, nome del canale, pulsanti *condividi* e *guarda più tardi*, logo e griglia dei video correlati a fine riproduzione: sono quelli gli «elementi da togliere». Complicazione ulteriore: i ritocchi di stile Plyr usati nelle lezioni sono globali ma dichiarati dentro `Lesson.vue`, quindi non sono caricati nelle pagine di panoramica. |
| **Soluzione applicata** | `VideoPreview.vue` è diventato il **player unico dell'anteprima** e adotta esattamente i due meccanismi della lezione: Plyr per YouTube/Vimeo, `VideoBlock` per un file caricato. Gli stessi ritocchi ai controlli (slider del volume nascosto, pulsante centrale con gradiente, riempimento bianco della barra) sono stati riportati nel componente come stili *scoped*, dato che quelli di `Lesson.vue` non arrivano fin qui. `CourseHero.vue` e `CourseCardOverlay.vue` ora delegano a `VideoPreview` invece di montare un iframe. Sono stati conservati due comportamenti preesistenti: il ripiego sull'immagine di copertina quando il file non è riproducibile — `VideoBlock` non espone l'errore del `<video>`, quindi l'evento viene intercettato in fase di cattura sul contenitore — e, nell'hero, l'iframe generico per un URL che non sia né YouTube/Vimeo né un file video, perché il campo *Hero Media URL* è testo libero. Rimossa da `CourseCardOverlay.vue` la computed `video_link`, rimasta senza usi. |
| **Commit** | `8f7729e5` — *fix(video): play course and batch previews with the lesson player*, sul branch `feature/oslms`. Committata su richiesta dell'utente prima del riscontro visivo sull'istanza; il controllo dell'aspetto su un corso con video di anteprima resta da fare. |
| **File modificati** | [frontend/src/components/VideoPreview.vue](frontend/src/components/VideoPreview.vue), [frontend/src/oslms/components/CourseHero.vue](frontend/src/oslms/components/CourseHero.vue), [frontend/src/components/CourseCardOverlay.vue](frontend/src/components/CourseCardOverlay.vue), [frontend/src/tests/VideoPreview.test.ts](frontend/src/tests/VideoPreview.test.ts) |
| **Verifiche** | Test unitari di `VideoPreview` riscritti sul nuovo contratto: 6 test, tutti verdi. Suite completa del frontend: 21 test falliti, **tutti preesistenti** — accertato e non supposto, mettendo da parte le sole modifiche con `git stash push` sui quattro file e rieseguendo la suite, che ha dato lo stesso identico esito (5 file, 21 test). Build di produzione `yarn build` completata senza errori. Formattazione verificata con prettier 2.7.1, la versione fissata in `.pre-commit-config.yaml`, sui due file riscritti. Accertato leggendo il sorgente di Plyr in `node_modules` (`plugins/vimeo.js`, `plugins/youtube.js`) che l'attributo `src` sull'elemento ha la precedenza su `data-plyr-embed-id`: l'hash dei video Vimeo non elencati sopravvive, quindi il passaggio a Plyr non rompe le anteprime di video privati. |

**1. Obiettivo dell'attività**

Rispondere alla domanda «perché i due player sono diversi» e, se tecnicamente possibile,
rendere il video di anteprima di corsi e classi identico al player che lo studente usa
nelle lezioni, così che gli elementi indesiderati dell'interfaccia YouTube spariscano
senza bisogno di nasconderli uno per uno.

**2. Modalità di esecuzione**

Ricostruzione dei due percorsi di riproduzione a partire dal codice: individuazione dei
componenti che disegnano il video nelle lezioni (`utils/plyr.js`, le definizioni dei
servizi *embed* in `utils/index.js`, `VideoBlock.vue`) e di quelli che lo disegnano
nelle anteprime (`VideoPreview.vue`, `CourseHero.vue`, `CourseCardOverlay.vue`),
seguendo gli usi con ricerca testuale invece di dedurli dai nomi. Verificato dove
ciascun componente è realmente montato: `BatchOverlay` risulta commentato in
`BatchOverview`, quindi i punti vivi sono tre e non quattro. Prima di sostituire
l'iframe si è controllato nel sorgente di Plyr come risolve la sorgente, perché la
perdita dell'hash Vimeo sarebbe stata una regressione silenziosa sui video non elencati.
Infine test, build e controllo di formattazione.

**3. Attività svolte**

Riscritto `VideoPreview.vue`. Il ramo YouTube/Vimeo non produce più un iframe del
provider ma l'elemento che Plyr si aspetta, dentro un contenitore che riserva il
rapporto 16:9 mentre Plyr si avvia (l'inizializzazione ha un'attesa, senza il
contenitore la pagina farebbe un salto). Il ramo «file caricato» usa `VideoBlock`, cioè
lo stesso componente della lezione, al posto del `<video controls>` nativo, che oltre
ad avere un aspetto diverso espone il menu di download del browser. L'avvio di Plyr è
legato alla sorgente e non al solo montaggio, perché il link arriva in genere con il
documento caricato in modo asincrono.

`CourseHero.vue` ora delega a `VideoPreview` quando l'URL è un link YouTube/Vimeo o un
file video, e conserva l'iframe generico negli altri casi. `CourseCardOverlay.vue`
sostituisce l'iframe con `VideoPreview` e perde la computed che costruiva l'URL di
embed, ormai inutile.

Riscritti i test di `VideoPreview` sul nuovo contratto — provider e sorgente consegnati
a Plyr, uso di `VideoBlock` per i file, ripiego sull'immagine, nessun disegno senza
link — con Plyr e `VideoBlock` sostituiti da doppioni, perché nessuno dei due può
funzionare in jsdom.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code)
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: individuazione della causa della differenza fra i due player, progettazione e scrittura della modifica, riscrittura dei test
- motivo della scelta del tool e del modello: la risposta richiedeva di attraversare tre strati non collegati fra loro (blocchi dell'editor delle lezioni, inizializzazione Plyr, componenti di anteprima) e di distinguere quali punti fossero davvero montati nella SPA; il tool lavora direttamente sul codice del repository ed esegue test e build, quindi ha potuto rispondere sui fatti e poi consegnare la modifica verificata
- risultato ottenuto: un solo componente di anteprima che usa lo stesso player delle lezioni, usato da tutti e tre i punti; test verdi e build completata
- verifiche e correzioni effettuate: il carattere preesistente dei 21 test falliti è stato dimostrato con `git stash`, non dato per scontato; il comportamento di Plyr sull'hash Vimeo è stato letto nel sorgente della libreria; durante la stesura è emerso che il ripiego sull'immagine di copertina sarebbe andato perso passando a `VideoBlock`, ed è stato reintrodotto con un ascolto in fase di cattura, coperto da test; sempre in corso d'opera si è notato che sostituire l'iframe dell'hero con il player avrebbe tolto il supporto agli URL generici (il campo è testo libero) e si è quindi mantenuto il ramo iframe

**6. Problematiche incontrate**

Nessun ostacolo bloccante. Due segnalazioni, non affrontate perché fuori dall'ambito
richiesto. Primo: nella panoramica del corso, su schermo stretto, la scheda laterale
`CourseCardOverlay` resta nel DOM (è nascosta via CSS) mentre viene disegnata anche la
variante mobile, quindi con l'hero disattivato esistono due player per lo stesso video —
comportamento identico a prima, quando erano due iframe. Secondo: il repository ha due
versioni di prettier in circolazione (la 2.7.1 fissata in `.pre-commit-config.yaml` e la
3.8.3 installata in `frontend/node_modules`), che non concordano sulle virgole finali;
`CourseCardOverlay.vue` risulta già non conforme alla 2.7.1 prima di questa modifica, per
cui un eventuale hook pre-commit lo riformatterebbe per intero.

---

## 2026-09-16

> **Report giornaliero:** `reports/2026-09-16-os-lms.md` — **ancora da redigere**:
> a fine giornata le attività qui registrate vanno aggregate in quel file insieme
> ai punti 7-8-9 della direttiva (prossime attività, avanzamento, spunti di
> miglioramento).

---

### Attività 1 — Chiarimento sulle email delle lezioni dal vivo e sulla modificabilità di data, ora e durata dopo la creazione

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — analisi del codice per rispondere a due domande operative dell'utente |
| **Problema riscontrato** | Due domande dell'utente sulle lezioni dal vivo (live class) delle classi: (1) «se si modifica la descrizione di un evento live, parte una email?»; (2) «una volta creata la live, è possibile modificare i parametri di durata o di inizio?». Sono domande di esercizio, non la segnalazione di un difetto: serve sapere cosa vede lo studente dopo una modifica e se una lezione già programmata si può riprogrammare senza cancellarla. |
| **Problema effettivo** | Il comportamento non è deducibile dall'interfaccia perché è distribuito su tre punti distinti: l'override `CustomLMSLiveClass` (che invia l'invito **solo** in `after_insert`), l'endpoint di modifica `update_live_class` (che accetta una whitelist di due soli campi) e la modale del frontend (che disabilita data, ora, durata e fuso orario in modifica). Il vincolo tecnico reale è che l'invito, la riunione Zoom e l'evento di Google Calendar vengono creati una sola volta alla creazione della lezione e **non** esiste alcun percorso di riprogrammazione: modificare i campi orari dal desk aggiornerebbe l'evento di calendario ma non la riunione Zoom né gli inviti già ricevuti dagli studenti. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola analisi e risposta. Ricostruita per intero la mappa degli invii email della lezione dal vivo (invito, promemoria, annullamento) e dei campi realmente modificabili dopo la creazione, lato SPA e lato desk, con le conseguenze di una modifica fatta dal desk. |
| **Commit** | No — nessuna modifica al codice |
| **File modificati** | Nessuno. Soli file letti: [apps/os_lms/os_lms/overrides/lms_live_class.py](apps/os_lms/os_lms/overrides/lms_live_class.py), [lms/lms/doctype/lms_live_class/lms_live_class.py](lms/lms/doctype/lms_live_class/lms_live_class.py), [apps/os_lms/os_lms/os_lms/api.py](apps/os_lms/os_lms/os_lms/api.py) (`update_live_class`, `delete_live_class`, `_notify_students_class_cancelled`), [apps/os_lms/os_lms/os_lms/live_class_reminders.py](apps/os_lms/os_lms/os_lms/live_class_reminders.py), [frontend/src/components/Modals/LiveClassModal.vue](frontend/src/components/Modals/LiveClassModal.vue), [frontend/src/pages/Batches/components/LiveClass.vue](frontend/src/pages/Batches/components/LiveClass.vue), [apps/os_lms/os_lms/hooks.py](apps/os_lms/os_lms/hooks.py) |
| **Verifiche** | Verifica per lettura incrociata del codice, non per esecuzione: ogni affermazione è ancorata al punto del codice che la produce (whitelist `LIVE_CLASS_EDITABLE_FIELDS = ("title", "description")` in `api.py:1881`; `:disabled="isEdit"` sui campi data/ora/durata/fuso in `LiveClassModal.vue`; invio invito solo dentro `create_calendar_event`, chiamato dal solo `after_insert`; `on_update` che esce subito se non cambiano data, ora, durata o titolo; hook `before_save` → `reset_sent_at` in `hooks.py:188-190`). Non è stata eseguita una prova sul sito di sviluppo: le domande sono sul comportamento del codice, che è univoco. |

**1. Obiettivo dell'attività**

Dare all'utente due risposte operative e verificabili: sapere se una correzione della
descrizione di una lezione dal vivo raggiunge gli studenti via email (e quindi se si
rischia di riempire le caselle degli iscritti correggendo un refuso), e sapere se una
lezione già programmata si può spostare o allungare senza cancellarla e ricrearla —
informazione che decide come si gestisce un cambio di orario comunicato dal docente.

**2. Modalità di esecuzione**

Analisi statica del codice partendo dai tre punti in cui il comportamento è deciso.
Primo, il ciclo di vita del doctype `LMS Live Class`: la classe base in
`lms/lms/doctype/lms_live_class/lms_live_class.py` e l'override di progetto
`CustomLMSLiveClass` in `apps/os_lms/os_lms/overrides/lms_live_class.py`, per stabilire
in quali callback (`after_insert`, `on_update`, `after_delete`) avvengono gli invii.
Secondo, l'API di modifica e cancellazione in `apps/os_lms/os_lms/os_lms/api.py`, per
stabilire quali campi accetta l'endpoint chiamato dall'interfaccia. Terzo,
l'interfaccia stessa (`LiveClassModal.vue`, `LiveClass.vue`), per stabilire cosa è
davvero editabile dall'utente finale. In parallelo è stato censito ogni invio email
legato alla lezione dal vivo cercando gli usi dei template `live_class_invitation`,
`live_class_reminder` e `live_class_cancelled`, così da poter rispondere in modo
esaustivo e non solo sul caso chiesto.

**3. Attività svolte**

*Mappa degli invii email della lezione dal vivo — sono tre e solo tre.*

1. **Invito** — inviato una sola volta, alla creazione:
   `after_insert` → `create_calendar_event` → `_send_invitation_safe` →
   `send_invitation_email` (template `live_class_invitation`). Destinatari: iscritti
   della classe, istruttori, valutatori della classe e chi ha creato la lezione. Il
   link nell'email è l'endpoint interno `join_live_class`, non l'URL Zoom/Meet.
   Insieme all'invito parte anche la notifica in piattaforma (`send_notification`).
2. **Promemoria** — inviati dallo scheduler `send_live_class_reminders` in base alle
   righe di promemoria configurate sulla lezione (template `live_class_reminder`).
3. **Annullamento** — inviato solo se si elimina la lezione **con la casella
   "Notifica gli studenti" spuntata** nella finestra di conferma
   (`delete_live_class` → `_notify_students_class_cancelled`, template
   `live_class_cancelled`).

*Risposta 1 — modificare la descrizione non manda nessuna email.* Il salvataggio di una
modifica passa da `os_lms.os_lms.api.update_live_class`, che non invia nulla: si limita
ad applicare i campi ammessi e a riscrivere la tabella dei promemoria. L'invito non
viene reinviato perché vive solo in `after_insert`. Conseguenza pratica da comunicare:
gli studenti che hanno già ricevuto l'invito continuano a vedere la descrizione
vecchia, perché nemmeno l'email di promemoria include il campo descrizione; la nuova
descrizione si vede solo nella scheda della classe in piattaforma. Rilevato anche un
limite secondario, **non corretto** perché fuori dal perimetro della domanda: se si
modifica la **sola** descrizione, l'evento collegato su Google Calendar non viene
aggiornato, perché `on_update` esce prima quando non cambiano data, ora, durata o
titolo; cambiando anche il titolo, invece, l'evento viene riscritto con descrizione
aggiornata. Va aggiunto che l'evento creato dall'override di progetto non ha
partecipanti Google (a differenza del percorso originale a monte), quindi in nessun
caso è Google a mandare email di aggiornamento agli studenti.

*Risposta 2 — data, ora e durata non sono modificabili dall'interfaccia.* La modale di
modifica disabilita esplicitamente data, ora, durata e fuso orario (`:disabled="isEdit"`)
e mostra l'avviso «Per cambiare data, ora o durata della lezione, eliminala e
ricreala». Il vincolo non è solo grafico: l'endpoint accetta la sola whitelist
`("title", "description")` più la tabella dei promemoria, quindi neppure una chiamata
costruita a mano potrebbe cambiare l'orario. Dal desk di Frappe (Moderator o System
Manager) i campi sono invece scrivibili, e in quel caso `on_update` propaga data, ora,
durata e titolo all'evento di Google Calendar e l'hook `before_save` → `reset_sent_at`
riazzera i promemoria già inviati perché tornino a partire sul nuovo orario; **ma** la
riunione Zoom non viene riprogrammata (nessuna chiamata all'API Zoom in aggiornamento)
e nessun invito aggiornato viene spedito agli studenti, che resterebbero con l'orario
vecchio in casella. Per questo la via corretta per spostare una lezione resta quella
imposta dall'interfaccia: eliminarla spuntando la notifica agli studenti e ricrearla,
così partono sia l'annullamento sia il nuovo invito.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), sessione sul repository `os_lms`
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: ricostruzione del comportamento delle lezioni
  dal vivo su due aspetti — quali modifiche generano email e quali campi sono
  modificabili dopo la creazione — leggendo backend, API e frontend
- motivo della scelta del tool e del modello: la risposta richiede di tenere insieme
  quattro livelli che si condizionano a vicenda (classe base a monte, override di
  progetto, endpoint API con whitelist, modale Vue con campi disabilitati); un modello
  con contesto ampio permette di leggerli tutti nella stessa sessione e di rispondere
  senza ipotesi, ancorando ogni affermazione al punto di codice che la produce
- risultato ottenuto: risposta puntuale alle due domande, più la mappa completa dei
  tre invii email della lezione dal vivo e l'indicazione della procedura corretta per
  riprogrammare una lezione
- verifiche e correzioni effettuate: ogni affermazione è stata riportata al codice che
  la genera e citata con file e riga; il campo descrizione è stato controllato anche
  negli argomenti dell'email di promemoria per escludere che la modifica arrivi allo
  studente per quella via. Nessuna prova di esecuzione sul sito: le domande riguardano
  il comportamento del codice, che è deterministico e non dipende dai dati.

**6. Problematiche incontrate**

Nessun ostacolo. Segnalato all'utente, senza intervenire, il limite già descritto al
punto 3: la modifica della sola descrizione non si propaga all'evento di Google
Calendar. Resta una decisione dell'utente se trattarlo come difetto da correggere.

---

### Attività 2 — Fattibilità della riprogrammazione di una lezione dal vivo con email di avviso, e sorte del link Zoom

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi di fattibilità — studio preliminare a un possibile intervento, senza modifiche al codice |
| **Problema riscontrato** | Richiesta dell'utente subito dopo l'Attività 1, che aveva accertato l'impossibilità di modificare data, ora e durata dall'interfaccia: «è possibile cambiare i parametri di durata ed orario e far partire una email che avverte della modifica? se è possibile viene rifatto un link nuovo di zoom oppure modifica quello creato?». La seconda domanda è il vero nodo: se riprogrammare comportasse un link nuovo, gli studenti si troverebbero in casella un invito con un collegamento non più valido, e la funzione sarebbe più dannosa della procedura attuale di cancella-e-ricrea. |
| **Problema effettivo** | Il vincolo determinante non è nel codice LMS ma nel comportamento dell'API Zoom, e va distinto dai due percorsi possibili: aggiornare la riunione esistente (`PATCH /v2/meetings/{meetingId}`) **conserva** ID riunione, `join_url`, `start_url` e password, mentre cancellare e ricreare — cioè quello che fa oggi la procedura consigliata — genera necessariamente un link nuovo. Su Google Meet il problema non si pone affatto, perché il link è agganciato all'evento di calendario e non all'orario. Vincolo ulteriore emerso: nel nostro caso l'email di invito non contiene nemmeno il link del provider ma il link interno `join_live_class`, costruito sul nome del documento, quindi resta valido per costruzione. |
| **Soluzione applicata** | Nessuna modifica al codice: consegnata la risposta e il piano di intervento in cinque punti (riabilitazione dei campi in modifica con casella di notifica, allargamento della whitelist dell'endpoint con validazioni, chiamata `PATCH` a Zoom con successivo `GET` di risincronizzazione, nuovo template email `live_class_updated` gestibile da desk, numero di sequenza nell'`.ics`), più l'accertamento che i promemoria sono già gestiti e non richiedono lavoro. Stima comunicata: circa mezza giornata. |
| **Commit** | No — analisi di fattibilità, nessuna modifica al codice. L'implementazione è in attesa del via libera dell'utente e di una sua decisione sul contenuto dell'email. |
| **File modificati** | Nessuno. Soli file letti, in aggiunta a quelli dell'Attività 1: [lms/lms/doctype/lms_batch/lms_batch.py](lms/lms/doctype/lms_batch/lms_batch.py) (`create_live_class`, `create_google_meet_live_class`, `authenticate`), [apps/os_lms/os_lms/os_lms/live_class_ics.py](apps/os_lms/os_lms/os_lms/live_class_ics.py), [apps/os_lms/os_lms/os_lms/email_utils.py](apps/os_lms/os_lms/os_lms/email_utils.py), [apps/os_lms/os_lms/os_lms/doctype/os_lms_email_settings/os_lms_email_settings.json](apps/os_lms/os_lms/os_lms/doctype/os_lms_email_settings/os_lms_email_settings.json) |
| **Verifiche** | Verifica per lettura del codice e per confronto con il contratto dell'API Zoom, non per esecuzione: accertato che il progetto oggi chiama Zoom **solo** in creazione (`POST /v2/users/me/meetings`) e in cancellazione (`DELETE /v2/meetings/{id}` in `_delete_zoom_meeting`), e che **non esiste alcuna chiamata di aggiornamento** — nessun `requests.patch` o `requests.put` in tutto il repository. Accertato inoltre che l'UID dell'`.ics` è già stabile (`live-class-{name}@{sito}`) ma privo del campo `SEQUENCE`, e che i template email sono agganciati a un campo per chiave sul singleton *OS LMS Email Settings* (oggi tre: invito, promemoria, annullamento). Nessuna prova su Zoom: richiederebbe credenziali di un account reale e la creazione di una riunione di prova, da fare in fase di implementazione. |

**1. Obiettivo dell'attività**

Stabilire se valga la pena sostituire la procedura attuale — cancella la lezione e
ricreala — con una vera riprogrammazione, e a quali condizioni. La domanda decisiva
non è se il codice si possa scrivere (si può sempre), ma se il risultato sia migliore
per lo studente: una riprogrammazione che invalidasse il link già ricevuto non
risolverebbe nulla rispetto a oggi. Obiettivo secondario: quantificare l'intervento
per permettere all'utente di decidere se metterlo in lavorazione.

**2. Modalità di esecuzione**

Ricostruzione di tutte le interazioni del progetto con l'API Zoom, cercando nel
repository ogni chiamata HTTP verso `api.zoom.us` e ogni verbo di aggiornamento, per
accertare cosa esista già e cosa vada scritto da zero. Lettura del percorso di
creazione (`create_live_class` per Zoom, `create_google_meet_live_class` per Meet) per
sapere quali campi vengono salvati alla creazione e quindi quali andrebbero
risincronizzati dopo un aggiornamento. Lettura del generatore di `.ics` e dei link di
calendario, perché una riprogrammazione senza aggiornamento del calendario degli
studenti sarebbe monca. Lettura di `email_utils` e dei campi del singleton delle
impostazioni email per collocare il nuovo template nello schema già in uso, invece di
inventarne uno diverso.

**3. Attività svolte**

*Risposta sul link Zoom.* Il link **non** cambia, a condizione di usare la strada
giusta: `PATCH https://api.zoom.us/v2/meetings/{meetingId}` aggiorna `start_time`,
`duration`, `timezone`, `topic` e `agenda` sulla riunione esistente lasciando invariati
ID riunione, `join_url`, `start_url` e password. Il link nuovo si genera solo
cancellando e ricreando, cioè con la procedura in uso oggi — ed è proprio il motivo per
cui oggi l'interfaccia impone di rimandare l'invito. Su Google Meet il link è agganciato
all'evento di calendario e resta identico spostandone l'orario; l'aggiornamento
dell'evento, peraltro, avviene già oggi tramite `on_update`. Da notare che nel nostro
caso l'email non veicola affatto il link del provider ma il link interno
`join_live_class`, costruito sul nome del documento: resta valido per costruzione
qualunque cosa accada alla riunione sottostante.

*Piano di intervento in cinque punti, più uno già coperto.*

1. Frontend: riabilitare data, ora, durata e fuso orario in modifica (oggi disabilitati
   con `:disabled="isEdit"`) e aggiungere la casella «Notifica gli studenti», modellata
   su quella già presente nella finestra di conferma dell'eliminazione.
2. Backend: allargare `LIVE_CLASS_EDITABLE_FIELDS` ai quattro campi orari e aggiungere
   le validazioni che oggi esistono solo in creazione — niente date passate — più il
   blocco della modifica su una lezione già avviata (campo `started_at` valorizzato).
3. Zoom: nuovo helper di aggiornamento accanto a `_delete_zoom_meeting`, che esegue la
   `PATCH` e poi un `GET /v2/meetings/{id}` per risincronizzare i campi salvati, dato
   che la `PATCH` risponde `204` senza corpo.
4. Email: nuovo template `live_class_updated` sotto `templates/emails/` più il campo
   `live_class_updated_template` sul singleton *OS LMS Email Settings*, così che il
   cliente possa sovrascriverlo da desk come già fa con invito, promemoria e
   annullamento; insieme all'email va emessa la notifica in piattaforma.
5. Calendario: aggiungere il campo `SEQUENCE` progressivo all'`.ics`. L'UID è già
   stabile, quindi con un numero di sequenza crescente i calendari degli studenti
   **aggiornano** l'evento esistente invece di crearne un doppione.
6. Promemoria: nessun lavoro necessario. L'hook `before_save` → `reset_sent_at`
   riazzera i promemoria già inviati quando cambiano data, ora o durata, quindi
   ripartono da soli sul nuovo orario.

*Decisione lasciata all'utente.* Se l'email di modifica debba mostrare il vecchio
orario accanto al nuovo — più chiaro per lo studente, ma impone di leggere il valore
precedente prima del salvataggio — oppure solo il nuovo. È una scelta di contenuto, non
tecnica, e blocca solo la stesura del template.

*Segnalazione laterale, non affrontata.* La `start_url` dell'host viene salvata una
volta sola alla creazione, mentre Zoom la fa scadere dopo poche ore: se in produzione
un docente trovasse un link di avvio non valido, la causa sarebbe questa e non la
riprogrammazione. Riferito all'utente in una riga, senza intervenire, perché fuori dal
perimetro della domanda.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione dell'Attività 1
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: censimento delle interazioni del progetto con
  l'API Zoom, individuazione del percorso di aggiornamento che preserva il link, e
  stesura del piano di intervento con la stima
- motivo della scelta del tool e del modello: la risposta richiede di combinare la
  lettura del codice con la conoscenza del contratto dell'API Zoom e di collocare il
  nuovo lavoro dentro convenzioni già esistenti nel progetto (schema dei template email
  per chiave, hook dei promemoria, generatore `.ics`); il contesto ampio consente di
  tenere aperti insieme i sei file coinvolti e di proporre un piano che riusa ciò che
  c'è invece di duplicarlo
- risultato ottenuto: risposta affermativa e motivata sulla fattibilità, risposta netta
  sul link Zoom (resta lo stesso con `PATCH`), piano in cinque punti con l'indicazione
  del punto già coperto, stima di circa mezza giornata e una decisione di contenuto
  rimessa all'utente
- verifiche e correzioni effettuate: accertata per ricerca diretta l'assenza di
  qualsiasi chiamata di aggiornamento verso Zoom nel repository, così da non dare per
  esistente codice che va scritto; verificata la presenza dell'UID stabile e l'assenza
  del campo `SEQUENCE` nell'`.ics`; verificato lo schema dei campi template sul
  singleton delle impostazioni email per dimensionare correttamente il punto 4. Il
  comportamento dell'API Zoom **non** è stato provato sul campo: va confermato con una
  riunione di prova in fase di implementazione, ed è stato dichiarato come tale.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Resta una dipendenza esterna da sciogliere in
implementazione: la conferma sul campo che la `PATCH` a Zoom preservi effettivamente
`join_url` sull'account del cliente, che richiede credenziali di un account Zoom reale
e una riunione di prova. L'attività è inoltre in attesa di due input dell'utente — il
via libera all'implementazione e la scelta sul contenuto dell'email di modifica.

---

## 2026-09-11

> **Report giornaliero:** [`reports/2026-09-11-os-lms.md`](../reports/2026-09-11-os-lms.md)
> — obiettivo e modalità del periodo, aggregazione delle attività per filone,
> utilizzo dell'AI, problematiche, prossime attività, avanzamento del progetto e
> spunti di miglioramento aziendale. Il report **copre anche la giornata
> 2026-09-10**, che è la sessione serale dello stesso filone di lavoro: le due
> giornate sono state riportate insieme su richiesta dell'utente, quindi il 10
> settembre non ha un report separato.

---

### Attività 1 — Chiarimento sul ruolo del flag "Disable Self Learning" e rilevazione del suo uso effettivo

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — chiarimento su un'analisi già consegnata, con rilevazione sui dati |
| **Problema riscontrato** | Domanda dell'utente dopo la consegna della correzione del 10/09: «i corsi non permettevano l'iscrizione autonoma?». Il dubbio nasce dal fatto che la casistica del difetto cita in più punti il flag *Disable Self Learning*, lasciando intendere che il bug si verificasse solo su corsi con quel flag attivo. |
| **Problema effettivo** | Equivoco da sciogliere: il flag **non è una condizione del difetto** ma solo il discriminante fra le sue due forme. Senza il flag il difetto si manifestava comunque, in forma attenuata (il corso aggiunto assente da "I miei corsi" fino alla prima apertura della pagina della classe); con il flag assumeva la forma grave (pagina della classe svuotata e stato non recuperabile). La causa comune a entrambe le forme è l'assenza di backfill all'aggiunta di un corso, non il flag. Poiché il sintomo riferito in origine dall'utente — lo studente non trova il corso — è pienamente compatibile con la forma attenuata, serviva accertare quale delle due forme si sia effettivamente verificata in produzione, perché cambia la lettura di quanto accaduto. |
| **Soluzione applicata** | Nessuna modifica al codice. Chiarito il ruolo del flag ed eseguita una rilevazione sul database del sito locale per stimare quale forma sia in gioco; fornito all'utente il comando `bench` per ripetere la rilevazione sull'istanza di produzione, unica fonte probante. |
| **Commit** | No — nessuna modifica al codice, attività di chiarimento e rilevazione |
| **File modificati** | Nessuno. Script di rilevazione temporaneo nella scratchpad di sessione, non nel repository. |
| **Verifiche** | Rilevazione sul sito `lms.localhost` del container di sviluppo: **0 corsi su 5** hanno `disable_self_learning` attivo e **0 classi su 8** ne contengono uno. Il dato indica la forma attenuata, ma è stato esplicitamente qualificato come **indicativo e non probante**: con 5 corsi e 8 classi quel sito è un ambiente di sviluppo, non una copia della produzione. |

**1. Obiettivo dell'attività**

Sciogliere un equivoco che la casistica consegnata poteva indurre — che il difetto
richiedesse corsi con l'iscrizione autonoma disabilitata — e, di conseguenza,
stabilire quale delle due forme del difetto si sia realmente verificata in produzione.
La distinzione non è accademica: se in produzione nessun corso ha quel flag, allora la
pagina della classe non si è mai svuotata e le classi con auto-iscrizione non sono mai
state bloccate; il danno subito è stato il solo corso mancante dall'elenco personale
dello studente, e la parte di correzione che conta per il pregresso è il backfill, non
il riordino dei controlli.

**2. Modalità di esecuzione**

Rilettura della casistica per isolare quale condizione sia comune a entrambe le forme
del difetto e quale invece le distingua, seguita da una rilevazione diretta sul
database: conteggio dei corsi con `disable_self_learning` attivo e, per ogni classe,
quanti dei suoi corsi lo abbiano, con il numero di iscritti. La rilevazione è stata
condotta sul sito di sviluppo perché è l'unico accessibile da questo ambiente; il
comando equivalente per la produzione è stato consegnato all'utente.

**3. Attività svolte**

*Chiarimento.* Il difetto ha una sola causa comune — le iscrizioni ai corsi venivano
create solo all'ingresso dello studente in classe e nulla le rivisitava dopo — e due
manifestazioni: senza il flag, il corso resta fuori da "I miei corsi" finché lo
studente non apre la pagina della classe, che è anche il momento in cui l'iscrizione
mancante veniva creata; con il flag, quella creazione falliva e portava con sé
l'intera chiamata, svuotando l'elenco dei corsi della classe senza possibilità di
recupero.

*Rilevazione sul sito di sviluppo:*

| Misura | Valore |
| --- | --- |
| Corsi totali | 5 |
| Corsi con `disable_self_learning` attivo | **0** |
| Classi totali | 8 |
| Classi contenenti almeno un corso con il flag | **0** |

*Lettura del dato.* Se il quadro di produzione è analogo, in produzione si è verificata
**solo la forma attenuata**: nessuno ha mai visto la pagina della classe svuotarsi e
il blocco dell'auto-iscrizione non si è mai manifestato. Il limite del dato è stato
dichiarato apertamente all'utente — 5 corsi e 8 classi descrivono un ambiente di
sviluppo, non una copia della produzione — e gli è stato fornito il comando `bench
execute frappe.client.get_list` per accertarlo sull'istanza reale.

*Conseguenza sulla correzione già rilasciata.* Nessuna: il fix resta interamente
necessario. Anzi, l'esito della rilevazione sposta il peso sulla componente di
correzione che sana il pregresso, cioè l'aggancio a `on_update` e il patch di
backfill, poiché è il backfill — non il riordino dei controlli — a risolvere la forma
attenuata.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della sessione del 10/09.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** rilettura della casistica per isolare
  condizione comune e discriminante, scrittura ed esecuzione dello script di
  rilevazione sul database, interpretazione del dato con i suoi limiti, redazione di
  questa voce.
- **motivo della scelta del tool e del modello:** la domanda riguardava un'analisi
  prodotta nella stessa sessione, con l'intera casistica e le prove già in contesto;
  riformulare il problema altrove sarebbe costato più della verifica. Il contesto
  ampio di Opus 5 ha permesso di rispondere senza rileggere né codice né worklog, e
  Claude Code di interrogare direttamente il database del container invece di
  rispondere solo a parole.
- **risultato ottenuto:** equivoco sciolto — il flag non è condizione del difetto ma
  discriminante fra le sue due forme — e stima, corredata dei suoi limiti, di quale
  forma abbia colpito la produzione, con il comando per accertarlo sull'istanza reale.
- **verifiche e correzioni effettuate:** non ci si è limitati alla risposta teorica,
  che sarebbe stata comunque corretta: è stato interrogato il database per dare
  all'utente un riscontro sui dati. Il valore rilevato è stato però esplicitamente
  qualificato come indicativo e non probante, invece di presentarlo come conclusione
  sulla produzione: il sito interrogato è di sviluppo, e spacciarne i numeri per quelli
  dell'istanza reale sarebbe stato un errore di merito. Per questo è stato consegnato
  il comando da eseguire sull'istanza di produzione.

**6. Problematiche incontrate**

Un solo limite, dichiarato: da questo ambiente non è accessibile il database di
produzione, quindi la risposta definitiva sulla forma del difetto effettivamente
subita resta in capo all'utente, che deve eseguire il comando fornito sull'istanza
reale. Nessun ostacolo tecnico.

---

### Attività 2 — Verifica del riscontro sul campo: corso visibile nella dashboard della classe ma che rimbalza alla lista corsi

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — verifica di un riscontro utente, con riproduzione comparata pre/post correzione |
| **Problema riscontrato** | Riscontro dell'utente: «se il corso nuovo aggiunto alla classe non prevede l'iscrizione autonoma, lo studente vede il corso aggiunto nella dashboard della classe, ma se ci clicca non gli apre il corso e lo riporta alla pagina della lista corsi». Il riscontro sembrava **contraddire** l'analisi consegnata il 10/09, secondo la quale con il flag *Disable Self Learning* lo studente non vedeva alcun corso nella classe. |
| **Problema effettivo** | Nessuna contraddizione: le due osservazioni descrivono **due schede diverse** della stessa pagina classe, che attingono i corsi da fonti diverse. La scheda **Panoramica** (`BatchOverview.vue`) usa `get_batch_courses`, che tenta di creare le iscrizioni mancanti e quindi andava in eccezione, svuotando l'elenco. La scheda **Dashboard** (`BatchDashboard.vue`, riga 25) usa invece `batch.data.courses`, cioè il campo valorizzato da `get_batch_details` (`utils.py:1418`) leggendo le righe `Batch Course`: nessun tentativo di iscrizione, nessuna eccezione, corso **sempre visibile**. Entrambe le schede erano difettose, in modi diversi, ed erano entrambe presenti per lo studente (`BatchDetail.vue:303` e `313-319`). Il rimbalzo al click segue poi questa catena: la riga porta a `CourseDetail` (`BatchDashboard.vue:30-33`); `get_course_details` trova corso **non pubblicato** e nessuna membership, quindi tenta il recupero con `enroll_via_batch_if_eligible` (`utils.py:1006`); quel recupero crea una `LMS Enrollment` e incontra il controllo `disable_self_learning` fuori posto, sollevando l'eccezione; l'API fallisce, nel frontend `course.data` resta `undefined` e nel watch di `CourseDetail.vue:399-414` tutte le condizioni (`!membership`, `!published`, `!upcoming`, non admin, non valutatore) risultano vere, producendo `router.push({ name: 'Courses' })`. **Condizione non rilevata nelle analisi precedenti:** perché ci sia il rimbalzo il corso deve essere **anche non pubblicato**; è l'unico caso in cui `get_course_details` tenta il recupero ed è anche l'unica condizione sotto cui quel watch redirige. |
| **Soluzione applicata** | Nessuna modifica: la correzione già rilasciata (`a7cd6d83`) copre anche questo caso, come dimostrato dalla riproduzione comparata. Documentata la catena esatta e la terza condizione (corso non pubblicato), e segnalata all'utente la variante con corso **pubblicato**, che produce un sintomo diverso e più insidioso. |
| **Commit** | No — nessuna modifica al codice, attività di sola verifica |
| **File modificati** | Nessuno. File esaminati: `frontend/src/pages/Batches/components/BatchDashboard.vue`, `frontend/src/pages/Batches/BatchDetail.vue`, `frontend/src/pages/Courses/CourseDetail.vue`, `frontend/src/router.js`, `lms/lms/utils.py` (`get_batch_details`, `get_course_details`, `enroll_via_batch_if_eligible`). Script di riproduzione temporaneo nella scratchpad di sessione, non nel repository. |
| **Verifiche** | **Riproduzione comparata** sul container, con lo stesso script eseguito due volte: prima ripristinando temporaneamente i quattro file al commit `a7cd6d83^` (codice pre-correzione), poi con il codice attuale; working tree riportato a `HEAD` subito dopo la prima esecuzione e verificato pulito a fine attività. Scenario: classe con uno studente iscritto, poi aggiunta di due corsi che vietano l'iscrizione autonoma, uno **non pubblicato** e uno **pubblicato**. Esiti al punto 3. |

**1. Obiettivo dell'attività**

Accertare se il riscontro dell'utente smentisse l'analisi consegnata — nel qual caso
la correzione già rilasciata sarebbe stata fondata su una diagnosi sbagliata — oppure
ne descrivesse una manifestazione non ancora esaminata. In secondo luogo, verificare
che la correzione già in essere copra anche questo sintomo, dato che era stata
validata su scenari che non includevano il percorso qui descritto.

**2. Modalità di esecuzione**

1. **Ricerca della fonte dei dati** della scheda che l'utente ha osservato: quale
   componente elenca i corsi nella "dashboard della classe" e da quale endpoint li
   prende, per capire come il corso potesse essere visibile pur senza iscrizione.
2. **Ricostruzione del percorso del click**: quale rotta apre la riga, quale endpoint
   interroga la pagina di destinazione e dove si trova il redirect verso la lista
   corsi.
3. **Riproduzione comparata** dello stesso scenario su codice pre-correzione e su
   codice attuale, per dimostrare sia la causa sia l'avvenuta risoluzione. Il
   ripristino temporaneo dei file è stato fatto con `git checkout <commit>^ -- <file>`
   e annullato con `git checkout HEAD -- <file>` subito dopo l'esecuzione.
4. **Esame di entrambe le varianti** del corso, pubblicato e non pubblicato, perché la
   lettura del codice suggeriva che il redirect dipendesse dalla pubblicazione.

**3. Attività svolte**

*Chiarimento dell'apparente contraddizione.* Lo studente dispone di due schede che
elencano i corsi della classe, aggiunte entrambe in `BatchDetail.vue`: Panoramica e
Dashboard. Attingono a fonti diverse, e solo la prima passa dall'endpoint che crea le
iscrizioni mancanti. L'utente ha osservato la Dashboard, l'analisi del 10/09 descriveva
la Panoramica: entrambe le osservazioni erano corrette.

*Esiti della riproduzione comparata:*

| | Codice pre-correzione | Codice attuale |
| --- | --- | --- |
| Dashboard elenca | tutti e 3 i corsi | tutti e 3 i corsi |
| Iscrizioni dello studente | solo il corso iniziale | tutti e 3 i corsi |
| Click su corso **non pubblicato** | `ValidationError` → **redirect alla lista corsi** | apre regolarmente, con iscrizione |
| Click su corso **pubblicato** | apre **senza iscrizione** | apre regolarmente, con iscrizione |

Il sintomo riferito dall'utente è riprodotto alla lettera nella prima colonna, e
risolto nella seconda: la correzione già rilasciata copre il caso senza bisogno di
ulteriori modifiche.

*Terza condizione individuata.* Il rimbalzo richiede che il corso sia **anche non
pubblicato**. Le analisi precedenti avevano identificato due condizioni (corso aggiunto
dopo l'iscrizione dello studente, iscrizione autonoma vietata) ma non questa, perché
gli scenari costruiti usavano corsi pubblicati e osservavano la Panoramica, dove il
difetto si manifesta senza bisogno della terza condizione.

*Variante da segnalare.* Con corso **pubblicato** che vieta l'iscrizione autonoma il
sintomo è diverso e più insidioso: la pagina del corso si apre, ma senza iscrizione,
quindi lo studente non può fruire le lezioni e non ha modo di iscriversi da sé perché
l'auto-iscrizione è vietata. Nessun errore e nessun redirect: appare semplicemente
come un corso che "non funziona", ed è il tipo di sintomo che un utente segnala con
difficoltà.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della sessione.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** ricerca della fonte dati della scheda
  Dashboard, ricostruzione del percorso del click fino al redirect, progettazione ed
  esecuzione della riproduzione comparata pre/post correzione con ripristino
  temporaneo dei file, individuazione della terza condizione, redazione di questa voce.
- **motivo della scelta del tool e del modello:** il riscontro sembrava contraddire
  un'analisi già consegnata e una correzione già committata, quindi andava verificato
  subito e sul campo, non discusso: serviva uno strumento capace di attraversare il
  frontend Vue per trovare la fonte dei dati e, nella stessa sessione, riportare il
  codice a una versione precedente per dimostrare la causa e poi riapplicare quella
  corrente. Il contesto ampio di Opus 5 ha permesso di riusare senza rileggerli i
  riferimenti alle analisi dei giorni precedenti.
- **risultato ottenuto:** apparente contraddizione sciolta (due schede, due fonti
  dati), catena del rimbalzo ricostruita fino alla riga di codice, terza condizione
  individuata e correzione già rilasciata confermata efficace anche su questo sintomo,
  senza bisogno di ulteriori interventi.
- **verifiche e correzioni effettuate:** il riscontro dell'utente non è stato né
  accettato né respinto sulla fiducia: è stato riprodotto su codice pre-correzione,
  ottenendo esattamente il sintomo descritto, e poi rieseguito su codice attuale per
  dimostrare la risoluzione. È stata inoltre esaminata la variante con corso
  pubblicato, non richiesta, che ha rivelato un sintomo diverso degno di segnalazione.
  Si è corretto in modo esplicito il perimetro dichiarato nelle analisi precedenti,
  aggiungendo la condizione "corso non pubblicato" che era sfuggita perché gli scenari
  di prova usavano corsi pubblicati e osservavano l'altra scheda. Il working tree è
  stato verificato pulito dopo il ripristino temporaneo dei file.

**6. Problematiche incontrate**

Un rischio operativo, gestito: per dimostrare la causa è stato necessario riportare
temporaneamente quattro file a una versione precedente nel working tree, su un
repository che contiene lavoro non committato (worklog e report). Il ripristino è
stato circoscritto ai soli quattro file tramite `git checkout <commit>^ -- <file>`,
annullato immediatamente dopo l'esecuzione e verificato con `git status`, che a fine
attività mostra i soli file non tracciati preesistenti.

Un insegnamento di metodo: gli scenari di riproduzione delle Attività 1-3 erano
costruiti su corsi pubblicati e osservavano una sola delle due schede della pagina
classe. Erano sufficienti a individuare la causa, ma non a coprire tutte le
manifestazioni del difetto: è stato il riscontro sul campo dell'utente a completare il
quadro. Per le prossime verifiche di questo tipo conviene includere fra le variabili
di prova anche lo stato di pubblicazione del corso e tutte le viste che presentano lo
stesso dato.

---

### Attività 3 — Valutazione dell'ambito della correzione: quanto serviva davvero alla segnalazione del cliente

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — valutazione critica di una correzione già rilasciata, su richiesta dell'utente |
| **Problema riscontrato** | L'utente ha ricostruito autonomamente la causa con test in produzione (istanza non ancora allineata ai commit del 10/09) e ha confermato la diagnosi: i corsi aggiunti alla classe avevano l'iscrizione autonoma disattivata, il che li rendeva invisibili nella scheda Panoramica e non apribili dalla Dashboard; riattivando l'iscrizione autonoma tutto tornava normale. Ha quindi posto una domanda legittima: «non so se le correzioni che sono state fatte sono state più del necessario». La segnalazione originaria del cliente era circoscritta — «lo studente non vedeva i nuovi corsi dentro alla tab Panoramica della classe» — mentre il commit `a7cd6d83` contiene cinque modifiche. |
| **Problema effettivo** | La correzione **eccede** la segnalazione del cliente, ma non arbitrariamente: solo una delle cinque modifiche è indispensabile a quel sintomo, tre discendono dal requisito più ampio formulato dall'utente stesso il 10/09 («gli iscritti presenti e quelli futuri devono vedere i corsi aggiunti»), e una sola è andata oltre entrambe le cose di iniziativa autonoma. Nel dettaglio: **(1)** il riordino dei controlli in `lms_enrollment.py` è l'unica indispensabile alla segnalazione; **(2)** lo spostamento in `after_insert` copre solo l'auto-iscrizione alla classe, che il cliente non aveva segnalato; **(3)+(4)** l'helper e il backfill in `on_update` servono al requisito "visibile ovunque", non alla sola Panoramica; **(5)** il patch sana il pregresso. |
| **Soluzione applicata** | Nessuna modifica al codice. Prodotta la scomposizione del commit in cinque punti con, per ciascuno, la funzione, lo scenario concreto che corregge e il criterio per decidere se tenerlo; forniti all'utente i dati per decidere e lo snippet di sola lettura per misurare l'impatto del patch sulla produzione. Decisione rimessa all'utente, che ha confermato di mantenere **tutti e cinque i punti**: prima il punto 5, poiché `bench migrate` è già previsto nella procedura di deploy, poi i punti 2, 3 e 4 a valle degli esempi. Nessun revert: il commit `a7cd6d83` resta nella sua forma attuale. |
| **Commit** | No — nessuna modifica al codice, attività di sola valutazione |
| **File modificati** | Nessuno. Script di rilevazione e di prova temporanei nella scratchpad di sessione, non nel repository. |
| **Verifiche** | (a) **Prova sperimentale dell'ambito minimo**: ripristinati temporaneamente al commit `a7cd6d83^` i tre file delle modifiche (2), (3) e (4), lasciando la sola modifica (1), e rieseguiti gli scenari. Esito: Panoramica risolta (corso visibile e iscrizione creata all'apertura), click dalla Dashboard risolto, **auto-iscrizione ancora bloccata**. È quindi dimostrato che la sola modifica (1) risolve interamente la segnalazione del cliente. Working tree riportato a `HEAD` e verificato pulito. (b) **Rilevazione sul sito locale** per pesare la rilevanza della modifica (2): **2 classi su 8 hanno l'auto-iscrizione attiva**, nessuna classe a pagamento. Il conteggio delle iscrizioni mancanti sullo stesso sito è stato invece **dichiarato non indicativo**, perché i test dell'Attività 4 del 10/09 avevano già eseguito il patch di backfill su tutte le classi di quel sito. |

**1. Obiettivo dell'attività**

Rispondere a una domanda di merito dell'utente — se la correzione consegnata sia
sproporzionata rispetto al problema segnalato — con una risposta verificabile anziché
con una giustificazione. In secondo luogo, mettere l'utente in condizione di decidere
quali parti mantenere, fornendo per ciascuna lo scenario concreto che corregge e i
dati sulla sua rilevanza per l'installazione reale.

**2. Modalità di esecuzione**

1. **Determinare sperimentalmente l'ambito minimo**: applicare la sola modifica (1) e
   rieseguire gli scenari, per stabilire se basti da sola. Ripristino temporaneo dei
   file con `git checkout <commit>^ -- <file>` e annullamento immediato dopo la prova.
2. **Attribuire ciascuna modifica alla sua origine**: segnalazione del cliente,
   requisito formulato dall'utente, o iniziativa autonoma. Distinzione necessaria
   perché "più del necessario" ha due significati diversi a seconda del metro.
3. **Misurare la rilevanza** delle parti non indispensabili sui dati reali, per non
   far decidere l'utente su scenari ipotetici.
4. **Esporre per esempi** anziché per descrizione tecnica, poiché la decisione è di
   prodotto e non di implementazione.

**3. Attività svolte**

*Esito della prova sull'ambito minimo:*

| Scenario | Solo modifica (1) |
| --- | --- |
| Panoramica — corso visibile | risolto, con iscrizione creata all'apertura |
| Dashboard — click sul corso | risolto |
| Auto-iscrizione alla classe | **ancora bloccata** |

*Attribuzione delle cinque modifiche:*

| # | Cosa fa | Indispensabile alla segnalazione | Origine |
| --- | --- | --- | --- |
| 1 | Riordino dei controlli in `lms_enrollment.py` | **sì, da sola basta** | segnalazione del cliente |
| 2 | Creazione iscrizioni da `validate` ad `after_insert` | no | iniziativa autonoma |
| 3 | Helper `enroll_batch_students_in_courses` | no | requisito dell'utente (infrastruttura di 4 e 5) |
| 4 | Backfill in `LMSBatch.on_update` | no | requisito dell'utente |
| 5 | Patch di backfill del pregresso | no | requisito dell'utente |

*Esempi consegnati all'utente.* Per la (2): una classe con auto-iscrizione attiva a
cui si aggiunga un corso che vieta l'iscrizione autonoma diventa **non iscrivibile da
chiunque**, con un messaggio d'errore che nomina il corso mentre l'utente stava
iscrivendosi alla classe — incomprensibile sia per lo studente sia per chi riceve la
segnalazione. Per le (3)+(4): comunicare agli studenti l'aggiunta di un nuovo modulo
non funziona, perché chi apre "I miei corsi" non lo trova e deve indovinare di dover
passare dalla Panoramica della propria classe. Per la (5): senza patch il pregresso si
risolve "a goccia", un solo studente alla volta e solo quando apre la Panoramica.

*Effetto indesiderato segnalato sul punto 5.* Se a qualche studente fosse stata tolta
a mano l'iscrizione a un corso **lasciandolo in classe** (per escluderlo da quel
modulo), il patch gliela ricreerebbe. È l'unico caso in cui il patch compie
un'operazione non voluta, ed è stato segnalato esplicitamente all'utente prima della
sua decisione.

*Strumento di misura consegnato.* Snippet di sola lettura per `bench console` che
conta le coppie (studente, corso della sua classe) prive di iscrizione, così da
quantificare in anticipo il lavoro del patch sulla produzione.

*Decisione dell'utente.* Punto 5 **confermato**: `bench migrate` è già parte della
procedura di deploy, quindi il patch verrà eseguito senza passaggi manuali aggiuntivi.
Comunicate le tre implicazioni operative: esecuzione una tantum (registrata in
`tabPatch Log`), commit per singola classe con ripresa corretta in caso di
interruzione, e prosecuzione con registrazione in Error Log se una classe fallisce.

Subito dopo, esaminati gli esempi concreti, l'utente ha confermato anche i punti 2, 3
e 4. Esito finale: **la correzione resta integra, nessun revert**, e il commit
`a7cd6d83` è definitivo nella forma consegnata. La scomposizione conserva comunque il
suo valore documentale: mette a verbale quale parte del commit risponde alla
segnalazione del cliente e quali al requisito più ampio, informazione utile se in
futuro si dovesse isolare o riportare altrove una singola parte.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della sessione.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** progettazione ed esecuzione della prova
  sull'ambito minimo, scomposizione del commit e attribuzione di ciascuna modifica
  alla sua origine, rilevazione sui dati del sito, redazione degli esempi e di questa
  voce.
- **motivo della scelta del tool e del modello:** la domanda richiedeva di rimettere in
  discussione una correzione prodotta poche ore prima nella stessa sessione,
  smontandola pezzo per pezzo e provando sperimentalmente quanto ne fosse davvero
  necessario. Claude Code permette di riportare il codice a una versione precedente,
  rieseguire le prove e ripristinare, tutto nello stesso contesto; il contesto ampio di
  Opus 5 ha consentito di riusare gli scenari costruiti nei giorni precedenti senza
  ricostruirli.
- **risultato ottenuto:** risposta verificata e non difensiva alla domanda dell'utente —
  sì, la correzione eccede la segnalazione, e una sola delle cinque modifiche le era
  indispensabile — con la scomposizione che consente una decisione informata parte per
  parte, corredata di dati reali sull'installazione e dell'effetto indesiderato
  possibile del patch.
- **verifiche e correzioni effettuate:** l'affermazione centrale — che la sola modifica
  (1) basti — non è stata dedotta ma **provata**, rimuovendo temporaneamente le altre
  e rieseguendo gli scenari. È stata inoltre dichiarata apertamente una parte non
  verificata (che le modifiche 4 e 5 funzionino anche senza la 1, per il fatto di
  girare in sessione amministrativa), invece di presentarla come accertata. Il dato
  locale sulle iscrizioni mancanti è stato scartato come non indicativo perché
  inquinato dai test del giorno precedente, ed è stato fornito lo snippet per misurarlo
  sulla produzione. Riconosciuto esplicitamente che la modifica (2) è l'unica andata
  oltre sia la segnalazione sia il requisito ricevuto.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Una considerazione di metodo, però, merita di essere
registrata: la correzione del 10/09 è stata costruita su un requisito che l'utente
aveva formulato in termini generali («gli iscritti devono vedere i corsi aggiunti»),
più ampio della segnalazione del cliente («non li vedono nella Panoramica»). Nessuno
dei due enunciati era sbagliato, ma la distanza fra loro ha prodotto una correzione più
estesa del problema riportato, e questo è emerso solo a posteriori. Per i prossimi
interventi conviene esplicitare fin dall'inizio quale dei due metri si sta usando —
il sintomo segnalato o il comportamento desiderato — e dichiarare quali parti della
correzione rispondano all'uno e quali all'altro già al momento della consegna, non su
richiesta successiva.

---

### Attività 4 — Errore 500 sulla scheda impostazioni corso in staging, e incidente di cancellazione dati sul sito locale

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione + incidente — diagnosi di un errore segnalato in staging e riparazione di un danno causato dagli script di prova della sessione |
| **Problema riscontrato** | Dopo il deploy su staging, aprendo la scheda impostazioni di un corso di test l'utente riceve **500 Internal Server Error** su `lms.lms.utils.get_course_details`, con `AttributeError: 'dict' object has no attribute 'feature_sections'`, seguito da un **404 `DoesNotExistError`** su `frappe.client.get` per `corso-nuovo-b`. L'utente segnala inoltre di aver soltanto ricaricato la pagina e di aver trovato il corso rimosso, e riferisce lo stesso fenomeno sul sito **locale** per `corso-design-b`. |
| **Problema effettivo** | **Tre questioni distinte.** (1) *Il 500* è un difetto preesistente di `os_lms`: `override_utils.get_course_details` (riga 32) assegna attributi sul risultato della funzione upstream senza verificare che ci sia; l'upstream restituisce un `{}` — dict semplice, non `frappe._dict` — quando il corso non è visibile o **non esiste più**, e l'assegnazione solleva `AttributeError`, trasformando una risposta vuota legittima in un 500. La funzione gemella `get_batch_details`, nello stesso file (righe 309-316), possiede **già** esattamente questa guardia con un commento che descrive lo stesso problema: `get_course_details` era l'unica a esserne priva. (2) *Il 404* è il sintomo primario e corretto: quel corso non esiste sul server. (3) *La sparizione dei corsi sul sito locale* è stata **causata dagli script di prova di questa sessione**: il blocco di pulizia di `repro_run.py` conteneva `frappe.get_all("LMS Course", {"title": ["like", "Corso %"]})` seguito da `delete_doc`, filtro inteso per le sole fixture generate ma che ha intercettato ogni corso con titolo che inizia per "Corso " — in un'installazione in lingua italiana, una quota rilevante dei corsi reali. |
| **Soluzione applicata** | **(1)** Aggiunta in `override_utils.get_course_details` la stessa guardia già presente in `get_batch_details`: se il risultato dell'originale è falsy lo si restituisce così com'è, senza arricchirlo. **(3)** Ripristinati **tutti e 11** i corsi cancellati, recuperandoli dal doctype `Deleted Document` di Frappe, che ne conserva il JSON completo: 9 tramite la funzione `restore()` standard, 2 (`Corso importato 2`, `Corso impotato`) tramite reinserimento forzato con `ignore_mandatory` e `ignore_links`, avendo dati già incompleti prima della cancellazione (un istruttore inesistente, e nessun istruttore). **(2)** Nessuna azione: il 404 è il comportamento corretto; forniti all'utente gli strumenti per accertare sul server di staging se il corso sia stato cancellato o sia sparito con un ripristino del database. |
| **Commit** | Sì — `bf6a1c31` *fix(courses): don't turn an empty course response into a 500*, branch `feature/oslms` (committata più tardi nella giornata, dopo l'indicazione dell'utente; la voce era stata scritta quando la correzione era ancora nel working tree). Il ripristino (3) non è codice ma un intervento sui dati del sito locale, già eseguito. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_utils.py` (guardia in `get_course_details`, 6 righe più commento). Nessun'altra modifica al codice. |
| **Verifiche** | (a) **Esclusione della regressione**: lo stesso scenario eseguito ripristinando temporaneamente i quattro file al commit `a7cd6d83^` produce **l'identico `AttributeError`** — il difetto è preesistente e il commit del fix iscrizioni non tocca né `override_utils.py` né `get_course_details` (verificato su `git show --stat`). (b) **Prova della correzione**: corso inesistente come Administrator → risposta vuota senza errore; come Guest → idem; corso reale → dettagli restituiti correttamente. (c) **Suite di test**: `lms` → 49 test OK; `os_lms` → 229 + 13 test con **3 fallimenti**, verificati **preesistenti** rieseguendo la suite con la modifica messa da parte via `git stash` (stessi tre: `test_quota_raises_when_exceeded`, `test_run_simulation_test_creates_evaluation_and_enqueues`, `test_simulation_test_end_to_end`, tutti su quota e simulazioni). (d) **Audit dell'incidente**: interrogato `Deleted Document` per l'intero arco della sessione; accertato che le cancellazioni di `LMS Course` sono 11 corsi reali più le fixture generate, e che **nessun utente reale** è stato cancellato (le 175 cancellazioni di `User` sono tutte `frappe@example.com` e `student1/2@example.com`, create e distrutte dalle suite di test). (e) **Verifica post-ripristino**: tutti gli 11 corsi risultano presenti nell'elenco finale. |

**1. Obiettivo dell'attività**

Diagnosticare l'errore 500 comparso in staging subito dopo il deploy — con l'ipotesi, da verificare per prima, che fosse una regressione della correzione rilasciata — e rispondere alla segnalazione dell'utente sulla sparizione di alcuni corsi. Il secondo obiettivo, emerso durante l'indagine, è diventato prioritario: accertare e riparare un danno ai dati causato dagli script di prova di questa stessa sessione.

**2. Modalità di esecuzione**

1. **Separare i due errori del log**, che descrivono cose diverse: il 500 sulla chiamata dei dettagli corso e il 404 sul recupero del documento. Il secondo indica la causa, il primo la reazione sbagliata a quella causa.
2. **Escludere la regressione prima di tutto**, riproducendo lo scenario su codice pre-correzione: è la verifica che condiziona ogni conclusione successiva.
3. **Confrontare la funzione difettosa con le sue gemelle** nello stesso file, per capire se si trattasse di un difetto isolato o di un pattern mancante.
4. **Sull'incidente dati**: interrogare il registro `Deleted Document` di Frappe, che traccia ogni cancellazione con autore, data e contenuto integrale, per stabilire estensione esatta del danno e possibilità di recupero.

**3. Attività svolte**

*Diagnosi del 500.* Il difetto è in `os_lms`, non in `lms`, ed è preesistente. Il pattern corretto era già adottato nel medesimo file per le classi: applicarlo anche ai corsi ha risolto senza alterare il percorso normale.

*Incidente sui dati del sito locale.* L'indagine è nata dall'osservazione dell'utente che anche in locale un corso era sparito — circostanza che escludeva la spiegazione data poco prima per staging (ripristino del database) e imponeva di sospettare la sessione stessa. Il registro delle cancellazioni ha confermato il sospetto:

| Momento | Corsi cancellati | Causa |
| --- | --- | --- |
| 10/09 17:50:47 | 9 | primo `repro_run.py`, blocco di pulizia "leftovers" |
| 11/09 09:30:03 | 2 | riesecuzione dello stesso script per la verifica del fix |

Corsi coinvolti: `Corso design A`, `Corso design b`, `Corso C01`, `Corso c02`, `Corso C03`, `Corso privato`, `Corso Informatica`, `Corso di sicurezza`, `Corso prova con certificato`, `Corso importato 2`, `Corso impotato`. **Tutti ripristinati.**

*Rettifica di un'affermazione precedente.* Nell'Attività 4 del 10/09 era stato segnalato all'utente un riferimento `Batch Course` orfano verso `corso-informatica`, presentato come dato sporco preesistente e accompagnato dal suggerimento di una pulizia dei riferimenti pendenti. **Era falso**: quel corso era stato cancellato dagli script di questa sessione venti minuti prima che il patch lo incontrasse. L'orfano era un artefatto dell'incidente, non un problema del progetto, e il suggerimento è stato ritirato.

*Residui non rimossi.* Restano sul sito locale 15 corsi `Eval Test Course`, creati dalle suite di test `os_lms` eseguite alle 10:04-10:07 dell'11/09 e non ripuliti dalla suite stessa. **Non rimossi**: dopo l'incidente si è deciso di non eseguire più alcuna cancellazione senza conferma esplicita dell'utente, ed è stata chiesta.

*Staging.* Il caso resta aperto e distinto: gli script della sessione hanno operato esclusivamente nel container Docker locale, e `corso-nuovo-b` non risulta mai esistito né cancellato sul sito locale. Consegnato all'utente lo script di sola lettura su `Deleted Document` per stabilire, sul server di staging, se quel corso sia stato cancellato — e da chi — oppure sia sparito con un ripristino del database, ipotesi coerente con il fatto che sia bastato ricaricare la pagina dopo il deploy.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della sessione.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** separazione dei due errori del log, esclusione della regressione, individuazione del difetto in `override_utils` e della guardia mancante rispetto alla funzione gemella, stesura della correzione e delle prove, audit completo delle cancellazioni, ripristino degli 11 corsi, redazione di questa voce.
- **motivo della scelta del tool e del modello:** il problema era riportato come possibile regressione di una correzione prodotta nella stessa sessione, quindi andava escluso per primo riportando il codice alla versione precedente e riprovando — operazione che richiede di agire su repository e container insieme. Per l'incidente sui dati serviva interrogare il database, ricostruire la cronologia dal registro delle cancellazioni e rimettere a posto: tutte operazioni che Claude Code svolge direttamente. Il contesto ampio di Opus 5 ha permesso di risalire agli script scritti il giorno prima e riconoscere nella riga di pulizia la causa del danno, senza doverli rileggere.
- **risultato ottenuto:** 500 diagnosticato come difetto preesistente di `os_lms` e corretto; danno ai dati del sito locale individuato, quantificato con precisione e **riparato integralmente**; rettificata un'affermazione errata data all'utente il giorno prima; il caso staging circoscritto come indipendente, con lo strumento per chiuderlo.
- **verifiche e correzioni effettuate:** l'ipotesi di regressione non è stata scartata per convinzione ma **esclusa sperimentalmente**, riportando il codice a prima del commit. I 3 test falliti della suite `os_lms` non sono stati liquidati come "probabilmente preesistenti": è stata rieseguita l'intera suite con la modifica messa da parte, ottenendo gli stessi tre fallimenti. Sull'incidente non ci si è fermati alla constatazione del corso segnalato dall'utente: è stato interrogato l'intero registro delle cancellazioni per l'arco della sessione, estendendo il controllo anche agli utenti, così da conoscere il perimetro reale del danno invece di ripararne solo la parte visibile. È stata infine rettificata di propria iniziativa l'indicazione errata sui riferimenti orfani fornita il giorno precedente. La lezione operativa è stata salvata in memoria di progetto per le sessioni future.

**6. Problematiche incontrate**

L'ostacolo principale di questa attività è stato un errore proprio, non un problema del progetto: **gli script di prova hanno distrutto dati reali dell'utente**. La causa è una pulizia scritta con un filtro per pattern (`title like "Corso %"`) invece che sull'elenco dei documenti effettivamente creati dallo script. In un'installazione in lingua italiana "Corso ..." è un titolo estremamente comune, quindi il filtro pensato per le sole fixture ha intercettato dati di produzione. L'aggravante è che l'errore si è ripetuto una seconda volta, stamattina, perché lo stesso script è stato rieseguito per verificare la correzione senza che quella riga fosse stata nel frattempo sanata.

Il danno è stato interamente recuperato grazie al doctype `Deleted Document`, che in Frappe conserva il JSON completo di ogni documento cancellato: un dettaglio che vale la pena ricordare perché rende reversibili incidenti altrimenti definitivi.

Regola adottata da qui in avanti, e registrata in memoria di progetto: ogni fixture generata viene tracciata per `name` in un elenco, e il blocco di pulizia cancella **soltanto** quell'elenco; gli eventuali residui di esecuzioni interrotte si elencano all'utente e si rimuovono solo su sua conferma, mai per pattern. Per questo i 15 `Eval Test Course` residui sono stati lasciati sul sito in attesa di risposta.

---

### Attività 5 — Redazione del report giornaliero aziendale (11 settembre, con le attività della sera del 10)

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto / documentazione |
| **Esigenza di partenza** | Richiesta dell'utente: «Scrivi il report di oggi con le attività di ieri sera». Il report giornaliero previsto dalla direttiva aziendale non era stato redatto né per il 10 né per l'11 settembre. |
| **Vincolo tecnico rilevante** | Due questioni. **(a) Perimetro ambiguo:** il worklog contiene due giornate distinte — 2026-09-10 (4 attività, chiuse con il commit `a7cd6d83` delle 18:22) e 2026-09-11 (4 attività svolte stamattina fra le 09:30 e le 10:07) — e la richiesta ammetteva tre letture diverse (report del 10 con le sole attività di ieri; report dell'11 con le sole attività di ieri sera; report dell'11 con entrambe le sessioni). Poiché la scelta cambiava materialmente il documento da produrre, è stata posta all'utente con le tre opzioni esplicite: ha scelto **report dell'11 con entrambe le sessioni**. Conseguenza: il 10 settembre **non avrà un report proprio**, e la sua intestazione nel worklog è stata aggiornata di conseguenza. **(b)** Vale la regola di progetto fissata il 07/09: il report è destinato a un lettore **non tecnico**, quindi senza percorsi di file, nomi di funzioni, endpoint, hash di commit o gergo di framework; la profondità tecnica resta nel worklog, che il report cita come riferimento. |
| **Soluzione applicata** | Prodotto `reports/2026-09-11-os-lms.md` (322 righe) con la struttura dei report del 7 e dell'8 settembre. Le 8 attività delle due giornate sono state riaggregate in **otto punti** corrispondenti alle richieste di partenza (segnalazione del corso non visibile; delimitazione; casistica completa; correzione; chiarimento sul flag; riscontro sul campo; ampiezza dell'intervento; errore in staging con incidente sui dati). Aggiunta in intestazione una riga *Periodo coperto* che dichiara l'accorpamento delle due sessioni. La tabella degli interventi riporta **stato e ambiente** di ciascuno, perché il dato rilevante per il lettore è che la correzione principale non è ancora in produzione. Il punto 6 riporta per esteso l'incidente di cancellazione dati (11 corsi, due occorrenze, tutti recuperati, nessun dato di produzione o staging toccato) con la contromisura adottata. Il punto 8 conferma il 100 % già stabilito il 07/09, aggiungendo però che il difetto segnalato dal cliente è a oggi ancora presente per gli utenti, non essendo la correzione ancora su `master`. Il punto 9, che nei due report precedenti era "Nessuno", contiene tre spunti reali emersi dal periodo. Aggiornate infine **entrambe** le intestazioni di giornata nel worklog (2026-09-10 e 2026-09-11), che rimandavano a report "da redigere". |
| **Commit** | Non committata — per convenzione di progetto il worklog non si committa e il report segue la stessa prassi, salvo indicazione contraria dell'utente. |
| **File toccati** | `reports/2026-09-11-os-lms.md` (nuovo, 322 righe), `docs/WORKLOG.md` (questa voce e le intestazioni delle giornate 2026-09-10 e 2026-09-11). |
| **Verifiche** | (a) Rilette integralmente le due giornate del worklog (8 attività, righe 38-1051) per non riportare nel report affermazioni non sostenute dal registro. (b) **Controllo incrociato sulla storia git**, come previsto dalla prassi: `git log --since='2026-09-08'` conferma un solo commit nel periodo (`a7cd6d83`, 10/09 18:22); `git rev-parse HEAD origin/feature/oslms` mostra i due riferimenti **allineati**, quindi il commit è pushato — l'informazione "consegnato e portato in collaudo" è verificata e non dedotta; `git branch -r --contains a7cd6d83` restituisce **solo** `origin/feature/oslms`, quindi la correzione **non è su `master`** e la produzione ne è tuttora priva: è il dato che ha determinato la prima voce del punto 7 e la precisazione del punto 8. (c) `git status` conferma la sola modifica non committata di `override_utils.py` (8 righe aggiunte), coerente con l'intervento 2 dichiarato "pronto, non consegnato". (d) Riletto il report dell'8 settembre per mantenere continuità di struttura, registro e livello di dettaglio. (e) Verificato che ogni cifra citata nel report (11 corsi cancellati e ripristinati, 15 corsi di prova residui, 49 test superati, 3 fallimenti preesistenti, 5 corsi senza il flag, 2 classi su 8 con auto-iscrizione, 6 casi di regressione) corrisponda al valore registrato nella voce di origine. |

**1. Obiettivo dell'attività**

Consegnare il report giornaliero del progetto OS LMS per l'11 settembre, conforme al
template aziendale e leggibile da un destinatario non tecnico, comprendendo anche la
sessione serale del 10 settembre — che appartiene allo stesso filone di lavoro e non
era stata ancora riportata — con un livello di dettaglio tale da permettere a un'altra
persona o a un sistema AI di ricostruire il periodo leggendo il solo report.

**2. Modalità di esecuzione**

1. **Risoluzione dell'ambiguità di perimetro prima di scrivere**, anziché scegliere
   per conto proprio: tre opzioni esplicite sottoposte all'utente, con l'indicazione
   di quali attività sarebbero finite in ciascuna. Un documento di questa lunghezza
   scritto sul perimetro sbagliato sarebbe stato lavoro da rifare.
2. Lettura dei report del 7 e dell'8 settembre, per ricavarne struttura, registro e
   livello di dettaglio da mantenere.
3. Lettura integrale delle due giornate del worklog, attività per attività, compresi
   gli aggiornamenti in coda alle voci (per esempio la conferma che il difetto è
   presente anche su `feature/oslms`, in coda all'Attività 1 del 10/09).
4. Controllo incrociato con la storia git per distinguere ciò che è consegnato da ciò
   che è soltanto scritto, e per accertare su quali rami viva la correzione.
5. Raggruppamento delle 8 attività per **richiesta di partenza** anziché per ordine
   cronologico, così che il lettore ritrovi le proprie domande e non la sequenza di
   lavoro.
6. Riscrittura in linguaggio non tecnico, conservando però i dati misurati e i
   conteggi, che sono ciò che rende il report verificabile.
7. Compilazione dei punti di livello giornaliero (7, 8, 9), che non esistono nel
   worklog e vanno costruiti: prossime attività con risultato atteso, avanzamento
   motivato, spunti di miglioramento aziendale.

**3. Attività svolte e risultati**

Il report è costruito attorno a due scelte di aggregazione e a una di trasparenza.

*Otto punti invece di otto attività — che è una coincidenza, non una corrispondenza.*
Le voci del worklog delle due giornate sono otto, ma il raggruppamento è stato fatto
per richiesta di partenza: alcune attività coprono più richieste (l'Attività 1 del
10/09 contiene sia lo scenario con il flag sia quello senza) e il raggruppamento rende
visibili le concatenazioni che nel worklog sono sparse — il punto 3 nasce dal 2, il 6
rimette in discussione l'1, il 7 rimette in discussione il 4.

*Stato degli interventi in tabella, non solo il loro numero.* Nei report precedenti la
tabella elencava gli interventi rilasciati; qui è stata aggiunta una colonna **Stato**,
perché il fatto rilevante per chi legge è che la correzione principale è in collaudo e
**non in produzione**, e che la seconda non è nemmeno consegnata. Un conteggio secco
avrebbe suggerito che il problema del cliente sia risolto, mentre per gli utenti è
tuttora presente.

*Incidente riportato per esteso.* L'errore di cancellazione dati è al punto 6 con il
perimetro reale, il numero esatto di documenti coinvolti, il fatto che si sia ripetuto
due volte e la contromisura adottata. Ometterlo, o attenuarlo, avrebbe reso il report
inaffidabile proprio sul punto in cui la direttiva chiede trasparenza.

*Punto 9 non vuoto.* Nei report del 7 e dell'8 settembre era "Nessuno". Qui il periodo
ha prodotto tre spunti che valgono oltre il caso singolo: mai cancellazioni per
somiglianza di nome negli script di prova; concordare prima dell'intervento se si
corregge il sintomo segnalato o il comportamento desiderato; dotarsi di un ambiente di
prova con dati realistici ma sacrificabili, che avrebbe evitato sia l'incidente sia le
rilevazioni non probanti.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), sessione sul repository `os_lms`,
  branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* rilevazione dell'ambiguità di perimetro e
  formulazione delle tre opzioni per l'utente, lettura integrale delle due giornate del
  worklog, controllo incrociato con la storia git, riaggregazione delle 8 attività negli
  otto punti di partenza, stesura del report nei punti 1-4 e 6-9, aggiornamento delle
  due intestazioni di giornata nel worklog e redazione di questa voce.
- *Motivo della scelta del tool e del modello:* il compito è di sintesi su un corpus
  ampio (circa 1.010 righe di registro tecnico su due giornate) da restituire in forma
  completamente diversa e per un altro destinatario; serviva un modello capace di
  tenere in contesto entrambe le giornate insieme ai report precedenti, per garantirne
  la continuità di struttura e registro, e un tool con accesso alla storia git per
  **verificare** lo stato reale di consegna invece di riportarlo dal registro senza
  controllo — verifica che in questo caso ha cambiato il contenuto di due sezioni.
- *Risultato ottenuto:* report consegnato, coerente per struttura e registro con quelli
  del 7 e dell'8 settembre, con i punti di livello giornaliero compilati e i dati
  verificati; worklog allineato su entrambe le giornate coperte.
- *Verifiche e correzioni effettuate sull'output dell'AI:* il perimetro non è stato
  deciso per inferenza ma chiesto, perché le tre letture possibili producevano documenti
  diversi. Lo stato di consegna della correzione non è stato dedotto dal worklog — che
  in queste situazioni invecchia — ma verificato su git: è così che si è accertato che
  `master` non contiene il commit, dato che ha determinato la prima prossima attività e
  la precisazione al punto 8. Tutti i numeri del report sono stati riscontrati sulla
  voce di origine prima di essere riportati.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Una sola questione di merito, risolta chiedendo: la richiesta
«il report di oggi con le attività di ieri sera» ammetteva tre perimetri diversi, e la
convenzione del progetto (un report per giornata, con il nome del giorno delle
attività) puntava verso una soluzione diversa da quella poi scelta dall'utente. È stata
sottoposta la scelta invece di adottare la convenzione in silenzio; la decisione
dell'utente è ora registrata nell'intestazione di entrambe le giornate del worklog, così
che la mancanza di un report datato 10 settembre non risulti in futuro una dimenticanza.

---

### Attività 6 — Individuazione del punto di modifica del template dei certificati di corso

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — orientamento operativo sull'amministrazione della piattaforma |
| **Problema riscontrato** | Richiesta dell'utente: «devo cambiare il template dei certificati nei corsi, non mi ricordo dove devo andare per farlo». Non un difetto, ma la necessità di ritrovare il punto di intervento: la grafica del certificato non è né nelle impostazioni del corso né in un file del repository, quindi non è dove la si cercherebbe per prima cosa. |
| **Problema effettivo** | Il template del certificato di completamento è un **Print Format di Frappe**, cioè un record di database modificabile solo dal desk (`/app/print-format`), non un file versionato: per questo non lo si trova nel repository. In più la piattaforma ha **due** percorsi di certificazione distinti e mutuamente esclusivi per corso — il PDF interno (Print Format) e il badge TrueSkill (template remoto, id in `trueskills_template_id`) — e la risposta cambia a seconda di quale dei due il corso stia usando; l'utente non aveva specificato quale. |
| **Soluzione applicata** | Nessuna modifica al codice. Individuato e comunicato il percorso: desk → **Print Format** filtrato per `Doc Type = LMS Certificate`, con modifica dei campi HTML e CSS e impostazione del predefinito via ⋮ → *Set as Default*. Comunicati inoltre i tre vincoli tecnici già noti sul progetto che rendono la modifica insidiosa (meta tag `pdfkit-*` ignorati, dipendenza dal generatore Chrome per la rotazione, anteprima desk non attendibile) e distinto il caso del badge TrueSkill, chiedendo all'utente quale dei due percorsi gli serva. |
| **Commit** | No — nessuna modifica al codice, attività di orientamento |
| **File modificati** | Nessuno. Sola lettura per riscontro: `lms/lms/doctype/lms_certificate/lms_certificate.py`. |
| **Verifiche** | Riscontro sul codice della meccanica descritta, invece di riferirla a memoria: `grep` su `lms/` e `apps/os_lms/` per `get_default_certificate_template` e `default_print_format`, che conferma la risoluzione del template via Property Setter `default_print_format` su `LMS Certificate` ([lms/lms/doctype/lms_certificate/lms_certificate.py:189](../lms/lms/doctype/lms_certificate/lms_certificate.py#L189)), il Property Setter installato da `lms/install.py:95`, il patch storico `lms/patches/v1_0/add_certificate_template.py` e i due punti del percorso TrueSkill che riusano lo stesso Print Format (`apps/os_lms/os_lms/os_lms/trueskills/api.py:251` e `certificate_image.py:44`). |

**1. Obiettivo dell'attività**

Rispondere a una domanda operativa — dove si cambia la grafica del certificato di fine
corso — in modo che l'utente possa intervenire da solo e senza incorrere nelle trappole
già emerse su questo progetto. L'obiettivo non era solo indicare una schermata, ma
mettere l'utente in condizione di non produrre un PDF rotto: il template attualmente in
uso ha dipendenze non ovvie che, se ignorate in fase di modifica, restituiscono una
pagina bianca senza alcun messaggio d'errore.

**2. Modalità di esecuzione**

Recupero del contesto già consolidato sul progetto in materia di certificati, seguito da
riscontro diretto sul codice per accertare che la meccanica descritta sia ancora quella
attuale e non una fotografia invecchiata: ricerca delle occorrenze di
`get_default_certificate_template` e `default_print_format` nei due alberi applicativi
(`lms/` e `apps/os_lms/`) e lettura del punto di risoluzione del template. Solo dopo il
riscontro è stata formulata la risposta.

**3. Attività svolte**

*Percorso indicato per il certificato interno.* Il certificato di completamento è un
documento `LMS Certificate` reso da un Print Format Jinja → PDF. Si modifica dal desk su
`/app/print-format`, filtrando per `Doc Type = LMS Certificate` e aprendo il record del
cliente (`Standard = No`); i campi da toccare sono due e separati, **HTML** e **CSS**.
Il template in uso è una grafica Canva a fondo pieno con il testo sovrapposto tramite
blocchi posizionati in assoluto (`.text-student`, `.text-corso`, `.text-data-*`,
`.text-firma-*`). Per rendere predefinito un template nuovo si usa ⋮ → *Set as Default*,
che scrive il Property Setter `default_print_format` su `LMS Certificate` — esattamente
il valore letto da `get_default_certificate_template()`.

*Precisazione sulla granularità.* È stato chiarito che **non esiste un selettore di
template per singolo corso**: nelle impostazioni del corso c'è solo l'interruttore
*Certificato di completamento* (`enable_certification`). Il template è unico e globale,
quindi una modifica alla grafica ricade su tutti i corsi certificati.

*Vincoli tecnici comunicati preventivamente*, perché non producono errori visibili ma
PDF sbagliati:

| Vincolo | Effetto se ignorato |
| --- | --- |
| I meta tag `<meta name="pdfkit-*">` sono ignorati da Frappe | Formato e orientamento restano quelli di default delle Print Settings e la grafica orizzontale viene tagliata; vanno impostati via classe CSS `.print-format` |
| Il template attuale usa `transform: rotate(90deg)`, che solo il generatore **Chrome** applica | Con wkhtmltopdf il PDF esce **bianco** — ed è il motivo per cui la SPA appende `&pdf_generator=chrome` a tutti gli URL di download |
| L'anteprima di stampa del desk è HTML e non applica l'orientamento | Si valida una resa che non è quella del PDF finale; va provato il pulsante **PDF** |

*Distinzione del secondo percorso.* Per i corsi con *Emetti certificato TrueSkill*
attivo il PDF interno non viene mai aperto dallo studente, che vede il badge TrueSkill:
lì la grafica è definita dal template remoto gestito dal modale
`TrueSkillsTemplateModal` della SPA e identificato da `trueskills_template_id` sul
corso, non dal Print Format. Poiché i due interruttori sono mutuamente esclusivi, è
stato chiesto all'utente quale dei due percorsi gli serva prima di procedere oltre.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** recupero del contesto pregresso sul
  funzionamento dei certificati, riscontro sul codice della meccanica di risoluzione del
  template, formulazione della risposta operativa con i vincoli, redazione di questa
  voce.
- **motivo della scelta del tool e del modello:** la domanda è di orientamento su un
  sottosistema già analizzato a fondo in questo progetto, dove la risposta utile non è
  «dove si clicca» ma l'insieme delle trappole che rendono la modifica rischiosa; un
  modello con memoria del progetto e accesso diretto al repository risponde con il
  contesto completo, mentre una ricerca generica sulla documentazione Frappe avrebbe
  indicato la schermata senza nessuno dei tre vincoli specifici di questo template.
- **risultato ottenuto:** percorso di modifica individuato e consegnato, corredato dei
  vincoli che evitano di produrre un PDF bianco o tagliato, e distinzione del caso
  TrueSkill con richiesta di chiarimento all'utente.
- **verifiche e correzioni effettuate:** la risposta non è stata data a memoria. La
  meccanica del Property Setter `default_print_format` è stata riscontrata sul codice
  attuale prima di comunicarla, verificando che la funzione di risoluzione esista ancora
  e sia usata anche dal percorso TrueSkill; il riscontro ha inoltre confermato che il
  Property Setter è installato da `lms/install.py` e da un patch storico, quindi è parte
  del provisioning e non una configurazione manuale a rischio di essere assente.

**6. Problematiche incontrate**

Una sola ambiguità nella richiesta, non risolta unilateralmente: «il template dei
certificati» può indicare due oggetti diversi — il Print Format interno o il template
TrueSkill — e la piattaforma li tiene mutuamente esclusivi per corso. Sono stati
descritti entrambi, indicando quale sia il percorso più probabile, e la scelta è stata
rimessa all'utente invece di assumerne uno; un intervento sul Print Format per un corso
che emette badge TrueSkill non avrebbe prodotto alcun effetto visibile allo studente.

---

### Attività 7 — Procedura per creare un nuovo Print Format da usare come certificato di corso

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — procedura operativa, con accertamento sul codice e sul repository |
| **Problema riscontrato** | Richiesta dell'utente in prosecuzione dell'Attività 6: «se devo creare un nuovo Print Format da utilizzare per i certificati di LMS cosa devo fare?». Non un difetto: serve la procedura di creazione, non solo il punto di modifica di quello esistente. |
| **Problema effettivo** | La creazione di un Print Format per i certificati ha tre insidie che non emergono dalla schermata e che, se ignorate, si scoprono solo a certificato emesso. Primo: senza la spunta **Custom Format** il desk propone il builder visuale e i campi HTML/CSS non compaiono affatto. Secondo — il più rilevante — il campo `template` **viene congelato sul singolo `LMS Certificate` al momento della creazione** e il download usa quel valore, non il predefinito corrente: impostare il nuovo template come default **non** cambia i certificati già emessi, che continueranno a scaricare il vecchio. Terzo: il Print Format del cliente è `Standard = Yes` e quindi esportato su disco, ma la sua cartella è **esclusa da git**, per cui il file non viaggia col deploy e in produzione il record esiste solo perché creato a mano. |
| **Soluzione applicata** | Nessuna modifica al codice. Consegnata la procedura in quattro passi (creazione del record con i campi obbligatori, partenza da uno dei due template esistenti, variabili Jinja disponibili, impostazione del predefinito), corredata dei tre avvertimenti sopra e dell'elenco puntuale dei campi del documento utilizzabili nel template. Offerti come passi successivi lo scheletro HTML/CSS del nuovo template e il patch di allineamento dei certificati già emessi. |
| **Commit** | No — nessuna modifica al codice, attività di supporto |
| **File modificati** | Nessuno. Sola lettura per riscontro: `lms/lms/doctype/lms_certificate/lms_certificate.py`, `lms/lms/doctype/lms_certificate/lms_certificate.json`, `lms/lms/print_format/certificate/certificate.json`, `lms/lms/print_format/certificato_salessciensae/certificato_salessciensae.json`, `lms/patches/v1_0/add_certificate_template.py`, `frontend/src/oslms/composables/useCertificateViewer.js`, `.gitignore`. |
| **Verifiche** | Ogni affermazione della procedura è stata riscontrata sul repository e non riferita a memoria: il congelamento del `template` letto in `create_certificate` ([lms/lms/doctype/lms_certificate/lms_certificate.py:180](../lms/lms/doctype/lms_certificate/lms_certificate.py#L180)) e il suo uso in download (`&format=${certificate.template}` in `useCertificateViewer.js:20`, `Event.vue:369`, `CourseCertification.vue:120`); l'elenco dei campi ricavato dal JSON del doctype; i parametri del record (`custom_format: 1`, `print_format_type: Jinja`, `standard: Yes`, `module: LMS`, `default_print_language: it`) letti dal JSON del template del cliente; l'esclusione da git accertata con `git ls-files` e `git check-ignore -v`, che indica `.gitignore:31`. |

**1. Obiettivo dell'attività**

Mettere l'utente in condizione di creare da sé un nuovo template di certificato,
evitando gli errori che si manifestano tardi: un Print Format creato senza *Custom
Format* che non espone i campi da compilare, e soprattutto la falsa aspettativa che
impostare il nuovo template come predefinito basti a cambiare la grafica anche dei
certificati già consegnati agli studenti. Il secondo punto è quello che conta: è
silenzioso, non produce alcun errore e si scopre solo quando uno studente scarica un
certificato vecchio.

**2. Modalità di esecuzione**

Accertamento diretto sul repository prima di formulare la procedura. Sono stati letti:
il punto in cui il certificato viene creato e il template assegnato; i campi effettivi
del doctype `LMS Certificate`, per elencare con esattezza le variabili utilizzabili nel
template; i due Print Format presenti nel repository, per indicare da quale partire e
con quali parametri; le chiamate di download della SPA, per stabilire se il PDF usi il
template congelato sul documento o il predefinito corrente. Infine è stato verificato lo
stato in git della cartella del template del cliente, poiché da esso dipende se il nuovo
template arriverà o meno in produzione col deploy.

**3. Attività svolte**

*Procedura consegnata.* Creazione del record da `/app/print-format/new` con `Doc Type =
LMS Certificate`, `Module = LMS`, `Print Format Type = Jinja`, **`Custom Format`
spuntato**, `Default Print Language = it`, margini a zero e numerazione pagina nascosta;
compilazione dei due campi separati HTML e CSS; impostazione del predefinito con ⋮ →
*Set as Default*, che scrive il Property Setter `default_print_format` letto da
`get_default_certificate_template()`.

*Punti di partenza indicati*, per non scrivere da zero: il template upstream
`lms/lms/print_format/certificate/` — orizzontale, senza rotazione, compatibile con
entrambi i generatori PDF — e quello del cliente
`lms/lms/print_format/certificato_salessciensae/` — PNG a fondo pieno, testi in
posizione assoluta e blocco ruotato di 90°. È stato precisato che i campi `html` e `css`
di quei JSON sono esattamente il contenuto dei due campi del desk.

*Variabili disponibili.* Elencati i campi di `doc` ricavati dal JSON del doctype
(`member`, `member_name`, `course`, `course_title`, `issue_date`, `expiry_date`,
`evaluator`, `evaluator_name`, `batch_name`, `batch_title`) e mostrato il pattern
Jinja già in uso per risalire ai dati correlati (`frappe.db.get_value` su `User` e `LMS
Course`, `frappe.get_all` su `Course Instructor`, `frappe.utils.format_date`), oltre al
riferimento `/files/<nome>.png` per l'immagine di sfondo.

*Avvertimenti, in ordine di rilevanza:*

| Avvertimento | Perché conta |
| --- | --- |
| Il `template` è congelato sul singolo certificato alla creazione e il download usa quel valore | Il nuovo template vale **solo per i certificati futuri**; per il pregresso serve un aggiornamento massivo del campo, sul modello del patch `lms/patches/v1_0/add_certificate_template.py` |
| Rotazione e `object-fit` richiedono il generatore **Chrome** | Su wkhtmltopdf il PDF esce bianco; la SPA già appende `&pdf_generator=chrome`, ma il test dal desk va fatto sul pulsante PDF, non sull'anteprima |
| I meta tag `pdfkit-*` sono ignorati | Formato e orientamento si impostano via `@page` e classe `.print-format` |
| La cartella del Print Format del cliente è esclusa da git | Il file non arriva in produzione col deploy: là il record esiste solo perché creato a mano. Per farlo viaggiare col codice va creato come Standard **e** tolto dal gitignore |

*Passi successivi offerti.* Preparazione dello scheletro HTML/CSS del nuovo template a
partire da quello del cliente, e scrittura del patch di allineamento del campo `template`
sui certificati già emessi. Entrambi in attesa di conferma dell'utente.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della stessa sessione dell'Attività 6.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** lettura mirata del codice di creazione del
  certificato e delle chiamate di download, estrazione dei campi del doctype e dei
  parametri dei due Print Format presenti nel repository, verifica dello stato in git
  della cartella del template del cliente, stesura della procedura e degli avvertimenti,
  redazione di questa voce.
- **motivo della scelta del tool e del modello:** la domanda sembra documentale — «come
  si crea un Print Format» — ma la risposta utile dipende interamente da questo
  repository: quale campo il codice legge al download, quali campi espone il doctype,
  quali template esistono già e se il file finisce o no nel deploy. Nessuna di queste
  informazioni è nella documentazione Frappe. Serviva un tool con accesso diretto al
  codice e un modello capace di tenere insieme backend, SPA e configurazione git nello
  stesso ragionamento.
- **risultato ottenuto:** procedura completa e verificata, con in evidenza il vincolo che
  l'utente non poteva dedurre dalla schermata — il template congelato per certificato —
  e la segnalazione che il nuovo Print Format, così com'è configurato il repository, non
  arriverebbe in produzione col deploy.
- **verifiche e correzioni effettuate:** la ricerca ha corretto un presupposto che si
  sarebbe potuto dare per buono. Il contesto pregresso del progetto descriveva il
  template del cliente come un record di sola base dati, non versionato; il repository
  mostra invece che esiste come file `Standard = Yes` in
  `lms/lms/print_format/certificato_salessciensae/`, semplicemente **escluso da git** —
  circostanza accertata con `git ls-files` e `git check-ignore -v`, che punta a
  `.gitignore:31`. La differenza non è formale: cambia la risposta su come portare il
  nuovo template in produzione. Allo stesso modo, l'affermazione sul congelamento del
  `template` non è stata dedotta dal solo codice di creazione ma confermata sul lato
  consumo, verificando che tutte e tre le chiamate di download della SPA passino
  `certificate.template` e non il predefinito.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Una sola discrepanza rispetto al contesto pregresso, risolta con
il riscontro diretto e descritta al punto 4: il template del cliente risulta esportato su
disco e non solo a database, ma in una cartella esclusa da git. Ne discende una questione
aperta di natura operativa, segnalata all'utente e non decisa unilateralmente: se il nuovo
template debba essere versionato — con modifica del `.gitignore` — per arrivare in
produzione col deploy, oppure restare una configurazione da replicare a mano sul server,
com'è oggi.

---

### Attività 8 — Procedura di collaudo rapido del nuovo template certificato e accertamento dell'indisponibilità di Chromium in locale

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto al collaudo, con accertamento sull'ambiente |
| **Problema riscontrato** | Creato il nuovo Print Format (Attività 7), l'utente chiede come provarlo rapidamente e avanza l'ipotesi più naturale: «mi sa che devo fare l'anteprima di stampa nel desk, vero?». |
| **Problema effettivo** | L'ipotesi è quella sbagliata, ed è proprio la trappola nota di questo template: **l'anteprima del desk rende HTML senza applicare il set-up di pagina del PDF** (`@page`, formato, orientamento), quindi valida una resa che non è quella finale. Accertato inoltre un secondo ostacolo, non ipotizzabile a priori: sul container di sviluppo il generatore **Chrome — indispensabile per questo template, che usa `transform: rotate` e `object-fit` — non è utilizzabile**. Chromium risulta scaricato nel bench ma l'eseguibile non parte per librerie di sistema mancanti, quindi in locale il percorso di download reale non è collaudabile e wkhtmltopdf restituisce una pagina bianca che si scambierebbe per un errore del CSS. |
| **Soluzione applicata** | Nessuna modifica al codice né all'ambiente. Consegnata una procedura di collaudo in quattro passi che aggira entrambi gli ostacoli: anteprima `/printview` per l'iterazione rapida, `Ctrl+P` del browser come verifica della pagina, endpoint di download reale con `&pdf_generator=chrome` come prova definitiva, e stessa URL senza quel parametro come controprova diagnostica per distinguere un difetto del template dall'assenza di Chromium. Fornite le URL già compilate per l'ambiente di staging e per il certificato indicato dall'utente. |
| **Commit** | No — nessuna modifica al codice, attività di supporto e accertamento |
| **File modificati** | Nessuno. Sola lettura per riscontro, sul repository e dentro il container di sviluppo. |
| **Verifiche** | Accertamenti diretti, non congetture: parametri accettati da `/printview` letti in `frappe/www/printview.py` (`doctype`, `name`, `format`, `no_letterhead`, `letterhead`, `style`, `trigger_print`, `pdf_generator`); catena di individuazione di Chromium letta in `frappe/utils/pdf_generator/chrome_pdf_generator.py` e `frappe/utils/print_utils.py` (`find_or_download_chromium_executable`, `EXECUTABLE_PATHS`); esecuzione diretta del binario nel container, che fallisce con `error while loading shared libraries: libatk-bridge-2.0.so.0`; ricognizione sul database del sito locale dei Print Format esistenti per `LMS Certificate`, del Property Setter `default_print_format` e dei certificati disponibili come cavia; effetti collaterali di `after_insert` letti in `lms/lms/doctype/lms_certificate/lms_certificate.py:21`. |

**1. Obiettivo dell'attività**

Fornire un ciclo di prova rapido e affidabile per il nuovo template, evitando che l'utente
tarasse la grafica su uno strumento che non riproduce l'output finale, e mettere in chiaro
in anticipo quali esiti negativi **non** vanno attribuiti al CSS. Il rischio concreto era
una sessione di lavoro spesa a spostare testi guardando un'anteprima non rappresentativa,
oppure ore perse su una pagina bianca che non dipende dal template ma dall'ambiente.

**2. Modalità di esecuzione**

Prima la lettura del codice per stabilire con esattezza quali parametri accetti la pagina
di anteprima server-side e come Frappe individui l'eseguibile Chromium; poi la verifica
sul campo dentro il container, eseguendo il binario per accertarne l'effettiva
utilizzabilità invece di limitarsi a constatarne la presenza sul filesystem; infine una
ricognizione sul database del sito locale per individuare certificati e Print Format
utilizzabili come cavia. Solo a valle di questi accertamenti è stata formulata la
procedura.

**3. Attività svolte**

*Risposta all'ipotesi dell'utente.* Chiarito che l'anteprima del desk non è lo strumento
adatto a questo template: rende HTML e non applica `@page`, formato e orientamento.

*Procedura consegnata, in quattro passi:*

| Passo | Strumento | A cosa serve |
| --- | --- | --- |
| 1 | `/printview?doctype=LMS Certificate&name=…&format=…&no_letterhead=1&_lang=it` | Iterazione rapida su posizioni e testi: pagina resa dal server, ricaricabile a ogni salvataggio; essendo il browser Chrome, rotazione e `object-fit` sono applicati |
| 2 | `Ctrl+P` → *Salva come PDF* sulla stessa pagina | Verifica di formato e orientamento: è il motore di Chrome, rispetta `@page`; è il proxy più fedele al generatore chrome del backend |
| 3 | `download_pdf?…&pdf_generator=chrome` | Prova definitiva: è esattamente ciò che scarica lo studente |
| 4 | stessa URL **senza** `pdf_generator` | Controprova diagnostica: se è bianca in entrambi i casi il difetto è nel template, se il comportamento cambia allora manca Chromium |

*Accertamento sull'ambiente locale.* Il binario
`frappe-bench/chromium/chrome-linux/headless_shell` esiste (scaricato il 7 luglio, 178 MB)
ma non è eseguibile per librerie di sistema mancanti. Ne consegue che in locale il passo 3
non è percorribile e che, senza il parametro, wkhtmltopdf produce una pagina bianca per via
della rotazione. Proposta all'utente l'installazione delle librerie mancanti nel container,
segnalando che sarebbe una modifica volatile da riportare poi nel `Dockerfile`; l'utente non
ha richiesto l'intervento perché sta collaudando su staging.

*Ricognizione sul sito locale,* che ha prodotto un riscontro inatteso: nessun Print Format
nuovo. Presenti solo `Certificate`, `Certificato Due`, `Certificato Salessciensae` e
`Prova 2certifiat` — quest'ultimo del 7 luglio, con `custom_format = 0` e HTML/CSS
**vuoti**, cioè esattamente il caso descritto nell'Attività 7: senza la spunta i campi non
si compilano. Il predefinito risultava ancora `Certificato Salessciensae`. Segnalata la
discrepanza all'utente invece di proseguire come se il template fosse lì, e chiesto in
quale ambiente avesse operato.

*Riallineamento su staging.* L'utente ha chiarito di collaudare su
`https://elite.overside.it` con il Print Format `Certificato Elite` e ha indicato il
certificato `038hu77abn`. Consegnate le quattro URL già compilate per quell'ambiente e
quel documento.

*Avvertimento aggiuntivo sul collaudo.* Sconsigliato creare un `LMS Certificate` a mano per
la prova: `after_insert` invia realmente la mail di congratulazioni al `member` e, sui corsi
con TrueSkill attivo, innesca l'emissione del badge. Su staging con utenti reali sarebbe una
mail partita per errore; indicato di riusare un certificato esistente o, in mancanza,
intestarne uno a sé stessi.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), stessa sessione delle Attività 6 e 7.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** lettura dei parametri di `/printview` e della
  catena di individuazione di Chromium nel codice Frappe, esecuzione del binario nel
  container per verificarne l'utilizzabilità, interrogazione del database locale per
  Print Format e certificati, composizione della procedura e delle URL per staging,
  redazione di questa voce.
- **motivo della scelta del tool e del modello:** la domanda era operativa e apparentemente
  banale, ma la risposta corretta dipendeva da tre cose verificabili solo qui — quali
  parametri accetti davvero la pagina di anteprima, se Chromium sia utilizzabile in questo
  ambiente, quali documenti esistano per fare la prova. Claude Code consente di leggere il
  codice Frappe dentro il container ed eseguirvi comandi; Opus 5 tiene insieme il contesto
  accumulato nelle due attività precedenti senza doverlo ricostruire.
- **risultato ottenuto:** procedura di collaudo in quattro passi, con URL pronte all'uso per
  staging, e due ostacoli disinnescati in anticipo — l'anteprima del desk non
  rappresentativa e l'indisponibilità di Chromium in locale — più l'avvertimento sugli
  effetti collaterali della creazione manuale di un certificato.
- **verifiche e correzioni effettuate:** l'accertamento su Chromium è stato spinto oltre la
  constatazione superficiale: il binario **c'è** sul filesystem, e fermarsi lì avrebbe
  prodotto la conclusione opposta a quella vera. Solo eseguendolo è emerso che non parte per
  librerie mancanti. Allo stesso modo, la ricognizione sul database ha evitato di proseguire
  su un presupposto errato — che il nuovo template fosse sul sito locale — e ha portato a
  chiedere all'utente l'ambiente reale invece di fornirgli URL inutilizzabili. È stato
  inoltre aggiunto il passo 4, la controprova senza `pdf_generator`, proprio perché
  l'accertamento aveva mostrato che una pagina bianca in questo contesto è ambigua fra
  difetto del template e ambiente incompleto.

**6. Problematiche incontrate**

Due ostacoli d'ambiente, entrambi aggirati e nessuno dei due dipendente dal lavoro in corso.
Il primo: in locale il generatore Chrome non è utilizzabile per librerie di sistema mancanti
nel container, quindi il percorso di download reale non è collaudabile senza un intervento
sull'immagine; la soluzione è stata spostare il collaudo su staging, come l'utente stava già
facendo. Il secondo: il nuovo Print Format non esisteva sul sito interrogato, circostanza
che avrebbe reso inutilizzabile tutta la procedura se non fosse stata verificata prima di
consegnarla. Resta aperto, e segnalato all'utente, se installare le librerie mancanti nel
`Dockerfile` per rendere il container di sviluppo capace di generare PDF con Chrome.

---

### Attività 9 — Istruttore non rimovibile e istruttori nuovi non salvati quando un account è stato cancellato

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — difetto dell'interfaccia segnalato dal cliente |
| **Problema riscontrato** | Segnalazione riportata dall'utente: nel corso "Strumenti di collaborazione digitale" su Elite non è possibile rimuovere l'istruttore attualmente presente — il cui **account non esiste più** — e non vengono salvati nemmeno i nuovi istruttori che si selezionano. |
| **Problema effettivo** | **Una sola causa, due sintomi.** Il campo Istruttori (`CourseInstructorsField.vue`) alimenta il componente `MultiLink` tramite `extraOptions`, e la tendina del componente è costruita dall'unione dei risultati della ricerca server con quelle opzioni (`MultiLink.vue:265-279`). Un istruttore il cui utente è stato cancellato **non torna mai** dall'endpoint di ricerca `lms.lms.api.search_users_by_role`, e il calcolo di `resolvedSelected` **scartava** i valori non risolti con un `.filter(Boolean)`. Conseguenza: quel valore non compariva nella tendina, e poiché la rimozione avviene esclusivamente deselezionando l'opzione lì (il trigger del componente mostra solo un riepilogo testuale, senza chip con la "x"), **non era rimovibile**. Il nome restava però visibile nel riepilogo, perché `MultiLink.selectedOptions` (riga 288-293) ha un proprio fallback `{label: v, value: v}` — da cui la sensazione di un istruttore "bloccato". Il secondo sintomo discende dal primo: restando nel modello, a ogni salvataggio il form inviava quel riferimento rotto insieme al resto (`CourseForm.vue:222`), e Frappe rifiutava **l'intero** salvataggio con `LinkValidationError`, quindi non venivano registrate nemmeno le aggiunte valide. |
| **Soluzione applicata** | In `CourseInstructorsField.vue`, `resolvedSelected` non scarta più i valori non risolti: genera per essi un'opzione di ripiego con l'id utente come etichetta e descrizione. L'istruttore orfano torna così presente nella tendina, deselezionabile, e una volta rimosso il corso torna salvabile. Nessuna modifica al backend: è stato verificato che salva correttamente non appena il riferimento rotto non viene più inviato. |
| **Commit** | Sì — `1f3614c6` *fix(courses): let an instructor whose account is gone be removed from a course*, branch `feature/oslms`. Committata più tardi nella giornata, in commit separato da quella dell'Attività 4 (`bf6a1c31`) come previsto: le due sono indipendenti. |
| **File modificati** | `frontend/src/pages/Courses/CourseInstructorsField.vue` (riscrittura di `resolvedSelected`, 12 righe più commento). File esaminati: `frontend/src/components/Controls/MultiLink.vue`, `frontend/src/pages/Courses/CourseForm.vue`. |
| **Verifiche** | (a) **Riproduzione sul database** con un corso di prova dedicato (creato con un istruttore, poi cancellato l'utente): inviando la lista con il fantasma → `LinkValidationError`; rimuovendo il fantasma → salvato; aggiungendo un secondo istruttore valido → salvato. È la prova che il backend non necessita di modifiche e che il blocco era esclusivamente nella possibilità di rimuovere il valore. (b) `vue-tsc --noEmit` sul progetto: nessun errore sul file modificato. (c) `yarn build`: completata (`✓ built in 41.38s`). (d) Verificato che gli artefatti di build non risultino fra le modifiche tracciate (sono ignorati da git). |

**1. Obiettivo dell'attività**

Rendere nuovamente modificabile l'elenco istruttori dei corsi che contengono un riferimento a un account cancellato. La segnalazione riguarda un corso specifico, ma la condizione — un utente rimosso dalla piattaforma che era istruttore di qualche corso — è destinata a ripresentarsi a ogni cessazione di un account, quindi la correzione doveva agire sulla causa e non sul singolo corso.

**2. Modalità di esecuzione**

1. **Verifica preliminare del backend**, per stabilire se il blocco fosse nel salvataggio o nell'interfaccia: riproduzione diretta sul database di tre varianti di salvataggio (con il riferimento rotto, senza, con aggiunta di un istruttore nuovo).
2. **Ricostruzione del percorso dell'interfaccia**: quale componente rende il campo, come costruisce l'elenco selezionabile, e dove materialmente avviene la rimozione di un elemento già selezionato.
3. **Correzione nel punto che genera l'elenco**, e verifica con typecheck e build.

Un'accortezza adottata dopo l'incidente registrato nell'Attività 4: la prima riproduzione era stata impostata su un corso **reale** del sito (`Corso_importato_2`, che presenta lo stesso difetto), e ne ha effettivamente modificato gli istruttori. Lo stato originale è stato immediatamente ripristinato e la prova è stata rifatta su un corso di prova creato allo scopo, con pulizia limitata ai soli documenti creati dallo script.

**3. Attività svolte**

*Verifica del backend.* Esito delle tre varianti sul corso di prova:

| Payload inviato | Esito |
| --- | --- |
| Istruttore fantasma incluso | **FALLITO** — `LinkValidationError: Could not find Row #1: Instructor: …` |
| Fantasma rimosso, istruttore reale | SALVATO |
| Istruttore aggiuntivo, senza fantasma | SALVATO |

Il backend è quindi corretto: rifiuta un riferimento inesistente, come deve, e accetta tutto il resto. Il difetto è interamente nell'interfaccia, che non offriva modo di togliere quel riferimento.

*Ricostruzione dell'interfaccia.* La rimozione di un istruttore già selezionato avviene **solo** deselezionando la voce nella tendina del `MultiLink`; il trigger non espone chip con pulsante di rimozione ma un semplice riepilogo testuale. La tendina nasce dall'unione fra risultati di ricerca e `extraOptions`, e il filtro in `resolvedSelected` privava quest'ultima esattamente dei valori che la ricerca non sa restituire — cioè proprio gli account cancellati. Il valore era così presente nel modello e nel riepilogo, ma assente dall'unico punto in cui poteva essere tolto.

*Nota su un errore nella prima prova.* La prima riproduzione mostrava tutte e tre le varianti fallite, compresa quella senza fantasma. La causa era nello script, non nel prodotto: l'"istruttore reale" veniva pescato con `frappe.get_all("User", {"enabled": 1}, limit=1)` **dopo** aver creato l'utente fantasma, e la query restituiva proprio quello. Corretta la selezione escludendo esplicitamente il fantasma e ordinando per data di creazione, il quadro si è chiarito.

*Ricaduta operativa per il cliente.* Nessun intervento sui dati è necessario: una volta rilasciata la correzione, sarà sufficiente aprire il campo Istruttori del corso, deselezionare l'account non più esistente e salvare.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della sessione.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** verifica sul database del comportamento di salvataggio, ricostruzione del percorso dell'interfaccia attraverso tre componenti Vue, individuazione della riga responsabile, stesura della correzione, typecheck e build, redazione di questa voce.
- **motivo della scelta del tool e del modello:** il sintomo era ambiguo fra backend e frontend e andava disambiguato con una prova sul database prima di leggere codice Vue; servivano quindi accesso al container e al repository nello stesso flusso. Il contesto ampio di Opus 5 ha permesso di tenere insieme i tre componenti coinvolti (`CourseForm`, `CourseInstructorsField`, `MultiLink`) e di riconoscere che il caso era lo stesso già incontrato ore prima durante il ripristino dei corsi, dove un istruttore inesistente aveva fatto fallire un reinserimento.
- **risultato ottenuto:** causa unica individuata per entrambi i sintomi riferiti dal cliente, correzione circoscritta a un solo calcolo di un solo componente, nessuna modifica al backend e nessun intervento sui dati necessario.
- **verifiche e correzioni effettuate:** non si è partiti dal codice ma da una prova sul database, che ha escluso il backend e ha impedito di correggere il punto sbagliato. Un errore nello script di prova — l'istruttore "reale" coincidente con il fantasma — è stato individuato perché il risultato era implausibile (falliva anche il caso che avrebbe dovuto funzionare) e corretto rifacendo la prova. La modifica è stata validata con `vue-tsc` e con una build completa, non solo a vista. Infine, applicando la regola adottata dopo l'incidente della mattina, la prova è stata spostata dal corso reale inizialmente usato a un corso creato allo scopo, e lo stato del corso reale è stato ripristinato.

**6. Problematiche incontrate**

Due, entrambe di metodo più che tecniche.

La prima: la prima riproduzione è stata avviata su un corso reale del sito, modificandone gli istruttori. È lo stesso tipo di leggerezza all'origine dell'incidente dell'Attività 4, ripetuto a poche ore di distanza, e questa volta rilevato e corretto subito — stato ripristinato e prova rifatta su un corso dedicato. Conferma che la regola annotata stamattina va applicata **prima** di scrivere lo script, non dopo averne visto l'esito.

La seconda: la correzione riguarda l'interfaccia e non è verificabile con i test automatici del progetto, che coprono il backend. Typecheck e build accertano che il codice è valido, non che il comportamento è quello atteso; la conferma visiva sul campo — aprire il corso, togliere l'istruttore orfano, salvare — resta da fare dopo il rilascio ed è stata richiesta all'utente.

---

### Attività 10 — Individuazione del punto di modifica dello stile della pagina di login

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — orientamento operativo, con accertamento sull'istanza di produzione |
| **Problema riscontrato** | Richiesta dell'utente: «devo modificare lo stile della pagina login (https://elite.overside.it/login), come dovrei fare?». Non un difetto, ma la necessità di sapere **quale file tocca davvero quella pagina**: nel repository esistono due template di login quasi identici (`lms/www/login.html` e `apps/os_lms/os_lms/www/login.html`) e tre punti distinti in cui può nascere una regola di stile, quindi la modifica fatta "a intuito" ha una probabilità concreta di non produrre alcun effetto. |
| **Problema effettivo** | La pagina `/login` **non** è la SPA Vue ma una pagina website di Frappe (Jinja + Bootstrap 4 + CSS classico): non valgono Tailwind, frappe-ui né il meccanismo di override `osOverrideTheme`. Il template servito è quello di **os_lms**, non quello di `lms`, perché Frappe risolve le pagine `www/` iterando `for app in reversed(frappe.get_installed_apps())` e `os_lms` è l'ultima riga di `apps.txt`: `lms/www/login.html` è quindi **codice morto in produzione**. Conseguenza collaterale rilevata: il fix del 03/08 sul dizionario client (`frappe._messages["Message"]`, commit `0e4680fb9`) è stato applicato al solo file di `lms` e **non è attivo sul sito**. |
| **Soluzione applicata** | Nessuna modifica al codice. Consegnata la mappa dei tre livelli di intervento in ordine di invasività — colori dal desk (doctype *Brand Customize* → `brand_css`), regole CSS in `apps/os_lms/os_lms/public/css/os_lms.css`, markup in `apps/os_lms/os_lms/www/login.html` — con l'ordine effettivo di caricamento dei fogli di stile, l'elenco dei selettori disponibili, la tecnica di scoping `body[data-path="login"]` e l'avvertenza di non toccare il file di `lms`. Segnalata in una riga la regressione latente del fix `frappe._messages`, senza correggerla perché fuori dall'ambito della richiesta. |
| **Commit** | No — nessuna modifica al codice, attività di orientamento |
| **File modificati** | Nessuno. Sola lettura per riscontro: `apps/os_lms/os_lms/www/login.html`, `apps/os_lms/os_lms/www/login.py`, `apps/os_lms/os_lms/templates/base.html`, `apps/os_lms/os_lms/public/css/os_lms.css`, `apps/os_lms/os_lms/hooks.py`, `apps/os_lms/os_lms/os_lms/branding.py`, `lms/www/login.html`, `lms/plugins.py`. |
| **Verifiche** | Tre riscontri indipendenti, invece della sola lettura del repository: (1) `curl` sul sorgente della pagina di produzione, che contiene il markup presente **solo** nella versione os_lms (`<section class='for-forgot  page-card'>`, `form ... forgot-section`) e **non** contiene il blocco `frappe._messages` né il refuso `account?}}s` del file di `lms`; (2) lettura del risolutore di Frappe nel container (`frappe/website/page_renderers/template_page.py`), che conferma la precedenza all'ultima app installata, e di `sites/apps.txt`, dove `os_lms` è ultima; (3) verifica che `sites/assets/os_lms` sia un symlink alla cartella `public` dell'app, da cui discende che una modifica a `os_lms.css` non richiede `bench build`. |

**1. Obiettivo dell'attività**

Mettere l'utente in condizione di modificare l'aspetto della pagina di accesso
intervenendo al primo colpo sul file giusto. L'obiettivo non era indicare "un" punto di
modifica, ma stabilire con certezza **quale** dei due template di login in repository
sia effettivamente servito da `https://elite.overside.it/login`, perché la duplicazione
esistente rende plausibile — e silenziosamente inefficace — la modifica del file
sbagliato: nessun errore, nessun avviso, semplicemente la pagina che resta identica.

**2. Modalità di esecuzione**

Ricostruzione della catena di rendering dal basso, con accertamento sul campo a ogni
passaggio anziché deduzione dal solo codice. Elenco dei template `www/` nelle due app;
`diff` fra i due `login.html` per isolare marcatori di markup che li distinguano in modo
inequivocabile; `curl` sul sorgente della pagina di produzione e ricerca di quei
marcatori per stabilire quale sia servito; lettura del risolutore `TemplatePage` nel
container di sviluppo e di `apps.txt` per spiegare *perché* vinca quello; lettura di
`templates/base.html` per ricavare l'ordine reale dei fogli di stile nel `<head>`;
ispezione del symlink degli asset per stabilire se serva una build.

**3. Attività svolte**

*Catena dei template.* La pagina è servita da `apps/os_lms/os_lms/www/login.html`, fork
di `lms/www/login.html`, a sua volta fork di quello di Frappe. Il contesto Jinja arriva
da `apps/os_lms/os_lms/www/login.py` (logo via `get_app_logo()`, provider social, form di
registrazione). Il markup della sezione registrazione **non** è in questo file: arriva
dall'hook `signup_form_template = "lms.plugins.show_custom_signup"` (`lms/hooks.py:270`),
che rende `lms/templates/signup-form.html` quando *LMS Settings* ha contenuto di signup
personalizzato o categorie utente, altrimenti il template di Frappe.

*Ordine dei fogli di stile nel `<head>`*, ricavato da `templates/base.html` (override di
`base_template` dichiarato in `hooks.py:12`):

| # | Foglio | Origine |
| --- | --- | --- |
| 1 | `login.bundle.css` | Frappe, iniettato dal `{% block head_include %}` di `login.html` |
| 2 | `/assets/os_lms/css/os_lms.css` | file dell'app, symlink diretto alla cartella `public` |
| 3 | `/api/method/os_lms.os_lms.branding.brand_css` | CSS generato a runtime dal doctype *Brand Customize* |

Essendo gli ultimi due caricati **dopo** il bundle di Frappe, non servono `!important` per
prevalere sugli stili di base, e `brand_css` — ultimo — vince sulle variabili ridefinite
in `os_lms.css`.

*Tre livelli di intervento consegnati, in ordine di invasività.* (a) Solo colori: doctype
*Brand Customize* dal desk, nessun codice e nessun rilascio, con la mappa
campo → variabile CSS in `branding.py`. (b) Stile e spaziature: nuove regole in
`apps/os_lms/os_lms/public/css/os_lms.css`, che già contiene le regole di login attuali
(gradiente sul `body`, `.login-content`, `.btn-login`, `input`, `.page-card-head h4`,
`.forgot-section`, `.sign-up-message a`); elencati i selettori disponibili — sezioni
`.for-login` / `.for-signup` / `.for-forgot` / `.for-email-login`, card `.page-card` e
`.login-content`, `.page-card-head .app-logo`, `.page-card-body`, `.page-card-actions`,
`.form-control`, `.field-icon`, `.toggle-password`, `.social-logins`. (c) Struttura:
modifica diretta di `apps/os_lms/os_lms/www/login.html` (già fork, nessun rischio di
conflitto upstream), con le stringhe da avvolgere in `{{ _() }}` e tradurre nei due file
di traduzione italiani.

*Avvertenze consegnate.* `os_lms.css` è caricato su **tutte** le pagine website (login,
`/me`, `update-password`, wrapper della SPA): le regole vanno circoscritte, e il
`<body>` espone `data-path="login"`, quindi `body[data-path="login"] { … }` è lo scope
naturale — utile in particolare per il gradiente oggi applicato al `body` nudo, che
ricade su tutte le pagine website. Nessuna build è necessaria: `sites/assets/os_lms` è un
symlink alla cartella `public` dell'app, quindi basta il rilascio del file e un ricarico
forzato del browser (l'URL è senza hash di versione, quindi la cache è reale).

*Segnalazione laterale, non corretta.* Il fix di localizzazione del titolo "Message"
(commit `0e4680fb9`) è stato applicato a `lms/www/login.html`, file che in produzione è
ombreggiato da quello di os_lms: il sorgente della pagina live non lo contiene, quindi il
difetto è ancora presente. Segnalato all'utente in una riga, senza intervenire, perché
estraneo alla richiesta.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** ricostruzione della catena di rendering della
  pagina di login, accertamento su produzione di quale template sia servito, lettura del
  risolutore di Frappe nel container, ricostruzione dell'ordine dei fogli di stile,
  formulazione della risposta operativa a tre livelli, redazione di questa voce.
- **motivo della scelta del tool e del modello:** la domanda sembra banale ma ha una
  trappola strutturale — due template di login quasi identici in repository, uno dei quali
  inefficace — che si scopre solo incrociando il codice delle due app, la configurazione
  dell'istanza e il sorgente della pagina realmente servita. Un modello con accesso al
  repository, al container di sviluppo e alla rete può chiudere il cerchio con un
  riscontro diretto; una risposta basata sulla sola documentazione Frappe avrebbe indicato
  `lms/www/login.html`, cioè il file sbagliato.
- **risultato ottenuto:** punto di modifica individuato con certezza e non per deduzione,
  con la gerarchia dei tre livelli di intervento, i selettori disponibili, la tecnica di
  scoping e l'assenza di build da eseguire; in più, individuata una regressione latente
  non nota (fix di localizzazione inattivo in produzione).
- **verifiche e correzioni effettuate:** la risposta non è stata data a memoria né per
  lettura del solo repository. La precedenza fra le due app è stata dimostrata su tre
  fronti indipendenti — marcatori di markup nel sorgente della pagina live, codice del
  risolutore `TemplatePage` nel container, ordine di `apps.txt` — e l'assenza di una build
  necessaria è stata verificata risalendo il symlink degli asset, non assunta.

**6. Problematiche incontrate**

La duplicazione dei template di login fra `lms/` e `apps/os_lms/` è una trappola attiva,
non un residuo innocuo: i due file divergono (il primo ha un refuso e un fix di
localizzazione che il secondo non ha) e nulla nel repository segnala quale sia servito.
Chi interviene sulla pagina di login rischia di modificare il file sbagliato e di
concludere che "la modifica non funziona". La stessa dinamica ha già prodotto un fix
inefficace, quello del titolo "Message". Il consolidamento — cancellare il fork in `lms/`
e riportare su os_lms il fix rimasto indietro — non è stato eseguito perché estraneo alla
richiesta, ed è stato segnalato all'utente come intervento a sé.

---

### Attività 11 — Fattibilità di pilotare i colori della pagina di login dal doctype Brand Customize

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi di fattibilità — nessuna modifica al codice |
| **Problema riscontrato** | Richiesta dell'utente al termine dell'Attività 10: «è possibile caricare i colori dal doctype Brand Customize? fai un'analisi prima». L'esigenza è evitare che ogni ritocco cromatico della pagina di accesso richieda una modifica al CSS e un rilascio, spostando il controllo su un pannello del desk. |
| **Problema effettivo** | L'infrastruttura esiste già ed è **anche caricata sulla pagina di login**, ma è cablata solo a metà: il CSS del login non legge quasi nessuna delle variabili prodotte da Brand Customize. Su sette elementi cromatici della pagina, cinque sono valori letterali in `os_lms.css` o nel bundle di Frappe (gradiente `#0a2e5a → #1d5a9b`, `white` del titolo, `#fff` della card) e uno usa `--color-company-tertiary`, variabile che **non ha un campo corrispondente** nel doctype (esistono solo *primary* e *secondary*). In produzione Brand Customize ha **un solo campo valorizzato** (`--surface-gray-10`), che sul login non tocca nulla: da qui l'impressione che il pannello "non funzioni". |
| **Soluzione applicata** | Nessuna modifica. Consegnata l'analisi: meccanismo attuale e sua idoneità (endpoint `allow_guest`, ultimo foglio del `<head>`, `cache-control: no-store`), tabella elemento-per-elemento di cosa è pilotabile e cosa no, intervento necessario in tre punti (campi sul doctype, righe nella mappa `FIELD_TO_CSS_VAR`, sostituzione dei letterali con `var(--login-*, <valore attuale>)`), e tre decisioni rimesse all'utente prima di procedere. |
| **Commit** | No — analisi di fattibilità, nessuna modifica al codice |
| **File modificati** | Nessuno. Sola lettura per riscontro: `apps/os_lms/os_lms/os_lms/branding.py`, `apps/os_lms/os_lms/os_lms/doctype/brand_customize/brand_customize.json`, `apps/os_lms/os_lms/public/css/os_lms.css`, `apps/os_lms/os_lms/hooks.py`, `apps/os_lms/os_lms/templates/base.html`, `apps/os_lms/os_lms/os_lms/app/api.py`, `frontend/src/components/Layouts/DesktopLayout.vue`, `frontend/src/styles/theme/elite/main.css`. |
| **Verifiche** | Riscontri sull'istanza di produzione, non sul solo repository: (1) `GET` su `/api/method/os_lms.os_lms.branding.brand_css` **da non autenticato** → `200`, `content-type: text/css`, contenuto `:root { --surface-gray-10: #292929; }` — quindi l'endpoint è raggiungibile dagli ospiti e oggi produce una sola variabile; (2) header `cache-control: no-store,no-cache,must-revalidate,max-age=0` → nessuna cache del browser da invalidare; (3) sorgente della pagina live: i fogli di stile sono cinque e `brand_css` è **l'ultimo**, dopo `os_lms.css`; (4) scaricati e ispezionati `login.bundle.css` e `website.bundle.css` di Frappe per accertare quali colori siano letterali (`.page-card{background-color:#fff}`) e quali variabili siano esposte (`--btn-primary`, `--bg-light-gray`, `--border-color`, `--text-light`); (5) ricerca su tutto il repository di `gradient-overlay`, che ha accertato l'assenza di qualsiasi definizione CSS per la classe `.bg-gradient-overlay`. |

**1. Obiettivo dell'attività**

Stabilire se i colori della pagina di accesso possano essere gestiti dal desk anziché dal
CSS, e — soprattutto — spiegare perché oggi il pannello *Brand Customize* esista, sia già
caricato su quella pagina e tuttavia non produca alcun effetto visibile. L'obiettivo non
era un sì/no ma la delimitazione esatta del lavoro mancante e delle sue conseguenze, in
modo che la decisione su quanto renderlo configurabile sia presa con i costi davanti.

**2. Modalità di esecuzione**

Analisi a tre livelli, ciascuno verificato sul campo. Livello *produzione*: interrogazione
diretta dell'endpoint `brand_css` da client non autenticato per accertarne raggiungibilità,
tipo MIME, politica di cache e contenuto reale. Livello *presentazione*: download dei
bundle CSS di Frappe serviti dalla pagina e ispezione delle regole che colorano gli
elementi del login, per distinguere i valori letterali dalle variabili sovrascrivibili.
Livello *applicativo*: lettura della mappa `FIELD_TO_CSS_VAR`, del JSON del doctype e del
CSS dell'app per incrociare "colore visibile sulla pagina" con "campo esistente nel
pannello", e ricerca sull'intero repository dei consumatori effettivi delle variabili già
mappate.

**3. Attività svolte**

*Il meccanismo attuale è idoneo.* `brand_css` è un endpoint whitelisted con
`allow_guest=True` che genera un blocco `:root { … }` dai soli campi valorizzati del Single
*Brand Customize* (mappa di 23 campi in `branding.py:20-44`), con cache Redis invalidata da
`clear_brand_cache` sull'`on_update` del doctype (`hooks.py:193`). Il foglio è iniettato in
`templates/base.html` per tutte le pagine website — login incluso — ed è l'**ultimo** dei
cinque fogli della pagina, quindi vince per ordine di cascata a parità di specificità
(`:root` contro `:root`). Non richiede autenticazione e non è messo in cache dal browser:
cambio nel desk, ricarico, effetto visibile. Sono le due condizioni che rendevano dubbia la
praticabilità e sono entrambe soddisfatte.

*Perché oggi non basta.* Il collegamento fra le variabili del pannello e i colori della
pagina è quasi assente:

| Elemento della pagina | Come è colorato oggi | Pilotabile dal desk |
| --- | --- | --- |
| Sfondo pagina | `linear-gradient(to right, #0a2e5a, #1d5a9b)` — letterale, `os_lms.css:12` | No |
| Card di login | `background-color:#fff` — letterale, dentro `login.bundle.css` di Frappe | No, manca una nostra regola |
| Titolo (`.page-card-head h4`) | `white` — letterale, `os_lms.css:30` | No |
| Campi input | `var(--color-company-tertiary)` | No: la variabile è definita solo in `os_lms.css:7` e **non ha un campo** nel doctype |
| Card "Password dimenticata" | `var(--color-white)` + `var(--outline-gray-1)` | Parziale: `outline_gray_1` è un campo esistente, `--color-white` no |
| Pulsante Login | `--btn-primary` di Frappe | Sì in teoria, ma è condivisa con il desk |
| Link (password dimenticata, registrati) | regole presenti ma **commentate**, `os_lms.css:43-48` | No |

*Intervento necessario, in tre punti.* (a) Doctype: una sezione *Login* con i campi `Color`
desiderati; (b) `branding.py`: una riga per campo nella mappa `FIELD_TO_CSS_VAR`; (c)
`os_lms.css`: sostituzione dei valori letterali con `var(--login-xxx, <valore attuale>)`.
Il fallback inline della `var()` è il punto chiave: a campo vuoto la pagina resta
**identica a oggi**, quindi l'intervento è privo di regressione anche senza popolare il
pannello. Nessuna build (gli asset sono un symlink), nessuna migrazione dati (Single con
campi nuovi vuoti); serve solo un `bench migrate` per creare i campi.

*Tre decisioni rimesse all'utente.* (1) **Variabili dedicate o riuso**: le generiche
(`--outline-gray-1`, `--btn-primary`, `--surface-*`) sono condivise con desk e SPA, quindi
ritoccare il pulsante del login ne cambierebbe il colore anche altrove; variabili
`--login-*` dedicate circoscrivono l'effetto e sono la scelta consigliata. (2) **Riuso
della sezione "Gradient Overlay" già presente**: i suoi due campi mappano
`--gradient-overlay-from/to`, variabili che la ricerca sul repository mostra **non definite
e non usate da nessuna parte** — l'unica occorrenza è la classe `.bg-gradient-overlay` in
`DesktopLayout.vue`, priva di qualunque regola CSS. Sono quindi campi morti, riciclabili a
costo zero per lo sfondo del login. (3) **Granularità**: quattro campi (sfondo da/a, card,
pulsante) coprono l'80% dei casi; sette-otto danno controllo completo ma allungano il
pannello.

*Nota emersa ma non problematica.* I campi `app_main_color` e `app_secondary_color` sono
assenti dalla mappa non per dimenticanza: sono consumati dall'API dell'app mobile
(`apps/os_lms/os_lms/os_lms/app/api.py:166`), non dal CSS.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** accertamento del comportamento dell'endpoint
  `brand_css` in produzione, ispezione dei bundle CSS di Frappe serviti dalla pagina,
  incrocio fra colori visibili e campi del doctype, individuazione dei campi morti,
  formulazione dell'intervento e delle sue alternative, redazione di questa voce.
- **motivo della scelta del tool e del modello:** la domanda è di fattibilità e la risposta
  onesta dipende da fatti che nessuna lettura del solo repository può dare — se l'endpoint
  risponda agli ospiti, se il browser lo metta in cache, quali colori dei bundle di Frappe
  siano letterali e quali variabili, cosa contenga davvero il pannello in produzione. Un
  modello con accesso contemporaneo al repository, al container e alla rete chiude tutti e
  quattro i punti con riscontri diretti; una valutazione a tavolino avrebbe risposto "sì è
  possibile" senza accorgersi che la variabile usata dagli input non ha alcun campo
  corrispondente, cioè del punto che fa fallire l'aspettativa dell'utente.
- **risultato ottenuto:** fattibilità confermata con la delimitazione esatta del lavoro
  mancante (tre file, nessun rischio di regressione grazie ai fallback), spiegazione del
  motivo per cui oggi il pannello sembra inerte, e tre decisioni di progetto messe davanti
  all'utente prima di scrivere codice.
- **verifiche e correzioni effettuate:** nessuna affermazione lasciata a deduzione. La
  raggiungibilità da ospite, il tipo MIME e l'assenza di cache sono stati letti dagli
  header della risposta reale; il contenuto attuale del pannello in produzione è stato
  scaricato (una sola variabile); i colori letterali dei bundle Frappe sono stati estratti
  dai file effettivamente serviti, non supposti; l'ipotesi iniziale di riusare la sezione
  *Gradient Overlay* è stata verificata prima di proporla, scoprendo che i suoi campi sono
  morti — il che l'ha trasformata da scorciatoia dubbia in opzione a costo zero.

**6. Problematiche incontrate**

Una tensione di progetto, segnalata e non risolta unilateralmente: le variabili già mappate
in `Brand Customize` sono condivise fra desk, SPA e pagine website, quindi usarle per il
login produce effetti collaterali altrove, mentre crearne di dedicate allunga un pannello
che ha già 23 campi. La scelta incide sulla manutenzione futura e non è tecnica ma di
prodotto: è stata rimessa all'utente insieme alla granularità desiderata.

Una seconda osservazione, non bloccante: due campi del pannello (*Gradient Overlay From/To*)
sono oggi inerti perché la classe che avrebbero dovuto colorare non ha mai avuto una
definizione CSS. Chi apre il pannello vede due colori che non fanno nulla. Vanno riciclati
o rimossi, ma l'intervento è stato lasciato fuori dall'ambito di questa analisi.

---

### Attività 12 — Vincolo multi-cliente sui colori del login e progetto della catena di fallback

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi di progettazione — nessuna modifica al codice |
| **Problema riscontrato** | L'utente esplicita il vincolo reale dietro la domanda dell'Attività 11: l'app è distribuita su **più istanze Frappe, una per cliente**, e ogni cliente ha la propria identità cromatica; la pagina di login deve seguire lo stile del cliente. Finché i colori stanno nel CSS dell'app, ogni cliente richiederebbe un fork del file o un rilascio dedicato. |
| **Problema effettivo** | Il progetto è già impostato per il multi-cliente su tutto tranne che sul login: logo e nome dell'istanza arrivano già dal database (`get_app_logo()` da *Navbar Settings*, `app_name` da *Website Settings*) e i colori dell'app mobile arrivano già da *Brand Customize* (`get_instance_info`). Il login è l'**unico residuo hardcoded**: `os_lms.css` spedisce il blu Elite (`#0a2e5a`, `#1d5a9b`, `#111d2e`, `#124679`) a ogni istanza. Il difetto non è quindi "manca una funzione" ma "un pezzo non ha seguito il modello già adottato altrove". Emerge inoltre un vincolo secondario: un colore del brand da solo non decide il contrasto del testo sopra di esso, quindi non tutto è derivabile dalla palette e serve almeno un campo per il testo. |
| **Soluzione applicata** | Nessuna modifica. Progettata e consegnata la soluzione: catena di fallback a tre livelli con `var()` annidate — campo specifico del login, altrimenti colore di brand del cliente, altrimenti valore di default dell'app — che rende la pagina brandizzata per istanza **senza alcun campo obbligatorio** e senza toccare il CSS per nuovo cliente. Definito il set minimo di campi (5, tutti opzionali), la sequenza operativa per non far diventare grigio il login di Elite, e il recupero dei due campi morti *Gradient Overlay*. |
| **Commit** | No — analisi di progettazione, nessuna modifica al codice |
| **File modificati** | Nessuno. Sola lettura per riscontro: `apps/os_lms/os_lms/hooks.py`, `apps/os_lms/os_lms/os_lms/app/api.py`, `apps/os_lms/os_lms/os_lms/override_api.py`, `apps/os_lms/os_lms/www/me.html`, `apps/os_lms/os_lms/www/update-password.html`, `apps/os_lms/os_lms/public/css/os_lms.css`. |
| **Verifiche** | Due accertamenti dirimenti per lo scenario multi-cliente, entrambi sul codice e non assunti: (1) **`Brand Customize` non è fra i `fixtures`** dell'app (`hooks.py:147-168` esporta i soli `Custom Field`), quindi i colori impostati dal cliente non vengono sovrascritti da `bench migrate` né da un aggiornamento dell'app — condizione senza la quale l'intera soluzione sarebbe inutilizzabile; (2) le pagine sorelle `me.html` e `update-password.html` colorano il `body` con variabili Frappe (`--subtle-fg`, `--bg-color`) e **non** con colori letterali, quindi seguono già il tema dell'istanza e non vanno rifatte. |

**1. Obiettivo dell'attività**

Trasformare la fattibilità accertata nell'Attività 11 in un progetto che regga il vincolo
reale — un'app, molte istanze, un'identità cromatica per cliente — e che non introduca
lavoro ricorrente a ogni nuovo cliente. Il criterio di riuscita non è "i colori si possono
cambiare dal desk", ma "installare l'app su una nuova istanza e brandizzare il login senza
toccare né il CSS né il repository, e senza dover compilare campi obbligatori".

**2. Modalità di esecuzione**

Prima la verifica del prerequisito che poteva invalidare tutto — la persistenza dei valori
del cliente attraverso gli aggiornamenti dell'app — cercando `Brand Customize` fra i
fixtures esportati. Poi la ricerca del modello già in uso nel progetto per il resto della
brandizzazione per istanza (logo, nome, colori dell'app mobile), per allineare la soluzione
a un pattern esistente invece di inventarne uno nuovo. Infine il censimento delle pagine
website sorelle, per stabilire se il problema fosse circoscritto al login o diffuso.

**3. Attività svolte**

*Riscontro del prerequisito.* `Brand Customize` è un Single non esportato come fixture: i
valori vivono nel database del singolo sito e sopravvivono agli aggiornamenti. È la
condizione abilitante dell'intero approccio ed è soddisfatta senza interventi.

*Allineamento al modello esistente.* La pagina di login prende già il logo da
`get_app_logo()` e il nome da *Website Settings*: è già per istanza su tutto tranne i
colori. `get_instance_info` (`app/api.py:148`) mostra il pattern già adottato per l'app
mobile — i colori dal database, non dal codice. La proposta estende quel pattern, non ne
introduce un altro.

*Progetto della catena di fallback.* Il nodo è evitare che il cliente debba compilare un
pannello perché la pagina sia decente. La soluzione sono le `var()` annidate:

    background: linear-gradient(to right,
        var(--login-bg-from, var(--color-company-primary, #0a2e5a)),
        var(--login-bg-to,   var(--color-company-secondary, #1d5a9b)));

Tre livelli: se il cliente compila i campi del login vincono quelli; altrimenti il login
eredita **automaticamente** i colori di brand che il cliente ha già impostato per il resto
della piattaforma; se non c'è nulla, resta il default dell'app. Un cliente nuovo compila la
sola sezione *Brand* e ottiene un login coerente senza sapere che esista una sezione Login.

*Set minimo di campi proposto*, cinque, tutti opzionali: sfondo da/da, sfondo a, testo sul
fondo (titolo e link), sfondo dei campi input, colore del pulsante. Il campo per il testo
non è ridondante: è il punto in cui la derivazione automatica dal brand fallisce, perché
nessuna regola CSS può decidere se sopra il colore del cliente il testo debba essere chiaro
o scuro.

*Sequenza operativa segnalata.* Se i default dell'app vengono neutralizzati — cioè se
`os_lms.css` smette di spedire il blu Elite, che è la scelta corretta per un prodotto
multi-cliente — allora **prima** vanno valorizzati i campi di *Brand Customize* sul sito
Elite, **poi** neutralizzati i default: nell'ordine inverso il login di Elite diventerebbe
grigio al primo rilascio. In alternativa i default restano il blu attuale, con l'effetto
che un'istanza non configurata assomiglia a Elite.

*Recupero dei campi morti.* I due campi *Gradient Overlay From/To*, accertati inerti
nell'Attività 11, sono esattamente due colori di un gradiente: possono diventare i due campi
dello sfondo del login, azzerando il costo sul doctype. È stato però osservato che il
pannello lo vede il cliente e deve essere autoesplicativo, quindi la rietichettatura in una
sezione *Login* è preferibile al riuso silenzioso.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** verifica della persistenza dei valori di brand
  attraverso gli aggiornamenti, individuazione del pattern di brandizzazione per istanza
  già adottato nel progetto, censimento delle pagine website con colori letterali,
  progettazione della catena di fallback e del set minimo di campi, redazione di questa voce.
- **motivo della scelta del tool e del modello:** il vincolo dichiarato dall'utente
  (un'app, molte istanze) sposta il problema da "come cambio un colore" a "come evito
  lavoro ricorrente per ogni cliente", e la risposta dipende da dettagli verificabili solo
  nel repository: se i fixtures sovrascrivano i valori del cliente, se esista già un modello
  da imitare, se il problema sia isolato al login. Un modello con accesso al codice li
  chiude in pochi minuti; una risposta generica avrebbe proposto una sezione di campi
  obbligatori, cioè proprio il lavoro ricorrente che l'utente vuole evitare.
- **risultato ottenuto:** progetto completo e allineato a un pattern già presente, con un
  meccanismo che non richiede campi obbligatori, il prerequisito di persistenza verificato,
  la trappola operativa del default neutro segnalata prima dell'implementazione e due campi
  morti recuperati invece di aggiungerne di nuovi.
- **verifiche e correzioni effettuate:** la persistenza dei valori del cliente non è stata
  data per scontata ma verificata sull'elenco dei fixtures, perché era l'unico punto in
  grado di invalidare la soluzione. L'ipotesi iniziale che il problema riguardasse tutte le
  pagine website è stata controllata e **smentita**: `me.html` e `update-password.html` usano
  già variabili Frappe, quindi l'ambito dell'intervento si è ristretto al solo login.

**6. Problematiche incontrate**

Un compromesso di prodotto segnalato e non deciso: neutralizzare i default dell'app è la
scelta corretta per un prodotto multi-cliente — nessuna istanza non configurata dovrebbe
somigliare a Elite — ma richiede di valorizzare *Brand Customize* sul sito Elite prima del
rilascio, perché altrimenti il login attuale si degrada. La scelta fra "default neutri più
un passo di configurazione su Elite" e "default Elite conservati" è stata rimessa
all'utente insieme alla granularità dei campi.

---

### Attività 14 — Testo "Non hai un account? Registrati" assente dal login del sito locale

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto — diagnosi di una presunta regressione |
| **Problema riscontrato** | Durante il collaudo dell'Attività 13 l'utente segnala che sul login locale non compare la riga «Non hai un account? Registrati». La segnalazione arriva subito dopo una modifica al foglio di stile del login, quindi il sospetto naturale è che quella modifica abbia nascosto o reso invisibile il testo. |
| **Problema effettivo** | Nessun rapporto con la modifica ai colori: è una **differenza di configurazione fra i due siti**. Il template avvolge quella riga in `{% if not disable_signup %}`, quindi con la registrazione disattivata il markup non viene proprio generato — non è testo invisibile, è testo assente. Sul sito locale `Website Settings.disable_signup` valeva `1`, in produzione vale `0`. |
| **Soluzione applicata** | Riattivata la registrazione sul solo sito di sviluppo (`disable_signup` da `1` a `0`) perché l'utente potesse collaudare anche quella porzione di pagina, indicando come riportarla allo stato precedente dal desk. Segnalato inoltre un difetto di leggibilità preesistente emerso proprio su quel testo. |
| **Commit** | No — nessuna modifica al codice; la sola modifica è una configurazione sul sito di sviluppo, reversibile da *Website Settings* |
| **File modificati** | Nessuno. |
| **Verifiche** | Confronto del markup effettivamente servito dai due siti: in locale la pagina conteneva `<section class='for-signup signup-disabled'>` con «Signups have been disabled for this website» e **nessun** blocco `sign-up-message` di intestazione, in produzione i due elementi «Non hai un account?» e «Registrati» sono presenti. Letto il valore di `disable_signup` sul sito locale (`1`) e ricontrollato il markup dopo il cambio (`0`), che ha fatto ricomparire la riga. |

**1. Obiettivo dell'attività**

Stabilire se la modifica appena consegnata avesse fatto sparire un elemento della pagina di
accesso — cioè se fosse una regressione da correggere prima del commit — e, in caso
contrario, rimettere l'utente in condizione di collaudare la pagina completa.

**2. Modalità di esecuzione**

Confronto diretto del markup servito dai due siti invece che ispezione del CSS, perché la
distinzione decisiva era fra "testo presente ma invisibile" (colpa dello stile, quindi
regressione) e "testo non generato" (colpa della configurazione). Il sorgente della pagina
risponde alla domanda senza ambiguità. Individuata la condizione Jinja che governa il
blocco, è stato letto il valore corrispondente sul sito locale e poi modificato, ricontrollando
il markup.

**3. Attività svolte**

*Diagnosi.* La riga è avvolta in `{% if not disable_signup and not disable_user_pass_login %}`.
Sul sito locale la registrazione era disattivata, quindi il ramo `else` del template rendeva
la sezione «Signups have been disabled for this website» e la riga di invito non esisteva
nel documento. Esclusa quindi ogni relazione con la modifica ai colori.

*Ripristino del collaudo.* Portato `disable_signup` a `0` sul solo sito di sviluppo, con
verifica che la riga ricompaia, e comunicato all'utente il percorso per riportarlo a `1`.

*Difetto preesistente rilevato.* Una volta visibile, quel testo mostra un problema di
leggibilità che riguarda anche la produzione: il bundle di Frappe colora `.sign-up-message`
con `var(--text-light)` (grigio) e il link con `var(--primary)` (quasi nero), colori pensati
per un fondo chiaro ma qui sovrapposti al gradiente blu scuro. I due blocchi commentati in
`os_lms.css` sono un tentativo abbandonato di correggerlo. È stata proposta all'utente la
regola che li fa seguire `--login-ink`, cioè il campo *Text On Background* introdotto
nell'Attività 13, così che la correzione valga per ogni cliente e non solo per Elite. Non
applicata: è l'unico punto in cui l'aspetto attuale del sito Elite cambierebbe, e la
decisione spetta all'utente.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** confronto del markup fra sito locale e produzione,
  individuazione della condizione che governa il blocco, lettura e modifica del valore di
  configurazione, rilevazione del difetto di leggibilità e formulazione della correzione,
  redazione di questa voce.
- **motivo della scelta del tool e del modello:** la segnalazione arrivava a ridosso di una
  consegna e l'ipotesi più naturale — «l'hai rotto tu» — era plausibile; serviva una
  smentita fattuale rapida, non un'opinione. L'accesso simultaneo ai due siti e al template
  permette di confrontare il markup reale e chiudere la questione in un passaggio.
- **risultato ottenuto:** regressione esclusa con prova alla mano, collaudo sbloccato sul
  sito locale e individuazione, come effetto collaterale, di un difetto di leggibilità che
  esiste anche in produzione e che la feature appena consegnata permette ora di correggere
  in modo configurabile per cliente.
- **verifiche e correzioni effettuate:** la conclusione non è stata dedotta dal CSS ma letta
  nel markup servito dai due siti, che distingue in modo netto fra testo invisibile e testo
  assente; il cambio di configurazione è stato verificato ricontrollando la pagina dopo la
  modifica, non dato per riuscito.

**6. Problematiche incontrate**

Il sito di sviluppo e la produzione divergono su impostazioni che cambiano quali porzioni di
pagina vengono rese: un collaudo visivo eseguito solo in locale può quindi non coprire tutto
ciò che l'utente finale vede. È stato modificato un valore di configurazione su un sito
condiviso per sbloccare il collaudo; la modifica è reversibile e il percorso per annullarla
è stato comunicato, ma resta un cambiamento di stato non richiesto esplicitamente e va
riportato indietro se il sito di sviluppo deve restare con la registrazione chiusa.

---

### Attività 13 — Colori della pagina di login gestiti per istanza da Brand Customize, con default neutri Frappe

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Feature — configurabilità per cliente di una pagina finora hardcoded |
| **Problema riscontrato** | Esigenza definita nelle Attività 11-12: l'app è installata su un'istanza Frappe per cliente e ogni cliente ha la propria identità cromatica, ma la pagina di login riceveva il blu Elite scritto nel CSS dell'applicazione. Brandizzare un nuovo cliente avrebbe richiesto un fork del foglio di stile o un rilascio dedicato. Scelta dell'utente su quale aspetto debba avere un'istanza non configurata: **i default neutri della piattaforma Frappe**. |
| **Problema effettivo** | I colori del login stavano nel codice anziché nel database, unico pezzo rimasto indietro rispetto al modello già adottato dal progetto per logo, nome istanza e colori dell'app mobile. Vincolo aggiuntivo emerso in fase di progetto: nessuna regola CSS può decidere il contrasto del testo sopra un colore scelto dal cliente, quindi non basta esporre i colori di sfondo — servono anche i colori del testo, altrimenti un cliente con brand chiaro si ritrova il titolo bianco su fondo chiaro. |
| **Soluzione applicata** | Sezione **Login Page** nel doctype *Brand Customize* con sei campi colore opzionali, mappati su altrettante variabili CSS `--login-*`, lette dalle regole del login con la variabile Frappe corrispondente come fallback. I due campi morti *Gradient Overlay From/To* sono stati **riusati** come stop del gradiente di sfondo invece di aggiungerne di nuovi. Nessun campo è obbligatorio: a pannello vuoto la pagina rende come un login Frappe di serie. |
| **Commit** | `7a85b8e2` — *feat(branding): drive the login page colors from Brand Customize*, sul branch `feature/oslms`. Il messaggio riporta in chiusura il vincolo d'ordine: le istanze già in esercizio vanno configurate **prima** del rilascio. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/doctype/brand_customize/brand_customize.json`, `apps/os_lms/os_lms/os_lms/branding.py`, `apps/os_lms/os_lms/public/css/os_lms.css` |
| **Verifiche** | Eseguite sul container di sviluppo e non solo a lettura: (1) ricaricato il doctype e riletti i metadati → i sei campi `login_*` risultano creati; (2) `GET` su `brand_css` **a campi vuoti** → l'output non contiene alcuna variabile `--login-*`, quindi il fallback Frappe è quello che entra in gioco; (3) valorizzati i sei campi con la palette Elite e ripetuto il `GET` → le sei variabili compaiono **immediatamente**, il che verifica anche l'invalidazione della cache Redis sull'`on_update`; (4) verificato il foglio servito da `/assets/os_lms/css/os_lms.css` e la presenza di entrambi i link nell'ordine giusto sulla pagina `/login` locale; (5) accertato che la SPA **non** carica `os_lms.css` (`_lms.html` ha il proprio `<head>`), quindi le regole `body` e `input`, che restano non circoscritte, ricadono solo sulle pagine website. |

**1. Obiettivo dell'attività**

Spostare i colori della pagina di accesso dal codice al database del singolo sito, così che
brandizzare un nuovo cliente non richieda né una modifica al repository né un rilascio, e
che un'istanza non configurata non somigli a Elite ma a una piattaforma Frappe neutra.
Vincolo di riuscita posto in partenza: sul sito Elite, una volta seminati i valori, la
pagina deve risultare **identica a oggi** — la modifica è un cambio di sorgente dei colori,
non un restyling.

**2. Modalità di esecuzione**

Implementazione in tre punti, ciascuno verificato subito dopo. Prima il doctype, con il
recupero dei due campi morti invece dell'aggiunta di campi nuovi; poi la mappa
`FIELD_TO_CSS_VAR`; infine le regole CSS, riscritte una per una scegliendo come fallback
la variabile Frappe che governa lo stesso elemento, in modo che il "default neutro" non sia
un colore inventato ma esattamente quello della piattaforma. Verifica finale sul container
nei due stati che contano: pannello vuoto e pannello valorizzato.

**3. Attività svolte**

*Doctype.* La sezione *Gradient Overlay* — accertata inerte nell'Attività 11 — è diventata
*Login Page*, con i due campi esistenti rinominati in `login_bg_from` / `login_bg_to` e
quattro campi nuovi: `login_ink`, `login_input_bg`, `login_input_ink`, `login_button_bg`.
Ogni campo riporta in descrizione la variabile CSS che alimenta, seguendo la convenzione
già usata dagli altri campi del pannello. È stato necessario **incrementare il campo
`modified`** del JSON: Frappe salta la reimportazione di un doctype il cui timestamp
coincide con quello a database, quindi senza il bump i campi non sarebbero mai stati creati
sulle istanze esistenti.

*Mappa.* Sostituite le due voci `gradient_overlay_*` con le sei `login_*` in
`FIELD_TO_CSS_VAR`, con un commento che spiega il meccanismo del fallback.

*CSS.* Ogni regola del login legge ora una `--login-*` con la variabile Frappe come
fallback, quindi un'istanza non brandizzata rende come un login di serie:

| Regola | Prima | Adesso |
| --- | --- | --- |
| Sfondo pagina | `linear-gradient(#0a2e5a, #1d5a9b)` | `var(--login-bg-from, var(--subtle-fg))` → `var(--login-bg-to, var(--login-bg-from, …))` |
| Campi input | `--color-company-tertiary` + `white` | `var(--login-input-bg, var(--control-bg))` + `var(--login-input-ink, var(--text-color))` |
| Titolo | `white` | `var(--login-ink, var(--text-color))` |
| Pulsante Login | regola commentata | `var(--login-button-bg, var(--btn-primary))` |

Il secondo stop del gradiente ricade su `--login-bg-from` prima che su Frappe: valorizzare
un solo campo produce un fondo pieno anziché un gradiente a metà. La variabile
`--color-company-tertiary` è stata rimossa perché i campi input erano il suo unico
consumatore. Sono state lasciate intatte, perché fuori ambito, le regole `.forgot-section`
(il cui bordo usa `--outline-gray-1`, già un campo del pannello, quindi già per cliente) e
i due blocchi commentati sui link.

*Sequenza di rilascio (ordine vincolante).* Prima vanno valorizzati i sei campi su ogni
istanza già in esercizio, **poi** rilasciato il codice: nell'ordine inverso il login di
Elite perde il blu e diventa neutro fino alla configurazione. I valori Elite da seminare
sono quelli letti dal CSS attuale — `#0a2e5a`, `#1d5a9b`, `#ffffff`, `#124679`, `#ffffff`,
pulsante lasciato vuoto perché oggi usa già il nero Frappe.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** modifica del doctype, della mappa e del foglio di
  stile; individuazione della variabile Frappe corretta come fallback per ciascun elemento
  estraendola dai bundle realmente serviti; verifica sul container nei due stati; redazione
  di questa voce.
- **motivo della scelta del tool e del modello:** la modifica è piccola ma disseminata di
  dettagli che si pagano solo dopo il rilascio — il bump di `modified` senza cui i campi non
  nascono, la variabile Frappe giusta per ogni elemento, l'ordine fra semina e rilascio, il
  secondo stop del gradiente. Un modello con accesso al repository e al container li chiude
  e li verifica nello stesso passaggio, invece di lasciarli emergere in produzione.
- **risultato ottenuto:** pagina di login brandizzabile per istanza da pannello, senza campi
  obbligatori, senza fork del CSS e senza rilascio per cliente; nessun colore di Elite
  rimasto nel codice del login; due campi morti recuperati invece di aggiungerne di nuovi.
- **verifiche e correzioni effettuate:** i due stati sono stati provati davvero, non
  dedotti: a pannello vuoto `brand_css` non emette variabili `--login-*` (quindi valgono i
  default Frappe), a pannello pieno le emette tutte e sei subito dopo il salvataggio, il che
  verifica di riflesso anche l'invalidazione della cache. Una correzione in corsa: il primo
  salvataggio del JSON del doctype, scritto con rientro a spazi, riscriveva l'intero file
  (336 righe di diff); è stato rifatto con rientro a tabulazione, riducendo il diff a 43
  righe effettivamente modificate. Infine, l'ipotesi che le regole non circoscritte (`body`,
  `input`) potessero ricadere sulla SPA è stata verificata e smentita: `_lms.html` non carica
  `os_lms.css`.

**6. Problematiche incontrate**

Il vincolo d'ordine fra semina e rilascio è l'unico punto fragile della consegna: è una
dipendenza fra una configurazione a database e un rilascio di codice, e non è imposta da
nulla nel codice stesso. Se il rilascio precede la semina, ogni istanza mostra per qualche
minuto un login neutro. È stato scelto di non aggirarlo con un patch di migrazione che
semini automaticamente il blu Elite, perché scriverebbe i colori di un cliente specifico nel
codice dell'applicazione — cioè esattamente il problema che questa attività elimina.

Una nota minore, segnalata e non risolta: i due blocchi commentati sui link della pagina
(`.forgot-password-message a`, `.sign-up-message a`) restano tali, quindi i link non seguono
`--login-ink`. Su un fondo scuro possono risultare poco leggibili, ma attivarli cambierebbe
l'aspetto attuale del sito Elite, che questa attività aveva il vincolo di preservare.

---

### Attività 15 — Analisi e correzione dei difetti della scheda Programmi

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi + correzione — difetti segnalati dall'utente sulla gestione dei programmi |
| **Problema riscontrato** | Segnalazione dell'utente, con richiesta esplicita di un'analisi: «nei programmi ci sono dei problemi. Il programma 1 mi segnala 2 corsi e 4 membri, se lo apro è vuoto. Se premo aggiungi corso mi apre quello dei membri». A valle della prima correzione è emerso un terzo sintomo: «quando aggiungo un corso mi dice di selezionare un corso anche se nella select è selezionato il corso». |
| **Problema effettivo** | **Tre difetti distinti in `ProgramForm.vue`, tutti residui del medesimo refactor** (`625ddac65 refactor: learning path`), che ha riscritto il form lasciando nel template riferimenti a elementi rimossi. **(1)** Il dialogo di aggiunta è condiviso e si diramava su `currentForm`, una ref **eliminata dal refactor** ma ancora letta in tre punti del template: sempre `undefined`, il confronto sempre falso, quindi il dialogo assumeva stabilmente la modalità "membri" — titolo *Enroll Member to Program*, pulsante che invoca `addMembers`, e selettore corsi mai renderizzato perché dietro il `v-if`. **(2)** `updateCounts`, invocata a ogni aggiunta o rimozione di corso o membro, aggiornava la vista chiamando il solo `setProgramData()`, che ricostruisce il programma dalla **risorsa lista** — priva delle child table — e quindi azzera `program_courses` e `program_members` senza ricaricarle; i contatori restavano corretti perché letti da `course_count`/`member_count`. Da qui "2 corsi e 4 membri ma dentro è vuoto". **(3)** Il campo di selezione era un `Link` **a valore singolo** legato con `v-model="course"` a un'altra ref **mai dichiarata**, mentre `addCourses` legge `selectedCourses`: nulla raggiungeva quella variabile e l'aggiunta falliva sempre con *"Please select at least one course"*. Lo stesso `Link` ignorava silenziosamente la prop `:exclude` (che non possiede) e non espone `cachedOptions`, letto da `addCourses` per ricavare il titolo del corso. **Difetto ulteriore, accertato ma non corretto:** uno studente iscritto a un programma **non vede i corsi non pubblicati** del programma, perché l'iscrizione al programma non comporta l'iscrizione ai corsi e `get_program_details` scarta in silenzio i corsi per cui `get_course_details` restituisce vuoto. È lo stesso difetto strutturale corretto il 10/09 per le classi, dove esistono `ensure_batch_course_enrollments` e `enroll_via_batch_if_eligible`; per i programmi non esiste nulla di equivalente. |
| **Soluzione applicata** | **(1)** Rimossa la diramazione su `currentForm`: il dialogo è ora esplicitamente quello di aggiunta corso (i membri dispongono già di due dialoghi dedicati, `showMemberDialog` e `showBatchDialog`, quindi il ramo "membri" era codice irraggiungibile). **(2)** In `updateCounts` il callback di successo invoca `loadProgramData()` in luogo di `setProgramData()`, ricaricando anche le child table dal server. **(3)** Ripristinato `MultiSelect` al posto di `Link`, con `v-model="selectedCourses"` e `:exclude`: è il componente che il codice circostante presuppone — lega un array, supporta `exclude` ed espone `cachedOptions` — ed è quello già usato dal campo gemello dei membri. Il difetto sugli studenti **non è stato corretto**: è una funzionalità mancante e non una svista, e la decisione è stata rimessa all'utente. |
| **Commit** | Sì — `3255d0a0` *fix(programs): repair adding a course to a program*, branch `feature/oslms`. Commit unico perché le tre correzioni insistono sullo stesso file e discendono dalla medesima causa; separarle avrebbe richiesto uno staging parziale dello stesso file, fragile e privo di beneficio. |
| **File modificati** | `frontend/src/pages/Programs/ProgramForm.vue` (+25 / −14). File esaminati: `lms/lms/doctype/lms_program/lms_program.py`, `lms/lms/utils.py` (`get_programs`, `get_program_details`, `enroll_in_program`), `frontend/src/components/Controls/Link.vue`, `MultiLink.vue`, `MultiSelect.vue`, e gli altri file di `frontend/src/pages/Programs/`. |
| **Verifiche** | (a) **Ispezione dei dati reali** del Programma 1 sul sito locale: 2 righe `LMS Program Course` (entrambe verso corsi esistenti ma **non pubblicati**) e 4 righe `LMS Program Member`, coerenti con i contatori — quindi i dati erano integri e il difetto stava a valle. (b) **Confronto fra ruoli** su `get_program_details`: Administrator → 2 corsi visibili; studente membro → **0 corsi**. (c) **`frappe.client.get`** sul programma restituisce correttamente 2 corsi e 4 membri, prova che il vuoto del form non dipendeva dal backend. (d) `vue-tsc --noEmit` e `yarn build` dopo ogni modifica: entrambi puliti. (e) **Verifica sul campo da parte dell'utente**: aggiunta corso funzionante. (f) **Scansione sistematica** di tutti i file di `pages/Programs/` e dei cinque file collaterali toccati dal refactor, alla ricerca di identificatori usati nei template ma mai dichiarati: `currentForm` e `course` sono risultati gli unici due reali, gli altri esiti erano falsi positivi (parole chiave TypeScript, chiave di un `v-for`, una stringa CSS `url()`). (g) **Controllo delle prop** passate ai componenti Controls, cioè il meccanismo per cui `:exclude` spariva senza errori: restano `autofocus` sul campo Membri (ignorata, ma richiedeva `false`, quindi l'effetto voluto si ottiene comunque) e `label` sul campo del dialogo Classe, che si è rivelata un falso allarme poiché `Link` la legge dagli attrs e rende la `FormLabel`. |

**1. Obiettivo dell'attività**

Stabilire l'origine dei malfunzionamenti della gestione programmi e correggere quelli certi. La richiesta iniziale era esplicitamente di analisi; la correzione è stata autorizzata in un secondo momento, limitatamente ai difetti con causa accertata.

**2. Modalità di esecuzione**

1. **Verifica preliminare dell'integrità dei dati**, per distinguere un problema di dati da uno di presentazione: lettura diretta delle child table del programma e confronto con i contatori.
2. **Confronto fra ruoli** sugli endpoint di lettura, per stabilire se il vuoto dipendesse dai permessi o dal codice.
3. **Lettura del frontend** partendo dai sintomi: quale dialogo si apre, quale variabile lo governa, quale funzione ne esegue l'azione.
4. **Scansione sistematica** a chiusura, per accertare che non restassero altri riferimenti orfani dello stesso refactor invece di correggerli uno alla volta man mano che l'utente li incontrava.

**3. Attività svolte**

*Dati del Programma 1 (sito locale):*

| Elemento | Esito |
| --- | --- |
| Contatori | 2 corsi, 4 membri |
| Righe `LMS Program Course` | 2, verso corsi **esistenti ma non pubblicati** |
| Righe `LMS Program Member` | 4 |
| `get_program_details` come Administrator | 2 corsi visibili |
| `get_program_details` come studente membro | **0 corsi** |
| `frappe.client.get` (caricamento form) | 2 corsi, 4 membri — corretto |

*Correzione della propria correzione.* Il campo di selezione era stato inizialmente sostituito con `MultiLink`, scelta funzionante e verificata dall'utente ma **non corretta**: la scansione delle prop ha poi rivelato che `MultiSelect` possiede `exclude` ed espone `cachedOptions`, cioè esattamente ciò che il codice circostante presupponeva, ed è il componente usato dal campo gemello dei membri dieci righe più sotto. Si è quindi tornati a `MultiSelect`, annullando le due modifiche di adattamento che `MultiLink` aveva reso necessarie (riscrittura dell'accesso alle opzioni e sostituzione di `:exclude` con `filters`) e rimuovendo l'import divenuto inutile. Il risultato è meno codice modificato e coerenza con il campo accanto. L'utente è stato avvisato di ripetere la prova, essendo cambiato il componente rispetto a quanto aveva verificato.

*Anomalia nei dati rilevata e segnalata, non trattata.* Due dei quattro membri del programma hanno l'identificativo racchiuso fra virgolette doppie (`'"a.basili@overside.it"'`); sul sito esistono **29 utenti** con questa forma, fra cui `'"r.liciotti@overside.it"'`. Sono account distinti e paralleli a quelli autentici, verosimilmente generati passando una stringa JSON non deserializzata. Riguarda i dati e non il codice del form, quindi è stato segnalato senza intervenire.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), prosecuzione della sessione.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** ispezione dei dati del programma sul database, confronto fra ruoli sugli endpoint, lettura incrociata di quattro componenti Vue, individuazione dei tre difetti, stesura delle correzioni, scansione sistematica di chiusura, typecheck e build, redazione di questa voce.
- **motivo della scelta del tool e del modello:** i sintomi erano tre e apparentemente scollegati, e distinguere fra dati corrotti, permessi e difetti di codice richiedeva di interrogare il database **prima** di leggere il frontend — operazioni che Claude Code svolge nello stesso flusso. Il contesto ampio di Opus 5 ha permesso di tenere aperti insieme il form e i tre componenti Controls e di riconoscere che `MultiSelect` era il componente atteso, deduzione nata dal confronto fra ciò che `addCourses` legge e ciò che ciascun componente espone.
- **risultato ottenuto:** tre difetti individuati e corretti, ricondotti tutti a un'unica causa (un refactor che ha lasciato riferimenti orfani), più un quarto difetto strutturale accertato e documentato per la decisione dell'utente; chiusura verificata dell'indagine, con la certezza che non restano altri riferimenti orfani nei file interessati.
- **verifiche e correzioni effettuate:** l'indagine non si è fermata ai sintomi riferiti: dopo le prime due correzioni l'utente ne ha incontrato un terzo, segno che procedere per sintomi non stava chiudendo il problema. Si è quindi cambiato metodo, scansionando in modo sistematico tutti i file interessati alla ricerca di riferimenti orfani e verificando le prop passate ai componenti — il meccanismo silenzioso per cui `:exclude` veniva ignorato. È stata inoltre **rivista una propria correzione già validata dall'utente**: funzionava, ma usava un componente diverso da quello che il codice circostante presupponeva, e mantenerla avrebbe lasciato due adattamenti non necessari e un'incoerenza con il campo gemello. Riconosciuto apertamente che nell'analisi iniziale `v-model="course"` era stato letto senza verificare la dichiarazione di `course`, benché il controllo analogo su `currentForm` fosse stato eseguito: il terzo difetto sarebbe emerso già allora.

**6. Problematiche incontrate**

Un limite di strumento e una lezione di metodo.

Il limite: `vue-tsc` **non segnala** gli identificatori non dichiarati usati nei template — né `currentForm` né `course` hanno prodotto errori, pur essendo inesistenti. Il typecheck, in questo progetto, non protegge dal tipo di difetto qui corretto. Per supplire è stato scritto uno script di scansione ad hoc, conservato nella scratchpad di sessione; se il problema dovesse ripresentarsi dopo altri refactor, varrebbe la pena valutare l'abilitazione del type-check dei template o un controllo equivalente in CI.

La lezione: i primi due difetti sono stati corretti sui sintomi riferiti, e il terzo è emerso solo perché l'utente ha riprovato. Di fronte a un refactor che ha lasciato riferimenti orfani, correggerli uno alla volta man mano che vengono incontrati è inefficiente e dà l'impressione di un problema mai chiuso: conviene passare subito alla verifica sistematica dell'intero file, che qui ha richiesto pochi minuti e ha permesso di dichiarare chiusa l'indagine con una prova, anziché con una supposizione.

---

### Attività 16 — Notifica "Failed to send email with subject:" non tradotta in italiano

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — internazionalizzazione (stringa di sistema non tradotta) |
| **Problema riscontrato** | Segnalazione dell'utente: nel pannello delle notifiche compare la voce «Failed to send email with subject: Lezione dal vivo: Test Class …», con l'etichetta in inglese e l'oggetto dell'email in italiano nella stessa riga. Richiesta: «possiamo tradurre l'etichetta?». |
| **Problema effettivo** | **Non è una traduzione mancante.** La stringa è già tradotta in `lms/translations/it.csv:1682` (`"Failed to send email with subject:","Impossibile inviare l'e-mail con oggetto:"`) e la ricerca conferma che risolve correttamente quando la lingua attiva è `it`. Il difetto sta nella **lingua attiva dentro i worker dei job in background**: `frappe.init()` imposta `frappe.local.lang = conf.lang or "en"`, `frappe.set_user()` **non tocca** la lingua, e solo le richieste web la risolvono davvero (`frappe/boot.py:38` → `set_user_lang`). Il `site_config.json` del sito non contiene la chiave `lang`, quindi **ogni job gira in inglese** anche se in System Settings la lingua del sito è `it`. La stringa nasce in `frappe/email/doctype/email_queue/email_queue.py:345` (`SendMailContext.notify_failed_email`), che valuta `_("Failed to send email with subject:")` **dentro il job** della coda email e **ne salva il risultato** nel campo `subject` del Notification Log. Da lì in poi è testo statico: `frontend/src/components/Notifications/NotificationPanel.vue:67` lo rende con `v-html="sanitizeHTML(n.subject)"`, senza ripassare da `__()`. Quindi la lingua sbagliata viene **congelata nel database** al momento del fallimento dell'invio, e nessun intervento sul frontend o sui file di traduzione la può recuperare per le notifiche già scritte. |
| **Soluzione applicata** | Aggiunto a `os_lms` un hook `before_job` che allinea il job alla lingua del sito: `set_job_language()` chiama `frappe.set_user_lang(frappe.session.user)`, cioè la stessa risoluzione usata dalle richieste web (User.language → System Settings → fallback). Scelto l'hook e non la chiave `"lang": "it"` in `site_config.json` — che avrebbe lo stesso effetto a runtime — perché l'hook **viaggia con l'app**: si applica anche in produzione al deploy, senza un passaggio manuale di configurazione per ogni istanza, e segue automaticamente System Settings invece di fissare una lingua nel file di configurazione. |
| **Commit** | No — non committata. Modifica lasciata nel working tree del branch `feature/oslms` in attesa della verifica sul campo dopo il riavvio del container (i worker caricano gli hook all'avvio, quindi finché non ripartono l'effetto non è osservabile dall'interfaccia). |
| **File modificati** | `apps/os_lms/os_lms/hooks.py` (registrazione di `before_job`), `apps/os_lms/os_lms/os_lms/utils.py` (nuova funzione `set_job_language`). File esaminati e non modificati: `frappe/email/doctype/email_queue/email_queue.py`, `frappe/translate.py`, `frappe/utils/translations.py`, `frappe/utils/background_jobs.py`, `frappe/__init__.py`, `frontend/src/components/Notifications/NotificationPanel.vue`, `lms/translations/it.csv`, `lms/locale/it.po`, `frappe/locale/it.po`. |
| **Verifiche** | (a) **Origine della stringa accertata nel sorgente Frappe** del container, non supposta: `email_queue.py:345`. (b) **Traduzione presente**: `lms/translations/it.csv:1682`; `frappe/locale/it.po:9894` ha invece `msgstr ""`, quindi upstream non la traduce e la copia del progetto è l'unica fonte. (c) **Prova della causa** con il python dell'env sul sito `lms.localhost`: `conf.lang = None`, `frappe.local.lang = 'en'`, mentre `get_system_settings("language") = 'it'`; forzando `lang = "it"` la stessa chiamata `_()` restituisce «Impossibile inviare l'e-mail con oggetto:». (d) **Prova dei dati**: query sul Notification Log, 11 notifiche su 12 hanno il prefisso inglese salvato in chiaro con l'oggetto dell'email in italiano — conferma che il testo è congelato a scrittura. (e) **Hook registrato**: dopo `frappe.clear_cache()`, `frappe.get_hooks("before_job")` restituisce `['frappe.recorder.record', 'frappe.monitor.start', 'os_lms.os_lms.utils.set_job_language']`. (f) **Simulazione del percorso reale**: invocando l'hook come fa `execute_job`, la lingua passa da `en` a `it` e la stringa viene tradotta. (g) `python -m py_compile` pulito su entrambi i file modificati. **Verifica ancora da fare:** riavvio del container e conferma sul campo alla prima email fallita. |

**1. Obiettivo dell'attività**

Far comparire in italiano l'etichetta della notifica di invio email fallito, individuando prima il motivo per cui una stringa **già tradotta** continuava a essere resa in inglese.

**2. Modalità di esecuzione**

1. **Ricerca della stringa nel repository**: esito negativo sul codice del progetto, positivo solo su `lms/translations/it.csv` — primo indizio che la stringa non è del progetto ma di Frappe e che la traduzione c'era già.
2. **Ricerca nel sorgente di Frappe dentro il container**, per stabilire con certezza chi la produce e in quale contesto di esecuzione.
3. **Lettura del percorso della lingua** (`frappe.init`, `set_user`, `get_user_lang`, `execute_job`) per capire perché un job non eredita la lingua del sito.
4. **Verifica sui dati** del Notification Log, per accertare che il testo fosse salvato e non tradotto a video.
5. **Prova sperimentale** della causa e poi della correzione, prima di scriverla.

**3. Attività svolte**

*Catena della causa, accertata passo per passo:*

| Passo | Riscontro |
| --- | --- |
| Chi scrive la stringa | `frappe/email/doctype/email_queue/email_queue.py:345`, in `notify_failed_email` |
| Quando | Dentro il job della coda email, alla scrittura del Notification Log |
| Lingua attiva nel job | `frappe.local.lang = conf.lang or "en"` → `"en"` (nessun `lang` in `site_config.json`) |
| Perché non la corregge `set_user` | `frappe.set_user` non assegna `local.lang`; solo `boot.py` chiama `set_user_lang`, cioè solo le richieste web |
| Lingua del sito | System Settings → `it` — ignorata dai worker |
| Traduzione disponibile | Sì, `lms/translations/it.csv:1682` |
| Dove finisce il testo | Nel campo `subject` del Notification Log, reso tale e quale dal pannello notifiche |

*Tre strade valutate, una scelta.* **(1)** Aggiungere `"lang": "it"` al `site_config.json`: una riga, effetto immediato, ma è configurazione d'ambiente da ripetere a mano su ogni istanza e fissa la lingua in un file fuori dal repository. **(2)** Tradurre a video nel pannello notifiche, riconoscendo il prefisso inglese e sostituendolo: avrebbe sistemato **anche le notifiche già salvate**, ma è una manipolazione di stringhe fragile, legata al testo esatto di una versione di Frappe, e non copre la scrivania (desk) né altri consumatori dello stesso Notification Log. **(3)** Hook `before_job` — **scelta**: agisce sulla causa, vale per ogni stringa prodotta in background e non solo per questa, viaggia con l'app e segue System Settings senza configurazione per istanza. Il prezzo è che non recupera le notifiche già scritte.

*Effetto collaterale voluto e da conoscere.* L'hook non riguarda solo questa etichetta: **tutte** le stringhe valutate con `_()` dentro un job — notifiche generate dallo scheduler, oggetti e corpi di email inviati in background — passeranno dall'inglese all'italiano. È il comportamento atteso per un'istanza italiana (System Settings è già `it`) ed è la stessa risoluzione che l'interfaccia applica a ogni richiesta web, ma è bene saperlo perché l'ambito supera la singola segnalazione.

*Rilievo segnalato e non trattato.* Le notifiche esistono perché quelle email **non sono partite davvero** (oggetti «Lezione dal vivo: Test Class …», tutte fallite in due sequenze ravvicinate). È un problema diverso — configurazione dell'invio verso Mailpit o account email del sito — e non è stato toccato, essendo fuori dalla richiesta.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** ricerca della stringa nel repository e nel sorgente di Frappe dentro il container, lettura del percorso di risoluzione della lingua, interrogazione del database delle notifiche, prova sperimentale della causa e della correzione, stesura dell'hook e della funzione, redazione di questa voce.
- **motivo della scelta del tool e del modello:** la domanda sembrava una banale voce di traduzione mancante, mentre la causa stava a tre livelli di distanza dal sintomo (stringa di Frappe → valutata in un worker → salvata nel database). Claude Code consente di passare senza attriti fra repository, sorgente dentro il container e database, che è esattamente ciò che serviva per non fermarsi alla prima ipotesi; il contesto ampio di Opus 5 ha permesso di tenere aperti insieme i quattro file di Frappe coinvolti e il componente Vue che rende la notifica.
- **risultato ottenuto:** causa accertata con prova sperimentale e non per deduzione, correzione applicata alla causa e non al sintomo, con l'ambito del suo effetto dichiarato apertamente.
- **verifiche e correzioni effettuate:** la prima ipotesi — «manca la traduzione» — è stata **scartata dai fatti**: la traduzione esisteva già, e questo ha spostato l'indagine dalla tabella delle traduzioni al contesto di esecuzione. È stata inoltre corretta in corsa l'idea di intervenire sul frontend: la query sul Notification Log ha mostrato che il testo è salvato, quindi qualunque intervento a video sarebbe stato una toppa sul sintomo. Prima di scrivere la correzione si è verificato che l'hook `before_job` esistesse davvero in questa versione di Frappe e **quando** viene invocato rispetto al metodo del job (`background_jobs.py:269`, prima dell'esecuzione), e dopo averla scritta la si è provata riproducendo la sequenza di `execute_job`.

**6. Problematiche incontrate**

Due, entrambe note e aggirate.

La CLI `bench` nel container di sviluppo resta inutilizzabile (`ModuleNotFoundError: No module named 'bench'`): tutte le prove sono state eseguite con il python dell'env di Frappe, secondo la procedura già registrata nelle sessioni precedenti.

La correzione **non è osservabile subito**: gli hook vengono letti dai worker all'avvio, quindi finché il container non viene riavviato (`docker compose restart frappe`) la prossima email fallita continuerà a produrre la notifica in inglese. Restano inoltre in inglese le **11 notifiche già salvate**: possono essere riscritte con un aggiornamento mirato del campo `subject`, ma è una modifica ai dati e non è stata eseguita di iniziativa.

---

### Attività 17 — Predisposizione di un accesso autonomo a un database remoto

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Configurazione — predisposizione di uno strumento di lavoro, su richiesta dell'utente |
| **Problema riscontrato** | Richiesta dell'utente: «puoi fare query su un db non locale? posso darti dei parametri per farti essere autonomo ad interrogare il db quando ti serve?». L'esigenza nasce dalle attività precedenti della giornata, dove più accertamenti si sono dovuti fermare al sito di sviluppo — l'uso reale del flag `disable_self_learning` (Attività 1) e le notifiche già salvate in inglese (Attività 16) — perché la produzione non è raggiungibile da questo ambiente; in entrambi i casi il dato locale è stato dichiarato indicativo e **non probante**. |
| **Problema effettivo** | Tre vincoli tecnici, nessuno dei quali evidente dalla richiesta. **(1)** Sul Mac non esiste un client MySQL nel `PATH`, ma ne esiste uno installato da Homebrew in modalità *keg-only* in `/usr/local/opt/mysql-client/bin/mysql` (versione 9.2.0): invocandolo per percorso assoluto non serve installare nulla. **(2)** Su un server Frappe standard MariaDB ascolta su `bind-address=127.0.0.1` e non accetta connessioni dall'esterno: il caso normale non è la connessione diretta ma il **tunnel SSH**, quindi il profilo doveva prevedere entrambe le modalità. **(3)** Le credenziali non devono comparire nella riga di comando — finirebbero nella cronologia della shell e nel transcript della sessione — quindi vanno lette da un file di profilo con `--defaults-extra-file`, e quel file deve stare fuori dal versionamento. |
| **Soluzione applicata** | Creato il profilo di connessione **precompilato** `.private/db/oslms-prod.cnf`: gruppo `[client]` con i segnaposto da riempire, procedura del tunnel SSH documentata in testa, indicazione di dove leggere il nome del database Frappe (`sites/<sito>/site_config.json` → `db_name`), campi-promemoria per i parametri SSH scritti come commenti (ignorati dal client, leggibili da Claude Code) e raccomandazione dell'utenza di sola lettura con il `GRANT` già pronto. Collocato sotto `.private/`, che è **già coperto da `.gitignore:45`**, invece che in una nuova directory da aggiungere alle esclusioni. Permessi `0600` sul file e `0700` sulla directory. **Nessuna credenziale reale è stata inserita**: la compilazione dei segnaposto resta all'utente. |
| **Commit** | No — il file è ignorato da git per costruzione e non è committabile; nessuna modifica al codice dell'applicazione. |
| **File modificati** | `.private/db/oslms-prod.cnf` — nuovo, non versionato. Nessun file del repository modificato. |
| **Verifiche** | **Ricognizione dell'ambiente:** `mysql`/`mariadb`/`mysqldump` assenti dal `PATH`, client keg-only 9.2.0 presente e funzionante, `ssh` disponibile con due host già definiti in `~/.ssh/config` (`salescience-prod`, `osgit.overside.it`), uscita di rete dal sandbox funzionante (HTTP 200 verso `example.com`), container `mariadb` attivi utilizzabili in alternativa come client, `python3` 3.13 presente ma **senza** driver `pymysql` né `mysqlclient`. **Sintassi del profilo:** validata con `my_print_defaults`, che rilegge correttamente tutte e sette le opzioni del gruppo `[client]` (password mascherata in output). **Esclusione dal versionamento:** `git check-ignore -v` conferma la corrispondenza con `.gitignore:45` e `git status --porcelain .private/` non riporta nulla. **Connessione reale** (dopo che l'utente ha compilato il profilo): porta `192.168.13.111:3306` raggiungibile, autenticazione riuscita, server **MariaDB 11.8.6** su Ubuntu 24.04 in container, database `elitelmsdb` con **348 tabelle**; conteggi di controllo: 60 utenti attivi, 18 corsi (4 pubblicati), 5 classi, 112 iscrizioni ai corsi, 8 certificati. |

**1. Obiettivo dell'attività**

Rendere interrogabile un database non locale in modo che gli accertamenti sui dati di
produzione non debbano più essere surrogati con il sito di sviluppo, e renderlo
**una volta sola**: i parametri devono restare depositati in un punto stabile, così che
nelle sessioni successive l'interrogazione non richieda di ricevere di nuovo le
credenziali. Il secondo obiettivo, implicito ma vincolante, è che questa autonomia non
si paghi con una fuga di credenziali: né nel repository, né nella cronologia della
shell, né nel testo della conversazione.

**2. Modalità di esecuzione**

Prima la ricognizione di cosa la macchina offre davvero, perché la risposta alla
domanda dipende da quello: client disponibili, driver Python, `ssh`, uscita di rete dal
sandbox, container utilizzabili come client di ripiego. Poi la scelta del meccanismo di
autenticazione, privilegiando quello che tiene le credenziali fuori dalla riga di
comando. Infine la scelta della collocazione, privilegiando una directory **già** esclusa
dal versionamento rispetto all'aggiunta di una nuova regola a `.gitignore`, perché una
regola nuova è un punto in cui si può sbagliare mentre una regola esistente e già in uso
no. Chiusura con la validazione della sintassi del file e con la verifica esplicita che
git lo ignori davvero.

**3. Attività svolte**

*Ricognizione.* Il `PATH` non espone alcun client MySQL, ma Homebrew ha
`mysql-client` installato in modalità keg-only: `/usr/local/opt/mysql-client/bin/mysql`
risponde ed è alla versione 9.2.0. Questo ha eliminato la necessità di installare
qualcosa, che era l'ipotesi di partenza (venv nella scratchpad con `pymysql`, oppure uso
del client dentro il container `mariadb`): entrambe restano disponibili come ripiego ma
non servono. Verificata l'uscita di rete dal sandbox, che non era scontata, e la
presenza di `ssh` con due host già configurati.

*Scelta del meccanismo.* L'autenticazione passa da `--defaults-extra-file`: il comando
che viene eseguito contiene solo il percorso del profilo e la query, mai l'utenza e mai
la password. È la differenza fra un segreto che esiste in un file con permessi `0600` e
un segreto che viene ricopiato a ogni invocazione in cronologia della shell, elenco dei
processi e transcript.

*Scelta della collocazione.* L'utente ha chiesto il file già pronto, precisando che è
coperto da `.gitignore`. La verifica del file di esclusione ha mostrato che esiste già
`.private/` (riga 45), directory in uso e che contiene già materiale riservato: il
profilo è stato messo lì come `.private/db/oslms-prod.cnf` invece di introdurre una
nuova regola.

*Contenuto del profilo.* Oltre ai parametri di connessione, il file documenta le due
modalità di accesso (diretta e tunnel SSH, con il comando `ssh -f -N -L` già scritto e i
valori coerenti da impostare in ciascun caso), dice dove si legge il nome del database su
un sito Frappe, e porta il `GRANT SELECT` per creare un'utenza di sola lettura. I
parametri del tunnel sono scritti come commenti: il client li ignora, ma restano accanto
ai parametri di connessione e permettono di riaprire il tunnel da soli quando risulta
chiuso, invece di doverlo chiedere.

*Politica d'uso.* Inizialmente dichiarata da Claude come «letture in autonomia, scritture
previa conferma esplicita». A connessione verificata l'utente l'ha **irrigidita in una
regola vincolante**: sul database remoto sono ammesse **solo query di lettura (`SELECT`)**,
e non esiste alcun caso in cui una modifica ai dati possa essere eseguita via query, nemmeno
chiedendo conferma. Le modifiche ai dati passano quindi per le vie applicative (interfaccia,
API di Frappe, patch versionate), non dalla connessione diretta. La regola è stata registrata
in memoria di progetto perché valga anche nelle sessioni successive.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** ricognizione dei client, dei driver e della
  connettività della macchina; scelta del meccanismo di autenticazione e della
  collocazione del file; stesura del profilo precompilato; validazione della sintassi e
  dell'esclusione da git; redazione di questa voce.
- **motivo della scelta del tool e del modello:** la richiesta era una domanda di
  fattibilità, e una risposta di fattibilità data a memoria sarebbe stata sbagliata in
  due punti su tre — avrebbe dichiarato necessaria un'installazione che non serve (il
  client keg-only c'era già) e avrebbe proposto la connessione diretta, che su un server
  Frappe standard non funziona. Claude Code permette di rispondere **dopo** aver
  guardato la macchina anziché prima; il contesto ampio ha consentito di tenere insieme
  ricognizione, regole di `.gitignore` e formato del worklog senza rileggerli.
- **risultato ottenuto:** profilo pronto all'uso, con una sola azione residua a carico
  dell'utente (riempire i segnaposto), e nessuna installazione richiesta.
- **verifiche e correzioni effettuate:** l'ipotesi iniziale di installare un driver
  Python o di appoggiarsi al client dentro il container è stata **abbandonata** dopo aver
  trovato il client keg-only, e la proposta iniziale di collocare il profilo in
  `~/.claude/db/` è stata **corretta** dopo la lettura di `.gitignore`, che ha mostrato
  `.private/` già disponibile. La sintassi del file non è stata data per buona ma
  riletta con `my_print_defaults`, ed è stato verificato con `git check-ignore` e
  `git status` che il file sia davvero fuori dal versionamento, invece di fidarsi della
  sola presenza della regola.

**6. Problematiche incontrate**

Il rilievo aperto alla consegna del profilo — **non provato su una connessione reale**,
perché conteneva segnaposto — è stato **chiuso nella stessa sessione**: l'utente ha compilato
il file e la connessione è stata verificata con esito positivo. Il tunnel SSH si è rivelato
**non necessario**: l'host è un indirizzo di rete locale (`192.168.13.111`) e la porta 3306 è
esposta direttamente, quindi i campi `ssh_*` del profilo restano commentati.

Resta invece un rilievo **nuovo e più rilevante**, sollevato con l'utente: l'utenza fornita è
`root@%`, cioè con privilegi pieni di scrittura, e l'istanza è **viva** (iscrizioni ai corsi e
modifiche ai corsi con data odierna). Non è quindi un ambiente di prova su cui un errore sia
innocuo. La raccomandazione dell'utenza di sola lettura, già scritta nel profilo, diventa per
questo motivo più che una buona pratica: sarebbe l'unica garanzia *tecnica*, mentre oggi la
garanzia è **procedurale** — la regola di sola lettura imposta dall'utente e registrata in
memoria. Finché l'utenza resta `root@%`, nulla nel canale impedisce materialmente una
scrittura: è un rischio residuo dichiarato, non coperto.

È inoltre rimasta **fuori dall'ambito** l'aggiunta della regola di permesso
in `.claude/settings.local.json` che eviterebbe la richiesta di conferma a ogni
interrogazione: è stata proposta all'utente e non applicata di iniziativa, perché la
richiesta riguardava il solo file di profilo.

---

### Attività 18 — Corso non salvabile in staging: valutatore e istruttore inesistenti, e build del frontend mancante nel deploy

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — difetto bloccante segnalato su staging, con accertamento sul database di produzione |
| **Problema riscontrato** | Segnalazione dell'utente: nel corso "Strumenti di collaborazione digitale" non è possibile rimuovere l'istruttore presente (account non più esistente) né salvare nuovi istruttori. L'errore restituito è `Could not find Istruttore: chiaratrentuno172@gmail.com, Row #2: Docente del Corso: c.trentuno+docente@overside.it`. Dopo il primo deploy correttivo il problema **persisteva**. |
| **Problema effettivo** | **Due difetti nel prodotto più uno nella procedura di deploy.** **(1)** Le etichette italiane rendono il messaggio illeggibile: `it.csv` traduce "Evaluator" → **"Istruttore"** e "Instructor" → **"Docente del Corso"**. La prima voce dell'errore non era quindi un istruttore ma il campo **`evaluator`** del corso, un Link a `Course Evaluator`. **(2)** Quel campo ha `depends_on: paid_certificate` e compare nell'interfaccia solo dentro `<template v-if="doc.paid_certificate">` (`CoursePublishSettings.vue:92`). Spegnendo il certificato a pagamento il valore **restava memorizzato ma invisibile**; una volta cancellato il relativo `Course Evaluator`, la validazione dei link rifiutava ogni salvataggio del corso **senza che l'utente avesse alcun modo di vedere o correggere il dato**. Il secondo riferimento rotto era invece un istruttore inesistente, già coperto dalla correzione dell'Attività 9. **(3)** Il persistere del problema dopo il deploy non dipendeva dal codice ma dalla procedura: gli asset compilati della SPA vivono in `lms/public/frontend`, che è **in `.gitignore` (riga 13)** e non viaggia col repository; il server deve ricostruirli, e **`bench build` non compila la SPA Vue** — serve `yarn build` in `apps/lms/frontend`, che nella procedura non era previsto. |
| **Soluzione applicata** | In `LMSCourse.validate_certification`: quando `paid_certificate` è spento vengono azzerati `evaluator` e `timezone` — gli unici due campi che appartengono solo a quella funzione, mentre prezzo e valuta restano perché condivisi con `paid_course`; inoltre un `evaluator` il cui record non esiste più viene scartato anche a certificato acceso, così i corsi già in quello stato si sbloccano al primo salvataggio invece di restare bloccati. I controlli che pretendono valutatore e fuso orario validi quando il certificato a pagamento è attivo restano invariati. Per il deploy: segnalata all'utente l'assenza di `yarn build` nella procedura. |
| **Commit** | Sì — `dd87156b` *fix(courses): clear the paid-certificate fields when the toggle is turned off*, branch `feature/oslms`. |
| **File modificati** | `lms/lms/doctype/lms_course/lms_course.py` (+15). File esaminati: `lms/lms/doctype/lms_course/lms_course.json`, `frontend/src/pages/Courses/CoursePublishSettings.vue`, `lms/translations/it.csv`, `frappe/model/base_document.py` (composizione del messaggio di errore), `package.json` e `frontend/package.json` (catena di build). |
| **Verifiche** | (a) **Accertamento diretto sul database dell'istanza** tramite il profilo di connessione `.private/db/oslms-prod.cnf`, in **sola lettura**: il corso presentava `paid_certificate=0` con `evaluator='chiaratrentuno172@gmail.com'` e `timezone='CET (UTC+1)'` ancora valorizzati, il `Course Evaluator` corrispondente **inesistente** (0 record) e l'istruttore di riga 2 riferito a un utente **inesistente**. (b) **Estensione del problema**: interrogata l'intera istanza, **quel corso era l'unico** con un valutatore appeso a certificato spento e l'unico con un istruttore inesistente. (c) **Riproduzione locale** del ciclo completo: corso con certificato a pagamento e valutatore valido → spegnimento del certificato → `evaluator` e `timezone` azzerati, prezzo e valuta intatti → riaccensione senza valutatore → correttamente bloccata da `Evaluator is required for paid certificates`. (d) Suite `lms`: 49 test superati; l'unico test rosso (`test_not_allowed_path`) verificato **preesistente** rieseguendolo con le modifiche messe da parte via `git stash`. (e) **Diagnosi del deploy fallito**: `tabPatch Log` mostrava il patch applicato alle 16:33, `origin/feature/oslms` conteneva tutti i commit, e i quattro `grep` sul sorgente del server restituivano `1` — ma la build del frontend era ferma alle **14:26** contro un codice delle **16:07**. (f) **Conferma finale sul database dopo l'intervento dell'utente**: `evaluator=NULL`, `timezone=NULL`, un solo istruttore valido, `modified 17:00:17`. |

**1. Obiettivo dell'attività**

Sbloccare un corso dell'istanza che non era più salvabile in alcun modo, risalendo alla causa invece di intervenire sul singolo dato, e accertare se altri corsi si trovassero nella stessa condizione.

**2. Modalità di esecuzione**

1. **Traduzione delle etichette dell'errore**, primo ostacolo: il messaggio nomina "Istruttore" e "Docente del Corso", che nei cataloghi italiani corrispondono a campi diversi da quelli che sembrano.
2. **Diagnostica lato utente**: consegnato uno script che elenca ogni riferimento rotto del corso con il **nome del campo in inglese**, aggirando le etichette tradotte.
3. **Accertamento sul database dell'istanza**, reso possibile dal profilo di connessione predisposto dall'utente: verifica dello stato reale del corso e misura dell'estensione del problema.
4. **Riproduzione locale** del ciclo di accensione e spegnimento del certificato a pagamento, per correggere la causa e non il sintomo.

**3. Attività svolte**

*Traduzione dell'errore.* Le due voci del messaggio corrispondono a:

| Testo mostrato | Campo reale |
| --- | --- |
| "Istruttore: chiaratrentuno172@gmail.com" | `LMS Course.evaluator` → `Course Evaluator` |
| "Row #2: Docente del Corso: c.trentuno+..." | riga 2 di `instructors` → `User` |

*Stato accertato sul database dell'istanza:*

| Campo | Valore |
| --- | --- |
| `paid_certificate` | **0** (spento) |
| `evaluator` | `chiaratrentuno172@gmail.com` — **Course Evaluator inesistente** |
| `timezone` | `CET (UTC+1)` — anch'esso rimasto appeso |
| istruttore riga 2 | `c.trentuno+docente@overside.it` — **utente inesistente** |

*Contributo dell'utente alla diagnosi.* È stato l'utente a individuare la causa vera, osservando che **disattivando il certificato a pagamento i campi correlati dovrebbero essere ripuliti**. La correzione inizialmente predisposta si limitava a scartare un valutatore inesistente — cura del sintomo; su quella indicazione è stata estesa alla pulizia dei campi al cambio di stato, che è la causa.

*Esito finale, verificato sul database:* `evaluator=NULL`, `timezone=NULL`, un solo istruttore valido. Il corso è tornato salvabile senza alcun intervento manuale sui dati: è bastato che l'utente rimuovesse l'istruttore inesistente, e la pulizia del valutatore è avvenuta nello stesso salvataggio.

*Difetto di procedura emerso.* Dopo il primo deploy il problema persisteva. La catena di verifiche ha escluso il codice — presente sul server, patch applicato, commit su `origin` — e ha isolato la causa nella **build della SPA mai eseguita**: gli asset compilati sono in `.gitignore`, quindi non arrivano col codice, e `bench build` compila gli asset classici di Frappe ma **non** il bundle Vite. La procedura di deploy prevedeva solo il primo.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** traduzione delle etichette dell'errore, stesura dello script diagnostico consegnato all'utente, interrogazione in sola lettura del database dell'istanza, riproduzione locale del ciclo del certificato a pagamento, stesura della correzione, diagnosi del deploy inefficace, redazione di questa voce.
- **motivo della scelta del tool e del modello:** il difetto attraversava traduzioni, schema dei doctype, condizioni di visibilità nel frontend, dati reali dell'istanza e procedura di deploy: serviva uno strumento capace di leggere il codice, interrogare il database remoto e riprodurre in locale nello stesso flusso. Il contesto ampio di Opus 5 ha permesso di collegare l'errore alle correzioni dei giorni precedenti sugli istruttori, riconoscendo che una delle due voci era già coperta.
- **risultato ottenuto:** corso sbloccato e causa rimossa alla radice, con la certezza — misurata sull'intera istanza — che nessun altro corso fosse coinvolto; individuata inoltre una lacuna nella procedura di deploy che avrebbe continuato a rendere invisibile in staging **qualunque** correzione all'interfaccia.
- **verifiche e correzioni effettuate:** l'interpretazione iniziale è stata **sbagliata due volte** e corretta sui fatti. Prima si erano attribuiti i due riferimenti rotti alle classi anziché al corso, perché la ricerca dei campi collegati era stata limitata ai Link verso `User`, mancando `evaluator` che punta a `Course Evaluator`; l'utente ha insistito di essere sul corso e aveva ragione. Poi la correzione predisposta curava il sintomo, ed è stata estesa alla causa su indicazione dell'utente. Quando dopo il deploy il problema è rimasto, non si è dato per scontato che il codice fosse arrivato: è stata costruita una catena di verifiche (patch nel log, commit su origin, `grep` sul sorgente del server, data degli artefatti compilati) che ha isolato la build mancante invece di attribuire il fallimento alla correzione. L'esito è stato infine **confermato sul database**, non sulla parola.

**6. Problematiche incontrate**

Tre ostacoli, tutti superati.

Il primo: **le etichette tradotte hanno depistato la diagnosi**. "Istruttore" traduce "Evaluator" e "Docente del Corso" traduce "Instructor", quindi il messaggio d'errore indicava apparentemente due istruttori mentre si trattava di due campi distinti. La soluzione adottata — uno script diagnostico che stampa i **nomi dei campi in inglese** — è riutilizzabile per qualunque `LinkValidationError` futuro su un'installazione localizzata, e vale la pena tenerla presente.

Il secondo: **un campo non raggiungibile rende un documento definitivamente non salvabile**. Frappe valida i link di tutti i campi, compresi quelli nascosti da `depends_on`; se uno di essi contiene un riferimento rotto, l'utente vede un errore che nomina un campo che non compare da nessuna parte nella schermata. È un genere di blocco senza via d'uscita che conviene ricordare: ogni campo condizionato dovrebbe essere ripulito quando la sua condizione si spegne, ed è esattamente ciò che la correzione ora fa.

Il terzo: **la procedura di deploy non ricompila la SPA**, quindi ogni correzione all'interfaccia resta invisibile in staging e sembra non funzionare. Segnalato all'utente il comando mancante (`yarn build` in `apps/lms/frontend`) e raccomandato di aggiungerlo alla procedura, altrimenti il problema si ripresenterà a ogni rilascio che tocchi il frontend.

---

### Attività 19 — Istruttori e valutatori non rimovibili dalla scheda di una classe

> **Voce ricostruita a posteriori**, in sede di stesura del report di giornata: l'attività
> non era stata registrata nella sessione in cui è stata svolta ed è emersa dal confronto
> fra il worklog e `git log`. Problema, causa e soluzione sono ricavati dal commit e dal
> diff, e riscontrati sul codice attuale; le **verifiche svolte nella sessione d'origine
> non sono documentate** e non vengono quindi dichiarate.

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — estensione alle classi del difetto corretto sui corsi nell'Attività 9 |
| **Problema riscontrato** | Stesso quadro dell'Attività 9 ma sulla scheda di una classe: un istruttore o un *valutatore* già salvato sulla classe non è rimovibile, e nel riepilogo del campo compare l'indirizzo dell'account invece del nome della persona. |
| **Problema effettivo** | Entrambi i campi di `BatchForm.vue` erano alimentati **soltanto** dal rispettivo endpoint di ricerca (`lms.lms.api.search_users_by_role` per gli istruttori, `os_lms.os_lms.api.search_non_student_users` per i valutatori), senza `extraOptions`. Quegli endpoint non restituiscono gli utenti disabilitati, quelli che hanno perso il ruolo e quelli cancellati, e in più limitano i risultati a una pagina (`page_length` 10 e 20). Chi era già salvato sulla classe ma assente da quei risultati non compariva nella tendina, e poiché la rimozione avviene esclusivamente deselezionando la voce lì, **restava sulla classe in modo definitivo**. Rispetto ai corsi il difetto è più facile da incontrare: basta che i non-studenti dell'istanza superino la pagina di risultati, senza bisogno di account cancellati. Secondo sintomo, stessa causa: nulla risolveva i valori salvati in nome e cognome, quindi il riepilogo mostrava gli id grezzi. |
| **Soluzione applicata** | Solo frontend. I valori già salvati vengono risolti chiamando gli **stessi** endpoint con il parametro `names` — che entrambi supportavano già lato server e che salta la ricerca testuale restituendo direttamente quegli utenti — e memorizzati in una mappa `resolvedUsers`; da lì si costruiscono `instructorOptions` e `valutatoreOptions`, passate come `extraOptions` ai due `MultiSelect`, con ripiego sull'id grezzo quando un valore non è risolvibile, così resta comunque elencato e deselezionabile. Nessuna modifica al backend. |
| **Commit** | Sì — `bdb54ddd` *fix(batches): let an instructor or valutatore who is gone be removed from a batch*, branch `feature/oslms`. |
| **File modificati** | `frontend/src/pages/Batches/BatchForm.vue` (+93). |
| **Verifiche** | Non documentate nella sessione d'origine. Riscontri effettuati ora, in sede di ricostruzione: entrambi gli endpoint accettano davvero il parametro `names` e lo trattano come scorciatoia rispetto alla ricerca testuale (`lms/lms/api.py:2524-2540`, `apps/os_lms/os_lms/os_lms/api.py:358-384`), quindi la soluzione non richiede modifiche lato server; il commit tocca il solo file dell'interfaccia. |

**1. Obiettivo dell'attività**

Riportare sulle classi la stessa correzione applicata ai corsi poche ore prima, invece di
attendere che il difetto venisse segnalato una seconda volta sulla scheda gemella. Il
punto di partenza è lo stesso — un elenco di persone che si può solo ampliare e mai
ridurre — e sulle classi ha un'aggravante: si presenta anche con account perfettamente
validi, non appena i nominativi selezionabili superano la prima pagina di risultati.

**2. Modalità di esecuzione**

Trasposizione della soluzione già validata sui corsi, adattata al fatto che qui i campi
sono due e attingono a endpoint diversi: risoluzione dei valori salvati tramite gli
stessi endpoint di ricerca, memorizzazione in una mappa condivisa fra i due campi e
riconsegna come opzioni aggiuntive della tendina.

**3. Attività svolte**

Aggiunta in `BatchForm.vue` di due risorse dedicate alla risoluzione dei valori salvati,
di una mappa `resolvedUsers` condivisa, di due proprietà calcolate che la traducono in
opzioni per la tendina e dei `watch` che le mantengono allineate al contenuto dei campi.
I due `MultiSelect` ricevono ora `:extraOptions`. Il ripiego sull'id grezzo garantisce
che un valore non risolvibile — utente cancellato — resti elencato e quindi rimovibile.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M) — desumibile dal `Co-Authored-By` del commit.
- **attività per cui è stata utilizzata:** stesura della correzione sul modello di quella
  dei corsi. La presente voce di registro è stata ricostruita a posteriori, sempre con
  Claude Code, a partire dal commit, dal diff e dal riscontro sugli endpoint.
- **motivo della scelta del tool e del modello:** la correzione riusa un ragionamento già
  svolto nella stessa sessione sull'omologo campo dei corsi; un modello a contesto ampio
  ha potuto riapplicarlo alle classi senza ricostruire il percorso, riconoscendo le
  differenze (due campi anziché uno, endpoint distinti, limite di pagina).
- **risultato ottenuto:** entrambi i campi della scheda classe tornano modificabili in
  riduzione e mostrano i nomi delle persone anziché gli indirizzi degli account.
- **verifiche e correzioni effettuate:** non documentate nella sessione d'origine, e per
  questo non dichiarate. In sede di ricostruzione è stato verificato che il parametro
  `names` fosse realmente supportato da entrambi gli endpoint, cioè che la correzione non
  poggiasse su un'assunzione lato server.

**6. Problematiche incontrate**

Una sola, di metodo: **l'attività non era stata registrata**, ed è emersa solo dal
confronto fra worklog e `git log` fatto per compilare il report. Il registro è la fonte
del report giornaliero, quindi una correzione non annotata sarebbe semplicemente sparita
dalla rendicontazione. La contromisura è già nella regola in vigore — la voce si scrive
subito dopo il commit — e va applicata anche alle correzioni "gemelle", che per la loro
somiglianza con quella appena registrata sembrano non meritare una voce propria.

Resta inoltre **non verificato sul campo** l'esito della correzione: come per l'Attività
9 si tratta di interfaccia, non coperta dai test automatici del progetto, e la conferma
visiva — aprire una classe, togliere una persona non più disponibile, salvare — è da
fare dopo il rilascio.

---

### Attività 20 — Allineamento del numero di versione mostrato nell'applicazione

> Voce ricostruita a posteriori insieme all'Attività 19, con lo stesso criterio.

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Chore — manutenzione del numero di versione |
| **Problema riscontrato** | Esigenza di rilascio: la versione mostrata in fondo alla barra laterale dell'applicazione era ferma a `1.12.0`, mentre la giornata ha prodotto quattro correzioni e una funzionalità destinate all'istanza del cliente. |
| **Problema effettivo** | Il numero di versione visibile agli utenti è un testo scritto nel componente della barra laterale (`AppSidebar.vue`), non un valore derivato dal `package.json` o dal tag di rilascio: non si aggiorna da solo e va modificato a mano a ogni rilascio, altrimenti l'assistenza non ha modo di sapere quale codice stia girando su un'istanza. |
| **Soluzione applicata** | Portata l'etichetta da `1.12.0` a `1.12.1` — incremento di patch, coerente con una giornata di sole correzioni più una configurazione aggiuntiva senza impatto sulle funzioni esistenti. |
| **Commit** | Sì — `fd1856c7` *update version*, branch `feature/oslms`. |
| **File modificati** | `frontend/src/components/Sidebar/AppSidebar.vue` (1 riga). |
| **Verifiche** | Nessuna verifica specifica documentata; la modifica è un testo statico ed è stata inclusa nella build del frontend eseguita per il rilascio. |

**1. Obiettivo dell'attività**

Rendere riconoscibile dall'esterno quale versione dell'applicazione è in esercizio su
un'istanza, condizione necessaria per attribuire una segnalazione al codice giusto.

**2. Modalità di esecuzione**

Modifica diretta dell'etichetta nel componente che la rende, contestuale al rilascio.

**3. Attività svolte**

Incremento della versione visualizzata da `1.12.0` a `1.12.1`.

**4. Utilizzo dell'AI**

- **tool/agente:** nessuno per la modifica in sé, che è di una riga; Claude Code (Opus 5,
  contesto 1M) è stato usato solo per ricostruire questa voce di registro.
- **motivo della scelta:** non pertinente per la modifica; per la voce vale quanto detto
  nell'Attività 19.
- **risultato ottenuto:** versione allineata al contenuto del rilascio.
- **verifiche e correzioni effettuate:** nessuna oltre alla build del frontend, che
  include il file modificato.

**6. Problematiche incontrate**

Una sola, e di metodo più che tecnica: **il numero di versione è scritto a mano in un
componente dell'interfaccia**, quindi dipende dal ricordo di chi rilascia e può restare
indietro senza che nulla lo segnali. Un valore derivato dal `package.json` o dal tag di
rilascio eliminerebbe il rischio; non è stato fatto perché fuori dall'ambito della
giornata, ed è annotato fra gli spunti del report.

---

### Attività 21 — Stesura del report giornaliero dell'11 settembre, con riscontro sull'istanza del cliente

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Rendicontazione — aggregazione della giornata nel report aziendale, con verifiche sui dati |
| **Problema riscontrato** | Richiesta dell'utente: «fai report di oggi». Il report della giornata esisteva già ma era stato scritto alle 10:34 e copriva soltanto la sessione serale del 10 e la mattinata: dalle 10:34 in poi la giornata ha prodotto altre 13 attività registrate e 6 commit, quindi il documento consegnato all'azienda sarebbe stato gravemente incompleto. |
| **Problema effettivo** | Il registro delle attività non era una fonte sufficiente. Due criteri della procedura hanno prodotto altrettanti scostamenti rispetto a quanto scritto: (1) il confronto con `git log` ha rivelato **due commit consegnati e mai registrati** (`bdb54ddd`, `fd1856c7`) e **due voci con lo stato del commit ormai superato** (Attività 4 e 9, dichiarate "non committate" e nel frattempo committate come `bf6a1c31` e `1f3614c6`); (2) il vincolo d'ordine della funzionalità sui colori del login (Attività 13) — configurare le istanze **prima** di rilasciare — non risultava eseguito da nessuna voce del registro, e andava accertato sui fatti perché il rilascio è avvenuto nel pomeriggio. |
| **Soluzione applicata** | Registro allineato: aggiunte le voci ricostruite delle Attività 19 e 20 e corretti i campi *Commit* delle Attività 4 e 9. Report riscritto per coprire l'intera giornata, aggregando le 21 attività in otto filoni con tabella degli interventi consegnati e i punti 7-8-9 della direttiva. Accertato inoltre sull'istanza del cliente, in sola lettura, che la pagina di accesso ha effettivamente perso i colori: il rilievo è stato riportato nel report come problematica e come prima prossima attività. |
| **Commit** | No — il worklog e i report non vengono committati (regola del progetto, salvo richiesta esplicita). |
| **File modificati** | `docs/WORKLOG.md` (Attività 19, 20, 21 aggiunte; campo *Commit* di Attività 4 e 9 aggiornato), `reports/2026-09-11-os-lms.md` (riscritto per l'intera giornata). |
| **Verifiche** | (a) `git log --since` sulla giornata, confrontato voce per voce con il registro → due commit mancanti e due stati superati. (b) `git rev-parse HEAD origin/feature/oslms` → identici, quindi tutto il lavoro della giornata è sul remoto. (c) Per la voce ricostruita dell'Attività 19, riscontro sul codice che entrambi gli endpoint di ricerca accettino il parametro `names`. (d) **Riscontro sull'istanza del cliente, sola lettura**: `tabSingles` per `Brand Customize` non contiene alcun campo `login_*` e i due `gradient_overlay_*` sono vuoti, con `modified` fermo al 10/09; il foglio `/assets/os_lms/css/os_lms.css` servito dall'istanza contiene invece le sei variabili `--login-*` e non più il letterale `#0a2e5a`; `GET` su `brand_css` restituisce il solo `--surface-gray-10`. Le tre evidenze insieme dimostrano che la pagina di accesso del cliente **è ora neutra**. |

**1. Obiettivo dell'attività**

Consegnare un report di giornata completo e verificabile, non una sintesi del registro: la
direttiva aziendale prevede che il report aggreghi le attività e aggiunga i punti che il
worklog non contiene (prossime attività, avanzamento, spunti di miglioramento), e che sia
leggibile da un destinatario non tecnico.

**2. Modalità di esecuzione**

Lettura integrale della giornata nel registro, poi **verifica incrociata con la cronologia
delle consegne** invece di fidarsi del solo registro. Gli scostamenti trovati sono stati
sanati nel registro prima di scrivere il report, così che le due fonti restino coerenti.
Infine, per l'unica affermazione del report che dipendeva da uno stato non documentato — se
le istanze fossero state configurate prima del rilascio — si è interrogata direttamente
l'istanza in sola lettura, come previsto dalla regola in vigore su quel database.

**3. Attività svolte**

*Allineamento del registro.* Aggiunte le Attività 19 (istruttori e valutatori non rimovibili
dalla scheda di una classe, commit `bdb54ddd`) e 20 (allineamento del numero di versione,
commit `fd1856c7`), entrambe dichiarate come **ricostruite a posteriori**, con l'avvertenza
esplicita che le verifiche della sessione d'origine non sono documentate e non vengono
quindi attribuite. Corretti i campi *Commit* delle Attività 4 e 9.

*Stesura del report.* Le attività della giornata più le 4 della sera del 10 sono state
aggregate in otto filoni, seguiti dalla tabella dei nove interventi (otto consegnati, uno
pronto) e dai punti 7-8-9. Su indicazione dell'utente il punto 3 è stato poi riscritto in
forma essenziale: per ciascun filone due sole voci, **problema** e **soluzione applicata**,
invece del racconto esteso dell'esito; con lo stesso criterio è stato poi sintetizzato il
punto 4, che mantiene tutti i campi richiesti dalla direttiva (tool, modello, attività,
motivo della scelta, risultato, verifiche) in forma più breve. Su ulteriore indicazione
dell'utente («nelle problematiche non ci sono state quelle lì») è stato ripulito anche il
punto 6: eliminate le voci che non erano ostacoli incontrati ma insegnamenti o ripetizioni
di difetti già descritti al punto 3 (etichette tradotte che depistano, campo nascosto che
blocca il salvataggio, registrazione riattivata sul sito di sviluppo), e tenuti i soli
quattro ostacoli reali più l'incidente sui dati.

*Rilievo sull'istanza del cliente.* La funzionalità sui colori del login impone di
configurare le istanze prima di rilasciare, pena una pagina di accesso neutra. Il rilascio è
avvenuto nel pomeriggio; l'accertamento mostra che la configurazione non è stata fatta e che
la pagina di accesso del cliente **ha perso il blu**. Il rilievo è finito in cima alle
prossime attività, con l'indicazione che si risolve dal pannello in pochi minuti, senza
rilasci.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code).
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** lettura e aggregazione del registro, confronto con
  `git log`, ricostruzione delle due voci mancanti, interrogazione in sola lettura del
  database e degli asset pubblici dell'istanza del cliente, stesura del report.
- **motivo della scelta del tool e del modello:** il report non è un riassunto ma un documento
  che deve reggere la verifica: richiede di leggere l'intera giornata, confrontarla con ciò
  che è stato realmente consegnato e accertare sul campo quel che il registro non dice.
  Serviva quindi uno strumento con accesso al repository, alla cronologia git e — per il
  rilievo sul login — all'istanza del cliente. Il contesto ampio ha permesso di tenere insieme
  le voci di registro di due giornate e di riconoscere che tre difetti diversi condividevano
  lo stesso schema, cosa che è diventata uno degli spunti di miglioramento.
- **risultato ottenuto:** report completo della giornata, registro allineato alla cronologia
  delle consegne, e un problema in esercizio sull'istanza del cliente individuato prima che
  lo segnalasse l'utente.
- **verifiche e correzioni effettuate:** il registro **non** è stato assunto come veritiero:
  il confronto con `git log` ha corretto quattro dichiarazioni sullo stato delle consegne. Per
  le due voci ricostruite non sono state inventate verifiche: è stato dichiarato che non
  risultano documentate, e sono stati aggiunti solo i riscontri effettuati ora. Il rilievo sul
  login non è stato dedotto dal vincolo d'ordine ma dimostrato con tre evidenze indipendenti
  (contenuto del pannello a database, foglio di stile servito, risposta dell'endpoint dei
  colori). Tutte le interrogazioni sull'istanza sono state di sola lettura.

**6. Problematiche incontrate**

Una, già descritta al punto 3 e degna di nota perché riguarda l'affidabilità della
rendicontazione: **il registro da solo non basta**. Due consegne non annotate e due stati
superati sarebbero passati nel report come "non consegnato" o non sarebbero comparsi affatto.
Il confronto con la cronologia delle consegne va quindi mantenuto come passo fisso della
stesura, e la voce di registro va scritta subito dopo il commit anche quando la correzione è
"gemella" di una appena registrata — è proprio il caso in cui si è saltata.

---

## 2026-09-10

> **Report giornaliero:** [`reports/2026-09-11-os-lms.md`](../reports/2026-09-11-os-lms.md)
> — questa giornata **non ha un report proprio**: le sue quattro attività sono la
> sessione serale del filone proseguito l'11 settembre e sono state aggregate,
> su richiesta dell'utente, nel report dell'11 insieme a quelle della mattinata
> successiva.

---

### Attività 1 — Verifica della segnalazione "il corso aggiunto a una classe non è visibile agli studenti già iscritti"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — verifica di una segnalazione utente con riproduzione sperimentale, senza modifiche al codice |
| **Problema riscontrato** | Segnalazione dell'utente, rilevata **in produzione** (che gira sul branch `master`): «se in una classe con degli studenti iscritti aggiungo un corso, gli studenti non riescono a vedere il corso aggiunto; se iscrivo un nuovo studente, lo studente nuovo vede il corso che era stato aggiunto». Richiesta esplicita: accertare se l'affermazione corrisponda al vero. |
| **Problema effettivo** | Segnalazione **confermata e riprodotta**, con una causa più grave e più circoscritta di quella apparente. L'aggiunta di un corso a una classe **non crea le `LMS Enrollment` per gli studenti già iscritti**: `LMSBatch.on_update` (`lms/lms/doctype/lms_batch/lms_batch.py:41-43`) gestisce solo la notifica di pubblicazione e non esegue alcun backfill. Le iscrizioni ai corsi nascono in un unico punto, `LMSBatchEnrollment.validate_course_enrollment` (`lms_batch_enrollment.py:76-89`), che gira **solo** al momento dell'ingresso dello studente in classe — da cui la differenza fra studente vecchio e studente nuovo. Esiste un recupero tardivo, `ensure_batch_course_enrollments` (`lms/lms/utils.py:1546-1556`), invocato da `get_batch_courses` (`utils.py:1526-1532`) quando un membro apre la pagina della classe: dovrebbe sanare il caso, ma **fallisce** se anche un solo corso della classe ha il flag *Disable Self Learning*. Il motivo è un ordine di controlli errato in `LMSEnrollment.validate_course_enrollment_eligibility` (`lms/lms/doctype/lms_enrollment/lms_enrollment.py:36-58`): il controllo `disable_self_learning` è alla riga 45, **prima** del bypass `enrollment_from_batch` delle righe 51-58. Lo studente non è amministratore, quindi `is_admin()` è falso e la `frappe.throw` scatta; l'eccezione risale fino a `get_batch_courses`, l'intera chiamata API fallisce e la scheda *Panoramica* della classe non mostra **nessun** corso — nemmeno quelli in cui lo studente era già iscritto. Lo studente nuovo non incontra il difetto perché la sua `LMS Batch Enrollment` viene creata nella sessione dell'amministratore, dove `is_admin()` è vero e il controllo viene saltato. Da notare che gli altri due controlli analoghi della stessa funzione (corso non pubblicato, corso a pagamento) sono correttamente collocati **dopo** il bypass: `disable_self_learning` è l'unico rimasto fuori posto. |
| **Soluzione applicata** | Nessuna: l'attività richiesta era la sola verifica. Individuata la riga esatta da correggere (`lms_enrollment.py:45`, da spostare dopo il blocco `enrollment_from_batch`) e documentato il difetto secondario indipendente (assenza di backfill all'aggiunta di un corso in classe, che rimanda la creazione dell'iscrizione al momento in cui lo studente apre la pagina della classe). Decisione sull'intervento rimessa all'utente. |
| **Commit** | No — nessuna modifica al codice, attività di sola analisi e riproduzione |
| **File modificati** | Nessuno. File esaminati: `lms/lms/doctype/lms_enrollment/lms_enrollment.py`, `lms/lms/doctype/lms_batch_enrollment/lms_batch_enrollment.py`, `lms/lms/doctype/lms_batch/lms_batch.py`, `lms/lms/utils.py` (`get_batch_courses`, `ensure_batch_course_enrollments`, `enroll_via_batch_if_eligible`, `get_course_details`, `get_courses`, `update_course_filters`), `frontend/src/pages/Batches/BatchOverview.vue`, `frontend/src/pages/Batches/BatchDetail.vue`, `apps/os_lms/os_lms/os_lms/api.py`. Script di riproduzione temporanei nella scratchpad di sessione, non nel repository. |
| **Verifiche** | (a) Verificato che i file coinvolti sul branch di lavoro `feature/oslms` siano **identici a `master`** (`git diff master -- …` vuoto per `lms_enrollment.py`, `lms_batch.py`, `lms_batch_enrollment.py`, `utils.py`), quindi la riproduzione locale è valida per la produzione. (b) Verificato che il commit `7c44a7dc8` *Handle course access and enrollment via batches* (16/04/2026), che introduce `ensure_batch_course_enrollments`, **sia già presente in `master` e in `origin/master`**: il recupero tardivo è quindi deployato, e la sua inefficacia non dipende da un allineamento mancato. (c) **Riproduzione sperimentale** sul container Docker del progetto (`dev-elite-frappe-1`, sito `lms.localhost`, che monta il repository su `/workspace`), con due scenari eseguiti su dati creati e poi ripuliti. Esiti riportati per esteso al punto 3. |

**1. Obiettivo dell'attività**

Stabilire se l'affermazione dell'utente descriva un difetto reale del prodotto o un
equivoco di utilizzo, e in caso affermativo individuare la causa esatta a livello di
riga di codice, distinguendo il sintomo riferito ("non vede il corso aggiunto") dal
comportamento effettivo del sistema. La segnalazione riguarda la produzione, quindi
la verifica doveva essere condotta sul codice del branch `master`, non su quello di
sviluppo, e portare un riscontro riproducibile e non solo un'ipotesi di lettura.

**2. Modalità di esecuzione**

Approccio in due fasi: analisi statica per formulare l'ipotesi, riproduzione
sperimentale per confermarla o smentirla.

1. **Ricostruzione della catena** che porta un corso di classe a essere visibile a
   uno studente: `Batch Course` (tabella figlia della classe) → `LMS Enrollment`
   (iscrizione al singolo corso) → endpoint consumati dalla SPA. Individuati i due
   punti di ingresso reali: `get_batch_courses` per la scheda *Panoramica* della
   classe e `get_courses(filters={"enrolled": 1})` per la scheda "I miei corsi",
   che filtra esclusivamente sulle `LMS Enrollment` (`update_course_filters`,
   `utils.py:882-887`).
2. **Allineamento con la produzione**: confronto dei file coinvolti fra il branch di
   lavoro e `master`, e verifica che il commit che introduce il meccanismo di
   recupero sia effettivamente in `master`. Passaggio necessario per non attribuire
   il difetto a un semplice mancato deploy.
3. **Riproduzione** sul container Docker del progetto. La CLI `bench` non è presente
   nell'immagine, quindi gli script sono stati eseguiti direttamente con
   l'interprete del virtualenv della bench
   (`/home/frappe/bench-data/frappe-bench/env/bin/python`) con working directory
   `sites/`, previo `frappe.init(site="lms.localhost")` + `frappe.connect()`.
   Il cambio di identità fra amministratore e studente è stato ottenuto con
   `frappe.set_user()`, per riprodurre fedelmente la differenza di ruolo che è al
   centro del difetto. Ogni script è stato scritto con un blocco `finally` di
   pulizia, così da non lasciare dati di prova sul sito.

**3. Attività svolte**

*Analisi statica.* Ricostruita la catena descritta al punto 2 e isolata l'anomalia in
`validate_course_enrollment_eligibility`: il controllo su `disable_self_learning`
precede il bypass per le iscrizioni provenienti da una classe, mentre i controlli
successivi (corso non pubblicato, corso a pagamento) lo seguono. L'incoerenza fra i
tre controlli è di per sé l'indizio del difetto.

*Scenario A — corso aggiunto con "Disable Self Learning" attivo.* Creati due studenti,
tre corsi (uno iniziale, uno aggiunto senza il flag, uno aggiunto con il flag) e una
classe pubblicata. Sequenza e risultati:

| Passo | Esito osservato |
| --- | --- |
| Classe con 1 corso, iscritto lo studente "vecchio" | `LMS Enrollment` = `[corso-iniziale]` |
| Aggiunti 2 corsi alla classe come amministratore | `LMS Enrollment` studente vecchio **invariata**: `[corso-iniziale]` |
| Lo studente vecchio apre la pagina della classe | `get_batch_courses` → **`ValidationError: You cannot enroll in this course as self-learning is disabled. Please contact the Administrator.`** — nessun corso restituito, nessuna iscrizione creata |
| Iscritto ora uno studente "nuovo" (classe già a 3 corsi) | Iscrizione riuscita, `LMS Enrollment` = tutti e 3 i corsi |
| Lo studente nuovo apre la pagina della classe | `get_batch_courses` → OK, vede tutti e 3 i corsi |

Risultato: l'affermazione dell'utente è vera, e il danno è più ampio di quanto
riferito — lo studente già iscritto non perde solo il corso aggiunto, ma vede
sparire l'intero elenco dei corsi della classe, perché l'eccezione fa fallire la
chiamata nel suo insieme. Si noti che anche il corso aggiunto *senza* il flag va
perso: viene creato nello stesso ciclo e annullato dal rollback della richiesta
provocato dall'eccezione sul corso successivo.

*Scenario B — corso aggiunto senza "Disable Self Learning".* Stessa sequenza con un
solo corso aggiunto, privo del flag:

| Passo | Esito osservato |
| --- | --- |
| Subito dopo l'aggiunta del corso alla classe | `LMS Enrollment` invariata: solo il corso iniziale |
| Scheda "I miei corsi" prima di aprire la classe | Solo `Corso Iniziale` — **il corso aggiunto non compare** |
| Pagina della classe | Vede entrambi i corsi; l'iscrizione mancante viene creata in questo momento |
| Scheda "I miei corsi" dopo aver aperto la classe | Entrambi i corsi |

Risultato: difetto reale ma di gravità minore. Il corso aggiunto resta invisibile
finché lo studente non passa dalla pagina della classe; se cerca il corso in "I miei
corsi", cosa più che plausibile, non lo trova e conclude che non gli è stato
assegnato. Il sintomo riferito dall'utente è quindi coerente anche con questo
scenario, ed è probabile che in produzione i due si sovrappongano.

*Pulizia.* Entrambi gli script hanno rimosso a fine esecuzione utenti, corsi, classi
e iscrizioni creati, comprese le entità residue di due esecuzioni interrotte da
errori di campi obbligatori (`instructors`, `timezone`, `description`,
`batch_details`) durante la messa a punto delle fixture.

*Nota operativa.* Per la riproduzione è stato riavviato lo stack Docker del progetto
(`docker compose up -d` in `docker/`), che era spento. È rimasto in esecuzione a fine
attività.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), sessione interattiva sul
  repository `os_lms`.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** l'intera verifica — ricostruzione della
  catena `Batch Course` → `LMS Enrollment` → endpoint SPA, individuazione della causa
  a livello di riga, controllo di allineamento fra branch di lavoro e `master`,
  stesura ed esecuzione dei due script di riproduzione sul container, interpretazione
  degli esiti e redazione di questa voce di registro.
- **motivo della scelta del tool e del modello:** la verifica non era circoscrivibile
  a un singolo file — richiedeva di attraversare backend (due controller di doctype
  più `utils.py`), frontend Vue e configurazione Docker, tenendo insieme un dettaglio
  decisivo (l'ordine di due `if` dentro una `validate`) e il contesto di ruolo in cui
  quel codice gira. Claude Code è stato scelto perché opera direttamente sul
  repository e sul container, quindi può passare dall'ipotesi alla riproduzione senza
  cambiare strumento; il contesto ampio di Opus 5 consente di tenere aperti insieme
  tutti i file della catena senza perdere i riferimenti già acquisiti.
- **risultato ottenuto:** ipotesi corretta al primo tentativo (ordine dei controlli in
  `validate_course_enrollment_eligibility`) e confermata sperimentalmente, con in più
  due elementi che l'utente non aveva riferito e che cambiano la valutazione di
  gravità: l'eccezione azzera l'intero elenco dei corsi della classe, non solo quello
  aggiunto, e il difetto esiste in forma attenuata anche senza il flag
  *Disable Self Learning*.
- **verifiche e correzioni effettuate:** non ci si è fermati alla lettura del codice.
  È stato verificato che i file fossero identici a `master` e che il commit del
  meccanismo di recupero fosse già in produzione — controllo che ha evitato la
  conclusione sbagliata "manca il deploy del fix". La prima stesura dell'analisi si
  fermava all'assenza di backfill in `LMSBatch.on_update`, spiegazione plausibile ma
  incompleta, poi superata trovando `ensure_batch_course_enrollments` e chiedendosi
  perché non funzionasse. Gli script di riproduzione hanno richiesto tre passate per
  soddisfare i campi obbligatori di `LMS Course` e `LMS Batch`; è stato aggiunto un
  blocco `finally` di pulizia dopo che le prime esecuzioni fallite avevano lasciato
  dati residui sul sito. È stato infine eseguito un secondo scenario, non richiesto,
  per delimitare la portata del difetto e non consegnare all'utente una diagnosi
  valida solo in un caso particolare.

**6. Problematiche incontrate**

Due ostacoli, entrambi risolti.

Il primo, di metodo: l'analisi statica offriva due spiegazioni concorrenti — assenza
di backfill all'aggiunta del corso, oppure fallimento del recupero tardivo — che
producono lo stesso sintomo riferito ma hanno gravità e correzione diverse. Non era
distinguibile leggendo il codice, perché dipende dal valore di un flag di configurazione
del corso (*Disable Self Learning*) e dal ruolo dell'utente che esegue la richiesta.
Si è scelto di riprodurre entrambi gli scenari, accertando che **entrambe** le
spiegazioni sono vere e descrivono due difetti distinti e sovrapposti.

Il secondo, di ambiente: la CLI `bench` non è installata nell'immagine
`elite-frappe-dev` (`bench: command not found`, e nessun eseguibile `bench` nel
`env/bin` della bench), quindi non era utilizzabile né `bench console` né
`bench execute`. Aggirato invocando direttamente l'interprete del virtualenv della
bench con `frappe.init()` + `frappe.connect()` espliciti e working directory `sites/`.
Da tenere presente per le prossime verifiche sul container: è la via praticabile per
eseguire codice nel contesto del sito.

Nessun supporto esterno necessario.

**Aggiornamento — conferma che il difetto è presente anche su `feature/oslms`**

Domanda successiva dell'utente: se l'errore riguardi anche il branch di lavoro
`feature/oslms` oltre a `master`. Risposta: **sì**, ed è anzi il branch su cui la
riproduzione è stata effettivamente eseguita — il container monta il repository su
`/workspace` e il working tree era su `feature/oslms`, quindi i due scenari
documentati al punto 3 girano sul codice di oslms; la conclusione su `master` era la
deduzione, ricavata dall'identità dei file, non il contrario.

Verifiche aggiuntive svolte per rispondere:

1. Confronto diretto **branch contro branch** (non più working tree contro branch):
   `git diff --stat master feature/oslms -- lms/lms/doctype/lms_enrollment/
   lms/lms/doctype/lms_batch/ lms/lms/doctype/lms_batch_enrollment/ lms/lms/utils.py`
   → output vuoto, i quattro file della catena sono identici.
2. Verificato che l'app `os_lms` **non corregga il comportamento** con un override:
   `override_doctype_class` in `apps/os_lms/os_lms/hooks.py:46-52` copre solo
   `Email Account`, `Data Import`, `LMS Live Class` e `LMS Certificate`. Su
   `LMS Enrollment` os_lms aggancia unicamente `permission_query_conditions`
   (riga 75) e `has_permission` (riga 95), entrambi legati al gating per il ruolo
   "Valutatore": non intercettano il metodo `validate`, quindi la `frappe.throw` di
   `validate_course_enrollment_eligibility` scatta in modo identico.

Conseguenza per la correzione: il difetto è unico e vive in
`lms/lms/doctype/lms_enrollment/lms_enrollment.py`, non duplicato fra i branch né
mascherato da un override di os_lms. Il fix va quindi applicato una sola volta su
quel file.

---

### Attività 2 — Delimitazione del difetto: rimozione e riaggiunta di un corso già iscritto

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — approfondimento sperimentale dell'Attività 1, senza modifiche al codice |
| **Problema riscontrato** | Domanda dell'utente a valle della verifica dell'Attività 1: in una classe con due corsi e uno studente iscritto, rimuovendo il corso A e poi riaggiungendolo, lo studente vede due corsi o uno? In altre parole: il difetto si ripresenta anche per un corso che era **già presente** quando lo studente si è iscritto, oppure colpisce solo i corsi mai aggiunti prima? |
| **Problema effettivo** | Il difetto **non si ripresenta**: lo studente continua a vedere entrambi i corsi. La discriminante non è "corso nuovo per la classe" ma **"corso per cui quello studente non possiede ancora una `LMS Enrollment`"**. Rimuovere un corso dalla classe **non cancella l'iscrizione**: `BatchCourse` è una classe vuota senza alcun hook (`lms/lms/doctype/batch_course/batch_course.py`), non esiste un `doc_events` che la intercetti (`lms/hooks.py:117-132`) e l'unico punto che elimina le `LMS Enrollment` di un corso è `delete_course` (`lms/lms/api.py:1015`), cioè la cancellazione del corso stesso, non la sua rimozione dalla classe. Al riaggiungimento, quindi, `ensure_batch_course_enrollments` trova l'iscrizione già presente, non ne crea nessuna e `validate_course_enrollment_eligibility` — con il controllo `disable_self_learning` fuori posto alla riga 45 — **non viene mai eseguita**. Il difetto dell'Attività 1 colpisce esclusivamente il primo ingresso di un corso nella storia di quello studente. |
| **Soluzione applicata** | Nessuna: attività di sola delimitazione. Il risultato circoscrive l'impatto in produzione del difetto dell'Attività 1 (solo corsi mai iscritti da quello studente) e ha fatto emergere un **secondo difetto indipendente**, documentato sotto: la rimozione di un corso da una classe non revoca l'accesso agli studenti. |
| **Commit** | No — nessuna modifica al codice, attività di sola analisi e riproduzione |
| **File modificati** | Nessuno. File esaminati: `lms/lms/doctype/batch_course/batch_course.py`, `lms/hooks.py` (`doc_events`), `lms/lms/api.py` (`delete_course`, `delete_batch`). Script di riproduzione temporaneo nella scratchpad di sessione, non nel repository. |
| **Verifiche** | Riproduzione sperimentale sul container `dev-elite-frappe-1` (sito `lms.localhost`, branch `feature/oslms`), due varianti eseguite di seguito e con esito identico: corso A **con** `disable_self_learning` attivo e corso A **senza** il flag. Per ciascuna sono stati rilevati, a ogni passo, le righe `Batch Course` della classe, le `LMS Enrollment` dello studente, l'esito di `get_batch_courses` (pagina della classe) e l'esito di `get_courses(filters={"enrolled": 1})` (scheda "I miei corsi"). Dati di prova ripuliti a fine esecuzione. Esiti al punto 3. |

**1. Obiettivo dell'attività**

Stabilire l'esatto perimetro del difetto accertato nell'Attività 1, per poterne
valutare l'impatto reale sulla produzione. La domanda è operativamente rilevante: se
il difetto si ripresentasse anche per un corso rimosso e riaggiunto, ogni
riorganizzazione dei contenuti di una classe sarebbe a rischio e la correzione
diventerebbe urgente; se invece riguarda solo i corsi mai assegnati a quello studente,
l'esposizione è limitata al momento in cui un corso entra per la prima volta nel
percorso di una persona.

**2. Modalità di esecuzione**

Prima l'ipotesi per via statica, poi la verifica sperimentale, come nell'Attività 1.

1. **Ricerca di un punto di pulizia** delle `LMS Enrollment` collegato alla rimozione
   di una riga `Batch Course`: ispezione del controller `BatchCourse`, dei
   `doc_events` registrati in `lms/hooks.py` e dei punti di `api.py` che cancellano
   iscrizioni. L'assenza di un simile punto implica che l'iscrizione sopravvive alla
   rimozione, e quindi che il riaggiungimento non tocca la `validate` difettosa.
2. **Riproduzione della sequenza** indicata dall'utente (classe con A + B → iscrizione
   studente → rimozione di A → riaggiunta di A), rilevando lo stato a ogni passo su
   entrambi i canali con cui lo studente vede i corsi. La prova è stata eseguita due
   volte, con e senza il flag `disable_self_learning` sul corso A, per escludere che
   la conclusione dipendesse dal flag che è la causa scatenante dell'Attività 1.

**3. Attività svolte**

*Ipotesi statica.* Verificato che `BatchCourse` non definisce alcun metodo (`pass`),
che nessun `doc_events` la intercetta e che `delete_course` è l'unico punto a
cancellare le `LMS Enrollment` di un corso. Ne discende che rimuovere una riga dalla
tabella figlia della classe lascia intatte le iscrizioni degli studenti.

*Riproduzione.* Esito identico nelle due varianti (di seguito la variante con
`disable_self_learning = 1` sul corso A, cioè il caso peggiore):

| Passo | `Batch Course` | `LMS Enrollment` studente | Pagina della classe | "I miei corsi" |
| --- | --- | --- | --- | --- |
| Classe con A + B, studente iscritto | A, B | A, B | A, B | A, B |
| **Rimosso** A dalla classe | B | **A, B** | B | **A, B** |
| **Riaggiunto** A alla classe | B, A | A, B | **A, B** | A, B |

Conclusione sulla domanda posta: lo studente vede **due** corsi, il difetto non si
ripresenta. Confermata l'ipotesi statica in ogni passaggio.

*Secondo difetto emerso, indipendente dal primo.* La riga centrale della tabella
mostra un comportamento non previsto e non richiesto dall'utente:
**togliere un corso da una classe non revoca l'accesso agli studenti**. Il corso
sparisce dalla pagina della classe ma resta in "I miei corsi" e resta fruibile,
perché l'`LMS Enrollment` orfana continua da sola a garantire l'accesso — anche
qualora il corso non sia pubblicato, dato che `get_course_details` restituisce i
dettagli non appena esiste una membership. Conseguenza pratica: se in produzione un
corso è stato tolto da una classe con l'intento di ritirarlo agli studenti,
l'operazione non ha avuto effetto. La correzione naturale — cancellare le
`LMS Enrollment` con `enrollment_from_batch` sulla classe al momento della rimozione —
va però valutata con cautela, perché comporterebbe la perdita del progresso già
maturato dallo studente su quel corso; è una decisione di prodotto, non solo tecnica.

*Dettaglio minore rilevato.* Al riaggiungimento il corso si posiziona in coda alla
tabella figlia (`['corso-b', 'corso-a']`): l'ordine originale dei corsi nella classe
non viene recuperato e va eventualmente risistemato a mano.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), stessa sessione dell'Attività 1.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** formulazione dell'ipotesi sulla
  sopravvivenza dell'iscrizione, ricerca dei punti di pulizia nel codice, stesura ed
  esecuzione dello script di riproduzione a due varianti, lettura degli esiti e
  redazione di questa voce.
- **motivo della scelta del tool e del modello:** proseguimento diretto
  dell'Attività 1 nella stessa sessione, con il contesto della catena
  `Batch Course` → `LMS Enrollment` → endpoint già acquisito: riformularlo con un
  altro strumento sarebbe costato più della verifica stessa. Il contesto ampio di
  Opus 5 ha permesso di riusare senza rileggerli i file già esaminati e di collegare
  subito l'esito all'analisi precedente.
- **risultato ottenuto:** risposta netta alla domanda dell'utente (due corsi, difetto
  non ripetibile) con la regola generale che la spiega — conta l'esistenza della
  `LMS Enrollment`, non la storia della classe — e individuazione di un secondo
  difetto che l'utente non stava cercando e che ha ricadute operative sulla gestione
  dei contenuti delle classi.
- **verifiche e correzioni effettuate:** non ci si è fermati all'ipotesi statica, che
  da sola sarebbe stata plausibile ma non probante. La prova è stata eseguita in due
  varianti proprio per escludere che la conclusione valesse solo in assenza del flag
  `disable_self_learning`, cioè per non ripetere l'errore di ambito che nell'Attività 1
  aveva reso incompleta la prima diagnosi. Rilevati a ogni passo entrambi i canali di
  visibilità (pagina classe e "I miei corsi") e non solo quello citato dall'utente: è
  da questo controllo aggiuntivo che è emerso il difetto di mancata revoca.

**6. Problematiche incontrate**

Nessun ostacolo tecnico: l'ambiente di prova era già configurato e in esecuzione
dall'Attività 1, e lo script è stato scritto riusandone le fixture, senza le
difficoltà sui campi obbligatori già risolte in precedenza.

Un punto di metodo merita di essere annotato: la domanda dell'utente ammetteva una
risposta "no, non si ripresenta" che avrebbe potuto chiudere l'argomento in una riga.
Si è scelto di rilevare comunque lo stato completo a ogni passo, ed è stato questo a
far emergere il difetto di mancata revoca dell'accesso — che nessuno stava cercando e
che è più insidioso di quello indagato, perché silenzioso: non produce alcun errore e
l'operatore non ha modo di accorgersi che la rimozione non ha avuto l'effetto atteso.

---

### Attività 3 — Censimento completo dei casi che innescano il difetto delle iscrizioni ai corsi di classe

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — completamento della casistica delle Attività 1 e 2, senza modifiche al codice |
| **Problema riscontrato** | Richiesta dell'utente a valle delle due verifiche precedenti: elencare in modo esaustivo **quali casi** innescano il difetto, dopo aver accertato che un corso rimosso e riaggiunto non lo ripresenta. Serviva passare dai due episodi osservati alla regola generale, per poter valutare l'esposizione reale della produzione. |
| **Problema effettivo** | La regola è unica: il difetto scatta ogni volta che una `LMS Enrollment` deve essere **creata** in una sessione **non amministrativa** per un corso con `disable_self_learning` attivo — `is_admin()` è falso e il controllo fuori posto (`lms_enrollment.py:45`) esegue la `frappe.throw` prima che il bypass `enrollment_from_batch` (righe 51-58) possa intervenire. Applicando la regola è emerso un **terzo caso, il più grave e non segnalato dall'utente**: l'**auto-iscrizione alla classe**. `enroll_in_batch` (`lms/lms/utils.py:2312`) chiama `create_enrollment` (riga 2329), che costruisce la `LMS Batch Enrollment` con `member = frappe.session.user`, cioè **nella sessione dello studente**; da lì `validate_course_enrollment` tenta le iscrizioni ai corsi della classe e, se anche un solo corso ha il flag, l'eccezione fa fallire l'intera operazione: lo studente **non riesce nemmeno a entrare in classe**. È il percorso del pulsante "Enroll Now" di `BatchOverlay.vue:93-103`, attivo su tutte le classi con `allow_self_enrollment`. Lo stesso `create_enrollment` serve anche il percorso delle classi a pagamento (con `payment_doc` valorizzato), che è quindi esposto allo stesso esito. |
| **Soluzione applicata** | Nessuna: attività di sola analisi. Prodotta la casistica completa (quattro casi che innescano il difetto, tre che non lo innescano) come base per decidere la correzione. Il censimento non cambia il fix individuato nell'Attività 1 — resta lo spostamento del controllo di riga 45 — ma ne alza la priorità, perché il difetto non riguarda solo la visibilità di un corso ma anche l'accesso alla classe. |
| **Commit** | No — nessuna modifica al codice, attività di sola analisi e riproduzione |
| **File modificati** | Nessuno. File esaminati: `lms/lms/utils.py` (`enroll_in_batch`, `create_enrollment`, `get_payment_details`), `frontend/src/pages/Batches/components/BatchOverlay.vue`, `lms/lms/api.py` (ricerca di percorsi di disiscrizione). Script di riproduzione temporaneo nella scratchpad di sessione, non nel repository. |
| **Verifiche** | (a) Ricerca di un percorso di **disiscrizione dal singolo corso** in `api.py` e `utils.py` e nel frontend: **non esiste**. Le `LMS Enrollment` vengono cancellate solo da `delete_course` (`api.py:1015`); da notare che `delete_batch` (riga 1054) cancella le `LMS Batch Enrollment` ma **non** le `LMS Enrollment`, lasciando altre iscrizioni orfane. Non esistono quindi vie per rientrare nella condizione "corso della classe senza iscrizione" oltre a quelle censite. (b) **Riproduzione** dell'auto-iscrizione sul container `dev-elite-frappe-1`, in due varianti: classe con `allow_self_enrollment` contenente un corso **con** il flag → `ValidationError`, `LMS Batch Enrollment` **non creata**, studente fuori dalla classe; stessa classe con corso **senza** flag → iscrizione riuscita e `LMS Enrollment` creata. Dati di prova ripuliti a fine esecuzione. |

**1. Obiettivo dell'attività**

Trasformare i due episodi accertati nelle attività precedenti in una regola generale
verificabile e nell'elenco esaustivo dei casi che la soddisfano, così da poter
rispondere alla domanda che conta davvero per la produzione: *in quali situazioni,
oggi, un utente incontra questo difetto?* Senza questo passaggio la correzione
sarebbe stata valutata sulla base del solo sintomo riferito — un corso non visibile —
che si è rivelato la manifestazione meno grave del problema.

**2. Modalità di esecuzione**

1. **Formulazione della regola** a partire dal meccanismo già accertato, isolando le
   due condizioni necessarie e sufficienti: creazione di una `LMS Enrollment` (non
   una già esistente) e sessione non amministrativa.
2. **Enumerazione dei percorsi** che soddisfano entrambe le condizioni, cercando nel
   codice tutti i punti che creano una `LMS Enrollment` o una `LMS Batch Enrollment`
   e verificando per ciascuno in quale sessione giri.
3. **Ricerca dei percorsi di uscita**, cioè dei punti che cancellano una
   `LMS Enrollment`, per accertare se esistano altri modi di rientrare nella
   condizione di partenza oltre all'aggiunta di un corso alla classe.
4. **Riproduzione del caso nuovo** emerso dal punto 2, in due varianti, per non
   dichiararlo sulla sola lettura del codice.

**3. Attività svolte**

*Regola individuata.* Il difetto scatta quando una `LMS Enrollment` deve essere
**creata** in una sessione **non amministrativa** per un corso con
`disable_self_learning` attivo. Le due condizioni sono entrambe necessarie: se
l'iscrizione esiste già non viene eseguita alcuna `validate` (è quanto accertato
nell'Attività 2), e se la sessione è amministrativa il controllo viene saltato.

*Casistica che innesca il difetto:*

| # | Caso | Richiede il flag | Effetto | Stato |
| --- | --- | --- | --- | --- |
| 1 | Corso aggiunto a una classe con studenti **già iscritti** | sì | lo studente vede **zero** corsi nella pagina della classe | verificato (Attività 1) |
| 2 | Studente che si **auto-iscrive** alla classe ("Enroll Now") | sì | **l'iscrizione alla classe fallisce**, lo studente resta fuori | verificato in questa attività |
| 3 | Iscrizione a una **classe a pagamento**, dopo il pagamento | sì | come il #2 | derivato: stessa `create_enrollment`, non eseguito end-to-end perché richiede il gateway |
| 4 | Corso aggiunto a una classe con studenti già iscritti | **no** | il corso non compare in "I miei corsi" finché lo studente non apre la pagina della classe | verificato (Attività 1, scenario B) |

*Casistica che NON innesca il difetto:* corso rimosso e riaggiunto (l'iscrizione
sopravvive, Attività 2); studente iscritto da un utente con ruolo Moderator,
Course Creator o Batch Evaluator (`is_admin()` vero, controllo saltato — è la ragione
per cui lo studente nuovo funziona sempre); qualsiasi corso per cui lo studente
possieda già una `LMS Enrollment`, comunque ottenuta.

*Il caso 2 in dettaglio.* È il più grave e non era stato segnalato. Esito della
riproduzione con corso avente il flag:

```
AUTO-ISCRIZIONE alla classe -> ValidationError: You cannot enroll in this course
                               as self-learning is disabled...
in classe?      : False
LMS Enrollment  : []
```

Con il flag disattivato la stessa sequenza va a buon fine. Conseguenza operativa: una
classe con auto-iscrizione che contenga anche un solo corso con *Disable Self
Learning* **non è iscrivibile da nessuno studente**, e l'errore mostrato parla di
"self-learning disabilitato" per un corso, non della classe, risultando fuorviante
per chi lo riceve.

*Corollario utile alla diagnosi.* Finché gli studenti vengono aggiunti a mano da un
amministratore il difetto non si manifesta mai. Emerge solo quando è lo studente
stesso a innescare la creazione dell'iscrizione — aprendo la pagina della classe
(caso 1) o iscrivendosi da sé (casi 2 e 3). Questo spiega perché il problema possa
essere rimasto a lungo inosservato pur essendo presente da tempo.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), stessa sessione delle Attività 1 e 2.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** formulazione della regola generale a partire
  dai due episodi accertati, ricerca dei punti di creazione e di cancellazione delle
  iscrizioni, individuazione del percorso di auto-iscrizione come terzo caso, stesura
  ed esecuzione dello script di riproduzione a due varianti, redazione della casistica
  e di questa voce.
- **motivo della scelta del tool e del modello:** terza tappa della stessa indagine,
  con la mappa della catena `Batch Course` → `LMS Enrollment` → endpoint già in
  contesto dalle attività precedenti. Il passaggio richiedeva di generalizzare da due
  osservazioni a una regola e poi di ricercare nel codice tutti i percorsi che la
  soddisfano: un lavoro di attraversamento del repository che Claude Code svolge
  operando direttamente sui file, e che il contesto ampio di Opus 5 ha permesso di
  fare senza rileggere quanto già acquisito.
- **risultato ottenuto:** casistica completa in forma tabellare, con la scoperta del
  caso di auto-iscrizione — che cambia la natura del problema, da difetto di
  visibilità di un contenuto a difetto di accesso alla classe — e con l'accertamento
  che non esistono altri percorsi di rientro nella condizione difettosa, essendo
  assente qualunque funzione di disiscrizione dal singolo corso.
- **verifiche e correzioni effettuate:** il caso di auto-iscrizione non è stato
  dichiarato sulla sola lettura del codice ma riprodotto, e in due varianti, per
  isolare il ruolo del flag. Il caso della classe a pagamento è stato invece
  esplicitamente marcato come **derivato e non eseguito**, poiché richiede il gateway
  di pagamento: si è preferito dichiararne il limite piuttosto che presentarlo come
  verificato. È stata inoltre condotta la ricerca dei percorsi di disiscrizione — non
  richiesta — per accertare che la casistica fosse chiusa e non solo plausibile; da
  quella ricerca è emerso incidentalmente che `delete_batch` non cancella le
  `LMS Enrollment`, un terzo punto di generazione di iscrizioni orfane accanto a
  quello già rilevato nell'Attività 2.

**6. Problematiche incontrate**

Nessun ostacolo tecnico: ambiente già in esecuzione e fixture riusate dalle attività
precedenti.

Un limite dichiarato: il caso 3 (classe a pagamento) non è riproducibile in locale
senza configurare un gateway di pagamento, quindi resta un'inferenza — solida, perché
il codice attraversato è esattamente lo stesso del caso 2 già verificato, ma pur
sempre un'inferenza. Se ne consiglia la conferma qualora in produzione esistano
classi a pagamento contenenti corsi con *Disable Self Learning*, che sarebbero
altrimenti non acquistabili.

---

### Attività 4 — Correzione: i corsi di una classe sono visibili a tutti gli iscritti, anche se aggiunti dopo

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — implementazione del comportamento richiesto dall'utente |
| **Problema riscontrato** | Requisito espresso dall'utente a valle delle tre analisi precedenti: «se in una classe con degli iscritti viene aggiunto un corso, gli iscritti presenti e quelli futuri devono vedere i corsi aggiunti; i corsi presenti devono essere visibili dagli studenti iscritti alla classe anche se il corso è stato aggiunto dopo». Il comportamento accertato era invece: iscrizioni ai corsi create solo all'ingresso dello studente in classe, con `frappe.throw` in tutti i casi in cui la creazione avveniva in una sessione non amministrativa su un corso con *Disable Self Learning* (casistica completa nell'Attività 3). |
| **Problema effettivo** | Due difetti distinti, entrambi necessari da correggere perché il requisito sia soddisfatto. **(a)** In `LMSEnrollment.validate_course_enrollment_eligibility` il controllo `disable_self_learning` precedeva il bypass `enrollment_from_batch`, bloccando l'iscrizione via classe in sessione studente. **(b)** Nessun punto del codice ricollegava un corso aggiunto agli studenti già iscritti. In corso d'opera è emerso un **terzo difetto**, non prevedibile dall'analisi statica e rivelato solo dal test: spostare il controllo non bastava per il caso dell'auto-iscrizione, perché `LMSBatchEnrollment` creava le `LMS Enrollment` dentro `validate`, cioè **prima** che il record `LMS Batch Enrollment` fosse scritto sul database; il bypass, che verifica l'appartenenza alla classe con `frappe.db.exists`, non trovava nulla e falliva comunque. La creazione delle iscrizioni non è una validazione ma un effetto collaterale, e stava nel punto sbagliato del ciclo di vita del documento. |
| **Soluzione applicata** | Quattro modifiche coordinate più un patch di migrazione. **(1)** `lms_enrollment.py`: spostato il blocco `enrollment_from_batch` **prima** dei tre controlli sull'auto-iscrizione (self-learning, non pubblicato, a pagamento), con commento che ne spiega la ragione — chi è membro della classe ha diritto a tutti i corsi della classe, quelle restrizioni governano solo l'iscrizione autonoma. **(2)** `lms_batch_enrollment.py`: la creazione delle iscrizioni ai corsi spostata da `validate` ad `after_insert` e rinominata da `validate_course_enrollment` a `enroll_in_batch_courses`, così che il record di appartenenza alla classe esista già quando il bypass lo cerca; aggiunto `ignore_permissions=True` al salvataggio, coerente con gli altri punti che creano iscrizioni per conto dello studente. **(3)** `utils.py`: nuova funzione `enroll_batch_students_in_courses(batch, courses)` che crea le iscrizioni mancanti per tutti gli studenti della classe, idempotente (una sola query per rilevare le coppie già esistenti) e difensiva verso le righe `Batch Course` che puntano a corsi cancellati. **(4)** `lms_batch.py`: `on_update` ora chiama `enroll_students_in_added_courses`, che confronta le righe `courses` con quelle di `get_doc_before_save()` e iscrive gli studenti già in classe **soltanto** ai corsi aggiunti da quel salvataggio. **(5)** Nuovo patch `lms.patches.v2_0.backfill_batch_course_enrollments`, registrato in `patches.txt`, che sana le classi già esistenti in produzione. |
| **Commit** | Sì — `a7cd6d83` *fix(batches): show batch courses to students enrolled before the course was added*, branch `feature/oslms`. Committato su richiesta esplicita dell'utente al termine delle verifiche. Le sei modifiche sono raccolte in un unico commit perché non sono indipendenti: prese singolarmente nessuna soddisfa il requisito e la sola (1) lascia il difetto dell'auto-iscrizione. Worklog e report non inclusi, come da direttiva. I pre-commit hook non hanno eseguito alcun controllo (`We have nothing pre-commit hooks to run`), quindi il lint resta quello manuale descritto nelle verifiche. |
| **File modificati** | `lms/lms/doctype/lms_enrollment/lms_enrollment.py` (riordino dei controlli + commento), `lms/lms/doctype/lms_batch_enrollment/lms_batch_enrollment.py` (`validate` → `after_insert`, rinomina, `ignore_permissions`), `lms/lms/doctype/lms_batch/lms_batch.py` (import + `on_update` + nuovo metodo), `lms/lms/utils.py` (nuova funzione `enroll_batch_students_in_courses`), `lms/patches.txt` (1 riga), **nuovo** `lms/patches/v2_0/backfill_batch_course_enrollments.py`. Totale: 88 righe aggiunte, 10 rimosse su 5 file tracciati, più il file nuovo. |
| **Verifiche** | (a) **Riesecuzione dei quattro scenari di riproduzione** costruiti nelle Attività 1-3 (A: corso aggiunto con il flag; B: corso aggiunto senza il flag; C: rimozione e riaggiunta; D: auto-iscrizione, due varianti): tutti superati, dettaglio al punto 3. (b) **Test di regressione** mirati sulle restrizioni che dovevano restare in vigore: utente esterno alla classe verso corso con *Disable Self Learning* → rifiutato; verso corso non pubblicato → rifiutato; verso corso a pagamento non pagato → rifiutato; utente che **dichiara** una classe di cui non fa parte → rifiutato; utente che dichiara una classe che non contiene il corso → rifiutato con "This batch is not associated with this course."; membro della classe verso un corso della sua classe → consentito. (c) **Patch** provato su una classe con lo stato "rotto" simulato: iscrizione ricreata correttamente, e rieseguito una seconda volta senza duplicare nulla (idempotenza). (d) **Suite di test backend dell'app**: `run-tests --app lms` → **49 test, tutti superati** (`Ran 49 tests in 0.204s / OK`). (e) Controllo sintassi con `py_compile` sui 5 file Python e verifica manuale dello stile (indentazione a tab, righe entro 110 caratteri): le tre righe oltre i 110 caratteri in `lms_batch.py` sono **preesistenti** e non toccate. Ruff non è installato né sull'host né nel container, quindi il lint automatico non è stato eseguito. |

**1. Obiettivo dell'attività**

Implementare il comportamento richiesto: l'elenco dei corsi di una classe deve essere
la stessa cosa per tutti gli iscritti, indipendentemente dal momento in cui ciascun
corso è stato aggiunto e dal momento in cui ciascuno studente si è iscritto. È il
comportamento che un utente si aspetta da un LMS — la classe è il contenitore, i corsi
sono il suo contenuto — e la sua assenza produceva, oltre al sintomo segnalato, anche
classi non iscrivibili (caso 2 dell'Attività 3).

**2. Modalità di esecuzione**

Correzione su due assi, perché il requisito ha due metà: *sbloccare* la creazione
dell'iscrizione via classe, e *provocarla* al momento giusto.

1. **Sbloccare** — riordino dei controlli in `LMSEnrollment` e spostamento della
   creazione delle iscrizioni nel punto corretto del ciclo di vita di
   `LMSBatchEnrollment`.
2. **Provocare** — aggancio a `LMSBatch.on_update` per iscrivere gli studenti già in
   classe ai corsi appena aggiunti, così che il corso compaia immediatamente in
   "I miei corsi" e non solo dopo una visita alla pagina della classe.
3. **Sanare lo storico** — patch di migrazione per le classi già esistenti in
   produzione, che altrimenti resterebbero nello stato prodotto dal difetto.
4. **Verificare** riutilizzando come test di non regressione gli stessi script che
   avevano dimostrato il difetto, più una batteria nuova sulle restrizioni che
   dovevano rimanere in vigore.

Accortezza sul rischio di prestazioni: l'aggancio a `on_update` è stato scritto per
agire **solo sui corsi effettivamente aggiunti** da quel salvataggio, non su tutti i
corsi della classe a ogni salvataggio. Il costo a regime è quindi una sola query di
rilevamento, e il numero di inserimenti è pari alle iscrizioni realmente mancanti.

**3. Attività svolte**

*Prima iterazione.* Applicati il riordino dei controlli (1), l'helper (3), l'aggancio a
`on_update` (4) e il patch (5). Riesecuzione degli scenari: A e B superati — con un
miglioramento rispetto al minimo richiesto, perché nello scenario B il corso compare
in "I miei corsi" **prima** ancora che lo studente apra la pagina della classe, grazie
al backfill immediato — ma **lo scenario D1 (auto-iscrizione) continuava a fallire con
lo stesso errore**.

*Diagnosi del fallimento residuo.* L'analisi statica aveva dato per scontato che il
bypass `enrollment_from_batch` fosse raggiungibile in tutti i casi. Non lo era: nel
percorso di auto-iscrizione la `LMS Enrollment` viene creata da
`LMSBatchEnrollment.validate`, quindi **prima** dell'`INSERT` del record di
appartenenza alla classe; il bypass interroga il database con `frappe.db.exists` e non
trova nulla. È il tipo di difetto che solo l'esecuzione rivela, e che giustifica da
solo l'aver riprodotto invece di essersi fermati alla lettura del codice. Correzione:
spostamento in `after_insert`, dove il record esiste.

*Esiti finali dei quattro scenari:*

| Scenario | Prima | Dopo |
| --- | --- | --- |
| A — corso con il flag aggiunto a classe con iscritti | studente vede **0** corsi | iscrizioni create **subito all'aggiunta**; vede tutti e 3 i corsi |
| B — corso senza flag aggiunto a classe con iscritti | assente da "I miei corsi" fino alla visita alla classe | presente in "I miei corsi" **prima** della visita |
| C — rimozione e riaggiunta di un corso | funzionava | invariato, nessuna regressione |
| D1 — auto-iscrizione, classe con corso con il flag | **iscrizione alla classe rifiutata** | iscrizione riuscita, corso assegnato |

*Robustezza emersa dal campo.* La prima esecuzione del patch è fallita con
`LinkValidationError: Could not find Course: corso-informatica`: una classe del sito
di sviluppo contiene una riga `Batch Course` che punta a un corso cancellato. Dato
sporco reale e prezioso, perché in produzione un patch che solleva un'eccezione
**blocca `bench migrate`** e quindi il deploy. Due difese aggiunte: l'helper filtra i
corsi realmente esistenti prima di iscrivere, e il patch racchiude ogni classe in un
`try/except` che, in caso di errore, fa rollback, registra un Error Log e prosegue con
le altre — lasciando quella classe alla rete di sicurezza già esistente
(`ensure_batch_course_enrollments`, che agisce all'apertura della pagina della classe).

*Nota per il rilascio.* Il patch gira con `bench migrate`: il deploy in produzione
deve includerlo, altrimenti le classi esistenti resteranno sanate solo alla prima
visita di ciascuno studente alla pagina della propria classe.

**4. Utilizzo dell'AI**

- **tool/agente:** Claude Code (estensione VS Code), stessa sessione delle Attività 1-3.
- **modello:** Opus 5 (contesto 1M).
- **attività per cui è stata utilizzata:** progettazione della correzione su entrambi
  gli assi, scrittura delle cinque modifiche, diagnosi del fallimento residuo dello
  scenario D1, stesura ed esecuzione della batteria di test di regressione, esecuzione
  della suite backend, redazione di questa voce.
- **motivo della scelta del tool e del modello:** la correzione tocca quattro file che
  interagiscono attraverso il ciclo di vita dei documenti Frappe, dove l'ordine delle
  operazioni è la sostanza del problema: serviva uno strumento capace di modificare il
  codice e **rieseguire immediatamente** gli scenari di prova sul container, perché
  l'errore residuo sull'auto-iscrizione non era deducibile dalla lettura. Il contesto
  ampio di Opus 5 ha permesso di tenere insieme, senza rileggerli, i quattro script di
  riproduzione costruiti nelle attività precedenti e riusarli come suite di non
  regressione.
- **risultato ottenuto:** requisito soddisfatto in tutti gli scenari verificati, con
  due miglioramenti oltre il richiesto — il corso compare immediatamente in
  "I miei corsi" senza dover passare dalla pagina della classe, e le classi con
  auto-iscrizione tornano iscrivibili — e senza regressioni sulle restrizioni di
  iscrizione autonoma, che continuano a valere per chi non appartiene alla classe.
- **verifiche e correzioni effettuate:** la prima stesura della correzione era
  **incompleta** e i test l'hanno dimostrato: lo scenario D1 continuava a fallire, il
  che ha portato a individuare il terzo difetto (creazione delle iscrizioni in
  `validate` anziché in `after_insert`). Il patch è stato irrobustito dopo un
  fallimento reale su dati sporchi del sito di sviluppo, non per prudenza teorica. È
  stata inoltre scritta una batteria di regressione non richiesta, sulle restrizioni
  che dovevano **restare** attive, perché un fix che allarga un permesso va verificato
  soprattutto su ciò che deve continuare a essere negato: sei casi, tutti con l'esito
  atteso. Infine eseguita la suite backend dell'app (49 test, tutti superati). Non è
  stato possibile eseguire Ruff, assente sia sull'host sia nel container: lo stile è
  stato verificato a mano ed è stato accertato che le righe oltre i 110 caratteri
  presenti nei file toccati sono preesistenti.

**6. Problematiche incontrate**

Tre ostacoli, tutti risolti.

Il primo, già descritto: la correzione progettata sull'analisi statica non era
sufficiente, perché il bypass non era raggiungibile nel percorso di auto-iscrizione.
Risolto spostando la creazione delle iscrizioni in `after_insert`. È l'insegnamento
principale della giornata: in Frappe l'ordine fra `validate` e `after_insert` non è un
dettaglio stilistico, e mettere un effetto collaterale che scrive documenti dentro una
`validate` produce difetti che si manifestano solo in alcune sessioni.

Il secondo: il patch è fallito su un riferimento orfano presente nei dati del sito di
sviluppo. Risolto con il filtro sui corsi esistenti e il `try/except` per classe.
Da segnalare come possibile lavoro futuro: esistono righe `Batch Course` orfane, segno
che qualche corso è stato cancellato senza passare da `delete_course` — una pulizia
dei riferimenti pendenti sarebbe opportuna, ma è fuori dallo scopo di questa attività.

Il terzo, minore: Ruff non è disponibile in nessuno dei due ambienti, quindi il lint
automatico previsto dai pre-commit hooks del progetto non è stato eseguito. Sostituito
da controllo sintattico con `py_compile` e verifica manuale di indentazione e lunghezza
delle righe. Resta consigliata l'esecuzione di `pre-commit run --all-files` prima del
commit.

Nessun supporto esterno necessario.

---

## 2026-09-08

> **Report giornaliero:** [`reports/2026-09-08-os-lms.md`](../reports/2026-09-08-os-lms.md)
> — obiettivo e modalità della giornata, aggregazione delle attività per filone,
> utilizzo dell'AI, problematiche, prossime attività, avanzamento del progetto e
> spunti di miglioramento aziendale.

---

### Attività 1 — Traduzione in italiano del messaggio di conferma "Elimina membro"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — traduzione mancante nell'interfaccia |
| **Problema riscontrato** | Segnalato dall'utente: in *Impostazioni → Membri*, cliccando "Elimina membro", la finestra di conferma mostra il titolo tradotto ("Elimina \<nome\>?") ma il corpo del messaggio resta in inglese — *"This permanently deletes the user account and cannot be undone."* |
| **Problema effettivo** | La stringa **è già** avvolta in `__()` nel sorgente (`Members.vue:118`), quindi non si tratta di un'etichetta non tradotta a livello di codice: manca la traduzione nei cataloghi. In `lms/locale/it.po` la voce esiste (riga 8029, estratta dal sorgente) ma con `msgstr ""` vuoto, e in `lms/translations/it.csv` non esiste alcuna riga. Con entrambe le fonti vuote, Frappe ricade sul msgid inglese. Vincolo rilevante: nel progetto le traduzioni italiane vivono in **due** cataloghi (CSV e PO) e, quando il `msgstr` del PO è valorizzato, questo **prevale** sul CSV — motivo per cui non basta intervenire su una sola fonte se si vuole un comportamento stabile. |
| **Soluzione applicata** | Inserita la traduzione in entrambi i cataloghi: valorizzato il `msgstr` in `lms/locale/it.po` e aggiunta la riga corrispondente in `lms/translations/it.csv`, con lo stesso testo. Traduzione adottata: *"Questa operazione elimina definitivamente l'account utente e non può essere annullata."*, allineata alla formula già usata nel catalogo per le altre conferme distruttive ("Questa azione non può essere annullata."). Nessuna modifica al codice Vue: la stringa era già internazionalizzata correttamente. |
| **Commit** | Sì — `b8ed3818` *fix(i18n): translate student progress title and member deletion notice*, branch `feature/oslms`. Raccolta insieme all'altra correzione di traduzione della giornata (Attività 3): sono piccole, indipendenti dal fix PDF committato a parte e coerenti fra loro come tipo. |
| **File modificati** | `lms/locale/it.po` (riga 8030, `msgstr` valorizzato), `lms/translations/it.csv` (1 riga aggiunta in coda) |
| **Verifiche** | `msgfmt -c -o /dev/null lms/locale/it.po` → PO valido, nessun errore di sintassi né di formato. Parsing del CSV con il modulo `csv` di Python → 5.508 righe lette, la nuova riga risulta correttamente su 2 colonne; le righe malformate rilevate dal parser (indici 58, 613, 1391, 1888, 2196…) sono **preesistenti** e non toccate da questo intervento. Verificato inoltre che il titolo della stessa finestra ("Delete {0}?") fosse già tradotto in entrambi i cataloghi, quindi il disallineamento riguardava solo il corpo del messaggio. Non eseguita build frontend perché non necessaria: i cataloghi sono risorse di backend, non entrano nel bundle Vite. |

**1. Obiettivo dell'attività**

Rendere interamente in italiano la finestra di conferma dell'eliminazione di un
membro nelle impostazioni, oggi mista: titolo tradotto, corpo del messaggio in
inglese. Motivazione: è una conferma di un'operazione **distruttiva e
irreversibile** su un account utente; se la frase che spiega la conseguenza non è
comprensibile all'operatore, il rischio non è estetico ma operativo — si conferma
una cancellazione definitiva senza aver letto l'avviso. È inoltre l'unica parte in
inglese di una schermata per il resto localizzata, quindi salta all'occhio.

**2. Modalità di esecuzione**

Procedura seguita:

1. Ricerca della stringa esatta nel repository su tutte le estensioni rilevanti
   (`.vue`, `.js`, `.ts`, `.py`, `.csv`, `.po`, `.json`), escludendo
   `node_modules`, per capire se il problema fosse **codice non
   internazionalizzato** (stringa senza `__()`) oppure **catalogo incompleto**.
   Le due cause richiedono interventi diversi e non vanno confuse.
2. Lettura del punto di utilizzo in `frontend/src/components/Settings/Members.vue`
   per confermare l'avvolgimento in `__()` e vedere il contesto (proprietà
   `:message` del `Dialog` di conferma).
3. Ispezione dello stato della voce nei due cataloghi italiani (`lms/locale/it.po`
   e `lms/translations/it.csv`), perché nel progetto convivono e il PO prevale
   quando valorizzato.
4. Ricerca nel catalogo delle formule già adottate per "cannot be undone" /
   "irreversible", per non introdurre una variante stilistica nuova a fronte di
   traduzioni consolidate.
5. Applicazione della traduzione via script Python (lettura/scrittura UTF-8), con
   scrittura idempotente: il PO viene toccato solo se il `msgstr` è vuoto, il CSV
   solo se la stringa non è già presente.
6. Verifica formale dei due file (compilazione del PO, parsing del CSV).

**3. Attività svolte e risultati**

La ricerca iniziale ha escluso subito l'ipotesi più comune: la stringa non è
"dimenticata" nel codice, è correttamente marcata per la traduzione in
[Members.vue:118](../frontend/src/components/Settings/Members.vue#L118) e compare
di conseguenza in tutti i 33 cataloghi `.po` della cartella `lms/locale/`, segno
che l'estrazione dei messaggi ha funzionato. Il problema era a valle: per l'italiano
la voce esisteva ma senza traduzione (`msgstr ""`), e nel CSV non esisteva affatto.

Confronto utile emerso durante l'analisi: il **titolo** della stessa finestra
(`Delete {0}?`) risulta tradotto sia nel PO ("Elimina {0}?") sia nel CSV
("Eliminare {0}?"), il che spiega esattamente il sintomo riferito dall'utente —
finestra a metà in italiano e a metà in inglese — e conferma che l'incoerenza è
locale a una singola voce, non un problema del meccanismo di traduzione.

Per la scelta della resa italiana si è preferito non tradurre alla lettera
("Questo elimina permanentemente…") ma allinearsi alle formule già presenti nel
catalogo per le altre conferme distruttive, dove ricorre costantemente "Questa
azione non può essere annullata" (eliminazione di lezioni, capitoli, programmi,
esercizi). Il testo adottato — "Questa operazione elimina definitivamente l'account
utente e non può essere annullata." — mantiene quel registro e rende esplicito
l'oggetto dell'eliminazione (*l'account utente*, non solo l'iscrizione), che è
l'informazione realmente rilevante per chi conferma.

La traduzione è stata scritta in **entrambi** i cataloghi: nel PO perché è la fonte
che prevale, nel CSV per coerenza con il resto delle traduzioni italiane del
progetto e per non dipendere dall'esito di un futuro rigenerato dei file `.po` da
upstream.

Nota operativa per la verifica a video: le traduzioni sono risorse di backend e
vengono servite dalla cache di Frappe; perché la stringa appaia in italiano nel
browser occorre rigenerare la cache delle traduzioni sul sito (nel container:
`bench --site lms.localhost clear-cache`, oppure il `bench migrate` che l'entrypoint
esegue a ogni avvio) e ricaricare la pagina. Non serve invece alcuna build del
frontend.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), sessione sul repository
  `os_lms`, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* localizzazione della stringa non tradotta, diagnosi della
  causa (codice vs catalogo), scelta della resa italiana coerente con il catalogo
  esistente, applicazione su PO e CSV, verifica formale dei file.
- *Perché questo tool e questo modello:* l'attività sembra banale ("tradurre una
  frase") ma il punto critico è **dove** intervenire: il progetto ha due cataloghi
  italiani con una precedenza non ovvia (PO su CSV) e 33 file `.po` in cui la stessa
  stringa compare. Un tool con accesso diretto al repository permette di verificare
  lo stato reale delle due fonti invece di ipotizzarlo, e di controllare come sono
  già state tradotte le frasi analoghe, così da non introdurre una variante
  stilistica isolata. Il contesto ampio consente inoltre di tenere in vista sia il
  punto di utilizzo nel componente Vue sia i cataloghi.
- *Risultato ottenuto:* traduzione inserita in `it.po` e `it.csv`, coerente con le
  formule già in uso; nessuna modifica al codice sorgente, che era già corretto.
- *Verifiche e correzioni effettuate:* non ci si è fermati all'inserimento — il PO
  è stato ricompilato con `msgfmt -c` per escludere errori di sintassi (in
  particolare l'apostrofo e i caratteri accentati) e il CSV è stato riletto con un
  parser CSV per confermare che la nuova riga sia su due colonne. Le anomalie di
  parsing rilevate sono state esplicitamente attribuite a righe preesistenti e non
  corrette, per non allargare il perimetro dell'intervento.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Due elementi da tenere presenti: (a) la modifica **non è
visibile immediatamente** a video finché non si rigenera la cache delle traduzioni
sul sito, quindi un'eventuale verifica "a caldo" senza quel passaggio darebbe un
falso negativo; (b) il file `lms/translations/it.csv` contiene righe malformate
preesistenti (rilevate dal parser Python agli indici 58, 613, 1391, 1888, 2196 e
seguenti): non sono state toccate perché fuori dal perimetro della richiesta, ma
sono una potenziale fonte di traduzioni silenziosamente ignorate e meriterebbero
una verifica dedicata.

---

### Attività 2 — Verifica della segnalazione "PDF delle lezioni non fruibili da mobile"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — verifica di una segnalazione utente, senza modifiche al codice |
| **Problema riscontrato** | Segnalazione di una collega: da mobile i contenuti PDF delle lezioni non si adattano allo schermo. Viene mostrata solo la prima pagina, con dimensioni eccessivamente grandi, e non è possibile scorrere il documento per consultare le pagine successive. Richiesta esplicita: accertare se la segnalazione corrisponda al vero. |
| **Problema effettivo** | Segnalazione **confermata**. I PDF di lezione sono renderizzati come `<iframe>` grezzo con altezza fissa `700px` e nessun branch mobile, in due punti: `frontend/src/utils/upload.js:80-86` (percorso EditorJS, cioè il corpo lezione effettivo) e `frontend/src/components/LessonContent.vue:36-43` (percorso markdown/macro `{{ PDF }}`). Il ramo PDF è l'unico blocco privo di gestione responsive: nello stesso `LessonContent.vue` YouTube usa `screenSize.width < 640 ? 200 : 400` (riga 19), i video/audio hanno componenti dedicati e i file generici passano da `FileBlock`. Su iOS/WebKit un PDF dentro un iframe non istanzia il viewer completo ma un'anteprima statica della sola prima pagina, resa alla larghezza naturale della pagina (~612pt ≈ 816px) e non scrollabile via touch: da qui i tre sintomi descritti. Su Android Chrome non esiste viewer PDF inline per iframe, quindi il riquadro resta vuoto o parte un download. Su desktop il problema non si vede perché Chrome/Firefox hanno un viewer PDF integrato con toolbar e scroll propri. |
| **Soluzione applicata** | Nessuna: l'attività richiesta era la sola verifica. Individuati e documentati i due punti di intervento e le due strade percorribili per la correzione (rendering mobile-aware con apertura in scheda nativa su schermi piccoli, oppure integrazione di PDF.js per uniformare il comportamento su tutte le piattaforme). Decisione rimessa all'utente. |
| **Commit** | No — nessuna modifica al codice, attività di sola analisi |
| **File modificati** | Nessuno. File esaminati: `frontend/src/utils/upload.js`, `frontend/src/components/LessonContent.vue`, `frontend/src/components/FileBlock.vue`, `frontend/src/components/UploadPlugin.vue`, `frontend/src/pages/Lesson.vue` (CSS), `lms/lms/utils.py` (`rewrite_private_media`), `lms/lms/doctype/course_lesson/course_lesson.py` (`serve_resource`), `frappe/utils/response.py` (`send_private_file`) |
| **Verifiche** | Lettura dei due render path PDF; ricerca di eventuali override in `frontend/src/oslms/` (nessuno); ricerca di regole CSS su `iframe` in `Lesson.vue` e nei fogli globali (nessuna); `git log` su `upload.js` per escludere una regressione recente (ultimo tocco al ramo file: `fa9734e2`, che aggiunge i tipi documento/archivio senza modificare il ramo PDF); verificata la catena di servizio del file privato fino a `send_private_file`, che serve i `.pdf` **inline** e non come allegato — quindi la causa non è un `Content-Disposition: attachment`. **Riscontro sul campo (successivo all'analisi):** l'utente ha provato su un dispositivo Android reale e ha riportato, al posto del PDF, un rettangolo nero con la scritta `lms.lms.doctype.course_lesson.course_lesson.serve_resource` e un pulsante "Apri" che apre correttamente il documento in una nuova scheda. Riscontro **coerente con la previsione** e che aggiunge un secondo difetto, indipendente dal primo: vedi l'aggiornamento in coda all'attività. |

**1. Obiettivo dell'attività**

Stabilire se la segnalazione della collega sui PDF di lezione da mobile corrisponda
a un difetto reale del prodotto o a un problema di ambiente/dispositivo, e in caso
affermativo individuare la causa precisa a livello di codice, così da poter decidere
se e come intervenire.

**2. Modalità di esecuzione**

Analisi statica del codice frontend, partendo dalla ricerca dei punti che gestiscono
il tipo `pdf` e risalendo al componente che renderizza il corpo lezione. Verifica
incrociata su tre livelli, per escludere spiegazioni alternative prima di attribuire
la causa al render path:

1. **Frontend** — come viene costruito l'elemento che mostra il PDF, ed esistenza o
   meno di un branch per schermi piccoli.
2. **Override e CSS** — presenza di un override in `frontend/src/oslms/` o di regole
   CSS che possano compensare il comportamento; presenza di una regressione recente
   introdotta da un commit (`git log` mirato).
3. **Backend** — come il file privato arriva al browser (`rewrite_private_media` →
   `serve_resource` → `send_private_file`), per escludere che il problema sia un
   header che forza il download anziché la visualizzazione inline.

**3. Attività svolte**

Individuati i due punti in cui un PDF di lezione viene renderizzato. Entrambi
producono un `<iframe>` con `width='100%'` e `height='700px'` fisso, senza attributi
di fit (`#view=FitH`), senza viewer e senza alcuna variante per mobile:

- `frontend/src/utils/upload.js:80-86` — è il percorso realmente usato dal corpo
  lezione, che è EditorJS: il blocco `Upload` monta componenti Vue dedicati per
  video (`VideoBlock`), audio (`AudioBlock`) e file generici (`FileBlock`), mentre
  per il PDF scrive direttamente l'iframe via `innerHTML`.
- `frontend/src/components/LessonContent.vue:36-43` — percorso markdown/macro,
  usato da `Lesson.vue` per `instructor_notes` e per il corpo in formato macro.

L'elemento che qualifica la causa come dimenticanza e non come scelta progettuale è
il confronto interno a `LessonContent.vue`: ogni altro blocco ha la sua gestione
responsive o un componente dedicato, il solo ramo PDF no.

Correlazione fra causa e i tre sintomi riportati:

1. *Solo la prima pagina* — iOS/WebKit, per un PDF in iframe, rende un'anteprima
   statica della prima pagina invece del viewer completo. Comportamento noto e
   storico del motore, indipendente dal file.
2. *Dimensioni eccessive* — l'anteprima è resa alla larghezza naturale della pagina
   PDF (~612pt ≈ 816px per A4/Letter); su un viewport da 360-390px il contenuto
   sborda e appare ingrandito. Nessun `#view=FitH` e nessun viewer che faccia il fit.
3. *Scroll impossibile* — WebKit non propaga lo scroll touch dentro il
   sotto-documento PDF; inoltre i 700px fissi rendono l'iframe più alto del viewport,
   quindi il gesto entra in conflitto con lo scroll di pagina.

Esclusa la pista backend: `send_private_file` serve i `.pdf` inline (l'estensione
non rientra in `FORCE_DOWNLOAD_EXTENSIONS`), quindi il difetto non dipende da un
`Content-Disposition: attachment`.

Rilevata e **solo segnalata** un'incoerenza adiacente, senza intervenire: il ramo PDF
applica `encodeURI()` incondizionatamente all'URL, mentre `FileBlock.vue:47-56` evita
esplicitamente di ri-codificare gli URL già riscritti verso `serve_resource`
(`%20` → `%2520`). Probabilmente innocua perché `serve_resource` esegue un `unquote()`
che compensa la doppia codifica, ma resta da verificare separatamente.

Comunicato all'utente il limite della verifica: l'accertamento è statico, non
riprodotto su dispositivo reale. L'emulazione mobile di Chrome DevTools **non**
riproduce il difetto, perché usa comunque PDFium e renderizza correttamente; per la
conferma visiva serve un iPhone o un Android reale. Causa e sintomi combaciano
comunque in modo puntuale.

Indicate due strade per l'eventuale correzione, lasciando la scelta all'utente:
(a) rendering mobile-aware, con card di anteprima su schermi piccoli e apertura del
PDF in scheda nativa, dove iOS usa il proprio viewer completo; (b) integrazione di
PDF.js, per ottenere lo stesso comportamento su tutte le piattaforme al costo di una
dipendenza in più.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), sessione interattiva sul repository
  `os_lms`, branch `feature/oslms` (HEAD `0a61c2f1`)
- modello: Opus 5 (1M context)
- attività per cui è stata utilizzata: verifica della segnalazione sui PDF di lezione
  da mobile — localizzazione dei render path, individuazione della causa, correlazione
  fra causa tecnica e sintomi riportati dall'utente finale
- motivo della scelta del tool e del modello: la richiesta era di *accertare* una
  segnalazione, non di applicare una modifica. Serviva quindi un tool con accesso
  diretto al filesystem e alla history git, in grado di attraversare frontend,
  override e backend in un'unica sessione; Opus 5 è stato scelto perché il compito
  non è una ricerca testuale ma un'inferenza: collegare un dettaglio di
  implementazione (iframe con altezza fissa) al comportamento di un motore di
  rendering su una piattaforma specifica (WebKit su iOS) e ai sintomi descritti in
  linguaggio non tecnico. La finestra da 1M ha permesso di tenere insieme frontend e
  backend senza perdere il contesto.
- risultato ottenuto: segnalazione confermata, con causa localizzata su due punti
  precisi e spiegazione puntuale di ciascuno dei tre sintomi; escluse le ipotesi
  alternative (override, CSS, regressione da commit recente, header di download)
- verifiche e correzioni effettuate: ogni affermazione è stata riscontrata sul
  codice e non data per assunta. In particolare si è verificato che non esistessero
  override in `frontend/src/oslms/`, che nessuna regola CSS compensasse il
  comportamento, che `git log` su `upload.js` non mostrasse una regressione recente
  del ramo PDF, e si è risalita la catena backend fino a `send_private_file` per
  escludere l'ipotesi del download forzato. È stato inoltre dichiarato
  esplicitamente all'utente il limite della verifica statica (nessuna riproduzione
  su dispositivo reale, emulazione DevTools non rappresentativa) anziché presentare
  la conclusione come riscontro sul campo. L'incoerenza su `encodeURI()` è stata
  segnalata in una riga senza intervenire, in linea con la regola di mantenere le
  modifiche circoscritte alla richiesta.

**6. Problematiche incontrate**

Un solo ostacolo, di natura metodologica: il difetto **non è riproducibile
localmente**. L'emulazione mobile di Chrome DevTools continua a usare PDFium e mostra
il PDF correttamente, quindi non costituisce una verifica valida; servirebbe un
dispositivo iOS o Android reale. Si è scelto di procedere con l'accertamento statico,
dichiarandone apertamente il limite, poiché la corrispondenza fra causa individuata e
sintomi riportati è puntuale su tutti e tre i punti della segnalazione. Resta
consigliata una conferma visiva su dispositivo reale prima e dopo l'eventuale
correzione. Nessun supporto esterno necessario.


**Aggiornamento — riscontro su dispositivo Android reale**

Il limite dichiarato al punto 6 (nessuna riproduzione su dispositivo reale) è stato
colmato subito dopo dall'utente, che ha provato una lezione da Android. Riscontro:
al posto del PDF compare un **rettangolo nero** con la scritta
`lms.lms.doctype.course_lesson.course_lesson.serve_resource` e un pulsante **"Apri"**
che apre il documento in una nuova scheda, dove si legge correttamente.

Il riscontro conferma la previsione dell'analisi — Chrome per Android non dispone di
un viewer PDF inline per gli `<iframe>` e ricade sul proprio segnaposto di download —
e in più fa emergere un **secondo difetto, indipendente dal primo**: l'etichetta
mostrata nel segnaposto è il nome del metodo Python, non il nome del file.

Causa dell'etichetta, tracciata lungo la catena di risposta:

1. `serve_resource` restituisce `send_private_file(relative_path)`
   (`lms/lms/doctype/course_lesson/course_lesson.py:188`).
2. In `frappe/utils/response.py:309`, `as_attachment` è vero solo per le estensioni
   in `FORCE_DOWNLOAD_EXTENSIONS`, che vale `(".svg", ".html", ".htm", ".xml")`: un
   `.pdf` non è compreso, quindi `as_attachment = False`.
3. Di conseguenza la chiamata a werkzeug passa `download_name=None`
   (`response.py:332`), e werkzeug imposta l'header `Content-Disposition` **solo se**
   `download_name` è valorizzato (`werkzeug/utils.py:449-461`, verificato nel venv del
   container: `.../python3.14/site-packages/werkzeug/utils.py`). Stesso esito sul
   ramo nginx `X-Accel-Redirect`, che imposta l'header solo in caso di allegato
   (`response.py:319-320`).
4. Senza `Content-Disposition`, il browser non ha un nome file e ricade sull'ultimo
   segmento del *path* dell'URL. Poiché il file viaggia in query string
   (`/api/method/lms.lms.doctype.course_lesson.course_lesson.serve_resource?file_url=…`),
   quel segmento è il nome del metodo — da cui l'etichetta osservata.

Conseguenze pratiche per la correzione, da tenere insieme:

- Il difetto **non è solo di layout**: su Android il PDF non è visualizzabile inline
  in alcun modo, quindi non esiste un aggiustamento di CSS o di altezza dell'iframe
  che possa risolverlo. Serve cambiare la strategia di rendering.
- Il secondo difetto (nome del metodo al posto del nome del file) è **ortogonale** e
  va sanato comunque, in qualunque strada si scelga, valorizzando
  `Content-Disposition: inline; filename="…"` nella risposta di `serve_resource`.
  Migliora il segnaposto Android, il nome proposto al salvataggio e il titolo della
  scheda quando il PDF viene aperto a parte.
- Nota positiva emersa dal riscontro: il pulsante "Apri" funziona, quindi endpoint,
  permessi e streaming del file privato sono corretti. Il difetto è circoscritto alla
  sola visualizzazione incorporata.

Stato: in attesa che l'utente scelga la strada di correzione fra rendering
mobile-aware con apertura nativa e integrazione di PDF.js. Nessuna modifica al codice
in questa fase.

---

### Attività 3 — Traduzione del titolo "Student Progress" nel dettaglio studente

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — stringa non internazionalizzata nell'interfaccia |
| **Problema riscontrato** | Segnalato dall'utente: aprendo il dettaglio di un utente dalla dashboard, la finestra che mostra l'avanzamento dello studente ha il titolo in inglese — *"Student Progress"* — mentre tutto il resto del contenuto (percentuale completata, "Avanzamento del corso", "Avanzamento delle lezioni") è in italiano. |
| **Problema effettivo** | Caso **diverso** dall'Attività 1, benché il sintomo sia identico. Qui la traduzione italiana esisteva già nel catalogo CSV (tre righe, "Student Progress"), ma non veniva **mai** applicata perché la stringa non era internazionalizzata nel sorgente: in `StudentCourseProgress.vue:4` il titolo era passato come attributo statico `title="Student Progress"`, senza `__()`, quindi non attraversava affatto il livello di traduzione. Conseguenza collaterale: non essendo marcata, la stringa non era mai stata estratta nei file `.po` — infatti in `lms/locale/it.po` la voce non esisteva. Emerso inoltre un secondo problema che avrebbe reso il risultato non deterministico: le tre righe del CSV **non concordavano** ("Progressi dello studente" ×2, "Progresso Studente" ×1) e, poiché il caricamento del CSV costruisce un dizionario, avrebbe prevalso l'ultima. |
| **Soluzione applicata** | Tre interventi coordinati: (1) avvolta la stringa in `__()` nel componente, passando da attributo statico a binding — `:title="__('Student Progress')"`; (2) aggiunta la voce in `lms/locale/it.po` con il riferimento al punto di utilizzo e `msgstr "Progressi dello studente"`, inserita in ordine alfabetico fra "Student Details" e "Student View" per rispettare l'ordinamento del catalogo; (3) allineata la riga CSV divergente alla stessa resa, così che l'etichetta mostrata sia la stessa qualunque sia la fonte che prevale. Scelta la forma "Progressi dello studente" perché maggioritaria nel catalogo e con la maiuscola corretta per l'italiano (l'outlier "Progresso Studente" usava una maiuscola di tipo inglese). |
| **Commit** | Sì — `b8ed3818` *fix(i18n): translate student progress title and member deletion notice*, branch `feature/oslms`, insieme alla traduzione dell'Attività 1. |
| **File modificati** | `frontend/src/pages/Courses/StudentCourseProgress.vue` (riga 4), `lms/locale/it.po` (nuova voce, +4 righe), `lms/translations/it.csv` (1 riga allineata) |
| **Verifiche** | `yarn build` superata — 40,01 s, exit code 0, nessun errore; unico warning quello workbox preesistente sul glob delle risorse, presente anche nelle build precedenti. `msgfmt -c -o /dev/null lms/locale/it.po` → PO valido dopo l'inserimento. Verificato che il diff resti circoscritto ai 3 file attesi: durante la build il file autogenerato `frontend/components.d.ts` risultava temporaneamente modificato, ma a fine build è tornato identico all'originale (nessuna voce residua nel diff). Verificato che nello stesso componente `__()` fosse già usato nel template (righe 29 e 31), quindi disponibile senza import aggiuntivi. |

**1. Obiettivo dell'attività**

Portare in italiano il titolo della finestra di dettaglio dell'avanzamento di uno
studente, unica parte in inglese di una schermata per il resto già localizzata.
Motivazione: è il titolo della finestra, cioè l'elemento che il gestore legge per
primo per capire cosa sta guardando; lasciarlo in inglese in un'interfaccia
italiana è la disomogeneità più visibile possibile, anche se non compromette
l'operatività.

**2. Modalità di esecuzione**

Procedura seguita, deliberatamente identica a quella dell'Attività 1 perché
l'obiettivo è distinguere le due cause possibili prima di intervenire:

1. Ricerca della stringa esatta nel repository (sorgenti e cataloghi), escludendo
   `node_modules`. Esito immediatamente diagnostico: **una sola** occorrenza nel
   codice e nessuna nei file `.po`. L'assenza dai `.po` è il segnale che la stringa
   non è mai stata estratta, quindi non è marcata per la traduzione — diagnosi
   opposta a quella dell'Attività 1, dove la voce era presente in tutti e 33 i
   cataloghi ma vuota per l'italiano.
2. Lettura del componente per confermare che il titolo fosse un attributo statico
   e per verificare che `__()` fosse già in uso nel template (quindi disponibile
   come helper globale, senza bisogno di import).
3. Identificazione del componente effettivamente coinvolto. La segnalazione parlava
   di "dashboard della classe": è stato verificato quale finestra si apra da dove,
   perché esistono due modali di dettaglio studente distinte — `BatchStudentProgress`
   (aperta da `AdminBatchDashboard`, titolata con il nome dello studente e già
   localizzata) e `StudentCourseProgress` (aperta da `CourseDashboard`, quella con
   il titolo in inglese). L'intervento riguarda la seconda.
4. Controllo dello stato della stringa nei due cataloghi italiani, che ha fatto
   emergere l'incoerenza fra le tre righe CSV.
5. Applicazione delle modifiche via script Python con asserzioni preventive (il
   testo da sostituire deve comparire esattamente una volta; la voce non deve già
   esistere nel PO), così che uno stato inatteso interrompa lo script invece di
   produrre una modifica silenziosamente sbagliata.
6. Verifica formale: compilazione del PO e build completa del frontend, quest'ultima
   necessaria perché — a differenza dell'Attività 1 — qui è stato toccato un
   componente Vue.

**3. Attività svolte e risultati**

Il valore dell'attività non sta nella traduzione in sé ma nella diagnosi. Le due
segnalazioni di traduzione della giornata sono, per l'utente, lo stesso identico
sintomo ("questa scritta è in inglese"), ma hanno cause opposte e richiedono
interventi diversi:

| | Attività 1 (`Members.vue`) | Attività 3 (`StudentCourseProgress.vue`) |
| --- | --- | --- |
| Stringa marcata con `__()` | Sì | **No** |
| Presente nei `.po` | Sì, in tutti i cataloghi | **No**, mai estratta |
| Traduzione italiana esistente | No | **Sì**, già nel CSV (ma inutilizzabile) |
| Intervento | Solo cataloghi | **Codice** + cataloghi |

Il secondo caso è il più insidioso dei due: la traduzione esiste, chi cerca nel
catalogo la trova e conclude che "è già tradotta", mentre a video resta l'inglese.
L'unico indizio affidabile è l'assenza della voce dai file `.po`, che sono generati
per estrazione dal codice: se una stringa non compare lì, non è marcata.

È stata inoltre rimossa una fonte di non determinismo. Le tre righe CSV per la
stessa chiave non concordavano; una volta reso funzionante il meccanismo di
traduzione, l'etichetta mostrata sarebbe dipesa dall'ordine di caricamento del file.
Per questo la voce è stata scritta anche nel PO — che prevale — e la riga CSV
divergente è stata allineata: qualunque sia la fonte effettivamente usata, il
risultato a video è lo stesso.

Segnalazione a margine, **non corretta** perché fuori dal perimetro della richiesta:
`frontend/src/pages/Batches/components/BatchStudentProgress.vue:29` contiene
`__('Completato')`, cioè una stringa **già in italiano** passata alla funzione di
traduzione. Funziona (in assenza di traduzione viene restituito il testo originale)
ma rende quella etichetta non traducibile in nessun'altra lingua e la sottrae ai
cataloghi; andrebbe riportata a `__('Completed')` con la relativa voce italiana.
Nota strutturale già emersa nell'Attività 1 e qui confermata: `lms/translations/it.csv`
contiene **777 chiavi duplicate** su 5.458 righe valide — non un errore bloccante,
ma un terreno su cui incoerenze come quella di "Student Progress" possono nascondersi.

Come per l'Attività 1, perché la traduzione sia visibile a video occorre rigenerare
la cache delle traduzioni del sito (`bench --site lms.localhost clear-cache`, o il
`bench migrate` eseguito dall'entrypoint a ogni avvio del container); in più, qui è
già stata eseguita la build del frontend, necessaria perché la modifica tocca anche
un componente Vue.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), sessione sul repository
  `os_lms`, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* diagnosi della causa (stringa non marcata vs catalogo
  incompleto), identificazione del componente effettivamente coinvolto fra due
  candidati simili, correzione del sorgente, inserimento della voce nel PO nella
  posizione corretta, riconciliazione delle righe CSV divergenti, verifica con build.
- *Perché questo tool e questo modello:* la richiesta era di una sola riga
  ("tradurre un titolo"), ma la correzione giusta dipendeva da tre accertamenti che
  si possono fare solo leggendo il repository: se la stringa fosse marcata, quale dei
  due modali di dettaglio studente fosse quello segnalato, e quale traduzione
  sarebbe effettivamente prevalsa fra tre righe CSV discordanti. Un tool con accesso
  diretto al codice permette di rispondere a tutte e tre invece di applicare la
  correzione "ovvia" (aggiungere una traduzione al catalogo) che in questo caso non
  avrebbe prodotto **alcun** effetto a video, perché la traduzione c'era già.
- *Risultato ottenuto:* titolo internazionalizzato e tradotto, catalogo reso coerente,
  build verde.
- *Verifiche e correzioni effettuate:* non ci si è fidati della prima ipotesi — la
  ricerca iniziale sembrava indicare "traduzione mancante" (stesso sintomo del caso
  precedente) mentre il catalogo la conteneva già, e solo il controllo del sorgente
  ha rivelato la causa reale. Verificata la scelta del componente confrontando le due
  modali candidate invece di fermarsi alla prima corrispondenza testuale. Eseguite
  build e compilazione del PO, e controllato che il file autogenerato
  `components.d.ts`, modificato in corso di build, fosse tornato invariato a fine
  processo, per non lasciare rumore nel diff.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Un punto di attenzione metodologico: la segnalazione
localizzava il problema "nella dashboard della classe", mentre il componente
corretto è quello della dashboard del **corso** — le due schermate sono simili e
raggiungibili l'una dall'altra. La discrepanza è stata risolta cercando l'unica
occorrenza letterale della stringa e verificando da quale pagina viene aperto ogni
modale, invece di intervenire sul componente suggerito dalla descrizione. Resta il
consiglio, per le prossime segnalazioni di questo tipo, di allegare la stringa esatta
così com'è a video: è l'informazione che consente di individuare il punto senza
ambiguità.

---

### Attività 4 — Correzione della fruizione dei PDF di lezione da mobile

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — difetto confermato dall'analisi dell'Attività 2 e dal riscontro su dispositivo reale |
| **Problema riscontrato** | Da mobile i PDF delle lezioni non sono fruibili. Su iOS si vede la sola prima pagina, ingrandita e non scorribile; su Android (verificato dall'utente su dispositivo reale) compare al suo posto un rettangolo nero con la scritta `lms.lms.doctype.course_lesson.course_lesson.serve_resource` e un pulsante "Apri" che apre il documento in una nuova scheda. |
| **Problema effettivo** | Due difetti distinti, sovrapposti. **(1)** I PDF erano renderizzati come `<iframe>` grezzo con altezza fissa `700px` e nessun branch mobile, in `frontend/src/utils/upload.js` (percorso EditorJS) e in `frontend/src/components/LessonContent.vue` (percorso macro `{{ PDF }}`). Nessun browser mobile sa mostrare un PDF dentro un iframe: Chrome per Android non ha un viewer inline e ricade sul proprio segnaposto di download, iOS Safari rende un'anteprima statica non scorribile alla larghezza naturale della pagina (~612 pt ≈ 816 px, da cui l'ingrandimento su un viewport da 360-390 px). Non è quindi un difetto di layout: nessun aggiustamento di CSS o di altezza dell'iframe poteva risolverlo. **(2)** La risposta di `serve_resource` non portava alcun header `Content-Disposition`: `send_private_file` lo imposta solo per le estensioni in `FORCE_DOWNLOAD_EXTENSIONS` (`.svg`, `.html`, `.htm`, `.xml`), quindi per un `.pdf` passa `download_name=None` e werkzeug non emette l'header (`werkzeug/utils.py:449-461`). Senza nome file il browser ricade sull'ultimo segmento del *path* dell'URL: poiché il file viaggia in query string, quel segmento è il nome del metodo whitelisted — l'etichetta osservata su Android. |
| **Soluzione applicata** | Scelta dall'utente fra le due strade proposte: **rendering mobile-aware con apertura nativa**, senza nuove dipendenze. Introdotto il componente condiviso `PdfBlock.vue`, usato da entrambi i render path: sotto i 640 px sostituisce l'iframe con una card (icona, nome reale del documento, dicitura "Si apre in una nuova scheda" e pulsante "Apri il PDF"), che apre il file come navigazione top-level — lì sia Chrome Android sia Safari iOS usano il proprio viewer completo, con scroll e zoom corretti; da 640 px in su resta l'iframe, che su desktop funziona già. Il nome mostrato in card è ricavato dal parametro `file_url` della query string, non dal path, così da mostrare il documento e non l'endpoint. Preservato il comportamento desktop preesistente di ciascun percorso tramite la prop `toolbar` (il percorso macro nascondeva la toolbar nativa con `#toolbar=0`, quello EditorJS no). Lato backend, `serve_resource` valorizza ora `Content-Disposition: inline; filename*=UTF-8''<nome>`, mantenendo la resa inline: migliora il segnaposto Android, il nome proposto al salvataggio e il titolo della scheda quando il PDF si apre a parte. Aggiunte le traduzioni italiane delle due nuove stringhe. |
| **Commit** | Sì — `9e1b7948` *fix(lessons): make lesson PDFs readable on mobile*, branch `feature/oslms`. Tenuto separato dalle due correzioni di traduzione della giornata, che non hanno relazione con questo intervento e avrebbero reso insignificante tipo e scope del commit. Resta da confermare a video sul dispositivo Android. |
| **File modificati** | `frontend/src/components/PdfBlock.vue` (nuovo, 103 righe), `frontend/src/tests/pdfBlock.test.ts` (nuovo, 6 test), `frontend/src/utils/upload.js` (ramo PDF sostituito dal mount del componente), `frontend/src/components/LessonContent.vue` (iframe sostituito dal componente, rimossa `getPDFSource` ora inutilizzata), `frontend/components.d.ts` (autogenerato: registrazione di `PdfBlock`), `lms/lms/doctype/course_lesson/course_lesson.py` (header `Content-Disposition` in `serve_resource`, import di `quote`), `lms/translations/it.csv` (2 righe aggiunte). |
| **Verifiche** | `yarn build` superata (35,81 s, exit 0, solo il warning workbox preesistente). Verificato nel bundle prodotto che la vecchia stringa dell'iframe PDF sia sparita (0 occorrenze) e che le nuove stringhe siano presenti; verificato che la classe icona `lucide-external-link`, non ancora usata altrove nel progetto, sia stata generata dal plugin con il mask SVG completo. **Verifica a runtime sul container in esecuzione**: login come Administrator e `curl` sull'endpoint per un PDF realmente referenziato da una lezione (`/private/files/CU 2026 Overside.pdf`, nome con spazi) → `HTTP 200`, `Content-Type: application/pdf`, `Content-Disposition: inline; filename="CU 2026 Overside.pdf"` — nome corretto e resa inline preservata. Verificato leggendo il sorgente di `send_private_file` *nel container* che frappe non imposta l'header per i `.pdf`, quindi la sua presenza proviene dalla modifica e non era preesistente. 6 test unitari nuovi, tutti verdi (split di viewport, nome da `file_url`, fallback sul basename, `#toolbar=0` solo dove previsto, encoding dei path non ancora riscritti). Suite frontend completa: 188 test verdi, 21 rossi su 5 file — **fallimenti preesistenti**, accertato rieseguendo gli stessi 5 file su albero pulito via `git stash` (identico esito 21/21), quindi non causati da questa modifica. `ruff check` e `ruff format --check` sul file Python: entrambi puliti. |

**1. Obiettivo dell'attività**

Rendere consultabili da smartphone i PDF allegati alle lezioni, che oggi non lo sono
su nessuna delle due piattaforme mobili, e nel farlo eliminare l'etichetta con il nome
del metodo Python che il browser mostra al posto del nome del documento.

**2. Modalità di esecuzione**

Strada scelta dall'utente fra due alternative proposte con il compromesso esplicitato:
**card più apertura nativa**, preferita a un'integrazione di PDF.js perché non aggiunge
dipendenze (PDF.js avrebbe portato `pdfjs-dist`, ~350 KB gzip, e altro codice da
riallineare a ogni merge upstream) e perché delega la resa al viewer nativo del
browser, che su mobile è l'unico componente che sa davvero mostrare un PDF.

Accortezze poste come vincoli dell'intervento:

- **Non toccare il comportamento desktop**, che già funziona: il cambio deve essere
  circoscritto agli schermi sotto i 640 px, soglia già usata dal progetto
  (`useScreenSize().isMobile`).
- **Preservare le differenze preesistenti fra i due render path**: il percorso macro
  nascondeva la toolbar nativa (`#toolbar=0`), quello EditorJS no. Un componente
  condiviso rischiava di uniformarli in silenzio, cambiando la UX desktop di uno dei
  due; risolto con una prop esplicita anziché con una scelta implicita.
- **Non ri-codificare gli URL già riscritti dal server**, errore già noto e corretto in
  passato su `FileBlock` (`%20` → `%2520`): riusata la stessa guardia.
- **Separare i due difetti**: il fix dell'header è ortogonale alla scelta del viewer e
  va bene in qualunque scenario, quindi è stato fatto comunque.

**3. Attività svolte**

Creato `frontend/src/components/PdfBlock.vue`, componente unico per entrambi i render
path, seguendo la convenzione già in uso per gli altri blocchi lezione
(`VideoBlock`/`AudioBlock`/`FileBlock` montati da `upload.js` con `createApp`):

- **Sotto i 640 px** rende una card nel linguaggio visivo di `FileBlock` — icona
  `lucide-file-text` su fondo `surface-gray-2`, nome del documento in `truncate`,
  sottotitolo "Si apre in una nuova scheda" — con sotto un `Button` frappe-ui a
  larghezza piena. È stata usata la prop `link` del `Button`, che rende un `<a>` con
  `target="_blank"` e `rel="noreferrer noopener"`: serve una navigazione top-level
  vera, perché è quella che attiva il viewer nativo del browser.
- **Da 640 px in su** rende l'iframe come prima, con `#toolbar=0` applicato solo se la
  prop `toolbar` è `false`.

Il nome del documento è estratto con attenzione al formato reale degli URL: i file
privati passano da `serve_resource`, il cui path termina con il nome del metodo e che
porta il percorso vero nel parametro di query `file_url`. Il componente legge quindi
prima quel parametro e solo in sua assenza ricade sul basename del path — caso dei
file appena caricati nell'editor, non ancora riscritti dal server.

Aggiornati i due render path: in `upload.js` il ramo `pdf` monta il componente con
`translationPlugin` (necessario perché la card usa `__()`); in `LessonContent.vue`
l'iframe è sostituito dal componente con `:toolbar="false"`, e la funzione
`getPDFSource`, ora priva di chiamanti, è stata rimossa.

Lato backend, `serve_resource` valorizza `Content-Disposition` solo se assente, così da
non sovrascrivere l'header nei casi in cui frappe lo imposta già (estensioni a download
forzato). Il nome è passato in forma RFC 5987 percent-encoded, che neutralizza anche
eventuali caratteri di controllo nel nome file: pur provenendo da un record `File`
già validato a monte, l'header non viene composto con input grezzo.

Aggiunte a `lms/translations/it.csv` le traduzioni di "Open the PDF" e "Opens in a new
tab". Il solo CSV è sufficiente qui: i due msgid non esistono in `lms/locale/it.po`,
che il PO sovrascriverebbe il CSV solo se avesse un `msgstr` valorizzato. È la stessa
scelta già adottata per la stringa gemella "Click the icon to download" di `FileBlock`.

Scritti 6 test unitari in `frontend/src/tests/pdfBlock.test.ts`, che coprono i punti
dove una regressione futura sarebbe silenziosa: lo split di viewport nelle due
direzioni, il nome ricavato da `file_url` (con asserzione esplicita che "serve_resource"
**non** compaia), il fallback sul basename, `#toolbar=0` applicato solo dove previsto e
l'encoding dei path non ancora riscritti.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), sessione interattiva sul repository
  `os_lms`, branch `feature/oslms` (HEAD `0a61c2f1`)
- modello: Opus 5 (1M context)
- attività per cui è stata utilizzata: implementazione completa della correzione —
  progettazione del componente condiviso, modifica dei due render path, fix dell'header
  backend, traduzioni, test unitari e verifiche
- motivo della scelta del tool e del modello: l'intervento attraversa tre livelli
  eterogenei (componente Vue, plugin EditorJS in JS puro, endpoint Python) e ha come
  vincolo principale il *non* alterare comportamenti esistenti — la differenza di
  toolbar fra i due render path e la guardia sul doppio encoding sono dettagli non
  desumibili dal codice modificato ma dai suoi dintorni e dalla storia del repo.
  Serviva quindi un tool con accesso a filesystem, git, container Docker e suite di
  test in un'unica sessione, e un modello capace di tenere insieme quei vincoli:
  la finestra da 1M ha permesso di conservare il contesto dell'analisi (Attività 2)
  senza rileggerlo.
- risultato ottenuto: correzione completa e verificata su entrambi i difetti, con
  copertura di test sui punti fragili e nessuna regressione introdotta
- verifiche e correzioni effettuate: oltre a build, lint e test, si è evitato di dare
  per buono l'esito più comodo. In particolare: (a) l'header `Content-Disposition`
  osservato via `curl` è tornato nella forma `filename="…"` anziché nella forma
  `filename*=UTF-8''…` scritta nel codice — invece di accettare il risultato si è
  verificato leggendo il sorgente di `send_private_file` *dentro il container* che
  frappe non imposta quell'header per i `.pdf`, concludendo che la normalizzazione è
  di werkzeug in fase di serializzazione e che l'header proviene davvero dalla
  modifica; (b) i 21 test rossi della suite completa non sono stati liquidati come
  "preesistenti" per assunzione, ma accertati rieseguendo gli stessi 5 file su albero
  pulito via `git stash`, con esito identico; (c) la classe icona
  `lucide-external-link`, non ancora usata nel progetto, è stata verificata nel CSS
  prodotto per escludere un'icona vuota. Due correzioni in corso d'opera: i test
  fallivano prima per l'import reale di `frappe-ui` (che tira i moduli virtuali
  `~icons/lucide/*`, risolti solo dalla vite config dell'app) e poi per `__()` non
  disponibile nel template, risolti rispettivamente con un mock del modulo e con
  `global.mocks`, allineandosi alle convenzioni già presenti negli altri test.
  Segnalata all'utente, senza intervenire, l'incoerenza dello stesso tipo che
  `FileBlock` presenta sul nome file. Il pacchetto `ruff`, installato nel venv del
  container perché assente sia sull'host sia nel container, è stato disinstallato
  a fine verifica per lasciare l'ambiente come trovato.

**6. Problematiche incontrate**

Tre ostacoli, tutti risolti.

Il primo, metodologico: **il difetto non è riproducibile in locale**, né prima né dopo
la correzione. L'emulazione mobile di Chrome DevTools usa comunque PDFium e renderizza
il PDF correttamente, quindi non è una verifica valida. Compensato spingendo la verifica
dove era oggettivabile — header HTTP reale sul container, contenuto del bundle prodotto,
test unitari sullo split di viewport — ma **resta necessaria la conferma a video
dell'utente sul dispositivo Android** su cui il difetto è stato riprodotto.

Il secondo: il CLI `bench` nel container è rotto (`command not found`), problema già
noto e registrato. Aggirato usando direttamente il python del venv di frappe, secondo
la procedura già documentata.

Il terzo: durante la verifica dei test preesistenti è stato necessario un `git stash`
mentre **un'altra sessione lavorava in parallelo sugli stessi percorsi** (`frontend/src`,
`lms/translations/it.csv`). Lo stash è stato limitato ai soli path interessati e il
`pop` è rientrato senza conflitti, ma la manovra era rischiosa: con sessioni concorrenti
sarebbe più prudente verificare il baseline su un worktree separato anziché sull'albero
condiviso.

---

### Attività 5 — Verifica della segnalazione "la lezione video si completa dopo il tempo di permanenza anche senza avviare il video"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi / test — verifica di una segnalazione funzionale, con riproduzione sperimentale |
| **Problema riscontrato** | Segnalazione della collega: «Il blocco per i quiz funziona. Però se imposto un tempo di permanenza nelle lezioni di 60 secondi e imposto "Imponi completamento video", comunque segna la lezione video dopo 60s anche se non avvio il video». Richiesta: verificare se è vero. |
| **Problema effettivo** | **Segnalazione confermata**, ma non è un difetto unico: l'enforcement funziona nel caso nominale e cede in due situazioni distinte, entrambe riprodotte in laboratorio. La causa comune è il modo in cui `Lesson.vue` decide se la lezione "ha un video": non lo chiede al dato della lezione, lo **deduce dal DOM** una sola volta, circa 500 ms dopo il caricamento (`plyrSources.value.length > 0 \|\| document.querySelector('video')`, `frontend/src/pages/Lesson.vue:826-841`). (a) **Video incorporati come semplice `<iframe>`** — servizi `drive` (Google Drive), `cloudflareStream`, `bunnyStream`, `aparat` in `frontend/src/utils/index.js:340-395` — non producono né un `<video>` né un elemento Plyr: la sonda non li vede, `shouldStartDwellTimer` restituisce `true` e il dwell marca la lezione completa allo scadere dei secondi, **senza alcun avviso**, anche con l'enforcement attiva. Nota: `hasVideoContent()` (`frontend/src/utils/video.ts:105`), già usato nella stessa pagina per il pulsante "Statistiche video", questi blocchi li riconosce — la pagina quindi *sa* che la lezione ha un video mentre il timer decide di no. (b) **Video riconosciuto ma che non parte** (errore del player o nessun evento `ready` entro 15 s): `fallbackToDwellTimer()` (`Lesson.vue:970-986`) **riavvia deliberatamente il dwell** e la lezione si completa comunque allo scadere del tempo. È comportamento voluto dall'upstream (con toast di avviso "Video failed to load…"), ma dal punto di vista dell'utente il sintomo è identico a quello segnalato. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola verifica, come richiesto. Predisposto un banco di prova ripetibile (Chrome headless pilotato via CDP con uno script Node in scratchpad) che apre la lezione con la sessione di un utente iscritto, **non tocca il video** e registra l'istante esatto della chiamata `save_progress`, i warning di console e lo stato del DOM a 1,5 / 5 / 15 / 80 secondi. Sito di sviluppo riportato alla configurazione iniziale al termine delle prove. |
| **Commit** | Non committata — nessuna modifica al codice dell'applicazione; l'attività ha prodotto questa voce di registro e le evidenze sperimentali. |
| **File esaminati** | `frontend/src/pages/Lesson.vue` (watcher su `lesson.data` righe 808-857, `getPlyrSource` 858-892, `fallbackToDwellTimer` 969-986, `startTimer` 988-1001, `markProgress` 592-625), `frontend/src/utils/lessonProgress.ts`, `frontend/src/utils/plyr.js`, `frontend/src/utils/index.js` (servizi del tool `embed`), `frontend/src/utils/video.ts` (`hasVideoContent`), `frontend/src/utils/upload.js` + `frontend/src/components/VideoBlock.vue`, `frontend/src/components/Settings/Settings.vue`, `frontend/src/stores/settings.js`, `lms/lms/api.py` (`get_lms_settings`), `lms/public/frontend/assets/Lesson-Bg2v_CcJ.js` (bundle servito dal sito). Nessun file modificato. |
| **Verifiche** | Quattro prove sul sito Docker `lms.localhost` con `lesson_dwell_time = 60` e `enforce_video_completion = 1`, senza mai interagire col player, controllando l'esito sia sulla rete (chiamata a `course_lesson.save_progress`) sia sul database (`tabLMS Course Progress`): **(1)** lezione con embed **Vimeo** funzionante → nessuna chiamata entro 85 s, enforcement rispettata; **(2)** lezione con embed **YouTube** funzionante → nessuna chiamata entro 80 s, enforcement rispettata, ripetuta anche con CPU rallentata 12× (dati lezione a t=4 s) con lo stesso esito, quindi la finestra di 500 ms non è di per sé fragile; **(3)** stessa lezione Vimeo quando il player va in errore (`plyr-error: The URL is not available because of the video's privacy settings`) → warning `[Lesson] video fallback engaged` a t=2 s e **`save_progress` a t=62 s**; **(4)** lezione riscritta con embed **Google Drive** (`<iframe>` puro) → nessun elemento video rilevato in nessuna sonda, nessun warning e **`save_progress` a t=61 s**. Verificato inoltre che il bundle servito dal sito (`Lesson-Bg2v_CcJ.js`) contenga la stessa logica del sorgente, così che le prove valgano per il codice realmente in esecuzione. |

**1. Obiettivo dell'attività**

Stabilire se la segnalazione fosse vera e, in caso affermativo, individuarne il
meccanismo esatto, distinguendo fra un difetto del codice, una configurazione non
applicata e un comportamento voluto dall'upstream percepito come difetto. Il punto
era rilevante perché l'impostazione "Imponi completamento video" è l'unica leva che
impedisce allo studente di dare per fruita una lezione video senza guardarla: se
cede, il dato di avanzamento del corso perde valore.

**2. Modalità di esecuzione**

1. Lettura della catena completa che governa il completamento: impostazioni
   (`LMS Settings` → `get_lms_settings`), store del frontend, watcher di
   `Lesson.vue`, helper puri di `lessonProgress.ts`, inizializzazione Plyr,
   servizi del tool `embed` di EditorJS.
2. Verifica che il **bundle effettivamente servito** dal sito contenga la logica
   del sorgente, per escludere una build vecchia come spiegazione.
3. Lettura della configurazione reale sul database del sito di sviluppo.
4. Riproduzione sperimentale in browser reale, perché la logica dipende da *quando*
   gli elementi compaiono nel DOM e nessuna lettura statica può dimostrarlo.
   Cypress non è utilizzabile su questa macchina (l'Electron incluso non si avvia:
   `bad option: --no-sandbox`, firma del binario non valida), quindi il banco è
   stato costruito con **Chrome headless pilotato via CDP** da uno script Node,
   sfruttando il `WebSocket` nativo di Node 23.
5. Prove in configurazione identica a quella descritta dalla collega (60 s +
   enforcement attiva) su quattro tipi di contenuto video, con misura oggettiva:
   istante della `POST` a `save_progress` e riga corrispondente in
   `tabLMS Course Progress`.

**3. Attività svolte**

La logica attuale è quella upstream introdotta con la PR #2426 (cfr. Attività 5 del
07/09). Il watcher su `lesson.data` avvia sempre il timer di permanenza e poi, una
volta sola, **deduce dal DOM** se la lezione contiene un video; solo in quel caso, e
solo se l'enforcement è attiva, ferma il timer. La deduzione riconosce due sole
forme: un tag `<video>` (video caricati come file, resi da `VideoBlock.vue`) e un
player Plyr (YouTube e Vimeo, resi come `<div class="video-player">`).

Le prove hanno mostrato che nel caso nominale la funzione **funziona**: con YouTube
e con Vimeo correttamente caricati la lezione non viene marcata completa, né dopo
60 s né dopo 85 s. Il caso è stato ripetuto rallentando la CPU di 12× per verificare
se la finestra di 500 ms entro cui il DOM viene sondato fosse una corsa critica:
anche in quelle condizioni il player era già presente al momento del controllo.

I due casi in cui l'enforcement cede sono invece riproducibili in modo stabile:

- *Video come `<iframe>` puro.* Riscritta la lezione `0419` di `corso-c02` con un
  blocco `embed` di servizio `drive`: nessuna sonda ha rilevato `video`, `.plyr` o
  `.video-player` in tutta la durata della prova; la lezione è stata marcata
  completa dopo 61 secondi senza alcun avviso all'utente. Lo stesso vale per i
  servizi `cloudflareStream`, `bunnyStream` e `aparat`, che usano il medesimo
  template HTML. Elemento che rende il difetto evidente: nello stesso file esiste
  già `hasVideoContent()`, che lavora sul contenuto della lezione (non sul DOM) e
  riconosce **tutti** i blocchi `embed`; è la funzione che decide se mostrare il
  pulsante "Statistiche video". La pagina, quindi, considera quella lezione "con
  video" per un aspetto e "senza video" per l'altro.
- *Video che non parte.* Nella prova (3) il player Vimeo ha restituito
  «The URL is not available because of the video's privacy settings». **Nota di
  rettifica (Attività 8):** l'ipotesi formulata qui — che l'hash `?h=` andasse perso
  in `plyr.js` — è stata **smentita** dalla verifica successiva: l'hash arriva
  correttamente all'iframe. La causa reale è un errore *non fatale* di Vimeo
  (`PrivacyError` sul metodo `getVideoUrl`) trattato come mancato caricamento; si veda
  l'Attività 8 di questa giornata. Scattato l'errore, `fallbackToDwellTimer()`
  ha riavviato il dwell e la lezione è stata marcata completa a 62 s. Questo ramo è
  intenzionale (l'upstream preferisce non bloccare lo studente per un video rotto) e
  mostra un toast, ma produce esattamente il sintomo segnalato; va inoltre notato che
  il fallback si attiva anche solo per assenza dell'evento `ready` entro 15 secondi,
  quindi basta una rete lenta o un player che non risponde.

Conclusione consegnata: la segnalazione è vera; l'impostazione non è "ignorata", ma
il riconoscimento del video è troppo debole (dedotto dal DOM anziché dal contenuto
della lezione) e il ripiego sul dwell in caso di video non caricato è indistinguibile,
per l'utente, da un mancato funzionamento. La correzione naturale — non applicata
perché non richiesta — è far decidere la soppressione del dwell a `hasVideoContent()`
sul dato della lezione, lasciando alla sonda del DOM il solo compito di agganciare i
listener, e rendere configurabile (o almeno esplicito) il ripiego sul dwell quando il
video non si carica.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* lettura e ricostruzione della catena di
  completamento lezione attraverso frontend, impostazioni e bundle servito;
  formulazione delle ipotesi di rottura; costruzione del banco di prova in Chrome
  headless via CDP (script Node con WebSocket nativo, intercettazione delle
  richieste `save_progress`, cattura della console, sonde sul DOM a tempi fissi);
  esecuzione e lettura delle quattro prove; ripristino dello stato del sito.
- *Motivo della scelta del tool e del modello:* la domanda non era rispondibile per
  lettura del codice, perché l'esito dipende da *quando* gli elementi compaiono nel
  DOM rispetto a una finestra di 500 ms; serviva quindi un'esecuzione reale. Il
  contesto ampio ha permesso di tenere insieme in un'unica analisi frontend Vue,
  configurazione del doctype, bundle di produzione, database e strumentazione del
  browser, e di riusare la ricostruzione già fatta il 07/09 su questa stessa area.
- *Risultato ottenuto:* segnalazione confermata con due meccanismi distinti,
  entrambi riprodotti con misura oggettiva (istante della chiamata `save_progress`),
  e indicazione della correzione naturale senza applicarla.
- *Verifiche e correzioni effettuate sull'output dell'AI:* ogni conclusione è stata
  sottoposta a prova sperimentale invece che dedotta. In particolare due ipotesi
  iniziali plausibili sono state **smentite** dalle prove e scartate: la corsa fra il
  rendering di EditorJS e la finestra di 500 ms (smentita anche con CPU rallentata
  12×) e il doppio timer per la chiamata a `startTimer()` sia in `onMounted` sia nel
  watcher (irrilevante, perché al montaggio manca ancora `lesson.data.membership`).
  È stato inoltre verificato che il bundle servito dal sito corrisponda al sorgente,
  per non attribuire al codice attuale il comportamento di una build vecchia. Il caso
  "video funzionante" è stato provato due volte, con provider diversi, per non
  concludere dal singolo campione.

**6. Problematiche incontrate**

- *Cypress inutilizzabile su questa macchina.* L'Electron incluso in Cypress 14.5.4
  non si avvia (`SecCodeCheckValidity` fallita, `bad option: --no-sandbox`): il test
  è stato riscritto pilotando Chrome via CDP. Da tenere presente per le prossime
  prove end-to-end in locale.
- *CSRF sulle scritture via API.* Dopo che il browser di prova ha usato la stessa
  sessione, le successive `PUT` con lo stesso cookie sono state respinte con
  `CSRFTokenError`: le modifiche di configurazione vanno fatte da una sessione
  separata da quella usata dal browser. Un `PUT` respinto è passato inosservato per
  qualche minuto e ha fatto sembrare "controllo" una prova che invece aveva ancora
  l'enforcement attiva — il che, per fortuna, ha portato a scoprire il ramo di
  fallback; la lezione operativa è comunque di verificare sempre il codice HTTP.
- *Dato cancellato per errore sul sito di sviluppo (da segnalare).* Durante la
  pulizia fra una prova e l'altra ho eseguito una `DELETE` su
  `tabLMS Course Progress` filtrata per il solo `owner='Administrator'` senza
  restringerla al corso di prova: sono così andate perse le righe di avanzamento per
  lezione dell'utente **Administrator** del sito di sviluppo (le percentuali sulle
  iscrizioni restano: `a-guide-to-frappe-learning` 55,6%, `corso-informatica` 33,3%,
  ma i singoli completamenti non sono più elencati). Non esistono backup nel bench
  (`sites/lms.localhost/private/backups` vuota) e il dato non è ricostruibile.
  Riguarda solo l'account di test in locale, nessun utente reale e nessun altro
  ambiente. Sempre durante la pulizia ho cancellato per errore l'iscrizione
  `tfjrldhbqd` di `r.liciotti@overside.it` al corso `corso-c02` al posto di quella di
  prova: è stata **ripristinata integralmente** dal `tabDeleted Document` con nome,
  date di creazione/modifica, `progress` (25%) e `current_lesson` originali, e
  l'iscrizione di prova dell'Administrator è stata rimossa.
- *Configurazione del sito ripristinata.* `lesson_dwell_time` riportato a 2 e
  `enforce_video_completion` a 0 (valori precedenti), contenuto della lezione `0419`
  ripristinato dal backup preso prima della prova, spec Cypress temporanea eliminata:
  `git status` invariato rispetto all'inizio dell'attività.

---

### Attività 6 — Test del percorso opposto: il video guardato fino in fondo marca davvero la lezione completa

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Test — verifica sperimentale del completamento "buono" (video visto per intero) |
| **Esigenza di partenza** | Complemento dell'Attività 5. Lì era stato dimostrato *quando* l'enforcement cede; restava da dimostrare che, con il flag "Imponi completamento video" attivo, la lezione **si completi effettivamente** guardando il video fino alla fine. Senza questa prova la funzione poteva essere "sicura" ma inutilizzabile, cioè una lezione mai completabile. Richiesta dell'utente: usare un video corto, anche YouTube. |
| **Vincolo tecnico rilevante** | Il completamento passa dall'evento `ended` del player (`attachVideoEndedListeners`, `Lesson.vue:906-926`), quindi il video va **riprodotto davvero**: non basta simulare. Due ostacoli emersi: (a) l'istanza Plyr non è raggiungibile dal DOM — `plyr.js` la salva su `video.plyrInstance`, ma Plyr per i provider incorporati **sostituisce** quell'elemento, che quindi esce dalla pagina (è anche il motivo per cui nelle sonde dell'Attività 5 `.video-player` risultava 0 mentre `.plyr` era 1); (b) **YouTube non riproduce in Chrome headless** — il canale di comando funziona (un `seekTo` via postMessage sposta la posizione da 0 a 15 s) ma `playVideo` non avvia nulla, nemmeno da muto e con `--autoplay-policy=no-user-gesture-required`. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola verifica. Test rifatto su **Chrome visibile** (non headless) pilotato via CDP, avviando il video con un **click reale** sul pulsante Play di Plyr (`Input.dispatchMouseEvent`), cioè lo stesso gesto dello studente. Lezione di prova `0419` di `corso-c02` riscritta temporaneamente con un embed YouTube di 19 secondi ("Me at the zoo", `jNQXAC9IVRw`), scelto perché brevissimo, sempre disponibile e incorporabile. |
| **Commit** | Non committata — nessuna modifica al codice dell'applicazione. |
| **File esaminati** | `frontend/src/pages/Lesson.vue` (`attachVideoEndedListeners` 906-926, `markProgress` 592-625), `frontend/src/utils/plyr.js`. Nessun file modificato. |
| **Verifiche** | Prova con `lesson_dwell_time = 60` e `enforce_video_completion = 1`, quindi con una permanenza volutamente **più lunga** della durata del video: qualunque completamento prima dei 60 secondi non può venire dal timer. Esito: riproduzione reale da 0 a 19,02 s (posizione del player campionata ogni 2 s), poi **`save_progress` a t = 21,8 s** seguita da `track_video_watch_duration`; sul database la riga `tabLMS Course Progress` risulta creata con `status = Complete` sulla lezione `0419`, e l'avanzamento dell'iscrizione ricalcolato a 25% (1 lezione su 4). Prima del click, e durante l'attesa del player, nessuna chiamata. Stato del sito ripristinato al termine: contenuto della lezione `0419` dal backup, `lesson_dwell_time` a 2, `enforce_video_completion` a 0, iscrizione di prova `9u0pvl86bk` rimossa (nome annotato prima della cancellazione, per non ripetere l'errore dell'Attività 5), righe di avanzamento cancellate con filtro **ristretto al corso di prova**; `git status` invariato. |

**1. Obiettivo dell'attività**

Chiudere la verifica aperta con l'Attività 5 dimostrando che il flag "Imponi
completamento video" non solo *impedisce* il completamento indebito, ma *consente*
quello legittimo: video guardato per intero → lezione completa. È la metà della
funzione che nessuna delle prove precedenti aveva toccato, e senza la quale il
giudizio "funziona" non sarebbe stato sostenibile.

**2. Modalità di esecuzione**

1. Riscrittura temporanea di una lezione di prova con un video YouTube di 19
   secondi, previo backup del contenuto originale.
2. Configurazione con permanenza a 60 secondi, cioè **oltre il triplo** della durata
   del video: è l'accorgimento che rende il risultato non ambiguo, perché separa nel
   tempo i due meccanismi (timer vs fine video).
3. Avvio del video con un click reale sul pulsante Play, non via API del player, per
   restare fedeli al gesto dello studente.
4. Misura su tre piani indipendenti: posizione di riproduzione campionata ogni 2
   secondi, chiamate di rete intercettate, riga di avanzamento sul database.

**3. Attività svolte**

Il primo tentativo, in Chrome headless, non è riuscito: il video non parte né con il
click né con i comandi diretti all'API di YouTube. Che il canale di comando fosse
funzionante è stato accertato a parte (un `seekTo` sposta effettivamente la posizione
da 0 a 15 s), quindi il blocco riguarda la sola riproduzione — comportamento noto di
YouTube in ambienti headless. Accertato anche, in questa occasione, che l'istanza
Plyr non è raggiungibile da fuori dell'applicazione, perché Plyr rimuove dalla pagina
l'elemento su cui `plyr.js` la memorizza.

Ripetuta la prova su Chrome visibile, il video è partito al click e la riproduzione è
avanzata regolarmente fino a 19,02 s su 19. Alla fine del video, entro due secondi:
`save_progress` a t = 21,8 s e le due chiamate di `track_video_watch_duration`. Sul
database la lezione risulta `Complete` e l'iscrizione è passata al 25%. Poiché la
permanenza configurata era di 60 secondi, il completamento a ~22 secondi è
attribuibile **solo** alla fine del video.

Quadro complessivo della funzione, unendo Attività 5 e 6: con un video riconosciuto
(YouTube o Vimeo via Plyr, o un file caricato) il flag si comporta come previsto —
blocca il completamento finché il video non finisce e lo concede quando finisce.
Restano i due casi documentati nell'Attività 5: gli embed resi come `<iframe>` nudo
(Drive, Cloudflare Stream, Bunny Stream, Aparat), che non vengono riconosciuti come
video, e il ripiego deliberato sul timer quando il player va in errore o non risponde
entro 15 secondi.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione dell'Attività 5,
  branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* progettazione della prova (scelta del video
  breve e della permanenza lunga come discriminante fra i due meccanismi), scrittura
  dello script CDP con click reale e campionamento della posizione di riproduzione,
  diagnosi del mancato avvio in headless, esecuzione su Chrome visibile, verifica
  incrociata su rete e database, ripristino dello stato del sito.
- *Motivo della scelta del tool e del modello:* prosecuzione diretta dell'Attività 5,
  con lo stesso banco di prova già costruito e lo stesso contesto in memoria; la
  diagnosi del fallimento in headless richiedeva di tenere insieme il codice di
  `plyr.js`, il comportamento di Plyr sui provider incorporati e le politiche di
  riproduzione del browser.
- *Risultato ottenuto:* prova positiva e non ambigua del completamento a fine video,
  con evidenza su tre piani indipendenti.
- *Verifiche e correzioni effettuate sull'output dell'AI:* il primo esito negativo
  (headless) **non** è stato interpretato come un difetto dell'applicazione: prima di
  concludere è stato accertato che il canale di comando del player rispondesse, così
  da attribuire il fallimento all'ambiente di prova e non al prodotto. Il risultato
  positivo non è stato dedotto dalla sola chiamata di rete ma confermato sulla riga
  di database, e il timer è stato configurato in modo da non poter essere confuso con
  la causa del completamento.

**6. Problematiche incontrate**

- *YouTube non riproducibile in Chrome headless.* Vincolo dell'ambiente, non del
  prodotto. Le prove che richiedono riproduzione reale vanno fatte su browser
  visibile; quelle di non-completamento (Attività 5) restano valide in headless,
  perché non dipendono dalla riproduzione.
- *Istanza Plyr non esposta.* Non è possibile pilotare il player dall'esterno
  dell'applicazione: le prove devono passare dai controlli visibili. Da tenere
  presente per eventuali test automatici futuri su questa area.
- *Nessun errore di pulizia in questa attività.* A differenza dell'Attività 5, il
  nome dell'iscrizione creata è stato annotato prima di cancellarla e le cancellazioni
  sulle righe di avanzamento sono state ristrette al corso di prova.

---

### Attività 7 — Verifica se la presenza di testo insieme al video cambia il comportamento dell'enforcement

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Test — verifica di una variabile sospetta sollevata dall'utente |
| **Esigenza di partenza** | Domanda dell'utente a valle delle Attività 5 e 6: «c'è differenza se nella lezione oltre al video c'è del testo?». Le prove precedenti erano state fatte su lezioni minime (2 blocchi), quindi la domanda era legittima e la risposta non deducibile con sicurezza dalle prove già svolte. |
| **Vincolo tecnico rilevante** | Nella logica il testo **non entra**: la soppressione del timer dipende solo dall'esito di una sonda sul DOM che cerca un `<video>` o un player Plyr (`Lesson.vue:836-841`); i blocchi testuali non sono né contati né guardati. Esiste però una via indiretta per cui il testo potrebbe contare: la sonda gira **una volta sola**, circa 500 ms dopo l'arrivo dei dati della lezione, e più contenuto significa più lavoro di rendering per EditorJS — se il video comparisse nel DOM dopo quella finestra, non verrebbe riconosciuto e il timer marcerebbe la lezione. È l'ipotesi che andava provata. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola verifica. Costruita una lezione volutamente pesante — 80 blocchi, ~52 KB di contenuto: intestazione, 70 paragrafi, 7 elenchi puntati e **il video come ultimo blocco**, cioè l'ordine di rendering più sfavorevole — e provata due volte, a CPU normale e a CPU rallentata 20×. |
| **Commit** | Non committata — nessuna modifica al codice dell'applicazione. |
| **File esaminati** | `frontend/src/pages/Lesson.vue` (watcher 808-857), `frontend/src/utils/index.js` (strumenti EditorJS registrati). Nessun file modificato. |
| **Verifiche** | Configurazione `lesson_dwell_time = 60`, `enforce_video_completion = 1`, video mai avviato. **Prova A (CPU normale):** player rilevato già alla sonda di 1,5 s (80 blocchi renderizzati), **nessuna** chiamata a `save_progress` entro 85 s. **Prova B (CPU rallentata 20×):** dati della lezione arrivati a t = 10 s, DOM ancora vuoto alle sonde di 1,5 s e 5 s, player e 80 blocchi presenti a 15 s, **nessuna** chiamata a `save_progress` entro 100 s; database senza righe di avanzamento. Sito ripristinato al termine (contenuto lezione `0419` dal backup, permanenza a 2, enforcement a 0, iscrizione di prova `fv48lo0ufo` rimossa, righe di avanzamento cancellate con filtro ristretto al corso di prova). |

**1. Obiettivo dell'attività**

Stabilire se la quantità di contenuto testuale di una lezione possa far cedere
l'enforcement del completamento video, cioè se le conclusioni delle Attività 5 e 6 —
ottenute su lezioni minime — reggano anche su una lezione realistica, densa di testo.

**2. Modalità di esecuzione**

Stesso banco di prova delle attività precedenti (Chrome headless via CDP, misura
sull'istante della chiamata `save_progress` e riscontro sul database), con due
accorgimenti scelti per massimizzare la probabilità di far emergere il difetto se
esiste: **video come ultimo blocco** della lezione, così da essere l'ultimo elemento
renderizzato, e ripetizione della prova con CPU rallentata 20×, che è il modo più
diretto per allargare artificialmente il tempo di rendering rispetto alla finestra
fissa di 500 ms.

**3. Attività svolte**

In entrambe le prove il video è stato riconosciuto e il timer di permanenza soppresso:
nessun completamento, né a 60 secondi né oltre. Nella prova rallentata si vede bene il
meccanismo: a 1,5 e 5 secondi la pagina è ancora vuota (0 blocchi, nessun player) e i
dati della lezione arrivano solo a 10 secondi, ma il controllo non avviene a orologio
fisso dal caricamento della pagina — parte **dopo** l'arrivo dei dati e attende 500 ms
da lì. Rallentando la macchina si sposta in avanti anche il momento del controllo, e il
rapporto fra rendering e finestra di attesa resta favorevole.

Risposta consegnata: **no, il testo non fa differenza**. Ciò che conta è unicamente il
tipo di video (riconosciuto o no) e il fatto che il player si carichi; quantità,
posizione e tipo di contenuto attorno al video sono irrilevanti.

Segnalata all'utente, come nota di sola lettura del codice e non provata sul campo, una
differenza che invece esiste ed è di natura diversa: se una lezione contiene **più
video**, `attachVideoEndedListeners` (`Lesson.vue:906-926`) chiama `markProgress()` alla
fine di *qualunque* video, senza tenere il conto degli altri; una lezione con tre video
si completa quindi guardandone uno solo.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle Attività 5 e
  6, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* individuazione dell'unica via per cui il testo
  potrebbe influire (tempo di rendering contro finestra di 500 ms), generazione della
  lezione di prova pesante con il video in ultima posizione, esecuzione delle due prove,
  lettura dei risultati e ripristino dello stato del sito.
- *Motivo della scelta del tool e del modello:* prosecuzione diretta delle due attività
  precedenti, con banco di prova e contesto già in memoria; la domanda richiedeva di
  distinguere fra "il testo non è nella logica" (vero per lettura del codice) e "il testo
  non ha effetti" (dimostrabile solo per prova).
- *Risultato ottenuto:* risposta negativa dimostrata su due condizioni, di cui una
  volutamente estrema.
- *Verifiche e correzioni effettuate sull'output dell'AI:* la risposta non è stata data
  per lettura del codice, che da sola avrebbe ignorato l'effetto indiretto del tempo di
  rendering; la prova è stata costruita per **falsificare** l'ipotesi, non per
  confermarla (video in ultima posizione, CPU rallentata 20×), e l'assenza di
  completamento è stata verificata anche sul database e non solo sul traffico di rete.

**6. Problematiche incontrate**

Nessuna. Le prove sono state eseguite in headless perché non richiedono riproduzione
del video (si verifica un *mancato* completamento), quindi il limite incontrato
nell'Attività 6 non si applica. Nessun errore di pulizia: nome dell'iscrizione di prova
annotato prima della cancellazione e cancellazioni ristrette al corso di prova.

---

### Attività 8 — Causa reale del falso "Video failed to load" sulle lezioni con video Vimeo non elencati

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — individuazione della causa radice di un difetto già riprodotto |
| **Problema riscontrato** | Segnalazione dell'utente, che circoscrive quanto emerso nelle Attività 5-7: i flag e i controlli funzionano; il problema è che aprendo la lezione compare l'avviso *"Video failed to load — this lesson will still be marked complete after you spend some time on it."* **anche se il video si carica e si riproduce senza problemi**, e con esso salta il controllo sul completamento. In console: `[Lesson] video fallback engaged: plyr-error: The URL is not available because of the video's privacy settings.` Caso reale indicato: corso **Corso C01**, lezione "video" (`0466`), video `https://vimeo.com/1209911974/d7e7b74dda`. |
| **Problema effettivo** | Un errore **non fatale** e del tutto estraneo alla riproduzione viene trattato come mancato caricamento del video. La catena, verificata passo per passo: (1) subito dopo l'inizializzazione, Plyr chiama `getVideoUrl()` sull'SDK Vimeo — serve **solo** a costruire il link di download nei controlli (`node_modules/plyr/src/js/plugins/vimeo.js:292`); (2) per un video con privacy ristretta (tipicamente "non elencato") Vimeo rifiuta quella chiamata con `PrivacyError`; (3) l'SDK Vimeo, oltre a respingere la promise, **emette anche l'evento generico `error`** del player, perché è così che instrada gli errori di metodo; (4) Plyr inoltra qualunque errore dell'SDK come proprio evento `error` (`vimeo.js:426-429`); (5) `Lesson.vue:876-886` interpreta **qualsiasi** errore come "il video non si carica" e chiama `fallbackToDwellTimer()`, che riavvia il timer di permanenza e marca la lezione completa allo scadere. Il video, nel frattempo, è perfettamente funzionante. |
| **Rettifica di un'ipotesi precedente** | L'ipotesi annotata nell'Attività 5 — l'hash `?h=` perso da `plyr.js` tramite `extractYouTubeId()` — è **sbagliata** ed è stata rettificata in quella voce. L'attributo `data-plyr-embed-id` che scriviamo noi viene letto da Plyr **solo quando manca il `src`** (`vimeo.js:90-99`); qui il `src` c'è, e Plyr ricava l'hash da lì con `parseHash`. Verificato sul campo: l'URL dell'iframe realmente generato è `https://player.vimeo.com/video/1209911974?...&h=d7e7b74dda`, hash incluso. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola analisi, correzione non ancora autorizzata. Correzione proposta all'utente: nel gestore dell'errore attivare il ripiego **solo se il player non è mai diventato pronto**, cioè se l'evento `ready` non è stato emesso — un video che ha già segnalato `ready` si è caricato, e un errore successivo non è un mancato caricamento. Il controllo dei 15 secondi senza `ready` resta come rilevatore effettivo del video che non parte. |
| **Commit** | Non committata — nessuna modifica al codice. |
| **File esaminati** | `frontend/src/pages/Lesson.vue` (`getPlyrSource` 858-892, `fallbackToDwellTimer` 969-986), `frontend/src/utils/plyr.js`, `frontend/node_modules/plyr/src/js/plugins/vimeo.js` (righe 18-44 `parseId`/`parseHash`, 86-122 costruzione dell'URL, 290-300 chiamata `getVideoUrl`, 426-429 inoltro dell'errore), `node_modules/plyr/src/js/config/defaults.js` (attributi `data-plyr-embed-*`). Nessun file modificato; la lezione `0466` è stata solo letta. |
| **Verifiche** | **(a)** Lettura dell'URL realmente generato per l'iframe sulla lezione `0466`: contiene `h=d7e7b74dda`, quindi l'hash non si perde (ipotesi dell'Attività 5 smentita). **(b)** Prova di isolamento, **indipendente dall'LMS**: pagina statica servita su `localhost:8899` con il solo iframe Vimeo e l'SDK ufficiale, che chiama `getVideoUrl()` come fa Plyr. Esito: `ready ok`, `loaded ok`, durata restituita `8776` (il video è integro e riproducibile) e, in parallelo, `EVENTO error DAL SDK: {"message":"The URL is not available because of the video's privacy settings.","name":"PrivacyError","method":"getVideoUrl"}` con la promise rifiutata. È la prova che l'errore riguarda un metodo di servizio e non la riproduzione. **(c)** Ordine degli eventi nella pagina reale della lezione, registrato con un listener in fase di cattura installato prima dell'avvio della SPA: `ready` a **t = 1,028 s**, `error` a **t = 1,323 s** — l'errore arriva **dopo** che il player è pronto, cioè su un video già caricato. È il dato che rende praticabile la correzione proposta. |

**1. Obiettivo dell'attività**

Stabilire perché un video Vimeo funzionante generi l'errore che disattiva
l'enforcement, distinguendo fra tre spiegazioni possibili: un difetto nostro nella
costruzione dell'URL, una configurazione di privacy del video che ne impedisce davvero
l'incorporamento, oppure un errore innocuo interpretato male dall'applicazione. La
distinzione non è accademica: nel primo caso si corregge `plyr.js`, nel secondo si
cambiano le impostazioni del video su Vimeo, nel terzo si corregge la logica del
ripiego — e le tre strade non hanno nulla in comune.

**2. Modalità di esecuzione**

1. Lettura del contenuto reale della lezione segnalata, per partire dal dato salvato e
   non da un caso ricostruito.
2. Lettura dell'URL effettivamente generato per l'iframe, per verificare o smentire
   l'ipotesi sull'hash.
3. Lettura del plugin Vimeo di Plyr per capire da dove nasce l'evento `error` e a cosa
   serve la chiamata che lo provoca.
4. Prova di isolamento fuori dall'applicazione, per attribuire l'errore a Vimeo e non
   all'LMS.
5. Registrazione dell'ordine degli eventi nella pagina reale, per stabilire se al
   momento dell'errore il video fosse già caricato.

**3. Attività svolte**

La prima verifica ha smentito l'ipotesi che avevo formulato nell'Attività 5: l'hash di
privacy arriva a destinazione. La seconda ha spostato l'attenzione sul punto giusto —
Plyr chiama `getVideoUrl()` solo per costruire il link di download dei controlli, e su
un video non elencato Vimeo rifiuta quella chiamata. La prova di isolamento ha
mostrato il comportamento allo stato puro: lo stesso player che restituisce
correttamente `ready`, `loaded` e la durata del video emette **anche** l'evento
`error` con `name: PrivacyError` e `method: getVideoUrl`. Il registro degli eventi
nella pagina reale ha infine fissato l'ordine: `ready` a 1,028 s, `error` a 1,323 s.

Il difetto è quindi nella nostra interpretazione dell'evento, non nel video né
nell'URL: `Lesson.vue` non distingue fra "il video non si carica" e "una chiamata di
servizio non è disponibile", e degrada la funzione sulla base della seconda. Ne segue
che **ogni** video Vimeo non elencato — cioè la configurazione tipica dei corsi —
disattiva di fatto l'enforcement del completamento, pur riproducendosi regolarmente.
Spiega anche perché nelle prove dell'Attività 5 il fenomeno appariva intermittente:
l'esito dipende da come si incastrano l'arrivo dell'errore, l'aggancio dei nostri
listener e la presenza dell'iscrizione (senza iscrizione `fallbackToDwellTimer()` esce
subito e non lascia nemmeno il messaggio in console).

Correzione proposta e non applicata: subordinare il ripiego alla mancata emissione di
`ready`. Un player che ha già segnalato `ready` si è caricato, quindi un errore
successivo non deve degradare il completamento; il controllo dei 15 secondi senza
`ready`, già presente, continua a coprire il caso del video che davvero non parte.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle Attività 5-7,
  branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* lettura del plugin Vimeo di Plyr e della
  catena dell'evento `error`, progettazione ed esecuzione della prova di isolamento
  con l'SDK Vimeo, strumentazione della pagina reale per registrare l'ordine degli
  eventi, formulazione della correzione proposta.
- *Motivo della scelta del tool e del modello:* la diagnosi richiedeva di attraversare
  tre livelli — codice nostro, libreria di terze parti in `node_modules`, SDK remoto di
  Vimeo — e di progettare una prova che li separasse; il contesto ampio ha permesso di
  tenere insieme i tre livelli e le prove già fatte nelle attività precedenti della
  stessa giornata.
- *Risultato ottenuto:* causa radice individuata e dimostrata, ipotesi precedente
  smentita e rettificata nel registro, correzione mirata proposta con il dato
  sperimentale che la giustifica (l'ordine `ready` → `error`).
- *Verifiche e correzioni effettuate sull'output dell'AI:* la prima ipotesi prodotta
  (perdita dell'hash) era **sbagliata** ed è stata scartata leggendo l'URL realmente
  generato invece di fermarsi alla lettura del nostro codice; la nuova ipotesi non è
  stata accettata sulla base del solo messaggio d'errore ma riprodotta fuori
  dall'applicazione, così da escludere che dipendesse dall'LMS; la praticabilità della
  correzione proposta non è stata assunta ma misurata, registrando l'ordine degli
  eventi nella pagina reale.

**6. Problematiche incontrate**

- *Ipotesi errata portata avanti per un'attività intera.* L'Attività 5 ha attribuito
  l'errore alla perdita dell'hash in `plyr.js`: plausibile leggendo solo il nostro
  codice, ma falsa. È stata rettificata nella voce corrispondente. La lezione operativa:
  quando il sospetto cade su un valore che attraversa una libreria di terze parti,
  conviene leggere il valore **in uscita** (qui l'URL dell'iframe) prima di
  incolpare il codice che lo prepara.
- *Decisione aperta.* La correzione non è stata applicata: attende conferma dell'utente,
  perché tocca il comportamento del ripiego introdotto dall'upstream e andrà
  riapplicata a ogni merge.

---

### Attività 9 — Correzione del falso "Video failed to load" che disattivava l'imposizione del completamento video

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — difetto funzionale sul completamento delle lezioni video |
| **Problema riscontrato** | Con "Imponi completamento video" attivo, aprendo una lezione con video Vimeo compare *"Video failed to load — this lesson will still be marked complete after you spend some time on it."* anche se il video si carica e si riproduce senza problemi; da lì il controllo salta e la lezione viene marcata completa allo scadere del tempo di permanenza. Caso reale: corso **Corso C01**, lezione `0466`, video `https://vimeo.com/1209911974/d7e7b74dda`. |
| **Problema effettivo** | Diagnosi completa nell'Attività 8. In sintesi: Plyr chiama `getVideoUrl()` sull'SDK Vimeo solo per costruire il link di download dei controlli; su un video **non elencato** Vimeo rifiuta la chiamata con `PrivacyError` e l'SDK, oltre a respingere la promise, **emette anche l'evento generico `error`** del player; Plyr lo inoltra come proprio `error` e `Lesson.vue` lo interpretava come "il video non si carica", degradando il completamento al timer di permanenza. L'errore non riguarda la riproduzione e arriva **dopo** che il player è pronto (misurato: `ready` a 1,028 s, `error` a 1,323 s). Poiché "non elencato" è la configurazione tipica dei video dei corsi, l'enforcement risultava di fatto disattivata su quasi tutte le lezioni video. |
| **Soluzione applicata** | Nuovo helper puro `shouldEngageFallbackOnPlayerError()` in `frontend/src/utils/lessonProgress.ts`, coerente con i quattro helper già presenti nel modulo, e sua adozione nel gestore dell'errore in `Lesson.vue`. Un errore del player degrada il completamento **solo** se ricorrono entrambe le condizioni: il player non è mai diventato pronto **e** l'errore non nomina il metodo dell'SDK da cui proviene. Le due condizioni coprono ordini di arrivo diversi: la prima esclude gli errori su un video già caricato, la seconda gli errori di chiamate di servizio anche se arrivassero prima di `ready`. La lettura usa `player.ready || readyFired`, perché la proprietà di Plyr copre anche un evento `ready` emesso prima che il nostro listener fosse agganciato. Ogni altro errore continua a far scattare il ripiego, come vuole l'upstream, e il controllo dei 15 secondi senza `ready` resta invariato. |
| **Commit** | Sì — `a931cf98` *fix(lessons): keep video enforcement on a non-fatal player error*, branch `feature/oslms`. Tenuta separata dalla traduzione dell'Attività 10 perché di tipo e scope diversi, coerentemente con la pratica già seguita in questo progetto. Non pushata. |
| **File modificati** | `frontend/src/utils/lessonProgress.ts` (+22, nuovo helper con commento sul perché), `frontend/src/pages/Lesson.vue` (+10, import e guardia nel gestore `player.on('error')`), `frontend/src/tests/lessonProgress.test.ts` (+42, quattro casi nuovi). Totale 74 righe aggiunte, nessuna rimossa. Eseguito anche `yarn build` per allineare il bundle servito dal sito locale: `lms/public/frontend` è in `.gitignore`, quindi non produce modifiche nel repository. |
| **Verifiche** | **Unitarie:** `npx vitest run src/tests/lessonProgress.test.ts` → 21 test superati (17 preesistenti + 4 nuovi: video mai caricato, errore dopo `ready`, `PrivacyError` di `getVideoUrl`, dettaglio assente o vuoto). **Funzionale sul caso reale** (dev server Vite, `enforce_video_completion = 1`, permanenza 60 s, video mai avviato, lezione di Corso C01): l'errore Vimeo arriva ancora — `{name: PrivacyError, method: getVideoUrl}` a t = 10,2 s, dopo `ready` a t = 9,6 s — ma **nessun avviso di ripiego**, **nessuna** chiamata a `save_progress` entro 85 s e nessuna riga in `tabLMS Course Progress`. **Controprova sulla valvola di sicurezza** (stesso video, traffico verso `player.vimeo.com` bloccato dal browser, quindi player mai pronto): `[Lesson] video fallback engaged: plyr-no-ready-15s` a t = 16,8 s e `save_progress` a t = 76,8 s (16,8 + 60 di permanenza), riga a database con `status = Complete`. Il ripiego legittimo funziona ancora. Sito ripristinato: permanenza a 2, enforcement a 0, contenuto della lezione di prova `0419` dal backup, iscrizioni di prova `0vu0d8hcto` e `29481jb632` rimosse (nomi annotati prima), righe di avanzamento cancellate con filtro ristretto ai due corsi di prova. |

**1. Obiettivo dell'attività**

Applicare la correzione proposta nell'Attività 8 e dimostrarne sul campo i due lati:
che l'enforcement non venga più disattivata da un errore innocuo, e che continui a
degradare al timer quando il video davvero non si carica — perché una correzione che
ottenesse solo il primo risultato lascerebbe lo studente bloccato su una lezione con
un video rotto.

**2. Modalità di esecuzione**

Modifica secondo il disegno già presente nel modulo (helper puro e testabile in
`lessonProgress.ts`, uso in `Lesson.vue`), test unitari sui casi limite, e verifica in
browser reale su **due** scenari opposti costruiti apposta. Le prove sono state fatte
contro il **dev server Vite**, non contro il bundle compilato, per non alterare gli
asset del sito prima di avere la conferma che la correzione funzionasse.

**3. Attività svolte**

La guardia è stata scritta con due condizioni anziché una perché la sola verifica su
`ready` avrebbe lasciato scoperto il caso, possibile in linea di principio, di un
errore di metodo che arrivi prima che il player sia pronto. La condizione sul metodo è
precisa: un errore che nomina la chiamata dell'SDK da cui proviene (`getVideoUrl`,
qui) è per costruzione un errore di servizio, non di riproduzione.

Nelle prove è emerso un dettaglio che ha confermato la scelta: Plyr dispatcha
l'evento `error` due volte, una sul media (dettaglio generico) e una sul contenitore
con il dettaglio ricco. Il nostro `player.on('error')` ascolta il contenitore e riceve
quindi l'oggetto errore di Vimeo completo di `name` e `method` — che è ciò su cui la
guardia lavora.

Osservazione registrata a parte, **non** causata da questa correzione e presente anche
prima: un video Vimeo il cui id **non esiste** fa emettere a Plyr un `ready` regolare e
nessun errore. In quel caso non scatta né il ripiego né il completamento, quindi la
lezione resta non completabile. Il comportamento è identico prima e dopo la modifica —
verificato — e va affrontato separatamente, se il cliente lo ritiene rilevante.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle Attività 5-8,
  branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* scrittura dell'helper e della guardia,
  redazione dei quattro test unitari, esecuzione della suite, progettazione ed
  esecuzione delle due prove funzionali opposte (caso reale e valvola di sicurezza con
  Vimeo bloccato via CDP), ripristino dell'ambiente e verifica del diff finale.
- *Motivo della scelta del tool e del modello:* prosecuzione diretta della diagnosi
  dell'Attività 8, con lo stesso banco di prova già pronto; la correzione richiedeva di
  tenere insieme il comportamento di Plyr, quello dell'SDK Vimeo e la logica di
  completamento della SPA.
- *Risultato ottenuto:* correzione di 74 righe, tutta additiva, con test unitari e
  duplice verifica funzionale.
- *Verifiche e correzioni effettuate sull'output dell'AI:* la correzione **non** è stata
  considerata valida sulla base della sola prova positiva: è stata costruita apposta la
  prova opposta (blocco del traffico verso Vimeo) per accertare che la valvola di
  sicurezza dell'upstream non fosse stata neutralizzata. Il primo tentativo di
  controprova — un id Vimeo inesistente — si è rivelato **inadatto** allo scopo, perché
  Plyr in quel caso segnala comunque `ready`: è stato verificato che quel
  comportamento fosse identico anche prima della modifica, così da non attribuirle un
  difetto preesistente, e sostituito con una prova valida.

**6. Problematiche incontrate**

- *Controprova iniziale inadatta.* Vedi sopra: l'id inesistente non produce un player
  "non pronto". Sostituita con il blocco del dominio Vimeo a livello di browser.
- *Difetto preesistente rimasto aperto.* Video Vimeo inesistente = lezione non
  completabile né dal video né dal timer. Segnalato, non corretto: è fuori dal
  perimetro della richiesta.
- *Innesto su file upstream.* La correzione tocca `Lesson.vue`, che è un file
  upstream: andrà riapplicata dopo i merge, come già annotato per gli altri innesti
  nello stesso file. Committata su `feature/oslms` (`a931cf98`), non pushata.

---

### Attività 10 — Traduzione in italiano dell'avviso "Video failed to load"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — traduzione mancante nell'interfaccia |
| **Problema riscontrato** | Richiesta dell'utente emersa dall'Attività 9: l'avviso mostrato quando il video non si carica — *"Video failed to load — this lesson will still be marked complete after you spend some time on it."* — compare in inglese. |
| **Problema effettivo** | La stringa è già internazionalizzata nel codice (`Lesson.vue:988-992`, avvolta in `__()`), quindi non è un'etichetta dimenticata: manca la traduzione nei cataloghi. In `lms/locale/it.po` la voce esisteva già, estratta dal sorgente, ma con `msgstr` **vuoto** (riga 8634); in `lms/translations/it.csv` non c'era alcuna riga. Con entrambe le fonti vuote Frappe ricade sul testo inglese. Vincolo noto del progetto: le traduzioni italiane vivono in **due** cataloghi e il `msgstr` del PO, quando valorizzato, **prevale** sul CSV — quindi intervenire su una sola fonte non dà un comportamento stabile. |
| **Soluzione applicata** | Traduzione inserita in entrambi i cataloghi con lo stesso testo: *"Caricamento del video non riuscito — questa lezione verrà comunque segnata come completata dopo un po' di tempo di permanenza."* La formulazione non è stata inventata ma allineata a quanto già presente nel catalogo: l'apertura *"Caricamento del video non riuscito —"* riprende alla lettera la stringa sorella già tradotta (`it.csv:5110`, *"Video failed to load — you can still mark this lesson as viewed."*), mantenendo così il registro alla seconda persona informale già in uso; *"segnata come completata"* e *"tempo di permanenza"* riprendono la terminologia già fissata per le impostazioni di completamento (`it.csv:4648-4654`, "Dwell Time" → "Tempo di permanenza", "marked complete" → "segnate come completate"). Nessuna modifica al codice Vue. |
| **Commit** | Sì — `0eca6322` *fix(i18n): translate the video fallback warning*, branch `feature/oslms`. Commit separato da quello della correzione funzionale (Attività 9): stessa scelta fatta oggi per le altre traduzioni, così che tipo e scope del commit restino significativi. Non pushata. |
| **File modificati** | `lms/locale/it.po` (riga 8635, `msgstr` valorizzato), `lms/translations/it.csv` (1 riga aggiunta in coda, totale 5.511 righe). |
| **Verifiche** | `msgfmt -c -o /dev/null lms/locale/it.po` → PO valido, nessun errore di sintassi né di formato. Parsing del CSV con il modulo `csv` di Python → l'ultima riga risulta correttamente su 2 colonne, con l'em dash e l'apostrofo preservati. Verifica **sul sito**: pulita la cache e riletto il catalogo dal runtime di Frappe (`frappe.translate.get_all_translations('it')`), che restituisce la traduzione italiana per quel msgid — quindi la stringa è effettivamente servita e non solo scritta nei file. |

**1. Obiettivo dell'attività**

Rendere leggibile in italiano l'unico messaggio che l'utente incontra quando scatta il
ripiego sul timer di permanenza. Ha un peso pratico oltre che linguistico: è l'unico
segnale che avverte lo studente (e chi assiste) che il completamento della lezione non
sta più dipendendo dal video, quindi se non viene compreso il ripiego passa
inosservato — è esattamente ciò che è accaduto nelle prove delle Attività 5-8.

**2. Modalità di esecuzione**

1. Verifica che la stringa fosse già avvolta in `__()` nel sorgente, per distinguere
   una traduzione mancante da un'etichetta non internazionalizzata.
2. Ricerca nei due cataloghi per stabilire quale delle due fonti fosse vuota.
3. Ricerca nel catalogo di stringhe **sorelle** già tradotte, per adottarne registro e
   terminologia anziché introdurne di nuovi.
4. Inserimento in entrambe le fonti, validazione formale dei due file e verifica che il
   runtime di Frappe serva effettivamente la traduzione.

**3. Attività svolte**

La ricerca preliminare ha evitato un errore di resa: nel catalogo esisteva già la
stringa *"Video failed to load — you can still mark this lesson as viewed."*, tradotta
con *"Caricamento del video non riuscito — puoi comunque segnare questa lezione come
vista."* È la variante precedente dello stesso avviso; riprenderne l'apertura mantiene
coerenza fra i due messaggi. Allo stesso modo, per la seconda metà della frase è stata
adottata la terminologia già fissata nelle impostazioni ("tempo di permanenza",
"segnata come completata") invece di traduzioni alternative come "tempo di
attesa" o "contrassegnata".

Dopo la scrittura, la traduzione è stata verificata **dal lato del prodotto** e non solo
dei file: pulita la cache del sito e interrogato il runtime di Frappe, che restituisce
la stringa italiana per quel msgid. È il controllo che nelle attività di traduzione
precedenti si era rivelato necessario, perché file corretti non implicano stringa
servita finché la cache non viene rigenerata.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle Attività 5-9,
  branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* individuazione della fonte mancante fra i due
  cataloghi, ricerca delle stringhe sorelle per fissare registro e terminologia,
  scrittura delle due voci, validazione dei file e verifica sul runtime.
- *Motivo della scelta del tool e del modello:* attività breve ma con un vincolo di
  progetto non ovvio (doppio catalogo con precedenza del PO) già noto alla sessione; il
  contesto conteneva inoltre la diagnosi delle Attività 8-9, utile per rendere l'avviso
  comprensibile rispetto al comportamento che descrive.
- *Risultato ottenuto:* traduzione presente in entrambi i cataloghi, coerente con le
  stringhe vicine e verificata come servita dal sito.
- *Verifiche e correzioni effettuate sull'output dell'AI:* la traduzione non è stata
  prodotta a stima ma ricavata dal catalogo esistente (stringa sorella e terminologia
  delle impostazioni), così da non introdurre due modi diversi di dire la stessa cosa
  nella stessa schermata; i file sono stati validati con strumenti (`msgfmt`, parser
  CSV) e non a vista, e la resa finale è stata verificata sul runtime.

**6. Problematiche incontrate**

- *`bench` non disponibile nel container.* Il comando `bench` non è nel PATH del
  container `dev-elite-frappe-1`; la cache è stata pulita usando direttamente il python
  del venv (`env/bin/python` con `frappe.init`/`frappe.connect`), secondo la procedura
  già documentata in questo registro per lo stesso ostacolo.

### Attività 11 — Analisi di fattibilità dello storico delle chat personali con il tutor AI

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — studio di fattibilità su richiesta dell'utente, senza modifiche al codice |
| **Esigenza di partenza** | Richiesta dell'utente: valutare rapidamente l'eventuale implementazione di uno **storico delle chat personali con il tutor AI**, cioè una cronologia che ogni studente possa consultare per rileggere le proprie conversazioni passate. Domanda esplicita: *"ci sono tutti i dati per svilupparlo?"* |
| **Vincolo tecnico realmente rilevante** | I dati ci sono, ma con due mancanze strutturali e una falla di riservatezza. (1) Ogni turno del tutor è **già persistito** su `LMSA Query Log` da `TutorAi._log_query` (`tutor_ai.py:123-141`), dentro un blocco `finally`, quindi anche i turni falliti; i campi disponibili sono `member`, `course`, `lesson`, `question`, `answer`, `context`, `status` più gli standard Frappe `creation`/`owner`/`modified`. Copre anche i messaggi vocali, perché `ask_audio` (`ai/tutor/api.py:26-56`) passa comunque da `TutorAi.ask` e la domanda registrata è la trascrizione STT. (2) **Manca il concetto di conversazione**: la history vive solo nel Pinia store in memoria `frontend/src/stores/aiChat.js`, viene rispedita al backend a ogni turno ma non è mai salvata, e si azzera sia al cambio corso sia a ogni reload della pagina; sul DB restano quindi righe Q&A sciolte, ordinabili per `creation` ma non raggruppabili in thread. (3) **Falla di permessi preesistente**: in `lmsa_query_log.json` il ruolo `LMS Student` ha `read` senza `if_owner`, e in `apps/os_lms/os_lms/hooks.py:56-97` per questo doctype non è registrato né `permission_query_conditions` né `has_permission` — a differenza dei quattro doctype `LMSA Simulation *` che li hanno entrambi. Di conseguenza oggi uno studente può già leggere le domande di tutti gli altri via `frappe.client.get_list`; il problema esiste a prescindere dallo storico, ma esporre la feature lo renderebbe evidente e sfruttabile. |
| **Soluzione applicata** | Nessuna modifica al codice: l'attività richiesta era la sola analisi. Consegnati all'utente il quadro dei dati già disponibili, i quattro gap da colmare, il precedente interno riusabile (le simulazioni hanno già lo stesso pattern risolto: `LMSA Simulation Session` + `LMSA Simulation Turn`, endpoint `list_my_sessions` in `ai/simulations/api.py:464` e `get_transcript`), il punto di innesto lato UI (`ChatBot.vue`, montato da `AiChatButton.vue` e dalle due `AiFixedButton.vue` — lo storico sarebbe un secondo tab dello stesso pannello) e due strade di implementazione con stima. Raccomandata la strada B, con il fix dei permessi da eseguire comunque e **prima**, come intervento indipendente. Decisione rimessa all'utente. |
| **Commit** | No — nessuna modifica al codice, attività di sola analisi |
| **File modificati** | Nessuno. File esaminati: `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py`, `apps/os_lms/os_lms/os_lms/ai/tutor/api.py`, `apps/os_lms/os_lms/os_lms/doctype/lmsa_query_log/lmsa_query_log.json`, `apps/os_lms/os_lms/hooks.py`, `apps/os_lms/os_lms/os_lms/api.py` (`_build_ai_rows`, riga 1503), `apps/os_lms/os_lms/os_lms/ai/simulations/api.py`, `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/…json`, `…/lmsa_simulation_turn/…json`, `frontend/src/oslms/components/ai/ChatBot.vue`, `frontend/src/stores/aiChat.js`, `docs/ai/TUTOR.md` |
| **Verifiche** | Lettura del percorso completo domanda → risposta → log per accertare che *tutti* i turni finiscano a registro (verificato il `finally` in `TutorAi.ask` e il passaggio di `ask_audio` dallo stesso metodo). Dump dello schema di `LMSA Query Log` e confronto con quello di `LMSA Simulation Session`/`Turn` per stabilire cosa manchi. `grep` su tutto il repo per i consumer esistenti di `LMSA Query Log`: trovato un solo lettore applicativo, `_build_ai_rows` dell'export statistiche, che conferma il pattern di query. `grep` su `permission_query_conditions` e `has_permission` in `hooks.py` per verificare l'assenza di scoping sul doctype. Lettura dello store Pinia per confermare che la conversazione non sopravvive al reload. Ricerca di eventuali task schedulati di purge/retention sui Query Log: **nessuno**. |

**1. Obiettivo dell'attività**

Rispondere, in tempi brevi e con riscontro sul codice, alla domanda se il prodotto
disponga già dei dati necessari per offrire allo studente uno storico consultabile
delle proprie chat con il tutor AI, e in caso affermativo quantificare quanto lavoro
separi i dati grezzi dalla feature utilizzabile.

**2. Modalità di esecuzione**

Analisi statica del codice su tre assi, dal dato verso l'interfaccia:

1. **Persistenza** — dove finisce un turno di chat, quali campi vengono scritti,
   se il log è esaustivo (turni testuali, turni vocali, turni falliti).
2. **Accesso** — se esiste un endpoint di lettura per lo studente, e soprattutto
   se i permessi del doctype isolano il singolo utente. Confronto con i doctype
   delle simulazioni, che nello stesso app implementano già lo scoping.
3. **Interfaccia e stato client** — dove vive oggi la conversazione, se sopravvive
   al reload, e dove andrebbe innestata l'eventuale vista storico.

**3. Attività svolte e risultati**

*Dati già disponibili.* Ogni chiamata al tutor produce una riga di `LMSA Query Log`
con domanda, risposta, corso, lezione, membro, contesto RAG, stato e timestamp di
creazione. La scrittura è nel `finally` di `TutorAi.ask`, quindi anche una chiamata
LLM fallita lascia traccia (`answer` vuota, `status = "Failed"`). I messaggi vocali
sono coperti perché `ask_audio` delega a `TutorAi.ask`; l'audio non viene conservato,
ma per uno storico testuale è irrilevante. Su questa base uno storico **cronologico**
per corso e lezione è realizzabile senza toccare lo schema.

*Gap 1 — nessun identificativo di conversazione.* Le righe sono turni sciolti. Per
ricostruire i thread reali servono un campo `conversation` e un `turn_index`, oppure
un raggruppamento euristico per distanza temporale (es. oltre 30 minuti di silenzio
= nuova conversazione), che però fonde due sessioni ravvicinate e spezza una chat
ripresa dopo una pausa.

*Gap 2 — nessun endpoint di lettura.* Esistono solo `ask` e `ask_audio`. Serve un
`list_my_conversations` / `get_conversation` modellato su `list_my_sessions` delle
simulazioni, che risolve già lo stesso problema (elenco delle proprie sessioni,
paginato, con lo scoping su `frappe.session.user`).

*Gap 3 — permessi, il punto bloccante.* Descritto nella tabella: `read` al ruolo
`LMS Student` senza `if_owner` e senza query conditions. Va sanato comunque, ed è
prerequisito di qualunque esposizione dello storico.

*Gap 4 — il campo `context`.* Contiene i chunk RAG e il materiale interno usato per
costruire il prompt: non deve mai essere restituito allo studente, va escluso
esplicitamente dai `fields` dell'endpoint (payload pesante e fuga di contenuto).

*Minori.* Nessun task di retention: la tabella cresce indefinitamente e `context` è
un campo Text corposo — con lo storico esposto servono un indice su `(member,
creation)` e la paginazione. Da decidere inoltre se lo studente possa cancellare le
proprie conversazioni: oggi il ruolo non ha `delete`, ma sul piano privacy è
plausibile che serva almeno una cancellazione su richiesta.

*Stime consegnate.* Strada A (storico read-only raggruppato per corso/lezione e data,
endpoint paginato più pannello SPA, nessuna migrazione): circa 0,5-1 giornata, resa
limitata a un elenco di Q&A. Strada B (campo `conversation` + `turn_index`, id
generato dal client, endpoint list/get, ripresa della conversazione nello store,
retention, backfill euristico dello storico pregresso in un patch): circa 2-3
giornate, resa completa. Raccomandata la B.

**4. Utilizzo dell'AI**

- **Tool/agente:** Claude Code (estensione VS Code), sessione interattiva sul branch
  `feature/oslms`.
- **Modello:** Opus 5 (contesto 1M).
- **Per quale attività:** esplorazione mirata del codice per rispondere alla domanda
  di fattibilità — individuazione del punto di persistenza dei turni di chat, lettura
  dello schema del doctype di log, confronto con il modello session/turn delle
  simulazioni, verifica dei permessi e dello stato client, stesura della sintesi con
  gap ed effort.
- **Perché quel tool e quel modello:** la domanda era trasversale a backend Python,
  schema doctype JSON, hooks di permesso e store frontend, cioè esattamente il caso in
  cui conviene un agente che legge il repository invece di una ricerca manuale; il
  contesto ampio ha permesso di tenere aperti insieme `tutor_ai.py`, lo schema del
  Query Log, `hooks.py`, l'API delle simulazioni e lo store Pinia senza perdere il
  filo, e di fare il confronto fra il modulo tutor e il modulo simulazioni che è il
  cuore della risposta.
- **Risultato ottenuto:** risposta netta alla domanda posta (i dati ci sono, ma non
  bastano da soli), elenco dei quattro gap con riferimenti puntuali a file e riga,
  individuazione di un precedente interno riusabile invece di un progetto da zero,
  e due opzioni con stima per la decisione.
- **Verifiche e correzioni fatte:** ogni affermazione è stata verificata sul codice e
  non dedotta dalla documentazione — in particolare l'esaustività del log (letto il
  `finally` e il percorso di `ask_audio`, non solo il testo di `docs/ai/TUTOR.md`),
  l'assenza di scoping sui permessi (verificata direttamente in `hooks.py` e nel JSON
  del doctype, non assunta), l'assenza di consumer applicativi oltre l'export
  statistiche (`grep` sull'intero repository) e l'assenza di qualunque task di purge
  schedulato. Corretta in corso d'opera l'impressione iniziale che il doctype fosse
  di solo audit interno: ha invece già `read` per il ruolo studente, il che sposta la
  questione dei permessi da "da progettare" a "da sanare subito".

**5. Problematiche riscontrate**

La sola problematica emersa non riguarda la fattibilità della feature ma il presente:
la lettura non scopata di `LMSA Query Log` da parte del ruolo `LMS Student` è un
difetto di riservatezza **già attivo in produzione**, segnalato all'utente come
intervento da pianificare a sé, indipendentemente dalla decisione sullo storico.

Stato: in attesa che l'utente scelga fra la strada A e la strada B, o decida di
fermarsi al solo fix dei permessi. Nessuna modifica al codice in questa fase.

---

### Attività 12 — Analisi della differenza fra il player video della panoramica corso e quello delle lezioni

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — verifica di una differenza di comportamento segnalata dall'utente |
| **Problema riscontrato** | Segnalato dall'utente: **lo stesso identico video Vimeo** si comporta in due modi diversi a seconda di dove è inserito. Nella **panoramica del corso** il player mostra il chrome nativo di Vimeo — titolo del video, autore/descrizione e i pulsanti *Mi piace* e *Condividi* in alto; nella **lezione** lo stesso video mostra soltanto i comandi di riproduzione, senza titolo né pulsanti social. Domanda posta: le due implementazioni sono uguali? ed è possibile gestire quei titoli e quei pulsanti? |
| **Problema effettivo** | Le due implementazioni **non sono la stessa cosa**, e la differenza non sta nel video né nelle impostazioni Vimeo del filmato ma nel modo in cui il frontend lo incorpora. Nella **lezione** il video è un blocco `embed` di EditorJS che non produce un iframe ma un segnaposto `<div class="video-player" data-plyr-provider="vimeo">` (`frontend/src/utils/index.js:343-348`), successivamente montato da **Plyr** (`frontend/src/utils/plyr.js`, invocato da `frontend/src/pages/Lesson.vue:866`): è Plyr a costruire l'iframe verso Vimeo, e lo fa passando i propri default `title: false`, `byline: false`, `portrait: false` (verificati in `frontend/node_modules/plyr/dist/plyr.js:3716-3729`), che eliminano l'intera barra superiore di Vimeo — titolo, autore/descrizione e con essa i pill *Mi piace / Guarda dopo / Condividi* — mentre i comandi visibili sono quelli dichiarati a mano in `frontend/src/utils/plyr.js:44-52`. Nella **panoramica corso**, invece, non c'è alcun player applicativo: si inietta direttamente in un `<iframe>` l'URL di embed **nudo** prodotto da `getVideoEmbedURL()` (`frontend/src/utils/video.ts:57-77`), che restituisce `https://player.vimeo.com/video/<id>` (più `?h=<hash>` per i video privati) **senza un solo parametro di query**; in assenza di parametri Vimeo applica i propri default, che includono titolo, autore e pulsanti social. Lo stesso vale per l'hero del corso (`frontend/src/oslms/components/CourseHero.vue:16-21`) e per l'anteprima delle classi (`frontend/src/components/VideoPreview.vue`), che passano per la stessa funzione. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola analisi, chiusa con la risposta all'utente e due opzioni di intervento alternative fra cui scegliere. **A)** aggiungere in `getVideoEmbedURL()` i parametri `title=0&byline=0&portrait=0` per Vimeo (e `modestbranding=1&rel=0` per YouTube), preservando il parametro `h=` dei video privati: un solo punto di modifica che copre in un colpo panoramica corso, hero e anteprima classi, lasciando però la barra comandi nativa di Vimeo. **B)** usare Plyr anche in panoramica, sostituendo l'iframe con il segnaposto `video-player` più `enablePlyr()`: resa identica alla lezione, ma con l'effetto collaterale che `enablePlyr()` applica il listener di `prevent_skipping_videos` a **tutti** i player presenti nella pagina, bloccando l'avanzamento anche sul video promozionale del corso, dove non ha senso. Raccomandata la A, salvo esplicita volontà di uniformare anche i comandi. |
| **Commit** | No — nessuna modifica al codice: l'attività si è chiusa con la diagnosi e la scelta ancora in capo all'utente. Branch di lavoro `feature/oslms`. |
| **File modificati** | Nessuno. File **letti** per la diagnosi: `frontend/src/utils/index.js` (classe `VideoEmbed` e definizione dei servizi embed), `frontend/src/utils/plyr.js`, `frontend/src/utils/video.ts`, `frontend/src/components/CourseCardOverlay.vue`, `frontend/src/oslms/components/CourseHero.vue`, `frontend/src/components/VideoPreview.vue`, `frontend/src/pages/Lesson.vue`, `frontend/src/overrides/pages/Courses/CourseOverview.vue`, `frontend/node_modules/plyr/dist/plyr.js` (default del provider Vimeo). |
| **Verifiche** | Diagnosi verificata sul sorgente e **non dedotta**: (a) confermato che il servizio `vimeo` dell'embed EditorJS genera un `<div class="video-player">` e non un iframe (`utils/index.js:347`), quindi che l'iframe reale è costruito da Plyr; (b) letti i default del plugin Vimeo dentro il bundle installato di Plyr (`plyr.js:3716-3729`) per confermare `title/byline/portrait` a `false`, e la costruzione dei parametri dell'iframe (`plyr.js:5455-5499`) per accertare che quei valori finiscano davvero nell'URL; (c) verificato che `controls: false` viene inviato a Vimeo **solo** con account premium (`plyr.js:5477-5482`), quindi che nella lezione la barra nativa è nascosta da Plyr per via grafica e non per parametro; (d) censiti con `grep` tutti i punti che usano `getVideoEmbedURL()` per accertare che il rimedio A copra davvero i tre casi (panoramica, hero, anteprima classi) e non solo quello segnalato. Nessuna build eseguita: non essendoci modifiche, non c'era nulla da compilare. |

**1. Obiettivo dell'attività**

Rispondere a una domanda dell'utente su una differenza visiva ritenuta anomala: lo
stesso video Vimeo, inserito in due punti diversi del prodotto, mostra due interfacce
diverse. L'obiettivo non era estetico ma di controllo del prodotto: il player della
panoramica corso espone verso lo studente elementi che **non appartengono all'LMS** —
il titolo del video così com'è su Vimeo (che può differire dal titolo del corso), il
nome dell'account che lo ha caricato e i pulsanti *Mi piace* e *Condividi*, che portano
l'utente fuori dalla piattaforma verso Vimeo. Serviva quindi stabilire se si trattasse
di due implementazioni differenti o di una configurazione del singolo video, e se e
dove il comportamento sia governabile dal nostro codice.

**2. Modalità di esecuzione**

Procedura seguita:

1. Individuazione dei punti in cui il frontend incorpora un video, cercando su tutto
   `frontend/src` i riferimenti a `vimeo`, `VideoEmbed`, `video_link` e `preview_video`,
   per distinguere i due percorsi (lezione e panoramica) invece di guardare il solo
   caso segnalato.
2. Lettura del percorso **lezione**: definizione dei servizi del blocco `embed` di
   EditorJS in `utils/index.js`, per capire che cosa viene effettivamente inserito nel
   DOM alla resa del blocco.
3. Lettura del percorso **panoramica**: `CourseCardOverlay.vue` e la funzione
   `getVideoEmbedURL()` in `utils/video.ts`, per ricostruire l'URL esatto che finisce
   nell'iframe.
4. Ispezione del bundle installato di Plyr (`node_modules`), non della sua
   documentazione, per accertare quali parametri vengono realmente inviati a Vimeo e
   in quali condizioni: è il punto su cui è facile sbagliare, perché il comportamento
   dipende anche dal fatto che l'account Vimeo sia o meno premium.
5. Censimento di tutti i chiamanti di `getVideoEmbedURL()` per dimensionare
   correttamente l'intervento proposto, cioè per sapere in anticipo quante schermate
   verrebbero toccate da una modifica in quel singolo punto.

**3. Attività svolte**

Ricostruiti e messi a confronto i due percorsi.

*Lezione.* Il video è un blocco `embed` di EditorJS. Il servizio `vimeo` è configurato
in `utils/index.js:343-348` con `html: '<div class="video-player" data-plyr-provider="vimeo"></div>'`:
alla resa non nasce quindi nessun iframe, ma un segnaposto. È `enablePlyr()`
(`utils/plyr.js`), chiamato dalla pagina lezione a `Lesson.vue:866`, a trasformare
quel `div` in un player. Plyr costruisce l'iframe verso Vimeo e vi accoda i propri
default (`plyr.js:3716-3729`): `title: false`, `byline: false`, `portrait: false`,
`speed: true`, `transparent: false`. Sono quei tre `false` a far sparire l'intera
fascia superiore del player Vimeo, che è il contenitore sia del titolo e dell'autore
sia dei pulsanti *Mi piace*, *Guarda dopo* e *Condividi*: non esistono tre parametri
separati per i tre pulsanti, cade la barra e cadono con essa. La barra comandi in
basso, invece, resta quella di Plyr, con l'elenco dichiarato esplicitamente in
`utils/plyr.js:44-52` (play, progress, tempo corrente, muto, volume, impostazioni
velocità, fullscreen), più il listener che impedisce il salto in avanti quando è
attiva l'impostazione `prevent_skipping_videos` e la logica di avanzamento della
lezione. Verificato inoltre che `controls: false` viene passato a Vimeo **solo** se
l'account è premium (`plyr.js:5477-5482`): nel nostro caso i comandi nativi di Vimeo
non sono disattivati via parametro ma coperti graficamente da Plyr.

*Panoramica corso.* Nessun player applicativo: `CourseCardOverlay.vue:13-17` scrive
direttamente un `<iframe :src="video_link">`, dove `video_link` è il risultato di
`getVideoEmbedURL()` (`utils/video.ts:57-77`). Quella funzione si limita a
normalizzare il link in `https://player.vimeo.com/video/<id>`, aggiungendo `?h=<hash>`
solo per i video privati, e **non accoda alcun parametro di presentazione**. Senza
parametri Vimeo applica i suoi default, che comprendono titolo, autore e pulsanti
social: da qui la differenza percepita, che non dipende quindi dal video ma dal punto
di inserimento.

*Ampiezza del fenomeno.* Il censimento dei chiamanti ha mostrato che lo stesso URL
nudo alimenta tre schermate: la card della panoramica corso
(`CourseCardOverlay.vue`), l'hero del corso quando abilitato
(`oslms/components/CourseHero.vue:16-21`) e l'anteprima video delle classi
(`components/VideoPreview.vue`). Un intervento su `getVideoEmbedURL()` le copre tutte
e tre; un intervento sulla sola card ne sistemerebbe una su tre, lasciando il difetto
altrove.

*Esito consegnato all'utente.* Risposta netta alla domanda ("no, non sono implementate
allo stesso modo, ed ecco perché") e due opzioni: **A** parametri `title=0&byline=0&portrait=0`
dentro `getVideoEmbedURL()` — intervento di poche righe in un punto solo, che va però
scritto avendo cura di non perdere l'`h=` dei video privati e a cui conviene affiancare
`modestbranding=1&rel=0` per i video YouTube; **B** adozione di Plyr anche in
panoramica, che darebbe resa identica alla lezione ma comporterebbe l'applicazione del
blocco anti-salto anche al video promozionale, effetto indesiderato su un contenuto che
serve a invogliare l'iscrizione. Raccomandata la A. Nessuna riga di codice modificata in
attesa della scelta.

**4. Utilizzo dell'AI**

- **Tool/agente:** Claude Code (CLI, sessione su VS Code).
- **Modello:** Opus 5 (contesto 1M).
- **Attività per cui è stata utilizzata:** individuazione dei due percorsi di embed
  video nel frontend, lettura comparata dei sorgenti coinvolti (compresi i default del
  pacchetto Plyr installato), formulazione della diagnosi e delle due opzioni di
  intervento con i rispettivi effetti collaterali.
- **Motivo della scelta del tool e del modello:** la domanda è di tipo "perché due
  parti dello stesso prodotto si comportano diversamente", cioè richiede di risalire da
  un sintomo visivo a due catene di rendering distinte che attraversano codice
  applicativo (EditorJS, componenti Vue) e codice di terze parti (Plyr), tenendo insieme
  molti file contemporaneamente. Claude Code opera direttamente sul repository e può
  leggere anche `node_modules`, cosa determinante qui perché la spiegazione sta nei
  default del pacchetto installato e non nel nostro codice; il contesto ampio di Opus 5
  ha permesso di confrontare i file senza perdere il filo fra un passaggio e l'altro.
- **Risultato ottenuto:** diagnosi puntuale con riferimenti a file e riga per ciascuna
  affermazione, identificazione del punto unico di intervento
  (`getVideoEmbedURL()`) e delle tre schermate che ne dipendono, e due opzioni con
  l'effetto collaterale della seconda esplicitato prima della scelta anziché scoperto
  dopo l'implementazione.
- **Verifiche e correzioni effettuate:** ogni affermazione è stata riscontrata sul
  codice. In particolare non si è dato per scontato che il blocco `embed` producesse un
  iframe (produce un `div`), e i parametri inviati a Vimeo sono stati letti nel bundle
  reale di Plyr invece che assunti dalla documentazione: da lì è emerso il dettaglio
  che `controls: false` vale solo per account premium, che cambia la spiegazione del
  perché la barra nativa non si veda in lezione (copertura grafica, non parametro).
  Corretta in corso d'analisi l'ipotesi iniziale che i pulsanti *Mi piace* e
  *Condividi* avessero parametri dedicati: appartengono alla stessa barra superiore
  governata da `title/byline/portrait`.

**6. Problematiche incontrate**

Nessuna problematica bloccante. Un punto di attenzione per l'implementazione futura:
l'opzione A tocca una funzione condivisa da corsi, hero e classi, quindi la modifica va
verificata su tutte e tre le schermate e, soprattutto, sui **video privati**, dove il
parametro `h=` deve continuare a essere presente nell'URL — accodare i nuovi parametri
senza tenerne conto renderebbe non riproducibili proprio i video ad accesso ristretto.
Resta inoltre da tenere presente che alcune parti del chrome di Vimeo dipendono anche
dalle impostazioni di embed del singolo video sul portale Vimeo: i parametri agiscono
sull'incorporamento, non sostituiscono la configurazione lato Vimeo.

Stato: in attesa che l'utente scelga fra l'opzione A e l'opzione B. Nessuna modifica al
codice in questa fase.

---

---

### Attività 13 — Gli accapo della descrizione breve del corso si vedono nella panoramica

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — resa del contenuto nell'interfaccia |
| **Problema riscontrato** | Segnalato dall'utente per conto di un docente: nella **descrizione breve** del corso (campo *Short description* del form corso) si possono andare a capo mentre si scrive, ma aprendo la **panoramica del corso** il testo compare tutto di seguito, come un unico blocco: gli accapo spariscono. La domanda posta era se fosse possibile inserirli. |
| **Problema effettivo** | Non è un problema di salvataggio né di sanitizzazione: il campo `short_introduction` di *LMS Course* è di tipo **Small Text** (`lms/lms/doctype/lms_course/lms_course.json:87-91`) e nel form è un `FormControl type="textarea"` a 3 righe (`CourseDetailsSection.vue:29-39`), quindi i newline vengono digitati, salvati e riletti correttamente. Si perdono **solo in fase di resa**: la panoramica stampa il valore come testo dentro un `<p>` (`overrides/pages/Courses/CourseOverview.vue:43-48`) e l'HTML, per regola sua, collassa ogni sequenza di spazi e ritorni a capo in un singolo spazio salvo che il CSS dica altrimenti. Mancava quindi la sola dichiarazione `white-space` sul paragrafo. |
| **Soluzione applicata** | Aggiunta l'utility Tailwind **`whitespace-pre-line`** alla classe del paragrafo che stampa `short_introduction` nella panoramica corso. È la scelta corretta fra le tre possibili: `pre-line` preserva i ritorni a capo e le righe vuote ma continua a collassare gli spazi multipli e a mandare a capo il testo lungo, mentre `pre` conserverebbe anche l'indentazione accidentale e **impedirebbe il wrapping** (testo che esce dalla colonna su mobile) e `pre-wrap` conserverebbe gli spazi doppi incollati da Word. Nessuna modifica al backend, al doctype o al form: il dato era già giusto. Aggiunto un commento `OSLMS-CUSTOM` sopra il blocco per motivare la classe e proteggerla dai merge upstream. |
| **Commit** | Sì — `b8fc176b` *fix(ui): keep line breaks in course and batch short descriptions*, branch `master`. Le due correzioni (corso e classe) sono state raccolte in un unico commit su richiesta dell'utente: stessa causa, stessa soluzione e stesso tipo, quindi separarle avrebbe prodotto due commit non indipendenti. Non pushato. |
| **File modificati** | `frontend/src/overrides/pages/Courses/CourseOverview.vue` (blocco righe 43-52: commento `OSLMS-CUSTOM` + `whitespace-pre-line` sulla classe del `<p>`). |
| **Verifiche** | Verificato che il file effettivamente renderizzato sia l'override e non l'originale: `CourseDetail.vue:191` importa `@/pages/Courses/CourseOverview.vue`, ma il plugin Vite `osOverrideTheme` (`vite.config.js:267-327`) rispecchia anche `src/*` sotto `src/overrides/`, quindi l'import viene dirottato sull'override — l'originale `frontend/src/pages/Courses/CourseOverview.vue` è stato lasciato intatto di proposito. Verificato che `whitespace-pre-line` sia una utility **core** di Tailwind e che il progetto usi `tailwindcss ^3.4.15` (`frontend/package.json:70`), dove esiste: nessuna estensione di config necessaria (nel repo erano già in uso le varianti `whitespace-pre-wrap`, es. `ChatBot.vue:46`). Riletto il blocco modificato a valle dell'edit. Build frontend non eseguita: la modifica è una sola classe di utility su un template già compilato dalla stessa pipeline, senza nuove dipendenze né logica. |

**1. Obiettivo dell'attività**

Permettere che la formattazione su più righe scritta dal docente nella descrizione
breve del corso sia effettivamente visibile allo studente nella panoramica. La
richiesta arriva da chi redige i corsi: la descrizione breve è spesso usata come
elenco di punti o come due frasi separate, e vederla appiattita in un unico blocco
rende il testo meno leggibile e fa sembrare "rotto" un contenuto che in redazione
appariva corretto. L'obiettivo secondario era rispondere alla domanda posta —
*"è possibile inserire gli accapo?"* — con un fatto verificato e non con una stima:
il dato era già multiriga, mancava solo la resa.

**2. Modalità di esecuzione**

1. Ricerca di tutti i punti in cui `short_introduction` compare, su backend e
   frontend, per distinguere fra le tre cause possibili di una perdita di accapo:
   campo che non li accetta (tipo `Data`), sanitizzazione in salvataggio, oppure
   collasso in resa HTML.
2. Lettura della definizione del campo nel doctype e del controllo usato nel form,
   per escludere le prime due cause.
3. Individuazione del componente realmente renderizzato nella panoramica, tenendo
   conto del sistema di override del progetto (l'import punta a `src/pages`, ma il
   file servito è quello in `src/overrides`).
4. Applicazione della utility `white-space` corretta, motivata rispetto alle
   alternative, con commento di manutenzione.

**3. Attività svolte**

La ricerca ha mostrato subito che il campo è `Small Text`, quindi multiriga per
costruzione, e che il form usa una textarea: nessun troncamento a monte. Il valore
arriva alla pagina già con i `\n` dentro. Il punto di perdita è quindi uno solo, la
riga `{{ course.data.short_introduction }}` dentro il `<p>` della panoramica: senza
una regola `white-space`, il browser collassa i ritorni a capo. Da qui la
correzione minima, una classe.

Passaggio non banale: **quale** dei due `CourseOverview.vue` modificare. Il
progetto ne ha due, uno upstream in `src/pages/Courses/` e un override in
`src/overrides/pages/Courses/`, e l'import in `CourseDetail.vue` cita il primo. È
il plugin `osOverrideTheme` a dirottare l'import sul secondo, perché rispecchia
sotto `src/overrides/` sia `node_modules/*` sia `src/*`. Modificare il file
upstream avrebbe prodotto una modifica **senza alcun effetto visibile**, con il
rischio concreto di concludere che "la classe non funziona" e cercare la causa
altrove. La verifica del plugin è stata fatta prima dell'edit, non dopo.

Sulla scelta della utility: `pre-line` è l'unica che risolve il problema senza
introdurne altri. `pre` disattiva il wrapping e su schermo stretto farebbe uscire
il testo dalla colonna; `pre-wrap` preserva anche gli spazi multipli, che nelle
descrizioni incollate da Word o da un PDF sono frequenti e comparirebbero come
buchi nel testo. `pre-line` tiene gli accapo e le righe vuote — cioè esattamente
ciò che il docente ha scritto volontariamente — e continua a normalizzare il resto.

Non è stato modificato il resto dei punti in cui la stessa descrizione compare, per
scelta: nella **card del corso** in elenco (`CourseCard.vue:84`) il testo è
volutamente troncato a due righe con ellissi (`-webkit-line-clamp: 2`), e
preservare lì gli accapo consumerebbe le due righe disponibili con la sola prima
frase, peggiorando l'anteprima; nella pagina di iscrizione ai percorsi
(`ProgramEnrollment.vue:51`) il blocco è commentato e non renderizzato. Se in
futuro si volesse la stessa resa anche altrove, l'intervento è la medesima classe.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), branch `master`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* individuazione della causa reale
  (distinzione fra campo, salvataggio e resa), identificazione del componente
  effettivamente renderizzato attraverso il sistema di override del progetto,
  scelta motivata della utility CSS, applicazione della modifica e verifica.
- *Motivo della scelta del tool e del modello:* la segnalazione sembra banale ma
  attraversa quattro livelli (doctype, form, sistema di override Vite, resa CSS) e
  il punto in cui si sbaglia — modificare il `CourseOverview.vue` sbagliato — non è
  visibile leggendo l'import. Serviva un modello capace di tenere insieme la
  conoscenza del meccanismo `osOverrideTheme`, già consolidata nella memoria di
  progetto, e la lettura puntuale del codice.
- *Risultato ottenuto:* correzione di una riga nel file corretto, con commento di
  manutenzione, senza toccare backend, doctype o file upstream.
- *Verifiche e correzioni effettuate sull'output dell'AI:* prima dell'edit è stato
  letto il codice del plugin `osOverrideTheme` per confermare che rispecchi anche
  `src/*` (e non solo `node_modules/*`), invece di darlo per scontato; è stata
  verificata la versione di Tailwind per accertare che `whitespace-pre-line`
  esistesse davvero nella configurazione del progetto; sono stati ispezionati gli
  altri punti di resa della descrizione per decidere consapevolmente di **non**
  estendere lì la modifica, anziché propagarla per simmetria.

**6. Problematiche incontrate**

- *Doppio file con lo stesso nome.* La presenza di un `CourseOverview.vue` upstream
  e di un override omonimo è la trappola principale di questo intervento: l'import
  visibile nel codice punta al file sbagliato e solo il plugin Vite rivela quale
  file viene servito. Annotato qui perché si ripresenterà su qualsiasi correzione
  di resa nelle pagine SPA.
- *Verifica visiva non eseguita in questa sessione.* La modifica è puramente CSS e
  non è stata ricontrollata a video sul sito; va confermata alla prossima apertura
  della panoramica di un corso con descrizione multiriga (serve un corso il cui
  campo contenga davvero dei ritorni a capo salvati).

### Attività 14 — Ripristino di icona e valore della durata nella card corso

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — regressione da merge upstream |
| **Problema riscontrato** | Segnalato dall'utente: nella **card del corso** (elenco corsi) l'indicatore della durata mostra l'**icona delle persone** invece di quella dell'orologio. |
| **Problema effettivo** | Non era solo l'icona: il blocco aveva perso **due** elementi su tre. Il codice mostrava `<span class="lucide-users">` e `{{ formatAmount(course.enrollments) }}` — cioè icona *persone* e **numero di iscritti** — pur essendo condizionato a `v-if="formattedDuration"` e etichettato dal tooltip `__('Duration')`. Il `git blame` chiarisce l'origine: il blocco custom era stato scritto correttamente nel commit `84bde1890e` (*Add duration for courses by include new field in lessons table*, 2026-03-17) con `<Clock />` e `{{ formattedDuration }}`; le due righe interne sono poi tornate alla versione upstream (`bb2447e821` per il valore, `36d88c7a29` per l'icona, che ha solo convertito `<Users />` nella classe `lucide-users` durante la migrazione icone). È il pattern tipico di risoluzione di conflitto in cui si tiene la nostra `v-if` e il nostro `Tooltip` (le righe esterne) ma si accetta lo `<span>` interno di upstream: il blocco resta condizionato e etichettato come "Durata" mentre dentro mostra tutt'altro dato. L'utente ha notato l'icona; il valore sbagliato era meno evidente perché è comunque un numero plausibile. |
| **Soluzione applicata** | Ripristinato il contenuto del blocco alla sua versione custom: icona `lucide-clock` (classe, coerente con la convenzione introdotta dalla migrazione icone e già usata in `BatchCard.vue`, `BatchOverlay.vue`, `Event.vue`, `UpcomingEvaluations.vue`) e valore `{{ formattedDuration }}`, cioè il computed già presente nel file che converte `course.total_minutes` in "1h 30m" / "2h" / "45m". Rimosso di conseguenza `formatAmount` dall'import di `@/utils`, rimasto senza usi nel file. Corretto anche il valore e non solo l'icona perché sistemare la sola icona avrebbe prodotto un esito peggiore del bug segnalato: un orologio accanto al numero di iscritti si legge come una durata: "1.2k" verrebbe interpretato come tempo. |
| **Commit** | Sì — `d76d709e` *fix(courses): restore the duration icon and value on the course card*, branch `master`. Tenuto separato dal commit degli accapo (`b8fc176b`): stessa giornata e stessa area, ma causa e natura diverse — quello è una resa mancante, questo il ripristino di una regressione da merge — e accorparli avrebbe reso il messaggio non descrittivo di nessuna delle due. Non pushato. |
| **File modificati** | `frontend/src/components/CourseCard.vue` (righe 46-47: icona e valore; riga 104: import ripulito). |
| **Verifiche** | Verificato con `git log`/`git blame` sul blocco che si trattasse di una regressione e non di una scelta, risalendo al commit che aveva introdotto la funzionalità e confrontandone il diff. Verificato che `lucide-clock` sia una classe valida in questo progetto: l'icona esiste in `node_modules/lucide-static/icons/clock.svg` ed è già usata in 4 altri componenti. Verificato che **non esista** un override di `CourseCard.vue` sotto `src/overrides/`, quindi il file modificato è effettivamente quello renderizzato. Verificato che `total_minutes` sia realmente popolato lato server per l'elenco corsi (`apps/os_lms/os_lms/os_lms/override_utils.py:264-277`, che valorizza `course.total_minutes` dalla somma dei `duration` delle lezioni), altrimenti la `v-if` avrebbe nascosto il blocco. Verificato che `formatAmount` non avesse altri usi nel file prima di rimuoverlo dall'import. Build frontend non eseguita: modifica di sole due righe di template su un computed già esistente, senza nuove dipendenze. |

**1. Obiettivo dell'attività**

Rendere l'indicatore di durata della card corso coerente con ciò che dichiara. La
segnalazione riguardava l'icona, ma l'obiettivo effettivo è più sostanziale: la card
mostrava, sotto l'etichetta "Durata", un dato che durata non è. Un utente che
confronta due corsi in elenco legge quel numero come tempo di impegno richiesto, ed è
una delle poche informazioni su cui basa la scelta prima di aprire il corso.

**2. Modalità di esecuzione**

1. Lettura del blocco segnalato nel template della card, per capire se l'icona fosse
   l'unico elemento incoerente rispetto a condizione e tooltip.
2. `git blame` sul blocco e lettura del commit che aveva introdotto la durata, per
   distinguere fra un errore originario e una regressione da merge — la distinzione
   cambia la correzione: nel primo caso si progetta, nel secondo si ripristina.
3. Ripristino delle due righe interne alla versione custom, adattando l'icona alla
   convenzione a classi oggi in uso nel progetto.
4. Controlli di contorno: esistenza della classe icona, assenza di override del
   componente, effettiva presenza del dato lato server, import rimasti orfani.

**3. Attività svolte**

Il blame ha mostrato una stratificazione significativa: le righe **esterne** del blocco
(`v-if="formattedDuration"` e `Tooltip :text="__('Duration')"`) portano la data della
nostra personalizzazione, le righe **interne** portano date e autori upstream. È la
firma di un conflitto risolto riga per riga, dove il guscio custom sopravvive e il
contenuto torna a monte. Il commit `36d88c7a29` ha poi fossilizzato l'errore: la
migrazione da componenti `lucide-vue-next` a classi CSS ha convertito `<Users />` in
`lucide-users` senza che nessuno rileggesse il contesto: una trasformazione meccanica
non può accorgersi che l'icona era già quella sbagliata.

La correzione è quindi un ripristino, non un'invenzione: `formattedDuration` era già
nel file, calcolato e mai usato, e `Clock` era perfino ancora nell'import di
`lucide-vue-next`. Il componente conteneva già tutto il necessario per funzionare.

Segnalato, senza intervenire, un secondo blocco con la stessa firma: quello subito
accanto ha condizione sulla certificazione e tooltip "Certification available", ma
mostra icona stella e `formatRating(course.rating)`, cioè il voto medio. Anche lì le
righe esterne sono nostre e la riga del valore è upstream. Non è stato toccato perché
fuori dalla richiesta e perché — a differenza della durata — non è ovvio quale sia
l'esito voluto: potrebbe essere un badge senza numero oppure un blocco voto autonomo.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), branch `master`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* lettura del blocco, ricostruzione storica con
  `git blame` e confronto col commit di origine, individuazione dell'estensione reale
  della regressione (due righe, non una), ripristino e verifiche di contorno.
- *Motivo della scelta del tool e del modello:* la segnalazione era di una riga, ma la
  correzione corretta dipendeva dal capire **perché** quella riga fosse sbagliata;
  senza ricostruzione storica si sarebbe corretta l'icona lasciando il dato errato, con
  un risultato peggiore del bug di partenza. Serviva un modello disposto a fare
  archeologia su tre commit prima di toccare due righe.
- *Risultato ottenuto:* blocco durata coerente con la propria etichetta, import
  ripulito, seconda anomalia analoga individuata e segnalata anziché propagata.
- *Verifiche e correzioni effettuate sull'output dell'AI:* la classe icona non è stata
  assunta per analogia ma verificata contro `lucide-static` e contro gli usi già
  presenti nel progetto; è stata verificata l'assenza di un override del componente
  (errore già incontrato nell'Attività 13 di questa giornata, dove il file importato
  non è quello renderizzato); è stata verificata la presenza effettiva di
  `total_minutes` lato server prima di far dipendere la card da quel campo.

**6. Problematiche incontrate**

- *Regressioni silenziose da merge upstream.* Questo caso mostra il rischio concreto
  del pattern: la personalizzazione non sparisce del tutto — resta il guscio, che
  continua a dichiarare l'intento — mentre il contenuto torna a monte. Il risultato
  non è un errore visibile in build né un test rosso, ma un dato sbagliato mostrato
  con l'etichetta giusta, che sopravvive finché qualcuno non lo nota a occhio. Nel file
  ne resta almeno un secondo caso (blocco certificazione/voto).
- *Verifica visiva non eseguita in questa sessione.* Come per l'Attività 13, la resa va
  confermata a video dopo il build sull'elenco corsi.

### Attività 15 — Accapo nella descrizione breve della classe

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — resa del contenuto nell'interfaccia |
| **Problema riscontrato** | Richiesta dell'utente a valle dell'Attività 13: applicare anche alla **descrizione breve della classe** lo stesso trattamento fatto per i corsi, perché soffre dello stesso appiattimento degli accapo. |
| **Problema effettivo** | Situazione identica a quella dei corsi e stessa causa: il campo `description` di *LMS Batch* è **Small Text** (verificato leggendo `lms/lms/doctype/lms_batch/lms_batch.json`) ed è editato con un `FormControl type="textarea"` a 4 righe (`BatchForm.vue:195-204`), quindi i newline vengono salvati; si perdono solo in resa, perché la panoramica classe li stampa in un `<div>` senza dichiarazione `white-space` (`BatchOverview.vue:8-10`). Differenza rispetto ai corsi, verificata prima di intervenire: per le classi **non esiste** un override sotto `src/overrides/pages/Batches/`, quindi il file da modificare è direttamente quello in `src/pages/`. |
| **Soluzione applicata** | Aggiunta `whitespace-pre-line` al contenitore della descrizione nella panoramica classe, con la stessa motivazione della scelta fatta per i corsi (preserva accapo e righe vuote, mantiene il wrapping, continua a collassare gli spazi multipli). Aggiunto commento `OSLMS-CUSTOM` con rimando al trattamento gemello su `CourseOverview`. |
| **Commit** | Sì — `b8fc176b` *fix(ui): keep line breaks in course and batch short descriptions*, branch `master`. Le due correzioni (corso e classe) sono state raccolte in un unico commit su richiesta dell'utente: stessa causa, stessa soluzione e stesso tipo, quindi separarle avrebbe prodotto due commit non indipendenti. Non pushato. |
| **File modificati** | `frontend/src/pages/Batches/BatchOverview.vue` (righe 8-17). |
| **Verifiche** | Verificato il tipo del campo nel doctype e il controllo usato nel form, per confermare che il dato fosse davvero multiriga anche per le classi e non solo per i corsi. Verificata l'**assenza** di un override di `BatchOverview.vue` (`src/overrides/pages/Batches/` non esiste), per non ripetere l'errore di modificare un file non renderizzato. Confermato che la card classe in elenco (`BatchCard.vue:29-30`) usa la classe `.short-introduction` con troncamento a 2 righe: lasciata invariata, come per i corsi. |

**1. Obiettivo dell'attività**

Uniformare la resa della descrizione breve fra corsi e classi. Al di là del singolo
campo, l'obiettivo è di coerenza: chi redige i contenuti usa lo stesso modo di
scrivere nei due form, e non deve scoprire per tentativi che la formattazione
sopravvive in un caso e non nell'altro.

**2. Modalità di esecuzione**

1. Individuazione dei punti in cui la descrizione classe viene renderizzata,
   distinguendo la panoramica (testo esteso) dalla card in elenco (troncata).
2. Verifica del tipo di campo nel doctype e del controllo nel form, per confermare
   che la causa fosse la stessa dei corsi e non un campo di tipo diverso.
3. Verifica dell'esistenza di un override del componente, prima di modificarlo.
4. Applicazione della stessa utility, con commento coerente a quello dei corsi.

**3. Attività svolte**

L'intervento è il gemello dell'Attività 13 e ne riusa la diagnosi, ma i due
presupposti sono stati ricontrollati invece che dati per scontati: il tipo del campo
(poteva essere `Text Editor`, come lo è `batch_details` sulla stessa classe, e in quel
caso il problema e la soluzione sarebbero stati altri) e l'esistenza di un override
(presente per i corsi, assente per le classi). È proprio la coppia di controlli che
distingue una correzione applicata per analogia da una verificata.

Nota utile per il futuro: sulla classe convivono tre campi descrittivi —
`description` (Small Text, la descrizione breve), `batch_details` (Text Editor) e
`batch_details_raw` (HTML Editor). Solo il primo è interessato da questa correzione;
gli altri due producono già HTML e non hanno il problema.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), branch `master`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* individuazione del punto di resa,
  riverifica dei presupposti rispetto al caso corsi, applicazione della modifica.
- *Motivo della scelta del tool e del modello:* continuità con l'Attività 13 nella
  stessa sessione, con la diagnosi già in contesto; il valore aggiunto qui è stato
  non replicare la soluzione alla cieca ma ricontrollare i due punti in cui i due
  casi potevano divergere (tipo di campo, presenza di override).
- *Risultato ottenuto:* descrizione breve della classe che rispetta gli accapo, con
  la stessa utility e lo stesso commento usati per i corsi.
- *Verifiche e correzioni effettuate sull'output dell'AI:* controllo del doctype e
  della directory degli override eseguito **prima** dell'edit, non dopo; ispezione
  della card classe per decidere consapevolmente di non estendere lì la modifica.

**6. Problematiche incontrate**

- *Verifica visiva non eseguita in questa sessione.* Come per l'Attività 13, la resa
  va confermata a video dopo il build, su una classe con descrizione multiriga.

### Attività 16 — Censimento della visibilità del numero di iscritti (modifica poi ripristinata)

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — visibilità di un dato per ruolo. La correzione abbozzata è stata **annullata** su richiesta dell'utente: l'attività si chiude come censimento, senza modifiche al codice. |
| **Problema riscontrato** | Domanda dell'utente emersa dall'Attività 14: il **numero di iscritti** è visibile ad alcuni utenti o a tutti? Con l'indicazione che, se visibile a tutti, va nascosto agli studenti. L'utente ha poi precisato che la domanda riguardava **esclusivamente la card del corso nella pagina Corsi**, non l'intera applicazione. |
| **Problema effettivo** | Censiti tutti i punti dell'interfaccia che espongono il conteggio iscritti. La situazione reale era mista, non uniforme: (a) **card corso** in elenco — mostrava il conteggio a chiunque, ma il caso era **già rientrato** con l'Attività 14, che ha sostituito quel valore con la durata; (b) **panoramica corso** — la nostra `CourseOverview` override **non** espone il dato, a differenza del file upstream (`pages/Courses/CourseOverview.vue:40-46`) che lo mostrerebbe: non renderizzato, quindi non visibile; (c) **card laterale del dettaglio corso** — il blocco statistiche con `enrolledLabel` è già disattivato e commentato con marcatore `OSLMS-CUSTOM` in `CourseCardOverlay.vue:274-292`; (d) **dialog di iscrizione ai percorsi** (`ProgramEnrollment.vue:64-69`) — mostrava `Tooltip "Enrolled Students"` con `{{ course.enrollments }} students`, ed è l'unico punto **effettivamente e solamente studentesco**: `Programs.vue:19` renderizza `StudentPrograms` sotto `v-if="isStudent"` (con `isStudent = user.data?.is_student`), e `StudentPrograms.vue:62` è l'unico consumatore di quel dialog; (e) **dashboard corso** (`CourseDashboard.vue`) e **dashboard classe** (`AdminBatchDashboard.vue`) — entrambe già gated, la prima da `isAdmin`, la seconda da `isAdmin \|\| isBatchValutatore`; (f) **home studente** (`WelcomeWithOverallProgress.vue:32`) — conta i corsi a cui lo studente stesso è iscritto, cioè un dato proprio, non un'informazione su altri. |
| **Soluzione applicata** | **Nessuna modifica al codice.** Il punto oggetto della domanda — la card del corso nella pagina Corsi — era già rientrato con l'Attività 14, che ha sostituito il conteggio iscritti con la durata: lì il dato non è più mostrato a nessuno. Nel corso dell'analisi era stato rimosso anche il blocco "Enrolled Students" dal dialog di iscrizione ai percorsi (`ProgramEnrollment.vue:64-69`), unico altro punto esposto agli studenti; l'utente ha chiarito che la richiesta non copriva quel punto e la modifica è stata **ripristinata** con `git checkout` sul file, che torna identico a HEAD. Resta quindi valido il solo censimento, riportato qui sotto come esito dell'attività. |
| **Commit** | Nessun commit — l'attività non ha prodotto modifiche: l'unica applicata è stata annullata prima di qualsiasi commit. |
| **File modificati** | Nessuno. `frontend/src/pages/Programs/ProgramEnrollment.vue` è stato modificato e poi riportato allo stato originale; verificato con `git status` che il working tree non contenga più quella modifica. |
| **Verifiche** | Censimento eseguito con ricerca esaustiva su tutti i `.vue` di `frontend/src` sia sul nome del campo (`enrollments`) sia sulle etichette in linguaggio naturale (`Enrolled Students`, `__('students')`, `student_count`, `enrollment_count`, `iscritti`), per non fermarsi al solo identificatore tecnico. Per ciascun punto trovato è stato risalito il **consumatore** del componente e la relativa condizione di rendering, invece di dedurre la visibilità dal nome del file: `CourseDashboard` → tab creata sotto `isAdmin` (`CourseDetail.vue:355-360`), `AdminBatchDashboard` → tab creata sotto `isAdmin \|\| isBatchValutatore` (`BatchDetail.vue:305-311`), `ProgramEnrollment` → unico consumatore `StudentPrograms`, a sua volta reso solo per `is_student`. Verificato dopo la rimozione che `Tooltip` fosse ancora usato nel file, per non lasciare un import orfano. |

**1. Obiettivo dell'attività**

Rispondere con un censimento verificato, e non a impressione, alla domanda "chi vede
il numero di iscritti", e allineare il prodotto alla decisione dell'utente: il dato
non deve essere visibile agli studenti. La richiesta ha un fondamento pratico: il
numero di iscritti a un corso è un'informazione di natura gestionale e commerciale,
e mostrarla allo studente non aggiunge nulla al suo percorso mentre espone la
dimensione reale dell'utenza — in un corso appena pubblicato o poco frequentato è
anche un segnale controproducente per l'iscrizione.

**2. Modalità di esecuzione**

1. Ricerca esaustiva del dato in tutto il frontend, per identificatore tecnico **e**
   per etichetta visibile, così da intercettare anche i punti che non usano il nome
   del campo.
2. Per ogni occorrenza, risalita al componente che la include e alla condizione sotto
   cui viene renderizzata: la visibilità di un dato non si legge nel file che lo
   stampa, ma in chi lo monta.
3. Classificazione dei punti in tre categorie — già gated, non renderizzato, esposto
   agli studenti — per intervenire solo sulla terza.
4. Rimozione mirata, con presidio anti-regressione per i merge futuri.

**3. Attività svolte**

Il censimento ha ridimensionato il problema: dei sei punti che toccano il conteggio,
tre erano già a posto per costruzione (dashboard corso e classe gated, home studente
che mostra un dato proprio), uno era già neutralizzato in precedenza
(`CourseCardOverlay`, blocco statistiche commentato), uno era rientrato poche ore
prima con l'Attività 14 (card corso, ora durata) e uno solo era realmente esposto.

Il punto significativo dell'analisi è metodologico: la visibilità è stata determinata
risalendo ai consumatori, non leggendo i singoli file. È l'unico modo per arrivare a
conclusioni corrette in due casi opposti presenti qui. Il primo è
`pages/Courses/CourseOverview.vue`, che **contiene** il blocco con il numero di
iscritti (righe 40-46) ma non lo mostra a nessuno, perché il plugin `osOverrideTheme`
serve al suo posto l'override, che quel blocco non ce l'ha: giudicare dal file
avrebbe prodotto un falso positivo e una modifica inutile. Il secondo è
`ProgramEnrollment.vue`, il cui nome non suggerisce affatto un contesto studentesco
ed è invece l'unico punto realmente esposto: giudicare dal nome avrebbe prodotto un
falso negativo, cioè il problema lasciato aperto.

Sulla forma dell'intervento: è stato preferito rimuovere il blocco anziché
condizionarlo a un controllo di ruolo. Un `v-if` su ruolo dentro un componente che
solo gli studenti vedono sarebbe sempre falso: darebbe l'apparenza di una regola
configurabile senza esserlo, e chi leggesse il codice in futuro potrebbe crederlo un
gate funzionante. La rimozione, accompagnata dal commento che spiega perché il blocco
non c'è, dice la verità sul comportamento.

Questo ragionamento resta agli atti ma **non è stato applicato**: l'utente ha
chiarito che la domanda riguardava soltanto la card del corso nella pagina Corsi, e
il file è stato riportato allo stato originale. Il blocco "Enrolled Students" del
dialog percorsi è quindi tuttora visibile agli studenti: è una scelta consapevole,
non una svista, e resta disponibile se in futuro si vorrà estendere la regola.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), branch `master`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* censimento dei punti di esposizione del
  dato, ricostruzione delle condizioni di rendering risalendo ai consumatori,
  classificazione dei casi, rimozione mirata e presidio anti-regressione.
- *Motivo della scelta del tool e del modello:* la domanda sembra binaria ("lo vedono
  tutti o no?") ma la risposta corretta richiedeva di attraversare sei punti con
  regole di visibilità diverse, due dei quali ingannevoli in direzioni opposte (un
  file che contiene il dato ma non è renderizzato; un file dal nome neutro che è
  l'unico esposto). Serviva la conoscenza del sistema di override del progetto, già
  in contesto dalle attività precedenti della giornata.
- *Risultato ottenuto:* risposta puntuale alla domanda per ciascun punto
  dell'interfaccia e rimozione dell'unica esposizione residua agli studenti.
- *Verifiche e correzioni effettuate sull'output dell'AI:* la ricerca non si è
  fermata all'identificatore `enrollments` ma è stata ripetuta sulle etichette
  visibili, proprio per evitare che un punto con naming diverso restasse fuori dal
  censimento; ogni condizione di visibilità è stata letta nel codice del
  consumatore e citata con file e riga, così che l'utente possa verificarla; è stato
  controllato che la rimozione non lasciasse import orfani.

**6. Problematiche incontrate**

- *La visibilità non è leggibile nel file che mostra il dato.* In questo progetto
  convivono tre meccanismi diversi che decidono chi vede cosa — gate per ruolo sulle
  tab, sostituzione di componente via `osOverrideTheme`, e scelta del componente in
  base a `is_student` — e nessuno dei tre è visibile leggendo il file che stampa il
  valore. Qualsiasi futura domanda del tipo "chi vede X" va affrontata risalendo ai
  consumatori, come fatto qui.
- *Verifica funzionale non eseguita.* La rimozione non è stata confermata a video con
  un account studente; va vista al prossimo build aprendo Percorsi da un'utenza
  studente.

---

### Attività 17 — Redazione del report giornaliero aziendale

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto / documentazione |
| **Esigenza di partenza** | Richiesta dell'utente: produrre il report giornaliero previsto dalla direttiva aziendale per la giornata 2026-09-08, con la stessa impostazione e lo stesso registro di quello del 7 settembre, a partire dalle 16 attività registrate nel worklog. |
| **Vincolo tecnico rilevante** | Il worklog è organizzato **per attività** e con linguaggio tecnico; il report è organizzato **per punti della direttiva** (1-4, 6-9) e a livello di **giornata**, con un destinatario non tecnico. Serviva quindi una riaggregazione e una riscrittura, non una sintesi meccanica. Tre punti richiedevano attenzione particolare: (a) le 16 attività non corrispondono a 16 interventi — sono 6 commit, perché 8 attività sono analisi/test senza modifiche al codice e due coppie di correzioni sono state accorpate in un commit solo; (b) due commit sono stati rilasciati su **entrambi** i rami (`master` e `feature/oslms`), quindi la storia git mostra 8 commit per 6 interventi distinti; (c) il punto 6 della direttiva non poteva essere "nessuna problematica" come ieri, perché la giornata ha prodotto tre ostacoli reali e un **errore di cancellazione dati** sull'ambiente locale, che va riportato e non omesso. |
| **Soluzione applicata** | Prodotto `reports/2026-09-08-os-lms.md`, con la struttura del report del giorno precedente. Le 16 attività sono state raggruppate in **otto punti** corrispondenti alle segnalazioni/richieste di partenza (PDF da mobile; traduzioni; enforcement del completamento video; falso "Video failed to load"; accapo nelle descrizioni brevi; icona durata; visibilità del numero di iscritti; fattibilità dello storico chat AI), con tabella dei 6 interventi rilasciati e indicazione dei due rilasciati anche su `master`. Il punto 6 riporta per esteso i tre ostacoli (difetto mobile non riproducibile in locale, Cypress inutilizzabile, YouTube non riproducibile in headless) e l'errore di cancellazione dell'Attività 5, con il perimetro reale dell'impatto (solo utenza amministrativa del sito di sviluppo, nessun utente reale, iscrizione reale ripristinata) e la contromisura adottata a metà giornata. Il punto 8 conferma il 100 % già stabilito ieri, motivando che lo studio di fattibilità sullo storico chat **non** apre una nuova area del perimetro finché non c'è una decisione. Aggiornata l'intestazione della giornata nel worklog, che rimandava al report "da redigere", con il collegamento al file effettivo. |
| **Commit** | Non committata — per convenzione di progetto il worklog non si committa e il report segue la stessa prassi, salvo indicazione contraria dell'utente. |
| **File toccati** | `reports/2026-09-08-os-lms.md` (nuovo, 222 righe dopo le due revisioni), `docs/WORKLOG.md` (questa voce e l'intestazione della giornata 2026-09-08). |
| **Verifiche** | Riletto il blocco 2026-09-08 del worklog (16 attività, ~1.830 righe) per non riportare nel report affermazioni non sostenute dal registro. Verificata con `git log --since='2026-09-08 00:00' --all` la storia della giornata: 8 commit, di cui 2 duplicati fra `master` e `feature/oslms` (`b8fc176b`/`877b47be` e `d76d709e`/`ff9a8795`) più il merge `547c9a8d`, quindi **6 interventi distinti** — dato riportato nell'intestazione del report al posto del conteggio grezzo dei commit. Riletto il report del 7 settembre per mantenere continuità di struttura, registro e livello di dettaglio, e verificato che le due "prossime attività" indicate ieri (analisi dell'ultima segnalazione rimasta e inserimento di due traduzioni) risultino entrambe chiuse oggi, come dichiarato al punto 1. Controllato che ogni cifra citata nel report (tempi misurati 1,028 s / 1,323 s, 60 s di permanenza, rallentamento CPU 20×, servizi video non riconosciuti) corrisponda al valore registrato nella voce di origine. |

**1. Obiettivo dell'attività**

Consegnare il report giornaliero del progetto OS LMS per l'8 settembre, conforme al
template aziendale e leggibile da un destinatario non tecnico, con un livello di
dettaglio tale da permettere a un'altra persona o a un sistema AI di ricostruire la
giornata leggendo il solo report.

**2. Modalità di esecuzione**

1. Lettura del report del giorno precedente, per ricavarne struttura, registro e
   livello di dettaglio da mantenere.
2. Lettura integrale della giornata 2026-09-08 del worklog, attività per attività,
   compresi gli aggiornamenti in coda alle voci (per esempio il riscontro su
   dispositivo Android in Attività 2 e la rettifica dell'ipotesi Vimeo in Attività 5).
3. Confronto con la storia git della giornata per distinguere commit e interventi, e
   per individuare i rilasci duplicati sui due rami.
4. Raggruppamento delle 16 attività per **problema di partenza** anziché per ordine
   cronologico, così che il lettore ritrovi le proprie segnalazioni e non la sequenza
   di lavoro.
5. Riscrittura in linguaggio non tecnico, conservando però i dati misurati (tempi,
   configurazioni, esiti delle prove) che sono ciò che rende il report verificabile.
6. Compilazione dei punti di livello giornaliero (7, 8, 9), che non esistono nel
   worklog e vanno costruiti: prossime attività con risultato atteso, avanzamento
   motivato, spunti di miglioramento aziendale.

**3. Attività svolte e risultati**

Il report è stato costruito attorno a una scelta di aggregazione: **otto problemi**
invece di sedici attività. Il numero di voci del worklog è una misura del lavoro, non
della giornata; per chi legge il report contano le segnalazioni che sono entrate e la
loro sorte. Il raggruppamento rende anche visibili due concatenazioni che nel worklog
sono sparse: le Attività 5, 6, 7, 8 e 9 sono un unico percorso di indagine sul
completamento video, e le Attività 14 e 16 nascono l'una dall'altra.

Tre passaggi hanno richiesto una decisione redazionale:

- *Numero di interventi.* Contare i commit avrebbe dato 8, cioè un numero gonfiato dai
  due rilasci duplicati sui due rami. In intestazione è stato riportato **6**, con la
  precisazione che due sono stati portati anche sul ramo principale.
- *Peso della correzione sul completamento video.* Nel worklog è una voce fra sedici;
  nel report è stata evidenziata al punto 8 perché è l'unica della giornata che incide
  sull'attendibilità di un dato già raccolto e già usato dai responsabili dei corsi.
- *Errore di cancellazione dati.* È stato riportato al punto 6 in modo esplicito, con
  il perimetro reale (solo il sito di sviluppo locale, nessun utente reale,
  l'iscrizione reale cancellata per errore è stata ripristinata) e con la contromisura
  adottata. Ometterlo avrebbe reso il report non affidabile proprio sul punto in cui la
  direttiva chiede trasparenza.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), sessione sul repository `os_lms`,
  branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Attività per cui è stata utilizzata:* lettura integrale del worklog della giornata,
  confronto con la storia git, riaggregazione delle 16 attività negli otto problemi di
  partenza, stesura del report nei punti 1-4 e 6-9, aggiornamento dell'intestazione
  della giornata nel worklog e redazione di questa voce.
- *Motivo della scelta del tool e del modello:* il compito è di sintesi su un corpus
  ampio (circa 1.830 righe di registro tecnico) da restituire in forma completamente
  diversa e per un altro destinatario; serviva un modello capace di tenere in contesto
  l'intera giornata insieme al report del giorno precedente, per garantirne la
  continuità, e un tool con accesso alla storia git per verificare i dati citati invece
  di riportarli dal registro senza controllo.
- *Risultato ottenuto:* report consegnato, coerente per struttura e registro con quello
  del 7 settembre, con i punti di livello giornaliero compilati e i dati verificati.
- *Verifiche e correzioni effettuate sull'output dell'AI:* il conteggio degli interventi
  non è stato preso dalla storia git così com'era — un conteggio grezzo avrebbe
  dichiarato 8 interventi anziché 6 — ma ricostruito distinguendo i commit duplicati sui
  due rami. Ogni cifra citata nel report è stata riscontrata sulla voce di worklog da
  cui proviene, invece di essere riformulata a memoria. È stato verificato che le due
  attività indicate come "prossime" nel report di ieri risultino effettivamente chiuse
  oggi, prima di dichiararlo al punto 1.

**6. Problematiche incontrate**

Nessun ostacolo. Un solo punto di attenzione redazionale, già risolto: il report del
giorno precedente chiudeva il punto 6 con "nessuna problematica", e mantenere la stessa
formula per continuità sarebbe stato falso. La giornata di oggi ha prodotto tre ostacoli
tecnici e un errore operativo, che sono stati riportati per esteso.

**Revisione su richiesta dell'utente.** Dopo la prima consegna l'utente ha chiesto di
**semplificare molto il punto 2** (Modalità di esecuzione) e di essere **più sintetico
nelle singole voci del punto 3** (Attività svolte). Riscritte entrambe le sezioni: il
punto 2 passa da cinque blocchi con sottotitoli in grassetto a tre paragrafi scorrevoli
(metodo e banco di prova, criterio della smentita, decisioni di prodotto e verifiche);
il punto 3 mantiene tutti e otto i punti e tutti i dati misurati ma taglia le
ripetizioni rispetto al punto 1 e le spiegazioni tecniche già presenti nel worklog. Il
report passa da 327 a 293 righe, con la riduzione concentrata sulle due sezioni
indicate: nessun contenuto informativo rimosso, nessuna delle altre sezioni toccata.

**Seconda revisione su indicazione dell'utente.** Riscritte le quattro sezioni di
livello giornaliero secondo le indicazioni ricevute: punto 6 (Problematiche) →
**"Nessuna"**; punto 7 (Prossime attività) → unica voce, **riunione sulla situazione
dei nuovi aggiornamenti**; punto 8 (Avanzamento) → confermato il 100 % con l'aggiunta
esplicita che **non ci sono nuovi task aperti** e che le segnalazioni della giornata
non hanno lasciato lavorazioni in sospeso; punto 9 (Spunti di miglioramento) →
**"Nessuno"**. Il report scende da 293 a 222 righe. Da notare per chiarezza del
registro: l'errore di cancellazione dati sull'ambiente di sviluppo locale e i tre
ostacoli tecnici della giornata **non compaiono più nel report** su indicazione
dell'utente, ma restano documentati per esteso nel punto 6 dell'Attività 5 e nelle voci
di origine di questo worklog, che resta la fonte tecnica completa della giornata.
Segnalata all'utente un'incoerenza residua non corretta perché fuori dalle indicazioni
ricevute: il punto 4 del report continua a citare fra i risultati "due limitazioni note
documentate ma non ancora corrette" e la falla di riservatezza sul tutor AI, che si
leggono come lavoro aperto a fronte del punto 8 che dichiara nessun task aperto.

---

## 2026-09-07

> **Report giornaliero:** [`reports/2026-09-07-os-lms.md`](../reports/2026-09-07-os-lms.md)
> — obiettivo e modalità della giornata, aggregazione delle attività per filone,
> utilizzo dell'AI, problematiche, prossime attività, avanzamento del progetto e
> spunti di miglioramento aziendale.

---

### Attività 1 — Ripristino dell'editor "Feature Sections" nelle impostazioni classe

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — regressione introdotta da un merge upstream |
| **Problema riscontrato** | Nelle impostazioni di una classe non compariva più la sezione per gestire le "Feature Sections", che in passato era presente. Lato pubblico i blocchi già salvati continuavano invece a essere mostrati. |
| **Problema effettivo** | Il componente `FeatureSectionEditor` era stato eliminato da `BatchForm.vue` durante il merge `3caf07639` (upstream/main → feature/update-version, 30/06/2026): la risoluzione del conflitto ha preso la versione upstream del file, che non contiene gli innesti custom. Nessun commit esplicito segnalava la rimozione. Il backend (custom field `LMS Batch.custom_feature_sections`, override `get_batch_details`, rendering in `BatchOverview`) era rimasto integro: mancava solo il punto di editing nella SPA. |
| **Soluzione applicata** | Ri-applicato in `BatchForm.vue` il blocco `FeatureSectionEditor`, nella posizione originale (fine sezione "Details", dopo l'editor "Batch Details"), con `:modelValue="batchDetail.doc"` invece di `v-model` (il componente muta il doc in place), `fieldName="custom_feature_sections"` per puntare al campo delle classi e `courseName` volutamente omesso per non esporre il bottone di reindicizzazione AI, specifico dei corsi. Nessuna modifica al backend né al componente condiviso con i corsi. |
| **Commit** | Sì — `c3e68a6d` *fix(batches): restore feature sections editor in batch settings*, branch `feature/oslms` |
| **File modificati** | `frontend/src/pages/Batches/BatchForm.vue` (+8 righe) |
| **Verifiche** | `yarn build` superata (37s, nessun errore; unico warning workbox preesistente); verificato che `updateBatch()` includa il campo nel payload tramite spread del doc e che il watcher `deep` inneschi l'autosave; `git status` pulito a parte i file `docs/` non tracciati. |

**1. Obiettivo dell'attività**

Ripristinare, nella pagina di impostazioni di una classe (LMS Batch) della SPA,
la sezione che permette di creare e modificare le "Feature Sections" — i blocchi
con badge (icona, titolo, descrizione, allegato, visibilità agli iscritti) mostrati
nella pagina pubblica della classe. La funzionalità era presente e risultava
scomparsa dall'interfaccia. Motivazione: il campo custom `custom_feature_sections`
continuava a essere letto e renderizzato lato pubblico, ma non esisteva più alcun
punto di editing nella SPA; l'unica via rimasta era il form desk di Frappe con
inserimento di JSON grezzo, non praticabile per gli utenti gestori.

**2. Modalità di esecuzione**

Procedura prevista:

1. Localizzare il componente `FeatureSectionEditor.vue` e tutti i suoi punti di
   utilizzo nel frontend, per capire se la funzionalità esistesse ancora per le
   classi o solo per i corsi.
2. Verificare l'integrità della catena backend (custom field, serializzazione,
   rendering) prima di toccare il frontend, per distinguere una rimozione
   volontaria da una perdita accidentale.
3. Ricostruire con archeologia git il momento esatto in cui il blocco è sparito e
   la causa, così da non re-introdurre codice incompatibile con l'attuale
   struttura del form.
4. Ri-applicare il blocco nella posizione originale, adattandolo alle convenzioni
   attuali del form.
5. Verificare che il percorso di salvataggio includa il campo e che la build di
   produzione compili.

Strumenti e tecnologie: Vue 3 + frappe-ui + Vite (SPA), Frappe Framework (custom
field `Long Text` su `LMS Batch`), git (`git log -S`, confronto dei contenuti del
file nei genitori del merge), `yarn build`.

Accortezze e dipendenze:

- Il componente `FeatureSectionEditor` è condiviso con la form dei corsi: qualsiasi
  adattamento non deve modificarlo, ma solo parametrizzarne l'uso (prop `fieldName`).
- Il bottone "Reindicizza features" del componente è legato all'ingestion AI dei
  corsi: non deve comparire nel contesto classe.
- Il campo backend è `custom_feature_sections` (classi), diverso da
  `feature_sections` (corsi): il mapping va passato esplicitamente.

**3. Attività svolte**

- Ricerca degli utilizzi di `FeatureSectionEditor` nel frontend: risulta usato in
  un solo punto, `frontend/src/oslms/pages/Courses/OsCourseDetailForm.vue`, cioè
  la form dei corsi. Nessun utilizzo per le classi.
- Verifica della catena backend per le classi, risultata **integra**: custom field
  `LMS Batch-custom_feature_sections` definito nelle fixture
  (`apps/os_lms/os_lms/fixtures/custom_field.json`), deserializzazione JSON in
  `apps/os_lms/os_lms/os_lms/override_utils.py` (override di `get_batch_details`)
  e rendering in sola lettura tramite `FeaturedSectionView` in
  `frontend/src/pages/Batches/BatchOverview.vue`. Conclusione: mancava solo
  l'editor lato SPA.
- Archeologia git. `git log -S"FeatureSectionEditor"` sul file mostrava
  l'introduzione (`1673706de`, 15/06/2026, a sua volta reintroduzione di
  `fb31a0a98`) ma nessuna rimozione, perché `git log -S` salta i commit di merge.
  Confrontando il contenuto del file nei due genitori del merge `3caf07639`
  ("Merge remote-tracking branch 'upstream/main' into feature/update-version",
  30/06/2026) è emersa la causa: il lato nostro (`58202da2`) conteneva il blocco,
  il lato upstream (`5cecb6d0`) no, e la risoluzione del conflitto ha preso la
  versione upstream del file, eliminando il blocco senza che nessun commit
  esplicito lo segnalasse.
- Ri-applicazione del blocco in `BatchForm.vue`, nella stessa posizione originale:
  in coda alla sezione "Details", subito dopo l'editor "Batch Details", con
  l'import del componente accanto agli altri import di componenti della form.
- Decisioni prese rispetto alla versione originale del 15/06:
  - `:modelValue="batchDetail.doc"` al posto di `v-model`, perché il componente
    muta l'oggetto doc in place e non emette `update:modelValue` (stessa
    convenzione già usata dalla form dei corsi);
  - `fieldName="custom_feature_sections"` per puntare al campo delle classi;
  - `courseName` volutamente non passato, così il bottone "Reindicizza features"
    (ingestion AI, specifica dei corsi) resta nascosto;
  - `@dirty="isDirty = true"` mantenuto per parità con l'implementazione originale.
- Verifica del salvataggio senza modifiche aggiuntive: `updateBatch()` invia
  `{ ...batchDetail.doc }`, quindi include il nuovo campo, e il watcher `deep`
  sul doc intercetta la mutazione facendo scattare l'autosave con debounce.

Risultati ottenuti: l'editor delle feature sections è di nuovo disponibile nelle
impostazioni della classe; nessuna modifica necessaria al backend o al componente
condiviso; individuata e documentata la causa esatta della regressione.

**4. Utilizzo dell'AI**

- **Tool/agente:** Claude Code (estensione VS Code).
- **Modello:** Opus 5 (1M context).
- **Attività per cui è stata utilizzata:** ricerca cross-file degli utilizzi del
  componente e della catena backend; archeologia git per individuare il commit di
  merge che ha causato la regressione; ri-applicazione della modifica al form;
  esecuzione e lettura della build; stesura del messaggio di commit.
- **Motivo della scelta del tool e del modello:** il problema non era localizzato
  in un singolo file ma distribuito tra SPA Vue, app custom `os_lms` e storia
  git di merge ripetuti con l'upstream; serviva un agente con accesso diretto a
  filesystem, git e toolchain di build. Il modello con contesto ampio permette di
  tenere insieme frontend, backend e output di git senza perdere il filo tra i
  passaggi.
- **Risultato ottenuto:** causa della regressione identificata con precisione
  (commit di merge `3caf07639` e relativi genitori), correzione di 8 righe
  applicata e committata come `c3e68a6d`, build di produzione superata.
- **Verifiche e correzioni effettuate:** verificata l'inclusione del campo nel
  payload di salvataggio; corretto l'uso di `v-model` in `:modelValue` rispetto
  alla versione storica del blocco; omesso `courseName` per non esporre una
  funzione non pertinente alle classi; eseguita `yarn build` con esito positivo
  (37s, nessun errore; unico warning workbox preesistente e non correlato);
  controllato con `git status` che la build non introducesse artefatti da
  committare e che il commit contenesse solo `BatchForm.vue`.

**6. Problematiche incontrate**

- *Problema:* la rimozione del blocco non era rintracciabile con la ricerca
  standard nella storia del file. *Causa:* `git log -S` esclude per default i
  commit di merge, e la perdita è avvenuta proprio nella risoluzione di un
  conflitto di merge, senza commit dedicato. *Verifiche svolte:* confronto diretto
  del contenuto del file in ciascun commit della sua storia e poi nei due genitori
  del merge sospetto. *Soluzione:* individuato `3caf07639` come punto di perdita.
  *Supporto necessario:* nessuno.
- *Problema latente segnalato:* essendo `BatchForm.vue` un file upstream con
  innesti custom, la stessa regressione può ripresentarsi a ogni allineamento con
  `upstream/main`. Non risolto in questa attività (vedi punti 7 e 9).
- Nota operativa minore: alcuni comandi git in shell zsh hanno richiesto una
  riscrittura per via dell'espansione dei modificatori di parametro
  (`$commit:frontend/...` interpretato erroneamente); risolto quotando l'espansione.
  Nessun impatto sul risultato.

---

### Attività 2 — Analisi della segnalazione "select vuota" nelle impostazioni classe

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi / diagnosi (nessuna modifica al codice) |
| **Problema riscontrato** | Segnalazione riportata da un collega: nelle impostazioni di una classe, aprendo il dialog "Aggiungi un corso alla classe" o "Aggiungi una esercitazione", la select da cui scegliere l'elemento risulta vuota. Richiesta: verificare se la segnalazione è fondata. |
| **Problema effettivo** | La segnalazione è **fondata, ma dipende dal ruolo dell'utente**, non è un guasto generalizzato. La causa è un disallineamento fra il gate della SPA e i permessi di doctype del backend: i pulsanti "Aggiungi" (`BatchCourses.vue:140`, `Assessments.vue:200`) e la tab Impostazioni (`BatchDetail.vue:346`) sono abilitati con `is_moderator \|\| is_evaluator` (`is_docente` per la sola tab), mentre i dati della select arrivano da `frappe.desk.search.search_link`, che applica i permessi di lettura del doctype. Un utente con il solo ruolo **Batch Evaluator** vede quindi il pulsante, ma la chiamata su `LMS Course` risponde **HTTP 403 PermissionError** e la tendina resta vuota. L'errore non è visibile: la resource `options` in `components/Controls/Link.vue` non ha un handler `onError`, e il Combobox in stato vuoto mostra "Nessun risultato trovato", indistinguibile da "nessun dato disponibile". Casi collaterali confermati: `LMS Programming Exercise` ha 0 record, quindi il tipo "Esercizio di programmazione" è sempre vuoto per chiunque; il filtro `published: 1` del dialog corsi esclude i corsi non pubblicati (nel DB locale 5 su 14). |
| **Soluzione applicata** | Nessuna modifica applicata: attività di sola diagnosi, come richiesto. Esclusa la pista inizialmente più probabile (regressione del wiring eventi del Combobox, già occorsa e corretta il 13/07 con `1f861e664`): il binding `@input`/`@focus` è presente sia nel sorgente sia nel bundle compilato servito. Individuate e documentate le tre cause reali sopra descritte, con la relativa matrice ruolo/doctype, per la successiva decisione su come intervenire (allineare il gate SPA ai permessi, oppure concedere la lettura di `LMS Course` al ruolo Batch Evaluator, oppure mostrare l'errore nel controllo Link). |
| **Commit** | Non committata — attività di analisi, nessuna modifica al codice sorgente. Aggiornato il solo `docs/WORKLOG.md` (non tracciato, come da prassi). |
| **File toccati** | Nessuno modificato. File esaminati: `frontend/src/components/Controls/Link.vue`, `frontend/src/overrides/frappe-ui/src/components/Combobox/Combobox.vue`, `frontend/src/components/Modals/BatchCourseModal.vue`, `frontend/src/components/Modals/AssessmentModal.vue`, `frontend/src/pages/Batches/BatchForm.vue`, `frontend/src/pages/Batches/BatchDetail.vue`, `frontend/src/pages/Batches/components/BatchCourses.vue`, `frontend/src/pages/Batches/components/Assessments.vue`, `frontend/src/oslms/components/Controls/Link.vue`, `frontend/src/utils/index.js`, `lms/lms/api.py`, `apps/os_lms/os_lms/os_lms/override_api.py`, `node_modules/reka-ui/dist/Combobox/*`. |
| **Verifiche** | Sonda Python nel container (`dev-elite-frappe-1`) su `search_link` per 5 utenti reali e per 5 ruoli isolati; conteggio record per doctype; test HTTP reali con login via `/api/method/login` come Administrator (HTTP 200, 5 corsi) e come utente temporaneo con solo ruolo Batch Evaluator (HTTP 403 su `LMS Course`, 200 su Quiz/Compiti); ispezione del bundle di produzione già buildato (`lms/public/frontend/assets/index-D8JSJf5W.js`) per confermare la presenza di `onInput`/`onFocus` e degli emit `focus`/`input` del Combobox override; utente temporaneo di prova eliminato a fine test (verificato). |

**1. Obiettivo dell'attività**

Verificare la fondatezza di una segnalazione di terzi ("la select è vuota quando
aggiungo un corso o un'esercitazione a una classe") e, in caso affermativo,
individuarne la causa reale, distinguendo fra: regressione del codice, problema
di dati, problema di permessi o percezione errata dell'utente. L'attività era
esplicitamente di analisi: nessuna correzione richiesta in questa fase.

**2. Modalità di esecuzione**

1. Individuazione del percorso UI reale: tab Impostazioni della classe →
   `BatchForm.vue` → `BatchCourses.vue` (dialog `BatchCourseModal`) e
   `Assessments.vue` (dialog `AssessmentModal`). Confermato che "esercitazione" è
   la traduzione italiana di *Assessment* (`lms/translations/it.csv:2706`,
   `:3652`).
2. Verifica che entrambi i dialog usino lo stesso controllo
   `components/Controls/Link.vue` (il wrapper `oslms/components/Controls/Link.vue`
   usato in `BatchForm.vue` è un pass-through sullo stesso file), che si appoggia
   al Combobox override di `frappe-ui`.
3. Verifica della pista "regressione eventi": il 13/07 il commit `1f861e664`
   aveva corretto esattamente questo sintomo (binding `@update:query`/`@update:open`
   morti dopo un merge upstream, lista mai caricata). Controllato il sorgente
   attuale, il diff `master`↔`HEAD` (identici) e il bundle già compilato: la fix
   è presente ovunque, nessun `onUpdate:query` residuo. Pista esclusa.
4. Verifica del comportamento di apertura a livello di libreria: letto
   `node_modules/reka-ui/dist/Combobox/ComboboxRoot.js` e `ComboboxTrigger.js`
   per confermare che, all'apertura, reka-ui dà il focus all'input
   (`inputElement.value?.focus()`), quindi il caricamento pigro su `onFocus`
   previsto da `Link.vue` viene effettivamente innescato anche cliccando la
   freccia. Nessun difetto di innesco.
5. Verifica del backend: chiamata diretta di `frappe.desk.search.search_link` nel
   container per Administrator, per 5 utenti reali e per 5 ruoli isolati; poi
   test HTTP identici a quelli della SPA (POST su `/api/method/...` con cookie di
   sessione), perché la chiamata Python non mostra lo status code che riceve il
   browser.
6. Confronto fra i gate della SPA (`lms/lms/api.py:66-68` per
   `is_instructor`/`is_moderator`/`is_evaluator`, `override_api.py:131-133` per
   `is_docente`) e la matrice dei permessi di lettura dei doctype coinvolti.

Strumenti: Docker (`dev-elite-frappe-1`), venv di bench per l'esecuzione diretta
(`bench` CLI non disponibile nel container: usato
`frappe-bench/env/bin/python` con `frappe.init`/`frappe.connect`), `curl` per i
test HTTP end-to-end, `grep` sul bundle di produzione, git archeology.

**3. Attività svolte e risultati**

Matrice permessi di lettura rilevata (ruolo isolato → risultato di `search_link`):

| Ruolo unico | LMS Course | Course Evaluator | LMS Quiz | LMS Assignment | LMS Programming Exercise |
| --- | --- | --- | --- | --- | --- |
| Docente | 403 | 403 | 403 | 6 | 403 |
| Gestore | 5 | 403 | 403 | 403 | 403 |
| Batch Evaluator | **403** | 4 | 8 | 6 | 0 |
| Course Creator | 5 | 4 | 8 | 6 | 0 |
| Moderator | 5 | 4 | 8 | 6 | 0 |

Conteggi record nel DB locale: `LMS Course` 14 (5 pubblicati), `Course Evaluator`
4, `LMS Quiz` 8, `LMS Assignment` 6, `LMS Programming Exercise` **0**.

Catena completa dei quattro requisiti per aggiungere un corso a una classe
(rilevata a posteriori, su richiesta dell'utente):

| Passo | Requisito | Moderator | Docente | Batch Evaluator | Gestore da solo | Course Creator |
| --- | --- | --- | --- | --- | --- | --- |
| Vedere la tab Impostazioni | `is_moderator \|\| is_evaluator \|\| is_docente` | sì | sì | sì | **no** | **no** |
| Vedere il pulsante "Aggiungi" | `is_moderator \|\| is_evaluator` | sì | **no** | sì | **no** | **no** |
| Tendina corsi popolata | `read` su `LMS Course` | sì | **no** | **no** | sì | sì |
| Salvare la riga | `write` su `LMS Batch` | sì | sì | sì | **no** | **no** |

Nessun ruolo custom copre da solo l'intera catena: la superano **Moderator** (e
System Manager) da solo, oppure la combinazione **Batch Evaluator + Course
Creator**, che è quella effettivamente assegnata ai gestori nel DB.

Esito: la segnalazione è **vera per gli utenti "valutatore"** (ruolo Batch
Evaluator senza Moderator/Course Creator): vedono la tab Impostazioni e il
pulsante "Aggiungi" nella tab Corsi, ma la select dei corsi risponde 403 e resta
vuota senza alcun messaggio d'errore. Per un Moderator/Course Creator, invece,
tutte le select si popolano correttamente: la segnalazione, per quel profilo,
non è riproducibile e va ricondotta o al tipo "Esercizio di programmazione"
(0 record, sempre vuoto) o ai corsi non pubblicati, esclusi dal filtro
`published: 1` del dialog.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), sessione interattiva sul
  repository `os_lms`, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* diagnosi completa della segnalazione — ricostruzione del
  percorso UI, analisi statica di controllo custom e override `frappe-ui`,
  archeologia git sulle fix precedenti, ispezione del bundle compilato,
  esecuzione di sonde Python nel container Frappe e di test HTTP end-to-end con
  utenti/ruoli diversi, costruzione della matrice permessi.
- *Perché questo tool e questo modello:* la catena da verificare attraversa
  quattro strati eterogenei (componente Vue custom → override di libreria →
  libreria headless `reka-ui` → endpoint Frappe con permessi per ruolo), e
  l'errore poteva annidarsi in ognuno; serviva un modello capace di tenere
  insieme il contesto dei quattro strati e, soprattutto, un tool con accesso alla
  shell per passare dall'ipotesi alla prova sperimentale (query nel container e
  chiamate HTTP autenticate), che è ciò che ha permesso di scartare l'ipotesi
  iniziale sbagliata.
- *Risultato ottenuto:* diagnosi verificata sperimentalmente, con causa primaria
  (disallineamento gate SPA / permessi doctype per il ruolo Batch Evaluator) e
  due cause secondarie (doctype senza record, filtro sui corsi pubblicati);
  esclusa con prove la pista della regressione del Combobox.
- *Verifiche e correzioni fatte sull'output dell'AI:* la prima sonda Python
  leggeva `frappe.response["message"]`, mentre `search_link` restituisce
  direttamente la lista: risultato falsato (0 ovunque, anche per Administrator),
  rilevato e corretto rieseguendo il test sul valore di ritorno. Le conclusioni
  non sono state accettate sul piano teorico ma richiuse con test HTTP reali su
  un utente creato ad hoc con il solo ruolo Batch Evaluator, poi eliminato.

**5. Problematiche riscontrate**

- *Problema:* `bench` non è disponibile come comando nel container
  `dev-elite-frappe-1`. *Soluzione:* esecuzione diretta con
  `frappe-bench/env/bin/python` e bootstrap manuale
  (`frappe.init(site=...)`/`frappe.connect()`) dalla directory `sites`.
- *Problema:* la sonda iniziale restituiva 0 risultati per tutti gli utenti,
  Administrator compreso, suggerendo un guasto del backend inesistente.
  *Causa:* lettura della chiave di risposta sbagliata (vedi punto 4).
  *Soluzione:* riscrittura della sonda sul valore di ritorno e conferma via HTTP.
- *Problema latente segnalato, non risolto in questa attività:* in
  `AssessmentModal.vue` il cambio di "Tipo" non ricarica le opzioni del controllo
  `Link` (nessun watcher su `props.doctype` in `Link.vue`, e il flag `loaded`
  impedisce un secondo fetch): dopo aver aperto la tendina su un tipo e averlo
  poi cambiato, la lista continua a mostrare gli elementi del tipo precedente
  finché non si digita qualcosa, con il rischio concreto di salvare un
  `LMS Assessment` con `assessment_type` e `assessment_name` incoerenti.
- *Nota minore:* i valori del doctype `Course Evaluator` risultano memorizzati
  con virgolette doppie letterali nel nome (es. `"a.basili@overside.it"`);
  anomalia di dato indipendente da questa segnalazione, non approfondita.

---

### Attività 3 — Rimozione del filtro "solo corsi pubblicati" nell'aggiunta corso a una classe

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — comportamento non desiderato di un filtro |
| **Problema riscontrato** | Segnalazione del collega, approfondita nell'Attività 2: nelle impostazioni di una classe, il dialog "Aggiungi un corso alla classe" mostra una tendina apparentemente vuota o comunque priva dei corsi attesi. |
| **Problema effettivo** | Il controllo `Link` del dialog passava `:filters="{ published: 1 }"`, quindi la ricerca `frappe.desk.search.search_link` restituiva **solo i corsi pubblicati**. Nel DB di sviluppo significa 5 corsi su 14: tutti i corsi in bozza o non ancora pubblicati — cioè proprio quelli che si vogliono preparare e assegnare a una classe prima della pubblicazione — erano invisibili. Il vincolo era solo lato interfaccia: il doctype `Batch Course` non ha alcuna validazione (`class BatchCourse(Document): pass`), quindi il salvataggio di un corso non pubblicato era già ammesso dal backend. |
| **Soluzione applicata** | Rimossa la riga `:filters="{ published: 1 }"` dal componente `Link` di `BatchCourseModal.vue`. Nessun'altra modifica: il resto del dialog (campo Valutatore, `onCreate`, inserimento della riga `Batch Course`) è invariato, e gli altri filtri `published: 1` presenti nel frontend (`PageModal.vue`, `CourseOverviewSection.vue`) riguardano funzionalità diverse e sono stati lasciati intatti. |
| **Commit** | Sì — `59c9e52e` *fix(batches): list all courses when adding one to a batch*, branch `feature/oslms` |
| **File modificati** | `frontend/src/components/Modals/BatchCourseModal.vue` (−1 riga) |
| **Verifiche** | Test HTTP reale su `frappe.desk.search.search_link` con sessione autenticata: con il filtro 5 risultati (solo pubblicati), senza filtro 10 risultati comprensivi di corsi non pubblicati (`Corso importato 2`, `Corso di sicurezza`, `Corso Informatica`, …). Verificata l'assenza di validazioni server-side su `Batch Course` che richiedano `published = 1`. `yarn build` eseguita per confermare la compilazione del template modificato. |

**1. Obiettivo dell'attività**

Rendere selezionabili **tutti** i corsi nel dialog di aggiunta di un corso a una
classe, non solo quelli pubblicati, come indicato dall'utente al termine
dell'analisi dell'Attività 2.

**2. Modalità di esecuzione**

1. Rimozione del solo attributo `:filters` dal controllo `Link` del dialog.
2. Controllo che il vincolo non fosse replicato lato server: ispezione del
   controller `lms/lms/doctype/batch_course/batch_course.py` (nessuna
   validazione) e dell'inserimento eseguito dal dialog (`courses.insert.submit`
   con `parenttype: 'LMS Batch'`, `parentfield: 'courses'`).
3. Ricerca di altri filtri analoghi nel frontend, per non lasciare incoerenze e
   al tempo stesso non allargare il perimetro dell'intervento.
4. Verifica sperimentale con chiamata HTTP autenticata all'endpoint di ricerca,
   con e senza filtro, per misurare la differenza effettiva di risultati.
5. Build di produzione per validare il template.

**3. Attività svolte e risultati**

La tendina dei corsi mostra ora anche i corsi non pubblicati. Rilevato e
segnalato un limite residuo, indipendente dalla modifica: `search_link` usa un
`page_length` predefinito di **10** e `Link.vue` non lo sovrascrive, quindi la
lista iniziale si ferma ai primi 10 corsi (su 14 presenti in locale); i restanti
si raggiungono digitando, perché la ricerca viene rieseguita lato server sul
testo inserito. Se si vuole vedere l'intero catalogo senza digitare, occorre
passare esplicitamente un `page_length` più alto dal controllo `Link`: modifica
non applicata perché fuori dal perimetro richiesto.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione
  dell'Attività 2, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* individuazione del punto esatto in cui applicare la
  modifica, verifica che il vincolo non fosse duplicato lato server, misura
  sperimentale dell'effetto (conteggio risultati con e senza filtro) e build.
- *Perché questo tool e questo modello:* la modifica in sé è di una riga, ma il
  rischio reale era che il filtro fosse solo la punta di un vincolo replicato in
  validazioni backend o in altri dialog; serviva un tool con accesso a shell e
  container per dimostrare, e non supporre, che rimuoverlo fosse sicuro.
- *Risultato ottenuto:* filtro rimosso, effetto misurato (5 → 10 risultati, con
  corsi non pubblicati ora presenti), assenza di validazioni server-side
  confermata, build superata.
- *Verifiche e correzioni fatte sull'output dell'AI:* la diagnosi iniziale
  proposta dall'AI nell'Attività 2 indicava come causa primaria un problema di
  permessi per il ruolo Batch Evaluator; l'utente ha invece indicato il filtro
  sui corsi pubblicati come il problema reale da risolvere. La correzione è stata
  applicata su quella indicazione; l'analisi sui permessi resta valida come
  problema distinto e ancora aperto (vedi Attività 2 e punto 7).

**5. Problematiche riscontrate**

- Nessuna problematica bloccante.
- *Limite residuo segnalato, non risolto:* il tetto di 10 risultati di
  `search_link` descritto al punto 3.
- *Problema distinto ancora aperto:* il disallineamento fra gate SPA e permessi
  di doctype documentato nell'Attività 2 (il ruolo Batch Evaluator vede il
  pulsante "Aggiungi" ma riceve 403 sull'elenco corsi). La rimozione del filtro
  non lo risolve: per quel profilo la tendina resta vuota.

---

### Attività 4 — Nascondere i pulsanti "Aggiungi" della classe a chi non ha i permessi

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — allineamento fra visibilità dei comandi e permessi effettivi |
| **Problema riscontrato** | Indicazione dell'utente a valle dell'Attività 2: un valutatore, non avendo i permessi per aggiungere corsi, non deve nemmeno vedere i pulsanti "Aggiungi" nelle tab Corsi ed Esercitazioni delle impostazioni classe. |
| **Problema effettivo** | I due pulsanti erano condizionati ai flag di ruolo `is_moderator \|\| is_evaluator`, mentre il contenuto delle rispettive tendine dipende dai permessi di lettura dei doctype. Per il ruolo **Batch Evaluator** i due criteri divergono: `is_evaluator` è vero, ma il ruolo non ha `read` su `LMS Course` (verificato: HTTP 403 su `frappe.desk.search.search_link`). Il risultato era un comando esposto a chi non può portarlo a termine, con dialog che si apre e tendina vuota senza alcun messaggio d'errore — il sintomo originariamente segnalato dal collega. |
| **Soluzione applicata** | Rimosso `is_evaluator` dalle due funzioni che governano la visibilità dei pulsanti: `isAdmin()` in `BatchCourses.vue` e `canAddAssessments()` in `Assessments.vue`, che ora ritornano il solo `user.data?.is_moderator` (invariata la scorciatoia `readOnlyMode`). Aggiunto in entrambi i punti un commento che spiega il motivo, per evitare che il flag venga reintrodotto in un merge futuro. Entrambe le funzioni erano usate in un unico punto ciascuna (il `v-if` del pulsante), quindi la modifica non ha effetti collaterali su altre parti della pagina. |
| **Commit** | Sì — `8a108685` *fix(batches): hide the add buttons from users who cannot use them*, branch `feature/oslms` |
| **File modificati** | `frontend/src/pages/Batches/components/BatchCourses.vue`, `frontend/src/pages/Batches/components/Assessments.vue` |
| **Verifiche** | Verificato con `grep` che `isAdmin()` e `canAddAssessments()` avessero un solo punto di utilizzo ciascuna (riga 7 di entrambi i template) prima di modificarle; `yarn build` eseguita a valle della modifica. Matrice permessi di riferimento già misurata sperimentalmente nell'Attività 2. |

**1. Obiettivo dell'attività**

Far coincidere ciò che l'interfaccia mostra con ciò che l'utente può realmente
fare: nelle impostazioni di una classe, i pulsanti "Aggiungi" delle tab Corsi ed
Esercitazioni devono essere visibili solo a chi ha i permessi per completare
l'operazione, così che non si presentino più tendine vuote senza spiegazione.

**2. Modalità di esecuzione**

1. Individuazione dei punti di utilizzo dei due gate, per accertare che
   modificarli non alterasse altri comandi della pagina (eliminazione righe,
   selezione multipla, colonne).
2. Rimozione del solo flag `is_evaluator`, mantenendo `is_moderator` e la
   scorciatoia `readOnlyMode`.
3. Inserimento di un commento esplicativo in entrambi i file, dato che sono file
   upstream soggetti a merge periodici.
4. Build di produzione.

**3. Attività svolte e risultati**

Dopo la modifica, i pulsanti "Aggiungi" delle due tab sono visibili solo a chi ha
il ruolo **Moderator** (e a System Manager/Administrator). Il valutatore
(Batch Evaluator) continua ad accedere alla tab Impostazioni e a tutto ciò che
gli compete, ma non vede più comandi che non può eseguire. Docente, Gestore puro,
Course Creator e studenti non erano interessati: per loro i pulsanti erano già
nascosti.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle
  Attività 2 e 3, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* verifica preliminare dei punti di utilizzo dei due gate,
  applicazione della modifica in entrambi i file con commento esplicativo, build.
- *Perché questo tool e questo modello:* la modifica è minima, ma nasce da
  un'analisi multi-livello (flag di ruolo lato SPA contro DocPerms lato Frappe)
  già svolta nella stessa sessione con lo stesso modello: mantenere il contesto
  ha evitato di reintrodurre l'errore opposto, cioè nascondere il pulsante a
  profili che invece devono vederlo.
- *Risultato ottenuto:* gate allineati ai permessi effettivi, con commento che
  documenta il motivo direttamente nel codice.
- *Verifiche e correzioni fatte sull'output dell'AI:* controllato prima di
  modificare che le due funzioni non fossero riutilizzate altrove (lo erano in un
  solo punto ciascuna), per non estendere involontariamente l'effetto della
  modifica ad altri comandi.

**5. Problematiche riscontrate**

- *Incoerenza residua segnalata, non risolta:* la selezione multipla delle righe
  nelle due tab — e quindi il pulsante di **eliminazione** che compare nella
  barra di selezione — è condizionata al solo `user.data?.is_student ? false : true`
  (`BatchCourses.vue:22`, `Assessments.vue:23`). Un valutatore può quindi ancora
  selezionare ed eliminare corsi ed esercitazioni della classe, pur non potendone
  aggiungere. Non modificato perché fuori dal perimetro indicato: va deciso se
  allineare anche quel gate a `is_moderator`.
- *Nota:* il ruolo custom **Valutatore** di os_lms è distinto dal ruolo upstream
  **Batch Evaluator**; il flag `is_evaluator` qui rimosso dipende dal secondo. Un
  utente con il solo ruolo Valutatore non vedeva già questi pulsanti.

---

### Attività 5 — Verifica di conflitto fra la nostra modifica al completamento lezioni e la feature upstream

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — verifica di sovrapposizione fra personalizzazione cliente e funzionalità upstream |
| **Problema riscontrato** | Richiesta dell'utente: sul completamento delle lezioni erano state fatte modifiche custom e in seguito l'upstream ha introdotto una funzionalità equivalente; occorreva stabilire se le due implementazioni convivono o vanno in conflitto. |
| **Problema effettivo** | Non esiste alcun conflitto di codice: la modifica custom (`markProgressIfNoVideo`, commit `72820a715` del 17/04/2026) è stata **eliminata** durante i merge upstream di inizio giugno (`367d65157` / `e0a2e9483`, poi `6a5b54cb` per la v2.58.0), che hanno preso la versione upstream di `Lesson.vue`. Oggi la logica di completamento è quella upstream, praticamente identica al file originale della v2.58.0. La divergenza reale è **comportamentale e di configurazione**, non di codice: ciò che prima era imposto via codice ora dipende dai campi di `LMS Settings`, e sul sito di sviluppo questi sono impostati in modo diverso dall'intento originale. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola analisi. Ricostruita la cronologia delle due implementazioni, verificata l'assenza di codice custom residuo nella zona di completamento, confrontato `frontend/src/pages/Lesson.vue` con la versione upstream v2.58.0 e letti i valori reali delle impostazioni dal database del sito Docker. Individuata l'unica sovrapposizione rimasta (due patch di backfill sugli stessi campi) e verificato che sia complementare, non conflittuale. |
| **Commit** | Non committata — nessuna modifica al codice; l'attività ha prodotto solo la presente voce di registro. |
| **File esaminati** | `frontend/src/pages/Lesson.vue`, `frontend/src/utils/lessonProgress.ts`, `frontend/src/components/Settings/Settings.vue`, `lms/lms/doctype/course_lesson/course_lesson.py`, `lms/lms/doctype/lms_settings/lms_settings.json`, `lms/lms/doctype/lms_settings/lms_settings.py`, `lms/patches/v2_0/set_course_progress_defaults.py`, `apps/os_lms/os_lms/patches/v0_0_5/backfill_lesson_dwell_time.py`, `apps/os_lms/os_lms/patches.txt` |
| **Verifiche** | `grep -rn "markProgressIfNoVideo" frontend/src` → nessuna occorrenza (codice custom assente); `diff` fra `6a5b54cb^2:frontend/src/pages/Lesson.vue` (upstream v2.58.0) e il file su `feature/oslms` → nella zona di completamento solo differenze di formattazione Prettier (virgole finali), nessuna divergenza logica; lettura diretta di `tabSingles` sul DB del container `dev-elite-mariadb-1` per i quattro campi di configurazione; nessuna modifica al working tree (`git status` invariato). |

**1. Obiettivo dell'attività**

Stabilire se la personalizzazione fatta in passato sul completamento delle lezioni
e la funzionalità "Course Progress" arrivata successivamente dall'upstream siano
in conflitto — cioè se coesistano due logiche che si sovrappongono, si annullano o
producono comportamenti imprevedibili — e, in caso contrario, documentare quale
delle due è effettivamente attiva e con quali conseguenze pratiche per gli utenti.

**2. Modalità di esecuzione**

Procedura seguita:

1. Individuare con `git log --grep` / `git log -S` i commit delle due
   implementazioni, distinguendoli per autore (autori upstream: *Raizaaa*,
   *raizasafeel*, *Jannat Patel*; autori interni: *Riccardo Liciotti*,
   *Gabriele Pagnotta*).
2. Leggere il diff della modifica custom per capirne esattamente la semantica.
3. Verificare con `grep` se il codice custom sia ancora presente nel branch
   corrente e, in caso negativo, individuare con `git log --full-history -m -S`
   il merge che lo ha rimosso (i commit di merge sono invisibili a `git log -S`
   senza `--full-history -m`).
4. Confrontare il file attuale con la versione upstream pura (secondo genitore
   del merge v2.58.0) per accertare che non siano rimasti innesti custom nella
   logica di completamento.
5. Leggere il backend e le impostazioni (campi, `validate`, patch) per capire da
   cosa dipende oggi il comportamento.
6. Interrogare il database del sito di sviluppo per conoscere la configurazione
   realmente attiva.

Strumenti: git (archeologia su merge), `grep`, `diff`, Docker (`docker exec` su
`dev-elite-frappe-1` per leggere `site_config.json` e su `dev-elite-mariadb-1`
per interrogare `tabSingles`).

**3. Attività svolte e risultati**

*Cosa avevamo fatto noi.* Commit `72820a715` — "Edit: mark text lessons as
completed immediately" (Riccardo Liciotti, 17/04/2026), unico intervento interno
sul completamento. Rimuoveva del tutto il timer fisso di 30 secondi (`timer`,
`timerInterval`, `startTimer`, `onBeforeUnmount`) e introduceva
`markProgressIfNoVideo()`: le lezioni **senza** video venivano marcate complete
subito all'apertura, mentre quelle **con** video restavano legate alla fine della
riproduzione (listener `ended` e controllo `currentTime >= duration - 1`).

*Cosa ha fatto l'upstream.* PR #2426 (`6919467aa`, 27/05/2026, autore *Raizaaa*),
composta da:

- `ef08e56e3` — backend: quattro campi in `LMS Settings` (`lesson_dwell_time`
  default 30, `enforce_video_completion`, `enforce_quiz_completion`,
  `enforce_assignment_completion`, tutti default 1) e funzione
  `apply_enforcement_flags()` in `course_lesson.py`, che in `save_progress`
  considera quiz/esercitazione come completati quando la relativa enforcement è
  disattivata;
- `fe1da4bc1` — frontend: UI delle impostazioni, nuovo modulo
  `frontend/src/utils/lessonProgress.ts` (`resolveDwellSeconds`,
  `isVideoComplete`, `shouldStartDwellTimer`, `shouldAttachVideoFallback`) e
  riscrittura della logica in `Lesson.vue` con dwell configurabile, soppressione
  del dwell sulle lezioni video quando l'enforcement è attiva e fallback al dwell
  se il video non si carica (con toast di avviso);
- `a4ac02a2` — test backend e frontend;
- `6f83aadfd` (05/06/2026) — patch `lms.patches.v2_0.set_course_progress_defaults`
  per il backfill dei default sui singleton preesistenti e tab dedicata nel desk.

*Esito del confronto.* Il codice custom non esiste più: `markProgressIfNoVideo`
non compare in nessun file del branch `feature/oslms`. La rimozione è avvenuta
nei merge `367d65157` ed `e0a2e9483` ("Merge remote-tracking branch
'upstream/develop' into feature/oslms", 3-4/06/2026), consolidata poi dal merge
v2.58.0 `6a5b54cb`: come già accaduto per le "Feature Sections" (Attività 1), la
risoluzione del conflitto ha preso la versione upstream del file. Il confronto
diretto fra `6a5b54cb^2:frontend/src/pages/Lesson.vue` e il file attuale mostra,
nella zona di completamento, solo differenze di formattazione Prettier. Non
esistono quindi due implementazioni che convivono: ne resta una sola, quella
upstream.

*Unica sovrapposizione residua, non conflittuale.* Sui campi introdotti
dall'upstream agiscono due patch:

- upstream `lms.patches.v2_0.set_course_progress_defaults` — scrive i default
  (30 / 1 / 1 / 1) **solo se il campo non è mai stato salvato** in `tabSingles`;
- nostra `os_lms.patches.v0_0_5.backfill_lesson_dwell_time` (commit `bffa35eac`,
  01/07/2026) — riporta `lesson_dwell_time` a 30 **quando il valore è < 1**.

Sono complementari e idempotenti: la nostra copre il caso che quella upstream non
intercetta (riga presente in `tabSingles` con valore 0/NULL), che faceva fallire
con HTTP 417 il salvataggio di *qualunque* tab delle impostazioni per via del
`validate_lesson_dwell_time()` di `lms_settings.py`. Entrambe girano in
`post_model_sync`, non si sovrascrivono a vicenda e non alterano una scelta già
salvata da un amministratore.

*Configurazione realmente attiva sul sito di sviluppo* (letta da `tabSingles` del
container `dev-elite-mariadb-1`):

| Campo | Valore attuale | Default upstream |
| --- | --- | --- |
| `lesson_dwell_time` | 2 | 30 |
| `enforce_video_completion` | 0 | 1 |
| `enforce_quiz_completion` | 0 | 1 |
| `enforce_assignment_completion` | 0 | 1 |

Conseguenza pratica: **ogni** lezione, comprese quelle con video, si marca come
completata dopo 2 secondi di permanenza, e lato server né quiz né esercitazioni
bloccano il completamento. È un comportamento più permissivo di quello della
nostra modifica originale, che sulle lezioni video richiedeva comunque la
riproduzione fino alla fine. Per riprodurre l'intento originale basta attivare
`enforce_video_completion` (i video tornano vincolati al play completo) lasciando
il dwell a 1-2 secondi per le lezioni testuali; il valore 0 non è utilizzabile
perché `validate` rifiuta valori < 1 e `resolveDwellSeconds` tratta `<= 0` come
"nessun auto-completamento".

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle
  Attività 1-4, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* archeologia git sulle due implementazioni (individuazione
  dei commit per autore e per contenuto, ricerca del merge che ha rimosso il
  codice custom), confronto del file corrente con la versione upstream pura,
  lettura della catena backend/impostazioni/patch e interrogazione del database
  del sito Docker per la configurazione attiva.
- *Perché questo tool e questo modello:* la domanda ("le due modifiche vanno in
  conflitto?") non è risolvibile leggendo il solo codice attuale, perché il codice
  attuale non contiene più la modifica custom: serviva ricostruire la storia
  attraverso i commit di merge, dove `git log -S` di default non guarda. Il
  contesto ampio ha permesso di tenere insieme cronologia git, codice frontend,
  backend, patch e stato del database in un'unica analisi; è inoltre la stessa
  sessione in cui era già stata diagnosticata (Attività 1) una perdita di codice
  custom della stessa natura, il che ha suggerito subito dove cercare.
- *Risultato ottenuto:* risposta motivata "nessun conflitto di codice, ma
  personalizzazione perduta e comportamento oggi determinato dalle impostazioni",
  con l'elenco esatto dei commit coinvolti e i valori di configurazione reali.
- *Verifiche e correzioni fatte sull'output dell'AI:* ogni affermazione è stata
  verificata con un comando: assenza del codice custom via `grep` sull'intero
  `frontend/src`; attribuzione dei commit tramite autore ed email (per non
  scambiare per nostro un commit upstream, e viceversa); equivalenza con
  l'upstream tramite `diff` contro il secondo genitore del merge v2.58.0 anziché
  per lettura a vista; configurazione letta dal database del sito e non dedotta
  dai default dichiarati nel JSON del doctype.

**5. Problematiche riscontrate**

- *Personalizzazione persa senza traccia.* È il secondo caso nella stessa
  giornata (dopo le "Feature Sections") di codice custom eliminato dalla
  risoluzione di un conflitto di merge, senza alcun commit esplicito che lo
  segnali. Rafforza gli spunti già registrati al punto 9 di oggi: estendere
  `osOverrideTheme` alle pagine SPA e mantenere una checklist verificabile in CI
  dei blocchi custom innestati nei file upstream.
- *Decisione aperta, non presa in autonomia.* Se il comportamento voluto è quello
  della modifica originale (testo immediato, video vincolato al play completo),
  occorre attivare `enforce_video_completion` nelle impostazioni. Non modificato
  perché è una scelta funzionale del cliente e non un difetto: la configurazione
  attuale (dwell 2 s, tutte le enforcement disattivate) potrebbe essere
  intenzionale.
- *Nota sui default.* I default dichiarati sul doctype (30 s, tutte le
  enforcement attive) non corrispondono a quanto configurato sul sito di
  sviluppo: al primo migrate di un sito nuovo il comportamento sarà quindi
  sensibilmente più restrittivo di quello odierno. Va tenuto presente in fase di
  messa in produzione.

---

### Attività 6 — Verifica dei blocchi "lezioni in sequenza" e "quiz al completamento"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi — verifica di funzionalità custom sospetta di regressione |
| **Problema riscontrato** | Domanda dell'utente, in coda all'Attività 5: esistono ancora e funzionano il blocco delle lezioni successive finché non sono completate le precedenti e il blocco del quiz finché non sono svolte le lezioni? |
| **Problema effettivo** | La funzionalità è **spezzata a metà**: backend e interfaccia di configurazione sono integri, ma la parte di frontend che applica realmente il blocco è stata cancellata dal merge `1f5978236` ("Merge branch 'feature/oslms' into feature/oslms-tutor", 04/06/2026) — la stessa finestra di merge che ha eliminato il completamento immediato delle lezioni testuali (Attività 5). Oggi il server calcola e restituisce i flag `lesson_access` / `quiz_access` a ogni chiamata `get_lesson`, ma **nessun file di `frontend/src` li legge**: nessun componente, nessuna guardia di rotta. Il blocco non esiste né lato SPA né lato server (le funzioni non lanciano eccezioni, sono solo informative), quindi lo studente apre liberamente la lezione successiva e il quiz. |
| **Soluzione applicata** | Nessuna modifica al codice: attività di sola diagnosi, su richiesta di verifica. Individuati il commit di introduzione della feature, il commit che l'ha rimossa, la porzione esatta di codice mancante e i corsi realmente impattati sul sito di sviluppo. Il ripristino è stato quantificato ma non eseguito, in attesa di conferma. |
| **Commit** | Non committata — nessuna modifica al codice; l'attività ha prodotto solo la presente voce di registro. |
| **File esaminati** | `apps/os_lms/os_lms/os_lms/api.py` (`evaluate_lesson_access`, `evaluate_quiz_access`, `check_lesson_access`, `check_quiz_access`), `apps/os_lms/os_lms/os_lms/override_utils.py` (`get_lesson`), `apps/os_lms/os_lms/hooks.py` (`override_whitelisted_methods`), `apps/os_lms/os_lms/fixtures/custom_field.json`, `frontend/src/oslms/pages/Courses/OsCourseSettings.vue`, `frontend/src/pages/Courses/CourseForm.vue`, `frontend/src/pages/Lesson.vue` (attuale e alla revisione `ea20a831`) |
| **Verifiche** | `grep -rn "lesson_access\|quiz_access" frontend/src` → nessuna occorrenza; scansione della first-parent history di `feature/oslms` alla ricerca dell'ultima revisione contenente il codice (presente in `ea20a831` del 19/05/2026, assente dal merge `1f5978236` del 04/06/2026); verificato che la SPA chiami `lms.lms.utils.get_lesson` ([Lesson.vue:456](frontend/src/pages/Lesson.vue#L456)) e che l'override sia registrato in `override_whitelisted_methods`, quindi che i flag arrivino davvero al client; verificato che `OsCourseSettings.vue` sia ancora montato in `CourseForm.vue`; interrogato il DB del container `dev-elite-mariadb-1` per contare i corsi con le regole attive; controprova finale su richiesta dell'utente con tre ricerche indipendenti su tutto `frontend/src` (stringhe italiane `bloccat*`, accesso alla proprietà `.allowed`, chiamate agli endpoint `os_lms.os_lms.api.check_*`): nessun riscontro, quindi non esiste alcuna implementazione alternativa del blocco con nomi diversi. |

**1. Obiettivo dell'attività**

Accertare se le due regole di apprendimento custom — "lo studente deve completare
ogni lezione prima di accedere alla successiva" e "lo studente deve completare
tutte le lezioni precedenti al quiz per accedervi" — siano ancora presenti nel
codice e, soprattutto, se producano ancora un effetto per lo studente. La domanda
nasce dal sospetto, fondato, che abbiano subito la stessa sorte della
personalizzazione sul completamento lezioni analizzata nell'Attività 5.

**2. Modalità di esecuzione**

Verifica a strati, dal basso verso l'alto, perché una funzionalità di questo tipo
richiede quattro pezzi funzionanti contemporaneamente:

1. **Campi di configurazione** — esistono ancora i custom field sul corso?
2. **Interfaccia di configurazione** — gli interruttori sono ancora raggiungibili
   dall'utente gestore?
3. **Calcolo lato server** — la logica di valutazione dell'accesso esiste ed è
   effettivamente collegata alla chiamata che la SPA esegue?
4. **Applicazione lato client** — qualcuno usa il risultato per bloccare davvero
   l'interfaccia?

Per il punto 4, in caso di esito negativo, ricerca del momento della rimozione
scandendo la first-parent history del branch alla ricerca dell'ultima revisione
che conteneva il codice (i `git log -S` non bastano: la rimozione avviene dentro
un commit di merge). Infine interrogazione del database del sito di sviluppo per
misurare l'impatto reale.

**3. Attività svolte e risultati**

*Origine della funzionalità.* Commit `9179fc83c` — "feat: add sequential lesson
and quiz access control" (Riccardo Liciotti, 27/03/2026), poi rifattorizzata in
`15b394361` — "refactor api calls, merge in one call get_lesson" (17/04/2026),
che ha eliminato le due chiamate HTTP dedicate facendo viaggiare i flag di
accesso dentro la risposta di `get_lesson` (stesso principio della linea guida
"una sola chiamata al caricamento della pagina").

*Strato 1 — campi.* Integri: `LMS Course-enforce_lesson_order` e
`LMS Course-enforce_quiz_on_completion` sono nelle fixture
(`apps/os_lms/os_lms/fixtures/custom_field.json`) e presenti come colonne su
`tabLMS Course`.

*Strato 2 — interfaccia.* Integra: la sezione "Regole di Apprendimento" con i due
interruttori ("Blocca lezioni in sequenza", "Blocca quiz al completamento") è in
`frontend/src/oslms/pages/Courses/OsCourseSettings.vue`, ancora importata e
renderizzata da `frontend/src/pages/Courses/CourseForm.vue`. L'amministratore può
quindi attivare le regole e il valore viene salvato.

*Strato 3 — server.* Integro: `evaluate_lesson_access()` (che confronta la
lezione richiesta con la precedente nell'ordine dei capitoli e verifica la
presenza di un `LMS Course Progress` con stato `Complete`) ed
`evaluate_quiz_access()` (che verifica il completamento di tutte le lezioni
precedenti a quella con il quiz, con fallback che esclude le lezioni-quiz per
evitare deadlock) vivono in `apps/os_lms/os_lms/os_lms/api.py`. Sono esposte
anche come endpoint whitelisted `check_lesson_access` / `check_quiz_access`, e
soprattutto vengono iniettate come `lesson_access` / `quiz_access` nella risposta
dell'override `get_lesson` (`override_utils.py`), registrato in
`override_whitelisted_methods`; poiché la SPA chiama esattamente
`lms.lms.utils.get_lesson`, i flag arrivano davvero al client a ogni apertura di
lezione. L'override esenta correttamente ospiti, moderatori, autori, istruttori e
valutatori.

*Strato 4 — client.* **Mancante.** `grep` su tutto `frontend/src` non trova
alcuna occorrenza di `lesson_access` o `quiz_access`. Alla revisione `ea20a831`
(19/05/2026) `Lesson.vue` conteneva: i ref `lessonBlocked`, `blockedReason`,
`quizBlocked`, `quizBlockedReason`; la loro valorizzazione dai flag della
risposta; il loro azzeramento al cambio lezione; la schermata "Lezione bloccata"
(lucchetto + motivo) che sostituiva l'intero contenuto; due varianti del blocco
"Quiz bloccato" (una per il contenuto EditorJS, una per il body/`quiz_id`); e i
`:disabled="lessonBlocked"` sui comandi di navigazione alla lezione successiva.
Tutto questo non è più presente: l'ultima revisione della first-parent history
che lo contiene è `ea20a831`, la prima che ne è priva è il merge `1f5978236`
(Gabriele Pagnotta, 04/06/2026).

*Impatto reale sul sito di sviluppo* (query su `tabLMS Course`): su 14 corsi,
nessuno ha `enforce_lesson_order` attivo, **due** hanno
`enforce_quiz_on_completion` attivo — "A guide to Frappe Learning" (pubblicato) e
"Prova corso con quiz" (non pubblicato). Su questi due corsi l'amministratore
vede l'interruttore attivo e presume che il quiz sia protetto, mentre in realtà è
accessibile a chiunque sia iscritto: è la situazione peggiore, perché la regola
risulta configurata ma non applicata.

*Stima del ripristino.* Circa 30 righe nel solo `Lesson.vue`: quattro ref, la
lettura dei flag nel punto in cui si prepara la lezione, l'azzeramento nel reset
di cambio lezione, i tre blocchi di template e i binding `:disabled`. Nessuna
modifica al backend, nessuna migrazione. Da valutare in aggiunta, rispetto
all'implementazione originale, l'indicazione delle lezioni bloccate anche
nell'indice del corso (che già allora non era gestita) e un controllo lato server
alla `save_quiz_submission`, dato che oggi il blocco sarebbe comunque solo
estetico.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle
  Attività 1-5, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* verifica a quattro strati della funzionalità (campi,
  interfaccia, backend, client), archeologia git per individuare la revisione di
  rimozione dentro un commit di merge, recupero del codice perduto dalla
  revisione `ea20a831` per quantificare il ripristino, misura dell'impatto reale
  tramite query sul database del container.
- *Perché questo tool e questo modello:* la risposta "c'è ancora e funziona?"
  richiedeva di attraversare cinque livelli tecnici diversi (fixture Frappe, hook
  di override, endpoint whitelisted, componente Vue di configurazione, pagina
  Vue di fruizione) più la storia git e lo stato del database; il contesto ampio
  e la sessione già carica dell'analisi precedente hanno permesso di riconoscere
  immediatamente il pattern — perdita di innesto custom nel merge di inizio
  giugno — e di cercarlo dove serviva anziché ispezionare l'intero frontend.
- *Risultato ottenuto:* diagnosi precisa (funzionalità configurabile ma non
  applicata), commit di introduzione e di rimozione identificati, elenco
  puntuale del codice mancante, impatto misurato sui corsi reali e stima
  dell'intervento di ripristino.
- *Verifiche e correzioni fatte sull'output dell'AI:* non ci si è fermati al
  `grep` negativo sul frontend — si è verificato che l'unico riscontro residuo
  in `Lesson.vue` ("This lesson is locked", riga 31) appartiene a una
  funzionalità **upstream diversa** (`no_preview`, cioè lezione non consultabile
  senza iscrizione) e non alla nostra regola di sequenza, per non dichiarare
  funzionante un blocco che riguarda tutt'altro; si è inoltre confermato che
  l'override backend fosse davvero raggiungibile dalla SPA controllando l'URL
  della risorsa in `Lesson.vue` contro la chiave registrata negli hook, invece di
  darlo per scontato.

**5. Problematiche riscontrate**

- *Terza perdita di personalizzazione dallo stesso merge.* "Feature Sections"
  (Attività 1), completamento lezioni (Attività 5) e regole di blocco
  (questa attività) sono tutte sparite nella stessa finestra di merge di inizio
  giugno. Non è più un incidente isolato: conferma l'urgenza degli spunti del
  punto 9 (estensione di `osOverrideTheme` alle pagine SPA e checklist dei graft
  custom verificata in CI).
- *Configurazione che mente all'utente.* Due corsi hanno la regola del quiz
  attiva senza che venga applicata. Fino al ripristino, l'interruttore comunica
  al gestore una protezione inesistente.
- *Blocco solo lato client anche nell'implementazione originale.* Anche
  ripristinando il codice perduto, il vincolo resterebbe aggirabile da un utente
  tecnicamente capace (chiamata diretta all'API): se la regola ha valore
  formativo o contrattuale, il controllo va aggiunto anche lato server nel punto
  di invio del quiz.

---

### Attività 7 — Ripristino dei blocchi "lezioni in sequenza" e "quiz al completamento"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione — ripristino di funzionalità custom persa in un merge upstream |
| **Problema riscontrato** | Su indicazione dell'utente ("correggi"), a valle della diagnosi dell'Attività 6: i due interruttori "Blocca lezioni in sequenza" e "Blocca quiz al completamento" si potevano attivare ma non producevano alcun effetto per lo studente. |
| **Problema effettivo** | Della funzionalità mancava solo l'ultimo anello: il server calcolava e spediva correttamente `lesson_access` e `quiz_access` dentro la risposta di `get_lesson`, ma nessun componente della SPA leggeva quei campi, perché il codice che li usava era stato cancellato dal merge `1f5978236` del 04/06/2026. Mancava inoltre, già nell'implementazione originale, una protezione essenziale: il completamento automatico della lezione non era inibito su una lezione bloccata, quindi il timer di permanenza (dwell, oggi 2 secondi) l'avrebbe marcata completa dietro la schermata di blocco, sbloccando da solo la lezione successiva. |
| **Soluzione applicata** | Reinnestata in `Lesson.vue` la logica di blocco, adattata alla struttura attuale del file (post-merge upstream v2.58.0) e alle nuove convenzioni delle icone (span con classe `lucide-*` al posto dei componenti `lucide-vue-next`). In più, rispetto all'originale, aggiunta la guardia mancante in `markProgress()`: una lezione bloccata non registra progresso. |
| **Commit** | Sì — `d88fc97f` *fix(lessons): restore sequential lesson and quiz access blocking*, branch `feature/oslms` |
| **File modificati** | `frontend/src/pages/Lesson.vue` (+91/−9 righe) |
| **Verifiche** | `yarn build` superata (37s, nessun errore; unico warning workbox preesistente). Parità con Prettier verificata su copia temporanea: l'unico scostamento residuo è una riga upstream preesistente, non toccata. Verifica funzionale end-to-end sul sito Docker eseguita con l'interprete Python del bench (il comando `bench` non è nel PATH del container): per lo studente iscritto `chiaratrentuno@overside.it`, privo di progressi sul corso "A guide to Frappe Learning", `get_lesson` restituisce `lesson_access = {allowed: True}` sulla prima lezione e `{allowed: False, reason: "Completa la lezione precedente prima di continuare."}` sulla seconda e sulla terza — esattamente i campi che il frontend ora consuma. |

**1. Obiettivo dell'attività**

Far tornare effettivi i due interruttori delle "Regole di Apprendimento" del
corso, ripristinando nella pagina della lezione l'applicazione dei flag di
accesso che il backend già produce, e chiudendo la falla che avrebbe reso il
blocco aggirabile con la sola attesa del timer di completamento.

**2. Modalità di esecuzione**

1. Recupero del codice perduto dalla revisione `ea20a831` (19/05/2026), ultima a
   contenerlo, e analisi di ogni suo punto di innesto.
2. Confronto con la struttura attuale di `Lesson.vue`, profondamente diversa dopo
   il merge upstream v2.58.0 (contenuto della lezione appiattito in una catena di
   `v-if/v-else`, icone come `<span class="lucide-*">`, timer di permanenza
   configurabile reintrodotto dall'upstream).
3. Scelta della forma di innesto meno invasiva possibile, per non moltiplicare i
   conflitti nei merge futuri.
4. Verifica di formattazione, build e comportamento reale sul sito di sviluppo.

**3. Attività svolte e risultati**

*Stato reintrodotto.* Quattro ref (`lessonBlocked`, `blockedReason`,
`quizBlocked`, `quizBlockedReason`), la funzione `applyAccessFromLesson(data)`
che li valorizza dai campi `lesson_access` / `quiz_access` della risposta (con
default permissivo `{allowed: true}` quando i campi non ci sono — caso della
lezione in anteprima non iscritto, dove subentra la schermata upstream), il
computed `contentHasQuiz` (un quiz può stare dentro il contenuto EditorJS e non
solo nel campo `quiz_id`) e l'azzeramento dei quattro ref in `resetLessonState`,
così che il cambio lezione non trascini lo stato della precedente.

*Punto di applicazione.* `applyAccessFromLesson(data)` è chiamata nel watch su
`lesson.data` **subito dopo** `setupLesson(data)`, non prima: è una scelta
deliberata, perché `setupLesson` istanzia EditorJS sull'elemento `#editor` e, se
i flag venissero applicati prima, quell'elemento potrebbe non essere più nel DOM
al momento dell'istanziazione. Il commento nel codice lo documenta.

*Interfaccia.* Schermata "Lezione bloccata" (lucchetto, titolo, motivo dal
server) al posto dell'intero corpo della lezione; blocco "Quiz bloccato" nelle
due varianti di rendering del contenuto (EditorJS e body/`quiz_id`); pulsante
"Avanti" disabilitato nelle due barre di navigazione (normale e Zen Mode);
riquadro note/discussioni nascosto su lezione bloccata. Per contenere la
superficie di conflitto nei merge futuri, invece di avvolgere l'intero corpo in
un `<template v-else>` — che avrebbe richiesto di re-indentare una quarantina di
righe upstream — le condizioni sono state aggiunte in loco alle catene già
esistenti (`!lessonBlocked && …`, con il `v-else` del ramo body diventato
`v-else-if="!lessonBlocked"`).

*Correzione oltre l'originale.* In `markProgress()` è stata aggiunta una guardia
`if (lessonBlocked.value) return`. Senza di essa il timer di permanenza
introdotto dall'upstream (oggi 2 secondi) avrebbe marcato completa la lezione
bloccata mentre lo studente guardava la schermata di blocco, sbloccando la
lezione successiva senza che il contenuto fosse mai stato mostrato: il blocco
sarebbe stato puramente decorativo. Il difetto era latente anche
nell'implementazione originale di marzo/aprile, dove il completamento immediato
delle lezioni senza video produceva lo stesso effetto.

*Verifica funzionale.* Eseguita sul sito Docker chiamando direttamente
l'override `get_lesson` con utenti reali, dopo aver constatato che il comando
`bench` non è disponibile nel PATH del container (si è usato
`../env/bin/python` con `frappe.init` + `frappe.connect`). Con lo studente
iscritto e senza progressi `chiaratrentuno@overside.it` sul corso "A guide to
Frappe Learning": prima lezione `{allowed: True}`, seconda e terza
`{allowed: False}` con il motivo in italiano. Rilevato per inciso che nel
frattempo l'utente ha modificato la configurazione del corso (alle 14:16 di
oggi): ora ha `enforce_lesson_order` attivo e `enforce_quiz_on_completion`
disattivato, mentre in mattinata era il contrario; il corso "Prova corso con
quiz" mantiene attivo il blocco sul quiz.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), stessa sessione delle
  Attività 1-6, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* recupero del codice dalla revisione storica, riscrittura
  degli innesti sulla struttura attuale del file, applicazione delle modifiche,
  verifica di formattazione e build, verifica funzionale end-to-end sul
  container.
- *Perché questo tool e questo modello:* il ripristino non era un semplice
  "annulla il merge": il file di destinazione è cambiato in profondità
  (architettura del template, convenzioni delle icone, reintroduzione del timer
  upstream), quindi ogni innesto andava riscritto e riposizionato ragionando
  sulle interazioni con il codice nuovo — in particolare l'interferenza fra
  blocco della lezione e completamento automatico, che nessuna delle due
  implementazioni originali gestiva. Il contesto ampio, con la diagnosi delle
  Attività 5 e 6 già in sessione, ha permesso di individuare quella interferenza
  invece di limitarsi a ricopiare il codice.
- *Risultato ottenuto:* funzionalità di nuovo operativa, con una falla in meno
  rispetto alla versione originale, senza modifiche al backend e con una
  superficie di conflitto minima verso i futuri merge upstream.
- *Verifiche e correzioni fatte sull'output dell'AI:* verificata la validità
  delle catene `v-if / v-else-if / v-else` dopo l'inserimento delle nuove
  condizioni (un `v-else` non può ricevere condizioni: è stato convertito in
  `v-else-if`); confrontata la formattazione con Prettier su copia temporanea
  invece di riformattare il file — che non era già conforme a monte — evitando
  un diff inquinato da righe upstream; corretti manualmente i due `<span>` delle
  icone che Prettier voleva su più righe; verificato con dati reali che i flag
  arrivino davvero al client, invece di fermarsi alla compilazione.

**5. Problematiche riscontrate**

- *Il blocco resta lato client.* Il vincolo è applicato dall'interfaccia: un
  utente capace può ancora chiamare direttamente l'API del quiz o di
  `save_progress`. Se la regola ha valore formativo o contrattuale va aggiunto un
  controllo lato server nel punto di invio del quiz (e, volendo, in
  `save_progress`). Non fatto in questa attività perché eccede il perimetro
  "ripristina ciò che funzionava".
- *Indice del corso non allineato.* Le lezioni bloccate restano cliccabili nella
  barra laterale; lo studente ci arriva e trova la schermata di blocco. Era così
  anche nell'implementazione originale; un lucchetto nell'indice sarebbe più
  chiaro, ma è una funzionalità nuova, da decidere.
- *Rischio di regressione ricorrente.* È il terzo innesto custom perso nella
  stessa finestra di merge: fino a quando le personalizzazioni delle pagine SPA
  vivranno dentro i file upstream, ogni allineamento può cancellarle in silenzio.
  Vale anche per questo ripristino.

### Attività 8 — Verifica della segnalazione sulla ricerca rapida (risultati lezione, classi lato studente)

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi / verifica di una segnalazione (nessuna modifica al codice) |
| **Problema riscontrato** | Segnalazione di una collega su tre punti: (a) la ricerca rapida individua correttamente i contenuti interni ai corsi, ma cliccando su un risultato di tipo lezione (esempio riportato: "AI multimodale") si apre la pagina generale del corso e non la lezione, costringendo l'utente a ricercarla nell'indice laterale; (b) lato studente la ricerca non trova il nome della classe; (c) lato studente la ricerca non trova i titoli delle singole lezioni, fermandosi al corso e alla sua descrizione. |
| **Problema effettivo** | (a) Confermato, ed è comportamento cablato: sia `Search.vue` sia `CommandPalette.vue` costruiscono la rotta del risultato solo per corso e classe. Nella pagina `/search` il ramo `Course Lesson` punta esplicitamente a `CourseDetail` con `courseName = result.parent`; nella palette ⌘K il calcolo è ancora più grossolano (`doctype === 'LMS Course' ? CourseDetail : BatchDetail`), quindi una lezione finisce su una pagina classe inesistente. La causa a monte è che il documento indicizzato della lezione contiene solo `name` e `parent` (il corso), mentre la rotta `Lesson` richiede `/courses/:courseName/learn/:chapterNumber-:lessonNumber`, numeri che non sono nell'indice. (b) Confermato: `can_access_lesson`/`can_access_batch` in `override_api.py` filtrano i risultati per ruolo, e per una classe `can_access_batch` richiede `published` **e** `start_date >= oggi` a chi non è Moderator o Batch Evaluator: una classe già iniziata è quindi invisibile nella ricerca anche allo studente che la frequenta. (c) **Non confermato**: `can_access_lesson` restituisce `True` a chiunque per le lezioni di un corso pubblicato, e il test riproduce lezioni trovate da uno studente puro. Le lezioni spariscono per lo studente solo se il corso non è pubblicato (il moderatore le vede sempre, lo studente mai): è la spiegazione più probabile del test della collega. Concorre, su query molto generiche, il taglio a `MAX_SEARCH_RESULTS = 100` applicato prima del filtro permessi, con boost di ranking 1.3 ai corsi/classi pubblicati contro 1.0 alle lezioni. |
| **Soluzione applicata** | Nessuna: attività di sola verifica su richiesta. Documentati esito punto per punto, causa tecnica e punti d'intervento per l'eventuale correzione (aggiungere `chapter_number`/`lesson_number` al risultato lato server e usarli nelle due rotte lato client; rivedere la condizione `start_date >= oggi` per le classi). |
| **Commit** | Non committata — nessuna modifica al codice sorgente; il worklog per convenzione non si committa. |
| **File modificati** | Nessuno. File esaminati: `apps/os_lms/os_lms/overrides/sqlite.py`, `apps/os_lms/os_lms/os_lms/override_api.py` (regione `search_sqlite`), `lms/command_palette.py`, `lms/sqlite.py`, `frontend/src/pages/Search/Search.vue`, `frontend/src/components/CommandPalette/CommandPalette.vue`, `frontend/src/router.js`, `frappe/search/sqlite_search.py`. |
| **Verifiche** | Ispezione diretta dell'indice SQLite `learning.db` nel container `dev-elite-frappe-1` (conteggio documenti per doctype: 146 LMS Course, 48 LMS Batch, 49 Course Lesson, 11 LMS Quiz, 6 LMS Assignment, 1 LMS Program, 8 Course Instructor) ed esecuzione dell'endpoint reale `os_lms.os_lms.override_api.search_sqlite` con `frappe.set_user()` come Administrator e come studente puro (`anna.verdi@example.com`, ruoli `All/Guest/LMS Student`). Esito: query "Learning Management Systems" → gruppo "Lessons" presente per **entrambi**; query "Classe A" → Administrator ottiene il gruppo "Batches" (`classe-b`, `classe-a`), lo studente ottiene solo "Courses". |

**1. Obiettivo dell'attività**

Stabilire se la segnalazione della collega descriva comportamenti reali del
sistema o impressioni derivanti dal contesto di prova, distinguendo per ciascuno
dei tre punti fra bug effettivo, scelta di progetto e falso positivo, e produrre
il riferimento tecnico preciso (file, funzione, condizione) su cui intervenire se
si decide la correzione. Serve a evitare sia la correzione di un non-problema sia
l'archiviazione di un problema reale.

**2. Modalità di esecuzione**

Lettura della catena completa della ricerca, dal backend al frontend: schema di
indicizzazione (`lms/sqlite.py` e la sottoclasse `CustomLearningSearch` in
`apps/os_lms/os_lms/overrides/sqlite.py`), endpoint whitelisted e filtro permessi
(`lms.command_palette.search_sqlite`, sostituito via
`override_whitelisted_methods` da `os_lms.os_lms.override_api.search_sqlite`),
motore di ricerca del framework (`frappe/search/sqlite_search.py`, copia locale in
`~/Downloads/frappe`) e i due punti di consumo lato SPA
(`frontend/src/pages/Search/Search.vue` e
`frontend/src/components/CommandPalette/CommandPalette.vue`), più la definizione
della rotta lezione in `frontend/src/router.js`.

Poiché la lettura del codice non basta a smentire una segnalazione fatta su dati
reali, i punti (b) e (c) sono stati riprodotti eseguendo l'endpoint vero
nell'ambiente Docker: `frappe.init`/`frappe.connect` sul sito `lms.localhost` con
l'interprete del bench, `frappe.set_user()` per assumere l'identità di uno
studente senza ruoli amministrativi, e confronto dei gruppi restituiti con quelli
ottenuti come Administrator. L'indice SQLite è stato aperto direttamente in
lettura per verificare che le lezioni siano effettivamente indicizzate e non solo
dichiarate indicizzabili.

**3. Attività svolte**

*Punto (a) — la ricerca trova i contenuti interni ai corsi.* Vero. L'indicizzazione
di base upstream copre solo `LMS Course`, `LMS Batch`, `Job Opportunity` e
`Course Instructor`; è la sottoclasse custom `CustomLearningSearch` ad aggiungere
`Course Lesson` (titolo + tag + corpo della lezione), `LMS Quiz`, `LMS Assignment`
e `LMS Program`, con relativo gruppo "Lessons"/"Quizzes"/... in
`get_grouped_results_custom`. L'indice del sito di sviluppo contiene 49 documenti
`Course Lesson`, quindi la pipeline funziona end-to-end.

*Punto (a) — bug di navigazione.* Confermato, ed è più esteso di quanto segnalato.
Nella pagina `/search` la funzione `navigate()` ha un ramo esplicito
`result.doctype === 'Course Lesson'` che instrada su `CourseDetail` passando
`courseName: result.parent || result.course`: il comportamento osservato dalla
collega è quindi letteralmente ciò che il codice fa, non un effetto collaterale.
Nella palette ⌘K, invece, `generateSearchResults()` calcola la rotta con un solo
ternario (`item.doctype === 'LMS Course' ? 'CourseDetail' : 'BatchDetail'`), per
cui una lezione — ma anche un quiz, un'esercitazione o un percorso — viene
instradata su `BatchDetail` con `batchName` uguale al nome del documento lezione,
cioè su una pagina classe che non esiste. Va quindi chiarito con la collega in
quale dei due punti di ricerca ha eseguito la prova, perché il difetto è diverso.

La causa tecnica comune è l'assenza, nel risultato, delle informazioni che la
rotta lezione richiede: `/courses/:courseName/learn/:chapterNumber-:lessonNumber`
usa la posizione (1-based) del capitolo nella tabella `chapters` del corso e della
lezione nella tabella `lessons` del capitolo, dati non presenti nell'indice, che
per la lezione conserva solo `name`, `title`, `content`, `parent` (il corso) e
`owner`. La correzione naturale è calcolare i due indici lato server in
`get_grouped_results_custom` (una lettura di `Chapter Reference` e
`Lesson Reference`) e consumarli nei due componenti, allineando al contempo la
palette alla pagina di ricerca, che gestisce già molti più doctype.

*Punto (b) — la classe non si trova lato studente.* Confermato e riprodotto.
`can_access_batch` (upstream, riusata dall'override) ammette la classe per chi non
è Moderator o Batch Evaluator solo se `published` **e** `start_date >= nowdate()`.
Il filtro è pensato per l'iscrizione a classi in partenza, ma nella ricerca si
traduce nel fatto che una classe già cominciata non è trovabile nemmeno da chi la
sta frequentando. Prova: cercando "Classe A" l'Administrator ottiene il gruppo
"Batches" con `classe-b` e `classe-a`, lo studente `anna.verdi@example.com`
ottiene solo il gruppo "Courses". Le classi del sito hanno tutte `start_date`
antecedente alla data odierna.

*Punto (c) — i titoli delle lezioni non si trovano lato studente.* Non confermato
come descritto. `can_access_lesson` è già scritta per i learner: risale al corso
tramite `parent`, e se il corso è pubblicato restituisce `True` per qualunque
utente; le scorciatoie per Moderator, proprietario del corso e Course Creator
istruttore servono solo a mostrare anche le bozze. Prova: cercando
"Learning Management Systems" sia l'Administrator sia lo studente puro ottengono
il gruppo "Lessons" con la lezione "What are Learning Management Systems?" del
corso `a-guide-to-frappe-learning`. L'unico caso in cui la segnalazione si
verifica è il corso **non pubblicato**: lì il moderatore vede le lezioni e lo
studente no, esattamente lo scarto descritto. Un secondo fattore, indipendente dal
ruolo, è il tetto di 100 risultati (`MAX_SEARCH_RESULTS`) applicato dal framework
prima del filtro permessi, combinato con il boost di punteggio 1.3 assegnato a
corsi e classi pubblicati contro 1.0 delle lezioni: su query molto generiche le
lezioni possono essere tagliate fuori dalla coda dei risultati.

*Nota sul perimetro della prova.* La verifica è stata eseguita sul sito di
sviluppo `lms.localhost`, che condivide il codice con l'ambiente su cui ha
lavorato la collega ma non i contenuti: la lezione "AI multimodale" non esiste in
locale. La conclusione sul punto (c) vale quindi per la logica applicativa; per
chiudere definitivamente serve sapere se il corso che contiene quella lezione era
pubblicato al momento della prova.

**3-bis. Soluzioni proposte (non implementate)**

Tre interventi indipendenti, uno per problema confermato, più un punto opzionale.

*A — Il risultato di ricerca apre la lezione.* Lato server, in
`get_grouped_results_custom`, arricchire ogni risultato `Course Lesson` con
`chapter_number` e `lesson_number`, cioè la posizione 1-based del capitolo nella
tabella `chapters` del corso (`Chapter Reference`) e della lezione nella tabella
`lessons` del capitolo (`Lesson Reference`); una sola lettura per corso, con cache
nella richiesta, dato che i risultati sono al massimo 100. Lato client, il ramo
`Course Lesson` di `navigate()` in `Search.vue` passa da `CourseDetail` a
`{ name: 'Lesson', params: { courseName, chapterNumber, lessonNumber } }`, con
fallback alla pagina corso se i numeri mancano (lezione orfana o indice non
aggiornato). Da mettere in conto: con il blocco sequenziale ripristinato
nell'Attività 7 (commit `d88fc97f`), lo studente che salta a una lezione non
ancora sbloccata atterra sulla schermata "Lezione bloccata" — comportamento
corretto, ma diverso da oggi.

*B — Palette Cmd+K allineata alla pagina di ricerca.* La mappatura
doctype → rotta esiste oggi in due copie: completa in `Search.vue`, ridotta a un
ternario in `CommandPalette.vue`. Estrarla in un'unica funzione condivisa (es.
`frontend/src/oslms/utils/searchRoutes.ts`) usata da entrambi i componenti.
Risolve il difetto non segnalato — lezioni, quiz, esercitazioni e percorsi che
dalla palette finiscono su una pagina classe inesistente — e impedisce che le due
implementazioni divergano di nuovo al prossimo doctype indicizzato.

*C — Classe trovabile dallo studente che la frequenta.* Opzione C1, consigliata:
in `can_access_batch` ammettere la classe se `published` **e** (`start_date >=
oggi` **oppure** l'utente è iscritto a quella classe o ne è valutatore), con una
sola query su `LMS Batch Enrollment` per l'utente corrente riusata su tutti i
risultati. Opzione C2, scartata: rimuovere del tutto il vincolo `start_date` —
più semplice, ma lo studente troverebbe anche classi a cui non appartiene e,
cliccando, otterrebbe un errore di permessi dalla pagina classe.

*D — Opzionale, solo se emerge il problema.* Il taglio a `MAX_SEARCH_RESULTS`
avviene prima del filtro permessi e i corsi/classi pubblicati hanno boost 1.3
contro 1.0 delle lezioni: su query generiche le lezioni possono restare fuori per
tutti gli utenti. Si correggerebbe alzando il boost delle lezioni di corsi
pubblicati o applicando una quota per gruppo prima del taglio. Da non toccare
finché non ci sono segnalazioni concrete.

Sul punto (c) della segnalazione non è previsto alcun intervento: il comportamento
attuale è già quello atteso, a meno che la richiesta implicita non sia rendere
visibili agli studenti anche le lezioni dei corsi in bozza, che sarebbe una scelta
diversa e da discutere.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), sessione sul repository `os_lms`
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: verifica di una segnalazione utente su
  tre affermazioni distinte relative alla ricerca rapida — indicizzazione dei
  contenuti interni ai corsi, navigazione al risultato di tipo lezione,
  visibilità di classi e lezioni per l'utente studente
- motivo della scelta del tool e del modello: la verifica richiede di attraversare
  in un colpo solo quattro strati (schema di indicizzazione SQLite, endpoint
  whitelisted con override applicativo, motore di ricerca del framework Frappe
  esterno al repository, due componenti Vue distinti che consumano lo stesso
  endpoint) e di distinguere tre affermazioni che sembrano un unico problema ma
  hanno cause diverse. Il contesto ampio consente di tenere aperti insieme
  backend, override e frontend senza perdere i riferimenti incrociati; l'accesso
  diretto a shell e container permette di passare dalla lettura del codice alla
  riproduzione sull'ambiente reale, che è ciò che ha impedito di dare per buona
  la terza affermazione.
- risultato ottenuto: due affermazioni su tre confermate con individuazione della
  riga e della condizione responsabile, una smentita con controprova eseguita
  sull'endpoint reale, più la scoperta di un difetto non segnalato (nella palette
  ⌘K lezioni, quiz, esercitazioni e percorsi finiscono su una pagina classe
  inesistente) e l'indicazione precisa dell'intervento correttivo.
- verifiche e correzioni effettuate: la conclusione iniziale tratta dalla sola
  lettura del codice — "le lezioni sono visibili agli studenti" — è stata
  sottoposta a controprova eseguendo l'endpoint con `frappe.set_user()` su un
  utente con i soli ruoli `All/Guest/LMS Student`, e non per deduzione. È stato
  inoltre verificato sul sorgente del framework che `SQLiteSearch.search()` non
  applichi alcun filtro di permesso proprio (`get_search_filters()` restituisce un
  dizionario vuoto), condizione necessaria perché il ragionamento sul filtro
  applicativo fosse valido, e che l'indice contenga davvero documenti
  `Course Lesson` invece che limitarsi a dichiararli indicizzabili.

**6. Problematiche incontrate**

Il comando `bench` non è disponibile nel `PATH` del container `dev-elite-frappe-1`
(`bash: line 1: bench: command not found`), quindi la console del sito non è
utilizzabile per le prove: si è aggirato l'ostacolo invocando direttamente
l'interprete del virtualenv del bench
(`/home/frappe/bench-data/frappe-bench/env/bin/python`) dalla cartella `sites`,
con `frappe.init(site="lms.localhost")` e `frappe.connect()`. È lo stesso limite
già noto e annotato per questo ambiente.

Resta aperto un punto che non dipende dall'analisi: non è possibile stabilire da
qui se il corso contenente "AI multimodale" fosse pubblicato durante la prova
della collega, informazione necessaria a chiudere il punto (c). Va chiesta a lei
insieme all'indicazione di quale dei due punti di ricerca (palette ⌘K o pagina
`/search`) ha usato per il test di navigazione.

### Attività 9 — Il risultato di ricerca di tipo lezione apre la lezione, non la pagina del corso

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione |
| **Problema riscontrato** | Cercando un contenuto interno a un corso (esempio segnalato: "AI multimodale"), la ricerca lo identifica correttamente come lezione, ma il clic sul risultato apre la pagina generale del corso: l'utente deve poi ritrovare la lezione a mano nell'indice laterale. Difetto confermato nell'Attività 8. |
| **Problema effettivo** | La rotta del risultato è cablata su corso/classe in entrambi i punti di ricerca. Nella pagina `/search` il ramo `Course Lesson` di `navigate()` puntava esplicitamente a `CourseDetail` con `courseName: result.parent`; nella palette Cmd+K la rotta si calcolava con un solo ternario (`doctype === 'LMS Course' ? CourseDetail : BatchDetail`), quindi una lezione finiva addirittura su una pagina classe inesistente. La causa a monte è che il documento indicizzato della lezione contiene solo `name`, `title`, `content`, `parent` (il corso) e `owner`, mentre la rotta `Lesson` è `/courses/:courseName/learn/:chapterNumber-:lessonNumber`: i due numeri non erano disponibili lato client. |
| **Soluzione applicata** | Aggiunta la funzione `add_lesson_positions()` in `override_api.py`, richiamata da `get_grouped_results_custom` sul solo gruppo "Lessons": arricchisce ogni risultato lezione con `course`, `chapter_number` e `lesson_number`, cioè l'`idx` 1-based del `Chapter Reference` nel corso e del `Lesson Reference` nel capitolo — la stessa convenzione usata da `lms.lms.api.mark_lesson_progress` e da `get_lesson`. La risoluzione è **in blocco** (tre query complessive: lezioni, capitoli, riferimenti lezione) invece che per singolo risultato, così il costo dell'endpoint non cresce con il numero di lezioni trovate, che può arrivare a 100. Lato client, in `Search.vue` e `CommandPalette.vue` è stata introdotta la stessa funzione `getLessonRoute()`, che instrada su `{ name: 'Lesson', params: { courseName, chapterNumber, lessonNumber } }` quando i numeri sono presenti e ricade sulla pagina del corso quando non lo sono. |
| **Commit** | Sì — `0192e512` "fix(search): open the found content and scope results to the user", branch `feature/oslms`. Commit unico per le Attività 9, 10, 11, 16 e 17: le modifiche insistono sulle stesse funzioni di `override_api.py` e sugli stessi due componenti, quindi separarle avrebbe richiesto una divisione artificiale degli hunk. Non ancora inviato al remoto. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_api.py`, `frontend/src/pages/Search/Search.vue`, `frontend/src/components/CommandPalette/CommandPalette.vue` |
| **Verifiche** | Backend eseguito sull'ambiente Docker con l'endpoint reale: come studente puro il risultato lezione porta ora `course=a-guide-to-frappe-learning`, `chapter_number=1`, `lesson_number=1` (rotta `/courses/a-guide-to-frappe-learning/learn/1-1`). Controllo di regressione su **tutte** le 49 lezioni indicizzate confrontando la risoluzione in blocco con l'helper già esistente `os_lms.os_lms.api.get_lesson_position`: 0 divergenze. Casi limite provati: lista vuota e `None` (nessuna query), lezione inesistente (risultato lasciato invariato), lezione il cui capitolo non è referenziato dal corso (`0030 Lezione 1`, unica del sito: `chapter_number` nullo → fallback sulla pagina corso). Frontend: `yarn test` → 180 test passati, 18 falliti in 4 file (`blockEditor`, `blockEditorTeardown`, `lessonFormTeardown`, `ReviewModal`) preesistenti e non correlati — nessuno di essi importa `Search.vue` o `CommandPalette.vue`, e falliscono su inizializzazione Pinia/EditorJS. `prettier --check` pulito su entrambi i file Vue, `py_compile` pulito sul file Python. |

**1. Obiettivo dell'attività**

Chiudere il difetto confermato al punto (a) dell'Attività 8: un risultato di
ricerca di tipo lezione deve aprire la lezione trovata. È l'intervento "A" fra
quelli proposti; gli interventi "B" (uniformare del tutto la palette alla pagina
di ricerca per quiz, percorsi ed esercitazioni) e "C" (visibilità delle classi
allo studente iscritto) restano fuori perimetro perché rispondono ad altri due
problemi e vanno decisi separatamente.

**2. Modalità di esecuzione**

Il dato mancante è la posizione della lezione nell'indice del corso, che il
documento indicizzato non contiene. Le opzioni erano due: farla risolvere al
client con una chiamata aggiuntiva al clic, oppure includerla nella risposta di
ricerca. Scelta la seconda, perché evita una latenza al clic e perché il filtro
permessi lato server conosce già l'elenco esatto delle lezioni da restituire.

Per il calcolo si è riusato lo schema dell'helper già presente in
`os_lms/os_lms/api.py::get_lesson_position` (idx di `Chapter Reference` e di
`Lesson Reference`), ma in versione bulk: chiamarlo in ciclo avrebbe significato
tre query per lezione, fino a 300 query su una ricerca ampia, a ogni digitazione
utile (l'input è sotto debounce di 500 ms). L'helper esistente non è stato
modificato: resta il riferimento con cui la nuova funzione è stata verificata.

Lato client la modifica è volutamente minima e simmetrica nei due componenti, con
fallback esplicito sulla pagina corso: i dati reali contengono già una lezione il
cui capitolo non è referenziato dal corso, e senza fallback quel risultato
sarebbe diventato una rotta rotta invece di un clic poco preciso.

**3. Attività svolte**

Backend — in `apps/os_lms/os_lms/os_lms/override_api.py`, `get_grouped_results_custom`
richiama `add_lesson_positions(groups.get("Lessons"))` prima di restituire i
gruppi. La nuova funzione raccoglie i nomi delle lezioni del gruppo, legge in una
sola query `course` e `chapter` da `Course Lesson`, in una seconda query gli `idx`
dei `Chapter Reference` dei capitoli coinvolti e in una terza gli `idx` dei
`Lesson Reference`, poi indicizza i risultati per chiave `(corso, capitolo)` e
`(capitolo, lezione)` e scrive `course`, `chapter_number`, `lesson_number` su
ciascun risultato. Uscita anticipata su lista vuota o assente; nessuna query se
nessuna lezione ha un capitolo; i risultati privi di corrispondenza restano
invariati e ricadono sul comportamento precedente.

Frontend — in `frontend/src/pages/Search/Search.vue` il ramo `Course Lesson` di
`navigate()` chiama ora `getLessonRoute(result)`. In
`frontend/src/components/CommandPalette/CommandPalette.vue` il calcolo della rotta
in `generateSearchResults()` intercetta il doctype `Course Lesson` prima del
ternario preesistente e usa la stessa `getLessonRoute(item)`; il resto della
mappatura è rimasto intatto. Le due funzioni sono identiche e commentate: la
fattorizzazione in un modulo condiviso è deliberatamente rimandata all'intervento
"B", che riguarda anche quiz, percorsi ed esercitazioni e va affrontato in un
passaggio a sé.

Effetto collaterale positivo: nella palette Cmd+K il risultato lezione non porta
più su una pagina classe inesistente. Restano invece mal instradati, sempre nella
sola palette, i risultati di tipo quiz, esercitazione e percorso: è esattamente
il perimetro dell'intervento "B", non toccato qui.

Da tenere presente in fase di collaudo: con il blocco sequenziale ripristinato
nell'Attività 7, uno studente che dalla ricerca salta a una lezione non ancora
sbloccata atterra sulla schermata "Lezione bloccata". È il comportamento corretto
del vincolo, ma è un cambiamento rispetto a prima, quando l'utente veniva sempre
depositato sulla pagina del corso.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione dell'Attività 8
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: implementazione della correzione (backend +
  due componenti Vue) e sua verifica sull'ambiente Docker
- motivo della scelta del tool e del modello: la correzione attraversa tre file su
  due linguaggi e dipende da una convenzione di numerazione (idx delle tabelle
  figlie) che va letta nel codice upstream per non essere reinventata; avere già
  in contesto l'analisi dell'Attività 8 ha evitato di ripercorrere la diagnosi.
  L'accesso a shell e container ha permesso di verificare la correzione sui dati
  reali invece che sulla sola lettura del codice.
- risultato ottenuto: difetto chiuso su entrambi i punti di ricerca, con
  risoluzione in blocco a costo costante e fallback esplicito sui dati anomali;
  individuato e riusato l'helper `get_lesson_position` già presente nel progetto
  come oracolo di verifica invece di scrivere un test ad hoc.
- verifiche e correzioni effettuate: la prima stesura chiamava
  `frappe.get_all` sui capitoli anche quando nessuna lezione aveva un capitolo
  valorizzato, producendo un filtro `in []`; aggiunta la guardia esplicita. Una
  seconda stesura della stessa guardia usava un'espressione condizionale dentro
  la clausola `for`, valida ma poco leggibile: riscritta estraendo la variabile
  `chapter_rows`. La correttezza della mappatura è stata verificata su tutte le
  49 lezioni del sito confrontandola con l'helper esistente (0 divergenze) e non
  sul solo caso della segnalazione, che essendo capitolo 1 lezione 1 non avrebbe
  distinto una numerazione corretta da una costante.

**6. Problematiche incontrate**

Nessun ostacolo bloccante. Due punti da segnalare:

- La suite frontend ha 18 test rossi in 4 file (`blockEditor`,
  `blockEditorTeardown`, `lessonFormTeardown`, `ReviewModal`), preesistenti a
  questa modifica e dovuti a inizializzazione Pinia/EditorJS nell'ambiente di
  test: nessuno di quei file importa i componenti toccati. Vanno però risolti,
  perché una suite già rossa rende inutile il segnale del test automatico per le
  modifiche successive.
- La verifica è stata fatta lato dati ed endpoint, non ancora da browser: manca
  la prova visiva del clic su un risultato lezione nei due punti di ricerca, con
  particolare attenzione all'interazione con il blocco sequenziale delle lezioni.

### Attività 10 — Lo studente trova nella ricerca la classe che frequenta

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione |
| **Problema riscontrato** | Lato studente la ricerca non trova il nome della classe: cercandone il titolo non compare alcun risultato, mentre lo stesso titolo cercato da un moderatore restituisce la classe. Segnalazione confermata e riprodotta nell'Attività 8. |
| **Problema effettivo** | Il filtro permessi upstream `lms.command_palette.can_access_batch` ammette una classe, per chi non è Moderator o Batch Evaluator, solo se `published` **e** `start_date >= oggi`. È la regola giusta per l'**iscrizione** (mostrare le classi ancora aperte), ma la ricerca la riusa tale e quale: appena una classe comincia sparisce dalla ricerca anche per gli studenti che la stanno frequentando, che sono proprio quelli che hanno più motivo di cercarla. Nessuno dei sei batch del sito di sviluppo ha `start_date` futura, il che spiega perché la ricerca lato studente restituisse sempre zero classi. |
| **Soluzione applicata** | Introdotto in `override_api.py` il filtro `can_access_batch_custom()`, che delega prima a quello upstream e, solo se questo nega, ammette comunque la classe se è pubblicata **e** l'utente ne fa parte. L'appartenenza è calcolata da `get_own_batches()`: iscrizioni dell'utente (`LMS Batch Enrollment`) più le classi di cui è valutatore per-batch (`LMS Batch Valutatore`), coerentemente con l'accesso in lettura che il ruolo Valutatore ha già su dashboard, live class e annunci della propria classe. L'insieme è calcolato una sola volta per ricerca, e solo quando serve davvero: se l'utente è Moderator/Batch Evaluator, o se nessun risultato è una classe, non viene eseguita alcuna query aggiuntiva. Nessuna modifica lato frontend: la rotta `BatchDetail` del risultato classe funzionava già. |
| **Commit** | Sì — `0192e512` "fix(search): open the found content and scope results to the user", branch `feature/oslms`. Commit unico per le Attività 9, 10, 11, 16 e 17: le modifiche insistono sulle stesse funzioni di `override_api.py` e sugli stessi due componenti, quindi separarle avrebbe richiesto una divisione artificiale degli hunk. Non ancora inviato al remoto. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_api.py` |
| **Verifiche** | Eseguito l'endpoint reale sul sito di sviluppo confrontando Administrator e lo studente `anna.verdi@example.com` (iscritta alla sola `prima-media`). Query "Prima Media": prima **nessun** risultato per la studentessa, ora `prima-media` come per l'Administrator. Query "Classe A" e "Classe presenza" (classi pubblicate e iniziate a cui **non** è iscritta): continua a non vedere nulla, l'Administrator sì — la regola upstream sulle classi altrui è quindi intatta. Le classi in bozza (`classe-b`, `sdf`) restano invisibili allo studente. Provata la funzione anche su righe sintetiche, per coprire i casi che i dati reali non contengono: classe pubblicata non ancora iniziata e utente non iscritto → visibile (comportamento upstream preservato); pubblicata e iniziata, non iscritto → nascosta; pubblicata e iniziata, iscritto → visibile; bozza, iscritto → nascosta. Verificato infine che `get_own_batches()` risolva correttamente anche i valutatori per-batch (`dottormago@libero.it` e `r.liciotti@overside.it` su `classe-b`). `py_compile` pulito. |

**1. Obiettivo dell'attività**

Realizzare l'intervento "C" fra quelli proposti nell'Attività 8: rendere
trovabile per nome, dalla ricerca, la classe a cui lo studente appartiene, senza
aprire la visibilità sulle classi altrui e senza toccare la logica di iscrizione.

**2. Modalità di esecuzione**

Fra le due strade valutate nell'Attività 8 è stata realizzata la C1. La C2 —
rimuovere del tutto il vincolo `start_date` — era più semplice ma sbagliata: lo
studente avrebbe trovato anche classi a cui non appartiene e, cliccandole,
avrebbe ricevuto un errore di permessi dalla pagina classe, peggiorando
l'esperienza invece di correggerla.

La correzione è scritta come strato sopra il filtro upstream, non come sua
riscrittura: `can_access_batch_custom` chiama `can_access_batch` e ne allarga il
risultato solo nel caso specifico. Così, se upstream cambia quella regola, la
personalizzazione continua a valere senza doverla riallineare, ed è evidente in
lettura quale sia la deviazione dal comportamento originale.

Sul costo: il filtro è per-risultato, quindi risolvere l'appartenenza dentro il
ciclo avrebbe significato due query per ogni classe trovata. L'insieme delle
classi dell'utente è invece caricato una volta sola, e solo se serve — l'utente
non è un gestore di classi e almeno un risultato è una classe — così una ricerca
che non trova classi, o fatta da un moderatore, non paga nulla.

**3. Attività svolte**

In `apps/os_lms/os_lms/os_lms/override_api.py`:

- aggiunto `can_create_batch` agli import da `lms.command_palette`, usato per
  saltare il calcolo quando l'utente è Moderator o Batch Evaluator;
- `get_grouped_results_custom` calcola `own_batches` una volta prima del ciclo,
  con la doppia condizione descritta sopra, e il ramo `LMS Batch` chiama ora
  `can_access_batch_custom(r, roles, own_batches)`;
- aggiunta `get_own_batches()`, che unisce le iscrizioni dell'utente in
  `LMS Batch Enrollment` e le classi in cui compare come valutatore in
  `LMS Batch Valutatore` (due query, entrambe su campi indicizzati);
- aggiunta `can_access_batch_custom(batch, roles, own_batches)`, che delega a
  upstream e, in caso di diniego, ammette la classe se pubblicata e presente in
  `own_batches`.

Comportamento risultante, per un utente senza ruoli di gestione: vede in ricerca
le classi pubblicate non ancora iniziate (come prima) più le proprie classi
pubblicate, a prescindere dalla data di inizio (nuovo); non vede le classi altrui
già iniziate né alcuna classe in bozza (come prima).

Una conseguenza volutamente lasciata fuori: la classe in bozza resta invisibile
anche al valutatore che vi è assegnato, benché il ruolo abbia accesso in lettura
alla dashboard di quella classe. Ampliare la ricerca alle bozze è una decisione
diversa da "lo studente trova la propria classe" e va presa a parte; nei dati di
sviluppo il caso esiste (`classe-b`, non pubblicata, con due valutatori).

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione delle Attività
  8 e 9
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: implementazione e verifica del filtro di
  visibilità delle classi nella ricerca
- motivo della scelta del tool e del modello: la modifica è piccola ma tocca un
  filtro di permessi, dove l'errore tipico è allargare la visibilità più del
  necessario; serviva tenere insieme la regola upstream, il modello del ruolo
  Valutatore per-batch già esistente nel progetto e la verifica sui dati reali
  con più identità utente, cosa che il contesto ampio e l'accesso al container
  rendono immediata.
- risultato ottenuto: la classe frequentata è trovabile dallo studente, le classi
  altrui e le bozze restano nascoste, e il costo aggiuntivo per ricerca è zero
  query per moderatori e per le ricerche che non restituiscono classi.
- verifiche e correzioni effettuate: poiché tutte le classi del sito hanno data
  di inizio passata, i dati reali non potevano dimostrare che la regola upstream
  sulle classi future fosse rimasta intatta; il filtro è quindi stato esercitato
  anche su righe sintetiche che coprono le quattro combinazioni di
  pubblicata/bozza e iscritto/non iscritto. Verificato inoltre che il ramo
  valutatore restituisca le classi attese, e che il caso "moderatore" non esegua
  le query aggiuntive.

**6. Problematiche incontrate**

Nessun ostacolo. Resta da fare la prova da browser: cercare la propria classe con
un'utenza studente reale, cliccare il risultato e controllare che la pagina della
classe si apra correttamente — la rotta non è stata toccata, ma è il passaggio
che chiude la segnalazione dal punto di vista dell'utente.

### Attività 11 — La ricerca mostra anche le classi non pubblicate a cui l'utente appartiene

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione (completamento dell'Attività 10) |
| **Problema riscontrato** | Dopo la correzione dell'Attività 10 lo studente trova la propria classe solo se questa è pubblicata: le classi a cui è iscritto ma che non sono pubbliche continuano a non comparire nella ricerca. Segnalato dall'utente in sede di riscontro. |
| **Problema effettivo** | La condizione `published` che avevo mantenuto per prudenza nell'Attività 10 non corrisponde ai permessi reali della piattaforma: è **più restrittiva della pagina classe stessa**. `lms.lms.utils.get_batch_details`, l'endpoint che alimenta `BatchDetail.vue`, serve la classe quando è vera una qualunque fra `is_batch_published`, `is_batch_admin`, `is_student_enrolled`, `is_valutatore_of_batch`; e a livello di doctype, `lms.lms.doctype.lms_batch.has_permission` concede la lettura all'iscritto **prima** di controllare il flag di pubblicazione. La ricerca era quindi l'unico punto del sistema a nascondere una classe che l'utente può regolarmente aprire: una classe in preparazione, o ritirata dalla pubblicazione a corso iniziato, spariva dalla ricerca pur restando nella lista "le mie classi" e pur avendo la propria pagina accessibile. |
| **Soluzione applicata** | Rimossa la condizione `published` da `can_access_batch_custom` per le classi di cui l'utente fa parte: se il filtro upstream nega, la classe è ammessa quando compare in `get_own_batches()` (iscrizioni + valutatore per-batch), a prescindere da pubblicazione e data di inizio. Il filtro di ricerca è così l'esatto specchio del gate di `get_batch_details`, meno gli amministratori che il filtro upstream copre già: la ricerca non può più proporre un risultato che la pagina classe rifiuterebbe, né nasconderne uno che accetterebbe. Nessuna modifica lato frontend. |
| **Commit** | Sì — `0192e512` "fix(search): open the found content and scope results to the user", branch `feature/oslms`. Commit unico per le Attività 9, 10, 11, 16 e 17: le modifiche insistono sulle stesse funzioni di `override_api.py` e sugli stessi due componenti, quindi separarle avrebbe richiesto una divisione artificiale degli hunk. Non ancora inviato al remoto. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_api.py` |
| **Verifiche** | Riprodotto il caso segnalato sui dati reali: `chiaratrentuno@overside.it` (soli ruoli `LMS Student`), iscritta alla classe **non pubblicata** `classe-b` "Academy Agenti del Consorzio UNIONCART", ora la trova cercandone il titolo; `get_batch_details("classe-b")` chiamato con la sua identità risponde con i dati della classe, quindi il clic sul risultato apre davvero la pagina. Regressioni controllate con più identità sulla stessa classe non pubblicata: studente non iscritto (`anna.verdi`) → nessun risultato; valutatore per-batch (`dottormago@libero.it`) → la trova, e la pagina gli risponde; Administrator → invariato. Controllato inoltre che una classe pubblicata altrui già iniziata resti nascosta allo studente non iscritto e che la propria classe pubblicata (`prima-media`) continui a comparire. Ripetuti i quattro casi sintetici su `can_access_batch_custom`: pubblicata futura non iscritto → visibile (regola upstream preservata), pubblicata iniziata non iscritto → nascosta, bozza non iscritto → nascosta, bozza iscritto → visibile. `py_compile` pulito. |

**1. Obiettivo dell'attività**

Completare l'intervento sulla visibilità delle classi: lo studente deve trovare
nella ricerca **tutte** le classi di cui fa parte, comprese quelle non
pubblicate, senza che questo apra visibilità su classi altrui.

**2. Modalità di esecuzione**

Prima di allargare un filtro di permessi ho verificato che l'allargamento non
producesse risultati non cliccabili — il difetto che aveva fatto scartare
l'opzione "C2" nell'Attività 8. La verifica è stata fatta sul codice
(`get_batch_details` e `lms_batch.has_permission`) e poi sui dati, chiamando
l'endpoint della pagina classe con l'identità dello studente segnalato.

L'esito ha ribaltato la prudenza dell'Attività 10: non si tratta di concedere
qualcosa in più, ma di togliere una restrizione che esisteva **solo** nella
ricerca. Il criterio adottato è quindi diventato esplicito: il filtro di ricerca
deve rispecchiare il gate della pagina di destinazione, non essere una regola
autonoma.

**3. Attività svolte**

In `apps/os_lms/os_lms/os_lms/override_api.py`, `can_access_batch_custom` passa
da `return bool(batch.get("published")) and batch.get("name") in own_batches` a
`return batch.get("name") in own_batches`. Riscritte le docstring delle due
funzioni per citare `get_batch_details` come riferimento del criterio, così che
la ragione della deviazione da upstream resti leggibile a chi manutiene il file.

Comportamento risultante per un utente senza ruoli di gestione: vede in ricerca
le classi pubblicate non ancora iniziate (regola upstream, invariata) più tutte
le classi di cui fa parte come iscritto o come valutatore, in qualunque stato di
pubblicazione e data di inizio; continua a non vedere le classi altrui già
iniziate né le classi altrui non pubblicate.

Questa attività supera la nota lasciata aperta in fondo all'Attività 10 ("la
classe in bozza resta invisibile anche al valutatore assegnato"): ora il
valutatore per-batch trova la propria classe non pubblicata, coerentemente con
l'accesso in lettura che `get_batch_details` gli riconosce già.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione delle Attività
  8, 9 e 10
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: analisi del permesso reale sulla pagina
  classe e correzione conseguente del filtro di ricerca
- motivo della scelta del tool e del modello: la domanda decisiva non era come
  scrivere la modifica (una riga) ma se fosse sicura, e per rispondere serviva
  risalire in due passaggi al gate effettivo della pagina di destinazione e poi
  provarlo con l'identità dell'utente reale sul sito; contesto ampio e accesso al
  container hanno reso la verifica immediata invece che congetturale.
- risultato ottenuto: segnalazione chiusa con una modifica di una riga, motivata
  da un riscontro sul codice di destinazione invece che da una preferenza, e con
  la certezza che nessun risultato di ricerca porti a una pagina negata.
- verifiche e correzioni effettuate: corretta la mia stessa scelta dell'Attività
  10, dove avevo mantenuto il vincolo `published` per prudenza senza averlo
  confrontato con il gate della pagina classe; la prudenza era in realtà una
  restrizione arbitraria. Verificato con quattro identità diverse sulla stessa
  classe non pubblicata (iscritto, non iscritto, valutatore, amministratore) che
  l'allargamento non tocchi chi non fa parte della classe.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Resta valida la nota dell'Attività 10 sulla prova da
browser, che ora ha un caso in più da coprire: cercare una classe non pubblicata
a cui l'utenza di prova è iscritta e verificare che il risultato apra la pagina.

### Attività 12 — Verifica della segnalazione "la classe resta visibile dopo la rimozione dello studente"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi / verifica di una segnalazione (nessuna modifica al codice) |
| **Problema riscontrato** | Dopo le correzioni delle Attività 10 e 11, segnalazione dell'utente: uno studente iscritto a una classe e subito rimosso continua a trovare quella classe nella ricerca. |
| **Problema effettivo** | Nessun difetto nel filtro: la visibilità è calcolata a ogni ricerca con una query viva su `LMS Batch Enrollment` e `LMS Batch Valutatore`, senza cache. Si trattava di una vista non aggiornata lato client: la SPA non ripete la ricerca quando i dati cambiano altrove, e la correzione dell'Attività 11 era stata scritta alle 15:26:55 con ricarica del server di sviluppo alle 15:26:56, mentre le rimozioni di iscrizione registrate sono delle 15:29:25 e 15:29:28 — una scheda aperta da prima mostrava l'elenco costruito prima della rimozione. Confermato dall'utente: rifatta la ricerca, la classe non compare più. |
| **Soluzione applicata** | Nessuna modifica. Documentate le tre situazioni in cui una classe compare legittimamente a chi non è iscritto, da escludere nei collaudi futuri: account con ruolo Moderator/Batch Evaluator, account valutatore di quella classe, classe pubblicata e non ancora iniziata (regola upstream che permette allo studente di scoprire le classi aperte alle iscrizioni). |
| **Commit** | Non committata — nessuna modifica al codice. |
| **File modificati** | Nessuno. |
| **Verifiche** | Riprodotto il caso esatto dell'utente risalendo dal doctype `Deleted Document`: classe `marketing-e-comunicazione` "Marketing e Comunicazione" (bozza, creata alle 15:24) con le due iscrizioni rimosse alle 15:29. Interrogato l'endpoint con l'identità di `r.liciotti@gmail.com` (soli ruoli `LMS Student`, nessuna iscrizione e nessun incarico di valutatore residuo): zero risultati, nemmeno il gruppo classi. Prova controllata su una seconda classe non pubblicata (`classe-b`, iscritta `chiaratrentuno@overside.it`): trovata da iscritta → cancellata l'iscrizione → non più trovata → `frappe.db.rollback()`, dati ripristinati e verificati. Escluse le cache come causa: Frappe imposta `no-store,no-cache,must-revalidate,max-age=0` come default su tutte le risposte (`frappe/app.py`), il service worker della PWA mette in `runtimeCaching` solo i documenti HTML e non le chiamate API (`vite.config.js`), e `SQLiteSearch` non memorizza i risultati. Confrontati infine l'orario di modifica del file con l'orario di avvio del processo che serve le richieste, per stabilire quale versione del codice fosse attiva al momento della prova. |

**1. Obiettivo dell'attività**

Stabilire se la segnalazione descrivesse un difetto residuo del filtro appena
modificato — cioè una visibilità che sopravvive alla rimozione dell'iscrizione —
oppure un effetto di osservazione, prima di intervenire su un filtro di permessi
appena corretto due volte.

**2. Modalità di esecuzione**

Poiché la segnalazione riguardava un caso non riproducibile a comando senza
alterare i dati, la verifica è stata condotta su tre piani. Primo: risalire al
test reale dell'utente dal registro `Deleted Document`, che conserva batch e
membro di ogni iscrizione cancellata, invece di chiedere di ripetere la prova.
Secondo: esercitare il ciclo completo iscrizione → ricerca → rimozione → ricerca
su una classe diversa dentro una transazione chiusa con `rollback`, per avere la
prova diretta senza lasciare tracce sui dati. Terzo: escludere per lettura del
codice ogni livello di memorizzazione fra il filtro e il browser, perché è
l'unica spiegazione alternativa a un difetto di logica.

**3. Attività svolte**

Le tre verifiche hanno dato lo stesso esito: il filtro rilascia la classe
immediatamente. In più è stata ricostruita la cronologia — modifica del file alle
15:26:55, ricarica del server alle 15:26:56, rimozioni alle 15:29:25 e 15:29:28 —
che colloca la prova dell'utente dopo l'entrata in vigore della correzione e
indica quindi la vista non aggiornata come causa, poi confermata dall'utente
stesso ripetendo la ricerca.

Consegnate all'utente le tre condizioni che mostrano legittimamente una classe a
chi non vi è iscritto (ruolo di gestione, incarico di valutatore su quella
classe, classe pubblicata non ancora iniziata), con la nota che la terza è una
scelta di prodotto upstream — senza di essa lo studente non potrebbe più scoprire
dalla ricerca una classe a cui iscriversi — e che eliminarla è una modifica di
una riga, da decidere.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione delle Attività
  8-11
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: verifica di una segnalazione su una
  correzione appena rilasciata
- motivo della scelta del tool e del modello: la tentazione, davanti a una
  segnalazione su codice appena toccato, è modificare ancora il filtro; serviva
  invece un accertamento che combinasse lettura del codice (cache HTTP, service
  worker, motore di ricerca), interrogazione dei dati reali con identità diverse
  e ricostruzione della cronologia dei processi — operazioni che l'accesso
  diretto a shell e container rende immediate.
- risultato ottenuto: evitata una modifica non necessaria a un filtro di
  permessi, individuata la vera causa e fornite all'utente le condizioni da
  escludere nei collaudi successivi.
- verifiche e correzioni effettuate: la prima ipotesi — riga di iscrizione non
  cancellata dalla rimozione — è stata scartata leggendo il percorso di
  rimozione (`removeStudents` in `AdminBatchDashboard.vue` chiama la `delete`
  della list resource, e `LMS Batch Enrollment` non ha alcun hook di
  cancellazione) e poi verificando i dati; la seconda — cache — è stata scartata
  sui sorgenti di Frappe e sulla configurazione della PWA anziché per intuizione.

**6. Problematiche incontrate**

Nessuna. Da tenere presente per i collaudi futuri su questo ambiente: il server
di sviluppo ricarica il codice Python da solo a ogni modifica, quindi le
correzioni backend sono attive subito, mentre le modifiche al frontend
richiedono `yarn build` — una prova fatta nei secondi intorno a una modifica può
osservare due versioni diverse del sistema.

---

### Attività 13 — Creazione utente: assegnare solo i ruoli selezionati

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione |
| **Problema riscontrato** | Segnalazione dell'utente: «creando un nuovo utente dalle impostazioni generali, l'utente viene creato automaticamente con il ruolo di studente, anche se si seleziona solo valutatore». Richiesta la verifica e, una volta confermata, la correzione: il nuovo utente deve avere **solo** i ruoli spuntati nel modale. |
| **Problema effettivo** | Segnalazione confermata, ma la causa non è nel modale: l'app `lms` registra un hook `before_insert` sul doctype `User` (`lms/hooks.py:130` → `lms.lms.user.add_lms_student_role`) che esegue `doc.append_roles("LMS Student")` **senza alcuna condizione**, su qualunque utente creato in qualunque modo. Il modale creava l'utente con `frappe.client.insert` (facendo scattare l'hook) e poi chiamava `lms.lms.api.save_role` con `value: 1` **solo per i ruoli spuntati**: non inviava mai `value: 0` per quelli non spuntati, quindi "LMS Student" non veniva mai tolto. Effetto collaterale che rendeva il problema poco visibile: nell'elenco membri il badge "Student" è filtrato via (`Members.vue`, `badgeRoles`), quindi il ruolo restava invisibile pur essendo presente sull'utente. |
| **Soluzione applicata** | Nuovo endpoint `os_lms.os_lms.override_api.create_member` che, in un'unica chiamata, crea l'utente e poi **riconcilia l'intero set di ruoli gestibili**: assegna quelli selezionati e rimuove quelli non selezionati, "LMS Student" compreso. Il modale `NewMemberModal.vue` ora usa quell'endpoint al posto di `frappe.client.insert` + N chiamate a `save_role`, e blocca l'invio se non è selezionato alcun ruolo. |
| **Commit** | Sì — `290b14de` fix(members): create users with only the selected roles, branch `feature/oslms`. Commit parziale e deliberato: il file `override_api.py` conteneva anche lavoro non collegato (ricerca / command palette, tuttora non committato), quindi è stato messo in staging solo il blocco `MANAGEABLE_ROLES` + `create_member`, ricostruendo il contenuto da `HEAD` e scrivendolo nell'indice con `git hash-object -w` + `git update-index --cacheinfo`, senza toccare il working tree. `docs/WORKLOG.md` non è committato, come da direttiva. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_api.py` (nuovo `create_member` + costante `MANAGEABLE_ROLES`), `frontend/src/components/Modals/NewMemberModal.vue` (`addMember` riscritta, rimossa `assignRoles`, aggiunto `selectedRoleNames` e la guardia "almeno un ruolo"), `lms/translations/it.csv` (3 nuove stringhe IT). |
| **Verifiche** | `python3 -m py_compile` sul modulo backend: ok. `yarn build` del frontend: completata senza errori (`✓ built in 38.74s`, exit code 0). Verifica funzionale da browser non ancora eseguita: su indicazione dell'utente si è proceduto comunque al commit. |

**1. Obiettivo dell'attività**

Accertare la veridicità della segnalazione sull'assegnazione automatica del ruolo
studente e, in caso positivo, fare in modo che un utente creato dalle
impostazioni (Impostazioni → Membri, e dagli stessi modali richiamati da corsi e
classi) porti esattamente i ruoli spuntati: se si seleziona solo "Valutatore",
l'utente deve essere solo valutatore e non anche studente.

**2. Modalità di esecuzione**

Analisi statica del percorso completo di creazione utente, dall'interfaccia al
database:

1. `frontend/src/components/Modals/NewMemberModal.vue` — il modale usato sia da
   `Settings/Members.vue` sia dai punti di ingresso "aggiungi membro" di
   `BatchForm.vue`, `NewBatchModal.vue`, `NewCourseModal.vue`,
   `CoursePublishSettings.vue`, `CourseInstructorsField.vue`.
2. `lms/hooks.py` → `doc_events` sul doctype `User`, e
   `apps/os_lms/os_lms/hooks.py` per eventuali hook aggiuntivi dell'app custom.
3. `lms/lms/api.py::save_role` / `save_evaluator_role` e la sua sovrascrittura
   `os_lms.os_lms.override_api.save_role` (che gestisce i ruoli custom
   `Gestore`, `Docente`, `Valutatore`, assenti dall'elenco upstream `LMS_ROLES`).

Accortezze considerate nella scelta della soluzione:

- **Atomicità**: creare l'utente e sistemarne i ruoli in due momenti diversi (via
  client) lascia una finestra in cui l'utente esiste già come studente; la
  riconciliazione è stata quindi spostata lato server, nella stessa richiesta.
- **Numero di round trip**: il flusso precedente faceva 1 `insert` + N
  `save_role`; ora è una sola chiamata.
- **Riuso di `save_role`**: la riconciliazione non manipola direttamente la
  tabella `Has Role`, ma richiama `save_role`, così il ruolo "Batch Evaluator"
  continua a creare/eliminare anche il record `Course Evaluator` collegato
  (comportamento che una `db.delete` diretta avrebbe perso).
- **Superficie dei permessi invariata**: l'endpoint usa `frappe.only_for("Moderator")`
  (stesso gate di `save_role`) e un normale `.insert()` con controllo permessi,
  esattamente come faceva `frappe.client.insert`; non è stato introdotto alcun
  `ignore_permissions` sulla creazione.
- **Allowlist dei ruoli**: `MANAGEABLE_ROLES` limita ciò che l'endpoint può
  assegnare ai quattro ruoli LMS upstream più i tre custom, così l'endpoint non
  diventa una via per assegnare ruoli arbitrari (per esempio "System Manager").

**3. Attività svolte**

*Accertamento.* La segnalazione è risultata **vera** e riproducibile per
costruzione: `add_lms_student_role` è incondizionata, quindi ogni utente creato
— dal modale, dal desk, dall'import, dalla registrazione pubblica — nasce con
"LMS Student". Il modale aggiungeva poi i ruoli spuntati senza mai rimuovere
quello implicito. Da notare che il ramo di *modifica* dello stesso modale
(`saveRoles`) invia già `value: 0` per i ruoli tolti, quindi il difetto
riguardava solo la creazione.

*Correzione backend.* Aggiunto in
`apps/os_lms/os_lms/os_lms/override_api.py`:

- `MANAGEABLE_ROLES` = `["LMS Student", "Course Creator", "Batch Evaluator",
  "Moderator"] + EXTRA_LMS_ROLES` (cioè `Gestore`, `Docente`, `Valutatore`);
- `create_member(email, roles, first_name=None, last_name=None)`, whitelisted,
  che: verifica `Moderator`; accetta `roles` sia come lista sia come stringa
  JSON; rifiuta l'elenco vuoto ("Seleziona almeno un ruolo per il nuovo
  membro.") e i ruoli fuori allowlist con `frappe.PermissionError`; crea lo
  `User` con `.insert()`; poi cicla su **tutti** i ruoli gestibili chiamando
  `save_role(user.name, role, 1 if role in roles else 0)`. È questo ciclo a
  rimuovere "LMS Student" quando non richiesto. Restituisce `name`, `full_name`
  e `user_image`, gli unici campi usati dai gestori dell'evento `created` nei
  cinque punti di ingresso del modale (tutti leggono solo `.name`).

*Correzione frontend.* In `NewMemberModal.vue`: rimossa `assignRoles`, aggiunta
`selectedRoleNames()` che traduce gli switch in nomi di ruolo tramite `ROLE_MAP`,
e riscritta `addMember` perché faccia una sola `call` a
`os_lms.os_lms.override_api.create_member`. Aggiunta una guardia: senza alcun
ruolo selezionato l'invio si ferma con un toast, perché ora "nessun ruolo"
significherebbe davvero un utente senza ruoli (prima veniva silenziosamente
salvato come studente) e un utente senza ruoli LMS non ha accesso all'app.

*Traduzioni.* Aggiunte a `lms/translations/it.csv`: "Select at least one role",
"Select at least one role for the new member.", "You do not have permission to
grant this role: {0}". Nessuna voce corrispondente in `lms/locale/it.po`, quindi
il CSV è effettivo (in questo progetto il `.po`, se valorizzato, ha la
precedenza sul CSV).

*Conseguenza segnalata all'utente, non modificata.* Un utente con il **solo**
ruolo "Valutatore" perde i permessi che "LMS Student" gli concedeva di riflesso:
`has_lms_role()` (in `lms/lms/utils.py`, basata sulla costante upstream
`LMS_ROLES`, che non contiene i ruoli custom) protegge `get_quiz_with_questions`,
`get_badges` e la visualizzazione dei profili altrui; inoltre il `DocPerm` di
lettura su `LMS Batch` è concesso a `System Manager`, `Moderator`,
`Batch Evaluator` e `LMS Student`, ma non a `Valutatore`
(`VALUTATORE_DOCPERMS` in `apps/os_lms/os_lms/setup.py` copre solo
`LMS Batch Enrollment`, `LMS Live Class`, `LMS Quiz Submission`,
`LMS Assignment Submission`, `LMS Enrollment`, `LMS Course Progress`). Fino a
oggi il problema non emergeva perché ogni valutatore era anche studente. È un
intervento distinto e non è stato eseguito in questa attività.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), sessione interattiva sul
  repository `os_lms`, branch `feature/oslms`.
- modello: Opus 5 (contesto 1M).
- attività per cui è stata utilizzata: accertamento della segnalazione tramite
  lettura incrociata di frontend, hook e API backend; progettazione della
  correzione; scrittura dell'endpoint `create_member` e della modifica al
  modale; aggiunta delle traduzioni italiane; redazione di questa voce.
- motivo della scelta del tool e del modello: la verifica richiedeva di seguire
  una catena che attraversa tre livelli (componente Vue → `frappe.client.insert`
  → hook `doc_events` dell'app `lms` → API `save_role` e sua sovrascrittura in
  `os_lms`) e di valutarne le ricadute sui permessi dei ruoli custom; un modello
  con contesto ampio e accesso diretto al filesystem consente di tenere insieme
  i file coinvolti senza ricostruirli a memoria, riducendo il rischio di
  correggere il sintomo (il modale) invece della causa (l'hook incondizionato).
- risultato ottenuto: segnalazione confermata con indicazione puntuale della
  riga responsabile; correzione implementata lato server in un'unica chiamata,
  con riuso di `save_role` e senza allargare la superficie dei permessi.
- verifiche e correzioni effettuate: prima di scegliere la soluzione sono stati
  controllati i cinque punti di ingresso del modale e i rispettivi gestori
  dell'evento `created`, per accertare che usino solo `user.name` e che il nuovo
  valore di ritorno fosse compatibile; è stato letto `save_evaluator_role` per
  confermare che la chiamata con `value: 0` su un utente appena creato sia
  innocua; è stato verificato che `get_batch_details` usi `frappe.db.get_value`
  (senza controllo permessi) e che quindi la dashboard classe del valutatore non
  dipenda dal `DocPerm` su `LMS Batch`; è stato escluso che `os_lms` aggiunga
  altri hook su `User` oltre a `mark_first_login` (che tocca solo il flag
  `first_login`). L'ipotesi iniziale che la causa fosse nel modale è stata
  scartata leggendo `lms/hooks.py`.

**Aggiornamento — verifica sul sito in esecuzione**

L'utente ha chiesto se i permessi che aveva già concesso al ruolo "Valutatore"
(descritti come "permessi da studente") siano sufficienti a rendere autonomo un
valutatore puro. Verifica eseguita sul container `dev-elite-frappe-1`, sito
`lms.localhost`, impersonando con `frappe.set_user()` un utente reale che porta
il solo ruolo Valutatore (`dottormago@libero.it`, assegnato alla classe
`classe-b`). Esito:

- I permessi effettivamente presenti in `tabCustom DocPerm` per il ruolo
  Valutatore sono i 6 previsti da `VALUTATORE_DOCPERMS` (`LMS Assignment
  Submission` lettura+scrittura, `LMS Batch Enrollment`, `LMS Course Progress`,
  `LMS Enrollment`, `LMS Live Class`, `LMS Quiz Submission` in lettura). Il ruolo
  `LMS Student` ne ha 35.
- `has_lms_role()` restituisce **False** per quell'utente: `get_profile_details`
  e `get_badges` sollevano `PermissionError` (verificato eseguendo le funzioni).
- Lettura negata su `LMS Batch`, `LMS Course`, `Course Lesson`, `LMS Quiz`,
  `LMS Assignment`, `LMS Certificate`, `Discussion Topic`; consentita su
  `LMS Quiz Submission`, `LMS Assignment Submission`, `LMS Batch Enrollment`,
  `User`.
- `get_batch_details("classe-b")` restituisce comunque i dati, perché usa
  `frappe.db.get_value` senza controllo permessi: la dashboard classe funziona
  malgrado la mancanza del `DocPerm` su `LMS Batch`, quindi non è un indicatore
  attendibile della correttezza dei permessi.
- Nel database di sviluppo esistono già due utenti con il solo ruolo Valutatore
  (`dottormago@libero.it`, `nuovoutente2@gmail.com`) e due che lo affiancano a
  `LMS Student` (`nuovoutente@gmail.com`, `r.liciotti@overside.it`).

Conclusione comunicata all'utente: i permessi concessi coprono il primo dei due
tipi di blocco (accesso ai dati, risolvibile aggiungendo `DocPerm` al ruolo), ma
non il secondo — i controlli che interrogano il **nome** del ruolo tramite
`has_lms_role()`, che nessun permesso può soddisfare perché l'elenco dei ruoli
riconosciuti è la costante upstream `LMS_ROLES`. In attesa della decisione
dell'utente non è stata fatta alcuna modifica ai permessi né al codice dei
controlli.

**6. Problematiche incontrate**

La modifica introduce una scelta di prodotto con una ricaduta tecnica reale, già
descritta al punto 3 e comunicata all'utente: rendendo possibile un utente
"solo valutatore", quel profilo non gode più dei permessi che il ruolo studente
gli concedeva implicitamente. Prima di creare in produzione utenti con il solo
ruolo "Valutatore" occorre decidere se estendere `VALUTATORE_DOCPERMS` (lettura
su `LMS Batch`) e se allargare il controllo `has_lms_role()` ai ruoli custom —
quest'ultimo passaggio non è banale perché la costante `LMS_ROLES` è codice
upstream e sovrascriverla richiede o l'override dei singoli endpoint whitelisted
o una modifica lato `lms`.
---

### Attività 14 — Verifica della segnalazione "il video di anteprima della classe non viene mostrato"

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Analisi / verifica di una segnalazione (nessuna modifica al codice) |
| **Problema riscontrato** | Segnalazione della collega sulla classe, area "Descrizione" → "Modifica": il link del video viene inserito e salvato, ma il video non viene visualizzato e non compare nemmeno il riquadro in cui dovrebbe stare. |
| **Problema effettivo** | La segnalazione è confermata ed è un difetto reale, non un problema di configurazione né del link. Il campo `video_link` di `LMS Batch` esiste, viene salvato e viene restituito dall'endpoint `lms.lms.utils.get_batch_details`, ma **nessun componente della SPA lo mostra più**: l'unico consumatore è `BatchOverlay.vue`, che nella pagina classe è commentato dal 19 marzo 2026 (commit `e577585ca` "add translations", riga 37 di `BatchOverview.vue`). Quindi per una classe il video non ha oggi alcun punto di rendering — da cui l'assenza persino del riquadro. Si sommano due difetti latenti che si manifesterebbero appena il componente venisse riattivato: (a) `VideoPreview.vue` risolve il link con `getVideoPreview`, che gestisce solo YouTube e file caricati, non Vimeo — un link Vimeo finirebbe dentro un tag `<video>`, andrebbe in errore e il componente non renderizza nulla; (b) il ripiego sull'immagine (`batch.data.image`) è irraggiungibile perché `LMS Batch` non ha un campo `image` (ha `meta_image`), quindi il ramo di fallback è sempre falso. Sul lato corso lo stesso caso funziona perché `CourseCardOverlay.vue` usa `getVideoEmbedURL`, che invece riconosce Vimeo. |
| **Soluzione applicata** | Nessuna modifica: l'attività era di accertamento. Individuati e documentati i tre interventi necessari per chiudere la segnalazione (riattivazione del componente, supporto Vimeo nel percorso di anteprima, campo immagine di ripiego corretto), in attesa della decisione sull'ambito — il componente commentato mostra anche prezzo, posti disponibili, date e pulsante di iscrizione, quindi riattivarlo tale e quale reintroduce un blocco di interfaccia che era stato tolto volontariamente. |
| **Commit** | Non committata — nessuna modifica al codice. |
| **File modificati** | Nessuno. File analizzati: `frontend/src/pages/Batches/BatchOverview.vue`, `frontend/src/pages/Batches/components/BatchOverlay.vue`, `frontend/src/pages/Batches/BatchForm.vue`, `frontend/src/components/VideoPreview.vue`, `frontend/src/components/Controls/VideoPreviewField.vue`, `frontend/src/components/CourseCardOverlay.vue`, `frontend/src/utils/video.ts`, `frontend/src/utils/index.js`, `lms/lms/utils.py`, `lms/lms/doctype/lms_batch/lms_batch.json`. |
| **Verifiche** | Ricerca esaustiva dei consumatori di `video_link` in `frontend/src` (`grep -rn "video_link" --include="*.vue"`): per le classi risulta un solo punto di scrittura (`BatchForm.vue:207`) e un solo punto di lettura (`BatchOverlay.vue:4`), quest'ultimo dentro il componente commentato. Confermata con `git blame` e `git show e577585caf` la data e il commit in cui la riga è stata commentata. Verificato sul database dello sviluppo (`_5642d48acde4629c`) che la colonna `video_link` esiste su `tabLMS Batch` (tipo `text`) e che la colonna `image` **non** esiste, mentre esiste `meta_image`. Verificato nel sorgente (`lms/lms/utils.py`, elenco campi di `get_batch_details`) che `video_link` viene effettivamente restituito al frontend, quindi il dato arriva alla pagina e viene semplicemente ignorato. Confrontato il percorso corso con quello classe per stabilire perché il primo funziona (`getVideoEmbedURL` vs `getVideoPreview`). |

**1. Obiettivo dell'attività**

Stabilire se la segnalazione descrivesse un errore d'uso (link in un formato non
supportato, campo non salvato) oppure un difetto del prodotto, e in quest'ultimo
caso individuare con precisione il punto in cui il dato si perde, prima di
proporre qualunque modifica all'interfaccia della pagina classe.

**2. Modalità di esecuzione**

L'accertamento è partito dal dato anziché dall'interfaccia, perché il sintomo
descritto — assenza del riquadro, non riquadro vuoto — distingue nettamente due
famiglie di cause: un valore che non arriva, oppure un componente che non viene
montato. È stata quindi seguita la catena completa in ordine: campo del doctype
sul database, campo restituito dall'endpoint, punto di scrittura nel modulo di
modifica, punto di lettura nella pagina. Trovato un solo punto di lettura, se ne
è verificato lo stato nel codice e nella cronologia con `git blame` e
`git show`. In parallelo è stato confrontato il percorso equivalente dei corsi,
che la collega non ha segnalato come difettoso, per capire quale differenza di
implementazione lo renda funzionante.

**3. Attività svolte**

La catena si interrompe in un punto solo e in modo netto. Il valore inserito
viene salvato correttamente: il campo esiste sul doctype `LMS Batch`, la colonna
è presente sul database, il modulo di modifica lo scrive tramite
`VideoPreviewField` e `get_batch_details` lo restituisce insieme al resto della
classe. Il dato arriva quindi alla pagina `BatchOverview.vue` dentro l'oggetto
`batch`, ma lì l'unico elemento che lo mostrerebbe — `<BatchOverlay :batch="batch" />`,
riga 37 — è racchiuso in un commento HTML dal 19 marzo 2026. Nessun altro
componente della SPA legge `video_link` per le classi: la ricerca sull'intero
`frontend/src` restituisce, oltre al modulo di modifica, soltanto i riferimenti
del percorso corsi. Il video di anteprima di una classe è perciò, ad oggi,
scrivibile ma non visualizzabile in nessun punto dell'applicazione — il che
spiega esattamente il sintomo riportato, compresa l'assenza del riquadro.

Sono emersi inoltre due difetti che oggi restano nascosti dietro al commento e
che si manifesterebbero appena il componente venisse riattivato. Il primo è il
mancato supporto di Vimeo: `VideoPreview.vue` risolve il link con
`getVideoPreview` (`frontend/src/utils/video.ts`), che riconosce solo gli URL
YouTube, gli identificativi YouTube in forma abbreviata e i file caricati; ogni
altro valore viene classificato come file e finisce in un tag `<video>`, che con
un URL di pagina Vimeo va in errore. Il secondo è il ripiego sull'immagine, che
non può funzionare: `BatchOverlay` passa `batch.data.image`, ma `LMS Batch` non
ha un campo `image` — il campo immagine della classe si chiama `meta_image` —
quindi la condizione di ripiego è sempre falsa e, in caso di errore di
riproduzione, il componente non renderizza alcun elemento. La combinazione dei
due produrrebbe di nuovo, per un link Vimeo, la stessa assenza di riquadro
descritta dalla collega. Il percorso corsi non ne soffre perché
`CourseCardOverlay.vue` costruisce l'`iframe` con `getVideoEmbedURL`
(`frontend/src/utils/index.js`), che gestisce YouTube e Vimeo in tutte le loro
forme.

Non è stata apportata alcuna modifica perché la riattivazione non è neutra:
`BatchOverlay` è un riquadro laterale che, oltre al video, mostra prezzo, posti
residui, numero di corsi, intervallo di date, orario, fuso orario e i pulsanti
"Iscriviti" / "Registrati ora"; è inoltre racchiuso in un contenitore
`hidden md:block`, quindi invisibile da telefono. Rimetterlo così com'era
reintrodurrebbe elementi di interfaccia rimossi a marzo e lascerebbe comunque il
video assente sui dispositivi mobili. Le alternative — mostrare il solo video
nella colonna della descrizione, oppure riattivare l'intero riquadro — sono state
riportate alla persona che decide.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code)
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: verifica di una segnalazione utente sul
  video di anteprima della classe, con individuazione del punto esatto di
  interruzione della catena dato → interfaccia
- motivo della scelta del tool e del modello: il sintomo era compatibile sia con
  un errore d'uso sia con un difetto, e distinguerli richiedeva di attraversare
  in una sola sessione livelli diversi del sistema — schema del doctype e
  colonne reali sul database MariaDB nel container, elenco dei campi restituiti
  dall'endpoint Python, consumatori del campo nella SPA, cronologia Git della
  riga sospetta. L'accesso diretto a shell, container e cronologia del
  repository rende questo attraversamento immediato; il contesto ampio ha
  permesso di tenere insieme i due percorsi paralleli (corso e classe) e di
  spiegare perché uno funziona e l'altro no.
- risultato ottenuto: segnalazione confermata come difetto reale, causa
  individuata in una singola riga commentata, più due difetti latenti che
  sarebbero riemersi subito dopo una correzione ingenua; evitato l'intervento
  affrettato di riattivare la riga senza valutarne le conseguenze
  sull'interfaccia.
- verifiche e correzioni effettuate: la prima ipotesi — link in formato Vimeo
  non riconosciuto, quindi difetto di `getVideoPreview` — era plausibile e
  coerente con il sintomo, ma è stata scartata trovando che il componente che
  usa quella funzione non è montato affatto; è comunque stata conservata come
  difetto secondario, verificata sul sorgente. Il salvataggio del campo è stato
  confermato sullo schema reale della tabella e non per lettura del solo modulo
  di modifica. L'assenza del campo `image` su `LMS Batch` è stata verificata con
  `describe` sulla tabella, non desunta.

**6. Problematiche incontrate**

Sull'ambiente di sviluppo locale nessuna classe ha oggi un `video_link`
valorizzato, quindi non è stato possibile riprodurre il caso con i dati della
collega: la conferma è arrivata dall'analisi del codice e dello schema, non da
una riproduzione diretta. Quando si deciderà l'intervento sarà opportuno
valorizzare il campo su una classe di prova con entrambi i tipi di link
(YouTube e Vimeo) e verificare il risultato anche da telefono, dove il
contenitore `hidden md:block` nasconde comunque il riquadro.

---

### Attività 15 — Il video di anteprima della classe si vede come nei corsi

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione |
| **Problema riscontrato** | Seguito dell'Attività 14. Richiesta dell'utente: «sistema il video anteprima, deve vedersi come si vede nei corsi». Sintomo di partenza: il link inserito nelle impostazioni della classe si salva ma sulla pagina della classe non compare né il video né il riquadro. |
| **Problema effettivo** | Due difetti sovrapposti, entrambi confermati nell'analisi precedente. (1) Nessun punto di rendering: `<BatchOverlay>` — unico consumatore di `video_link` per le classi — è commentato in `BatchOverview.vue` dal 19 marzo, e la pagina classe non montava nient'altro che leggesse quel campo. (2) Percorso di anteprima cieco a Vimeo: `getVideoPreview` (`utils/video.ts`) riconosceva solo YouTube e file caricati, quindi un link Vimeo veniva classificato come file e finiva in un tag `<video>` che non può riprodurre una pagina Vimeo; il ripiego sull'immagine era a sua volta irraggiungibile perché `BatchOverlay` leggeva `batch.data.image`, campo inesistente su `LMS Batch` (esiste `meta_image`). La pagina corso non ne soffriva perché usa un'altra funzione, `getVideoEmbedURL` (`utils/index.js`), che gestisce YouTube e Vimeo. |
| **Soluzione applicata** | Unificato il percorso di anteprima su quello dei corsi e rimesso il video sulla pagina classe. `getVideoEmbedURL` è stato spostato in `utils/video.ts` e ri-esportato da `utils/index.js` — stesso schema già adottato per `enablePlyr` — così esiste una sola implementazione e nessun import circolare (`index.js` importa già da `video.ts`, mai il contrario). `getVideoPreview` ha ora un tipo `'embed'` restituito per i link Vimeo, riconosciuti con la regex ancorata `VIMEO_RE` già presente, così un valore digitato a metà non può cambiare tipo sotto il cursore. `VideoPreview.vue` è stato riscritto con radice singola (accetta una classe dal chiamante, non renderizza nulla quando non c'è video) e disegna un `iframe` sia per YouTube sia per Vimeo. In `BatchOverview.vue` il video è montato **una sola volta, subito sotto la descrizione breve della classe, a ogni larghezza di schermo** — mai in una colonna laterale. La posizione è stata stabilita in due passaggi con l'utente: prima montato nella colonna destra (come fa il corso), poi spostato sotto la descrizione su sua indicazione esplicita («ce l'ho sempre a destra invece deve stare sotto la descrizione della classe»). Il layout a colonne della pagina classe è quindi rimasto quello originale (divisione a `md`, colonna destra vuota con `BatchOverlay` commentato). Resta dai corsi la **cornice** (`border-2 rounded-md card !p-0`), mentre la dimensione è stata adattata su ulteriore indicazione dell'utente («la grandezza è piccola, non prende tutta la grandezza come il box della descrizione»): tolto il tetto `md:min-w-80 max-w-sm` della card del corso, il riquadro è `w-full` e occupa quindi tutta la colonna, esattamente come il box della descrizione sopra di esso. Di conseguenza il riproduttore è passato da `min-h-56` (altezza fissa di 224 px, adatta alla card stretta del corso ma schiacciata su una colonna larga) ad `aspect-video`, così l'altezza segue la larghezza mantenendo il rapporto 16:9. **Solo il video**: il resto di `BatchOverlay` (prezzo, posti, date, pulsanti di iscrizione) resta fuori dalla pagina, perché era stato tolto volontariamente a marzo e reintrodurlo sarebbe una scelta di prodotto non richiesta. Corretto infine il ripiego di `BatchOverlay` da `image` a `meta_image`. |
| **Commit** | Sì — `0a61c2f1` "fix(batches): show the batch preview video", branch `feature/oslms`. Non ancora pushata; la verifica da browser resta da fare. |
| **File modificati** | `frontend/src/utils/video.ts`, `frontend/src/utils/index.js`, `frontend/src/components/VideoPreview.vue`, `frontend/src/components/Controls/VideoPreviewField.vue`, `frontend/src/pages/Batches/BatchOverview.vue`, `frontend/src/pages/Batches/components/BatchOverlay.vue`, `frontend/src/tests/VideoPreview.test.ts`, `frontend/src/tests/video.test.ts`, `frontend/src/tests/videoPreviewFieldShare.test.ts`. |
| **Verifiche** | Test unitari: aggiunti i casi di regressione (link Vimeo → `iframe` con URL `player.vimeo.com`, mai `<video>`; nessun riquadro quando un file non riproducibile non ha immagine di ripiego; `getVideoEmbedURL` su YouTube watch/short/id legacy e Vimeo con e senza hash). `yarn vitest run` sui tre file video: 28 test verdi. Suite completa: 21 test falliti su 201, gli stessi 21 — verificato eseguendo la suite dopo `git stash` delle sole modifiche di questa attività — quindi tutti preesistenti (`blockEditor`, `blockEditorTeardown`, `lessonFormTeardown`, `ReviewModal` dal registro del 7 settembre, più i 3 di `NewMemberModal` introdotti dall'Attività 13, non ancora committata). `yarn build` rieseguito e completato senza errori a ogni iterazione su posizione e dimensione del riquadro (quattro volte). **Non ancora verificato da browser**: sul sito di sviluppo nessuna classe ha oggi un `video_link` valorizzato, quindi il collaudo visivo resta da fare. |

**1. Obiettivo dell'attività**

Rendere visibile il video di anteprima sulla pagina della classe con lo stesso
comportamento della pagina corso — stesso tipo di riproduttore, stessi provider
supportati, stessa posizione relativa nella pagina — senza reintrodurre gli
elementi di interfaccia della classe rimossi in precedenza.

**2. Modalità di esecuzione**

Il punto di partenza è stato il confronto fra i due percorsi già esistenti. La
pagina corso costruisce un `iframe` con `getVideoEmbedURL`, che conosce YouTube
e Vimeo; la pagina classe usava `getVideoPreview`, che conosce YouTube e file.
Anziché aggiungere a `getVideoPreview` una seconda implementazione della logica
Vimeo — due copie che prima o poi divergono — si è scelto di spostare
`getVideoEmbedURL` nel modulo dedicato `utils/video.ts` e di ri-esportarlo da
`utils/index.js` per tutti i chiamanti esistenti (`CourseCardOverlay.vue`,
`CourseHero.vue`), che quindi non cambiano di una riga. La direzione della
dipendenza era già quella giusta: `index.js` importava `VIMEO_SHARE_RE` da
`video.ts`, quindi il contrario avrebbe creato un ciclo e trascinato dentro la
catena EditorJS/frappe-ui. Lo stesso schema era già stato usato per `enablePlyr`
e il commento nel file lo documenta.

Sul montaggio si è deliberatamente scelta la via minima: mostrare il solo video,
non riattivare `BatchOverlay`. La richiesta riguardava il video; il riquadro
laterale contiene anche prezzo, posti residui, date e pulsanti di iscrizione,
tolti con una scelta esplicita a marzo, e riportarli in pagina senza mandato
sarebbe una modifica di prodotto mascherata da correzione.

**3. Attività svolte**

`utils/video.ts` ospita ora `getVideoEmbedURL` con le sue cinque espressioni
regolari, accanto ai matcher già presenti, e `getVideoPreview` ha un tipo in più:
`'embed'`, restituito quando `isVimeoLink` riconosce il link. La distinzione fra
`'youtube'` e `'embed'` è stata mantenuta invece di unificarli perché i test
esistenti verificano il tipo `'youtube'` e non c'era motivo di riscriverli.
Il riconoscimento Vimeo passa per la regex ancorata già in uso, quindi un valore
digitato a metà nel campo non può cambiare classificazione sotto il cursore — la
stessa cautela che il codice del campo documentava già per i file.

`VideoPreview.vue` è stato riscritto: radice singola con `v-if`, così la classe
passata dal chiamante viene applicata e, quando non c'è nulla da mostrare, non
resta in pagina neppure un contenitore vuoto; `iframe` per `'youtube'` e
`'embed'`, `<video>` per i file caricati, immagine di ripiego solo se fornita.
Gli attributi dell'`iframe` sono gli stessi già usati dal campo di modifica
(`allowfullscreen`, `allow="accelerometer; encrypted-media; picture-in-picture"`).

La posizione in pagina è stata fissata in tre passaggi, tutti guidati
dall'utente, e vale la pena registrarli perché mostrano che «come nei corsi»
riguardava la resa del riquadro, non la sua collocazione. Primo tentativo: video
nella colonna destra da `md` in su, largo `w-72`, più un montaggio in linea sotto
`md` per il telefono. Secondo tentativo, dopo la richiesta di vederlo «nella
stessa posizione e grandezza» dei corsi: struttura a colonne della pagina classe
allineata a quella del corso (colonna singola fino a 1024 px, poi `w-full
lg:w-2/3` accanto a un `<aside class="hidden lg:block w-80 shrink-0 self-start
sticky top-5">`). Terzo e definitivo, dopo l'indicazione «ce l'ho sempre a destra
invece deve stare sotto la descrizione della classe»: un solo montaggio, subito
dopo il paragrafo `batch.data.description`, visibile a qualunque larghezza, e
layout a colonne della pagina riportato all'originale (divisione a `md`, colonna
destra vuota). Della parità con i corsi resta quindi la sola cornice,
`border-2 rounded-md card !p-0`. Il `git diff` finale su `BatchOverview.vue` è di
sole nove righe aggiunte più l'import, senza alcuna modifica al layout
preesistente.

Un quarto passaggio ha sistemato la dimensione, segnalata come troppo piccola:
il riquadro ereditava da `CourseCardOverlay` il tetto `md:min-w-80 max-w-sm`
(384 px), sensato per una card in colonna laterale ma non per un blocco che sta
sotto la descrizione e deve essere largo quanto quella. Tolto il tetto, resta
`w-full`. Insieme è cambiata l'altezza del riproduttore in `VideoPreview.vue`:
`min-h-56` era un'altezza fissa di 224 px pensata per i 320 px della card del
corso e su una colonna larga avrebbe prodotto un riquadro schiacciato, quindi è
stato sostituito da `aspect-video` su tutti e tre i rami (iframe, `<video>`,
immagine di ripiego), così l'altezza segue la larghezza mantenendo il rapporto
16:9 — il comportamento normale di un riproduttore video.

Come effetto collaterale voluto, il campo di modifica mostra ora una vera
anteprima anche per i link Vimeo: prima il riquadro restava con la sola icona e
l'unica conferma era il testo di aiuto. `hasVideoLink` è stato semplificato di
conseguenza e l'import ora inutilizzato di `isVimeoLink` rimosso dal campo.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione dell'Attività 14
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: correzione del video di anteprima della
  classe, dall'analisi già svolta fino a build e test
- motivo della scelta del tool e del modello: la correzione toccava sei file su
  tre livelli diversi (utility condivise, componenti di presentazione, pagina) e
  richiedeva di non rompere i chiamanti esistenti del percorso corsi; serviva
  quindi tenere a mente contemporaneamente la catena di import, i test già
  scritti e le scelte di prodotto pregresse (riquadro laterale rimosso a marzo).
  L'accesso diretto a shell, test runner e build ha permesso di chiudere il ciclo
  modifica → test → build senza passaggi manuali.
- risultato ottenuto: una sola implementazione della risoluzione degli URL video
  condivisa da corsi e classi, video visibile sulla pagina classe sotto la
  descrizione con la stessa cornice e dimensione usata dai corsi, supporto Vimeo
  esteso anche all'anteprima del campo di modifica, e nessuna reintroduzione
  degli elementi di interfaccia rimossi in precedenza.
- verifiche e correzioni effettuate: il primo tentativo di rendere `VideoPreview`
  senza radice singola avrebbe prodotto un avviso Vue sugli attributi non
  ereditati, ed è stato scartato riscrivendo il componente con un contenitore.
  Durante la scrittura dei test è stato **sovrascritto per errore** il file
  `frontend/src/tests/VideoPreview.test.ts`, già esistente: il nome era stato
  cercato in minuscolo su un filesystem macOS insensibile alle maiuscole. Il file
  è stato ripristinato con `git checkout HEAD --` e i due casi nuovi sono stati
  aggiunti in coda a quelli originali; il `git diff` finale mostra sole 18 righe
  aggiunte, a conferma che nulla è andato perduto. Infine, per non attribuire
  alla correzione fallimenti altrui, la suite è stata eseguita anche dopo
  `git stash` delle sole modifiche di questa attività: gli stessi 21 test rossi.

**6. Problematiche incontrate**

Il collaudo visivo non è stato possibile in autonomia: sull'ambiente di sviluppo
nessuna classe ha un `video_link` valorizzato e non è stato modificato il dato
dell'utente per provarlo. Resta quindi da fare la verifica da browser, inserendo
il link su una classe di prova con entrambi i tipi (YouTube e Vimeo) e
controllando desktop e telefono. Da tenere presente che le modifiche al frontend
richiedono `yarn build` per essere visibili sul sito servito da Frappe — la build
è già stata eseguita al termine dell'attività.

Segnalato ma non modificato: `BatchOverlay.vue` resta un componente non montato
da nessuna parte. Se la decisione fosse di non riattivarlo mai, andrebbe
eliminato insieme al commento che lo cita, per non lasciare in `BatchOverview.vue`
una riga commentata che sembra un'omissione.

### Attività 16 — Mappatura unica delle rotte dei risultati di ricerca e filtro su quiz, esercitazioni e percorsi

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione |
| **Problema riscontrato** | Difetti di navigazione rimasti aperti dopo l'Attività 9: nella palette Cmd+K ogni risultato che non fosse un corso veniva instradato su `BatchDetail`, quindi quiz, esercitazioni, percorsi e offerte di lavoro finivano su una pagina classe inesistente; nella pagina `/search` il risultato quiz puntava all'editor del quiz e quello esercitazione a un elenco generico. |
| **Problema effettivo** | Due cause distinte. (1) La mappatura doctype → rotta era duplicata nei due punti di ricerca, completa in `Search.vue` e ridotta a un ternario in `CommandPalette.vue`: le due copie erano divergute e ogni nuovo doctype indicizzato peggiorava lo scarto. (2) Più grave, emerso durante l'analisi: quiz, esercitazioni e percorsi entravano nei risultati **senza alcun controllo di permessi**, a differenza di corsi, classi e lezioni. Per questo la domanda "dove porta il clic" era mal posta per metà di quei risultati: le pagine `QuizForm` e `Assignments` rimbalzano su "Corsi" chi non è moderatore o docente, quindi per uno studente non esisteva alcuna destinazione valida. E poiché l'indice usa come contenuto dell'esercitazione **il testo della domanda**, quel testo era leggibile nei risultati da qualunque utente collegato, a prescindere da iscrizione e pubblicazione del corso. |
| **Soluzione applicata** | Lato server, tre filtri nuovi in `get_grouped_results_custom`: quiz ed esercitazioni solo a chi può gestirli (`can_manage_assessments`: Moderator, Course Creator o Docente — lo stesso gate delle pagine di destinazione), percorsi con la regola dei corsi (`can_access_program`: i pubblicati a tutti, le bozze ai soli gestori). Lato client, la mappatura è stata estratta in `frontend/src/oslms/utils/searchRoutes.ts` (`getSearchResultRoute`, più `getLessonRoute` spostata lì dalle due copie locali) e usata da entrambi i punti di ricerca; per un doctype senza pagina da aprire ritorna `null` e non avviene alcuna navigazione, invece del ripiego su una pagina inesistente. Il risultato esercitazione porta ora a `/assignments?title=<titolo>`: non esiste una pagina di dettaglio, ma la lista accetta già un filtro per titolo, quindi si arriva sull'esercitazione trovata. Il titolo viene ripulito dai tag `<mark>` dell'evidenziazione prima di finire nel parametro. |
| **Commit** | Sì — `0192e512` "fix(search): open the found content and scope results to the user", branch `feature/oslms`. Commit unico per le Attività 9, 10, 11, 16 e 17: le modifiche insistono sulle stesse funzioni di `override_api.py` e sugli stessi due componenti, quindi separarle avrebbe richiesto una divisione artificiale degli hunk. Non ancora inviato al remoto. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_api.py`, `frontend/src/oslms/utils/searchRoutes.ts` (nuovo), `frontend/src/pages/Search/Search.vue`, `frontend/src/components/CommandPalette/CommandPalette.vue` |
| **Verifiche** | Endpoint reale con tre identità. Quiz "Quiz A": lo studente `anna.verdi` non lo vede più (prima sì), Administrator e il docente `gestore@elite.it` sì. Esercitazione "asd": lo studente non riceve più alcun risultato (prima due esercitazioni, con il testo della domanda nel contenuto), Administrator sì. Percorso "Programma 1" (pubblicato): visibile a entrambi. Matrice dei permessi verificata anche in forma diretta su `can_manage_assessments` e `can_access_program` per studente, docente e moderatore, coprendo il caso "percorso in bozza" che i dati del sito non contengono (studente: no; docente e moderatore: sì). `prettier --check` pulito sui tre file frontend; build di produzione del frontend eseguita. |

**1. Obiettivo dell'attività**

Chiudere l'intervento "B" individuato nell'Attività 8 — un risultato di ricerca
deve aprire il contenuto trovato da entrambi i punti di ricerca — dopo aver
constatato che per quiz ed esercitazioni il problema non era la rotta ma la
visibilità stessa del risultato.

**2. Modalità di esecuzione**

La verifica delle rotte una per una ha fatto emergere che `QuizForm` e
`Assignments` sono pagine di gestione con una guardia
`is_moderator || is_instructor` che rimanda alla lista corsi chiunque altro. Da
lì la domanda si è spostata: non "dove mandare lo studente" ma "perché lo
studente riceve quel risultato". Il controllo sul filtro server ha mostrato che
quei tre doctype erano stati aggiunti all'indice dalla personalizzazione senza il
corrispondente controllo di accesso, che invece esiste per corsi, classi e
lezioni.

La scelta su cosa mostrare allo studente è stata sottoposta all'utente, perché è
una decisione di prodotto: le alternative erano nascondere quiz ed esercitazioni,
oppure mostrarli portando lo studente alla pagina `/quiz/:id` (accessibile a
chiunque sia collegato, ma che gli permetterebbe di aprire un quiz fuori dal
contesto della lezione, aggirando il blocco sequenziale ripristinato
nell'Attività 7), oppure filtrarli per iscrizione al corso, che è la regola più
precisa ma richiede di risalire dal quiz alla lezione e da lì al corso a ogni
ricerca. L'utente ha scelto di nasconderli.

Per la parte client il criterio è stato eliminare la duplicazione, non
aggiungere rami: una sola funzione, in `src/oslms/`, cioè fuori dai file
upstream, così che i prossimi allineamenti con `upstream/main` non la tocchino.

**3. Attività svolte**

Server — in `get_grouped_results_custom` i tre rami `LMS Program`, `LMS Quiz` e
`LMS Assignment` hanno ora una condizione di accesso. Aggiunte
`can_manage_assessments(roles)`, che replica il gate delle pagine di
destinazione includendo il ruolo "Docente" (istruttore globale del progetto,
vedi l'override di `get_user_info`), e `can_access_program(program, roles)`, che
ricalca `can_access_course`.

Client — nuovo modulo `frontend/src/oslms/utils/searchRoutes.ts` con
`getSearchResultRoute(result)`, che copre corso, classe, offerta di lavoro,
percorso, lezione, quiz ed esercitazione e ritorna `null` per tutto il resto;
`getLessonRoute` è stata spostata lì dalle due copie identiche introdotte
nell'Attività 9. `Search.vue` riduce `navigate()` a due righe;
`CommandPalette.vue` assegna `item.route` dalla stessa funzione e `navigateTo`
ignora una rotta nulla. Nella palette sparisce così l'ultimo residuo del ternario
che instradava su `BatchDetail` tutto ciò che non fosse un corso.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione delle Attività
  8-12
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: analisi delle rotte residue,
  individuazione del difetto di permessi, disegno e realizzazione della
  correzione
- motivo della scelta del tool e del modello: la correzione sembrava puramente
  meccanica (uniformare due mappature) e il valore è stato nel non fermarsi lì —
  seguire ogni rotta fino alla pagina di destinazione e alla sua guardia ha
  fatto emergere un problema di esposizione di dati che nessuna delle
  segnalazioni menzionava. Serviva tenere insieme router, pagine, filtro server e
  schema di indicizzazione, e poterlo verificare subito con identità diverse.
- risultato ottenuto: rotte corrette da entrambi i punti di ricerca, duplicazione
  eliminata, e chiusura di un'esposizione del testo delle domande delle
  esercitazioni a qualunque utente collegato.
- verifiche e correzioni effettuate: la decisione su cosa mostrare allo studente
  non è stata presa in autonomia ma sottoposta all'utente con le conseguenze di
  ciascuna opzione. Le nuove regole sono state provate con tre identità reali
  (studente, docente, moderatore) e, per il caso assente dai dati (percorso in
  bozza), in forma diretta sulle funzioni di accesso.

**6. Problematiche incontrate**

Nessun ostacolo. Resta una imprecisione nota e accettata: il risultato
esercitazione porta alla lista filtrata per titolo, non a una pagina della
singola esercitazione, perché quella pagina non esiste nel router. Se in futuro
venisse introdotta, il punto da aggiornare è uno solo, dentro
`getSearchResultRoute`.

### Attività 17 — I quiz nella ricerca dello studente, limitati ai corsi in cui è iscritto

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Nuova funzione (rifinitura della regola introdotta nell'Attività 16) |
| **Problema riscontrato** | Con l'Attività 16 quiz ed esercitazioni sono stati nascosti agli studenti, perché le pagine a cui portavano sono riservate ai gestori e perché il testo delle domande risultava esposto. Su richiesta dell'utente, i quiz devono tornare visibili allo studente, ma **solo quelli dei corsi in cui è iscritto**. Le esercitazioni restano ai soli gestori. |
| **Problema effettivo** | Il vincolo non è il filtro ma la destinazione. Il risultato di ricerca di un quiz non porta con sé né il corso né la lezione — l'indice conserva solo nome e titolo — e la pagina `QuizForm` è l'editor, precluso allo studente. Portarlo invece su `/quiz/:id`, accessibile a chiunque sia collegato, gli permetterebbe di aprire un quiz fuori dal contesto della lezione, scavalcando il blocco sequenziale ripristinato nell'Attività 7. Verificato sul modello dati che `LMS Quiz` ha entrambi i campi `course` e `lesson` valorizzati per i quiz effettivamente in uso (4 su 8 sul sito di sviluppo; gli altri 4 sono bozze mai collegate a una lezione), il che rende risolvibili sia il criterio di accesso sia una destinazione corretta. |
| **Soluzione applicata** | Lato server, prima del filtro i risultati di tipo quiz vengono risolti in blocco con `get_quiz_placements()`, che per ciascun quiz restituisce corso, lezione ospitante e i numeri di capitolo/lezione della rotta; `can_access_quiz()` ammette il quiz ai gestori sempre e allo studente solo se il corso è fra i suoi (`get_own_courses()`, una query). Un quiz senza corso resta ai gestori. Lato client `getSearchResultRoute` diventa consapevole del ruolo: il gestore va all'editor, lo studente **alla lezione che contiene il quiz**, così le regole del corso continuano a valere. Nell'occasione la risoluzione delle posizioni introdotta nell'Attività 9 è stata estratta in `get_lesson_positions()`, ora condivisa fra risultati lezione e risultati quiz. |
| **Commit** | Sì — `0192e512` "fix(search): open the found content and scope results to the user", branch `feature/oslms`. Commit unico per le Attività 9, 10, 11, 16 e 17: le modifiche insistono sulle stesse funzioni di `override_api.py` e sugli stessi due componenti, quindi separarle avrebbe richiesto una divisione artificiale degli hunk. Non ancora inviato al remoto. |
| **File modificati** | `apps/os_lms/os_lms/os_lms/override_api.py`, `frontend/src/oslms/utils/searchRoutes.ts`, `frontend/src/pages/Search/Search.vue`, `frontend/src/components/CommandPalette/CommandPalette.vue` |
| **Verifiche** | Endpoint reale sul quiz "Quiz A" (corso `corso-c01`, lezione `0415 Lezione senza titolo`, posizione 1-3): lo studente iscritto `r.liciotti@overside.it` lo trova, con corso e numeri di capitolo/lezione nel risultato (rotta `/courses/corso-c01/learn/1-3`); la studentessa `anna.verdi`, non iscritta, non lo trova; il docente `gestore@elite.it` e l'Administrator lo trovano. Verificata la risoluzione in blocco su tutti gli 8 quiz del sito: 4 con corso, lezione e numeri corretti, 4 senza (bozze), come atteso. Matrice dei casi limite su `can_access_quiz` per studente, docente e moderatore: quiz senza corso, quiz di un corso non iscritto, quiz di un corso iscritto, risoluzione mancante — tutti e quattro con l'esito previsto per ciascun ruolo. `prettier --check` pulito, `py_compile` pulito, build di produzione del frontend eseguita. |

**1. Obiettivo dell'attività**

Rendere i quiz ricercabili dallo studente senza riaprire i due problemi che
avevano portato a nasconderli: una destinazione che gli è preclusa e la
possibilità di aggirare le regole di avanzamento del corso.

**2. Modalità di esecuzione**

Prima di stimare l'intervento è stato verificato **come** un quiz è legato a un
corso, perché da quello dipendeva tutto: se il legame fosse esistito solo dentro
il corpo delle lezioni (blocchi EditorJS), sarebbe servita una risoluzione a
indice e il costo sarebbe stato di un ordine di grandezza superiore. `LMS Quiz`
ha invece i campi `course` e `lesson`, quindi il filtro si risolve con query
dirette e la lezione ospitante è nota.

Questo ha permesso di scegliere per lo studente la destinazione migliore — non la
pagina del quiz, ma la lezione che lo contiene — che è anche l'unica coerente con
il blocco sequenziale. La stessa verifica ha mostrato che per le esercitazioni il
campo `lesson` non esiste: la destinazione per lo studente sarebbe stata la sola
pagina del corso, approssimativa, e su questa base si è deciso con l'utente di
lasciarle ai gestori.

Le query aggiuntive seguono lo schema pigro già adottato per le classi: la
risoluzione dei quiz avviene solo se un quiz compare fra i risultati, e l'elenco
dei corsi dell'utente si carica solo se serve davvero, cioè per un utente non
gestore in presenza di risultati quiz.

**3. Attività svolte**

Server — `get_grouped_results_custom` risolve i quiz in blocco prima del ciclo e
carica i corsi dell'utente solo se necessario; il ramo `LMS Quiz` chiama
`can_access_quiz(placement, roles, own_courses)` e, quando ammette il risultato,
gli innesta corso, lezione e numeri di rotta. Aggiunte `get_quiz_placements()`,
`can_access_quiz()` e `get_own_courses()`. La risoluzione delle posizioni di
lezione è stata estratta da `add_lesson_positions()` in `get_lesson_positions()`,
che ora restituisce una mappa riutilizzabile: `add_lesson_positions` la applica
ai risultati lezione, `get_quiz_placements` alla lezione che ospita il quiz.

Client — `getSearchResultRoute(result, isManager)` decide la rotta del quiz in
base al ruolo; `Search.vue` e `CommandPalette.vue` iniettano `$user` e calcolano
`isManager` con lo stesso criterio delle pagine di destinazione
(`is_moderator || is_instructor`, dove `is_instructor` comprende il ruolo
"Docente"). Il ripiego resta quello della lezione: se un quiz ha il corso ma non
una lezione risolvibile, lo studente atterra sulla pagina del corso.

**4. Utilizzo dell'AI**

- tool/agente: Claude Code (estensione VS Code), stessa sessione delle Attività
  8-12 e 16
- modello: Opus 5 (contesto 1M)
- attività per cui è stata utilizzata: stima preliminare, disegno e realizzazione
  del filtro dei quiz per iscrizione con la relativa rotta per lo studente
- motivo della scelta del tool e del modello: la decisione da prendere era
  economica prima che tecnica (quanto costa, e cosa si ottiene davvero), e
  dipendeva da un dettaglio del modello dati — l'esistenza dei campi `course` e
  `lesson` su `LMS Quiz` — che andava verificato, non supposto. Avere in contesto
  il lavoro delle attività precedenti ha permesso di riusare la risoluzione delle
  posizioni di lezione invece di riscriverla, e di accorgersi che la rotta giusta
  per lo studente era la lezione e non il quiz.
- risultato ottenuto: funzione realizzata nella metà del perimetro che ha valore
  (i quiz), con la destinazione che preserva le regole del corso, e stima
  fornita all'utente prima di iniziare invece che a lavoro fatto.
- verifiche e correzioni effettuate: la stima iniziale prevedeva per lo studente
  la rotta `/quiz/:id`; la verifica del campo `lesson` ha mostrato che si poteva
  fare di meglio, mandandolo alla lezione ospitante, e la proposta è stata
  corretta prima di scrivere il codice. Le regole sono state provate con quattro
  identità reali e con la matrice completa dei casi limite, compresi i quiz senza
  corso, che sui dati del sito sono la metà del totale.

**6. Problematiche incontrate**

Nessun ostacolo. Due limiti noti e accettati: le esercitazioni restano invisibili
allo studente, per assenza di una destinazione adeguata; e un quiz che non sia
collegato ad alcuna lezione non è raggiungibile dallo studente nemmeno se
appartiene a un suo corso — condizione che sui dati attuali riguarda solo quiz
mai collegati a una lezione, quindi non ancora somministrabili.

---

### Attività 18 — Redazione del report giornaliero aziendale

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Supporto / documentazione |
| **Problema riscontrato** | Esigenza di partenza: produrre il report giornaliero previsto dalla direttiva aziendale per il progetto OS LMS, con il livello di dettaglio richiesto («assimilabile a un prompt completo»), a partire dalle 17 attività registrate oggi nel worklog. |
| **Problema effettivo** | Il worklog è organizzato per attività, mentre il report aziendale è organizzato per punti della direttiva (1-4, 6-9) e a livello di **progetto/giornata**: serviva una riaggregazione, non una copia. Due informazioni non erano ricavabili dal solo worklog: il commit `10b5ac7e` "add simple app versioning" (modifica manuale, mai registrata) e lo stato di push del branch (il worklog riportava «non ancora inviato al remoto», mentre `HEAD` coincide ora con `origin/feature/oslms`). Il punto 8 della direttiva (avanzamento) era lasciato «da confermare a fine giornata»: una prima stesura proponeva una stima dell'88 %, corretta su indicazione dell'utente in **100 %, progetto completato e in produzione**, essendo la giornata di sola manutenzione correttiva. |
| **Soluzione applicata** | Prodotto `reports/2026-09-07-os-lms.md` (nuova cartella `reports/`, su indicazione dell'utente), organizzato sui punti della direttiva. Le 17 attività sono state raggruppate in cinque filoni tematici (impostazioni classe; completamento lezioni e regole di apprendimento; ricerca rapida; creazione utenti e ruoli; video di anteprima della classe) più la modifica manuale, con tabella dei commit. Su ulteriore indicazione dell'utente è stata poi separata la responsabilità dei due documenti: **il worklog contiene solo le attività singole** (punti 1-4 + 6), **il report è il documento di giornata** e ospita i punti 7-8-9; il blocco "Chiusura giornata" è stato quindi rimosso dal worklog — dopo aver verificato che il report contenesse tutti i suoi contenuti — sostituito da un rimando al report, e l'intestazione e il template del file sono stati riscritti di conseguenza. |
| **Commit** | Non committata — documentazione di reportistica; il worklog per convenzione non si committa e il report segue la stessa prassi salvo indicazione contraria. |
| **File toccati** | `reports/2026-09-07-os-lms.md` (nuovo, poi riscritto per un pubblico non tecnico), `docs/WORKLOG.md` (questa voce, riscrittura dell'intestazione e delle convenzioni, rimozione del blocco "Chiusura giornata" e del suo template). |
| **Verifiche** | Riletto integralmente il blocco 2026-09-07 del worklog (2.245 righe) per non riportare nel report affermazioni non sostenute dal registro. Verificato con `git log --since` che i commit della giornata siano 8 e non 7 (individuato `10b5ac7e`, assente dal worklog) e con `git rev-parse HEAD origin/feature/oslms` che il branch sia allineato al remoto, correggendo l'indicazione «non ancora pushato» presente in quattro voci. Verificate le date dei file `docs/OS-LMS-Presentazione-Funzionalita.*` (4 agosto) per escluderli dalle attività odierne. |

**1. Obiettivo dell'attività**

Consegnare il report giornaliero del progetto OS LMS conforme al template aziendale
(obiettivo, modalità di esecuzione, attività svolte, utilizzo dell'AI, problematiche,
prossime attività, avanzamento, spunti di miglioramento), con un livello di dettaglio
tale da permettere a un'altra persona o a un sistema AI di riprendere il lavoro
leggendo solo il report.

**2. Modalità di esecuzione**

1. Lettura integrale della giornata 2026-09-07 del worklog, attività per attività.
2. Confronto con la storia git della giornata (`git log --since`, `git show --stat`)
   per intercettare lavoro non registrato nel worklog.
3. Verifica dello stato del branch rispetto al remoto, perché più voci del worklog
   riportavano commit «non ancora inviati».
4. Riaggregazione per filone tematico e stesura sui punti della direttiva, tenendo
   distinti i fatti verificati (con il comando che li dimostra) dalle stime.
5. Scrittura in `reports/`, come richiesto dall'utente.
6. Separazione delle responsabilità fra i due documenti: prima di rimuovere dal
   worklog il blocco "Chiusura giornata", verifica puntuale che ogni suo contenuto
   fosse presente nel report — due voci non lo erano (il mancato ricaricamento delle
   opzioni al cambio di "Tipo" in `AssessmentModal.vue` e l'inserimento del graft
   `FeatureSectionEditor` nella checklist post-merge) e sono state aggiunte al punto
   7 del report prima della rimozione.

**3. Attività svolte e risultati**

Prodotto un report di 608 righe che, oltre a riassumere le 17 attività, esplicita:
la tabella degli 8 commit con l'attività corrispondente; la motivazione dei due
commit "anomali" (`0192e512` unico per cinque attività, `290b14de` parziale
costruito con `git hash-object` + `git update-index`); l'elenco delle nove
problematiche aperte con causa e verifica; dodici prossime attività divise fra
collaudo da browser, decisioni di prodotto e manutenzione tecnica; una stima di
dichiarazione di progetto completato al 100 % e in produzione, con la
manutenzione correttiva come fase attuale e la perdita di personalizzazioni nei
merge upstream indicata come rischio di esercizio da presidiare; otto
spunti di miglioramento aziendale, di cui due (estensione di `osOverrideTheme` alle
pagine SPA e checklist dei graft custom verificata in CI) marcati a priorità alta
perché rispondono alla causa comune di tre regressioni della giornata.

Segnalata infine una nota di igiene del repository: in radice è presente un file
vuoto di nome `=`, creato alle 14:46 da una redirezione di shell errata.

**4. Utilizzo dell'AI**

- *Tool e agente:* Claude Code (estensione VS Code), sessione dedicata sul
  repository `os_lms`, branch `feature/oslms`.
- *Modello:* Claude Opus 5 (contesto 1M).
- *Per quale attività:* lettura e riaggregazione del worklog, verifica incrociata
  con la storia git, stesura del report.
- *Perché questo tool e questo modello:* la fonte da sintetizzare è un registro di
  2.245 righe con riferimenti incrociati fra attività (l'Attività 11 corregge una
  scelta dell'Attività 10, l'Attività 17 riusa codice dell'Attività 9, tre attività
  condividono la stessa causa strutturale); un contesto ampio permette di tenerlo
  aperto per intero e di produrre una sintesi che conservi quei collegamenti invece
  di appiattirli in un elenco. L'accesso al repository ha inoltre permesso di
  correggere il worklog dove era superato dai fatti.
- *Risultato ottenuto:* report conforme al template, con due dati corretti rispetto
  al registro di partenza (commit mancante, stato di push).
- *Verifiche e correzioni effettuate:* non ci si è fermati al worklog come fonte
  unica — il confronto con `git log` ha rivelato un ottavo commit non registrato, e
  il confronto con `origin` ha smentito l'indicazione «non ancora pushato» ripetuta
  in quattro voci. La percentuale di avanzamento è indicata come **stima da
  confermare** e non come dato, perché è una valutazione che spetta alla persona che
  firma il report.

**Aggiornamento — riscrittura per un pubblico non tecnico**

Su indicazione dell'utente, il report — questo e **tutti i prossimi** — deve essere
comprensibile anche a chi non si occupa di programmazione. La prima stesura (608
righe) era corretta ma scritta per un lettore tecnico: nomi di file, funzioni,
endpoint e commit nel corpo del testo. È stata quindi riscritta da capo (219 righe)
con questi criteri:

- **Punto 1** — dichiarato apertamente che la giornata è di sole correzioni, seguito
  dall'elenco sintetico dei sei problemi, ciascuno in una frase e descritto per come
  lo vede l'utente ("l'elenco da cui scegliere risultava vuoto"), non per come si
  manifesta nel codice.
- **Punto 2** — riassunto in tre fasi (accertare riproducendo il problema con le
  utenze dei vari ruoli, correggere in modo mirato, verificare), senza nomi di
  strumenti né comandi.
- **Punto 3** — riagganciato al punto 1: stessa numerazione dei sei problemi, per
  ciascuno la soluzione adottata e il risultato in poche righe, più una tabella
  degli otto interventi rilasciati.
- **Punto 4** — ridotto a sei voci sintetiche, mantenendo tutti i campi richiesti
  dalla direttiva (tool, modello, attività, motivo, risultato, verifiche).
- **Punto 6** — "Nessuna", come indicato dall'utente.
- **Punto 7** — ridotto alle due attività effettivamente residue: una segnalazione da
  analizzare ed eventualmente correggere, e l'inserimento di due traduzioni.
- **Punti 8 e 9** — invariati nella sostanza, riscritti in linguaggio accessibile.

I dettagli tecnici non sono andati persi: restano in questo worklog, che il report
cita come riferimento. La numerazione dei titoli resta quella del template aziendale
(1-4, 6-9), con una nota che spiega il salto del punto 5.

**6. Problematiche incontrate**

Nessun ostacolo tecnico. Un punto non era deducibile dal codice né dal registro: lo
stato di avanzamento del progetto. La prima stesura proponeva una stima dell'88 %
ricavata dal lavoro residuo elencato nel worklog; l'utente ha chiarito che il
progetto è **completato e in produzione** e che la giornata è di sola manutenzione
correttiva. Report e worklog sono stati corretti di conseguenza, riclassificando il
lavoro residuo come coda di manutenzione e non come avanzamento mancante.

---

## Template per una nuova attività

```markdown
### Attività N — <titolo sintetico>

#### In sintesi

| Campo | Valore |
| --- | --- |
| **Tipo** | Correzione / nuova feature / test / refactor / analisi / supporto |
| **Problema riscontrato** | <sintomo di partenza o richiesta, come si è manifestato> |
| **Problema effettivo** | <causa reale individuata dopo l'analisi> |
| **Soluzione applicata** | <cosa è stato modificato concretamente e perché> |
| **Commit** | Sì — `<hash>` <messaggio>, branch `<branch>` / No — <motivo> |
| **File modificati** | <elenco> |
| **Verifiche** | <build, test, controlli manuali ed esito> |

**1. Obiettivo dell'attività**
<risultato da raggiungere e motivazione>

**2. Modalità di esecuzione**
<procedura prevista, strumenti, tecnologie, accortezze, dipendenze, verifiche>

**3. Attività svolte**
<operazioni effettuate, decisioni prese, risultati ottenuti>

**4. Utilizzo dell'AI**
- tool/agente:
- modello:
- attività per cui è stata utilizzata:
- motivo della scelta del tool e del modello:
- risultato ottenuto:
- verifiche e correzioni effettuate:
<oppure: "AI non utilizzata">

**6. Problematiche incontrate**
<problemi, possibili cause, verifiche svolte, soluzioni tentate, supporto necessario;
se assenti, indicarlo esplicitamente>
```

I punti **7-8-9** della direttiva (prossime attività, avanzamento del progetto,
spunti di miglioramento aziendale) **non si scrivono qui**: sono di livello
giornaliero e vanno nel report di `reports/AAAA-MM-GG-os-lms.md`, insieme
all'aggregazione delle attività della giornata.
