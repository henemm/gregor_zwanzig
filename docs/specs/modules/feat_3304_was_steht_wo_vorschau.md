---
entity_id: feat_3304_was_steht_wo_vorschau
type: module
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
workflow: feat-3041-tabelle-beim-anlegen
tags: [was-steht-wo, placements, vorschau, anlegen, epic-3122]
---

# Vorschau der Tabelle „Was steht wo“ für noch nicht angelegte Trips und Orte (#3304)

## Approval

- [ ] Approved

## Purpose

Die Karte „Was steht wo“ lädt heute nur für ein gespeichertes Abo (`GET /api/briefings/{id}/placements`). Damit die Tabelle auch auf den Anlegeseiten von Trip und Orten erscheinen kann (#3041, Epic #3122), liefert dieser Teil A einen reinen Lese-Endpunkt `POST /api/briefings/placements/vorschau?kind=route|vergleich`: Er nimmt den Entwurf im Körper und antwortet mit derselben Ansicht wie das Lesen eines gespeicherten Abos, aber mit `stored=false`, ohne etwas zu speichern. Teil B (#3305, Karte im Anlege-Modus und Trip), C (#3306, Orte) und D (#3307, Zustellung und Entfernen des Alt-Panels) sind nicht Teil dieser Spec.

## Source

- **File:** `src/services/placements_view_service.py`, `api/routers/placements.py`, `internal/handler/placements.go`, `internal/router/router.go`
- **Identifier:** `build_placements_preview` (neu), `_trip_abo`/`_orte_abo` (aufgeteilt in Laden und „aus Objekt bauen“), Route `POST /api/briefings/placements/vorschau`, `BriefingPlacementsPreviewHandler` (neu)

> **Schicht-Hinweis:** Python-Core (`src/services/`, `api/`) baut die Ansicht; Go-API (`internal/handler/`, `internal/router/`) prüft Anmeldung, Größe und leitet weiter. **Kein Frontend in dieser Spec** (Anbindung = #3305/#3306).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** EIN Endpunkt, EIN Handler, EINE Service-Funktion mit `kind`; keine zweite Berechnung der Ansicht. Trip und Orte teilen sich `_antwort`/`_tabelle_aufloesen` mit dem GET-Weg.
> - **Mandantentrennung:** `user_id` ausschließlich aus dem Anmeldekontext (Go verwirft Client-`user_id` in Query und Körper, `forwardPreview`); Orte im Entwurf werden nur aus dem Bestand dieses Nutzers aufgelöst; nie `"default"`. Test mit zwei verschiedenen Nutzern.
> - **Kanäle:** Die Ansicht enthält wie bisher die Stellen E-Mail, Telegram, SMS (inkl. Premium-SMS) mit demselben Inhalt wie der GET-Weg; Beispielwerte kommen aus dem festen synthetischen Datensatz (`placements_beispiel`), kein Wetterabruf.

## Estimated Scope

- **LoC:** Produktion ca. +150 bis +220, Tests ca. +300
- **Files:** 4 Produktionsdateien + 3 bis 4 Testdateien
- **Effort:** medium (Risiko LOW bis MEDIUM: rein additiv; Risiken sind Orts-Auflösung über Nutzergrenzen und Routen-Kollision mit `{id}`)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/placements_view_service.py` | MODIFY | `_trip_abo`/`_orte_abo` in „Laden“ und „aus Objekt bauen“ trennen; neue Funktion `build_placements_preview(kind, draft, user_id)`; fehlen `placements.rows` im Entwurf, entstehen sie über `placements_aus_grundauswahl` wie bei `erstanlage_placements`; Antwort mit `stored=False` |
| `api/routers/placements.py` | MODIFY | `POST /api/briefings/placements/vorschau` (`user_id` Query, `kind` Pflicht: sonst 400 `kind_required`); Entwurf unlesbar: 422 `invalid_preset`; Fehlertexte nur über `error_body` |
| `internal/handler/placements.go` | MODIFY | `BriefingPlacementsPreviewHandler`: Anmeldung (401), `kind` prüfen (400 `kind_required`), Körper mit `http.MaxBytesReader` (256 KB) lesen (zu groß: 413 `payload_too_large`, kaputtes JSON: 400 `bad_request`, beides vor dem Kern-Aufruf), per `forwardPreview` (POST) weiterreichen; `user_id` nur aus dem Anmeldekontext |
| `internal/router/router.go` | MODIFY | `r.Post("/api/briefings/placements/vorschau", …)` registrieren, ohne den Pfad `/api/briefings/{id}/…` zu berühren |
| `tests/tdd/test_3304_placements_vorschau.py` | CREATE | Python-Tests gegen Service und Endpunkt (echte Dateien im Datenbaum, zwei Nutzer) |
| `internal/handler/placements_vorschau_3304_test.go` | CREATE | Go-Handler-Tests gegen einen echten Python-Kern-Stub-Server (Muster `placements_test.go`, `placements_erstanlage_3154_test.go`) |
| `internal/router/placements_vorschau_route_3304_test.go` | CREATE | Routing-Test über den echten Router (Muster `placements_route_test.go`) |
| `docs/reference/api_contract.md` | MODIFY | Endpunkt und Antwortform eintragen (Antwort = GET-Ansicht, `stored=false`) |

### Nicht in dieser Spec

- Karte im Anlege-Modus, Frontend-Aufruf, Entprellung und Sequenznummer, Trip-Nutzlast (`placements`, `show_night_block`, `report_config.*`): **#3305** (B).
- Orte-Anbindung (`display_config.placements`, `hourly_enabled`, `telegram_style`): **#3306** (C).
- `ZustellungTab` im Anlege-Modus und Entfernen von `WetterMetrikenVersandPanel`: **#3307** (D).
- Änderungen am Speichern, am ETag/If-Match, an der Go-Anlage (`anlageTabelle`) oder am GET/PUT-Weg.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.load_trip` (akzeptiert `dict`, `src/app/loader.py:428`) | Python | Entwurf eines Trips ohne Datei in das Trip-Objekt umsetzen |
| `app.loader.compare_preset_to_dict` | Python | Orts-Vergleich-Entwurf in die Wörterbuch-Form des gespeicherten Abos bringen |
| `services.placements.placements_aus_grundauswahl` / `read_placements` / `resolve_rows` | Python-Service | Tabelle aus Grundauswahl, wenn der Entwurf keine Zeilen trägt |
| `services.placements_beispiel` | Python-Service | synthetische Beispielwerte (kein Wetterabruf) |
| `app.loader.load_all_locations(user_id)`, `order_locations_by_ids` | Python | Orte des Entwurfs nur aus dem Bestand des angemeldeten Nutzers |
| `services.send_outcomes.error_body` | Python | Fehlerantworten über den i18n-Katalog |
| `forwardPreview` (`internal/handler/preview_proxy.go`) | Go | Proxy, injiziert `user_id` aus dem Anmeldekontext |
| `middleware.LimitBody` (`internal/middleware/request_guard.go`) | Go | globale Rumpfgrenze, hier durch die engere Handler-Grenze ergänzt |
| `feat_3122_was_steht_wo`, `feat_3237_altpfad_entfernen` | Spec | Antwortform, Erstanlage-Regel |
| ADR-0124 | ADR | Tabelle als einzige Quelle |

## Implementation Details

**Python-Service.** `_trip_abo` und `_orte_abo` bestehen heute aus „Abo laden“ plus „`_Abo` und Muster-Funktion bauen“. Der zweite Teil wird zu je einer Funktion, die ein Trip-Objekt bzw. ein Preset-Wörterbuch entgegennimmt; der Ladeteil ruft sie unverändert (GET- und Erstanlage-Weg bleiben bitgleich). `build_placements_preview(kind, draft, user_id)` ruft sie mit dem Entwurf: Trip über `load_trip(dict)`, Orte über `compare_preset_to_dict` auf dem Entwurf. Danach läuft der unveränderte Rest von `build_placements_view` (`_tabelle_aufloesen`, `_tabellen_zeilen`, `_antwort`) und liefert dieselben Schlüssel. Weil `_tabelle_aufloesen` ohne gespeicherte Tabelle `placements_aus_grundauswahl` nutzt und `stored` aus „Entwurf trägt lesbare `placements.rows`“ ableitet, wäre `stored` für einen Entwurf mit Zeilen `True`; die Vorschau setzt es **immer** auf `False`. Zeilen im Entwurf bleiben unverändert in `placements` erhalten (wie beim GET).

**Orte und Nutzergrenze.** Ortsnamen und Anzahl (`location_count`) kommen aus `_orte_des_abos(preset, user_id)` mit `load_all_locations(user_id)`; Orts-IDs im Entwurf, die dem Nutzer nicht gehören oder unbekannt sind, entfallen still (`order_locations_by_ids` behält nur bekannte). Eine im Körper mitgeschickte `user_id` oder Fremdkennung wirkt nicht: die Funktion bekommt die Kennung ausschließlich als Argument aus der Query, die Go-API überschreibt sie aus der Anmeldung. Die Kennung des Entwurfs (`id`) wird nicht zum Laden irgendeiner Datei verwendet.

**Kein Schreiben.** Der Service ruft keine Speicherfunktion und kein Anlegen. Der Router gibt weder ETag noch `If-Match`.

**Python-Router.** `POST /api/briefings/placements/vorschau` wird als eigener fester Pfad registriert. Er steht in derselben Datei, aber ohne `{entity_id}`-Segment an der Stelle des Pfadteils `placements`; die bestehenden `GET /api/briefings/{entity_id}/placements(/erstanlage)` haben andere Methode und Segmentstruktur. Fehler: `kind` fehlt/unbekannt: `_error("kind_required")` (400); Entwurf kein Objekt oder von `load_trip`/`compare_preset_to_dict` nicht lesbar: `invalid_preset` (422) mit Text aus `versand.vorschau.entwurf_unlesbar` (`error_body(..., text_key=...)`), alle Texte über `error_body` in der Nutzersprache.

**Go-Handler.** `BriefingPlacementsPreviewHandler(pythonURL)`: Nutzer aus `middleware.UserIDFromContext`, leer → 401 `unauthorized`; `kind` über `isValidBriefingKind`, sonst 400 `kind_required`; Körper über `http.MaxBytesReader` auf 256 KB begrenzt und vollständig gelesen: `*http.MaxBytesError` → 413 `payload_too_large`, kein gültiges JSON-Objekt → 400 `bad_request`; erst danach `forwardPreview(w, r, POST, pythonURL+"/api/briefings/placements/vorschau", previewProxyTimeout)` mit dem gelesenen Körper und nur `kind` in der Query (Client-`user_id` fällt weg, `forwardPreview` setzt die echte). Kein Store-Zugriff nötig, also kein `WithUser`; dennoch bleibt die Isolation durch die Python-Seite (Orte aus dem Bestand des Nutzers).

**Router (Go).** Registrierung neben Zeile 388/389. chi bevorzugt den statischen Pfad vor `{id}`-Mustern; ein Test bestätigt, dass `placements` nicht als `{id}` gelesen wird.

## Expected Behavior

- **Input:** `POST /api/briefings/placements/vorschau?kind=route|vergleich` mit angemeldetem Nutzer; Körper = Entwurf in der Form der Anlage-Nutzlast (`POST /api/trips` bzw. Orts-Vergleich-Anlage), mit oder ohne `display_config.placements.rows`.
- **Output:** JSON mit denselben Schlüsseln wie `GET /api/briefings/{id}/placements` (`kind, lang, stored, placements, location_count, columns, fixed_rows, rows, sms_example, outlook_reports, blocks, legend, example_version`), `stored` immer `false`.
- **Side effects:** keine. Es wird nichts gespeichert, kein Abo angelegt, kein Wetter abgerufen.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Trip-Entwurf im Körper und ein gespeicherter Trip mit gleicher Konfiguration / When die Vorschau mit `kind=route` und `GET /api/briefings/{id}/placements?kind=route` abgefragt werden / Then haben beide Antworten dieselben Schlüssel und denselben Inhalt in Spalten, Zeilen, SMS-Beispiel, Legende und Ausblick, nur `stored` ist bei der Vorschau `false`.
  - Test: Trip speichern, dieselbe Konfiguration als Entwurf senden, beide Antworten vergleichen (Schlüsselmenge gleich, Werte gleich außer `stored`).

- **AC-2:** Given ein Nutzer mit Orts-Vergleich-Entwurf (zwei eigene Orte) und ein gespeichertes Orts-Vergleich-Abo gleicher Konfiguration / When die Vorschau mit `kind=vergleich` und der GET-Weg abgefragt werden / Then stimmen Form und Inhalt überein (inklusive `location_count` und Beispielwerten der Orte), nur `stored` ist `false`.
  - Test: Orte und Vergleich speichern, Entwurf gleicher Konfiguration senden, Antworten vergleichen.

- **AC-3:** Given ein Entwurf ohne `placements.rows` und ein Entwurf mit eigenen Zeilen / When die Vorschau abgefragt wird / Then enthält die Antwort im ersten Fall die Zeilen aus der Grundauswahl, exakt wie sie die Erstanlage schreiben würde, im zweiten Fall genau die mitgeschickten Zeilen in dieser Reihenfolge, und `stored` bleibt in beiden Fällen `false`.
  - Test: Antwort `placements.rows` gegen `erstanlage_placements` desselben Entwurfs bzw. gegen die mitgeschickten Zeilen vergleichen.

- **AC-4:** Given ein Nutzer mit bekanntem Datenbaum / When er die Vorschau für Trip und Orts-Vergleich mehrfach abruft / Then bleibt der Datenbaum byte-gleich (keine neue Datei, kein neues Abo, keine geänderte Datei) und die Antwort trägt weder ETag noch eine Anlage-Kennung.
  - Test: Verzeichnisbaum mit Dateiinhalten vor und nach den Aufrufen vergleichen; Trips und Orts-Vergleiche des Nutzers zählen.

- **AC-5:** Given zwei verschiedene Nutzer A und B, wobei der Entwurf von A eine Orts-ID von B und eine unbekannte ID nennt und im Körper `user_id` von B steht / When A die Vorschau abruft / Then erscheinen nur die eigenen Orte von A (`location_count` zählt nur sie, keine Namen oder Werte von B), und die `user_id` im Körper und in der Query bleiben ohne Wirkung, weil allein die Anmeldung gilt.
  - Test: Zwei Nutzer mit je eigenen Orten anlegen; Vorschau als A mit fremder ID und fremder `user_id`; Antwort enthält keine Daten von B; derselbe Aufruf als B liefert dessen eigene Orte.

- **AC-6:** Given eine Anfrage ohne Anmeldung / When die Vorschau aufgerufen wird / Then antwortet die API mit 401 und es erfolgt kein Aufruf des Python-Kerns.
  - Test: Aufruf ohne Sitzung über den echten Router; Kern-Stub zählt null Anfragen.

- **AC-7:** Given ein angemeldeter Nutzer / When `kind` fehlt oder unbekannt ist / Then antwortet die API mit 400 und dem Fehlercode `kind_required` im Text der Nutzersprache (Katalog, kein Freitext), auch direkt am Python-Kern.
  - Test: Aufruf ohne `kind` und mit `kind=foo` an Go und an den Kern; Status 400, Code `kind_required`.

- **AC-8:** Given ein angemeldeter Nutzer / When der Körper größer als 256 KB oder kein gültiges JSON-Objekt ist / Then antwortet die API bei zu großem Körper mit 413 `payload_too_large` und bei kaputtem JSON mit 400 `bad_request`, jeweils ohne dass der Python-Kern aufgerufen wird; ein Entwurf, den der Kern nicht lesen kann, ergibt 422 `invalid_preset`.
  - Test: Körper mit 300 KB, Körper `{kaputt` und Körper `[]` über den Go-Handler gegen den Kern-Stub (null Anfragen); lesbarer, aber ungültiger Entwurf direkt am Kern (422).

- **AC-9:** Given der bestehende Lese-, Schreib- und Anlegeweg / When nach der Änderung `GET` und `PUT /api/briefings/{id}/placements` sowie die Anlage eines Trips und Orts-Vergleichs (`anlageTabelle`) laufen / Then verhalten sie sich unverändert (gleiche Antworten, ETag und If-Match wie zuvor, Anlage schreibt weiterhin die volle Tabelle).
  - Test: bestehende Tests `placements_test.go`, `placements_erstanlage_3154_test.go`, `briefing_anlage_tabelle_3237_test.go`, `test_placements_tabelle_endpoint.py` und `test_3237_placements_aus_grundauswahl.py` laufen unverändert grün.

- **AC-10:** Given ein Trip oder Orts-Vergleich mit der Kennung `placements` oder ein Aufruf des Pfads `/api/briefings/placements/vorschau` / When die Vorschau über Go und Python aufgerufen wird / Then wird der Pfad als Vorschau behandelt und nicht als Abo mit der Kennung `placements` gelesen (kein 404 `not_found` für ein Abo, kein Aufruf des GET-Handlers).
  - Test: Router-Test mit echtem Router und Kern-Stub: der Stub sieht Pfad `/api/briefings/placements/vorschau`, nie `/api/briefings/placements/placements`; Python-Test ruft den Endpunkt über `TestClient` auf.

## Definition of Done

- AC-1 bis AC-10 durch Kern-Tests ohne Mock-Theater grün (Python-Service/Router, Go-Handler und Route gegen echten Kern-Stub wie in den bestehenden placements-Tests).
- Zwei-Nutzer-Test (AC-5) grün; Datenbaum nach Vorschau-Aufrufen byte-gleich (AC-4).
- Bestehende Tests zu GET/PUT der Tabelle und zur Go-Anlage unverändert grün (AC-9).
- `docs/reference/api_contract.md` beschreibt den Vorschau-Weg.
- Staging: Vorschau-Aufruf mit angemeldetem Prüfkonto liefert die Ansicht für Trip- und Orte-Entwurf; Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN gespeicherter Trip und gleicher Entwurf WHEN Vorschau und GET THEN gleiche Schlüssel und Werte, `stored=false` (AC-1)
- [ ] Test 2: GIVEN Orts-Vergleich gespeichert und als Entwurf WHEN Vorschau und GET THEN gleiche Form, `location_count` gleich (AC-2)
- [ ] Test 3: GIVEN Entwurf ohne Zeilen / mit Zeilen WHEN Vorschau THEN Grundauswahl-Zeilen bzw. genau die mitgeschickten (AC-3)
- [ ] Test 4: GIVEN Datenbaum WHEN mehrere Vorschau-Aufrufe THEN Baum unverändert (AC-4)
- [ ] Test 5: GIVEN Nutzer A und B, fremde Orts-ID und fremde `user_id` im Körper WHEN Vorschau als A THEN nur Orte von A (AC-5)
- [ ] Test 6: GIVEN keine Anmeldung WHEN Vorschau THEN 401, Kern ohne Aufruf (AC-6)
- [ ] Test 7: GIVEN `kind` fehlt oder unbekannt WHEN Vorschau THEN 400 `kind_required` (AC-7)
- [ ] Test 8: GIVEN 300-KB-Körper, kaputtes JSON, unlesbarer Entwurf WHEN Vorschau THEN 413, 400 bzw. 422, Kern ohne Aufruf bei 413/400 (AC-8)
- [ ] Test 9: GIVEN bestehende GET/PUT/Anlage-Tests WHEN neue Route registriert THEN unverändert grün (AC-9)
- [ ] Test 10: GIVEN Pfad `/api/briefings/placements/vorschau` WHEN Router und Python-App THEN Vorschau-Handler, nicht `{id}`-Handler (AC-10)

Test-Politik: kein Mock-Theater. Python-Tests nutzen echte Dateien im temporären Datenbaum mit zwei Nutzern; Go-Handler- und Router-Tests nutzen einen echten HTTP-Stub-Server für den Python-Kern, der die empfangenen Pfade, Queries und Körper aufzeichnet (Muster der bestehenden placements-Tests). Dateiinhalt-Checks sind kein Verhaltensnachweis.

## Known Limitations

- Die Vorschau gilt nur für Beispielwerte aus dem festen Datensatz; echte Wetterwerte erscheinen nicht (wie beim GET-Weg).
- Der Endpunkt prüft die Zeilen im Entwurf nicht inhaltlich (wie beim PUT, ADR-0077); unlesbare Zeilen wirken nicht, wie bisher im Lesepfad.
- Solange B bis D fehlen, ruft kein Frontend die Vorschau auf; der Endpunkt ist rein additiv.
- Gate-Konfiguration und Sperren werden nicht angefasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0124 gilt unverändert)
- **Rationale:** ADR-0124 macht die Tabelle zur einzigen Quelle; dieser Endpunkt liefert nur die Ansicht für einen noch nicht gespeicherten Entwurf über dieselbe Service-Logik und ändert keine frühere Entscheidung. Er ist Teil der Umsetzung von #3041 (Anlegen = Bearbeiten, PO-Vorgabe).

## Changelog

- 2026-11-23: Initial spec created (Teil A von #3041, Issue #3304, Epic #3122).
- 2026-11-23: Fehlercode nach Adversary F001: Code bleibt 422 `invalid_preset` (AC-8 freigegeben), der Text kommt aber aus dem eigenen Katalogschlüssel `versand.vorschau.entwurf_unlesbar` (DE/EN) statt „Orte-Abo nicht versendbar: {reason}“ (offener Platzhalter, bei Trips falsch).
