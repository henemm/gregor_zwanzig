---
entity_id: fix_3284_legende_bereich_ohne_l
type: bugfix
created: 2026-11-23
updated: 2026-11-23
status: active
version: "1.0"
workflow: fix-3284-legende-l-doppelt
tags: [was-steht-wo, sms, legende, kuerzel]
---

# Kürzel-Legende „Was steht wo“: kein „L“ beim Temperatur-Bereich (#3284)

## Approval

- [x] Approved (automatisch, Ampel grün, 2026-11-23)

## Purpose

Die Kürzel-Legende der Karte „Was steht wo“ soll nur Kürzel nennen, die die SMS wirklich sendet, jedes höchstens einmal mit genau einer Bedeutung. Bisher steht bei gewähltem Tiefst- und Höchstwert „L = Tagestiefstwert“ in der Legende, obwohl die SMS nur das Bereichs-Token `D13/27` sendet; dadurch kollidiert es mit dem festen „L = Stufe gelb“.

## Source

- **File:** `src/services/placements_view_service.py`
- **Identifier:** `_legende` (baut `legend.metrics` und `legend.fixed`); Hilfsfunktion `_sms_kuerzel` bleibt unverändert

> Schicht: Python-Core (`src/services/`, `src/output/tokens/`). Keine Frontend-Änderung: `wasStehtWoAnsicht.ts` rendert `legend` unverändert.
>
> Querschnitt: Trip und Orte nutzen dieselbe Legendenfunktion (`_legende`, Fläche `trip` bzw. `compare`); die Regel gilt für beide. Es werden keine Nutzerdaten bewegt (reine Anzeige). Alle vier Kanäle sind unberührt, der SMS-Versand ändert sich nicht.

## Scope

- **In Scope:** Legende der Tabelle „Was steht wo“ (Feld `legend.metrics` der Tabellen-Antwort) für Trip und Orte, DE und EN: Tiefstwert-Kürzel (`L`/`FL`) entfällt, wenn die SMS es mit dem Höchstwert zum Bereichs-Token (`D`/`FD`) verschmilzt; das Bereichs-Kürzel trägt die zusammengesetzte Bedeutung.
- **Out of Scope:** SMS-Format und Versand (unverändert), feste Legenden-Einträge (`legend.fixed`), Frontend-Darstellung, neue Katalogtexte.

## Definition of Done

- AC-1 bis AC-7 durch echte Endpunkt-Tests grün nachgewiesen (Trip und Orte, DE und EN).
- Bestehende Legenden-Tests und Golden-Fixtures grün (bei Bedarf angepasst, nur `legend.metrics`).
- Staging zeigt in der Antwort der Tabelle bei Orten mit Tiefst- und Höchstwert kein `L` mehr in `legend.metrics`.

## Estimated Scope

