---
entity_id: fix_1355_regen_adjektiv
type: module
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [bugfix, compact_summary, briefing]
---

# Fix #1355: Regen-Adjektiv im "starts_later"-Zweig

## Approval

- [ ] Approved

## Purpose

Die Kurz-Zusammenfassungszeile im Briefing (`CompactSummaryFormatter._format_precipitation`) gibt bei spät einsetzendem Regen unbedingt `"trocken, Regen ab {HH}:00"` aus — auch wenn die Tagesregensumme erheblich ist (Beleg: 15,4 mm → "starker Regen"). Das bereits berechnete Adjektiv (`_precip_adjective`) wird in diesem Zweig verworfen. Für ein Briefing-Tool, das Tourenentscheidungen unter Zeitdruck stützt, ist "trocken" am Satzanfang bei starkem Regen eine irreführende Aussage.

## Source

- **File:** `src/output/renderers/compact_summary.py`
- **Identifier:** `CompactSummaryFormatter._format_precipitation` (Zeile 360-395), Zweig `kind == "starts_later"` (Zeile 388-389)

> **Schicht:** Python-Core / Domain-Backend (`src/output/renderers/`) — Renderer-Baustein, geteilt zwischen HTML-Mail, Plain-Mail und Trip-Report.

## Estimated Scope

- **LoC:** ~5-10
- **Files:** 3 (`compact_summary.py`, `docs/specs/modules/compact_summary.md`, eine Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/trip_report.py:800-810` | Aufrufer | Einziger Call-Site von `format_stage_summary` — Fix wirkt automatisch in allen Kanälen |
| `src/output/renderers/email/html.py` | Downstream | Nutzt trip_report-Renderer-Kern (HTML-Mail) |
| `src/output/renderers/email/plain.py` | Downstream | Nutzt trip_report-Renderer-Kern (Plain-Mail) |
| `CompactSummaryFormatter._precip_adjective` | Upstream (unverändert) | Liefert "leichter/mäßiger/starker Regen" aus der Tagesfenster-Summe |

## Implementation Details

Im `starts_later`-Zweig (Zeile 388-389) das bereits berechnete `adj` (Zeile 377) einfließen lassen, analog zum bestehenden `ends_early`-Zweig (`f"{adj} bis {end_h}:00, trocken ab {dry_h}:00"`):

```python
if kind == "starts_later":
    return f"trocken, {adj} ab {pattern['start_hour']}:00"
```

`adj` enthält bereits "Regen" als Substantiv ("starker Regen" / "mäßiger Regen" / "leichter Regen") — nur das Wort "Regen" wird durch `adj` ersetzt, der übrige Satzbau bleibt unverändert. Kein Eingriff in `_find_rain_pattern` (Musteranalyse) nötig.

Beispiel aus dem Issue: 15,4 mm Tagesregen ab 15:00 → bisher `"trocken, Regen ab 15:00"` → neu `"trocken, starker Regen ab 15:00"`.

**Doku-Pflicht (kein separates Modul, Teil dieses Fixes):** `docs/specs/modules/compact_summary.md` dokumentiert aktuell den Bug als Soll-Zustand und muss mit-aktualisiert werden:
- Zeile 94 (Muster-Tabelle): `"Regen beginnt spaeter" → "trocken, Regen ab {HH}:00"` wird zu `"trocken, {adj} ab {HH}:00"`.
- Zeile 72/79 (Output-Beispiele): enthalten aktuell keinen `starts_later`-Fall — kein Zwang zur Änderung, aber bei Gelegenheit ein Beispiel ergänzen.
- Zeile 390-393 (AC-Abschnitt `test_rain_starts_later`): THEN-Zeile um die Adjektiv-Erwartung ergänzen (heute nur `"Regen ab 13:00"`).

**Renderer-Commit-Gate #811:** Änderung an `compact_summary.py` löst das Gate aus. Vor Commit: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Erfolgslog gegen eine echte Staging-Testmail (`gregor-test@henemm.com`).

## Expected Behavior

- **Input:** Tagesfenster-Stundenwerte mit isolierter trockener Phase gefolgt von durchgehendem Regen bis (nahe) Fensterende, Tagessumme deutlich über der "starker Regen"-Schwelle (>10mm).
- **Output:** Satz beginnt weiterhin mit "trocken" für die tatsächlich trockene Phase, nennt danach das korrekte Adjektiv statt des neutralen Worts "Regen".
- **Side effects:** keine — reine Textänderung, wirkt identisch in HTML-Mail, Plain-Mail, Trip-Report (geteilter Renderer-Kern).

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit isoliert-trockener Morgenphase und anschließendem Regen bis Fensterende mit Tagessumme >10mm (z.B. mehrere Stunden à 2-3mm) / When `format_stage_summary` gerufen wird / Then enthält die Ausgabe **nicht** `"trocken, Regen ab"`, sondern `"trocken, starker Regen ab {HH}:00"` mit der korrekten Startstunde.
  - Test: `test_rain_starts_later_keeps_adjective` (oder passender Name nach Namensregel) in `tests/integration/test_compact_summary.py`, ergänzend zum bestehenden `test_rain_starts_later` (nicht ersetzend). Prüft konkreten String-Inhalt der Zusammenfassungszeile, kein Dateiinhalt-Check.

- **AC-2:** Given den bestehenden Test `test_rain_starts_later` (Tagessumme 8mm, "mäßiger Regen") / When der Fix angewendet ist / Then bleibt der Test grün, da er nur `"13:00" in result or "13" in result` prüft, keine Bindung an den exakten "trocken"-Wortlaut hat.
  - Test: bestehender `tests/integration/test_compact_summary.py::test_rain_starts_later` läuft unverändert grün (Regressionsnachweis).

- **AC-3:** Given den Adversary-Test für den Fensterrand-Fall (`tests/tdd/test_sms_daywindow_aggregation.py:700`, prüft `"trocken, Regen ab 04:00" not in compact`) / When der Fix angewendet ist / Then bleibt der Test grün, da der neue Satz ohnehin nicht mehr "trocken, Regen ab" lautet.
  - Test: bestehender Test läuft unverändert grün (Regressionsnachweis).

- **AC-4:** Given der Fix ist implementiert / When `docs/specs/modules/compact_summary.md` geprüft wird / Then zeigt Zeile 94 der Muster-Tabelle den korrigierten Wortlaut `"trocken, {adj} ab {HH}:00"` statt des alten `"trocken, Regen ab {HH}:00"`.
  - Test: manuelle Prüfung im Rahmen der Implementierung (Doku-Pflicht, keine automatisierte Verhaltens-AC).

## Known Limitations

- Der Fix ändert nur den Textbaustein — keine Änderung an der Musteranalyse (`_find_rain_pattern`), an den Adjektiv-Schwellen oder an anderen Zweigen (`peak`, `throughout`, `window`, `ends_early`), die bereits korrekt `adj` nutzen.
- Keine Migration auf `metric_format.format_value` (siehe Kommentar am Klassenkopf von `compact_summary.py`) — bleibt narrativer Satzbau.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Bugfix an einem bestehenden Textbaustein, keine Architektur- oder Datenmodell-Entscheidung betroffen.

## Changelog

- 2026-08-04: Initial spec created (Issue #1355)
