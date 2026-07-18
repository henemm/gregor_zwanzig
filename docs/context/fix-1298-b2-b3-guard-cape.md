# Context + Analyse: fix-1298-b2-b3-guard-cape

## Request Summary
Issue #1298 (Scheiben B2+B3 aus Paket #1301): (1) der Metrik-Wächter-Test
`test_compare_metric_catalog_consistency.py` pflegt eine Hand-Kopie der 15
`ALL_METRICS`-IDs statt sie aus `compareMetricDefs.ts` zu lesen — bei einer
16. Metrik ohne Renderer-Mapping bleibt er fälschlich grün. (2) Die
CAPE-Zeile in der Vergleichs-Matrix hat keine Farb-Schwelle, obwohl der
Katalog welche definiert. (3) "Frostgrenze" → "Nullgradgrenze" (PO-Entscheid
2026-07-17), nur das Anzeige-Label, nicht die ID `freezing_level_m`.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/unit/test_compare_metric_catalog_consistency.py` | B3: Hand-Kopie (Zeile 33-49) durch TS-Parser gegen `compareMetricDefs.ts::ALL_METRICS` ersetzen, inkl. Vakuum-Schutz-Selbsttest |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | Quelle der 15 Metrik-IDs (`ALL_METRICS`, Zeile 54-58) + Label „Frostgrenze" (Zeile 46) |
| `src/output/renderers/compare_metric_ids.py` | `FRONTEND_TO_RENDERER_METRIC_ID` (bereits alle 15 IDs enthalten — Mapping selbst ist NICHT kaputt, nur der Wächter ist blind für künftige Lücken) |
| `src/output/renderers/email/compare_html.py` | B2: `_sev_wind` (Zeile 85-91) als Vorbild für `_sev_cape`; CAPE-Zeile ohne `sev` (Zeile 216); Label „Frostgrenze" (Zeile 217) |
| `src/app/metric_catalog.py` | CAPE-Schwellen `display_thresholds={"yellow":1000,"orange":2500,"red":3500}` (Zeile 258, `id="cape"`); `freezing_level` Katalogeintrag mit `alert_label="Nullgradgrenze"` (Zeile 391-400) |
| `src/output/metric_format.py` | `severity_for(metric_id, value)` — liest Katalog-Schwellen, `None` bei fehlenden Schwellen oder `value=None` |
| `src/output/renderers/comparison.py` | **Zusatzfund (nicht im Issue-Text, aber PO „überall"):** Klartext-Renderer `_DAILY_PLAIN_ROWS` (Zeile 50) hat ebenfalls "Frostgrenze" hart im Label |
| `tests/unit/test_compare_extra_daily_metrics.py` | Bestehender Test nutzt Label-String "Frostgrenze" für Matching (`_IS_FREEZING` Zeile 152, Assertions Zeile 243/330) — muss mit umbenannt werden, sonst bricht ein bislang grüner Test |

## Existing Patterns
- **Sev-Funktion nach Katalog-Schwellen:** `_sev_wind` (`compare_html.py:85-91`) ist exakt das Vorbild für `_sev_cape` — `_CANONICAL_TO_COMPARE.get(severity_for("cape", v), "ok")`. Kein hartcodierter Schwellenwert, liest ausschließlich den Katalog.
- **`sev`-Feld ist optional in den Metrik-Dicts** (`CV2_METRICS`/`HOUR_METRICS`) und wird über `m.get("sev")` konsumiert (Zeile 409, 573) — Hinzufügen ist rückwärtskompatibel, keine Downstream-Änderung nötig.
- **TS-Konstanten-Parsing:** `compareMetricDefs.ts` ist ein einfaches, konsistentes Ein-Zeile-pro-Konstante-Format (`const NAME: MetricDef = { ..., key: 'xxx', ... };`) plus ein `ALL_METRICS`-Array aus Konstantennamen. Regex-Extraktion (Name→key-Mapping, dann Array-Reihenfolge auflösen) ist ausreichend — kein echter TS-Parser nötig, deckt sich mit „kein Cross-Language-Tooling"-Vorgabe aus dem bestehenden Test-Kommentar.

## Dependencies
- Upstream: `metric_catalog.py` (Schwellen), `metric_format.severity_for` (Ampel-Logik) — beide unverändert, nur gelesen.
- Downstream: Vergleichs-Mail (HTML + Klartext), Renderer-Commit-Gate #811 greift bei `compare_html.py`-Änderung → vor Commit `tests/tdd/test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf gegen echte Staging-Mail (`X-GZ-Mail-Type: compare`) Pflicht.

## Existing Specs
- `docs/specs/modules/issue_1296_compare_metrics_dropped.md` — Vorgänger-Spec des Wächter-Tests, AC-6 ist die Baseline, die B3 härtet.
- `docs/specs/modules/model_metric_fallback.md` — nicht direkt betroffen (A1/A2-Scope).

