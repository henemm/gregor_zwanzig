---
entity_id: issue_1214_metric_format_slice1_2
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [metric-format, compare-html, konsolidierung, issue-1214]
---

# Metric-Format-Konsolidierung — Scheibe 1+2 (neues Modul + Compare-Migration)

## Approval

- [ ] Approved

## Purpose

Issue #1214 verlangt die Konsolidierung der 6-8fach duplizierten Metrik-Formatierung/Ampel-Logik/Labels in ein gemeinsames Modul. Dieser Workflow deckt nur Scheibe 1 (neues Modul `src/output/metric_format.py` + Tests, noch ohne Consumer) und Scheibe 2 (`compare_html.py` auf das neue Modul umstellen, inkl. Angleichung der Wind-Schwellen an den Katalog) ab. Scheiben 3-6 (weitere Consumer, Thunder-Ordinal/Wolken-Skala) sind explizit NICHT Teil dieser Spec und folgen in separaten Workflows.

## Source

- **File:** `src/output/metric_format.py` (neu), `src/output/renderers/email/design_tokens.py`, `src/output/renderers/email/compare_html.py`
- **Identifier:** `format_value()`, `severity_for()`, `tone_css()`, `label()`

**Schicht:** Python-Core/Domain-Backend (`src/app/`, `src/output/`) — kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** Scheibe 1 ~300-350 LoC (neues Modul + Tests), Scheibe 2 ~200-250 LoC Diff (Migration + Regressionstests, netto -60 bis -120 LoC in `compare_html.py` durch Konsolidierung, +40-60 LoC neue Tests)
- **Files:** 4 (siehe Scope-Tabelle)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`MetricDefinition`, `get_metric`, `format_metric_value`) | module | Single Source of Truth für Metrik-Metadaten (unit, decimals, display_thresholds); neues Modul liest daraus, ruft `format_metric_value` intern nur in Richtung metric_id→unit auf |
| `src/output/renderers/email/helpers.py` (`ampel_level`, `fmt_val`) | module | Bestehende Ampel-/Formatierungs-Logik, bleibt UNVERÄNDERT bestehen; `severity_for` ist eine Neuimplementierung, kein Ersatz von `ampel_level` in dieser Scheibe |
| `src/output/renderers/email/design_tokens.py` | module | Reine Farbkonstanten (`G_SUCCESS`, `G_WARNING`, `G_DANGER`, `G_ALERT_L2/L3/L4` etc.); wird um `tone_css(level)` ergänzt |
| `src/output/renderers/email/compare_html.py` (`_sev_*`, `_fmt_*`, `_RISK_CELL`, `CV2_METRICS`, `HOUR_METRICS`) | module | Ziel der Migration in Scheibe 2 |
| `.claude/hooks/renderer_mail_gate.py` | gate | Blockiert Commit an `compare_html.py` ohne frischen Matrix-Test-Lauf + Mail-Validator-Nachweis (Implementierungsdetail, kein AC) |

## Implementation Details

**Koexistenz statt Thin-Wrapper (Tech-Lead-Entscheidung):** `format_metric_value(unit, value, *, signed=False)` (bestehende, unit-keyed Signatur in `metric_catalog.py`) bleibt unverändert bestehen und wird NICHT zum Thin-Wrapper umgebaut. Das neue `format_value(metric_id, value, style)` ist eine eigenständige Implementierung, die `get_metric(metric_id).decimals`/`.unit` direkt nutzt. `format_value` darf `format_metric_value` intern aufrufen (Richtung metric_id→unit), niemals umgekehrt — ein Rückschluss unit→metric_id wäre nicht eindeutig, da mehrere Metriken dieselbe Einheit mit unterschiedlichen `decimals` teilen (z.B. mehrere km/h-Metriken).

