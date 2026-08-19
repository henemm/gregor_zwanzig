---
entity_id: fix_1948_s3_sms_sofortfix
type: bugfix
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [alarm, sms, format]
---

# SMS-Sofortfix Δ-Alarm (Zweig a) — #1948 Scheibe S3

> **Ersetzt vollständig:** `docs/specs/modules/fix_1948_1939_alarm_sms_referenzzeitpunkt.md`
> (laut Konzept v3 `docs/analysis/alarm-format-konzept-2026-08.md` §8 obsolet —
> „entfernen statt umformulieren"). Deren Notations-ACs (`@HH:MM`-Umformulierung
> im Kopf) sind durch diese Spec vollständig überholt; die alte Spec-Datei ist
> im Repo nicht mehr vorhanden.

## Approval

- [ ] Approved

## Purpose

Die Δ-Alarm-SMS (Zweig a) verliert den redundanten Vergleichszeitpunkt-Präfix
`@HH:MM` im Kopf (behebt den #1948-Auslöser-Bug UND macht #1939 strukturell
unmöglich), wechselt die Von-Bis-Notation von `>` (liest sich als „größer
als") auf `->` ohne Vorzeichen-Präfix, und rendert Gewitter-Stufen (`thunder`)
künftig als Buchstaben (`M->H`) statt als Rohzahlen (`2->3`) — dieselbe
`LEVELS`-Leiter, die das Trip-Briefing bereits produktiv nutzt. Ziel: EIN
Alarm-Format, das der Empfänger aus dem täglichen Briefing bereits kennt
(PO-Leitsatz „Format folgt dem Phänomen, nicht der Quelle", Konzept §0).

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `render_sms()` (Kopf-Zweig, Z.793-794), `_sms_token()` (Z.707-715)

## Estimated Scope

- **LoC:** ~60-90 (Renderer-Logik + neues Katalog-Feld + Testanpassungen)
- **Files:** 3 Quelldateien + 3 Bestandstestdateien angepasst + mind. 1 neue Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertEvent` | dataclass (`src/output/renderers/alert/model.py:12`) | Liefert `value_from`/`value_to`/`occurred_at`/`metric_id` — Grundlage jedes Δ-Tokens |
| `get_sms_code()` | function (`src/app/metric_catalog.py:1213`) | Liefert das Metrik-Kürzel (`TH`, `VS`, ...) für `_code()` |
| `LEVELS` | dict (`src/output/tokens/metrics.py:14`) | Bestehende Stufenbuchstaben-Map `{0:"-",1:"L",2:"M",3:"H"}`, bislang nur vom Briefing-Builder genutzt |
| `MetricDefinition` | dataclass (`src/app/metric_catalog.py:28-91`) | Trägt das neue additive Feld `is_level`; Katalog-Eintrag `thunder` (Z.413-431) bekommt `is_level=True` |
| Premium-SMS-Renderer | — | Nutzt denselben `render_sms()` wie Standard-SMS (kein eigener Renderer) — erbt die Änderung automatisch |
| Dedupe-Schlüssel (#1954) | — | Basiert auf Events, nicht auf gerendertem Text — von dieser Scheibe unberührt |

## Implementation Details

**1. Kopf-Präfix entfernen (`render_sms`, Z.788-794).** Der Block

```
if msg.reference_at:
    head += f"@{msg.reference_at} "
```

entfällt ersatzlos, für ALLE Kopf-Zweige (Ein-Ort, Mehr-Orte-Bündel, Trip-Δ,
kopfloser Compare-Pfad). `AlertMessage.reference_at` bleibt als DTO-Feld
bestehen — nur `render_sms()` liest es nicht mehr. `render_email()` (Z.547,
602 „verglichen mit HH:MM") bleibt unverändert; Telegram nutzt das Feld
schon heute nicht (S6-Frage, hier tabu).

**2. `->`-Notation ohne Vorzeichen im Trip-Δ-Pfad (`_sms_token`, Z.707-711).**
Nur der Zweig `location_positions is None` (Trip-Δ) ändert sich:

- Vorzeichen-Präfix `{sign}` entfällt vollständig.
- Trennzeichen wechselt von `>` auf `->` (ASCII, zwei GSM-7-Basis-Zeichen).
- Beispiel numerisch: `-VS1400>280` (alt) → `VS1400->280` (neu).

Der Compare-Änderungspfad (`location_positions` gesetzt) bleibt **byte-
identisch** inklusive Vorzeichen-Präfix und `>`-Notation (`{sign}{code}{bis}`,
Invariante #1467 AC-9) — dort ändert sich ausschließlich der Wegfall des
`@HH:MM`-Kopf-Präfix aus Schritt 1 (das ist der #1939-Fix).

**3. Stufenbuchstaben für `is_level`-Metriken.** Neues additives Feld
`is_level: bool = False` an `MetricDefinition` (`src/app/metric_catalog.py`).
Nur der `thunder`-Eintrag bekommt `is_level=True`; alle anderen Metriken
bleiben beim Default `False` (insbesondere `cape` und andere
`default_format_mode="symbol"`-Metriken — dieses Feld ist als Trigger
untauglich, da es auch nicht-stufige Größen trägt). `_sms_token()` fragt den
Katalog für `e.metric_id` ab: ist `is_level=True`, werden `value_from`/
`value_to` über die bestehende `LEVELS`-Map (`output/tokens/metrics.py:14`,
`{0:"-",1:"L",2:"M",3:"H"}`) in Buchstaben übersetzt statt als Zahl
formatiert, UND der Code-Teil bekommt einen Doppelpunkt-Suffix (`TH:` statt
`TH`, analog `FORECAST_TH="TH:"` im Briefing-Builder,
`src/output/tokens/builder.py:18`). Numerische Metriken (kein `is_level`)
bleiben ohne Doppelpunkt. Die Stufenbuchstaben-Übersetzung gilt NUR im
Trip-Δ-Pfad (Schritt 2) — der Compare-Pfad bleibt unverändert (Invariante).

**4. Unverändert (explizite Nicht-Ziele dieser Scheibe).** `_render_sms_onset`
(Zweig c, Onset-Token `TH!{minuten}`), `_sms_corridor_token` (reiner
Schwellen-Alarm, `!{code}{wert}`), `official_alerts.py` (Zweig b, amtliche
Warnungen) — alle drei sind spätere Scheiben (S4/S5).

## Expected Behavior

- **Input:** `AlertMessage` mit `reference_at` gesetzt und mind. einem
  `AlertEvent` im Trip-Δ-Pfad (`location_positions=None`), inkl. Gewitter-
  Events (`metric_id="thunder"`) und numerischen Events (z.B. `visibility`).
- **Output:** `render_sms()` liefert einen String ohne `@HH:MM`-Kopf-Präfix;
  numerische Δ-Token im Format `{code}{von}->{bis}[@{stunde}]` ohne
  Vorzeichen; Gewitter-Δ-Token im Format `{code}:{buchstabe_von}->{buchstabe_bis}[@{stunde}]`.
  Compare-Pfad-Token (`location_positions` gesetzt) bleiben byte-identisch
  zum Vor-S3-Zustand, nur ohne den `@HH:MM`-Kopf-Präfix.
- **Side effects:** keine — reine Renderer-Formatierung, kein Datenmodell-
  Wandel, keine Persistenz betroffen.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Δ-Alarm mit `AlertMessage.reference_at="18:03"` und
  einem Sicht-Ereignis (Segment „Ziel", 1400→280m) / When `render_sms(msg)`
  gerendert wird / Then enthält der resultierende Text an keiner Stelle
  `@18:03` — der Kopf endet direkt mit `"Ziel: "`, gefolgt vom Token.
  - Test: `render_sms()` mit gesetztem `reference_at` aufrufen, Ergebnis-
    String auf Abwesenheit von `msg.reference_at` prüfen (kein
    Dateiinhalt-Check — echter DTO-Aufruf durch den echten Renderer).

- **AC-2:** Given denselben Fall wie AC-1 / When gerendert / Then lautet das
  Ereignis-Token exakt `VS1400->280@14` — kein führendes `+`/`-`, ASCII `->`
  statt `>`.
  - Test: Token per Regex/Substring aus dem gerenderten String extrahieren
    und auf exakten Wert `VS1400->280@14` prüfen.

- **AC-3:** Given ein Trip-Δ-Alarm mit einem Gewitter-Ereignis
  (`metric_id="thunder"`, `value_from=2.0`, `value_to=3.0`,
  `occurred_at="16"`) / When gerendert / Then lautet das Token exakt
  `TH:M->H@16` — Doppelpunkt nach `TH`, Stufenbuchstaben `M`/`H` statt der
  Rohzahlen `2`/`3`.
  - Test: gerenderten String auf exakten Substring `TH:M->H@16` prüfen.

- **AC-4:** Given ein Ortsvergleich-Änderungspfad-Ereignis mit gesetztem
  `location_positions` (z.B. Regen 2→45mm, Position 2) / When gerendert /
  Then lautet das Token weiterhin `2:+R45` — Vorzeichen-Präfix UND `>`-freie
  Bis-Wert-Notation bleiben exakt wie vor S3 (Invariante #1467 AC-9); die
  `->`-Notation und Stufenbuchstaben aus AC-2/AC-3 gelten NICHT für diesen
  Pfad.
  - Test: `render_sms(msg, location_positions={...})` aufrufen, Ergebnis
    gegen den vor-S3 gemessenen Goldstring vergleichen (Regressionstest,
    Vorbild `test_alert_sms_location_positions.py`).

- **AC-5:** Given einen Ortsvergleich-Änderungsalarm über den echten
  Aufrufpfad (`CompareAlertService.check_all_compare_presets()`), bei dem
  intern `reference_at` gesetzt wird / When die SMS an der Senke ankommt /
  Then bleibt der Kopf weiterhin vollständig leer (kein Ortsname, kein
  Vergleichsname, Regressionsschutz K-1 bis K-4) UND enthält keinen
  `@HH:MM`-Zeitstempel — das ist der strukturelle #1939-Fix.
  - Test: `test_alert_sms_location_positions.py` K1-K4 (bereits vorhanden,
    `live`-markiert) laufen ohne inhaltliche Änderung grün, sobald der
    Kopf-Präfix aus Schritt 1 der Implementation Details entfernt ist.

- **AC-6:** Given denselben Trip-Δ-Alarm wie AC-1 / When `render_email(msg)`
  gerendert wird / Then enthält der Mail-Text weiterhin den Referenz-
  Zeitpunkt-Footer („verglichen mit ...HH:MM", `render.py:547/602`)
  unverändert zum Vor-S3-Zustand.
  - Test: `render_email()` direkt aufrufen, Footer-Text auf Anwesenheit der
    Referenzzeit prüfen (Regressionsschutz, kein Dateiinhalt-Check).

- **AC-7:** Given ein Onset-Ereignis (Zweig c, `OnsetEvent` mit
  `location_label=None`) / When `render_sms()` über `_render_sms_onset`
  rendert / Then bleibt das Token-Format (`{code}!{minuten}`, z.B. `TH!8`)
  byte-identisch zum Vor-S3-Zustand — S3 rührt `_render_sms_onset` nicht an.
  - Test: bestehende Onset-Regressionstests (z.B.
    `test_regression_trip_radar_alert_sms_text_unchanged`) bleiben grün ohne
    Anpassung.

- **AC-8:** Given einen reinen Schwellen-Alarm (Corridor-Event, kein
  Δ-Vergleich) / When `render_sms()` über `_render_sms_corridor_only`
  rendert / Then bleibt das Corridor-Token-Format (`!{code}{wert}`, z.B.
  `!G55`) byte-identisch zum Vor-S3-Zustand.
  - Test: bestehender Corridor-Regressionstest bleibt grün ohne Anpassung.

- **AC-9:** Given eine amtliche Warnung (Zweig b, `official_alerts.py`) /
  When ihre SMS gerendert wird / Then bleiben Kopf, Stufennotation
  (`GELB1/3` etc.) und Trip-Präfix (`KHW403`) unverändert zum Vor-S3-Zustand
  — Zweig b ist S5-Scope, hier nicht angefasst.
  - Test: bestehende `official_alerts.py`-Tests bleiben grün ohne Anpassung.

## Offene Entscheidungsfrage (NEU — PO-Entscheid ausstehend, NICHT Teil dieser Scheibe)

**Führende Null im Stunden-Suffix.** `_sms_token()` baut den Zeitsuffix
heute über `@{e.occurred_at[:2]}`, was bei einstelligen Stunden eine
führende Null erzeugt (`@09`). Die Briefing-Notation (`sms_format.md:52`,
Konzept-Regel 5) verzichtet auf die führende Null (`@9`). Da die
Zielbild-Beispiele dieser Scheibe (`@16`, `@14`) beide zweistellig sind,
entscheidet keines der ACs oben diese Frage — **S3 lässt das bestehende
`occurred_at[:2]`-Verhalten (mit führender Null) unverändert.** Empfehlung
für eine Folge-Scheibe: angleichen (ohne führende Null), da Regel 5
verlangt, dass dieselbe `@`-Notation identisch in Briefing- UND Alarm-SMS
gilt. Wird hier ausdrücklich NICHT vorentschieden.

## Known Limitations

- Zweig c (Nowcast) und Zweig b (amtlich) bleiben im heutigen Format —
  Folgescheiben S4/S5.
- Der Compare-Änderungspfad bekommt keine Stufenbuchstaben und keine
  `->`-Notation — Ortsvergleich ist laut Konzept durchgehend zurückgestellt.
- Die führende-Null-Frage (s.o.) bleibt offen und wird nicht in dieser
  Scheibe entschieden.
- Telegram-Parität (S6) ist eine Folgefrage, die erst durch diese Scheibe
  entsteht (Telegram zeigte `reference_at` bisher gar nicht, E-Mail zeigt
  ihn weiterhin — ob Telegram künftig dem neuen SMS-Verhalten folgt, ist
  offen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Renderer-Formatänderung innerhalb eines bereits
  bestehenden, PO-freigegebenen Konzepts (`docs/analysis/alarm-format-konzept-2026-08.md`,
  PO-Runde 4). Kein neues Datenmodell, keine neue Architekturentscheidungs-
  fläche (kein neuer Kanal, kein neuer Provider, keine Persistenz-Änderung).

## Changelog

- 2026-08-19: Initial spec created (S3 des Alarm-Format-Konzepts #1948, löst
  #1939 strukturell mit).
