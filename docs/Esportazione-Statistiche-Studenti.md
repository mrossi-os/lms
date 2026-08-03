# Esportazione delle statistiche degli studenti

## In due righe

Vogliamo aggiungere alla piattaforma una **nuova pagina** che permetta di scaricare le statistiche degli studenti in un file **Excel o CSV** (i formati che si aprono con Excel, Fogli Google, ecc.).
Chi la usa potrà **scegliere quali informazioni includere** nel file, e la piattaforma **ricorderà le colonne scelte** l'ultima volta.

## Come funzionerà, passo per passo

1. L'utente autorizzato apre la nuova pagina **"Esportazione statistiche"** dal menu.
2. Sceglie **che tipo di report** vuole (vedi sotto: Utenti, Corsi, Quiz, Interazioni AI).
3. Spunta le **colonne** che gli interessano (es. Email, % completamento, punteggio quiz…).
4. Se serve, applica dei **filtri** per restringere i dati (vedi il capitolo *Filtri*).
5. Clicca **Esporta** e sceglie il formato (Excel o CSV).
6. Il file viene scaricato sul suo computer.

La volta successiva ritroverà **già selezionate le stesse colonne** che aveva scelto.

## Un punto importante: i dati stanno su "livelli" diversi

Non tutte le informazioni possono stare nello stesso foglio. Alcune riguardano **la persona** (una riga per studente), altre **la persona in un corso** (una riga per ogni corso a cui è iscritta), altre ancora **ogni singolo quiz** o **ogni domanda fatta al tutor AI**.

### Perché non un unico report con tutto dentro

Verrebbe naturale pensare a un solo file con tutte le colonne insieme. In pratica non funziona, proprio perché i dati vivono su livelli diversi: per mettere tutto su un'unica riga bisognerebbe **ripetere lo stesso studente moltissime volte**.

Esempio: uno studente iscritto a 3 corsi, con 12 quiz svolti e 40 domande al tutor AI, in un file unico occuperebbe **decine di righe** — una per ogni combinazione — con nome, email e altri dati personali **ripetuti su ogni riga** e la maggior parte delle colonne **vuote** (la riga di un quiz non ha nulla da dire sulle interazioni AI, e viceversa).

Il risultato sarebbe un file enorme, pieno di duplicati e di celle vuote, difficile da leggere e da usare in Excel — e anche facile da interpretare male (ad esempio contando più volte lo stesso studente).

### La soluzione: scegliere il tipo di report

Per questo la pagina chiede prima **che tipo di report** si vuole. Ogni tipo ha il suo "livello" (una riga = uno studente, oppure uno studente in un corso, ecc.) e mostra solo le colonne che hanno senso a quel livello. Così ogni file è **pulito, coerente e senza ripetizioni inutili**. Se servono più livelli, si fanno più esportazioni, una per tipo.

| Tipo di report | Ogni riga rappresenta… | Esempi di informazioni disponibili |
|---|---|---|
| **Utenti** | uno studente | Nome, Email, Ruolo, Classe, Data di registrazione, Stato, Ultimo accesso |
| **Utenti × Corsi** | uno studente in un corso | Titolo corso, Data d'iscrizione, % di completamento, date di avvio/completamento |
| **Quiz** | uno studente in un quiz | Titolo quiz, numero di tentativi, punteggio migliore, ultimo punteggio |
| **Interazioni AI** | una domanda al tutor AI | Data/ora, corso, domanda dello studente, risposta del tutor |

## Filtri

Prima di esportare, l'utente può **restringere i dati** con dei filtri, così da scaricare solo ciò che serve (ed evitare file enormi). I filtri previsti sono:

- **Per corso** — solo gli studenti/dati relativi a uno o più corsi specifici.
- **Per classe** — solo gli studenti appartenenti a una o più classi.
- **Per studenti** — uno o più studenti selezionati singolarmente.
- **Per data di attività** — solo i dati compresi in un intervallo di date (dal… al…).

I filtri si possono **combinare** tra loro (ad esempio: un certo corso + un intervallo di date). Se non si imposta alcun filtro, l'esportazione considera **tutti** i dati disponibili per il tipo di report scelto.

## Le colonne implementate

Ecco tutte le informazioni che si potranno selezionare ed esportare, raggruppate per tipo di report. Le colonne che identificano lo studente sono presenti in tutti i report, così da poter collegare i dati.

**Report "Utenti"** — una riga per studente
- ID univoco utente
- Nome e cognome
- Email
- Ruolo
- Classe
- Data di registrazione
- Stato utente (attivo / disattivato)
- Data e ora dell'ultimo accesso

**Report "Utenti × Corsi"** — una riga per iscrizione a un corso
- ID, Nome ed Email dello studente
- ID corso
- Titolo corso
- Data di iscrizione al corso
- Stato del corso (% di completamento)
- Data di primo avvio *(approssimata)*
- Data dell'ultima attività nel corso *(approssimata)*
- Data di completamento

**Report "Quiz"** — una riga per studente e quiz
- ID e Nome dello studente
- Titolo del corso
- ID quiz / test
- Titolo quiz / test
- Numero di tentativi
- Data del primo tentativo
- Data dell'ultimo tentativo
- Punteggio dell'ultimo tentativo
- Punteggio migliore
- Punteggio massimo / percentuale

