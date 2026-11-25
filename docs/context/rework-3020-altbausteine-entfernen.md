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

> Stand 25.11. auf c8329fea4 (nach #3357). Ersetzt „Analysis (überholt)“ bis „TDD RED“ weiter unten; dort nur noch als Vorlage für Testhelfer, Testtabelle und Mutationen nachsehen. S1-Stand vollständig: `8b9749601` (Vorfahr dieses Branches, zusätzlich Branch `sicherung-3020-s1`).

### Type
Rückbau, zweiter Teil (Feature-Pfad, kein Bug). Keine sichtbare Änderung.

### Was #3357 erledigt hat, was bleibt
12 der 54 Dateien sind gelöscht (Panel, WeatherMetricsTab, BriefingScheduleTab, VersandTab, MailInhaltCard, OutlookLayoutControls, WeatherV2Reihenfolge, channelMetricLayouts, weatherMetricsSavePayload, weatherMetricsTabSections, kuerzelLegende, kuerzelMarken). Der Baum hier ist `origin/main` plus unsere Doku.

1. **Restbestand: 42 Dateien, 4 454 Zeilen, alle ohne produktiven Importeur** (Liste A 26/2 598, Liste B 16/1 856). Gemessen mit `erreichbarkeit_v2.py` → `tot_nach_3357.txt`. Korrektur am Skript: die alte Fassung wertet den Beispiel-Import im Kopfkommentar von `organisms/index.ts` als Kante und hielt auf diesem Stand OutputLayoutEditor, OutboxCard, AlertsCard, PresetRail, MetricOffShelf und Nachbarn für lebend. Barrel-Zeilen: diese fünf in `organisms/index.ts`, TablePreview in `trip-detail/index.ts`.
2. **Tests dazu:** 79 Testdateien nennen einen der 42 Namen, 24 importieren einen direkt (Regex, `restbestand_tests.txt`), 15 E2E-Dateien nennen einen. Wie viele nach der Löschung rot werden, ist auf diesem Stand NICHT gemessen; erster Schritt der Lösch-Scheibe ist die Probe-Löschung.
3. **Entfallene Prüfungen aus #3357:** 60 `*.test.ts` gelöscht, dazu 145 Fälle in weiterlaufenden Testdateien entfallen (Namensvergleich 539d16963 gegen main, `testnamen_diff.txt`; umbenannte Fälle zählen mit, 125 davon standen in S1 noch, ein Teil prüfte nur Alt-Quelltext).
   - Von den 60 laut `rework_3020_testtabelle.md`: 3 „löschen“. Von den 57 „umstellen“ haben **23 einen Vermerk „neu in S3/S4“** (Ersatzbeleg erst zu schreiben), **16 nennen einen Beleg, der auf main nicht existiert** (u. a. `wetter_tab_karte_mitspeichern_3020`, `feld_erhalt_ohne_ausnahme`, `trip_python_skip_next_ohne_412`, `s3a2794_speicher_owner_waechter`), 6 davon beides; die übrigen **24 nennen nur vorhandene Dateien**. Zusammen 33 Zeilen mit Lücke.
   - Die 24 sind nur nach Dateiname geprüft. Einige Belegdateien hat #3357 gekürzt (`trip_reiter_roundtrip_jedes_feld` 26→13 Fälle, `trip_reiter_nutzlast_nur_eigene_felder` 12→8). R1 klärt je Zeile, ob der genannte Fall noch steht.
   - Vorrang (Datenverlust, Zwei-Nutzer): skip_next-Schutz (in S1 vier `todo` wegen #3355), If-Match/keepalive-Flush an Zustellung, `show_night_block` „aus bleibt aus“, Feld-Erhalt samt `sms_threshold`, Roundtrip je Feld, Retry-/412-Fälle, zwei Nutzer beim Laden, Kanal-Vorgaben gleich Auslieferung (Telegram, SMS, Premium-SMS), Reiter Wetter und Zustellung an einem Controller. Danach: Telegram-Grenze Orte (Katalog 23–34), Klebeschicht-Ladetests, Übriges.
4. **Katalog „Einstellung = Mail“:** aus `fallliste_editor.json` sind 15 Fälle gestrichen, alle mit Status grün (SMS-LADEN-A/B, zwölf F3/F3N-Fälle Trip/Orte, P12-TL3-ORTE-KURZSTIL). Je Fall: lebenden Beleg wieder eintragen oder Streichung begründen. Verweisänderungen verbliebener Fälle, auch in `fallliste_trip` und `fallliste_orte`, sind nicht ausgewertet.
5. **`test_einstellung_gleich_mail_fallliste.py`:** `assert praefixe` ist durch „Template-Titel in den verwiesenen Dateien“ ersetzt. Laut Kommentar im Test ist `praefixe` heute leer, die Teilmengen-Prüfung läuft also leer, weil die Editor-Dateien weg sind. Nur am Diff gelesen. In R1 auf die neuen Testdateien richten.
6. **Vorlage folgt der Fortbewegung (#3196 AC-7):** im lebenden Reiter Wetter (`shared/wetter-tab`, `organisms/wetter-tab`) liefert die Suche nach `tempo` keinen Treffer; die einzige bekannte Zuordnung stand in `WeatherMetricsTab`. Nicht im Browser gemessen. AC-7 ist freigegeben, also keine PO-Frage, sondern ein Bug: #3358; nicht Teil dieses Rückbaus.
7. **Grenzen:** Liste C (24 Dateien) bleibt, ebenso drei neu als tot gemeldete Dateien (`mobile/Drawer`, `CompareStatusRow`, `ScoreToggle`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| 42 Dateien (`tot_nach_3357.txt` ∩ Listen A/B) | DELETE | R2 |
| `organisms/index.ts`, `trip-detail/index.ts` | MODIFY | 6 Barrel-Zeilen |
| Tests aus S1 (`wetter_tab_karte_mitspeichern_3020`, `trip_python_skip_next_ohne_412`, `feld_erhalt_ohne_ausnahme`, Nutzlast/Roundtrip) | CREATE/MODIFY | R1, aus `8b9749601` portieren, nicht blind kopieren (Helfer haben sich geändert) |
| neue Belege laut Testtabelle „neu in S3/S4“ | CREATE | R1 |
| `rework_3020_testtabelle.md`, Wächter und Probe (`rework_3020_*`) | MODIFY/CREATE | auf Restbestand umstellen; R2-F2 (Ersatzbeleg muss Testdatei sein), R2-F3 (Anzahl festhalten) mitnehmen, R2-F1 (Attribute in `WetterTabInhalt` unbewacht) prüfen |
| `fallliste_editor.json`, `test_einstellung_gleich_mail_fallliste.py` | MODIFY | Befund 4 und 5 |
| i18n-Kataloge DE/EN, `bausteine_waechter_regeln.ts`, `ein_katalog_ausnahmen.json`, svelte-check-Baseline, `pendant_gate.py` | MODIFY | R2, Ratschen senken, nie lockern; Bedarf erst nach der Probe bekannt |

### Scope Assessment
- R1: 0 Produktionszeilen, geschätzt 20–30 Testdateien. R2: rund −4 450 Produktionszeilen, Testanteil erst nach der Probe bekannt.
- Risk Level: MEDIUM (Löschen niedrig; Schutzlücke in Tests hoch, bis R1 fertig ist).

### Technical Approach
Zwei Scheiben, je eigener PR, je grün und einzeln auslieferbar, EINE Spec (bisherige Spec neu fassen; Scheibenschnitt 19/26/9 und AC-3/4/6/11/12 beziehen sich auf den alten Stand):
1. **R1 Schutz wiederherstellen** (Vorrangliste Befund 3, dazu 4 und 5). Jede Zusicherung mit Mutationsprobe am lebenden Code. Fälle zu #3355 bleiben `todo` mit Verweis.
2. **R2 Restbestand löschen:** Probe-Löschung → Testtabelle je rotem Test → löschen → verwaiste Katalogschlüssel und Ratschen mitziehen.

R1 zuerst: die Schutzlücke besteht heute schon auf main, und das Löschen macht sie nicht kleiner.

**Abgrenzung:** `compareHourlyMetricDefs.ts` und `hourlyFriendlyMap.ts` löscht R2 (Nachweis für #3301); #3298 übernimmt Typen und Sperre. Vor R2 erneut prüfen, ob #3298 läuft. Worktree `delegated-humming-dijkstra` ist gesperrt, Inhalt nicht geprüft.

**Achtung:** die Spec #3297 (Z. 164) schließt beim Abschluss auch #3020. Per Kommentar in #3020 und #3297 widersprochen.

Abweichung von `/20-analyse`: keine Explore-/Plan-Teilagenten; Restbestand und Testlücken sind gemessen, der Scheibenschnitt ist nicht von einem zweiten Agenten geprüft. Das holt der spec-validator nach.

### Dependencies
Upstream: #3357 auf main (Live-Stand hier nicht geprüft). Daneben: #3355, #3298, #3301. Downstream: #3351 (Datenlauf).

### Open Questions
Keine an den PO.

## Analysis (überholt, Stand vor #3357)

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

### Nachtrag 25.11. nach Rebase
- PR #3353 (#2987) ist gemergt, der Branch steht darauf. **S4 ist damit nicht mehr blockiert**; Befund 7 und die Upstream-Abhängigkeit sind überholt, die Sperre für die vier Dateien von #2987 ebenso.
- Die Probe-Löschung lief auf dem Stand davor. Neu seither im Frontend: 6 Dateien, darunter `reportConfigPayload.ts`, `zustellungModell.ts`, `tripNewLogic.ts`, `briefingStartwerte.ts`. Probe in S1 auf dem neuen Stand wiederholen.
- `docs/artifacts/` ist per `.gitignore` ausgenommen: Belegdateien liegen nur in diesem Worktree auf der Platte.

### TDD RED (Phase 5, S1)
- Neu in `frontend/src/lib/__tests__/`: `rework_3020_umfang.ts` (Listen aus der Spec), `rework_3020_rueckbau_waechter.test.ts` (AC-3/AC-4), `rework_3020_probe_loeschung.test.ts` plus `rework_3020_probe_hooks.mjs` (AC-11). Die Probe verbirgt die 54 Dateien je Kindprozess (Modulladen und `fs`), ohne Kopie; das ist die in S1 verlangte Wiederholung für die lebenden Helfer-Nutzer. Die Vollmessung der roten Liste für die Testtabelle (heute 160) steht noch aus.
- RED: Probe 24 von 24 lebenden Nutzern rot, jeweils mit einem toten Baustein als Ursache; Kontrolle ohne Sperre 24 von 24 grün; Selbsttest 3 grün. Wächter bei STAND 1: 3 rot (LayoutTabPruefstand, Testtabelle fehlt, 48 Testdateien ohne Entscheid), bei `GZ_3020_STAND=4` 58 rot (129 Importe). svelte-check unverändert 33/83.
- **STAND** im Wächter: S1 = 1, jede Scheibe erhöht ihn im selben PR (Dateien späterer Scheiben müssen bis dahin existieren). Probe-Dateien fallen mit S4.
- **Abgrenzung der 24:** nur Tests mit lebender Aussage. Draußen (Entscheid über Testtabelle): nur tote Oberfläche (`trip_versand_reiter_ohne_dauer_keepalive`, `trip_night_block_schalter_*`, `wetter_metriken_versand_panel_speicherung`), gemischt (`trip_hub_sprache`, `layout_korridor_sprache`, `tempo_fixloop4_3196`, `tempo_verdrahtung_3196_fixloop2`, `ausblick_ein_name_3155`, `feat_3190_vorlage_dialog_inline`), Nutzer von `_editor_kette`, `f5Pruefstand`, `f6VersandSsr` (S3/S4, AC-6). Zuordnung nach Namenstreffer/Aufrufstellen, nicht jede Datei gelesen; S1 prüft nach.
- **Achtung Umbau:** 10 der 24 nutzen `P.wetterMetrikenReiter`/`P.versandReiter` aus `tripMehrreiterPruefstand.ts`, also die toten Reiter. Sie müssen auf `wetter-tab/`, `WasStehtWoKarte`, `zustellung-tab/` umgestellt werden (AC-5, mit Mutationsprobe); ein Umbau nur des Imports reicht nicht. Die 14 anderen scheitern am Vorab-Laden toter Bausteine in `f9Pruefstand`/`f8Pruefstand`: toten Teil abtrennen.
- **Korrektur zur Spec:** `LayoutTabPruefstand.svelte` hat 0 *Test*-Nutzer, aber `f8Pruefstand.ts` rendert ihn (Z. 46, 85, 108 f.). Löschen in S1 heißt dort umstellen; `infoboxSsr.ts` selbst lädt keine tote Datei (nur seine Nutzer über `lade(...)`).
- Testtabelle, vom Wächter geprüftes Zeilenformat: Pfad ab `lib/` oder `routes/` in Backticks, S1 bis S4, `löschen`/`umstellen`/`Ersatzbeleg`, Begründung, Ersatzbeleg, Mutation.
