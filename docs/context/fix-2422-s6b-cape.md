# Context: fix-2422-s6b-cape

## Request Summary
PO-Entscheid 2026-10-01 (Henning): „CAPE aus der Roh/Einfach-Liste streichen". Bei der Staging-E2E von #2422 S6 war CAPE als Roh/Einfach-fähige SMS-Größe nicht erfüllbar (Verdict BROKEN, AC-6 und der cape-Teil von AC-7/AC-8). Ursache: `cape` ist seit #1585 bewusst `selectable=False`. Die Folgescheibe nimmt `cape` aus der Roh/Einfach-Menge und setzt die Zusicherung dort an, wo sie wirkt.

## Befund (Staging, 3f7b2153)
- Test-Trip mit `cape` (Roh, gespeichert) im SMS-Layout. Vorschau: `E1: TF11@8 W- R- PR- G- TH:- TH+:- CT100@12 SU10 DP13@18`. `CP` fehlt ganz, auch die Nullform `CP-`.
- `GET /api/metrics` liefert `sms_format_capable=true` nur für 4 Größen. Die Konstante nennt 5.
- Der Kern-Test `tests/tdd/test_sms_einfach_roh_je_metrik.py` (Docstring Z. 13–21) hat den Widerspruch schon gemeldet. CAPE wurde dort nur auf Builder-Ebene geprüft.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py:792` | `SMS_FORMAT_MODE_METRIC_IDS`: `"cape"` streichen |
| `src/app/metric_catalog.py:492ff` | `cape` mit `selectable=False` (#1585, `a288efb2`); bleibt unverändert |
| `src/app/metric_catalog.py:799` | `SMS_NULLFORM_METRIC_IDS` enthält `cape`; andere Konstante, älter als S6, nicht anfassen |
| `src/output/tokens/metrics.py:31-41` | `cape_stufe()` und `STUFEN_FN["CP"]`, von S6 eingeführt. Werden ohne Konstanten-Eintrag tot; wieder entfernen, damit eine spätere Freischaltung von cape keine ungeprüften Bänder erbt |
| `src/output/tokens/builder.py:207-215` | liest `STUFEN_FN.get(symbol)`; ohne `CP`-Eintrag bleibt CP Zahl. Keine Änderung nötig |
| `api/routers/config.py:118` | `sms_format_capable = m.id in SMS_FORMAT_MODE_METRIC_IDS`; Verhalten am Endpoint bleibt bei 4 Größen |
| `src/output/renderers/sms_trip.py:104`, `trip_report.py:423`, `validator_render_service.py:529` | lesen die Konstante; keine Änderung |
| `tests/tdd/test_sms_einfach_roh_je_metrik.py` | AC-6-Block (Z. 227–264), CAPE-Hälfte AC-7 (Z. 271–281), AC-8-Spec-Menge (Z. 329–390) anpassen |
| `tests/helpers/einstellung_auslieferung_orakel.py:217-232` | liest die Produktkonstante; keine eigene Liste |
| `tests/helpers/metrik_listen_scan.py:321-325` | registriert die Konstante als Metrik-Liste |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts:51` | `SMS_MIT_FORM` enthält `'cape'` und muss raus |
| `docs/specs/modules/fix_2422_s6_register_leeren.md` | AC-6 und cape-Teile AC-7/AC-8 werden durch diese Scheibe abgelöst; einzeiliger Verweis |
| `docs/reference/sms_format.md:727` (Version 2.33) | nennt „Wolken … und CAPE" als Roh/Einfach; korrigieren. ADR-0011-Nachtrag (Z. 155) betrifft nur TF, unverändert |

