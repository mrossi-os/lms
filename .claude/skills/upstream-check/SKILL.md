---
name: upstream-check
description: Usare dopo aver fatto il merge dell'upstream (frappe/lms) in un branch, per sapere quali personalizzazioni sono state ripulite o alterate. Produce un rapporto; non ripara.
---

# upstream-check — verifica dopo un merge upstream

Questa skill risponde a una domanda sola: **il merge che ho appena fatto ha rotto o ripulito le mie personalizzazioni?**

Fonte di verità: `docs/customizations/*.toml`. Progetto e motivazioni: `docs/superpowers/specs/2026-09-18-upstream-regression-harness-design.md`.

## Regola inviolabile

**Non modificare mai un test per farlo passare.** Davanti a un test rosso hai due mosse consentite:

- **(a)** riparare il **codice**, perché la regola dichiarata nell'inventario è ancora valida;
- **(b)** **fermarti e chiedere all'utente** se la regola è cambiata.

Se la regola è cambiata si aggiorna **prima l'inventario** e poi il test si riscrive da lì. Un test è un output, non un input. Vale anche per l'inventario: non cancellare una voce per far tornare verde il rilevatore.

## Passo 0 — Guardia sul branch

```bash
git branch --show-current
```

Se sei su `develop`, `master` o `main`, **fermati** e dillo all'utente: questa skill si usa su un branch di merge. Non proseguire.

## Passo 1 — Rilevatore di scostamento

```bash
python3 scripts/check_customizations.py --json
```

Leggi il JSON. Significato dei controlli:

| Controllo | Significato | Gravità |
| --- | --- | --- |
| `C1` | l'ancora non c'è più nel file: **la riga è stata ripulita dal merge** | errore |
| `C2` | il file non esiste più: l'upstream lo ha rinominato o rimosso | errore |
| `C3` | un file ha il marcatore `OSLMS-CUSTOM` ma nessuna voce lo censisce | errore |
| `C4` | una voce non ha test collegati, o il test dichiarato non esiste | avviso |

In Fase 0 gli avvisi `C4` sono attesi su tutte le voci: i test arrivano in Fase 1. Non segnalarli come problema.

## Passo 2 — Diff mirato

È il passo di maggior valore: riduce la superficie da controllare dai file del merge ai soli file censiti.

```bash
python3 scripts/check_customizations.py --list-files > /tmp/oslms-watched.txt
git diff HEAD^1..HEAD -- $(cat /tmp/oslms-watched.txt | tr '\n' ' ')
```

`HEAD^1` è il primo genitore del commit di merge, cioè lo stato del branch **prima** di ricevere l'upstream. Se il merge non è l'ultimo commit, chiedi all'utente il riferimento da cui partire e usalo al posto di `HEAD^1`.

Leggi il diff **per intero**. Per ogni voce dell'inventario il cui file compare nel diff, stabilisci quale dei tre casi si applica:

- **intatta** — il file è cambiato ma non nella parte che porta la regola;
- **a rischio** — il file è stato riscritto attorno alla regola: l'ancora c'è ancora ma il contesto è diverso, e la regola potrebbe non applicarsi più come prima;
- **persa** — l'ancora non c'è più (te lo ha già detto il Passo 1, qui capisci *come* è successo).

Un `C1` senza corrispondenza nel diff è un caso da segnalare a parte: significa che l'ancora è sparita **fuori** dal merge, quindi per mano nostra.

## Passo 3 — Rapporto

Scrivi `docs/upstream-checks/AAAA-MM-GG-<versione-upstream>.md` con:

1. **Intestazione** — data, branch, riferimenti dei due lati del merge, versione upstream.
2. **Esito in una riga** — quante voci intatte, a rischio, perse; quanti marcatori non censiti.
3. **Una sezione per ogni voce non intatta** — id, titolo, file, cosa ha fatto il merge, l'`intent` dichiarato, e la riapplicazione **proposta** (il codice, non applicato).
4. **Voci a bassa confidenza** — l'elenco delle voci `confidence = "low"` toccate dal merge, che meritano uno sguardo del committente perché la regola dichiarata potrebbe non essere quella vera.
5. **Marcatori non censiti** — i `C3`, con la voce di inventario proposta per ciascuno.

## Passo 4 — Worklog

Registra l'attività in `docs/WORKLOG.md` secondo le convenzioni del file: blocco «In sintesi» con i campi obbligatori, poi i punti 1-4 e 6. Il worklog non si committa salvo richiesta esplicita.

## Cosa questa skill NON fa (in Fase 0)

- Non applica riparazioni: le **propone** nel rapporto. La riparazione assistita in commit separati arriva in Fase 1.
- Non esegue test applicativi: non esistono ancora. Arrivano in Fase 1.
- Non tocca `frontend/src/overrides/`: quelle pagine sono congelate per scelta e si riconciliano a parte.
