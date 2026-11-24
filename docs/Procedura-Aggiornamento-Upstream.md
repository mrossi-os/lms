# Procedura di aggiornamento upstream

**Destinatari:** chi esegue l'aggiornamento della piattaforma dal progetto originale (`frappe/lms`) e chi decide cosa tenere delle nostre personalizzazioni.

**Documenti di progetto:**
- [`superpowers/specs/2026-09-18-upstream-release-walk-design.md`](superpowers/specs/2026-09-18-upstream-release-walk-design.md): il percorso release per release;
- [`superpowers/specs/2026-11-23-tracciamento-personalizzazioni-design.md`](superpowers/specs/2026-11-23-tracciamento-personalizzazioni-design.md): il catalogo delle funzionalità e il controllo sui commit.

> **Stato (2026-11-24):** la skill `/upstream-upgrade` (`.claude/skills/upstream-upgrade/SKILL.md`) lavora con il catalogo delle funzionalità.
> - Prima di partire calcola la mappa delle personalizzazioni.
> - A ogni release confronta le novità upstream con le nostre funzionalità e chiede sempre a te.
> - Il controllo sui commit è attivo da questa data.
>
> Cosa manca ancora: §10.

---

## 1. In una riga

**Fai partire la skill, rispondi a due domande, e vieni richiamato quando serve una tua decisione. Fra le decisioni c'è sempre quella di tenere una nostra funzionalità o passare a quella upstream.**

```
/upstream-upgrade
```

---

## 2. Una tantum, per ogni copia del repository

```bash
git remote add upstream https://github.com/frappe/lms.git
git config rerere.enabled true
git config core.hooksPath .githooks
```

**✅ Remote e `rerere` sono attivi su questo repository dal 2026-09-18. Il controllo sui commit (`core.hooksPath`) è attivo dal 2026-11-24.** Sono impostazioni della singola copia: su un altro computer, o in un clone nuovo, vanno rieseguite. Se manca qualcosa, la skill lo propone al primo passo.

**`rerere`** registra come risolvi un conflitto e riapplica la stessa risoluzione quando il conflitto si ripresenta identico, cosa che accade spesso attraversando più release consecutive. Ha un rischio da conoscere: **ripete fedelmente anche gli errori**. Se una volta risolvi male, lo rifarà. Non attivare mai `rerere.autoUpdate`: metterebbe i file in stage da solo, togliendoti il momento di controllo.

Per disfare, a tre livelli:

```bash
git rerere forget <percorso-file>   # dimentica UNA risoluzione sbagliata
git config --unset rerere.enabled   # spegne, la cache resta
rm -rf .git/rr-cache                # cancella tutto lo storico
```

**`core.hooksPath .githooks`** accende il controllo sui commit (§3.3). Serve python3 3.11 o più recente come primo `python3` nel PATH di git. Sul Mac `/usr/bin/python3` è 3.9: i client git grafici (IDE, app) devono trovare prima quello giusto, altrimenti i loro commit vengono rifiutati.

---

## 3. Tutti i giorni: come si tracciano le personalizzazioni

L'aggiornamento funziona bene solo se in ogni momento sappiamo **cosa abbiamo cambiato e perché**. Per questo il tracciamento non si fa al momento dell'aggiornamento: si fa a ogni commit.

### 3.1 Il catalogo delle funzionalità

Ogni nostra funzionalità ha una **scheda** in `docs/customizations/features/<id>.toml`; lo schema è nel `README.md` della stessa cartella. La scheda dice:
- cosa fa la funzionalità, regola per regola (`behaviour`), e per quali ruoli;
- dove vive: file e cartelle (`areas`), dati come campi personalizzati e doctype (`data`), test (`tests`);
- cosa cercare nelle release upstream per capire se l'upstream sta facendo la stessa cosa (`upstream_watch`);
- la sua storia (`history`).

Una scheda non si cancella mai. Se la funzionalità sparisce passa a `retired`; se la sostituisce l'upstream passa a `replaced-by-upstream`.

### 3.2 L'inventario degli innesti

Quando una funzionalità modifica un file upstream, la modifica ha una **voce** in `docs/customizations/spa-grafts.toml`. La voce contiene:
- un'**ancora**, cioè una riga di testo che esiste solo nel nostro codice;
- l'`intent`, cioè perché c'è la modifica;
- il collegamento alla scheda (`feature = "<id>"`).

