---
entity_id: feat_1680_s4_gewitter_herkunft_trip_stundentabelle
type: feature
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [thunder, trip, telegram, adr-0007, adr-0025, adr-0048, issue-1680, issue-1419]
---

<!-- Issue #1680, Scheibe 4 (Trip-Stundentabelle). Vorgaenger: Scheibe 1
     (Ortsvergleich, live 2026-08-12), Scheibe 2 (Trip-Kurzzusammenfassung +
     GEWITTER-Kommando, live 2026-08-12), Scheibe 3 (vier weitere Orte inkl.
     GLANCE und Compare-Stundentabelle, live 2026-08-13). Bezug: Epic #1419
     Rang 4, Entscheidung E1. Grundlage: PFLICHTLEKTUERE
     docs/context/feat-1680-s4-herkunft-trip-stundentabelle.md (gemessen vor
     dieser Spec), zusaetzlich zwei am Code korrigierte Annahmen dieser Spec
     selbst (s. Abschnitt "Am Code korrigiert"). -->

# Gewitter: Herkunft der Stufe in der Trip-Stundentabelle sichtbar machen (#1680 Scheibe 4)

## Approval

- [ ] Approved

## Purpose

Seit Scheibe 1-3 zeigen sieben Ausgabeorte (Ortsvergleich-Tagesuebersicht,
Trip-Kurzzusammenfassung, GEWITTER-Kommando, Pille, Kommando-Timeline,
GLANCE-Zeile, Ortsvergleich-Stundentabelle) neben der fusionierten
Gewitterstufe die tragende(n) Zutat(en) (`14:00  leicht · CAPE`). Die
**Trip-Stundentabelle** — die Vollmail-Tabelle mit einer Zeile je Stunde bzw.
je 2h-Nachtblock — ist bewusst der letzte in `docs/reference/
metric_output_matrix.md` als "weiterhin ohne" gefuehrte Ausgabeort, der ohne
Aenderung an `HourlyValue` oder `aggregate_stage()` erreichbar ist (die
anderen drei dort gelisteten — Mehrtages-Ausblick, Gewitter-Vorschau — bleiben
strukturell blockiert, s. Known Limitations). Diese Scheibe schliesst diese
Luecke ueber zwei bereits etablierte Konstruktionsstellen (Seitenkanal-Muster
`row["_hail_flag"]`) und eine bereits geteilte Formatierfunktion
(`fmt_val()`), ohne neue Felder oder neue Aggregationswege. Die Herkunft
nennt weiterhin nur die Zutat, keine Bewertung und keine
Handlungsempfehlung (ADR-0007).

## Source

> **Schicht-Hinweis:** ausschliesslich Python-Core (`src/output/renderers/`).
> Kein Frontend, keine Go-Beteiligung, kein neuer Endpoint, keine neuen
> Persistenz-Felder (alle benoetigten Felder existieren bereits seit
> Scheibe 1/2) — reine Renderlogik an zwei bestehenden Konstruktionsstellen
> plus einer bereits geteilten Formatierfunktion.

- **File:** `src/output/renderers/trip_report.py` —
  `TripReportFormatter._dp_to_row()` (Z. 653-688, Seitenkanal `row["_hail_flag"]`
  bei Z. 687 — Vorbild fuer den neuen `row["_thunder_signals"]`) und
  `TripReportFormatter._aggregate_night_block()` (Z. 560-651, Seitenkanal
  `row["_hail_flag"] = hail_priority(...)` bei Z. 649 — Vorbild fuer die
  Aggregation ueber `union_of_max_carriers()`)
- **File:** `src/output/renderers/email/helpers.py` — `fmt_val()`, Zweig
  `key == "thunder"` (Z. 732-757), darin der Klartext-/Roh-Pfad
  `if mode == "raw" or not html:` (Z. 750-753). Der HTML-Ampel-Kreis-Pfad
  (Z. 754-757, `_ampel_dot_css`) bleibt UNVERAENDERT.
- **Nur Lesend, kein eigener Code:** `src/output/renderers/narrow.py` —
  `_cell()` (Z. 77-82) ruft `fmt_val()` **ohne** `html=True` auf und erbt
  damit den neuen Herkunfts-Zusatz strukturell fuer die Telegram-rich-
  Stundentabelle (Bubbles) mit — s. "Am Code korrigiert" unten.
- **Identifier:** `output.renderers.trip_report.TripReportFormatter._dp_to_row()`,
  `output.renderers.trip_report.TripReportFormatter._aggregate_night_block()`,
  `output.renderers.email.helpers.fmt_val()`

## Estimated Scope

- **LoC:** ~30-45 Quellcode (zwei Ein-Zeiler-Seitenkanaele + `fmt_val()`s
  Roh-Zweig auf das `_fmt_thunder()`-Muster erweitert, ~10-15 Zeilen) +
  geschaetzt ~180-260 Tests (13 ACs, jeweils durch die volle Renderkette bis
  zum zurueckgegebenen `email_plain`/`html_body`/Telegram-Bubble-Text, inkl.
  der neu entdeckten Telegram-Kohaerenz). **Schaetzung, keine Messung** —
  analog S1-S3 (dort waren fruehere Schaetzungen durchweg zu optimistisch)
  in der RED-Phase neu zu pruefen; `docs/reference/metric_output_matrix.md`
  zaehlt laut CLAUDE.md nicht gegen das LoC-Limit.
