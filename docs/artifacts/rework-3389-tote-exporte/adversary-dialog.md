# Adversary Dialog — rework-3389-tote-exporte
Spec: docs/specs/modules/rework_3389_tote_exporte.md
Datum: 2026-11-26 10:53

## Checkliste
- [x] **Input:** Quelltext von `frontend/src` und `frontend/e2e`.
- [x] **Output:** Beide Module exportieren genau die fünf lebenden Hydrations-Funktionen; kein Name der 23 kommt in Code vor; Wächter, Ratschen und Frontend-Suite sind grün; `EINGEFROREN` hat 8 Einträge.
- [x] **Side effects:** keine sichtbare Änderung für Nutzer; Tests, Prüfstand-Hilfen und zwei Produktionsdateien schrumpfen.
- [x] **AC-1 (Struktur-Wächter):** Given die beiden Module `versandVergleichSpeicherung.ts` und `weatherMetricsCompareSave.ts` / When der Lösch-Nachweis ihren Quelltext nach `export`-Namen durchsucht / Then ist die Menge der Exporte je Modul exakt die der lebenden Hydrations-Funktionen (Versand: eine, Weather: vier), und keiner der 21 toten Namen samt `VersandSnapshot` und `LayoutSnapshot` ist als Export zurückgekehrt; ein Beleg für Nutzerverhalten ist das nicht, den liefern AC-4, AC-5, AC-8 und AC-10.
- [x] **AC-2 (Struktur-Wächter):** Given der gesamte Quelltext unter `frontend/src` und `frontend/e2e` / When der Wortscan ohne Kommentare nach den 23 Namen sucht / Then gibt es keinen Treffer außerhalb der Lösch-Nachweis-Datei, die 21 gelöschten Testdateien und der Prüfstand `wetterMetrikenVergleichPruefstand.ts` existieren nicht mehr, und die fünf lebenden Exporte haben weiterhin ihre Produktionsaufrufer in `CompareTabs.svelte`, `compareHubHydration.ts` und `compareNewVorlage.ts` (Schutz gegen Rückkehr toter Namen, kein Verhaltensnachweis).
- [x] **AC-3 (Struktur-Wächter):** Given der Selbstnachweis des Wächters / When er auf eingebettete Mini-Quellen läuft / Then meldet er ein wieder eingeführtes `export function erstelleVersandVergleichSpeicherung`, meldet einen neuen Export `neuerExport` als Abweichung von der Exportmenge, meldet einen Importfund eines gelöschten Namens in einer anderen Datei und meldet keinen Fund, wenn der Name nur in einem Kommentar steht (der Wächter selbst wird geprüft, damit er nicht still blind ist).
- [x] **AC-4:** Given ein Ortsvergleich-Preset mit gesetztem, fehlendem oder `null`-wertigem Tagesfenster / When die lebende Hydration `hydrateDayWindowFromPreset` es liest / Then liefert sie die gespeicherten Stunden (6 und 21) oder den Trip-Standard 4 und 19.
- [x] **AC-5:** Given die 21 gelöschten Testdateien und die 15 umgebauten Dateien / When die Löschung geliefert ist / Then bleiben genau diese Fälle als lebender Prüfling stehen: in `hub_versand_inline` die 3 Fälle des Blocks `AC-36 (Basis): hydrateVersandFieldsFromPreset` und die 4 Fälle des Blocks `hubActivationBanner`; in `versand_vergleich_premium_sms` der Fall `hydrateVersandFieldsFromPreset liest preset.send_premium_sms`; in `s3a2794_zustellung_vergleich_ein_speicherer` die Fälle 1 und 2 (Cooldown, Stille Stunden: ein PUT über den Alarme-Speicherer); in `alarme_vergleich_kein_zurueckschreiben` der Block `S2-AC-3`; in `alarme_vergleich_kanalwahl_speicherweg` 10 Fälle, darunter `AC-57` am Wertebereiche-Teil-PUT; in `compare_alarm_versand_nutzlast_trennung` die 3 Alarm-/Kanal-/Anlege-Blöcke; in `compare_retry_reiterwechsel_eingabe_bleibt` 9 Fälle ohne `F301a`/`PX2`; in `hub_nochmal_speichern_ueber_reiterwechsel` alle 3 Fälle am Wertebereiche-Speicherer; in `hub_put_queue` 5 Fälle, davon `F002-Integration` und `F003-Regression` am Alarme-Speicherer; in `compare_outlook_metric_formats_persistenz` die 3 Fälle des Blocks `#2049 F004`; in `fix_3061_hub_hydrierer` 8 Fälle, darunter `AC-4` mit Hydrations-Ergebnis (`activeMetricKeys` null, Layout); in `feat3276_vergleich_ohne_altfelder` 8 Fälle, darunter `Alarm- und Wertebereiche-Speicherer senden keinen Altschluessel`; in `feat3298_vergleich_ohne_altfelder` die Reiter-Schleife (alarme, wertebereiche), der neue Fall `zustellung`, der `hydrateLayoutFieldsFromPreset`-Fall und `Lese-Naht channel_active_metrics ist entfernt`; in `wetter_metriken_hydration_vollstaendig_vor_baseline` die 5 Fälle des Blocks `AC-3 (Prädikat)`; in `wetter_metriken_und_wertebereiche_teilen_active_metric_keys` Fall 2 am Wertebereiche-Speicherer. Die Zusicherungen der gelöschten Dateien (Pausieren-Flush, Keepalive, `end_date`, Eigenfelder, kein Wetter-Feld in der Zustellung) stehen am lebenden Zustellungs-Speicherer in `zustellungSpeicherung.test.ts` (`ac10_bis_datum_und_zurueck`, `ac32_nur_morgenzeit_ein_put_fremdfelder_unveraendert`, `ac26_vergleich_cooldown`, `NIE`-Liste) und `rework_3020_zustellung_ifmatch_keepalive.test.ts`.
- [x] **AC-6 (Struktur-Wächter):** Given die Prüfstände / When die Löschung geliefert ist / Then ist `wetterMetrikenVergleichPruefstand.ts` gelöscht, `compareReiterAufbauPruefstand.ts` kennt nur noch die Reiter `alarme` und `wertebereiche`, `versandVergleichPruefstand.ts` enthält nur noch `makePreset` und `createController`, `goMergeServerPruefstand.ts` kennt keine Eigenfelder für `versand` und `wetterMetriken`, und die Matrix-Tests (`compare_konflikt_nutzlast_am_eintrag`, `compare_reiter_nutzlast_nur_eigene_felder`, `feat3298` mit Fall `zustellung`, `compare_retry_fehlerpfade_kein_verlust` mit Alarme-Ersatz im Teil-Erfolg-Fall) laufen grün; die Prüfstand-Struktur wird vom Wächter aus AC-2 gegen Rückkehr gesichert, das Verhalten belegt AC-5.
- [x] **AC-7 (Struktur-Wächter):** Given die Ratschen und Katalogverweise / When die Zählstellen nach dem Löschen gegengemessen werden / Then ist `EINGEFROREN_SOLL_ANZAHL` von 10 auf 8 gesenkt (Einträge `versandVergleichSpeicherung.ts:236` und `weatherMetricsCompareSave.ts:364` entfernt), die ac2-Endbilanz, ihr Spiegel `rework_2276_s6h_ac2_endbilanz.md` und `endbilanz_summenzeile_stimmt.test.ts` (HERKUNFT 1) führen 5/2/1 = 8, die Fallliste verweist beim Fall `D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend` auf `editor_standard_gleich_ausgabe_3020.test.ts`, die Positivkontrolle in `totcode_rueckbau_speicherweg.test.ts` nennt `hydrateVersandFieldsFromPreset` und `hydrateWeatherMetricsFromPreset`, und `BEKANNTE_WAISEN`, `BESTAND_OBERGRENZE`, `hoechststand`/`HOECHSTSTAND`, `E2E_MIN_*` und die `rework_3020_*`-Zahlen sind unverändert; die Werte sind verbindlich, jede Abweichung ist ein Umsetzungsfehler und führt zu einem Spec-Nachtrag, nicht zu einer stillen Anpassung.
- [x] **AC-8:** Given der Ortsvergleich-Editor und der Hub (Reiter Alarme, Wetter, Zustellung, Hydration beim Öffnen, Aktivieren und Pausieren, Konfliktbehandlung) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die lebenden Editor- und Hub-Tests (`hub_versand_inline`, `compare_versand_hydration_unter_wetter_metriken`, `fix_3061_hub_hydrierer`, `compareActiveMetricsStorageFormat`, `compare_retry_reiterwechsel_eingabe_bleibt`, `compare_hub_pausieren_flusht_vorher`, `rework_3020_vergleich_parallele_schreiber`, `s3a2794_flush_hydration_kette`, `zustellungSpeicherung`) laufen vollständig grün, die `svelte-check`-Zahlen (Fehler und Warnungen) wurden vor dem Löschen gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
- [x] **AC-9 (Struktur-Wächter):** Given Browser-Specs, CI-Konfiguration, Hooks und Produktionscode außerhalb der Löschmenge / When die Scheibe geliefert ist / Then sind `frontend/e2e/`, `.github/` (darin `ci_e2e_specs.txt` und `ci.yml` mit `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`) und `.claude/hooks` gegenüber `origin/main` unverändert, und die einzigen geänderten Produktionsdateien sind die zwei Module und `CompareTabs.svelte`.
- [x] **AC-10:** Given ein gespeicherter Ortsvergleich mit Versand-Einstellung (Premium-SMS, Zustellzeit), Tagesfenster, Wetter-Metrik-Auswahl und Stundenverlauf-Schalter / When der Nutzer ihn im Editor oder Hub öffnet und die Hydrations-Funktionen ihn laden / Then sind die Versand-, Tagesfenster-, Wetter-Metrik- und Layout-Felder des Editors mit den gespeicherten Werten gefüllt, und ein Altbestand ohne diese Felder bleibt mit Standardwerten (Metrikauswahl `null`, Tagesfenster 4 bis 19) unverändert.