Il **rilevatore** (`python3 scripts/check_customizations.py`) controlla che ogni ancora esista ancora. Se un merge la cancella, lo dice. Le traduzioni italiane nostre sono registrate in `docs/customizations/translations-it.toml`: si rigenera con `python3 scripts/customization_translations.py --write` e non si scrive a mano.

### 3.3 Il controllo sui commit

Ogni commit che tocca file upstream o codice nostro deve dire **a quale funzionalità appartiene**, con una riga nell'ultimo paragrafo del messaggio:

```
feat(live-class): save every live class as a draft

<descrizione>

Version: 1.16.80

Oslms-Feature: live-class-draft-publish
Co-Authored-By: ...
```

Il controllo (`.githooks/commit-msg`, che esegue `scripts/commit_guard.py`) funziona così:
- rifiuta il commit se la riga manca, e propone le schede candidate;
- rifiuta un commit che rompe un'ancora;
- rifiuta un `feat` senza la sua scheda in stage.

Le regole complete sono in `CLAUDE.md`, sezione «Customization tracking». Non servono righe per i commit che toccano solo `docs/`, gli script, le traduzioni o i file generati. Un commit senza effetti sul comportamento può usare `Oslms-Feature: none (<motivo>)`, mai per `feat` o `fix`. Il controllo non si salta mai (`--no-verify`): se rifiuta, si corregge il messaggio o la scheda come dice.

Il 99% dei commit lo fa Claude, che scrive la riga da solo. Tu la vedi nel messaggio.

### 3.4 La mappa

```bash
python3 scripts/customization_map.py               # per funzionalità
python3 scripts/customization_map.py --unattributed # solo i buchi
```

La mappa confronta il branch con l'ultima release upstream fusa. Divide ogni differenza in blocchi e attribuisce ciascun blocco a una funzionalità. Le fonti, in ordine: le righe `Oslms-Feature` dei commit, le ancore, le `areas` delle schede e, per le modifiche più vecchie della regola, `docs/customizations/legacy-attribution.toml`.

Il numero che conta è **zero**:
- zero blocchi che nessuno rivendica;
- zero file nostri che nessuna scheda copre.

L'unica eccezione è il **residuo** che hai approvato tu, a voce, con data. Per esempio una virgola lasciata da un merge: si registra come `[[residue]]` nello stesso file `legacy-attribution.toml`.

---

## 4. Avvio: controlli, mappa, due domande

```
/upstream-upgrade
```

La skill esegue da sola, in sequenza:

| | Cosa fa | Se qualcosa non va |
| --- | --- | --- |
| 1 | Controlla che il working tree sia pulito (sono tollerati `docs/WORKLOG.md` modificato e i file non tracciati), che non ci sia un merge in corso, e che remote, `rerere` e controllo sui commit siano attivi | Si ferma e chiede |
| 2 | `git fetch upstream --tags` | — |
| 3 | **Piano** (`scripts/upstream_plan.py`). Per ogni release fra dove sei e l'ultima mostra: commit e file **reali** (dal diff, non dalle note), rotture dichiarate, versione di `frappe-ui`, voci di inventario toccate, pagine congelate toccate, file nostri modificati ma non censiti. Chiude con una raccomandazione motivata su dove fermarsi | — |
| 4 | **Mappa delle personalizzazioni** per funzionalità, incrociata con le release del piano: quali nostre funzionalità sono più esposte | **F9** se ci sono buchi |

Poi ti fa **due domande**:

> **1.** Fino a quale release vuoi arrivare? *[proposta fra parentesi]*
> **2.** Da quale branch parto e con quale nome? *[`feature/oslms` → `merge/upstream-<versione>`]*

La seconda domanda **dichiara la partenza** invece di darla per scontata: è il momento in cui ti accorgi se sei sul branch sbagliato.

Prima di creare il branch del percorso, la skill lancia il rilevatore sulla partenza: **F0** se trova errori. Le correzioni di F9 e F0 sono commit sul branch di partenza, ciascuno dopo il tuo ok. Non si crea il branch con una delle due aperta: un'ancora già rotta prima del merge non può dire se il merge ha cancellato la regola.

### Perché le note di release non bastano

