---
entity_id: fix_2221_dpc_gueltigkeit
type: bugfix
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: fix-2221-dpc-gueltigkeit
tags: [dpc, official-alerts, gueltigkeit, italien]
---

# DPC-Warnungen erhalten Gültigkeitsfenster (Issue #2221)

## Approval

- [ ] Approved

## Purpose

Warnungen der italienischen Zivilschutz-Quelle (`DpcSource`) tragen bisher kein `valid_from`/`valid_to`. Dadurch fehlt die „Gültig:"-Zeile, das Melde-Gedächtnis kann Warnungen verschiedener Bezugstage nicht trennen und der Fensterfilter behält DPC-Warnungen immer. Die Spec gibt jeder DPC-Warnung das amtliche Fenster des Bezugstags (ganzer Kalendertag Europe/Rome).

## Source

- **File:** `src/services/official_alerts/dpc.py`
- **Identifier:** `_select_day_records`, `_alerts_for_zone`, `DpcSource.fetch`

> Schicht: Python-Core (`src/services/`). Keine Go-/Frontend-Änderung.
> Trip/Ortsvergleich-Teilung: nicht betroffen, die Quelle wird von beiden Pfaden über dieselbe Registry genutzt (`trip_alert.py`, `compare_official_alert.py`), es entsteht keine neue Komponente.
> Mandantentrennung: keine Nutzerdaten bewegt, DPC-Abruf ist national und nutzerunabhängig.
> Kanäle: E-Mail, Telegram, SMS und Premium-SMS erhalten denselben Inhalt (Fenster in der Warnung); die kanalgerechte Darstellung bleibt unverändert in den Renderern (siehe Implementation Details).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/dpc.py` | MODIFY | Bezugstag als Kalendertag Europe/Rome; `_alerts_for_zone` setzt `valid_from`/`valid_to` (Bezugstag 00:00:00–23:59:59 Europe/Rome, gespeichert als aware UTC) |
| `tests/tdd/test_dpc_gueltigkeit.py` | CREATE | Kern-Tests AC-1 bis AC-7 mit echten Bulletin-Fixtures, Uhr über `_NOW_FN` |

Nicht im Scope: Renderer-Änderungen (Ganztags-Darstellung bleibt Hausregel), Auswertung von `Cap_<ts>.xml`, Folgetags-Warnungen.

## Estimated Scope

- **LoC:** ~20 Quellcode, ~80 Tests
- **Files:** 2 (1 Quelle, 1 Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.models.OfficialAlert` | module | Felder `valid_from`/`valid_to` (Optional, aware UTC, Hausnorm #1345) |
| `services.official_alerts.base.filter_alerts_to_window` | function | gleicht Warnungen mit Fenster gegen Briefing-/Etappenfenster ab |
| `output.renderers.alert.official_alerts` (`_warn_hour`, `_format_validity`, `official_alert_state_key`) | module | Darstellung und Melde-Gedächtnis-Schlüssel, bleiben unverändert |
| `zoneinfo.ZoneInfo("Europe/Rome")` | stdlib | italienischer Kalendertag |
| `docs/specs/modules/feat_1427_dpc_warn_fallback.md` | spec | DPC-Quelle, Bezugstag (AC-3) |
| `docs/specs/modules/fix_1657_warnfenster_identitaet.md` | spec | Fenster als Teil der Warn-Identität |
| `tests/fixtures/dpc/ruhetag_20260730_1511.zip`, `unwettertag_20260118_1515.zip` | fixture | echte Bulletins |

## Implementation Details

Root Cause: `_alerts_for_zone` baut `OfficialAlert(...)` ohne Fenster; der Bezugstag ist in `fetch()` bekannt, wird aber nicht weitergereicht. Nebenursache: `_select_day_records` vergleicht `_NOW_FN().date()` im UTC-Datum statt im italienischen Kalendertag, so gilt zwischen 00:00 und 01:00/02:00 Ortszeit noch der Vortag.

Beleg für das Fenster: `Cap_<ts>.xml` im Bulletin (Fixture `ruhetag_20260730_1511.zip`) trägt für den Bezugstag `onset 2026-07-31T00:00:00+02:00` und `expires 2026-07-31T23:59:59+02:00`, amtlich also der ganze Bezugstag in Ortszeit Europe/Rome.

Ansatz:

1. `_select_day_records` bestimmt den heutigen Tag als `_NOW_FN().astimezone(ZoneInfo("Europe/Rome")).date()` und liefert zusätzlich den Bezugstag: Ausgabetag bei `today`-Datensatz, Ausgabetag + 1 bei `tomorrow`-Datensatz (der Bezugstag ist in beiden Fällen der heutige Rome-Tag; ist das Bulletin älter, bleibt das Ergebnis leer wie bisher).
2. `_alerts_for_zone(row, ref_day)` setzt `valid_from` = Bezugstag 00:00:00 Europe/Rome und `valid_to` = Bezugstag 23:59:59 Europe/Rome, beide per `.astimezone(timezone.utc)` als tz-aware UTC gespeichert (Hausnorm #1345).
3. `DpcSource.fetch` reicht `ref_day` durch.

Keine Renderer-Änderung. Ein Fenster 00:00–23:59 Ortszeit gilt hausweit für alle Quellen als ganztägig: Mail/Telegram zeigen „<Datum> · ganztägig", der SMS-Eintrag hat keinen Stundenteil (`_warn_hour` liefert `None`). Das im Issue genannte „SMS-Zeit-Token" folgt damit ausdrücklich der Ganztags-Regel: die Ursache (kein Fenster) wird behoben, ein `@h` entsteht bewusst nicht. Premium-SMS folgt dem SMS-Eintrag.

Folgen:

- Melde-Gedächtnis: `official_alert_state_key` enthält künftig das Fenster statt `none|none`. Einmaliger Übergang: eine am Deploy-Tag schon gemeldete DPC-Warnung kann einmal erneut kommen (akzeptiert wie bei #1245).
- `filter_alerts_to_window` gleicht DPC-Warnungen jetzt mit dem Briefing-/Etappenfenster ab statt sie immer zu behalten (gewollt).

## Expected Behavior

- **Input:** DPC-Bulletin + Ort in einer DPC-Zone, Uhr `_NOW_FN`.
- **Output:** `OfficialAlert`s mit `valid_from`/`valid_to` = ganzer Rome-Kalendertag des Bezugstags (UTC-gespeichert); Stufen und Gefahrenzuordnung unverändert.
- **Side effects:** neuer Melde-Gedächtnis-Schlüssel (einmaliger Übergang), Fensterfilter greift für DPC.

## Test Plan

### Automated Tests (TDD RED)

Tests in `tests/tdd/test_dpc_bulletin_source.py` (oder neue `tests/tdd/test_dpc_gueltigkeit.py`), ohne Mocks/`patch`: echte Fixture-Zips über den lokalen Test-Server, Uhr per `monkeypatch` auf `_NOW_FN`.

- [ ] Test 1: GIVEN Fixture `unwettertag_20260118_1515` und Abruf am Ausgabetag WHEN `fetch` THEN Fenster = Ausgabetag 00:00–23:59:59 Europe/Rome in UTC.
- [ ] Test 2: GIVEN `ruhetag_20260730_1511` und Abruf 31.07. vormittags WHEN `fetch` THEN Fenster 31.07. 00:00–23:59:59 Rome.
- [ ] Test 3: GIVEN Abruf 30.07. 22:30 UTC (31.07. 00:30 Rome) WHEN `fetch` THEN `tomorrow`-Datensatz, Warnung Tren-A mit Fenster 31.07.
- [ ] Test 4: GIVEN eine DPC-Warnung mit Fenster WHEN Mail-/Telegram-Zeile und SMS-Eintrag gerendert THEN „<Datum> · ganztägig" bzw. kein Stundenteil.
- [ ] Test 5: GIVEN zwei DPC-Warnungen gleicher Zone und Gefahr an zwei Bezugstagen WHEN `official_alert_state_key` THEN verschiedene Schlüssel.
- [ ] Test 6: GIVEN DPC-Warnung vom Vortag WHEN `filter_alerts_to_window` mit Folgetag-Fenster THEN verworfen; mit Bezugstag-Fenster THEN behalten.
- [ ] Test 7: GIVEN bestehende Stufen-/Gefahren-Fixtures und veraltetes Bulletin THEN unveränderte Stufen, leere Liste.

## Acceptance Criteria

- **AC-1:** Given ein aktuelles DPC-Bulletin mit `today`-Datensatz / When am Ausgabetag die Warnungen für einen Ort in einer gewarnten Zone abgerufen werden / Then trägt jede Warnung das Fenster Ausgabetag 00:00:00 bis 23:59:59 Europe/Rome, als tz-aware UTC gespeichert.
  - Test: Abruf mit echter Fixture `unwettertag_20260118_1515` und gesetzter Uhr, Fenster der Warnung wird geprüft.

- **AC-2:** Given das echte Bulletin `ruhetag_20260730_1511` mit Warnung Tren-A Temporali GIALLA nur im `tomorrow`-Datensatz / When am 31.07. vormittags abgerufen wird / Then trägt die Warnung das Fenster 31.07. 00:00:00 bis 23:59:59 Europe/Rome.
  - Test: Abruf gegen die Fixture mit gesetzter Uhr 31.07. 08:00 Rome.

- **AC-3:** Given dasselbe Bulletin vom 30.07. / When am 30.07. um 22:30 UTC (31.07. 00:30 Rome) abgerufen wird / Then wird der `tomorrow`-Datensatz mit Bezugstag 31.07. gewählt, die Warnung Tren-A erscheint und ihr Fenster ist der 31.07.
  - Test: Mitternachtsgrenze, Uhr auf 22:30 UTC, Warnung vorhanden und Fenster 31.07. Rome.

- **AC-4:** Given eine DPC-Warnung mit ganztägigem Fenster / When die Mail-/Telegram-Gültig-Zeile und der SMS-Eintrag erzeugt werden / Then zeigt die Zeile das Datum des Bezugstags mit „ganztägig" und der SMS-Eintrag hat keinen Stundenteil (Hauskonvention für ganztägige Fenster, auch für das im Issue genannte SMS-Zeit-Token).
  - Test: Rendern einer echten DPC-Warnung aus der Fixture über die bestehenden Renderer-Funktionen, Textprüfung der Ausgabe.

- **AC-5:** Given zwei DPC-Warnungen gleicher Zone und gleicher Gefahr an zwei verschiedenen Bezugstagen / When `official_alert_state_key` gebildet wird / Then sind die beiden Melde-Gedächtnis-Schlüssel verschieden.
  - Test: Warnungen zu zwei gesetzten Uhrzeiten abrufen, Schlüssel vergleichen.

- **AC-6:** Given eine DPC-Warnung des Vortags mit Fenster / When `filter_alerts_to_window` mit einem Fenster am Folgetag aufgerufen wird / Then wird die Warnung verworfen, und mit einem Fenster am Bezugstag bleibt sie erhalten.
  - Test: Filteraufruf mit zwei Fenstern auf dieselbe echte DPC-Warnung.

- **AC-7:** Given die bestehenden DPC-Fixtures und ein veraltetes Bulletin / When abgerufen wird / Then bleiben Stufen- und Gefahrenzuordnung unverändert und ein veraltetes Bulletin liefert weiterhin eine leere Liste.
  - Test: bestehende Stufen-/Zuordnungs-Tests bleiben grün, plus Abruf mit Uhr zwei Tage nach Ausgabetag liefert leere Liste.

## Definition of Done

- AC-1 bis AC-7 durch Kern-Tests (pytest, ohne Mock-Theater, echte DPC-Fixtures) grün; zuvor rot nachgewiesen.
- Bestehende DPC-Tests (`tests/tdd/test_dpc_bulletin_source.py`, `tests/tdd/test_dpc_official_alert_bbox.py`) unverändert grün.
- Alle 6 CI-Checks grün, Staging-Verifikation bestanden, live auf Produktion mit Selftest Exit 0.

## Known Limitations

- Ganztägiges Fenster: SMS zeigt bewusst keine Stunde, das ist die hausweite Konvention.
- Einmaliger Doppelversand einer bereits gemeldeten DPC-Warnung am Deploy-Tag (Schlüsselwechsel `none|none` → Fenster).
- Das Fenster wird aus dem Bezugstag abgeleitet, nicht aus dem CAP-XML gelesen; die Laufzeit liest weiterhin nur die `.dbf`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Bugfix innerhalb einer Quelle, folgt der bestehenden Hausnorm (aware UTC, #1345) und Ganztags-Konvention; keine Entscheidungsfläche ändert sich.

## Changelog

- 2026-11-28: Initial spec created
