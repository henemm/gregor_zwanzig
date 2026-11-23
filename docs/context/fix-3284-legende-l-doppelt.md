# Context: fix-3284-legende-l-doppelt

## Request Summary
Die Kürzel-Legende („Kürzel erklärt“) der Karte „Was steht wo“ zeigt bei Orten „L = Tagestiefstwert“ und zusätzlich „L = Stufe gelb“. Die SMS sendet bei gewähltem Tiefst- UND Höchstwert nur das Bereichs-Token `D13/27` (kein eigenes `L`), die Legende soll nur wirklich gesendete Kürzel zeigen, jedes höchstens einmal mit einer Bedeutung (Trip und Orte, DE und EN).

## Related Files
| File | Relevance |
|------|-----------|
| src/services/placements_view_service.py:254 `_sms_kuerzel` | Kürzel je Zeile: Trip aus `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC`, Orte aus `orte_kuerzel_je_metrik()` — liefert `L` für `temperature_day_low` unabhängig davon, ob `D` auch gewählt ist |
| src/services/placements_view_service.py:278 `_legende` | baut `legend.metrics` (je SMS-Haken-Zeile die Kürzel) + `legend.fixed` (u. a. `L`=stufe_gelb, `M`, `H` aus `LEVEL_LETTERS`) — hier liegt die Korrektur |
| src/output/tokens/builder.py:466-484 | Bereichs-Token #1824: sind `L` und `D` (bzw. `FL`/`FD`) beide da, wird daraus EIN Token `D<tief>/<hoch>`, `L` fällt weg — gilt für Trip- UND Orte-SMS |
| src/output/renderers/orte_sms.py:79 `_BEREICH`, :290 `orte_kuerzel_je_metrik`, :299 `token_metriken` | Orte-Seite kennt dieselbe Bereichslogik (`D`→`L`, `FD`→`FL`) |
| src/app/metric_catalog.py:220-252, 324-342 | `kuerzel_bedeutung_de/en`: L=Tagestiefstwert, D=Tageshöchstwert, FL=„L gefühlt“, FD=„D gefühlt“; `kuerzel_bedeutung()` :1771 |
| src/output/tokens/hazard_symbols.py `LEVEL_LETTERS` | Warnstufen L/M/H (feste Legenden-Einträge) |
| frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts | rendert `legend` (keine eigene Logik zu erwarten) |

## Existing Patterns
- `_trip_sms_werte` (placements_view_service.py:432ff) behandelt den verschmolzenen Bereich bereits für die Beispielwerte (Tiefstwert zeigt das gemeinsame `D14/18`-Token) — dieselbe Regel muss die Legende kennen.
- `token_metriken` (orte_sms) ordnet das Bereichs-Token beiden Metriken zu.

