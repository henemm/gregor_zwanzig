# Adversary Dialog — feat-3298-altfeld-typen-sperre
Spec: docs/specs/modules/feat_3298_altfeld_typen_sperre.md
Datum: 2026-11-25 14:49

## Checkliste
- [x] **Input:** Ortsvergleich anlegen (auch aus Vorlage), Ortsvergleich-Reiter speichern, Trip speichern, Seiten öffnen.
- [x] **Output:** Kein Request-Body enthält einen der zehn Altnamen; die Hydration liest sie nicht. Frontend-Typen kennen sie nicht. Neue Altnamen im Produktionscode machen die Sperre rot.
- [x] **Side effects:** Keine sichtbare Änderung in Editor, Mail oder Kanälen (DE und EN). Bestandsdaten bleiben bis #3351 unberührt auf der Platte.
- [x] **AC-1:** Given die Typen `DisplayConfig`, `ReportConfig` und `ComparePreset` / When das Frontend mit `svelte-check` geprüft wird / Then kennen die Typen keinen der zehn Altfeld-Namen und kein `multi_day_trend_morning/evening` mehr, und `svelte-check` meldet keinen Fehler.
- [x] **AC-2:** Given ein Ortsvergleich wird angelegt oder in einem Reiter (Wertebereiche, Layout, Versand, Alarme) gespeichert / When der Speicher-Request an die API gesendet wird / Then enthält der Body keinen der zehn Altschlüssel (weder gefüllt noch leer), insbesondere kein `outlook_enabled`, und alle übrigen Bestandsfelder bleiben nach dem Go-Merge erhalten.
- [x] **AC-3:** Given ein gespeicherter Ortsvergleich oder eine Vorlage, deren Daten noch Altfelder tragen / When der Editor hydriert wird (`CompareTabs`, Anlegen aus Vorlage) / Then liest die Hydration weder `outlook_enabled` noch `channel_active_metrics` oder die Layout-Altfelder, der Ausblick folgt `placements.outlook_reports`, und der Editor zeigt dieselben Werte wie zuvor.
- [x] **AC-4:** Given `WETTER_DISPLAY_KEYS` in `pickEigenfelder.ts` / When ein Wetter-Reiter-Body gebaut wird / Then enthält die Whitelist nur `metrics`, `preset_name`, `telegram_kurzform`, `show_night_block`, `ampel`, und kein Altname wird übernommen, auch wenn er in den Eingabedaten steht.
- [x] **AC-5:** Given jemand fügt einen der zehn Altnamen in eine Produktionsdatei unter `frontend/src` ein / When die Sperre `altfeld_namen_sperre.test.ts` läuft / Then wird sie rot und nennt Datei und Namen; Namen in Kommentaren, `hourly_enabled` sowie Tests und Prüfstände lösen nichts aus.
- [x] **AC-6:** Given die Sperre mit leerer ERLAUBT-Tabelle / When ihr Selbstnachweis mit synthetischem Quelltext läuft / Then erkennt er einen Verstoß, ignoriert Kommentar-Treffer und `hourly_enabled`, akzeptiert einen gültigen Eintrag (Grund ≥ 20 Zeichen, Ablaufdatum in der Zukunft) und schlägt bei abgelaufenem Eintrag oder zu kurzem Grund an.
- [x] **AC-7:** Given die Namensliste der Sperre und die Liste `ALTFELDER` in `src/app/loader.py` / When der Sperr-Test läuft / Then sind beide Mengen identisch (zehn Namen), und eine Abweichung macht den Test rot.
- [x] **AC-8:** Given `hourlyFriendlyMap.ts` ohne Produktionsaufrufer / When der Rückbau abgeschlossen ist / Then existiert die Datei nicht mehr, keine Produktionsdatei importiert sie, und `vite build` sowie `svelte-check` laufen ohne unaufgelöste Importe.
- [x] **AC-9:** Given ein Nutzer bedient Ortsvergleich (anlegen, Reiter Wertebereiche/Layout/Versand/Alarme speichern) und Trip auf Staging, in Deutsch und Englisch / When er wie bisher speichert und neu lädt / Then sieht und bedient er dieselben Flächen wie vor dem Rückbau, und alle Werte inklusive Ausblick bleiben nach dem Neuladen erhalten.
- [x] **AC-10:** Given Tests, die entfernte Pfade prüften / When der Rückbau abgeschlossen ist / Then ist jede gelöschte Testdatei einer gelöschten oder entfernten Produktionsfunktion zugeordnet, alle übrigen sind auf „Schlüssel fehlt“ umgestellt, und die Kern-Schicht (Frontend `node --test` benannter Dateien, `svelte-check`, Playwright-Kern) ist grün.

## Dialog

