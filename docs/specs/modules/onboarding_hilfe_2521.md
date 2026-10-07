---
entity_id: onboarding_hilfe_2521
type: module
created: 2026-10-07
updated: 2026-10-07
status: draft
version: "1.0"
tags: [frontend, go, python, onboarding, hilfe, tooltip, infobox, standardwerte, testmail, i18n, textkatalog, issue-2521]
---

# Onboarding und Hilfe für eingeladene Nutzer

## Approval

- [ ] Approved (PO-Freigabe ausstehend: ACs auf Deutsch lesen und mit `approved` bzw. `freigabe` bestätigen)

## Purpose

Ein eingeladener Nutzer soll vom ersten Login bis zum ersten zugestellten Briefing ohne Anleitung kommen und verstehen, was er sieht. Dazu: Willkommens-Hinweis nach dem ersten Login, Startklar-Checkliste auf der Startseite, eine echte Testmail an die bestätigte Adresse, „Mit Standardwerten speichern" in den Anlege-Editoren, eine Hilfeseite „So funktioniert Gregor" sowie Tooltips und Infoboxen für Fachbegriffe und optionale Reiter. Issue #2521. Baut auf dem Textkatalog aus #2520 auf. Der Editor-Aufbau selbst bleibt unverändert (ADR-0032).

## Source

- **File:** `frontend/src/routes/_home/EmptyKachel.svelte` (ersetzt/erweitert), `frontend/src/routes/+page.svelte`, `frontend/src/routes/+page.server.ts`, `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/hilfe/` (neu), `frontend/src/lib/components/shared/` (Tooltip, Infobox, `anlegeLockEngine.ts`, `EditorStickyFooter.svelte`), `frontend/src/lib/i18n/messages/de.json`, `internal/model/user.go`, `internal/handler/auth.go`, `api/routers/notify.py`, `src/services/channel_test_service.py`
- **Identifier:** `Willkommen`, `StartklarCheckliste`, `Tooltip`, `Infobox`, `canSaveWithDefaults`, `buildDefaultsPayload`, `User.OnboardingDismissed`, `send_test_message`

> **Schicht-Hinweis:** Full-Stack, aber nur drei kleine Eingriffe außerhalb des Frontends: ein Go-Profilfeld (S2), der E-Mail-Zweig von `send_test_message` (S2) und nichts sonst. Trip und Ortsvergleich teilen sich Tooltip, Infobox, `canSaveWithDefaults` und den Footer-Knopf (Parameter `context="route"|"vergleich"`); es entsteht kein Compare-Pendant.

## Estimated Scope

- **LoC:** vier Etappen, jede ein eigener Workflow/PR, jede <= 250 LoC ohne Tests, Katalog und `docs/`. S1 ca. 180, S2 ca. 240, S3 ca. 150, S4 ca. 120.
- **Files:** ca. 30 Code-/Katalogdateien plus Tests
- **Effort:** large (gestuft)

### Betroffene Dateien

