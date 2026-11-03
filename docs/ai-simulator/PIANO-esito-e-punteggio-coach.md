# Piano: punteggio indicativo del Coach ed esito deciso da una persona

| Voce | Valore |
|---|---|
| Data | 2026-11-03 |
| Stato | approvato dall'utente; fasi 1-6 fatte il 2026-11-03 (non rilasciate) |
| Origine | test di equità del Coach (punto 5 ESG): `docs/ai-governance/registro-test-bias.md`, azioni A1, A5, A6 |
| Branch | `feature/esg-bias-tests` |

## Perché

Il Coach dava in media 1,5 punti in meno a chi scrive in italiano come seconda lingua e lo promuoveva meno (25% contro 42%): la penalità stava nel voto complessivo, che il Coach decide da sé. La prova 1 del 2026-11-03 (criteri su scala fissa 0-10, voto complessivo dai criteri) la riduce a −0,5 e rende il punteggio stabile, ma abbassa i promossi per tutti. Il Coach in produzione non è ancora usato: si può cambiare il sistema di voto.

Decisione: l'AI dà solo un **punteggio indicativo**; la promozione esiste solo nelle simulazioni che la prevedono e la decide **una persona**.

## Decisioni prese (2026-11-03)

1. **Punteggio indicativo** calcolato dal codice come media pesata dei voti per criterio (scala 0-10, portata su 100). Il numero scelto dal Coach resta salvato nella risposta grezza, per i test.
2. **Nessuna promozione automatica**: il codice non calcola più "superata" dalla soglia dello schema. La soglia si nasconde nell'editor degli schemi (non si cancella).
3. **Casella nella scheda della simulazione** (`LMSA Simulation Scenario`): etichetta **"Simulazione con esito (superata / non superata)"**, spenta di default, con testo di aiuto:
   > Se attiva, al termine di ogni sessione un docente, un valutatore o un gestore decide se lo studente ha superato la simulazione, con una motivazione se non è superata. Il punteggio dell'AI resta indicativo e non decide l'esito. Se non attiva, lo studente riceve solo il report con il punteggio indicativo; il docente può comunque aggiungere la sua revisione.
4. **Report a due versioni** a fine sessione, visibile allo studente:
   - **versione AI**: punteggio indicativo, voti per criterio, punti di forza, miglioramenti, consigli, lezioni suggerite; non si modifica;
   - **versione docente/valutatore**: parte dalla versione AI e si modifica (punteggio, criteri, punti di forza, miglioramenti, consigli), più un commento libero; con la casella attiva anche l'esito, con motivazione obbligatoria se "non superata". Si registrano chi, quando e cosa ha cambiato.
   - La versione AI **non contiene un esito**: lo decide solo la persona.
   - Senza casella la revisione è facoltativa ("non ancora rivista da un docente"); con la casella lo studente vede "in attesa di valutazione" finché la persona non decide.
5. **Chi rivede e decide l'esito**: Docente (corsi di cui è docente), Valutatore (solo studenti delle sue classi), Gestore, Administrator. Non il Moderator semplice.
   **Permessi completi, decisi il 2026-11-03** (sulle simulazioni contano solo Gestore, Docente, Valutatore, LMS Student e gli amministratori; il Moderator non è usato da solo):
   - **Gestore**, Administrator, System Manager: tutto, su tutti i corsi.
   - **Docente**: crea, modifica e vede le simulazioni dei corsi di cui è docente (anche quelle create da un collega dello stesso corso), con sessioni, report e versione del docente; anche senza il ruolo Creatore corsi.
   - **Valutatore**: come il Docente, sui corsi delle classi in cui è valutatore; sessioni, report e versione del docente solo per gli studenti di quelle classi (decisione 5).
   - **Moderator** senza Gestore né System Manager: nessun accesso da gestore alle simulazioni. Sullo staging (2026-11-03) i 6 Moderator hanno tutti anche Gestore o System Manager.
   - **Studente** (LMS Student): invariato, fa le simulazioni pubblicate dei corsi a cui è iscritto e vede le proprie.
6. **Lo studente vede** anche i voti per criterio e i punteggi dei tentativi precedenti; può rifare la sessione (pulsante già esistente, `clone_session`, con i limiti giornalieri). Un miglioramento si mostra solo sopra i 5 punti (sotto è rumore).
7. **Avvisi**: al docente quando una sessione aspetta l'esito, promemoria dopo 7 giorni; allo studente quando l'esito è pronto. Nessuna scadenza automatica.
8. **Debrief già esistenti** (solo staging): restano come sono, senza ricalcolo.
9. **Prompt aggiornato al deploy solo dove non è stato modificato dal pannello**: ogni record ricorda l'impronta del testo con cui il codice l'ha creato o aggiornato; a ogni migrate (in `after_migrate`, non con una patch: il deploy dello staging salta le patch) il record si aggiorna se il testo è ancora quello, altrimenti resta e si segnala.

