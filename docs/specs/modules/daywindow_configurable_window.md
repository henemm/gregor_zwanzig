---
entity_id: daywindow_configurable_window
type: feature
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [gewitter, sms, tagesfenster, epic-1319, issue-1319-slice-b, adr-0025, konfigurierbarkeit]
---

# Konfigurierbares Tagesfenster pro Wanderung (Epic #1319, Scheibe B+C)

## Approval

- [x] Approved (PO „freigabe" 2026-07-23)

## Purpose

Scheibe A (`docs/specs/modules/sms_daywindow_aggregation.md`) hat das Tagesfenster für alle
vier Kurzformen (SMS, E-Mail-Kurzzusammenfassung, Metriken-Pillen, Telegram-Fußzeile) fest auf
04:00–19:00 zentralisiert. Diese Spec ersetzt die beiden benannten Modul-Konstanten
`DAY_WINDOW_START_HOUR`/`DAY_WINDOW_END_HOUR` durch ein pro Wanderung einstellbares
Start-/Endstunden-Paar — inklusive Persistenz (additiv in `report_config`, mandantengetrennt)
und Bedienoberfläche im Trip-Editor (SMS-/Zeitplan-Einstellung). Ohne gesetzten Wert bleibt das
bisherige Verhalten (Default 04–19) unverändert, sowohl für neue als auch für bestehende
Wanderungen.

## Source

- **File:** `src/output/renderers/day_window.py`
- **Identifier:** `DAY_WINDOW_START_HOUR`/`DAY_WINDOW_END_HOUR` (Modul-Konstanten) →
  `build_day_window_points(segments, night_weather, tz)` (Zeile 59-63) bekommt ein optionales
  Fenster-Parameterpaar; ohne Wert bleibt Default 4/19 (Rückwärtskompatibilität für Alt-Aufrufer).

- **File:** `src/app/models.py`
- **Identifier:** `TripReportConfig` (Zeile 723-789) — neues Feld-Paar
  `day_window_start_hour: Optional[int]` / `day_window_end_hour: Optional[int]`.

- **File:** `internal/store/slot_hour_normalization.go`
- **Identifier:** neue Validierungs-/Klemmungsfunktion analog `NormalizeReportConfigSlotTimes`
  (Zeile 71-85), die `report_config.day_window_start_hour`/`_end_hour` auf 0–23 und
  `start < end` prüft und bei Verstoß auf `nil` (= Default 4/19 beim Python-Lesen) zurücksetzt.

- **File:** `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte`
- **Identifier:** neues Fenster-Control, analog dem bestehenden `{#if isRoute}`-Block
  (Zeile 173-194, Mehrtages-Trend-Karte) — gleiches Muster: nur `context="route"` sichtbar.

> **Schicht-Hinweis:** Persistenz-Feld und Renderer-Logik liegen im Python-Core
> (`src/app/`, `src/output/`), Validierung/Klemmung im Go-Store (`internal/store/`), Bedienung
> im SvelteKit-Frontend (`frontend/src/lib/components/shared/`). Alle drei Schichten sind
> betroffen, keine Doppelarbeit zwischen ihnen (Issue #129-Muster geprüft).

## Estimated Scope

- **LoC:** ~250-290 (Voll-Stack: 6 Python-Dateien, 1 Go-Datei, 2-3 Frontend-Dateien, 1 Doku-Datei,
  3-4 Testdateien). **Über dem 250-LoC-Workflow-Limit — PO hat den Override für diese Scheibe
  bereits autorisiert** (DEC-3, PO 2026-07-23, wegen Scope-Erweiterung um die UI). Konkreter
  `loc_limit_override`-Aufruf erfolgt in der Implement-Phase, nicht in dieser Spec.
- **Files:** ~13-14 (Python 6: `day_window.py`, `sms_trip.py`, `compact_summary.py`,
  `email/helpers.py`, `narrow.py`, `notification_service.py`, `models.py`, `loader.py` — Python
  ist hier 8, nicht 6, s. Affected-Files-Tabelle; Go 1; Frontend 2-3; Doku 1; Tests 3-4).
- **Effort:** high (cross-language, 5 Durchreich-Stellen, kritische Gap-Kopplung, geteilter
  Frontend-Baustein mit Compare-Ausschluss, Mandantentrennung muss mit zwei Nutzern bewiesen
  werden).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `sms_daywindow_aggregation` (Scheibe A, Commit `087f643f`) | Spec/Modul | Liefert das geteilte Fenster-Modul `day_window.py` und die Erkenntnis, dass Fenster-Logik nie viermal unabhängig nachgebaut werden darf (#874/#1275-Fehlermodus) |
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | Architekturentscheidung | „Eine Quelle, ein Fenster für alle Kanäle" — diese Spec ändert den Fenster-**Wert** (jetzt konfigurierbar), nicht das Prinzip |
| `src/services/notification_service.py` (`compute_has_gap`, Zeile ~190-214) | function | Nutzt dieselben Konstanten für die Datenlücken-Erkennung — MUSS dasselbe (konfigurierte) Fenster verwenden, sonst divergieren Anzeige und Gap-Erkennung (Issue #1331/#1334-Regressionsrisiko) |
| `internal/handler/config_merge.go` (`mergeConfigMap`) | function | RMW-Merge für `report_config`-Map — neuer Key fließt automatisch durch, kein eigener Merge-Code nötig |
| `src/app/loader.py` (`_deep_merge_preserve_unknown`, Zeile ~98) | function | Python-seitiger RMW-Merge; bewahrt unbekannte/alte Keys beim Speichern |
| `ComparePreset.hour_from`/`hour_to` (Go-Modell) | Naming-Präzedenz | Exaktes Vorbild für ein int-Stunden-Paar im selben Codebestand |
| `VTSchedulePlan.svelte` `{#if isRoute}`-Block (Mehrtages-Trend-Karte) | Frontend-Muster | Exaktes Vorbild für „nur im Route-Kontext sichtbar" |
| Issue #1318 FB01 (Compare-Ausschluss-Präzedenz) | Entscheidung | Begründet, warum Compare-eigene Zeitfenster (`hour_from`/`hour_to`) unabhängig vom Trip-Tagesfenster bleiben |

## Implementation Details

**Persistenz (additiv, kein neues DTO):** Zwei neue Felder in `TripReportConfig`:
`day_window_start_hour: Optional[int] = None`, `day_window_end_hour: Optional[int] = None`.
`None`/fehlend = Default 4/19 (Rückwärtskompatibilität für alle bestehenden Trip-JSONs unter
`data/users/<user_id>/briefings/<trip_id>.json`). Python-seitig müssen `_parse_trip` und
`_trip_to_dict` (`loader.py`) das Feld-Paar lesen/schreiben; der bestehende
`_deep_merge_preserve_unknown`-RMW-Merge bewahrt dabei alle anderen `report_config`-Keys
unverändert. Go-seitig ist `report_config` bereits eine generische `map[string]interface{}` —
der neue Key fließt ohne Code-Änderung durch `mergeConfigMap` (`internal/handler/config_merge.go`,
aufgerufen aus `trip.go:241`); Auth läuft bereits über
`s.WithUser(middleware.UserIDFromContext(...))` (`trip.go:192`).

**Validierung (Defense-in-Depth, DEC-2):** Das Frontend verhindert ungültige Eingabe bereits am
Control selbst (Endstunde-Optionen sind auf „> gewählte Startstunde" begrenzt, beide nur
0–23 wählbar). Zusätzlich klemmt der Go-Store defensiv (analog
`NormalizeReportConfigSlotTimes`, `slot_hour_normalization.go:71-85`): liegt einer der beiden
Werte außerhalb 0–23 oder ist `start >= end`, wird das Feld-Paar beim Lesen auf „nicht gesetzt"
(→ Python-Default 4/19) zurückgesetzt — kein HTTP-400 im Normalpfad, nie ein kaputtes Briefing
durch Import/Migration/API-Umgehung der UI.

**Renderer-Durchreichung:** `build_day_window_points(segments, night_weather, tz, start_hour=4,
end_hour=19)` — Default-Parameter halten alle Alt-Aufrufer (z. B. Tests ohne Fenster-Argument)
funktionsfähig. Die fünf Aufrufstellen (`sms_trip.py:170`, `compact_summary.py:175`,
`email/helpers.py:1514`, `narrow.py:200`, `notification_service.py`s `compute_has_gap`) lesen
das Fenster aus `TripReportConfig.day_window_start_hour`/`_end_hour` (mit Default-Fallback 4/19)
und reichen es an dieselbe Funktion durch — **eine** Implementierung, nicht fünf unabhängige
Kopien.

**Semantik bleibt unverändert (aus Scheibe A übernommen):** Endstunde bleibt **inklusiv**
(`start_hour <= h <= end_hour`, h = Endstunde ist noch im Fenster). Kein Wrap-Around (Tagesfenster,
`start < end` erzwungen). Die ortsgenaue Zuordnung (vor Ankunft = Segment-Zeitreihe, ab Ankunft =
`night_weather`) und die Höchstwert-Dedup-Logik (`_merge_hour`) ändern sich nicht — es ändert sich
nur, **welche** Stunden-Grenzen das Fenster hat, nicht **wie** innerhalb des Fensters aggregiert
wird.

**Frontend:** `VTSchedulePlan.svelte` (bzw. das übergeordnete `VersandTab.svelte`) bekommt ein
neues Fenster-Control (zwei Stunden-Dropdowns oder ein Zeit-Doppel-Input, analog dem bestehenden
`vt-time-input`-Stil) unter der bestehenden SMS-/Zeitplan-Sektion. Endstunde-Optionen werden
reaktiv auf „> Startstunde" begrenzt (kein serverseitiger 400 nötig, aber clientseitig sauber).
Sichtbarkeit exakt wie die bestehende Mehrtages-Trend-Karte: `{#if isRoute}` — bei
`context="vergleich"` erscheint das Control nicht (DEC-4, Präzedenz #1318 FB01). Speichern läuft
über den bestehenden `report_config`-PUT-Pfad, kein neuer Endpoint.

## Expected Behavior

- **Input:** Trip-Editor: Nutzer wählt Start-/Endstunde im Fenster-Control und speichert.
  Backend: `TripReportConfig` mit optionalem `day_window_start_hour`/`_end_hour`.
- **Output:** Alle vier Kurzformen UND `compute_has_gap()` verwenden fortan konsistent das
  konfigurierte Fenster statt 4/19. Ohne gesetzten Wert bleibt das Verhalten identisch zu
  Scheibe A (Default 4/19).
- **Side effects:** Keine neuen Fetches, keine neue Persistenzstruktur — reine Erweiterung des
  bestehenden `report_config`-Feld-Sets und der bestehenden Renderer-Parameter.

## Acceptance Criteria

- **AC-1:** Given zwei verschiedene Nutzer A und B mit je einer Wanderung / When Nutzer A
  `day_window_start_hour=5`/`day_window_end_hour=17` über den Trip-Editor speichert / Then wird
  ausschließlich Nutzer As Trip-JSON unter `data/users/<user_a>/briefings/<trip_id>.json` verändert,
  Nutzer Bs Wanderung bleibt beim Default 4/19, und alle vorher vorhandenen `report_config`-Keys
  (z. B. `show_stability`, `daily_summary_metrics`) bleiben in beiden Dateien unangetastet (RMW-Merge,
  kein Datenverlust, Mandantentrennung).
  - Test: PUT `report_config` als Nutzer A und Nutzer B (unterschiedliche `user_id` aus
    Auth-Kontext) gegen je eine vorbereitete Trip-Datei mit bereits gesetzten Fremd-Feldern;
    Assert, dass nur die jeweils eigene Datei das neue Feld trägt und alle Alt-Felder erhalten
    bleiben.

- **AC-2:** Given eine bestehende Wanderung ohne `day_window_start_hour`/`_end_hour` im
  `report_config` (Alt-Trip vor dieser Spec angelegt) / When einer der vier Kurzform-Renderer
  oder `compute_has_gap()` aufgerufen wird / Then wird das Fenster 04:00–19:00 verwendet, identisch
  zum Verhalten vor dieser Änderung (kein Crash, kein `KeyError`, still ladender Default).
  - Test: Trip-Fixture ohne die beiden neuen Felder laden, `build_day_window_points()` ohne
    explizites Fenster-Argument aufrufen; Assert auf identisches Ergebnis wie mit `start_hour=4,
    end_hour=19` explizit übergeben.

- **AC-3:** Given eine Wanderung mit gespeichertem Fenster 06:00–16:00 und einer Wetter-Zeitreihe
  mit je einem Ereignis um 05:00 (außerhalb) und um 16:00 (innerhalb, Grenzstunde inklusiv) /
  When SMS, E-Mail-Kurzzusammenfassung, Metriken-Pille, Telegram-Fußzeile UND `compute_has_gap()`
  aus demselben `format_email()`-Aufruf erzeugt werden / Then zeigen alle vier Kurzformen
  konsistent nur das 16:00-Ereignis (nicht 05:00), und `compute_has_gap()` markiert keine Lücke
  für 16:00 (Erkennung == Anzeige, kein Divergieren zwischen den vier Kanälen und der
  Gap-Erkennung).
  - Test: ein `format_email()`-Aufruf mit konfiguriertem Fenster 06-16, Assert über alle vier
    Ausgabefelder plus einen separaten `compute_has_gap()`-Aufruf mit denselben Segmenten/demselben
    Fenster.

- **AC-4:** Given ein über die API direkt gesetztes ungültiges Fenster (z. B.
  `day_window_start_hour=20`, `day_window_end_hour=10`, also `start >= end`, oder ein Wert außerhalb
  0–23 — simuliert eine Umgehung der UI-Validierung, z. B. Import/Migration) / When die Wanderung
  geladen und ein Briefing gerendert wird / Then fällt das Fenster still auf den Default 4/19
  zurück (kein HTTP-400, kein Absturz, kein leeres/kaputtes Briefing).
  - Test: Trip-JSON mit ungültigem Feld-Paar direkt auf die Platte schreiben (unter Umgehung der
    UI), Go-Store-Ladepfad und anschließenden Renderer-Aufruf prüfen; Assert auf geklemmten/
    zurückgesetzten Wert und ein normal gerendertes Briefing.

- **AC-5:** Given ein Nutzer öffnet die SMS-/Zeitplan-Einstellung eines Trips im Editor
  (`context="route"`) / When er eine Startstunde wählt / Then bietet das Endstunde-Control nur
  noch Werte an, die größer als die gewählte Startstunde sind (0–23 begrenzt), und beim Speichern
  löst genau EIN PUT-Request aus, der das Feld-Paar persistiert.
  - Test: Playwright-E2E auf Staging — Startstunde setzen, prüfen dass Endstunde-Optionen
    reduziert sind, ungültige Kombination ist nicht wählbar, Speichern auslösen und PUT-Count
    (Netzwerk-Log) auf genau 1 prüfen, danach Reload und Persistenz verifizieren.

- **AC-6:** Given derselbe geteilte VersandTab-Organismus wird im Compare-Editor mit
  `context="vergleich"` gerendert / When die Zeitplan-Sektion angezeigt wird / Then erscheint das
  Tagesfenster-Control NICHT (Präzedenz #1318 FB01) — der bestehende Compare-eigene
  `hour_from`/`hour_to`-Mechanismus bleibt unverändert und unberührt.
  - Test: Component-/E2E-Test rendert `VTSchedulePlan` mit `context="vergleich"` und prüft, dass
    kein Fenster-Control-Testid im DOM vorhanden ist, während `context="route"` es zeigt.

## Known Limitations

- **N-Logik** (Nacht-Tiefsttemperatur-Fensterung, Scheibe D) und **TH+:**-Bezugstag-Verhalten
  (Scheibe E) bleiben unverändert und sind nicht Teil dieser Spec.
- Die Fenster-**Semantik** selbst (inklusive Endstunde, kein Wrap-Around, ortsgenaue
  Ankunfts-Logik) wird nicht verändert — nur die Zahlenwerte werden konfigurierbar.
- Der Compare-eigene `hour_from`/`hour_to`-Mechanismus (`ComparePreset`) ist von dieser Spec
  vollständig unberührt; es entsteht keine Konvergenz zwischen beiden Konzepten in dieser Scheibe.
- Die aus Scheibe A bekannte Provider-Einschränkung (volle Tagesdaten im ersten Segment nur für
  OpenMeteo verifiziert) gilt unverändert fort und wird durch die Konfigurierbarkeit nicht neu
  geprüft.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025 (Fortführung, keine Novellierung nötig)
- **Rationale:** ADR-0025 verlangt „eine Quelle, ein Fenster für alle Kanäle" — diese Spec ändert
  nicht das Prinzip, sondern macht den Fenster-**Wert** pro Wanderung konfigurierbar, wobei
  weiterhin exakt **eine** Implementierung (`build_day_window_points`) von allen vier Kurzformen
  **und** der Gap-Erkennung (`compute_has_gap`) konsumiert wird. Die Konsistenz-Invariante (kein
  Kanal widerspricht einem anderen) bleibt vollständig erhalten, unabhängig davon, welches
  Fenster konfiguriert ist.

## Changelog

- 2026-07-23: Initial spec created (Epic #1319, Scheibe B+C, PO-Scope-Erweiterung um UI 2026-07-23)
