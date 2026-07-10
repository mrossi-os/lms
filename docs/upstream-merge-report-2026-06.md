# Report merge upstream — 2026-06

**Merge:** commit `3caf0763` (2026-06-30) — `upstream/main` → `feature/update-version`
**Ampiezza:** ~247 commit upstream
**Cambio strutturale chiave:** frappe-ui `0.1.276` → `1.0.0-beta.7` (codemod tokens-v2, migrazione icone, shift tipografia)

**Legenda "Tipo":** Aggiunta · Redesign · Refactor · Fix · Sicurezza · Rimozione · Cosmetica · Modifica
**Colonna "Impatto custom":** riconciliazioni fatte lato nostro (os_lms / componenti custom) durante il merge; "—" = nessun impatto.

---

## 📚 Corsi
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| Courses.vue | Barra filtri tabs-first | Filtri a tab + `ClearableCombobox` + loading states | Redesign | Ripristinata `categories` (createListResource) persa nel merge; aggiunto `provide('tagColorMap')` |
| Courses.vue | Rinomina tab | Rimossa tab "New", "Live" → "Published" | Modifica | — |
| CourseForm | Autosave + Ctrl+S | Salvataggio automatico e Ctrl+S unificato | Aggiunta | Re-graft feature custom sezionate (vedi memory courseform_sectioned_custom_grafts) |
| CourseForm | Prezzo corsi a pagamento | Richiede prezzo/valuta positivi; rifiuta importo 0 | Fix | — |
| CourseForm | Certificazione | Sezione collegata alla lista Print Format | Fix | Presente sezione TrueSkill custom |
| CourseDashboard | Redesign dashboard | Tabelle ridisegnate, empty state centrati, enroll in header | Redesign | Migrati token colore vecchi (codemod) |
| VideoPreviewField / VideoPreview | Video anteprima corso | Upload + playback YouTube | Aggiunta | — |
| CourseOverview | Categoria + progress | Categoria cliccabile, titolo progresso sticky | Aggiunta | — |
| api / CourseCard | Related courses | Limitati a corsi pubblicati e visibili | Fix/Sicurezza | — |

## 🎓 Lezioni / Editor
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| BlockEditor.vue | Editor condiviso | Nuovo componente EditorJS per contenuto + note istruttore | Aggiunta | — |
| LessonForm | Redesign editor lezione | Titolo inline, toggle "Student View", card note istruttore | Redesign | Ricostruito: base upstream + graft `OsLessonForm`, `aiContext`, allowlist `EDITABLE_LESSON_FIELDS` (protegge campi AI ingestion) |
| BlockEditor | Strumenti inline | Sottolineato, barrato, allineamento, colore | Aggiunta | Dep custom `editorjs-color-picker` ripristinata in package.json |
| BlockEditor | Block tunes | Taglia/copia/incolla blocchi | Aggiunta | — |
| CourseOutline | Editing inline | Crea lezione inline, rinomina capitolo, edit solo SCORM, auto-refresh | Aggiunta | — |
| CourseOutline | Rimozione edit per-lezione | Tolta la voce "edit" per singola lezione | Modifica | — |
| api / LessonForm | Creazione atomica | Lezione + reference create insieme (no orfani) | Fix | — |
| LessonForm | Autosave titolo | Salva lezioni con solo titolo; contenuto non obbligatorio | Fix | — |

## ✅ Quiz
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| LMS Question (doctype) | Opzioni fino a 10 | Nuovi campi `option_5..10` / `possibility_5..10` | Aggiunta | — |
| Question editor | Righe dinamiche | 2–10 opzioni/possibilità con add/remove | Aggiunta | — |
| Quiz view | Scoring 10 opzioni | Render e valutazione fino a 10 opzioni | Aggiunta | — |
| QuizForm | Autosave | Rimosso Save manuale, flush all'unmount | Modifica | Ricostruito su redesign upstream + classe custom `os-list-view`; feature mobile custom superate (da rivalutare) |
| QuizForm | Inline create + delete | Creazione inline, azione elimina, breadcrumb con nome membro | Aggiunta | — |
| QuizForm | Layout ListView | Divider full-height, footer, empty state | Fix | — |

## 🎥 Classi live / Batch
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| LiveClassModal | API Dialog + Timezone | Dialog v2; Timezone da `Autocomplete` → `Combobox` | Refactor | Feature custom preservate (isEdit, Reminders, Google Meet); ripristinati import icone + `:disabled=isEdit` + token v2 persi nel merge |
| LiveClass.vue (Batch) | Migrazione icone/token | Solo cosmetica (span lucide, token v2) | Cosmetica | Tenuta versione custom (ChevronRight expand) |
| Batch / Announcements | Gate annunci | "Make Announcement" solo con studenti + bottone outline | Aggiunta/Fix | Rewire bottone→figlio via `childRef`; `Announcements.vue` espone `openAnnouncementModal`; ripristinato `v-if isPlainNotification` + import vue persi |
| Batch | Label campi orario | Ripristinate label ora perse da beta.7 | Fix | — |
| Batches.vue | Barra filtri tabs-first | Come Courses (tab + combobox + loading) | Redesign | Persistenza tab custom |
| AdminBatchDashboard | — | — | — | Ripristinato import `useRouter` perso nel merge |

## 🔔 Notifiche
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| NotificationPanel.vue + stores/notifications.js | Pannello slide-over | Sostituita la pagina con pannello stile CRM | Aggiunta | — |
| pages/Notifications.vue | Rimozione pagina | Vecchia pagina notifiche eliminata | Rimozione | Verificato: nessun import residuo lato custom |
| NotificationPanel | Tab Unread/Read | Larghezza piena + empty state condiviso | Fix | — |

