---
entity_id: fix_1430_meteoalarm_lawine
type: bugfix
created: 2026-10-12
updated: 2026-10-12
status: draft
version: "1.0"
tags: [meteoalarm, official_alerts, avalanche, sms, telegram, premium-sms, email, hazard-symbols]
workflow: fix-1430-lawinenwarnung-meteoalarm-typ9
---

# MeteoAlarm-Lawinenwarnung (Typ 9) wird nicht mehr verworfen

## Approval

- [ ] Approved

## Purpose

MeteoAlarm meldet Lawinenwarnungen als Awareness-Typ 9. Der Mapper kennt diesen Typ nicht und
wirft die Warnung ohne Log weg; im Bericht steht dann "keine amtlichen Warnungen", obwohl eine
Lawinenwarnung vorliegt (Issue #1430, Epic #2258). Die Spec fuehrt die Gefahrenart `avalanche`
im Katalog ein, damit die Warnung ueber beide Eingangswege (CAP-XML und JSON-Feed) und alle vier
Kanaele (E-Mail, Telegram, SMS, Premium-SMS) ankommt, und macht die bewusst nicht
unterstuetzten Typen Nebel (4) und Kueste (7) im Log sichtbar statt stumm.

Sie ergaenzt den Kuerzel-Katalog aus `docs/specs/modules/sms_official_alert_tokens.md`
(Abschnitt 1/1b) um einen Eintrag; die Datei dieser freigegebenen Spec bleibt unveraendert,
massgeblich fuer `avalanche` ist diese Spec.

## Source

- **File:** `src/services/official_alerts/meteoalarm.py` — `_TYPE_HAZARD_MAP`, `_group_and_map_info_entries()`
- **File:** `src/output/tokens/hazard_symbols.py` — `HAZARD_SMS_SYMBOLS`, `HAZARD_BEDEUTUNG_EN/_DE`
- **File:** `src/output/renderers/alert/official_alerts.py` — `_HAZARD_LABELS`
- **File:** `src/output/renderers/email/compare_html.py` — `_warn_short()`
- **Identifier:** `_TYPE_HAZARD_MAP`, `HAZARD_SMS_SYMBOLS`, `_warn_short`

**Schicht:** ausschliesslich Python-Core (`src/services/`, `src/output/`). Kein Go-API-Anteil,
kein neuer Endpoint, kein Frontend-Code (die Kuerzel-Legende im Frontend liest den
Backend-Katalog zur Laufzeit, siehe `sms_official_alert_tokens.md` Abschnitt 5).

## Estimated Scope

- **LoC:** ca. +60/-5 (Code und Tests, ohne Doku)
- **Files:** 4 Code-Dateien, 7 Testdateien (davon 2 neu), 1 Fixture (neu), 1 Doku-Datei
- **Effort:** low

### Affected Files

| Datei | Aktion |
|-------|--------|
| `src/services/official_alerts/meteoalarm.py` | ändern |
| `src/output/tokens/hazard_symbols.py` | ändern |
| `src/output/renderers/alert/official_alerts.py` | ändern |
| `src/output/renderers/email/compare_html.py` | ändern |
| `tests/tdd/test_meteoalarm_source.py` | ändern |
| `tests/tdd/test_meteoalarm_feed_oesterreich.py`, `..._italien.py`, `..._deutschland.py` | ändern |
| `tests/tdd/test_sms_official_alert_tokens.py`, `test_hazard_symbols.py`, `test_telegram_official_alert_bubble.py`, `test_official_alert_hazard_labels.py` | ändern |
| `tests/tdd/test_avalanche_official_alert_channels.py` | neu |
| `tests/tdd/test_hazard_symbol_catalog_docs.py` | neu |
| `tests/fixtures/meteoalarm/feed_avalanche_type9.json` | neu |
| `docs/reference/sms_format.md` | ändern |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `sms_official_alert_tokens` (Spec) | Spec | Kuerzel-Katalog-Modell, `!`-Warn-Block, Stufenfilter >= orange (unveraendert) |
| `tokens/builder.py` `STD_SYMBOLS` | Modul | Kollisionspruefung des neuen Kuerzels (Quelle der belegten Wetter-/Baustein-Kuerzel) |
| `tokens/metrics.py` / Metrik-Katalog `sms_symbol` | Modul | zweite Quelle belegter Kuerzel (Wetter-Metriken) |
| `meteoalarm_feed._info_entries_from_alert` | Modul | JSON-Feed-Eingang (IT, AT, DE), laeuft durch dasselbe `_group_and_map_info_entries` |
| `render_official_alert_sms/_telegram`, `warn_block` | Modul | geteilte Renderer fuer Telegram, SMS, Premium-SMS, E-Mail |
| `trip_command_processor.py` (`CODES`/`KUERZEL`) | Modul | liest `HAZARD_SMS_SYMBOLS`/`HAZARD_BEDEUTUNG_*` — neues Kuerzel erscheint dort ohne Zusatzcode |
| ADR-0018 | ADR | Nicht-Kaschieren: ein verworfener Typ darf nicht stumm verschwinden |
| #1441 S1, #1473 | Folge-Issues | nutzen `avalanche` bzw. Lawinen-Stufe `AV`; daher jetzt saubere Kuerzel-Abgrenzung |

## Implementation Details

### 1. Mapper (`meteoalarm.py`)

- `_TYPE_HAZARD_MAP` erhaelt `9: "avalanche"`. Die Awareness-Stufe 1-4 bleibt unveraendert
  (`OfficialAlert.level`); die 1-5-Skala der Lawinenlage (EAWS) betrifft nicht diese Warnart,
  sondern #1441.
- Der Kommentar ueber dem Mapping wird korrigiert (Typ 9 ist gemappt).
- Bewusst verworfen: Typ 4 (Nebel) und Typ 7 (Kuesten-Ereignis). Sie stehen in einer eigenen
  Konstante `_DISCARDED_TYPES: dict[int, str]` (Typ -> Grund). Trifft ein Eintrag mit so einem
  Typ ein, schreibt `_group_and_map_info_entries` eine Debug-Zeile mit Typ, Name und Stufe.
  Auch jeder andere unbekannte Typ erhaelt eine Debug-Zeile ("unbekannter awareness_type").
  Das stumme `continue` entfaellt. Beide Eingangswege laufen durch diese eine Stelle, es
  genuegt eine Aenderung.

### 2. Kuerzel-Entscheidung: `AW`

Katalogeintrag `avalanche` -> `AW` (Avalanche Warning), eingefuegt direkt nach `snow` (Sortier-
Reihenfolge bei gleicher Warnstufe: ... `snow`, `avalanche`, `black_ice` ...).

Kollisionspruefung gegen alle belegten Kuerzel:

| Kandidat | Befund |
|----------|--------|
| `AV` | **belegt**: Lawinen-Stufe (`builder.py` `POSITIONAL`/`PRIORITY`, `sms_format.md`, Wintersport-Token #1473). Ausgeschlossen. Auch der Fallback `sms_symbol_for("avalanche")` wuerde `AV` liefern — das verhindert der Katalogeintrag, ein Test sichert es ab. |
| `AW` | frei: weder in `STD_SYMBOLS` (N L D FN FL FD TF R PR W G TH TH+ HU DP WD: CP PT: CT CL CM CH VS SU UV HP FZ HR: Z: MAX M: SD NS24+ SL AV X? DBG) noch in den Warn-Kuerzeln (TS FO RA WG SN IC HT CD FR AB) noch als Reserve `X`/`XX`. |
| `LW` | frei, aber vom deutschen Wort abgeleitet; die Katalog-Vorgabe lautet "international verstaendlich" (alle anderen Warn-Kuerzel sind englisch abgeleitet). |
| `AL` | frei, aber im Wintersport-Umfeld missverstaendlich (Alpine/Altitude) und nicht als Warnung lesbar. |

Entscheidung `AW`, weil frei, englisch abgeleitet wie alle uebrigen Warn-Kuerzel und gleichzeitig
sofort als zur Lawine gehoerig erkennbar. Das Restrisiko der Aehnlichkeit mit `AV` ist
mechanisch entschaerft: die Warnung steht nur im `!`-Block und traegt Doppelpunkt plus
Stufenbuchstabe (`!AW:M`), die Lawinen-Stufe ist ein Zahlen-Token ohne `!` (`AV3`). Im
Telegram-/Mail-Text steht das Klartext-Label, das Kuerzel gibt es nur in SMS-artigen Kanaelen.
Bedeutung (EN/DE) wird an der einen Stelle gepflegt: `HAZARD_BEDEUTUNG_EN["avalanche"] = "avalanche"`,
`HAZARD_BEDEUTUNG_DE["avalanche"] = "Lawine"`.

### 3. Anzeige

- `_HAZARD_LABELS["avalanche"] = "Lawine"`. Pflicht gleichzeitig mit dem Katalogeintrag:
  `_HAZARD_DISPLAY` indiziert `HAZARD_SMS_SYMBOLS[hazard]` fuer jedes Label — ein Label ohne
  Katalogeintrag (oder umgekehrt) bricht beim Import.
- `compare_html._warn_short()`: eigener Zweig `avalanche` -> Text "Lawine", Severity aus der
  Stufe (2 caution, 3 warn, 4 danger) wie bei `flood`. Ohne den Zweig erschiene im
  Ortsvergleichs-Chip der Rohtext der Quelle (`alert.label`).
- Trip-Briefing-E-Mail, Telegram, SMS-Token-Zeile und Premium-SMS beziehen Label und Kuerzel
  ausschliesslich aus den beiden Katalogen oben; sie brauchen keinen eigenen Zweig.

### 4. Doku

`docs/reference/sms_format.md` §3.4c (Tabelle der Warn-Kuerzel) um `avalanche | AW | Lawine`
ergaenzen; Hinweis, dass `AW` (Warnung, im `!`-Block) und `AV` (Lawinen-Stufe, Wintersport-
Token) verschiedene Dinge sind. Zaehlt nicht ins LoC-Limit.

## Expected Behavior

- **Input:** MeteoAlarm-Warnung mit `awareness_type` "9; avalanche", Stufe 2-4 (CAP-XML oder
  JSON-Feed); daneben Warnungen der Typen 4 und 7.
- **Output:** `OfficialAlert(hazard="avalanche", level=<Awareness-Stufe>)`. Lawinenwarnung erscheint in
  E-Mail (Warn-Kasten und Ortsvergleichs-Chip), Telegram, SMS (`!AW:<Stufe>`) und Premium-SMS
  nach den bestehenden Regeln (Stufenfilter >= orange fuer SMS/Telegram). Typen 4 und 7
  liefern weiterhin keine Warnung, hinterlassen aber eine Debug-Zeile.
- **Side effects:** keine Persistenz-Aenderung; nur Log-Ausgabe.

## Acceptance Criteria

- **AC-1:** Given die aufgezeichnete MeteoAlarm-CAP-Datei mit einer Lawinenwarnung (Typ 9,
  Stufe 3 orange, GeoSphere Oesterreich) und einer Hitzewarnung / When die Datei ueber den
  CAP-Weg eingelesen wird / Then entsteht eine amtliche Warnung der Gefahrenart `avalanche` mit
  Stufe 3 (zusaetzlich zur Hitzewarnung), und die Stufe wird nicht auf eine andere Skala
  umgerechnet.
  - Test: `tests/tdd/test_meteoalarm_source.py` — Fixture `cap_avalanche_plus_heat.xml`
    durch die echte Eingangsfunktion; Assertion auf `hazard == "avalanche"`, `level == 3`,
    zwei Warnungen insgesamt.

- **AC-2:** Given ein Eintrag im JSON-Feed (Oesterreich, Italien und Deutschland) mit
  Lawinenwarnung Typ 9 / When der Feed ueber den Sammelweg `meteoalarm_feed` verarbeitet wird /
  Then liefert der Sammelweg dieselbe Warnung der Gefahrenart `avalanche` mit der
  Awareness-Stufe des Eintrags, nicht nur der CAP-Weg.
  - Test: `tests/tdd/test_meteoalarm_feed_oesterreich.py`, `..._italien.py`,
    `..._deutschland.py` (je ein Fall) mit neuem Feed-Fixture
    `tests/fixtures/meteoalarm/feed_avalanche_type9.json`, abgeleitet aus einer
    aufgezeichneten Feed-Antwort (Typ-Feld auf "9; avalanche" gesetzt, im Fixture-Kopf
    als abgeleitet gekennzeichnet — Vorbild `cap_flooding_type12_ro.json`).

- **AC-3:** Given Warnungen der Typen Nebel (4) und Kueste (7) sowie ein voellig unbekannter
  Typ in einer MeteoAlarm-Antwort / When die Antwort verarbeitet wird / Then entsteht fuer keinen
  dieser Typen eine Warnung, aber das Log enthaelt je eine Debug-Zeile mit Typnummer und Stufe
  (Nebel und Kueste mit dem Vermerk "bewusst nicht unterstuetzt"); die uebrigen Warnungen der
  Antwort bleiben unberuehrt.
  - Test: `tests/tdd/test_meteoalarm_source.py` — `caplog` auf Debug-Ebene, Eintraege der
    Typen 4, 7 und 99 neben einer Typ-9-Warnung; Assertion auf die Log-Zeilen und darauf, dass
    genau die Typ-9-Warnung uebrig bleibt.

- **AC-4:** Given eine Lawinenwarnung der Stufe orange fuer den Tag eines Trips / When die
  Trip-Briefing-SMS erzeugt wird / Then steht im Warn-Block `!AW:M`, und das Kuerzel `AW`
  unterscheidet sich von allen anderen belegten Kuerzeln — insbesondere vom Lawinen-Stufen-Token
  `AV`, der unveraendert weiter fuer die Lawinenstufe steht.
  - Test: `tests/tdd/test_sms_official_alert_tokens.py` — Fixture (AC-1) -> Alert -> `SMSTripFormatter().format_sms`;
    Assertion `"!AW:M"` in SMS; zusaetzlich `tests/tdd/test_hazard_symbols.py`: `HAZARD_SMS_SYMBOLS["avalanche"] == "AW"`,
    `"AW"` nicht in den Wetter-Kuerzeln (`STD_SYMBOLS`, Metrik-Katalog), nicht doppelt im Warn-Katalog,
    `sms_symbol_for("avalanche") != "AV"`.

- **AC-5:** Given eine Lawinenwarnung (Quelle: Fixture aus AC-1) / When die eigenstaendige
  Warn-SMS (Standalone) und die Premium-SMS (Garmin inReach) fuer diese Warnung erzeugt werden /
  Then enthalten beide das Kuerzel `AW` und die Stufe, und beide Nachrichten liegen jeweils
  im Laengenbudget ihres Kanals.
  - Test: neue Datei `tests/tdd/test_avalanche_official_alert_channels.py` — Fixture ->
    `OfficialAlert` -> `render_official_alert_sms`; Premium-SMS ueber denselben Pfad wie
    `notification_service` (Aufruf der Premium-Text-Funktion mit dem Alert), Assertion auf
    `AW` und `len(...)` je Kanal-Limit. Gleiche Datei: Anti-Divergenz — Trip-SMS und
    Standalone-SMS liefern fuer `avalanche` dasselbe Kuerzel.

- **AC-6:** Given eine Lawinenwarnung der Stufe orange oder rot / When der Telegram-Bericht fuer
  den Trip und der Telegram-Alarm erzeugt werden / Then steht im Text die Bezeichnung "Lawine"
  samt Stufe, nicht der Rohtext der Quelle und nicht ein leerer Warnblock.
  - Test: `tests/tdd/test_avalanche_official_alert_channels.py` und
    `tests/tdd/test_telegram_official_alert_bubble.py` — Fixture -> `OfficialAlert` ->
    `render_official_alert_telegram`; Assertion auf "Lawine" und Stufentext; Stufe gelb (2)
    erzeugt keine Warn-Bubble (bestehender Filter).

- **AC-7:** Given eine Lawinenwarnung / When die Trip-Briefing-E-Mail (Warn-Kasten) und die
  Ortsvergleichs-E-Mail (Warn-Chip) erzeugt werden / Then zeigen beide die Bezeichnung "Lawine"
  mit der Schwere passend zur Stufe (Stufe 2 Hinweis, 3 Warnung, 4 Gefahr); der Rohtext der
  Quelle erscheint nicht als Chip-Text.
  - Test: `tests/tdd/test_avalanche_official_alert_channels.py` und
    `tests/tdd/test_official_alert_hazard_labels.py` — `_HAZARD_LABELS["avalanche"] == "Lawine"`,
    `_warn_short(alert)` fuer Stufe 2/3/4, `render_warn_block` enthaelt "Lawine".

- **AC-8:** Given Warnungen mehrerer Gefahrenarten mit gleicher Stufe (Schnee und Lawine) /
  When die Warnungen sortiert in die SMS geschrieben werden / Then steht die Lawine unmittelbar
  nach Schnee und vor Glatteis, die Reihenfolge ist bei jedem Lauf gleich.
  - Test: `tests/tdd/test_hazard_symbols.py` — `HAZARD_ORDER["avalanche"] == HAZARD_ORDER["snow"] + 1`;
    SMS mit zwei Warnungen gleicher Stufe zeigt `SN` vor `AW`.

- **AC-9:** Given Nutzer A mit Trip in einer Region mit Lawinenwarnung und Nutzer B mit Trip in
  einer Region ohne Warnung / When fuer beide die Trip-Briefing-SMS erzeugt wird / Then enthaelt
  nur die SMS von Nutzer A `AW`, die von Nutzer B bleibt unveraendert ohne Warn-Block.
  - Test: `tests/tdd/test_avalanche_official_alert_channels.py` — zwei getrennte Trips/Segmentlisten,
    nacheinander durch `format_sms()`; kein neuer Endpoint, daher kein HTTP-Zwei-Nutzer-Test.

- **AC-10:** Given die Befehle `CODES` und `KUERZEL` per Nachricht / When ein Nutzer sie abruft /
  Then steht `AW` mit der Bedeutung "Lawine" (deutsch) bzw. "avalanche" (englisch) in der Antwort,
  und `AV` steht weiterhin getrennt als "Lawinenstufe".
  - Test: `tests/tdd/test_hazard_symbols.py` — `HAZARD_BEDEUTUNG_DE/EN["avalanche"]` gesetzt;
    Aufruf der Antwort-Erzeugung aus `trip_command_processor` (Weg wie bestehender
    Kuerzel-Test), Assertion beider Eintraege.

- **AC-11 (doc-compliance-test):** Given die aktualisierte `docs/reference/sms_format.md` /
  When die Warn-Kuerzel-Tabelle gelesen wird / Then enthaelt sie `avalanche | AW | Lawine` und
  die Abgrenzung zu `AV`.
  - Test: `# doc-compliance-test` in `tests/tdd/test_hazard_symbol_catalog_docs.py` —
    ausdruecklich Dokukonformitaet, kein Verhaltensnachweis.

## Test Plan

| AC | Testdatei | Art |
|----|-----------|-----|
| AC-1 | `test_meteoalarm_source.py` | Verhalten, aufgezeichnete Fixture |
| AC-2 | `test_meteoalarm_feed_{oesterreich,italien,deutschland}.py` | Verhalten, abgeleitete Feed-Fixture |
| AC-3 | `test_meteoalarm_source.py` | Verhalten (`caplog`) |
| AC-4 | `test_sms_official_alert_tokens.py`, `test_hazard_symbols.py` | Verhalten + Kollisionstest |
| AC-5 | `test_avalanche_official_alert_channels.py` | Verhalten (Standalone-SMS, Premium-SMS) |
| AC-6 | `test_avalanche_official_alert_channels.py`, `test_telegram_official_alert_bubble.py` | Verhalten |
| AC-7 | `test_avalanche_official_alert_channels.py`, `test_official_alert_hazard_labels.py` | Verhalten |
| AC-8 | `test_hazard_symbols.py` | Verhalten (Sortierung) |
| AC-9 | `test_avalanche_official_alert_channels.py` | Verhalten, zwei Nutzer |
| AC-10 | `test_hazard_symbols.py` | Verhalten (`CODES`/`KUERZEL`) |
| AC-11 | `test_hazard_symbol_catalog_docs.py` | `# doc-compliance-test` |

Alle Tests laufen im Kern (ohne Netz), mit aufgezeichneter bzw. abgeleiteter Fixture.

## Known Limitations

- Die Lawinen-Stufe 1-5 (EAWS, Lawinenlagebericht) bleibt Gegenstand von #1441/#1473. Diese
  Spec transportiert nur die MeteoAlarm-Awareness-Stufe 1-4 der Warnung.
- Nebel (4) und Kueste (7) sind weiterhin keine Gefahrenart der App; sie werden nur
  protokolliert (Debug), nicht angezeigt.
- Der Feed-Fixture fuer AC-2 ist abgeleitet (Typ-Feld ersetzt), keine reine Aufzeichnung; die
  Aufzeichnungstreue gilt fuer den CAP-Fixture aus AC-1.
- `AW` und `AV` unterscheiden sich in einem Buchstaben; die Trennung beruht auf `!`-Block,
  Doppelpunkt und Stufenform, nicht auf der Buchstabenwahl.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** additive Erweiterung des bestehenden Katalogs (ADR-0011: ein geteilter
  Renderer; ADR-0018: Verwerfen wird sichtbar), keine neue Entscheidungsflaeche.

## Changelog

- 2026-10-12: Initial spec created (Issue #1430, Epic #2258)
