---
entity_id: fix_1935_1779_alarm_nachricht_klarheit
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: draft
workflow: fix-1935-1779-alarm-nachricht-klarheit
---

# Alarm-Nachricht klar formulieren: Änderungsbetrag statt Messwert, Ortsbezug statt Kilometerspanne (#1935, #1779)

> **Teilweise überholt durch `docs/specs/modules/fix_1948_s3_sms_sofortfix.md`
> (#1948 Scheibe S3):** Die hier dokumentierten SMS-Token-Beispiele mit
> Vorzeichen-Präfix und `>`-Notation (`-VS1400>280`) gelten seit S3 nur noch
> für den Ortsvergleich-Änderungspfad. Der Trip-Δ-Pfad (dieselben Beispiele
> hier) schreibt seither `VS1400->280` ohne Vorzeichen. Diese Datei bleibt als
> historischer Nachweis für Ortsbezug/Änderungsbetrag (#1935/#1779) unverändert
> — nur die Notation ist an der genannten Stelle abgelöst.

## Approval

- [ ] Approved

## Purpose

Der Abweichungs-Alarm ist auf zwei Wegen unnötig schwer lesbar, beide vom PO gemeldet
(#1779 und fünf Tage später erneut, konkreter, als #1935): (1) Die E-Mail-Datenzeile
`Alarm-Schwelle 1.000 m: jetzt darüber ✗` behauptet fälschlich etwas über den **Messwert**
(280 m), obwohl `threshold` per ADR-0013 immer eine **Δ-Auslöseschwelle** ist — der
Verdict-Chip eine Zeile höher sagt es bereits richtig, wodurch dieselbe Mail sich selbst
widerspricht. (2) Die Alarm-SMS nennt den Ort als nutzlose Kilometerspanne
(`km12-12`) statt der Etappen-/Zielsprache, die E-Mail und Betreff längst sprechen, und
führt den Trip-Namen mit, obwohl der auf einer Kurznachricht an den Trip-Teilnehmer
selbst keine Information trägt. Diese Spec macht in beiden Fällen sichtbar, WAS sich
geändert hat und WO — ohne die zugrundeliegende Δ-Semantik (#958/ADR-0013) anzurühren.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_datablock_single` (E-Mail-Einzelereignis-Datenzeile), `render_email`
  (Multi-Event-Zweig, Zeilen ~552-559), `render_subject` (Multi-Event-Top-3),
  `render_telegram` (Multi-Event-Zeile), `render_sms`, `_sms_token`,
  `_render_sms_onset`, `_render_sms_corridor_only`, `_ascii`

Schicht: **Python-Core** (Renderer). Keine Go-Änderung, keine Frontend-Änderung.

## Estimated Scope

- **LoC:** ca. +60/-30 in `render.py`; Test-LoC deutlich höher (6 Bestandsdateien
  angepasst + 1 neue Verhaltens-Testdatei) — zählt gegen das separate 500er-Test-Budget
  (CLAUDE.md), nicht gegen die 250 Prod-LoC. `loc_limit_override` einplanen.
- **Files:** 1 Produktivdatei, 6 Bestands-Testdateien, 1 neue Testdatei
- **Effort:** medium — Wortlaut ist breit gebunden (Golden-Tests), aber kein Gate und
  kein Frontend hängt am Text; klar abgegrenzter Renderer, ADR-0011 (ein Backend-Renderer
  für alle vier Kanäle) macht die Änderung an einer Stelle für alle Kanäle wirksam.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.model.over_thr` / `side_label` / `delta_pct` | Funktion | #958-Kernsemantik (ADR-0013) — bleibt UNVERÄNDERT, nur der Text um ihre Rückgabewerte ändert sich |
| `output.renderers.alert.segments.format_alert_location` / `_km_str` | Funktion | bestehende, gemeinsame Ortssprache (#1744 AC-3) — wird für die SMS-Kopfzeile erstmals genutzt, nicht verändert |
| `app.metric_catalog.get_sms_code` / `get_metric` | Funktion | Kürzel (`VS`, `G`, …) und Einheit für Token bzw. Betreff/Telegram-Einheitensuffix |
| `utils.ascii_fold.fold_ascii` | Funktion | ASCII/GSM-7-Faltung der SMS — MUSS für Alarm-Ortstexte um eine Emoji-Entfernung ERGÄNZT werden (AC-7), sonst entsteht `:checkered_flag:` |
| `docs/adr/0013-alert-threshold-ist-delta-sensitivitaet.md` | ADR | bleibt inhaltlich bindend — nur der Textträger ändert sich |
| `docs/specs/modules/fix_1744_alarm_format_angleichen.md` AC-5 | Spec | **wird durch diese Spec abgelöst** (s. u.) |
| `docs/specs/modules/fix_1861_1865_alarm_mail_klarheit.md` | Spec | Vorgänger-Fix derselben Zeile — Ausgangspunkt (`Alarm-Schwelle N: jetzt darüber ✗`) |

## Implementation Details

### E1 — E-Mail-Einzelereignis-Datenzeile: Änderungsbetrag statt Messwert

`_datablock_single()`s zweite Zeile (`render.py:403-428`) zeigt heute Label
`Alarm-Schwelle {threshold}` und Wert `jetzt {über|unter} {✓|✗}`. Beides zeigt auf den
Messwert (Einheit am Schwellwert, Zeitwort „jetzt"), obwohl die dahinterstehende Tatsache
`abs(value_to - value_from) >= threshold` eine Aussage über die **Änderung** ist. Neu:
Label nennt den tatsächlichen Änderungsbetrag, Wert stellt ihn der Schwelle gegenüber:

```
row2 = (
    f"Änderung {_val(e, abs(e.value_to - e.value_from))}",
    f"{side_label(e)} Alarm-Schwelle {_val(e, e.threshold)} {mark}",
)
```

`over_thr()`/`side_label()`/`mark` bleiben unverändert — nur der gebaute Satz ändert sich.
`_SIDE_ADVERB` (`über`→`darüber`) entfällt ersatzlos, weil „jetzt" (das Zeitwort, das auf
den Messwert zeigte) nicht mehr vorkommt. Ergebnis am Fall aus #1935:
`Änderung 1.120 m: über Alarm-Schwelle 1.000 m ✗` (bzw. `Änderung 100 m: unter
Alarm-Schwelle 1.000 m ✓`) — deckungsgleich mit dem Verdict-Chip eine Zeile höher
(`_verdict_single`, unverändert: `Änderung über deiner Alarm-Schwelle (1.000 m)`).

### E2 — E-Mail-Mehrereignis-Zweig: Änderungsbetrag zusätzlich zur Schwelle

Die über-Schwelle-Zeile im Multi-Event-Zweig (`render_email:552-559`) nennt heute nur die
Schwelle, nicht den Änderungsbetrag — dieselbe Ambiguität wie E1, nur im gebündelten Fall.
Label wird um `Änderung {Δ}` ergänzt (vor `Schwelle`, analog zur Reihenfolge in E1):

```
delta_suffix = " %" if unit == "%" else ""
label = f"{loc_prefix}{_label(e)}{where_when} · Änderung {_num(e, e.threshold and abs(e.value_to - e.value_from))}{delta_suffix} · Schwelle {_num(e, e.threshold)}{threshold_suffix}"
```

Am Fixture aus `test_978_deviation_line_readability.py` (Böen 20→80, Schwelle 40, Δ=60):
neues Label `Böen · Änderung 60 · Schwelle 40` statt bisher `Böen · Schwelle 40`. Die
gedämpfte Unter-Schwelle-Zeile (`render_email:560-567`, Issue #980) nennt schon heute
keine Zahl und bleibt unverändert — sie hat den Root-Cause-Bug nicht. Telegram-Multi-Zeile
(`render_telegram:643-648`) nennt „Schwelle" bewusst gar nicht (steht in der fetten
Kopfzeile, `test_metric_line_has_no_schwelle_word`) — bleibt unverändert, dort besteht
keine Ambiguität.

### E5 — Einheiten in Betreff und Telegram nachziehen

`render_subject`s Top-3-Auswahl (`:358-361`) und `render_telegram`s Multi-Zeile
(`:643-648`) hängen die Einheit heute nur bei `%` an (`Böen 80` statt `Böen 80 km/h`),
während der E-Mail-Zweig sie immer anhängt. Beide Stellen werden auf „immer mit Einheit"
umgestellt — dieselbe Regel wie in `_val()`/E-Mail bereits gilt.

### E3/E4 — Alarm-SMS: Ortsbezug statt km-Spanne, Von-Wert im Token, kein Trip-Name

Betrifft ausschließlich den **Trip-Δ-Pfad** von `render_sms()` (den `else`-Zweig ohne
`location_positions`, ohne `multi_location`, ohne `msg.location_label` — der einzige
Zweig, der heute `{trip} km{a}-{b}: ` baut) sowie — nur für den Trip-Namen, NICHT für die
Ortsauflösung — `_render_sms_onset`. `_render_sms_corridor_only` ist seit `8f2053f9`
(#1460 P1a) toter Code (unerreichbar in Produktion) und trägt in dieser Spec **keine**
Verhaltenszusicherung — s. „Known Limitations".

**Kopf (nur Trip-Δ-Pfad):** statt `{trip} km{a}-{b}: ` die gemeinsame Ortsauflösung
`_km_str(msg)` (dieselbe Funktion, die Betreff/E-Mail/Telegram schon nutzen), Emoji vorher
entfernt (nicht transliteriert, s. AC-7), kein Trip-Name mehr:

```
loc = _ascii_alert_location(_km_str(msg))   # neuer Schritt: Emoji-Entfernung vor fold_ascii
head = f"{loc}: "
```

**Token (nur Trip-Δ-Pfad, `_sms_token()` NUR wenn `location_positions is None`):** statt
`{sign}{code}{value_to}` neu `{sign}{code}{value_from}>{value_to}` — der Von-Wert macht
den Ausschlag lesbar, ohne dass der Empfänger den letzten Mailstand kennen muss. Der
Ortsvergleich-Zweig (`location_positions` gesetzt) behält sein heutiges Token
byte-identisch (Regressions-Invariante, s. u.) — die Positionszahl-Kodierung von #1467 S2
AG3b bleibt unangetastet.

Am Fall aus #1935 (Sicht 1.400→280 m, Schwelle 1.000, Ziel-Segment): Kopf `Ziel: `,
Token `-VS1400>280` → **`Ziel: -VS1400>280`**. Mehr-Ereignis-Beispiel (Segmente 2, 3 und
Ziel, Böen 30→80 @15:xx, Sicht 1.400→280 @14:xx):
**`Segment 2-3, Ziel: +G30>80@15 -VS1400>280@14`**.

**Kopf-Trip-Name (E4, zwei Zweige, nur Namensentfernung, keine Ortsauflösungs-Änderung):**

- `render_sms()` Trip-Δ-Zweig: s. o. (Ortsauflösung UND Namensentfernung zusammen).
- `_render_sms_onset` (Trip-Radar/Onset): Kopf verliert `{trip} `, bleibt sonst
  `km{a}-{b}: ` — **außer** das führende Event trägt `location_label` (gebündelter
  Ortsvergleich-Onset, `to_multi_location_onset_alert_message`, `OnsetEvent.location_label`
  gesetzt); dort ist `msg.trip_short` in Wahrheit der Orts-Sammelname (z. B.
  „Zermatt, Chamoni") und bleibt unangetastet (E4-Ausnahme, AC-10). Die Trip/Compare-
  Weiche selbst ist AC-12 (s. u.) — ein Test, der beide Fälle gegeneinanderstellt, statt
  nur den Trip-Fall isoliert zu prüfen.

`_render_sms_corridor_only` bekommt in dieser Spec **keine** Zusicherung: der Pfad ist
laut `docs/specs/modules/fix_1744_alarm_format_angleichen.md` („Was sich ausdrücklich
NICHT ändert") seit #1460 P1a unerreichbar. Eine Namensentfernung dort wäre unbewacht —
niemand könnte sie am Verhalten nachweisen. Wird der Pfad im Zuge der Implementierung
ohnehin mitgezogen (z. B. weil derselbe Helper wiederverwendet wird), ist das erlaubt,
aber kein AC dieser Spec deckt ihn ab.

### E6 — Ausdrücklich NICHT in dieser Spec

Die Trip-Briefing-SMS (`src/output/renderers/sms_trip.py`, Präfix `E10:`) — anderer
Renderer, anderes Wire-Format, eigenes Längenbudget. PO-Entscheid: bleibt konsequent bei
der Etappe ohne Trip-Namen, also unverändert.

## Was sich ausdrücklich NICHT ändert (Invarianten)

- **Δ-Semantik von `over_thr()`/`side_label()`/`delta_pct()`** (ADR-0013, #958) — nur die
  Darstellung ändert sich, nicht die Berechnung.
- **Ortsvergleich-Pfade in `render_sms()`:** `location_positions` gesetzt (Compare-
  Änderungspfad, #1467 S2 AG3b) bleibt kopflos und mit unverändertem Token-Format;
  `multi_location`/`msg.location_label`-Zweige (Compare-Punkt-/Bündel-Alert) bleiben
  byte-identisch — dort ist `trip_short` bereits der Orts-Sammelname, kein Trip-Name.
- **Amtliche-Warnung-SMS** (`render_official_alert_sms`, `KHW403 AMT GELB1/3: …`) —
  anderer Renderer, geregelt in `docs/specs/modules/sms_official_alert_tokens.md`.
  **Bewusst offene Rest-Inkonsistenz:** sie trägt weiterhin ihren eigenen Kurz-Ortsbezug
  nach eigenem Format, während die Trip-Δ-SMS jetzt dieselbe Ortssprache wie E-Mail/Betreff
  spricht. Vorschlag für eine spätere Entscheidung: entweder die amtliche Warn-SMS auf
  `format_alert_location` umstellen (eigene Spec, prüft `sms_official_alert_tokens.md`
  AC-Kollisionen) oder die Abweichung dokumentiert stehen lassen, weil beide SMS-Typen
  unterschiedliche Absender-Systeme (DWD-Warnstufen vs. Δ-Alarm) sind und ihre Kürze aus
  verschiedenen Gründen entsteht.
- **Trip-Briefing-SMS** (`sms_trip.py`, `E10:`) — s. E6.
- **SMS-Längenbudget:** weiterhin ≤140 Zeichen, ASCII/GSM-7-kodierbar (die vorhandene
  Kürzungslogik in `render_sms()` — Token-für-Token bis zum Limit, dann `+N` — bleibt
  strukturell unverändert; der Von-Wert im Token macht einzelne Token länger, das
  bestehende Kürzungsverfahren fängt das ab).

## Abgelöste Festlegungen

Diese Spec hebt **AC-5 der Spec `fix_1744_alarm_format_angleichen.md`** auf: „Kurznachricht
nennt weiterhin keinen Ortsbezug" (PO-Entscheid 2026-08-04). Faktisch trug die SMS auch
vorher schon einen Ortsbezug (`km12-12`) — nur den unbrauchbarsten; „keinen Ortsbezug"
meinte im damaligen Kontext offenbar „keinen Segmentnamen". Der neue PO-Entscheid vom
2026-08-17 nimmt das ausdrücklich zurück: die Alarm-SMS bekommt denselben Ortstext wie
E-Mail/Betreff. **Scope der Spec-Writer-Rolle:** diese Datei ändert `fix_1744_...md` nicht
selbst (Spec-Writer schreibt nur die neue Spec); die Implementierung MUSS dort einen
Kurzvermerk ergänzen (`> Abgelöst durch fix_1935_1779_alarm_nachricht_klarheit.md, AC-5/AC-6
(PO-Entscheid 2026-08-17) — AC-5 dieser Spec gilt nicht mehr für den Trip-Δ-Pfad.`).

## Migration bestehender Tests

| Datei | Was heute bindet | Warum sie mitgezogen werden muss |
|---|---|---|
| `tests/tdd/test_issue_1169_compare_alert_consumer.py::test_ac7_trip_alert_rendering_unchanged` | **byte-genauer** Plain-Vergleich der ganzen Trip-Mail, u. a. `"Alarm-Schwelle 10,0 mm: jetzt darüber ✗"` | Zeile ändert sich per E1 zu `"Änderung 16,0 mm: über Alarm-Schwelle 10,0 mm ✗"`; alle anderen Zeilen bleiben byte-identisch (Golden-Master-Charakter des Tests bleibt erhalten, nur der betroffene Ausschnitt wird nachgezogen — kein Löschen). |
| `tests/tdd/test_alert_bundle_958ff.py` (`test_ac2_…`) | `"jetzt darüber ✗"` als vollständiger Zielsatz (#1865-Fix) | Bindet exakt die Zeile, die E1 ersetzt — wird auf `"über Alarm-Schwelle … ✗"` umgestellt. |
| `tests/tdd/test_alert_bundle_958ff.py` (`test_ac10_…`) | Mehr-Ereignis-Zeile ohne Änderungsbetrag | Wird um die Änderung-Betrag-Assertion aus E2 ergänzt. |
| `tests/tdd/test_978_deviation_line_readability.py` (4 Tests) | `"Böen · Schwelle 40"`, `"20 ↑ 80 km/h"` | Label-Literal wird zu `"Böen · Änderung 60 · Schwelle 40"` (E2); der Wert-Teil `"20 ↑ 80 km/h"` bleibt unverändert (nicht Teil dieser Spec). |
| `tests/tdd/test_957_alert_mail_literal_structure.py` | `✓`/`✗`-Marker, `"2 über Schwelle"` | Beide Literale bleiben **unverändert** (der Marker und der Zähler-Text sind nicht Teil von E1/E2) — Test bleibt grün, keine Anpassung nötig, aber als Nachweis in der QA-Runde explizit gegenlaufen lassen. |
| `tests/tdd/test_alert_sms_location_positions.py` (`test_regression_trip_deviation_alert_sms_text_unchanged`, `test_regression_trip_radar_alert_sms_text_unchanged`) | Goldstrings `"ProbeTrip km12-18: +R30"`, `"ProbeTrip km5-18: R!12"` | Beide ändern sich ABSICHTLICH per E3/E4 zu `"Segment 1: +R2>30"` bzw. `"km5-18: R!12"` (Trip-Radar behält km-Fallback, verliert nur den Namen). `test_regression_compare_radar_alert_sms_text_unchanged` (`"Zermatt, Chamoni km0-0: R!8"`) bleibt **unverändert grün** — das ist die E4-Ausnahme (Compare-Bündel-Onset, `location_label` gesetzt) und die stärkste Positivkontrolle dafür, dass die Trip/Compare-Unterscheidung in `_render_sms_onset` funktioniert. |
| `tests/tdd/test_multi_location_onset_alert.py::test_single_onset_telegram_sms_byte_identical` | `EXPECTED_SMS = 'GR20-Test km5-18: R!12'` | Ändert sich zu `'km5-18: R!12'` (Trip-Radar-Pfad, `location_label=None`) — der Test selbst bleibt bestehen (er heißt seit #1041 „byte_identical" auf ein Vorher, das per dieser Spec nachgezogen wird), nicht löschen. |

Kein Test wird ohne fachlichen Grund gelöscht: jeder gebundene String, der nur den alten,
nachweislich missverständlichen Wortlaut zementiert hätte, wird auf den neuen Wortlaut
umgestellt — die Zusicherung dahinter (Byte-Gleichheit / Regression) bleibt erhalten.

## Expected Behavior

- **Input:** dieselben `AlertEvent`/`AlertMessage`-Objekte wie heute (kein Modellfeld
  ändert sich); Trip-Δ-Alarm, Trip-Radar/Onset-Alarm, reiner Schwellen-Alarm,
  Ortsvergleich-Alarm (alle Spielarten).
- **Output:** E-Mail-Datenblock (Einzel- und Mehrereignis) nennt den Änderungsbetrag statt
  eines missverständlichen Messwert-Bezugs; Betreff/Telegram führen die Einheit immer;
  Trip-Δ-Alarm-SMS nennt denselben Ortstext wie E-Mail/Betreff, ohne Trip-Namen, mit
  Von-Wert im Token; Trip-Radar/Onset-SMS verliert nur den Trip-Namen.
- **Side effects:** keine — reines Text-Templating, kein Zustand, kein I/O, keine
  Auslöselogik, kein Kanal-Routing.

## Acceptance Criteria

- **AC-1:** Given ein einzelnes `AlertEvent` mit `value_from=1400.0`, `value_to=280.0`,
  `threshold=1000.0`, `metric_id="visibility"` (Fall aus #1935) / When `render_email()` den
  Datenblock rendert / Then lautet die zweite Datenzeile (Label:Wert) „Änderung 1.120 m:
  über Alarm-Schwelle 1.000 m ✗" — weder das Wort „jetzt" noch die Einheit direkt am
  Schwellwert-Label kommen mehr vor, sowohl in `html` als auch in `plain`.
  - Test: `AlertEvent`/`AlertMessage` mit den o. g. Werten bauen, `render_email()`
    aufrufen, die zweite Datenzeile aus `plain` extrahieren (Zeilenweise Split, nicht
    Substring-Suche im Volltext) und auf den exakten Wortlaut prüfen; dieselbe Prüfung auf
    dem `html`-Rückgabewert (Zellinhalt der zweiten `<table>`-Zeile).

- **AC-2:** Given denselben Fall wie AC-1, aber mit `cmp`/Werten, die unter der Schwelle
  bleiben (`value_from=280.0`, `value_to=380.0`, `threshold=1000.0`) / When die Datenzeile
  gerendert wird / Then lautet sie „Änderung 100 m: unter Alarm-Schwelle 1.000 m ✓".
  - Test: dieselbe Bauform wie AC-1, invertierter Fall — beweist, dass die Umstellung
    symmetrisch für den unter-Schwelle-Fall gilt und nicht nur für den gemeldeten Fehlerfall.

- **AC-3:** Given eine E-Mail mit genau einem `AlertEvent` / When Verdict-Chip
  (`_verdict_single`) UND zweite Datenzeile (`_datablock_single`) gerendert werden / Then
  nennen beide denselben Änderungs-Bezug: dieselbe Richtung (über/unter), denselben
  Schwellwert-Text und keine widersprüchliche Aussage über den Messwert — eine Mail sagt
  intern nicht zweierlei über dieselbe Tatsache.
  - Test: für mindestens zwei Fixtures (über- und unter-Schwelle) beide Texte extrahieren
    und programmatisch prüfen, dass beide dasselbe `side_label(e)`-Wort und denselben
    `_val(e, e.threshold)`-String enthalten — kein reiner Blick auf den einen String isoliert.

- **AC-4:** Given eine `AlertMessage` mit drei `AlertEvent`s derselben Metrik über der
  Schwelle (Böen 20→80, Schwelle 40) / When `render_email()` den Mehr-Ereignis-Datenblock
  rendert / Then enthält die zugehörige Datenzeile sowohl den Änderungsbetrag (`60`) als
  auch die Schwelle (`40`), unterscheidbar als zwei verschiedene Zahlen in derselben Zeile.
  - Test: `_multi_msg()`-artige Fixture (analog `test_978_deviation_line_readability.py`)
    bauen, `render_email()` aufrufen, Zeile extrahieren und auf beide Zahlen prüfen.

- **AC-5:** Given ein Trip-Δ-Alarm (kein Ortsvergleich) für das Ziel-Segment, Sicht
  1.400→280 m, Schwelle 1.000 m / When `render_sms()` (ohne `location_positions`) rendert
  / Then lautet der Kopf der Kurznachricht „Ziel: " — derselbe Ortstext, den
  `format_alert_location` für dasselbe Ereignis in der Betreffzeile liefert — und **nicht**
  mehr der Trip-Name oder eine Kilometerspanne.
  - Test: dieselbe `AlertMessage` durch `render_subject()` UND `render_sms()` schicken und
    prüfen, dass der Ortsteil aus `render_subject()` als Präfix in `render_sms()`
    wiederkehrt (Kanalkonsistenz, keine zwei Ortssprachen).

- **AC-6:** Given denselben Fall wie AC-5 / When das Token gerendert wird / Then enthält es
  Von- UND Bis-Wert im Format `{Vorzeichen}{Kürzel}{Von}>{Bis}`, z. B. `-VS1400>280` — der
  reine Bis-Wert-Token von heute (`-VS280`) kommt nicht mehr vor.
  - Test: `render_sms()`-Ergebnis auf das exakte Token-Muster per Regex prüfen
    (`[+-][A-Z]{1,2}\d+>\d+`) und den Von-Wert `1400` sowie den Bis-Wert `280` konkret
    nachweisen.

- **AC-7:** Given ein Trip-Δ-Alarm für das Ziel-Segment (Ortstext enthält 🏁) / When
  `render_sms()` den Kopf rendert / Then steht dort „Ziel" ohne das Emoji-Zeichen und
  **ohne** dessen Transliteration (`:checkered_flag:` darf nicht vorkommen) — das Emoji
  wird entfernt, nicht ASCII-gefaltet.
  - Test: `render_sms()` für ein Ziel-Segment-Ereignis aufrufen und sowohl auf Abwesenheit
    von `:checkered_flag:` als auch auf Anwesenheit von `Ziel` im Kopf prüfen; zusätzlich
    Längen-Assertion, dass der Kopf dadurch NICHT künstlich länger wird als der reine
    Textname.

- **AC-8:** Given denselben Trip-Δ-Alarm über mehrere Segmente (2, 3, Ziel) mit je einem
  Ereignis / When `render_sms()` rendert / Then trägt der Kopf die zusammengefasste
  Segment-Sprache (`format_segment_reference`, z. B. „Segment 2-3, Ziel"), ASCII-gefaltet
  (Gedankenstrich zu Bindestrich), und jedes Token trägt weiterhin seinen eigenen Von/Bis-
  Wert nach AC-6.
  - Test: Bündel-`AlertMessage` mit drei Ereignissen bauen, `render_sms()` aufrufen, Kopf
    und beide Token per Regex/Substring gegen das Golden-Beispiel aus dieser Spec prüfen.

- **AC-9 (Regressionsschutz):** Given ein Ortsvergleich-Änderungsalarm mit
  `location_positions` gesetzt / When `render_sms()` rendert / Then bleibt die Ausgabe
  **byte-identisch** zu heute — kein Kopf, Token-Format unverändert (kein Von-Wert, keine
  `>`-Notation) — die Positionszahl-Kodierung aus #1467 S2 AG3b bleibt unangetastet.
  - Test: `tests/tdd/test_alert_sms_location_positions.py::test_k1_*`/`test_k2_*`/`test_k3_*`/`test_k4_*`
    bleiben **unverändert** grün (keine Anpassung an diesen vier Tests).

- **AC-10 (Regressionsschutz):** Given ein Ortsvergleich-Bündel-Radar-Alarm (zwei Orte,
  `OnsetEvent.location_label` gesetzt) / When `render_sms()` über `_render_sms_onset`
  rendert / Then bleibt die Ausgabe byte-identisch zu heute (`"Zermatt, Chamoni km0-0:
  R!8"`) — der Orts-Sammelname in `trip_short` ist kein Trip-Name und bleibt stehen.
  - Test: `tests/tdd/test_alert_sms_location_positions.py::test_regression_compare_radar_alert_sms_text_unchanged`
    bleibt unverändert grün.

- **AC-11 (Regressionsschutz Betreff/Telegram):** Given eine Mehr-Ereignis-Nachricht mit
  einer Nicht-Prozent-Metrik / When `render_subject()` und `render_telegram()` rendern /
  Then führen beide die Einheit am Wert (z. B. „80 km/h" statt „80"), Prozent-Metriken
  bleiben unverändert mit angehängtem `%`.
  - Test: `_multi_msg()`-Fixture durch beide Renderer schicken und die Einheit im
    resultierenden Top-3-/Metrik-Text nachweisen.

- **AC-12:** Given zwei `AlertMessage`s über `_render_sms_onset` — eine mit
  `OnsetEvent.location_label=None` (echter Trip-Radar/Onset-Alarm, `trip_short` ist der
  Trip-Kurzname) und eine mit gesetztem `location_label` (Ortsvergleich-Bündel-Onset,
  `trip_short` ist der Orts-Sammelname) — ansonsten identisch aufgebaut (gleiche
  `onset_minutes`, `km_from`/`km_to`) / When `render_sms()` beide rendert / Then enthält
  **nur** die zweite Nachricht den Wert von `trip_short` im Kopf; die erste beginnt direkt
  mit der km-Spanne (`km{a}-{b}: `) ohne Trip-Namen davor. Die Zusicherung ist der
  **Vergleich** der beiden Ergebnisse, nicht die isolierte Prüfung des Trip-Falls.
  - Test: neuer Test in der Verhaltens-Testdatei — beide Fixtures aus derselben
    Basis-`AlertMessage`/`OnsetEvent` ableiten (nur `location_label` unterscheidet sich),
    `render_sms()` auf beide anwenden und gegeneinanderstellen: Trip-Fall beginnt mit
    `"km"`, Compare-Fall beginnt mit dem Sammelnamen-Text UND enthält `trip_short`
    vollständig. Würde die Weiche fehlen oder verkehrt herum stehen, behielte entweder der
    Trip-Fall fälschlich den Namen oder der Compare-Fall (AC-10) verlöre ihn — beide
    Regressionen werden durch den direkten Vergleich sichtbar, nicht nur durch einen
    isolierten Golden-String je Fall.

## Known Limitations

- **Amtliche-Warnung-SMS bleibt inkonsistent zur Trip-Δ-SMS** (eigener Ortsbezug, eigenes
  Format) — bewusst offen, s. „Was sich ausdrücklich NICHT ändert".
- **Trip-Briefing-SMS (`E10:`) bleibt außen vor** — anderer Renderer, eigenes Ticket bei
  Bedarf (s. E6).
- **`_render_sms_corridor_only` bleibt ohne Zusicherung.** Der Pfad ist seit `8f2053f9`
  (#1460 P1a) toter Code (`docs/specs/modules/fix_1744_alarm_format_angleichen.md`, „Was
  sich ausdrücklich NICHT ändert") — unerreichbar in Produktion. Diese Spec fordert dort
  **keine** Verhaltensänderung, und **kein** AC deckt ihn ab; wird er im Zuge der
  Implementierung dennoch mitgezogen (z. B. gemeinsame Helper-Nutzung), ist das erlaubt,
  aber unbewacht — toter Code darf keine Zusicherung tragen, die niemand einlösen kann.
- **Von-Wert im SMS-Token kann bei langen Fließkommazahlen das Längenbudget stärker
  belasten** als bisher; die bestehende Token-Kürzungslogik (bis zum Limit, dann `+N`)
  fängt das strukturell ab, macht im Extremfall aber ein Ereignis mehr zum „+1"-Rest als
  vorher. Kein bekannter PO-Bug-Report dafür, kein eigenes AC.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Text-/Templating-Korrektur innerhalb des bestehenden,
  kanonischen Alert-Renderers (ADR-0011). `AlertEvent`/`AlertMessage`/`over_thr`/
  `side_label` (ADR-0013-Kontext, #958) bleiben unverändert. Die Rücknahme von
  `fix_1744_alarm_format_angleichen.md` AC-5 ist ein PO-Entscheid zum Wortlaut, keine
  neue Entscheidungsfläche im Sinne von `docs/adr/README.md` (Kanal, Provider,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie) — dokumentiert
  im Abschnitt „Abgelöste Festlegungen" oben, kein eigenes ADR nötig.

## Changelog

- 2026-08-17: Initial spec created
- 2026-08-17: AC-12 ergänzt (Trip/Compare-Weiche in `_render_sms_onset` explizit
  zugesichert, nicht nur über AC-10 negativ abgeleitet); `_render_sms_corridor_only`
  aus der aktiven Änderungsliste genommen und ausdrücklich als unbewachter toter Code
  markiert (Known Limitations) — Koordinator-Feedback.
