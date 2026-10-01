---
entity_id: fix_2422_s6b_cape_aus_roh_einfach
type: bugfix
created: 2026-10-01
updated: 2026-10-01
status: draft
version: "1.0"
tags: [sms, roh-einfach, cape, invariante, kanaele, fix]
workflow: fix-2422-s6b-cape
issues: ["#2422"]
---

# Fix #2422 (Scheibe S6b): CAPE aus der Roh/Einfach-Liste streichen

## Approval

- [ ] Approved

## Purpose

CAPE wird aus der Menge der Roh/Einfach-fähigen SMS-Größen entfernt. Die Roh/Einfach-Liste enthält danach nur Größen, die der Nutzer im Editor tatsächlich wählen kann, und eine Invariante verhindert, dass dieselbe Lücke wiederkehrt.

## Anlass

PO-Entscheid 2026-10-01 (Henning): „CAPE aus der Roh/Einfach-Liste streichen". Die Staging-Messung von #2422 S6 (Stand `3f7b2153`) ergab Verdict BROKEN, und zwar nur wegen CAPE: Ein Trip mit gespeichertem `cape` (Roh) lieferte `E1: TF11@8 W- R- PR- G- TH:- TH+:- CT100@12 SU10 DP13@18`, also weder `CP` noch die Nullform `CP-`. `GET /api/metrics` meldet `sms_format_capable=true` nur für 4 Größen, die Konstante nennt 5.

Ursache: `cape` ist seit #1585 bewusst `selectable=False`; die Kanal-Kaskade (`models.get_metrics_for_channel`, `models._is_selectable`) filtert nicht wählbare Größen aus jedem Layout. Der Roh/Einfach-Modus von `cape` kann deshalb nie wirken. Die S6-Tests prüften CAPE nur am Token-Builder, nicht an der Wirkstelle (Endpoint und Kanal-Kaskade). Die Entscheidung aus #1585 (`cape` nicht wählbar) bleibt unverändert.

## Löst ab

Gegenüber `docs/specs/modules/fix_2422_s6_register_leeren.md` gilt:

- **AC-6** (CAPE Roh/Einfach) ist **vollständig abgelöst**.
- Der **CAPE-Teil von AC-7** (Kanalgleichheit CAPE aus `severity_for("cape")`) ist abgelöst.
- Der **cape-Teil von AC-8** ist abgelöst: `SMS_FORMAT_MODE_METRIC_IDS` enthält jetzt genau die 4 Wolken-Ids.
- Die **Wolken-Teile von AC-5, AC-7 und AC-8 bleiben unverändert gültig.**

## Source

- **File:** `src/app/metric_catalog.py`, `src/output/tokens/metrics.py`
- **Identifier:** `SMS_FORMAT_MODE_METRIC_IDS`; `cape_stufe`, `_AMPEL_STUFEN`, `STUFEN_FN`

## Estimated Scope

- **LoC:** ca. -15 (netto, produktiv)
- **Files:** 2 Produktivdateien, 2 Testdateien, 2 Doku-Dateien
- **Effort:** low

