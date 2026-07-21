---
entity_id: issue_912_pill_textformat
type: feature
created: 2026-06-29
updated: 2026-06-29
status: draft
version: "1.0"
tags: [email, briefing, pills, metrics, format]
---

<!-- Issue #912 — Pill-Textformat METRIKEN-ÜBERBLICK an JSX-Design-Vorlage angleichen -->

# Issue 912 — Pill-Textformat: METRIKEN-ÜBERBLICK an JSX-Vorlage angleichen

## Approval

- [x] Approved

## Purpose

Die Pill-Texte im Abschnitt „METRIKEN-ÜBERBLICK" der Briefing-Mail weichen von
der freigegebenen JSX-Design-Vorlage (`screen-output-preview.jsx`) ab. Dieses
Feature gleicht alle Metrik-Formate an: Klasse-2-Metriken (Bereich) erhalten
erstmals eine Uhrzeit, Klasse-1-Metriken (Ereignis) wechseln auf ein kompakteres
Format mit Schwellenwert-Präfix, und vier Labels werden umbenannt.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `build_metrics_summary_pills`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py` | Python-Modul | Pill-Render-Logik (einzige Änderungsdatei im Produktivcode) |
| `tests/tdd/test_issue_664_metrics_summary.py` | Testdatei | Formatstrings anpassen (4 Tests betroffen) |
| `tests/tdd/test_issue_795_briefing_quality.py` | Testdatei | 3 durch #912 überholte Tests invertieren/anpassen |
| `tests/tdd/test_issue_807_reproduction.py` | Testdatei | Ggf. anpassen wenn Formatstrings kollidieren |
| `docs/context/911-pill-format-delta.md` | Kontext | Delta-Tabelle IST → SOLL als fachliche Referenz |

## Estimated Scope

- **LoC:** ~150 (105 geändert + 45 neu)
- **Files:** 4 MODIFY
- **Effort:** medium

## Implementation Details

Alle Änderungen konzentrieren sich auf `build_metrics_summary_pills` in
`src/output/renderers/email/helpers.py`. Die Funktion rendert pro aktivierter
Metrik eine `(text, tone)`-Pille. Die Logik wird pro Metrikklasse getrennt:

**Klasse 1 — Ereignis-Metriken (Wind, Böen, Regen, Regenwahrscheinlichkeit):**

- Ohne Schwellenüberschreitung: neu `"Wind max X km/h (HH:00)"` statt `"Wind ruhig"`
- Mit Schwellenüberschreitung: `"Wind >thr km/h ab HH:00 · max X (HH:00)"` —
  Präfix `>thr` ersetzt das alte `ab HH:00 · Spitze X um HH:00`
- Regen (mm): vereinfacht auf `"Regen ab HH:00 · X mm"` (kein `gesamt, Spitze`)
- Regenwahrscheinlichkeit: Label `"Regen-W."` statt `"Regenrisiko"`,
  Format `"Regen-W. >thr% ab HH:00 · max X% (HH:00)"`
- Gewitter: bleibt enum-basiert (kein `thunder_pct`-Feld), keine Änderung

**Klasse 2 — Bereichs-Metriken (Temperatur, Bewölkung, Nullgradgrenze, Taupunkt, UV):**

- Temperatur: `"8–11°C · Max 15:00"` — Bereich + Uhrzeit des Tageshöchstwerts
- Gefühlt: `"gef. min 6.6°C · 13:00"` — Min-Wert + Uhrzeit
- Bewölkung: `"60–95% bewölkt · Max 12:00"`
- UV: `"UV max 2.4 (14:00)"`
- Nullgradgrenze: Label `"0°-Linie"` statt `"0°-Grenze"`,
  Format `"0°-Linie 2.310–2.550 m · Max 15:00"` (Tausenderpunkt)
- Taupunkt: `"Taupunkt min 5.8°C (08:00)"`

**Sicht-Metriken:**

- Gut: `"Sicht min X km (HH:00)"` statt `"gute Sicht"`
- Schlecht: `"Sicht <2 km ab HH:00 · min X km (HH:00)"` statt `"Sicht ab HH:00 unter 2 km"`

**Feuchte:**

- Gut (unter Schwelle): `"Feuchte X–Y% · Max HH:00"` statt `"Luft trocken"`
- Schlecht: `"Feuchte >90% ab HH:00 · max X% (HH:00)"`

**Überschriebene Tests aus Issue #795:**

- `test_temperature_range_no_time` assertiert aktuell `"KEIN Max HH:00"` für
  Temperatur — nach #912 soll Temperatur genau dieses `· Max HH:00` tragen.
  Der Test wird invertiert: er assertiert nun, dass `· Max HH:00` vorhanden ist.
- `test_wind_below_threshold_calm_form` assertiert `"Wind ruhig"` — nach #912
  lautet die ruhige Form `"Wind max X km/h (HH:00)"`. Der Test wird angepasst.
- `test_wind_event_written_out_with_peak` assertiert `"Spitze … um HH:00"` —
  nach #912 ist das Format `"max X (HH:00)"`. Wird angepasst.

**Renderer-Commit-Gate (Issue #811):** `helpers.py` ist eine geschützte
Mail-Content-Datei. Vor dem Commit müssen laufen:
1. `uv run pytest tests/tdd/test_issue_811_mode_matrix.py`
2. `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen die
   Staging-Mail

