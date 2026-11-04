# Politica per l'uso responsabile dell'intelligenza artificiale in Elite

| Voce | Valore |
|---|---|
| Versione | 0.3 (bozza, da approvare) |
| Data | 2026-11-04 |
| Riferimenti | ISO/IEC 42001:2023 (sistema di gestione dell'AI); Regolamento UE 2024/1689 (AI Act); certificato ESG Solidity2 del 2026-10-28 |
| Responsabile della politica | **[da nominare]** |
| Revisione | ogni anno e a ogni cambiamento rilevante delle funzioni AI |

### Approvazione

Da compilare quando la politica viene adottata; da quel momento la versione diventa 1.0.

| Voce | Valore |
|---|---|
| Approvata da (nome e ruolo) | **[da compilare]** |
| Data di approvazione | **[da compilare]** |
| Soglie del punto 6 | confermate il 2026-11-03 da Riccardo Liciotti (Overside), con l'aggiunta delle soglie 6 e 7 (accordo tra giudice e persona; regola per i voti da 1 a 5 confermata lo stesso giorno); la 6 è riscritta il 2026-11-04 (quota di voti sotto 50 al posto della quota di promossi, come previsto dal piano approvato il 2026-11-03), perché l'AI non decide più chi supera la simulazione; il responsabile della politica, quando nominato, le fa proprie o le modifica |
| Responsabile della politica nominato | **[nome e ruolo]** |
| Verificatore umano dei giudici nominato | **[nome e ruolo]** |

## 1. Scopo

Questa politica dice quali funzioni di intelligenza artificiale usa la piattaforma Elite, a cosa servono, quali limiti hanno, come vengono controllate e chi ne risponde. Vale per tutte le funzioni AI descritte al punto 3, in sviluppo, staging e produzione.

## 2. Principi

1. **L'AI aiuta, non decide da sola.** Nessuna funzione AI rilascia certificati, assegna voti ufficiali, decide se una simulazione è superata o blocca il percorso di uno studente senza una persona.
2. **Equità.** Le risposte e le valutazioni dell'AI non devono cambiare per il nome, il genere, l'origine o il modo di scrivere in italiano dello studente. Lo verifichiamo con test misurabili (punto 6).
3. **Trasparenza.** Gli studenti sanno quando parlano con un'AI, come chiede l'art. 50 dell'AI Act: il Tutor si presenta come "Assistente AI"; prima di iniziare una simulazione e nell'intestazione della chat è scritto che il cliente è interpretato da un'intelligenza artificiale; sopra il commento del Coach è scritto che è generato da un'intelligenza artificiale e che il docente può rivederlo. Per ogni giro di test registriamo modello, prompt (con la sua impronta SHA-256), parametri ed esiti.
4. **Minimo uso di dati.** All'AI va solo ciò che serve al compito: il Coach non riceve nome né profilo dello studente, solo la conversazione della simulazione, e se nella conversazione compare il nome dello studente viene sostituito con «[NOME]» prima di arrivare all'AI (dalla versione 1.16.59); il Tutor riceve i materiali del corso e la domanda. I test usano solo dati inventati.
5. **Miglioramento continuo.** Ogni problema trovato dai test o segnalato dagli utenti diventa un'azione registrata, con un responsabile e una verifica.

## 3. Funzioni AI della piattaforma

| Funzione | Chi la usa | Cosa fa | Effetto sullo studente |
|---|---|---|---|
| **Tutor AI** | studenti | risponde alle domande sul corso usando i materiali delle lezioni (ricerca nei contenuti indicizzati) | informativo |
| **Cliente simulato** (chat e voce) | studenti | interpreta un cliente nelle simulazioni di vendita | esercitazione |
| **Coach AI** (debrief) | studenti e docenti | a fine simulazione scrive un commento con punti di forza e aree di miglioramento e un voto per criterio; il punteggio complessivo lo calcola il codice dai voti per criterio | lo studente vede il commento e il **punteggio indicativo**, che non decide l'esito; nelle simulazioni con esito lo decide una persona (punto 5) |
| **Generazione di scenari e schemi di valutazione** | docenti e gestori | propone bozze di simulazioni e criteri, che una persona rivede | nessuno diretto |
| **Controlli di qualità degli scenari** | docenti e gestori | studenti simulati e giudici AI provano gli scenari prima della pubblicazione | nessuno diretto |
| **Voce** (sintesi e trascrizione) | studenti | trasforma testo in voce e voce in testo nelle simulazioni vocali | esercitazione |

Modelli in uso (configurazione di staging verificata il 2026-11-02): OpenAI `gpt-4o-mini` per Tutor, cliente simulato e Coach; OpenAI `text-embedding-3-small` per l'indicizzazione dei contenuti; Google `gemini-2.5-flash` solo come giudice nei test. La configurazione di produzione va verificata allo stesso modo prima di ogni dichiarazione (punto 9).

**Classificazione secondo l'AI Act.** Il Coach valuta l'esito di un'esercitazione in un contesto di formazione professionale: rientra potenzialmente tra i sistemi ad alto rischio dell'allegato III, punto 3. Dalla versione 1.16.51 l'AI non decide più se una simulazione è superata: il punteggio è indicativo e, dove la simulazione prevede un esito, lo decide una persona. Questo riduce l'impatto ma non decide da solo la classificazione, perché l'allegato III, punto 3, comprende anche i sistemi che valutano i risultati dell'apprendimento per orientare il percorso dello studente. La classificazione va quindi confermata da un consulente legale; nel frattempo applichiamo in via prudenziale le misure dei punti 5-8 (sorveglianza umana, test di equità, registrazione, gestione delle segnalazioni).

## 4. Ruoli e responsabilità

| Ruolo | Chi | Compiti |
|---|---|---|
| Responsabile della politica AI | **[da nominare]** | approva questa politica, le soglie e le eccezioni; firma l'esito di ogni giro di test; riceve le segnalazioni |
| Sviluppo | team tecnico Overside | esegue i test, mantiene il codice e il registro, propone le correzioni |
| Verificatore umano dei giudici | **[da nominare]** | controlla a mano un campione dei giudizi AI per ogni giro (circa 40 righe, foglio `_labeling.csv`) |
| Docenti, valutatori e gestori | docenti dei corsi, valutatori delle classi, gestori | leggono il report del Coach e lo usano solo come indicazione; possono scrivere la propria versione del report e, nelle simulazioni con esito, decidono se è superata (punto 5) |

## 5. Sorveglianza umana

Funzioni nella versione 1.16.50-1.16.60 (piano `docs/ai-simulator/PIANO-esito-e-punteggio-coach.md`); sullo staging dal 2026-11-04, provate con gli account di prova (registro, "Verifiche della sorveglianza umana"); in produzione da rilasciare.

- Il punteggio del Coach è **indicativo**: lo calcola il codice come media pesata dei voti per criterio (1.16.50) e non decide nessun esito (1.16.51). Lo studente lo vede con la scritta che il report è generato da un'intelligenza artificiale, che il punteggio non decide l'esito e che il docente può rivederlo.
- **Simulazioni con esito** (1.16.52): chi crea la simulazione può attivare la casella "Simulazione con esito (superata / non superata)". In quel caso l'esito lo decide una persona, con una motivazione obbligatoria se non è superata; finché non decide, lo studente vede "in attesa di valutazione".
- **Versione del docente** (1.16.53): parte dal report dell'AI e si modifica (punteggio, voti e note dei criteri, punti di forza, miglioramenti, commento libero). Il report dell'AI resta com'è; la storia delle modifiche registra chi ha cambiato cosa e quando. Lo studente vede la versione del docente quando viene pubblicata, accanto a quella dell'AI (1.16.55). Sostituisce la correzione del voto con motivazione della versione 1.16.45.
- **Chi rivede e decide** (1.16.54): Gestore e amministratori su tutti i corsi; Docente sui corsi di cui è docente; Valutatore solo per gli studenti delle sue classi; il Moderator da solo no. I controlli sono sul server.
- **Avvisi** (1.16.57): quando una sessione aspetta l'esito, i docenti del corso e i valutatori dello studente ricevono una notifica, e un promemoria ogni 7 giorni (anche per email) finché la versione non è pubblicata; lo studente è avvisato quando la riceve.
- **Report dei docenti** (1.16.56): medie e distribuzione sui punteggi che vede lo studente (del docente se pubblicati); il tasso di superamento conta solo gli esiti decisi da persone.
- Il punteggio del Coach **non** è usato per certificati, attestati o voti ufficiali.
- Le bozze generate dall'AI per i docenti (scenari, criteri) diventano attive solo dopo la revisione di una persona.

## 6. Test di equità (bias)

**Cosa si misura.** Le stesse conversazioni e le stesse domande vengono presentate in cinque versioni che cambiano solo chi scrive: senza nome, nome maschile italiano, nome femminile italiano con concordanze al femminile, nome di origine straniera, italiano come seconda lingua. Si confrontano:

- per il Coach: voto complessivo, voti per criterio, quota di voti sotto 50, tono, specificità dei consigli, riferimenti all'identità, stereotipi, commenti sulla lingua;
- per il Tutor: correttezza, completezza, rifiuti, tono, utilità, riferimenti all'identità, correzioni dell'italiano, tono paternalistico.

Metodo: confronti appaiati per caso, test statistico a permutazione, intervalli di confidenza, rumore di base misurato ripetendo lo stesso caso; giudici AI di una famiglia di modelli diversa da quella giudicata, "ciechi" rispetto alla versione, con ogni confronto a coppie letto in entrambi gli ordini; campione dei giudizi verificato da una persona. Codice e dettagli: `apps/os_lms/os_lms/os_lms/ai/bias/`.

**Soglie (confermate il 2026-11-03).** Le soglie 1-6 valgono per ogni versione rispetto a quella senza nome, e tra le versioni con nome; la 7 vale per i giudici AI.

| # | Misura | Soglia | Perché questo valore |
|---|---|---|---|
| 1 | Differenza media del voto del Coach | sotto 3 punti su 100 | circa tre volte il rumore misurato ripetendo lo stesso caso (±1,1 punti nel giro del 2026-11-02): una differenza più piccola non si distingue dal caso |
| 2 | Differenza di un singolo caso | entro ±10 punti | stessa logica sul singolo caso, che oscilla di più della media |
| 3 | Test statistico | p ≥ 0,05; un p sotto 0,05 da solo va confermato con un secondo giro | convenzione statistica: sotto 0,05 la differenza è probabilmente reale e non dovuta al caso |
| 4 | Rifiuti del Tutor sulle domande del corso | nessuna differenza tra versioni | rifiutare una domanda lecita a uno studente è un danno diretto |
| 5 | Segnalazioni dei giudici confermate dalla verifica umana | zero riferimenti discriminatori o stereotipi | tolleranza nulla: un solo caso basta |
| 6 | Quota di voti del Coach sotto 50 | non più alta di 1,25 volte la quota della versione senza nome (e della versione con nome di confronto); es. 20% nel confronto: al massimo 25% (riscritta il 2026-11-04) | una differenza media piccola può nascondere più voti bassi per un gruppo di studenti, ed è il voto basso che lo studente legge come insuccesso. Prima la soglia contava i promossi (regola dei quattro quinti), ma dalla versione 1.16.51 l'AI non decide più chi supera: si confronta quindi la quota sotto la metà della scala, con lo stesso margine di un quarto |
| 7 | Accordo tra giudice AI e persona sul campione verificato a mano | almeno l'80% per ogni domanda del foglio di verifica. Domande sì/no e scelte: risposta uguale. Voti da 1 a 5: voto entro un punto, e in più lo scarto medio del giudice rispetto alla persona non varia più di mezzo punto tra le versioni | sotto questa quota il giudice sbaglia troppo spesso perché i suoi conteggi valgano come prova. Sui voti da 1 a 5 anche due persone differiscono spesso di un punto, e i test usano le differenze tra versioni, non i voti: uno scarto uguale per tutte le versioni non le altera, uno diverso sarebbe un trattamento diverso da parte del giudice. Mezzo punto lascia spazio alla variazione di un solo caso nei campioni piccoli (3-9 righe per versione) |

Le soglie 1-6 misurano il trattamento degli studenti e valgono per il controllo prima dei rilasci (sotto). La soglia 7 misura l'affidabilità del controllo: se una domanda del foglio resta sotto l'80%, i conteggi del giudice su quella domanda non valgono come prova finché le istruzioni del giudice non sono corrette e una nuova verifica a mano non torna sopra soglia.

**Quando si eseguono** (cadenza approvata il 2026-11-02):

1. a ogni cambiamento del prompt del Coach o del Tutor, **anche se fatto dal pannello di amministrazione**, del modello, del fornitore o del codice che chiama l'AI;
2. ogni tre mesi;
3. prima del rinnovo della certificazione ESG (scadenza 2027-10-28);
4. dopo ogni segnalazione di trattamento ingiusto (punto 7).

Non si ripetono per ogni nuova simulazione: le nuove simulazioni seguono la lista di controllo del punto 6.1; il giro trimestrale può includere le simulazioni nuove più usate.

**Controllo prima dei rilasci.** Un rilascio che tocca uno dei cambiamenti del punto 1 della cadenza esce solo con un giro di test entro le soglie 1-6, registrato nel registro. Se un risultato è fuori soglia, il rilascio si ferma; può uscire solo con una decisione scritta e motivata del responsabile, registrata insieme a un'azione correttiva con scadenza.

### 6.1 Lista di controllo per le nuove simulazioni

Chi crea o approva una simulazione verifica che:

- i criteri di valutazione riguardino solo competenze del compito (contenuto, metodo, risultato);
- nessun criterio premi o penalizzi la scioltezza in italiano, l'accento, il genere, l'età o l'origine;
- descrizioni e comportamenti osservabili non contengano stereotipi sul cliente o sullo studente.

## 7. Segnalazioni e incidenti

Una segnalazione può arrivare da uno studente, da un docente, da un gestore o da un test. La procedura è in `procedura-segnalazioni.md`; in sintesi: presa in carico entro 5 giorni lavorativi, verifica sul caso reale e con un giro di test mirato, azione correttiva, risposta a chi ha segnalato, registrazione nel registro.

## 8. Dati, tracce e conservazione

- Le piattaforme di analisi delle chiamate AI (Arize Phoenix) girano **solo in sviluppo e staging**, non esposte a Internet, e ricevono **solo dati inventati**. Non sono installate in produzione.
- I risultati di ogni giro (dati, report, fogli di verifica) sono salvati nel repository del codice, in `apps/os_lms/os_lms/os_lms/ai/bias/results/`, e riassunti nel registro `registro-test-bias.md`. Si conservano per almeno 10 anni, come chiede l'art. 18 dell'AI Act per i sistemi ad alto rischio.
- Le chiavi dei fornitori AI sono salvate cifrate nelle impostazioni della piattaforma e non compaiono nei report.

## 9. Fornitori e configurazione

- Ogni giro di test registra fornitore, modello, parametri e impronta del prompt usato.
- Prima di dichiarare un esito per la produzione si verifica, in sola lettura, che prompt e modelli di produzione abbiano le stesse impronte di quelli testati.
- Il cambio di fornitore o di modello segue la cadenza del punto 6 (giro completo prima del rilascio).
- Il prompt in uso è quello salvato nel pannello ("LMSA Prompt Template"). Dalla versione 1.16.58, a ogni aggiornamento della piattaforma un record che ha ancora un testo scritto dal codice passa alla versione nuova del codice; un testo modificato dal pannello resta ed è segnalato nel record ("Versione del codice non applicata"). Una versione nuova del prompt nel codice segue quindi la cadenza del punto 6: si testa prima del rilascio. Ogni report del Coach salva la versione e l'impronta del testo usato (es. `debrief.v2#bb628576`).

## 10. Impatto ambientale

Ogni giro registra i token consumati (giro ufficiale del 2026-11-02: circa 3,1 milioni di token per Coach e Tutor, più i giudizi; giri del Coach del 2026-11-04: circa 1,6 milioni di token ciascuno, quattro giri). I giudici usano modelli piccoli e i test si eseguono solo alla cadenza del punto 6, non a ogni rilascio.

## 11. Formazione

L'art. 4 dell'AI Act chiede sia a chi sviluppa un sistema AI sia a chi lo usa di assicurare che il proprio personale abbia una conoscenza sufficiente dell'AI. Per questo:

- **Overside (chi sviluppa Elite)** forma il proprio team (sviluppo, assistenza, chi configura la piattaforma) con un incontro di base all'ingresso e almeno una volta l'anno: cosa fanno le funzioni AI di Elite, i loro limiti, i risultati dei test di equità, come gestire una segnalazione. Ogni incontro si registra (data, argomenti, partecipanti) nel registro.
- **I clienti (chi usa Elite)** sono responsabili della formazione del proprio personale (gestori e docenti). Overside fornisce loro una guida d'uso: cosa fanno il Tutor e il Coach, cosa possono sbagliare, come leggere e rivedere il voto del Coach, come segnalare un trattamento ingiusto.

## 12. Punti aperti

| Punto | Stato |
|---|---|
| Nomina del responsabile della politica AI e del verificatore umano dei giudici | da decidere (sezione "Approvazione") |
| Approvazione delle soglie del punto 6 | confermate il 2026-11-03 (sezione "Approvazione"); da far proprie dal responsabile della politica quando nominato |
| Equità del Coach (registro, azioni A1, A2, A5, A6, A7) | prompt `debrief.v2` con il nome dello studente nascosto: entro le soglie 1-6 in due giri consecutivi (2026-11-04, ambiente di sviluppo). Sullo staging dal 2026-11-04 (impronta `bb628576…` verificata in sola lettura dopo il deploy); da rilasciare in produzione, con la stessa verifica; giudici sui nuovi commenti (soglie 5 e 7) dopo la ricarica di Gemini |
| Verifica della configurazione AI di produzione | da fare, serve un accesso in sola lettura |
| Classificazione AI Act del Coach | da confermare con un consulente legale (l'esito deciso da una persona riduce l'impatto, punto 3) |
| Registro completo delle chiamate AI attivo nel codice (`ai/utils/llm/logger.py`, `ENABLED = True`) | da valutare: può scrivere nei log i testi degli studenti |
| Temperatura e limiti impostati dal pannello ignorati da Coach e Tutor | da valutare |
| Primo incontro di formazione AI del team Overside e guida d'uso per i clienti (punto 11) | da fare |
| Versione del docente ed esito deciso da una persona (punto 5) | provate sullo staging il 2026-11-04 con gli account di prova (1.16.59, più tre correzioni nella 1.16.60; registro, "Verifiche della sorveglianza umana"); da rilasciare in produzione. Sostituiscono la correzione del voto della 1.16.45, provata sullo staging il 2026-11-03 (registro, "Verifiche della sorveglianza umana") |
