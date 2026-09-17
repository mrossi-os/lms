# OS LMS — La piattaforma di formazione digitale

**Documento di presentazione funzionale**
_Versione 1.0 — agosto 2026_

---

## Indice

1. [In sintesi](#1-in-sintesi)
2. [Come è costruita la piattaforma](#2-come-è-costruita-la-piattaforma)
3. [Le funzionalità di base](#3-le-funzionalità-di-base)
4. [Le personalizzazioni OS LMS](#4-le-personalizzazioni-os-lms)
5. [Intelligenza artificiale](#5-intelligenza-artificiale)
6. [Ruoli e governance](#6-ruoli-e-governance)
7. [Reportistica e dati](#7-reportistica-e-dati)
8. [Identità visiva e comunicazione](#8-identità-visiva-e-comunicazione)
9. [Certificazione digitale verificabile](#9-certificazione-digitale-verificabile)
10. [Accesso da mobile](#10-accesso-da-mobile)
11. [Sicurezza, privacy e conformità](#11-sicurezza-privacy-e-conformità)
12. [Tecnologia e infrastruttura](#12-tecnologia-e-infrastruttura)
13. [Riepilogo: base standard vs OS LMS](#13-riepilogo-base-standard-vs-os-lms)

---

## 1. In sintesi

**OS LMS** è una piattaforma di *Learning Management* completa, pensata per erogare, gestire e
misurare la formazione aziendale e professionale.

Poggia su una base **open source consolidata e matura** (Frappe Learning), sulla quale è stato
costruito un livello di personalizzazione proprietario che aggiunge le funzionalità realmente
distintive: **assistente didattico basato su intelligenza artificiale**, **simulazioni
conversazionali con valutazione automatica**, **certificazione digitale verificabile secondo
standard internazionali**, **reportistica avanzata**, **personalizzazione completa dell'identità
visiva** e un modello di **ruoli e permessi** modellato sui processi reali del cliente.

Tre caratteristiche riassumono l'approccio del progetto:

| | |
|---|---|
| **Nessun lock-in** | La base è open source. I dati sono vostri, esportabili, su database standard. La piattaforma può essere ospitata su cloud gestito o su vostra infrastruttura. |
| **Personalizzabile senza forzature** | Le personalizzazioni convivono con la base senza modificarla: gli aggiornamenti della piattaforma open source continuano a essere recepiti, e le vostre funzionalità restano intatte. |
| **AI integrata, non un accessorio** | L'intelligenza artificiale è nativa nel percorso formativo — assiste lo studente, allena le competenze relazionali, valuta le performance e supporta il docente nella creazione dei contenuti. |

---

## 2. Come è costruita la piattaforma

La piattaforma è composta da due livelli che lavorano insieme in modo trasparente per l'utente:

```
┌──────────────────────────────────────────────────────────┐
│  LIVELLO BASE — Frappe Learning (open source)            │
│  Corsi, lezioni, classi, quiz, compiti, certificati,     │
│  lezioni live, profili, notifiche, ricerca               │
└──────────────────────────────────────────────────────────┘
                          ▲
                          │  estende, non sostituisce
┌──────────────────────────────────────────────────────────┐
│  LIVELLO OS LMS — personalizzazione proprietaria         │
│  Tutor AI · Simulazioni AI · Openbadge · Ruoli custom    │
│  Branding · Reportistica · Import massivo · Push mobile  │
│  Localizzazione italiana · Ottimizzazione mobile         │
└──────────────────────────────────────────────────────────┘
```

**Perché è importante.** Il livello OS LMS non "forka" (non duplica) la base: la **estende**.
In pratica significa che quando la comunità open source rilascia miglioramenti, correzioni di
sicurezza o nuove funzionalità, la piattaforma può recepirli — mentre le personalizzazioni
sviluppate per voi restano in un modulo separato e continuano a funzionare.

È una scelta architetturale che protegge l'investimento nel tempo: non si resta bloccati su una
versione vecchia della piattaforma per non perdere le proprie personalizzazioni.

---

## 3. Le funzionalità di base

Tutto ciò che ci si aspetta da un LMS moderno è già presente e operativo.

### 3.1 Struttura dei contenuti

I contenuti sono organizzati su **tre livelli** — Corso → Capitolo → Lezione — così che ogni lezione
erediti il contesto del capitolo in cui vive.

- **Lezioni multimediali**: testo formattato, immagini, video (YouTube, Vimeo, file caricati),
  documenti, allegati, quiz e compiti incorporati direttamente nella lezione.
- **Editor visuale a blocchi**: i contenuti si compongono trascinando blocchi, senza scrivere codice.
- **Contenuti SCORM**: è possibile caricare pacchetti SCORM prodotti con altri strumenti di authoring.
- **Programmi formativi**: più corsi possono essere raggruppati in un percorso strutturato con
  iscrizione unica.
- **Categorie e tag**: per organizzare il catalogo e alimentare la ricerca.
- **Esercizi di programmazione**: per la formazione tecnica, con esecuzione e test automatici del codice.

### 3.2 Classi e gestione dei gruppi

Le **classi** (batch) raggruppano gli studenti attorno a uno o più corsi, con una finestra temporale definita.

- Iscrizione manuale, autonoma (self-enrollment) o a pagamento.
- **Calendario didattico** con timetable e template riutilizzabili.
- **Bacheca annunci** rivolta alla classe.
- **Area discussioni** interna alla classe.
- **Raccolta feedback** di fine percorso.
- **Posti disponibili** e gestione delle liste.
- **Dashboard di classe** per il docente con progressi degli studenti.

### 3.3 Lezioni in diretta

Integrazione nativa con **Zoom** e **Google Meet**: la lezione live si crea dall'interno della
piattaforma e appare automaticamente nell'agenda degli studenti della classe, con rilevazione
automatica della presenza.

### 3.4 Valutazione

- **Quiz** con domande a scelta singola, scelta multipla, risposta aperta e risposta a input libero.
  Configurabili con: numero massimo di tentativi, punteggio di superamento, durata a tempo,
  mescolamento delle domande, estrazione di un sottoinsieme casuale, penalità per errore,
  visibilità delle soluzioni e dello storico tentativi.
- **Compiti (assignment)**: lo studente consegna un documento, un PDF, un'immagine, un URL o un testo;
  il docente valuta e restituisce un giudizio.
- **Esercizi di programmazione** con casi di test automatici.
- **Valutazioni orali/certificative**: lo studente prenota uno slot con un valutatore, che registra
  l'esito e sblocca il certificato.

### 3.5 Certificazione

- Rilascio del **certificato** al completamento del corso o della classe.
- Modello di certificato incluso, completamente personalizzabile nella grafica.
- Certificati con **data di scadenza** opzionale.
- **Pagina pubblica dei certificati** sul profilo dello studente.
- Elenco dei **partecipanti certificati**, filtrabile.

### 3.6 Utenti, profili e comunicazione

- Profilo pubblico dello studente con competenze, formazione ed esperienze professionali.
- **Notifiche in-app** e via email.
- **Ricerca globale** (command palette) su tutta la piattaforma.
- **Sistema di badge** e riconoscimenti.
- **Bacheca annunci** e **email transazionali** su tutti gli eventi rilevanti del percorso.

### 3.7 Funzioni disponibili e attivabili su richiesta

Queste funzioni fanno parte della base e possono essere abilitate se rientrano nel vostro scenario d'uso:

- **Pagamenti online** per corsi e classi a pagamento, con gestione di coupon e sconti.
- **Bacheca annunci di lavoro** con candidature integrate.

---

## 4. Le personalizzazioni OS LMS

Questa è la parte che differenzia la piattaforma da un LMS standard.

### 4.1 Percorso formativo guidato

| Funzionalità | Cosa fa |
|---|---|
| **Ordine sequenziale delle lezioni** | Impedisce di saltare avanti: la lezione successiva si sblocca solo al completamento della precedente. Attivabile per singolo corso. |
| **Quiz obbligatorio per il completamento** | Una lezione risulta completata solo se il quiz associato è stato superato. |
| **Video di benvenuto** | Al primo accesso lo studente riceve un video di onboarding, con titolo e sottotitolo configurabili, e una notifica di benvenuto personalizzata. |
| **Notifica di benvenuto** | Messaggio configurabile inviato al primo accesso. |
| **Hero della pagina corso** | Ogni corso può aprirsi con un video o un'immagine di impatto, prima della descrizione. |
| **Sezioni "in evidenza"** | Blocchi personalizzabili (icona + titolo + testo) sulla pagina del corso e della classe, per comunicare obiettivi, destinatari, prerequisiti. |
| **Durata stimata** | Ogni lezione dichiara la propria durata; la piattaforma calcola e mostra il tempo totale del corso. |
| **Tag sui contenuti** | Etichette libere su corsi e lezioni, usate anche dalla ricerca. |
| **Ricerca estesa** | La ricerca globale, che nella versione standard copre solo classi e annunci di lavoro, è stata estesa a **corsi, programmi, quiz, compiti e singole lezioni** (contenuto incluso). |
| **Catalogo filtrato per lo studente** | Lo studente vede per impostazione predefinita i corsi a cui è iscritto, senza dispersione sul catalogo completo. |

### 4.2 Lezioni in diretta — versione evoluta

La gestione delle lezioni live è stata ricostruita per risolvere i problemi tipici della formazione a distanza:

- **Doppio provider**: Zoom e Google Meet gestiti in modo omogeneo.
- **Promemoria programmabili**: per ogni lezione live si possono impostare più promemoria
  (es. 24 ore prima, 1 ora prima), inviati automaticamente.
- **Invito con allegato calendario (.ics)**: l'email di invito contiene il pulsante "Aggiungi al
  calendario" e genera un evento compatibile con Apple Calendar, Outlook, Google Calendar.
- **Sincronizzazione con Google Calendar** per i docenti che autorizzano l'integrazione.
- **Accesso controllato alla stanza**: gli studenti non ricevono il link diretto della videoconferenza.
  Il pulsante "Partecipa" passa da un controllo lato server:
  - se il docente ha avviato la lezione → si viene reindirizzati alla stanza;
  - se non è ancora iniziata → si vede una pagina di attesa che si aggiorna da sola ed entra
    automaticamente all'avvio;
  - se è terminata → si vede un messaggio dedicato.

  Questo evita che gli studenti entrino in stanza prima del docente e che il link circoli fuori
  dalla piattaforma.
- **Registrazione dell'orario reale di avvio** della sessione.

### 4.3 Importazione massiva dei dati

Un modulo di import dedicato consente di caricare grandi volumi di dati da **file Excel o CSV**:

- **Import di corsi** con struttura, capitoli e lezioni.
- **Import di iscrizioni a una classe**, con **creazione automatica degli utenti** che non esistono ancora
  (l'import standard di piattaforma non lo consente).
- **Template di esempio scaricabili** già allineati al formato atteso.
- Interfaccia completamente in italiano con anteprima e validazione prima dell'import.

### 4.4 Interfaccia in italiano e ottimizzazione mobile

- **Localizzazione italiana completa**: non solo le etichette della piattaforma, ma anche editor
  di testo, selettori di data, calendari, messaggi di sistema, email transazionali e pagine di login.
- **Interfaccia responsive rivista** per l'uso da smartphone: pagine corso e classe ricompattate,
  indice del corso riposizionato, barra "Continua il corso" fissa in basso, moduli e tabelle
  ripensati per lo schermo piccolo, caricamento immagini utilizzabile da mobile.

---

## 5. Intelligenza artificiale

L'AI è il cuore della differenziazione di OS LMS. È organizzata in **tre funzionalità distinte**,
attivabili in modo indipendente.

### 5.1 Tutor AI — l'assistente didattico sul contenuto

Uno studente che sta seguendo una lezione può aprire una **chat** e fare domande sul contenuto del corso.

**Come funziona.** La piattaforma analizza i contenuti dei corsi e ne costruisce un indice
semantico. Quando lo studente pone una domanda, il sistema recupera i passaggi più pertinenti
**dai materiali del corso** e li usa per costruire la risposta. Il tutor risponde quindi
**sui vostri contenuti**, non su conoscenza generica di internet.

**Punti chiave:**

- **Indicizzazione automatica** dei testi delle lezioni.
- **Trascrizione automatica dei video** YouTube e Vimeo: anche il parlato dei video diventa
  interrogabile dal tutor.
- **Rispetto del percorso didattico**: lo studente riceve risposte basate **solo sulle lezioni
  che ha già completato** — il tutor non anticipa contenuti non ancora sbloccati. Docenti e
  amministratori interrogano invece l'intero corso.
- **Aggiornamento automatico**: quando una lezione viene modificata, il contenuto viene
  re-indicizzato automaticamente.
- **Interazione vocale opzionale**: lo studente può dettare la domanda a voce e ascoltare la
  risposta letta ad alta voce.
- **Registro delle interazioni**: ogni domanda e ogni risposta vengono archiviate, sia per
  audit sia per capire dove gli studenti fanno più fatica (dato esportabile — vedi §7).

### 5.2 Simulazioni AI — allenare le competenze relazionali

È la funzionalità più innovativa: lo studente **conversa con un personaggio interpretato
dall'intelligenza artificiale** e viene valutato sulla sua performance.

Il personaggio è **agnostico rispetto al settore**: può essere un cliente difficile in una
simulazione di vendita, un paziente in ambito sanitario, un candidato in un colloquio, un
esaminatore, un interlocutore ostile in una negoziazione.

**L'esperienza dello studente:**

1. Dalla lezione avvia una simulazione tra quelle pubblicate per quel corso.
2. Riceve un **briefing** sulla situazione.
3. **Conversa** con il personaggio AI — in chat scritta oppure **a voce, in tempo reale**
   (conversazione parlata naturale, con rilevamento automatico dei turni di parola).
4. Al termine riceve un **debrief automatico**: punteggio complessivo, esito
   superato/non superato, valutazione su ogni criterio della griglia, **punti di forza**,
   **aree di miglioramento** e **contenuti consigliati** per colmare le lacune.
5. Il docente può aggiungere un proprio commento sopra la valutazione automatica.

**Gli strumenti del docente:**

- **Editor di scenari**: definizione del personaggio, della situazione, degli obiettivi formativi
  e delle variabili che rendono ogni sessione diversa dalla precedente.
- **Griglie di valutazione riutilizzabili**: criteri con peso, indicatori positivi e negativi,
  soglia di superamento. Una griglia può essere usata da più scenari.
- **"Compila con IA"**: la piattaforma può generare la bozza dello scenario e della griglia di
  valutazione **partendo dai contenuti del corso**. Il docente rivede e salva — nulla viene
  pubblicato automaticamente.
- **Test dello scenario prima della pubblicazione**: la piattaforma simula uno studente artificiale
  (con profili configurabili: *competente*, *principiante*, *fuori tema*, *provocatorio*), fa girare
  la conversazione e produce un report di qualità su quattro dimensioni:
  **aderenza al personaggio**, **copertura degli obiettivi formativi**, **accuratezza del debrief**
  e **calibrazione della difficoltà**. Il docente vede punteggi, motivazioni, citazioni di supporto
  e la trascrizione completa.
- **Cruscotto docente** con l'andamento delle simulazioni per corso e per studente.

**Controlli e sicurezza:**

- **Quota giornaliera per studente** configurabile, per governare i costi.
- **Difesa dalle manipolazioni**: i tentativi dello studente di forzare il comportamento dell'AI
  ("ignora le istruzioni…") vengono rilevati, il personaggio risponde restando in carattere e
  il tentativo viene segnalato al docente.
- **Sessioni immutabili** una volta chiuse: la trascrizione resta integra per finalità di audit.
- **Pseudonimizzazione** dell'identità dello studente nelle chiamate ai servizi AI esterni.

### 5.3 Governo dell'AI

- **Più fornitori supportati**: OpenAI, Google Gemini, Anthropic, DeepSeek. Si sceglie il fornitore
  e il modello **da pannello, senza interventi tecnici**, e si può definire una **catena di
  fallback** (se un fornitore è momentaneamente indisponibile, il sistema passa automaticamente
  al successivo).
- **Prompt configurabili**: tutte le istruzioni date all'AI (tutor, personaggio, generazione del
  debrief, valutatori automatici) sono **modificabili da pannello di amministrazione**, versionate
  e ripristinabili ai valori di default. Non serve un rilascio software per cambiare il
  comportamento dell'AI.
- **Attivazione selettiva**: tutor e simulazioni si accendono e spengono in modo indipendente,
  globalmente o corso per corso.
- **Tracciabilità**: ogni interazione è registrata con contesto utilizzato, esito e versione del
  prompt applicata.

---

## 6. Ruoli e governance

Ai ruoli standard della piattaforma (Studente, Docente/Instructor, Creatore di corsi, Moderatore,
Amministratore) sono stati aggiunti **tre ruoli modellati sull'organizzazione reale del cliente**.

| Ruolo | Ambito | Cosa può fare |
|---|---|---|
| **Docente** | Globale | Ruolo di insegnamento a livello di piattaforma: opera su corsi, classi e contenuti senza dover essere assegnato uno per uno. |
| **Gestore** | Globale | Profilo manageriale completo: accede alle funzioni di gestione di corsi, classi, utenti e reportistica. |
| **Valutatore** | **Limitato a una singola classe** | Assegnato dall'amministratore all'interno di una specifica classe. Vede la dashboard, le lezioni live e gli annunci **solo di quella classe**; consulta le risposte ai quiz degli studenti di quella classe; **corregge e restituisce la valutazione dei compiti** di quegli studenti. Non ha visibilità sul resto della piattaforma. |

Il ruolo **Valutatore** è particolarmente rilevante: consente di coinvolgere correttori esterni o
tutor d'aula in modo sicuro, dando loro **esattamente** ciò che serve per lavorare e **nulla di più**.
La restrizione è applicata a livello di server, non solo nascondendo pulsanti nell'interfaccia.

Altre funzioni di governance aggiunte:

- **Annunci con destinatari controllati**: lo studente vede solo gli annunci di cui è effettivamente
  destinatario.
- **Docenti nascosti agli studenti**, dove richiesto dal processo del cliente.
- **Reset dei progressi di un corso** per un singolo utente, dal pannello amministrativo
  (per far ripetere un percorso da zero).
- **Esportazione e importazione della configurazione dei permessi** di un ruolo, per replicare
  l'impostazione tra ambienti.

---

## 7. Reportistica e dati

### 7.1 Esportazione delle statistiche studenti

Una pagina dedicata consente di estrarre i dati della piattaforma in **Excel o CSV**, scegliendo
il tipo di report, le colonne e i filtri.

| Tipo di report | Ogni riga rappresenta | Informazioni disponibili |
|---|---|---|
| **Utenti / Utenti × Corsi** | uno studente, oppure uno studente in un corso | Nome, email, ruolo, classe, data di registrazione, stato dell'account, ultimo accesso, corso, data d'iscrizione, percentuale di completamento, date di avvio e completamento |
| **Quiz** | uno studente su un quiz | Corso, quiz, numero di tentativi, data primo e ultimo tentativo, ultimo punteggio, punteggio migliore, punteggio massimo |
| **Interazioni AI** | una domanda al tutor AI | Data e ora, corso, lezione, domanda dello studente, risposta del tutor, contesto usato, eventuali errori, casi di "non posso rispondere" |

**Caratteristiche:**

- **Filtri combinabili**: per corso, per classe, per singoli studenti, per intervallo di date.
- **Colonne selezionabili**, con memoria dell'ultima selezione effettuata.
- **Elaborazione in background**: le esportazioni pesanti non bloccano l'interfaccia; il file
  compare in un elenco di report scaricabili quando è pronto.
- **Accesso ristretto**: la funzione è riservata ai profili autorizzati, poiché il file contiene
  dati personali.

### 7.2 Statistiche di classe

- **Dashboard di classe** per docenti e amministratori, con l'avanzamento di ogni studente.
- **Grafici di sintesi** dei progressi (distribuzione dei completamenti).
- **Drill-down per corso e per lezione**: si può scendere fino a vedere quali lezioni ha
  completato ciascuno studente.
- **Colonne ordinabili** e barra di avanzamento per studente.
- **Esportazione dei progressi di classe** in Excel (riepilogo) o CSV (dato grezzo), riservata
  agli amministratori della classe.

### 7.3 Tracciamento accessi

La piattaforma standard conserva lo storico accessi solo per un periodo limitato, dopo il quale
i dati vengono ripuliti automaticamente. OS LMS aggiunge un **registro permanente per utente** che
accumula gli accessi (riusciti e falliti) in modo indipendente dalla pulizia dei log: il dato resta
disponibile per tutta la vita dell'account.

---

## 8. Identità visiva e comunicazione

### 8.1 Personalizzazione grafica (white label)

Un pannello dedicato — **senza toccare una riga di codice** — permette di allineare la piattaforma
all'identità visiva del cliente:

- Colori primari e secondari del brand.
- Colori di sfondo, superfici, barra laterale, barra dei menu.
- Colori dei testi e dei bordi.
- Gradienti.
- Tema chiaro e scuro.
- Logo.

La personalizzazione si applica **sia all'interfaccia dello studente sia al pannello
amministrativo**, incluse le pagine di login e registrazione.

### 8.2 Email personalizzabili

Le comunicazioni automatiche (invito alla lezione live, promemoria, annullamento, accesso tramite
link email) hanno modelli predefiniti in italiano e con il vostro branding. Ogni modello può essere
**sostituito da pannello** con una versione personalizzata, senza rilasci software.

---

## 9. Certificazione digitale verificabile

OS LMS integra la piattaforma **TrueSkill** per l'emissione automatica di **Openbadge conformi allo
standard W3C Verifiable Credentials**.

**Cosa cambia rispetto a un certificato tradizionale.** Un PDF si può falsificare e non è
verificabile da terzi. Un Openbadge è un attestato digitale **firmato crittograficamente**, che
chiunque (un datore di lavoro, un ente) può verificare in autonomia, e che lo studente può
pubblicare sul proprio profilo professionale.

**Come funziona:**

1. Si attiva l'integrazione a livello di piattaforma e si associa un **template di certificato**
   ai corsi che devono emettere l'Openbadge.
2. Quando uno studente completa il corso e riceve il certificato, il sistema emette
   **automaticamente e in background** il badge sulla piattaforma TrueSkill.
3. Lo studente trova nella propria area certificati i pulsanti per **scaricare il badge** (immagine
   con metadati incorporati) e il **certificato in formato JSON-LD** verificabile.

**Affidabilità operativa:**

- Ogni emissione è tracciata in un **registro dedicato** con esito, data e messaggi di errore.
- Un processo automatico orario **riconcilia** le emissioni rimaste in sospeso (es. per un timeout
  di rete), senza intervento manuale.
- Gli amministratori possono **rilanciare manualmente** un'emissione fallita con un pulsante.
- Il processo è **silenzioso per lo studente**: non vede nulla di anomalo finché il badge non è pronto.

---

## 10. Accesso da mobile

- **Interfaccia web completamente responsive**, ottimizzata per l'uso quotidiano da smartphone
  (vedi §4.4).
- **Notifiche push su app mobile**: ogni notifica generata dalla piattaforma (nuovo annuncio,
  lezione live imminente, compito valutato…) viene **recapitata anche come notifica push** sui
  dispositivi dello studente, tramite l'app mobile dedicata.

---

## 11. Sicurezza, privacy e conformità

| Ambito | Come è gestito |
|---|---|
| **Controllo degli accessi** | Permessi applicati **lato server**, non solo nascondendo elementi dell'interfaccia. Ogni ruolo vede esclusivamente i dati di propria competenza. |
| **Dati personali** | La piattaforma è installabile **su infrastruttura del cliente** o su cloud europeo. I dati risiedono su database standard, sempre esportabili. |
| **Dati inviati all'AI** | Ai servizi AI esterni viene inviato il contenuto necessario alla risposta; l'identità dello studente è **pseudonimizzata**. È possibile scegliere il fornitore AI in base alle proprie politiche di conformità. |
| **Tracciabilità** | Interazioni con il tutor AI, sessioni di simulazione, emissioni di certificato ed esportazioni dati sono registrate e consultabili. |
| **Sessioni immutabili** | Le sessioni di simulazione, una volta chiuse, non sono più modificabili: la trascrizione fa fede. |
| **Accesso ai dati esportati** | Le esportazioni con dati personali sono riservate ai profili autorizzati. |
| **Protezione dell'AI** | Rilevamento dei tentativi di manipolazione del comportamento dell'assistente, con segnalazione al docente. |

---

## 12. Tecnologia e infrastruttura

| | |
|---|---|
| **Base applicativa** | Frappe Framework (Python) — piattaforma applicativa open source matura, usata in produzione da migliaia di organizzazioni |
| **Interfaccia utente** | Vue 3 — applicazione web moderna, fluida, senza ricaricamenti di pagina |
| **Database** | MariaDB / MySQL |
| **Ricerca semantica AI** | Indice vettoriale su Redis |
| **Fornitori AI supportati** | OpenAI, Google Gemini, Anthropic, DeepSeek (selezionabili da pannello) |
| **Videoconferenza** | Zoom, Google Meet |
| **Certificazione digitale** | TrueSkill (Openbadge W3C) |
| **Notifiche mobile** | Firebase Cloud Messaging |
| **Installazione** | Cloud gestito oppure on-premise / cloud privato del cliente, tramite container Docker |
| **Aggiornamenti** | La piattaforma recepisce gli aggiornamenti della base open source mantenendo le personalizzazioni |

---

## 13. Riepilogo: base standard vs OS LMS

| Area | LMS standard | OS LMS |
|---|---|---|
| Struttura corsi | ✅ Corso → Capitolo → Lezione | ✅ + ordine sequenziale obbligatorio, quiz bloccante, durata, tag, hero, sezioni in evidenza |
| Classi e iscrizioni | ✅ | ✅ + import massivo da Excel con creazione utenti |
| Quiz e compiti | ✅ | ✅ + correzione delegabile a un valutatore di classe |
| Lezioni live | ✅ Zoom | ✅ Zoom **+ Google Meet**, promemoria programmati, invito con calendario .ics, accesso controllato alla stanza, sincronizzazione Google Calendar |
| Certificati | ✅ PDF | ✅ + **Openbadge W3C verificabile** (TrueSkill), emissione automatica e riconciliazione |
| Ricerca | ✅ Classi e annunci di lavoro | ✅ + corsi, programmi, quiz, compiti e **contenuto delle lezioni** |
| Ruoli | ✅ Studente, Docente, Moderatore… | ✅ + **Gestore**, **Docente globale**, **Valutatore di classe** |
| Reportistica | ✅ Statistiche di base | ✅ + **esportazioni Excel/CSV configurabili**, dashboard di classe con grafici, drill-down per lezione, tracciamento accessi permanente |
| Branding | Personalizzazione limitata | ✅ **White label completo** da pannello (colori, logo, tema chiaro/scuro, login, email) |
| Lingua | Inglese | ✅ **Italiano completo**, inclusi editor, calendari ed email |
| Mobile | Responsive di base | ✅ Interfaccia ottimizzata + **notifiche push su app** |
| **Tutor AI** | ❌ | ✅ Assistente sui contenuti del corso, con trascrizione automatica dei video e rispetto del percorso didattico |
| **Simulazioni AI** | ❌ | ✅ Role-play conversazionale in chat e **a voce**, con debrief automatico, griglie di valutazione e QA degli scenari |
| **AI per il docente** | ❌ | ✅ Generazione assistita di scenari e griglie di valutazione dai contenuti del corso |

---

## Contatti

**ELITE / Overside**
info@overside.it

---

_Documento riservato. Le funzionalità descritte riflettono lo stato della piattaforma alla data
indicata. Alcune integrazioni (videoconferenza, certificazione digitale, servizi AI, notifiche
push) richiedono la sottoscrizione dei rispettivi servizi di terze parti e una fase di
configurazione iniziale._