## Dialog

### Runde 1
**Adversary:**
Volle Frontend-Suite im Worktree: 11893 Tests, 11876 pass, 0 fail, 2 skipped, 15 todo. svelte-check: 32 Fehler, 70 Warnungen, 49 Dateien, deckungsgleich mit dem Stand vor der Löschung. Python (4 benannte Dateien): 124 passed. Wortsuche über frontend (src, e2e, Konfigs, .py/.go/.json/.yml im Repo) nach den 23 Namen: Treffer nur in der Lösch-Nachweis-Datei, in Kommentaren (hub_versand_inline, versand_vergleich_premium_sms, compare_hub_alarme_bridge, compare_outlook..., feat3276/3298) und in den zwei internen, nicht exportierten Typen. Keine dynamischen oder String-Importe. Die 21 Exporte sind tot.
Mutationen an den lebenden Exporten (26 Testdateien): 22 von 24 Verfälschungen fielen rot (Versand-Felder, Tagesfenster tauschen und Standardwerte, `null` zu `[]`, Katalog-Auswertung, Gate `&&` zu `||`/`true`/einseitig). Überlebt haben: W7 `hourlyEnabled: true` statt `preset.hourly_enabled ?? true` (F001) und W13 Standard-Katalog `[]` (F002). Wächter: Export zurück (G1, G2), Prüfstand zurück (G3), Namen in anderer Datei (G4), Zählstelle ±1 (G5, G6), Spiegel-Summe (G7), Reiter `versand` zurück (G9) alle rot; G8 (zusätzlicher Export im Versand-Prüfstand) blieb grün (F003). Mutationen am lebenden `compareHubPersistenz.ts` (Schreibschlange, Pausieren, Deep-Copy): 5 von 7 rot, `statusZielNutzlast`-Zweig überlebt, aber dort gab es auch vor der Löschung keinen Test (kein Abdeckungsverlust).
**Implementierer:** Keine Antwort eingeholt (Prüfauftrag ohne Rückkanal); Befunde gehen an den Hauptkontext.