| Datei | Etappe | Änderung | Beschreibung |
|-------|--------|----------|--------------|
| `frontend/src/lib/components/shared/Tooltip.svelte` | S1 | CREATE | Tipp-/Tastatur-/Hover-fähiger Erklär-Baustein (kein reines `title=`) |
| `frontend/src/lib/components/shared/Infobox.svelte` | S1 | CREATE | Hinweisbox „Kannst du überspringen — Standard: …" |
| `frontend/src/routes/hilfe/+page.svelte` | S1 | CREATE | Hilfeseite „So funktioniert Gregor" |
| Navigation/Footer-Komponente (Sidebar bzw. Footer) | S1 | MODIFY | Link „Hilfe" auf `/hilfe` |
| `frontend/src/lib/i18n/messages/de.json` | S1-S4 | MODIFY | Alle neuen Texte (`hilfe.*`, `onboarding.*`, `tip.*`, `info.*`, `defaults.*`) |
| `internal/model/user.go` | S2 | MODIFY | Feld `OnboardingDismissed bool` (`json:"onboarding_dismissed,omitempty"`) |
| `internal/handler/auth.go` | S2 | MODIFY | `profileResponse` und `UpdateProfileHandler` um `onboarding_dismissed` erweitern |
| `frontend/src/routes/+layout.server.ts` | S2 | MODIFY | Profilfelder `email_verified`, `telegram_chat_id`, `tier`, `sms_allowed`, `premium_sms_allowed`, `onboarding_dismissed` durchreichen |
| `frontend/src/routes/+page.svelte`, `_home/EmptyKachel.svelte` | S2 | MODIFY | Willkommen + Checkliste; Link „+ Neuer Vergleich" auf `/compare/new` (`+page.svelte:162` und EmptyKachel) |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | S2 | CREATE | Checkliste mit vier Punkten |
| `src/services/channel_test_service.py` | S2 | MODIFY | E-Mail-Zweig über den echten Versandweg |
| `frontend/src/lib/components/shared/anlegeLockEngine.ts` | S3 | MODIFY | `canSaveWithDefaults(...)` neben `canFinish` |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | S3 | MODIFY | Zusätzlicher Knopf „Mit Standardwerten speichern" |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte` | S3 | MODIFY | Knopf anbinden, Standard-Nutzlast bauen |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor*.svelte`, `versand-tab/*`, `AlarmeTab.svelte`, `alerts-tab/AlertCooldownCard.svelte`, `AlertChannelPicker.svelte`, `layout-tab/`, `lib/utils/alertMetricLabels.ts` | S4 | MODIFY | Tooltips und Infoboxen platzieren |
| Tests je Etappe (`__tests__`, `tests/`, `internal/**/_test.go`, `frontend/e2e/`) | S1-S4 | CREATE | Tests zu den ACs |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `t(key)` / `MessageKey` (`frontend/src/lib/i18n/index.ts`, #2520) | module | Einziger Ort für neue Texte; unbekannter Schlüssel ist ein TypeScript-Fehler |
| `GET/PUT /api/auth/profile` (`internal/handler/auth.go`) | endpoint | Quelle für `email_verified`, `telegram_chat_id`, `tier`, `sms_allowed`, `premium_sms_allowed`; `PUT` setzt das neue Flag |
| `PasskeyPromptDismissed` (`user.go:43`, `auth.go:866/1017/1280`) | pattern | Vorlage: Pointer-Feld im Update-Decoder, Read-Modify-Write, immer vorhandenes Bool im Profil |
| `POST /api/notify/test` (`api/routers/notify.py:18`) | endpoint | Testmail-Auslöser (`channel: "email"`) |
| `Settings.with_user_profile` (`src/app/config.py:394`) | function | Lädt Empfänger aus `data/users/<user_id>/user.json`, setzt `mail_to` nur aus dem Profil |
| `EmailOutput` (`src/output/channels/email.py`) | module | Echter Versandweg |
| `anlegeLockEngine.ts`, `EditorStickyFooter.svelte`, `WeatherMetricsTab` / `GET /api/metrics` (`default_enabled`) | module | Geteilte Anlege-Bausteine; Metrik-Vorauswahl kommt aus dem Katalog |
| `buildCreateTripPayload` (`tripNewLogic.ts:197`), `compareEditorSave.ts` | function | Speicher-Nutzlast für Trip bzw. Ortsvergleich |
| ADR-0032 (Editor-Paradigma), ADR-0066 (E-Mail-Bestätigung), ADR-0049 (Premium-SMS) | adr | Editor bleibt unverändert; Bestätigung vor Versand; Premium-SMS nur bei Tarif |

## Implementation Details

**S1 — Bausteine und Hilfeseite.**
`Tooltip.svelte`: ein Auslöser (Button mit `aria-describedby`, Fokus per Tab, Öffnen per Tipp/Enter/Leertaste, Schließen per Esc, erneuten Tipp oder Fokusverlust; Hover ist nur Zusatz). Text in `--g-ink` auf `--g-card`, Kontrast >= 4.5:1, nie `--g-ink-4`. Nicht nur `title=`, weil das auf Touch nicht erscheint. `Infobox.svelte`: Karte mit Text „Kannst du überspringen — Standard: …", Parameter `standard` und `context`. Beide Bausteine sind geteilt und nehmen nur Katalogschlüssel entgegen. Hilfeseite `/hilfe` (auch für Eingeloggte sichtbar, Link in Navigation/Footer) mit den Abschnitten: Briefing-Zeiten (morgens/abends), Alarme, Kanäle (E-Mail Hauptkanal; Telegram; SMS/Premium-SMS nur als Hinweis „je nach Tarif"), danach untergeordnet „Antwortbefehle". Die Seite nennt nirgends, dass ein Kanal einen anderen ersetzt.

