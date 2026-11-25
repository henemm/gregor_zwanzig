# Context: rework-3020-altbausteine-entfernen

## Request Summary
Issue #3020 (Epic #3122/#2795): Die alte Wetter-/Zustellungs-Oberfläche (`WeatherMetricsTab.svelte` und Umfeld) löschen. Keine sichtbare Änderung. Voraussetzungen erfüllt: #3154, #3332/#3333 (Anlegen), #3036 (Übergangsblock) live. PO-Freigabe, dass Alt-Bausteine, `telegram_kurzform`-Anzeige und SMS-Schwellen mit #3020 fallen, liegt vor (#3036, 24.11.). Intake-Score 4, AUTONOMY=auto. Reihenfolge der Restarbeiten: Kommentar in #3122 vom 25.11.

## Befund (Stand `main` 323c46e37)
- `WetterMetrikenVersandPanel` hat keinen produktiven Import. `WeatherMetricsTab` hängt nur noch daran und an zwei Barrel-Re-Exports (`lib/components/trip-detail/index.ts:7`, `lib/components/organisms/index.ts:18`), die niemand unter diesem Namen importiert.
- Ermittelt mit `docs/artifacts/rework-3020-altbausteine-entfernen/erreichbarkeit.py frontend/src`: statischer Import-Graph ab `routes/`, `hooks*`, `app*`, `service-worker*`, Barrels namensgenau, die zwei Re-Exports ausgeblendet. Ergebnislisten: `umfangslisten.md` im selben Ordner.
- Grenzen: Regex statt Parser, Typ-Importe zählen als Kante, dynamische Pfade und CSS nicht geprüft; „tests“ in den Listen = Testdateien, die den Dateinamen nennen (grob). In der Analyse per Probe-Löschung und `svelte-check` bestätigen.
- Liste A (erst mit WeatherMetricsTab tot): 35 Dateien, 6 296 Zeilen. Liste B (heute schon tot, Panel-/Versand-/Layout-Cluster): 19 Dateien, 2 585 Zeilen. Liste C (heute schon tot, fachfremd, nicht Umfang): 24 Dateien, 2 063 Zeilen.
- Nicht löschen laut Spec #3036 Nr. 5 (Z. 83, dort vollständig lesen): `channelConnectionStatus.ts`, `sendTargetLabel.ts`, `dayWindowClamp.ts`, `nextBriefingText`-Umfeld.
- Erreichbar laut Skript (in keiner Liste), obwohl alte Felder darin stehen: `weatherMetricsCompareSave.ts`, `compareChannelMetricLayouts.ts`, `reportConfigPayload.ts`, `mailInhaltZustand.ts`, `mailInhaltKonstanten.ts`, `kanalStilSpeicherung.ts`, `pickEigenfelder.ts`.

## Related Files (außer den Listen)
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/index.ts:7`, `organisms/index.ts:18` | Re-Exports entfernen; weitere Barrel-Zeilen toter Bausteine prüfen |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` (:583-620, `BESTAND`, `BESTAND_OBERGRENZE`) | Ratsche senken (ADR-0112); verwaiste Einträge sind rot |
| `tests/unit/ein_katalog_ausnahmen.json:28` | Ausnahme für WeatherMetricsTab entfernen |
| `frontend/src/lib/i18n/__tests__/*` und Kataloge | Wächter nennen Dateien; tote Schlüssel prüfen |
| `shared/__tests__/anlegeseiten_ohne_versand_panel_3333.test.ts:37` | Vakuum-Schutz verlangt heute, dass die Panel-Datei existiert; umstellen |
| `compare_versand_wertprops.test.ts:518,536`, `compare_wetter_metriken_wertprops.test.ts:424` | bewachen `versandPropsAus`/`wetterMetrikenPropsAus` bis zum Rückbau |
| `weather-metrics-tab/__tests__/_editor_kette.ts`, `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` | Prüfkatalog „Einstellung = Mail“: klären, ob er über tote Module läuft; darf nicht still entfallen |
| `frontend/e2e/*.spec.ts` | rund 30 nennen die Namen; ob nur im Kommentar, ist nicht geprüft. CI-Positivliste prüfen |