**Neues Modul `src/output/metric_format.py` (Scheibe 1), vier Funktionen:**
- `format_value(metric_id, value, style)` — formatiert einen Wert für eine gegebene Metrik-ID und einen Darstellungsstil (analog zu bestehenden Format-Modi, siehe `docs/specs/modules/issue_435_metric_format_modes.md`), nutzt Katalog-`decimals`/`unit`.
- `severity_for(metric_id, value)` — Verschiebung/Neuimplementierung von `helpers.ampel_level`-Logik in das neue Modul, arbeitet threshold-basiert über `get_metric(metric_id).display_thresholds`/`highlight_threshold`, gibt kanonisches Vokabular `green/yellow/orange/red` (oder `None` bei fehlenden Thresholds) zurück. WICHTIG: `helpers.ampel_level` bleibt UNVERÄNDERT als eigenständige Funktion bestehen (kein Alias, kein gemeinsamer Codepfad in dieser Scheibe) — Konsumenten von `ampel_level` werden nicht umgestellt.
- `tone_css(level)` — neu in `design_tokens.py` (nicht im neuen Modul selbst, sondern dort re-exportiert/importiert), mappt kanonisches Vokabular (`green/yellow/orange/red`) auf `(bg, fg)`-Hex-Tupel, ersetzt `_RISK_CELL` in `compare_html.py`. Operiert AUSSCHLIESSLICH auf dem kanonischen Ampel-Vokabular — MUSS strikt getrennt bleiben von `_ALERT_LEVEL_CELL` (4 amtliche Warnstufen 1-4 für Wetterwarnungen, eigenes System, NICHT Teil dieser Konsolidierung).
- `label(metric_id, style)` — Katalog-Passthrough für Labels (`label_de`/`compact_label`/`col_label` je nach `style`), keine neue Logik, nur ein einheitlicher Zugriffspunkt.

**Level-Vokabular-Mapping:** Ampel (`green/yellow/orange/red`, kanonisch) ↔ Compare-lokal (`ok/caution/warn/danger`) sind 1:1 kompatibel: `ok↔green, caution↔yellow, warn↔orange, danger↔red`. `severity_for()` gibt immer das kanonische Vokabular zurück; die Übersetzung auf Compares lokales Vokabular erfolgt an der Aufrufstelle in `compare_html.py`, nicht im neuen Modul (Compare-Vokabular bleibt dort lokal, wird nicht global umbenannt).

**Scheibe 2 — Migration `compare_html.py`:**
- `HOUR_METRICS`/`CV2_METRICS` (Dict-Listen) bekommen ein zusätzliches Feld `"metric_id"` (String), das auf den passenden Eintrag in `metric_catalog._METRICS` verweist. Keine neue Katalog-Lookup-Funktion nötig, bestehendes `get_metric(metric_id)` genügt.
- Die lokalen `_sev_*`-Funktionen werden durch Aufrufe von `severity_for(metric_id, value)` + lokale Übersetzung auf `ok/caution/warn/danger` ersetzt, MIT AUSNAHME von Funktionen, deren Katalog-Metrik keine Standard-`display_thresholds` (`yellow`/`orange`/`red`) hat oder invertierte Schwellen nutzt (z.B. `temperature`, `uv_index`, `visibility` — echte Katalog-Divergenzen, verifiziert in der Implementierung) — nur `_sev_wind` divergiert real vom Katalog und wird in dieser Scheibe migriert. Diese Ausnahme-Klausel gilt symmetrisch zur bereits bestehenden `_fmt_*`-Ausnahme unten.
- Die 7 lokalen `_fmt_*`-Funktionen (`_fmt_deg`, `_fmt_kmh`, `_fmt_rain`, `_fmt_uv`, `_fmt_pop`, `_fmt_visibility`, `_fmt_thunder`) werden durch `format_value(metric_id, value, style)` ersetzt, MIT AUSNAHME von Spezialfällen mit nicht pauschal übertragbaren Rundungsregeln (z.B. `_fmt_visibility`: variable Nachkommastelle für Sicht in km) — diese werden einzeln geprüft und bleiben ggf. lokal, wenn `format_value`/Katalog-`decimals` das Verhalten nicht 1:1 abbilden kann.
- `_RISK_CELL` wird durch `tone_css(level)` ersetzt.
- `_THUNDER_LEVEL_LABEL`/`_THUNDER_SEV` (Compare-eigenes Vokabular für Gewitter-Ordinalstufen, s. Docstring-Kommentar Z.102-105) bleiben als lokale, bewusst eigenständige Kopie bestehen — keine Migration in dieser Scheibe (Thunder-Ordinal-Konsolidierung ist Scheibe 6, PO-Entscheidung ausstehend).
- `_ALERT_LEVEL_CELL` bleibt vollständig unangetastet.