Il piano calcola l'ampiezza dal **diff dei commit**, mai dalle note. Misurato su questo repository il 2026-09-18: le note di `v2.62.0` dichiarano 26 PR, ma la release porta **200 commit e 515 file**. Quelle di `v2.59.0` ne dichiarano 206, ma 193 sono più vecchie di PR già possedute. Le note sbagliano in **entrambe** le direzioni: servono a capire l'*intento* di un cambiamento, non la sua ampiezza.

### Perché il piano mostra i cambi di dipendenze

Perché sono la categoria che nessuno strumento vede. Un aggiornamento di libreria viene fuso senza conflitti, il rilevatore non segnala nulla e la build può passare. Le rotture si vedono solo a runtime, nei componenti copiati in `frontend/src/overrides/`. È il rischio più grosso e il meno visibile: va isolato e affrontato come attività a sé.

---

## 5. Il percorso

### 5.1 Il ciclo, per ogni release in ordine dalla più vecchia

Le fermate che richiedono una tua decisione si ricavano dal piano **prima** del merge: così i conflitti si risolvono già nella direzione che hai scelto.

| | Passo | Fermata |
| --- | --- | --- |
| a | File nostri modificati ma non censiti, toccati dalla release | F7 |
| b | Aggiornamento di `frappe-ui` o pagine congelate toccate | F6 |
| c | Rotture dichiarate (`!`) | F4 |
| d | **Novità upstream che potrebbero sostituire una nostra funzionalità** (§6) | F5 |
| e | API nuove che potrebbero aggirare una correzione di sicurezza o ESG | F8 |
| f | Merge della release | F1 |
| g | Rilevatore sulla risoluzione e commit del merge (con le righe `Oslms-Feature` se ci sono stati conflitti) | — |
| h | Adozione delle novità upstream che hai scelto in F5 | — |
| i | Rilevatore: personalizzazioni sparite senza conflitto | F2 |
| j | Build | F3 |
| k | Nulla da segnalare → release successiva, senza chiederti niente | — |

### 5.2 Le fermate

| Fermata | Quando | Chi decide | Cosa ricevi |
| --- | --- | --- | --- |
| **F9** · Personalizzazioni senza padrone | Prima di partire: blocchi che la mappa non attribuisce, o file nostri senza scheda | **Tu** | Per ogni blocco il diff e i commit, con una proposta di attribuzione; se lo scopo non si ricostruisce, ti chiede se approvarlo come residuo |
| **F0** · Errori di partenza | Prima di creare il branch: il rilevatore trova ancore rotte, traduzioni perse o voci senza scheda | **Tu** | Per ogni errore la correzione proposta |
| **F1** · Conflitto git | Durante il merge | **Agente**, con l'`intent` della voce; se non basta, chiede | Riga di rapporto |
| **F2** · Personalizzazione persa in silenzio | Un'ancora sparita in un file fuso senza conflitto | **Agente**: riapplica la regola | Commit separato di ripristino |
| **F3** · Build rotta | Dopo il merge | **Agente**: diagnostica e corregge | Riga di rapporto |
| **F4** · Rottura dichiarata | Prima del merge | **Tu** | Valutazione d'impatto |
| **F5** · Novità upstream simile a una nostra funzionalità | Prima del merge | **Sempre tu** (§6) | Confronto regola per regola e raccomandazione |
| **F6** · Pagina congelata toccata o aggiornamento di `frappe-ui` | Prima del merge | **Tu** | Cosa la nostra copia non ha ricevuto, con il confronto a tre vie (`scripts/frozen_diff.py`) e una proposta |
| **F7** · File nostri non censiti toccati | Prima del merge | **Tu** | Proposta di censirli **prima** del merge: voce di inventario collegata a una scheda |
| **F8** · Superficie nuova per la conformità | Prima del merge: un'API nuova fa ciò che una nostra correzione di sicurezza o ESG ha chiuso | **Tu**, se tocca un'area protetta | Spiegazione e proposta |

Puoi **interrompere quando vuoi**: lo stato del percorso è su file (`.git/oslms-upstream-walk.json`), non nella conversazione. Riprendi giorni dopo, anche da una sessione nuova, e il percorso sa dov'era e perché si era fermato.

---

## 6. F5: quando l'upstream fa una cosa che facevamo noi

