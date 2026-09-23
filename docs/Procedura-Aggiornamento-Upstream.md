# Procedura di aggiornamento upstream

**Destinatari:** chi esegue l'aggiornamento della piattaforma dal progetto originale (`frappe/lms`).
**Documento di progetto:** [`superpowers/specs/2026-09-18-upstream-release-walk-design.md`](superpowers/specs/2026-09-18-upstream-release-walk-design.md) — come è fatto il sistema e perché.

> **Stato (2026-09-23):** la versione 1 di `/upstream-upgrade` è costruita — skill `.claude/skills/upstream-upgrade/SKILL.md` e piano `scripts/upstream_plan.py`. Gli strumenti ancora marcati ⚙️ **non esistono ancora**. Vedi §8 per cosa manca.

---

## 1. In una riga

**Fai partire la skill, rispondi a due domande, e vieni richiamato solo quando serve una tua decisione.**

```
/upstream-upgrade
```

---

## 2. Una tantum, una volta sola nella vita del progetto

```bash
git remote add upstream https://github.com/frappe/lms.git
git config rerere.enabled true
```

Non si ripetono mai più. **✅ Già eseguiti su questo repository il 2026-09-18.**

`rerere` registra come risolvi un conflitto e riapplica la stessa risoluzione quando lo stesso conflitto identico si ripresenta — cosa che accade spesso attraversando più release consecutive. Ha un rischio da conoscere: **ripete fedelmente anche gli errori**. Se una volta risolvi male, lo rifarà. È il motivo per cui il rilevatore di scostamento (Fase 0) va costruito prima del primo aggiornamento vero.

Non attivare mai `rerere.autoUpdate`: metterebbe i file in stage da solo, togliendoti il momento di controllo.

Per disfare, a tre livelli:

```bash
git rerere forget <percorso-file>   # dimentica UNA risoluzione sbagliata
git config --unset rerere.enabled   # spegne, la cache resta
rm -rf .git/rr-cache                # cancella tutto lo storico
```

---

## 3. Avvio: un comando, due domande

```
/upstream-upgrade
```

Il comando esegue da solo, in sequenza:

| | Cosa fa | Se qualcosa non va |
| --- | --- | --- |
| 1 | Verifica che il working tree sia pulito (sono tollerati `docs/WORKLOG.md` modificato e i file non tracciati) | Si ferma ed elenca cosa c'è di non committato |
| 2 | Verifica remote e `rerere` | Propone i comandi mancanti |
| 3 | `git fetch upstream --tags` | — |
| 4 | Calcola il piano (`scripts/upstream_plan.py`): per ogni release fra dove sei e l'ultima — **commit e file reali** (dal diff, non dalle note), rotture dichiarate, **versione di `frappe-ui`**, tuoi file censiti coinvolti, pagine congelate toccate, **tuoi file modificati ma non censiti** | — |
| 5 | Mostra il piano con una **raccomandazione motivata** su dove fermarsi | — |

Poi ti fa **due domande**:

> **1.** Fino a quale release vuoi arrivare? *[proposta fra parentesi]*
> **2.** Da quale branch parto e con quale nome? *[`feature/oslms` → `merge/upstream-<versione>`]*

La seconda domanda **dichiara la partenza** invece di darla per scontata: è il momento in cui ti accorgi se sei sul branch sbagliato. Partire per distrazione da `develop` invece che dal tuo branch di lavoro farebbe lavorare il percorso per ore su una base sbagliata.

### Perché le note di release non bastano

Il piano al punto 4 calcola l'ampiezza dal **diff dei commit**, mai dalle note. Misurato su questo repository il 2026-09-18: le note di `v2.62.0` dichiarano 26 PR ma la release porta **200 commit e 515 file**; quelle di `v2.59.0` ne dichiarano 206 ma 193 sono più vecchie di PR già possedute. Le note sbagliano in **entrambe** le direzioni: servono a capire l'*intento* di un cambiamento, non la sua ampiezza.

### Perché il piano mostra i cambi di dipendenze

Perché sono la categoria che nessuno strumento vede. Un bump di libreria viene fuso pulito, il rilevatore non segnala nulla, la build può passare, e le rotture si manifestano a runtime nei componenti che hai copiato in `frontend/src/overrides/`. È il rischio più grosso e il meno visibile: va isolato e affrontato come attività a sé.

---

## 4. Il percorso

### 4.1 Il ciclo, per ogni release in ordine dalla più vecchia

Le fermate che richiedono una tua decisione si ricavano dal piano **prima** del merge: così i conflitti si risolvono già nella direzione che hai scelto.

| | Passo | Se fallisce |
| --- | --- | --- |
| a | File tuoi modificati ma non censiti, toccati dalla release | → Fermata 7 |
| b | Bump di `frappe-ui` o pagine congelate toccate | → Fermata 6 |
| c | Rotture dichiarate (`!`) | → Fermata 4 |
| d | Sovrapposizioni con funzioni tue | → Fermata 5 |
| e | Merge della release | → Fermata 1 |
| f | Rilevatore di scostamento | → Fermata 2 |
| g | Build | → Fermata 3 |
| h | Nulla da segnalare → release successiva, senza chiederti niente | — |

### 4.2 Le sette fermate