**Wind-Schwellen-Angleichung (eigener, sichtbarer Teilschritt):** `_sev_wind` ist aktuell hartcodiert auf `>40→danger, >30→warn, >20→caution`, während der Katalog für `wind` `display_thresholds={yellow:30, orange:50, red:70}` definiert. Diese Divergenz wird als expliziter, eigens benannter Schritt/Commit innerhalb Scheibe 2 behoben (nicht als stille Nebenwirkung im generischen Refactoring versteckt). Sichtbare Folge: Wind 45 km/h zeigt in Compare-Mails künftig gelb (`orange`-Schwelle bei 50 noch nicht erreicht → tatsächlich: 45 liegt zwischen yellow=30 und orange=50, also `yellow`/gelb) statt bisher rot (`>40→danger`). Eigener Regressionstest `test_wind_45_kmh_yellow_not_red` beweist dies explizit.

**Korrigierter Befund (2026-07-11, gegen echten Katalog-Code verifiziert):** Die zunächst vermutete „variable Rundung" von `_fmt_visibility` existiert NICHT — die Funktion rundet fix auf 1 Dezimalstelle (`f"{v/1000:.1f} km"`), was exakt zu `visibility.decimals=1` + `visibility.display_unit="km"` passt. **Neue, verifizierte Anforderung:** `format_value` MUSS das `display_unit`-Feld respektieren, falls gesetzt (aktuell nur bei `visibility`: `unit="m"` → `display_unit="km"`, Konvertierungsfaktor 1000) — Wert erst umrechnen, dann mit `decimals` runden und `display_unit` als Suffix anhängen. Für alle anderen Metriken (`display_unit=""`) bleibt `unit` unverändert Anzeige-Einheit. `_fmt_metric` (generischer Helper für `CV2_METRICS`, nutzt `decimals`+`unit` direkt aus der Dict-Definition, nicht aus dem Katalog) kann 1:1 durch `format_value(metric_id, ...)` ersetzt werden, sobald jeder `CV2_METRICS`/`HOUR_METRICS`-Eintrag ein `metric_id`-Feld hat.

## Expected Behavior

- **Input:** Ein `metric_id` (z.B. `"temperature"`, `"wind"`, `"visibility"`) plus numerischer Wert plus Darstellungsstil.
- **Output:** `format_value` liefert einen formatierten String passend zur Katalog-Definition (Dezimalstellen, Einheit); `severity_for` liefert `green|yellow|orange|red|None`; `tone_css` liefert ein `(bg, fg)`-Hex-Tupel; `label` liefert den passenden Label-String.
- **Side effects:** Keine — reine Funktionen ohne I/O, State oder Netzwerkzugriff. `compare_html.py`-Rendering-Output ändert sich NUR bei der bewusst gewollten Wind-Schwellen-Angleichung (45 km/h: rot → gelb), sonst identisch zu vorher.

## Acceptance Criteria

