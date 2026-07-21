---
entity_id: fix_862_849_col_labels
type: bugfix
created: 2026-06-23
updated: 2026-06-23
status: implemented
version: "1.0"
tags: [validator, metric-catalog, api, frontend, col-label, briefing-mail]
---

<!-- Issues #862 + #849 — Validator EN-Blacklist entfernen + Spaltenköpfe E-Mail/Vorschau synchronisieren -->

# Fix #862 + #849 — Validator EN-Blacklist + Spaltenköpfe synchronisieren

## Approval

- [x] Approved (2026-06-23)

## Purpose

Zwei zusammenhängende Defekte in der Spaltenköpfe-Kette beheben: (1) Der `briefing_mail_validator` lehnte korrekte englische Spaltenköpfe als Lokalisierungsfehler ab — die EN-Blacklist war eine Fehlspezifikation aus Issue #833 und wird vollständig entfernt. (2) E-Mail-Briefing und Frontend-Vorschau zeigten unterschiedliche Spaltenköpfe, weil das Frontend `col_label` (kurzes Kürzel) nicht kannte und stattdessen `label` (deutschen Langnamen) abschnitt — die API wird um `col_label` erweitert und das Frontend nutzt es direkt.

## Source

- **File:** `.claude/hooks/briefing_mail_validator.py` — Validator-Logik
- **File:** `src/app/metric_catalog.py` — Metrikkatalog mit `col_label`-Feldern
- **File:** `api/routers/config.py` — GET `/api/metrics` Response
- **File:** `frontend/src/lib/types.ts` — TypeScript-Interface `MetricEntry`
- **File:** `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` — Mail-Vorschau
- **File:** `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` — Metrik-Reihenfolge-UI

## Estimated Scope

- **LoC:** ~−10 netto (EN-Blacklist-Entfernung überwiegt neue API-Felder)
- **Files:** 10
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `briefing_mail_validator.py` | tool | Prüft zugestellte Briefing-Mails gegen Spec — EN-Blacklist wird entfernt |
| `MetricDefinition.col_label` | Python | Kurzes Spaltenkürzel (z.B. "W", "Gust", "Thdr") — Single Source of Truth |
| `GET /api/metrics` | Go-API | Liefert Metrik-Definitionen an Frontend — wird um `col_label` erweitert |
| `MetricEntry` | TypeScript | Frontend-Typ für API-Antwort — erhält optionales `col_label` |
| `WeatherV2MailPreview.svelte` | Frontend | Mail-Vorschau nutzt `shortOf()` — wird auf `col_label` umgestellt |
| `WeatherV2Reihenfolge.svelte` | Frontend | Metrik-Reihenfolge-UI — zeigt `col_label` als Badge neben Langname |

## Implementation Details

### #862 — EN-Blacklist aus Validator entfernen

In `.claude/hooks/briefing_mail_validator.py`:
- Zeile 42: Konstante `_EN_BLACKLIST = ("Gust", "Rain", "Sun", "Feels", "Cloud", "Thunder", "Visib", "Humid")` entfernen
- Zeilen 197–204: Funktion `def _check_localization(html: str)` vollständig entfernen
- Zeile 362: `errors.extend(_check_localization(html))` entfernen

Hintergrund: Spaltenköpfe bleiben bewusst englisch (PO-Entscheidung). Die Funktion war ein fehlgeleitetes AC-5 aus Issue #833 und hat korrekte E-Mails als fehlerhaft markiert.

### #849a — Zwei fehlerhafte `col_label`-Werte im Metrikkatalog

In `src/app/metric_catalog.py`:
- Z. 195: `col_label="Blitz"` → `col_label="Thdr"` (thunder-Metrik, jetzt konsistent mit EN-Konvention)
- Z. 185: `col_label="Sicherheit"` → `col_label="Conf"` (confidence-Metrik; ist `selectable=false` und wird im Render-Pfad ignoriert, aber Konsistenz im Katalog ist Pflicht)

### #849b — API um `col_label` erweitern

In `api/routers/config.py` (~Z. 44): Im Response-Dictionary der Metrik-Einträge `"col_label": m.col_label` hinzufügen. Damit kennt das Frontend das kurze Kürzel ohne eigene Abschneide-Logik.

In `frontend/src/lib/types.ts` (~Z. 150): `col_label?: string` zu Interface `MetricEntry` hinzufügen (optional, für Rückwärtskompatibilität).

In `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` (~Z. 70): Die `shortOf()`-Hilfsfunktion, die bisher `m.label` auf 6 Zeichen abschnitt, auf `m.col_label ?? m.label` umstellen. Damit stimmen E-Mail und Vorschau überein.

### #849c — `col_label`-Badge in Metrik-Reihenfolge-UI

In `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` (~Z. 60): Unter dem vollen deutschen Metrik-Namen (`m.label`) das Kürzel `m.col_label` als kleinen Badge/Tag einblenden. Kontext: Der User sieht im Reihenfolge-Dialog "Temperatur" und daneben das Badge "T" — so versteht er, was in der Mail-Spalte steht.

### Betroffene Tests

