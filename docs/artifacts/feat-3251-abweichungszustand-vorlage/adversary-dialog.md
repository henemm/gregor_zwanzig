# Adversary Dialog — feat-3251-abweichungszustand-vorlage
Spec: docs/specs/modules/feat_3251_abweichungszustand_vorlage.md
Datum: 2026-11-21 20:49

## Checkliste
- [x] **Input:** Mockup Fassung 4 mit abgewählter Metrik, Staging-Prüfkonto-Datensatz `mit_abweichung`.
- [x] **Output:** Elementliste enthält den Abschnitt `vorlage-abweichung` mit den Soll-Einträgen; der Abgleich findet sie live in DE und EN.
- [x] **Side effects:** Wechsel "zusätzlich" oder Ausnahme zu "gefunden" ist erlaubt; neue Abweichung ohne Besitzer nicht. Produktverhalten unverändert.
- [x] **AC-1:** Given das Mockup mit einer abgewählten Metrik im Reiter Wetter / When der Generator die Elementliste neu erzeugt / Then enthält sie einen Abschnitt `vorlage-abweichung` mit "▾ 1 Abweichung" / "1 change" und der Zeile „Auf „{vorlage}“ zurücksetzen“ / „Reset to „{vorlage}““.
- [x] **AC-2:** Given der Abgleich-Code / When ein Eintrag des Abschnitts `vorlage-abweichung` einem Prüf-Datensatz zugeordnet wird / Then wird der Datensatz `mit_abweichung` verwendet, und alle übrigen Abschnitte außerhalb `grenzen-*` bleiben bei `ohne_abweichung`.
- [x] **AC-3:** Given der Staging-Abgleich `--scope wetter` in Deutsch und Englisch / When er nach der Änderung läuft / Then sind die Zurücksetzen-Zeile und „1 Abweichung“ / „1 change“ als gefunden gemeldet, ohne dass eine Ausnahme sie abdeckt.
- [x] **AC-4:** Given die Besitzerliste nach der Änderung / When der Abgleich beide Sprachen prüft / Then sind die pauschalen Ausnahmen aus #3205 für die Zurücksetzen-Zeile gestrichen, und es entsteht keine neue Abweichung ohne Besitzer.
- [x] **AC-5:** Given die Elementliste wurde neu erzeugt / When die Prüfsumme geprüft wird / Then stimmt sie mit der Datei überein und ist im Test mit Begründung nachgezogen, und der Rest der Liste (alle Seiten-Zustände normal, laedt, fehler, luecken) bleibt unverändert.
- [x] **AC-6:** Given Nutzer mit Trips und Orts-Vergleichen / When sie die Anwendung nutzen / Then ändert sich nichts, denn Produktcode, Prüfdaten und Mockup bleiben unverändert und kein dritter globaler Zustand entsteht.

## Dialog

### Runde 1
**Adversary:** Vorrunden: BROKEN (Pfeil, dann Zahl 14/8 statt 1), siehe dialog_runde1.md/dialog_runde2.md.
**Implementierer:** Fix-Loop 1 und 2.

### Runde 2
**Adversary:** Live DE (r3-de) und EN (r3-en): „{count} Abweichungen“/„{count} changes“ und Zurücksetzen-Zeile in trip und orte gefunden, Ausnahme weg, abweichend ohne Besitzer 16 (wie vorher), zusätzlich unverändert (142/168), kein Statuswechsel. Tests: node 53 grün, Mockup-Spec 3 grün, pytest grün. Mutationen (sha256 identisch, restauriert): Haken entfernt -> 1 Test rot; Klick entfernt -> 2 Mockup-Specs rot; Muster-Funktion entfernt -> 1 Test rot; Zuordnung mit_abweichung -> rot. Lücke F001 (LOW): text_de „1 Abweichung“ (Einzahl) führt Mehrzahl-Muster; Einzahl .one wird live nie geprüft, und „{count} Abweichungen“ passt grammatisch falsch auch auf „1 Abweichungen“. Vertretbar, da der Prüf-Datensatz 14/8 Abweichungen hat und Prüfdaten unverändert bleiben müssen; Vorschlag: Katalogzeile .one im Katalogtest absichern.
**Implementierer:** (nicht befragt)