- **AC-1:** Given das neue Modul `src/output/metric_format.py` mit den vier Funktionen `format_value`, `severity_for`, `tone_css`, `label` / When es für mindestens drei unterschiedliche Metriktypen aufgerufen wird (Temperatur ohne Dezimalstelle [Katalog `decimals=0`], Wind ohne Dezimalstelle [Katalog `decimals=0`], Sicht mit einer Dezimalstelle UND Einheiten-Konvertierung m→km [Katalog `decimals=1`, `display_unit="km"`]) / Then liefert jede Funktion für jeden dieser drei Metriktypen einen korrekten, gegen die Katalog-Definition (`decimals`, `unit`, `display_unit`, `display_thresholds`) verifizierten Wert zurück.
  - Test: `tests/tdd/test_metric_format.py` prüft `format_value("temperature", 21.6, ...) == "22°C"` (0 Dezimalstellen, Python round-half-to-even via `f"{v:.0f}"`-Formatierung, nicht kaufmännisch), `format_value("wind", 45.0, ...) == "45 km/h"`, `format_value("visibility", 4200, ...) == "4.2 km"` (m→km konvertiert, 1 Dezimalstelle) sowie die zugehörigen `severity_for`/`tone_css`/`label`-Aufrufe gegen konkrete erwartete String-/Farbwerte, kein Dateiinhalt-Check.

- **AC-2:** Given die bestehende Funktion `format_metric_value(unit, value)` in `metric_catalog.py` / When das neue Modul `metric_format.py` eingeführt wird / Then verhält sich `format_metric_value` exakt wie vorher (keine Signaturänderung, keine Ergebnisänderung).
  - Test: Bestehende Tests `test_issue_131_alert_klarheit.py` und `test_952_alert_mail_design_fidelity.py` bleiben ohne Anpassung grün (z.B. `format_metric_value("m", 12240.0) == "12.240 m"`).

- **AC-3:** Given ein Wind-Wert von 45 km/h in einer Compare-Mail / When die Ampel-Farbe nach der Migration auf `severity_for`/`tone_css` bestimmt wird / Then zeigt Compare für diesen Wert dieselbe Ampel-Farbe (gelb) wie das Trip-Briefing — vor der Migration zeigten beide Pfade unterschiedliche Farben (Compare rot, Trip-Briefing gelb).
  - Test: Neuer Regressionstest `test_wind_45_kmh_yellow_not_red` in `tests/tdd/test_compare_html_email.py` (oder benachbarter Testdatei) rendert eine Compare-Zelle mit Wind=45 km/h und prüft, dass die resultierende Zellfarbe der gelben (`yellow`/`caution`) Tönung entspricht, nicht der roten.

- **AC-4:** Given die vollständige Migration von `compare_html.py` auf das neue Modul / When die bestehende Compare-Test-Suite ausgeführt wird / Then bestehen alle bisherigen Testfälle unverändert (keine Regression im Compare-Mail-Rendering).
  - Test: `tests/tdd/test_compare_html_email.py` (351 Zeilen) läuft nach der Migration vollständig grün, ohne Anpassung bestehender Erwartungswerte (außer dem bewusst geänderten Wind-45-Fall aus AC-3).

- **AC-5:** Given `_ALERT_LEVEL_CELL` (4 amtliche Warnstufen für Wetterwarnungen, separates System) / When die Migration in Scheibe 1+2 durchgeführt wird / Then bleibt das Rendering amtlicher Warnstufen-Zellen vollständig unverändert — `tone_css` wird an keiner Stelle mit `_ALERT_LEVEL_CELL` vermischt oder ersetzt es.
  - Test: Eigener Test rendert eine amtliche Warnstufen-Zelle (Stufe 1-4) vor und nach der Migration und vergleicht die resultierenden Farbwerte auf Identität; prüft zusätzlich, dass `tone_css` und `_ALERT_LEVEL_CELL` getrennte Codepfade bleiben (kein gemeinsamer Aufruf).

- **AC-6:** Given alle bisherigen Konsumenten von `ampel_level`/`fmt_val`/`format_metric_value` außerhalb von `compare_html.py` (`narrow.py`, `compact.py`, `plain.py`, `comparison.py`, `weather_metrics.py`, `api/routers/validator.py`, `html.py`, `alert/render.py`) / When Scheibe 1+2 abgeschlossen ist / Then funktionieren diese Konsumenten unverändert, ohne Codeänderung an ihnen selbst.
  - Test: Volle bestehende Testsuite dieser Module (u.a. `test_issue_759_email_ampel.py`, `test_issue_810_raw_format_ampel.py`, `test_ampel_css_dots.py`, `test_issue_914_slice1_foundation.py`) bleibt grün, ohne dass diese Dateien selbst angepasst werden.