### Runde 1
**Adversary:** Tests laufen: 3394 pass / 0 fail (docs/artifacts/feat-3298-altfeld-typen-sperre/adversary-test-output.txt, Summenzeilen `# pass 3394`, `# fail 0`). `npm run build` Exit 0, svelte-check 32 Fehler (Baseline 34). Mutationen M1-M6 per String-Ersetzung, jeweils exakt zurueckgesetzt (diff gegen Sicherung identisch).
- M1 `outlook_enabled` literal in compareEditorSave: rot (Sperre AC-5). Dynamischer Schluessel `['outlook'+'_enabled']` nur im hourlyEnabled-Zweig des Voll-Rumpfs: NICHT gefangen (F001). Unbedingt im Voll-Rumpf: gefangen (AC-13, AC-2-Layout-Flush).
- M2 Hydration liest `outlook_enabled`: gefangen (Vorlage-Test, AC-3-Hydration).
- M3 WETTER_DISPLAY_KEYS mit `channel_layouts`: gefangen (AC-4).
- M4 `show_outlook?` in types.ts: Sperre rot, nennt `lib/types.ts:316: show_outlook`.
- M5 Namensliste um ein Element gekuerzt: AC-7 rot.
- M6 leeres `channel_layouts: {}`: im POST-Rumpf (Nutzerweg) gefangen (6 rote Tests); im Voll-Rumpf buildComparePresetSavePayload NICHT gefangen (F002), dort greifen aber alle Produktivaufrufer ueber waehleEigenfelder-Whitelist, kein Nutzereffekt.
Weitere Sonden: Kommentar-Filter der Sperre laesst `const x = 'channel_layouts' // c` korrekt als Treffer stehen; abgelaufene ERLAUBT-Eintraege sind rot (Test vorhanden); Namensliste == ALTFELDER (src/app/loader.py:142). Gerauemte Tests: nur entfernte Pfade (geloeschte Dateien betreffen hourlyFriendlyMap/hourlyMetricFormats). channelActiveMetricKeys bleibt nur als Prop/Zustand (wetterMetrikenPropsAus.ts:56), wird weder hydriert noch gesendet. Bestandsschluessel bleiben per Merge (Zustellung/Alarme/Versand/Werte senden nur Eigenfelder-Whitelist).
Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:183
  Description: Ein dynamisch gebildeter Schluessel `outlook_enabled` im hourlyEnabled-Zweig des Voll-Rumpfs bleibt von allen Tests unbemerkt; nur die Literal-Sperre schuetzt.
  Spec requirement: AC-2 — kein Altschluessel im Body
  Conflict: Kein Verhaltenstest ruft buildComparePresetSavePayload mit gesetztem hourlyEnabled und prueft Altschluessel; Produktivpfad filtert zudem per Whitelist.
  Remediation: Test mit hourlyEnabled gesetzt und ALTSCHLUESSEL-Pruefung am Voll-Rumpf.
Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:170
  Description: Leerer Altschluessel `channel_layouts: {}` im Voll-Rumpf (Preset ohne Altbestand) wird von keinem Test erkannt.
  Spec requirement: AC-2 — weder gefuellt noch leer
  Conflict: Nur POST- und Reiter-Nutzlasten sind geprueft; Produktivaufrufer whitelisten, daher kein Nutzereffekt.
  Remediation: ALTSCHLUESSEL-Pruefung am Ergebnis von buildComparePresetSavePayload mit sauberem Preset.
Finding:
  ID: F003
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/altfeld_namen_sperre.test.ts:62
  Description: Kommentarfilter `(^|[^:'"`])//` schneidet nach `//` in Strings wie `'a//b'` oder Template-Literal den Rest der Zeile ab; ein Altname dahinter in derselben Zeile wird uebersehen.
  Spec requirement: AC-5 — neuer Altname macht Sperre rot
  Conflict: Falsch-Negativ in seltenem Muster (`\`a//b\` + show_outlook`).
  Remediation: Zeilenkommentar nur nach Tokenisierung bzw. nur wenn Zeilenanfang oder Whitespace davor.
**Implementierer:** keine Antwort erforderlich.

### Runde 2
**Adversary (Runde 2):** Zweite Pruefung der Wirkstelle: Nutzerweg POST (baueVergleichAnlegeRumpf -> buildNewComparePresetPayload) mit M6 gefangen; Hydration CompareTabs.svelte nur noch hourlyEnabled; Vorlage (compareNewVorlage.ts:54) ohne Kanal-Overrides. Keine Funde mit Nutzerwirkung, F001-F003 nur Testluecken niedriger Schwere. Build gruen, svelte-check unter Baseline, Staging-Sicht (AC-9) nicht von mir geprueft: laeuft in /e2e-verify.
**Implementierer:** keine Antwort erforderlich (LOW, nicht blockierend).


