# Context: feat-2521-s2-willkommen

Issue #2521 (Onboarding + Hilfe), Scheibe 2. Meilenstein „Going Live: externe Nutzer".
S1 (Begriff-Erklärung ⓘ + Infobox) ist seit 12.10. live (PR #2550, Spec `docs/specs/modules/begriff_erklaerung_infobox.md`).
Grundlage: Entwurf `docs/specs/modules/onboarding_hilfe_2521.md` (Status `draft`, **nie freigegeben**), Abschnitt S2, AC-4 bis AC-14.
Abgleich gegen HEAD `6fafebf3e` am 2026-10-16.

## Request Summary
Ein eingeladener Nutzer sieht nach dem ersten Login einen Willkommens-Hinweis und eine Startklar-Checkliste auf der Startseite (bis zum ersten erhaltenen Briefing), kann eine echte Testmail an seine bestätigte Adresse senden, und „+ Neuer Vergleich" führt auf `/compare/new`.

## Related Files (Ist-Stand mit Zeilen)
| File | Relevance |
|------|-----------|
| `internal/model/user.go:10-77` | `User`; vorhanden: `EmailVerifiedAt :36`, `PasskeyPromptDismissed :47` (omitempty), `IsTestUser :60`. NEU nötig: `OnboardingDismissed`, `ChecklistDismissed`, `TestMailSentAt`. `sms_allowed`/`premium_sms_allowed` sind KEINE Felder, sondern aus Tarif abgeleitet (`model.SmsAllowed(tier)`) |
| `internal/handler/auth.go:844-912` | `profileResponse` (liefert `sms_allowed :852`, `email_verified :855`, `premium_sms_allowed :878`, `passkey_prompt_dismissed :889`; `telegram_chat_id :850` omitempty) |
| `internal/handler/auth.go:928-978` | `toProfileResponse` (Passkey-Flag `:971`) |
| `internal/handler/auth.go:1021,1041,1304-1306,1339` | `UpdateProfileHandler`: Decoder `*bool`, Übernahme `if != nil`, `s.SaveUser(*user)` |
| `internal/store/user.go:76-90, :120` | `SaveUser` schreibt typisiertes Modell (Fremdfelder gehen verloren); `mergeUserJSON` erhält Fremdfelder |
| `internal/router/router.go:256` | `POST /api/notify/test` → `ProxyPostHandler` |
| `internal/handler/proxy.go:122-153, :158` | `ProxyPostHandler` (io.Copy, `appendUserID`, 120 s Timeout) |
| `internal/handler/sms_daily_usage.go:17-37` | nächstes Muster für „Python aufrufen und Antwort lesen" |
| `internal/store/log.go:10-15, :23, :103` | `BriefingLogEntry{TripID, Kind, SentAt string, Channels}`, `LoadBriefingLog` fail-soft, `BriefingCountByTrip` |
| `internal/model/compare_preset.go:35` | `letzter_versand` am Preset (Ortsvergleich) |
| `internal/handler/admin_users.go:20-33` | `AdminUser`-DTO (S5, hier nicht) |
| `src/services/channel_test_service.py:12-46` | `send_test_message`; E-Mail-Zweig `:26-31` nutzt `with_user_profile(user_id).for_testing()` — Kommentar „Issue #198: … nie Resend" |
| `src/app/config.py:362, :400, :414, :444, ~320-338` | `for_testing`, `with_user_profile`, `force_test` (staging/Testnutzer), `email_verified_at`, Resend-Default-Deny unter pytest |
| `src/outputs/email.py:239-300, :754, :782` | Resend-Allowlist (nur auf Resend-Weg) |
| `src/services/trip_report_scheduler.py:1787, :2170` | einziger Schreiber von `briefing_log.json` (schreibt zusätzlich `on_demand`, `mail_to`) |
| `src/services/scheduler_dispatch_service.py:272, :732` | Ortsvergleich setzt `letzter_versand` (geplant + manuell) |
| `frontend/src/routes/+layout.server.ts:5-33` | ein Profilabruf; reicht heute `displayName`, `hasPasskey`, `isAdmin`, `passkeyPromptDismissed :22/30` durch |
| `frontend/src/routes/+page.svelte:104, :162, :167` | `buildCompareCtaHref` → `/compare`; Kopfzeilen-Link `/compare`; Einbindung `EmptyKachel` |
| `frontend/src/routes/_home/EmptyKachel.svelte:9` | Leerzustand „Willkommen bei Gregor 20" (hart codiert), Link `/compare` |
| `frontend/src/routes/account/+page.svelte:275-290, :679, :786` | heutiger Testmail-Auslöser `sendTest` (prüft `resp?.error`) |
| `frontend/src/lib/i18n/index.ts`, `messages/de.json` | Textkatalog `t(key)`, keine Interpolation; 49 Schlüssel (`start.*`, `info.*`, `tip.*`) |
| `frontend/src/lib/components/molecules/BegriffErklaerung.svelte`, `Infobox.svelte`, `shared/infoboxKeys.ts` | S1-Bausteine (nicht `shared/Tooltip.svelte` wie im Entwurf) |

## Existing Patterns
- **Profil-Flag:** `PasskeyPromptDismissed` (#2248): Feld omitempty, Antwort immer, Decoder `*bool`. Test-Muster `internal/handler/profile_passkey_prompt_test.go:52` (PUT nur mit Flag, Nachbarfelder auf der Platte prüfen, `newTestStore`), dazu `profile_test.go`.
- **Fremdfeld-Erhalt:** nur über `mergeUserJSON` (`store/user.go:120`), nicht über `SaveUser`.
- **Frontend-Tests:** `node --test` (`frontend/package.json:13`), Beispiele `routes/__tests__/*.test.ts`. E2E: `frontend/e2e/startseite.spec.ts:58`, `issue-314-empty-state.spec.ts`, `passkey-angebot.spec.ts`.

## Dependencies
- Upstream: Profil-Endpoint `GET/PUT /api/auth/profile`, Python `/api/notify/test`, `briefing_log.json`, Preset `letzter_versand`, Textkatalog aus #2520/S1.
- Downstream: Leser von `briefing_log.json`: `briefing_slots.py:365ff`, `BriefingHistoryHandler` (`briefing_history.go:25`), **`CockpitStatusHandler` (`cockpit.go:21`, Startseite)**, **`BriefingCountByTrip` (`log.go:103`)** — die letzten beiden fehlen im Entwurf.

## Existing Specs
- `docs/specs/modules/onboarding_hilfe_2521.md` — Gesamt-Entwurf, draft, nicht freigegeben
- `docs/specs/modules/begriff_erklaerung_infobox.md` — S1, geliefert

## Abweichungen Entwurf ↔ Ist-Stand (für /20-analyse und Spec)
1. **AC-6 (Fremdfeld bleibt erhalten) ist mit `SaveUser` nicht erfüllbar.** Lösung: Setter über `mergeUserJSON` (auch für `TestMailSentAt`; zugleich sicher gegen gleichzeitigen Profil-PUT).
2. **Testmail ohne `.for_testing()` kehrt Entscheidung #198 um** („nie Resend" für Testmail). Braucht Prüfung gegen ADRs / ggf. neues ADR. `send_test_message` prüft heute **keine** bestätigte Adresse; fehlt `user.json`, fällt `with_user_profile` auf globale `mail_to` (Betreiber-Adresse) zurück → muss der Dienst selbst sperren (AC-8).
3. Konflikt-Tests: `tests/tdd/test_channel_test_button.py:82` (echte Mail mit `user_id="default"`), `tests/test_success_status_guard.py:2144` (zitiert Zeilennummern aus `channel_test_service`).
4. **`/hilfe` existiert nicht** — S1 hat sie nicht geliefert, AC-14 setzt sie voraus.
5. **Ortsvergleich schreibt keinen Log-Eintrag.** Alternative ohne Python-Änderung: „Erstes Briefing erhalten" = Trip-Log-Eintrag ODER Preset mit `letzter_versand`. Offen: setzt `:732` `letzter_versand` auch nach fehlgeschlagenem Versand? Zählt ein `on_demand`-Versand als „erstes Briefing"?
6. AC-Texte nennen „Vitest" — Runner ist `node --test`.
7. Zeilennummern im Entwurf veraltet (siehe Tabelle oben).

## Umfang
Schätzung ohne Tests/Katalog: Go ~150, Python ~30(+30–40), Frontend ~220 → **~400–440 LoC**, deutlich über 250.
Teilung laut Entwurf sinnvoll:
- **S2a:** Profil-Flags (Merge-Setter), Willkommen, Checkliste, Link-Fix (~230)
- **S2b:** Testmail-Handler, `test_mail_sent_at`, `first_briefing_at` (~170–210; kleiner mit `letzter_versand`-Ableitung)

## Risks & Considerations
- Datenverlust in `user.json` (CLAUDE.md „Daten-Schema-Reworks"): Merge statt Replace; Edit an `user.go` löst Pre-Snapshot-Hook aus.
- Mandantentrennung: Testmail nur an Profiladresse des aufrufenden Nutzers, nie `"default"`, nie Betreiber-Adresse; Zwei-Nutzer-Test Pflicht.
- Testmail-Umbau berührt Kanal-/Versandentscheidung (#198) → ADR-Prüfung.
- Checkliste „Erstes Briefing" muss beide Flächen (Trip + Ortsvergleich) zählen (Code-Teilung).
- Willkommen nur für Nutzer ohne Trips/Vergleiche und `onboarding_dismissed=false` — Bestandsnutzer dürfen nichts sehen.

## Analysis

### Type
Feature (Scheibe S2 von #2521). Workflow bleibt **eine** Scheibe S2 mit allen ACs; LoC über `workflow.py set-field loc_limit_override 500` (PO-Regel: Umfang nie eigenmächtig verengen, Scheiben nur als eigene Workflows).

### Kernbefunde (am Code belegt, 2026-10-16)
1. **Heutiger Testmail-Knopf erreicht externe Nutzer gar nicht.** `channel_test_service.py:26-31` nutzt `.for_testing()` → Stalwart-Host. Der Lokal-Guard `src/output/channels/email.py:810-850` (#1235) lässt dort nur `@henemm.com` durch → externer Eingeladener bekommt `OutputConfigError` → Dienst antwortet `{"error": …}`. Zusätzlich: fehlt `user.json`, fällt `mail_to` in `with_user_profile` auf die globale Betreiberadresse (`@henemm.com`) zurück → die passiert den Guard → **Testmail landet beim Betreiber** (Cross-User-Muster) → begründet AC-8.
2. **„Entscheidung #198" ist kein ADR**, nur Archiv-Spec `docs/specs/_archive/bugfix/bug_198_notify_test_resend.md:20-22` + Kommentar. ADR-0087 (Empfängerschutz): Fremdadressen nur über Resend und nur mit `email_verified_at` (Allowlist `email.py:242-300`).
3. **Freigegebene AC wird abgelöst:** `docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md:247-248` („E-Mail-Zweig des Test-Knopfs bleibt unverändert (#198)"), bewacht von `tests/tdd/test_telegram_inbound_reply_contract.py:414` (`verbindungen == [TEST_SMTP_HOST]`). Neue Spec muss die Ablösung **ausdrücklich** benennen; Test nicht still anpassen.
4. **Python schreibt `user.json` nirgends** (grep leer). Ein zweiter Schreiber neben Go (`mergeUserJSON`) wäre ein Race-/Datenverlustrisiko.
5. **Ortsvergleich `letzter_versand`** (`scheduler_dispatch_service.py:300-304`, Aufruf `:732`) wird auch bei `send_result.sent == False` gesetzt (nur Exception verhindert es) → als „Briefing erhalten"-Signal ungeeignet.
6. `briefing_log.json` nur Trips, nur bei Erfolg, inkl. `on_demand=true`-Einträgen (Test/Anfrage). Leser `cockpit.go:21`, `BriefingCountByTrip log.go:103`, `briefing_history.go:25`, `briefing_slots.py:365` würden bei Compare-Einträgen ohne `trip_id` falsch zählen/anzeigen.

### Varianten
**A Testmail**
| Variante | Vorteil | Nachteil |
|---|---|---|
| A1 eigener Onboarding-Pfad | Kanal-Knopf unberührt | zwei Wahrheiten; Konto-Knopf bleibt für Externe kaputt |
| A2 `.for_testing()` im E-Mail-Zweig entfernen | ein Pfad, repariert Konto-Knopf | ohne Sperre Rückfall auf Betreiberadresse |
| **A3 = A2 + Sperre im Dienst** | erfüllt AC-8 | Tests/ADR nachziehen |

→ **A3.** Dienst liest `email_verified_at` + Profil-`mail_to` des Aufrufers selbst; fehlt eins (oder `user.json`, oder `user_id` leer/`"default"`) → nichts senden, deutscher Fehlertext. Normale Versandkette (Resend-Allowlist) für echte Nutzer; Testnutzer/Staging bleiben über `force_test` auf Stalwart (E2E unverändert). Neues ADR „Nutzer-Testmail = Versand an bestätigte Profiladresse" (Ablösung der #198-Regel für echte Nutzer, Bezug ADR-0087) + Index (`tests/test_adr_index_drift.py`).

**B „Erstes Briefing erhalten"**
| Variante | Vorteil | Nachteil |
|---|---|---|
| B1 Go leitet aus Trip-Log ODER `letzter_versand` ab | kein Python | `letzter_versand` auch bei Fehlschlag; on_demand zählt mit |
| B2 Compare schreibt in `briefing_log.json` | eine Quelle | 4 Leser betroffen, Regressionsfläche |
| B3 `first_briefing_at` in `user.json` (Python) | keine Leser betroffen | zweiter Schreiber auf `user.json` → Race |
| **B3' eigene Datei `data/users/<id>/first_briefing.json`** | keine Leser betroffen, kein konkurrierender Schreiber, beide Flächen gleiche Semantik | neue kleine Datei |

→ **B3'.** Geteilter Python-Helfer, einmalig (nur schreiben, wenn Datei fehlt), nur bei echtem Erfolg; aufgerufen im Trip-Pfad nach `_append_briefing_log` (`trip_report_scheduler.py:~1787`) und im Compare-Pfad nur bei `send_result.sent`. Go liest die Datei in `toProfileResponse` (fail-soft) und liefert `first_briefing_at`; nie im PUT-Decoder. Ob Test-/Anfrage-Versände zählen: PO-Frage (s. u.).

**C Frontend:** Profilfelder über `+layout.server.ts` (ein Abruf, Passkey-Muster `+layout.svelte:78-92`, `api.put` nur eigenes Feld). `StartklarCheckliste.svelte` neu in `_home/`, Willkommen ersetzt/ergänzt `EmptyKachel.svelte`. Link-Fix `/compare` → `/compare/new` in `+page.svelte:104/162`, `EmptyKachel.svelte:9`; Fundstellen `:739/789/899` einzeln prüfen (Listen-Links bleiben `/compare`). AC-14: `/hilfe` existiert nicht und ist laut PO-Kommentar 08.10. eine spätere Scheibe → **AC-14 ohne Hilfelink formulieren** (technisch entschieden). AC-Texte: `node --test` statt Vitest.

**D Profilfelder (Go):** `OnboardingDismissed`, `ChecklistDismissed` (omitempty, in Response immer), `TestMailSentAt *time.Time`. Decoder nur die zwei `*bool`. **Alle Schreibwege über `mergeUserJSON`**, nicht `SaveUser` (AC-6 Fremdfeld). Prüfen, ob der Passkey-PUT schon `SaveUser` nutzt (dann gleicher Weg). Testmail-Zeitstempel nur bei Kanal `email` + Antwort `status==ok` — eigener Go-Handler statt `ProxyPostHandler` an `router.go:256`.

### Affected Files (with changes)
| File | Change | Description |
|---|---|---|
| `internal/model/user.go` | MODIFY | 3 neue Felder (Pre-Snapshot-Hook) |
| `internal/store/user.go` | MODIFY | Merge-Setter für Flags + `TestMailSentAt`; Lesen `first_briefing.json` |
| `internal/handler/auth.go` | MODIFY | `profileResponse`/`toProfileResponse`/`UpdateProfileHandler` |
| `internal/handler/notify.go` | CREATE | `NotifyTestHandler` (Proxy + Zeitstempel bei Erfolg) |
| `internal/router/router.go` | MODIFY | `:256` auf neuen Handler |
| `src/services/channel_test_service.py` | MODIFY | A3: ohne `.for_testing()` für echte Nutzer, Sperre bestätigte Adresse |
| `src/services/first_briefing.py` (o. ä.) | CREATE | geteilter Einmal-Setter |
| `src/services/trip_report_scheduler.py` | MODIFY | Aufruf nach Erfolg |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Aufruf nur bei `send_result.sent` |
| `frontend/src/routes/+layout.server.ts` | MODIFY | Felder durchreichen |
| `frontend/src/routes/+page.svelte` | MODIFY | Willkommen/Checkliste, Link-Fix |
| `frontend/src/routes/_home/EmptyKachel.svelte` | MODIFY | Link-Fix, Willkommen |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | CREATE | Checkliste |
| `frontend/src/lib/i18n/messages/de.json` | MODIFY | Texte |
| `docs/adr/00xx-…md` + `docs/adr/README.md` | CREATE/MODIFY | neues ADR |
| `tests/tdd/test_telegram_inbound_reply_contract.py:414`, `tests/tdd/test_channel_test_button.py:81-101`, `tests/test_success_status_guard.py` (Zeilenzitate) | MODIFY | an A3 anpassen (Ablösung benennen) |
| Neue Tests Go / Python / `node --test` / E2E | CREATE | inkl. Zwei-Nutzer- und „user.json fehlt"-Fall |

### Scope Assessment
- Dateien prod.: ~14; LoC prod. ~430–450 → `loc_limit_override 500`
- Risk Level: **MEDIUM** — Versandentscheidung (Testmail an echte Adressen), `user.json`-Schema, Mandantentrennung

### Risiken
- Mandantentrennung: alle Wege mit `user_id` aus Auth-Kontext; Zwei-Nutzer-Tests (AC-5/8/9/12) Pflicht; Test „user.json fehlt → kein Versand an Betreiber".
- Datenverlust `user.json`: nur Merge-Schreibwege.
- Bestandsnutzer mit Trips/Vergleichen dürfen den Willkommens-Hinweis nicht sehen.

### Reihenfolge
1 Spec (PO-Freigabe) → 2 Go Felder+Merge+Profil → 3 Frontend → 4 ADR + A3 + Tests → 5 Go Testmail-Handler → 6 Python B3' + Checklistenpunkt.

### PO-Entscheidungen (2026-10-16, per AskUserQuestion)
- [x] **„Erstes Briefing erhalten" zählt nur ein planmäßiges Briefing** — Test-/Anfrage-Versände (`on_demand=true`, manueller Compare-Versand) haken NICHT ab. → B3'-Helfer nur im planmäßigen Erfolgsfall aufrufen.
- [x] **Checkliste nur für neu Eingeladene** — Bestandsnutzer (Konto vor dem Live-Gang von S2) sehen sie nicht. Kein Backfill nötig. Technische Umsetzung in der Spec festlegen (z. B. Merkmal am Konto beim Anlegen/erstem Login nach Deploy, oder Kontoerstellungsdatum ≥ Stichtag) — muss mit Zwei-Nutzer-Test (alt/neu) belegt werden.
