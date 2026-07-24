---
entity_id: rework_1351_compare_catalog
type: module
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [compare, metric_catalog, wind_chill, channel_layouts, epic_1230]
---

<!-- Issue #1351 — Epic #1230 — Scheibe 3 der Compare-Metrik-Angleichung -->

# Rework #1351 — Compare-Metrik-Angleichung: Gefühlte Höchsttemperatur + channel_layouts-Ballast

## Approval

- [ ] Approved

## Purpose

Zwei unabhängige Teile derselben Aufräum-Scheibe (Epic #1230, Compare/Trip-Konvergenz):

1. **Gefühlte Höchsttemperatur** (`wind_chill_max_c`) wird intern bereits berechnet, ist aber weder
   im Trip- noch im Compare-Metrik-Katalog wählbar/anzeigbar — analog zur normalen Temperatur, die
   min UND max anbietet, fehlt bei „Gefühlte Temperatur" die max-Variante vollständig.
2. **`channel_layouts`** round-trippt im Compare-Kontext unsichtbar mit, obwohl der Compare-Editor
   das Feld seit #1287/#1291 gar nicht mehr bedient. Toter Ballast im geteilten
   `display_config`-Modell wird entfernt, ohne den Trip-Pfad (wo `channel_layouts` eine echte
   Funktion ist) anzufassen.

## Source

- **File:** `src/app/metric_catalog.py` — `class MetricDefinition` Registry, Eintrag `id="wind_chill"` (Zeile ~101-112)
- **Identifier:** `_METRICS` Liste, `wind_chill`-Eintrag

> **Schicht-Hinweis:** Teil 1 betrifft Python-Core (`src/app/`, `src/services/`, `src/output/renderers/`) und Go-API nicht. Teil 2 betrifft Python-Core-Migrationsskript + Frontend (`frontend/src/lib/...`), keine Go-Änderung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py` | module | Berechnet `wind_chill_max_c` bereits (Zeile 766, 783-784) — Datenquelle für Teil 1 |
| `src/output/renderers/compare_metric_catalog.py` | module | Compare-Katalog (SSoT seit #1350), braucht neuen `wind_chill_max_c`-Eintrag |
| `src/output/renderers/compare_metric_ids.py` | module | `FRONTEND_TO_RENDERER_METRIC_ID` — Drift-assert erzwingt parallelen Eintrag zu compare_metric_catalog.py |
| `src/app/user.py` (`LocationResult`) | module | Datenmodell für Compare-Locations — braucht `wind_chill_max`-Feld |
| `src/services/comparison_engine.py` | module | Verdrahtet berechnete Werte in `LocationResult` — max wird bereits berechnet (Z. 461-465), nur nicht durchgereicht |
| `src/output/renderers/email/helpers.py` | module | Trip-Pill-Renderer, hartkodierter `wind_chill`-Zweig |
| `src/output/renderers/email/compare_html.py` | module | Compare-HTML-Renderer, hartkodierter `wind_chill_min`-Eintrag |
| `src/output/renderers/comparison.py` | module | Compare-Plain/SMS-Renderer, hartkodierter `wind_chill_min`-Zweig |
| `scripts/migrate_1191_compare_active_metrics.py`, `scripts/migrate_1244_null_lists.py` | pattern | Vorbild für idempotente Presets-Migration (Teil 2) |
| `.claude/hooks/data_schema_backup.py` | hook | Automatischer Pre-Snapshot bei Persistenz-Edits (greift bei Migrations-Skript) |
| `src/services/report_config_resolver.py` | module | Compare-Resolver — ignoriert `channel_layouts` bereits, bleibt unverändert (Teil 2 Regressionsschutz) |
| `frontend/src/lib/.../compareEditorSave.ts`, `compareWizardState.svelte.ts`, `compareHubWizardBridge.ts` | frontend | Round-Trip-Stellen für `channelLayouts`, die in Teil 2 entfernt werden |

## Estimated Scope

- **LoC:** ~180-230 (Teil 1 ~120-150, Teil 2 ~60-80) — siehe Abschnitt „Umfang/Risiken"
- **Files:** ~14 (9 Teil 1, 5 Teil 2, plus 2-3 Testdateien)
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/metric_catalog.py` | MODIFY | `wind_chill`: `default_aggregations` um `"max"` erweitern, `summary_fields` um `"max": "wind_chill_max_c"` ergänzen; `is_precursor`/ADR-0010-Eigenschaft erhalten |
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | Neuer Eintrag `wind_chill_max_c` (Vorbild `temp_max_c`) |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | Paralleler Eintrag `wind_chill_max_c` in `FRONTEND_TO_RENDERER_METRIC_ID`, sonst schlägt der Drift-assert fehl |
| `src/app/user.py` | MODIFY | `LocationResult`: neues Feld `wind_chill_max` |
| `src/services/comparison_engine.py` | MODIFY | `wind_chill_max` aus bereits berechnetem Wert (Z. 461-465) in `LocationResult` verdrahten (analog Z. 250, 314 für min) |
| `src/output/renderers/email/helpers.py` | MODIFY | Trip-Pill: `wind_chill`-Zweig um max-Fall ergänzen |
| `src/output/renderers/email/compare_html.py` | MODIFY | Compare-HTML: neuer Eintrag „Gefühlte Temp. max" analog Zeile 245 |
| `src/output/renderers/comparison.py` | MODIFY | Compare-Plain/SMS: max-Zweig analog Zeile 150-152 |
| `frontend/src/lib/.../compareEditorSave.ts` | MODIFY | `channelLayouts`-Round-Trip entfernen (Zeile ~88-89) |
| `frontend/src/lib/.../compareWizardState.svelte.ts` | MODIFY | `channelLayouts`-Feld aus Compare-State entfernen (Zeile ~132) |
| `frontend/src/lib/.../compareHubWizardBridge.ts` | MODIFY | `channelLayouts`-Bridge-Übergabe im Compare-Pfad entfernen (Zeile ~111) |
| `scripts/migrate_1351_drop_compare_channel_layouts.py` | CREATE | Idempotente Migration: entfernt `channel_layouts` aus bestehenden Vergleichs-Presets (`briefings/` kind=vergleich) |
| `tests/tdd/test_wind_chill_max_selectable.py` (oder passendes Modul-Suite-Ziel) | CREATE | RED/GREEN-Nachweis Teil 1 |
| `tests/tdd/test_compare_drops_channel_layouts.py` (oder passendes Modul-Suite-Ziel) | CREATE | RED/GREEN-Nachweis Teil 2 |

## Implementation Details

### Teil 1 — Gefühlte Höchsttemperatur

**Katalog-Erweiterung** (`metric_catalog.py`, Vorbild `temperature`-Eintrag Zeile 77-86):

```
default_aggregations=("min", "max"),
summary_fields={"min": "wind_chill_min_c", "max": "wind_chill_max_c"},
```

Die Vorboten-Eigenschaft (`default_change_threshold=None`, `risk_thresholds`, ADR-0010) bleibt für
beide Aggregationen erhalten — `wind_chill` ist und bleibt eine Metrik ohne Abweichungs-Alert.

**Compare-Katalog** (`compare_metric_catalog.py`, Vorbild `temp_max_c`-Eintrag): neuer Dict-Eintrag
`{"key": "wind_chill_max_c", "label": "Gefühlte Temp. max", "unit": "°C", "decimals": 0,
"higherIsBetter": True, "kind": "range", "rangeMin": -20, "rangeMax": 45, "step": 1}` — Wertebereich
an `temp_max_c` angelehnt (nicht an `wind_chill_min_c`, da die Höchstwert-Verteilung wärmer liegt).

**Paralleler Eintrag** in `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`:
`"wind_chill_max_c": "wind_chill_max"` (Vorbild Zeile 15/45 für `_min`). Ohne diesen Eintrag schlägt
der Drift-assert in `compare_metric_catalog.py` (Zeile 92-97) beim Modulimport fehl — das ist so
gewollt (verhindert stille Divergenz wie #1324).

**Datenpfad:** `LocationResult` (`user.py` Zeile ~133) erhält `wind_chill_max: float | None`.
`comparison_engine.py` verdrahtet den bereits berechneten `wind_chill_max_c`-Wert (Zeile 461-465)
analog zum bestehenden `wind_chill_min`-Pfad (Zeile 250, 314).

**Renderer** (drei hartkodierte Stellen, je ein zusätzlicher max-Zweig neben dem bestehenden
min-Zweig, kein genereller Refactor der min/max-Iteration):
- `email/helpers.py` Zeile ~1233-1242 (Trip-Pill)
- `email/compare_html.py` Zeile ~245 (Compare-HTML)
- `comparison.py` Zeile ~150-152 (Compare-Plain/SMS)

**Auswahl-UI:** Kein Frontend-Änderungsbedarf für die Metrik-Auswahl selbst — `/api/compare/metrics`
liefert den Katalog direkt an `WeatherMetricsTab.svelte` (SSoT seit #1350). Die Auswahlliste zeigt
den neuen Eintrag automatisch, sobald der Backend-Katalog ihn führt.

### Teil 2 — channel_layouts-Ballast entfernen

**Frontend:** Die drei Round-Trip-Stellen (`compareEditorSave.ts`, `compareWizardState.svelte.ts`,
`compareHubWizardBridge.ts`) hören auf, `channelLayouts` beim Speichern/Laden eines Vergleichs
mitzuführen. Kein Compare-`.svelte`-Component schreibt das Feld aktuell — es wird nur entfernt, wo
es transportiert wird.

**Backend-Migration:** Einmaliges, idempotentes Skript (Vorbild `migrate_1191_compare_active_metrics.py`,
`migrate_1244_null_lists.py`) entfernt `channel_layouts` aus allen Vergleichs-Presets in `briefings/`
(kind=vergleich). Idempotenz-Check: Skript darf mehrfach laufen ohne Fehler, wenn das Feld bereits
fehlt. Der Pre-Snapshot-Hook `data_schema_backup.py` greift automatisch bei Persistenz-Edits.

**Regressionsschutz:** `report_config_resolver.py` (Compare-Resolver, Zeile 227-234) liest
`channel_layouts` bereits nicht — bleibt unverändert. Der Trip-Pfad (`trip_report.py`,
`channel_layout.py`, `models.py`) wird in dieser Scheibe NICHT angefasst.

## Expected Behavior

- **Input Teil 1:** Nutzer wählt im Compare-Editor (oder Trip-Editor) „Gefühlte Temp. max" als
  aktive Metrik aus einem Vergleichs- bzw. Trip-Preset.
- **Output Teil 1:** Vergleichs-Mail (HTML + Plain/SMS) und Trip-Briefing zeigen die gefühlte
  Höchsttemperatur als eigene Zeile/Spalte, unabhängig von der weiterhin verfügbaren Tiefsttemperatur.
- **Input Teil 2:** Nutzer speichert einen Vergleich im Editor; Migrations-Skript läuft einmalig gegen
  Bestandsdaten.
- **Output Teil 2:** Gespeicherte Vergleichs-Presets (neu UND migrierte Alt-Presets) enthalten kein
  `channel_layouts`-Feld mehr. Trip-Presets sind unverändert.
- **Side effects:** Migrations-Skript erzeugt einen Backup-Snapshot vor der Änderung (via
  `data_schema_backup.py`).

## Acceptance Criteria

- **AC-1:** Given ein Trip- oder Vergleichs-Preset, in dem der Nutzer „Gefühlte Temperatur" als
  Metrik ausgewählt hat / When er zusätzlich die Höchstwert-Variante auswählt / Then bietet die
  Metrik-Auswahl (Trip-Editor und Compare-Editor) „Gefühlte Temp. max" als eigene wählbare Option an,
  getrennt von der bestehenden Tiefstwert-Option.
  - Test: `/api/compare/metrics` liefert einen Eintrag mit Key `wind_chill_max_c`; die Trip-Metrik
    `wind_chill` erlaubt die Aggregation `max` im Katalog.

- **AC-2:** Given ein Vergleichs-Preset mit ausgewählter gefühlter Höchsttemperatur / When der
  Ortsvergleich per Mail versendet wird / Then zeigt die Vergleichs-Mail (HTML-Version) für jeden
  verglichenen Ort die gefühlte Höchsttemperatur als eigenen, benannten Wert.
  - Test: gegen echt zugestellte Staging-Mail via `email_spec_validator.py` (X-GZ-Mail-Type: compare)
    geprüft — kein Mock des Renderers.

- **AC-3:** Given dasselbe Vergleichs-Preset / When die kompakte Plain-/SMS-Variante der
  Vergleichs-Mail gerendert wird / Then erscheint die gefühlte Höchsttemperatur auch dort als
  eigener Wert, nicht nur in der HTML-Fassung.
  - Test: Unit-Test auf `comparison.py`-Renderer-Output mit einer Fixture, die `wind_chill_max_c`
    im Locationergebnis führt.

- **AC-4:** ~~Given ein Trip mit ausgewählter gefühlter Höchsttemperatur / When das Trip-Briefing
  (Mail) gerendert wird / Then erscheint die gefühlte Höchsttemperatur im Trip-Briefing als eigener
  Wert, analog zur bereits vorhandenen Tiefstwert-Darstellung.~~
  **AUSGEGLIEDERT nach #1357 (PO-Entscheidung 2026-07-24).** Grund: Im Trip existiert kein
  Auswahl-Pfad für Aggregationen — `MetricConfig.aggregations` wird nur serialisiert/geparst
  (`src/app/loader.py:156,772,806,839`), aber von keinem Renderer gelesen (0 Treffer in `src/`,
  `api/`); `build_metrics_summary_pills()` erhält ausschließlich Metrik-IDs
  (`src/output/renderers/email/html.py:1157`). Eine Anzeige ohne Auswahl-Signal würde die
  Höchsttemperatur ungefragt bei JEDEM Trip einblenden (Adversary-Finding F001, CRITICAL, brach 10
  golden-Tests). Trip-Pill daher auf Vorzustand zurückgebaut
  (`src/output/renderers/email/helpers.py:1233-1247`). Regressionsschutz verschärft:
  `tests/tdd/test_issue_912_pill_textformat.py::test_wind_chill_format_exact` prüft jetzt exakt
  statt per Substring.
  - Test: entfällt in dieser Scheibe — Nachweis erfolgt in #1357.

- **AC-5:** Given ein Trip- oder Vergleichs-Preset, das ausschließlich die gefühlte
  Tiefsttemperatur ausgewählt hat (kein max) / When Mails weiterhin versendet werden / Then bleibt
  die Darstellung der Tiefsttemperatur unverändert — keine Regression durch die neue max-Option.
  - Test: bestehender Renderer-Test/Fixture mit reiner min-Auswahl bleibt grün.

- **AC-6:** Given ein Nutzer speichert einen Vergleich im Compare-Editor / When das Preset danach
  aus dem Editor erneut geöffnet oder als Rohdaten betrachtet wird / Then enthält das gespeicherte
  Vergleichs-Preset kein `channel_layouts`-Feld mehr.
  - Test: End-to-End über Compare-Save-API — gespeichertes Preset-JSON wird auf Abwesenheit des
    Feldes geprüft (kein Dateiinhalt-String-Grep, sondern strukturierter Feldvergleich).

- **AC-7:** Given bestehende Vergleichs-Presets aus der Zeit vor dieser Änderung / When das
  Migrations-Skript einmalig ausgeführt wird / Then verlieren alle betroffenen Presets ihr
  `channel_layouts`-Feld, ein Backup-Snapshot der Vorher-Daten existiert, und ein erneuter Lauf des
  Skripts verändert nichts mehr (Idempotenz).
  - Test: Migrations-Skript zweimal hintereinander gegen dieselben Test-Fixture-Presets laufen
    lassen — zweiter Lauf meldet „nichts zu tun" und ändert keine Datei.

- **AC-8:** Given ein bestehender Trip mit konfigurierten `channel_layouts` (z.B. unterschiedliche
  Metriken für E-Mail vs. SMS) / When das Trip-Briefing gerendert wird / Then funktioniert die
  Kanal-spezifische Metrikauswahl weiterhin unverändert — die Compare-Bereinigung wirkt sich nicht
  auf Trips aus.
  - Test: bestehender Trip-Channel-Layout-Test bleibt grün, ergänzt um einen Lauf nach der Migration.

## Known Limitations

- Der Wertebereich (`rangeMin`/`rangeMax`) für `wind_chill_max_c` im Compare-Katalog ist eine
  begründete Schätzung (angelehnt an `temp_max_c`), keine empirisch kalibrierte Grenze — bei Bedarf
  in einer separaten Kalibrierungs-Runde nachschärfen.
  - Test: `pytest tests/tdd/test_wind_chill_max_selectable.py`
- Teil 2 betrifft ausschließlich Vergleichs-Presets; sollte in Zukunft doch eine Kanal-spezifische
  Metrikauswahl für Compare gewünscht werden, ist das eine neue Spec (widerspricht aktuell #1287/#1291
  und der Konvergenz-Richtung, siehe Context-Doc).
- Keine aktiven Produktiv-Nutzer zum Zeitpunkt der Migration — das Migrationsrisiko ist damit real
  minimal, unabhängig von der Testabdeckung.

## Umfang/Risiken

Teil 1 und Teil 2 zusammen nähern sich dem 250-LoC-Limit pro Workflow (Schätzung ~180-230 LoC ohne
Tests). Beide Teile sind bewusst minimal gehalten:
- Kein genereller Refactor der hartkodierten min/max-Renderer-Zweige zu einer generischen
  Iteration über `summary_fields` — das wäre ein separates Aufräum-Vorhaben.
- Teil 2 beschränkt sich auf Entfernen + Migration, keine Erweiterung des `display_config`-Modells.
- Sollte die Umsetzung während `/40-tdd-red` oder `/50-implement` absehbar über 250 LoC hinauswachsen,
  ist die Entscheidung „`workflow.py set-field loc_limit_override 500`" explizit beim PO einzuholen
  (siehe `feedback_no_loc_override_without_permission`), NICHT automatisch zu setzen.
- Alternative bei Überschreitung: Teil 1 und Teil 2 in zwei separate Workflows/Commits aufteilen
  (beide sind fachlich unabhängig voneinander).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Teil 1 erweitert ein bestehendes Muster (min/max-Aggregation, wie bei `temperature`
  bereits etabliert) ohne neue Architekturentscheidung. Teil 2 ist eine PO-Entscheidung (2026-07-24,
  dokumentiert im Context-Doc `docs/context/rework-1351-compare-catalog.md`), keine
  Grundsatzentscheidung im Sinne der ADR-Kategorien (Kanäle, Provider, Datenmodell/Persistenz-Strategie,
  Auth, Editor-Paradigma, Test-/Deploy-Strategie) — sie entfernt lediglich ungenutzten Ballast aus
  einem bestehenden, bereits per ADR/Issue entschiedenen Feld (channel_layouts bleibt Trip-only,
  #1287/#1291 hat das Compare-Editing bereits entschieden).

## Changelog

- 2026-07-24: Initial spec erstellt — Issue #1351, Epic #1230, Scheibe 3 der Compare-Metrik-Angleichung
- 2026-07-24: AC-4 nach #1357 ausgegliedert (PO-Entscheidung). Adversary-Findings behoben: F001 (Trip-Pill
  auf Vorzustand zurückgebaut, golden-Tests wieder grün), F002 (Compare-Save entfernt `channel_layouts`
  aktiv statt es weiterzureichen), F003 (Frontend-Fallback-Liste ergänzt + Paritäts-Test gegen Backend-Katalog).