## Dependencies
- Upstream: SMS-Symboltabellen (sms_trip), orte_sms, metric_catalog, hazard_symbols.
- Downstream: GET Tabelle „Was steht wo“ (Feld `legend`), Frontend-Karte, Elementliste/Schnappschuss `docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json` (#3258), Golden-Fixtures `tests/fixtures/ein_vokabular_3101/*.golden.json` (enthalten evtl. `legend`).

## Existing Specs
- docs/specs/modules/feat_3122_was_steht_wo.md Nr. 12 / AC-31 (Legende = Kürzel der Metriken mit SMS-Haken)
- docs/specs/modules/feat_3258_sms_kuerzel_legende.md

## Risks & Considerations
- Offene Fachfrage für die Analyse: Ist NUR der Tiefstwert gewählt (ohne Höchstwert), sendet die SMS tatsächlich ein einzelnes `L13` — dann kollidiert `L` echt mit `L` = Stufe gelb (unterschiedliche Position: Warnstufe nur im `!`-Block). Wie die Legende das zeigt, muss die Spec festlegen.
- Bei verschmolzenem Bereich ist „D = Tageshöchstwert“ allein ungenau (D13/27 trägt Tief/Hoch) — Bedeutungstext ggf. anpassen (Katalog-Schnappschuss #3258 driftet mit).
- Dateien von #3237 (placements.py, channel_list_resolver.py) nicht anfassen — placements_view_service.py ist nicht betroffen.
- Golden-Fixtures mit `legend` können sich ändern.

## Analysis

### Type
Bug

### Ursache (belegt)
`_legende` (src/services/placements_view_service.py:278) listet je Zeile mit SMS-Haken die Symbole der Symboltabellen (`_sms_kuerzel` :254). Der Token-Builder (src/output/tokens/builder.py:478-484) verschmilzt aber `L`+`D` (und `FL`+`FD`) zu EINEM Bereichs-Token unter `D`/`FD` (`D13/27`) — gilt für Trip und Orte (Orte: `_BEREICH` in orte_sms.py:79). Die Legende kennt diese Verschmelzung nicht und nennt `L`/`FL` trotzdem → „L = Tagestiefstwert“ neben dem festen „L = Stufe gelb“.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/placements_view_service.py | MODIFY | `_legende`: sind Tiefst- UND Höchstwert-Kürzel eines Paares (`L`/`D`, `FL`/`FD`) beide in der Liste, entfällt der Tiefstwert-Eintrag; der Höchstwert-Eintrag trägt die zusammengesetzte Bedeutung „<Tief-Bedeutung>/<Hoch-Bedeutung>“ aus dem Katalog (DE „Tagestiefstwert/Tageshöchstwert“, EN „day min/day max“) — kein neuer Katalogtext, Schnappschuss #3258 bleibt unverändert. Paar-Tabelle aus derselben Quelle wie der Builder (eine gemeinsame Konstante, z. B. `_BEREICH` aus orte_sms bzw. neue Konstante im Builder, die beide nutzen). |
| src/output/tokens/builder.py | MODIFY (klein, optional) | Paar-Tabelle `(("L","D"),("FL","FD"))` als benannte Konstante, damit Legende und Builder dieselbe Quelle lesen |
| tests/tdd/test_3284_legende_bereich_ohne_l.py | CREATE | Endpunkt-Tests (echte Tabelle, Feld `legend`): Trip und Orte, DE und EN; Tiefst+Höchst gewählt ⇒ kein `L`/`FL` in `legend.metrics`, `D` mit Bereichsbedeutung; jedes Kürzel in `legend.metrics` kommt im SMS-Beispiel vor; nur Tiefstwert gewählt ⇒ `L` bleibt (wird gesendet) |
| tests/fixtures/ein_vokabular_3101/*.golden.json | evtl. MODIFY | falls ein Golden `legend.metrics` mit L enthält |

### Scope Assessment
- Files: 2 Quell-, 1–2 Test-Dateien
- Estimated LoC: +25/-3 Quelle, +80 Test
- Risk Level: LOW (nur Anzeige der Legende; Versand unverändert)

### Technical Approach
Nachbearbeitung in `_legende` nach dem Sammeln der Metrik-Einträge (nicht in `_sms_kuerzel`, weil `_sms_kuerzel` auch für Haken/Beispielwerte genutzt wird). Verschmolzen wird nur, wenn beide Kürzel tatsächlich in der Legenden-Liste stehen — genau die Bedingung des Builders (beide Hälften entstehen).

### Entscheidung zum Einzelfall (Tech Lead)
Ist nur der Tiefstwert gewählt, sendet die SMS wirklich `L13`; dann bleibt „L = Tagestiefstwert“ in der Legende stehen, weil die Legende genau die gesendeten Kürzel zeigt (Spec Nr. 12). Das `L` der Warnstufe steht nur innerhalb des `!`-Blocks (`!TS:L@14`) und ist dort eindeutig. Das ist eine Eigenschaft des SMS-Formats (sms_format.md), nicht der Legende — als Known Limitation in der Spec, kein Umbau des Formats in diesem Bug.

### Dependencies
Frontend rendert `legend` unverändert (keine Frontend-Änderung). #3237-Dateien nicht betroffen.

### Open Questions
- keine (Einzelfall oben entschieden)
