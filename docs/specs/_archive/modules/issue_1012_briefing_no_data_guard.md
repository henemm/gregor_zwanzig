---
entity_id: issue_1012_briefing_no_data_guard
type: module
created: 2026-07-05
updated: 2026-07-05
status: draft
version: "1.0"
tags: [briefing, scheduler, weather, monitoring, bug]
---

<!-- Issue #1012 — Kein Briefing bei komplettem Wetterdaten-Ausfall -->

# Issue 1012 — Kein Briefing bei komplettem Wetterdaten-Ausfall (Guard, Hinweis-Nachricht, Monitoring-Sichtbarkeit)

## Approval

- [x] Approved (PO 'go', 2026-07-05 — inkl. Catch-up + Teilausfall-Nachlieferung)

## Purpose

Verhindert, dass ein Trip-Briefing mit komplett leeren Wetterdaten versendet wird, wenn der
Wetter-Provider für ALLE Segmente ausfällt (Root Cause von Issue #1012: der bestehende Guard
`if not segment_weather` greift nie, weil `_fetch_weather()` bei Provider-Fehlern pro Segment
einen `has_error=True`-Platzhalter statt einer leeren Liste liefert). Statt eines leeren
Briefings geht eine kurze Hinweis-Nachricht raus, der Job zählt den Trip korrekt als
fehlgeschlagen, und der Go-Scheduler macht den Ausfall für das externe Monitoring sichtbar
(bisher `last_run=ok` trotz Fehlversand).

## Source

- **File:** `src/services/trip_report_scheduler.py` — `_send_trip_report_outcome()` (Guard,
  ca. Z.519-525), `send_reports_for_hour()` (Zählung, Z.203-248), `_send_service_error_email()`
  / `build_service_error_email_html()` (Vorlage für Hinweis-Versand, Z.87-140, 762-767)
- **File:** `internal/scheduler/scheduler.go` — `triggerEndpointForUser()` (Z.202-217),
  `recordRun()` (Z.182-198)

> Python-Backend-Schicht (`src/services/`) für den Guard/Zählungs-/Hinweis-Teil, Go-API-Schicht
> (`internal/scheduler/`) für den Monitoring-Teil. Kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~250–340 (Python ~90–140 + Catch-up inkl. Teilausfall ~110–130 + Renderer-Kennzeichnung
  ~20–30 + Go ~30–50) — überschreitet voraussichtlich das 250-Limit; LoC-Override ist durch die
  PO-Entscheidungen „Catch-up mit reinnehmen" + „auch Teilausfall nachliefern" (2026-07-05)
  vorab gedeckt
- **Files:** 3–5 (trip_report_scheduler.py, scheduler.go, neue Testdatei; ggf. Renderer-Datei(en)
  für die „nicht verfügbar"-Kennzeichnung → Renderer-Commit-Gate beachten; neue Persistenz-Datei
  `pending_briefings.json` pro User, keine Migration)
- **Effort:** medium–high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers/openmeteo.py` (5× Backoff + 5-Modell-Fallback-Kette) | intern | Bleibt unverändert — IST bereits der Retry-Mechanismus; kein zusätzliches Sleep-Retry in diesem Fix |
| `trip_command_processor.py:193-210` (On-Demand #1007) | intern | Nutzt denselben `_send_trip_report_outcome`; profitiert automatisch vom Guard ohne Zusatzarbeit |
| `/api/scheduler/trip-reports` (`api/routers/scheduler.py:24-40`) | intern | Baut `status="partial"` bereits aus `(sent, failed)` — Fix liegt in der Zählung selbst, nicht im Endpoint |
| `check-gregor20.sh` (externes Monitoring) | extern | Liest `/api/scheduler/status`; ist der Konsument der Go-seitigen Sichtbarkeits-Änderung |
| Stunden-Takt des Go-Schedulers (trip-reports) | intern | Träger des Catch-up: jeder Folge-Lauf prüft offene Nachliefer-Marker (PO-Entscheidung 2026-07-05: Catch-up IM Scope, #1016 dadurch obsolet) |

## Implementation Details

**(a) Guard — `_send_trip_report_outcome()`, ca. Z.519-525.** Ersetzt die nie greifende Prüfung
`if not segment_weather` durch eine Prüfung auf vollständigen Ausfall:

```
segment_weather = self._fetch_weather(segments)
if not segment_weather or all(s.has_error for s in segment_weather):
    logger.warning(f"All-failed weather data for trip {trip.id}")
    self._send_no_data_hint(trip, report_type)
    return "no_weather"