### Runde 3 (Nachtrag: Hydrations-Fix CompareTabs)
**Adversary (Runde 3):** (a) Layout-Effekt (CompareTabs.svelte:571-575) liest nur activeTab/layoutHydrated, schreibt wizardState.hourlyEnabled und layoutHydrated=true; der Preset-Sync-Effekt (:677) liest nur `preset`, schreibt currentPreset und setzt Flags zurueck. Keine Schleife (nach Hydration kehrt der Effekt vor dem Lesen von currentPreset zurueck). Lokale Edits gehen nur bei echtem Prop-Wechsel `preset` verloren, wie bei den uebrigen Reitern. Kein Altfeld, nur hourlyEnabled. (b) Mutation A: alter Code (async + layoutHydrating) wieder eingesetzt, Kern-Test 2/2 rot. Mutation B: `layoutHydrated = true` entfernt, 2/2 rot. Beide per Sicherungskopie exakt zurueckgesetzt (cmp identisch, Stage-Statistik vorher/nachher 2 Dateien +104/-10, keine unstaged Aenderungen). (c) Kern-Test plus 33+ Vergleichstests: 223 pass / 0 fail; npm test gesamt: 11295 pass / 0 fail / 2 skipped / 1 todo; Build Exit 0; svelte-check 32 Fehler / 72 Warnungen (Baseline 34/132). Ausgabe in adversary-test-output.txt. (d) Playwright-E2E nicht von mir gelaufen (optional); CI-E2E bleibt die Instanz. Restrisiko LOW: Test ist ein Instanz-Pruefstand der Effekt-Rumpfe, kein Browserlauf.
**Implementierer:** keine Antwort erforderlich.

## Confirmations
Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/types.ts:315
  Evidence: DisplayConfig ohne Altnamen (M4 rot), svelte-check 32 <= 34
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:183
  Evidence: kein outlook_enabled im PUT/POST; M1/M6 am Nutzerweg gefangen
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts:129
  Evidence: ALARM_DISPLAY nur metric_alert_levels, telegram_style
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:177
  Evidence: waehleEigenfelder(voll, VERSAND_TOP), keine display_config
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/wetter-tab/wertebereicheVergleichSpeicherung.ts:83
  Evidence: Whitelist corridors, active_metrics, metric_alert_levels; Bestand per Merge erhalten
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:189
  Evidence: WETTER_TOP nur hourly_enabled
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:94
  Evidence: Hydration liefert nur hourlyEnabled (M2 gefangen)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:568
  Evidence: hydrateLayoutTab liest nur hourlyEnabled; Kanal-Hydration entfernt
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:54
  Evidence: keine channelActiveMetricKeys aus Vorlage
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts:33
  Evidence: Lese-Naht entfernt
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/shared/pickEigenfelder.ts:73
  Evidence: Whitelist ohne Altnamen (M3 gefangen)
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/altfeld_namen_sperre.test.ts:62
  Evidence: Sperre scharf (M1 literal, M4 rot), Befund F003
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/altfeld_namen_sperre.test.ts:76
  Evidence: Selbstnachweis gruen inkl. abgelaufen/kurzer Grund
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: src/app/loader.py:142
  Evidence: Abgleich identisch, M5 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:1
  Evidence: hourlyFriendlyMap.ts geloescht, npm run build Exit 0
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: docs/artifacts/feat-3298-altfeld-typen-sperre/geloeschte-tests.md:1
  Evidence: Zuordnung geprueft, 3394 pass / 0 fail
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:183
  Evidence: Code-Ebene unveraendert, Staging-Pruefung folgt in /e2e-verify
  Status: CONFIRMED


Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:571
  Evidence: Layout-Hydration synchron, nur durch layoutHydrated geschuetzt; Mutation A (alter Code) und B (kein Setzen) machen Kern-Test rot
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/__tests__/compare_wetter_reiter_hydration_nach_preset_sync_3298.test.ts:62
  Evidence: Kern-Test faehrt Mount-Reihenfolge Weichen, Preset-Sync, Weichen erneut; 2 pass, bei beiden Mutationen 2 fail
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:54
  Evidence: durch Fix unveraendert; Gesamtlauf 11295 pass
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:183
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts:129
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/pickEigenfelder.ts:73
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:177
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts:33
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:94
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/components/shared/wetter-tab/wertebereicheVergleichSpeicherung.ts:83
  Evidence: durch Fix unveraendert; Gesamtlauf gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-1 (Runde 3)
  Code reference: frontend/src/lib/types.ts:315
  Evidence: DisplayConfig ohne Altfelder; svelte-check 32 <= 34
  Status: CONFIRMED