### Runde 2
**Adversary:**
Gegenprobe der Abdeckung: die 22 gelöschten Tests prüften über die toten Speicherer nur `compareHubPersistenz.ts`-Pfade, die lebende Tests (`hub_put_queue`, `compare_hub_pausieren_flusht_vorher`, `zustellungSpeicherung`) weiter bewachen (P1, P2, P3, P5, P7 rot). Das Teil-Erfolg-Szenario in `compare_retry_fehlerpfade_kein_verlust` ist fachlich gleichwertig: ein zweiter Alarme-Aufbau mit altem ETag wird mit 412 abgelehnt, Server-Stand vor/nach unverändert (stärker als vorher). Nachzüge in `rework_3020_testtabelle.md` (G38, E017, E018, E023) verweisen auf existierende Tests mit denselben Zahlen (8; 5/2/1); der Testtitel `die Summenzeile nennt 3 HERKUNFT` ist veraltet (F004). Die Abweichung der AC-4-Prüfung `hydrateLayoutFieldsFromPreset` bleibt: kein Test hydriert ein Preset mit gespeichertem `hourly_enabled: false`.
**Implementierer:** Keine Antwort eingeholt.

### Runde 3
**Adversary:**
Nachprüfung nach Fix-Loop 1. W7 (`hourlyEnabled: true`) rot durch den neuen Fall `hourly_enabled: false`; W13 (Standard-Katalog `[]`) rot durch den neuen Fall ohne Katalog-Argument; G8 (zusätzlicher Export im Versand-Prüfstand) rot durch die neue Exportmengen-Prüfung; G1 bis G7 und G9 weiter rot. Volle Suite: 11896 Tests, 11879 pass, 0 fail. Neue Schwächen: keine gefunden. Der Katalog-Test setzt die Registrierung per `afterEach` zurück (kein Zustandsleck), die Prüfstand-Liste ist wie bei den Modulen sortiert verglichen.
F001 bis F004 sind behoben (F004: Titel `1 HERKUNFT` und E024 nachgezogen).
**Implementierer:** Fix-Loop 1 laut Hauptkontext, nur Tests.

