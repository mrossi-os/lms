# OS LMS — Sviluppi in programma

**Documento di presentazione**
_18 settembre 2026_

---

## In sintesi

Quattro progetti sono stati analizzati e progettati: per ciascuno sappiamo cosa si fa,
come si fa e che cosa comporta. **Nessuno è ancora stato realizzato**: questo documento
serve a condividerli prima di iniziare.

Due riguardano il modo in cui la piattaforma è costruita e mantenuta — non si vedono, ma
decidono quanto costa e quanto è sicuro ogni sviluppo successivo. Due riguardano ciò che
le persone vedono e usano.

**Le sezioni che seguono sono nell'ordine in cui si lavora**, non in ordine di importanza.

| | Progetto | Cosa cambia | Per chi | Tempo |
|---|---|---|---|---|
| **1** | Aggiornamento della base, con la sua rete di sicurezza | Recuperiamo otto versioni di arretrato senza perdere ciò che abbiamo costruito sopra | Continuità del servizio | Una settimana di verifica, dal 21 settembre |
| **2** | Editor delle lezioni | Si scrive una lezione come si scrive un documento | Docenti e redattori dei contenuti | 2 giorni lavorativi |
| **3** | Storico del tutor AI | Le conversazioni con il tutor restano e si consultano, corso per corso | Studenti e Gestori | 2 giorni lavorativi |
| **4** | Pannello di configurazione | Attivare, nascondere o regolare una funzione diventa un'operazione da pannello, non uno sviluppo | Amministratori, e di riflesso tutti | 3 giorni lavorativi |

---

## 1. Aggiornare la piattaforma di base senza perdere ciò che abbiamo costruito

**Il contesto.** OS LMS è costruita su una piattaforma open source che continua a
evolvere: periodicamente ne recepiamo gli aggiornamenti, ed è un vantaggio, perché
riceviamo miglioramenti e correzioni fatti da altri. Su quella base però abbiamo aggiunto
le nostre funzioni, e alcune di esse vivono dentro parti che l'aggiornamento riscrive.

**Il problema ha due facce.** La prima: quando arriva un aggiornamento, una nostra
modifica può essere cancellata senza che nessuno se ne accorga, e l'unico modo per
scoprirlo è riprovare l'intera piattaforma a mano o aspettare la segnalazione di un
utente. La seconda, che è la conseguenza della prima: gli aggiornamenti si sono
accumulati. L'ultimo recepimento risale all'inizio di luglio, da allora ne sono uscite
**otto**, e fino a oggi mancava perfino il collegamento tecnico al progetto originale,
senza il quale non era possibile rispondere alla domanda "che cosa c'è di nuovo". Il
collegamento è stato ripristinato e l'arretrato è stato misurato per la prima volta:
oltre cinquecento modifiche distribuite su quasi settecento file.

**Cosa cambia: due strumenti che lavorano insieme.**

*La rete di sicurezza.* Viene creato l'elenco completo delle personalizzazioni — ne sono
state censite quarantanove — e un controllo automatico che, subito dopo un aggiornamento,
risponde in pochi secondi a due domande: *le nostre modifiche ci sono ancora?* e
*funzionano ancora come devono?* Dove qualcosa è saltato, il sistema dice esattamente che
cosa e propone di rimetterlo a posto. Un esempio del secondo tipo di controllo: un
pulsante visibile solo al ruolo Gestore è una regola nostra, che la piattaforma di base
non conosce e che quindi nessun aggiornamento si preoccupa di rispettare; il controllo
verifica che sia rimasto visibile a chi deve vederlo e invisibile a tutti gli altri.

*Il percorso guidato.* L'aggiornamento affronta **una versione alla volta**, dalla più
vecchia. Per ciascuna: recepisce le novità, risolve i punti di sovrapposizione senza
cancellare le nostre personalizzazioni, legge le note della versione per capire se una
novità *sostituisce* o *rende obsoleto* qualcosa che già usiamo, e si ferma a chiedere
quando la decisione non è meccanica. A fine versione si verifica e si prosegue.

**L'elenco non dipende dalla memoria di nessuno.** Il rischio di uno strumento del genere
non è che smetta di funzionare, ma che smetta di coprire tutto: si aggiungono
personalizzazioni nuove senza registrarle e, dopo qualche mese, il controllo dà esito
positivo su metà del perimetro reale. Per questo la registrazione è automatica: quando
una personalizzazione viene aggiunta e non è stata censita, il sistema se ne accorge da
solo e lo segnala sul momento, indicando dove.

