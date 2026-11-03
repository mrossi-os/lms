# Politica per l'uso responsabile dell'intelligenza artificiale in Elite

| Voce | Valore |
|---|---|
| Versione | 0.2 (bozza, da approvare) |
| Data | 2026-11-03 |
| Riferimenti | ISO/IEC 42001:2023 (sistema di gestione dell'AI); Regolamento UE 2024/1689 (AI Act); certificato ESG Solidity2 del 2026-10-28 |
| Responsabile della politica | **[da nominare]** |
| Revisione | ogni anno e a ogni cambiamento rilevante delle funzioni AI |

### Approvazione

Da compilare quando la politica viene adottata; da quel momento la versione diventa 1.0.

| Voce | Valore |
|---|---|
| Approvata da (nome e ruolo) | **[da compilare]** |
| Data di approvazione | **[da compilare]** |
| Soglie del punto 6 | **[approvate così / approvate con queste modifiche: …]** |
| Responsabile della politica nominato | **[nome e ruolo]** |
| Verificatore umano dei giudici nominato | **[nome e ruolo]** |

## 1. Scopo

Questa politica dice quali funzioni di intelligenza artificiale usa la piattaforma Elite, a cosa servono, quali limiti hanno, come vengono controllate e chi ne risponde. Vale per tutte le funzioni AI descritte al punto 3, in sviluppo, staging e produzione.

## 2. Principi

1. **L'AI aiuta, non decide da sola.** Nessuna funzione AI rilascia certificati, assegna voti ufficiali o blocca il percorso di uno studente senza una persona.
2. **Equità.** Le risposte e le valutazioni dell'AI non devono cambiare per il nome, il genere, l'origine o il modo di scrivere in italiano dello studente. Lo verifichiamo con test misurabili (punto 6).
3. **Trasparenza.** Gli studenti sanno quando parlano con un'AI, come chiede l'art. 50 dell'AI Act: il Tutor si presenta come "Assistente AI"; prima di iniziare una simulazione e nell'intestazione della chat è scritto che il cliente è interpretato da un'intelligenza artificiale; sopra il commento del Coach è scritto che è generato da un'intelligenza artificiale e che il docente può rivederlo. Per ogni giro di test registriamo modello, prompt (con la sua impronta SHA-256), parametri ed esiti.
4. **Minimo uso di dati.** All'AI va solo ciò che serve al compito: il Coach non riceve nome né profilo dello studente, solo la conversazione della simulazione; il Tutor riceve i materiali del corso e la domanda. I test usano solo dati inventati.
5. **Miglioramento continuo.** Ogni problema trovato dai test o segnalato dagli utenti diventa un'azione registrata, con un responsabile e una verifica.

## 3. Funzioni AI della piattaforma

| Funzione | Chi la usa | Cosa fa | Effetto sullo studente |
|---|---|---|---|
| **Tutor AI** | studenti | risponde alle domande sul corso usando i materiali delle lezioni (ricerca nei contenuti indicizzati) | informativo |
| **Cliente simulato** (chat e voce) | studenti | interpreta un cliente nelle simulazioni di vendita | esercitazione |
| **Coach AI** (debrief) | studenti e docenti | a fine simulazione scrive un commento con punti di forza e aree di miglioramento, e un voto per criterio e complessivo | lo studente vede solo il commento; **il voto lo vede solo il docente** |
| **Generazione di scenari e schemi di valutazione** | docenti e gestori | propone bozze di simulazioni e criteri, che una persona rivede | nessuno diretto |
| **Controlli di qualità degli scenari** | docenti e gestori | studenti simulati e giudici AI provano gli scenari prima della pubblicazione | nessuno diretto |
| **Voce** (sintesi e trascrizione) | studenti | trasforma testo in voce e voce in testo nelle simulazioni vocali | esercitazione |

Modelli in uso (configurazione di staging verificata il 2026-11-02): OpenAI `gpt-4o-mini` per Tutor, cliente simulato e Coach; OpenAI `text-embedding-3-small` per l'indicizzazione dei contenuti; Google `gemini-2.5-flash` solo come giudice nei test. La configurazione di produzione va verificata allo stesso modo prima di ogni dichiarazione (punto 9).

**Classificazione secondo l'AI Act.** Il Coach valuta l'esito di un'esercitazione in un contesto di formazione professionale: rientra potenzialmente tra i sistemi ad alto rischio dell'allegato III, punto 3. La classificazione va confermata da un consulente legale; nel frattempo applichiamo in via prudenziale le misure dei punti 5-8 (sorveglianza umana, test di equità, registrazione, gestione delle segnalazioni).

## 4. Ruoli e responsabilità

| Ruolo | Chi | Compiti |
|---|---|---|
| Responsabile della politica AI | **[da nominare]** | approva questa politica, le soglie e le eccezioni; firma l'esito di ogni giro di test; riceve le segnalazioni |
| Sviluppo | team tecnico Overside | esegue i test, mantiene il codice e il registro, propone le correzioni |
| Verificatore umano dei giudici | **[da nominare]** | controlla a mano un campione dei giudizi AI per ogni giro (circa 40 righe, foglio `_labeling.csv`) |
| Docenti | docenti dei corsi | leggono i voti del Coach, li usano solo come indicazione e possono scrivere una propria valutazione |

## 5. Sorveglianza umana

- Il voto del Coach (complessivo, per criterio, superato o no) è visibile **solo ai docenti**; lo studente riceve il commento formativo, non il voto.
- Il docente può aggiungere una propria valutazione scritta al debrief (campo "Instructor Review"), che lo studente vede.
- Il docente può **correggere il voto complessivo** del Coach (pannello "Trascrizione + Debrief"), con una motivazione obbligatoria. Il voto dell'AI resta salvato e non viene sovrascritto; si registrano chi ha corretto, quando e perché; "superato" si ricalcola sul voto del docente, che diventa il voto finale in report e medie. La correzione si può annullare tornando al voto dell'AI, e resta valida anche se il commento del Coach viene rigenerato.
- Il voto del Coach **non** è usato per certificati, attestati o voti ufficiali.
- Le bozze generate dall'AI per i docenti (scenari, criteri) diventano attive solo dopo la revisione di una persona.

## 6. Test di equità (bias)

**Cosa si misura.** Le stesse conversazioni e le stesse domande vengono presentate in cinque versioni che cambiano solo chi scrive: senza nome, nome maschile italiano, nome femminile italiano con concordanze al femminile, nome di origine straniera, italiano come seconda lingua. Si confrontano:

- per il Coach: voto complessivo, voti per criterio, quota di promossi, tono, specificità dei consigli, riferimenti all'identità, stereotipi, commenti sulla lingua;
- per il Tutor: correttezza, completezza, rifiuti, tono, utilità, riferimenti all'identità, correzioni dell'italiano, tono paternalistico.

Metodo: confronti appaiati per caso, test statistico a permutazione, intervalli di confidenza, rumore di base misurato ripetendo lo stesso caso; giudici AI di una famiglia di modelli diversa da quella giudicata, "ciechi" rispetto alla versione, con ogni confronto a coppie letto in entrambi gli ordini; campione dei giudizi verificato da una persona. Codice e dettagli: `apps/os_lms/os_lms/os_lms/ai/bias/`.

**Soglie (proposte, da approvare dal responsabile).** Per ogni versione rispetto a quella senza nome, e tra le versioni con nome:

| Misura | Soglia |
|---|---|
| Differenza media del voto del Coach | sotto 3 punti su 100 |
| Differenza di un singolo caso | entro ±10 punti |
| Test statistico | p ≥ 0,05; un p sotto 0,05 da solo va confermato con un secondo giro |
| Rifiuti del Tutor sulle domande del corso | nessuna differenza tra versioni |
| Segnalazioni dei giudici confermate dalla verifica umana | zero riferimenti discriminatori o stereotipi |

**Quando si eseguono** (cadenza approvata il 2026-11-02):

1. a ogni cambiamento del prompt del Coach o del Tutor, **anche se fatto dal pannello di amministrazione**, del modello, del fornitore o del codice che chiama l'AI;
2. ogni tre mesi;
3. prima del rinnovo della certificazione ESG (scadenza 2027-10-28);
4. dopo ogni segnalazione di trattamento ingiusto (punto 7).

Non si ripetono per ogni nuova simulazione: le nuove simulazioni seguono la lista di controllo del punto 6.1; il giro trimestrale può includere le simulazioni nuove più usate.

**Controllo prima dei rilasci.** Un rilascio che tocca uno dei cambiamenti del punto 1 della cadenza esce solo con un giro di test entro le soglie, registrato nel registro. Se un risultato è fuori soglia, il rilascio si ferma; può uscire solo con una decisione scritta e motivata del responsabile, registrata insieme a un'azione correttiva con scadenza.

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

## 10. Impatto ambientale

Ogni giro registra i token consumati (giro ufficiale del 2026-11-02: circa 3,1 milioni di token per Coach e Tutor, più i giudizi). I giudici usano modelli piccoli e i test si eseguono solo alla cadenza del punto 6, non a ogni rilascio.

## 11. Formazione

L'art. 4 dell'AI Act chiede sia a chi sviluppa un sistema AI sia a chi lo usa di assicurare che il proprio personale abbia una conoscenza sufficiente dell'AI. Per questo:

- **Overside (chi sviluppa Elite)** forma il proprio team (sviluppo, assistenza, chi configura la piattaforma) con un incontro di base all'ingresso e almeno una volta l'anno: cosa fanno le funzioni AI di Elite, i loro limiti, i risultati dei test di equità, come gestire una segnalazione. Ogni incontro si registra (data, argomenti, partecipanti) nel registro.
- **I clienti (chi usa Elite)** sono responsabili della formazione del proprio personale (gestori e docenti). Overside fornisce loro una guida d'uso: cosa fanno il Tutor e il Coach, cosa possono sbagliare, come leggere e rivedere il voto del Coach, come segnalare un trattamento ingiusto.

## 12. Punti aperti

| Punto | Stato |
|---|---|
| Nomina del responsabile della politica AI e del verificatore umano dei giudici | da decidere (sezione "Approvazione") |
| Approvazione delle soglie del punto 6 | da decidere (sezione "Approvazione") |
| Correzione della penalità del Coach sull'italiano come seconda lingua (registro, azioni A1, A5, A6) | regola di equità attiva sullo staging dal 2026-11-03 (impronta `169d9628…`, invariata dopo i deploy); da applicare in produzione quando userà il Coach; giudici sui nuovi commenti dopo la ricarica di Gemini; scala e soglia da decidere con i docenti |
| Verifica della configurazione AI di produzione | da fare, serve un accesso in sola lettura |
| Classificazione AI Act del Coach | da confermare con un consulente legale |
| Registro completo delle chiamate AI attivo nel codice (`ai/utils/llm/logger.py`, `ENABLED = True`) | da valutare: può scrivere nei log i testi degli studenti |
| Temperatura e limiti impostati dal pannello ignorati da Coach e Tutor | da valutare |
| Primo incontro di formazione AI del team Overside e guida d'uso per i clienti (punto 11) | da fare |
| Correzione del voto del Coach da parte del docente | fatta (punto 5): sullo staging dalla versione 1.16.45, provata il 2026-11-03 (registro, "Verifiche della sorveglianza umana"); in produzione con il prossimo rilascio |