**S2 — Willkommen, Checkliste, Testmail.**
*Erstlogin-Erkennung:* neues Feld `OnboardingDismissed bool` in `internal/model/user.go` (`omitempty`, `json:"onboarding_dismissed"`), Muster `PasskeyPromptDismissed`. `profileResponse` gibt es immer aus (kein „Feld fehlt"). `UpdateProfileHandler` nimmt es als `*bool` an; `if update.OnboardingDismissed != nil { user.OnboardingDismissed = *update.OnboardingDismissed }` auf dem geladenen Objekt (Read-Modify-Write, kein Replace). Schema-Änderung: der Pre-Snapshot-Hook greift automatisch; Migrations-/Roundtrip-Test siehe AC-S2-6.
*Bestandsnutzer:* kein Backfill. Angezeigt wird das Willkommen nur, wenn `onboarding_dismissed == false` **und** der Nutzer weder Trips noch Orts-Vergleiche hat. Wer schon etwas angelegt hat, sieht es nie, ohne dass `user.json` angefasst wird. Das Flag wird gesetzt, sobald der Nutzer „Verstanden" klickt oder die Checkliste vollständig erledigt ist.
*Datenfluss Home:* `+layout.server.ts` liest schon denselben Profilabruf (`passkey_prompt_dismissed`); er gibt zusätzlich `emailVerified`, `telegramChatId`, `tier`-abgeleitete `smsAllowed`/`premiumSmsAllowed` und `onboardingDismissed` weiter (kein zweiter Abruf). `+page.svelte` liest sie über `data` aus dem Layout.
*Willkommen:* Karte auf `/` oberhalb der Kacheln, nur Konto-Ebene, keine Editor-Logik: 1. Was Gregor macht (Briefing morgens/abends, Alarme), 2. Testmail an die bestätigte Adresse senden, 3. ersten Trip oder Ortsvergleich anlegen. E-Mail ist Hauptkanal; Telegram erscheint nur als optionaler Hinweis; SMS/Premium-SMS nur, wenn `smsAllowed` bzw. `premiumSmsAllowed` wahr sind.
*Startklar-Checkliste* (`StartklarCheckliste.svelte`, ersetzt den Leerzustand in `EmptyKachel.svelte`, sichtbar bis alles Pflichtige erledigt): „E-Mail bestätigt" (`email_verified`) · „Testmail gesendet" · „Ersten Trip oder Vergleich angelegt" (Trips oder Presets nicht leer) · „Telegram verknüpft" (optional, blockiert nicht, ausgegraut als „optional"). Ist die Checkliste vollständig bis auf Telegram, verschwindet sie.
*Testmail über den echten Versandweg:* Heute baut der E-Mail-Zweig von `send_test_message` (`src/services/channel_test_service.py:25`) `Settings().with_user_profile(user_id).for_testing()`; `for_testing()` (`config.py:356`) lenkt `smtp_host/-user/-pass` auf den Test-SMTP (`test_smtp_*`), also kommt die Mail nie über den Produktivweg. Neu: für `channel == "email"` entfällt `.for_testing()`, es gilt `Settings().with_user_profile(user_id)`. `with_user_profile` setzt `mail_to` aus dem Profil des Nutzers und wählt den Test-SMTP selbst für Testnutzer und `env == staging` (`config.py:408`); damit läuft Produktion über Resend, Staging und Testnutzer weiter über Stalwart. Der Telegram-Zweig bleibt unverändert. Die `user_id` kommt aus dem Auth-Kontext (Go-Proxy reicht sie durch), nie `"default"`; fehlt `mail_to` oder ist die Adresse unbestätigt (`email_verified_at` leer), antwortet der Dienst `{"error": ...}` mit klarem deutschem Text und sendet nichts. Die Mail geht ausschließlich an die Profil-Adresse, nie an die globale Betreiber-Adresse. Absender, Betreff („Gregor 20 — Testmeldung") und Text bleiben, ergänzt um einen Satz, was als Nächstes passiert.
*Link-Fix:* „+ Neuer Vergleich" führt auf `/compare/new` (statt `/compare`) in `+page.svelte:162` und `EmptyKachel`.

**S3 — Mit Standardwerten speichern.**
`canSaveWithDefaults(pflichtErfuellt: boolean): boolean` in `anlegeLockEngine.ts`, kind-neutral; Trip übergibt `name && startDate && stages.length >= 1`, Ortsvergleich `name && orte.length >= 2`. Der Knopf sitzt im geteilten `EditorStickyFooter` (neuer optionaler Slot/Prop, gleiche Optik für `context="route"` und `"vergleich"`), ist deaktiviert, solange die Pflichtfelder fehlen, und blendet sich nicht von den Tabs ab: Tabs bleiben nutzbar. Nutzlast: Metrik-Vorauswahl wie sie der Wetter-Metriken-Reiter standardmäßig anzeigt, also aus `GET /api/metrics` per `default_enabled`/`trip_default_enabled` (ein Hilfsaufruf `buildDefaultsPayload(catalog)` im geteilten Baustein; dieselbe Funktion nutzt der Reiter, kein zweites Regelwerk). Hinweis: `TripNewEditor.svelte:103` startet `weatherMetrics` leer und füllt aus dem Reiter, deshalb darf der Knopf nicht auf den Reiterstand warten, sondern berechnet die Auswahl direkt aus dem Katalog. Versand: E-Mail an; Alarme: Kanal E-Mail als Standard, übrige Alarm-Felder aus `initialCreateTripAlarmState()`. Speichern geht denselben Weg wie „Anlegen" (`buildCreateTripPayload` bzw. Compare-Speichern), keine Nebenroute.

**S4 — Tooltips und Infoboxen platzieren.**
Tooltips (Katalogtexte `tip.*`) an: „Wertebereiche", „Kanal-Schwelle" und „Dringlichkeits-Schwelle" (`AlertChannelPicker`), „Cooldown" (`AlertCooldownCard`), „Gewitterenergie (CAPE)" (`alertMetricLabels.ts:35`; der Label-Text bleibt, der Tooltip erklärt ihn), weitere Fachbegriffe aus Layout-/Versand-Reitern. Infoboxen je Reiter („Kannst du überspringen — Standard: …") in Wertebereiche, Alarme, Versand, Layout. Alle Texte stehen im Katalog; kein deutscher Fließtext im Markup.

## Expected Behavior

- **Input:** erster Login eines eingeladenen Nutzers; Klick auf „Testmail senden"; Anlegen eines Trips/Vergleichs; Aufruf von `/hilfe`.
- **Output:** Willkommens-Hinweis und Checkliste auf `/`; Testmail im Postfach der bestätigten Adresse; gespeicherter Trip/Vergleich mit Standardwerten; Hilfeseite; Tooltips/Infoboxen in den Reitern.
- **Side effects:** `onboarding_dismissed` im Profil (S2); eine echte Mail pro Klick (S2). Keine Änderung an Bestandsdaten anderer Felder.

## Acceptance Criteria

- **AC-1 (S1):** Given ein Nutzer in einem Editor-Reiter mit Fachbegriff / When er den Begriff per Tipp auf ein Touch-Gerät oder per Tab-Taste und Enter aktiviert / Then erscheint die Erklärung lesbar und lässt sich mit Esc oder erneutem Tipp schließen, ohne dass eine Maus nötig ist.
  - Test: Vitest-Komponententest (Fokus, `aria-describedby`, Enter/Esc/Tipp); Playwright mit Touch-Emulation 375 px.
- **AC-2 (S1):** Given ein eingeloggter Nutzer / When er in der Navigation bzw. im Footer „Hilfe" wählt / Then öffnet `/hilfe` mit den Abschnitten Briefing-Zeiten, Alarme, Kanäle und einem untergeordneten Abschnitt „Antwortbefehle", E-Mail als Hauptkanal genannt und SMS/Premium-SMS nur als „je nach Tarif".
  - Test: Render-Test der Seite gegen den Katalog; Playwright gegen Staging (Link vorhanden, Seite lädt).
- **AC-3 (S1):** Given die neuen Bausteine und Katalogtexte / When der Quelltext mit einem nicht vorhandenen Schlüssel kompiliert wird / Then schlägt `svelte-check` fehl, und Tooltip/Infobox/Hilfeseite enthalten keinen deutschen Fließtext außerhalb von `t(...)`; Textfarben haben >= 4.5:1 und nutzen nie `--g-ink-4`.
  - Test: Typtest `@ts-expect-error`; Katalog-/Markup-Test (`# doc-compliance-test`); Kontrast-Node-Test der Token.
- **AC-4 (S2):** Given ein neu registrierter Nutzer ohne Trips und Vergleiche und mit `onboarding_dismissed=false` / When er sich zum ersten Mal einloggt und `/` öffnet / Then sieht er den Willkommens-Hinweis (Was Gregor macht, Testmail senden, ersten Trip oder Vergleich anlegen) und die Startklar-Checkliste; ein Bestandsnutzer mit mindestens einem Trip oder Vergleich sieht ihn nicht.
  - Test: Vitest mit Layout-/Page-Daten beider Fälle; Playwright gegen Staging mit frisch angelegtem Testnutzer und mit Nutzer mit Trip.
- **AC-5 (S2):** Given der Willkommens-Hinweis / When der Nutzer „Verstanden" klickt und die Seite auf einem anderen Gerät neu lädt / Then bleibt der Hinweis weg, weil `onboarding_dismissed=true` im Profil steht, und alle übrigen Profilfelder (E-Mail, Telegram, Tarif, Passkey-Flag) sind unverändert.
  - Test: Go-Test `PUT /api/auth/profile` mit nur `onboarding_dismissed`: Nachbarfelder bleiben byte-gleich; Zwei-Nutzer-Test, Flag von Nutzer A ändert B nicht.
- **AC-6 (S2):** Given eine bestehende `user.json` ohne Feld `onboarding_dismissed` / When sie geladen, durch `PUT /api/auth/profile` verändert und wieder gespeichert wird / Then ist `GET /api/auth/profile` immer mit `onboarding_dismissed` (false) vorhanden, und kein unbekanntes Feld der Datei geht verloren.
  - Test: Go-Roundtrip-Test mit Fixture-Altdatei inkl. Fremdfeld (Muster `passkey_angebot_banner`); Hook `data_schema_backup.py` greift bei Edit an `user.go`.
- **AC-7 (S2):** Given ein Nutzer mit bestätigter E-Mail-Adresse / When er „Testmail senden" klickt / Then kommt innerhalb weniger Minuten eine Mail über den echten Versandweg im Postfach dieser Adresse an, ohne dass ein Trip existiert, und die Checkliste zeigt „Testmail gesendet".
  - Test: Python-Test von `send_test_message("email", uid)` mit aufgezeichnetem SMTP-Gegenstück (kein Mock der eigenen Annahme): der Verbindungshost ist der aus `Settings().with_user_profile(uid)` und nicht `test_smtp_host`; Staging-E2E via IMAP-Postfach (`GZ_IMAP_*`) mit Testnutzer.
- **AC-8 (S2):** Given zwei verschiedene Nutzer A und B mit unterschiedlichen Adressen / When A die Testmail auslöst / Then geht sie nur an As bestätigte Adresse, nie an B, nie an die globale Betreiber-Adresse und nie unter der `user_id` `"default"`; hat A keine bestätigte Adresse, wird nichts gesendet und A sieht einen klaren deutschen Fehlertext.
  - Test: Python-Test mit zwei Nutzerprofilen (`get_data_dir`-Isolation): Empfänger je Nutzer geprüft; Fall ohne `email_verified_at` und ohne `mail_to`.
- **AC-9 (S2):** Given die Startseite eines Nutzers mit Tarif ohne SMS / When Willkommen und Checkliste angezeigt werden / Then erscheinen weder SMS noch Premium-SMS, Telegram nur als optionaler Hinweis ohne Blockade; bei Tarif mit `sms_allowed` bzw. `premium_sms_allowed` erscheint der jeweilige Hinweis.
  - Test: Vitest Render-Tests je Tarifstand; kein Text im Katalog nennt Telegram als Pflichtschritt.
- **AC-10 (S2):** Given die Startseite ohne Trips und Vergleiche / When der Nutzer „+ Neuer Vergleich" klickt (Kopfzeile oder Leerzustand) / Then landet er auf `/compare/new` und nicht auf `/compare`.
  - Test: Render-Test beider Links; Playwright gegen Staging.
- **AC-11 (S2):** Given ein Nutzer mit bestätigter E-Mail-Adresse und mindestens einem Trip oder Vergleich / When er `/` öffnet / Then ist die Checkliste verschwunden; solange einer dieser beiden Pflichtpunkte offen ist, bleibt sie sichtbar. „Testmail gesendet" und „Telegram verknüpft" werden angezeigt, blockieren das Verschwinden aber nicht.
  - Test: Vitest Zustandsmatrix der vier Punkte (Mutation: Testmail als Pflichtpunkt muss rot werden).
- **AC-12 (S3):** Given ein Trip-Editor auf `/trips/new` mit Name, Startdatum und mindestens einer Etappe / When der Nutzer „Mit Standardwerten speichern" wählt, ohne einen weiteren Reiter zu öffnen / Then wird der Trip mit der Metrik-Vorauswahl des Wetter-Metriken-Reiters, aktivem E-Mail-Versand und E-Mail als Alarm-Kanal gespeichert.
  - Test: Vitest `buildDefaultsPayload` gegen Fixture `metric_catalog_selectable.json` (Metriken = alle `default_enabled`); Playwright gegen Staging: Trip anlegen, Reiter prüfen.
- **AC-13 (S3):** Given ein Ortsvergleich-Editor auf `/compare/new` mit Name und mindestens zwei Orten / When der Nutzer „Mit Standardwerten speichern" wählt / Then wird der Vergleich mit denselben Standardwerten (Metriken, E-Mail-Versand, E-Mail-Alarm) über dieselbe geteilte Funktion gespeichert.
  - Test: Vitest, derselbe Test-Fall parametrisiert über `context="route"|"vergleich"`; Playwright gegen Staging.
- **AC-14 (S3):** Given ein Editor mit fehlendem Pflichtfeld (z. B. kein Name, keine Etappe, weniger als zwei Orte) / When der Nutzer den Footer ansieht / Then ist „Mit Standardwerten speichern" deaktiviert und die Reiter-Freischaltung bleibt unverändert.
  - Test: Vitest `canSaveWithDefaults` Wahrheitstabelle; Mutation `>= 1` statt `>= 2` bei Orten muss rot werden.
- **AC-15 (S4):** Given der Alarme-Reiter / When der Nutzer die Begriffe „Kanal-Schwelle", „Dringlichkeits-Schwelle", „Cooldown" oder „Gewitterenergie (CAPE)" ansieht / Then ist an jedem ein Tooltip nach AC-1 erreichbar, dessen Text in einfacher Sprache erklärt, was der Begriff bewirkt.
  - Test: Vitest Render-Test je Begriff (Tooltip vorhanden, Katalogschlüssel gesetzt); Playwright Touch.
- **AC-16 (S4):** Given die Reiter Wertebereiche, Alarme, Versand und Layout im Anlege-Editor / When der Nutzer sie öffnet / Then zeigt jeder eine Infobox „Kannst du überspringen — Standard: …" mit dem tatsächlichen Standardwert, in Trip und Ortsvergleich identisch.
  - Test: Render-Test je Reiter und `context`; Review-Punkt: kein Compare-eigener Duplikat-Baustein.

## Known Limitations

- **Offene Frage Testmail-Status:** Eine persistierte Zeit `test_mail_sent_at` würde ein weiteres Schema-Feld und einen weiteren Schreibpfad im Go-Profil bedeuten (nicht billig). Entscheidung: Die Checkliste führt „Testmail gesendet" **clientseitig pro Sitzung** (`sessionStorage`, Schlüssel je `user_id`). Der Punkt zählt nicht als Nachweis der Zustellung, nur des erfolgreichen Versands (`{"status": "ok"}`). Nach Neuanmeldung kann der Nutzer die Testmail erneut senden; das stört die Pflicht-Logik nicht, weil das Verschwinden der Checkliste nur an bestätigter E-Mail und erstem Trip/Vergleich hängt (AC-11). Bei Bedarf Nachrüstung als eigenes Ticket.
- Nur Deutsch; Texte im Katalog, keine Sprachumschaltung.
- Kein Backfill der Bestandsnutzer; sie werden über „hat Trips/Vergleiche" ausgeblendet. Ein Bestandsnutzer ohne Daten sieht den Hinweis einmal und kann ihn wegklicken.
- Die Testmail kann bei fehlender Betreiber-Konfiguration (kein Resend-Token auf Produktion) auf den Test-SMTP umgelenkt werden (Default-Deny, `config.py:309`); dann meldet der Dienst den Fehler statt leise zu senden.
- Telegram-Verknüpfung bleibt außerhalb dieses Moduls (Token-Flow, #2141); die Checkliste verlinkt nur auf die Konto-Seite.
- Antwortbefehle auf der Hilfeseite sind eine kurze Übersicht, keine vollständige Befehlsreferenz.

## Architektur-Entscheidung (ADR)

Kein neues ADR nötig. ADR-0032 (Editor-Paradigma) bleibt unberührt: die Etappe S3 ergänzt nur einen Footer-Knopf, keine Editor-Struktur. Die Umstellung der Testmail auf den echten Versandweg ändert nur den E-Mail-Zweig einer Test-Funktion und hebt das Test-Routing für Test-/Staging-Nutzer nicht auf (`with_user_profile` erzwingt es weiter). Falls die Review dies als Kanal-/Provider-Entscheidung wertet: Abweichung ⇒ neues ADR.

## Changelog

- 2026-10-07: Initial spec created (Issue #2521), gestuft S1-S4
