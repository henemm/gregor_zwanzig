# Adversary Dialog — feat-3203-metrikzeilen-mockup
Spec: docs/specs/modules/feat_3203_metrikzeilen_mockup.md
Datum: 2026-11-21 12:42

## Checkliste
- [x] **Input:** Staging-Seite Reiter Wetter (Trip und Orts-Vergleich), Prüfkonto-Seed.
- [x] **Output:** Abgleich meldet für Skala-Zahlen (-10/-15), Gewitter-Stufen keins/mittel/hoch, „· grün: …“ und die Alarm-Satz-Reihenfolge keine Abweichung mehr; keine herrenlosen Besitzer-Einträge.
- [x] **Side effects:** Wechsel abweichend→gefunden in anderen Reitern ist erlaubt; neue Abweichungen außerhalb `#3203` sind es nicht. Screenreader-Ausgabe unverändert.
- [x] **AC-1:** Given Reiter Wetter im Trip mit Skala unter einer Metrik (Marken mit `aria-hidden`) / When der Elementlisten-Abgleich die Seite liest / Then zählen Skala-Zahlen (z. B. -10, -15) und die Gewitter-Stufen keins/mittel/hoch als sichtbarer Text und werden gefunden.
- [x] **AC-2:** Given Reiter Wetter im Orts-Vergleich mit derselben Metrik-Zeile / When der Abgleich läuft / Then wird der Trennpunkt mit „grün: 2 bis 27 °C“ als ein Text erkannt, und die Alarm-Satz-Reihenfolge meldet keine Abweichung.
- [x] **AC-3:** Given ein Element mit `display:none`, `visibility:hidden` oder ein reines Icon/SVG unter `aria-hidden` / When die Abgleich-Logik Texte sammelt / Then wird es nicht gezählt und erzeugt kein Rauschen.
- [x] **AC-4:** Given Reiter Wetter in Deutsch und Englisch, Trip und Orts-Vergleich / When der Abgleich beider Sprachen läuft / Then meldet er keinen Eintrag mit Besitzer `#3203`, und der Zählwächter steht auf 0.
- [x] **AC-5:** Given Tiefe Wolken (Trip) und Sonnenstunden (Orte), die keine Vorboten sind / When der Nutzer die Zeile liest / Then steht dort „Kein Alarm. Die Farbe erscheint nur im Briefing.“ (DE) bzw. der englische Katalogtext, und das Mockup Fassung 4 zeigt dasselbe.
- [x] **AC-6:** Given ein Screenreader-Nutzer im Reiter Wetter (Trip und Orte) / When die Zeile vorgelesen wird / Then bleiben Skala-Marken und Trennpunkt für Hilfstechnik verborgen wie bisher.
- [x] **AC-7:** Given alle Reiter der Einstellungen im Staging-Abgleich / When vorher und nachher verglichen wird / Then gibt es keine neue Abweichung außerhalb der `#3203`-Einträge.

## Dialog

### Runde 1
**Adversary:** Zusammenfassung der Runden 1-3 (Protokoll dialog_runde1-3.md). Live-Messung gegen Staging, Prüfkonto-Seed, alle Reiter, DE und EN; vorher = Stand vor der Änderung, nachher = Arbeitsstand. Zahlen aus den Berichten nachgeprüft (nachher3.log / vorher.log): DE gefunden 1825 -> 1877, abweichend 639 -> 587; EN gefunden 1779 -> 1829, abweichend 547 -> 497. Skala -10/-15, keins/mittel/hoch, „· grün: …“, Vorbote-/Kein-Alarm-Sätze Trip 106 und Orte 84 wechseln abweichend -> gefunden; Einträge mit Besitzer #3203: 52 (DE) / 50 (EN) vorher, jetzt 0. Erste Fassung erzeugte neue Abweichungen (Reiterleiste, Zähler, „Amtliche Warnungen“, neue herrenlose Zusatztexte): F001-F003, im Fix-Loop behoben. Nach dem Fix: Wechsel gefunden -> abweichend nur 8 je Sprache („Ausblick im Morgen-/Abend-Briefing“, Besitzer #3122, aufgedeckter Reihenfolge-Befund, gegengebucht durch 8 Einträge #3122 abweichend -> gefunden, netto 0); neue herrenlose Einträge 0. Mutationen der neuen Logik rot, offen blieben R3 (verbunden-Markierung) und R7 (visibility in ganzerText): F004. Produkt-aria-hidden unverändert (keine Komponentendatei im Diff), Mockup-Diff eine Zeile (428), Pin = Mockup-sha256.
**Implementierer:** (kein Gegenüber, Prüfung ohne Implementierer-Antwort)

### Runde 2
**Adversary:** Prüfung F004. Produkt- und Werkzeugstand seit der Live-Messung unverändert (sha256 gleich zum Stempel: elementliste_abgleich_logik.ts 4c6b9b6f…, Staging-Spec 529c758b…, Besitzerliste 14ee5838…, Mockup e8d3efb5…, Verdrahtungs- und Übersichts-Test unverändert); geändert nur elementliste_abgleich_logik.test.ts (sha 57de30ae…) mit dem Block „#3203 AC-2/AC-3 (F004)“, zwei Tests: aria-hidden-Kind mit Wort neben Eigentext -> ['Dauer Std gesamt'] (keine Doppelzählung); visibility:hidden unter verbundenem Kind -> ['Wert sichtbar']. Suite: 8518 Tests, 8514 bestanden, 0 fehlgeschlagen, 3 übersprungen (vorbestehend); Besitzer-Test 35 bestanden. Mutationen selbst wiederholt (String-Ersetzung, Sicherung im Scratchpad, sha256 vorher 4c6b9b6f891c = nachher): R3 `verbunden.add(k)` entfernt -> 2 Fehlschläge (Test 1 und 2, Block rot); R7 visibility-Prüfung in ganzerText entfernt -> 1 Fehlschlag (Test 2). Beide jetzt gefangen. Mutierte Datei danach zurückgespielt, Hash identisch. Restrisiko: Spec-Stil ohne checkVisibility (R11) nur live prüfbar, durch Live-Messung belegt.
**Implementierer:** (kein Gegenüber)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Findings

