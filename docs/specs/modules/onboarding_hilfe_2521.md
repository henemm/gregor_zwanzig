---
entity_id: onboarding_hilfe_2521
type: module
created: 2026-10-07
updated: 2026-10-07
status: draft
version: "1.1"
tags: [frontend, go, python, onboarding, hilfe, tooltip, infobox, standardwerte, testmail, admin, i18n, textkatalog, issue-2521]
---

# Onboarding und Hilfe für eingeladene Nutzer

## Approval

- [ ] Approved (PO-Freigabe ausstehend: ACs auf Deutsch lesen und mit `approved` bzw. `freigabe` bestätigen)

## Purpose

Ein eingeladener Nutzer soll vom ersten Login bis zum ersten zugestellten Briefing ohne Anleitung kommen und verstehen, was er sieht. Dazu: Willkommens-Hinweis nach dem ersten Login, Startklar-Checkliste auf der Startseite (bis zum ersten erhaltenen Briefing), eine echte Testmail an die bestätigte Adresse mit gespeichertem Sendedatum, „Mit Standardwerten speichern" in den Anlege-Editoren, eine Hilfeseite „So funktioniert Gregor", Tooltips und Infoboxen für Fachbegriffe und optionale Reiter sowie eine Admin-Übersicht, wo jeder Nutzer im Onboarding steht. Issue #2521. Baut auf dem Textkatalog aus #2520 auf. Der Editor-Aufbau selbst bleibt unverändert (ADR-0032).

## Source

- **File:** `frontend/src/routes/_home/EmptyKachel.svelte` (ersetzt/erweitert), `frontend/src/routes/+page.svelte`, `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/hilfe/` (neu), `frontend/src/routes/admin/+page.svelte`, `frontend/src/lib/components/shared/` (Tooltip, Infobox, `anlegeLockEngine.ts`, `EditorStickyFooter.svelte`), `frontend/src/lib/i18n/messages/de.json`, `internal/model/user.go`, `internal/handler/auth.go`, `internal/handler/admin_users.go`, `internal/handler/notify.go` (neu), `internal/router/router.go`, `src/services/channel_test_service.py`
- **Identifier:** `Willkommen`, `StartklarCheckliste`, `Tooltip`, `Infobox`, `canSaveWithDefaults`, `buildDefaultsPayload`, `User.OnboardingDismissed`, `User.ChecklistDismissed`, `User.TestMailSentAt`, `NotifyTestHandler`, `firstBriefingAt`, `send_test_message`

> **Schicht-Hinweis:** Full-Stack. Außerhalb des Frontends: drei Go-Profilfelder, ein eigener Go-Handler für die Testmail, eine abgeleitete Profilangabe `first_briefing_at`, Admin-DTO-Felder und der E-Mail-Zweig von `send_test_message`. Trip und Ortsvergleich teilen sich Tooltip, Infobox, `canSaveWithDefaults` und den Footer-Knopf (Parameter `context="route"|"vergleich"`); es entsteht kein Compare-Pendant.

## Estimated Scope

- **LoC:** fünf Etappen, jede ein eigener Workflow/PR, jede <= 250 LoC ohne Tests, Katalog und `docs/`. S1 ca. 180, S2 ca. 250, S3 ca. 150, S4 ca. 120, S5 ca. 130. S2 ist knapp: wird das Limit überschritten, wird sie geteilt in S2a (Flags, Willkommen, Checkliste, Link-Fix) und S2b (Testmail-Handler, `test_mail_sent_at`, `first_briefing_at`); `loc_limit_override` nur nach Rücksprache.
- **Files:** ca. 38 Code-/Katalogdateien plus Tests
- **Effort:** large (gestuft)

### Betroffene Dateien

