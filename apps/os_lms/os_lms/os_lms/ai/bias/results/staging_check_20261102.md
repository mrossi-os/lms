# Verifica della configurazione di staging — 2026-11-02

Il giro ufficiale dei test di bias (fase 7) gira nell'ambiente di sviluppo, non dentro lo staging: il codice dei test non è installato sullo staging. Prima del giro è stato verificato che quello che il test misura (modello, prompt, parametri, materiali, codice delle chiamate) sia uguale a quello attivo su elite.overside.it.

Fonti: database di staging in sola lettura (solo SELECT) e pagina pubblica `/lms` dello staging.

## Modelli

| Impostazione (LMSA Settings) | Staging | Usato nei test |
|---|---|---|
| `simulation_debrief_provider` / `simulation_debrief_model` (Coach) | openai / gpt-4o-mini | openai / gpt-4o-mini |
| `simulation_chat_provider` / `simulation_chat_model` (Tutor) | vuoto → `simulation_provider_default` openai / gpt-4o-mini | openai / gpt-4o-mini |
| `simulation_provider_fallback_order` | vuoto (nessun ripiego) | nessun ripiego |

## Prompt (LMSA Prompt Template)

| Prompt | Versione | Modificato | SHA-256 istruzioni di sistema (staging) | Copia usata nei test |
|---|---|---|---|---|
| debrief (Coach) | debrief.v1 | 2026-07-09 11:03 | `bac7c3a5345f2531…` | uguale (`datasets/debrief_prompt_staging.json`) |
| debrief, messaggio utente | | | `88322dfa1dc03fc3…` | uguale |
| tutor | tutor.v1 | 2026-06-12 15:05 | `99d192075fe004d2…` | uguale (`datasets/tutor_context_staging.json`) |

Parametri: il Coach usa temperatura 0,2 e 2000 token fissati nel codice (`tasks._ask_llm`; il valore 0,30 del desk non viene usato); il Tutor usa i predefiniti del provider (temperatura 0,7, 1024 token; i valori 0,70 / 1000 del desk non vengono passati). Il test usa gli stessi valori del codice.

## Materiali

- Simulazione SCN-0144: ultima modifica 2026-09-11, schema di valutazione "Schema 1" 2026-06-12: precedenti alla copia del 2026-11-02 (`datasets/scn0144_scenario.json`).
- Corso `corso-sales-transformation`: titolo, introduzione e descrizione attuali tutti presenti nella copia usata dal Tutor (la data di modifica del corso è di oggi, ma l'ultima modifica registrata dei contenuti è del 2026-10-27, precedente alla copia).

## Codice

Lo staging mostra la versione **1.16.35** (etichetta nella barra laterale del bundle pubblicato), commit `c681dda47`. Tra quel commit e il branch dei test, nel codice del Coach (`ai/simulations/tasks.py`, `ai/simulations/prompts/`), del Tutor (`ai/tutor/`), dei provider (`ai/utils/llm/`), del caricamento dei prompt e del contesto del corso cambia solo l'aggiunta del registratore delle tracce (`ai/utils/llm/tracing.py`), usato soltanto dai test.

## Esito

Configurazione di staging verificata: il giro ufficiale misura lo stesso modello, gli stessi prompt, gli stessi parametri e lo stesso codice di chiamata attivi sullo staging.
