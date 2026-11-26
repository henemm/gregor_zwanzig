# Adversary Dialog — rework-3383-waisen-s1
Spec: docs/specs/modules/rework_3383_waisen_s1.md
Datum: 2026-11-26 00:45

## Checkliste
- [x] **Input:** Quelltext von `frontend/src`.
- [x] **Output:** Wächter grün, solange die Waisenmenge (ohne `AUSNAHMEN`) exakt `BEKANNTE_WAISEN` (26 Einträge) entspricht und `OBERGRENZE_WAISEN` (26) nicht überschritten wird; Löschung ohne Funktionsänderung.
- [x] **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen und Katalog schrumpfen.
- [x] **AC-1:** Given die 14 Dateien der Gruppe S1 (`weather-metrics-tab/*` neun, `trip-detail/{AboutOutputLayout,WeatherV2Kanaele,weatherSaveGate}`, `reportConfigDirty.ts`, `GrundauswahlLeerHinweis.svelte`) / When das Dateisystem nach S1 geprüft wird / Then existiert keine der 14 Dateien mehr, `weatherMetricsCompareSave.ts`, `metricsEditor.ts` und `WaypointPin.svelte` bestehen weiter, und kein Produktionscode importiert die gelöschten Basisnamen.
- [x] **AC-2:** Given `outlookFriendlyCapability.ts` stand bisher in `ERHALTEN` des Lösch-Nachweises und als bekannte Waise im Wächter / When S1 umgesetzt ist / Then steht sie in `GELOESCHT` (nicht mehr in `ERHALTEN`), und der Test "outlookFriendlyCapability.ts ist bis S1 (#3383) bekannte Waise" in `waisen_waechter.test.ts` ist entfernt (an seine Stelle tritt der `GELOESCHT`-Eintrag), sodass kein Test eine nicht mehr vorhandene Datei erwartet.
- [x] **AC-3:** Given der Waisen-Wächter mit den S1-Einträgen gestrichen / When er die Erreichbarkeit ab `routes/` und `src/*.ts` berechnet / Then ist die Waisenmenge (ohne `AUSNAHMEN`) genau `BEKANNTE_WAISEN` mit 26 Einträgen (19 S4, 7 S3), `OBERGRENZE_WAISEN` ist die feste Literal-Konstante 26 (um genau 14 gesenkt), und der Test ist grün; ohne Streichen der S1-Einträge oder ohne Löschung wäre er rot.
- [x] **AC-4:** Given der Selbstnachweis des Wächters an einem erfundenen Mini-Baum / When er die Fälle (a) dynamischer Import, (b) `import.meta.glob`, (c) `new URL('./x', import.meta.url)` und (d) Datei, die nur von einer Testdatei unter `routes/` importiert wird, sowie (e) die Array-Form von `import.meta.glob` durchrechnet / Then gelten (a), (b) und (c) als erreichbar, (d) als Waise, und (e) führt zu einer roten Meldung „nicht unterstützt“ statt still durchzulaufen; jeder der fünf Fälle hat einen eigenen Testblock.
- [x] **AC-5:** Given die Löschung der Wetter-Metriken- und Trip-Detail-Waisen / When die Tests, die nur diese Dateien prüfen, und die gemischten Prüfstände (`f5`, `f9`) bearbeitet sind / Then sind reine Waisentests gelöscht, Tests mit lebendem Anteil (`saveStatus`, `vorlageName_render`, `fix2955_metrik_inhalte`, `deutsch_unveraendert`, Nutzer von `f9Pruefstand`) nur um die Waisen-Fälle gekürzt und grün, und die f9-Goldens sind ausschließlich mit dem Projektwerkzeug neu erzeugt, wobei Goldens ohne Bezug zu `WeatherV2Kanaele` unverändert bleiben.
- [x] **AC-6:** Given die Löschung / When die Zahlenratschen (`BESTAND_OBERGRENZE`, ink4, `hoechststand`/`HOECHSTSTAND` ein_katalog, Zählung in `reaktivitaet_waechter`, Katalogschlüssel de/en) geprüft werden / Then stimmen alle Zahlen mit der Messung nach dem Löschen überein und sind nur gesunken, `hoechststand` (JSON) und `HOECHSTSTAND` (Python) sind identisch gesenkt, die entfernten Einträge in `ein_katalog_ausnahmen.json` gehören nur zu den S1-Dateien, de und en führen dieselbe Schlüsselmenge, und kein Schlüssel ohne Verwender bleibt im Katalog.
- [x] **AC-7:** Given die Seiten und Ansichten (insbesondere Trip-Editor, Vergleichs-Editor, Wetter-Metriken-Reiter, Trip-Detail) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die svelte-check-Zahlen (Fehler/Warnungen) wurden vor dem Löschen auf dem Branch-Stand gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
- [x] **AC-8:** Given die Scheiben S3 (#3385), S4 (#3384) und die Browser-Specs (#3374) sowie `EinstellTabelle.svelte` und `.claude/hooks` / When S1 geliefert ist / Then sind deren Dateien unverändert, die 26 verbleibenden Wächter-Einträge entsprechen genau den Scheiben S3 und S4, und keine Datei der Löschliste existiert mehr, ohne dass ein Import darauf zurückbleibt.

## Dialog

### Runde 1
**Adversary:** Behauptung "Loeschung ohne Funktionsaenderung" gegen die Wirkung geprueft, nicht nur gegen den Testlauf.
- Gegenprobe Namen/Exporte der 14 Dateien per grep ueber frontend/src, frontend/e2e, src, api, internal, tests, scripts, .claude/hooks: Treffer ausschliesslich Kommentare, Teststrings und ein Python-Staging-Test (tests/tdd/test_issue_692_telegram_disabled_unconfigured.py, Marker staging, Playwright; Docstring/Meldung, kein Import). Kein Produktionsaufrufer. `npm run build` Exit 0, svelte-check 32 Fehler / 72 Warnungen = Stand vorher.
- Katalogschluessel (trip.about 19, trip.kanaele 13, wertebereiche 22 = 54 je Sprache): kein Verwender, auch nicht dynamisch (Suche nach Template- und Konkatenationsformen ohne Treffer; symbolzeile/preset/grundauswahl/schwelle nur in Tests und Kommentaren). Gegenprobe M7 rot. Kein sichtbarer Text der lebenden Oberflaeche verschwunden.
- Umgebaute Tests per Diff gegen HEAD: saveStatus (nur der Block "Fix-Loop 1", Komposition der zwei geloeschten Waisen), vorlageName_render (nur PresetBar-Block), fix2955 (Symbolzeilen-Schluessel entfallen, Alarme-Zusicherung bleibt), f9Pruefstand/f9KatalogAnker/trip_hub_sprache (nur WeatherV2Kanaele-Render und dessen Strings; Golden-Diff je Sprache genau eine Zeile wm2-kanaele), feat3250/3204 (Namen aus daten/metrik_namen.json: alle 16 de/en-Namen identisch mit den entfernten Katalogtexten, per Skript verglichen). Keine Pruefung fuer lebenden Code verloren.
- thunderThresholdLevels.test.ts bleibt zu Recht: importiert compareMetricCatalogLoader.ts (lebend), ThresholdMetricRow steht nur in Kommentaren.
- Elementliste: 2950 Eintraege, keine ID entfallen. Aenderungen: 28 i18n_key -> null (EN unveraendert, verifiziert), 8 trip.about.kanal -> zustellung.spalte.kanal (DE/EN gleich), 4 "Eigene": wertebereiche.preset.eigene -> wetter.vorlage.eigene, EN "Custom" -> "Your own" (en/wetter.json:10, App-Wortlaut der Trip-Vorlagenauswahl, ohne Nutzerwirkung, nur Dokument), 20 "Telegram": wetter.wsw.spalte.telegram -> level.zeile.telegram (siehe F003).
- Ratschen: BESTAND 184 -> 177 = genau die 7 Baustein-Dateien; ink4 -3 = WeatherV2Grundauswahl 1 + WeatherV2Kanaele 2; ein_katalog 433 -> 430 = 3 Dateien je 1, JSON und Python identisch gesenkt.
- Fund (siehe F001/F002): Literal OBERGRENZE_WAISEN wird von keinem Test festgenagelt; die Array-Glob-Meldung greift nicht bei der Typargument-Form import.meta.glob<T>(...).
**Implementierer:** Antwort auf F001/F002 siehe Runde 2.

### Runde 2
**Adversary:** Mutationen per String-Ersetzung, Sicherung im Scratchpad unter bk, Wiederherstellung per sha256 geprueft (alle 8 Dateien identisch; Hash des Indexes unveraendert 73e3ab32...).
- M1 Waechter-Throw (e) Regex entschaerft -> rot "(e) Array-Form ... wird laut rot" (faengt).
- M2 OBERGRENZE_WAISEN 26 -> 40 -> GRUEN (F001, faengt nichts).
- M3 new-URL-Kante entfernt -> rot, Mini-Baum-Liste und (c) (faengt).
- M4 BESTAND_OBERGRENZE 177 -> 184 -> rot "genau die Laenge des Bestands" (faengt).
- M5 ink4: WeatherV2Kanaele-Ausnahme zurueck -> rot "Zaehler groesser als Ist" (faengt).
- M6 HOECHSTSTAND (Python) 430 -> 433 rot; "hoechststand" (JSON) 430 -> 433 rot; wertebereicheAnzeige.ts als Ausnahme zurueck rot (faengt, 3 Mutationen).
- M7 Katalogschluessel trip.about.titel in de und en wieder eingefuegt -> rot (katalog_schluessel_haben_verwender, Bestand AC-5) (faengt).
- M8 neue Waise frontend/src/lib/utils/zzOrphanAdv.ts angelegt -> Waechter rot, danach entfernt (faengt).
- M9 geloeschte Datei weatherSaveGate.ts neu angelegt -> Loesch-Nachweis und Waechter rot, danach entfernt (faengt).
- Umbenennung des Echtbaum-Tests: Koerper identisch (Ratschenpruefung mit denselben Parametern), nur der Name passt jetzt zu 26; keine Schutzwirkung umgangen (M8/M9 rot unter dem neuen Namen); Waechter-Throw am Mini-Baum (e) durch eigenen Testblock belegt (M1).
- Tests: gesamte Frontend-Suite 11743 passed / 0 failed / 2 skipped; 17 benannte Dateien 671 passed; 4 benannte Python-Dateien 72 passed (docs/artifacts/rework-3383-waisen-s1/adversary-test-output.txt).
**Implementierer:** F001 (Literal nicht festgenagelt) stammt aus dem Muster von #3366, F002 ist ein Randfall der Waechterlogik; beide verletzen keine AC dieser Scheibe. Nachzug in einer Folgescheibe moeglich.

## Findings

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:79
  Description: OBERGRENZE_WAISEN ist ein Literal (26); kein Test nagelt den Wert fest. Mutation 26 -> 40 bleibt gruen, weil pruefeRatsche (Zeile 199) nur bekannte.length > obergrenze meldet.
  Spec requirement: AC-3 — OBERGRENZE_WAISEN ist die feste Literal-Konstante 26 (um genau 14 gesenkt)
  Conflict: Der Wert 26 ist korrekt gesetzt, wird aber nirgends gegen die Messung gebunden; ein stilles Anheben (dann Waise in BEKANNTE_WAISEN) faengt kein Test.
  Remediation: Test, der OBERGRENZE_WAISEN === BEKANNTE_WAISEN.length verlangt (Muster BESTAND_OBERGRENZE "genau die Laenge"). Nicht blockierend, Muster stammt aus #3366.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:142
  Description: Die Fail-closed-Regel /import\.meta\.glob\(\s*\[/ erkennt die Form mit Typargument import.meta.glob<T>([...]) nicht; die Kantenerkennung KANTE (Zeile 83) ebenso nicht. Im Produktionscode kommt heute kein import.meta.glob vor.
  Spec requirement: AC-4 — Array-Form fuehrt zu roter Meldung statt still durchzulaufen
  Conflict: Fuer die geforderte Form erfuellt; die Typargument-Variante liefe still durch.
  Remediation: Regex auf glob(?:<[^>]*>)?\( erweitern, Mini-Baum-Fall ergaenzen.

Finding:
  ID: F003
  Severity: LOW
  Category: anti_pattern
  Code reference: docs/context/einstellungen_neu/elementliste.json:44
  Description: Neu erzeugte Elementliste tauscht bei 20 "Telegram"-Eintraegen (reiter wetter und zustellung) den i18n_key wetter.wsw.spalte.telegram gegen level.zeile.telegram. Altstand ohne S1-Bezug (laut Kommentar elementliste_uebersicht_2969.test.ts:130), Text DE/EN gleich; der alte Schluessel ist lebend (wasStehtWoAnsicht.ts:24), der neue gehoert zur Funktionen-Seite.
  Spec requirement: Spec "Ratschenzahlen und Katalog schrumpfen", keine sichtbare Aenderung
  Conflict: Nur Dokument, ohne Nutzerwirkung, aber fachlich ungenauere Zuordnung und nicht durch S1 verursacht.
  Remediation: Generator-Tiebreak (lebender Schluessel vor alphabetisch erstem) in einer Folgescheibe; hier dokumentiert hingenommen.

Finding:
  ID: F004
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts:155
  Description: Kommentare und Teststring verweisen weiter auf die geloeschte ThresholdMetricRow.svelte:28 (ebenso compareMetricCatalogLoader.ts:205 und tests/tdd/test_sms_snow_symbols.py:790).
  Spec requirement: AC-1 — kein Produktionscode importiert die gelöschten Basisnamen
  Conflict: Nur Kommentare, kein Import; Verwechslungsgefahr.
  Remediation: Verweise bei Gelegenheit streichen.

## Confirmations

Confirmation:
  AC: Input
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:35
  Evidence: Waechter liest Quelltext unter frontend/src; Baumlauf gruen (11743 passed in der Gesamtsuite).
  Status: CONFIRMED

Confirmation:
  AC: Output
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:79
  Evidence: BEKANNTE_WAISEN 26 Eintraege (19 S4, 7 S3), Wert 26; Echtbaum-Test gruen; M8 (neue Waise) und M9 (wieder angelegte Datei) rot.
  Status: CONFIRMED

Confirmation:
  AC: Side effects
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:718
  Evidence: BESTAND 177, ink4 -3, ein_katalog 430 gesenkt, Katalog je Sprache -54; Produktions-Build Exit 0, keine Oberflaechenaenderung (Komponenten ohne Importeur).
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:196
  Evidence: 14 Dateien fehlen im Dateisystem, weatherMetricsCompareSave.ts/metricsEditor.ts/WaypointPin.svelte bestehen; grep auf Basisnamen ohne Produktionstreffer; M9 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:40
  Evidence: outlookFriendlyCapability.ts steht in GELOESCHT, nicht in ERHALTEN; der Waisen-Test dazu ist aus waisen_waechter.test.ts entfernt.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:210
  Evidence: Echtbaum-Test gruen mit 26; ohne Loeschung rot (M9, M8). Literal-Pin fehlt, siehe F001 (MEDIUM, nicht blockierend).
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:323
  Evidence: Fuenf Testbloecke (a)-(e), je eigener test(); M1 macht (e) rot, M3 macht (c) rot; Typargument-Randfall siehe F002.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/trip-detail/__tests__/f9Pruefstand.ts:238
  Evidence: Reine Waisentests geloescht, gemischte Tests nur um Waisen-Faelle gekuerzt (Diff gegen HEAD geprueft), Golden-Diff je Sprache eine Zeile wm2-kanaele; Suite gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py:39
  Evidence: HOECHSTSTAND 430 = hoechststand 430 in ein_katalog_ausnahmen.json (M6 rot bei Abweichung); BESTAND 177 (M4 rot); ink4 (M5 rot); 54 Schluessel je Sprache ohne Verwender (M7 rot bei Rueckkehr), de/en-Paritaet gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: docs/artifacts/rework-3383-waisen-s1/svelte-check-nachher.txt:1
  Evidence: Eigener Lauf: npm run check 32 Fehler / 72 Warnungen, gleich dem Vorher-Stand; npm run build Exit 0; Gesamtsuite 11743 passed, 0 failed.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:62
  Evidence: Die gestagte Liste enthaelt keine versand-tab-, layout-/S4-Dateien, keine Browser-Specs (*.spec.ts); nur die drei Node-Testdateien frontend/e2e/feat32xx_*.test.ts sind angepasst, keine EinstellTabelle, keine .claude/hooks; die 26 Eintraege sind 19 S4 und 7 S3.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

F001 (MEDIUM), F002/F003/F004 (LOW) sind nicht blockierend und als Nachzug vermerkt; 9 Mutationen, 8 davon rot, M2 gruen (F001). Tests 11743 passed, 0 failed.

## Geprüfte Dateien

- sha256:da3f85a878f880316b27e01983ce10ded87e606c35dc1fcafe245f06a44285c6  docs/artifacts/rework-3383-waisen-s1/svelte-check-nachher.txt
- sha256:2058d3e788b8d804cfa4c5551e08b3e828da62e42cb65108f44ad8c0b699b1f2  docs/context/einstellungen_neu/elementliste.json
- sha256:03d0b0de8b60c3bbc4030d03e7313e1343d0e8b02c8ac76afcacbe407c8407e4  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:0584c92bf323e39d9344b4a6e47a5403a20a5c7cde21fa46dbfbbf8c56b586f7  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:beed9f735e554071b3b71e7af2722f8a629c349019baba851f5c304f0487e089  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:efaa0738146bda84c5887c7085f7c5ffa859e8029f3697257e18ee70ae549010  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts
- sha256:d62f0841ffd80392eb250c0d49fa1c6a2b778efab7b93760e08a0265fbff88f7  frontend/src/lib/components/trip-detail/__tests__/f9Pruefstand.ts
- sha256:1af9b6d5028f5d8dd58578cc24f3548a18dc6050527f7a326eba31ea966d8052  tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py

## Prüfbasis

- base: 4b095ade2a1d74749b9c6248920e45bc85715793
- blob:c950404b5b21817bf2b686b50ee8451d709a33ed  docs/artifacts/rework-3383-waisen-s1/svelte-check-nachher.txt
- blob:3f46054f564229c66a42fe7d550b1389b104fcf8  docs/context/einstellungen_neu/elementliste.json
- blob:b18ccf59143663e9bbce3b87a24774917b69b1a5  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:eddaf09500cfc7058f84001915c93e06ec154e26  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:bc43a2780462101e18d066bc237f63013b99858b  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:6fba79aef53c63725b03a7ef7823b585ec54e0b3  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts
- blob:803ad675d507ca3bf305eb03cd961096ca6a12d6  frontend/src/lib/components/trip-detail/__tests__/f9Pruefstand.ts
- blob:04f65c4a60e813150bb9205547449dbce60a60e0  tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py

## Geprüfte Dateien

- sha256:da3f85a878f880316b27e01983ce10ded87e606c35dc1fcafe245f06a44285c6  docs/artifacts/rework-3383-waisen-s1/svelte-check-nachher.txt
- sha256:2058d3e788b8d804cfa4c5551e08b3e828da62e42cb65108f44ad8c0b699b1f2  docs/context/einstellungen_neu/elementliste.json
- sha256:03d0b0de8b60c3bbc4030d03e7313e1343d0e8b02c8ac76afcacbe407c8407e4  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:0584c92bf323e39d9344b4a6e47a5403a20a5c7cde21fa46dbfbbf8c56b586f7  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:beed9f735e554071b3b71e7af2722f8a629c349019baba851f5c304f0487e089  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:efaa0738146bda84c5887c7085f7c5ffa859e8029f3697257e18ee70ae549010  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts
- sha256:d62f0841ffd80392eb250c0d49fa1c6a2b778efab7b93760e08a0265fbff88f7  frontend/src/lib/components/trip-detail/__tests__/f9Pruefstand.ts
- sha256:1af9b6d5028f5d8dd58578cc24f3548a18dc6050527f7a326eba31ea966d8052  tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py

## Prüfbasis

- base: 4b095ade2a1d74749b9c6248920e45bc85715793
- blob:c950404b5b21817bf2b686b50ee8451d709a33ed  docs/artifacts/rework-3383-waisen-s1/svelte-check-nachher.txt
- blob:3f46054f564229c66a42fe7d550b1389b104fcf8  docs/context/einstellungen_neu/elementliste.json
- blob:b18ccf59143663e9bbce3b87a24774917b69b1a5  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:eddaf09500cfc7058f84001915c93e06ec154e26  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:bc43a2780462101e18d066bc237f63013b99858b  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:6fba79aef53c63725b03a7ef7823b585ec54e0b3  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts
- blob:803ad675d507ca3bf305eb03cd961096ca6a12d6  frontend/src/lib/components/trip-detail/__tests__/f9Pruefstand.ts
- blob:04f65c4a60e813150bb9205547449dbce60a60e0  tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py
