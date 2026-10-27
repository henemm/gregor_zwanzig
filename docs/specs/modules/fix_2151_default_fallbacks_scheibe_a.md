---
entity_id: fix_2151_default_fallbacks_scheibe_a
type: bugfix
created: 2026-09-18
updated: 2026-09-19
status: implemented
workflow: fix-2151-default-fallbacks-entfernen
issue: 2151
---

# Scheibe A: `"default"`-Rückfälle in Python-Sende-/Lesepfaden entfernen (#2151)

## Approval

- [ ] Approved

## Purpose

Ein authentifizierter Pfad darf nie stillschweigend auf den Nutzer `"default"` zurückfallen —
das ist laut ADR-0003 ein Cross-User-Datenleck. Diese Scheibe schließt das aktive, lesende Leck
in der Trip-Vorschau (#2057: GPX wird aus `users/default/gpx` statt aus dem GPX des anfragenden
Nutzers geladen), macht `user_id` in drei Python-Routen zur Pflicht statt zum stillen Default, und
ersetzt den Telegram-Sentinel `"default"` für „unbekannter Absender" durch `None` (analog zum
E-Mail-Reader, #2147). Ein AST-basierter Wächter-Test verhindert, dass neue `"default"`-Defaults
in `api/` entstehen und dass die bekannte Restmenge in `src/` unbemerkt wächst.

## Source

- **File:** `src/services/preview_service.py`
- **Identifier:** `def render_email_preview` / `def render_sms_preview` / `def render_telegram_preview` (Zeile ~158: `TripReportSchedulerService(self.settings)`)

> **Schicht:** Python-Core (`api/routers/`, `src/services/`) — kein Go, kein Frontend in dieser Scheibe.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0003 (Multi-Tenant-Isolation) | ADR | Grundsatz: kein `"default"`-Rückfall in authentifiziertem Pfad |
| `src/services/inbound_email_reader.py` (`_resolve_user_for_sender`, ~Z.280-302) | Vorbild-Code | Zeigt das Zielmuster „unbekannt = `None`", bereits als Muster für #2147 B2/AC-14 etabliert |
| `docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md` | Spec | Hat `WithUser("")`-No-Op (Go) bewusst unangetastet gelassen — betrifft Scheibe B, hier nur als Abgrenzung relevant |
| `tests/test_output_timezone_guard.py` | Test-Muster | Vorbild für AST-basierten Wächter-Test (Struktur statt String-Suche) |
| `internal/handler/proxy.go:~264`, `internal/handler/compare_preset.go:~571` | Go-Bestandscode (unverändert) | Hängt `user_id` bei beiden Send-Routen bereits heute automatisch an — Referenz für AC-4/AC-5, wird in dieser Scheibe nicht editiert |
| Scheibe B (Folge-Workflow, Go) | Folgearbeit | `cfg.UserID`-Default entfernen, Store fail-closed, Seed nur bei `GZ_USER_ID` |
| Scheibe C (Folge-Workflow, Python) | Folgearbeit | Restliche ~190 Signatur-Defaults (`user_id="default"`) entfernen, inkl. `NotificationService()` in `inbound_email_reader.py:72`/`inbound_telegram_reader.py:108`, Ratsche leerräumen |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/preview_service.py` | MODIFY | `user_id` der Anfrage bis `TripReportSchedulerService(self.settings, user_id=...)` durchreichen (Z.~158); `persist_backfill=False` bleibt unverändert |
| `api/routers/scheduler.py` | MODIFY | Z.213 `user_id: str = "default"` → `Query(...)` (Pflicht); Z.299 `Query("default")` → `Query(...)` |
| `api/routers/debug.py` | MODIFY | Z.20 `user_id="default"` → `Query(...)` (Pflicht) |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_resolve_user_for_chat` (~Z.476): `lookup_user_by_telegram_chat_id(...) or "default"` → `... or None`; `_process_update` (~Z.190) und `_process_callback_query` (~Z.383): Prüfung `user_id == "default"` → `user_id is None` |
| `tests/test_user_id_default_guard.py` | CREATE | AST-Wächter: (a) keine `user_id`-Signatur-Defaults `"default"` mehr in `api/`; (b) fixierte, nur schrumpfbare Bestandsliste der verbleibenden `src/`-Defaults; (c) kein `or "default"`-Rückfall in `src/services/inbound_*.py` |
| `tests/test_preview_service_user_isolation.py` | CREATE | Vorschau lädt GPX/Trip-Daten des anfragenden Nutzers, nie von `users/default` |
| `tests/test_scheduler_router_requires_user_id.py` | CREATE | Drei Routen liefern 422 ohne `user_id`, versenden nichts; explizites `user_id=default` bzw. `user_id=<anderer Nutzer>` dispatcht unverändert (Go-Proxy-Aufrufform) |
| `tests/test_inbound_telegram_unknown_chat.py` | MODIFY/CREATE | Unbekannter Chat weiterhin nur Registrierungshinweis; Konto `default` mit verknüpftem Chat gilt als bekannt |

