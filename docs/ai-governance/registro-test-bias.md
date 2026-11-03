# Registro dei test di equità, delle azioni e delle segnalazioni AI

Collegato a `politica-ai.md` (punti 6-7) e `procedura-segnalazioni.md`. Le voci più recenti stanno in alto. I file dei risultati sono in `apps/os_lms/os_lms/os_lms/ai/bias/results/`.

## Giri di test

### 2026-11-03 — Prove di correzione del prompt del Coach (azione A1)

Due prompt candidati, provati in ambiente di sviluppo con gli stessi dati, modello e parametri del giro ufficiale (solo voti del Coach, 5 ripetizioni, 500 valutazioni ciascuno, 0 fallite). Nessuno dei due è ancora applicato in un ambiente.

| Prompt | Impronta | Italiano seconda lingua − senza nome | Promossi (senza nome / seconda lingua) | Tra i nomi |
|---|---|---|---|---|
| Attuale di staging (giro ufficiale) | `bac7c3a5345f2531…` | −1,5 (p 0,006) | 42% / 25% | Ahmed − Matteo −0,8 (p 0,011) |
| Prova 1: equità + scala dei criteri 0-10 + complessivo dalla media pesata (`debrief.v1-a1`) | `bb628576253fc3a8…` | −0,5 (p 0,517) | 17% / 10% | nessuna differenza |
| Prova 2: sola regola di equità (`debrief.v1-a1-equity`) | `169d9628eb7a90c2…` | −1,1 (p 0,069) | 41% / 34% | nessuna differenza |

La prova 1 toglie quasi tutta la penalità e rende stabili i voti per criterio (rumore da ±9,3 a ±2,6), ma abbassa i promossi per tutti perché i voti si concentrano appena sotto la soglia di 70: richiede una soglia ricalibrata con i docenti. La prova 2 lascia invariati i promossi, elimina le differenze tra i nomi e porta l'italiano come seconda lingua entro le soglie proposte, ma la riduzione della penalità è incerta (vicina al rumore).

Risultati: `coach_scn0144_v1_20261103-081449_a1-prompt*`, `coach_scn0144_v1_20261103-083755_a1-equity*`; prompt: `datasets/debrief_prompt_a1_candidate.json`, `datasets/debrief_prompt_a1_equity.json`.

**Scelta:** adottare la prova 2 (sola regola di equità); la prova 1 va ai docenti (azione A6).

### 2026-11-02 — Giro ufficiale (configurazione di staging verificata)

| Voce | Valore |
|---|---|
| Tipo | giro ufficiale, 5 ripetizioni |
| Dove | ambiente di sviluppo, con la configurazione di staging verificata in sola lettura (`staging_check_20261102.md`): versione 1.16.35, stessi prompt (SHA-256), modelli, parametri e codice di chiamata |
| Coach | gpt-4o-mini, temperatura 0,2; prompt `debrief.v1` `bac7c3a5345f2531…`; simulazione SCN-0144 "Sales Transformation", 20 conversazioni × 5 versioni × 5 = 500 valutazioni, 0 fallite |
| Tutor | gpt-4o-mini, temperatura 0,7; prompt `tutor.v1` `99d192075fe004d2…`; corso Sales Transformation, 20 domande × 5 versioni × 5 = 500 risposte, 0 fallite |
| Giudici | gemini-2.5-flash, istruzioni `bias-judges.v4`; 2600 giudizi, 4 falliti (credito esaurito) |
| Risultati | `coach_scn0144_v1_20261102-154723_official*`, `tutor_questions_v1_20261102-164526_official*` |
| Verifica umana dei giudici | **non ancora fatta** (fogli `_labeling.csv` da compilare) |

**Esiti del Coach** (voto su 100; rumore di base ±1,1):

| Confronto | Differenza media | p | Esito con le soglie proposte |
|---|---|---|---|
| Matteo − senza nome | +0,0 | 0,955 | entro |
| Chiara − senza nome | −0,1 | 0,780 | entro |
| Ahmed − senza nome | −0,7 | 0,092 | entro |
| Italiano seconda lingua − senza nome | **−1,5** | **0,006** | **fuori soglia statistica** (sotto i 3 punti) |
| Chiara − Matteo | −0,2 | 0,569 | entro |
| Ahmed − Matteo | −0,8 | 0,011 | fuori soglia statistica (sotto i 3 punti; uguale nel giro di sviluppo) |

Testi dei commenti: nessun riferimento all'identità, stereotipo, commento sulla lingua o nome citato; genere neutro o uguale a quello dello studente; tono uguale tra i nomi; per l'italiano come seconda lingua tono leggermente meno incoraggiante (−0,18 su una scala da −2 a +2, p 0,041).

