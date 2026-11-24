# Percorsi d'uso della piattaforma — da compilare

| | |
| --- | --- |
| Creato il | 2026-10-02 |
| Stato | **Bozza di Claude, da correggere e completare** |
| Scopo | Descrivere **come usiamo davvero** la piattaforma, per verificare dopo ogni aggiornamento upstream che le nostre personalizzazioni ci siano ancora e funzionino |
| Dopo la compilazione | Claude trasforma ogni percorso confermato in una voce `flow` dell'inventario (`spa-grafts.toml`) e in un test nel browser, da eseguire a ogni aggiornamento |

---

## Come compilarlo

### In breve

Questo file l'ha già scritto Claude. **Tu non scrivi da zero: correggi.** Ci sono solo tre cose da fare:

| Cosa trovi | Cosa fai |
| --- | --- |
| `[ ]` una casella | metti una `x` dentro le parentesi per sceglierla: `[x]` |
| ✏️ la matita | scrivi la tua risposta **subito dopo la matita**, sulla stessa riga o sotto |
| un testo scritto da Claude (passi, ruoli, proposte) | se è giusto lo lasci; se è sbagliato lo **modifichi direttamente**; se non vale per voi lo **cancelli** |

Tutto il resto lo lasci com'è. Il testo in _corsivo tra parentesi_ è un suggerimento: puoi cancellarlo quando hai scritto.

**Non serve scrivere bene né usare termini tecnici.** Bastano frasi brevi. Se un punto non lo sai, lascia la matita vuota: si chiede dopo.

Un percorso che **non usate** si chiude in un secondo: metti la `x` su «Non lo usiamo» e passa al successivo, senza compilare altro.

### Le parti del file

- **Parte A — Contesto d'uso:** domande generali (chi ha quali ruoli, quanto si usa il telefono, cosa **non** usate). Accanto c'è una proposta di Claude: correggila o scrivi «ok».
- **Parte B — Percorsi d'uso:** i 20 processi già scritti da Claude. Il grosso del lavoro è qui.
- **Parte C — Percorsi da aggiungere:** un modello vuoto per i processi che mancano.
- **Parte D — Domande aperte:** 6 domande a cui rispondere dopo la matita.

Consiglio: comincia dalla **Parte A4** (funzioni che non usate). Dopo, molti percorsi della Parte B li chiudi subito con «Non lo usiamo».

### I campi di un percorso, uno per uno

| Campo | Dove | Cosa scrivi |
| --- | --- | --- |
| **Stato** | `[ ] Confermato  [ ] Non lo usiamo` | una `x` in **una** casella. «Confermato» = lo usiamo, e i passi sono giusti (o li hai corretti). «Non lo usiamo» = si scarta. Vuoto = non hai ancora deciso |
| **Importanza** | `[ ] alta  [ ] media  [ ] bassa` | una `x`. **Alta**: se si rompe, il cliente se ne accorge subito o si blocca il lavoro di tutti i giorni. **Media**: si usa, ma per qualche giorno si può farne a meno. **Bassa**: si usa raramente |
| **Chi** | dopo «Chi:» | i ruoli che fanno quel processo. Correggi la proposta se è sbagliata |
| **Quanto spesso** | dopo la matita | «ogni giorno», «una volta a settimana», «a inizio corso»… |
| **Passi** | l'elenco numerato | ogni riga è *chi fa cosa → cosa deve succedere*. Correggi le righe sbagliate, cancella quelle che non fate, aggiungi quelle che mancano |
| **Cosa non deve mai succedere** | l'elenco puntato, dopo la matita | gli errori che per voi sarebbero gravi: un dato visto da chi non dovrebbe, un'email mandata due volte, una consegna persa. Uno per riga |
| **Note** | dopo la matita | tutto il resto: eccezioni, abitudini dei clienti, problemi già segnalati |
| **Personalizzazioni coinvolte (per Claude)** | il riquadro richiudibile in fondo | **niente**: serve a Claude per collegare il percorso al codice |

### Esempio: prima e dopo

