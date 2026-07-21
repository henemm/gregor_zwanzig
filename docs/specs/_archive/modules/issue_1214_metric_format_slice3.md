---
entity_id: issue_1214_metric_format_slice3
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [metric-format, trip-briefing, konsolidierung, issue-1214]
---

# Metric-Format-Konsolidierung — Scheibe 3 (Trip-Briefing `fmt_val` Migration)

## Approval

- [ ] Approved

## Purpose

Issue #1214 Scheibe 3 migriert die 6 sicher migrierbaren Zweige (`wind`/`gust`/`precip`/`pop`/`cape`/`freeze_lvl`) der zentralen Trip-Briefing-Formatierungsfunktion `fmt_val` (`src/output/renderers/email/helpers.py`) auf das in Scheibe 1+2 gebaute Modul `src/output/metric_format.py`, sowie die HTML-Ampel-Levelquelle der 5 Ampel-fähigen Metriken auf `severity_for`. Dies existiert, um die in Scheibe 1+2 begonnene Konsolidierung der mehrfach duplizierten Metrik-Formatierungs-/Ampel-Logik auf den bislang größten und am häufigsten durchlaufenen Renderer-Pfad (JEDER Trip-Briefing-Versand: E-Mail HTML/Plain, Telegram) auszuweiten, ohne für Nutzer sichtbares Verhalten zu ändern.

## Source

- **File:** `src/output/metric_format.py` (`format_value`, neuer `style="bare"`-Zweig), `src/output/renderers/email/helpers.py` (`fmt_val`)
- **Identifier:** `format_value()`, `fmt_val()`