## Existing Patterns
- Rückbau-Vorbilder: `docs/specs/modules/fix_2931_daywindowcard_rueckbau.md`, Wächter `*_rueckbau_waechter.test.ts`, `tests/test_altpfad_import_sperre.py`.
- Alt-Tests nie still löschen: je Test entscheiden „prüft nur toten Code → löschen“ oder „Zusicherung gilt weiter → auf den lebenden Baustein umstellen“ (Muster: Spec #3333 Z. 149).

## Dependencies
- Upstream: tote Bausteine importieren lebende Helfer (die bleiben).
- Downstream: nach Skript nur Tests, Barrels, Ratschen-Listen.

## Existing Specs
- `rework_3036_uebergangsblock_aufloesen.md` (Z. 60, 61, 83, 147), `feat_3332_zustellung_anlegen_trip.md`, `feat_3333_zustellung_anlegen_orte.md`, `feat_3122_was_steht_wo.md` (AC-38, Z. 307/331), ADR-0124, ADR-0112.

## Risks & Considerations
- **Größe:** A+B = 54 Dateien, 8 881 Zeilen Produktion, dazu rund 190 Dateien, die einen der Namen nennen (WorkingSet nach grep, viele evtl. nur Kommentar; Zahl der Tests mit echter Verdrahtung nicht ermittelt). Überschreitet jedes Limit; Schnitt in Scheiben nötig (Vorschlag: erst Blätter aus B, dann WeatherMetricsTab + A; je Scheibe grün und einzeln auslieferbar).
- **Testverlust:** Tests mit toten Komponenten als Maßstab können gültige Zusicherungen tragen (Speicherweg, Read-Modify-Write, zwei Nutzer, Premium-SMS).
- **Parallelsitzung #2987** (Worktree `gentle-popping-seal`) ändert `reportConfigPayload.ts`, `zustellungModell.ts`, `tripNewLogic.ts`, `standardwerte_payload_paritaet_trip.test.ts`. Nicht anfassen. Dieser Test hängt an VersandTab/MailInhaltCard und wird dort umgestellt; deren Löschung erst nach dem Merge von #2987.
- Liste C bleibt liegen (kein Drive-by).
- #3301: `compareHourlyMetricDefs.ts` steht in Liste B, die Anlege-Karte ist mit #3333 weg. Nach der Löschung prüfen und #3301 mit Nachweis schließen.

## Analysis

### Type
Rückbau (Feature-Pfad, kein Bug). Keine sichtbare Änderung.

### Beleg durch Probe-Löschung (Wegwerf-Kopie, Stand 819a37abf, 25.11.)
Gelöscht: Listen A+B (54 Dateien) plus 8 Barrel-Zeilen (`trip-detail/index.ts`: WeatherMetricsTab, TablePreview; `organisms/index.ts`: OutputLayoutEditor, WeatherMetricsTab, OutboxCard, AlertsCard, PresetRail, MetricOffShelf).

| Messung | vorher | nach Löschung |
|---|---|---|
| `vite build` | nicht gemessen | Exit 0 |
| svelte-check Fehler in Produktionsdateien | CompareNewEditor 3, dialog-content 1, WeatherConfigDialog 1, _design 1, AlertsCard 1 | dieselben ohne AlertsCard, keine neuen |
| svelte-check gesamt | 33 Fehler / 83 Warnungen | 141 / 70 (alle neuen in Testcode) |
| `npm test` | 11 770 Tests, 2 rot | 10 198 Tests, 441 rot |

Damit ist belegt: kein lebender Produktionscode braucht A+B. Grenzen: lokal Node 26, CI Node 22; Python- und Playwright-Tests nicht gelaufen. Schon vorher nennt die lokale Ausgabe drei Testdateien als rot (`pill_toene_kontrast`, `anlege_lock_engine_waechter`, `weather_metric_kuerzel_marken`); Grund nicht untersucht, sie sind aus den 160 herausgerechnet.

Ablage in `docs/artifacts/rework-3020-altbausteine-entfernen/`: `probeloeschung_folgen.txt` (160 rote Testdateien, 34 567 Zeilen, dazu Verweise außerhalb `frontend/src` und in lebender Produktion), `importebenen.txt` (Löschreihenfolge, Testhelfer), `verwaiste_schluessel.txt` (196 Katalogschlüssel: wertebereiche 76, trip 46, versand 36, layout 24, bausteine 14; je DE und EN), `probeloeschung.py` (Löschskript, Pfad oben anpassen).

### Kernbefunde
1. **Das Risiko liegt in den Tests, nicht im Code.** Von den 160 Dateien prüfen etliche lebendes Verhalten (z. B. `tempo_*`, `trip_retry_*`, `hub_kopf_*`) und fallen nur, weil ein geteilter Testhelfer tote Dateien lädt: `tripMehrreiterPruefstand.ts` (21 Nutzer), `f9Pruefstand.ts` (16), `f5Pruefstand.ts` (9), `_editor_kette.ts` (5), `f6VersandSsr.ts` (4), `f8Pruefstand.ts` (3), `infoboxSsr.ts` (Nutzerzahl nicht gemessen), `LayoutTabPruefstand.svelte`. Diese Nutzer nicht pauschal löschen.
2. **Reihenfolge:** Importgraph von A+B ist zyklenfrei, 5 Ebenen; Wurzel des Kerns ist `WetterMetrikenVersandPanel`.
3. **Prüfkatalog „Einstellung = Mail“:** `fallliste_editor.json` hat 148 Fälle, alle grün. Ein Teil läuft über `_editor_kette.ts`, also über das tote `channelMetricLayouts.ts`, oder liest WeatherMetricsTab (`telegram_kanalgrenze_*`, `telegram_schnittlinie_*`, je 6 Fälle). Diese Fälle prüfen eine Oberfläche, die kein Nutzer sieht. Je Fall: lebender Beleg vorhanden (`ac26_einstellung_gleich_*` 21, `p5c_ableitung_hub_orte_*` 17) → umhängen; sonst auf lebendes Modul neu schreiben; Streichen nur mit Begründung. Genaue Zahl der betroffenen Fälle nicht ermittelt. Wächter: `tests/tdd/test_einstellung_gleich_mail_fallliste.py`.
4. **#3301:** `compareHourlyMetricDefs.ts` ist Ebene 1 ohne Importeur und in der Probe ohne Folgen für die Produktion gelöscht. Nach Auslieferung mit diesem Nachweis schließen.
5. **#3297:** nur der Teil in A/B ist mit abgedeckt. Altfeld-Stellen in lebenden Dateien (z. B. `weatherMetricsCompareSave.ts`) sind nicht Umfang.
6. **Python-Verweise** mit Pfadauswertung: `.claude/hooks/pendant_gate.py:84`, `test_pendant_gate.py:1130`, `test_pendant_gate_bekannte_paare.py:45`, `test_issue_289_surface_tokens.py:45`, `ein_katalog_ausnahmen.json` (6 tote Dateien). `test_issue_692_telegram_disabled_unconfigured.py` in der Spec klären. Übrige Treffer sahen in der Stichprobe nach Kommentaren/Docstrings aus.
7. **PR #3353 (#2987)** offen, alle Checks außer `e2e` grün. Er baut `standardwerte_payload_paritaet_trip.test.ts` um, das ohne ihn rot wird. Versand-Scheibe erst nach dem Merge.
8. `frontend/e2e/issue-1093-unit.spec.ts` importiert `src/lib` und nennt `layoutPreviewRows.ts`. Ob E2E-Dateien mit toten Namen in der CI-Positivliste stehen, ist nicht geklärt.
9. Ungeklärt: warum `trip_hub_loeschen.test.ts` rot wird (Einzellauf fand wegen der Klammern im Pfad keine Tests) und wie `home_hero_paritaet.test.ts` an OutlookLayoutControls hängt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| Listen A + B (54 Dateien, 8 881 Zeilen) | DELETE | `umfangslisten.md` |
| `trip-detail/index.ts`, `organisms/index.ts` | MODIFY | 8 Barrel-Zeilen |
| 7 Testhelfer + `LayoutTabPruefstand.svelte` | MODIFY/DELETE | von toten Dateien lösen |
| 160 Testdateien | MODIFY/DELETE | je Test entscheiden |
| i18n-Kataloge DE/EN | MODIFY | 196 verwaiste Schlüssel |
| `bausteine_waechter_regeln.ts` und übrige rote Wächter in `probeloeschung_folgen.txt`, `ein_katalog_ausnahmen.json`, `fallliste_editor.json` | MODIFY | Ratschen senken, nie lockern |
| `.github/workflows/ci.yml` (svelte-check-Baseline), `pendant_gate.py` + 2 Tests | MODIFY | Werte/Pfade nachziehen |
| Kommentarverweise in lebenden Dateien | – | nicht Umfang |

### Scope Assessment
- Files: 54 gelöscht, rund 180 weitere berührt. Estimated LoC: rund −8 900 Produktion; Test grob −10 000 bis −20 000 (Schätzung, Anteil löschen/umstellen nicht ermittelt).
- Risk Level: MEDIUM (Produktion niedrig, belegt; Testabdeckung hoch ohne Einzelentscheid).

### Technical Approach
Vier Scheiben, je eigener PR, jede grün und einzeln auslieferbar, eine Spec mit einer Freigabe:
1. **S1 Testunterbau:** Testhelfer auf lebende Bausteine umstellen, Produktion unverändert. Beweis: die Nutzer bleiben grün, auch in der Probe-Löschung.
2. **S2 Lose Blätter:** Ebene 1 ohne Panel, dazu der Teilbaum unter `OutputLayoutEditor` (BucketSection, BucketSectionOff, PresetRow, ActiveMetricRow, ChannelLimitMarkers).
3. **S3 Kern:** Panel, WeatherMetricsTab, BriefingScheduleTab, Wetter- und Layout-Cluster; `fallliste_editor` umhängen.
4. **S4 Versand-Cluster:** VersandTab, VT*, MailInhaltCard, `channelContactLabel`, `vtBriefingChannelsText`; erst nach Merge von #3353.

Je Scheibe: Testtabelle (löschen/umstellen mit Ersatzbeleg) → löschen → Katalogschlüssel und Ratschen mitziehen → Mutationsprobe auf umgestellte Zusicherungen. Nachweis „keine sichtbare Änderung“: Elementlisten-Abgleich DE/EN unverändert.

Nicht löschen (Spec #3036 Nr. 5, keine davon in A/B): `channelConnectionStatus.ts`, `sendTargetLabel.ts`, `dayWindowClamp.ts`, `nextBriefingText.ts`, `naechstesBriefingLader.svelte.ts`, `nextBriefingLoad.ts`, `reportConfigPayload.ts`, `mergeReportConfig.ts`, `ltChannels.ts`, `kanalStilSpeicherung.ts`.

Abweichung von `/20-analyse`: keine Explore-/Plan-Teilagenten, weil /10-context und die Probe-Löschung deren Fragen gemessen beantworten. Die Scheibung ist daher nicht von einem zweiten Agenten gegengeprüft; das holt der spec-validator nach.

### Dependencies
Upstream: PR #3353 nur für S4. Downstream: #3297 → #3298 → #3277.

### Open Questions
Keine an den PO. In der Spec zu klären: Befunde 3 (Fallzahl), 6 (`test_issue_692`), 8, 9.