È la fermata che protegge la regola più importante: **se l'upstream implementa una funzionalità che può sostituire la nostra, si preferisce l'upstream, ma decidi sempre tu, dopo aver capito quanto si somigliano.**

Per ogni release la skill:
1. **Cerca i candidati.** Incrocia le novità della release (messaggi dei commit, file, doctype e campi nuovi, endpoint, stringhe) con ogni scheda attiva: `upstream_watch`, `areas`, `data`, voci di inventario. Lo fa anche per le funzionalità che vivono solo in `apps/os_lms`, che il merge non tocca mai: sono proprio quelle che una novità upstream può rendere inutili senza un solo conflitto. Un riscontro di parole non basta: legge il codice.
2. **Confronta**, nel rapporto di percorso, per ogni candidato:
   - cosa fa la novità, letta dal codice della release;
   - le regole della scheda una per una: coperta, coperta in parte, non coperta;
   - i ruoli;
   - i dati da migrare;
   - cosa si perde e quanto costa ciascuna strada;
   - la somiglianza in parole: **alta**, **parziale** o **bassa**.
3. **Chiede sempre**, per ogni candidato con somiglianza alta o parziale, anche quando la raccomandazione sembra ovvia. Le risposte possibili sono sempre quattro:

| Risposta | Cosa succede |
| --- | --- |
| **Adottare l'upstream e ritirare la nostra** | Il nostro codice si toglie in commit dedicati; la scheda passa a `replaced-by-upstream`; se servono, i dati si migrano con una patch che vedi prima |
| **Adottare l'upstream e riportare sopra solo le regole non coperte** | La scheda resta attiva con le sole regole che l'upstream non ha, riscritte sopra il codice upstream, ciascuna con voce e test |
| **Mantenere la nostra** | Nessun cambiamento alla nostra funzionalità; la novità upstream entra con il merge |
| **Rimandare** | Il percorso si ferma alla release precedente; questa non si fonde |

4. **Registra** la decisione nella storia della scheda e nello stato del percorso.

I candidati a somiglianza bassa finiscono in una riga del rapporto, senza domanda. La skill non adotta e non scarta mai niente da sola.

---

## 7. Chiusura: le tre cose che si chiamano tutte "testare"

Sono tre attività distinte, con tre esecutori distinti.

| | Cosa | Chi lo fa materialmente | Cosa fai tu | Quanto dura |
| --- | --- | --- | --- | --- |
| **7.1** | Suite automatica | **L'agente** | Leggi l'esito | minuti |
| **7.2** | Revisione del codice | **L'agente prepara, tu giudichi** | Leggi il diff | 5-15 minuti |
| **7.3** | Prova nell'applicazione | **Tu** | Apri il browser e provi | 2-30 minuti |

### 7.1 I test automatici: non li lanci tu

Li lancia l'agente a fine percorso, dopo aver rigenerato il registro delle traduzioni:

```bash
python3 scripts/check_customizations.py              # rilevatore
python3 scripts/customization_map.py --unattributed  # zero buchi, residuo approvato a parte
python3 -m unittest discover -s scripts/tests -t .   # test degli strumenti
cd frontend && yarn test                              # Vitest
```

Poi i test backend di `os_lms` nel container Docker, e le suite di conformità OWASP ed ESG, elencate per nome nella skill. Prima di avviare il container o di lanciare il `migrate`, l'agente chiede: il `migrate` aggiorna il DB di sviluppo e non torna indietro. Infine la skill `/upstream-check`, che fa il rapporto di cosa è stato ripulito o alterato. Tu ricevi l'esito di ciascun comando.

### 7.2 La revisione: i comandi non li devi digitare

```bash
git log --oneline <tuo-branch>..HEAD
git diff <tuo-branch>..HEAD -- <file di interesse>
```

Sono **in sola lettura e li esegue l'agente**, che ti presenta il diff già filtrato sui punti che contano. Quello che **non** è delegabile è il giudizio: guardare come è stato risolto un conflitto e dire «sì, la regola è ancora quella che volevo» oppure «no, hai interpretato male».

### 7.3 La prova sul campo: questa la fai tu

Apri `http://lms.localhost:8000/lms` e provi le aree toccate.