- **LoC:** +25/-3 Quelle, ca. +90 Test
- **Files:** 2 Quelldateien, 1 Testdatei, evtl. Golden-Fixtures
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/services/placements_view_service.py | MODIFY | `_legende`: sind Tiefst- UND Höchstwert-Kürzel eines Paares (`L`/`D`, `FL`/`FD`) beide in der Legenden-Liste, entfällt der Tiefstwert-Eintrag; der Höchstwert-Eintrag trägt die zusammengesetzte Bedeutung „<Tief-Bedeutung>/<Hoch-Bedeutung>“ aus dem Katalog |
| src/output/tokens/builder.py | MODIFY (klein) | Paar-Tabelle `(("L","D"),("FL","FD"))` als benannte Konstante, die Builder (Bereichs-Token #1824) und Legende gemeinsam lesen |
| tests/tdd/test_3284_legende_bereich_ohne_l.py | CREATE | Endpunkt-Tests gegen die echte Tabelle (Feld `legend`) |
| tests/fixtures/ein_vokabular_3101/*.golden.json | MODIFY (nur falls betroffen) | falls ein Golden `legend.metrics` mit `L`/`FL` enthält |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.tokens.builder` (Bereichs-Token, :466-484) | module | Quelle der Verschmelzung `L`+`D` zu `D<tief>/<hoch>`; liefert die Paar-Konstante |
| `output.renderers.orte_sms` (`_BEREICH`, `orte_kuerzel_je_metrik`) | module | gleiche Bereichslogik auf der Orte-Seite |
| `app.metric_catalog` (`kuerzel_bedeutung`, `kuerzel_bedeutung_de/en`) | module | Bedeutungstexte; kein neuer Katalogtext, Schnappschuss #3258 bleibt unverändert |
| `output.tokens.hazard_symbols` (`LEVEL_LETTERS`) | module | feste Warnstufen-Einträge L/M/H, bleiben unverändert |
| feat_3122_was_steht_wo (Nr. 12, AC-31), feat_3258_sms_kuerzel_legende | Spec | Vorgänger-Festlegungen zur Legende |

## Implementation Details

Nachbearbeitung in `_legende`, nachdem die Metrik-Einträge gesammelt sind (nicht in `_sms_kuerzel`, weil das auch für Haken und Beispielwerte genutzt wird). Für jedes Paar aus der gemeinsamen Konstante gilt: stehen beide Kürzel in `legend.metrics`, wird der Eintrag des Tiefstwert-Kürzels entfernt und der Eintrag des Höchstwert-Kürzels erhält als `meaning` die Zusammensetzung „<Tiefstwert-Text>/<Höchstwert-Text>“ aus `kuerzel_bedeutung` in der Sprache des Nutzers (DE „Tagestiefstwert/Tageshöchstwert“, EN „day min/day max“; gefühlt entsprechend „L gefühlt/D gefühlt“). Verschmolzen wird nur, wenn beide Kürzel tatsächlich in der Liste stehen, also genau unter der Bedingung, unter der der Builder das Bereichs-Token bildet. Steht nur ein Kürzel des Paares in der Liste, bleibt die Legende unverändert. Die festen Einträge (`legend.fixed`) werden nicht angefasst.

## Expected Behavior

- **Input:** GET der Tabelle „Was steht wo“ für Trip oder Orte, Sprache DE oder EN, mit SMS-Haken auf Tages-Tief und Tages-Hoch (ggf. gefühlt).
- **Output:** `legend.metrics` enthält kein `L`/`FL`; `D`/`FD` trägt die Bereichsbedeutung. Jedes Kürzel dort kommt im SMS-Beispiel der Antwort vor, keines doppelt.
- **Side effects:** keine; SMS-Inhalt und Versand bleiben unverändert.

## Test Plan

### Automated Tests (TDD RED)

Alle Tests rufen die echte Tabelle über `TestClient` auf (Muster `tests/tdd/test_placements_tabelle_nachzug.py`), ohne Mock.

- [ ] Test 1: GIVEN Orte-Vergleich, DE, SMS-Haken auf Tiefst+Höchst WHEN Tabelle abgerufen THEN kein `L` in `legend.metrics`, `D` mit „Tagestiefstwert/Tageshöchstwert“
- [ ] Test 2: GIVEN wie Test 1, Sprache EN WHEN abgerufen THEN `D` mit „day min/day max“
- [ ] Test 3: GIVEN Trip mit Tages-Tief und Tages-Hoch (DE und EN) WHEN abgerufen THEN dito
- [ ] Test 4: GIVEN gefühlte Tief+Hoch gewählt WHEN abgerufen THEN kein `FL`, `FD` mit „L gefühlt/D gefühlt“ (je Sprache nach Katalog)
- [ ] Test 5: GIVEN beliebige Konfiguration (Trip/Orte, DE/EN) WHEN abgerufen THEN jedes Kürzel aus `legend.metrics` steht im SMS-Beispiel, kein Kürzel doppelt
- [ ] Test 6: GIVEN nur Tiefstwert gewählt WHEN abgerufen THEN `L` mit „Tagestiefstwert“ bleibt in `legend.metrics`
- [ ] Test 7: GIVEN beliebige Auswahl WHEN abgerufen THEN `legend.fixed` (u. a. L/M/H-Stufen) ist unverändert gegenüber dem bisherigen Stand

## Acceptance Criteria

- **AC-1:** Given ein Orte-Vergleich in deutscher Sprache mit SMS-Haken auf Tagestiefst- und Tageshöchstwert der Temperatur / When die Tabelle „Was steht wo“ abgerufen wird / Then enthält `legend.metrics` kein Kürzel `L`, und der Eintrag `D` trägt die Bedeutung „Tagestiefstwert/Tageshöchstwert“.
  - Test: Echter Abruf der Orte-Tabelle (TestClient), Feld `legend.metrics` prüfen, kein Mock.

- **AC-2:** Given derselbe Orte-Vergleich mit Nutzersprache Englisch / When die Tabelle abgerufen wird / Then enthält `legend.metrics` kein `L`, und `D` trägt die Bedeutung „day min/day max“.
  - Test: Echter Abruf mit englischem Nutzer, Bedeutung des Eintrags `D` lesen.

- **AC-3:** Given ein Trip mit SMS-Haken auf Tages-Tief und Tages-Hoch der Temperatur / When die Tabelle für den Trip abgerufen wird (Deutsch und Englisch) / Then fehlt `L` in `legend.metrics`, und `D` trägt die Bereichsbedeutung der jeweiligen Sprache.
  - Test: Echter Abruf der Trip-Tabelle in beiden Sprachen, Feld `legend.metrics`.

- **AC-4:** Given gefühlte Tiefst- und Höchstwerte sind mit SMS-Haken gewählt (Trip und Orte) / When die Tabelle abgerufen wird / Then fehlt `FL` in `legend.metrics`, und `FD` trägt die zusammengesetzte Bedeutung „L gefühlt/D gefühlt“ (englisch entsprechend nach Katalog).
  - Test: Echter Abruf für Trip und Orte, Eintrag `FD` lesen und Fehlen von `FL` prüfen.

- **AC-5:** Given eine beliebige Auswahl von SMS-Metriken bei Trip oder Orten in Deutsch oder Englisch / When die Tabelle abgerufen wird / Then kommt jedes Kürzel aus `legend.metrics` im SMS-Beispiel derselben Antwort vor, und kein Kürzel steht in `legend.metrics` doppelt.
  - Test: Echter Abruf, Kürzel der Legende gegen den Text des SMS-Beispiels abgleichen und auf Duplikate prüfen.

- **AC-6:** Given nur der Tagestiefstwert der Temperatur ist mit SMS-Haken gewählt, der Höchstwert nicht / When die Tabelle abgerufen wird / Then bleibt `L` mit der Bedeutung „Tagestiefstwert“ in `legend.metrics`, weil die SMS dann tatsächlich `L` sendet.
  - Test: Echter Abruf (Trip und Orte), Eintrag `L` vorhanden, Beispiel-SMS enthält `L`.

- **AC-7:** Given beliebige Metrik-Auswahl / When die Tabelle abgerufen wird / Then sind die festen Legenden-Einträge (Stufen L/M/H, Warnung, Zeit, Lawine u. a.) in `legend.fixed` unverändert gegenüber dem Stand vor der Korrektur.
  - Test: Echter Abruf, `legend.fixed` gegen die erwartete Liste der Tokens und Kennungen prüfen.

## Known Limitations

- Ist nur der Tiefstwert gewählt, sendet die SMS `L13` und die Legende nennt „L = Tagestiefstwert“. Das `L` der Warnstufe „gelb“ steht nur innerhalb des `!`-Blocks (z. B. `!TS:L@14`) und ist dort eindeutig. Die gleiche Buchstaben-Wahl ist eine Eigenschaft des SMS-Formats (`docs/reference/sms_format.md`), nicht der Legende; ein Umbau des Formats ist nicht Teil dieses Bugfixes.
- **PO-Entscheidung 2026-11-23:** Im Sonderfall „nur Tiefstwert gewählt“ bleiben beide Zeilen stehen („L = Tagestiefstwert“ in den Metriken, „L = Stufe gelb“ in den festen Einträgen), weil die SMS beides wirklich so schreibt. Ein eigenes SMS-Kürzel für den Tiefstwert wäre ein eigenes Ticket. Die Forderung „höchstens einmal“ aus AC-5 gilt deshalb innerhalb von `legend.metrics`.
- Die Bereichsbedeutung wird aus den vorhandenen Katalogtexten zusammengesetzt; ein eigener Katalogtext für das Bereichs-Token entsteht nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Korrektur der Legendenanzeige an die bereits geltende Bereichsregel des Token-Builders (#1824); keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth) wird berührt.

## Changelog

- 2026-11-23: Initial spec created (Issue #3284)