| Fermata | Chi decide | Cosa ricevi |
| --- | --- | --- |
| 1 · Conflitto git | **Agente** — risolve usando l'intento dichiarato nell'inventario | Riga di rapporto |
| 2 · Personalizzazione persa | **Agente** — riapplica la regola | Commit separato di ripristino |
| 3 · Build rotta | **Agente** — diagnostica e corregge | Riga di rapporto |
| 4 · Rottura dichiarata | **Tu** | Valutazione d'impatto |
| 5 · Sostituzione o deprecazione | **Tu** | Analisi comparativa e raccomandazione |
| 6 · Pagina congelata toccata o bump di `frappe-ui` | **Tu** | Diff upstream e proposta (il confronto a tre vie arriverà quando sarà registrata la base di ogni override) |
| 7 · File tuoi non censiti toccati | **Tu** | Proposta di censirli **prima** del merge: marcatore e voce di inventario |

Puoi **interrompere quando vuoi**: lo stato del percorso è su file, non nella conversazione. Riprendi giorni dopo, anche da una sessione nuova, e il percorso sa dov'era e perché si era fermato.

---

## 5. Chiusura: le tre cose che si chiamano tutte "testare"

È la parte che genera più confusione. Sono tre attività distinte, con tre esecutori distinti.

| | Cosa | Chi lo fa materialmente | Cosa fai tu | Quanto dura |
| --- | --- | --- | --- | --- |
| **5.1** | Suite automatica | **L'agente** | Leggi l'esito | 10 secondi |
| **5.2** | Revisione del codice | **L'agente prepara, tu giudichi** | Leggi il diff | 5-15 minuti |
| **5.3** | Prova nell'applicazione | **Tu** | Apri il browser e provi | 2-30 minuti |

### 5.1 I test automatici — non li lanci tu

Li lancia l'agente a fine percorso:

```bash
python3 scripts/check_customizations.py        # secondi
cd frontend && yarn test                        # ~30 secondi
bench --site <sito> run-tests --app os_lms
bench --site <sito> run-ui-tests lms --headless # ⚙️ opzionale, lento
```

Tu ricevi una riga di esito. Se sono verdi, non c'è niente da fare.

### 5.2 La revisione — i comandi non li devi digitare

```bash
git log --oneline <tuo-branch>..HEAD
git diff <tuo-branch>..HEAD -- <file di interesse>
```

Sono **in sola lettura e li esegue l'agente**, che ti presenta il diff già filtrato sui punti che contano invece di lasciarti scorrere decine di file. Se preferisci lanciarli tu per avere il controllo diretto puoi farlo, ma è una preferenza, non un obbligo.

Quello che **non** è delegabile è il giudizio: guardare come è stato risolto un conflitto e dire «sì, la regola è ancora quella che volevo» oppure «no, hai interpretato male».

### 5.3 La prova sul campo — questa sì, sei tu

Apri `http://lms.localhost:8000/lms` e provi le aree toccate.

**Ma l'elenco di cosa provare te lo dà l'agente.** È il passaggio che cambia di più rispetto a oggi: l'agente sa quali file ha toccato, quali voci di inventario insistono su quei file e quale funzione ciascuna protegge, quindi consegna una **lista chiusa** con il ruolo con cui provare ciascuna voce. Esempio:

> **Da provare (1 voce)**
> Apri un corso con "ordine sequenziale lezioni" attivo, come **Studente**: la seconda lezione deve restare bloccata finché non completi la prima. *(Conflitto risolto su `ChapterRow.vue`, voce `chapter-row-lesson-lock`.)*

Da «ritesto tutta la piattaforma perché non so dove guardare» a «provo una cosa, so quale e so perché».

### 5.4 Integrazione

Unisci nel branch di lavoro e decidi se pubblicare. **L'agente non pubblica mai nulla di sua iniziativa.**

---

## 6. Regole valide sempre

1. L'agente **non modifica mai un test** per farlo passare: ripara il codice, oppure si ferma e chiede.
2. **Non cancella una voce di inventario** per far tornare verde il rilevatore: se una regola non vale più, la marca come scostamento accettato, con data e motivo.
3. **Non decide una sostituzione** al posto tuo: è una scelta di prodotto.
4. **Non prosegue** oltre una fermata non risolta.
5. **Non pubblica nulla** su un remote.

## 7. Cosa resta manuale, sempre

- **I bump di dipendenze maggiori** e le loro conseguenze sui componenti copiati in `overrides/`.
- **Le decisioni di prodotto**: se adottare una novità upstream al posto di una funzione tua.
- **La prova sul campo** (§5.3), di cui però ricevi la lista puntuale.

## 8. Cosa manca ancora

| ⚙️ Strumento | Sblocca | Stato |
| --- | --- | --- |
| Inventario + rilevatore (Fase 0) | Fermata 2, riparazione guidata, lista di cosa provare | ✅ Completo |
| Test backend e Vitest (Fase 1) | §5.1, e la fiducia nel «procedi da solo» | Da pianificare |
| Motore del percorso + skill | §3, §4 | ✅ Versione 1 (2026-09-23): `plan` è codice (`scripts/upstream_plan.py`); ciclo, fermate e stato sono dentro la skill |
| Seeding + E2E (Fasi 2-3) | L'ultima riga di §5.1 | Da pianificare |

**Il minimo utile è la Fase 0:** con quella soltanto puoi già fare un aggiornamento a mano sapendo esattamente cosa hai perso.

## 9. Consultazione senza aggiornare

```bash
python3 scripts/upstream_plan.py                  # tutte le release a monte
python3 scripts/upstream_plan.py --to <versione>  # fino a una release
python3 scripts/upstream_plan.py --json           # per strumenti e agenti
```

Per guardare cosa c'è a monte senza nessuna intenzione di aggiornare — per esempio per decidere *quando* farlo. Non modifica nulla.

## 10. Cadenza

Il costo di questa procedura cresce **più che linearmente** con l'attesa: poche release sono un percorso, molte release diventano un progetto. Aggiornare spesso e a piccoli passi costa meno che aggiornare di rado.
