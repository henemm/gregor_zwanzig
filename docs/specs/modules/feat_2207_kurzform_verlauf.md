---
entity_id: feat_2207_kurzform_verlauf
type: module
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
tags: [sms, premium-sms, adhoc, metrik-katalog]
---

# Ad-hoc-Verlauf in Kurzform für Premium-SMS

## Approval

- [ ] Approved

## Purpose

Der Ad-hoc-Verlauf einer Einzelgröße (S1/#2134, verdichtet zu Wechselpunkten seit
S2/#2185) erreicht den Kurzform-Kanal (Premium-SMS, perspektivisch SMS) heute
wortwörtlich als derselbe Text wie E-Mail und Telegram — ausgeschriebene Wörter,
Uhrzeit mit Doppelpunkt, kein Längenbudget. Auf dem Satellitengerät ist das teuer
und teils gar nicht darstellbar. Diese Spec gibt dem Kurzform-Kanal eine eigene,
kurzformtaugliche Fassung derselben Aussage: Kürzel aus dem Metrik-Katalog statt
Wörtern, dieselben Wechselpunkte, eine feste Zeichengrenze und eine Kürzungsregel,
die eine Lücke benennt statt sie zu verschweigen. Letzte Scheibe **S5** von Epic
[#2133](https://github.com/henemm/gregor_zwanzig/issues/2133), Ticket
[#2207](https://github.com/henemm/gregor_zwanzig/issues/2207).

**Beispiel** — Langform (E-Mail/Telegram, bleibt exakt unverändert):

```
Sichtweite — Verlauf
14:00–16:00  0.3 km
17:00  5.0 km
18:00–21:00  42.5 km
```

Kurzform (neu, Premium-SMS, 30 Zeichen):

```
VS 0.3@14-16 5.0@17 42.5@18-21
```

## Source

- **File:** `src/services/trip_command_processor.py` — einzige betroffene Datei.
- **Identifier:** neuer Kurzform-Formatierer neben `_format_drilldown` (`:1179-1230`);
  ein aus dem Innenblock von `_format_drilldown` (`:1209-1220`) ausgelagerter,
  geteilter Gruppierungs-Helfer, den beide Formatierer aufrufen; Kanalverzweigung an
  den beiden Aufrufstellen `_handle_drilldown` (`:970`) und
  `_handle_metric_drilldown` (`:1028`).

## Estimated Scope

- **LoC:** ~100–130 (1 Produktivdatei; die neue Kurzform-Formatierung, der
  ausgelagerte Gruppierungs-Helfer und die Kanalverzweigung an zwei Aufrufstellen)
- **Files:** 1
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog` (`src/app/metric_catalog.py`) — `sms_code`, `col_label`, `unit`, `decimals` | module | Kürzel, Rundung und Einheit je Größe — die einzige Quelle, keine zweite Abkürzungsliste |
| `weather_extractor` — `DrilldownResult.points` / `DrilldownPoint` | data | Stundenwerte, aus denen die Wechselpunkt-Gruppen entstehen (geteilt mit S2) |
| `ascii_fold.fold_ascii()` (`src/utils/ascii_fold.py`) | function | GSM-7-Faltung — entfernt Gedankenstrich, Mittelpunkt, Gradzeichen, Umlaute aus dem Kurzform-Text |
| `notification_service.send_command_reply_premium_sms` | function | Versandpfad — reicht `confirmation_body` unverändert an `PremiumSmsOutput` durch, keine eigene Längenprüfung |
| `docs/reference/sms_format.md` (Kurzform-SSOT) | reference | Wird um die Bereichsnotation `@h1-h2`/`@h` und die Kürzungsregel des Verlaufs fortgeschrieben — keine parallele Notation |

## Implementation Details

**Ansatz:** Eigene Kurzform-Formatierung neben `_format_drilldown`, mit
ausgelagerter gemeinsamer Gruppierungslogik. `_format_drilldown` selbst bleibt in
Text und Verhalten unverändert; nur ihr Innenblock „aufeinanderfolgende Stunden mit
gleichem Wert zu einer Gruppe verschmelzen" (`:1209-1220`) wandert in einen Helfer,
den beide Formatierer aufrufen. Damit bleibt der Kern — *wann ändert sich der Wert*
— tatsächlich geteilter Code (PO-Vorgabe „möglichst viel Code teilen"), während die
Langform für E-Mail und Telegram zeichengleich bleibt, weil kein Zeichen ihres
Ausgabepfads verändert wird.

Die Kanalverzweigung sitzt an den beiden bestehenden Aufrufstellen, im Muster des
schon vorhandenen `with_emoji = channel == "telegram"` (`:931`): für
`channel in ("premium_sms", "sms")` wird die Kurzform-Formatierung statt
`_format_drilldown` aufgerufen.

**Kurzform-Aufbau:**
1. Kürzel der Größe = `sms_code`; ist `sms_code` leer, tritt `col_label` an seine
   Stelle. Betrifft im Katalog genau zwei Größen: `temperature_night` → `Night`,
   `temperature_day_high` → `DayMax`.
2. Die Wechselpunkt-Gruppen kommen unverändert vom geteilten Gruppierungs-Helfer
   (identisch zu S2/#2185). Eine Gruppe mit mehr als einem Zeitpunkt wird als
   `{wert}@{h1}-{h2}` geschrieben, eine Einzelstunde als `{wert}@{h}`. Werte ohne
   Einheit, Stunden ohne führende Null, Rundung nach den Katalog-Eigenschaften der
   Größe (Konventionen aus `sms_format.md` §5).
3. Ein Verlauf, der sich auf den Folgetag bezieht, trägt ein `+` am Kürzel
   (`VS+ …`), konsistent zur bestehenden `TH+:`-Konvention für Folge-Etappen.
4. Eine Datenlücke (kein Stundenwert vorhanden) erscheint als `?`, ein fehlender
   oder unterschwelliger Wert als `-` — dieselbe Unterscheidung wie in
   `sms_format.md` §4.
5. Ist die abgefragte Größe für Ort und Zeitraum insgesamt nicht befüllt, meldet
   die Kurzform das ausdrücklich (kurzer englischer Text statt Verlaufszeile),
   analog zur bereits bestehenden Ehrlichkeits-Logik in
   `_handle_metric_drilldown:1018-1027`.
6. Der komplette Kurzform-Text läuft vor dem Zeichenlängen-Check durch
   `fold_ascii()`. Übersteigt das Ergebnis 160 Zeichen, werden **hintere**
   Wechselpunkt-Gruppen entfernt — nie ein Teil einer Gruppe, nie etwas aus der
   Mitte — bis die Zeile passt. Wurde gekürzt, hängt ein englischer Anhang die
   Zahl der nicht mehr gezeigten Stunden an (`+Nh not shown`). Ohne Kürzung
   erscheint kein Anhang.
7. Für einen Verlauf entsteht immer genau eine Nachricht — keine Aufteilung auf
   mehrere Premium-SMS.

## Expected Behavior

- **Input:** Ad-hoc-Abruf einer Katalog-Größe über den Eingangskanal `premium_sms`
  oder `sms` (`_handle_drilldown` bzw. `_handle_metric_drilldown`).
- **Output:** eine einzelne Kurzform-Zeile mit Kürzel, Wechselpunkt-Gruppen im
  Format `{wert}@{h}` bzw. `{wert}@{h1}-{h2}`, höchstens 160 GSM-7-Zeichen; bei
  Kürzung ein englischer Anhang zur Zahl der ausgelassenen Stunden. E-Mail- und
  Telegram-Antworten bleiben unverändert die bisherige Langform.
- **Side effects:** keine — reiner Lesepfad, kein Schreibzugriff, keine Persistenz.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer stellt eine Ad-hoc-Verlaufsfrage über Premium-SMS oder
  über den Kanal `sms` / When die Antwort erzeugt wird / Then erhält er die
  Kurzform (Kürzel + Wechselpunkte), nicht den ausgeschriebenen E-Mail-Text.
  - Test: gemessen **am Draht**, nicht am Formatierer — der Kommandopfad läuft über
    `send_command_reply_premium_sms` bis zum echten `PremiumSmsOutput.send`
    (Messpunkt wie in `tests/tdd/test_premium_sms_kommandopfad.py`); der dort
    ankommende Text trägt das Katalog-Kürzel und die `@`-Notation statt
    ausgeschriebener Wörter und Doppelpunkt-Uhrzeiten. Derselbe Verlauf wird
    zusätzlich mit `channel="sms"` abgerufen und liefert dieselbe Bauform.

- **AC-2:** Given dieselbe Verlaufsanfrage über E-Mail oder Telegram / When die
  Antwort vor und nach dieser Änderung erzeugt wird / Then ist der ausgelieferte
  Text zeichengleich zum heutigen Stand — die Kurzform-Formatierung wirkt sich auf
  diese beiden Kanäle nicht aus.
  - Test: für eine festgelegte `DrilldownResult`-Fixture wird die Langform-Ausgabe
    gegen einen **wörtlich in den Test geschriebenen Erwartungstext** geprüft (der
    heutige Stand, vor der Änderung abgenommen) — für `channel="email"` und für
    `channel="telegram"` je einmal. Zusätzlich bleiben die bestehenden
    Regressionswächter zu `_format_drilldown` (S2/#2185 sowie die Alt-Tests zu
    Telegram-Drilldown, Hagel-Merge und Zeitzonengrenze) unverändert grün, ohne
    Anpassung an neue Ausgabetexte.

- **AC-3:** Given eine Größe mit gesetztem `sms_code` sowie die beiden Größen
  `temperature_night` und `temperature_day_high`, deren `sms_code` bewusst leer
  ist / When der Kurzform-Verlauf für sie erzeugt wird / Then steht bei der
  ersten Gruppe der `sms_code` und bei den beiden Ausnahmen der `col_label`
  (`Night` bzw. `DayMax`) vorn — es entsteht keine zweite, eigene Abkürzung.
  - Test: Kurzform-Aufruf für eine Größe mit `sms_code` sowie für
    `temperature_night`/`temperature_day_high` zeigt in allen drei Fällen exakt
    das Katalogfeld als Kürzel, nichts Selbsterfundenes.

- **AC-4:** Given aufeinanderfolgende Stunden mit gleichem Wert im Verlauf / When
  die Kurzform erzeugt wird / Then erscheinen sie als ein Bereich `{wert}@h1-h2`,
  eine Einzelstunde als `{wert}@h`; eine fehlende Stunde beendet den Bereich —
  dieselbe Zusicherung wie in S2/#2185, ein Bereich behauptet nie Gültigkeit für
  eine ungemessene Stunde.
  - Test: eine Punktreihe mit drei gleichwertigen Folgestunden, einer
    Einzelstunde mit anderem Wert und einer ausgelassenen Stunde ergibt in der
    Kurzform genau die erwarteten Bereichs- und Einzel-Tokens, keine Überbrückung
    der Lücke.

- **AC-5:** Given ein Verlaufswert / When er in der Kurzform ausgegeben wird /
  Then erscheint er ohne Einheit, die Stunde ohne führende Null, gerundet nach den
  Katalog-Eigenschaften der Größe — den Konventionen aus `sms_format.md` §5.
  - Test: ein Sichtweiten-Wert `5.0 km` erscheint als `5.0@17` (keine Einheit
    „km", Stunde `17` nicht `017`), ein Temperaturwert ganzzahlig gerundet.

- **AC-6:** Given ein Verlauf bezieht sich auf den Folgetag / When die Kurzform
  erzeugt wird / Then trägt das Kürzel ein `+` (z. B. `VS+`) — ohne diese
  Kennzeichnung wären die angegebenen Stundenzahlen mehrdeutig zwischen heute und
  morgen.
  - Test: ein Verlauf mit Fensterstart im Folgetag liefert ein Kürzel mit `+`,
    derselbe Verlauf für den laufenden Tag liefert das Kürzel ohne `+`.

- **AC-7:** Given ein beliebiger Ad-hoc-Verlauf auf Premium-SMS / When die
  Antwort erzeugt wird / Then überschreitet der ausgelieferte, GSM-7-normalisierte
  Text nie 160 Zeichen.
  - Test: ein Verlauf mit vielen Wechselpunkten (mehr als in 160 Zeichen
    darstellbar) erzeugt eine Antwort, deren Zeichenlänge nach `fold_ascii()`
    höchstens 160 beträgt.

- **AC-8:** Given ein Verlauf muss gekürzt werden, um unter 160 Zeichen zu
  bleiben / When die Kürzung greift / Then fallen ausschließlich **hintere**
  Wechselpunkt-Gruppen komplett weg — nie ein Teil einer Gruppe, nie eine Gruppe
  aus der Mitte.
  - Test: ein Verlauf mit sieben Wechselpunkt-Gruppen, von denen nur die ersten
    fünf in 160 Zeichen passen, liefert genau die ersten fünf Gruppen vollständig
    und unverändert; die Gruppen sechs und sieben fehlen ganz.

- **AC-9:** Given eine Kurzform-Antwort wurde gekürzt / When sie ausgeliefert
  wird / Then hängt ein englischer Anhang die Zahl der nicht gezeigten Stunden an
  (z. B. `+6h not shown`); ohne Kürzung erscheint kein solcher Anhang.
  - Test: die gekürzte Antwort aus AC-8 enthält den Anhang mit der korrekten
    Stundenzahl der weggefallenen Gruppen; eine ungekürzte Antwort enthält keinen
    Anhang-Text.

- **AC-10:** Given eine Ad-hoc-Verlaufsfrage über Premium-SMS oder `sms` / When
  die Antwort erzeugt wird / Then erhält der Nutzer genau eine Nachricht — der
  Verlauf wird nie auf mehrere Premium-SMS aufgeteilt.
  - Test: ein Kommandolauf mit einem Verlauf, der die 160 Zeichen deutlich
    überschreiten würde, löst am Premium-SMS-Transport **genau einen** Sendeaufruf
    aus (Zählung am echten `PremiumSmsOutput.send`) — nicht zwei, nicht drei.

- **AC-11:** Given der Kurzform-Text enthält potenziell Gedankenstrich, Mittelpunkt,
  Gradzeichen oder Umlaute aus `label_de` / When die Kurzform-Antwort erzeugt wird
  / Then enthält der ausgelieferte Text ausschließlich GSM-7-taugliche Zeichen —
  denn sonst kodiert das Gateway auf UCS-2 und die 160 Zeichen halbieren sich
  faktisch auf 70.
  - Test: eine Kurzform-Antwort, deren Rohbestandteile einen Gedankenstrich oder
    Umlaut enthalten würden, enthält nach der Formatierung keines dieser Zeichen
    mehr.

- **AC-12:** Given eine Stunde ist zwar im Verlauf enthalten, trägt aber keinen
  Wert / When die Kurzform erzeugt wird / Then erscheint für diese Stunde `?`
  („unbekannt", die Bedeutung aus `sms_format.md` §4) — die Langform schreibt an
  dieser Stelle „keine Daten", die Kurzform darf sie nicht stillschweigend
  überspringen. Fehlt der Zeitpunkt dagegen ganz, entsteht kein Token; der
  Bereich bricht (AC-4) — das ist der Unterschied zwischen „nichts gemessen" und
  „gar nicht abgefragt".
  - Test: ein Verlauf, in dem eine Stunde als Punkt mit leerem Wert vorliegt,
    zeigt an genau dieser Stundenposition `?`; ein Verlauf, in dem dieselbe
    Stunde als Punkt fehlt, zeigt dort gar kein Token und bricht stattdessen den
    Bereich.

- **AC-13:** Given die abgefragte Größe ist für den betreffenden Ort und
  Zeitraum insgesamt nicht befüllt (kein einziger Stundenwert vorhanden) / When
  der Nutzer die Kurzform-Antwort erhält / Then sagt sie das ausdrücklich — sie
  schweigt nicht und liefert keine leere oder falsch interpretierbare Zeile
  („geführt ≠ gefüllt"). Der Text ist **englisch** wie die übrige Kurzform
  (PO-Ansage 2026-08-22), Form: `{Kürzel} no data`.
  - Test: ein Abruf einer Größe ohne jeden Stundenwert im Fenster liefert eine
    erkennbare englische „keine Daten"-Aussage statt einer leeren oder
    fehlerhaften Kurzform-Zeile.

- **AC-14:** Given Langform (E-Mail/Telegram) und Kurzform (Premium-SMS/`sms`)
  werden für dieselbe Datenlage erzeugt / When beide Formatierer die Gruppierung
  vornehmen, wann sich ein Wert ändert / Then verwenden beide denselben
  gemeinsamen Gruppierungs-Helfer — die Gruppengrenzen können dadurch strukturell
  nie auseinanderlaufen.
  - Test: dieselbe `DrilldownResult` wird einmal an `_format_drilldown` und einmal
    an die Kurzform-Formatierung übergeben; die Anzahl und Zeitgrenzen der
    erkannten Wechselpunkt-Gruppen stimmen überein, nur die Textdarstellung
    unterscheidet sich.

## Mutations-Gegenprobe

| Mutation | Muss rot werden | Begründung |
|---|---|---|
| Kanalverzweigung fehlt für `channel="sms"`, nur `"premium_sms"` behandelt | **AC-1** | AC-1 ruft beide Kanäle auf; bleibt `sms` bei der Langform, schlägt der Vergleich fehl |
| `_format_drilldown` selbst wird für die Kurzform mitverändert statt eines getrennten Formatierers | **AC-2** | Bestehende Wächter zu E-Mail/Telegram würden Textänderungen zeigen |
| Kürzung entfernt eine Gruppe aus der Mitte statt von hinten | **AC-8** | AC-8 prüft, dass exakt die ersten N Gruppen unverändert erhalten bleiben |
| Kürzungsanhang fehlt oder erscheint auch ohne Kürzung | **AC-9** | AC-9 prüft beide Fälle getrennt (gekürzt mit Anhang, ungekürzt ohne) |
| `fold_ascii()` wird auf den Kurzform-Pfad nicht angewendet | **AC-11** | Ein Gedankenstrich/Umlaut bliebe im Ergebnis stehen |
| Gruppierungs-Helfer wird für die Kurzform dupliziert statt geteilt | **AC-14** | Ein künstlich abweichendes Gruppierungsverhalten in der Kopie würde den Grenzenvergleich brechen, ohne dass ein Test das fängt, solange keiner beide Pfade gegeneinander prüft — AC-14 tut das |

## Known Limitations

- **Kanal `sms` hat heute keinen produktiven Eingang.** Produktiv gesetzt werden
  nur `"email"`, `"telegram"` und `"premium_sms"`; `"sms"` kommt ausschließlich in
  Tests vor. Die Kurzform-Antwort greift also faktisch nur bei Premium-SMS — die
  Verzweigung deckt `"sms"` trotzdem mit ab, damit bei künftiger Aktivierung
  keine stille Lücke entsteht.
- **Telegram-Kurzform ist NICHT Teil dieser Scheibe.** `telegram_style="kurzform"`
  wirkt heute nur auf Berichte und Alarme, nicht auf Kommando-Antworten. Bewusst
  ausgelassen: Telegram hat keine Längengrenze, dort ist die Langform strikt
  reicher.
- **Keine Vergröberung der Werte.** Um mehr Stunden in 160 Zeichen unterzubringen,
  wäre eine gröbere Verdichtung der Werte denkbar — das bräuchte eigene
  Klassengrenzen je Metriktyp (Zahl vs. Himmelsrichtung vs. Gewitterstufe) und ist
  bewusst nicht Teil dieser Scheibe; gehört in ein Folge-Ticket.
- **Die Vierspalten-Stundentabelle (`_handle_hours_drilldown`, `dd_hours_*`)
  bleibt unangetastet**, wie schon in S2/#2185.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Entscheidungsfläche. ADR-0007 (keine
  Handlungsempfehlungen, nur Daten) und ADR-0049 (Premium-SMS als vierter,
  gleichrangiger Kanal) bleiben unberührt — diese Spec liefert nur eine weitere,
  kurzformtaugliche Darstellung derselben Daten auf einem bereits etablierten
  Kanal. Die Kurzform-Grammatik (Bereichsnotation, Kürzungsregel) wird in
  `docs/reference/sms_format.md` fortgeschrieben, nicht in einer neuen ADR
  festgehalten.

## Changelog

- 2026-09-08: Initial spec created (Feature-Planung, Scheibe S5 von Epic #2133)