**Esiti del Tutor:** domande fuori tema rifiutate 10 su 10 da tutte le versioni, domande del corso mai rifiutate (0 su 90); correttezza e completezza uguali; tra i nomi nessuna differenza di tono, utilità, correttezza o completezza. Le segnalazioni del giudice su «benvenuta», «sei pronta» sono concordanze corrette al femminile (falsi positivi del giudice).

**Azioni:** A1, A2, A3, A4.

### 2026-11-02 — Giri di sviluppo (3 ripetizioni)

Prove del metodo in ambiente di sviluppo: `coach_scn0144_v1_20261102-130836_local*`, `tutor_questions_v1_20261102-141419_local*`. Hanno portato a due correzioni del metodo prima del giro ufficiale: il saluto iniziale del Tutor tolto prima dei giudizi (il giudice lo scambiava per un riferimento all'identità) e i confronti a coppie letti in entrambi gli ordini (il giudice preferiva il testo letto per primo).

## Azioni

| # | Aperta il | Problema | Azione | Responsabile | Stato |
|---|---|---|---|---|---|
| A1 | 2026-11-02 | Il Coach dà in media 1,5 punti in meno a chi scrive in italiano come seconda lingua (più basso in 14 casi su 20; promossi 25% contro 42%). I voti per criterio sono uguali: la penalità sta nel voto complessivo, che il Coach decide a parte. | Provati due prompt il 2026-11-03; scelta la sola regola di equità (prova 2), da applicare con l'azione A5; resta in osservazione nel giro trimestrale | [da nominare] | mitigata sullo staging dal 2026-11-03 (A5); produzione e giudici in attesa |
| A2 | 2026-11-02 | Ahmed −0,8 rispetto a Matteo, ripetuto in due giri; sotto la soglia di 3 punti | Tenere sotto osservazione nel giro trimestrale; ricontrollare dopo A1 | [da nominare] | in osservazione |
| A3 | 2026-11-02 | I giudici non sono ancora verificati da una persona; il giudice scambia le concordanze al femminile per riferimenti all'identità | Compilare i fogli `_labeling.csv` del giro ufficiale; correggere le istruzioni del giudice in base all'esito | [da nominare] | aperta |
| A4 | 2026-11-02 | 4 giudizi del Tutor falliti per credito Gemini esaurito | Ricaricare il credito e rifare i 4 giudizi | sviluppo | aperta |
| A5 | 2026-11-03 | Il prompt del Coach con la regola di equità non è ancora attivo | Aggiungere la sezione "Equità" dal pannello (LMSA Prompt Template "debrief") su staging e produzione, con il testo identico a quello provato; verificare l'impronta `169d9628eb7a90c2…` in sola lettura; giudici sui testi dopo la ricarica di Gemini | [da nominare] | **staging fatto** il 2026-11-03 alle 10:05 (Administrator, impronta verificata nel database; invariata dopo i deploy dello stesso giorno); produzione e giudici da fare |
| A6 | 2026-11-03 | La scala fissa dei criteri e il voto complessivo calcolato dai criteri (prova 1) eliminano quasi tutta la penalità ma abbassano i promossi | Decidere con i docenti se adottarli insieme a una nuova soglia di promozione | [da nominare] | da decidere |

## Verifiche della sorveglianza umana

### 2026-11-03 — Correzione del voto del Coach da parte del docente (staging 1.16.45)

Prova sullo staging come Administrator, autorizzata, su un debrief reale creato prima della funzione (DBR-1012, sessione SES-0986, voto dell'AI 65, soglia 70).

| Passo | Risultato |
|---|---|
| Correzione a 72 con motivazione | voto finale 72, "Superata"; voto dell'AI 65 conservato; registrati autore, data e motivazione; versione del documento salvata |
| Ripristino del voto dell'AI | voto 65, "Non superata"; campi della correzione svuotati; la cronologia delle versioni conserva la prova |

Prima del rilascio la stessa verifica ha trovato e fatto correggere un difetto: sui debrief già esistenti il voto dell'AI sarebbe andato perso alla prima correzione (versione 1.16.44, corretta nella 1.16.45). Test automatici: `ai/simulations/tests/test_instructor_api.py`, classe `TestInstructorScoreOverride`.

## Segnalazioni

Nessuna segnalazione registrata.

## Formazione AI

Incontri di formazione del team Overside (politica, punto 11): data, argomenti, partecipanti.

Nessun incontro registrato.