## Risks & Considerations
- **Renderer-Gate #811:** Commit von `compare_html.py` blockiert ohne frischen Mode-Matrix-Test + Mail-Validator-Lauf — beide vor Commit einplanen.
- **Label-Rename-Vollständigkeit:** Drei Fundstellen für "Frostgrenze" (HTML-Renderer, Klartext-Renderer, Frontend-Konstante), nicht nur die zwei im Issue-Text genannten — sonst uneinheitlich zwischen HTML- und Klartext-Teil derselben Mail.
- **Bestehender Test bricht sonst:** `test_compare_extra_daily_metrics.py` erwartet aktuell den String "Frostgrenze" — muss synchron umbenannt werden (kein neuer Test, Anpassung an bestehendem).
- **B3-Parser-Vakuum-Schutz:** Muss selbst testen, dass der Parser bei kaputtem/leerem Pfad nicht 0 IDs liefert und den Guard dadurch scheinbar erfüllt (false green) — Issue #1298 nennt das explizit als Pflichtbestandteil.
- **Kein Verhaltenswandel bei B3 selbst:** Die Hand-Kopie und der Parser sollten aktuell dieselben 15 IDs liefern (Mapping ist seit #1296 vollständig) — B3 ist ein reiner Guard-Härtungs-Fix, kein Bugfix am Mapping. Nachweis: Test für eine hypothetische 16. Metrik ohne Mapping muss ROT werden (heute bleibt die Hand-Kopie synchron und würde nicht triggern, aber das ist Ziel des Nachweis-Tests, nicht des Produktivpfads).

## Analyse: Technischer Ansatz

**B2 (CAPE-Einfärbung):**
1. `_sev_cape(v)` in `compare_html.py` neben `_sev_wind` ergänzen: `return _CANONICAL_TO_COMPARE.get(severity_for("cape", v), "ok")`.
2. `CV2_METRICS`-Eintrag `cape_max` um `"sev": _sev_cape` ergänzen.
3. Kommentar Zeile 210-213 anpassen (aktuell: "cape_max/freezing_level ebenfalls ohne 'sev'" — stimmt nach dem Fix nicht mehr für CAPE).

**B3 (Metrik-Wächter):**
1. Neue Hilfsfunktion (im Testmodul oder `tests/unit/_ts_metric_parser.py`) liest `compareMetricDefs.ts`, extrahiert `const NAME: MetricDef = { ... key: 'xxx' ... }`-Zuordnungen per Regex, löst dann `ALL_METRICS`-Array (Namensliste) zu Keys auf.
2. Vakuum-Schutz-Selbsttest: Parser muss auf der echten Datei > 0 IDs finden (z.B. `assert len(parsed) == 15` oder `assert len(parsed) > 0` mit Nachricht, die auf einen Pfad-/Parsing-Fehler hinweist).
3. `ALL_METRICS_FRONTEND_IDS` (Hand-Kopie) durch den Parser-Aufruf ersetzen; bestehende zwei Tests (`test_unmapped_metric_logs_warning...`, `test_all_frontend_metric_ids_have_renderer_mapping`) bleiben inhaltlich, nutzen aber die geparste Menge statt der Konstante.
4. Neuer Nachweis-Test (rot vor Fix wäre falsch hier, da B3 kein Bugfix ist — aber Nachweis-Pflicht laut Issue): ein Test, der zeigt, dass der Guard bei einer NICHT im Renderer-Mapping vorhandenen ID (simuliert, nicht die echte Datei) tatsächlich fehlschlägt — z.B. durch Parametrisierung/direkten Vergleich mit einer künstlich reduzierten Mapping-Kopie in einem isolierten Test, ODER (einfacher, robuster) ein Test, der `FRONTEND_TO_RENDERER_METRIC_ID` direkt gegen die geparste Menge hält und bei Diskrepanz rot wird — das ist strukturell bereits `test_all_frontend_metric_ids_have_renderer_mapping`, nur mit lebendiger statt toter Quelle.

**Label-Rename (Teil von B2/B3-Nachbarschaft, PO-Entscheid):**
1. `compare_html.py:217` Label → "Nullgradgrenze".
2. `comparison.py:50` Label → "Nullgradgrenze".
3. `compareMetricDefs.ts:46` Label → "Nullgradgrenze".
4. `tests/unit/test_compare_extra_daily_metrics.py`: `_IS_FREEZING`-Lambda (Zeile 152) und alle Literalvorkommen "Frostgrenze" in Assertions/Docstrings (Zeile 237, 243, 248, 254, 259, 330, 332) synchron auf "Nullgradgrenze" ändern.
5. ID `freezing_level_m` / `freezing_level` bleibt unverändert (nur Anzeige-Label).

## Nächster Schritt
`/30-write-spec` — Spec mit AC-N-Format (B2, B3, Label-Rename als getrennte ACs), danach User-Freigabe auf Deutsch.
