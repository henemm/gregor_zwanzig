---
entity_id: bug_1146_badge_window_mismatch
type: bugfix
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [bugfix, email-renderer, badge, segment-window, issue-1146]
---

<!-- Issue #1146 — Metriken-Überblick-Badge zeigt "kein Regen" trotz Regen in der Ankunftsstunde der Stundentabelle -->

# Issue #1146 — Bug-Fix: Metriken-Badge deckt Ankunftsstunde des letzten Segments ab

## Approval

- [ ] Approved

## Zweck

Das Metriken-Überblick-Badge in Briefing-Mails (E-Mail/Plain/Compact-Pfad) aggregiert Wetterdaten über alle Segmente eines Reports mit einem exklusiven Fenster-Ende (`s_h <= h < e_h`). Für das **letzte** Segment eines Reports fällt dadurch die Ankunftsstunde komplett aus der Aggregation heraus, obwohl die direkt darunter gerenderte Stundentabelle diese Stunde (inklusiv) korrekt anzeigt. Ergebnis: Das Badge kann "kein Regen" behaupten, während die Tabelle reale Regenwerte in der Ankunftsstunde zeigt — ein Widerspruch, der bereits vom `briefing_mail_validator.py` (AC-4) gegen echte Staging-Mails als FULL-Plausibilitätsfehler gemeldet wird.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `build_metrics_summary_pills` (Zeilen 1281–1322, betroffene Filterlogik 1298–1311)

> **Schicht-Hinweis:** Python-Core/Domain-Backend (`src/output/renderers/...`). Kein Frontend-, kein Go-API-Code betroffen. `src/output/renderers/email/{html,plain,compact}.py` rufen dieselbe Funktion mit denselben `segments` wie die Stundentabelle auf — keine weitere Anpassung an den Call-Sites nötig.

## Estimated Scope

- **LoC:** ~10–15 (Kernfix in `helpers.py`) + ~40–60 (neue Testdatei)
- **Files:** 1 Quelldatei (`helpers.py`) + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/trip_report.py::_extract_hourly_rows` (Zeilen 257–274) | Referenzverhalten | Baut die Stundentabelle pro Segment mit **inklusivem** Ende — Ziel-Konvention für die Ankunftsstunde des letzten Segments |
| `src/app/models.py::TripSegment` (Zeile 323) | Datenmodell | "typically ~2 hours" — ein Tag/eine Etappe besteht i.d.R. aus mehreren aufeinanderfolgenden Segmenten |
| `.claude/hooks/briefing_mail_validator.py::_check_metric_plausibility` (Zeilen 267–291) | Bestehender Validator | AC-4: meldet den "kein Regen"-Widerspruch bereits gegen echte Staging-Mails; nach dem Fix darf dieser Fehlerfall nicht mehr auftreten |
| `tests/tdd/test_issue_807_reproduction.py::test_pills_respect_segment_window` | Bestehender Test | Regressionsschutz — Peak liegt weit außerhalb des Fensters (nicht an der Grenzstunde), muss weiterhin ausgeschlossen bleiben |
| `src/output/renderers/email/{html,plain,compact}.py` | Aufrufer | Rufen `build_metrics_summary_pills(segments, ...)` mit denselben `segments` wie die Tabelle auf — unverändert |

## Implementation Details

In `build_metrics_summary_pills` (`helpers.py:1298–1311`) beim Aufbau von `all_dps`: nur für das **letzte** Segment in der übergebenen `segments`-Liste das Fenster-Ende inklusiv behandeln, alle vorherigen Segmente bleiben exklusiv wie bisher.

```python
# Vorher (alle Segmente exklusiv):
all_dps = []
for seg_data in segments:
    ts = getattr(seg_data, "timeseries", None)
    if ts is not None:
        s = seg_data.segment
        s_h = s.start_time.hour
        e_h = s.end_time.hour
        for dp in ts.data:
            h = dp.ts.hour
            include = (s_h <= h < e_h) if s_h <= e_h else (h >= s_h or h < e_h)
            if include:
                all_dps.append(dp)

# Nachher (letztes Segment inklusiv):
all_dps = []
last_idx = len(segments) - 1
for idx, seg_data in enumerate(segments):
    ts = getattr(seg_data, "timeseries", None)
    if ts is not None:
        s = seg_data.segment
        s_h = s.start_time.hour
        e_h = s.end_time.hour
        is_last = idx == last_idx
        for dp in ts.data:
            h = dp.ts.hour
            if s_h <= e_h:
                include = (s_h <= h <= e_h) if is_last else (s_h <= h < e_h)
            else:
                include = (h >= s_h or h <= e_h) if is_last else (h >= s_h or h < e_h)
            if include:
                all_dps.append(dp)
