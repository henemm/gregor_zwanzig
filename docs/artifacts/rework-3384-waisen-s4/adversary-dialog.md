# Adversary Dialog — rework-3384-waisen-s4
Spec: docs/specs/modules/rework_3384_waisen_s4.md
Datum: 2026-11-26 02:09

## Checkliste
- [x] **Input:** Quelltext von `frontend/src`.
- [x] **Output:** Wächter grün, solange die Waisenmenge (ohne `AUSNAHMEN`) exakt `BEKANNTE_WAISEN` (7 Einträge, S3) entspricht und `OBERGRENZE_WAISEN` (7) exakt der Listenlänge gleicht; Löschung ohne Funktionsänderung.
- [x] **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen, Katalog, CI-Positivliste (85 Specs) und Doku schrumpfen.
- [x] **AC-1:** Given die 19 Dateien der Gruppe S4 (`compare/*` sechs, `edit/*` vier, `mobile/*` drei, `utils/*` fünf, `trip-detail/waypoints/WaypointPin.svelte`) / When das Dateisystem nach S4 geprüft wird / Then existiert keine der 19 Dateien mehr, kein Produktionscode importiert die gelöschten Basisnamen, und `EinstellTabelle.svelte` besteht weiter.
- [x] **AC-2:** Given die Gruppe S4 in `BEKANNTE_WAISEN` gestrichen / When der Wächter die Erreichbarkeit ab `routes/` und `src/*.ts` berechnet / Then ist die Waisenmenge (ohne `AUSNAHMEN`) genau `BEKANNTE_WAISEN` mit 7 Einträgen (nur S3), `OBERGRENZE_WAISEN` ist die feste Literal-Konstante 7 (um genau 19 gesenkt), und der Test ist grün; ohne Streichen oder ohne Löschung wäre er rot.
- [x] **AC-3 (F001):** Given `pruefeRatsche` mit Obergrenze und Liste / When die Obergrenze größer als die Listenlänge ist (etwa erhöht, ohne Eintrag hinzuzufügen) oder kleiner / Then wird der Wächter rot, weil die Obergrenze exakt der Listenlänge entsprechen muss; am echten Baum gilt `OBERGRENZE_WAISEN === BEKANNTE_WAISEN.length`.
- [x] **AC-4 (F002):** Given ein erfundener Mini-Baum mit `import.meta.glob<T>(['./x/*.ts'])` und ein zweiter mit `import.meta.glob<T>('./x/*.ts')` / When der Wächter die Erreichbarkeit berechnet / Then bricht er beim ersten laut mit „Array-Form von import.meta.glob nicht unterstützt — Wächterlogik ergänzen“ ab, und beim zweiten gelten die passenden Dateien als erreichbar; die Form ohne Typparameter bleibt unverändert rot (Array) bzw. erreichbar (String).
- [x] **AC-5 (F004):** Given Verweise auf das gelöschte `ThresholdMetricRow` in Code und Kommentaren / When S4 umgesetzt ist / Then findet ein Scan über `frontend/src` (`.ts`, `.svelte`, `.js`) das ganze Wort `ThresholdMetricRow` nur noch in `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (der einen festen Ausnahme, die den Namen als Gelöscht-Eintrag führt), und die Verweise in `bausteine_waechter_regeln.ts`, `compareMetricCatalogLoader.ts` und `thunderThresholdLevels.test.ts` sind entfernt.
- [x] **AC-6:** Given die Löschung der compare/edit/mobile/utils-Waisen / When die in der Tabelle genannten Testdateien nach DELETE bzw. MODIFY bearbeitet und die Prüfstände (`f9`, `f10`) gekürzt sind / Then sind die sechs reinen Waisentests gelöscht, alle gemischten Tests nur um die Waisen-Fälle gekürzt und grün, in `f10Pruefstand.ts` fallen nur Teile weg, die gelöschte S4-Dateien rendern oder importieren, die f9-/f10-Goldens sind ausschließlich mit dem Projektwerkzeug neu erzeugt (Goldens ohne Bezug unverändert), die Python-Tests `test_trip_alert_stage_name` und `test_issue_316_docs_cleanup` laufen ohne Waisenpfade grün, und `docs/reference/frontend_components.md` führt keine der 19 Komponenten mehr; weitere beim Löschen auffallende Importeure folgen derselben Regel und stehen im Lieferbericht.
- [x] **AC-7:** Given die Löschung inklusive `issue-1093-unit.spec.ts` / When die Zahlenratschen (`BESTAND_OBERGRENZE`, ink4, `hoechststand`/`HOECHSTSTAND` ein_katalog, Zählung in `reaktivitaet_waechter`, Katalogschlüssel de/en, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`, Positivliste) geprüft werden / Then stimmen alle Zahlen mit der Messung nach dem Löschen überein und sind nur gesunken, `hoechststand` (JSON) und `HOECHSTSTAND` (Python) sind identisch gesenkt, `E2E_MIN_SPECS` steht in `ci.yml` und in `test_2243_playwright_loeschscheibe.py` auf 85 und die Positivliste hat 85 Einträge, `E2E_MIN_EXECUTED_HAUPT` steht an beiden Stellen auf 757 (760 minus gemessene 3 Fälle), die Positivliste führt `issue-1093-unit` nicht mehr, und `test_e2e_positivliste_ratschen_bindung.py` sichert per Abwesenheits-Zusicherung, dass die Spec weder als Datei noch auf der Liste vorkommt; de und en führen dieselbe Schlüsselmenge und kein Schlüssel ohne Verwender bleibt.
- [x] **AC-8:** Given die Seiten und Ansichten (insbesondere Trip-Editor, Vergleichs-Editor, Trip-Detail, mobile Navigation) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die svelte-check-Zahlen (Fehler/Warnungen) wurden vor dem Löschen auf dem Branch-Stand gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
- [x] **AC-9:** Given die Scheibe S3 (#3385), alle übrigen Browser-Specs (#3374), `EinstellTabelle.svelte` und `.claude/hooks` / When S4 geliefert ist / Then sind deren Dateien unverändert (einzige Browser-Spec-Ausnahme ist die mitgelöschte `issue-1093-unit.spec.ts` samt Config), und die 7 verbleibenden Wächter-Einträge entsprechen genau der Scheibe S3.

## Dialog

### Runde 1
**Adversary:** Geprüft: (1) Importeure der 27 gelöschten Dateien per grep -w über src, e2e, tests, docs/reference: keine Produktionsverwender, nur Kommentare und Löschnachweise; npm run build Exit 0. (2) Katalog: 35 Schlüssel je Sprache, kein Verwender außerhalb der gelöschten Komponenten, kein dynamischer Zugriff (grep auf Templates). (3) E2E-Zahlen aus ci.yml, Positivliste (85) und test_2243 stimmen; playwright --list = 802 inkl. Setup. (4) Mutationen: pruefeRatsche `!==`->`>` rot; OBERGRENZE 8 rot; Guard-Regex ohne Typparameter rot; KANTE-Regex ohne Typparameter rot; Orphan-Datei naturalSort.ts neu rot; ThresholdMetricRow im Kommentar rot; BESTAND_OBERGRENZE 168 rot; gelöschter Baustein wieder in BESTAND rot; Dead-Key de+en rot; HOECHSTSTAND 430 py/json rot; issue-1093-unit.spec.ts neu rot. Alle wiederhergestellt (Diff gegen Sicherung leer, Index unverändert).
**Implementierer:** Keine Rückmeldung nötig, kein Finding offen.

### Runde 2
**Adversary:** Nachprüfung der umgebauten Tests gegen HEAD: compare_feldsatz_roundtrip_datenerhalt, hub_reiter_gemeinsame_aufloesung (feldsatz.sendSms statt versandPropsAus: dieselbe Zusicherung, späte Alarm-Hydration überschreibt Nutzerwert nicht), versand_vergleich_premium_sms (nur Adapterblock weg, Persistenz-/Nutzlast-Block bleibt), hub_geteilte_felder_cooldown_quiet (Adapterblock weg; Wirkort-Block am echten Editor prüft Zustellung->Alarme und POST). issue_462: die 3 entfallenen Tests liefen ausschließlich über die nun leere MIGRATED_FILES-Liste, zu Recht entfallen. Ein Lücken-Befund (LOW): der Adapter-Test „Löschen im Alarme-Reiter kommt im Versand an“ ist am echten Editor nicht mehr nachgebildet; ein ci.yml-Mutationslauf war im Sandbox-Modus nicht möglich, die Schutzwirkung wurde stattdessen über test_2243 (Gleichheit 85/757) und die gemessene Fallzahl belegt.
**Implementierer:** Die LOW-Punkte sind nicht blockierend.

Finding:
  ID: F001
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:16
  Description: Kopfkommentar nennt noch `BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN`, der Code prüft jetzt exakte Gleichheit.
  Spec requirement: AC-3 — Obergrenze muss exakt der Listenlänge entsprechen
  Conflict: veralteter Kommentar widerspricht der Prüfung.
  Remediation: Kommentar auf „==“ ändern.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts:42
  Description: Der entfallene Adapter-Block prüfte auch den Rückweg (Cooldown im Alarme-Reiter löschen ⇒ Versand zeigt undefined); der Wirkort-Block prüft nur die Richtung Zustellung -> Alarme.
  Spec requirement: AC-6 — gemischte Tests nur um Waisen-Fälle gekürzt
  Conflict: eine Richtung der geteilten Feldsatz-Zusicherung ist nur noch indirekt (gleicher Feldsatzobjekt) bewacht.
  Remediation: optional einen Rückrichtungsfall am echten Editor ergänzen.

Confirmation:
  AC: Input
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:71
  Evidence: Wächter scannt frontend/src (.svelte/.ts/.js/.mjs); KANTE-Regex liest auch import.meta.glob<T>(…).
  Status: CONFIRMED

Confirmation:
  AC: Output
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:68
  Evidence: OBERGRENZE_WAISEN = 7 Literal, 7 Einträge (nur S3 versand-tab); Mutation 8 statt 7 -> 2 rot.
  Status: CONFIRMED

Confirmation:
  AC: Side effects
  Code reference: docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
  Evidence: svelte-check 32 Fehler (vorher 32), 71 Warnungen (vorher 72); npm run build Exit 0; Katalog de/en je -35 Schlüssel ohne Verwender.
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:241
  Evidence: 27 gelöschte Dateien (19 Spec + 6 Waisentests + issue-1093-unit samt Config) per grep -w auf alle Basisnamen: nur Kommentare/Löschnachweis; EinstellTabelle.svelte besteht (molecules/). Mutation: naturalSort.ts neu angelegt -> Löschnachweis rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:61
  Evidence: Orphan-Datei neu angelegt -> Wächter rot; Waisenmenge exakt BEKANNTE_WAISEN (7), Test grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:185
  Evidence: `!==` Prüfung; Mutation `>` -> 1 rot (Selbstnachweis), OBERGRENZE 8 -> 2 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:129
  Evidence: Guard-Regex ohne Typparameter -> 1 rot; KANTE-Regex ohne Typparameter -> 2 rot; beide Mutationen werden gefangen.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
  Evidence: Scan: ThresholdMetricRow nur noch in dieser Datei; Mutation (Wort in reportSlotAktiv.ts-Kommentar) -> rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts:72
  Evidence: Stichproben gegen HEAD: versandPropsAus-Aufrufe durch gleichwertiges feldsatz.morningTime/sendSms ersetzt; issue_462 verlor genau die 3 nur über die gelöschte MIGRATED_FILES-Liste laufenden Tests; Adapter-Blöcke versandPropsAus entfielen mit der Datei. 883 node-Tests grün, 96 Python grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: tests/unit/test_2243_playwright_loeschscheibe.py:269
  Evidence: Positivliste 85 Zeilen, E2E_MIN_SPECS 85, HAUPT 757 in ci.yml und Test; playwright --list der Hauptlauf-Auswahl: 802 Fälle in 85 Dateien, Abstand 45 wie vorher (805/760) -> Schwelle nicht zu tief. BESTAND 167 = 177 minus 10 gelöschte Svelte-Bausteine (nachgezählt), HOECHSTSTAND 422 = JSON 422; Mutationen (BESTAND 168, NavIcon-Eintrag, HOECHSTSTAND/JSON 430, Dead-Key de+en, issue-1093-unit.spec.ts neu) -> alle rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
  Evidence: Frontend-Tests 883/0, Build Exit 0, svelte-check Zahlen nicht gestiegen; gelöschte Texte nur in gelöschten Komponenten verwendet (grep je Schlüssel, auch dynamisch: keine Treffer).
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/molecules/EinstellTabelle.svelte
  Evidence: Index enthält keine Änderung an .claude, EinstellTabelle, S3-Dateien oder Browser-Specs außer issue-1093-unit samt Config; 7 Wächter-Einträge = versand-tab (S3).
  Status: CONFIRMED


## Herkunft der Vorbedingungen

Kein Feld mit Test-Zuweisung gefunden — nichts zu pruefen. Nicht anwendbar: die Scheibe löscht Waisen und ändert Zahlenratschen; es gibt keine neuen Testvorbedingungen (Zuweisungen in Tests an Modellfeldern), die Herkunft wäre nur die Umstellung versandPropsAus -> direkte Feldsatz-Zuweisung (feldsatz.morningTime, feldsatz.sendSms), beide Felder werden in den Hub-Komponenten von CompareTabs selbst gesetzt.

Confirmation:
  AC: AC-5 (F004)
  Code reference: frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts:13
  Evidence: Der Verweis auf ThresholdMetricRow ist aus dem Kommentar entfernt; ein Wortscan über frontend/src findet den Namen nur noch im Lösch-Nachweis.
  Status: CONFIRMED

## Verdict

VERDICT: VERIFIED
2 LOW-Findings, nicht blockierend. Tests: 883 node-Tests und 96 Python-Tests grün, 11 Mutationen alle gefangen, Build Exit 0.

## Geprüfte Dateien

- sha256:b4d8a47c478459e75b52d9f8a7517048b5b589a925ff1c9e911816b89635cda0  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- sha256:118bac55ae2c1005b55d309f1698a4da361b840ec3df42aa51dc508c301ec9d9  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:0aede88fd305e35f098d6394984fe9661a32d94b3a86ad5e556d5d95477f48b1  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:bdc295aed0315b4f9ca9dc4f271dce9b514ae50f2b42fc0cf6400014dbb21b66  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- sha256:681c4242bc6c168bf579f4e5b8080b1a4c2d30a6734e900d905e8ffa58e4cec9  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- sha256:3bbe521ea9b46fe128d325231420313bcee2367f7f0ecbc173c4103abfccf0a3  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- sha256:81b115889b97b0eca435e763ebc5814aa772d64f1c5828ee3cfe58bea5fc5a3f  tests/unit/test_2243_playwright_loeschscheibe.py

## Prüfbasis

- base: 152ee14be09d5b59c42c6e646e4a5d38e1f8deb2
- blob:443074b317b51d138bedbcf73b47eb33d23eeca4  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- blob:83301a846d936b86d4e4bd8adba544ebf34f12f7  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:610eab50040bd24936fdfcc39679a551b0a3b65a  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:09419494a397c4f3289bca0c1bcb42df96f43b37  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- blob:53252927acc649b370de18d083555e7bede9778a  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- blob:f57b877a72ed36c7a169545c12cab5592cf405c5  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- blob:5b295865061818b2b6583d6221e4b155c4c73fb6  tests/unit/test_2243_playwright_loeschscheibe.py

## Geprüfte Dateien

- sha256:b4d8a47c478459e75b52d9f8a7517048b5b589a925ff1c9e911816b89635cda0  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- sha256:118bac55ae2c1005b55d309f1698a4da361b840ec3df42aa51dc508c301ec9d9  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:0aede88fd305e35f098d6394984fe9661a32d94b3a86ad5e556d5d95477f48b1  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:bdc295aed0315b4f9ca9dc4f271dce9b514ae50f2b42fc0cf6400014dbb21b66  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- sha256:681c4242bc6c168bf579f4e5b8080b1a4c2d30a6734e900d905e8ffa58e4cec9  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- sha256:3bbe521ea9b46fe128d325231420313bcee2367f7f0ecbc173c4103abfccf0a3  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- sha256:81b115889b97b0eca435e763ebc5814aa772d64f1c5828ee3cfe58bea5fc5a3f  tests/unit/test_2243_playwright_loeschscheibe.py

## Prüfbasis

- base: 152ee14be09d5b59c42c6e646e4a5d38e1f8deb2
- blob:443074b317b51d138bedbcf73b47eb33d23eeca4  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- blob:83301a846d936b86d4e4bd8adba544ebf34f12f7  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:610eab50040bd24936fdfcc39679a551b0a3b65a  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:09419494a397c4f3289bca0c1bcb42df96f43b37  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- blob:53252927acc649b370de18d083555e7bede9778a  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- blob:f57b877a72ed36c7a169545c12cab5592cf405c5  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- blob:5b295865061818b2b6583d6221e4b155c4c73fb6  tests/unit/test_2243_playwright_loeschscheibe.py

## Geprüfte Dateien

- sha256:b4d8a47c478459e75b52d9f8a7517048b5b589a925ff1c9e911816b89635cda0  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- sha256:118bac55ae2c1005b55d309f1698a4da361b840ec3df42aa51dc508c301ec9d9  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:0aede88fd305e35f098d6394984fe9661a32d94b3a86ad5e556d5d95477f48b1  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:bdc295aed0315b4f9ca9dc4f271dce9b514ae50f2b42fc0cf6400014dbb21b66  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- sha256:681c4242bc6c168bf579f4e5b8080b1a4c2d30a6734e900d905e8ffa58e4cec9  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- sha256:3bbe521ea9b46fe128d325231420313bcee2367f7f0ecbc173c4103abfccf0a3  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- sha256:81b115889b97b0eca435e763ebc5814aa772d64f1c5828ee3cfe58bea5fc5a3f  tests/unit/test_2243_playwright_loeschscheibe.py

## Prüfbasis

- base: 152ee14be09d5b59c42c6e646e4a5d38e1f8deb2
- blob:443074b317b51d138bedbcf73b47eb33d23eeca4  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- blob:83301a846d936b86d4e4bd8adba544ebf34f12f7  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:610eab50040bd24936fdfcc39679a551b0a3b65a  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:09419494a397c4f3289bca0c1bcb42df96f43b37  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- blob:53252927acc649b370de18d083555e7bede9778a  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- blob:f57b877a72ed36c7a169545c12cab5592cf405c5  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- blob:5b295865061818b2b6583d6221e4b155c4c73fb6  tests/unit/test_2243_playwright_loeschscheibe.py

## Geprüfte Dateien

- sha256:b4d8a47c478459e75b52d9f8a7517048b5b589a925ff1c9e911816b89635cda0  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- sha256:118bac55ae2c1005b55d309f1698a4da361b840ec3df42aa51dc508c301ec9d9  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:0aede88fd305e35f098d6394984fe9661a32d94b3a86ad5e556d5d95477f48b1  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:bdc295aed0315b4f9ca9dc4f271dce9b514ae50f2b42fc0cf6400014dbb21b66  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- sha256:681c4242bc6c168bf579f4e5b8080b1a4c2d30a6734e900d905e8ffa58e4cec9  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- sha256:3bbe521ea9b46fe128d325231420313bcee2367f7f0ecbc173c4103abfccf0a3  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- sha256:e277706c3e7091d03934d66a63ff736aa1caa7f6c6a36b6cc0ba690227ee491c  frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts
- sha256:81b115889b97b0eca435e763ebc5814aa772d64f1c5828ee3cfe58bea5fc5a3f  tests/unit/test_2243_playwright_loeschscheibe.py

## Prüfbasis

- base: 152ee14be09d5b59c42c6e646e4a5d38e1f8deb2
- blob:443074b317b51d138bedbcf73b47eb33d23eeca4  docs/artifacts/rework-3384-waisen-s4/svelte-check-nachher.txt
- blob:83301a846d936b86d4e4bd8adba544ebf34f12f7  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:610eab50040bd24936fdfcc39679a551b0a3b65a  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:09419494a397c4f3289bca0c1bcb42df96f43b37  frontend/src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts
- blob:53252927acc649b370de18d083555e7bede9778a  frontend/src/lib/components/molecules/EinstellTabelle.svelte
- blob:f57b877a72ed36c7a169545c12cab5592cf405c5  frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts
- blob:be210b32b8361fa5b368c4731b0bc97d128a055f  frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts
- blob:5b295865061818b2b6583d6221e4b155c4c73fb6  tests/unit/test_2243_playwright_loeschscheibe.py
