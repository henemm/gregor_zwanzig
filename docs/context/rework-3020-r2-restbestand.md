# Kontext: #3020 Scheibe R2 — Restbestand der Alt-Bausteine löschen

Workflow `rework-3020-r2-restbestand`, Stand 2026-11-26 auf `origin/main` d7180c9e8.

## Request Summary

Letzte Scheibe von #3020 nach Spec `docs/specs/modules/rework_3020_altbausteine_entfernen.md` 2.0 (R2, AC-1 und AC-7 bis AC-12).
R1 ist live (PR #3382, #3391). Seit der Spec haben #3298 (9bf9c2dbf), #3301 (02f684e86), #3366 (PR #3386, layout-tab),
#3383/#3384/#3385 (Waisen S1–S4) und #3389 (tote Exporte, PR #3408) Teile des Restbestands schon gelöscht.

## Gemessener Restbestand (11 von 42 Dateien, alle ohne Produktions-Importeur außer Barrel/gegenseitig)

| Datei (unter `frontend/src/lib/components/`) | Verwender außerhalb des Restbestands |
|---|---|
| `organisms/AlertsCard.svelte` | Barrel `organisms/index.ts`; Tests `issue_578_molecules_organisms`, Wächter-Regeln |
| `organisms/MetricOffShelf.svelte` | Barrel; `ink4_waechter`, `issue_578_…` |
| `organisms/OutboxCard.svelte` | Barrel; `bausteine_sprache`, `issue_578_…`, `rework_3020_probe_loeschung` |
| `organisms/PresetRail.svelte` | Barrel; `ink4_waechter`, `bausteine_sprache`, `issue_578_…` |
| `shared/OutputLayoutEditor.svelte` | Barrel; Tests `OutputLayoutEditor.test`, `legacy_wizard_removed`, `layout_korridor_sprache`, Prüfstände `f8Pruefstand/f8Altbausteine/f8KatalogAnker`, `f9Altbausteine`, i18n-Wächter `keine_hartkodierten_nutzertexte`, `reaktivitaet_waechter` |
| `trip-detail/ActiveMetricRow.svelte` | `BucketSection`; `bug_499_skala_label.test`, `f9*` |
| `trip-detail/BucketSection.svelte` | `OutputLayoutEditor`; `layout_korridor_sprache`, `f9*` |
| `trip-detail/BucketSectionOff.svelte` | `OutputLayoutEditor`; `f9Altbausteine`; `tests/unit/ein_katalog_ausnahmen.json` |
| `trip-detail/ChannelLimitMarkers.svelte` | `BucketSection`; `f9Altbausteine` |
| `trip-detail/PresetRow.svelte` | `OutputLayoutEditor`; `PresetRow.test`; `tests/tdd/test_issue_289_surface_tokens.py` |
| `trip-detail/TablePreview.svelte` | Barrel `trip-detail/index.ts`; `bug_499`, `metricsEditor.test`, Kommentar in `metricsEditor.ts`; `ein_katalog_ausnahmen.json` |

Schon gelöscht (Existenzprüfung via `VORAB_GELOESCHT` im Wächter): `compare/compareHourlyMetricDefs.ts`, `compare/hourlyFriendlyMap.ts`, 6× `shared/layout-tab/*`.

## Related Files / Existing Patterns

- Wächter-Infrastruktur steht schon (R1): `frontend/src/lib/__tests__/rework_3020_rueckbau_waechter.test.ts` (Schalter `STAND` 1→2 macht AC-7 scharf; `GZ_3020_STAND=2` zeigt RED ohne Änderung), `rework_3020_umfang.ts` (RESTBESTAND 19, BARREL 6, BLEIBT), `rework_3020_probe_loeschung.test.ts`, `rework_3020_probe_hooks.mjs`.
- Testtabelle `docs/specs/modules/rework_3020_testtabelle.md`: R2-Abschnitt nötig (AC-8, je roter Testdatei aus Probe-Löschung ein Entscheid).
- Ratschen: `bausteine_waechter_regeln.ts` (`BESTAND_OBERGRENZE`), `tests/unit/ein_katalog_ausnahmen.json`, `.github/ci_e2e_specs.txt`/`ci.yml` (E2E-Spec `issue-1093-unit` prüfen, ob noch existiert), svelte-check-Baseline.
- Muster aus #3383/#3384/#3385/#3389: Probe-Löschung in Wegwerf-Kopie, Zahlen nach dem Löschen messen, Lösch-Nachweis.
- Offene Pflegepunkte aus #3385-Nachtrag: `rework_3020_rote_liste.ts` E070/E071/E080/E081/E086–E088 (Testdateien bereits gelöscht), `_hinweis` in `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`.

## Dependencies / Dependents

Keine Produktionsimporte. Katalogschlüssel (i18n DE/EN) der Bausteine werden verwaist → `katalog_schluessel_haben_verwender` misst. Kein Python/Go-Produktionscode.

## Existing Specs

`rework_3020_altbausteine_entfernen.md` 2.0 (R2-Umfang, freigegeben für R1+R2). Abweichung: Restbestand 11 statt 42 → Spec-Nachtrag (Changelog), AC unverändert.
#3301 und #3298 sind schon geschlossen (AC-12 dort erfüllt bzw. nur noch Nachweis-Kommentar).

## Risks

- Prüfstände `f8*/f9*` (`layout-tab/__tests__`, `trip-detail/__tests__`) nutzen Alt-Bausteine als Fixtures für Katalog-Anker-Prüfungen: prüfen, ob ein lebender Anteil bleibt (Ersatzbeleg statt stilles Löschen).
- `ink4_waechter`, `bausteine_sprache`, i18n-Wächter führen die Namen in Listen: nur Einträge streichen, nicht lockern.
- Parallele Sitzungen an Waisen-/Altbaustein-Dateien: vor Start `sessions` prüfen (heute keine).

## Analysis

**Type:** Rückbau (Feature-Track, keine sichtbare Änderung). Spec 2.0 deckt R2 ab; nur Nachtrag Restbestand 42 → 11 (Changelog), ACs unverändert.

**Probe-Löschung (2026-11-26, Wegwerf-Kopie, volle Frontend-Suite, 11 Dateien + 6 Barrel-Zeilen entfernt), Differenz zur Baseline derselben Umgebung:**
Baseline 118 rote Dateien (umgebungsbedingt, identisch), Probe 129; neu bzw. stärker rot genau 13 Dateien (Anzahl roter Fälle Probe/Baseline):

| Testdatei | rot | Entscheid (Vorschlag) |
|---|---|---|
| `components/molecules/issue_578_molecules_organisms.test.ts` | 16/0 | Fälle für AlertsCard/OutboxCard/PresetRail/MetricOffShelf streichen (prüfen nur Alt-Bausteine) |
| `components/shared/__tests__/OutputLayoutEditor.test.ts` | 4/0 | Datei löschen (prüft nur gelöschten Baustein) |
| `components/trip-detail/bug_499_skala_label.test.ts` | 5/0 | Fälle für ActiveMetricRow/TablePreview streichen bzw. Datei löschen, falls kein lebender Anteil |
| `components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` | 1/0 | OutputLayoutEditor-/BucketSection-Fall streichen; f8-Prüfstand um Alt-Bausteine kürzen |
| `components/trip-detail/__tests__/trip_hub_sprache.test.ts` | 4/0 | f9-Prüfstand (`f9Altbausteine.ts`) um gelöschte Bausteine kürzen bzw. Datei löschen |
| `components/__tests__/bausteine_sprache.test.ts` | 5/0 | Einträge OutboxCard/PresetRail streichen |
| `i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | 2/0 | verwaiste DE/EN-Schlüssel entfernen (AC-9), Wächter nicht lockern |
| `i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | 2/0 | Eintrag OutputLayoutEditor streichen |
| `i18n/__tests__/reaktivitaet_waechter.test.ts` | 4/0 | Eintrag OutputLayoutEditor streichen |
| `__tests__/bausteine_waechter.test.ts` | 2/0 | BESTAND-Einträge (7) und AUSNAHMEN (4) streichen, `BESTAND_OBERGRENZE` 162 → 155 |
| `__tests__/ink4_waechter.test.ts` | 1/0 | Einträge MetricOffShelf/PresetRail streichen |
| `__tests__/rework_3020_rueckbau_waechter.test.ts` | 15/2 | `STAND` 1 → 2 (erwartet), VORAB_GELOESCHT bleibt |
| `__tests__/rework_3020_probe_loeschung.test.ts` | 12/10 | Probe-Test nach R2 auflösen/umstellen (Prüfling existiert nicht mehr) |

Außerhalb der Frontend-Suite: `tests/tdd/test_issue_289_surface_tokens.py::test_preset_row_color_mix_uses_surface0` (liest PresetRow.svelte) → streichen; `tests/unit/ein_katalog_ausnahmen.json` Einträge BucketSectionOff/TablePreview streichen. E2E-Specs nennen die Namen nur in Kommentaren (keine Änderung, `E2E_MIN_*` unverändert). `metricsEditor.ts` nennt TablePreview nur im Kommentar.
Doku: `docs/reference/{frontend_components,api_contract,gates_und_ratschen}.md`, `docs/features/architecture.md`, `docs/features/epic-1273-compare-one-surface.md` auf gelöschte Bausteine prüfen.
Pflege aus #3385: `rework_3020_rote_liste.ts` E070/E071/E080/E081/E086–E088, `_hinweis` in `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`.

**Scope/Risk:** 11 Produktionsdateien gelöscht (nur toter Code), ~15 Testdateien/Listen angepasst, Doku. Risiko niedrig für Nutzer (kein Produktionsimporteur, Build-Nachweis in CI), mittel für Wächter-Ehrlichkeit (nur Einträge streichen, nie lockern).

**Technical Approach:** RED: `STAND=2` im Wächter (rot, solange Dateien existieren) + Testtabelle-Abschnitt R2 (13 Zeilen + Python-Fall). GREEN: löschen, Barrel, Listen kürzen, Ratschen senken, Katalogschlüssel entfernen, svelte-check-Baseline nur senken.

**Open Questions:** keine (PO-Freigabe des Rückbaus liegt vor, #3036 2026-11-24).