**Nicht in dieser Scheibe:** `src/services/inbound_email_reader.py` (`NotificationService()`-Konstruktion
Z.72) und die analoge Stelle in `inbound_telegram_reader.py` (Z.108) — beide hängen am
`Settings().with_user_profile("default")`-internen Default, der erst in Scheibe C entfällt; bis
dahin bleibt die heutige Konstruktion funktionsfähig und wird hier nicht angefasst (siehe Known
Limitations).

### Estimated Changes
- Files: ~4 Quelldateien, ~4 Testdateien (neu/geändert)
- LoC: +210/-35 (grob) — bei Überschreitung von 250 `loc_limit_override` setzen, kein Scope-Schnitt

## Implementation Details

**1. Vorschau-Leck (#2057).** `render_email_preview`/`render_sms_preview`/`render_telegram_preview`
in `preview_service.py` erhalten `user_id` bereits als Keyword. Diese `user_id` wird beim Aufbau
von `TripReportSchedulerService` mitgegeben, sodass `_convert_trip_to_segments` intern nicht mehr
über den impliziten `_user_id="default"`-Default auf `backfill_stage_distances(trip, "default", ...)`
zurückfällt, sondern die echte Nutzerkennung nutzt. `persist_backfill=False` bleibt gesetzt — die
Vorschau bleibt reines Render ohne Schreib-Nebenwirkung.

**2. Drei Router ohne Rückfall.** `scheduler.py:213` und `scheduler.py:299` sowie `debug.py:20`
werden auf das bestehende Pflicht-Muster (`user_id: str = Query(...)`, siehe `scheduler.py:27/62/195`)
umgestellt. Fehlt `user_id` im Request, antwortet FastAPI mit 422, bevor irgendein Versand- oder
Trigger-Code läuft. Der Go-Proxy (`internal/handler/proxy.go:~264`, `internal/handler/compare_preset.go:~571`)
hängt `user_id` bei beiden Send-Routen bereits heute immer an — diese Scheibe editiert keine
Go-Datei; der Beweis, dass sich das Produktionsverhalten über den Proxy nicht ändert, wird auf
Python-Seite geführt, indem die Route exakt in der Aufrufform getestet wird, die der Proxy sendet
(`?user_id=<id>` als Query-Parameter, kein Body). Staging-Debug-Tests, die `user_id=default`
explizit mitgeben, bleiben unverändert gültig, weil `default` als Wert erlaubt bleibt (siehe
Designentscheidung unten).

**3. Telegram-Sentinel.** `_resolve_user_for_chat` liefert für unbekannte Chats `None` statt
`"default"`. Die beiden Aufrufer prüfen entsprechend auf `is None`. Das sichtbare Verhalten für
unbekannte Chats bleibt exakt erhalten: Registrierungshinweis an den fragenden Chat via
`settings.model_copy(update={"telegram_chat_id": chat_id})`, keine Trip-Daten, kein Rückfall auf
die Betreiber-Chat-ID. Neu: Ist ein echtes Konto `default` mit einem Telegram-Chat verknüpft, liefert
`lookup_user_by_telegram_chat_id` `"default"` zurück und der Chat wird wie jeder andere bekannte
Nutzer behandelt — vorher hätte die reine String-Prüfung `== "default"` diesen Fall fälschlich als
unbekannt eingestuft.

**4. Wächter-Test.** `tests/test_user_id_default_guard.py` parst die betroffenen Module per `ast`
(kein Dateiinhalt-String-Check als Verhaltensnachweis — Struktur-Wächter nach Vorbild
`test_output_timezone_guard.py`):
- (a) in `api/**/*.py` gibt es keine Funktionssignatur mit Parameter `user_id`, deren Default ein
  String-Literal `"default"` ist, und keinen `Query("default")`-Aufruf.
- (b) für `src/**/*.py` existiert eine im Test fest codierte Liste `(Datei, Funktionsname)` der
  heute noch bestehenden `user_id="default"`-Signatur-Defaults (Bestand aus Scheibe A, wird in
  Scheibe C schrittweise geleert). Der Test vergleicht die im Code tatsächlich gefundene Menge
  gegen diese Liste: Ein Eintrag ohne Fundstelle im Code ist rot (Liste veraltet), ein im Code
  gefundener Default, der nicht in der Liste steht, ist rot (neue Stelle). Die Liste darf nur
  schrumpfen, nie wachsen.
- (c) in `src/services/inbound_email_reader.py` und `src/services/inbound_telegram_reader.py` gibt
  es keinen `or "default"`-Ausdruck (AST `BoolOp`/`Or` mit einem `Constant("default")`-Operanden)
  bei der Auflösung der Nutzerkennung aus Absenderdaten.

## Designentscheidung: `"default"` bleibt gültiger Kontoname

Das Issue #2151 fordert wörtlich, `"default"` als Wert abzulehnen. Diese Spec weicht davon
begründet ab: `default` ist ein reales Bestandskonto — es wird auf Prod/Staging als Seed-Konto
angelegt (`cmd/server/main.go:73-89`, Go-Scheibe B), hat Daten unter `users/default/` und steht in
Cleanup-Schutzlisten (`NEVER_DELETE`/`REQUIRED_ACCOUNTS`). Würde der Wert `"default"` grundsätzlich
abgelehnt, wäre dieses Konto ausgesperrt — ein neuer Schaden, den ADR-0003 nicht verlangt. ADR-0003
verbietet den automatischen Rückfall auf `"default"` bei fehlender/unklarer Identität, nicht die
Verwendung von `"default"` als expliziter, vom Aufrufer bewusst übergebener Wert. Scheibe A setzt
das entsprechend um: Endpunkte verlangen `user_id` als Pflichtparameter (kein impliziter Default
mehr), ein Aufruf mit explizit `user_id=default` bleibt weiterhin gültig und funktioniert
unverändert (siehe AC-4 und AC-5).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (`test_preview_service_user_isolation.py`): GIVEN zwei echte Testkonten `nutzer_a` und
  `default` mit je eigener GPX-Datei unter `users/nutzer_a/gpx/` bzw. `users/default/gpx/` mit
  unterschiedlichem Inhalt (unterschiedliche Distanz), WHEN `render_email_preview` mit
  `user_id="nutzer_a"` aufgerufen wird, THEN basiert die berechnete Segment-Distanz auf der GPX von
  `nutzer_a`, nicht auf der von `default`.
- [ ] Test 2 (`test_preview_service_user_isolation.py`): GIVEN Konto `default` existiert nicht im
  Test-Datenverzeichnis, WHEN `render_sms_preview` mit `user_id="nutzer_b"` aufgerufen wird, THEN
  wirft kein Fallback-Zugriff auf `users/default/` einen Fehler und die Vorschau liefert die Daten
  von `nutzer_b` korrekt.
- [ ] Test 3 (`test_scheduler_router_requires_user_id.py`): GIVEN ein POST an
  `/api/scheduler/trips/{trip_id}/send` ohne `user_id`-Query-Parameter, WHEN der Request die API
  erreicht, THEN antwortet die API mit 422 und es wird nachweislich keine Mail/SMS versendet
  (Spy/Fixture-Zähler bleibt bei 0).
- [ ] Test 4 (`test_scheduler_router_requires_user_id.py`): GIVEN ein POST an
  `/api/scheduler/compare-presets/{preset_id}/send` sowie an `/api/debug/trigger-radar-alert` ohne
  `user_id`, WHEN der Request gesendet wird, THEN antworten beide Routen mit 422 ohne jede
  Nebenwirkung (kein Versand, kein Alarm-Trigger).
- [ ] Test 5 (`test_scheduler_router_requires_user_id.py`): GIVEN ein POST an
  `/api/scheduler/trips/{trip_id}/send` in exakt der Query-Form, die der Go-Proxy sendet
  (`?user_id=default` bzw. `?user_id=<anderer echter Nutzer>`), WHEN der Request verarbeitet wird,
  THEN dispatcht die Route in beiden Fällen unverändert wie vor dieser Änderung (Versand/Trigger
  läuft, kein 422).
- [ ] Test 6 (`test_inbound_telegram_unknown_chat.py`): GIVEN ein Telegram-Chat, der in keiner
  Nutzerkonfiguration verknüpft ist, WHEN eine Nachricht von diesem Chat verarbeitet wird, THEN
  erhält genau dieser Chat den Registrierungshinweis und es werden keine Trip-Daten irgendeines
  Kontos ausgeliefert.
- [ ] Test 7 (`test_inbound_telegram_unknown_chat.py`): GIVEN das echte Konto `default` hat den
  Telegram-Chat `123456` verknüpft, WHEN eine Nachricht von Chat `123456` eintrifft, THEN wird sie
  als Nachricht des bekannten Kontos `default` verarbeitet (kein Registrierungshinweis).
- [ ] Test 8 (`test_user_id_default_guard.py`): GIVEN der aktuelle Quellbaum unter `api/`, WHEN der
  AST-Wächter über alle Router-Dateien läuft, THEN findet er keine Funktionssignatur mit
  `user_id`-Default `"default"` und keinen `Query("default")`-Aufruf mehr.
- [ ] Test 9 (`test_user_id_default_guard.py`): GIVEN eine testweise eingefügte neue Funktion mit
  `def handler(user_id: str = "default")` in einer `api/`-Datei (Mutations-Fixture im Testverzeichnis,
  nicht im Produktivcode), WHEN der Wächter läuft, THEN schlägt genau dieser Test fehl — der Wächter
  fängt neue Stellen, nicht nur die bekannten.
- [ ] Test 10 (`test_user_id_default_guard.py`): GIVEN die fixierte `src/`-Bestandsliste im Test,
  WHEN ein Listeneintrag im aktuellen Code keine Entsprechung mehr hat (weil er in einer früheren
  Scheibe entfernt wurde), THEN schlägt der Test rot an, bis die Liste manuell nachgezogen wird —
  die Liste darf nie stillschweigend veralten.
- [ ] Test 11 (`test_user_id_default_guard.py`): GIVEN `inbound_email_reader.py` und
  `inbound_telegram_reader.py` nach dieser Änderung, WHEN der Wächter nach `or "default"`-Mustern
  bei der Chat-/Absender-Auflösung sucht, THEN findet er keinen mehr.

Alle Tests laufen ohne `Mock()`/`patch()` auf reale Fixture-Dateien in einem temporären
Test-Datenverzeichnis (Muster: `tmp_path`/`data_dir`-Fixture), lösen den Prüfling relativ zur
eigenen Testdatei auf und sind nach Verhalten benannt, nicht nach Issue-Nummer. Tests 1/2/6/7 sind
die geforderte Zwei-Nutzer-Belegung datenbewegender Pfade (ADR-0003).

## Acceptance Criteria

- **AC-1:** Given zwei echte Testnutzer `nutzer_a` und `default` mit je eigener, unterschiedlicher GPX-Datei unter ihrem Nutzerverzeichnis / When eine E-Mail-, SMS- oder Telegram-Vorschau mit `user_id="nutzer_a"` gerendert wird / Then verwendet die Berechnung ausschließlich die GPX-Daten von `nutzer_a`, niemals die von `default`.
- **AC-2:** Given das Konto `default` besitzt keine GPX-Daten im Testverzeichnis / When eine Vorschau für einen anderen, echten Nutzer angefordert wird / Then greift der Vorschau-Pfad zu keinem Zeitpunkt lesend auf `users/default/` zu und die Vorschau liefert korrekt die Daten des angefragten Nutzers.
- **AC-3:** Given ein POST an eine der drei Routen `scheduler.py:trips/{id}/send`, `scheduler.py:compare-presets/{id}/send` oder `debug.py:trigger-radar-alert` ohne `user_id`-Parameter / When der Request verarbeitet wird / Then antwortet die Route mit HTTP 422 und es wird nachweislich weder eine Nachricht versendet noch ein Alarm ausgelöst.
- **AC-4:** Given ein Aufruf einer der drei Routen mit explizit gesetztem `user_id=default` / When der Request verarbeitet wird / Then läuft der Versand bzw. Trigger unverändert wie vor dieser Änderung durch, weil `default` als expliziter Wert weiterhin gültig ist.
- **AC-5:** Given ein Request in exakt der Query-Form, die der Go-Proxy heute automatisch anhängt (`?user_id=<id>` bei beiden Send-Routen, keine Go-Datei wird in dieser Scheibe geändert) / When dieser Request gegen die geänderte Python-Route läuft / Then dispatcht sie identisch zum Verhalten vor dieser Änderung, für einen anderen echten Nutzer ebenso wie für `default`.
- **AC-6:** Given ein Telegram-Chat ohne jede Verknüpfung zu einem Nutzerkonto / When von diesem Chat eine Nachricht eintrifft / Then erhält ausschließlich dieser fragende Chat den Registrierungshinweis, ohne dass Trip-Daten eines beliebigen Kontos preisgegeben werden.
- **AC-7:** Given das echte Konto `default` hat einen Telegram-Chat verknüpft / When von diesem Chat eine Nachricht eintrifft / Then wird sie wie bei jedem anderen bekannten Nutzer als Nachricht des Kontos `default` verarbeitet, nicht mehr als „unbekannter Absender" behandelt.
- **AC-8:** Given der aktuelle Code unter `api/` nach dieser Änderung / When der AST-Wächter-Test über alle Router läuft / Then findet er keinen `user_id`-Parameter mit String-Default `"default"` und keinen `Query("default")`-Aufruf mehr.
- **AC-9:** Given eine testweise als Mutations-Fixture eingefügte neue Router-Funktion mit `user_id: str = "default"` / When der Wächter-Test erneut läuft / Then schlägt er fehl und benennt die neue Stelle, statt sie stillschweigend zu übergehen.
- **AC-10:** Given die im Wächter-Test fixierte Bestandsliste bekannter `src/`-Signatur-Defaults / When ein Listeneintrag im Code nicht mehr existiert oder eine im Code gefundene Stelle nicht in der Liste steht / Then schlägt der Test in beiden Richtungen rot an, sodass die Liste nie unbemerkt veraltet.
- **AC-11:** Given `inbound_email_reader.py` und `inbound_telegram_reader.py` nach dieser Änderung / When der Wächter-Test nach einem `or "default"`-Rückfall bei der Nutzerauflösung aus Absenderdaten sucht / Then findet er keinen mehr, weder für E-Mail- noch für Telegram-Absender.

## Known Limitations

- Die Go-Seite (`cfg.UserID`-Default, `WithUser("")`-No-Op, Seed-Verhalten) ist bewusst nicht Teil
  dieser Scheibe — siehe Scheibe B.
- Die verbleibenden ~190 Python-Test-Aufrufe mit `user_id="default"`-Signatur-Defaults (u.a.
  `TripReportSchedulerService`, `save_trip`, `TripAlertService`, `WeatherSnapshotService`) sowie die
  `NotificationService()`-Konstruktionen in `inbound_email_reader.py:72` und
  `inbound_telegram_reader.py:108` (hängen am internen `Settings().with_user_profile("default")`-Default)
  werden hier nicht angefasst; der Wächter-Test toleriert die Signatur-Defaults über die fixierte
  Bestandsliste bis Scheibe C.
- Die öffentliche Erreichbarkeit von `/api/debug/` ohne Auth-Kontext ist ein bekanntes, separates
  Problem (#2304) und wird hier nicht behoben — nur der `user_id`-Parameter wird Pflicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (Multi-Tenant-Isolation, bestehend)
- **Rationale:** Diese Scheibe setzt ADR-0003 konsequent um (Rückfall-Verbot), begründet aber
  explizit eine engere Lesart als der Issue-Wortlaut: `"default"` bleibt als expliziter Wert
  zulässig, weil ADR-0003 den automatischen Fallback bei fehlender Identität verbietet, nicht die
  bewusste Verwendung eines existierenden Kontonamens. Kein neues ADR nötig, kein Widerspruch zu
  ADR-0003 — die Abweichung vom Issue-Text wird hier dokumentiert und mit der Spec-Freigabe vom PO
  bestätigt.

## Changelog

- 2026-09-19: Implementiert, Adversary VERIFIED
- 2026-09-18: Initial spec created (Scheibe A von #2151, Analyse aus `docs/context/fix-2151-default-fallbacks-entfernen.md`)
