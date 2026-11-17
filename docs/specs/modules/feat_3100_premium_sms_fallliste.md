---
entity_id: feat_3100_premium_sms_fallliste
type: feature
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feat-3100-premium-sms-fallliste
tags: [epic-3058, phase-3e, epic-3047, pruefkatalog, premium-sms, empfangsweg]
---

# Premium-SMS-Fallliste im Prüfkatalog (Phase 3e von #3047)

## Approval

- [ ] Approved

## Purpose

Der Prüfkatalog bekommt eine eigene Fallliste für die Premium-SMS (Garmin inReach), die vom Wächter mitgezählt wird. Sie belegt über den echten Empfangsweg (Garmin-Befehl über `inbound_sms_reader`, Antwort per Premium-SMS), dass die Premium-SMS inhaltlich der SMS desselben Trips bzw. Orts-Vergleichs folgt, bis auf die kürzere Grenze von 153 statt 160 Zeichen.

**Abweichung vom Issue-Text:** Die erste Zeile von #3100 (eigene Premium-Spalte bzw. eigener Resolver-Schlüssel `premium_sms`) ist durch die PO-Freigabe vom 17.11. und ADR-0124 Nr. 8 überholt. Die Premium-SMS folgt vorerst der SMS; ein eigener Schlüssel `premium_sms` wird hier ausdrücklich NICHT ausgewertet (das ist #2801). Diese Spec liefert nur den Nachweis im Prüfkatalog.

## Source

- **File:** `tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json`, `tests/tdd/test_3100_premium_sms_fallliste.py`
- **Identifier:** Fallliste `premium_sms` (Fall-IDs mit Präfix `psms-`), Wächter `tests/tdd/test_einstellung_gleich_mail_fallliste.py` (`TEILDATEIEN`, `PY_TEST_GLOBS`)

> **Schicht-Hinweis:** Reine Nachweis-Arbeit in Tests und Prüfkatalog. Produktionscode im Python-Core (`src/services/inbound_sms_reader.py`, `trip_command_processor.py`, `channel_list_resolver.py`) bleibt voraussichtlich unverändert; kein Frontend, keine Go-API. Scheitert ein Eingangsweg-Test fachlich, ist das ein Befund (eigenes Issue bzw. Fix im Rahmen), kein Grund, den Test aufzuweichen.
>
> **Trip/Orte-Teilung:** Die Fallliste und die Tests decken beide Kontexte (Trip und Orte) mit demselben Muster ab; kein neues Pendant-Paar von Komponenten.
>
> **Mandantentrennung:** Die Eingangsweg-Tests laufen mit zwei verschiedenen Nutzern; jede Premium-Antwort enthält nur Auswahl und Daten des eigenen Nutzers. `user_id` kommt aus dem Kontext des Befehls, kein Fallback auf `"default"`.
>
> **Kanäle:** Betroffen ist die Premium-SMS im Vergleich zur SMS. E-Mail und Telegram bleiben unverändert. ADR-0095: alle vier Kanäle gleichrangig, gleicher Inhalt.

## Scope

In Scope:
- Neue Fallliste `fallliste_premium_sms.json` (ca. 12 bis 16 Fälle), Wächter-Registrierung.
- Neue Tests am echten Eingangsweg (Trip und Orte), Kürzungsfall, Wächter-Selbsttest.
- Doku-Zeile in der Ausgabe-Matrix.

