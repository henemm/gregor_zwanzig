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