| Datei | Etappe | Änderung | Beschreibung |
|-------|--------|----------|--------------|
| `frontend/src/lib/components/shared/Tooltip.svelte` | S1 | CREATE | Tipp-/Tastatur-/Hover-fähiger Erklär-Baustein (kein reines `title=`) |
| `frontend/src/lib/components/shared/Infobox.svelte` | S1 | CREATE | Hinweisbox „Kannst du überspringen — Standard: …" |
| `frontend/src/routes/hilfe/+page.svelte` | S1 | CREATE | Hilfeseite „So funktioniert Gregor" |
| Navigation/Footer-Komponente (Sidebar bzw. Footer) | S1 | MODIFY | Link „Hilfe" auf `/hilfe` |
| `frontend/src/lib/i18n/messages/de.json` | S1-S5 | MODIFY | Alle neuen Texte (`hilfe.*`, `onboarding.*`, `tip.*`, `info.*`, `defaults.*`, `admin.onboarding.*`) |
| `internal/model/user.go` | S2 | MODIFY | Felder `OnboardingDismissed bool` (`onboarding_dismissed`), `ChecklistDismissed bool` (`checklist_dismissed`), `TestMailSentAt *time.Time` (`test_mail_sent_at`), alle `omitempty` |
| `internal/handler/auth.go` | S2 | MODIFY | `profileResponse` gibt alle drei Felder plus abgeleitetes `first_briefing_at` aus; `UpdateProfileHandler` nimmt nur die beiden Bool-Flags an |
| `internal/handler/notify.go` | S2 | CREATE | `NotifyTestHandler`: leitet an Python weiter und setzt bei erfolgreicher E-Mail `TestMailSentAt` |
| `internal/router/router.go` | S2 | MODIFY | `r.Post("/api/notify/test", …)` (Zeile ca. 250) von `ProxyPostHandler` auf `NotifyTestHandler` umstellen |
| `frontend/src/routes/+layout.server.ts` | S2 | MODIFY | Profilfelder `email_verified`, `telegram_chat_id`, `sms_allowed`, `premium_sms_allowed`, `onboarding_dismissed`, `checklist_dismissed`, `test_mail_sent_at`, `first_briefing_at` durchreichen |
| `frontend/src/routes/+page.svelte`, `_home/EmptyKachel.svelte` | S2 | MODIFY | Willkommen + Checkliste; Link „+ Neuer Vergleich" auf `/compare/new` (`+page.svelte:162` und EmptyKachel) |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | S2 | CREATE | Checkliste mit fünf Punkten und „Ausblenden" |
| `src/services/channel_test_service.py` | S2 | MODIFY | E-Mail-Zweig über den echten Versandweg |
| `frontend/src/lib/components/shared/anlegeLockEngine.ts` | S3 | MODIFY | `canSaveWithDefaults(...)` neben `canFinish` |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | S3 | MODIFY | Zusätzlicher Knopf „Mit Standardwerten speichern" |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte` | S3 | MODIFY | Knopf anbinden, Standard-Nutzlast bauen |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor*.svelte`, `versand-tab/*`, `AlarmeTab.svelte`, `alerts-tab/AlertCooldownCard.svelte`, `AlertChannelPicker.svelte`, `layout-tab/`, `lib/utils/alertMetricLabels.ts` | S4 | MODIFY | Tooltips und Infoboxen platzieren |
| `internal/handler/admin_users.go` | S5 | MODIFY | `AdminUser` um Onboarding-Felder erweitern |
| `frontend/src/routes/admin/+page.svelte` | S5 | MODIFY | Spalten für den Onboarding-Stand |
| Tests je Etappe (`__tests__`, `tests/`, `internal/**/*_test.go`, `frontend/e2e/`) | S1-S5 | CREATE | Tests zu den ACs |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `t(key)` / `MessageKey` (`frontend/src/lib/i18n/index.ts`, #2520) | module | Einziger Ort für neue Texte; unbekannter Schlüssel ist ein TypeScript-Fehler |
| `GET/PUT /api/auth/profile` (`internal/handler/auth.go`) | endpoint | Quelle der Checklisten-Daten; `PUT` setzt die zwei Bool-Flags |
| `PasskeyPromptDismissed` (`user.go:43`, `auth.go:866/1017/1280`) | pattern | Vorlage: Pointer-Feld im Update-Decoder, Read-Modify-Write, immer vorhandenes Bool im Profil |
| `POST /api/notify/test` (`api/routers/notify.py:18`), `ProxyPostHandler` (`router.go` ca. 250) | endpoint | Testmail-Auslöser; Python antwortet auch bei Fehlern mit HTTP 200 und `{"error": …}`, nur `{"status": "ok"}` heißt gesendet |
| `Store.LoadBriefingLog` (`internal/store/log.go:23`), `briefing_log.json` je Nutzer | function | Quelle für `first_briefing_at` (Eintrag trägt `trip_id`, `kind`, `sent_at`, `channels`); Vorlage `BriefingHistoryHandler` (`briefing_history.go`) |
| `AdminListUsersHandler`, `requireAdmin` (`router.go:316`), `frontend/src/routes/admin/` | endpoint/route | Admin-Übersicht; Schutz im Router, nicht im Handler |
| `Settings.with_user_profile` (`src/app/config.py:394`) | function | Lädt Empfänger aus `data/users/<user_id>/user.json`, setzt `mail_to` nur aus dem Profil |
| `EmailOutput` (`src/output/channels/email.py`) | module | Echter Versandweg |
| `anlegeLockEngine.ts`, `EditorStickyFooter.svelte`, `WeatherMetricsTab` / `GET /api/metrics` (`default_enabled`) | module | Geteilte Anlege-Bausteine; Metrik-Vorauswahl kommt aus dem Katalog |
| `buildCreateTripPayload` (`tripNewLogic.ts:197`), `compareEditorSave.ts` | function | Speicher-Nutzlast für Trip bzw. Ortsvergleich |
| ADR-0032 (Editor-Paradigma), ADR-0066 (E-Mail-Bestätigung), ADR-0049 (Premium-SMS) | adr | Editor bleibt unverändert; Bestätigung vor Versand; Premium-SMS nur bei Tarif |

## Implementation Details

**S1 — Bausteine und Hilfeseite.**
`Tooltip.svelte`: ein Auslöser (Button mit `aria-describedby`, Fokus per Tab, Öffnen per Tipp/Enter/Leertaste, Schließen per Esc, erneuten Tipp oder Fokusverlust; Hover ist nur Zusatz). Text in `--g-ink` auf `--g-card`, Kontrast >= 4.5:1, nie `--g-ink-4`. Nicht nur `title=`, weil das auf Touch nicht erscheint. `Infobox.svelte`: Karte mit Text „Kannst du überspringen — Standard: …", Parameter `standard` und `context`. Beide Bausteine sind geteilt und nehmen nur Katalogschlüssel entgegen. Hilfeseite `/hilfe` (auch für Eingeloggte sichtbar, Link in Navigation/Footer) mit den Abschnitten: Briefing-Zeiten (morgens/abends), Alarme, Kanäle (E-Mail Hauptkanal; Telegram; SMS/Premium-SMS nur als Hinweis „je nach Tarif"), danach untergeordnet „Antwortbefehle". Die Seite nennt nirgends, dass ein Kanal einen anderen ersetzt.