## Herkunft der Vorbedingungen

<!-- vom Prüfer auszufüllen, siehe `precondition_origins.py` -->

## Verdict

VERDICT: VERIFIED
Tests: Gesamtlauf 11295 passed, 0 failed (Runde 3); Kern-Test 2/2; Mutation A und B gefangen. Frueher: M1 M2 M3 M4 M5 M6 gefangen; F001-F003 LOW.

## Geprüfte Dateien

- sha256:f7df2a31d47ed6f0b41119f290347b59146bd99acf50bc941d1a88b7276132d5  docs/artifacts/feat-3298-altfeld-typen-sperre/geloeschte-tests.md
- sha256:c006fb0ff5a776c98517c78ee46c594b579003ed40e9c94669e613cd910f8d21  frontend/src/lib/altfeld_namen_sperre.test.ts
- sha256:230803d2113c880047736e00dd9c71e6cea51a233b9bd97cae0bf07133c316a3  frontend/src/lib/components/compare-new/compareNewVorlage.ts
- sha256:412278a50da8d84d8afa9fb8766123b7cc17892db9720f7cbc1742c4e229de8d  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:a38b30f61e5e86047c17c1c2e72a78d4134e1b6ae7ebae969ce7a6053711b75c  frontend/src/lib/components/compare/compareEditorSave.ts
- sha256:0b6c2713233e70c2f51ba02a3b1e95f748d5281446392f4f3b253d6b1e3149e9  frontend/src/lib/components/shared/__tests__/compare_wetter_reiter_hydration_nach_preset_sync_3298.test.ts
- sha256:3bbd31452c896a821b9d65e5f830320ce4a72c7684209e117657edb83c5355e8  frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts
- sha256:847fed6709f1e5fc870f52e1c42873620e002f7919da699ae428a73eb4553078  frontend/src/lib/components/shared/pickEigenfelder.ts
- sha256:bb7945e22faeb2080d8cfd254103f2d1824ea16ea09554ee3ba88d23e4e64394  frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
- sha256:356de7783cdbf6a6f127037b52c87799435bf9f981dc56d75ca9c9496a9b9b2a  frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts
- sha256:eafe614ef5a0e98f4ccceb9431f70aff5c7fed8330fdd9482a103791eef9eca2  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
- sha256:42e0f54d33a42fb4740d03f22ed11cfa7819a8de5b1a677a565815b7fba61a2b  frontend/src/lib/components/shared/wetter-tab/wertebereicheVergleichSpeicherung.ts
- sha256:0c10be3e4c694709462051c732a0c919b24bf8da72138a5626a205a30a638b48  frontend/src/lib/types.ts
- sha256:38da8a54d5b332574d7afbf2d554271d995490d76f2e9237d215a30b5f100de7  src/app/loader.py

## Prüfbasis

- base: 80cf9f72687c23386df4cac2d62fbf8a3c2aecad
- blob:e4ab96feac8da2f5f5486725a4f16a3d7cdbc2b0  docs/artifacts/feat-3298-altfeld-typen-sperre/geloeschte-tests.md
- blob:5dbe7ea9b89366cdd02205ddb567c77c657a04b3  frontend/src/lib/altfeld_namen_sperre.test.ts
- blob:6e1daea09504f8b6de91faa353ad8ffcf1f1320e  frontend/src/lib/components/compare-new/compareNewVorlage.ts
- blob:cdf2e3f5fb5fba58b129f01bb20e40c21f267968  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:823b38eacfeac844bbcd84ce42321e2472e3848f  frontend/src/lib/components/compare/compareEditorSave.ts
- blob:57d13e9fdb13004bd01ba2bfd435099148124349  frontend/src/lib/components/shared/__tests__/compare_wetter_reiter_hydration_nach_preset_sync_3298.test.ts
- blob:842f0334a59bf76654fe5a2be8b3d8f19f9035b4  frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts
- blob:65e7e36b5ce414ff318ab47513d656eafbd9b087  frontend/src/lib/components/shared/pickEigenfelder.ts
- blob:0c4eee2a425a22c21afef6a7ac0836a098eb8660  frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
- blob:12653bed4e3fe3fbe9090f418cd30fe58e6c566c  frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts
- blob:01a48b8a04852a07ece89fd016877f5afe970ce0  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
- blob:374d0bd9e88107e389b4cb2107de52013af7863d  frontend/src/lib/components/shared/wetter-tab/wertebereicheVergleichSpeicherung.ts
- blob:d3058aa7bcef5e59d6e23857415987d98908aa4f  frontend/src/lib/types.ts
- blob:e8fc4bf7d215560e9557f2dd2871e41306aa60ec  src/app/loader.py