- **Files:** 2 Quelldateien (s. Source) + 1 neue Testdatei, nach Verhalten
  benannt: `tests/tdd/test_thunder_origin_trip_hour_table.py` (Vorbild: die
  drei Vorgaengerdateien `test_thunder_origin_{compare,trip,four_places}.py`).
- **Effort:** low-medium. Additiv, kein Breaking Change, keine neue
  Persistenz, kein Frontend — beide gelesenen Felder existieren bereits seit
  Scheibe 1. Das Risiko liegt (a) im Nicht-Verwechseln der zwei
  Aggregationsregeln an den zwei Konstruktionsstellen (roh vs. vereinigt) und
  (b) im automatischen Mit-Erben der Telegram-rich-Stundentabelle ueber die
  geteilte `fmt_val()` — ein Wirkort, den die Aufgabenbeschreibung nicht
  vorsah (s. "Am Code korrigiert").

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1680-s4-herkunft-trip-stundentabelle.md` | GRUNDLAGE (gemessen) | Belege, Datei-/Zeilenangaben, technischer Ansatz dieser Spec sind daraus uebernommen — zwei Annahmen darin haben der Nachmessung fuer diese Spec nicht standgehalten, s. "Am Code korrigiert" |
| `docs/specs/modules/feat_1680_s2_gewitter_herkunft_trip.md` | VORGAENGER | `union_of_max_carriers()` (D1 dort) ist der geteilte Helfer, den diese Scheibe am Nacht-Block anschliesst — keine neue Aggregationsfunktion |
| `docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md` | VORGAENGER | `_fmt_thunder()`-Muster (`teile`-Liste, `" · "`-Join) ist das Formatier-Vorbild fuer `fmt_val()`s Roh-Zweig |
| `docs/specs/modules/feat_1680_s3_gewitter_herkunft_vier_orte.md` | VORGAENGER | Known Limitation 4 dort haelt fest, dass die Trip-Stundentabelle "eigene, nicht diese Scheibe" ist — genau diese Scheibe loest das ein; ausserdem Vorbild fuer die "F001-Garantie traegt nicht am rohen Durchgriff"-Lehre (dortiger Fund 1) |
| ADR-0007 (`docs/adr/0007-daten-statt-empfehlungen.md`) | ZUSAGE | Herkunfts-Label ist Beschreibung, keine Bewertung |
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | ZUSAGE | Eine Gewitter-Quelle fuer alle Kanaele — diese Scheibe erweitert additiv, baut keine zweite Fusion |
| ADR-0048 (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`) | KONTEXT | Unbekannte/ungeeichte Herkunft ist keine Aussage ueber die Guete der Eichung |
| `src/output/metric_format.py:559-609` (`union_of_max_carriers()`) | ZUSAGE (S2) | Garantiert SELBST, dass eine Hoechststufe `NONE` zu `None` (keine Traeger) fuehrt — Pflicht fuer den Nacht-Block, s. D2 |
| `src/output/metric_format.py:448-471` (`thunder_signal_carriers()`) | ZUSAGE (S1) | Liefert bei `NONE` `[]` — die EINZIGE Absicherung, auf die sich der rohe Pro-Stunde-Durchgriff verlaesst (kein eigener Guard an der Konstruktionsstelle, exakt die S3-Lehre "Fund 1") |
| `src/output/metric_format.py:374-390` (`THUNDER_SIGNAL_LABEL_DE`, `thunder_signal_label()`) | ZUSAGE (S1) | Deutscher Wortkatalog, Katalogreihenfolge wettercode/blitzdichte/cape/blitzpotenzial |
| `src/app/models.py:204` (`ForecastDataPoint.thunder_level_signals`) | ZUSAGE (S1) | Feld existiert bereits additiv, `list[str]` — diese Scheibe legt KEIN neues Feld an |
| `src/output/renderers/email/compare_html.py:204-233` (`_fmt_thunder()`) | MUSTER | `teile = [label]` → Signale (falls vorhanden) → Hagel-Hinweis, `" · "`-Join — exaktes Vorbild fuer `fmt_val()`s Erweiterung |
| `src/output/renderers/trip_report.py:648-649` (`hail_priority()`-Aufruf im Nacht-Block) | MUSTER | Aggregationsmuster fuer den zweiten `union_of_max_carriers()`-Aufruf dieser Scheibe |
| `.claude/hooks/renderer_mail_gate.py` | WAECHTER | `trip_report.py` matcht `_MAIL_PATTERNS` (Z. 44) → Trip-Validator-Nachweis (`briefing_mail_validator.py`) Pflicht. `email/helpers.py` matcht `_SHARED_HELPER_PATTERNS` (Z. 77) → BEIDE Nachweise Pflicht (Trip- UND Compare-Validator), obwohl `fmt_val()` selbst laut Messung nicht von Compare aufgerufen wird — die Datei traegt andere geteilte Funktionen (`format_units_legend`, `format_column_legend`), die Klassifikation bleibt korrekt auf Datei-Ebene |
| `tests/tdd/test_issue_811_mode_matrix.py` | WAECHTER | muss gruen sein, bevor der Renderer-Mail-Gate-Nachweis fuer `trip_report.py`/`helpers.py` akzeptiert wird |

## PO-Entscheidungen

**Fortbestehend aus Scheibe 1-3, unveraendert gueltig:**

