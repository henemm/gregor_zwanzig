---
entity_id: issue_995_mail_bugs_bundle
type: bugfix
created: 2026-07-03
updated: 2026-07-03
status: draft
version: "1.0"
tags: [briefing, email, scheduler, trip-model, mail-rendering]
---

<!-- Issue #995 — E-Mail Fehler (Bug-Bündel: Segment-Startzeit, Zell-Tönung, Pause-Scheduler) -->

# Issue 995 — E-Mail-Fehler-Bündel (Startzeitpunkt, Zellhintergrund, Pausierte Trips)

## Approval

- [ ] Approved

## Purpose

Drei unabhängige, im selben GitHub-Issue #995 gemeldete E-Mail-/Briefing-Fehler beheben:
(A) eine geänderte Etappen-Startzeit wird in der Segmenttabelle ignoriert, weil GPX-Import-
Zeiten fälschlich denselben Rang wie bewusst gesetzte Zeiten haben, (B) der farbige
Zellhintergrund der Warn-Spalten (z.B. Gust) füllt die Tabellenzelle in manchen Mail-Clients
nicht vollflächig aus, weil ein Span/Negativ-Margin-Trick statt direktem Inline-Style auf dem
`<td>` verwendet wird, (C) Briefings werden trotz aktivem Trip-Detail-Pause-Button weiterhin
automatisch verschickt, weil der Scheduler `trip.paused_at` nicht prüft. Alle drei Punkte sind
in `docs/context/fix-995-mail-bugs-bundle.md` vollständig analysiert (Root-Cause, Datei:Zeile,
Challenger-Verdict) — diese Spec baut direkt darauf auf.

## Source

- **File (Gruppe A):** `src/services/trip_segments.py` — `convert_trip_to_segments()` (Zeilen 77-102, insb. Prioritätskette 86-96)
- **File (Gruppe A):** `src/services/gpx_processing.py` — `segments_to_trip()` (Zeilen 125-160)
- **File (Gruppe A):** `src/app/trip.py` — `Waypoint` (Zeile 62ff.), neues Herkunfts-Flag
- **File (Gruppe B):** `src/output/renderers/email/html.py` — `_render_html_table()` (Zeilen 586-592), Referenz-Pattern `_otd()` (Zeilen 1106-1117)
- **File (Gruppe C):** `src/app/trip.py` — `Trip`-Dataclass (Zeile 168ff.), neues Feld `paused_at`
- **File (Gruppe C):** `src/app/loader.py` — `load_trip()` (Zeilen 395-428), Schreib-Pfad (Zeilen 1042-1062)
- **File (Gruppe C):** `src/services/trip_report_scheduler.py` — `_get_active_trips()` (Zeilen 262-303)
- **Identifier:** `convert_trip_to_segments`, `segments_to_trip`, `_render_html_table`, `_get_active_trips`, `class Trip`, `class Waypoint`, `load_trip`

> **Schicht-Hinweis:** Alle drei Punkte liegen ausschließlich im Python-Backend
> (`src/services/`, `src/app/`, `src/output/renderers/email/`, FastAPI-Core). Kein Go-Code
> (`internal/`, `api/`) und kein Frontend-Code (`frontend/src/`) wird geändert. `Trip.paused_at`
> spiegelt lediglich das bereits existierende Go-Feld `internal/model/trip.go:104` auf der
> Python-Leseseite — kein Schreibzugriff von Python auf das Go-Modell.

## Estimated Scope

- **LoC:** ~180-230 (Produktionscode ~50-80: Punkt 1 ~25-40, Punkt 2 ~15-25, Punkt 3 ~10-15;
  Tests zusätzlich ~100-150 über alle drei Punkte). **Risiko:** LoC-Limit 250 kann knapp
  werden — ggf. `workflow.py set-field loc_limit_override <N>` mit expliziter User-Freigabe
  nötig, falls die Summe das Limit überschreitet.
