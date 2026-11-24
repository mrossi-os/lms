---
name: upstream-check
description: Usare dopo aver fatto il merge dell'upstream (frappe/lms) in un branch, per sapere quali personalizzazioni sono state ripulite o alterate. Produce un rapporto; non ripara.
---

# upstream-check — verifica dopo un merge upstream

Questa skill risponde a una domanda sola: **il merge che ho appena fatto ha rotto o ripulito le mie personalizzazioni?**

Fonte di verità: `docs/customizations/*.toml` (voci di inventario) e `docs/customizations/features/<id>.toml` (catalogo delle funzionalità: una scheda per funzionalità, a cui le voci puntano con `feature`). Progetto e motivazioni: `docs/superpowers/specs/2026-09-18-upstream-regression-harness-design.md` e `docs/superpowers/specs/2026-11-23-tracciamento-personalizzazioni-design.md`.

## Regola inviolabile

**Non modificare mai un test per farlo passare.** Davanti a un test rosso hai due mosse consentite:

- **(a)** riparare il **codice**, perché la regola dichiarata nell'inventario è ancora valida;
- **(b)** **fermarti e chiedere all'utente** se la regola è cambiata.

Se la regola è cambiata si aggiorna **prima l'inventario** e poi il test si riscrive da lì. Un test è un output, non un input. Vale anche per l'inventario: non cancellare una voce per far tornare verde il rilevatore.

## Passo 0 — Guardia sul branch

```bash
git branch --show-current
```

Se sei su `develop`, `master`, `main` o `feature/oslms`, **fermati** e dillo all'utente: questa skill si usa su un branch di merge (di norma `merge/upstream-<tag>`, creato da `/upstream-upgrade`), non sul branch di partenza. Non proseguire.

## Passo 1 — Rilevatore di scostamento

```bash
python3 scripts/check_customizations.py --json
```

Leggi il JSON. Significato dei controlli:

| Controllo | Significato | Gravità |
| --- | --- | --- |
| `C0` | la base upstream non è calcolabile (mancano i tag: `git fetch upstream --tags`), quindi `C5` è stato saltato | avviso |
| `C1` | l'ancora non c'è più nel file: **la riga è stata ripulita dal merge** | errore |
| `C2` | il file non esiste più: l'upstream lo ha rinominato o rimosso | errore |
| `C3` | un file ha il marcatore `OSLMS-CUSTOM` ma nessuna voce lo censisce | errore |
| `C4` | una voce non ha test collegati, o il test dichiarato non esiste | avviso |
| `C5` | l'ancora compare anche nel file della base upstream: non distingue la nostra versione da quella upstream, quindi il suo esser presente non prova che la regola sia sopravvissuta | avviso |
| `C6` | l'ancora compare più di una volta nel file | errore |
| `C7` | una nostra traduzione registrata in `docs/customizations/translations-it.toml` non c'è più in `lms/locale/it.po`, o è cambiata | errore |
| `C8` | la voce non ha `feature`, o punta a una scheda che non esiste | avviso; errore quando esiste `docs/customizations/features/.strict` |
| `C9` | una copia congelata in `frontend/src/overrides/` non dice da quale versione upstream è stata presa (`frozen_from`) | avviso |

Dopo il merge la base è la release appena fusa: le voci con `C5` sono quelle che il Passo 2 deve guardare a mano, perché il rilevatore non può dire se la regola c'è ancora.

## Passo 2 — Diff mirato

È il passo di maggior valore: riduce la superficie da controllare dai file del merge ai soli file censiti.

Il riferimento di partenza è lo stato del branch **prima** di ricevere l'upstream. Un percorso di `/upstream-upgrade` fa più merge, quindi non è `HEAD^1`: è lo `start_commit` dello stato del percorso.

```bash
cat "$(git rev-parse --git-dir)/oslms-upstream-walk.json"
ls "$(git rev-parse --git-dir)"/oslms-upstream-walk.*.done.json
```