## Fasi

| # | Fase | Contenuto |
|---|---|---|
| 1 | Punteggio stabile | prompt predefinito `debrief.v2` = testo della prova 1 (criteri 0-10, regola di equità); punteggio complessivo calcolato dai criteri in `ai/simulations/prompts/debrief.py` e usato in `tasks.py`; il runner dei test di equità usa lo stesso calcolo |
| 2 | Via la promozione automatica | `lmsa_simulation_debrief.py` non calcola più `passed`; tolti l'etichetta "Superata/Non superata" (`TranscriptDrawer.vue`), il "Tasso di successo" calcolato dall'AI (`InstructorReports.vue`, `api.py`), la soglia dall'editor e dal generatore AI degli schemi |
| 3 | Casella nella simulazione | campo nello scenario, editor della simulazione, testo di aiuto |
| 4 | Report a due versioni | versione docente modificabile (campi o tabelle nuove sul debrief), esito con motivazione, storia delle modifiche; la correzione del punteggio e l'"Instructor Review" esistenti confluiscono qui |
| 5 | Permessi | Gestore/amministratori tutto; Docente sui suoi corsi; Valutatore sui corsi delle sue classi, solo i suoi studenti; Moderator da solo niente; controlli lato server (API e regole dei doctype di scenario, sessione e debrief) e schede della SPA |
| 6 | Pagine dello studente | report a fine sessione, stati "non ancora rivista" / "in attesa di valutazione", punteggi dei tentativi |
| 7 | Report docenti | media, distribuzione, miglioramento tra tentativi, tasso di superamento solo sugli esiti decisi da persone, sessioni da valutare |
| 8 | Avvisi | notifiche al docente e allo studente, promemoria a 7 giorni |
| 9 | Prompt al deploy | aggiornamento in `after_migrate` solo dei record non modificati, con segnalazione degli altri |
| 10 | Test di equità | giro del Coach (solo OpenAI) con prompt e calcolo finali; soglia 6 sostituita da "quota di punteggi sotto 50 non più alta di un quarto rispetto alla versione senza nome"; calcolo automatico delle soglie nei rapporti; giudici Gemini dopo la ricarica |
| 11 | Documenti e traduzioni | politica (punto 5, soglia 6, nota AI Act: l'impatto si riduce ma la classificazione va confermata dal legale), registro (A1, A5, A6), stringhe in `it.csv` e `it.po` |
| 12 | Staging, poi produzione | prova sullo staging con gli account di prova, poi rilascio |

Stima: 6-8 giorni di sviluppo e test, più i giri di equità.

## Note

- **Fase 2, cosa resta di proposito:** il campo `passed` del debrief e il campo `passing_threshold` dello schema restano nel database (il secondo nascosto nel pannello e nell'editor); l'esportazione e l'importazione degli schemi lo portano ancora con sé. Il runner dei test di equità calcola ancora i promossi con la soglia dello schema: va sostituito nella fase 10. Il prompt del generatore AI degli schemi è cambiato nel codice (`eval_schema_gen_ai.v2`, senza soglia), ma i record già nel database lo citano ancora finché non arriva la fase 9; la soglia che eventualmente restituisce non viene più copiata nell'editor.
- **Fase 3:** il campo si chiama `has_human_outcome` (Check, spento di default) ed è nella sezione dello schema di valutazione; passa da `get_scenario` e `save_scenario` e dall'esportazione/importazione JSON dell'editor, ma non dal generatore AI degli scenari (lo decide il docente). Per ora non cambia nulla per lo studente: lo useranno le fasi 4-8.
- **Fase 4, decisioni dell'utente (2026-11-03):** lo studente vede la versione del docente solo dopo "Pubblica"; il punteggio del docente è un numero libero 0-100 (non ricalcolato dai criteri); con la casella attiva l'esito serve per pubblicare. Una volta pubblicata, ogni salvataggio arriva subito allo studente e l'esito non torna "da decidere"; si può eliminare solo una bozza.
- **Fase 4, com'è fatta:** campi `review_*`, `outcome*` e `review_published_*` sul debrief, che riusano le tabelle figlie dell'AI (`review_criterion_scores`, `review_strengths`, `review_improvements`); il commento libero è il vecchio `instructor_review`. La storia delle modifiche la registra Frappe (track changes già attivo). `passed` = 1 solo se la versione è pubblicata con esito "superata". Sostituiti "Correggi voto" e "Nota docente" (endpoint `instructor_override_score`, `instructor_reset_score`, `instructor_review_debrief` e campi `ai_overall_score`, `score_override_*`, mai usati sullo staging: 0 su 48 debrief al 2026-11-03). Il docente modifica voti e note dei criteri dell'AI ma non ne aggiunge di nuovi. Il report docenti conta ancora solo i miglioramenti e i punteggi dell'AI: cosa usare (AI o docente) lo decide la fase 7. Per ora la pagina dello studente mostra solo il commento del docente pubblicato: il resto della versione e l'esito arrivano con la fase 6. I permessi sono quelli della fase 5.
- **Fase 5, com'è fatta:** tutte le regole stanno in `ai/simulations/access.py` (`has_full_access`, `managed_courses`, `can_manage_course`, `may_author`, `review_scope`, `can_review`) e le usano gli endpoint di `api.py`, quelli delle valutazioni di qualità (`eval/permissions.py`, che ora chiedono anche l'accesso alle sessioni citate nelle tracce, perché contengono le trascrizioni), la chiusura della sessione vocale e le regole dei doctype di scenario, sessione, debrief e schema. Il Docente non ha più bisogno del ruolo Course Creator: basta essere tra i docenti del corso. Gli schemi di valutazione: il Gestore li vede e modifica tutti; gli altri vedono i propri, quelli condivisi e quelli usati dagli scenari dei corsi che gestiscono, e modificano solo i propri. La scheda Simulazioni del corso ora si vede anche per il Valutatore. Restano fuori di proposito: il Tutor (`lmsa_query_log.py` dà ancora tutto al Moderator, non è oggetto del piano) e i permessi del Desk (il Valutatore e il Docente senza Course Creator non hanno righe di permesso sui doctype delle simulazioni: lavorano solo dalla SPA, come prima).
- **Fase 6, decisioni dell'utente (2026-11-03):** report dello studente a **due schede** (Docente / AI; la scheda Docente compare solo con la versione pubblicata e si apre per prima); nella lista dei tentativi **un solo punteggio**, quello del docente se pubblicato, altrimenti quello dell'AI marcato "indicativo"; pulsante **"Rifai la simulazione"** nel report.
- **Fase 6, com'è fatta:** lo studente ora riceve il punteggio indicativo e i voti per criterio dell'AI (prima nascosti, commit `33b550c9d`) e, una volta pubblicata, la versione del docente intera con i suoi punteggi. Sopra le schede lo stato: esito con motivazione e chi l'ha deciso, "In attesa di valutazione" (simulazione con esito, versione non pubblicata, bozze comprese) o "Non ancora rivista da un docente". Nel lanciatore (Tentativi) ogni tentativo mostra punteggio, fonte (docente / indicativo), esito o "In attesa di valutazione" e "+N" solo se supera di più di 5 punti il tentativo precedente dello stesso scenario (calcolato sul punteggio mostrato, che può essere del docente o dell'AI). "Rifai la simulazione" usa `clone_session` (stessi controlli e limiti di un avvio) e apre il briefing; compare solo a chi ha fatto la sessione. La pagina mostra la versione del docente solo pubblicata anche a chi rivede la sessione: le bozze si lavorano nel pannello della trascrizione. La vecchia pagina `CourseStudentSimulations.vue` non è più usata da nessuna parte e non è stata toccata.
- **Fasi 1 e 2 vanno rilasciate insieme.** Con la sola fase 1 la soglia di promozione dei 70 resta attiva su un punteggio calcolato dai criteri, che è più basso: i promossi scenderebbero per tutti (dal 37-45% al 9-17% nei test).
- **Lo staging non riceve il prompt v2 da solo**: il suo record `debrief` è stato modificato dal pannello (regola di equità, impronta `169d9628…`) e non verrà toccato nemmeno dalla fase 9. Senza la scala fissa 0-10 il Coach sceglie la scala di ogni criterio e il punteggio calcolato oscilla di più (±9,3 contro ±2,6 nei test): al rilascio il testo del prompt sullo staging va sostituito con quello di `debrief.v2` (impronta `bb628576…`) dal pannello.

- `prompt_version` del debrief registra la costante del codice, non la versione né l'impronta del testo realmente usato (il prompt dello staging è modificato dal pannello ma porta ancora `debrief.v1`): da valutare insieme alla fase 9.
- L'AI Act include tra i sistemi ad alto rischio quelli che valutano i risultati dell'apprendimento anche solo per orientare lo studente: togliere la promozione automatica riduce l'impatto ma non decide da solo la classificazione.