```

Der Mitternachts-Übergangsfall (`s_h > e_h`, z.B. 23…01) wird analog behandelt: für das letzte Segment wird auch dort das Ende inklusiv (`h <= e_h` statt `h < e_h`).

**Keine Änderung** an `trip_report.py::_extract_hourly_rows` (Tabelle bleibt Referenzverhalten), an `narrow.py::_overview_line` (Telegram, bereits korrekt) und an `compact_summary.py::_collect_hourly_data` (separate Funktion, siehe Known Limitations).

## Expected Behavior

- **Input:** `segments: list[SegmentWeatherData]` — dieselbe Liste, die auch für die Stundentabelle verwendet wird
- **Output:** `all_dps` enthält jetzt zusätzlich den Datenpunkt der Ankunftsstunde des letzten Segments (sofern in der Timeseries vorhanden); alle Grenzstunden zwischen zwei nicht-letzten, aufeinanderfolgenden Segmenten bleiben weiterhin exakt einmal gezählt
- **Side effects:** Keine — reine Aggregationsänderung innerhalb einer bestehenden Funktion; keine neuen Parameter, keine API-Änderung

## Acceptance Criteria

- **AC-1:** Given ein Report, dessen letztes Segment in seiner Ankunftsstunde Regen in der Timeseries hat / When `build_metrics_summary_pills` für diesen Report aufgerufen wird / Then muss das Regen-Pill diesen Regen ausweisen und darf nicht "kein Regen" zeigen, obwohl die Stundentabelle für diese Stunde Regen zeigt
  - Test: `test_last_segment_arrival_hour_included` — neuer Test in `tests/tdd/test_issue_1146_badge_window_mismatch.py`, reproduziert exakt den gemeldeten Fall (Regen exakt in der Ankunftsstunde des letzten Segments)

- **AC-2:** Given mehrere aufeinanderfolgende, NICHT-letzte Segmente eines Tages, bei denen Segment 1 endet wo Segment 2 beginnt (gemeinsame Grenzstunde) und dort ein Peak-Wert liegt / When `build_metrics_summary_pills` mit beiden Segmenten aufgerufen wird / Then darf dieser Peak nur einmal in die Aggregation einfließen, nicht doppelt (Regressionsschutz für #806/#807)
  - Test: `test_shared_boundary_hour_not_double_counted` — neuer Test in `tests/tdd/test_issue_1146_badge_window_mismatch.py`

- **AC-3:** Given der bestehende Test `test_issue_807_reproduction.py::test_pills_respect_segment_window` (Peak liegt weit außerhalb des Segment-Fensters) / When die Testsuite nach dem Fix läuft / Then bleibt dieser Test grün (keine Regression)
  - Test: bestehender Test `tests/tdd/test_issue_807_reproduction.py::test_pills_respect_segment_window` unverändert grün

- **AC-4:** Given eine echte, über Staging zugestellte Briefing-Mail mit Regen in der Ankunftsstunde des letzten Segments / When `briefing_mail_validator.py::_check_metric_plausibility` (AC-4) gegen diese Mail läuft / Then meldet der Validator keinen "'kein Regen' widerspricht Tabellen-Summe"-Fehler mehr für diesen Fall
  - Test: `briefing_mail_validator.py`-Lauf gegen Staging-Testmail (Trip 074a5d84 / vergleichbarer Nachfolge-Trip, User validator-issue110) im Rahmen der E2E-Verifikation nach Deploy — kein neuer Unit-Test, da Validator bereits existiert

## Known Limitations

- Betrifft ausschließlich den E-Mail/Plain/Compact-Pfad (`build_metrics_summary_pills` in `helpers.py`). Telegram (`narrow.py::_overview_line`) berechnet seine Kurzübersicht bereits direkt aus den fertigen Tabellenzeilen (`seg_tables`) und ist von diesem Bug nicht betroffen — wird nicht verändert.
- **Nebenbefund (nicht Teil dieses Fixes):** `src/output/renderers/compact_summary.py::_collect_hourly_data` (Zeilen 103–119) enthält eine strukturell identische Kopie derselben exklusiven Fenster-Logik (`s_h <= h < e_h`) mit demselben potenziellen Ankunftsstunden-Lücken-Effekt für die Natursprache-Zusammenfassung (`CompactSummaryFormatter.format_stage_summary`, aufgerufen von `trip_report.py:815-826`). Dieser Pfad ist im aktuellen Ticket-Scope explizit nicht enthalten (Team-Lead-Vorgabe: nur `helpers.py`, ~10–15 LoC) und wird hier nur als Beobachtung dokumentiert — Entscheidung über einen eigenen Issue/Sammel-Eintrag liegt beim Product Owner.

## Out of Scope

- Änderung an `trip_report.py::_extract_hourly_rows` (Tabellen-Fenster bleibt inklusiv, unverändert — Option 2 aus der Issue explizit verworfen)
- Änderung am Validator `briefing_mail_validator.py` (Option 3 aus der Issue explizit verworfen — würde den echten Fehler nur verstecken)
- Fix der strukturell identischen Fenster-Logik in `compact_summary.py::_collect_hourly_data` (siehe Known Limitations)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix innerhalb einer bestehenden Funktion. Die grundsätzliche Boundary-Konvention ("inclusive start, exclusive end" aus #806/#807) bleibt unverändert bestehen — es wird lediglich ein Spezialfall (letztes Segment eines Reports) ergänzt, kein neuer Architektur-Entscheid.

## Changelog

- 2026-07-10: Initial spec erstellt. Fix für Issue #1146 — Ankunftsstunde des letzten Segments wird jetzt inklusiv in die Badge-Aggregation aufgenommen, ohne die #806/#807-Anti-Doppelzählung für vorherige Segmente zu brechen.
