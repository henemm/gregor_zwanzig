---
entity_id: feat_2185_verlauf_wechselpunkte
type: feature
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [ad-hoc-abruf, trip-command-processor, wechselpunkte, epic-2133]
---

# Ad-hoc-Verlauf: Wechselpunkte statt Stunde-für-Stunde-Liste

## Approval

- [ ] Approved

## Purpose

Der Ad-hoc-Verlauf einer Einzelgröße (`_handle_drilldown`/`_handle_metric_drilldown`)
listet heute jede Stunde einzeln auf, obwohl das Zeitfenster bereits „ab jetzt" reicht
(S1/#2134). Für die typische Frage unterwegs — „wann verzieht sich der Nebel?" — ist der
**Wechselpunkt** die gesuchte Information, nicht der Einzelmesswert; eine 12-zeilige
Stundenliste beantwortet sie nicht direkt. O-Ton PO (Epic #2133, 2026-09-05): „Es ist im
Moment neblig und ich will wissen, wann die Wolken sich verziehen — keine Chance, das
herauszufinden."

Diese Spec fasst aufeinanderfolgende Stunden mit identischem formatiertem Wert zu einem
Zeitbereich zusammen. Scheibe **S2** von Epic #2133, Ticket #2185.

**Abgrenzung:** Diese Spec deckt ausschließlich diesen Verdichtungs-Formatierer ab
(vormals „Teil B" der Epic-Zerlegung). Das „ab jetzt"-Fenster für die drei
Tages-Aggregat-Antworten (`glance`/`heute_gewitter`/`timeline_heute`, vormals „Teil A")
ist beim Nachmessen strukturell nicht auf demselben Weg leistbar (`_aggregate_day`
aggregiert fertige Etappen-Zusammenfassungen, keine Stundenpunkte) und als eigenes
Ticket **#2186** abgetrennt. Details: `docs/context/feat-2185-wechselpunkte-ab-jetzt.md`,
Abschnitt „Kernbefund der Analyse".

## Source

- **File:** `src/services/trip_command_processor.py` — einzige betroffene Datei.
- **Identifier:** `_format_drilldown` (`:1174-1199`) — Kopfzeile `— stündlich` →
  `— Verlauf` (`:1191`).

## Estimated Scope

- **LoC:** Produktivcode +40–60 (1 Datei, `_format_drilldown`). Tests +250–400 (neue
  Wächter für Gruppierung/Lücken/Rundungsgrenze/Kanalparität plus Umschreiben der fünf
  bestehenden Zeilenzahl-Wächter). `loc_limit_override 500` ist vor der RED-Messung
  einzuplanen, nicht erst bei Blockade zu beantragen — die Schwesterscheibe S3/#2126
  hatte dasselbe Profil und landete bei +817.
- **Files:** 1 Produktivdatei, 1 neue Testdatei, 3 angepasste Testdateien, 1 Fremd-Spec
  (Vermerk, kein Code).
- **Effort:** medium
- **Risk:** MEDIUM — `_format_drilldown` wird von ZWEI Aufrufern geteilt
  (`_handle_drilldown` für die drei Legacy-Token thunder/wind/precip, UND
  `_handle_metric_drilldown` für jede S1-Katalog-Größe); eine Änderung wirkt auf beide
  gleichzeitig, gewollt, aber die Testlast verdoppelt sich.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `local_fmt` (`src/utils/timezone.py:123-133`) | function | Ortszeit-Formatierung für Bereichsgrenzen — beide Grenzen einer Gruppe laufen über dieselbe Funktion (hält `fix_1470` AC-4) |
| `format_hail_note` (`src/output/metric_format.py`) | function | Liefert die Hagelnotiz je Zeitpunkt — geht als zweiter Bestandteil in den Gruppenschlüssel ein |
| `_metric_formatter`/`get_metric` (Katalog, S1/#2134) | function | Liefert den bestehenden Formatierer je Größe — die Gruppierung vergleicht dessen Textausgabe, keine neue Pro-Metrik-Logik |
| `DrilldownResult.points` / `DrilldownPoint` (`weather_extractor.py:57-60`) | data | Liefert die Stundenpunkte (`ts`, `value`); schlichtes Dataclass — ein Test kann jeden beliebigen `ts`-Abstand konstruieren, nicht nur den heute produktiv vorkommenden |
| `_handle_drilldown` (`:912`) / `_handle_metric_drilldown` (`:993`) | method | Beide Aufrufer von `_format_drilldown` — die Änderung wirkt auf beide gleichzeitig, EINE Formatierung statt zweier |

## Implementation Details

### Gruppierung

1. **Gruppenschlüssel = (formatierter Text, Hagelnotiz-Text).** Nicht der Rohwert — die
   Rundung des bestehenden Formatierers *ist* die Kategorie (Epic-Prinzip „ein
   Vokabular"). Die Hagelnotiz im Schlüssel lässt die Gruppe automatisch brechen, wenn
   sie wechselt.
2. **Fortsetzungsbedingung `ts_next - ts_cur <= 1 h`**, nicht `== 1 h`. Gleichheit bräche
   bei feinerem Raster; die Obergrenze degradiert bei gröberem Raster sauber auf die
   heutige Einzelzeilen-Form — fail-safe statt falsch (geprüft, nicht nur behauptet:
   AC-11). **Eine fehlende Stunde beendet die Gruppe** und verhindert damit, dass ein
   Zeitbereich eine Lücke überbrückt.
3. **Fehlende Werte brauchen keine Sonderlogik:** `fmt(None, with_emoji=with_emoji)`
   erzeugt einen eigenen Text (z. B. „– keine Daten") und damit einen eigenen
   Gruppenschlüssel. Die Lücke bleibt benannt (S1/AC-17), mehrere fehlende Stunden
   hintereinander werden ehrlich zu einem eigenen, benannten Bereich zusammengefasst.
4. **Zeilenform unverändert:** `f"{zeit}  {wert}"`, optional `· {note}`. Nur das
   Zeitfeld wird bei ≥2 Punkten in der Gruppe zu `HH:MM–HH:MM` (beide Grenzen über
   `local_fmt`). Eine Einzelstunde bleibt **zeichengleich** zu heute — das hält jeden
   Volltext-Test grün, dessen Fixture stündlich wechselt (`test_thunder_origin_trip.py`).
5. **Kein „ab HH:MM" für die letzte Gruppe.** Das Fensterende kann über das Ende der
   gespeicherten Reihe hinausreichen (`weather_extractor.py:195`); „ab 14:00" würde dann
   Gültigkeit für Stunden ohne Daten behaupten — genau die #2167-Falle (fehlender Wert
   vs. echte Aussage). Die letzte Gruppe wird wie jede andere geschlossen dargestellt:
   `14:00–19:00`, begrenzt durch den letzten tatsächlich vorhandenen Punkt.
6. **Kopfzeile `— Verlauf`** statt `— stündlich` (`:1191`). Nachgemessen: kein Test prüft
   diesen String wörtlich, die Treffer auf „stündlich" im Testbaum sind Kommentare und
   Docstrings.

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `_format_drilldown` (`:1174`) gruppiert; Kopfzeile (`:1191`) |
| `tests/tdd/test_adhoc_verlauf_wechselpunkte.py` | CREATE | Neue Wächter: Gruppierung, Rundungsgrenze, Lücke, fehlender Wert, Abdeckung, Kanalparität, beide Aufrufer, Fortsetzungsgrenze bei feinerem Raster |
| `tests/tdd/test_issue_654_telegram_thunder_drilldown.py` | MODIFY | Zeilenzahl-Zusicherung (`:180`, `:291`, ≥6 Zeilen) durch Abdeckungs-Zusicherung ersetzen |
| `tests/tdd/test_telegram_drilldown_local_time_boundary.py` | MODIFY | dito (`:210`) |
| `tests/tdd/test_adhoc_abruf_am_telegram_draht.py` | MODIFY | Schwelle `>=3` (`:254`, `:302`) durch Abdeckungs-Zusicherung ersetzen |
| `docs/specs/modules/telegram_tier3_drilldown.md` | MODIFY | AC-1 als „abgelöst durch #2185, PO-Entscheid <Datum der Freigabe>" markieren — Zeile bleibt stehen, wird nicht gelöscht |

## Expected Behavior

- **Input:** Ad-hoc-Abruf einer Katalog-Größe (`_handle_metric_drilldown`) oder einer der
  drei Legacy-Token thunder/wind/precip (`_handle_drilldown`), gestellt zu beliebiger
  Tageszeit, über E-Mail oder Telegram.
- **Output:** Aufeinanderfolgende Stunden mit gleichem formatiertem Wert erscheinen als
  EIN Zeitbereich (`HH:MM–HH:MM`) statt als Einzelzeilen; eine Stunde ohne Vorgänger/
  Nachfolger mit gleichem Wert bleibt eine Einzelzeile wie bisher; die letzte Gruppe ist
  geschlossen dargestellt, kein „ab HH:MM".
- **Side effects:** keine — reiner Lesepfad, kein Schreibzugriff, keine Persistenz.

## Spec-Konflikt: Ablösung von `telegram_tier3_drilldown.md` AC-1

`docs/specs/modules/telegram_tier3_drilldown.md` ist `status: live`, PO-freigegeben
2026-06-08, und fordert in AC-1 eine stündliche Liste mit **≥6 Zeilen, je Uhrzeit eine**
(`tests/tdd/test_issue_654_telegram_thunder_drilldown.py:180`, `:291`;
`tests/tdd/test_telegram_drilldown_local_time_boundary.py:210`; mit Schwelle `>=3`
zusätzlich `tests/tdd/test_adhoc_abruf_am_telegram_draht.py:254`, `:302`). Diese
Zusicherung ist mit der Gruppierung unvereinbar: ein Verlauf mit einem einzigen
Wechselpunkt liefert künftig 2 Zeilen statt ≥6.

**Diese AC wird durch diese Spec ausdrücklich abgelöst, nicht gelöscht.** Ersatz ist
keine zweite Formvorschrift, sondern eine **Abdeckungs-Zusicherung**:

> Jeder Zeitpunkt, für den im Antwortfenster ein Datenpunkt vorliegt, ist von genau
> einer Zeile abgedeckt — und keine Zeile deckt einen Zeitpunkt ab, für den keiner
> vorliegt.

Das erhält die ursprüngliche Absicht von AC-1 („man sieht den ganzen Verlauf, keine
Stunde fehlt") und prüft sie **stärker**: Die alte Form „≥6 Zeilen" hätte auch eine
Antwort bestehen lassen, die sechs beliebige (auch lückenhafte oder doppelt gezählte)
Zeilen enthält, solange nur die Anzahl stimmt. Die Abdeckungs-Zusicherung rekonstruiert
aus den ausgelieferten Zeitbereichen die Menge der tatsächlich abgedeckten Stunden und
vergleicht sie mit `res.points` — sie fängt damit auch einen verschluckten Punkt ganz
ohne Gruppierung, den die alte Form-Regel nicht geprüft hätte, und verbietet zugleich
genau das Überbrücken einer Lücke.

`telegram_tier3_drilldown.md` bekommt bei Umsetzung dieser Spec einen Vermerk direkt
unter AC-1: „Abgelöst durch #2185 (Wechselpunkt-Verdichtung), PO-Entscheid
<Datum der Freigabe> — Zeilenzahl-Form ersetzt durch Abdeckungs-Zusicherung, siehe
`feat_2185_verlauf_wechselpunkte.md`." Der Text der alten AC bleibt lesbar stehen.

**PO-Entscheidungspunkt:** Bestätigt der PO diese Ablösung ausdrücklich als Teil der
Spec-Freigabe? Ohne diese Bestätigung darf `_format_drilldown` nicht geändert werden —
sonst wird die alte, live freigegebene Spec kommentarlos verletzt.

## Acceptance Criteria

- **AC-1:** Given ein Verlauf, in dem Stunde 09:00 und 10:00 denselben formatierten Wert
  tragen / When der Nutzer den Verlauf abruft / Then erscheinen beide Stunden als EIN
  Zeitbereich `09:00–10:00`, nicht als zwei Einzelzeilen.
  - Test: zwei aufeinanderfolgende `DrilldownPoint`s mit identischem `fmt()`-Ergebnis
    ergeben genau eine Zeile mit Bereichsangabe.

- **AC-2:** Given ein Wert bleibt über das gesamte Antwortfenster unverändert (z. B.
  durchgehend trocken) / When der Verlauf abgerufen wird / Then erscheint GENAU EIN
  Zeitbereich, der das ganze Fenster abdeckt — kein Wechselpunkt wird erfunden, wo keiner
  ist.
  - Test: zwölf Punkte mit identischem formatiertem Wert ergeben eine einzige Zeile mit
    Bereich vom ersten bis zum letzten Zeitpunkt.

- **AC-3:** Given ein Wert wechselt JEDE Stunde (z. B. stark schwankender Wind) / When
  der Verlauf abgerufen wird / Then erscheint je Stunde eine eigene Zeile — kein Wert
  geht verloren oder wird einer falschen Uhrzeit zugeordnet.
  - Test: zwölf Punkte mit paarweise unterschiedlichem formatiertem Wert ergeben zwölf
    Zeilen, jede mit korrekter Einzeluhrzeit statt Bereich.

- **AC-4:** Given zwei aufeinanderfolgende Stunden mit unterschiedlichem Rohwert, aber
  identischem formatiertem Text (z. B. Rundungsgrenze) / When der Verlauf abgerufen wird
  / Then bilden beide EINEN Zeitbereich — die Gruppierung vergleicht den formatierten
  Text, nicht den Rohwert.
  - Test: zwei Rohwerte, die auf denselben Anzeigetext runden, ergeben eine Zeile statt
    zwei.

- **AC-5:** Given im Antwortfenster fehlt eine Stunde ganz (kein Datenpunkt zwischen zwei
  vorhandenen) / When der Verlauf abgerufen wird / Then endet der Zeitbereich vor der
  Lücke und ein neuer beginnt danach — kein Bereich überbrückt die fehlende Stunde.
  - Test: Punktliste mit einer ausgelassenen Stunde zwischen zwei sonst gleichwertigen
    Punkten ergibt zwei getrennte Zeilen, keine durchgehende Bereichsangabe.

- **AC-6:** Given aufeinanderfolgende Punkte mit `value=None` / When der Verlauf
  abgerufen wird / Then bilden sie einen eigenen, benannten Bereich („keine Daten"),
  der nie mit einem Messwert verschmilzt (S1/AC-17 gilt weiter).
  - Test: zwei `None`-Punkte gefolgt von einem Messwert ergeben zwei Zeilen — eine
    Lücken-Zeile über beide Stunden, eine Messwert-Zeile — nie eine gemeinsame.

- **AC-7:** Given ein beliebiges Antwortfenster mit vorhandenen und fehlenden
  Datenpunkten / When der Verlauf abgerufen wird / Then ist jeder Zeitpunkt, für den ein
  Datenpunkt in `res.points` vorliegt, von genau einer Zeile abgedeckt, und keine Zeile
  deckt einen Zeitpunkt ab, für den kein Datenpunkt vorliegt.
  - Test: aus den ausgelieferten Zeitbereichen rekonstruierte Stundenmenge wird
    strukturell mit der Menge der `ts`-Werte aus `res.points` verglichen (löst
    `telegram_tier3_drilldown.md` AC-1 ab, s. o.).

- **AC-8:** Given dieselbe Datenlage wird einmal mit `channel="email"` und einmal mit
  `channel="telegram"` abgerufen / When beide Antworten erzeugt werden / Then liegen die
  Gruppengrenzen (welche Stunden zusammengefasst werden) in beiden Kanälen identisch —
  der Emoji-Schalter `with_emoji` verändert nur die Wortwahl innerhalb einer Zeile, nie
  die Gruppierung.
  - Test: gleiche `DrilldownResult` über beide Kanäle formatiert, Anzahl und
    Zeitgrenzen der Bereiche stimmen überein, nur der Zeilentext unterscheidet sich.

- **AC-9:** Given eine Datenlage mit gruppierbaren Folgestunden / When sie einmal über
  `_handle_drilldown` (Legacy-Token thunder/wind/precip) und einmal über
  `_handle_metric_drilldown` (S1-Katalog-Größe) abgerufen wird / Then verdichtet sich
  die Antwort in BEIDEN Fällen zu Zeitbereichen — die Änderung wirkt über beide
  Aufrufer, nicht nur über einen.
  - Test: je ein Aufruf pro Aufrufer mit identischer zugrunde liegender Punktliste,
    beide Antworten enthalten Bereichszeilen statt Einzelstunden.

- **AC-10:** Given `_handle_hours_drilldown` (die feste Vierspalten-Tabelle Temp/Wind/
  Regen/Gewitter) / When sie aufgerufen wird / Then bleibt sie unverändert eine
  Stunde-für-Stunde-Tabelle — diese Scheibe fasst sie NICHT an.
  - Test: bestehender Regressionstest für `_handle_hours_drilldown` bleibt unverändert
    grün; eine Zeile je Stunde, keine Bereichszusammenfassung.

- **AC-11:** Given zwei aufeinanderfolgende Datenpunkte im Abstand von 30 Minuten mit
  identischem formatiertem Wert / When der Verlauf abgerufen wird / Then bilden sie
  EINEN Zeitbereich — die Fortsetzung hängt an einem Abstand von höchstens einer Stunde,
  nicht an exakt einer Stunde. Diese AC prüft ausschließlich das Gruppierungsverhalten
  des Formatierers bei einem konstruierten `ts`-Abstand; sie sichert **nicht** zu, dass
  ein Wetterdienst je ein feineres Raster liefert.
  - Test: zwei `DrilldownPoint`s mit `ts`-Differenz `timedelta(minutes=30)` und
    identischem `fmt()`-Ergebnis, direkt am Formatierer konstruiert (nicht über einen
    echten Provider-Abruf) — Ergebnis ist eine Zeile mit Bereichsangabe, nicht zwei.

## Mutations-Gegenprobe

| Mutation | Muss rot werden | Begründung |
|---|---|---|
| Gruppenschlüssel vergleicht Rohwert statt formatiertem Text | **AC-4** | Zwei Stunden mit gleichem Anzeigetext, aber unterschiedlichem Rohwert erscheinen fälschlich als zwei Bereiche |
| Fortsetzungsbedingung von `<= 1 h` auf `== 1 h` verschärft | **AC-11** | Bei einem 30-Minuten-Abstand ist `30min == 1h` falsch — die Gruppe würde fälschlich aufgebrochen, obwohl der formatierte Wert gleich bleibt |
| Lückenprüfung entfernt — ein Bereich überbrückt eine fehlende Stunde | **AC-5** | Ohne die Lückenprüfung würde die Gruppe über die fehlende Stunde hinweg fortgesetzt, AC-5 verlangt genau die Trennung |
| Gruppierung wirkt nur in einem der beiden Aufrufer (z. B. nur in `_handle_metric_drilldown`) | **AC-9** | AC-9 ruft beide Aufrufer mit derselben Datenlage auf; bleibt einer bei der alten Stunde-für-Stunde-Form, schlägt der Vergleich fehl |

## Known Limitations

- **`_handle_hours_drilldown` (Vierspalten-Tabelle) bleibt unangetastet.** Vier
  unabhängig wechselnde Metriken in Wechselpunkte zusammenzufassen ist ein eigenes,
  ungelöstes Problem (unterschiedliche Wechselzeitpunkte je Spalte) und nicht Teil dieser
  Scheibe (AC-10).
- **Teil A (Tages-Aggregat „ab jetzt") ist nicht Teil dieser Spec**, siehe Abschnitt
  Purpose — abgetrennt nach #2186.
- **Kein Bezug zu S4/#2184** (Premium-SMS als Eingangsweg). Der Formatierer wird nur von
  `_handle_drilldown`/`_handle_metric_drilldown` genutzt, die ausschließlich über E-Mail
  und Telegram erreichbar sind — SMS/Premium-SMS haben derzeit keinen Kommandopfad.
- **Abgabe an S5** (Verlaufsdarstellung für die Kurzform). S5 baut auf dieser Scheibe auf,
  ist aber nicht identisch: S2 liefert die Wechselpunkt-Darstellung in voller Wortform
  ohne Längenbudget; S5 muss zusätzlich Katalog-Kürzel statt voller Wörter verwenden und
  ein Längenbudget für SMS/Premium-SMS einhalten. S2 trifft dazu keine Festlegung — das
  ist bewusst S5 überlassen.
- **Gröberes Raster als eine Stunde fällt bewusst auf Einzelzeilen zurück.** Liefert die
  Quelle für einen Zeitraum nur alle drei Stunden einen Wert (z. B. Open-Meteo in der
  Ferne teils dreistündlich), greift die Fortsetzungsbedingung (`<= 1 h`) nicht, und die
  Antwort bleibt bei Einzelzeilen — dieselbe Regel wie bei der Stundenlücke (AC-5), nur
  an der anderen Kante: ein Bereich über drei Stunden hinweg würde eine Durchgängigkeit
  behaupten, die nicht gemessen ist. Kein Fehler, keine Sonderbehandlung nötig.
- **Formatierungs-Rundung entscheidet die Gruppierung.** Ändert sich künftig die
  Nachkommastellen-Genauigkeit eines Formatierers, ändert sich implizit auch, wie fein
  die Wechselpunkt-Gruppierung auflöst — gewollte Kopplung (ein Vokabular), sollte aber
  bei künftigen Formatierer-Änderungen bewusst mitgedacht werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Lesepfad-Änderung an einem bestehenden Ad-hoc-Antwortformatierer,
  keine neue Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth). Der Konflikt mit
  `telegram_tier3_drilldown.md` ist ein Spec-Ablösungsvorgang (dokumentiert oben), keine
  neue Grundsatzentscheidung.

## Changelog

- 2026-09-07: Initial spec created (Feature-Planung, Scheibe S2 von Epic #2133, Teil B
  aus dem ursprünglichen Draft, Teil A abgetrennt nach #2186)
- 2026-09-07: AC-11 ergänzt (feineres Raster, `<=1h`-vs-`==1h`-Mutation jetzt gefangen),
  Known-Limitations-Eintrag zur ungeprüften Lücke gestrichen, stattdessen Known
  Limitation zur gegenteiligen Kante (gröberes Raster fällt auf Einzelzeilen zurück)
  ergänzt