## 🔍 Ricerca / Navigazione
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| CommandPalette | Palette da ricerca | La ricerca apre la command palette; menu polish | Aggiunta | — |
| pages/Search/Search.vue | Rimozione pagina Search | Sostituita dalla command palette | Rimozione | **Ripristinata**: avevamo una route custom che la usa |
| Sidebar | Fix allineamento | Rimosso `overflow-y-auto`, menu polish | Fix | — |

## 💬 Discussioni
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| Discussions | Layout master-detail | Nuova disposizione a due pannelli | Redesign | — |
| Discussions | Conteggio risposte | Reply count + apertura diretta nuove domande | Aggiunta | — |
| DiscussionReplies | Editor risposte | Renderizzato senza attendere le mentions | Fix | — |

## 🔒 Sicurezza / Media / SCORM
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| lms/lms/permissions.py | Permessi accesso lezione | Nuovo file helper permessi | Aggiunta | ⚠️ Da verificare interazione con gating custom os_lms (Docente/Valutatore) |
| api / lesson media | Media privati + gated | Media lezione privati, serviti da endpoint con controllo accesso | Sicurezza | ⚠️ Possibile impatto su AI ingestion (parsing media lezione) |
| SCORM | SCORM privato | Estratto in `private/`, servito con permesso + validazione | Sicurezza | — |
| vari (v-html) | Sanitizzazione HTML | Sanitize v-html/iframe, escapeHTML, upload quiz solo immagini | Sicurezza/Fix | Annunci: mantenuto branch `AnnouncementContent` (iframe) + `sanitizeRichHTML` |

## ⚙️ Impostazioni / Profilo / Statistiche
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| ZoomSettings / GoogleMeetSettings / AccountForm | Cosmetica | Migrazione token/icone | Cosmetica | — |
| Settings.vue | — | — | — | Tenuta versione custom (grande); API Dialog vecchia (retrocompat) |
| Members | Filtro ruoli Load More | Filtro ruolo applicato anche al "Load More" | Fix | — |
| Coupons | Salvataggio items | Salva nuovi applicable items in modifica coupon | Fix | — |
| Statistics | Guard grafici | Nasconde donut senza completamenti; esclude Admin/Guest dai signup | Fix | — |
| PersonaForm / ProfileRoles | Fix UI | Select full-width; stella rating `LucideStar` | Fix | — |

## 🎨 UI / Tema (trasversale)
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| frappe-ui | Bump 1.0-beta.7 | Aggiornamento major libreria UI | Refactor | `yarn install` obbligatorio; API legacy retrocompatibili |
| tokens-v2 | Rinomina token colore | Codemod: `surface-white`→`base`, ecc. + shift tipografia | Refactor | Codice custom migrato col codemod; `branding.py` + doctype Brand Customize allineati (fieldname v2) |
| icone | lucide → span CSS | Da componenti a classi `lucide-*` (lucide-static) | Refactor | Tenuti componenti lucide dove ours dominava (AdminHome/StudentHome/MultiLink) |
| Switch / Autocomplete / Rating | Rinomini componenti | `Switch`→`BooleanSwitch`, `Autocomplete`→`Combobox`, `Rating`→frappe-ui | Refactor/Rimozione | 6 file custom re-puntati a `BooleanSwitch`; `Autocomplete` ripristinato per FilePicker |
| vari | Coerenza visiva | Label form normalizzate, bordi/tabelle addolciti, empty state centrati, dark-mode editor | Cosmetica | — |

## 🏗️ Architettura / Utils / Dipendenze
| Componente | Titolo | Descrizione | Tipo | Impatto custom |
|---|---|---|---|---|
| @/utils | Rotto ciclo barrel | Nuovi moduli foglia: format, plyr, video, lessonForm, courseForm, batchForm, courseOutline, sanitizeRichHTML | Refactor | Rimossi resti orfani in `utils/index.js` (Plyr, escapeHTML duplicato) |
| useKeyboardShortcuts.ts + ShortcutTooltip | Scorciatoie | Composable tastiera + tooltip (Ctrl+S) | Aggiunta | — |
| ClearableCombobox.vue | Nuovo controllo | Combobox con clear per i filtri | Aggiunta | — |
| package.json | Dipendenze | +headlessui, editorjs-drag-drop, lucide-static, codemirror; −editorjs checklist/code, vue-chartjs, vue-draggable-next | Modifica | Ripristinata dep custom `editorjs-color-picker` |
| lms/locale/it.po | Traduzioni | Aggiornate da upstream | Modifica | ⚠️ **In sospeso**: duplicati msgid + 1 errore sintassi (saltato su richiesta) |

---

## Note / lavoro in sospeso
- **Traduzioni `it.po`**: ~116 msgid duplicati + 1 errore di sintassi (`restrict_ip`) — da sistemare (`bench update-po-files` o `msgcat --use-first`). Le traduzioni IT custom restano in `lms/translations/it.csv`.
- **Sicurezza media/SCORM + `permissions.py`**: verificare l'interazione col gating custom os_lms (ruoli Docente/Valutatore) e con l'AI ingestion (parsing media lezione).
- **QuizForm mobile**: le personalizzazioni mobile precedenti sono superate dal redesign upstream — rivalutare se serve.
- **Refuso preesistente**: `bg-surface-white-2` in `CourseDashboard.vue` (classe inesistente, non legata al merge).