```

Der Guard greift VOR dem restlichen Versandpfad (Ensemble-Anreicherung, Stabilitäts-Label,
Kanal-Versand Z.681 ff., Briefing-Log Z.756) — bei Trigger wird KEINER dieser Schritte
ausgeführt, insbesondere kein `_append_briefing_log`-Aufruf.

**(b) Hinweis-Nachricht — neue Methode `_send_no_data_hint(trip, report_type)`.**
Generalisiert das Muster aus `_send_service_error_email`/`build_service_error_email_html`
(bisher nur für SMS-only-Trips bei Teilfehlern), sendet aber über ALLE für den Trip
konfigurierten Kanäle (Muster wie Z.681-731: `config = trip.report_config`; E-Mail wenn
`not config or config.send_email`; SMS wenn `config.send_sms and can_send_sms()`; Telegram wenn
`config.send_telegram and can_send_telegram()`). Text: „Wetterdienst aktuell nicht erreichbar —
wir versuchen es weiter und liefern das Briefing nach, sobald Daten verfügbar sind." Betreff
enthält den Trip-Namen (analog `[{trip.name}] Wetterdaten nicht verfügbar`). Keine
Wettertabellen, keine `has_error`-Detailzeilen (das bleibt der SMS-only-Service-Mail vorbehalten).

**(b2) Catch-up / Nachliefern — neue Persistenz `data/users/<uid>/pending_briefings.json`.**
Marker-Format: `{trip_id, report_type, date, slot_hour, failed_segment_ids, attempts,
created_at}` (Read-Modify-Write, neue Datei — keine Migration nötig). Geschrieben bei
Komplettausfall (AC-1, `failed_segment_ids` = alle) UND Teilausfall (AC-3, nur die
`has_error`-Segmente). Jeder folgende Stunden-Lauf (`send_reports_for_hour`) verarbeitet ZUERST
offene Marker des Users: erneuter Abruf; **Erfolgskriterium = die zuvor fehlenden Segmente
liefern jetzt Daten** → vollständiges Briefing nachliefern mit Hinweis-Präfix (Komplettausfall:
„Nachgeliefert — der Wetterdienst war um {slot_hour}:00 nicht erreichbar"; Teilausfall:
„Aktualisiert — jetzt mit vollständigen Daten"; Muster analog On-Demand-Hint Z.653-666),
regulärer `briefing_log`-Eintrag, Marker löschen, zählt als `sent`. Zuvor fehlende Segmente
weiterhin ohne Daten → KEIN Re-Send (`attempts += 1`, zählt als `failed`) — Lärmschutz, nie
zwei identische Briefings. **Verfall:** Marker wird gelöscht, sobald der nächste reguläre
Termin desselben Trips fällig wird (morning-Marker verfällt beim evening-Slot bzw. spätestens
am Tagesende) — verhindert Doppel-Briefings und veraltete Nachlieferungen.

**(b3) Kennzeichnung fehlender Segmente (AC-3):** Prüfen, wie die Renderer (`email`/`telegram`)
`has_error`-Segmente heute darstellen; falls kommentarlos leer, ausdrückliche
„Wetterdaten nicht verfügbar"-Kennzeichnung im Segment-Block ergänzen (kleinste mögliche
Änderung — Achtung: Mail-Inhalts-Dateien lösen das Renderer-Commit-Gate aus →
Modus-Matrix-Vertragstest + briefing_mail_validator gegen die Staging-Mail sind Pflicht).

**(c) Zählung — `send_reports_for_hour()`, Z.203-248.** Ruft aktuell den bool-Wrapper
`_send_trip_report()` auf und ignoriert dessen Rückgabewert (`sent += 1` unabhängig vom
Outcome, nur Exceptions zählen als `failed`). Wechselt auf `_send_trip_report_outcome()` und
wertet gezielt aus: Outcome `"no_weather"` → `failed += 1`; alle anderen Outcomes
(`"sent"`, `"no_channels"`, `"no_stage"`) bleiben unverändert `sent += 1` (kein Regress für
Nicht-Wetter-Fälle, die außerhalb dieses Fixes liegen). `/api/scheduler/trip-reports`
(`api/routers/scheduler.py:38-40`) baut `status="partial" if failed > 0 else "ok"` bereits
korrekt aus `(sent, failed)` — hier ist keine Änderung nötig.

**(d) Go-Monitoring — `triggerEndpointForUser()`, Z.202-217.** Parst den JSON-Response-Body
(`{"status", "count", "failed"}`) zusätzlich zum HTTP-Statuscode; ist `failed` vorhanden und
`> 0`, liefert die Funktion einen Fehler zurück (auch bei HTTP 200), sodass `recordRun()`
(Z.182-198) den Job als `Status: "error"` mit Fehlertext verbucht. Generischer Ansatz — gilt für
alle über `triggerEndpointForUser` aufgerufenen Endpoints; nur `/api/scheduler/trip-reports`
liefert aktuell ein `failed`-Feld > 0, die übrigen (`alert-checks`, `radar-alert-checks`,
`compare-presets-daily`) bleiben unberührt (Feld fehlt bzw. ist 0).

**(e) On-Demand (#1007):** keine Änderung nötig — `trip_command_processor.py:193-210` hat für
`outcome == "no_weather"` bereits den fertigen Hinweistext, der Guard-Fix in (a) macht ihn nur
jetzt auch für den kompletten Ausfall erreichbar.

## Expected Behavior

- **Input:** Ein Trip, dessen Wetterabruf für ALLE Segmente `has_error=True` liefert (z.B.
  Open-Meteo-Ausfall über die gesamte Fallback-Kette hinweg)
- **Output:** Kein Briefing mit leeren Wetterdaten; stattdessen eine kurze Hinweis-Nachricht über
  die konfigurierten Kanäle; der Job zählt den Trip als `failed`; `/api/scheduler/status` zeigt
  `last_run.status=error` für `trip_reports_hourly`
- **Side effects:** Kein `briefing_log`-Eintrag bei komplettem Ausfall (Cockpit-Kachel „Was geht
  heute raus" zeigt dafür nichts an — Sichtbarkeit läuft stattdessen über `last_run`/Monitoring,
  siehe Known Limitations); On-Demand-Pfad (#1007) profitiert automatisch, kein separater Codepfad

## Acceptance Criteria

- **AC-1 (All-Failed-Guard, regulärer Versand):** Given alle Segmente eines Trips liefern beim
  Abruf einen Provider-Fehler (`has_error=True` für jedes Segment) / When der reguläre
  Briefing-Versand läuft / Then wird KEIN Briefing versendet (keine E-Mail/Telegram/SMS mit
  leeren Wetterdaten) und KEIN `briefing_log`-Eintrag geschrieben; das Outcome ist `"no_weather"`.
  - Test: Trip mit injiziertem Fake-Provider (wirft `ProviderRequestError` für jedes Segment)
    aufsetzen, `_send_trip_report_outcome` aufrufen, beweisen dass Outcome `"no_weather"` ist
    und dass kein Eintrag in `briefing_log.json` für den Trip erscheint. Negativ-Beweis für
    den Versand OHNE Mocks: echter Versandpfad an den Stalwart-Test-Account, IMAP-Prüfung
    beweist, dass KEINE reguläre Briefing-Mail (Tabellen-Layout) zugestellt wurde — nur die
    Hinweis-Mail aus AC-2 (gemeinsamer IMAP-Check beider ACs).

- **AC-2 (Hinweis-Nachricht):** Given der All-Failed-Fall aus AC-1 / When der Versand
  unterdrückt wird / Then geht stattdessen über die konfigurierten Kanäle des Trips eine kurze
  Hinweis-Nachricht raus („Wetterdienst aktuell nicht erreichbar — wir versuchen es weiter und
  liefern das Briefing nach, sobald Daten verfügbar sind", Betreff mit Trip-Name), KEINE
  Wettertabellen.
  - Test: Denselben All-Failed-Trip mit `send_email=True` konfigurieren, echten Versand über den
    Stalwart-Test-Account (`gregor-test@henemm.com`) auslösen und per IMAP beweisen, dass eine
    Mail mit dem Trip-Namen im Betreff und dem Hinweistext (nicht dem regulären Tabellen-Layout)
    ankommt.

- **AC-3 (Teilausfall: pünktlich senden + kennzeichnen + Marker):** Given mindestens ein
  Segment hat gültige Wetterdaten und mindestens ein Segment `has_error=True` / When der
  Versand läuft / Then wird das Briefing pünktlich versendet (Outcome `"sent"`,
  `briefing_log`-Eintrag wie bisher), die betroffenen Abschnitte sind im Briefing ausdrücklich
  als „Wetterdaten nicht verfügbar" gekennzeichnet (keine kommentarlos leeren Tabellen), und es
  wird ein Nachliefer-Marker mit den fehlenden Segment-IDs geschrieben.
  - Test: Trip mit gemischtem Fake-Provider (ein Segment liefert Daten via FixtureProvider,
    eines wirft Fehler) aufsetzen, `_send_trip_report_outcome` aufrufen; beweisen: Outcome
    `"sent"`, `briefing_log`-Eintrag vorhanden, IMAP-Mail enthält für das Fehler-Segment die
    „nicht verfügbar"-Kennzeichnung (und Tabellen für das gesunde Segment), Marker-Datei
    enthält Eintrag mit den fehlenden Segment-IDs.

- **AC-4 (Job-Zählung + API):** Given ein Stunden-Lauf mit mindestens einem All-Failed-Trip /
  When `send_reports_for_hour` läuft / Then zählt dieser Trip als `failed` (nicht `sent`) und
  `/api/scheduler/trip-reports` liefert `status=partial` mit `failed>0`.
  - Test: Zwei Trips für dieselbe fällige Stunde konfigurieren (einer All-Failed via
    Fake-Provider, einer mit gültigen Daten), `send_reports_for_hour` aufrufen und das
    zurückgegebene `(sent, failed)`-Tupel prüfen (`sent=1, failed=1`); zusätzlich echten Aufruf
    von `POST /api/scheduler/trip-reports` (lokaler Test-Client, Uvicorn/TestClient gegen die
    echte FastAPI-App) unter denselben Bedingungen und Prüfung von `status=="partial"` sowie
    `failed>0` im JSON-Body.

- **AC-5 (Monitoring-Sichtbarkeit, Go):** Given der Go-Scheduler ruft den Python-Endpoint auf
  und erhält HTTP 200 mit `failed>0` im JSON-Body / When `recordRun` das Ergebnis verbucht /
  Then zeigt `/api/scheduler/status` für den Job `last_run.status=error` (mit Fehlertext),
  sodass das externe Monitoring anschlägt.
  - Test: Go-Unit-Test in `internal/scheduler/scheduler_test.go` (Muster wie
    `TestTriggerEndpoint_Success`/`TestTriggerEndpoint_PythonError`): `httptest.NewServer`
    liefert HTTP 200 mit Body `{"status":"partial","count":1,"failed":1}`;
    `triggerEndpointForUser` MUSS einen Fehler zurückgeben (echter HTTP-Roundtrip gegen einen
    echten Test-Server, kein Mock der Funktion selbst). Zusätzlich
    **Staging-Verifikationspunkt** (im E2E-Schritt nachzuweisen, da die volle
    Go-Scheduler↔Python-Kette dort erstmals real zusammenläuft): nach Deploy einen All-Failed-Fall
    gegen Staging auslösen und `/api/scheduler/status` auf `last_run.status=error` für
    `trip_reports_hourly` prüfen.

- **AC-6 (Nachliefern bei Erholung — Komplett- UND Teilausfall):** Given ein Nachliefer-Marker
  aus AC-1 (Komplettausfall) oder AC-3 (Teilausfall, mit fehlenden Segment-IDs) / When ein
  späterer Stunden-Lauf für die zuvor fehlenden Segmente wieder Wetterdaten erhält / Then wird
  ein vollständiges Briefing nachgeliefert (Hinweis-Präfix: bei Komplettausfall „Nachgeliefert —
  der Wetterdienst war um HH:00 nicht erreichbar", bei Teilausfall „Aktualisiert — jetzt mit
  vollständigen Daten"), ein `briefing_log`-Eintrag geschrieben und der Marker entfernt.
  **Lärmschutz:** Liefern die zuvor fehlenden Segmente weiterhin KEINE Daten, wird NICHT erneut
  gesendet (`attempts += 1`, Marker bleibt bis Verfall) — nie zwei identische Briefings.
  - Test (Komplettausfall): All-Failed-Lauf (Fake-Provider) erzeugt Marker → zweiter Lauf mit
    FixtureProvider → beweisen: IMAP-Mail mit Nachgeliefert-Hinweis + Tabellen-Layout,
    `briefing_log`-Eintrag, Marker-Datei leer.
  - Test (Teilausfall): AC-3-Lauf erzeugt Marker mit Segment-IDs → zweiter Lauf, jetzt alle
    Segmente mit Daten → beweisen: IMAP-Mail mit Aktualisiert-Hinweis und Tabellen für ALLE
    Segmente, Marker entfernt. Gegenprobe (Lärmschutz): zweiter Lauf mit weiterhin fehlendem
    Segment → beweisen: KEINE weitere Mail, Marker mit `attempts=1` weiterhin vorhanden.

- **AC-7 (Verfall, kein Doppel-Briefing):** Given ein offener Nachliefer-Marker (z.B. morning)
  / When der nächste reguläre Termin desselben Trips fällig wird (z.B. evening-Slot) oder der
  Tag endet / Then verfällt der Marker ersatzlos — es wird höchstens EIN Briefing pro Slot
  versendet, nie ein veraltetes Morning-Briefing nach dem Evening-Briefing.
  - Test: Marker anlegen, Lauf zur Stunde des nächsten regulären Termins mit funktionierendem
    Provider ausführen → beweisen: genau ein Briefing (das reguläre), Marker entfernt, kein
    zweiter `briefing_log`-Eintrag für den verfallenen Slot.

**Hinweis zu On-Demand (#1007):** `heute`/`morgen`-Kommandos profitieren automatisch vom Guard
(bestehender „Wetterdaten aktuell nicht verfügbar"-Text in `trip_command_processor.py:193-210`)
— durch den AC-1-Test am selben Outcome (`"no_weather"`) mit abgedeckt, kein eigenes AC. On-Demand
erzeugt KEINEN Nachliefer-Marker (der Nutzer fragt aktiv erneut).

## Known Limitations

- **Kein zusätzliches Sleep-Retry.** Die Provider-Kette hat bereits 5× Backoff (2–60s) +
  5-Modell-Fallback (`providers/openmeteo.py:94-98`). Ein zusätzliches Sleep-Retry in der
  synchronen Trip-Schleife würde die Job-Laufzeit bei echtem Ausfall über alle fälligen User
  vervielfachen, ohne etwas zu retten.
- **Nachliefer-Takt = Stunden-Takt.** Das Catch-up hängt am stündlichen trip-reports-Lauf —
  frühestens ~1 Stunde nach dem Ausfall, kein minütliches Polling. Marker verfallen zum
  nächsten regulären Termin (AC-7); ein Ausfall, der bis dahin andauert, wird nicht mehr
  nachgeliefert (dann greift der reguläre nächste Slot).
- **Hinweis-Nachricht erscheint nicht in der Cockpit-Kachel „Was geht heute raus".** Da kein
  `briefing_log`-Eintrag geschrieben wird, bleibt die Kachel für den Ausfalltag leer.
  Sichtbarkeit läuft stattdessen ausschließlich über `last_run`/das externe Monitoring (AC-4/AC-5).
- **Teilausfall: pünktliches Briefing hat Lücken.** Das pünktliche Briefing enthält für
  ausgefallene Abschnitte nur die „nicht verfügbar"-Kennzeichnung; die vollständige Version
  folgt als Aktualisierung im Stunden-Takt (AC-6) — kein Minuten-Polling.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Fehlerbehandlungs-Bugfix am bestehenden Sendepfad (Guard-Bedingung,
  Zählung, Monitoring-Auswertung) — keine neue Architektur-Entscheidung, kein neuer
  Kanal/Datenfluss.

## Testplan

**Datei:** `tests/tdd/test_issue_1012_no_data_guard.py`

Keine Mocks (Projektregel) — Fehler-Provider wird über den bestehenden
`provider`-Injektionsparameter von `_fetch_weather` (Demo-Mode-Seam, Issue #483) durch einen
eigenen `FailingProvider` ersetzt, der `ProviderRequestError` wirft — Substitution der externen
Abhängigkeit (Open-Meteo), nicht der eigenen Logik, markiert mit `# fake-provider-seam`. Für
AC-2 echter Versand + IMAP-Verifikation gegen `gregor-test@henemm.com` (kein Gmail, keine
String-Presence-Checks). Für AC-4 zusätzlich echter Aufruf der FastAPI-App über `TestClient`
(kein Mock des Routers). AC-5 ergänzt einen echten HTTP-Roundtrip-Test in Go
(`internal/scheduler/scheduler_test.go`) plus einen Staging-Verifikationspunkt im E2E-Schritt.