**L'elenco di cosa provare te lo dà l'agente.** Sa quali file ha toccato, quali voci e quali schede insistono su quei file, e quali regole ciascuna protegge. Consegna quindi una **lista chiusa**, con il ruolo con cui provare ciascuna voce. Per le funzionalità adottate dall'upstream in F5, la lista contiene le regole della scheda da riprovare sulla versione upstream. Esempio:

> **Da provare (1 voce)**
> Apri un corso con "ordine sequenziale lezioni" attivo, come **Studente**: la seconda lezione deve restare bloccata finché non completi la prima. *(Conflitto risolto su `ChapterRow.vue`, voce `chapter-row-lesson-lock`.)*

### 7.4 Integrazione

Unisci nel branch di lavoro e decidi se pubblicare. **L'agente non pubblica e non unisce mai nulla di sua iniziativa.**

---

## 8. Regole valide sempre

1. **Nel dubbio, l'agente chiede.** Indovinare è l'errore più costoso, perché `rerere` ripete la risoluzione sbagliata nelle release successive.
2. L'agente **non modifica mai un test** per farlo passare: ripara il codice, oppure si ferma e chiede.
3. **Non cancella voci di inventario né schede.** Se una regola non vale più, la marca come scostamento accettato (`accepted-drift`) con data e motivo; una scheda passa a `retired` o `replaced-by-upstream`. Sempre dopo il tuo ok.
4. **Non decide una sostituzione** al posto tuo (§6): è una scelta di prodotto.
5. **Non prosegue** oltre una fermata non risolta.
6. **Non pubblica nulla** su un remote e non unisce nel branch di partenza senza il tuo ok.
7. **Le correzioni di sicurezza (OWASP) e i requisiti ESG non si perdono e non si indeboliscono.** Nel dubbio fra la versione upstream e la nostra, tiene la nostra e chiede.
8. **Ogni commit passa il controllo** (§3.3), mai `--no-verify`.

## 9. Cosa resta manuale, sempre

- **I bump di dipendenze maggiori** e le loro conseguenze sui componenti copiati in `overrides/`.
- **Le decisioni di prodotto**: se adottare una novità upstream al posto di una funzione nostra (§6).
- **L'approvazione del residuo**: modifiche che non appartengono a nessuna funzionalità.
- **La prova sul campo** (§7.3), di cui però ricevi la lista puntuale.

## 10. Stato degli strumenti

| Strumento | Sblocca | Stato |
| --- | --- | --- |
| Inventario e rilevatore | F1, F2, F0, lista di cosa provare | ✅ Completo |
| Motore del percorso e skill | §4, §5 | ✅ Dal 2026-09-23: `scripts/upstream_plan.py` più ciclo, fermate e stato nella skill |
| Catalogo, controllo sui commit, mappa | §3, F9, F5 | ✅ Dal 2026-11-24: 69 schede, modalità stretta attiva |
| Confronto a tre vie delle copie congelate | F6 | ✅ `scripts/frozen_diff.py` |
| Test backend e Vitest | §7.1, e la fiducia nel «procedi da solo» | Parziale: suite os_lms, Vitest e suite di conformità ci sono; non coprono tutto |
| Seeding ed E2E | La prova sul campo automatica | Da pianificare |
| Lacune di F5 emerse dalla simulazione v2.64→v2.65 (2026-11-24) | F5 più preciso | Rinviate. La principale: un nuovo controllo di permessi upstream che esclude Docente o Valutatore non ha ancora un esito F5 «da reinnestare»; per ora lo intercettano i test `test_role_gates_*` |

## 11. Consultazione senza aggiornare

```bash
python3 scripts/upstream_plan.py                     # tutte le release a monte
python3 scripts/upstream_plan.py --to <versione>     # fino a una release
python3 scripts/customization_map.py                 # le nostre personalizzazioni per funzionalità
python3 scripts/customization_map.py --feature <id>  # una sola funzionalità
python3 scripts/check_customizations.py              # lo stato del rilevatore
```

Servono a guardare cosa c'è a monte e cosa abbiamo noi, senza nessuna intenzione di aggiornare: per esempio per decidere *quando* farlo. Non modificano nulla.

## 12. Cadenza

Il costo di questa procedura cresce **più che linearmente** con l'attesa: poche release sono un percorso, molte release diventano un progetto. Aggiornare spesso e a piccoli passi costa meno che aggiornare di rado.
