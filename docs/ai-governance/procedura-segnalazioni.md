# Procedura per le segnalazioni e gli incidenti AI

| Voce | Valore |
|---|---|
| Versione | 0.1 (bozza, da approvare) |
| Data | 2026-11-03 |
| Collegata a | `politica-ai.md`, punto 7 |
| Responsabile | il responsabile della politica AI **[da nominare]** |

## Cosa si considera un incidente

- Uno studente, un docente o un gestore segnala che un'AI di Elite (Tutor, cliente simulato, Coach) lo ha trattato in modo ingiusto, offensivo o stereotipato, o ha dato una valutazione che sembra dipendere da nome, genere, origine o modo di scrivere.
- Un giro di test di equità dà un risultato fuori soglia (`politica-ai.md`, punto 6).
- Una risposta dell'AI contiene dati personali di altre persone, consigli pericolosi o contenuti fuori dal compito che il sistema doveva rifiutare.

## Passi

| # | Passo | Chi | Tempo |
|---|---|---|---|
| 1 | **Registrare** la segnalazione nel registro (`registro-test-bias.md`, sezione Segnalazioni): data, chi segnala, funzione AI, sessione o domanda interessata, descrizione | chi la riceve | subito |
| 2 | **Prendere in carico** e rispondere a chi ha segnalato che la segnalazione è in esame | responsabile | entro 5 giorni lavorativi |
| 3 | **Contenere** se serve: per un problema grave (contenuto offensivo, dati personali) si può sospendere la funzione dal pannello (simulazioni disattivabili da LMSA Settings) o tornare al prompt precedente | responsabile + sviluppo | appena accertato |
| 4 | **Verificare** sul caso reale (sessione, commento, risposta) e con un giro di test mirato che riproduca la situazione con le versioni controfattuali | sviluppo | entro 10 giorni lavorativi |
| 5 | **Correggere**: modifica del prompt, del codice o dei criteri della simulazione; per un voto del Coach contestato, il docente scrive la propria valutazione nel debrief | sviluppo, docente | secondo gravità |
| 6 | **Riprovare**: giro di test completo dopo la correzione, entro le soglie | sviluppo | prima del rilascio della correzione |
| 7 | **Chiudere**: risposta a chi ha segnalato, esito e azione nel registro, firma del responsabile | responsabile | alla chiusura |

## Regole

- Le segnalazioni si trattano in modo riservato: nel registro va il riferimento alla sessione, non i dati personali di chi ha segnalato.
- Un incidente che riguarda dati personali segue anche la procedura privacy della piattaforma (eventuale notifica di violazione ai sensi del GDPR).
- Un fornitore AI che cambia modello senza preavviso e altera i risultati è trattato come un incidente: si ripete il giro di test.