### Affected Files (Schicht: Python-Core)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/metric_catalog.py` | MODIFY | `"cape"` aus `SMS_FORMAT_MODE_METRIC_IDS` streichen, Kommentar anpassen |
| `src/output/tokens/metrics.py` | MODIFY | `cape_stufe`, `_AMPEL_STUFEN`, `STUFEN_FN["CP"]` entfernen |
| `tests/tdd/test_sms_einfach_roh_je_metrik.py` | MODIFY | CAPE-Tests (AC-6, CAPE-Hälfte AC-7) entfernen, AC-8-Spec-Menge auf 4 Wolken-Ids, neue Tests AC-1 bis AC-5 |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts` | MODIFY | `SMS_MIT_FORM` ohne `'cape'` |
| `docs/reference/sms_format.md` | MODIFY (Doku) | Zeile 727: „und CAPE" streichen |
| `docs/specs/modules/fix_2422_s6_register_leeren.md` | MODIFY (Doku) | Verweiszeile: AC-6 und cape-Teile von AC-7/AC-8 durch S6b abgelöst |

## Nicht im Scope

CAPE in Alarmen, Highlights und Gewitter-Ablation (`trip_report.py`, `test_thunder_ablation.py`); `SMS_NULLFORM_METRIC_IDS` (enthält `cape`, älter als S6, andere Konstante); `selectable` von `cape` selbst; `builder.py` (fällt ohne `CP`-Eintrag in `STUFEN_FN` von selbst auf die Zahl zurück).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricDefinition.selectable`, `models._is_selectable` | module | Wählbarkeits-Regel (#710, #1585), Grundlage der Invariante |
| `models.get_metrics_for_channel` | function | Kanal-Kaskade, filtert nicht wählbare Größen |
| `api/routers/config.py` (`sms_format_capable`) | module | Endpoint `GET /api/metrics`, liest die Konstante unverändert |
| `src/output/tokens/builder.py` | module | liest `STUFEN_FN.get(symbol)`, keine Änderung |
| `src/output/renderers/sms_trip.py`, `trip_report.py`, `validator_render_service.py` | module | lesen die Konstante, keine Änderung |
| `tests/helpers/einstellung_auslieferung_orakel.py` | test-helper | liest die Produktkonstante, keine eigene Liste |

## Implementation Details

1. Konstante auf `cloud_total`, `cloud_low`, `cloud_mid`, `cloud_high` reduzieren, Kommentar nennt den Grund (nur wählbare Größen).
2. `cape_stufe`, `_AMPEL_STUFEN` und `STUFEN_FN["CP"]` löschen. Tote Bänder sollen eine spätere Freischaltung von `cape` nicht ungeprüft erben; `STUFEN_FN` bleibt Spiegel der Konstante (Drift-Test).
3. Zusicherung an der Wirkstelle: Invariante „jede Id der Konstante ist wählbar" und Endpoint-Gleichheit, nicht nur Builder-Test.
4. Bestandsdaten bleiben unberührt: ein gespeicherter `cape`-Eintrag mit `format_mode` wird weiter geladen und nicht überschrieben; der Renderer ignoriert ihn wie seit #1585.

## Expected Behavior

- **Input:** Katalog, `GET /api/metrics`, Trip mit gespeichertem `cape`-Eintrag.
- **Output:** `sms_format_capable=true` nur für die 4 Wolken-Größen; kein `CP`-Token; Wolken-Tokens unverändert.
- **Side effects:** keine; nutzersichtbar ändert sich nichts, weil `cape` nirgends angeboten wird.

## Acceptance Criteria

- **AC-1:** Given der Metrik-Katalog, When die Invariante läuft, Then ist jede Id in `SMS_FORMAT_MODE_METRIC_IDS` im Katalog wählbar (`selectable=True`, besteht `models._is_selectable`).
  - Test: `tests/tdd/test_sms_einfach_roh_je_metrik.py`, Invariante gegen den echten Katalog. Mutation: `cape` erneut in die Konstante aufnehmen macht diesen Test rot.

- **AC-2:** Given `GET /api/metrics`, When die Antwort gelesen wird, Then ist `sms_format_capable=true` genau für `cloud_total`, `cloud_low`, `cloud_mid`, `cloud_high` und für keine andere Metrik; der Editor-SMS-Reiter bietet den Roh/Einfach-Umschalter genau dort an.
  - Test: Endpoint-Test in `tests/tdd/test_sms_einfach_roh_je_metrik.py` (Menge der `true`-Größen == die 4 Ids); Frontend-Test `sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts` mit `SMS_MIT_FORM` ohne `'cape'`.

- **AC-3:** Given `STUFEN_FN`, When mit der Konstante verglichen, Then gibt es eine Stufenabbildung nur für Kürzel von Größen der Konstante (`CT`/`CL`/`CM`/`CH`), keine für `CP`.
  - Test: Drift-Test in `tests/tdd/test_sms_einfach_roh_je_metrik.py` (Kürzelmenge von `STUFEN_FN` == Kürzel der Konstante). Mutation: `STUFEN_FN["CP"]` wieder einfügen macht ihn rot.

- **AC-4:** Given ein Bestands-Trip mit gespeichertem `cape`-Eintrag inklusive `format_mode` im SMS-Layout, When SMS-/Premium-SMS-Text und Vorschau erzeugt werden, Then entsteht kein Fehler und kein `CP`-Token (`cape` bleibt wie seit #1585 ausgefiltert), und die übrigen Token sind byte-gleich zum Stand vor S6b.
  - Test: Produkttest in `tests/tdd/test_sms_einfach_roh_je_metrik.py` mit Trip-Fixture inklusive `cape`/`format_mode`; Vergleichstext aus dem Stand vor S6b (Staging-Befund `E1: TF11@8 W- R- PR- G- TH:- TH+:- CT100@12 SU10 DP13@18` als Muster).

- **AC-5:** Given die Wolken-Größen, When Roh bzw. Einfach gewählt ist, Then bleiben die S6-Ergebnisse unverändert (z.B. Roh `CT100@12`, Einfach `CT:OVC@12`).
  - Test: bestehende AC-5-/AC-8-Wolken-Tests in `tests/tdd/test_sms_einfach_roh_je_metrik.py` bleiben unverändert grün (Regressionsschutz).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Katalog WHEN jede Id aus `SMS_FORMAT_MODE_METRIC_IDS` geprüft wird THEN ist sie wählbar (rot, solange `cape` in der Konstante steht).
- [ ] Test 2: GIVEN `GET /api/metrics` WHEN gelesen THEN `sms_format_capable=true` genau für die 4 Wolken-Ids (rot, solange die Konstante 5 nennt bzw. Test die Menge einschränkt).
- [ ] Test 3: GIVEN `STUFEN_FN` WHEN mit der Konstante verglichen THEN kein `CP` (rot, solange `STUFEN_FN["CP"]` existiert).
- [ ] Test 4: GIVEN Bestands-Trip mit `cape`-`format_mode` WHEN SMS erzeugt THEN kein Fehler, kein `CP`, Rest byte-gleich.
- [ ] Test 5: GIVEN Wolken-Größen WHEN Roh/Einfach THEN S6-Ergebnisse unverändert.

### Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer Sicherungskopie)

1. `"cape"` zurück in `SMS_FORMAT_MODE_METRIC_IDS` -> AC-1 und AC-2 rot.
2. `STUFEN_FN["CP"]` wieder einfügen -> AC-3 rot.

## Known Limitations

Wird `cape` später wieder wählbar, braucht es eine neue Spec mit eigenen Bändern und Tests an der Wirkstelle.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rückkehr zur bestehenden Entscheidung aus #1585 (`cape` nicht wählbar); keine neue Grundsatzentscheidung.

## Changelog

- 2026-10-01: Initial spec created (PO-Entscheid Henning, #2422 S6b)