**Tre cose che l'analisi ha già fatto emergere.**

- **Le note delle versioni non sono affidabili sull'ampiezza**: una dichiara ventisei
  modifiche e ne porta duecento. Il percorso si basa quindi sul confronto reale del
  codice, e usa le note solo per capire le intenzioni di chi le ha scritte.
- **Il punto più delicato non è l'ultimo, è il secondo**: alla seconda versione cambia una
  libreria grafica di base, nella stessa versione che in passato ha già causato un
  disservizio in produzione su questo progetto. Va isolato e affrontato da solo.
- **Ventiquattro pagine sono "congelate"**: ne usiamo una nostra copia, e per queste
  dall'aggiornamento non arriva nulla — né miglioramenti né correzioni — senza che nessuno
  se ne accorga. Il percorso le rende finalmente visibili.

**Cosa non cambia.** Nessun aggiornamento è stato ancora eseguito: a oggi è stato solo
misurato e pianificato. La piattaforma in esercizio non viene toccata da questo lavoro
finché non è verificato.

**Come e quando si fa.** L'automazione è affidata a un assistente AI che esegue una
procedura scritta passo per passo, già preparata. Tre condizioni di lavoro:

- si lavora su un **ramo di lavoro separato**, dedicato solo a questo, così che la
  piattaforma in esercizio non sia mai coinvolta;
- le prove si fanno **prima in locale**, sulla postazione di sviluppo;
- solo dopo si passa all'**ambiente di prova (staging)**, e nulla arriva in produzione
  finché lì non è verificato.

Si parte **lunedì 21 settembre**, con un tempo massimo di **una settimana** per stabilire
se l'approccio regge. L'obiettivo di questa prima settimana non è completare
l'aggiornamento: è capire se il percorso guidato funziona davvero e a quali condizioni.
La durata complessiva si potrà indicare solo al termine di quella verifica.

**A che punto siamo.** La rete di sicurezza ha un piano di lavoro pronto, già provato in
laboratorio con quaranta verifiche superate, e le fasi successive sono definite. Il
percorso guidato è progettato, con la guida operativa pronta e alcune scelte ancora da
chiudere.

---

## 2. Scrivere una lezione come si scrive un documento

**Com'è oggi.** La lezione si compone a blocchi: un blocco per il testo, uno per il
titolo, uno per l'elenco, uno per l'immagine. Ogni volta che si cambia tipo di contenuto
bisogna aggiungere un blocco nuovo. Il testo, dentro il suo blocco, ha pochissime
possibilità di formattazione: chi scrive una lezione lavora in modo più scomodo di chi
scrive la descrizione di un corso, dove l'editor è invece completo.

**Cosa cambia.** Il testo della lezione si scrive nello stesso editor usato per le
descrizioni dei corsi e delle classi: titoli, grassetti, elenchi, tabelle e colori si
applicano direttamente mentre si scrive, senza creare un blocco per ciascuno. È il modo
di lavorare a cui chiunque è abituato in un programma di videoscrittura.

**Cosa non cambia.** Quiz, elaborati, esercizi di programmazione e video restano elementi
a sé, da inserire nel punto della lezione dove servono. Il video in particolare non è solo
un contenuto: è il meccanismo che registra quanto lo studente ha guardato, gli fa
riprendere dal punto in cui aveva lasciato e segna la lezione come completata — quindi
resta esattamente com'è, insieme a PDF, audio e allegati.

**E soprattutto: le lezioni già pubblicate non vengono toccate.** Nessuna conversione,
nessun rischio di perdere contenuti già scritti: le lezioni esistenti si apriranno
semplicemente nel nuovo editor.

**Come e quando si fa.** Viene subito dopo l'aggiornamento della base, e non per caso: è
l'area che quell'aggiornamento tocca più da vicino — l'ultima versione disponibile
riscrive la creazione dei quiz e corregge il salvataggio dei contenuti delle lezioni —
quindi recepirlo prima evita di rifare due volte lo stesso lavoro. Durata prevista:
**sette giorni lavorativi**.

**A che punto siamo.** Analisi di fattibilità completata e scelte di impostazione
approvate. Prima di iniziare serve il documento di dettaglio, che è il passo mancante.

---

## 3. Il tutor AI si ricorda le conversazioni

**Com'è oggi.** Lo studente può fare domande al tutor AI mentre segue un corso, ma la
conversazione vive solo nella pagina aperta: basta ricaricare o cambiare corso e sparisce.
Nulla di ciò che lo studente ha chiesto, e nulla di ciò che il tutor ha risposto, gli
resta a disposizione.