Nicht in Scope:
- Eigener Resolver-Schlüssel `premium_sms`, eigene Premium-Auswahl oder Premium-Spalte (#2801, ADR-0124 Nr. 8).
- Live-Dialog über die zweite seven.io-Nummer (bleibt Teil von `/e2e-verify` bzw. Deploy, Opt-in, nur Prod).
- Neue Alarm-Tests (Alarme sind nur Verweis-Fall, Kanalparität #1701 ist bereits belegt).
- Jede sichtbare Änderung der zugestellten Premium-SMS.

## Estimated Scope

- **LoC:** ca. +350/-5 (Test ca. 200, JSON ca. 120, Doku und Wächter der Rest)
- **Files:** 4 bis 5 (1 Fallliste, 1 neuer Test, 1 Wächter, 1 Doku-Datei, diese Spec)
- **Effort:** low bis medium (Risiko LOW: nur Tests und Prüfkatalog)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/inbound_sms_reader.py` | module | Echter Eingangsweg: Journal-GET, Befehl lesen, Antwort versenden (Trip und Vergleich, `resolved_kind`) |
| `src/services/trip_command_processor.py` | module | Befehlsverarbeitung, Antwort per Premium-SMS |
| `src/services/channel_list_resolver.py` | module | `premium_sms` fällt ohne eigene Ebene auf `sms` zurück (Zeilen 158-162), bleibt unverändert |
| `src/output/renderers/channel_layout.py` | module | Premium-Grenze 153, SMS-Grenze 160 |
| `tests/tdd/test_premium_sms_kommandopfad.py` | tests | Muster für Außengrenzen: Journal-GET, Learn-POST, vier Kanal-Ausgänge |
| `tests/tdd/test_3099_sms_resolver.py` | tests | Muster Trip-Versand und Orte-Versand (AC-6, AC-7), Wächter-AC |
| `tests/tdd/test_3047_r7_kanaele_trip.py` | tests | Zwei-Nutzer-Versandkette mit Aufzeichner an den Kanal-Ausgängen |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | tests | Wächter: `TEILDATEIEN`, `PY_TEST_GLOBS`, Kanal-Abdeckung (f) |
| `fallliste_sms.json`, `fallliste_trip.json`, `fallliste_orte.json` | fixture | Enthalten die verstreuten Premium-Fälle, die bleiben |
| `src/services/trip_alert.py`, `compare_alert_channels.py` | module | Alarm-Verweis-Fall (Kanalparität #1701) |
| `docs/reference/metric_output_matrix.md` | doc | Ausgabe-Matrix, Premium-Zeile verweist auf die neue Fallliste |
| ADR-0049, ADR-0095, ADR-0121 (Nr. 5), ADR-0124 (Nr. 8) | ADR | Entscheidungsgrundlage |

## Implementation Details

Reihenfolge: Spec, Fälle und RED-Tests, Wächter-Registrierung, Doku.

1. **Eigene Teildatei:** `fallliste_premium_sms.json` im heutigen Format, neue Fall-IDs mit Präfix `psms-` (global eindeutig). Achsen in `merkmale`: Kontext (Trip/Orte), Weg (Eingang/Versand/Alarm-Verweis), Report-Typ (morning/evening), Kanal-Ebene für `channel_layouts.premium_sms` (nie/leer/abweichend gesetzt), Roh/Einfach, Kürzung.
2. **Empfangsweg (neu, Kern):** Die Tests treiben den echten `inbound_sms_reader` mit Außengrenzen wie in `test_premium_sms_kommandopfad.py` (Journal-GET, Learn-POST, Aufzeichner an den vier Kanal-Ausgängen, kein `Mock()`/`patch()`). Je Nutzer wird ein Trip bzw. ein Orts-Vergleich mit abweichender `channel_layouts.premium_sms` angelegt; ein Garmin-Befehl („heute/morgen“) löst die Antwort aus. Verglichen wird der an die Premium-SMS-Ausgabe gebuchte Text mit dem SMS-Text desselben Ziels (Versandkette `send_on_demand_report(..., restrict_to_channel="sms")`).
3. **Gleichheitsregel:** „Gleich“ heißt: Premium-Text == SMS-Text, solange dieser in 153 Zeichen passt; darüber kürzt Premium nach derselben Regel vom Listenende, die amtliche Warnung bleibt (ADR-0121 Nr. 6). Ein Eingangsweg-Fall mit langem Text (> 153) prüft Präfix-Gleichheit und Warnung hinten.
4. **Keine Auswertung eines eigenen Schlüssels:** Eine abweichende `channel_layouts.premium_sms` wird bewusst NICHT gelesen; der Test belegt genau das (kein Vorgriff auf #2801).
5. **Verstreute Premium-Fälle bleiben** in ihren Dateien (u. a. `R7-KAT-trip-premium-matrix`, `R7-KAT-trip-premium-gleich-sms-kuerzung`, `R7-KAT-orte-premium-gleich-sms`, `sms-premium-gleich-sms-text`, `sms-orte-versand-roh/einfach`, `orte_premium_sms`-Fälle). IDs bleiben global eindeutig, die Kanal-Abdeckung (f) sinkt nicht; die neue Liste nennt sie im `hinweis`.
6. **Alarm-Verweis-Fall:** Ein Fall verweist auf die vorhandenen Kanalparitäts-Tests (`test_compare_alert_channel_equivalence.py`, `test_onset_ende_kanalparitaet.py`); Alarme lesen keine Metrikauswahl, daher kein neuer Test.
7. **Wächter:** `TEILDATEIEN` + `premium_sms`, `PY_TEST_GLOBS` + `tests/tdd/test_3100_*.py`, Selbsttest „fehlende Premium-Teildatei scheitert klar“.
8. **Doku:** Premium-Zeile in `docs/reference/metric_output_matrix.md` verweist auf `fallliste_premium_sms.json` und nennt ADR-0124 Nr. 8.

## Expected Behavior

- **Input:** Garmin-Befehl eines Nutzers (Trip bzw. Orts-Vergleich) über den Eingangsweg, sowie der reguläre Versand für Trip und Orte.
- **Output:** Die Premium-SMS-Antwort ist gleich dem SMS-Text desselben Ziels, höchstens 153 Zeichen (bei Überlänge gleiche Kürzungsregel, Warnung bleibt hinten); eine abweichende Premium-Ebene ändert nichts.
- **Side effects:** keine; reine Prüfung, Produktionsverhalten unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit abweichender `channel_layouts.premium_sms` und ein Garmin-Befehl über den Eingangsweg / When die Antwort per Premium-SMS versendet wird / Then ist der gesendete Premium-Text gleich dem SMS-Text desselben Trips und die abweichende Premium-Ebene wird nicht gelesen.
  - Test: `test_3100_premium_sms_fallliste.py`, echter `inbound_sms_reader` mit Aufzeichner an den Kanal-Ausgängen, Trip morning und evening, Text an `PremiumSmsOutput` gegen SMS-Text.

- **AC-2:** Given ein Orts-Vergleich mit abweichender `channel_layouts.premium_sms` und ein Garmin-Befehl über den Eingangsweg / When die Antwort per Premium-SMS versendet wird / Then ist der Premium-Text gleich dem SMS-Text desselben Vergleichs, auch mit Roh und Einfach.
  - Test: Eingangsweg mit `resolved_kind="vergleich"`, Roh- und Einfach-Konfiguration, Premium-Text gegen SMS-Text; kein `Mock()`/`patch()`.

- **AC-3:** Given zwei verschiedene Nutzer mit unterschiedlicher SMS-Auswahl, jeder mit eigenem Garmin-Befehl / When beide Antworten hintereinander (beide Aufrufreihenfolgen) versendet werden / Then enthält jede Premium-Antwort nur Auswahl und Daten des eigenen Nutzers und niemals Inhalte des anderen.
  - Test: Zwei Nutzer im selben Prozess, Premium-Texte je Nutzer gegen die jeweilige SMS; Empfänger gehören dem eigenen Nutzer; kein Fallback auf `"default"`.

- **AC-4:** Given ein Trip mit langem SMS-Text über 153 Zeichen und einer amtlichen Warnung / When die Antwort per Premium-SMS über den Eingangsweg versendet wird / Then ist der Premium-Text höchstens 153 Zeichen lang, ein Anfangsstück des SMS-Textes (Kürzung vom Listenende) und die amtliche Warnung steht weiter hinten im Text.
  - Test: Eingangsweg-Fall mit Überlänge; Präfix-Gleichheit gegen den SMS-Text, Länge ≤ 153, Warnblock im Premium-Text vorhanden.

- **AC-5:** Given die Fallliste `fallliste_premium_sms.json` / When sie die Achsen Trip/Orte, Eingang/Versand, morning/evening, Kanal-Ebene nie/leer/abweichend und Roh/Einfach betrachtet / Then deckt sie jede dieser Achsen mit mindestens einem Fall mit Präfix `psms-` ab, und alle Fälle verweisen auf einen Test, der sie tatsächlich ausführt.
  - Test: Auswertung der `merkmale` der Fälle gegen die Achsenliste; jeder Fall nennt einen existierenden Test; Fall ohne Test scheitert klar.

- **AC-6:** Given die neue Fallliste und die bereits verstreuten Premium-Fälle in `fallliste_trip.json`, `fallliste_orte.json` und `fallliste_sms.json` / When der Wächter `test_einstellung_gleich_mail_fallliste.py` läuft / Then ist die neue Datei registriert und mitgezählt, alle Pflichtfelder sind gefüllt, alle IDs sind global eindeutig, die verstreuten Fälle sind im `hinweis` genannt, und die Kanal-Abdeckung `premium_sms` ist nicht kleiner als vorher.
  - Test: Wächter einzeln inklusive Selbsttests der Fehlerzahl; `test_3100_*` über `PY_TEST_GLOBS` mitgezählt; fehlende Premium-Teildatei scheitert mit klarer Meldung.

- **AC-7:** Given Alarme an die Premium-SMS (Trip- und Orts-Alarm) / When der Prüfkatalog den Alarm-Fall führt / Then steht er als Verweis auf die bestehenden Kanalparitäts-Tests und nicht als neue Metrikauswahl-Prüfung; der Alarmtext der Premium-SMS bleibt gleich dem SMS-Alarmtext.
  - Test: Der Verweis-Fall nennt `test_compare_alert_channel_equivalence.py` und `test_onset_ende_kanalparitaet.py`; beide laufen einzeln grün.

- **AC-8:** Given die Premium-SMS folgt vorerst der SMS (ADR-0124 Nr. 8) / When der Code nach dieser Arbeit geprüft wird / Then ist der Resolver-Schlüssel `premium_sms` weiterhin eine Kopie der SMS-Liste ohne eigene Auswertung, und es gibt keine Produktionsänderung, die eine eigene Premium-Auswahl liest.
  - Test: Verhaltenstest am Eingangsweg, abweichende Premium-Ebene ändert den gesendeten Text nicht; `test_3057_channel_list_resolver.py` und `test_compare_premium_sms_versand.py` einzeln unverändert grün.

- **AC-9:** Given die Ausgabe-Matrix `docs/reference/metric_output_matrix.md` / When ein Leser die Premium-SMS-Zeile liest / Then verweist sie auf die neue Fallliste und nennt, dass die Premium-SMS vorerst der SMS folgt und eine eigene Auswahl mit #2801 kommt.
  - Test: `# doc-compliance-test` für die Doku-Zeile; fachlicher Nachweis liegt in AC-1 bis AC-6.

## Definition of Done

- AC-1 bis AC-9 durch benannte Tests grün; Wächter einzeln grün; kein bestehender Test geändert, um Rot zu verdecken.
- Mutations-Gegenprobe durch den Adversary (siehe Test Plan).
- Vor dem ersten Code gegen `origin/main` abgeglichen.
- Alle 6 CI-Checks grün; Staging-Verifikation und Prod-Selftest bestanden; Live-Empfang über die zweite seven.io-Nummer bleibt Teil von `/e2e-verify`.

## Test Plan

### Automated Tests (TDD RED)

Zusicherungen am Wirkort (Aufzeichner an den Kanal-Ausgängen), kein Mock-Theater.

- [ ] Neu `tests/tdd/test_3100_premium_sms_fallliste.py`: GIVEN Trip mit abweichender Premium-Ebene WHEN Garmin-Befehl über `inbound_sms_reader` THEN Premium-Antwort == SMS-Text, morning und evening (AC-1).
- [ ] Neu: GIVEN Orts-Vergleich (Roh/Einfach) WHEN Garmin-Befehl THEN Premium-Antwort == SMS-Text desselben Vergleichs (AC-2).
- [ ] Neu: GIVEN zwei Nutzer WHEN beide Aufrufreihenfolgen THEN je eigene Premium-Antwort (AC-3).
- [ ] Neu: GIVEN Überlänge und Warnung WHEN Antwort THEN ≤ 153, Präfix des SMS-Textes, Warnung hinten (AC-4).
- [ ] Neu: GIVEN Fallliste WHEN Achsenprüfung THEN alle Achsen belegt, jeder Fall hat einen ausführenden Test (AC-5).
- [ ] Neu: Wächter-Selbsttest „fehlende Premium-Teildatei scheitert klar“, `TEILDATEIEN`/`PY_TEST_GLOBS` angepasst (AC-6).
- [ ] Neu: Alarm-Verweis-Fall, Verweistests einzeln grün (AC-7).
- [ ] Neu: abweichende Premium-Ebene ändert gesendeten Text nicht (AC-8).
- [ ] Unverändert grün (Regression, einzeln benannt): `test_premium_sms_kommandopfad.py`, `test_3099_sms_resolver.py`, `test_3047_r7_kanaele_trip.py`, `test_compare_premium_sms_versand.py`, `test_compare_channel_layouts_3039.py`, `test_3057_channel_list_resolver.py`, `test_einstellung_gleich_mail_fallliste.py`.
- [ ] Mutations-Gegenprobe durch den Adversary (Kopie extern, String-Ersetzung, nie `git checkout/stash/reset`): Premium liest `channel_layouts.premium_sms`; Premium-Grenze 153 auf 160 geändert; Kürzung entfernt die Warnung statt Listenende; Antwort an Empfänger eines anderen Nutzers; Fall ohne Test in der Liste. Jede Verfälschung muss mindestens einen Test rot machen.
- Live-E2E: Dialog Prod mit zweiter seven.io-Nummer in `/e2e-verify` bzw. Deploy (Opt-in, außerhalb der Kern-Schicht).

## Affected Files

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json` | CREATE | Premium-SMS-Fallliste, Präfix `psms-`, ca. 12 bis 16 Fälle |
| `tests/tdd/test_3100_premium_sms_fallliste.py` | CREATE | Eingangsweg-Tests Trip und Orte, Zwei-Nutzer, Kürzung, Achsenprüfung |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | `TEILDATEIEN` + `premium_sms`, `PY_TEST_GLOBS` + `test_3100_*`, Selbsttest |
| `docs/reference/metric_output_matrix.md` | MODIFY | Premium-Zeile verweist auf neue Fallliste |
| `docs/specs/modules/feat_3100_premium_sms_fallliste.md` | CREATE | diese Spec |
| `src/…` | keine Änderung erwartet | Befund statt Änderung, falls ein Eingangsweg-Test fachlich scheitert |

## Known Limitations

- Die Premium-SMS hat keine eigene Auswahl; eine eigene Premium-Liste kommt frühestens mit #2801.
- Der Text von #3100 (erste Zeile) bildet den Umfang vor der PO-Entscheidung ab und gilt insoweit nicht mehr.
- Der Live-Empfang auf dem echten Gerät bzw. der zweiten Nummer ist nicht Teil der Kern-Schicht.
- Fälle bleiben im heutigen Format `channel_layouts.*`; Neuformulierung beim Neuschnitt (#3122/ADR-0124).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Nr. 8), ADR-0049, ADR-0095; kein neues ADR nötig
- **Rationale:** Die Spec setzt die PO-Entscheidung „Premium-SMS folgt vorerst der SMS“ als Nachweis im Prüfkatalog um; ADR-0095 (jeder Kanal beantwortet jede Frage mit demselben Inhalt) bleibt erfüllt. Keine Entscheidung wird rückgängig gemacht.

## Changelog

- 2026-11-17: Initial spec created (Phase 3e, Issue #3100, Epic #3058)
- 2026-11-17: Befund aus RED (AC-4) im Rahmen behoben: das Trip-Briefing sandte an die Premium-SMS den 160er-SMS-Text (bis 160 > 153 Zeichen). Neu `TripReport.premium_sms_text` (gleich `sms_text`, solange ≤ 153; sonst derselbe Formatter mit Grenze 153), gesendet in `notification_service.py`. Damit sind „Side effects: keine“ und „src: keine Änderung“ überholt; keine eigene Premium-Auswahl (AC-8 unverändert). `test_3047_r7_kanaele_trip.py::test_ac23` sicherte das alte Verhalten zu und folgt jetzt der Regel aus Punkt 3.