**S2 — Willkommen, Checkliste, Testmail.**
*Neue Profilfelder (Schema-Änderung):* in `internal/model/user.go` drei Felder, alle `omitempty`: `OnboardingDismissed bool`, `ChecklistDismissed bool`, `TestMailSentAt *time.Time`. `profileResponse` gibt beide Bools immer aus (kein „Feld fehlt", Muster `PasskeyPromptDismissed`) und `test_mail_sent_at` als Rohzeitstempel (fehlt, solange nie gesendet). `UpdateProfileHandler` nimmt **nur** die beiden Bools als `*bool` an, jeweils `if update.X != nil { user.X = *update.X }` auf dem geladenen Objekt (Read-Modify-Write, kein Replace). `test_mail_sent_at` steht bewusst nicht im Update-Decoder: ein vom Client mitgeschickter Wert wird nie gelesen. Der Pre-Snapshot-Hook `data_schema_backup.py` greift beim Edit an `user.go`; Roundtrip-Test siehe AC-6.
*Erstlogin-Erkennung / Bestandsnutzer:* kein Backfill. Das Willkommen erscheint nur, wenn `onboarding_dismissed == false` **und** der Nutzer weder Trips noch Orts-Vergleiche hat. Es wird mit „Verstanden" weggeklickt (`PUT … {onboarding_dismissed: true}`).
*Datenfluss Home:* `+layout.server.ts` nutzt schon den Profilabruf für `passkey_prompt_dismissed` und reicht zusätzlich die in der Tabelle genannten Felder durch (kein zweiter Abruf); `+page.svelte` liest sie aus dem Layout-`data`.
*Willkommen:* Karte auf `/` oberhalb der Kacheln, nur Konto-Ebene, keine Editor-Logik: 1. Was Gregor macht (Briefing morgens/abends, Alarme), 2. Testmail an die bestätigte Adresse senden, 3. ersten Trip oder Ortsvergleich anlegen. E-Mail ist Hauptkanal; Telegram nur als optionaler Hinweis; SMS/Premium-SMS nur, wenn `sms_allowed` bzw. `premium_sms_allowed` wahr sind.
*`first_briefing_at` (abgeleitet, kein neues Schemafeld):* Die Go-Seite führt je Nutzer `briefing_log.json` (`Store.LoadBriefingLog`, fail-soft, fehlende Datei = leer). `first_briefing_at` ist der früheste `sent_at` aller Einträge dieses Nutzers; ein Eintrag steht für ein tatsächlich versendetes Briefing, egal ob Trip oder Ortsvergleich, weil das Log nicht nach Art filtert. Berechnung als kleine Funktion im Store (`FirstBriefingAt()`), vom Profil-Handler (`profileResponse`) und vom Admin-DTO genutzt, immer über `s.WithUser(<user_id aus Auth-Kontext>)`, nie `"default"`. Das ist die einfachste Variante: kein neuer Endpoint, kein zusätzlicher Abruf der Startseite. Geprüft 2026-10-07: Nur der Trip-Versand schreibt nach `briefing_log.json` (`trip_report_scheduler._append_briefing_log`, `:2148`); der Ortsvergleich-Versand schreibt keinen Eintrag. S2b ergänzt daher den Compare-Versandpfad (geplant und manuell) um einen Log-Eintrag im selben Format (`preset_id` statt `trip_id`, `kind`, `sent_at`, `channels`), ohne bestehende Leser (`briefing_slots.py`, `BriefingHistoryHandler`) zu stören.
*Startklar-Checkliste* (`StartklarCheckliste.svelte`, ersetzt den Leerzustand in `EmptyKachel.svelte`): fünf Punkte. **Pflicht:** „E-Mail bestätigt" (`email_verified`) · „Ersten Trip oder Vergleich angelegt" (Trips oder Presets nicht leer) · „Erstes Briefing erhalten" (`first_briefing_at` gesetzt). **Angezeigt, aber nicht blockierend:** „Testmail gesendet am <Datum>" (aus `test_mail_sent_at`, ohne Datum als offener Punkt mit Knopf „Testmail senden") · „Telegram verknüpft" (optional). Die Checkliste verschwindet, sobald alle drei Pflichtpunkte erledigt sind (Ziel laut Issue: bis zum ersten zugestellten Briefing). Zusätzlich hat sie „Ausblenden": der Klick setzt `checklist_dismissed=true`; danach bleibt sie dauerhaft weg, auch wenn Pflichtpunkte offen sind. Die Hilfeseite bleibt über die Navigation erreichbar.
*Testmail echter Versandweg (Python):* Heute baut der E-Mail-Zweig von `send_test_message` (`src/services/channel_test_service.py:25`) `Settings().with_user_profile(user_id).for_testing()`; `for_testing()` (`config.py:356`) lenkt SMTP auf den Test-Host (`test_smtp_*`), die Mail kommt also nie über den Produktivweg. Neu: für `channel == "email"` entfällt `.for_testing()`, es gilt `Settings().with_user_profile(user_id)`. `with_user_profile` setzt `mail_to` aus dem Profil und wählt den Test-SMTP selbst für Testnutzer und `env == staging` (`config.py:408`); Produktion läuft damit über Resend, Staging und Testnutzer weiter über Stalwart. Der Telegram-Zweig bleibt unverändert. Fehlt `mail_to` oder ist die Adresse unbestätigt (`email_verified_at` leer), antwortet der Dienst `{"error": …}` mit deutschem Text und sendet nichts. Die Mail geht ausschließlich an die Profil-Adresse. Betreff „Gregor 20 — Testmeldung" bleibt, ergänzt um einen Satz, was als Nächstes passiert.
*Testmail Zeitstempel (Go):* `NotifyTestHandler` ersetzt den bloßen Proxy. Er liest `user_id` aus dem Auth-Kontext (401 ohne), liest die Anfrage (`channel`) und reicht sie unverändert an den Python-Core weiter (Anfrage-Body wird zurückgesetzt). Nur wenn `channel == "email"` **und** die Python-Antwort `{"status": "ok"}` enthält (HTTP 200 allein genügt nicht, Python meldet Fehler als 200 mit `{"error": …}`), lädt er den Nutzer, setzt `TestMailSentAt = now` und speichert Read-Modify-Write. Fehlerhafte Antworten und Telegram-Tests ändern das Feld nie. Die Python-Antwort geht unverändert an den Client zurück.
*Link-Fix:* „+ Neuer Vergleich" führt auf `/compare/new` (statt `/compare`) in `+page.svelte:162` und `EmptyKachel`.

**S3 — Mit Standardwerten speichern.**
`canSaveWithDefaults(pflichtErfuellt: boolean): boolean` in `anlegeLockEngine.ts`, kind-neutral; Trip übergibt `name && startDate && stages.length >= 1`, Ortsvergleich `name && orte.length >= 2`. Der Knopf sitzt im geteilten `EditorStickyFooter` (neuer optionaler Slot/Prop, gleiche Optik für `context="route"` und `"vergleich"`), ist deaktiviert, solange die Pflichtfelder fehlen; Tabs bleiben nutzbar. Nutzlast: Metrik-Vorauswahl wie sie der Wetter-Metriken-Reiter standardmäßig anzeigt, also aus `GET /api/metrics` per `default_enabled`/`trip_default_enabled` (`buildDefaultsPayload(catalog)` im geteilten Baustein; dieselbe Funktion nutzt der Reiter, kein zweites Regelwerk). `TripNewEditor.svelte:103` startet `weatherMetrics` leer und füllt aus dem Reiter, deshalb berechnet der Knopf die Auswahl direkt aus dem Katalog. Versand: E-Mail an; Alarme: Kanal E-Mail als Standard, übrige Alarm-Felder aus `initialCreateTripAlarmState()`. Speichern geht denselben Weg wie „Anlegen" (`buildCreateTripPayload` bzw. Compare-Speichern), keine Nebenroute.

**S4 — Tooltips und Infoboxen platzieren.**
Tooltips (Katalogtexte `tip.*`) an: „Wertebereiche", „Kanal-Schwelle" und „Dringlichkeits-Schwelle" (`AlertChannelPicker`), „Cooldown" (`AlertCooldownCard`), „Gewitterenergie (CAPE)" (`alertMetricLabels.ts:35`; Label bleibt, Tooltip erklärt), weitere Fachbegriffe aus Layout-/Versand-Reitern. Infoboxen je Reiter („Kannst du überspringen — Standard: …") in Wertebereiche, Alarme, Versand, Layout. Alle Texte stehen im Katalog.

**S5 — Admin-Übersicht Onboarding-Stand.**
`AdminUser` (`internal/handler/admin_users.go:20`) bekommt: `test_mail_sent_at` (`*time.Time`), `has_trip_or_compare` (bool, aus den Store-Ladern des jeweiligen Nutzers), `first_briefing_at` (aus `FirstBriefingAt()`), `onboarding_dismissed` (bool); `email_verified_at` ist bereits enthalten. Die Route `GET /api/admin/users` bleibt hinter `requireAdmin` (`router.go:316`); der Handler bekommt keine eigene Rollenprüfung, kein neuer Endpoint. `frontend/src/routes/admin/+page.svelte` zeigt pro Nutzer fünf Spalten: E-Mail bestätigt · Testmail (Datum) · erster Trip/Vergleich · erstes Briefing · Willkommen weggeklickt. Katalogtexte unter `admin.onboarding.*`.

## Expected Behavior

- **Input:** erster Login eines eingeladenen Nutzers; Klick auf „Testmail senden", „Verstanden", „Ausblenden"; Anlegen eines Trips/Vergleichs; Aufruf von `/hilfe`; Admin öffnet `/admin`.
- **Output:** Willkommen und Checkliste auf `/`; Testmail im Postfach der bestätigten Adresse mit Datum in der Checkliste; gespeicherter Trip/Vergleich mit Standardwerten; Hilfeseite; Tooltips/Infoboxen; Onboarding-Spalten im Admin.
- **Side effects:** `onboarding_dismissed`, `checklist_dismissed`, `test_mail_sent_at` in `user.json` (S2); eine echte Mail pro Klick. Keine Änderung an anderen Bestandsdaten.

## Acceptance Criteria

- **AC-1 (S1):** Given ein Nutzer in einem Editor-Reiter mit Fachbegriff / When er den Begriff per Tipp auf ein Touch-Gerät oder per Tab-Taste und Enter aktiviert / Then erscheint die Erklärung lesbar und lässt sich mit Esc oder erneutem Tipp schließen, ohne dass eine Maus nötig ist.
  - Test: Vitest-Komponententest (Fokus, `aria-describedby`, Enter/Esc/Tipp); Playwright mit Touch-Emulation 375 px.
- **AC-2 (S1):** Given ein eingeloggter Nutzer / When er in der Navigation bzw. im Footer „Hilfe" wählt / Then öffnet `/hilfe` mit den Abschnitten Briefing-Zeiten, Alarme, Kanäle und einem untergeordneten Abschnitt „Antwortbefehle", E-Mail als Hauptkanal genannt und SMS/Premium-SMS nur als „je nach Tarif".
  - Test: Render-Test der Seite gegen den Katalog; Playwright gegen Staging (Link vorhanden, Seite lädt).
- **AC-3 (S1):** Given die neuen Bausteine und Katalogtexte / When der Quelltext mit einem nicht vorhandenen Schlüssel kompiliert wird / Then schlägt `svelte-check` fehl, und Tooltip/Infobox/Hilfeseite enthalten keinen deutschen Fließtext außerhalb von `t(...)`; Textfarben haben >= 4.5:1 und nutzen nie `--g-ink-4`.
  - Test: Typtest `@ts-expect-error`; Katalog-/Markup-Test (`# doc-compliance-test`); Kontrast-Node-Test der Token.
- **AC-4 (S2):** Given ein neu registrierter Nutzer ohne Trips und Vergleiche und mit `onboarding_dismissed=false` / When er sich zum ersten Mal einloggt und `/` öffnet / Then sieht er den Willkommens-Hinweis (Was Gregor macht, Testmail senden, ersten Trip oder Vergleich anlegen) und die Startklar-Checkliste; ein Bestandsnutzer mit mindestens einem Trip oder Vergleich sieht den Hinweis nicht.
  - Test: Vitest mit Layout-/Page-Daten beider Fälle; Playwright gegen Staging mit frisch angelegtem Testnutzer und mit Nutzer mit Trip.
- **AC-5 (S2):** Given der Willkommens-Hinweis / When der Nutzer „Verstanden" klickt und die Seite auf einem anderen Gerät neu lädt / Then bleibt der Hinweis weg, weil `onboarding_dismissed=true` im Profil steht, und alle übrigen Profilfelder (E-Mail, Telegram, Tarif, Passkey-Flag) sind unverändert.
  - Test: Go-Test `PUT /api/auth/profile` mit nur `onboarding_dismissed`: Nachbarfelder bleiben byte-gleich; Zwei-Nutzer-Test, Flag von Nutzer A ändert B nicht.
- **AC-6 (S2):** Given eine bestehende `user.json` ohne die neuen Felder `onboarding_dismissed`, `checklist_dismissed` und `test_mail_sent_at`, aber mit einem unbekannten Fremdfeld / When sie geladen, durch `PUT /api/auth/profile` verändert und wieder gespeichert wird / Then liefert `GET /api/auth/profile` beide Bools immer (false) und `test_mail_sent_at` nur, wenn gesetzt, und weder Fremdfeld noch bestehende Felder gehen verloren.
  - Test: Go-Roundtrip-Test mit Fixture-Altdatei inkl. Fremdfeld (Muster `passkey_angebot_banner`), je Feld einzeln und alle zusammen; Hook `data_schema_backup.py` greift bei Edit an `user.go`.
- **AC-7 (S2):** Given ein Nutzer mit bestätigter E-Mail-Adresse / When er „Testmail senden" klickt / Then kommt innerhalb weniger Minuten eine Mail über den echten Versandweg im Postfach dieser Adresse an, ohne dass ein Trip existiert, und die Checkliste zeigt „Testmail gesendet am" mit dem heutigen Datum.
  - Test: Python-Test von `send_test_message("email", uid)` mit aufgezeichnetem SMTP-Gegenstück (kein Spiegel-Mock): Verbindungshost stammt aus `Settings().with_user_profile(uid)`, nicht aus `test_smtp_host`; Staging-E2E via IMAP-Postfach (`GZ_IMAP_*`) mit Testnutzer.
- **AC-8 (S2):** Given zwei verschiedene Nutzer A und B mit unterschiedlichen Adressen / When A die Testmail auslöst / Then geht sie nur an As bestätigte Adresse, nie an B, nie an die globale Betreiber-Adresse und nie unter der `user_id` `"default"`; hat A keine bestätigte Adresse, wird nichts gesendet und A sieht einen klaren deutschen Fehlertext.
  - Test: Python-Test mit zwei Nutzerprofilen (`get_data_dir`-Isolation): Empfänger je Nutzer; Fall ohne `email_verified_at` und ohne `mail_to`.
- **AC-9 (S2):** Given ein Testmail-Aufruf / When er erfolgreich war (`status` = `ok`, Kanal E-Mail) / Then steht `test_mail_sent_at` im Profil des aufrufenden Nutzers und nur dort; bei Fehlerantwort (`error`), bei Kanal Telegram und bei einem vom Client per `PUT /api/auth/profile` mitgeschickten `test_mail_sent_at` bleibt das Feld unverändert.
  - Test: Go-Handlertest mit echtem Python-Gegenstück-Stub als HTTP-Server (Antworten `ok`, `error`, Telegram); `PUT` mit gefälschtem `test_mail_sent_at` bleibt wirkungslos; Zwei-Nutzer-Test (A löst aus, B unverändert); Mutation „2xx statt `status==ok` genügt" muss rot werden.
- **AC-10 (S2):** Given die Startseite eines Nutzers mit Tarif ohne SMS / When Willkommen und Checkliste angezeigt werden / Then erscheinen weder SMS noch Premium-SMS, Telegram nur als optionaler Hinweis ohne Blockade; bei Tarif mit `sms_allowed` bzw. `premium_sms_allowed` erscheint der jeweilige Hinweis.
  - Test: Vitest Render-Tests je Tarifstand; kein Katalogtext nennt Telegram als Pflichtschritt.
- **AC-11 (S2):** Given die Startseite ohne Trips und Vergleiche / When der Nutzer „+ Neuer Vergleich" klickt (Kopfzeile oder Leerzustand) / Then landet er auf `/compare/new` und nicht auf `/compare`.
  - Test: Render-Test beider Links; Playwright gegen Staging.
- **AC-12 (S2):** Given ein Nutzer, dem ein Briefing zugestellt wurde (Eintrag in seinem `briefing_log.json`, aus Trip oder Ortsvergleich) / When er `/` öffnet / Then zeigt die Checkliste „Erstes Briefing erhalten" als erledigt, `first_briefing_at` im Profil ist der früheste `sent_at` seines Logs, und ein anderer Nutzer ohne Eintrag sieht den Punkt weiterhin offen.
  - Test: Go-Test mit zwei Nutzerverzeichnissen (A mit Log, B ohne), je ein Eintrag von Trip und von Vergleich; fehlende/kaputte Logdatei ergibt leer statt Fehler.
- **AC-13 (S2):** Given ein Nutzer mit bestätigter E-Mail, mindestens einem Trip oder Vergleich und einem erhaltenen Briefing / When er `/` öffnet / Then ist die Checkliste verschwunden; solange einer dieser drei Pflichtpunkte offen ist, bleibt sie sichtbar. „Testmail gesendet" und „Telegram verknüpft" werden angezeigt, blockieren das Verschwinden aber nicht.
  - Test: Vitest Zustandsmatrix der fünf Punkte (Mutation: Testmail oder Telegram als Pflichtpunkt, oder „Briefing erhalten" nicht als Pflicht, muss rot werden).
- **AC-14 (S2):** Given die sichtbare Checkliste mit offenen Pflichtpunkten / When der Nutzer „Ausblenden" klickt und später auf einem anderen Gerät `/` öffnet / Then bleibt die Checkliste weg, `checklist_dismissed=true` steht im Profil, die Hilfeseite bleibt über die Navigation erreichbar, und Nachbarfelder sind unverändert.
  - Test: Go-Test `PUT` mit nur `checklist_dismissed` (Nachbarfelder byte-gleich, Zwei-Nutzer-Test); Vitest: dismissed schlägt offene Pflichtpunkte.
- **AC-15 (S3):** Given ein Trip-Editor auf `/trips/new` mit Name, Startdatum und mindestens einer Etappe / When der Nutzer „Mit Standardwerten speichern" wählt, ohne einen weiteren Reiter zu öffnen / Then wird der Trip mit der Metrik-Vorauswahl des Wetter-Metriken-Reiters, aktivem E-Mail-Versand und E-Mail als Alarm-Kanal gespeichert.
  - Test: Vitest `buildDefaultsPayload` gegen Fixture `metric_catalog_selectable.json` (Metriken = alle `default_enabled`); Playwright gegen Staging: Trip anlegen, Reiter prüfen.
- **AC-16 (S3):** Given ein Ortsvergleich-Editor auf `/compare/new` mit Name und mindestens zwei Orten / When der Nutzer „Mit Standardwerten speichern" wählt / Then wird der Vergleich mit denselben Standardwerten (Metriken, E-Mail-Versand, E-Mail-Alarm) über dieselbe geteilte Funktion gespeichert.
  - Test: Vitest, derselbe Fall parametrisiert über `context="route"|"vergleich"`; Playwright gegen Staging.
- **AC-17 (S3):** Given ein Editor mit fehlendem Pflichtfeld (z. B. kein Name, keine Etappe, weniger als zwei Orte) / When der Nutzer den Footer ansieht / Then ist „Mit Standardwerten speichern" deaktiviert und die Reiter-Freischaltung bleibt unverändert.
  - Test: Vitest `canSaveWithDefaults` Wahrheitstabelle; Mutation `>= 1` statt `>= 2` bei Orten muss rot werden.
- **AC-18 (S4):** Given der Alarme-Reiter / When der Nutzer die Begriffe „Kanal-Schwelle", „Dringlichkeits-Schwelle", „Cooldown" oder „Gewitterenergie (CAPE)" ansieht / Then ist an jedem ein Tooltip nach AC-1 erreichbar, dessen Text in einfacher Sprache erklärt, was der Begriff bewirkt.
  - Test: Vitest Render-Test je Begriff (Tooltip vorhanden, Katalogschlüssel gesetzt); Playwright Touch.
- **AC-19 (S4):** Given die Reiter Wertebereiche, Alarme, Versand und Layout im Anlege-Editor / When der Nutzer sie öffnet / Then zeigt jeder eine Infobox „Kannst du überspringen — Standard: …" mit dem tatsächlichen Standardwert, in Trip und Ortsvergleich identisch.
  - Test: Render-Test je Reiter und `context`; Review-Punkt: kein Compare-eigener Duplikat-Baustein.
- **AC-20 (S5):** Given ein Admin / When er die Admin-Seite öffnet / Then zeigt die Nutzerliste je Nutzer die Spalten E-Mail bestätigt, Testmail (Datum), erster Trip/Vergleich, erstes Briefing und Willkommen weggeklickt, jeweils mit dem tatsächlichen Stand des Nutzers (leer bzw. „nein", wenn offen).
  - Test: Go-Test `GET /api/admin/users` mit drei Nutzern in verschiedenen Ständen (Werte je Spalte); Vitest Render-Test der Spalten; Playwright gegen Staging.
- **AC-21 (S5):** Given ein eingeloggter Nutzer ohne Admin-Rolle oder ein Besucher ohne Sitzung / When er `GET /api/admin/users` oder die Admin-Seite aufruft / Then bekommt er 403 bzw. 401 und keine Onboarding-Daten anderer Nutzer.
  - Test: Go-Test mit Nutzer-Rolle und ohne Sitzung; bestehende Admin-Zugriffstests bleiben grün.

## Known Limitations

- **Testmail-Zustellung:** `test_mail_sent_at` belegt, dass der Versand erfolgreich angenommen wurde, nicht, dass die Mail im Postfach liegt. Zustellung bleibt Sache der Nutzerin bzw. des Nutzers.
- **`first_briefing_at` und Ortsvergleich:** Die Ableitung zählt, was `briefing_log.json` enthält. Der Ortsvergleich-Versand schreibt heute keinen Log-Eintrag (geprüft). S2b ergänzt ihn; bis dahin zählt der Punkt nur Trip-Briefings. Bestehende Leser des Logs filtern auf `trip_id` und dürfen durch Vergleichs-Einträge nicht anders reagieren (Regressionstest).
- Ein Briefing zählt als „erhalten", sobald es versendet wurde, nicht erst bei Zustellung/Öffnung.
- Nur Deutsch; Texte im Katalog, keine Sprachumschaltung.
- Kein Backfill der Bestandsnutzer; sie werden über „hat Trips/Vergleiche" vom Willkommen ausgenommen. Die Checkliste zeigt sich ihnen, solange ein Pflichtpunkt offen ist, bis sie „Ausblenden" klicken.
- Die Testmail kann bei fehlender Betreiber-Konfiguration (kein Resend-Token auf Produktion) auf den Test-SMTP umgelenkt werden (Default-Deny, `config.py:309`); dann meldet der Dienst den Fehler statt leise zu senden.
- Telegram-Verknüpfung bleibt außerhalb dieses Moduls (Token-Flow, #2141); die Checkliste verlinkt nur auf die Konto-Seite.
- Antwortbefehle auf der Hilfeseite sind eine kurze Übersicht, keine vollständige Befehlsreferenz.

## Architektur-Entscheidung (ADR)

Kein neues ADR nötig. ADR-0032 (Editor-Paradigma) bleibt unberührt: S3 ergänzt nur einen Footer-Knopf. Die Umstellung der Testmail auf den echten Versandweg ändert nur den E-Mail-Zweig einer Test-Funktion und hebt das Test-Routing für Test-/Staging-Nutzer nicht auf (`with_user_profile` erzwingt es weiter). Die drei Profilfelder folgen dem Muster aus #2248 (Persistenz im Go-Nutzermodell). Falls die Review dies als Kanal-/Provider-/Datenmodell-Entscheidung wertet: Abweichung ⇒ neues ADR.

## Changelog

- 2026-10-07: Initial spec created (Issue #2521), gestuft S1-S4
- 2026-10-07: PO-Entscheidungen: `test_mail_sent_at` serverseitig gesetzt (eigener Go-Handler), Checklistenpunkt „Erstes Briefing erhalten" (abgeleitet, Pflicht), `checklist_dismissed` mit „Ausblenden", Admin-Übersicht (S5); ACs neu nummeriert (AC-1..AC-21)