**Cosa cambia.** Le conversazioni diventano permanenti e consultabili, organizzate **per
corso**: il corso funziona da contenitore e al suo interno lo studente trova tutte e sole
le conversazioni avute su quel corso, con la possibilità di riaprirne una, continuarla,
rinominarla o metterla da parte. È il modello dei "progetti" di NotebookLM, portato dentro
il percorso formativo.

**Chi può leggere.** Solo lo studente proprietario della conversazione e il ruolo
**Gestore**, che dalla stessa pagina può scegliere lo studente di cui vedere lo storico.
Nessun altro ruolo — docenti, moderatori, valutatori — ha accesso alle conversazioni.

**Cosa non cambia.** Lo studente non cancella le conversazioni, le archivia: lo storico
resta integro. E non c'è scadenza: le conversazioni si conservano senza limite di tempo.

**Perché conta.** Da funzione di assistenza istantanea, il tutor diventa un materiale di
studio che lo studente accumula corso per corso; e dà per la prima volta visibilità su
come l'AI viene realmente usata e su che cosa gli studenti faticano davvero.

**Come e quando si fa.** Progetto autonomo, che non dipende dai due precedenti: si può
anticipare o posticipare senza conseguenze sugli altri. Durata prevista: **sette giorni
lavorativi**.

**A che punto siamo.** Analisi, progetto e piano di lavoro completati e approvati, con
verifica sui dati reali della piattaforma. Pronto per l'implementazione.

---

## 4. Un pannello unico per configurare la piattaforma

**Com'è oggi.** Ogni volta che si vuole accendere, spegnere o nascondere qualcosa — un
filtro, una scritta, un pulsante, una funzione — serve un intervento di sviluppo. Non
esiste un posto dove l'amministratore possa decidere da solo: il pannello impostazioni
contiene oggi una manciata di voci costruite una per una.

**Cosa cambia.** Nasce un sistema unico di configurazioni con tre sezioni — **Corsi**,
**Classi** e la nuova sezione **App** — pensato per arrivare a una ventina di parametri
per sezione. Non solo interruttori acceso/spento: anche numeri, testi, elenchi di voci da
mostrare o nascondere. I parametri di Corsi e Classi valgono anche per l'app mobile;
quelli della sezione App riguardano solo l'app e non toccano il sito. Il primo caso
concreto già deciso: scegliere quali filtri mostrare nell'elenco dei corsi.

**Perché conta.** Oggi ogni singola opzione è un piccolo progetto a sé. Con questo sistema
l'aggiunta di una nuova opzione diventa un'operazione minima e ripetibile, e molte
richieste che oggi richiedono uno sviluppo diventano una spunta nel pannello.

**Cosa non cambia.** Due garanzie messe nell'impostazione. La prima: ogni parametro, se
non configurato, lascia la piattaforma esattamente come è oggi — non si può rompere nulla
dimenticando di impostare qualcosa. La seconda: i parametri dicono sempre cosa *togliere*,
mai cosa *tenere*, così una funzione aggiunta in futuro compare normalmente invece di
sparire senza che nessuno l'abbia deciso.

**Come e quando si fa.** Va per ultimo non perché valga meno, ma perché il suo beneficio è
sul lavoro futuro: rende economico tutto ciò che verrà chiesto dopo, e nessuna delle
richieste in corso lo sta aspettando. Durata prevista: **sette giorni lavorativi**.

**A che punto siamo.** Progetto approvato e piano di lavoro pronto, passo per passo. Prima
di partire vanno indicate quali altre funzioni rendere configurabili, oltre al primo caso
già definito.

---

## Il calendario in breve

| | Progetto | Quando parte | Durata | Cosa serve prima |
|---|---|---|---|---|
| **1** | Aggiornamento della base | Lunedì 21 settembre | Una settimana, per stabilire se il percorso regge | Nulla: si parte |
| **2** | Editor delle lezioni | Dopo l'aggiornamento | 2 giorni lavorativi | Il documento di dettaglio |
| **3** | Storico del tutor AI | A seguire | 2 giorni lavorativi | Nulla: il piano è pronto |
| **4** | Pannello di configurazione | A seguire | 3 giorni lavorativi | L'elenco delle altre funzioni da rendere configurabili |


**Un solo vincolo di ordine.** I progetti sono indipendenti fra loro, tranne per un punto:
l'aggiornamento della base interviene sull'area delle lezioni e dei quiz, quindi va
recepito prima di rifare l'editor. Gli altri due si possono spostare nella sequenza senza
conseguenze.