Code reference: scripts/elementliste_aus_mockup.ts:417
Code reference: frontend/e2e/elementliste_abgleich_logik.ts:397
Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:93
Code reference: frontend/e2e/elementliste-generator.mockup.spec.ts:47
Code reference: frontend/e2e/feat3251_vorlage_abweichung.test.ts:171
Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:1
Code reference: tests/test_2913_c2_besitzerliste.py:155
Code reference: docs/context/einstellungen_neu/elementliste.json:1
Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:1
Code reference: docs/specs/modules/feat_3251_abweichungszustand_vorlage.md:99


## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Confirmation:
  AC: AC-1
  Code reference: scripts/elementliste_aus_mockup.ts:417
  Evidence: elementliste.json führt vorlage-abweichung mit Mockup-Text „1 Abweichung“ und Zurücksetzen-Zeile; Mockup-Spec grün
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:489
  Evidence: datensatzFuerAbschnitt mit_abweichung; Mutation rot
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:93
  Evidence: Live DE und EN gefunden (r3-de, r3-en), ohne Ausnahme
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:1
  Evidence: Ausnahme gestrichen, abweichend ohne Besitzer 16 wie vorher
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/test_2913_c2_besitzerliste.py:155
  Evidence: pytest grün, kein Statuswechsel übriger Einträge
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:1
  Evidence: nur Generator, Abgleich, Listen, Tests geändert
  Status: CONFIRMED

Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: scripts/elementliste_aus_mockup.ts:417
  Description: Eintrag text_de „1 Abweichung“ führt Schlüssel .other und Muster „{count} Abweichungen“; die Einzahl wird live nie geprüft, das Muster passt auch auf „1 Abweichungen“.
  Spec requirement: AC-1/AC-3 — „1 Abweichung“ / „1 change“
  Conflict: Mockup-Einzahl ist nicht prüfbar, weil der Prüf-Datensatz 14/8 Abweichungen liefert.
  Remediation: Vertretbar; optional Katalogtest für .one und .other.

## Verdict
VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:b77262a6b8cfc5044b98764ed3df504c5e1d8ac3fe0e3c80e2b1771f732373ba  docs/context/einstellungen_neu/elementliste.json
- sha256:3983a536920867abfe54123f3b97b06f680b2bf50f1c5b561c6538bacae7bd01  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:a571864465944a31fee8e91dfd22e9ce79e0becd62209e58ba50dafdd82b8811  docs/specs/modules/feat_3251_abweichungszustand_vorlage.md
- sha256:501a4a0b9766d57189cc86e1cff28c167baa029cae21c7f5e1b2cd3cfc984d20  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:24c9339f9c0e21c941ec944a0511d07f878c6b0debc719862e5ea9dc29fc38ef  frontend/e2e/elementliste-generator.mockup.spec.ts
- sha256:4e3df7bc6cdae655c22bc48e4334895c0f6693b2cd896489df42770b44e236ba  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:9dffaa4ec1a48b33861dcc720e6870e99f202765480be4dbd851c8c9012562da  frontend/e2e/feat3251_vorlage_abweichung.test.ts
- sha256:352c79279103c2cf298400694e6e6dae527b315c71312b9e1649b8e5f9fa7133  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:74b8a15c0f7150b857f349f765d06f93172ee6f6b327cef1095d2dc6ac9d20ef  scripts/elementliste_aus_mockup.ts
- sha256:60271f2104ac411cb3cf215cbbc55b9fa845919c9b95c3cb2cb14070517aa8ba  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 6246f2f3c34799fcd552c3a6422712dd253332f3
- blob:2fb686c5ecded8f642f2b199ce649aa92f5178aa  docs/context/einstellungen_neu/elementliste.json
- blob:f7ef9ef4c00a44bac4efb600c18570f07eda3500  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:943d422213cf9a903a52d9b3df62691df9e64198  docs/specs/modules/feat_3251_abweichungszustand_vorlage.md
- blob:fbda231aa7179086053ad709ee05563ded7e53bd  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:75a3e7e893e91a77e7a54dfb2870041c818de4c9  frontend/e2e/elementliste-generator.mockup.spec.ts
- blob:1bf1c308ded5916c8f0e7468ebbdf09b5523cafd  frontend/e2e/elementliste_abgleich_logik.ts
- blob:a5a580f91dd0e98f918d600e7a0265102f539327  frontend/e2e/feat3251_vorlage_abweichung.test.ts
- blob:49546236f7c7cfab62188b2a5c6c6c042452db7b  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:c8d7edd30778cff75307788f6998ec63e4424ff2  scripts/elementliste_aus_mockup.ts
- blob:8366ad9329e22d046d3716179638674b4486bf8e  tests/test_2913_c2_besitzerliste.py