## Findings

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:75
  Description: `hydrateLayoutFieldsFromPreset` liefert `{ hourlyEnabled: preset.hourly_enabled ?? true }`. Mutation `hourlyEnabled: true` (gespeicherter Wert wird ignoriert) lässt alle 26 Zieldateien plus Wächter grün. Die lebenden Fälle (`fix_3061_hub_hydrierer` AC-4, `feat3298` Z.280) hydrieren nur Altbestand oder ein Preset mit `hourly_enabled: true`.
  Spec requirement: AC-10 — der Stundenverlauf-Schalter eines gespeicherten Ortsvergleichs wird mit dem gespeicherten Wert gefüllt.
  Conflict: Ein Ortsvergleich mit ausgeschaltetem Stundenverlauf käme im Editor wieder eingeschaltet an, und kein Test fiele rot. Die Zusicherung ist nur am Standardwert geprüft, nicht am gespeicherten Wert. Die Lücke bestand vor der Scheibe, die Spec behauptet sie aber als belegt.
  Remediation: Einen Fall `hourly_enabled: false` -> `hourlyEnabled === false` in `fix_3061_hub_hydrierer.test.ts` oder `weather_metrics_hydration_tagesfenster.test.ts` ergänzen.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:50
  Description: Standardargument `catalog = registeredCompareMetricCatalog()` auf `[]` gesetzt: kein Test rot. Beide Produktionsaufrufer (`CompareTabs.svelte:528`, `compareHubHydration.ts:132`) übergeben den Katalog; der Default wird nirgends genutzt.
  Spec requirement: AC-8 — lebende Hydrations-Tests belegen das Verhalten.
  Conflict: Ein Default ohne Aufrufer und ohne Test; äquivalent zu totem Code, kein Nutzerrisiko.
  Remediation: Default entfernen (Parameter verpflichtend) oder einen Test ohne Katalog ergänzen.

Finding:
  ID: F003
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/__tests__/versandVergleichPruefstand.ts:12
  Description: AC-6 verlangt, dass der Prüfstand nur `makePreset` und `createController` enthält. Ein zusätzlicher `export function flushX()` (G8) lässt Wächter und Matrix-Tests grün; gesichert ist nur die Rückkehr der 23 alten Namen (Wortscan).
  Spec requirement: AC-6 — Prüfstand enthält nur noch `makePreset` und `createController`.
  Conflict: Die Struktur ist nicht geprüft, nur die Namen; die Spec räumt das selbst als Struktur-Wächter ein.
  Remediation: Exportmenge der Prüfstand-Datei im Wächter wie bei den Modulen prüfen oder AC-6 auf "keine alten Namen" abschwächen.