| AC | Test-Funktion / Nachweis |
|----|--------------------------|
| AC-1 | `test_all_failed_weather_suppresses_send_and_briefing_log` |
| AC-2 | `test_all_failed_weather_sends_hint_message_via_imap` |
| AC-3 | `test_partial_failure_sends_on_time_with_labels_and_marker` |
| AC-4 | `test_send_reports_for_hour_counts_all_failed_as_failed` + `test_trip_reports_endpoint_returns_partial_status` |
| AC-5 | `TestTriggerEndpoint_FailedBodyTreatedAsError` (Go, `scheduler_test.go`) + Staging-Verifikationspunkt (E2E-Schritt) |
| AC-6 | `test_pending_marker_written_and_briefing_delivered_on_recovery` (Komplettausfall) + `test_partial_marker_redelivers_updated_briefing_on_recovery` + `test_no_resend_while_segments_still_failing` (Lärmschutz) |
| AC-7 | `test_pending_marker_expires_at_next_regular_slot_no_double_briefing` |

## Changelog

- 2026-07-05: Initial spec erstellt — Issue #1012
- 2026-07-05: Catch-up/Nachliefern in den Scope aufgenommen (AC-6/AC-7, PO-Entscheidung; #1016 obsolet)
- 2026-07-05: PO-Entscheidung: auch Teilausfälle nachliefern — AC-3 (Kennzeichnung + Marker) und AC-6 (Aktualisiert-Nachlieferung + Lärmschutz) erweitert
