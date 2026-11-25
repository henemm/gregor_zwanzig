# Context: fix-3359-staging-pruefungen-altfelder

## Request Summary
Issue #3359 (Epic #3122, Nebenbefund aus #3297): E2E-Prüfungen säen noch die zehn Altfelder
(`channel_layouts`, `channel_layouts_per_report`, `channel_active_metrics`, `outlook_metrics`,
`outlook_metric_formats`, `hourly_metrics`, `hourly_metric_formats`, `show_outlook`,
`multi_day_trend_reports`, `outlook_enabled`). Seit #3277 liest Python sie nicht mehr; Wahrheit ist
allein `display_config.placements` (rows[].places/formats, outlook_reports), ohne `rows` gilt die
Tabelle aus der Grundauswahl (`display_config.metrics`). Prüfungen auf `placements` umstellen.
Kein Produktfehler, reine Testarbeit.

## Wichtige Tatsache (Go)
Go verwirft die Altfelder NICHT: `display_config`/`report_config` sind Maps und werden durchgereicht
(`internal/model/trip.go:124-125`, `internal/model/compare_preset.go:48`; bewusst so laut
`docs/specs/modules/feat_3277_altfelder_entfernen.md` „Kein serverseitiger Go-Strip“). Einzige Ausnahme:
`outlook_enabled` oben am Vergleich (Struct-Feld entfernt). Python (`src/app/loader.py:142`,
`altfelder_entfernen`) verwirft sie beim Laden/Speichern.
Folge: „Altfeld bleibt unberührt“-Zusicherungen sind meist grün, schützen aber nichts Wirksames
(Schein-Schutz). Rot sind nur Prüfungen, die eine WIRKUNG der Altfelder erwarten.

## Bestandsaufnahme frontend/e2e (Explore, 25.11.)
**C — erwartet Wirkung, heute rot:**
- `editor-gleich-gespeichert.staging.spec.ts` AC-10 (Z.101-114): sät `tests/fixtures/einstellung_auslieferung/golden_c.json`
  (dc: `channel_layouts`, `metrics`, `outlook_metrics`, KEIN `placements`), erwartet exakt `erwartung_golden_c.json`;
  E-Mail-Spalte stammt aus `channel_layouts.email` (7), heute Grundauswahl (11) → cloud_low, sunshine, uv_index, wind_chill zusätzlich.
- `standardwerte-und-hilfe.spec.ts:127` AC-6: erwartet `report_config.multi_day_trend_reports == ['evening']`;
  Frontend sendet den Schlüssel seit #3297 nicht mehr. Zweck (#3155 AC-7): „Ausblick nur abends“ → `placements.outlook_reports == ['evening']`.

**B — Schein-Schutz, auf placements umstellen:**
- `editor-gleich-gespeichert.staging.spec.ts` AC-11 (Z.142-150): `channel_layouts` vorher=nachher → `metrics` + `placements` prüfen.
- `was-steht-wo-karte.spec.ts` ALTFELDER (Z.186-202) + WS-14 (Z.880, 905, 913): Read-Modify-Write-Nachweis mit echten fremden Feldern (`daily_summary_metrics`, `wind_exposition_min_elevation_m`) statt Altfeldern.
- `feat-3276-vergleich-ohne-altfelder.spec.ts` Z.96-98/130-131: Bestand A/B mit `placements.rows` säen; Fehlen-Prüfung im PUT bleibt.
- `hub-save-chip.spec.ts` SC-1b (Z.137-186): Bestand mit eigener `placements.rows`; nachher `placements` gleich, 0 PUTs.
- `kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts` S1 (Z.112, 224-227): SMS-Teil auf `placements.rows` (wind_chill sms=true) oder streichen.
- `compare-outlook-metric-selection.staging.spec.ts` Z.35-45: Bestand über `placements` (outlook-Stelle + outlook_reports) oder Bestandsschleife streichen.
- `compare-uebersicht-kanal-persistenz.staging.spec.ts` Z.28, 41: leere Prüfung, ersatzlos streichen.

**E — tote Saat / toter Helfer, streichen:**
`hub-wetter-metriken-speichert-selbst.spec.ts` Z.127,134-135 · `compare-uebersicht-kanal.helpers.ts:109` (`gespeicherteKanalAuswahl`, ohne Aufrufer)
· `compare-hourly-metric-order.spec.ts:85` · `s3b2795-zustellung.helpers.ts:98` (`show_outlook`) · `hub-konfliktschutz-zwei-kontexte.spec.ts:208`.

