# Context: fix-952-alert-mail-design-fidelity

## Request Summary
Die #914/#917-Alert-Renderer (Betreff/E-Mail/Telegram für Abweichungs-Alerts, `msg.source is None`)
weichen gegen die eigenen Akzeptanzkriterien (#914 C3/C6) und die vorhandene Claude-Design-Vorlage ab:
Langform statt Kürzel, unrunde Zahlen, doppeltes "km", kein Branding im HTML.

## Related Files
| File | Relevanz |
|------|----------|
| `src/output/renderers/alert/render.py` | `_label()`, `_km_str()`, `render_email()` — Ort der 4 Befunde |
| `src/app/metric_catalog.py` | `MetricDefinition` (Z. 24-73), `format_metric_value()` (Z. 679-712), fehlendes Kürzel-Feld |
| `src/output/renderers/email/design_tokens.py` | Bestehende Marken-Tokens, von `render.py` nicht importiert |
| `src/output/renderers/email/html.py`, `compare_html.py`, `helpers.py` | Referenz: nutzen `design_tokens.py` korrekt |
| `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html` | Soll-Referenz (Zeilen 156-188 = eigentliche Mail-Struktur `.mail`/`.mail-body`) |
| `tests/` (Fixtures aus #917) | Bestehende Renderer-Tests — dürfen für die Onset-Pfade nicht brechen |

## Existing Patterns
- Andere Mail-Renderer binden `design_tokens.py` ein und bauen HTML mit `G_ACCENT`/`G_INK`/`G_SUCCESS`/`G_DANGER`/`FONT_UI`/`FONT_DATA` (Hex direkt, keine CSS-Variablen wegen Outlook).
- Slice 1 (#914) hat neue Katalog-Felder (`sms_code`, `decimals`, `cmp`) als Single Source direkt in `MetricDefinition` ergänzt — kein Renderer-seitiges Mapping. Gleiches Muster passt für das fehlende Kürzel-Feld.
- `format_metric_value()` ist eine geteilte Funktion (Einheiten-Switch); Erweiterung um Fallback-Rundung darf bestehende Branches (`m/km/hPa/%/km/h/°C/mm`) nicht verändern.

## Kernbefund aus der Kontext-Recherche (neu ggü. Analyse aus Issue #952)
`col_label` (z. B. "Gust", "Rain%", "Thndr%") und `compact_label` (z. B. "CE", "G") sind
**ältere, andere Felder** (Tabellen-Header eines Bestandssystems) — sie entsprechen NICHT
den in #914 geforderten deutschen Alert-Kürzeln ("CAPE", "Böen", "Niedersch", "Regen%", "Gewitter", …).
Ein passendes Feld existiert im Katalog **noch nicht**. `col_label="Thndr%"` bei `cape` ist zudem
offensichtlich ein Copy-Paste-Rest von `thunder` (eigener, nicht in #952 gemeldeter Altfehler —
nicht Gegenstand dieses Fixes, nur zur Kenntnis).

→ Konsequenz für die Spec: neues Katalog-Feld (Arbeitsname `alert_label`) nötig, befüllt exakt nach
der #914-Registry-Tabelle für alle alert-fähigen Metriken, mit `label_de`-Fallback für den Rest.

## Dependencies
- Upstream: `format_metric_value()` wird u.a. von Compact-/Compare-Renderern mitgenutzt (Grep vor Änderung: sicherstellen, dass nur der Fallback-Zweig erweitert wird, keine bestehenden Branches).
- Downstream: `TripAlertService._send_alert` (trip_alert.py) ruft die Alert-Renderer im echten Versandpfad auf — Änderungen wirken sich sofort auf Produktions-Alerts aus.

## Existing Specs
- Keine dedizierte Spec-Datei zu #914/#917 im Repo gefunden (Architektur-Entscheidung stand als GitHub-Kommentar auf #914, siehe ADR-0011). Diese Fix-Spec wird `docs/specs/modules/fix_952_alert_mail_design_fidelity.md`.

## Risks & Considerations
- `format_metric_value()`-Änderung ist die riskanteste Stelle (geteilte Funktion) — Fix muss strikt additiv sein (nur der `else`-Fallback), bestehende Einheiten-Branches unverändert lassen, mit Tests für alle bereits gehandhabten Einheiten als Regressionsnetz.
- Neues Katalog-Feld `alert_label` muss für ALLE aktuell alert-fähigen Metriken befüllt werden (nicht nur CAPE), sonst bleibt der Bug für andere Metriken bestehen.
- HTML-Redesign betrifft nur `render_email()` im Deviation-Pfad (`msg.source is None`); Onset-Pfad (`_render_email_onset`) bleibt unverändert (eigener Scope, nicht gemeldet).
- Reales Sende-Verhalten prüfen ohne echte Wetterabweichung: `alert-preview`-Endpoint auf Staging (siehe #952-Body) — kein Mock.