| Frage | Entscheidung |
|---|---|
| Auslegung | **(ii) Alle tragenden Signale.** Genannt wird JEDE Zutat, die die gezeigte Stufe erreicht. Kein Gewinner wird gekuert. |
| Kanaele | **E-Mail und Telegram JA · SMS und Premium-SMS ausdruecklich OHNE Herkunft** — aktiv abzuwaehlen/zu pruefen, nicht stillschweigend auszulassen. |

**Diese Scheibe, praezisiert (kein neuer PO-Entscheid noetig, s. "Am Code korrigiert"):**

| Frage | Entscheidung |
|---|---|
| Ausgabeort | Genau die **Trip-Stundentabelle** (Vollmail: HTML-Ampel-Kreis-Modus bewusst ausgenommen, Klartext-/Roh-Modus ja). Weil `fmt_val()` bereits VOR dieser Scheibe von der Telegram-rich-Stundentabelle (Bubbles) genutzt wird, erbt diese den Zusatz strukturell mit — konsistent mit der fortbestehenden "E-Mail und Telegram JA"-Entscheidung, daher **kein Widerspruch, kein neuer PO-Entscheid**, aber ein eigenes AC (AC-2), weil die Aufgabenbeschreibung von "nur E-Mail" ausging. |
| Ampel-Kreis-Modus | Bleibt UNVERAENDERT — kein Textplatz, keine der Scheiben S1-S3 hat je einen visuellen Herkunfts-Indikator gebaut. Explizites AC (AC-9) statt stillem Auslassen. |

## Am Code korrigiert (vor Freigabe, 2026-08-13)

Zwei Annahmen aus der Aufgabenbeschreibung bzw. dem Kontext-Dokument halten
der Nachmessung fuer diese Spec nicht stand. Beide sind Praezisierungen, kein
Widerspruch zu bestehenden PO-Entscheidungen.

1. 🔴 **`fmt_val()` ist NICHT "die geteilte Zellwert-Formatierfunktion fuer
   Trip- UND Compare-Stundentabelle".** Grep bestaetigt: weder
   `comparison.py` noch `email/compare_html.py` importieren `fmt_val` —
   Compare baut seine Stundenzeilen ausschliesslich ueber `_fmt_thunder()`
   (`compare_html.py`) bzw. die eigene `_PLAIN_ROWS`-Tupelliste
   (`comparison.py`). `fmt_val()` wird tatsaechlich nur von drei
   Trip-Renderern aufgerufen: `email/plain.py:75/90`, `email/html.py:749`,
   `narrow.py:82/510/511` (Telegram rich). Die Regressionsgefahr fuer Compare
   ist damit **strukturell null**, nicht nur "additiv mit sicherem Default"
   wie in der Aufgabenbeschreibung angenommen — AC-12 weist das nach. Der
   Renderer-Mail-Gate bleibt trotzdem mit BEIDEN Nachweisen scharf (s.
   Dependencies): `helpers.py` traegt andere, tatsaechlich von Compare
   importierte Funktionen.