**A/D — bleiben** (prüfen bewusst Abwesenheit bzw. nur Kommentar): `feat-3297-trip-ohne-altfelder`, `hub-anlegen-ablauf` (veralteter Kommentar Z.430-432),
`layout-tab-vergleich`, `vergleich-anlegen-was-steht-wo-3306`, `trip-anlegen-zustellung-3332`. Veraltete Kommentare in B/C-Dateien mitziehen.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/fixtures/einstellung_auslieferung/golden_c.json` | NICHT ändern: von ~14 Python-Tests genutzt (golden-Tests, test_einstellung_gleich_auslieferung, test_placements_tabelle_jede_metrik) |
| `tests/fixtures/einstellung_auslieferung/erwartung_golden_c.json` | NICHT ändern: Python AC-5 (SMS-Reihenfolge), Drift-Test `tests/test_erwartungsdatei_drift_einstellung_gleich_auslieferung.py`, `test_placements_tabelle_jede_metrik.py:96` (Teilmengen-Prüfung) |
| `frontend/e2e/was-steht-wo.helpers.ts` | Helfer `oeffneKarte`, `folge`, `haken`, `stand`, `tabelle` |
| `src/services/placements.py` | Format `placements` (`rows[{metric_id, places{email,telegram,sms,outlook}, formats}]`, `outlook_reports`, `version: 1`) |
| `.github/ci_e2e_specs.txt` | CI-Liste: enthält hub-save-chip, kurzform, hub-wetter-metriken, hub-konfliktschutz, was-steht-wo-karte; `*.staging.spec.ts` laufen nur in /e2e-verify |

## Existing Patterns
- Python-Seite hat den Golden-C-Bruch schon so gelöst: Erwartungsdatei als Teilmenge („jede erwartete Ausgabe hat eine angehakte Zelle“, `test_placements_tabelle_jede_metrik.py:96-107`); je Kanal eigene Folgen sind in „Was steht wo“ nicht ausdrückbar (Kommentar `test_einstellung_gleich_auslieferung.py:75-88`).
- Saat mit explizitem `placements` im Test-Body (z. B. `was-steht-wo-karte.spec.ts` Vergleich: `placements: { outlook_reports: [] }`).

## Dependencies
- Upstream: Go-API Trip/Vergleich POST/PUT/GET, `/api/.../placements` (Python), Staging-Stack.
- Downstream: /e2e-verify-Läufe aller Folge-Issues im Epic #3122 (insb. #3351, das die Altfelder auf der Platte löscht — danach würden B-Prüfungen, die Altfelder vorher/nachher vergleichen, je nach Saat ebenfalls kippen).

## Existing Specs
- `docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md` (AC-10/11/17)
- `docs/specs/modules/feat_3122_was_steht_wo.md` (Epic-Spec, Teil A Nr. 8 Altfelder)
- `docs/specs/modules/feat_3277_altfelder_entfernen.md`

## Risks & Considerations
- Keine Überschneidung mit dem parallel laufenden #3298 (ändert keine Dateien unter `frontend/e2e` / Golden-Fixtures, geprüft 25.11.).
- Abschwächung vermeiden: jede umgestellte Prüfung muss weiterhin rot werden, wenn die Karte/der Speicherweg die Tabelle falsch zeigt bzw. fremde Felder überschreibt (Mutationsprobe).
- Lauf der Staging-Prüfungen nur in /e2e-verify gegen Staging; CI-Prüfungen gegen den lokalen Stack.

## Analysis

### Type
Bug (reine Testarbeit, kein Produktcode)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/editor-gleich-gespeichert.staging.spec.ts` | MODIFY | AC-10: Karte == `tabelle()` je Stelle (exakt, `rows[].cells[stelle].state==='on'`) PLUS `erwartung_golden_c.json` als Teilmenge (wie Python `test_placements_tabelle_jede_metrik.py:96-107`); optional Einzelwert `cloud_low` email=an festnageln. AC-11: `channel_layouts` → `metrics` + `placements` vorher=nachher. Kopfkommentar Z.48-57 („GENAU“) anpassen |
| `frontend/e2e/standardwerte-und-hilfe.spec.ts` | MODIFY | AC-6: statt `report_config.multi_day_trend_reports` den WIRKSAMEN Wert prüfen: `tabelle(request,'route',a).outlook_reports == ['evening']` (Feld existiert: `src/services/placements_view_service.py:274`). NICHT `display_config.placements.outlook_reports` (Frontend schreibt es nur mit geöffneter Karte, `tripNewLogic.ts:352-395`; Vorbelegung macht Python `resolve_outlook_reports`, `placements.py:231`). Zusätzlich Tabelle A == Tabelle B |
| `frontend/e2e/was-steht-wo-karte.spec.ts` | MODIFY | ALTFELDER (Z.186-202), WS-14 (Z.880/905/913): Read-Modify-Write mit echten fremden Feldern (`daily_summary_metrics`, `wind_exposition_min_elevation_m`) |
| `frontend/e2e/feat-3276-vergleich-ohne-altfelder.spec.ts` | MODIFY | Bestand mit `placements.rows` (+`version: 1`) säen; Fehlen-Prüfung im PUT bleibt |
| `frontend/e2e/hub-save-chip.spec.ts` | MODIFY | SC-1b: Bestand mit eigener `placements.rows`; nachher gleich, 0 PUTs |
| `frontend/e2e/kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts` | MODIFY | S1: SMS-Teil auf `placements.rows` (wind_chill sms) oder streichen |
| `frontend/e2e/compare-outlook-metric-selection.staging.spec.ts` | MODIFY | Bestand über `placements` (outlook-Stelle + outlook_reports) oder Bestandsschleife streichen |
| `frontend/e2e/compare-uebersicht-kanal-persistenz.staging.spec.ts` | MODIFY | leere Altfeld-Prüfung Z.28/41 streichen |
| `frontend/e2e/compare-uebersicht-kanal.helpers.ts` | MODIFY | toten Helfer `gespeicherteKanalAuswahl` (Z.97, kein Aufrufer, per grep bestätigt) streichen |
| `hub-wetter-metriken-speichert-selbst.spec.ts`, `compare-hourly-metric-order.spec.ts`, `s3b2795-zustellung.helpers.ts`, `hub-konfliktschutz-zwei-kontexte.spec.ts` (alle `frontend/e2e/`) | MODIFY | tote Altfeld-Saat streichen |
| `frontend/e2e/hub-anlegen-ablauf.spec.ts` | MODIFY | nur veralteter Kommentar Z.430-432 |
| `tests/fixtures/einstellung_auslieferung/golden_c.json`, `erwartung_golden_c.json` | — | NICHT ändern (~14 Python-Tests) |