## Known Limitations

- Scheiben 3-6 (weitere Consumer-Migration wie `narrow.py`/`compact.py`/`plain.py`/`comparison.py`/`weather_metrics.py`/`api/routers/validator.py`/`alert/render.py`/`html.py:574`, sowie Thunder-Ordinal- und Wolken-Skalen-Konsolidierung) sind explizit NICHT Teil dieser Spec und folgen in separaten, späteren Workflows.
- `helpers.ampel_level`/`helpers.fmt_val` bleiben in dieser Scheibe unverändert bestehen — sie werden nicht durch das neue Modul ersetzt, auch nicht als Alias. Eine spätere Konsolidierung (Scheibe 3+) müsste dies separat spezifizieren.
- `_fmt_visibility` lässt sich (entgegen einer zunächst falschen Vermutung) VOLLSTÄNDIG durch `format_value` ersetzen — die Funktion rundet fix auf 1 Dezimalstelle nach m→km-Konvertierung, was exakt `visibility.decimals=1`+`display_unit="km"` entspricht. `format_value` muss `display_unit` als Konvertierungs-Suffix unterstützen (einzige betroffene Metrik aktuell: `visibility`, Faktor 1000).
- Die Wind-Schwellen-Angleichung ist eine bewusst gewollte, für Nutzer sichtbare Verhaltensänderung (nicht rückwärtskompatibel im Sinne "pixel-identisch zu vorher") — dies ist laut Issue-AC explizit gefordert, nicht ein unbeabsichtigter Nebeneffekt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Modul-Konsolidierung innerhalb der bestehenden Python-Core-Schicht ohne neue externe Abhängigkeit, ohne Schema-/Persistenzänderung, ohne API-Vertragsänderung (Koexistenz-Strategie verhindert Breaking Changes an bestehenden Signaturen). Kein architekturrelevanter Entscheidungsbedarf über die im Analyse-Schritt bereits getroffene Tech-Lead-Entscheidung (Koexistenz statt Thin-Wrapper) hinaus.

## Changelog

- 2026-07-11: Initial spec created
- 2026-07-11 (nach Freigabe, Fakten-Korrektur in TDD-RED-Vorbereitung): AC-1 korrigiert — "Temperatur mit einer Dezimalstelle" war sachlich falsch, Katalog hat `decimals=0` für Temperatur (verifiziert gegen `metric_catalog.py:85` und `compare_html._fmt_deg`, das bereits 0 Dezimalstellen zeigt). "Bekanntes Risiko" zu `_fmt_visibility` war unbegründet (Funktion rundet nachweislich FIX auf 1 Dezimalstelle, kein variables Verhalten) — stattdessen neue, verifizierte Anforderung ergänzt: `format_value` muss `display_unit` (m→km-Konvertierung, aktuell nur bei `visibility`) unterstützen. Acceptance-Substanz (AC-Anzahl, Testbarkeit, Scope) unverändert — nur konkrete Beispielwerte korrigiert.
- 2026-07-12 (Adversary Fix-Loop 2, Finding F002): Implementation-Details-Zeile zu den `_sev_*`-Funktionen präzisiert — forderte zuvor unbedingte Vollmigration aller 9 Funktionen ohne Ausnahme-Klausel, obwohl mehrere Katalog-Metriken (temperature, uv_index: keine Standard-Thresholds; visibility: invertierte Thresholds) real vom Compare-lokalen Schema abweichen. Jetzt symmetrisch zur `_fmt_*`-Ausnahme formuliert. Kein Scope-/AC-Wechsel, nur Klarstellung der bereits in der Implementierung korrekt getroffenen Entscheidung.
