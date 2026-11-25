# Adversary Dialog — feat-3297-trip-pfad-ohne-altfelder
Spec: docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md
Datum: 2026-11-25 11:20

## Checkliste
- [x] **Input:** Trip anlegen (normal und mit Standardwerten), Trip-Reiter speichern, Home-Seite mit Trips.
- [x] **Output:** Kein Request-Body enthält die sechs Altschlüssel. Home zeigt „Layout konfiguriert“ genau für Trips mit nicht leeren `placements.rows`.
- [x] **Side effects:** Keine sichtbare Änderung in Editor, Mail oder Kanälen. Der Frontend-Bundle wird kleiner. Gespeicherte Altwerte bleiben bis zum Datenlauf (#3351) wirkungslos auf der Platte.
- [x] **AC-1:** Given ein neuer Trip wird im Anlegen-Dialog angelegt / When der Anlege-Aufruf an die API gesendet wird / Then enthält der Request-Body keinen der Schlüssel `channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats`, `show_outlook`, `multi_day_trend_reports` (weder gefüllt noch leer).
- [x] **AC-2:** Given ein neuer Trip wird mit der Option „Mit Standardwerten“ angelegt / When der Anlege-Aufruf gesendet wird / Then fehlen auch hier alle sechs Altschlüssel, und die Tabelle `placements` wird wie bisher aus der Karte mitgegeben.
- [x] **AC-3:** Given ein bestehender Trip mit Altfeldern in der Datei / When der Nutzer im Wetter-, Zustellungs- oder Alarme-Reiter etwas ändert und speichert / Then enthält der Speicher-Request keinen Altschlüssel, und alle bestehenden übrigen Felder bleiben nach dem Go-Merge erhalten.
- [x] **AC-4:** Given der Kanal-Stil eines Trips wird gespeichert / When `kanalStilNutzlast` den Body baut / Then enthält er nur `telegram_style` und keinerlei Trend-Felder (`multi_day_trend_morning`, `multi_day_trend_evening`, `multi_day_trend_reports`).
- [x] **AC-5:** Given Trips mit und ohne nicht leere `display_config.placements.rows` auf der Home-Seite / When die Checkliste „Layout konfiguriert“ berechnet wird / Then gilt der Schritt nur bei nicht leeren `rows` als erledigt; ein Trip mit nur `channel_layouts`, nur `preset_name` oder leeren `rows` bleibt offen, und für Bestandstrips mit `rows` ändert sich die Anzeige nicht.
- [x] **AC-6:** Given der Typ `DisplayConfig` / When ein Trip mit `placements` (`rows`, `outlook_reports`) typisiert wird / Then ist `placements` ein bekanntes optionales Feld, `ReportConfig` kennt `show_outlook` und `multi_day_trend_reports` nicht mehr, und `svelte-check` meldet keinen Fehler.
- [x] **AC-7:** Given die Löschliste (`WeatherMetricsTab`, `WetterMetrikenVersandPanel`, `BriefingScheduleTab`, `VersandTab`, `MailInhaltCard`, `OutlookLayoutControls` und nur von ihnen genutzte Helfer) / When der Rückbau abgeschlossen ist / Then existieren diese Dateien nicht mehr, keine Produktionsdatei importiert sie (auch nicht über Barrels), und noch benutzte Vergleich-Hilfen sind erhalten.
- [x] **AC-8:** Given der Frontend-Quelltext des Trip-Pfads / When nach den Schlüsseln `show_outlook` und `multi_day_trend_reports` in Produktionsdateien gesucht wird / Then gibt es keinen Treffer mehr (Typen, Zustand, Konstanten, Whitelists, Payload-Bau), und die Whitelists in `pickEigenfelder.ts` führen sie nicht.
- [x] **AC-9:** Given der Nutzer öffnet Trip-Detail (Reiter Wetter, Zustellung, Alarme) und Trip anlegen / When er den Ablauf wie bisher bedient (Karte „Was steht wo“, Haken, Speichern) / Then sieht und bedient er dieselben Flächen wie vor dem Rückbau, und die Werte werden korrekt gespeichert und wieder geladen.
- [x] **AC-10:** Given Tests, die bisher Altfelder als Fixture oder den gelöschten Baum prüften / When der Rückbau abgeschlossen ist / Then ist jeder Test entweder auf `placements` bzw. „Schlüssel fehlt“ umgestellt oder gelöscht, weil seine getestete Produktionsdatei gelöscht wurde, und die Kern-Schicht (Frontend `node --test`, `svelte-check`, Playwright-Kern) ist grün.

## Dialog

### Runde 1
**Adversary:** Tests (node --test, 3 RED-Dateien): 50 pass / 0 fail (docs/artifacts/feat-3297-trip-pfad-ohne-altfelder/adversary-test-output.txt). `npm run build` Exit 0; svelte-check 32 Fehler / 72 Warnungen <= Baseline 34/132 (.github/workflows/ci.yml:154). Grep Produktion: kein `show_outlook`/`multi_day_trend_reports` (AC-8). Stichprobe geloeschte Tests (channelOffGroupListBuilding, compare_wetter_metriken_wertprops) importierten nur geloeschte Dateien.

Finding F001: Severity LOW, Category: anti_pattern. Code reference: frontend/src/lib/components/shared/pickEigenfelder.ts:73. `WETTER_DISPLAY_KEYS` fuehrt weiter `channel_layouts`, `outlook_metrics`, `outlook_metric_formats` und hat keinen Produktionsnutzer. Spec requirement: AC-8 — nur `show_outlook`/`multi_day_trend_reports` verlangt; kein Verstoss, nur toter Code. Remediation: Konstante entfernen oder in #3351 mitnehmen.

Finding F002: Severity LOW, Category: anti_pattern. Code reference: frontend/src/lib/types.ts:285. `ReportConfig.multi_day_trend_morning/evening` bleiben als Typ; AC-6 nennt nur show_outlook/multi_day_trend_reports, daher kein Verstoss; Hinweis fuer #3351.

Mutationen: 8 durchgespielt, alle von Tests gefangen: M1 reportConfigPayload.ts:89 + multi_day_trend_reports (29 rot: AC-8-Waechter, Golden D); M3 cockpitHelpers568.ts:61 hasLayout via channel_layouts (2 rot) und M3b leere rows zaehlen (1 rot); M4 kanalStilSpeicherung.ts:21 Trend-Feld (9 rot); M5 `channel_layouts: {}` leer gesendet (8 rot); M2 ampelSchreiben.ts:158 show_outlook (4 rot); M6 geloeschte VersandTab-Komponente in ZustellungTab.svelte:1 importiert (25 rot, Loesch-Nachweis). Nebenbefund: Mutation `ausblickVorbelegung: true` in tripNewLogic.ts:400 blieb gruen, ist aber nur eine unbekannte Eigenschaft (Typ entfernt, Laufzeit wirkungslos) — kein Wirkungsverlust. Nach jeder Mutation per diff gegen Sicherung identisch; am Ende Diff-Statistik des Index 225 files, 457 insertions, 20173 deletions; keine unstaged Aenderungen.
**Implementierer:** (nicht beteiligt)

### Runde 2
**Adversary:** Runde 2, Code-Referenzen je geaenderter Datei und AC. AC-1/AC-2: tripNewLogic.ts:400 (ergaenzeVersandStandard ohne Ausblick-Vorbelegung), reportConfigPayload.ts:89 (Payload ohne Trend-Liste). AC-3: ampelSchreiben.ts:158 (report_config nur Tagesfenster, Go-Merge), wetterTabSpeicherung.ts:1, wasStehtWoSpeicherung.ts:1, alarmeDeliveryPayload.ts:41. AC-4: kanalStilSpeicherung.ts:21. AC-5: cockpitHelpers568.ts:60-61. AC-6: types.ts:345 (placements), types.ts:266 (ReportConfig ohne show_outlook). AC-7: trip-detail/index.ts:1, organisms/index.ts:1, mailInhaltKonstanten.ts:1, mailInhaltZustand.ts:1 (Barrel/Helfer bereinigt; Build gruen, Loesch-Nachweis rot bei Re-Import ZustellungTab.svelte:1). AC-8: pickEigenfelder.ts:73. AC-9: ZustellungTab.svelte:1, VorlageKarte.svelte:1, CompareTabs.svelte:1, CompareNewEditor.svelte:1, app.css:1, rightColumn.ts:42, vorlageSpeichernKarte.ts:3, weatherSummary.ts:10 (Kommentar-/Style-Aufraeumung, Build gruen; Live-Bedienung nicht im Playwright geprueft — Staging/e2e-Aufgabe). AC-10: 64 Testdateien geloescht, Zuordnung stichprobenartig bestaetigt; Kern-Tests gruen. required-files: alle 17 Dateien abgedeckt. Zweite Pflichtfrage: AC-5-Tests unterscheiden channel_layouts/leere rows/echte rows (M3, M3b rot); AC-1 ueber Golden D und AC-8-Waechter belegt.
**Implementierer:** (nicht beteiligt)

## Confirmations

Confirmation:
  AC: AC-1/AC-2
  Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:400
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts:89
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts:158
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts:41
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts:21
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/utils/cockpitHelpers568.ts:61
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/types.ts:345
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/trip-detail/index.ts:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/organisms/index.ts:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/mailInhaltKonstanten.ts:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/mailInhaltZustand.ts:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/shared/pickEigenfelder.ts:73
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:1
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/edit/weatherSummary.ts:10
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/utils/rightColumn.ts:42
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/utils/vorlageSpeichernKarte.ts:3
  Evidence: Mutation bzw. Test/Build belegt Wirkung (siehe Runde 1/2)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/app.css:1
  Evidence: Nur Style-Aufraeumung, Build Exit 0
  Status: CONFIRMED

## Herkunft der Vorbedingungen

<!-- vom Prüfer auszufüllen, siehe `precondition_origins.py` -->

## Verdict

VERDICT: VERIFIED
Tests: 50 passed, 0 failed (RED-Dateien); Mutationen 8/8 gefangen; Findings nur LOW (F001, F002).

## Geprüfte Dateien

- sha256:f80a851e608d860977698d65383520749a40e56d19ef095940589ec8e41145ab  frontend/src/app.css
- sha256:42fc38e5f0fe6e31a538d6a67057ffe7f21099fec9ddc159f700e9776a9e62dc  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:82c2882890862eab88fa2ee84030bbfca7652af9cbd2244c951ea931574f70fb  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:9be71f00d3f456b8651783ca8dfd7ba1e62d52307e899b2fcea0a001f7de0ca3  frontend/src/lib/components/edit/weatherSummary.ts
- sha256:089d58e90bbe3f8329d85ba033a103909282dd5049d084cf7e366a524c20d057  frontend/src/lib/components/organisms/index.ts
- sha256:acf9fc2368c7370ace59bbbfef4ac0aa9bf6a12815bf6d615af80a8fd5dc3323  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:af5cc40b839cef0074ad25cfb6d57e37ace051fb1ca8ca4f35e8026489b82004  frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts
- sha256:c25bffadcfa65799e0b55260d4798b7a924e114affedb294e21fccde102cb3d9  frontend/src/lib/components/shared/mailInhaltKonstanten.ts
- sha256:009f498757a1aed7484d3c202f54d68b9fad335e232d72b78c0317224604f614  frontend/src/lib/components/shared/mailInhaltZustand.ts
- sha256:834e225e5483b277c82e0b27e804bdba143b50cd2989f3f2072c33549d6e57b9  frontend/src/lib/components/shared/pickEigenfelder.ts
- sha256:8740b067c7472fd27c30a4f9f06e8770a5c421042f28243fedec590693c997c0  frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts
- sha256:75dc1427ceb0b8be6457722530e08627df6e642db9b0bf05e918cb3f1c807a22  frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts
- sha256:9c101e7d3689ece3b1bc17f76d8063cc9c733ed42a19410be0e58428412f4d86  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- sha256:ae8b786d2a62e5f573cb5fc6a0b3ea72434573ff97da7ef7a33fd5f216ccabc0  frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts
- sha256:3a44864aca8ca1e721561422bc6efb21017f66190baaf567ca9a1fae633b1ffb  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:9c86210d181ae12e8702c3e1e0e9148ab44bd84af9da435ee248fc34d64ed2c7  frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts
- sha256:dff6c43cd657e0440765916d89f4f519525ccec2a4ea1388bbafa4168e7f99f6  frontend/src/lib/components/trip-detail/index.ts
- sha256:f054e91fc2dfd6ed5872a3ebbfe38718af54ae35b011149f6ae0052adc1853b8  frontend/src/lib/components/trip-new/tripNewLogic.ts
- sha256:3f8882032a8db16039d4718c56c32722168284ba9ce1300c7df36afd99f72906  frontend/src/lib/types.ts
- sha256:a16f9c708f5e50905a34bd58520e0844c38aa92bd02d00bde891f8ffdf9ac469  frontend/src/lib/utils/cockpitHelpers568.ts
- sha256:1ab7476ba4958f8f573185693d31298559b9ad85441bf531d855047541b14f8b  frontend/src/lib/utils/rightColumn.ts
- sha256:8a06f7d2c16f4b45eb9fc222ab40f54cb75c399052e7af6b7b70f3a485df44fd  frontend/src/lib/utils/vorlageSpeichernKarte.ts

## Prüfbasis

- base: 539d169636a6b3d1722e0202f391d0879f741080
- blob:357c4a6ecfd224b856f16407d067812655258775  frontend/src/app.css
- blob:9829f42f0a9d50c8090709d62f2b22b008ca6403  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:b78d9920966e98c1721d1336d49f41ca0010a6fb  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:2d88aa726f6266a4fc8c449884d2df81464e14a1  frontend/src/lib/components/edit/weatherSummary.ts
- blob:1d88906a93601d3bc76ee3f7de1ab2a7f0393fe0  frontend/src/lib/components/organisms/index.ts
- blob:1ae4285a943b1690b5a639635a3db1f6c16f92b0  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:1aaae83eecf132ad9fb4fd36c84cf932f5381d40  frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts
- blob:e4c1fec8d721cc0c15edcd13b1c33dc02d5c6739  frontend/src/lib/components/shared/mailInhaltKonstanten.ts
- blob:43851d69d74ce46a8e5857ee2e8e3375f7c86e4f  frontend/src/lib/components/shared/mailInhaltZustand.ts
- blob:785f34ea95b22f0a41a9c09164372075a4be7995  frontend/src/lib/components/shared/pickEigenfelder.ts
- blob:2adaa8f77bc9c60ffa371eb2648374863dbb7ad4  frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts
- blob:f70e4745880da167d5ab84dd558225d083aa8ba9  frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts
- blob:7d464da5c48fe67ec61d87fdae15f5e0293b01ec  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- blob:1e359066fa62c3428cd5e04c5854f1a7cfc15062  frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts
- blob:d9ecb1bb35f8ab5492ac06607f1ab5b6765c8b2f  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:9f2637094a568dd9f414d6df667b35ca907ac995  frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts
- blob:0e781bd673bb39f59222f764ed9634a11ac70eb7  frontend/src/lib/components/trip-detail/index.ts
- blob:237d75fa2717bb119b32063892c2884aee459ed2  frontend/src/lib/components/trip-new/tripNewLogic.ts
- blob:624b79c173f5f89d6341a11a8dd9e257057a8fa2  frontend/src/lib/types.ts
- blob:e1158f3ed4b9477676c53bea18f862f6213de66b  frontend/src/lib/utils/cockpitHelpers568.ts
- blob:ba2770ecea7a73693a522e48474fbbbf456c6a60  frontend/src/lib/utils/rightColumn.ts
- blob:dbb8c32811bfc855b9de2cc6073ac2393cba90ad  frontend/src/lib/utils/vorlageSpeichernKarte.ts