- Se esiste `oslms-upstream-walk.json` e il suo `branch` è il branch corrente, usa il suo `start_commit`.
- Altrimenti, se un file archiviato `oslms-upstream-walk.<target>.done.json` ha `branch` uguale al branch corrente, usa il suo `start_commit` (se più d'uno, il più recente per `started_at`).
- Altrimenti (merge fatto a mano, fuori da `/upstream-upgrade`) **chiedi all'utente** il riferimento da cui partire. Non ripiegare su `HEAD^1` da solo.

Scrivi nel rapporto quale riferimento hai usato e da dove viene. Poi, con `<partenza>` letterale:

```bash
python3 scripts/check_customizations.py --list-files > /tmp/oslms-watched.txt
git diff <partenza>..HEAD -- $(cat /tmp/oslms-watched.txt | tr '\n' ' ')
```

Leggi il diff **per intero**. Per ogni voce dell'inventario il cui file compare nel diff, stabilisci quale dei tre casi si applica:

- **intatta** — il file è cambiato ma non nella parte che porta la regola;
- **a rischio** — il file è stato riscritto attorno alla regola: l'ancora c'è ancora ma il contesto è diverso, e la regola potrebbe non applicarsi più come prima;
- **persa** — l'ancora non c'è più (te lo ha già detto il Passo 1, qui capisci *come* è successo).

Un `C1` senza corrispondenza nel diff è un caso da segnalare a parte: significa che l'ancora è sparita **fuori** dal merge, quindi per mano nostra.

## Passo 2b — Funzionalità toccate

```bash
git diff --name-only <partenza>..HEAD > /tmp/oslms-merged-files.txt
python3 scripts/customization_map.py --json
```

Le funzionalità toccate dal merge sono quelle i cui `files` nella mappa compaiono fra i file cambiati. Per ognuna:

```bash
python3 scripts/customization_map.py --feature <id>
```

e leggi la scheda `docs/customizations/features/<id>.toml`. Raccogli: titolo, file e blocchi della funzionalità toccati dal merge, esito delle sue voci (intatte, a rischio, perse dal Passo 2) e, per le regole di `behaviour` che dipendono da quei file, se il diff le lascia in piedi, le mette a rischio o le toglie. Raccogli anche i blocchi che la mappa non attribuisce a nessuna funzionalità: `python3 scripts/customization_map.py --unattributed`.

## Passo 3 — Rapporto

Scrivi `docs/upstream-checks/AAAA-MM-GG-<versione-upstream>.md` con:

1. **Intestazione** — data, branch, riferimenti dei due lati del merge, versione upstream.
2. **Esito in una riga** — quante voci intatte, a rischio, perse; quanti marcatori non censiti.
3. **Una sezione per ogni voce non intatta** — id, titolo, file, cosa ha fatto il merge, l'`intent` dichiarato, e la riapplicazione **proposta** (il codice, non applicato).
4. **Per funzionalità** — una sottosezione per ogni funzionalità toccata (Passo 2b): titolo e id, file e blocchi toccati, esito delle voci, regole di `behaviour` a rischio o perse; in coda i blocchi non attribuiti, con la funzionalità proposta per ciascuno.
5. **Voci a bassa confidenza** — l'elenco delle voci `confidence = "low"` toccate dal merge, che meritano uno sguardo del committente perché la regola dichiarata potrebbe non essere quella vera.
6. **Marcatori non censiti** — i `C3`, con la voce di inventario proposta per ciascuno.
7. **Altri esiti del rilevatore** — `C5` (con l'esito della verifica a mano), `C6`, `C7` (traduzioni perse, con la coppia da riapplicare), `C8`, `C9`.

## Passo 4 — Worklog

Registra l'attività in `docs/WORKLOG.md` secondo le convenzioni del file: blocco «In sintesi» con i campi obbligatori, poi i punti 1-4 e 6. Il worklog non si committa salvo richiesta esplicita.

## Cosa questa skill NON fa

- Non applica riparazioni: le **propone** nel rapporto. Le ripara `/upstream-upgrade` (F2), in commit separati.
- Non esegue i test applicativi: li esegue `/upstream-upgrade` al Passo 7.
- Non tocca `frontend/src/overrides/`: quelle pagine sono congelate per scelta e si riconciliano a parte (`/upstream-upgrade`, F6, con `scripts/frozen_diff.py`).
- Non decide se adottare una novità upstream al posto di una nostra funzionalità: è F5 di `/upstream-upgrade`, e decide sempre l'utente.
