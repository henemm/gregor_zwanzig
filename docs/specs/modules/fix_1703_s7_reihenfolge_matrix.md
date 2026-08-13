---
entity_id: fix_1703_s7_reihenfolge_matrix
type: module
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [reihenfolge, compare, kompaktform, matrix-test, epic-1703, kanal-achse]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 7. Deckt Flaeche 5 aus
     docs/reference/metric_output_matrix.md §4.2 (Reihenfolge jenseits E-Mail
     und Telegram-rich). Setzt auf Scheibe 8 auf (Kanal-Ebene der
     Compare-Uebersicht, ADR-0053). Enthaelt EINEN nutzersichtbaren
     Produktivcode-Fix (Pillen-Reihenfolge der Kurz-E-Mail); alles Uebrige ist
     Waechter-Ausbau bzw. Charakterisierung. -->

# Reihenfolge-Wächter jenseits E-Mail/Telegram-rich (#1703 Scheibe 7)

## Approval

- [x] Approved (PO, 2026-08-13 — inkl. `loc_limit_override 550`)

## Purpose

Die im Editor eingestellte **Metrik-Reihenfolge** soll in den Ausgabeorten
bewacht werden, die heute keinen katalog-vollständigen Reihenfolge-Wächter
haben. Das sind nach Nachmessung nicht die im Issue genannten, sondern:

- die **Compare-Übersicht** über alle vier Kanäle — dort bewacht der Bestand
  (`tests/unit/test_compare_metric_order.py`, #1359) nur **4 fest getippte**
  von 25 wählbaren Metriken und nur **eine globale** Liste,
- die **Kanal-Achse** der Compare-Übersicht, die es erst seit Scheibe 8 gibt
  (`enabled_metrics_by_channel`) und für die noch gar kein Reihenfolge-Wächter
  existiert,
- die **Trip-Kompaktformen** (Kurz-E-Mail, Telegram-Kurzübersicht,
  Kompakt-Zusammenfassung), deren Reihenfolge nirgends geprüft wird.

## Korrektur der Scheiben-Prämisse (vor dem Schreiben der ACs gemessen)

Fläche 5 ist im Matrix-Dokument als „Reihenfolge in **allen** Kanälen außer
E-Mail und Telegram-rich" beschrieben und nennt als Fundstellen
`tokens/builder.py:78` und `comparison.py:237`. **Beide Angaben treffen nicht
mehr zu** — dieselbe Prämissen-Falle wie bei Scheibe 2 und Scheibe 5.

| Behauptung in Fläche 5 | Gemessener Ist-Zustand |
|---|---|
| Trip-SMS-Reihenfolge unbewacht (`tokens/builder.py:78`) | **bewacht** — `test_channel_metric_matrix.py::test_ac15_sms_kurzform_selection_deselection_and_order` (c) prüft paarweise Reihenfolge über alle 26 Katalog-Metriken; die Lücke ist mit #1677/#1660 B geschlossen (`_POSITION_SORTABLE_CATEGORIES`, `MetricSpec.position`) |
| Compare-Klartext nutzt die Reihenfolge „nur als Sichtbarkeitsfilter (#1356)" | **überholt** — `_ordered_rows()` (`comparison.py:126-140`) setzt sie seit #1359 um; der HTML-Zwilling `_visible_metrics()` (`compare_html.py:798`) ebenso |

Der Kopfkommentar von `test_channel_metric_matrix.py` (Zeile 20) nennt den
SMS-Reihenfolge-Teil weiterhin „RED". Das ist seit dem Fix zu #1677 falsch und
wird in dieser Scheibe mitkorrigiert (AC-S7-10) — ein Kommentar, der eine
geschlossene Lücke als offen ausweist, ist die Vorstufe zur nächsten
falschen Prämisse.

## Der Kern der Scheibe

Nach diesen Korrekturen bleiben **drei** Blöcke, in dieser Reihenfolge:

1. **Katalog-Deckung der Compare-Übersicht** (AC-S7-1 bis AC-S7-4). Das Prinzip
   ist bewacht, die Deckung nicht — genau die Konstellation, die Scheibe 2
   vorgefunden hat („bewacht war nur das Auswahl-PRINZIP mit zwei fest getippten
   Auswahlen, nicht die Katalog-DECKUNG").
2. **Die Kanal-Achse** (AC-S7-5). Scheibe 8 hat für die *Auswahl* an der
   zugestellten Ausgabe belegt, dass dieselbe Sendung in der E-Mail 9, in
   Telegram 5 und in der SMS 2 Metriken zeigt. Für die *Ordnung* fehlt dieser
   Nachweis vollständig.
3. **Die Trip-Kompaktformen** (AC-S7-6 bis AC-S7-9), darunter der einzige
   Produktivcode-Fix dieser Scheibe.

## Der Fix (AC-S7-6) — die Kurz-E-Mail verwirft die Reihenfolge

`build_metrics_summary_pills()` (`src/output/renderers/email/helpers.py:1844`)
bekommt vom Aufrufer `render_compact()` die **geordnete** Liste
`resolve_trip_active_metrics(dc.metrics, …)` und kollabiert sie sofort zu einer
Menge:

```python
ids_set = set(metric_ids)
# Render in catalog order
```

Der Docstring sagt es ausdrücklich: „Returns list of (text, tone) tuples **in
catalog order**". Die im Editor je Kanal eingestellte Reihenfolge kann den
Metriken-Überblick der Kurz-E-Mail damit **strukturell nicht erreichen**.

Das ist ein Bedienelement ohne Wirkung — die Fehlerklasse, gegen die dieses
Epic gebaut wurde (#1450, #1362, #1660 A/B, #1677). Kein Test bemerkt es:
AC-S4-1/2/3 aus Scheibe 4 prüfen Auswahl und Abwahl, nie die Position.

**Empfehlung: fixen.** Der Eingriff ist klein und lokal — die Katalog-Ordnung
wird zur Ordnung der übergebenen Liste. Für Trips ohne gespeicherte eigene
Reihenfolge ändert sich nichts, weil `resolve_trip_active_metrics()` dann
ohnehin die Katalog-Ordnung liefert.

**Was der Fix NICHT tut:** Er ändert weder Auswahl noch Schwellenlogik noch
die Ampelstufen. Nur die Ausgabereihenfolge der Pillen folgt der Nutzerliste.

## Bewusst NICHT in dieser Scheibe

- **Compare-Ausblick und -Stundenverlauf.** Beide führen weiterhin je eine
  einzige globale Auswahlliste ohne Kanal-Ebene (ADR-0053 Punkt 1). Es gibt
  dort keine kanalbezogene Soll-Reihenfolge, gegen die sich prüfen ließe. Ein
  Wächter dafür bräuchte zuerst deren eigene Kanal-Kette.
- **Die Altbestands-Divergenz zwischen HTML und Klartext.** Bei
  `enabled_metrics=None` (Preset ohne gespeicherte Auswahl) behält jede Seite
  ihre eigene Quellcode-Ordnung: ab Position 3 steht im HTML `precip_sum`, im
  Klartext `temp_min`; die Mengen sind identisch (25), nur die Ordnung nicht.
  Sie wird in AC-S7-4 **charakterisiert, nicht gefixt** — die
  `_PLAIN_ROWS`-Ordnung ist in `test_compare_metric_order.py` (AC-7)
  ausdrücklich als Altbestands-Standard **eingefroren**, ein Fix zöge diesen
  Bestandstest mit und gehört als eigene Entscheidung behandelt. Nebenbefund
  → #1199.
- **Neue Gates.** Leitplanke des Epics: Erweiterung des bestehenden,
  budgetierten Gates #1677 B (Option C — kein zweites Register, kein neues
  Prüfdatum).

## Scope

- **Dateien (Tests):** `tests/tdd/test_channel_metric_matrix.py` (MODIFY,
  neue Achse `AC-S7-n` + Kopfkommentar-Korrektur), `tests/helpers/compare_order.py`
  (CREATE, gerechnete Soll-Menge + Label-Auslese je Kanal — Vorbild
  `tests/helpers/outlook_columns.py` aus Scheibe 2)
- **Dateien (Produktivcode):** `src/output/renderers/email/helpers.py`
  (MODIFY, nur AC-S7-6)
- **Dateien (Doku):** `docs/reference/metric_output_matrix.md` (Fläche 5 +
  Abschnitt 6 umtragen — Definition of Done jeder Scheibe),
  `docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md` (diese Datei)
- **Geschätzte LoC:** Tests **+420/-10**, Produktivcode **+8/-4**
- **LoC-Limit:** Das Standard-Limit von 250 wird durch den Testanteil
  überschritten. **Beantragt: `loc_limit_override 550`** — begründet durch
  neun ACs über vier Kanäle mit paarweiser Reihenfolgeprüfung; die
  Vorgängerscheiben lagen mit vergleichbarem Zuschnitt bei 600 (S1) bzw. 552
  Testzeilen (S8).

## Test-Strategie

Alle neuen Tests laufen in der **Kern-Schicht** (deterministisch, ohne Netz),
gegen die Funktionen, die der Produktivpfad **tatsächlich** aufruft:

| Kanal | Prüfling | Aufrufer im Produktivpfad |
|---|---|---|
| Compare E-Mail (HTML + Klartext) | `render_compare_email()` — liefert beide Formen in EINEM Aufruf | `scheduler_dispatch_service.py:439` |
| Compare Telegram | `render_compare_telegram()` | `scheduler_dispatch_service.py:505` |
| Compare SMS | `render_compare_sms()` | `scheduler_dispatch_service.py:509` |
| Trip Kurz-E-Mail | `render_compact()` | `TripReportFormatter.format_email()` |
| Trip Telegram-Kurzübersicht | `render_telegram_bubbles()` | Telegram-Versandpfad |

**Prüfmuster durchgehend paarweise:** dieselbe Metrik-MENGE in zwei
Reihenfolgen rendern und die Positionen der beiden Labels vergleichen. Das
schlägt sowohl bei „Reihenfolge ignoriert" als auch bei „intern nach eigener
Priorität umsortiert" an — ein Test gegen eine einzelne feste Erwartung täte
das nicht.

**Soll-Mengen gerechnet, nie getippt** (Epic-Leitplanke), mit der
Einschränkung aus Scheibe 2 F001: *Rechnen sichert Vollständigkeit, nie
Zuordnung.* Jede Zuordnungsbehauptung braucht deshalb eine eigene Assertion,
und jede gerechnete Menge einen Vakuum-Schutz (Mindestgröße), damit ein leerer
Katalog den Test nicht stillschweigend bestehen lässt.

**Kappungs-bewusst:** Compare-Telegram kappt bei 7 Metrikspalten
(`CHANNEL_LIMITS["telegram"]`), Compare-SMS am Zeichenbudget. Dort wird
paarweise mit **zwei** Metriken geprüft, nicht mit der vollen Liste — sonst
misst der Test die Kappung statt der Reihenfolge.

## Acceptance Criteria

- **AC-S7-1 (Soll-Menge gerechnet, Vakuum-geschützt):** Gegeben der
  Ortsvergleich-Katalog `get_compare_metric_catalog()`, wenn die Soll-Menge der
  reihenfolge-fähigen Übersichts-Metriken gebildet wird, dann entsteht sie
  ausschließlich aus dem Katalog (26 roh minus der nicht wählbaren `cape_max_jkg`
  = 25) und niemals aus einer getippten Liste; der Test scheitert ausdrücklich,
  wenn die gerechnete Menge unter 20 Einträge fällt, damit ein leerer oder
  kaputter Katalog nicht als bestandener Test durchgeht.

- **AC-S7-2 (Compare-HTML folgt der Reihenfolge, über den ganzen Katalog):**
  Gegeben zwei Metriken aus der Soll-Menge von AC-S7-1, wenn dieselbe
  Vergleichs-Mail einmal mit der Reihenfolge [A, B] und einmal mit [B, A]
  gerendert wird, dann steht in der HTML-Übersichtstabelle im ersten Fall die
  Zeile von A vor der von B und im zweiten Fall umgekehrt — geprüft für jede
  der 25 Metriken gegen einen festen Partner, nicht nur für vier ausgewählte.

- **AC-S7-3 (Compare-Klartext folgt derselben Reihenfolge, aus derselben
  Sendung):** Gegeben derselbe Aufruf von `render_compare_email()` wie in
  AC-S7-2, wenn der Klartext-Teil derselben Mail ausgelesen wird, dann steht
  dort dieselbe Metrik-Reihenfolge wie im HTML-Teil — die Prüfung erfolgt an
  einem gemeinsamen Renderaufruf, damit eine Divergenz zwischen den beiden
  Formen derselben Mail nicht durch getrennte Aufrufe verdeckt wird.

- **AC-S7-4 (Altbestand ohne gespeicherte Auswahl — charakterisiert):** Gegeben
  ein Vergleich ohne gespeicherte Metrik-Auswahl (`enabled_metrics=None`), wenn
  HTML- und Klartext-Teil derselben Mail gerendert werden, dann hält der Test
  den heutigen Zustand als Charakterisierung fest: beide zeigen dieselbe Menge
  von 25 Zeilen, aber in unterschiedlicher Ordnung (HTML folgt `CV2_METRICS`,
  Klartext `_PLAIN_ROWS`, erste Abweichung an Position 3). Die Divergenz wird in
  dieser Scheibe **nicht behoben**; der Test dokumentiert sie mit Begründung,
  damit sie nicht unbemerkt in eine spätere Scheibe weiterwandert.

- **AC-S7-5 (Kanalweise unterschiedliche Reihenfolge in EINER Sendung):**
  Gegeben ein Vergleichs-Preset, dessen `channel_active_metrics` für E-Mail,
  Telegram und SMS dieselben Metriken in **drei verschiedenen** Reihenfolgen
  führt, wenn eine Sendung über alle drei Kanäle gerendert wird, dann zeigt jeder
  Kanal seine eigene Reihenfolge — geprüft an der jeweils zugestellten Ausgabe
  (E-Mail-Tabelle, Telegram-Nachricht, SMS-Text), nicht am Rückgabewert von
  `resolve_channel_enabled_metrics()`. Zusätzlich wird belegt, dass ein
  Zurückdrehen der Kanal-Auflösung an mindestens einer der acht Aufrufstellen
  mindestens einen dieser Tests rot macht.

- **AC-S7-6 (DER FIX — die Kurz-E-Mail folgt der eingestellten Reihenfolge):**
  Gegeben ein Trip, dessen E-Mail-Kanal-Layout zwei Metriken in einer von der
  Katalogordnung abweichenden Reihenfolge führt, wenn die Kurz-E-Mail über
  `render_compact()` gerendert wird, dann erscheinen die beiden Pillen im
  Metriken-Überblick in der eingestellten Reihenfolge — heute erscheinen sie
  stattdessen in Katalogordnung, weil `build_metrics_summary_pills()` die
  geordnete Liste zu einer Menge kollabiert. Auswahl, Abwahl, Schwellenlogik und
  Ampelstufen bleiben unverändert; das belegt ein Test, der dieselben Pillen bei
  gleicher Reihenfolge byte-gleich zum Vorzustand hält.

- **AC-S7-7 (Trip-Telegram-Kurzübersicht folgt der Reihenfolge):** Gegeben ein
  Trip mit zwei Metriken in zwei verschiedenen Reihenfolgen, wenn die
  Kurzübersicht-Bubble über `render_telegram_bubbles()` gerendert wird, dann
  folgen die Zeilen der eingestellten Reihenfolge. Der Test hält zusätzlich fest,
  dass diese Bubble ihre Ordnung aus `dc.get_enabled_metric_ids()` bezieht und
  **nicht** aus dem `render_for_channel()`-Layout, das dieselbe Funktion für die
  Tabellen-Bubbles baut — zwei Reihenfolge-Quellen in einem Renderer sind ein
  Driftrisiko und sollen benannt sein, solange sie bestehen.

- **AC-S7-8 (Compare-Telegram und Compare-SMS folgen der Reihenfolge unter
  Kappung):** Gegeben zwei Metriken in zwei Reihenfolgen, wenn
  `render_compare_telegram()` bzw. `render_compare_sms()` gerendert werden, dann
  folgt die Zellen- bzw. Token-Folge je Ort der eingestellten Reihenfolge. Weil
  Telegram bei sieben Metrikspalten und die SMS am Zeichenbudget kappt, wird
  paarweise geprüft; zusätzlich wird belegt, dass bei einer Auswahl oberhalb der
  Kappungsgrenze die Reihenfolge darüber entscheidet, **welche** Metrik erhalten
  bleibt — in der SMS ist ein Reihenfolgefehler damit ein Inhaltsfehler.

- **AC-S7-9 (Kompakt-Zusammenfassung — benannte Ausnahme):** Gegeben der
  Fließtext-Block `format_stage_summary()`, wenn seine Reihenfolge-Achse geprüft
  wird, dann hält der Test fest, dass er einer festen Positivliste folgt und
  keine nutzergesteuerte Reihenfolge kennt — als **benannte, begründete
  Ausnahme** mit Verweis auf AC-S4-6 aus Scheibe 4 (feste Positivliste als
  akzeptierter Dauerzustand), nicht als stillschweigende Auslassung.

- **AC-S7-10 (Matrix-Dokument und Kopfkommentar sind wahr):** Gegeben die
  gelieferten Wächter, wenn `docs/reference/metric_output_matrix.md` (Fläche 5,
  Abschnitt 6) und der Kopfkommentar von `test_channel_metric_matrix.py` gelesen
  werden, dann tragen beide den neuen Stand — insbesondere ist die Angabe „AC-15
  (c) → RED" entfernt, weil dieser Teil seit #1677 grün läuft, und die beiden
  oben belegten Prämissen-Korrekturen sind ausdrücklich vermerkt, damit sie
  nicht in eine Folgescheibe weiterwandern.

## Mutations-Gegenproben (Pflicht, Adversary)

Der Adversary muss mindestens diese fünf Verfälschungen einzeln vornehmen und
melden, welcher Test jeweils rot wird — wird einer nicht gefangen, ist das ein
Finding:

1. In `_ordered_rows()` (`comparison.py`) die Sortierung durch die rohe
   Quellcode-Ordnung ersetzen → muss AC-S7-3 fangen.
2. In `_visible_metrics()` (`compare_html.py`) dasselbe → muss AC-S7-2 fangen.
3. Den Fix aus AC-S7-6 zurückdrehen (`set(metric_ids)` wiederherstellen) → muss
   genau AC-S7-6 fangen und **keinen** der Scheibe-4-Tests.
4. An einer der acht Compare-Aufrufstellen `enabled_metrics_by_channel[<kanal>]`
   durch `enabled_metrics` ersetzen → muss AC-S7-5 fangen.
5. In der gerechneten Soll-Menge (AC-S7-1) den Katalog durch eine leere Liste
   ersetzen → muss am Vakuum-Schutz scheitern, nicht stillschweigend bestehen.

Zusätzlich die Leitfrage aus Scheibe 8, die dort viermal getragen hat: *Ist die
Zusicherung dort geprüft, wo sie WIRKT — oder nur dort, wo der Code steht?*
`resolve_channel_enabled_metrics()` behauptet in seinem Docstring, die
Ergebnis-Reihenfolge sei die der Kanal-Liste; geprüft gehört das an der
zugestellten Ausgabe, nicht an der reinen Funktion.

## Known Limitations

- **Ausblick und Stundenverlauf des Ortsvergleichs bleiben ungedeckt** — sie
  haben keine Kanal-Ebene (ADR-0053). Kein Versäumnis dieser Scheibe, sondern
  eine offene Folgepflicht.
- **Die Altbestands-Divergenz HTML/Klartext wird charakterisiert, nicht
  behoben** (Begründung oben) → Nebenbefund #1199.
- **Zwei Reihenfolge-Quellen in `render_telegram_bubbles()`** bleiben bestehen
  (AC-S7-7 benennt sie). Eine Zusammenführung wäre ein eigener Schnitt.
- **`format_stage_summary()` bekommt keinen Reihenfolge-Wächter**, weil es
  keine Reihenfolge-Achse hat (AC-S7-9).

## Definition of Done

- [ ] Alle zehn ACs als Tests in `tests/tdd/test_channel_metric_matrix.py` grün
- [ ] Fünf Pflicht-Mutationen einzeln nachgemessen, jede vom vorgesehenen Test
      gefangen
- [ ] `docs/reference/metric_output_matrix.md` Fläche 5 + Abschnitt 6 umgetragen
- [ ] Kopfkommentar der Testdatei korrigiert (kein falsches „RED" mehr)
- [ ] Renderer-Commit-Gate #811 erfüllt (`test_issue_811_mode_matrix.py` grün +
      frischer `briefing_mail_validator.py`-Lauf), weil AC-S7-6 eine
      Mail-Inhalts-Datei berührt
- [ ] Adversary-Verdict VERIFIED
- [ ] Staging-Verifikation der Kurz-E-Mail-Reihenfolge an einer echt
      zugestellten Mail (AC-S7-6 ist nutzersichtbar)