## Acceptance Criteria

- **AC-1:** Given eine Briefing-Mail mit aktivierter Temperatur-Metrik und Stundenwerten 8–11°C, Tageshöchstwert um 15 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie das Format `8–11°C · Max 15:00` mit Temperaturbereich und Uhrzeit des Tageshöchstwerts — kein Gradzeichen-Abstand wie im alten `Temperatur 8–11 °C` mehr

- **AC-2:** Given eine Briefing-Mail mit aktivierter Gefühlt-Metrik und Mindestwert 6.6°C um 13 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `gef. min 6.6°C · 13:00` — zwei separate Pills für Temperatur und Gefühlt, kein zusammengefasster Text

- **AC-3:** Given eine Briefing-Mail mit Wind-Metrik aktiviert, max Wind 12 km/h um 11 Uhr Lokalzeit, kein Schwellenwert überschritten / When die Pill gerendert wird / Then zeigt sie `Wind max 12 km/h (11:00)` — die alte ruhige Form `Wind ruhig` erscheint nicht mehr

- **AC-4:** Given eine Briefing-Mail mit Wind-Metrik aktiviert, Schwelle 40 km/h ab 10 Uhr Lokalzeit, Spitzenwert 40 km/h ebenfalls um 10 Uhr / When die Pill gerendert wird / Then zeigt sie `Wind >40 km/h ab 10:00 · max 40 (10:00)` — das alte Format `Wind ab 10:00 · Spitze 40 km/h um 10:00` erscheint nicht

- **AC-5:** Given eine Briefing-Mail mit Regen-Metrik, Regen ab 11 Uhr Lokalzeit, Summe 7.3 mm / When die Pill gerendert wird / Then zeigt sie `Regen ab 11:00 · 7.3 mm` — der alte Suffix `gesamt, Spitze HH:00` erscheint nicht mehr; `kein Regen` bleibt bei regenfreiem Tag

- **AC-6:** Given eine Briefing-Mail mit Regenwahrscheinlichkeits-Metrik aktiviert, Schwelle 50% ab 12 Uhr Lokalzeit, Maximum 68% um 13 Uhr / When die Pill gerendert wird / Then zeigt sie `Regen-W. >50% ab 12:00 · max 68% (13:00)` — das Label `Regenrisiko` erscheint nirgendwo im Metriken-Überblick

- **AC-7:** Given eine Briefing-Mail mit Bewölkung 60–95% aktiviert, Maximum um 12 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `60–95% bewölkt · Max 12:00` — das alte Format `Bewölkung 60–95 %` (mit Label-Präfix) erscheint nicht mehr

- **AC-8:** Given eine Briefing-Mail mit Sicht-Metrik, Sicht durchgehend gut (kein Unterschreiten der Sichtschranke) und Mindestsicht 8.5 km um 11 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `Sicht min 8.5 km (11:00)` — die alte Form `gute Sicht` erscheint nicht mehr

- **AC-9:** Given eine Briefing-Mail mit Nullgradgrenze 2310–2550 m aktiviert, Maximum um 15 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `0°-Linie 2.310–2.550 m · Max 15:00` — das Label `0°-Grenze` erscheint nicht mehr, Tausenderpunkt ist gesetzt

- **AC-10:** Given eine Briefing-Mail mit Feuchte-Metrik, Wert durchgehend unter Schwelle, Bereich 55–72%, Maximum um 14 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `Feuchte 55–72% · Max 14:00` — die alte Form `Luft trocken` erscheint nicht mehr

- **AC-11:** Given eine Briefing-Mail mit UV-Metrik, UV-Spitze 2.4 um 14 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `UV max 2.4 (14:00)` — das alte Format `UV bis 7` (ohne Uhrzeit) erscheint nicht mehr

- **AC-12:** Given eine Briefing-Mail mit Taupunkt-Metrik, Mindesttaupunkt 5.8°C um 08 Uhr Lokalzeit / When die Pill gerendert wird / Then zeigt sie `Taupunkt min 5.8°C (08:00)` — das alte Format `Taupunkt 5–8 °C` (als Bereich ohne Uhrzeit) erscheint nicht mehr

## Known Limitations

- Gewitter-Metrik bleibt enum-basiert (`ThunderLevel`), weil kein `thunder_pct`-Feld in `ForecastDataPoint` vorhanden ist. Das SOLL-Format aus der Delta-Tabelle (`Gewitter max X% (HH:00)`) ist für ein Folge-Issue reserviert, wenn das Feld ergänzt wird.
- Böen-Format ist analog zu Wind (AC-3/AC-4) — kein eigenes AC, da die Render-Logik dieselbe Funktion mit anderen Schwellenwerten durchläuft.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Format-Änderung in einer einzigen Hilfsfunktion; keine Architektur- oder API-Entscheidung erforderlich. Bestehende Ampel-Logik (`ampel_dot`, `ampel_stage_tone`) und Tone-Zuordnung bleiben unverändert.

## Changelog

- 2026-06-29: Initial spec erstellt — Issue #912, Workflow feat-912-pill-textformat