- `tests/unit/test_weather_metrics_ux.py`: Assertions für `col_label`-Werte aktualisieren
- `tests/tdd/test_forecast_confidence_output.py` Z. 151: `"Sicherheit"` → `"Conf"`
- `tests/tdd/test_bundle_771_796_787.py` Z. ~116–133: `"Blitz"` → `"Thdr"`
- `tests/tdd/test_horizon_filter.py` Z. ~254–257: `col_label`-Assertion aktualisieren

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | `_EN_BLACKLIST` + `_check_localization()` + Aufruf entfernen (Z. 42, 197–204, 362) |
| `src/app/metric_catalog.py` | MODIFY | `col_label="Blitz"` → `"Thdr"`, `col_label="Sicherheit"` → `"Conf"` (Z. 185, 195) |
| `api/routers/config.py` | MODIFY | `"col_label": m.col_label` zur `/api/metrics`-Response hinzufügen (~Z. 44) |
| `frontend/src/lib/types.ts` | MODIFY | `col_label?: string` zu `MetricEntry` hinzufügen (~Z. 150) |
| `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` | MODIFY | `shortOf()` nutzt `m.col_label ?? m.label` statt String-Abschneiden (~Z. 70) |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | MODIFY | `col_label`-Badge unter Metrik-Langname einblenden (~Z. 60) |
| `tests/unit/test_weather_metrics_ux.py` | MODIFY | `col_label`-Assertions aktualisieren |
| `tests/tdd/test_forecast_confidence_output.py` | MODIFY | `"Sicherheit"` → `"Conf"` (Z. 151) |
| `tests/tdd/test_bundle_771_796_787.py` | MODIFY | `"Blitz"` → `"Thdr"` (Z. ~116–133) |
| `tests/tdd/test_horizon_filter.py` | MODIFY | `col_label`-Assertion aktualisieren (Z. ~254–257) |

### Estimated Changes

- Files: 10
- LoC: ~−10 netto

## Acceptance Criteria

- **AC-1:** Given eine korrekte Staging-Briefing-Mail mit englischen Spaltenköpfen (z.B. "Gust", "Rain", "Thdr") / When `briefing_mail_validator.py` gegen diese Mail läuft / Then gibt der Validator Exit 0 zurück — kein Lokalisierungsfehler wird gemeldet, weil `_check_localization()` nicht mehr existiert
  - Test: Echter `briefing_mail_validator.py`-Lauf gegen Staging-Mail aus Stalwart-IMAP (`gregor-test@henemm.com`) — Exit-Code und Fehler-Liste prüfen

- **AC-2:** Given ein Briefing-Trip mit der thunder-Metrik / When eine Test-Mail über den Scheduler erzeugt und an `gregor-test@henemm.com` zugestellt wird / Then enthält die Mail die Spaltenüberschrift "Thdr" (nicht "Blitz") — prüfbar via IMAP-Abruf und `briefing_mail_validator.py`
  - Test: Echter Scheduler-Aufruf auf Staging → IMAP-Abruf → HTML-Parsing des `<th>`-Inhalts

- **AC-3:** Given ein eingeloggter Nutzer auf Staging in der Mail-Vorschau des Trip-Editors / When er die Wettertabelle im Vorschau-Tab sieht / Then stimmen die Spaltenköpfe exakt mit den Kürzeln in der zugestellten E-Mail überein — kein Abschneide-Artefakt wie "Temper" statt "T"
  - Test: Playwright-E2E gegen `https://staging.gregor20.henemm.com` als eingeloggter Nutzer — Spaltenköpfe im Vorschau-Tab vs. Spaltenköpfe in der Staging-Mail vergleichen

- **AC-4:** Given ein eingeloggter Nutzer im Metrik-Reihenfolge-Dialog / When er die Metrik-Liste sieht / Then zeigt jede Metrik neben dem deutschen Langnamen (z.B. "Böen") das kurze Kürzel als Badge (z.B. "Gust"), damit der Bezug zur Mail-Spalte klar ist
  - Test: Playwright-E2E gegen `https://staging.gregor20.henemm.com` — Reihenfolge-Dialog öffnen, Badge-Text neben mindestens einer Metrik prüfen

- **AC-5:** Given GET `/api/metrics` auf Staging / When ein HTTP-Call gegen `https://staging.gregor20.henemm.com/api/metrics` gemacht wird / Then enthält jedes Metrik-Objekt in der Antwort das Feld `col_label` mit einem nicht-leeren String — kein Metrik-Eintrag hat `col_label: null` oder ein fehlendes Feld
  - Test: Echter HTTP GET, JSON-Response parsen, alle Einträge auf `col_label`-Vorhandensein prüfen

- **AC-6:** Given `uv run pytest tests/unit/test_weather_metrics_ux.py tests/tdd/test_forecast_confidence_output.py tests/tdd/test_bundle_771_796_787.py tests/tdd/test_horizon_filter.py` / When alle vier Test-Dateien lokal ausgeführt werden / Then laufen alle Tests grün durch — keine stale `"Blitz"`- oder `"Sicherheit"`-Assertions schlagen fehl
  - Test: Direkter pytest-Aufruf, Exit-Code 0, kein FAILED in Output

## Known Limitations

- `confidence`-Metrik hat `selectable=false` und wird im Render-Pfad ignoriert; das `col_label="Conf"`-Update ist reine Katalog-Konsistenz und hat keine sichtbare Auswirkung auf E-Mails oder Vorschau.
- Der `col_label`-Badge in `WeatherV2Reihenfolge.svelte` ist nur informativ und hat keine Auswirkung auf die Metrik-Auswahl oder Reihenfolge-Logik.
- `briefing_mail_validator.py` prüft ausschließlich Trip-Briefing-Mails — der `email_spec_validator.py` (Orts-Vergleich) ist von diesem Fix nicht betroffen.

## Changelog

- 2026-06-23: Initial spec erstellt — Issues #862 + #849, Workflow fix-862-849-col-labels
