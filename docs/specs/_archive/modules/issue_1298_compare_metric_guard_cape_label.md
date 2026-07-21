---
entity_id: issue_1298_compare_metric_guard_cape_label
type: bugfix
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [compare, cape, metric-guard, label-rename]
---

# Metrik-Wächter reparieren + CAPE-Einfärbung + Label-Vereinheitlichung (#1298)

## Approval

- [ ] Approved

## Purpose

Drei kleine, lokal begrenzte Härtungen im Ortsvergleich (Scheiben B2+B3 aus
Paket #1301): CAPE bekommt in der Vergleichsmatrix eine Farb-Ampel wie die
übrigen Metriken, der strukturelle Metrik-Wächter-Test wird von einer
blinden Hand-Kopie auf einen echten Parser gegen die Frontend-Quelle
umgestellt (damit eine künftige 16. Metrik ohne Renderer-Mapping tatsächlich
rot wird), und das Anzeige-Label "Frostgrenze" wird produktweit auf
"Nullgradgrenze" vereinheitlicht (PO-Entscheid 2026-07-17).

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `def _sev_wind` (Vorbild, Zeile 85-91), `CV2_METRICS` (Zeile 193-218)
- **File:** `tests/unit/test_compare_metric_catalog_consistency.py`
- **Identifier:** `ALL_METRICS_FRONTEND_IDS` (Zeile 33-49)
- **File:** `frontend/src/lib/components/compare/compareMetricDefs.ts`
- **Identifier:** `FREEZING_LVL`, `ALL_METRICS` (Zeile 46, 54-58)
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** `_DAILY_PLAIN_ROWS` (Zeile 41-51)

Alle betroffenen Dateien sind Python-Core (`src/app/`, `src/output/`,
`tests/unit/`) bzw. SvelteKit-Frontend (`frontend/src/lib/components/compare/`)
— keine Go-API/`internal/`-Berührung.

## Estimated Scope

- **LoC:** ~70-90 (Produktivcode ~15, Testcode/Parser ~55-70, Label-Renames ~5)
- **Files:** 6 (`compare_html.py`, `comparison.py`, `compareMetricDefs.ts`,
  `test_compare_metric_catalog_consistency.py`, neuer `tests/unit/_ts_metric_parser.py`,
  `test_compare_extra_daily_metrics.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::MetricDefinition(id="cape")` | module | Liefert `display_thresholds` für die CAPE-Ampel (nur gelesen, unverändert) |
| `src/output/metric_format.py::severity_for` | function | Kanonisches Ampel-Band aus Katalog-Schwellen (nur gelesen, unverändert) |
| `src/output/renderers/compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID` | module | Referenzmenge, gegen die der gehärtete Wächter prüft (nur gelesen, unverändert) |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | module | Quelle der 15 wählbaren Metrik-IDs + des Frostgrenze-Labels |

## Implementation Details

**B2 — CAPE-Einfärbung (`compare_html.py`):**
```
def _sev_cape(v: float) -> str:
    return _CANONICAL_TO_COMPARE.get(severity_for("cape", v), "ok")
```
Direkt neben `_sev_wind` (Zeile 85-91) ergänzt — identisches Muster, kein
hartcodierter Schwellenwert, ausschließlich `severity_for("cape", v)` gegen
`metric_catalog.py:258` (`display_thresholds={"yellow":1000,"orange":2500,"red":3500}`).
`severity_for` ist bereits importiert (Zeile 39), keine neue Abhängigkeit.
`CV2_METRICS`-Eintrag `cape_max` (Zeile 216) bekommt `"sev": _sev_cape`. Der
Kommentar Zeile 210-213 ("cape_max/freezing_level ebenfalls ohne 'sev'") wird
angepasst, da er für CAPE nach dem Fix nicht mehr zutrifft.

**B3 — Metrik-Wächter-Härtung (`tests/unit/test_compare_metric_catalog_consistency.py`):**
Neue Hilfsfunktion `tests/unit/_ts_metric_parser.py::parse_all_metrics_ids(path)`
liest `compareMetricDefs.ts` und extrahiert per Regex:
1. `const NAME: MetricDef = { ..., key: 'xxx', ... };` → Mapping `NAME -> 'xxx'`.
2. Das `ALL_METRICS`-Array (Zeile 54-58) → Liste von `NAME`-Referenzen in
   Deklarationsreihenfolge, aufgelöst zu Keys über das Mapping aus Schritt 1.

`ALL_METRICS_FRONTEND_IDS` (Hand-Kopie, Zeile 33-49) wird durch den
Parser-Aufruf gegen die reale Datei ersetzt. Ein neuer Vakuum-Schutz-Test
stellt sicher, dass der Parser auf der echten Datei exakt 15 IDs findet
(nicht 0) — ein leerer/kaputter Parser darf den Wächter nicht fälschlich
grün erscheinen lassen. Ein zweiter neuer Test beweist die Wächter-Wirkung
direkt: er hält eine künstlich um eine ID reduzierte Kopie von
`FRONTEND_TO_RENDERER_METRIC_ID` gegen die geparste Menge und erwartet ein
`AssertionError` — Nachweis, dass der Vergleich bei einer Lücke tatsächlich
rot wird (nicht nur bei zufälliger Übereinstimmung grün bleibt).

**Label-Rename "Frostgrenze" → "Nullgradgrenze":**
1. `compare_html.py:217` — `"label": "Frostgrenze"` → `"Nullgradgrenze"`.
2. `comparison.py:50` — `("freezing_level", "Frostgrenze", ...)` → `"Nullgradgrenze"`.
3. `compareMetricDefs.ts:46` — `FREEZING_LVL.label: 'Frostgrenze'` → `'Nullgradgrenze'`.
4. `metric_catalog.py:391`/`:400` (`label_de`/`alert_label="Nullgradgrenze"`)
   ist bereits korrekt — keine Änderung nötig, nur die drei renderer-lokalen
   Hardcodes ziehen nach.
5. `tests/unit/test_compare_extra_daily_metrics.py`: `_IS_FREEZING`-Lambda
   (Zeile 152, sucht `"frostgrenze" in l`) und alle Literalvorkommen
   "Frostgrenze" in Assertions/Docstrings (u.a. Zeile 237, 243, 330, 332)
   synchron auf "nullgradgrenze"/"Nullgradgrenze" umstellen — dieser Test
   ist heute grün und darf durch den Rename nicht brechen (Kern-Testpolitik:
   100% grün).
6. Die Daten-ID `freezing_level_m`/`freezing_level` bleibt in allen Dateien
   unverändert — nur das Anzeige-Label wechselt.

## Expected Behavior

- **Input (B2):** CAPE-Tageswert eines Ortes in der Vergleichsmatrix
  (z.B. 2800 J/kg).
- **Output (B2):** Die CAPE-Zelle bekommt die Ampel-Klasse `warn` (orange,
  da ≥2500 und <3500 laut `display_thresholds`) statt der bisher
  unfarbigen Standarddarstellung.
- **Input (B3):** `compareMetricDefs.ts::ALL_METRICS` enthält eine ID ohne
  Eintrag in `FRONTEND_TO_RENDERER_METRIC_ID`.
- **Output (B3):** `test_all_frontend_metric_ids_have_renderer_mapping`
  schlägt fehl und benennt die fehlende ID — vorher (Hand-Kopie) hätte der
  Test dies nur erkannt, wenn jemand die Kopie synchron mitgepflegt hätte.
- **Input (Label):** Vergleichs-Mail (HTML und Klartext) sowie
  Compare-Editor-Metrikliste im Frontend.
- **Output (Label):** Alle drei zeigen "Nullgradgrenze" statt "Frostgrenze";
  keine funktionale Änderung an Werten/IDs.
- **Side effects:** Renderer-Commit-Gate #811 greift bei
  `compare_html.py`-Änderung — vor Commit `tests/tdd/test_issue_811_mode_matrix.py`
  grün und `briefing_mail_validator.py`-Lauf gegen echte Staging-Mail
  (`X-GZ-Mail-Type: compare`) Pflicht.

## Acceptance Criteria

- **AC-1:** Given ein Ort mit CAPE-Tageswert im orange-Band (≥2500, <3500
  J/kg laut Katalog-Schwellen) / When die Vergleichs-Mail (HTML) gerendert
  wird / Then zeigt die CAPE-Zeile für diesen Ort dieselbe Farb-Klasse
  (`warn`), die `severity_for("cape", v)` liefert — analog zur bestehenden
  Wind-Einfärbung, ohne neuen hartcodierten Schwellenwert.
  - Test: `render_compare_html()` mit einem Ergebnis, dessen CAPE-Wert im
    orange-Band liegt, aufrufen und die tatsächlich gerenderte
    Ampel-Farbklasse der CAPE-Zeile prüfen (nicht nur, dass ein `sev`-Key
    im Dict steht).

- **AC-2:** Given `compareMetricDefs.ts::ALL_METRICS` enthält (simuliert)
  eine 16. Metrik-ID, die nicht in `FRONTEND_TO_RENDERER_METRIC_ID` steht /
  When der gehärtete Metrik-Wächter-Test läuft / Then schlägt er mit einer
  Meldung fehl, die die fehlende ID benennt — der Parser selbst liefert auf
  der echten `compareMetricDefs.ts` nachweislich alle 15 realen IDs (nicht
  0), sodass ein kaputter Parser den Wächter nicht fälschlich grün erscheinen
  lässt.
  - Test: zwei Tests — (a) Vakuum-Schutz: Parser gegen die reale
    `compareMetricDefs.ts` liefert exakt 15 IDs; (b) Wirkungsnachweis: eine
    künstlich um eine ID reduzierte Kopie von
    `FRONTEND_TO_RENDERER_METRIC_ID` gegen die geparste Menge geprüft löst
    tatsächlich einen `AssertionError` aus.

- **AC-3:** Given ein Nutzer betrachtet die Vergleichs-Mail (HTML und
  Klartext) oder die Metrikauswahl im Compare-Editor / When die
  Frostgrenze-Metrik angezeigt wird / Then lautet das sichtbare Label
  überall "Nullgradgrenze" (nicht mehr "Frostgrenze"), während die
  zugrundeliegende Daten-ID `freezing_level_m`/`freezing_level` unverändert
  bleibt.
  - Test: `render_compare_html()` und `render_comparison_text()` mit
    aktivierter Frostgrenze-Metrik aufrufen und prüfen, dass der
    gerenderte Text "Nullgradgrenze" enthält und "Frostgrenze" nicht mehr
    vorkommt; bestehender Test `test_compare_extra_daily_metrics.py`
    (`_IS_FREEZING`, betroffene Assertions) läuft nach der Anpassung
    weiterhin grün.

## Known Limitations

- Der TS-Parser (`tests/unit/_ts_metric_parser.py`) ist bewusst
  regex-basiert und deckt nur das aktuelle Ein-Zeile-pro-Konstante-Format
  von `compareMetricDefs.ts` ab (`const NAME: MetricDef = { ... key: 'xxx' ... };`
  gefolgt von einem `ALL_METRICS`-Array aus Namensreferenzen). Kein
  vollständiger TypeScript-Parser — das ist eine bewusste, dokumentierte
  Grenze (deckt sich mit der bisherigen "kein Cross-Language-Tooling"-Vorgabe
  im Testkommentar). Bricht das TS-Dateiformat grundlegend um (z.B.
  Mehrzeilen-Objektliterale, Spread-Syntax im Array), muss der Parser
  nachgezogen werden — der Vakuum-Schutz-Test macht ein stilles Versagen in
  diesem Fall sichtbar (0 statt 15 gefundene IDs).
- B3 ändert kein Verhalten am Renderer-Mapping selbst — die Hand-Kopie und
  der Parser liefern heute dieselben 15 IDs (Mapping ist seit #1296
  vollständig). Es ist ein reiner Guard-Härtungs-Fix, kein Bugfix am
  Mapping.
- CAPE-Einfärbung nutzt ausschließlich die bestehenden Katalog-Schwellen;
  eine fachliche Neubewertung der CAPE-Schwellenwerte selbst ist nicht Teil
  dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kleine, lokal begrenzte Änderung ohne Architekturwandel —
  eine neue Severity-Helferfunktion nach bereits etabliertem Muster
  (`_sev_wind`), ein Test-Parser als reines Test-Tooling, drei
  String-Literal-Renames. Kein neues Modul, kein neuer Datenfluss, keine
  Schema-Änderung.

## Changelog

- 2026-07-17: Initial spec created