## Existing Patterns
- Die `selectable=False`-Regel (#710 confidence, `temperature_cold`, #1585 cape) wird zentral über `get_all_metrics()` / `_is_selectable` gefiltert. Eigene Listen dürfen diese Regel nicht unterlaufen (vgl. `metric_command_words()`, Docstring Z. 1138ff).
- Zusicherung an der Wirkstelle: Endpoint- und Kanal-Kaskade (`models.get_metrics_for_channel`), nicht am Builder.

## Dependencies
- Upstream: `MetricDefinition.selectable`, `get_metrics_for_channel`.
- Downstream: SMS-Builder (Einfachform), Editor-SMS-Reiter (`sms_format_capable`), Test-Orakel.

## Risks & Considerations
- Fehlt eine Invariante „jede Id in `SMS_FORMAT_MODE_METRIC_IDS` ist wählbar", kann dieselbe Lücke wieder entstehen. Diese Invariante ist die eigentliche Absicherung.
- Kein nutzersichtbarer Unterschied: cape wird nirgends angeboten. Bestandsdaten mit `format_mode` auf cape gibt es praktisch nicht. Wenn doch, ignoriert der Renderer sie schon heute.
- Nicht anfassen: CAPE in Alarmen, Highlights und Gewitter-Ablation (`trip_report.py:876ff`, `test_thunder_ablation.py`).

## Analysis

### Type
Bug (Spec-/Implementierungsfehler aus #2422 S6, an der Staging-Messung gefunden) mit PO-Entscheid zur Richtung.

### Root Cause (belegt)
- `SMS_FORMAT_MODE_METRIC_IDS` (`src/app/metric_catalog.py:792`) nimmt `cape` auf, obwohl `cape` `selectable=False` ist (#1585).
- Die Kanal-Kaskade filtert nicht wählbare Größen aus jedem Layout (`src/app/models.py:713` `_is_selectable`, genutzt von `get_metrics_for_channel` Z. 939). `/api/metrics` führt nur wählbare Größen.
- Folge: Der Roh/Einfach-Modus von cape kann nie wirken. Die S6-Tests prüften cape nur am Builder (`tests/tdd/test_sms_einfach_roh_je_metrik.py:227ff`). Es gibt keine Invariante „jede Id der Konstante ist wählbar".

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/metric_catalog.py` | MODIFY | `"cape"` aus `SMS_FORMAT_MODE_METRIC_IDS`, Kommentar anpassen |
| `src/output/tokens/metrics.py` | MODIFY | `cape_stufe`, `_AMPEL_STUFEN`, `STUFEN_FN["CP"]` entfernen |
| `tests/tdd/test_sms_einfach_roh_je_metrik.py` | MODIFY | AC-6-/AC-7-CAPE-Tests entfernen, AC-8-Spec-Menge auf 4 Wolken-Ids, neue Invariante und Endpoint-Gleichheit |
| `frontend/.../sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts` | MODIFY | `SMS_MIT_FORM` ohne `'cape'` |
| `docs/specs/modules/fix_2422_s6_register_leeren.md` | MODIFY (Doku) | Verweis: AC-6 und cape-Teile AC-7/AC-8 sind durch S6b abgelöst |
| `docs/reference/sms_format.md:727` | MODIFY (Doku) | „und CAPE" streichen |

### Scope Assessment
- Produktiv: 2 Dateien, etwa −15 LoC netto. Tests: 2 Dateien.
- Risk Level: LOW. Nutzersichtbar ändert sich nichts, weil cape nirgends angeboten wird. CAPE in Alarmen, Highlights und Gewitter-Ablation bleibt unberührt (eigene Pfade, kein `STUFEN_FN`).

### Technical Approach
1. Konstante auf die vier Wolken-Ids reduzieren. Die tote CAPE-Stufenabbildung entfernen: Eine spätere Freischaltung von cape soll keine ungeprüften Bänder erben, und `STUFEN_FN` bleibt Spiegel der Konstante (Drift-Test).
2. Zusicherung an der Wirkstelle:
   - (a) Invariante: jede Id in `SMS_FORMAT_MODE_METRIC_IDS` ist im Katalog `selectable=True` (`models._is_selectable`).
   - (b) `GET /api/metrics`: `sms_format_capable=true` genau für `cloud_total`/`cloud_low`/`cloud_mid`/`cloud_high`.
   - Mutationsprobe: `cape` wieder in die Konstante aufnehmen macht (a) rot.
3. Ein Trip mit gespeichertem cape-`format_mode` (Altbestand) liefert SMS-Text wie zuvor: CP wird weiter herausgefiltert, es entsteht kein Fehler.

### Dependencies
Builder `STUFEN_FN.get(symbol)` (fällt für CP auf Zahl zurück), `config.py:118`, Orakel `einstellung_auslieferung_orakel.py:224` (liest Produktkonstante).

### Open Questions
- keine (Richtung durch PO am 2026-10-01 entschieden)