**Schicht:** Python-Core/Domain-Backend (`src/output/`) — kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** `metric_format.py` ~15-20 LoC (neuer Zweig + Tests), `helpers.py` ~30-50 LoC Diff (6 Zweige umgestellt), Testdatei-Ergänzungen ~30-50 LoC
- **Files:** 3 (siehe Scope-Tabelle)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/metric_format.py` (`format_value`, `severity_for`) | module | Scheibe 1+2 Konsolidierungs-Modul; `format_value` bekommt neuen additiven `style="bare"`, `severity_for` wird für die 5 Ampel-Metriken erstmals außerhalb von Compare genutzt |
| `src/app/metric_catalog.py` (`get_metric`, `display_thresholds`, `decimals`) | module | Single Source of Truth für Metrik-Metadaten, von `format_value`/`severity_for` gelesen |
| `src/output/renderers/email/helpers.py` (`fmt_val`, `_AMPEL_KEY_TO_METRIC_ID`, `ampel_dot`, `_ampel_dot_css`) | module | Ziel der Migration (6 Zweige) — `_level_from_thresholds`/`ampel_level`/`ampel_dot`/`_ampel_dot_css` bleiben UNVERÄNDERT bestehen, nur die Level-Quelle für 5 Zweige wechselt auf `severity_for` |
| `src/output/renderers/narrow.py`, `src/output/renderers/email/plain.py`, `src/output/renderers/email/html.py` | module | Drei asymmetrische `fmt_val`-Aufrufer (unterschiedliche Parameter-Teilmengen) — Signatur/Verhalten darf für keinen brechen |
| `src/output/renderers/trip_report.py` (`_fmt_val`) | module | Eigene, divergente Kopie — explizit NICHT Teil dieser Scheibe (Scheibe 4) |
| `.claude/hooks/renderer_mail_gate.py` | gate | Greift ECHT (nicht No-Op wie bei Compare) — blockiert Commit an `helpers.py` ohne frischen `test_issue_811_mode_matrix.py`-Lauf + `briefing_mail_validator.py`-Nachweis gegen eine echte, frisch versendete Trip-Briefing-Test-Mail (Implementierungsdetail, kein AC) |

## Implementation Details

**Neuer additiver Stil `style="bare"` in `format_value` (`metric_format.py`):** Liefert die reine, auf Katalog-`decimals` gerundete Zahl inkl. `display_unit`-Konvertierung (falls gesetzt), aber OHNE Einheiten-Suffix — im Unterschied zu `style="plain"` (bestehend aus Scheibe 1, hängt immer die Einheit an, z.B. `"45 km/h"`). Grund: `fmt_val`s migrierbare Zweige geben bewusst nackte Zahlen zurück, da die Einheit bereits in der Spalten-Überschrift der Trip-Briefing-Tabelle steht; ein Einheiten-Suffix in der Zelle würde alle Snapshot-Tests brechen und beim Wind mit dem Kompass-Anhängsel kollidieren (`"45 km/h N"` statt korrekt `"45 N"`). `style="plain"` bleibt exakt wie in Scheibe 1 implementiert (kein Verhaltenswechsel, reine Koexistenz zweier Stile im selben `if/elif`-Dispatch von `format_value`).

**Migrierte Zweige in `fmt_val` (6 Stück, alle mit identischem Katalog-`decimals` wie bisherige Hartcodierung):**
| `fmt_val`-Zweig | Katalog-`metric_id` | Katalog-`decimals` | Bisherige Hartcodierung |
|---|---|---|---|
| `wind` | `wind` | 0 | `f"{val:.0f}"` |
| `gust` | `gust` | 0 | `f"{val:.0f}"` |
| `precip` | `precipitation` | 1 | `f"{val:.1f}"` |
| `pop` | `rain_probability` | 0 | `f"{val:.0f}"` |
| `cape` | `cape` | 0 | `f"{val:.0f}"` |
| `freeze_lvl` | `freezing_level` | 0 | `f"{val:.0f}"` |

Jeder dieser 6 Zweige ruft für die Zahl `format_value(metric_id, val, style="bare")` statt der bisherigen `f"{val:.Nf}"`-Hartcodierung auf. Wind behält den lokalen Kompass-Anhängsel-Merge (`_wind_dir_deg` aus `row`) bei — dieser bleibt unverändert in `helpers.py`, nur die reine Zahl davor kommt aus `format_value`.

**Ampel-Levelquelle-Migration (5 Metriken: `wind`/`gust`/`precip`/`pop`/`cape`):** Der lokale Ampel-Aufruf in `fmt_val` (`if html and _use_ampel: return ampel_dot(val, get_metric(metric_id).display_thresholds)`) wird auf `severity_for(metric_id, val)` als Levelquelle umgestellt; das CSS-Dot-Markup selbst (`_ampel_dot_css(level)`) bleibt lokal in `helpers.py` und wird unverändert mit dem von `severity_for` gelieferten kanonischen Level (`green/yellow/orange/red`) aufgerufen. `ampel_dot`/`_level_from_thresholds`/`ampel_level` bleiben als eigenständige Funktionen bestehen (keine Löschung, kein Alias) — sie werden nur für diese 5 spezifischen Aufrufstellen in `fmt_val` nicht mehr benutzt. `freeze_lvl` hat keine `display_thresholds` im Katalog und war nie Ampel-fähig — bleibt unverändert ohne Ampel-Pfad.

**Explizit UNVERÄNDERT in dieser Scheibe:** `ampel_level` (die für `_render_html_table`-Zell-Tönung in `html.py:574` genutzte Funktion) — eine zentrale Migration hätte größeren, hier nicht beabsichtigten Blast Radius (u.a. weil `ampel_level` bei fehlenden Thresholds `"green"` liefert, `severity_for` aber bewusst `None` — Scheibe-1-Fix). Alle anderen `fmt_val`-Zweige (`thunder`, `temp`/`felt`/`dewpoint`, `snow_limit`/`snow_depth`, `cloud*`, `sunshine`, `humidity`, `pressure`, `visibility`, `wind_dir`) bleiben unverändert bestehen — Katalog-`decimals`/`display_thresholds` divergieren dort genuin von der bestehenden Formatierung (siehe Known Limitations) oder sind mechanismusfremd (z.B. `thunder`-Wort-vs-Symbol-Logik).

**Katalog-Verifikation (gegen `metric_catalog.py` verifiziert):** `wind` `display_thresholds={yellow:30, orange:50, red:70}`, `gust`={yellow:50, orange:65, red:80}, `precipitation`={yellow:1, orange:5, red:10}, `rain_probability`={yellow:30, orange:60, red:80}, `cape`={yellow:1000, orange:2500, red:3500} — alle 5 vollständig, nicht invertiert. `severity_for` liefert für keine dieser 5 Metriken `None` bei einem numerischen Wert. Anders als bei Wind in Compare/Scheibe 2 (dort echte Divergenz zwischen hartcodierten `40/30/20`-Schwellen und Katalog `70/50/30`) stimmen die in `fmt_val` bisher verwendeten Katalog-Lookups (`get_metric(metric_id).display_thresholds`, bereits vor dieser Scheibe katalog-basiert über `_AMPEL_KEY_TO_METRIC_ID`) bereits 1:1 mit `severity_for`s Quelle überein — die Migration ist ein reiner Implementierungstausch ohne sichtbare Verhaltensänderung.

## Expected Behavior

- **Input:** Trip-Briefing-Rendering (E-Mail HTML/Plain, Telegram) mit numerischen Wetterwerten für `wind`/`gust`/`precip`/`pop`/`cape`/`freeze_lvl`.
- **Output:** `fmt_val` liefert für diese 6 Spalten exakt dieselben Zahlenstrings wie vor der Migration; die 5 Ampel-fähigen Metriken zeigen exakt dieselbe CSS-Dot-Farbe wie vor der Migration.
- **Side effects:** Keine — reine Formatierungsfunktionen ohne I/O, State oder Netzwerkzugriff. Kein für Nutzer sichtbarer Unterschied zu vorher (im Gegensatz zur bewusst gewollten Wind-Schwellen-Angleichung in Scheibe 2).

## Acceptance Criteria

- **AC-1:** Given `format_value(metric_id, value, style="bare")` in `metric_format.py` / When es für mindestens drei der sechs migrierten Metriken aufgerufen wird (z.B. `wind`, `precipitation`, `cape`) / Then liefert es die korrekte nackte Zahl ohne Einheiten-Suffix, gerundet auf den Katalog-`decimals`-Wert der jeweiligen Metrik.
  - Test: `tests/tdd/test_metric_format.py` prüft u.a. `format_value("wind", 45.0, style="bare") == "45"` (0 Dezimalstellen, kein `" km/h"`-Suffix), `format_value("precipitation", 3.26, style="bare") == "3.3"` (1 Dezimalstelle), `format_value("cape", 1234.0, style="bare") == "1234"`.

- **AC-2:** Given `format_value(metric_id, value, style="plain")` (bestehender Stil aus Scheibe 1) / When der neue `style="bare"`-Zweig eingeführt wird / Then verhält sich `style="plain"` exakt wie vorher (Regressionsschutz, keine Signatur- oder Ergebnisänderung).
  - Test: Bestehende `style="plain"`-Tests aus `tests/tdd/test_metric_format.py` (Scheibe 1, z.B. `format_value("wind", 45.0, style="plain") == "45 km/h"`) bleiben ohne Anpassung grün.

- **AC-3:** Given eine Trip-Briefing-Tabelle (E-Mail HTML, `html.py`) mit Spalten für die 6 migrierten Metriken / When die Migration von `fmt_val` auf `format_value(..., style="bare")` abgeschlossen ist / Then zeigt jede Zelle exakt denselben Zahlenwert wie vor der Migration — keine für Nutzer sichtbare Änderung.
  - Test: Bestehende Rendering-/Snapshot-Tests, die konkrete Zellwerte für wind/gust/precip/pop/cape/freeze_lvl prüfen (u.a. Teile von `tests/tdd/test_issue_435_format_modes.py`, `tests/tdd/test_issue_810_raw_format_ampel.py`), laufen unverändert grün, ohne Anpassung der erwarteten Werte.

- **AC-4:** Given die Ampel-Darstellung (CSS-Dot) für die 5 Ampel-fähigen Metriken (`wind`/`gust`/`precip`/`pop`/`cape`) / When die HTML-Ampel-Levelquelle in `fmt_val` von der lokalen Threshold-Logik auf `severity_for(metric_id, val)` umgestellt wird / Then zeigt jede Metrik für Referenzwerte an jeder Schwellengrenze (knapp unter/über yellow/orange/red) exakt dieselbe Dot-Farbe wie vor der Migration — keine Verhaltensänderung, da Katalog-Schwellen bereits mit den bisher genutzten übereinstimmten.
  - Test: `tests/tdd/test_issue_759_email_ampel.py` und `tests/tdd/test_ampel_css_dots.py` laufen unverändert grün, ergänzt um mindestens einen expliziten Grenzwert-Test je migrierter Metrik, der die Dot-Farbe vor/nach dem Umbau vergleicht.

- **AC-5:** Given alle anderen `fmt_val`-Zweige, die nicht Teil dieser Migration sind (`thunder`, `temp`/`felt`/`dewpoint`, `cloud*`, `sunshine`, `snow_limit`/`snow_depth`, `humidity`, `pressure`, `visibility`, `wind_dir`) / When Scheibe 3 abgeschlossen ist / Then bleibt ihr Verhalten vollständig unverändert, ohne dass diese Zweige selbst angepasst werden.
  - Test: Die vollständige bestehende Testsuite (`tests/red/test_issue_435_format_modes.py`, `tests/tdd/test_issue_759_email_ampel.py`, `tests/tdd/test_issue_810_raw_format_ampel.py`, `tests/tdd/test_ampel_css_dots.py`, `tests/tdd/test_issue_831_mobile_einfach.py`) bleibt grün, ohne dass diese Testdateien für die nicht-migrierten Zweige angepasst werden müssen.

- **AC-6:** Given die drei asymmetrischen `fmt_val`-Aufrufer `narrow.py` (Telegram), `email/plain.py` (Plain-Text) und `email/html.py` (Desktop-Tabelle) mit jeweils unterschiedlichen Parameter-Teilmengen (`friendly_keys`/`html`/`row`/`format_modes`/`indicator_keys`) / When `fmt_val` intern auf `format_value`/`severity_for` umgestellt wird / Then funktionieren alle drei Aufrufer unverändert, ohne Codeänderung an ihnen selbst und ohne Signaturänderung an `fmt_val`.
  - Test: `tests/tdd/test_issue_811_mode_matrix.py` (deckt alle Modus-Kombinationen über alle drei Aufrufer ab) läuft unverändert grün; zusätzlich echte, frisch versendete Trip-Briefing-Test-Mail wird via `briefing_mail_validator.py` gegen `gregor-test@henemm.com` verifiziert (Renderer-Mail-Gate #811, Implementierungsdetail).

## Known Limitations

- `ampel_level`/`html.py:574` (zentrale Zell-Tönung-Ampel-Migration) bleibt in dieser Scheibe unverändert — nicht Teil des Scopes, größerer Blast Radius wäre nicht beabsichtigt (potenzieller Folge-Workflow).
- Die übrigen `fmt_val`-Zweige (`thunder`, `temp`/`felt`/`dewpoint`, `cloud*`, `sunshine`, `snow_limit`/`snow_depth`, `humidity`, `pressure`, `visibility`, `wind_dir`) sind bewusste Ausnahmen mit echten Sonderregeln (fixe `.1f`-Präzision divergiert von Katalog-`decimals`, katalogfremde Emoji-/Wort-Logik, echte variable Rundung bei `visibility`, Falsy-0-Sonderfall bei Schnee) — keine Migration in dieser Scheibe, keine stille Lücke.
- `trip_report.py::_fmt_val` (eigene Divergenzen: 2-Stufen-Highlight statt 4-Stufen-Ampel, fehlende Orange-Schwelle, toter CAPE-Pfad, verbotene englische Sichtweite-Wörter) ist explizit NICHT Teil dieser Scheibe — eigene Root-Cause-Analyse und eigene ACs nötig (Scheibe 4).
- Diese Scheibe hat einen deutlich höheren Blast Radius als Scheibe 1+2, da `fmt_val` bei JEDEM Trip-Briefing-Versand läuft (nicht nur beim optionalen Compare-Feature) — daher greift `renderer_mail_gate.py` ECHT und verlangt eine echte, frisch versendete Test-Mail-Verifikation vor dem Commit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Konsolidierung innerhalb der bestehenden Python-Core-Schicht, additive Erweiterung von `format_value` um einen neuen Stil ohne Bruch bestehender Signaturen/Verhalten (Koexistenz-Strategie wie in Scheibe 1+2), keine neue externe Abhängigkeit, keine Schema-/Persistenzänderung, keine API-Vertragsänderung. Kein architekturrelevanter Entscheidungsbedarf über die bereits in der Analyse-Phase getroffene Tech-Lead-Entscheidung (additiver `style="bare"` statt Umbau von `style="plain"`) hinaus.

## Changelog

- 2026-07-12: Initial spec created