2. 🔴 **Der Kanalscope ist NICHT "nur E-Mail".** `narrow.py::_cell()`
   (Z. 77-82) ruft `fmt_val(key, row.get(key), friendly_keys=friendly_keys,
   row=row)` — **ohne** `html=True`. Der Roh-/Text-Zweig aus D3 (`mode ==
   "raw" or not html`) greift damit unveraendert auch fuer die
   Telegram-rich-Stundentabelle (Bubbles), weil `seg_tables_telegram`
   (`trip_report.py:268`) ueber **dieselbe** `_dp_to_row()`-Methode gebaut
   wird wie die E-Mail-Zeilen. Kein Zusatzcode noetig — der Zusatz entsteht
   automatisch, sobald D1/D3 stehen. Das ist konsistent mit der seit
   Scheibe 1 geltenden PO-Entscheidung "E-Mail und Telegram JA", aber die
   Aufgabenbeschreibung ("Nur E-Mail (HTML + Klartext) betroffen — keine
   Telegram-/SMS-Variante der Stundentabelle") ist an dieser Stelle falsch.
   Konsequenz: AC-2 macht dieses Verhalten explizit und bewacht es, statt es
   unbewacht mitlaufen zu lassen.

## Berichtigung während GREEN (2026-08-13)

Während der Implementierung (Developer Agent, GREEN-Phase) fiel auf, dass D4s
Aussage "kein Implementierungsaufwand" für die Telegram-rich-Stundentabelle
unvollständig war: die strukturelle Vererbung über `fmt_val()` stimmt, aber
D4 hatte nicht gemessen, dass `narrow.py`s feste Tabellenbreite
(`_TG_TABLE_WIDTH = 32`) den neuen Herkunfts-Zusatz bei der Standard-
Spaltenbelegung (7 Spalten, u. a. `TH`) mitten im Zusatz umbricht ("hoch ·" /
"CAPE" auf zwei Zeilen statt "hoch · CAPE" auf einer). Real beobachtet im
GREEN-Testlauf, kein Fixture-Artefakt.

**PO-Entscheidung (2026-08-13):** Kein Eingriff in `narrow.py`/`_wrap()` —
das wäre ein Eingriff in einen geteilten, tief liegenden Formatierbaustein
weit über die drei Dateien dieser Scheibe hinaus. AC-2 wird stattdessen so
korrigiert, dass sie die tatsächliche Zusicherung prüft: Inhalt (Stufe UND
Zutat) im selben Segment-Block vorhanden, nicht zwingend als zusammen-
hängender Teilstring. Der Umbruch selbst bleibt unverändert und ist damit
kein Fehlverhalten dieser Scheibe.

## Implementation Details

**D1 — Pro-Stunde: roher Durchgriff, Muster `_hail_flag`.**
`_dp_to_row()` (`trip_report.py:653-688`) erhaelt nach Zeile 687
(`row["_hail_flag"] = getattr(dp, "hail_flag", None)`) die neue Zeile
`row["_thunder_signals"] = getattr(dp, "thunder_level_signals", None)`. Keine
Aggregation noetig — eine Zeile entspricht genau einem `dp`. Die
`NONE`-Sicherheit ("kein Gewitter" ⇒ kein Zusatz, AC-4) haengt dabei
ausschliesslich an `thunder_signal_carriers()`s eigener Garantie (leere Liste
bei `NONE`, `metric_format.py:470-471`) — dieselbe duennste Stelle, die S3 an
der Compare-Stundenzelle als "Fund 1" dokumentiert hat. Kein eigener Guard an
dieser Stelle noetig, aber Pflicht-Gegenprobe im Test (AC-4).

**D2 — Nacht-Block: Vereinigung, Muster `hail_priority()`.**
`_aggregate_night_block()` (`trip_report.py:560-651`) erhaelt nach Zeile 649
(`row["_hail_flag"] = hail_priority(...)`) die neue Zeile
```
from output.metric_format import union_of_max_carriers
row["_thunder_signals"] = union_of_max_carriers(
    (dp.thunder_level, getattr(dp, "thunder_level_signals", None)) for dp in dps
)
```
(call-time Import, Muster der Zeile direkt darueber). Anders als D1 ist hier
KEIN zusaetzlicher `NONE`-Guard an der Aufrufstelle noetig — `union_of_max_
carriers()` garantiert bereits selbst `None`, wenn die Hoechststufe des
Blocks `NONE` ist (`metric_format.py:580-588`, seit S2 F001-Garantie).

**D3 — `fmt_val()`s Roh-/Klartext-Zweig, Muster `_fmt_thunder()`.**
`helpers.py:750-753` wird von
```python
if mode == "raw" or not html:
    label = THUNDER_LABEL_DE.get(val, "–")
    note = format_hail_note(row.get("_hail_flag") if row else None)
    return f"{label} · {note}" if note else label
```
zu
```python
if mode == "raw" or not html:
    from output.metric_format import thunder_signal_label
    label = THUNDER_LABEL_DE.get(val, "–")
    teile = [label]
    signals = row.get("_thunder_signals") if row else None
    if signals:
        teile.append(", ".join(thunder_signal_label(s) for s in signals))
    note = format_hail_note(row.get("_hail_flag") if row else None)
    if note:
        teile.append(note)
    return " · ".join(teile)
```
Reihenfolge Stufe → Herkunft → Hagel, identisch zur Reihenfolge in
`_fmt_thunder()` (Compare, S1) und `_fmt_gewitter()` (Trip-Kommando, S2). Ohne
`row` bzw. ohne den Schluessel bleibt das Ergebnis zeichengleich zu vor
dieser Scheibe (`row.get("_thunder_signals")` liefert `None`, `teile` bleibt
`[label]`, s. AC-10). Der Ampel-Kreis-Zweig (Zeile 754-757) wird NICHT
angefasst.

**D4 — Telegram-rich (Bubbles) erbt strukturell, kein eigener Code (s. "Am
Code korrigiert").** `narrow.py::_cell()` ruft `fmt_val()` ohne `html=True`
auf; `seg_tables_telegram` entsteht ueber dieselbe `_dp_to_row()`-Methode
(D1). Der Roh-Zweig aus D3 greift damit automatisch. Kein Implementierungs-
Aufwand, aber Pflicht-AC (AC-2) und Pflicht-Test gegen den echten
`render_telegram_bubbles()`-Pfad — sonst waere dieser Wirkort unbewacht
"zufaellig richtig".

**D5 — Kein struktureller Kohaerenz-Guard, zwei verschiedene
Beweisebenen.** Analog S2 D6/S3 D5: an beiden Konstruktionsstellen entstehen
Stufe UND Herkunft aus DEMSELBEN Objekt bzw. derselben Liste.
- **Pro-Stunde:** dasselbe `dp` liefert `dp.thunder_level` (ueber
  `metric_def.dp_field`, Zeile 675) UND `dp.thunder_level_signals` (D1).
- **Nacht-Block:** dieselbe `dps`-Liste speist sowohl die bestehende
  `max_thunder(values)`-Bildung (Zeile 597-601) als auch den neuen
  `union_of_max_carriers()`-Aufruf (D2).

Kein Laufzeit-Guard noetig — die Kohaerenz wird durch AC-5/AC-6/AC-13 UND die
zugehoerigen Mutationsproben nachgewiesen, nicht durch eine Pruefung im Code.

## Expected Behavior

- **Input:** eine Trip-Etappe mit `ForecastDataPoint`s, die ueber die echte
  Anreicherung (`thunder_enrichment.enrich_thunder()`) unterschiedliche
  Gewitter-Rohwerte tragen (z. B. eine Stunde mit CAPE oberhalb der Leiter,
  eine andere mit Blitzpotenzial oberhalb derselben Hoechststufe; ein
  Nachtblock mit zwei Datenpunkten unterschiedlicher Zutat auf derselben
  Blockhoechststufe).
- **Output:** die Trip-Stundentabelle (E-Mail Klartext, E-Mail-HTML im
  Roh-/Klartext-Modus, Telegram-rich-Bubbles) zeigt neben der Stufe die
  tragende(n) Zutat(en); der HTML-Ampel-Kreis-Modus, Trip-SMS, Premium-SMS
  und der gesamte Compare-Pfad bleiben unveraendert.
- **Side effects:** keine neuen Datenfelder, keine Persistenz-Aenderung —
  beide gelesenen Felder existieren bereits additiv seit Scheibe 1. Die
  Telegram-rich-Stundentabelle aendert sich strukturell mit, ohne eigene
  Codezeile (D4).

## Acceptance Criteria

- **AC-1:** Given eine Stunde einer Trip-Etappe erreicht ihre Gewitterstufe
  ausschliesslich ueber eine Zutat (z. B. CAPE), When die Vollmail gerendert
  wird, Then zeigt die Stundentabellen-Zeile im Klartextteil „leicht · CAPE"
  statt nur „leicht".
  - Test: `TripReportFormatter.format_report()`/`render_email()` mit einer
    Fixture, deren Stundenpunkt via echter Anreicherung nur CAPE oberhalb der
    Leiter traegt; Assertion auf den Teilstring „· CAPE" im zurueckgegebenen
    `email_plain`.

- **AC-2 (Telegram-rich, s. "Am Code korrigiert" und "Berichtigung während GREEN"):** Given dieselbe Stunde wird als Telegram-Bubble gerendert,
  When `render_telegram_bubbles()` aufgerufen wird, Then enthaelt der
  Segment-Block der Bubble-Tabelle sowohl die Stufe ("hoch") als auch die
  Zutat ("CAPE") — strukturell geerbt ueber dieselbe
  `fmt_val()`/`_dp_to_row()`-Kette wie die E-Mail, ohne eigenen Code-Pfad.
  Der feste 32-Zeichen-Umbruch der Telegram-Tabelle (`narrow.py:60
  _TG_TABLE_WIDTH`, `_wrap()`) kann die Zeile zwischen „·" und der Zutat auf
  zwei Zeilen trennen ("hoch ·" / "CAPE") — das ist eine bewusst hingenommene
  Umbruchstelle, KEIN Datenverlust: beide Teile bleiben im selben Segment-
  Block sichtbar. Kein zusammenhaengender Teilstring wird verlangt.
  - Test: `render_telegram_bubbles()` mit derselben Fixture wie AC-1;
    Assertion, dass sowohl die Stufe als auch die Zutat im Text des
    betroffenen Segment-Blocks vorkommen (nicht notwendig als
    zusammenhaengender Teilstring).

- **AC-3:** Given innerhalb einer Stunde tragen zwei Zutaten gemeinsam die
  Hoechststufe (z. B. CAPE UND Blitzpotenzial erreichen beide „hoch"), When
  die Stundenzeile gerendert wird, Then werden BEIDE in der Katalogreihenfolge
  aus `THUNDER_SIGNAL_LABEL_DE` genannt („hoch · CAPE, Blitzpotenzial") — kein
  Gewinner wird gekuert.
  - Test: Fixture mit einem Datenpunkt, dessen CAPE- und LPI-Rohwerte beide
    auf die Hoechststufe fuehren; Assertion auf beide Labels in dieser
    Reihenfolge im zurueckgegebenen Text.

- **AC-4 (NONE ⇒ kein Zusatz, Pro-Stunde-Gegenprobe):** Given eine Stunde
  zeigt „kein" Gewitter (keine Zutat erreicht eine Stufe ueber NONE), When die
  Stundenzeile gerendert wird, Then bleibt sie zeichengleich zu vor dieser
  Scheibe — kein „·"-Zusatz, obwohl der Pro-Stunde-Durchgriff (D1) roh und
  ohne eigenen Guard erfolgt.
  - Test: Fixture ohne jedes Gewittersignal; Assertion, dass der Zellentext
    keinen `·`-Zusatz nach dem Stufenwort traegt.

- **AC-5 (Kohaerenz Pro-Stunde, keine Vermischung benachbarter Zeilen):**
  Given zwei benachbarte Stunden desselben Segments tragen ihre jeweilige
  Stufe ueber verschiedene Zutaten, When die Stundentabelle gerendert wird,
  Then zeigt JEDE Zeile ausschliesslich die Zutat(en) IHRES EIGENEN
  Datenpunkts — keine Vermischung zwischen Zeilen.
  - Test: zwei aufeinanderfolgende `dp`s mit unterschiedlichen
    `thunder_level_signals` (Stunde A nur CAPE, Stunde B nur Blitzdichte);
    Assertion, dass Zeile A nur „CAPE" und Zeile B nur „Blitzdichte" zeigt.

- **AC-6 (Nacht-Block: Vereinigung ueber mehrere Datenpunkte):** Given zwei
  Datenpunkte desselben Nachtblocks erreichen die Blockhoechststufe ueber
  unterschiedliche Zutaten, When der Nacht-Block gerendert wird, Then nennt
  die Zeile BEIDE Zutaten — nicht nur die eines einzelnen `dp` des Blocks.
  - Test: `_aggregate_night_block()` mit einer Fixture aus zwei Datenpunkten
    derselben Blockstunde, `dp` A nur CAPE, `dp` B nur Blitzpotenzial, beide
    auf derselben Hoechststufe; Assertion auf beide Labels im gerenderten
    Zeilentext.

- **AC-7 (Kohaerenz Nacht-Block, kein Leck unterhalb des Maximums):** Given
  im selben Nachtblock traegt ein dritter Datenpunkt eine Zutat, die NUR eine
  niedrigere Stufe erreicht als die Blockhoechststufe, When der Nacht-Block
  gerendert wird, Then erscheint diese dritte Zutat NICHT in der Zeile.
  - Test: drei Datenpunkte im selben Block — zwei auf der Hoechststufe mit je
    einer Zutat, ein dritter auf einer niedrigeren Stufe mit einer DRITTEN,
    exklusiven Zutat; Assertion, dass die dritte Zutat im Zeilentext fehlt.

- **AC-8 (Nacht-Block NONE ⇒ kein Zusatz):** Given alle Datenpunkte eines
  Nachtblocks zeigen „kein" Gewitter, When der Block gerendert wird, Then
  bleibt die Zeile zeichengleich zu vor dieser Scheibe — garantiert durch
  `union_of_max_carriers()` selbst (liefert `None` bei Hoechststufe `NONE`),
  nicht durch einen Guard an der Aufrufstelle.
  - Test: Fixture ohne jedes Gewittersignal im gesamten Block; Assertion,
    dass der Zeilentext keinen `·`-Zusatz traegt.

- **AC-9 (Ampel-Kreis-Modus bleibt unveraendert — bewusste Scope-Grenze):**
  Given die Gewitter-Spalte wird im HTML-Ampel-Kreis-Modus gerendert (nicht
  im Roh-/Klartext-Modus), When eine Stunde eine Herkunft haette, Then bleibt
  der gerenderte Kreis zeichengleich zu vor dieser Scheibe — kein Text, kein
  visueller Herkunfts-Indikator.
  - Test: `fmt_val()`/`render_html()` mit `html=True` und einer Spalten-
    Konfiguration, die die Ampel aktiviert (`indicator_keys` enthaelt
    „thunder"), gegen eine Fixture mit gesetzter Herkunft; Assertion, dass
    der zurueckgegebene HTML-Schnipsel byteidentisch zu einer Bestandsfixture
    aus einer Zeit vor dieser Scheibe bleibt.

- **AC-10 (Rueckwaertskompatibilitaet `fmt_val()` ohne Seitenkanal):** Given
  ein Aufrufer ruft `fmt_val(key="thunder", ...)` OHNE `row` oder mit einem
  `row`-Dict ohne den Schluessel `_thunder_signals`, When die Zelle formatiert
  wird, Then bleibt die Ausgabe zeichengleich zum Verhalten vor dieser
  Scheibe — kein Fehler, kein leerer `·`-Zusatz.
  - Test: `fmt_val("thunder", ThunderLevel.LOW, row=None)` UND
    `fmt_val("thunder", ThunderLevel.LOW, row={})` direkt aufgerufen;
    Assertion auf Textgleichheit mit einer Bestandsfixture UND auf
    Fehlerfreiheit.

- **AC-11 (Trip-SMS/Premium-SMS bleiben unberuehrt):** Given dieselbe Fixture
  wuerde in der Stundentabelle eine Herkunft zeigen, When der Trip-Bericht
  als SMS/Premium-SMS versendet wird, Then enthaelt weder `report.sms_text`
  noch — ueber den Rueckfallweg `sms_text or email_plain`
  (`notification_service.py`, mehrere Aufrufstellen, u. a. Z. 433/451/472) —
  die tatsaechlich zugestellte SMS/Premium-SMS irgendeine der vier
  Zutat-Bezeichnungen; `report.sms_text` ist nicht-leer (belegt, dass der
  Rueckfall auf `email_plain` strukturell nicht greift, analog S2 AC-8/#868).
  - Test: `TripReportFormatter` mit einer Fixture, deren Stundentabelle eine
    Herkunft ausloesen wuerde; Assertion, dass `report.sms_text` weder „CAPE"
    noch „Blitzpotenzial" noch „Blitzdichte" noch „Wettercode" enthaelt UND
    dass `report.sms_text` nicht-leer ist.

- **AC-12 (Compare bleibt strukturell unberuehrt, s. "Am Code korrigiert"):**
  Given `fmt_val()` wird um den Seitenkanal `_thunder_signals` erweitert,
  When die Ortsvergleich-Stundentabelle (HTML `_render_hour_row()`/
  `_fmt_thunder()`, Klartext `render_comparison_text()`) gerendert wird, Then
  bleibt ihr Text zeichengleich zu vor dieser Scheibe — sie ruft `fmt_val()`
  gar nicht auf.
  - Test: ein bestehender Compare-Stundentabellen-Test aus S1/S3
    (`tests/tdd/test_thunder_origin_four_places.py` bzw.
    `test_thunder_origin_compare.py`) bleibt unveraendert gruen, PLUS eine
    neue Assertion, dass `email.helpers.fmt_val` in keinem der beiden
    Compare-Rendermodule importiert wird (Grep-basierte Struktur-Assertion,
    kein Verhaltens-Mock).

- **AC-13 (Alt-Snapshot ohne Feld):** Given ein bereits gespeicherter
  Wetter-Schnappschuss OHNE das Feld `thunder_level_signals` (Alt-Snapshot
  vor Scheibe 1) wird fuer die Trip-Stundentabelle geladen, When die
  Vollmail gerendert wird, Then zeigt die Stundenzeile die Gewitterstufe
  unveraendert, aber OHNE Herkunfts-Zusatz — kein „unbekannt", kein leerer
  Trenner, kein Fehler.
  - Test: `WeatherSnapshotService.load()` mit einem Dict ohne den Schluessel
    deserialisiert; `_dp_to_row()`/`render_email()` mit der daraus
    entstehenden Timeseries aufgerufen; Assertion, dass die Stufe erscheint
    und kein „·" nach dem Stufenwort folgt.

## Testplan

**Kern-Schicht** (deterministisch, ohne Netz, echte Fusions-/Aggregations-
/Renderpfade — kein Mock-Theater): eine neue, nach Verhalten benannte
Testdatei `tests/tdd/test_thunder_origin_trip_hour_table.py` deckt AC-1 bis
AC-13 ueber die echten Funktionen
(`TripReportFormatter.format_report()`/`_dp_to_row()`/
`_aggregate_night_block()`, `render_email()`, `render_telegram_bubbles()`,
`WeatherSnapshotService.load()`).

**Pruefort=Wirkort, ohne Ausnahme:** jeder AC laeuft mindestens einmal durch
die vollstaendige Kette bis zum zurueckgegebenen `email_plain`/`html_body`/
Telegram-Bubble-Text — keine Isolation auf `fmt_val()` oder
`union_of_max_carriers()` allein (Ausnahme AC-10, das bewusst `fmt_val()`
direkt prueft, weil genau ihr Default-Verhalten der Gegenstand ist).

### Pflicht-Mutationsproben (mindestens 3, hier 6)

- **(a) Pro-Stunde: die neue Zeile `row["_thunder_signals"] = getattr(dp,
  "thunder_level_signals", None)` aus `_dp_to_row()` wieder entfernen** ⇒
  AC-1/AC-2/AC-3/AC-5 MUESSEN rot werden — beweist, dass der Seitenkanal
  tatsaechlich der Wirkort ist, nicht nur behauptet.
- **(b) Nacht-Block: `union_of_max_carriers(...)` durch den rohen Wert des
  LETZTEN Datenpunkts ersetzen** (`dps[-1].thunder_level_signals` statt
  Vereinigung) ⇒ AC-6/AC-7 MUESSEN rot werden.
- **(c) `fmt_val()`: den neuen `if signals: teile.append(...)`-Block
  auskommentieren** (Herkunfts-Erweiterung komplett entfernen, Rueckbau auf
  den Vor-Scheibe-4-Stand) ⇒ AC-1/AC-2/AC-3/AC-6 MUESSEN rot werden —
  bestaetigt, dass `fmt_val()` selbst der zentrale Wirkort ist.
- **(d) Pro-Stunde: `row["_thunder_signals"]` unbedingt auf eine feste,
  nicht-leere Liste setzen** statt `getattr(dp, "thunder_level_signals",
  None)` ⇒ AC-4 MUSS rot werden — eine „kein Gewitter"-Stunde zeigte dann
  faelschlich eine Zutat.
- **(e) Ampel-Kreis-Zweig (`band is not None`-Pfad in `fmt_val()`): denselben
  `teile`-Aufbau wie im Roh-Zweig einfuegen** (versehentliche Kopie) ⇒ AC-9
  MUSS rot werden.
- **(f) `fmt_val()`s Default-Handling `row.get("_thunder_signals") if row
  else None` durch einen direkten `row["_thunder_signals"]`-Zugriff
  ersetzen** (kein `.get()`, kein `row`-Null-Check) ⇒ AC-10 MUSS rot werden —
  ein `KeyError`/`AttributeError` statt eines stillen `None` bei fehlendem
  Schluessel bzw. fehlendem `row`, weil AC-10 `fmt_val()` DIREKT mit
  unvollstaendigem `row` aufruft. **Berichtigung (Adversary-Fund F002,
  2026-08-13):** AC-13 haengt entgegen der urspruenglichen Fassung NICHT an
  diesem Guard — `_dp_to_row()` setzt `row["_thunder_signals"]` ueber
  `getattr(dp, "thunder_level_signals", None)` (D1) IMMER, auch bei fehlendem
  Feld (Ergebnis dann `None`, nicht Schluessel-Abwesenheit). Der volle
  Renderpfad, den AC-13 durchlaeuft, kann `row["_thunder_signals"]` deshalb
  nie mit `KeyError` treffen — AC-13s eigentliche Absicherung ist
  `_dp_to_row()`s `getattr()`-Guard (`trip_report.py:692`), nicht `fmt_val()`s
  `.get()`.

Mutationen ausschliesslich per String-Ersetzung mit externer Sicherungskopie
(kein `git checkout`/`stash`/`reset`, CLAUDE.md-Vorgabe).

## Known Limitations

1. **`sdi_2` (Superzellen) bleibt aussen vor.** Die Fusion hat vier, nicht
   fuenf Zutaten — unveraendert seit Scheibe 1 (dort Known Limitation 1).
2. **EU_REST-LPI ist ein ausgewiesener Interim-Wert** (unbelegte Schwelle,
   Feineichung offen als #1678, ADR-0048). Unveraendert seit Scheibe 1 (dort
   Known Limitation 2).
3. **`aggregate_stage()` bleibt unangeschlossen.** Wie in S1-S3 (dort Known
   Limitation 7 bzw. 3): keiner der beiden Konstruktionswege dieser Scheibe
   (`_dp_to_row()`, `_aggregate_night_block()`) ruft `aggregate_stage()` auf
   — beide lesen `ForecastDataPoint`s direkt. Der generische `else`-Zweig
   (`weather_metrics.py:1265-1266`) bleibt weiterhin unerreicht durch diese
   Scheibe.
4. **Mehrtages-Ausblick und Gewitter-Vorschau bleiben ohne Herkunft.**
   `HourlyValue` (`src/output/tokens/dto.py:15-18`) ist ein frozen Dataclass
   mit nur `hour`/`value` — die Traeger gehen dort strukturell verloren
   (unveraendert seit S3 Known Limitation 4).
5. **Go-DTO und Frontend bleiben ERSATZLOS.** Kein Frontend-Ort rendert heute
   eine Gewitterstufen-Beschriftung (unveraendert seit S1-S3).
6. **Telegram-rich (Bubbles) erbt den Zusatz strukturell, nicht durch
   eigenen Code (D4).** Wer kuenftig `fmt_val()`s Roh-Zweig aendert, aendert
   unweigerlich auch die Telegram-Stundentabelle — es gibt keinen separaten
   Schalter. Wer das Verhalten NUR fuer einen der beiden Kanaele aendern
   will, braucht in Zukunft einen expliziten Parameter (analog `include_
   origin` bei Compare/S1), nicht nur eine Bedingung in `fmt_val()`.
7. **Restrisiko am SMS-Rueckfallausdruck bleibt bestehen** (unveraendert seit
   S2 Known Limitation 5/S3 Known Limitation 8), jetzt mit der
   Stundentabelle als zusaetzlicher Quelle von Herkunftstext in
   `email_plain`. Bewacht durch AC-11 und Mutationsprobe-Analogie zu S2 (d).
8. **`_deserialize_timeseries()` filtert unbekannte Schluessel nicht**
   (`weather_snapshot.py:301-324`). Unveraendert seit Scheibe 1 (dort Known
   Limitation 5) — unkritisch fuer additive Aenderungen.

## Nicht in dieser Scheibe

- **Mehrtages-Ausblick** (`email/outlook.py`) — s. Known Limitations 4.
- **Gewitter-Vorschau** (`email/html.py:1307-1329`, `email/plain.py:307-332`)
  — s. Known Limitations 4.
- **`aggregate_stage()`s Dispatch-Zweig fuer `union_of_max_carriers`** — s.
  Known Limitations 3. Bleibt fuer die Scheibe reserviert, die den
  Mehrtages-Ausblick bringt (erster echter Verbraucher, s. S1/S2/S3).
- **Go-DTO und Frontend** — s. Known Limitations 5, ersatzlos.
- **GLANCE/GEWITTER/TIMELINE-Kommando** — bereits in Scheibe 2/3 geliefert,
  von dieser Scheibe unberuehrt.
- **Ortsvergleich (jeder Ausgabeort)** — bereits in Scheibe 1/3 geliefert,
  von dieser Scheibe strukturell unberuehrt (s. AC-12, "Am Code korrigiert").
- **Ein expliziter Kanal-Schalter fuer Telegram** — diese Scheibe fuegt
  KEINEN Parameter hinzu, um die Telegram-rich-Stundentabelle unabhaengig
  von der E-Mail abschalten zu koennen (s. Known Limitations 6). Waere eine
  Produktentscheidung gegen "E-Mail und Telegram JA" und liegt ausserhalb
  dieser Scheibe.
- **Fuenfte Fusions-Zutat, Superzellen (`sdi_2`)** — s. Known Limitations 1.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue) — diese Scheibe wendet ADR-0007 (Daten statt
  Empfehlungen), ADR-0025 (eine Gewitter-Quelle fuer alle Kanaele) und
  ADR-0048 (unbekannte/ungeeichte Herkunft = keine Aussage) an, ohne eine
  davon zu aendern.
- **Rationale:** Additive Sichtbarmachung einer bereits vorhandenen internen
  Groesse (welche Zutat trug) am letzten noch offenen, strukturell
  erreichbaren Trip-Ausgabeort, ueber bereits bestehende Felder und einen
  bereits bestehenden geteilten Helfer (`union_of_max_carriers()`, S2) —
  kein neues Architekturprinzip, keine neue Datenquelle, kein neuer Kanal,
  keine neue Persistenz-Strategie. Dass die Aenderung strukturell auch die
  Telegram-rich-Stundentabelle mitzieht, ist eine Konsequenz der bereits
  bestehenden Code-Teilung (`fmt_val()`), keine neue Architekturentscheidung.
  Kein Bezug zu ADR-0034 (Herkunfts-Fusszeile/Datenquelle) — andere
  Dimension, s. Scheibe 1s Architektur-Entscheidung fuer die Abgrenzung.

## Changelog

- 2026-08-13: Initial spec created (Issue #1680, Scheibe 4). Grundlage:
  `docs/context/feat-1680-s4-herkunft-trip-stundentabelle.md`. Am Code vor
  Freigabe korrigiert (s. "Am Code korrigiert"): (1) `fmt_val()` wird
  entgegen der Aufgabenbeschreibung NICHT von Compare aufgerufen — die
  Regressionsgefahr fuer Compare ist strukturell null, nicht nur additiv
  abgesichert; (2) der Kanalscope ist NICHT auf E-Mail beschraenkt — die
  Telegram-rich-Stundentabelle (Bubbles, `narrow.py`) nutzt denselben
  `fmt_val()`-Rohtext-Pfad ueber dieselbe `_dp_to_row()`-Konstruktion und
  erbt den Herkunfts-Zusatz strukturell mit, konsistent mit der seit
  Scheibe 1 geltenden PO-Entscheidung „E-Mail und Telegram JA". AC-2 und
  AC-12 wurden entsprechend ergaenzt bzw. praezisiert.