### Scope Assessment
- Files: ~13 (alle unter `frontend/e2e/`)
- Estimated LoC: +~120 / -~150
- Risk Level: LOW (kein Produktcode; Risiko liegt in Abschwächung von Prüfungen)

### Technical Approach
Plan/Sonnet-Bewertung (25.11.), Empfehlung übernommen:
- **AC-10 Option (a)**: Karte == Server-Tabelle exakt je Stelle (Mutation „Karte zeigt falschen Haken“ → rot) + Golden-C-Erwartung als Teilmenge (Mutation „Tabelle verliert erwartete Ausgabe“ → rot). Restlücke „Karte und Server gemeinsam zu viele Haken“ deckt Python über die Golden-Tests. Verworfen: (b) eigene Fixture (AC-10 prüfte dann nicht mehr Golden C, anderer Seed als AC-11/17), (c) nur Teilmenge (zu schwach).
- **AC-6**: wirksamer Ausblick-Wert aus der Tabellen-Ansicht, nicht gespeichertes Feld.
- **B**: echte fremde Felder bzw. `placements`+`metrics` statt Altfeldern; Saat mit `version: 1`; Saat-Zeilen so wählen, dass sie von der Grundauswahl abweichen (sonst Tautologie).
- **E**: streichen.
- Je umgestellter Prüfung Mutationsprobe (Adversary).

### Dependencies
- CI-Liste `.github/ci_e2e_specs.txt`: hub-save-chip, kurzform, hub-wetter-metriken, hub-konfliktschutz, was-steht-wo-karte laufen in CI (lokaler Stack); `*.staging.spec.ts`, feat-3276, standardwerte nur in /e2e-verify.
- Folge-Issue #3351 (Altfelder auf der Platte löschen) profitiert: nach der Umstellung vergleicht keine Prüfung mehr Altfelder.

### Open Questions
- keine Produktfrage; Detail im RED-Lauf: ob `placements.rows`-Saat von Python beim Laden normalisiert wird (dann Vergleich auf normalisierte Form).