Finding:
  ID: F004
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/__tests__/endbilanz_summenzeile_stimmt.test.ts:63
  Description: Der Testtitel nennt noch `3 HERKUNFT`, die geprüften Werte sind jetzt 1. `rework_3020_testtabelle.md` E024 verweist wörtlich auf diesen Titel, deshalb bleibt die Zuordnung formal gültig.
  Spec requirement: AC-7 — Zählstellen und Katalogverweise führen 5/2/1 = 8.
  Conflict: Irreführender Titel; Verweis und Zahl in der Testtabelle passen nicht zusammen, wenn man liest.
  Remediation: Titel auf `1 HERKUNFT` umstellen und E024 gleichzeitig nachziehen.

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:641
  Evidence: Exportmengenprüfung je Modul; G1/G2 (zusätzlicher Export) rot; `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:39` und `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:23` bis `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:82` exportieren genau 1 + 4 Funktionen.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:652
  Evidence: Wortscan über src und e2e; G3 (Prüfstand zurück) und G4 (Name in anderer Datei) rot; eigene Wortsuche bestätigt keinen Treffer im Code; Aufrufer in CompareTabs.svelte:433/517/539/573, compareHubHydration.ts:132, compareNewVorlage.ts:56 vorhanden.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:671
  Evidence: Selbstnachweise (a) bis (e) laufen grün und prüfen eingebettete Mini-Quellen.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:23
  Evidence: W1 (Start/Ende vertauscht), W2 und W3 (Standard 5/20) rot durch `weather_metrics_hydration_tagesfenster.test.ts`.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:39
  Evidence: M1 bis M10 rot durch `hub_versand_inline` (AC-36 Basis), `versand_vergleich_premium_sms` und `s3a2794_*`; Fall Teil-Erfolg in `compare_retry_fehlerpfade_kein_verlust` fachlich gleichwertig; P1, P2, P3, P5, P7 an `compareHubPersistenz.ts` rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/__tests__/compareReiterAufbauPruefstand.ts:35
  Evidence: Reiter nur `alarme` und `wertebereiche`; G9 (Reiter `versand` zurück) rot. Einschränkung F003.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts:297
  Evidence: `EINGEFROREN_SOLL_ANZAHL = 8`; G5 und G6 (9, 7) und G7 (Spiegel-Summe 9) rot; Python-Ratschen 124 passed.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:82
  Evidence: Volle Suite 11876 pass, 0 fail; svelte-check 32/70 unverändert; W8 bis W11 (Gate) rot; Produktions-Build nicht von mir gefahren (Artefakt des Implementierers), svelte-check ohne neue Fehler.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:433
  Evidence: Diff gegen Merge-Base 1a58c297b: frontend/e2e, .github, .claude/hooks unverändert; Produktionsdateien geändert: CompareTabs.svelte, die zwei Module.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`): für TypeScript gibt es keine Verdachtsliste. Die geprüften Hydrations-Funktionen sind reine Funktionen (Preset in, Werte aus); es gibt keine Zuweisungs-Vorbedingungen. Die einzige zustandsabhängige Stelle ist das Gate `wetterMetrikenHydrationAbgeschlossen` (zwei Booleans), geprüft durch W8 bis W11.

## Verdict
**VERIFIED**

F001 bis F004 in Fix-Loop 1 behoben und per Mutation bestätigt (W7, W13, G8 jetzt rot). Alle Checklistenpunkte bewiesen.

## Geprüfte Dateien

- sha256:37010360c040063b712249ace30c3bddcf28dd23501d8bce1d3ffe105391e1bd  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:692c324c541f03e175be5c38b281ffbb4e374deb00fa1468857aeb92c57dfcb4  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:fc55ebc1f0bc292d2cd736891980dd923cc0eaeae31ce140a5ac86a328349ec0  frontend/src/lib/components/shared/__tests__/compareReiterAufbauPruefstand.ts
- sha256:b37616d4edce880b2d5588dc99351b9c9424eaa56f01bd8d7c653453cec195bd  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- sha256:0aaed41643e78d99dcce37849afa54a57474e03feaaf49c9f696672e7cf6cb31  frontend/src/lib/components/shared/__tests__/endbilanz_summenzeile_stimmt.test.ts
- sha256:d96ebb0cc285cb3b6863464f0a85f0d74d9656f4bab0bf049fb5261e2346ce07  frontend/src/lib/components/shared/__tests__/versandVergleichPruefstand.ts
- sha256:bc19f0d48751ab0333e22c7c5775087abddf79db42fb95b873ee04e61308ae1e  frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
- sha256:c3569b4f0722b9871d486ef449899d55aa11b0b5f986f2e4ca61fea3586316b8  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts

## Prüfbasis

- base: 1a58c297b2ab745e69e3c3eca7924ece47a66d7f
- blob:45bdeada7b3283ac1b74ce0dda695f700519db9e  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:18a8ebb76f996d02b2a60e2396ee886c98b55414  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:d5d64809b376d9a613c5082f67307934fe7c79bf  frontend/src/lib/components/shared/__tests__/compareReiterAufbauPruefstand.ts
- blob:dc37b04519755c7b5baa07254671ef7e1dd40e73  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- blob:094f2cb1739ece63e8ebd4993a09e5e126888ca7  frontend/src/lib/components/shared/__tests__/endbilanz_summenzeile_stimmt.test.ts
- blob:40f9eff60e2a77bdff673bf6c64b86e061ef6fc3  frontend/src/lib/components/shared/__tests__/versandVergleichPruefstand.ts
- blob:05188b681963668afcc8942244e34a5c270d83f4  frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
- blob:faf35528fd2aa07f9d4088e3b79331b28b480527  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