**Report "Interazioni AI"** — una riga per domanda al tutor AI
- ID studente
- Data e ora dell'interazione
- Corso
- Contenuto / lezione
- Domanda dello studente
- Risposta del tutor AI
- Contesto usato dall'AI per rispondere
- Errori del server durante la risposta
- Risposte in cui il tutor dichiara "Non posso rispondere"

> Le voci contrassegnate con *(approssimata)* sono ricavate in modo indiretto (vedi la nota in fondo al capitolo successivo).

## Le colonne escluse o non affidabili

Non tutte le informazioni della lista di riferimento possono essere esportate. Quelle che restano fuori si dividono in due gruppi, per motivi diversi.

### Non registrate dalla piattaforma

Questi dati **non esistono** da nessuna parte nel sistema: nessuno li sta misurando. Per esportarli andrebbe prima costruito lo strumento che li misura e li salva.

| Informazione | Categoria (dal file) | Perché non è disponibile | Cosa servirebbe per averla |
|---|---|---|---|
| Tempo totale trascorso in piattaforma | Utilizzo generale | La piattaforma non misura quanto tempo un utente resta collegato | Un sistema che registra l'attività dell'utente momento per momento |
| Tempo trascorso nel periodo selezionato | Utilizzo generale | Stesso motivo del punto precedente | Come sopra |
| Tempo totale dedicato al corso | Fruizione | Non si misura il tempo speso dentro un corso | Come sopra, ma distinto per corso |
| Tempo di fruizione del contenuto | Fruizione singolo contenuto | Non si misura il tempo speso su una singola lezione/video | Come sopra, ma distinto per contenuto |
| Percentuale fruita del contenuto | Fruizione singolo contenuto | Non si registra quanta parte di un video/documento è stata effettivamente vista | Tracciamento dell'avanzamento *dentro* il contenuto (es. minuti visti di un video) |
| Numero di accessi / visualizzazioni del contenuto | Fruizione singolo contenuto | Non si conta quante volte un contenuto viene aperto | Un contatore delle aperture di ogni contenuto |
| Log data e ora di accesso/uscita dal contenuto | Fruizione singolo contenuto | Non si registrano gli orari di ingresso e uscita da un contenuto | Registrazione degli eventi "entra"/"esce" |
| Data e ora di invio richiesta registrazione | Accessi | Il processo di iscrizione non salva questo momento come dato separato | Una modifica al flusso di registrazione |
| Data e ora di completamento registrazione | Accessi | Stesso motivo del punto precedente | Come sopra |

Di conseguenza **non è previsto un report dedicato ai singoli contenuti** (lezioni/video): le informazioni identificative esisterebbero, ma le parti più utili — tempo, percentuale vista, numero di aperture — rientrano proprio tra i dati non registrati qui sopra, quindi un report simile resterebbe quasi vuoto.

### Ricavabili ma non affidabili nel tempo

Questi dati si potrebbero *ricostruire* dallo "storico accessi" del sistema, ma quello storico **viene ripulito periodicamente** in automatico: i conteggi risalenti a mesi prima andrebbero persi. Per averli in modo affidabile serve salvarli in modo permanente.

| Informazione | Categoria (dal file) | Perché è escluso | Cosa servirebbe per averla |
|---|---|---|---|
| Data e ora del primo accesso | Accessi | Ricavabile dallo storico, ma lo storico viene ripulito → il dato può sparire | Salvare in modo permanente il primo accesso di ogni utente |
| Numero totale di accessi | Accessi | È un conteggio sullo storico che viene ripulito → non affidabile | Un contatore permanente degli accessi |
| Numero di giorni distinti di attività | Accessi | Stesso motivo del punto precedente | Come sopra |
| Accessi falliti | Accessi | Stesso motivo: i tentativi falliti vengono ripuliti dallo storico | Un registro permanente dei tentativi di accesso falliti |

### Nota — informazioni incluse ma con qualche limite

Alcune informazioni vengono esportate, ma è bene sapere che oggi sono un po' semplificate:

- **Stato utente**: disponibili "attivo" e "disattivato"; lo stato **"sospeso"** come terza opzione oggi non esiste (andrebbe aggiunto).
- **Data di completamento del corso**: non è salvata come dato a sé, ma si ricava in modo **affidabile** come il momento in cui lo studente ha completato l'ultima lezione (oppure, per i corsi con attestato, dalla data di rilascio del certificato). Unico limite: se al corso vengono aggiunte lezioni *dopo*, chi era al 100% torna "non completato" finché non le recupera.
- **Date di "primo avvio" e "ultima attività" nel corso**: più deboli, perché la piattaforma registra solo le lezioni *completate*, non le semplici aperture. Sono quindi delle **stime**, contrassegnate con *(approssimata)* nel capitolo precedente.
- **ID sessione** delle interazioni AI: disponibile per le *simulazioni*, ma non per le normali domande al tutor, quindi non compare nel report Interazioni AI.

## Da tenere a mente

- **Privacy**: il file conterrà dati personali degli studenti e persino le domande/risposte scambiate con il tutor AI. L'accesso resterà quindi ristretto e valuteremo di **tenere traccia di chi effettua le esportazioni**.
- **Quantità di dati**: su molti studenti e corsi il file può diventare grande; per questo sono previsti i **filtri** descritti nell'apposito capitolo, per estrarre solo ciò che serve.