F001, F002, F003 (Runde 1): BEHOBEN. 

Finding:
  ID: F004
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:580
  Description: Zwei Zweige der Logik (verbunden-Markierung, visibility in ganzerText) waren ohne Test.
  Spec requirement: AC-3 — verstecktes erzeugt kein Rauschen
  Conflict: war Testlücke; jetzt durch zwei Tests in elementliste_abgleich_logik.test.ts gefangen (R3 und R7 rot). BEHOBEN.
  Remediation: erledigt

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:531
  Evidence: Live Staging DE/EN: Skala, keins/mittel/hoch gefunden; Mutationen rot
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:129
  Evidence: "· grün: …" und Reihenfolge live gefunden, Spec ruft sichtbareTextBloecke
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/e2e/elementliste_abgleich_logik.test.ts:144
  Evidence: display, visibility, hidden, svg, verbunden je Mutation rot, F004-Tests grün
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:4566
  Evidence: #3203 = 0, keine neue herrenlose Abweichung (DE/EN); Besitzer-Test 35 grün
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:428
  Evidence: Trip 106 und Orte 84 live gefunden; Liste neu erzeugt
  Status: CONFIRMED

Confirmation:
  AC: AC-5 (Liste)
  Code reference: docs/context/einstellungen_neu/elementliste.json:4
  Evidence: mockup_hash der Liste = Mockup-sha256
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/organisms/__tests__/feat3203_aria_hidden_bleibt.test.ts:1
  Evidence: aria-hidden unverändert, keine Produktdatei im Diff
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts:1
  Evidence: Differenzlauf: nur 8 Ausblick-Wechsel je Sprache (Besitzer #3122), netto 0
  Status: CONFIRMED

Confirmation:
  AC: Pin und Zählwächter
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:66
  Evidence: Pin = Mockup-Hash
  Status: CONFIRMED

Confirmation:
  AC: Besitzer-Test
  Code reference: tests/test_2913_c2_besitzerliste.py:147
  Evidence: 35 bestanden
  Status: CONFIRMED

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: 8514 passed, 0 failed, 3 übersprungen (vorbestehend); Besitzer-Test 35 passed
Edge cases: F004 behoben, beide Mutationen jetzt rot
Regressions: keine neue Abweichung außerhalb #3203/#3122 (Live-Messung)
Checklist: 7/7 ACs proven

## Geprüfte Dateien

- sha256:5ca54db073a504a04a32ed3069f390ca2d05984ed53ec49d8b86307548625389  docs/context/einstellungen_neu/elementliste.json
- sha256:14ee583877fad88af9ca454ab638799d10bdb5e74c7cc69260ff80322dac7dbd  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:e8d3efb5375527887c7be7081c2aa892324738f7a7f552ee9bfa06e301e8b095  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:529c758b5110d02c8b05af5277ff8fa9c126c35aef72409e1b6f7ebb0d60300f  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:57de30ae2732a0ea9d8128134a7b06a09a957f72c37caa8ac6eafa333c2d943f  frontend/e2e/elementliste_abgleich_logik.test.ts
- sha256:4c6b9b6f891c3e85d1af859b1ca5dd782fc7a10a76e22ae3bd58f0098d6d1255  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:90bf6db88d3d3587ff3372acc84e35433c9e56653186a87f71b2f3e360a4db72  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:81562eefc5ad63483622d5aa89237feedf4a4dffc08b29a225e1a6d8469c7256  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:c409925c33ef85dad546b0f677f13dc4893bdad2df3e0c30deba792d9ea885b0  frontend/src/lib/components/organisms/__tests__/feat3203_aria_hidden_bleibt.test.ts
- sha256:1bf30b569f46d230a6c3aeddf695d11baecf3a8a3d1d1abb52beacf0ba2d7ef2  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 3af30628e4b76ca89f9d6df09e54499c54a1afb7
- blob:47ccf3bfb0917d06ae9c0f238ea57108d2640619  docs/context/einstellungen_neu/elementliste.json
- blob:a80ab7f0aaf1836a5cca6a1f71b0d3cc49d5538b  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:9c9286661d8fc892b4d7be561f2fc31741211cc4  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:2f6444a8019786dd9511359f9fe98993e9a36ad9  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:fa38331ef950f53ade6ea99ff4ca05816acef604  frontend/e2e/elementliste_abgleich_logik.test.ts
- blob:c64aae76285e4dd364c02eefa4804d8be0fab6ba  frontend/e2e/elementliste_abgleich_logik.ts
- blob:61fb3b444149138bee894b36bddf1740a6045034  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:e48b51535b146c864353eb3376c86b8a5f96c437  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:a2062040e94ed75b3395a171a3dced1fb09469c4  frontend/src/lib/components/organisms/__tests__/feat3203_aria_hidden_bleibt.test.ts
- blob:ca8e6c3c03b60d8d1f2b456b3e54c1364636612f  tests/test_2913_c2_besitzerliste.py