- **Files:** 8-10 (6 Produktionsdateien, 2 neue Testdateien, 1 erweiterte Testdatei)
- **Effort:** medium (Punkt 1 hat breiten Blast-Radius über 4 SSoT-Aufrufer; Punkt 3 berührt
  Versand-Gate-Logik; Punkt 2 ist isoliert und risikoarm)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `convert_trip_to_segments()` (`trip_segments.py`) | function | SSoT für Segment-Zeitpriorität — 4 Aufrufer (`trip_report_scheduler.py`, `preview_service.py`, `trip_command_processor.py`, `trip_alert.py`) müssen konsistent denselben (korrigierten) Wert sehen |
| `Waypoint.arrival_override.origin` (Issue #303) | pattern | Vorbild für das neue Herkunfts-Flag an `time_window` — unterscheidet "manuell gesetzt" von "algorithmisch/importiert" |
| `_otd()` (`html.py:1106-1117`) | function | Bereits bewährtes Inline-Style-Muster (Background+Padding direkt auf `<td>`), auf das Punkt 2 umgestellt wird |
| `Trip.archived_at` (Issue #805) | pattern | Vorbild für den Go↔Python-Feld-Roundtrip von `paused_at`: Dataclass-Feld → `loader.py` Lesen → `loader.py` Schreiben |
| `internal/model/trip.go:104` (`PausedAt`) | Go-Feld | Quelle der Wahrheit für den Trip-Detail-Pause-Button (Go schreibt, Python liest nur mit) |
| `_get_active_trips()` (`trip_report_scheduler.py`) | function | Einziger Ort, an dem der neue Pause-Filter sitzen darf — NICHT `load_all_trips()` (sonst würden Alerts mit unterdrückt) |
| `briefing_mail_validator.py` | tool | Projekt-Pflicht-Validator vor "E2E bestanden" für Trip-Briefing-Mails; finale Bestätigung von Gruppe B |
| `data_schema_backup.py` | hook | Pre-Snapshot-Hook, wird durch die Änderung an `src/app/trip.py` automatisch ausgelöst (Schema-relevante Datei) |
| `docs/specs/modules/epic_135_step2_trip_detail_actions.md:359` | spec | Dokumentiert die von Gruppe C geschlossene, bewusst zurückgestellte Lücke (Issue #153) |

## Implementation Details

### Gruppe A — Segment-Startzeitpunkt

**Problem:** In `convert_trip_to_segments()` (`trip_segments.py:86-91`) hat `wp1.time_window`
unbedingten Vorrang vor `stage.start_time` — auch wenn `time_window` nur ein Artefakt des
GPX-Imports ist (`gpx_processing.py:135-138`, `segments_to_trip()` setzt es für JEDEN
Wegpunkt fest, ohne Herkunft zu markieren). Ändert der User später `stage.start_time`, bleibt
die alte Import-Zeit sichtbar. Kein reiner Prioritäts-Swap (siehe Analyse: dritter Patch an
derselben Kette in 5 Monaten, `time_window` war bisher immer bewusst oben — ein Swap würde
bewusst gesetzte `time_window`-Werte kaputt machen).

**Ansatz:** Neues optionales Feld an `Waypoint` (analog `arrival_override`/`origin` aus
Issue #303), z.B. `time_window_origin: Optional[str] = None` mit Werten `"imported"` /
`"manual"`. `segments_to_trip()` setzt beim GPX-Import `time_window_origin="imported"` für
jeden erzeugten Wegpunkt. Die Prioritätskette in `convert_trip_to_segments()` wird für ALLE
Wegpunkte (nicht nur `i==0`) angepasst — minimal-invasiv, indem ein als `"imported"` markiertes
`time_window` in der Kette wie `None` behandelt wird (fällt durch auf die bereits seit #783
korrekt geordneten Folgeglieder, statt eine neue Sonderregel einzuführen):

```
wp_tw = wp.time_window if wp.time_window_origin != "imported" else None

if wp_tw is not None:
    start = wp_tw.start                   # bewusst gesetzt — weiterhin Vorrang
elif wp_override is not None:
    start = wp_override                   # expliziter User-Override
elif i == 0 and stage.start_time:
    start = stage.start_time              # neu: schlägt importierte time_window am Etappenanfang
elif wp_calculated is not None:
    start = wp_calculated                 # Naismith-Kaskade, auch für importierte time_window bei i>0
elif i == 0:
    start = default_start
else:
    start = cumulative_time               # Fallback wie bisher (Zeile 100)
```

Für `i>0` mit importiertem `time_window` fällt die Zeit also auf `arrival_calculated` (Naismith,
kaskadiert von der neuen `stage.start_time` aus) zurück, statt eine eigene Stage-Ebenen-Regel zu
brauchen — dieselbe Neuberechnung, die schon bei nicht-importierten Wegpunkten läuft.

Alle 4 SSoT-Aufrufer (`trip_report_scheduler.py`, `preview_service.py`,
`trip_command_processor.py`, `trip_alert.py`) rufen dieselbe Funktion auf — kein Aufrufer-
seitiger Code nötig, aber TDD-RED muss alle vier End-to-End abdecken.

### Gruppe B — Zellhintergrund

**Problem:** `_render_html_table()` (`html.py:586-590`) wickelt getönte Zellen in einen
inneren `<span style="display:block;background:{cell_bg};margin:-6px -6px;padding:6px 6px;">`,
der das Zell-Padding aus dem globalen `<style>`-Block kompensieren soll. In Mail-Clients, die
den `<style>`-Block strippen oder die negativen Margins anders auflösen (Outlook, teils Apple
Mail), füllt der Span die Zelle nicht vollflächig.

**Ansatz:** Hintergrund und Padding direkt inline auf das `<td>` selbst legen — exakt das
bereits vorhandene `_otd()`-Muster (`html.py:1106-1117`), das an anderer Stelle in derselben
Datei für dasselbe visuelle Problem verwendet wird:

```
if cell_bg:
    tds += f'<td style="{_td_grid}background:{cell_bg};padding:6px;" data-label="{label}">{cell}</td>'
else:
    tds += f'<td style="{_td_grid}" data-label="{label}">{cell}</td>'
```

Der `<span>`-Wrapper mit Negativ-Margin entfällt für getönte Zellen vollständig.

### Gruppe C — Pausierte Trips

**Problem:** `_get_active_trips()` (`trip_report_scheduler.py:262-303`) prüft `rc.enabled`
und `rc.paused_until` (Report-Config-Snooze), aber nicht `trip.paused_at` (Trip-Detail-Pause-
Button, gesetzt via Go-Handler `PATCH /trips/{id}/state`). Python liest `Trip` bislang ohne
`paused_at`-Feld — `loader.py:load_trip()` verwirft es beim Parsen stillschweigend (keine
`data.get("paused_at")`-Zeile vorhanden).

**Ansatz — #805-Muster (Go↔Python-Feld-Roundtrip):**
1. `src/app/trip.py`: `paused_at: Optional[str] = None` an `Trip` ergänzen (analog `archived_at`)
2. `src/app/loader.py` `load_trip()`: `paused_at=data.get("paused_at")` beim Konstruieren von `Trip`
3. `src/app/loader.py` Schreib-Pfad (~Zeile 1044-1062): `if trip.paused_at: data["paused_at"] = trip.paused_at` — Read-Modify-Write, kein Replace
4. `src/services/trip_report_scheduler.py::_get_active_trips()`: zusätzliche Sperre `if trip.paused_at is not None: continue` — ausschließlich hier, NICHT in `load_all_trips()` (das würde `trip_alert.py`, das `load_all_trips()` direkt aufruft, unbeabsichtigt mit unterdrücken)

`send_test_report()` (`trip_report_scheduler.py:380-402`) ruft `_send_trip_report()` direkt
auf und umgeht `_get_active_trips()` komplett — bleibt vom Fix unberührt (by design, manueller
Test-Versand soll immer funktionieren).

## Expected Behavior

- **Input:** (A) Trip mit GPX-importierten Wegpunkten + geänderter `stage.start_time`; (B) HTML-
  E-Mail mit einer Zelle, deren Wert einen Warn-Schwellwert überschreitet; (C) Trip mit
  `paused_at` gesetzt über den Trip-Detail-Pause-Button
- **Output:** (A) Segmenttabelle zeigt die aktuelle Startzeit; (B) getönte Zelle füllt die
  gesamte `<td>`-Fläche in allen getesteten Mail-Clients; (C) automatischer Scheduler-Lauf
  überspringt den Trip, manueller Test-Versand und Alert-Dispatch bleiben unberührt
- **Side effects:** Änderung an `src/app/trip.py` löst den Pre-Snapshot-Hook
  `data_schema_backup.py` aus (`.backups/`-Snapshot vor dem Edit)

## Acceptance Criteria

### Gruppe A — Startzeitpunkt

- **AC-1:** Given ein Trip mit GPX-importierten Wegpunkten (Herkunfts-Flag "imported") und einer danach geänderten `stage.start_time` / When die Segmenttabelle über den Trip-Detail-Endpoint (`preview_service.py`) gerendert wird / Then zeigt Segment 1 (und alle nachfolgenden Segmente mit importiertem `time_window`) die NEUE Startzeit, nicht die alte Import-Zeit
  - Test: Echter Trip via GPX-Import anlegen, danach `stage.start_time` per API ändern, dann die Stundentabelle real abrufen und den tatsächlich gerenderten Zeit-String prüfen — kein Dateiinhalt-Check

- **AC-2:** Given ein Wegpunkt mit bewusst manuell gesetztem `time_window` (`time_window_origin="manual"` bzw. nicht "imported") / When `convert_trip_to_segments()` für denselben Trip läuft / Then bleibt das manuell gesetzte `time_window` weiterhin maßgeblich — kein Regressionsverhalten für bewusst gesetzte Zeiten
  - Test: Integrationstest mit zwei Wegpunkten derselben Etappe (einer `origin="manual"`, einer `origin="imported"`) im selben Aufruf — nur der importierte wird durch `stage.start_time` überschrieben, der manuelle bleibt unverändert

- **AC-3:** Given derselbe korrigierte Trip / When alle 4 SSoT-Aufrufer (`trip_report_scheduler.py`, `preview_service.py`, `trip_command_processor.py`, `trip_alert.py`) unabhängig voneinander die Segmentzeiten abfragen / Then liefern alle vier denselben, aktuellen Startzeitpunkt — keiner zeigt noch die alte Importzeit
  - Test: 4 echte Aufrufe der jeweils öffentlichen Funktion/Endpoints gegen denselben Trip-Zustand, Vergleich der zurückgegebenen Zeitwerte auf Übereinstimmung

### Gruppe B — Zellhintergrund

- **AC-4:** Given eine gerenderte HTML-E-Mail mit einer getönten Zelle (z.B. Gust über Schwelle) / When die Zelle im Playwright/Chromium-Headless-Browser vermessen wird / Then deckt die Bounding-Box des Hintergrund-tragenden Elements (jetzt direkt `<td>`, kein `<span>` mehr) die volle `<td>`-Fläche ab (Breiten-/Höhen-Differenz < 1px) — Geometrie-Vergleich, nicht nur Farbwert
  - Test: Playwright `getBoundingClientRect()`-Vergleich `td` vs. (ehemals) inneres `span`, als Erweiterung von `tests/tdd/test_fix_911_visual_table.py`

- **AC-5:** Given dieselbe getönte Zelle nach dem Fix / When das generierte HTML einer Datenzeile inspiziert wird / Then existiert kein `<span style="...margin:-6px...">`-Wrapper mehr innerhalb der Datenzellen — Hintergrund und Padding sitzen direkt inline auf `<td>`
  - Test: Playwright zählt `span[style*="margin:-6"]`-Elemente innerhalb der `tbody`-Zellen im tatsächlich gerenderten DOM — muss 0 sein

- **AC-6:** Given der Fix ist implementiert / When eine echte Test-Mail mit einer getönten Zelle über `briefing_mail_validator.py` gegen das Staging-Testpostfach (`gregor-test@henemm.com`) verschickt und geprüft wird / Then meldet der Validator Exit 0 als finale Bestätigung für reale Mail-Client-Zustellung (nicht nur Chromium-Simulation)
  - Test: Echter Versand über Resend an `gregor-test@henemm.com`, Abruf via IMAP, `briefing_mail_validator.py`-Lauf — kein Mock, kein Gmail. **Bekannte Einschränkung:** siehe Known Limitations zu Issue #997

### Gruppe C — Pausierte Trips

- **AC-7:** Given ein Trip mit `paused_at` gesetzt (via `PATCH /trips/{id}/state`) / When der automatische Scheduler-Lauf `_get_active_trips()` für "morning" oder "evening" aufruft / Then ist dieser Trip NICHT in der zurückgegebenen aktiven Liste — kein automatischer Versand erfolgt
  - Test: Echter Aufruf von `_get_active_trips()` mit zwei verschiedenen Test-Usern, je einem pausierten und einem aktiven Trip pro User — Assert auf die tatsächlich zurückgegebene Trip-Liste, keine Mocks

- **AC-8:** Given derselbe pausierte Trip / When der User manuell den Test-Versand auslöst (`send_test_report()`) / Then wird die Test-Mail trotzdem verschickt — der manuelle Versand bleibt vom Pause-Filter unberührt
  - Test: Echter Aufruf von `send_test_report()` gegen den pausierten Trip, Ankunft der Mail im Test-Postfach via IMAP verifiziert

- **AC-9:** Given derselbe pausierte Trip mit einer aktiven Alert-Regel, deren Bedingung erfüllt ist / When der Alert-Dispatch (`trip_alert.py`, nutzt `load_all_trips()` direkt) läuft / Then wird der Alert trotzdem ausgelöst — der Pause-Filter sitzt ausschließlich in `_get_active_trips()`, nicht in `load_all_trips()`
  - Test: Echter Alert-Dispatch-Lauf gegen den pausierten Trip mit erfüllter Trigger-Bedingung, Assert auf tatsächlich verschickten/geloggten Alert

- **AC-10:** Given ein bestehender Trip mit mehreren weiteren Feldern (z.B. 3 `alert_rules`, gesetzter `report_config`) und einem PATCH, das nur `paused_at` verändert / When der Trip anschließend über `load_trip()`/`save_trip()` neu geladen wird (Read-Modify-Write) / Then bleiben alle anderen Felder byte-gleich erhalten — kein Datenverlust, verifiziert mit zwei verschiedenen Test-Usern (Mandantentrennung)
  - Test: Echten Trip mit mehreren Feldern anlegen, `paused_at` per Roundtrip setzen, danach laden und alle ursprünglichen Feldwerte (inkl. `alert_rules`, `report_config`) auf Unverändertheit prüfen — für zwei unterschiedliche `user_id`

## Known Limitations

- **Gruppe A — keine rückwirkende Migration:** Bereits vor diesem Fix per GPX importierte und
  gespeicherte Wegpunkte haben kein `time_window_origin`-Flag (Feld ist `None`). Um bestehende,
  bewusst gesetzte `time_window`-Werte nicht zu gefährden, wird `None` konservativ wie `"manual"`
  behandelt — solche Alt-Trips zeigen das alte (fehlerhafte) Verhalten weiter, bis sie neu
  importiert oder das Feld nachträglich migriert wird. Kein Daten-Migrations-Skript in diesem
  Scope.
- **Gruppe B — Mail-Client aus Screenshot nicht verifizierbar:** Der konkrete Mail-Client aus
  dem #995-Screenshot ist nicht mit Sicherheit feststellbar; der Fix wird nach bestem Wissen
  (robusteres, bereits bewährtes `_otd()`-Inline-Pattern) umgesetzt. Endgültige Bestätigung nur
  über echten Testversand (AC-6).
- **Gruppe B — Renderer-Commit-Gate-Kollision mit offenem Issue #997:** `html.py` fällt unter
  den Renderer-Commit-Gate (#811). Issue #997 ist aktuell OFFEN und macht diesen Gate für
  Full-Format-Mails mit Trend-Zeile strukturell rot (False-Positive der Plausibilitätsregel,
  unabhängig von dieser Änderung). Der Commit für Gruppe B kann dadurch bei der Implementierung
  ggf. zurückgestellt werden müssen, bis #997 unabhängig gefixt ist — #997 wird NICHT im Rahmen
  dieses Workflows selbst behoben.
- **Gruppe C — keine Regression zu Issue #153:** Dies schließt eine in
  `docs/specs/modules/epic_135_step2_trip_detail_actions.md:359` bereits dokumentierte, bewusst
  zurückgestellte Lücke ("Scheduler ignoriert pausierten Status... bewusst out of scope für
  Issue #153"). Kein Verhalten wird rückgängig gemacht, nur die dort angekündigte Folge-Arbeit
  nachgeholt.
- **Gruppe C — Idempotenz auf Timestamp-Ebene:** Wie bei `archived_at`/#153 bereits dokumentiert,
  überschreibt ein wiederholtes Pause-Setzen `paused_at` mit einem neuen Timestamp. Das ist
  bestehendes, dokumentiertes Go-Verhalten (unverändert) und kein Teil dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine der drei Änderungen fällt unter die ADR-Guard-Kategorien aus
  `docs/adr/README.md` (Kanal-/Provider-/Quellenwahl, Metrik-Sichtbarkeit, Gate-/Guard-Hook-
  Entscheidung). Gruppe C fügt zwar ein neues Datenschema-Feld hinzu (`Trip.paused_at`), folgt
  dabei aber exakt dem bereits etablierten, nicht-ADR-pflichtigen `archived_at`-Muster aus
  Issue #805 — keine neue Persistenz-Grundsatzentscheidung, sondern Anwendung eines bestehenden
  Musters. Sollte `adr_guard.py` beim Commit dennoch anschlagen (z.B. weil `trip.py` als
  Datenschema-Datei erkannt wird), ist `[no-adr]` in der Commit-Message zulässig, mit Verweis
  auf diese Spec-Sektion als Begründung.

## Test Coverage

- `tests/tdd/test_issue_995_segment_start_time.py` (NEU) — AC-1, AC-2, AC-3: geänderte
  Etappen-Startzeit vs. GPX-Import-Zeit, Herkunfts-Flag-Regression, Konsistenz über alle 4
  SSoT-Aufrufer
- `tests/tdd/test_fix_911_visual_table.py` (ERWEITERT) — AC-4, AC-5: Geometrie-Bounding-Box-
  Vergleich `td` vs. `span`, Abwesenheit des Negativ-Margin-Wrappers
- Manueller/skriptgestützter Lauf `briefing_mail_validator.py` gegen Staging-Testpostfach —
  AC-6 (kein Python-Testfile, sondern Projekt-Pflicht-Validator-Lauf als Nachweis)
- `tests/tdd/test_issue_995_scheduler_pause.py` (NEU) — AC-7, AC-8, AC-9, AC-10: Scheduler-
  Filter, manueller Versand unberührt, Alert-Dispatch unberührt, Read-Modify-Write mit zwei
  Test-Usern

## Changelog

- 2026-07-03: Initial spec erstellt — Issue #995, Bug-Bündel aus 3 Punkten (Segment-
  Startzeitpunkt, Zellhintergrund, Pausierte Trips), aufbauend auf
  `docs/context/fix-995-mail-bugs-bundle.md`