**Prima** (come l'ha scritto Claude):

```markdown
- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Gestore ✏️ _(proposta; aggiungi o togli: Moderatore? Docente?)_
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Gestore crea una nuova classe → i campi obbligatori mancanti danno un avviso in italiano.
2. Aggiunge i corsi alla classe → nella scelta compaiono anche i corsi in bozza.
3. Iscrive gli studenti importandoli da file → risultano iscritti anche ai corsi della classe.

**Cosa non deve mai succedere:**

- Uno studente iscritto alla classe non risulta iscritto ai corsi della classe.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️
```

**Dopo** (compilato):

```markdown
- **Stato:** [x] Confermato  [ ] Non lo usiamo
- **Importanza:** [x] alta  [ ] media  [ ] bassa
- **Chi:** Gestore
- **Quanto spesso:** ✏️ all'inizio di ogni edizione, circa 2 volte al mese

**Passi (bozza):**

1. Il Gestore crea una nuova classe → i campi obbligatori mancanti danno un avviso in italiano.
2. Aggiunge i corsi alla classe → nella scelta compaiono anche i corsi in bozza.
3. Iscrive gli studenti importandoli da un Excel che manda il cliente → risultano iscritti anche ai corsi della classe.
4. Manda l'annuncio di benvenuto a tutta la classe.

**Cosa non deve mai succedere:**

- Uno studente iscritto alla classe non risulta iscritto ai corsi della classe.
- ✏️ Uno studente viene iscritto due volte.

**Note:**

✏️ Il file Excel a volte ha email scritte in maiuscolo.
```

Cosa è cambiato: due `x`, il «Chi» ripulito, la frequenza scritta dopo la matita, il passo 3 corretto, un passo 4 aggiunto, un caso grave e una nota scritti dopo la matita.

---

## Parte A — Contesto d'uso

Domande generali che cambiano come e cosa si testa. Accanto a ogni domanda c'è la **proposta di Claude**, ricavata dal codice: correggila direttamente, e scrivi dopo ogni ✏️ (anche solo «ok»).

### A1. Ruoli: chi li ha e quanti sono

Proposta di Claude:

| Ruolo | Chi è | Quanti (circa) |
| --- | --- | --- |
| Studente | I corsisti | ✏️ |
| Docente | Istruttore globale: lavora su tutti i corsi senza essere istruttore di ciascuno | ✏️ |
| Valutatore | Legato alla singola classe: vede e corregge solo gli studenti della sua classe | ✏️ |
| Gestore | Gestione completa, sempre insieme a Moderatore, Docente, Course Creator e Batch Evaluator. Quasi sempre senza accesso al Desk | ✏️ |
| Moderatore | ✏️ | ✏️ |
| Course Creator | ✏️ | ✏️ |
| Amministratore / System Manager | Solo il personale tecnico | ✏️ |

✏️ **Risposta:** correggi direttamente la tabella qui sopra (dove c'è ✏️ scrivi il dato) e aggiungi una riga per ogni ruolo che manca.

### A2. Dispositivi e browser

Proposta di Claude: gli studenti usano molto il telefono (ci sono molte personalizzazioni mobili: barra «Continua», PDF su telefono, quiz a una colonna). Docenti e gestori usano il computer.

- Quota approssimativa di studenti da telefono: ✏️
- iPhone o Android prevalenti: ✏️
- Browser più usati su computer: ✏️
- Ci sono ruoli diversi dallo studente che lavorano da telefono? (es. il Valutatore che corregge da telefono): ✏️

✏️ **Altro da aggiungere:**

### A3. Integrazioni attive in produzione

Segna con una `x` quelle **attive oggi** e scrivi accanto se è usata poco o tanto.

- [ ] TrueSkill — emissione dei certificati (Openbadge)
- [ ] TrueSkill — certificati emessi direttamente da TrueSkill, visibili nel profilo
- [ ] Elite API — TrueSkill legge corsi, classi e studenti
- [ ] Zoom + Google Calendar — lezioni dal vivo
- [ ] Google Meet — lezioni dal vivo
- [ ] OpenAI — tutor AI sui materiali del corso
- [ ] OpenAI — simulazioni (chat)
- [ ] OpenAI — simulazioni vocali
- [ ] Vimeo — video nelle lezioni
- [ ] YouTube — video nelle lezioni
- [ ] Notifiche push sul telefono
- [ ] Email (annunci, promemoria delle live, notifiche)
- [ ] Raven
- [ ] Altro: ✏️

✏️ **Note:**

### A4. Funzioni della piattaforma che NON usate

Serve a **non perdere tempo** a testare ciò che non usate e a non segnalare come bug cose che non vi interessano. Segna con una `x` quelle che **non usate**.

- [ ] Pagamenti, coupon, corsi a pagamento
- [ ] Offerte di lavoro (Jobs)
- [ ] Esercizi di programmazione
- [ ] Pacchetti SCORM
- [ ] Sorveglianza dei quiz con webcam
- [ ] Penalità nei quiz
- [ ] Programmazione delle date di quiz e compiti (nuova in v2.64)
- [ ] Valutazioni con prenotazione (certificazione con valutatore e calendario)
- [ ] Discussioni / chat della classe
- [ ] Programmi
- [ ] Import di dati da file
- [ ] Iscrizione autonoma degli studenti (registrazione dal sito)
- [ ] Accesso senza login (visitatori)
- [ ] Altro: ✏️

✏️ **Note:**

### A5. Materiale di prova disponibile

Cosa può usare Claude per i test sul sito di sviluppo:

- Un pacchetto SCORM di prova: ✏️ _(dove si trova, oppure scrivi «cercane uno pubblico»)_
- Un PDF di prova realistico (es. una dispensa vera): ✏️
- Un video Vimeo di prova (anche privato con link di condivisione): ✏️
- Account TrueSkill o chiave di test utilizzabili: ✏️ _(sì / no / solo per lettura)_
- Può creare utenti e dati con prefisso `collaudo-` sul sito di sviluppo e cancellarli a fine giro: ✏️ _(sì / no)_

---

## Parte B — Percorsi d'uso (bozza di Claude)

Ordinati seguendo la vita di un corso: dalla preparazione al certificato.

---

### P01 — Primo accesso dello studente

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Studente
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Lo studente riceve le credenziali, oppure si registra dal sito → nella registrazione non c'è la categoria utente e i termini stanno in un riquadro scorrevole.
2. Primo accesso → compaiono la notifica e il video di benvenuto.
3. Arriva nella home → vede i suoi corsi, le sue classi ed eventualmente i suoi programmi; logo e colori sono quelli del cliente nel tema chiaro (il default); dal menu utente può passare al tema scuro standard.
4. Apre il profilo e lo modifica → può inserire il codice fiscale; il modulo è ridotto ai campi essenziali.
5. Nell'elenco corsi vede **solo** i corsi a cui è iscritto; nell'elenco classi solo le sue classi.

**Cosa non deve mai succedere:**

- Lo studente vede corsi o classi a cui non è iscritto.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`signup-form-terms-no-category`, `settings-welcome-tab`, `home-welcome-video-hero`, `home-programs-row`, `profile-edit-codice-fiscale`, `profile-edit-reduced-fields`, `courses-list-students-enrolled-only`, `batch-list-student-enrolled-only`, `default-light-theme`, `theme-elite-import`, `main-brand-customize-css`, `profile-tab-bar-hidden-for-students`; backend: `User.after_insert` → `mark_first_login`.

</details>

---

### P02 — Preparazione di un corso e delle sue lezioni

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Docente ✏️ _(proposta; aggiungi o togli: Course Creator? Moderatore?)_
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Docente crea un corso → compila i dettagli: categoria, tag colorati, durata, video di anteprima (YouTube o Vimeo), descrizione con immagini, sezioni in evidenza.
2. Nelle impostazioni del corso sceglie il certificato → **o** quello interno **o** quello TrueSkill, mai entrambi.
3. Crea capitoli e lezioni → nell'editor scrive testo con colori, evidenziazioni e allineamento; dopo il salvataggio restano.
4. Inserisce nella lezione un PDF, un documento o un archivio, un video Vimeo (anche link di condivisione), un quiz, un compito.
5. Imposta nella lezione le opzioni os_lms (pannello impostazioni): per esempio l'obbligo di vedere il video.
6. Attiva il blocco sequenziale delle lezioni → lo studente non apre la lezione successiva senza aver completato la precedente.
7. Nell'editor vede lo stato di indicizzazione per il tutor AI.
8. Lavora anche su corsi **creati da altri docenti** → può modificare tutto (Docente globale).

**Cosa non deve mai succedere:**

- Il Docente salva e perde una parte del contenuto (colori, pacchetto SCORM, allegati) senza accorgersene.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`course-form-os-sections`, `course-details-tag-picker`, `course-details-os-link`, `course-video-link-youtube-id`, `video-preview-field-vimeo`, `description-images-upload-public`, `course-trueskills-publish-settings`, `course-certificate-trueskill-exclusive`, `course-instructors-orphan-removable`, `editor-inline-color-persist`, `editor-i18n-labels`, `block-editor-i18n-labels`, `upload-documents-and-archives`, `embed-vimeo-share-links`, `lesson-form-os-settings-panel`, `lesson-form-editable-fields`, `lesson-ai-status`, `lesson-rename-rag-reindex`, `router-lesson-edit-route`, `lesson-edit-button-editor-hash`, `course-editor-tab-hash`, `quiz-editor-placeholder-title`, `assignment-block-empty-placeholder`, `permissions-docente-global-v264`; backend: `Course Lesson.before_save/on_trash/after_rename`.

</details>

---

### P03 — Creazione di una classe e iscrizione degli studenti

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Gestore ✏️ _(proposta; aggiungi o togli: Moderatore? Docente?)_
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Gestore crea una nuova classe → i campi obbligatori mancanti danno un avviso in italiano.
2. Nelle impostazioni della classe aggiunge istruttori e **valutatori** → si salvano; i valutatori ricevono il ruolo in automatico.
3. Aggiunge i corsi alla classe → nella scelta compaiono anche i corsi in bozza.
4. Iscrive gli studenti: più studenti insieme, oppure importandoli da file nella dashboard → gli studenti risultano iscritti anche a **tutti i corsi** della classe.
5. Aggiunge un corso a una classe già avviata → gli studenti già presenti vengono iscritti anche al nuovo corso.
6. Toglie un valutatore o un istruttore (anche con account cancellato) → si può togliere.

**Cosa non deve mai succedere:**

- Uno studente iscritto alla classe non risulta iscritto ai corsi della classe.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`batch-new-modal-required-warnings`, `batch-new-modal-i18n`, `batch-form-valutatori`, `batch-form-people-dirty-autosave`, `batch-form-saved-people-removable`, `batch-form-os-link`, `batch-course-modal-all-courses`, `batch-student-modal-bulk-enroll`, `batch-dashboard-import-students`, `batch-enrollment-courses-after-insert`, `batch-added-courses-enroll-existing-students`, `patch-backfill-batch-course-enrollments`, `batch-content-add-moderator-only`; backend: `LMS Batch.on_update` → `sync_batch_valutatore_roles`.

</details>

---

### P04 — Lo studente segue un corso

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Studente
- **Quanto spesso:** ✏️ _(proposta: quotidiano)_

**Passi (bozza):**

1. Apre il corso → vede il programma navigabile e la descrizione comprimibile; **non** vede istruttori, recensioni né la card dell'autore.
2. Da telefono → la barra «Continua» resta fissa in basso e il programma è in fondo alla pagina.
3. Apre una lezione → la barra laterale apre il capitolo giusto; testi lunghi vanno a capo.
4. Guarda un video con l'obbligo di visione → non può saltarlo, anche se il player ha un errore non grave.
5. Apre un PDF → si legge anche da telefono, con il nome giusto.
6. Evidenzia del testo e prende appunti → le evidenziazioni restano sul punto scelto; niente discussioni nella lezione, solo le sue note.
7. Prova ad aprire una lezione successiva senza aver finito quella prima → è bloccata.
8. Usa il tutor AI → il tutor sa in quale lezione si trova.

**Cosa non deve mai succedere:**

- Lo studente salta lezioni o video obbligatori.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`course-card-outline`, `course-description-collapsible`, `course-instructors-hidden-from-students`, `course-reviews-removed`, `course-creator-card-removed`, `course-content-section-removed`, `course-mobile-cta-bar`, `course-mobile-outline-bottom`, `course-tablet-inline-card`, `course-hero-banner`, `lesson-sidebar-open-active-chapter`, `lesson-long-strings-wrap`, `lesson-video-error-keeps-enforcement`, `upload-pdf-block-mobile`, `lesson-pdf-inline-filename`, `lesson-highlight-offset`, `lesson-discussions-removed`, `lesson-sequential-access-lock`, `lesson-zen-mode-fullscreen-only`, `lesson-ai-tutor-context`, `app-ai-tutor-route-context`, `ai-fixed-buttons-layouts`, `popover-above-floating-buttons`, `video-utils-vimeo-embed`.

</details>

---

### P05 — Lo studente svolge un quiz

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Studente; Docente che prepara il quiz
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Docente crea il quiz dalla banca domande, eventualmente con penalità e timer → tipi di domanda in italiano.
2. Lo studente avvia il quiz → risposte con pulsanti radio classici; da telefono è a una colonna.
3. Salta una domanda e consegna da una domanda intermedia → avviso sulle domande senza risposta, consegna riuscita, la saltata vale 0 (o −1 con la penalità).
4. Quiz a tempo: cambia scheda e torna dopo la scadenza → consegnato **una sola volta**.
5. Lezione bloccata che contiene un quiz → avviso «quiz bloccato».

**Cosa non deve mai succedere:**

- Una consegna persa o doppia.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`quiz-submit-unanswered`, `quiz-skip-unanswered-ui`, `quiz-timer-wall-clock`, `quiz-player-style-translations`, `quiz-radio-classic`, `quiz-list-style`, `assessment-list-search-words`, `list-search-restarts-paging`; patch `restrict_student_quiz_submission_perms`.

</details>

---

### P06 — Consegna e correzione dei compiti

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Studente; Valutatore e/o Docente che corregge
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Docente crea il compito → avvisi sui campi obbligatori; tipi di consegna in italiano.
2. Lo studente consegna dalla lezione (testo, file o link) → da telefono la pagina è a una colonna.
3. Il Valutatore della classe, o il Docente, apre l'elenco delle consegne → vede solo quelle degli studenti che gli competono.
4. Corregge → la risposta dello studente è in sola lettura; voto e commento si salvano.
5. Lo studente riapre il compito corretto → vede il voto e non può più modificare la risposta.

**Cosa non deve mai succedere:**

- Chi corregge modifica per sbaglio la risposta dello studente.
- Un Valutatore vede o corregge compiti di un'altra classe.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`assignment-form-required-warnings`, `assignment-form-translations`, `assignment-mobile-single-column`, `assignment-style-translations`, `assignment-block-iframe-height`, `assignment-submission-mobile-frame`, `assignment-submission-list-style`, `assignment-list-type-i18n`, `assignment-list-style`, `assignment-valutatore-grading`, `assignment-answer-readonly-for-graders`.

</details>

---

### P07 — Il Valutatore segue la sua classe

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Valutatore
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Valutatore entra → riceve la home in stile amministratore.
2. Elenco classi → vede le classi che valuta, anche non pubblicate; **non** vede le altre.
3. Apre la classe → schede e dashboard amministrativa; **non** può rimuovere studenti, esportare le statistiche, fare annunci o gestire le live.
4. Dashboard → progressi degli studenti, con il dettaglio per lezione, **solo della sua classe**.
5. Apre un corso della classe, anche non pubblicato → panoramica e dashboard in sola lettura; lezioni, quiz e SCORM leggibili.
6. Apre le consegne dei quiz → in sola lettura, senza il registro con le foto della sorveglianza.
7. Vede le lezioni dal vivo della sua classe → in sola lettura.
8. Da telefono, dalle liste delle consegne → «indietro» torna alla pagina precedente.

**Cosa non deve mai succedere:**

- **Il Valutatore vede dati (studenti, voti, consegne, foto) di una classe che non è sua.**
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`home-valutatore-admin-home`, `batch-list-valutatore-docente`, `batch-detail-valutatore-tabs`, `course-detail-valutatore-tabs`, `course-card-valutatore-no-enroll`, `permissions-valutatore-lesson-access`, `permissions-valutatore-quiz-access`, `permissions-valutatore-course-scope-v264`, `course-lesson-list-mirrors-read-gate`, `quiz-submission-valutatore-readonly`, `proctoring-log-hidden-from-valutatore`, `live-class-valutatore-read`, `live-class-batch-card-observer`, `valutatore-phone-back-history`, `batch-dashboard-export-statistics`, `batch-dashboard-remove-students`, `batch-detail-header-actions`; backend: `valutatore.py`, hook di permesso del Valutatore.

</details>

---

### P08 — Lezioni dal vivo

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Docente / Gestore che organizza; Studente che partecipa; Valutatore che osserva
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Docente crea una lezione dal vivo dalla classe → serve un account Zoom attivo e collegato a un Google Calendar autorizzato; l'ora è a 24 ore e viene inviata a Zoom come ora locale.
2. Imposta i promemoria → vengono inviati agli studenti all'orario previsto.
3. Modifica o riprogramma la lezione → gli iscritti ricevono l'email di aggiornamento.
4. Lo studente riceve l'invito e il file per il calendario → al momento giusto entra con «Partecipa» dalla card o dall'email, che passa dalla piattaforma: fuori dall'orario, o se non è iscritto, non entra.
5. Il Valutatore vede la lezione da osservatore, senza poterla modificare.

**Cosa non deve mai succedere:**

- Il link Zoom diretto arriva a chi non è iscritto.
- Promemoria mandati due volte, o all'ora sbagliata.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`live-class-docente-manage`, `live-class-edit-delete`, `live-class-modal-edit-reschedule`, `live-class-modal-reminders`, `live-class-modal-submit-guard`, `live-class-modal-time-24h-i18n`, `live-class-pagination-sort`, `live-class-batch-card-observer`, `zoom-account-enabled-calendar-required`, `live-class-calendar-oauth-check`, `zoom-start-time-local-wallclock`, `zoom-authenticate-error-message`, `zoom-account-google-calendar-field`, `home-admin-live-class-card`, `home-live-classes-toggle`, `batch-detail-live-classes-toggle`; backend: `live_class_join.py`, `live_class_reminders.py`, `live_class_ics.py`, `google_calendar.py`.

</details>

---

### P09 — Annunci e comunicazioni

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Gestore / Docente che scrive; Studente che riceve
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Dalla scheda Annunci della classe scrive un annuncio, eventualmente partendo da un modello email → a tutta la classe o a studenti scelti.
2. L'annuncio arriva come notifica in piattaforma e, se scelto, anche via email, con i colori del modello.
3. Lo studente apre la notifica → arriva alla pagina giusta; la notifica è in italiano.
4. Le notifiche arrivano anche come push sul telefono _(se attive)_.
5. Le email automatiche (iscrizione, promemoria, aggiornamenti) usano i modelli personalizzati dal Desk, quando esistono.

**Cosa non deve mai succedere:**

- Un annuncio arriva a studenti di altre classi.
- Notifiche o email in inglese.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`announcement-send-os-lms`, `announcement-email-template-composer`, `announcement-specific-recipients`, `announcement-named-colors`, `announcement-rich-render`, `announcement-list-pagination`, `announcement-modal-in-tab`, `notifications-link-routing`, `notifications-tabs-translated`, `batch-detail-tab-notification-badges`; backend: `email_utils.py` (`send_templated_email`), `OS LMS Email Settings`, `notification_links.py`, `push_notifications.py`, lingua nei job in background (`before_job` → `set_user_lang`).

</details>

---

### P10 — Discussioni e chat della classe

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Studenti, Docente, Gestore
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Nella classe si apre un argomento di discussione → l'etichetta del pulsante è quella scelta nelle impostazioni.
2. Si risponde → nessun pulsante per incorporare iframe; i messaggi più recenti in alto.
3. Gli altri ricevono la notifica → cliccandola si apre la classe sulla scheda giusta.

**Cosa non deve mai succedere:**

- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`discussion-new-label`, `discussion-no-embed-toolbar`, `discussion-batch-chat-newest-first`, `discussion-reply-null-user`, `discussion-replies-style`, `notifications-link-routing`.

</details>

---

### P11 — Certificati

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Studente; Gestore che controlla
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Lo studente completa un corso con certificato **TrueSkill** → il certificato viene emesso solo se nel profilo c'è il codice fiscale; altrimenti un avviso lo chiede.
2. L'emissione avviene in automatico; se TrueSkill non risponde, viene ritentata più tardi.
3. Lo studente apre «Visualizza certificato» → vede il badge TrueSkill al posto del PDF interno; può scaricarlo.
4. Con un certificato **interno** → «Scarica certificato» genera il PDF con il layout del cliente.
5. Profilo → Certificati → due gruppi: «Certificati Elite» e «Certificati TrueSkill» (anche quelli emessi direttamente da TrueSkill); li vede solo il proprietario, il System Manager e il Gestore.
6. Sulla card del corso non compare un doppio pulsante del certificato.

**Cosa non deve mai succedere:**

- Un certificato emesso senza codice fiscale.
- Un utente vede i certificati di un altro.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`trueskills-certificate-viewer`, `profile-trueskills-received-certificates`, `course-card-certificate-dedup`, `course-certificate-pdf-chrome`, `certification-links-view-on-profile`, `course-certificate-trueskill-exclusive`, `courses-card-certification-badge`, `profile-tabs-certificates-only`; backend: `LMS Certificate.after_insert` → `trueskills.emission.enqueue_issue`, `trueskills.scheduler.reconcile_pending`, `trueskills/received.py`, `TrueSkills Issue Log`.

</details>

---

### P12 — Programmi

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Docente / Course Creator / Moderatore che crea; Studente membro
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Si crea un programma → titolo modificabile, descrizione formattata con immagini visibili a tutti.
2. Si aggiungono più corsi insieme e i membri in blocco o da una classe.
3. Un altro Docente o Course Creator modifica lo stesso programma → può farlo.
4. Lo studente membro vede il programma nella home con la sua descrizione.
5. Apre un corso **non pubblicato** del programma prima di iscriversi → vede l'outline e può iscriversi.

**Cosa non deve mai succedere:**

- Chi non è membro del programma vede i corsi non pubblicati.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`program-form-title-rename`, `program-form-description-editor`, `description-images-upload-public`, `program-form-add-courses-multi`, `program-form-add-members-bulk`, `program-form-full-document`, `program-authoring-pool`, `program-description`, `home-programs-row`, `program-member-unpublished-course`.

</details>

---

### P13 — Monitoraggio, statistiche e pulizia degli iscritti

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Gestore, Docente, Amministratore
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Dashboard del corso → elenco studenti ordinabile e cercabile, legenda dei progressi in italiano, leggibile da telefono.
2. Dashboard della classe → progressi per studente e per corso, dettaglio per lezione.
3. Il Gestore esporta le statistiche (voce «Export Statistics» nella barra laterale) → il file contiene i dati attesi.
4. Il Gestore o l'Amministratore rimuove uno studente da un corso → i dati restano; solo il System Manager può fare la pulizia completa, certificati e dati AI compresi.
5. Il Docente o il Gestore rimuove studenti da una classe.

**Cosa non deve mai succedere:**

- La pulizia completa disponibile a chi non è System Manager.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`course-dashboard-sortable-students`, `course-dashboard-search-by-name`, `course-dashboard-progress-labels-it`, `course-dashboard-mobile-layout`, `course-dashboard-rating-card-hidden`, `batch-dashboard-student-progress`, `batch-dashboard-progress-panel`, `batch-dashboard-sortable-students`, `batch-student-progress-lesson-drilldown`, `sidebar-export-statistics`, `router-student-stats-export-route`, `batch-dashboard-export-statistics`, `course-dashboard-remove-students`, `batch-dashboard-remove-students`, `statistics-chart-labels-i18n`; backend: `course_students.py`, `Student Stats Export`, `access_tracking.py`.

</details>

---

### P14 — Gestione degli utenti e dei ruoli

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Moderatore / Gestore
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Impostazioni → Membri → crea un membro con i ruoli scelti → ha **solo** quei ruoli (lo «Studente» non viene aggiunto da solo).
2. Clic sulla riga di un membro → si apre la modifica; il badge Valutatore è visibile.
3. Dal profilo di un utente → interruttori per Valutatore, Gestore e Docente.
4. Un utente con ruoli di gestione attiva la «vista studente» → vede la piattaforma come uno studente, anche se è Valutatore, Docente o Gestore.

**Cosa non deve mai succedere:**

- Un utente riceve ruoli non scelti.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`member-valutatore-role-exact-roles`, `settings-members-row-opens-edit`, `settings-members-valutatore-badge`, `profile-roles-custom-role-toggles`, `student-view-oslms-roles`.

</details>

---

### P15 — Impostazioni della piattaforma

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Gestore, Amministratore
- **Quanto spesso:** ✏️ _(proposta: raramente)_

**Passi (bozza):**

1. Il Gestore apre le Impostazioni → vede le schede os_lms (TrueSkill, Elite API, Google Calendar…), ma non quelle di sistema riservate all'amministratore.
2. Configura gli account Zoom collegati a Google Calendar → si salvano.
3. Modifica branding, colori e voci della barra laterale → si applicano a tutti.
4. Imposta il messaggio e il video di benvenuto.
5. Non imposta più il tema: di default è chiaro con i colori del cliente e ogni utente può passare al tema scuro standard dal menu utente.
6. Crea e revoca le chiavi dell'Elite API.

**Cosa non deve mai succedere:**

- Il Moderatore senza Gestore accede alle schede riservate.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`settings-oslms-tabs-injection`, `settings-admin-only-tabs`, `settings-google-calendar-tab`, `settings-raven-admin-only`, `settings-sidebar-extra-toggles`, `settings-welcome-tab`, `settings-payment-group-removed`, `settings-elite-api-tab`, `default-light-theme`, `zoom-account-rename-keeps-account-name`; backend: `branding.py`, `Brand Customize`, `LMSA Settings`.

</details>

---

### P16 — Import di dati e file

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Gestore / Moderatore
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Menu utente → «Importa» → pagina «Carica file».
2. Configurazione → import dati da Excel o CSV → titoli in italiano, l'import riesce.
3. Il Gestore **non** vede l'import dei corsi da file nell'elenco corsi.

**Cosa non deve mai succedere:**

- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`user-dropdown-file-upload-item`, `router-file-upload-route`, `data-import-doctype-titles-i18n`, `courses-list-gestore-no-import`; fork `DataImport` di frappe-ui.

</details>

---

### P17 — Tutor AI sui materiali del corso

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Docente che carica i materiali; Studente che fa domande
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Docente carica i materiali e scrive le lezioni → vengono indicizzati; lo stato si vede nell'editor.
2. Rinomina o modifica una lezione → l'indice si aggiorna.
3. Lo studente apre il tutor AI dai pulsanti flottanti → fa una domanda sulla lezione e riceve una risposta basata sui materiali del corso.
4. Il tutor rispetta i limiti d'uso impostati per l'utente.

**Cosa non deve mai succedere:**

- Il tutor risponde con materiali di un corso a cui lo studente non è iscritto.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`lesson-ai-status`, `lesson-ai-tutor-context`, `app-ai-tutor-route-context`, `lesson-rename-rag-reindex`, `ai-fixed-buttons-layouts`; backend: `ai/` (ingestion, api, scheduler `reindex_lesson_content`), `LMSA Material`, `LMSA Chunk`, `LMSA Query Log`, `LMSA User Access`.

</details>

---

### P18 — Simulazioni con l'AI

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Docente che prepara lo scenario; Studente che si esercita
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Il Docente prepara uno scenario di simulazione con obiettivi e criteri di valutazione.
2. Lo studente avvia la simulazione → chat (o voce) con il personaggio AI; il tempo limite è rispettato.
3. Allo scadere il personaggio chiude la conversazione; lo studente termina con «Termina».
4. Lo studente riceve il resoconto con punti di forza e di miglioramento.
5. Le sessioni rispettano la quota giornaliera.

**Cosa non deve mai succedere:**

- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`router-simulation-routes`; backend: `ai/simulations/` (orchestrator, tasks `reap_stale_sessions`), `LMSA Simulation *`, `LMSA Evaluation *`, `LMSA Simulation Debrief`. Nota: in sviluppo la quota giornaliera risulta 200 volte quella impostata (bug noto B3.2, in attesa di risposta).

</details>

---

### P19 — TrueSkill legge i dati tramite l'Elite API

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Sistema TrueSkill (nessun utente); Gestore che gestisce le chiavi
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. TrueSkill chiama l'API con la chiave → riceve l'elenco di corsi e classi con i riepiloghi di avanzamento.
2. Chiede gli studenti di un corso o di una classe → li riceve con il codice fiscale.
3. Ogni chiamata viene registrata.
4. Una chiave revocata o sbagliata → la chiamata viene rifiutata.

**Cosa non deve mai succedere:**

- Una chiave dà accesso a qualcosa di diverso dalla sola lettura di quei dati.
- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`settings-elite-api-tab`; backend: `elite_api/` (auth, keys, v1, progress), `Elite API Key`, `Elite API Access Log`; guida `docs/elite-api/guida-integrazione.md`.

</details>

---

### P20 — Ricerca e navigazione

- **Stato:** [ ] Confermato  [ ] Non lo usiamo
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** Tutti
- **Quanto spesso:** ✏️

**Passi (bozza):**

1. Nelle liste (corsi, classi, quiz, compiti, programmi) si cerca per parole anche non consecutive → i risultati sono giusti; cambiando la ricerca si riparte dalla prima pagina.
2. Le liste ricordano la scheda scelta e il filtro categoria vale per la scheda attiva.
3. Cmd+K → risultati aperti sulla pagina giusta secondo il ruolo; «Cerca…» porta alla pagina di ricerca.
4. Le date sono in italiano («ieri», «3 giorni fa»).

**Cosa non deve mai succedere:**

- ✏️ _(aggiungi qui gli altri casi, uno per riga)_

**Note:**

✏️

<details><summary>Personalizzazioni coinvolte (per Claude)</summary>

`search-like-filter-words`, `courses-programs-list-search`, `batch-list-search-words`, `assessment-list-search-words`, `list-search-restarts-paging`, `courses-list-persist-tab`, `courses-list-category-per-tab`, `batch-list-default-tab-persist`, `batch-list-category-all`, `command-palette-result-routes`, `command-palette-search-page-entry`, `router-search-page-route`, `time-ago-italian`.

</details>

---

## Parte C — Percorsi da aggiungere

Qui sotto ci sono due percorsi vuoti, pronti da compilare: scrivi dopo ogni ✏️. Se te ne servono altri, copia e incolla uno dei due blocchi e cambia il numero. Anche poche righe vanno bene; un percorso vuoto lo ignoro.

### P21 — ✏️ _(nome del processo)_

- **Stato:** [x] Confermato
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** ✏️ _(ruoli)_
- **Quanto spesso:** ✏️

**Passi:**

1. ✏️ _(chi fa cosa → cosa deve succedere)_
2. ✏️
3. ✏️

**Cosa non deve mai succedere:**

- ✏️

**Note:**

✏️

### P22 — ✏️ _(nome del processo)_

- **Stato:** [x] Confermato
- **Importanza:** [ ] alta  [ ] media  [ ] bassa
- **Chi:** ✏️ _(ruoli)_
- **Quanto spesso:** ✏️

**Passi:**

1. ✏️ _(chi fa cosa → cosa deve succedere)_
2. ✏️
3. ✏️

**Cosa non deve mai succedere:**

- ✏️

**Note:**

✏️

---

## Parte D — Domande aperte di Claude

Punti su cui il codice non basta a capire cosa volete. Rispondi sotto ciascuna.

1. **Moderatore senza Gestore:** esiste davvero chi ha solo il ruolo Moderatore? Molte regole lo trattano diversamente dal Gestore.
   ✏️
2. **Docente e classi:** il Docente gestisce le classi come un moderatore (annunci, live, rimozione studenti). È voluto per tutti i Docenti?
   ✏️
3. **Valutatore e live:** il Valutatore deve solo osservare le lezioni dal vivo o anche condurle?
   ✏️
4. **Certificato senza codice fiscale:** cosa deve vedere lo studente che completa un corso TrueSkill senza codice fiscale? Oggi il certificato non viene emesso.
   ✏️
5. **Studenti da telefono:** ci sono processi che gli studenti fanno **solo** da telefono (es. quiz, compiti con foto)?
   ✏️
6. **Altro che ti viene in mente** e che non rientra in nessun percorso:
   ✏️
