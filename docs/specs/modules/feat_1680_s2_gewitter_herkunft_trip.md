---
entity_id: feat_1680_s2_gewitter_herkunft_trip
type: feature
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [thunder, trip, adr-0007, adr-0025, adr-0048, issue-1680, issue-1419]
---

<!-- Issue #1680, Scheibe 2 (Trip-Seite). Vorgaenger: Scheibe 1 (Ortsvergleich),
     live seit 2026-08-12, Spec docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md.
     Bezug: Epic #1419 Rang 4, Entscheidung E1. Grundlage: PFLICHTLEKTUERE
     docs/context/feat-1680-s2-herkunft-trip.md (gemessen 2026-08-12), PO-Entscheid
     zum Umfang dieser Scheibe (2026-08-12). -->

# Gewitter: Herkunft der Stufe auf der Trip-Seite sichtbar machen (#1680 Scheibe 2)

## Approval

- [x] Approved — PO-Freigabe „go" am 2026-08-12 auf die zehn Akzeptanzkriterien

## Purpose

Seit Scheibe 1 zeigt der Ortsvergleich neben der fusionierten Gewitterstufe die
tragende(n) Zutat(en) (`hoch · CAPE`). Auf der Trip-Seite fehlt diese Angabe noch
vollstaendig — die Kurzzusammenfassung der Trip-Mail meldet nur ein Zeitfenster
(„Gewitter moeglich 14:00–17:00"), das GEWITTER-Kommando nur ein Wort („leicht"),
ohne dass der Nutzer erfaehrt, worauf die Meldung beruht. Diese Scheibe macht die
Herkunft an diesen zwei Trip-Ausgabeorten sichtbar UND loest dabei einen strukturellen
Befund an ZWEI der DREI betroffenen Aggregationswege: die Regel „Vereinigung der
Traeger der Maximal-Segmente" existiert bereits als private Methode an der Engine,
aber unabhaengige Aggregationswege auf Tages- und Stunden-Ebene rechnen die Stufe je
selbst — ohne den geteilten Helfer wuerden hier Kopien derselben Regel entstehen
(Fehlerklasse #1480). Der dritte Weg (Etappen-Ebene, `aggregate_stage()`) bleibt
bewusst aussen vor, weil er in dieser Scheibe keinen erreichbaren Konsumenten hat
(s. Nicht in dieser Scheibe). Die Herkunft nennt weiterhin nur die Zutat, keine
Bewertung und keine Handlungsempfehlung (ADR-0007).

## Source

> **Schicht-Hinweis:** ausschliesslich Python-Core (`src/output/`,
> `src/services/`). Kein Frontend, keine Go-Beteiligung, kein neuer Endpoint,
> keine neuen Persistenz-Felder (alle benoetigten Felder existieren bereits seit
> Scheibe 1) — reine Aggregations-/Renderlogik.

- **File:** `src/output/metric_format.py` — neue freie Funktion
  `union_of_max_carriers()`, platziert neben `hail_priority()` (Z. 568-583, Vorbild
  fuer Struktur und Docstring-Stil)
- **File:** `src/services/weather_metrics.py` — `_compute_thunder_level_signals()`
  (Z. 616-642, wird duenner Wrapper um den neuen Helfer). `aggregate_stage()`
  (Z. 1164-1267) wird in dieser Scheibe NICHT angefasst — s. Nicht in dieser
  Scheibe.
- **File:** `src/services/trip_command_processor.py` — `_aggregate_day()`
  (Z. 804-830), `_fmt_gewitter()` (Z. 863-881)
- **File:** `src/output/renderers/day_window.py` — `_merge_hour()` (Z. 56-71)
- **File:** `src/output/renderers/compact_summary.py` — `_format_thunder()`
  (Z. 567-601); zusaetzlich Korrektur des irrefuehrenden Kommentars Z. 90-94
  (behauptet, `_aggregate()` sei auch Quelle fuer Gewitter — der Code widerspricht,
  `_format_thunder()` hat gar keinen `summary`-Parameter, ADR-0025 Entscheidung 1;
  Fundstelle selbst nachgemessen, die urspruengliche Angabe „91-93" war leicht
  ungenau)
- **Nur Kommentar, keine Logikaenderung:** `src/services/notification_service.py`
  Z. 417, 433 — erklaerender Hinweis am Rueckfallausdruck `report.sms_text or
  report.email_plain`, dass ein leerer `sms_text` die Herkunft in die SMS/
  Premium-SMS durchreichen wuerde (Restrisiko, s. Known Limitations)
- **Identifier:** `output.metric_format.union_of_max_carriers()`,
  `services.trip_command_processor.TripCommandProcessor._fmt_gewitter()`,
  `output.renderers.day_window._merge_hour()`,
  `output.renderers.compact_summary.CompactSummaryFormatter._format_thunder()`

## Estimated Scope

- **LoC:** ~55-90 Quellcode (ein neuer Helfer + vier duenne Andockstellen) +
  geschaetzt ~150-210 Tests (Pruefeorte=Wirkort ueber zwei getrennte
  Aggregationswege, s. Testplan) ⇒ Gesamt ~205-300. **Schaetzung, keine Messung**
  — analog Scheibe 1 (dort war „~80-110" zu optimistisch, gemessen wurden 365
  Testzeilen) ist ein `loc_limit_override` moeglicherweise noetig, aber in der
  RED-Phase neu zu pruefen statt hier vorwegzunehmen.
- **Files:** 5 Quelldateien (s. Source) + 1 neue Testdatei, nach Verhalten
  benannt: `tests/tdd/test_thunder_origin_trip.py` (Vorbild: S1s
  `test_thunder_origin_compare.py`).
- **Effort:** medium. Kein Breaking Change (additiv, alle Datenfelder existieren
  bereits seit Scheibe 1), kein Frontend, keine neue Persistenz. Das Risiko liegt
  in der korrekten Vereinigungsregel ueber zwei STRUKTURELL verschiedene
  Aggregationsebenen (Wegpunkte, Stunden — die dritte, Segmente/
  `aggregate_stage()`, bleibt unangeschlossen, s. Nicht in dieser Scheibe) und im
  SMS-Restrisiko (Rueckfallausdruck, muss aktiv geprueft werden).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1680-s2-herkunft-trip.md` | GRUNDLAGE (gemessen) | Belege, Messwerte, PO-Entscheidungen dieser Spec sind daraus uebernommen |
| `docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md` | VORGAENGER | Aufbau, Detailgrad, AC-12-Lehre (Kohaerenz) — dasselbe Muster (eine uebernommene Aussage erst auf ihre Voraussetzung pruefen) greift hier ein zweites Mal bei Known Limitation 7 dort, s. Nicht in dieser Scheibe |
| ADR-0007 (`docs/adr/0007-daten-statt-empfehlungen.md`) | ZUSAGE | Herkunfts-Label ist Beschreibung, keine Bewertung |
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | ZUSAGE | Eine Gewitter-Quelle fuer alle Kanaele — diese Scheibe erweitert additiv, baut keine zweite Fusion |
| ADR-0048 (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`) | KONTEXT | Unbekannte/ungeeichte Herkunft ist keine Aussage ueber die Guete der Eichung |
| `src/output/metric_format.py:568-583` (`hail_priority()`) | MUSTER | Freie Funktion, mehrfach importiert statt kopiert — Vorbild fuer `union_of_max_carriers()` |
| `src/output/metric_format.py:374-390` (`THUNDER_SIGNAL_LABEL_DE`, `thunder_signal_label()`) | ZUSAGE (S1) | Deutscher Wortkatalog, vier feste Schluessel — nicht neu zu definieren |
| `src/app/models.py:204,430` (`ForecastDataPoint.thunder_level_signals`, `SegmentWeatherSummary.thunder_level_max_signals`) | ZUSAGE (S1) | Beide Felder existieren bereits, `list[str]`, additiv — diese Scheibe legt KEIN neues Feld an |
| `src/output/renderers/email/compare_html.py:643-658` (`loc_thunder_signals()`) | KONTEXT | Vorbild fuer additive Suffix-Anhaengung, ABER dort mit Kohaerenz-Guard gegen einen zweiten Rechenweg (D7 in S1) — auf der Trip-Seite entfaellt dieser Guard strukturell, s. D5/D6 |
| `.claude/hooks/renderer_mail_gate.py` | WAECHTER | `compact_summary.py` steht auf der Liste — Commit blockiert ohne frischen `briefing_mail_validator.py`-Lauf UND gruene `tests/tdd/test_issue_811_mode_matrix.py` |
| `docs/reference/metric_output_matrix.md:94` | KONTEXT | Fuehrt den Herkunfts-Zusatz heute als Compare-only — Zeile ist nach Auslieferung dieser Scheibe um die zwei Trip-Ausgabeorte zu ergaenzen (Doku-Pflege, nicht Teil des Code-Diffs) |

## PO-Entscheidungen

**Fortbestehend aus Scheibe 1 (2026-08-11), unveraendert gueltig:**

| Frage | Entscheidung |
|---|---|
| Auslegung | **(ii) Alle tragenden Signale.** Genannt wird JEDE Zutat, die die gezeigte Stufe erreicht. Kein Gewinner wird gekuert. |
| Kanaele | **E-Mail und Telegram JA · SMS und Premium-SMS ausdruecklich OHNE Herkunft** — aktiv abzuwaehlen/zu pruefen, nicht stillschweigend auszulassen. |

**Neu, 2026-08-12 (Umfang dieser Scheibe):**

| Frage | Entscheidung |
|---|---|
| Ausgabeorte | Genau **zwei**: Kurzzusammenfassung der Trip-Mail UND GEWITTER-Kommando. Alle anderen Trip-Ausgabeorte (s. Nicht in dieser Scheibe) bleiben unveraendert. |
| Geteilter Helfer | Die Regel „Vereinigung der Traeger der Maximal-Segmente" wird EINMAL als freie Funktion herausgeloest (statt kopiert) und an den Aggregationswegen DIESER Scheibe angeschlossen (Wegpunkte, Stunden). Die dritte konzeptionelle Ebene (Segmente/`aggregate_stage()`) bleibt bewusst unangeschlossen — Tech-Lead-Entscheid, s. Nicht in dieser Scheibe. |

## Implementation Details

**D1 — Geteilter Helfer `union_of_max_carriers()` in `metric_format.py`.**
Generalisiert die bestehende private Methode
`WeatherMetricsService._compute_thunder_level_signals()`
(`weather_metrics.py:616-642`) zu einer freien Funktion, Vorbild `hail_priority()`
(`metric_format.py:568-583`). Nimmt eine Sequenz von Paaren `(stufe, traeger)`
entgegen — `stufe: Optional[ThunderLevel]`, `traeger: Optional[list[str]]` — und
liefert die Vereinigung der Traegerlisten aller Paare, deren Stufe das Maximum
unter den NICHT-`None`-Stufen erreicht (`max_thunder()`), dedupliziert unter
Erhalt der Erstauftrittsreihenfolge, `None` (nicht `[]`) wenn keine Stufe vorliegt
oder kein Paar am Maximum einen Traeger nennt. Die genaue Regel ist unveraendert
gegenueber der bestehenden Methode — nur der Datenzugriff wird generisch (Paare
statt fest verdrahteter `dp.thunder_level`/`dp.thunder_level_signals`-Attribute):

```
def union_of_max_carriers(
    pairs: Iterable[tuple[Optional[ThunderLevel], Optional[list[str]]]],
) -> Optional[list[str]]:
    paare = list(pairs)
    stufen = [s for s, _ in paare if s is not None]
    if not stufen:
        return None
    top = max_thunder(stufen)
    traeger: list[str] = []
    for stufe, liste in paare:
        if stufe != top:
            continue
        for name in liste or []:
            if name not in traeger:
                traeger.append(name)
    return traeger or None
```

`WeatherMetricsService._compute_thunder_level_signals()` wird zum duennen
Wrapper (`return union_of_max_carriers((dp.thunder_level, dp.thunder_level_signals)
for dp in timeseries.data)`) — zeichengleiches Verhalten, weil die intern
berechnete Maximalstufe ueber dieselbe Datenmenge laeuft wie der bisher von
aussen uebergebene `thunder_max`-Parameter. Der Helfer ist bewusst generisch
gehalten (Paare statt Attribute), damit neben den in dieser Scheibe
angeschlossenen Wegpunkten und Stunden auch die Segment-Ebene
(`aggregate_stage()`) spaeter ohne Umbau andocken kann — s. Nicht in dieser
Scheibe.

**D2 — `_aggregate_day()` liest die bereits vorhandenen Segment-Trailer.**
`trip_command_processor.py:804-830` erweitert das Rueckgabe-Dict um
`"thunder_signals": union_of_max_carriers([(p.metrics.thunder_level_max,
p.metrics.thunder_level_max_signals) for p in points])`. Kein neuer Datenzugriff
noetig: `p.metrics` ist `SegmentWeatherSummary` (per `TimelinePoint.metrics =
seg.aggregated`, `weather_extractor.py:98`), das Feld `thunder_level_max_signals`
existiert dort bereits seit Scheibe 1 und wird von `compute_basis_metrics()`
befuellt (`weather_metrics.py:438-440,462`).

**D3 — `_fmt_gewitter()` haengt additiv an, VOR dem Hagel-Suffix.**
`trip_command_processor.py:863-881` liest `agg.get("thunder_signals")`; sind
Traeger vorhanden, wird ein zusaetzlicher `·`-Abschnitt zwischen Stufenwort und
Hagel-Suffix eingefuegt (`f"⛈ Gewitter heute ({today:%d.%m}): {label} ·
{herkunft}{suffix}"`, wobei `herkunft = ", ".join(thunder_signal_label(n) for n in
traeger)`). Ohne Traeger bleibt die Zeile zeichengleich zu heute.
`_fmt_day_agg()`/das GLANCE-Kommando (Z. 832-843), das denselben `agg`-Dict
liest, bekommt bewusst KEINEN Zugriff auf den neuen Schluessel — Umfang dieser
Scheibe ist ausschliesslich das GEWITTER-Kommando.

**D4 — `_merge_hour()` ueberschreibt die Traegerliste als Vereinigung.**
`day_window.py:56-71` erweitert den bestehenden `dataclasses.replace(...)`-Aufruf
um `thunder_level_signals=union_of_max_carriers((dp.thunder_level,
dp.thunder_level_signals) for dp in dps)`. Loest den in `docs/context/feat-1680-s2-
herkunft-trip.md` als „Neuer Befund 1" beschriebenen Fehler: bisher blieb die
Traegerliste unveraendert bei `base` — also bei GENAU EINEM der Punkte mit
Hoechststufe, ausgewaehlt ueber einen fuer die Herkunft sachfremden
Tie-Break (Niederschlag, dann Boeen). Erreichbar an der Ankunftsstunde, wo sich
Segment- und Nachtfenster ueberschneiden (Docstring `day_window.py:39-41`).

**D5 — `_format_thunder()`: Herkunft bezieht sich auf die Spitzenstufe des
Zeitfensters (Tech-Lead-Entscheid 2026-08-12, Variante A von zwei erwogenen).**
Die Kurzzusammenfassung zeigt KEINE Stufe, nur ein Zeitfenster („Gewitter
moeglich 14:00–17:00") — anders als beim GEWITTER-Kommando gibt es hier kein
angezeigtes „top", gegen das die Herkunft naturgemaess kohaerent sein muesste.
Erwogen wurden zwei Auslegungen:

- **Variante A (gewaehlt):** die Herkunft nennt die Zutat(en), die innerhalb
  des Zeitfensters die HOECHSTE Stufe getragen haben.
- **Variante B (verworfen):** die Herkunft nennt die Zutaten ALLER Stunden mit
  irgendeinem Gewitter im Fenster, unabhaengig von deren Stufe.

Gruende fuer Variante A: (1) es ist dieselbe Regel wie an jedem anderen
Ausgabeort (`union_of_max_carriers`) — keine Sonderlocke fuer einen einzelnen
Ausgabeort; (2) Variante B naennte bei einer schwachen Wettercode-Stunde und
einer starken CAPE-Stunde im selben Fenster beide Zutaten und suggerierte, sie
truegen dieselbe Meldung, obwohl nur eine davon die eigentliche Gefahr ist; (3)
Variante A haelt Kurzzusammenfassung und GEWITTER-Kommando konsistent, die
dieselbe Tageslage beschreiben. Berechnung: `traeger =
union_of_max_carriers((dp.thunder_level, dp.thunder_level_signals) for dp in
hourly if dp.thunder_level and dp.thunder_level != ThunderLevel.NONE)` —
dieselbe Teilmenge, die bereits `thunder_hours`/`hail_values` bildet
(Z. 585-588), kein separater Datenzugriff. Suffix-Reihenfolge: Zeitfenster ·
Herkunft · Hagel (Hagel-Suffix bleibt am Ende, unveraendert).

**D6 — Kohaerenz ohne zusaetzlichen Guard.** Anders als in Scheibe 1 (dort D7:
`LocationResult.thunder_level_max` stammt aus dem Engine-Lauf, die Herkunft aber
aus einer ZWEITEN, unabhaengigen Live-Ableitung — daher der Kohaerenz-Guard in
`loc_thunder_signals()`) entsteht auf der Trip-Seite die Stufe/das Zeitfenster UND
die Herkunft an BEIDEN Ausgabeorten aus DEMSELBEN Funktionsaufruf mit DERSELBEN
Eingabeliste (`_format_thunder(hourly, ...)` bzw. `_aggregate_day(timeline,
target_date)` fuellt `"thunder"` UND `"thunder_signals"` im selben Dict-Aufbau).
Ein struktureller Guard ist daher nicht noetig — die Kohaerenz wird stattdessen
durch AC-6/AC-7 UND die zugehoerigen Mutationsproben nachgewiesen (s. Testplan),
nicht durch eine Laufzeit-Pruefung im Code.

## Expected Behavior

- **Input:** eine `Trip`/`Stage`-Konfiguration mit Segmenten, deren
  `ForecastDataPoint`s ueber die echte Anreicherung (`thunder_enrichment.enrich_thunder()`)
  unterschiedliche Gewitter-Rohwerte tragen (z. B. eine Stunde mit CAPE oberhalb
  der Leiter, eine andere mit Blitzpotenzial oberhalb derselben Hoechststufe);
  bzw. ein GEWITTER-Kommando gegen einen gespeicherten Wetter-Snapshot mit
  gleicher Eigenschaft.
- **Output:** die Kurzzusammenfassung der Trip-Mail und die Antwort auf das
  GEWITTER-Kommando zeigen neben Zeitfenster bzw. Stufe die tragende(n)
  Zutat(en); Trip-SMS und Premium-SMS zeigen weiterhin nur die Stufe bzw. das
  Zeitfenster, ohne Zutat-Bezeichnung.
- **Side effects:** keine neuen Datenfelder, keine Persistenz-Aenderung — alle
  gelesenen Felder existieren bereits additiv seit Scheibe 1. Der neue Helfer
  `union_of_max_carriers()` ist oeffentlich importierbar und macht
  `WeatherMetricsService._compute_thunder_level_signals()` zu einem duennen
  Wrapper (zeichengleiches Verhalten der bestehenden 11 Bestandstests, die an
  `compute_basis_metrics()` haengen).

## Acceptance Criteria

- **AC-1:** Given die Kurzzusammenfassung der Trip-Mail zeigt ein Gewitterfenster,
  das ausschliesslich ueber eine Zutat (z. B. CAPE) zustande kommt, When die Mail
  gerendert wird, Then lautet der Satz „Gewitter moeglich 14:00–17:00 · CAPE"
  statt nur „Gewitter moeglich 14:00–17:00".
  - Test: `_format_thunder()`/`format_stage_summary()` mit einer Fixture, deren
    Stundenpunkte via echter Anreicherung (`_fuse_thunder_levels`) nur CAPE
    oberhalb der Leiter tragen; Assertion auf den Teilstring „· CAPE" im
    zurueckgegebenen Text.

- **AC-2:** Given die Antwort auf das GEWITTER-Kommando zeigt eine Gewitterstufe,
  die ausschliesslich ueber eine Zutat zustande kommt, When der Nutzer GEWITTER
  sendet, Then lautet die Antwort „⛈ Gewitter heute (13.08.): leicht · CAPE"
  statt nur „... leicht".
  - Test: `_fmt_gewitter()` mit einer Timeline-Fixture, deren Wegpunkte am
    Zieltag nur CAPE-Signale tragen; Assertion auf den Teilstring „· CAPE" in
    der Antwort.

- **AC-3:** Given innerhalb einer Stunde tragen zwei Zutaten gemeinsam die
  Hoechststufe (z. B. CAPE UND Blitzpotenzial erreichen beide „hoch"), When die
  Kurzzusammenfassung gerendert wird, Then werden BEIDE in der
  Katalogreihenfolge aus `THUNDER_SIGNAL_LABEL_DE` genannt („· CAPE,
  Blitzpotenzial") — kein Gewinner wird gekuert.
  - Test: Fixture mit einem Datenpunkt, dessen CAPE- und LPI-Rohwerte beide auf
    die Hoechststufe fuehren; Assertion auf beide Labels in dieser Reihenfolge
    im zurueckgegebenen Text.

- **AC-4:** Given zwei Wegpunkte desselben Kalendertags erreichen die
  Tages-Hoechststufe des GEWITTER-Kommandos ueber verschiedene Zutaten, When der
  Nutzer GEWITTER sendet, Then nennt die Antwort BEIDE Zutaten, nicht nur die
  des zeitlich ersten Wegpunkts.
  - Test: `_aggregate_day()`/`_fmt_gewitter()` mit einer Timeline-Fixture aus
    zwei Wegpunkten desselben `target_date` — Wegpunkt A nur CAPE, Wegpunkt B
    nur Blitzpotenzial, beide auf derselben Hoechststufe; Assertion auf beide
    Labels im zurueckgegebenen Antworttext.

- **AC-5:** Given an der Ankunftsstunde ueberschneiden sich Segment- und
  Nachtfenster mit zwei Datenpunkten, die dieselbe Hoechststufe ueber
  verschiedene Zutaten erreichen, When die Kurzzusammenfassung die Stunden zu
  einem Punkt zusammenfuehrt (`_merge_hour()`), Then traegt der
  zusammengefuehrte Punkt BEIDE Zutaten — nicht nur die des per
  Niederschlag/Boeen gewonnenen Tie-Breaks.
  - Test: `_merge_hour()`/`build_day_window_points()` mit zwei ueberlappenden
    Datenpunkten derselben Ortszeit-Stunde, deren Niederschlags-/Boeenwerte den
    Tie-Break zugunsten des Datenpunkts mit NUR einer der beiden Zutaten
    entscheiden wuerden; Assertion, dass trotzdem beide Zutaten im gerenderten
    Text erscheinen.

- **AC-6:** Given die Kurzzusammenfassung berechnet Zeitfenster UND Herkunft aus
  derselben gefensterten Stundenliste (kein zweiter, unabhaengiger
  Datenzugriff), When eine zusaetzliche Stunde ausserhalb dieser Liste eine
  dritte, abweichende Zutat traegt, Then erscheint diese dritte Zutat NICHT im
  Text.
  - Test: `_format_thunder()` direkt mit einer `hourly`-Liste aufgerufen, die
    bewusst NICHT alle Rohdaten des Segments enthaelt (eine dritte Zutat
    existiert nur ausserhalb der uebergebenen Liste, z. B. in einer separaten
    Segment-Rohzeitreihe); Assertion, dass der Text nur Zutaten aus der
    uebergebenen Liste nennt.

- **AC-7:** Given `_aggregate_day()` berechnet Stufe UND Herkunft des
  GEWITTER-Kommandos aus derselben, nach `target_date` gefilterten
  Wegpunktliste, When ein Wegpunkt eines ANDEREN Kalendertags eine dritte,
  abweichende Zutat traegt, Then erscheint diese dritte Zutat NICHT in der
  Kommando-Antwort.
  - Test: Timeline-Fixture mit einem Wegpunkt ausserhalb `target_date`, der
    eine dritte Zutat traegt; Assertion, dass die Kommando-Antwort nur Zutaten
    von Wegpunkten DES Zieltags nennt.

- **AC-8:** Given die Trip-SMS und die Premium-SMS werden aus demselben Bericht
  wie die E-Mail erzeugt, When der Bericht versendet wird, Then traegt weder
  der `sms_text` noch — ueber den Rueckfallweg `sms_text or email_plain` — die
  tatsaechlich zugestellte SMS/Premium-SMS irgendeine der vier
  Zutat-Bezeichnungen; die Gewitterstufe selbst bleibt dort unveraendert
  sichtbar.
  - Test: `TripReportFormatter` mit einer Fixture, deren Gewittersignale in der
    Kurzzusammenfassung eine Herkunft ausloesen wuerden; Assertion, dass
    `report.sms_text` weder „CAPE" noch „Blitzpotenzial" noch „Blitzdichte" noch
    „Wettercode" enthaelt UND dass `report.sms_text` nicht-leer ist (belegt,
    dass der Rueckfall auf `email_plain` strukturell nicht greift, #868).

- **AC-9:** Given ein bereits gespeicherter Wetter-Schnappschuss OHNE das Feld
  `thunder_level_max_signals` (Alt-Snapshot vor Scheibe 1/2) wird fuer das
  GEWITTER-Kommando geladen, When der Nutzer GEWITTER sendet, Then zeigt die
  Antwort die Gewitterstufe unveraendert, aber OHNE Herkunfts-Zusatz — kein
  „unbekannt", kein leerer Trenner, kein Fehler.
  - Test: `WeatherSnapshotService.load()` mit einem Dict ohne den Schluessel
    deserialisiert; `_fmt_gewitter()` mit der daraus entstehenden Timeline
    aufgerufen; Assertion, dass die Stufe erscheint und kein „·" im Text folgt.

- **AC-10:** Given eine Stunde bzw. ein Tag zeigt „kein" Gewitter (keine Zutat
  erreicht eine Stufe ueber NONE), When die Kurzzusammenfassung bzw. das
  GEWITTER-Kommando gerendert werden, Then bleibt die Ausgabe an BEIDEN Orten
  zeichengleich zu heute — kein Herkunfts-Zusatz; ebenso bleibt die
  unveraenderte GLANCE-Antwort (`_fmt_day_agg`), die denselben
  `_aggregate_day()`-Dict liest, zeichengleich.
  - Test: Fixture ohne jedes Gewittersignal; Assertion, dass `_format_thunder()`
    weiterhin `None` liefert (keine Gewitterzeile), `_fmt_gewitter()` „kein"
    ohne Suffix zeigt, und `_fmt_glance()`/`_fmt_day_agg()` textuell
    unveraendert zur Bestandsfixture bleiben.

## Testplan

**Kern-Schicht** (deterministisch, ohne Netz, echte Fusions-/Aggregations-
/Renderpfade — kein Mock-Theater): eine neue Testdatei
`tests/tdd/test_thunder_origin_trip.py` (nach Verhalten benannt) deckt AC-1 bis
AC-10 ueber die echten Funktionen
(`CompactSummaryFormatter._format_thunder`/`format_stage_summary`,
`TripCommandProcessor._fmt_gewitter`/`_fmt_glance`, `build_day_window_points`/
`_merge_hour`, `WeatherSnapshotService.load`).

**Prueforte=Wirkort, ohne Ausnahme:** jeder AC laeuft mindestens einmal durch
die vollstaendige Kette bis zum zurueckgegebenen Mail-/Kommando-Text. Ein
frueherer Entwurf dieser Spec sah hier eine Ausnahme fuer `aggregate_stage()`
vor (Test auf Funktionsebene statt ueber die Renderkette) — die Ausnahme ist
mit dem Entfernen von `aggregate_stage()` aus dem Scheiben-Umfang hinfaellig
geworden (s. Nicht in dieser Scheibe).

### Pflicht-Mutationsproben (mindestens 3, hier 5)

- **(a) Traegerfilter in `union_of_max_carriers()` entfernen** (Vereinigung ueber
  ALLE Paare statt nur ueber die am Maximum) ⇒ AC-4/AC-5 MUESSEN rot
  werden — ein Wegpunkt/Datenpunkt mit niedrigerer Stufe wuerde faelschlich
  seine Zutat neben der Hoechststufe zeigen.
- **(b) `_merge_hour()`s neuen Override fuer `thunder_level_signals` entfernen**
  (Rueckfall auf `base`s unveraenderten Wert) ⇒ AC-5 MUSS rot werden.
- **(c) `union_of_max_carriers`-Aufruf in `_aggregate_day()` durch
  `points[0].metrics.thunder_level_max_signals` ersetzen** (erstes statt
  vereinigtes Element) ⇒ AC-4 MUSS rot werden.
- **(d) `sms_text = SMSTripFormatter().format_sms(...)` durch `sms_text = ""`
  ersetzen** (simuliert den bisher nie beobachteten leeren Fall) ⇒ AC-8s
  zweite Assertion („nicht-leer") MUSS rot werden — beweist, dass der Test die
  Rueckfall-Kante wirklich prueft, nicht nur behauptet, dass sie nie greift.
- **(e) Herkunfts-Suffix in `_format_thunder()` UND `_fmt_gewitter()`
  auskommentieren** (Aufruf des Helfers entfernen) ⇒ AC-1/AC-2 MUESSEN rot
  werden.

Mutationen ausschliesslich per String-Ersetzung mit externer Sicherungskopie
(kein `git checkout`/`stash`/`reset`, CLAUDE.md-Vorgabe).

## Known Limitations

1. **`sdi_2` (Superzellen) bleibt aussen vor.** Die Fusion hat vier, nicht fuenf
   Zutaten — unveraendert seit Scheibe 1 (dort Known Limitation 1). Diese
   Scheibe erfindet keine fuenfte Zutat.
2. **EU_REST-LPI ist ein ausgewiesener Interim-Wert** (unbelegte Schwelle,
   Feineichung offen als #1678, ADR-0048). Das Label „Blitzpotenzial" nennt NUR,
   welche Zutat die Stufe erreicht hat — keine Aussage ueber die Guete der
   Eichung (ADR-0007). Unveraendert seit Scheibe 1 (dort Known Limitation 2).
3. **GEWITTER-Kommando erreicht ausschliesslich E-Mail und Telegram — belegt,
   nicht angenommen.** `InboundMessage` (die DTO, die Kommandos an den
   `TripCommandProcessor` traegt) hat GENAU ZWEI Erzeuger:
   `inbound_email_reader.py:144` (`channel="email"`) und
   `inbound_telegram_reader.py:222,316` (`channel="telegram"`). Es gibt KEINEN
   SMS- oder Premium-SMS-Kommandopfad — `inbound_sms_reader.py` existiert zwar,
   meldet aber nur die Absendernummer an einen internen Endpunkt fuer den
   Garmin-Ruckkanal (#1676 S1) und erzeugt keine `InboundMessage`. Die Herkunft
   in `_fmt_gewitter()` erreicht damit strukturell GENAU die zwei Kanaele, die
   sie laut PO-Entscheidung tragen duerfen — eine Kanal-Unterscheidung in
   `_fmt_gewitter()` ist NICHT noetig. Doku-Drift: der Docstring
   `trip_command_processor.py:44` (`channel: str  # "email" or "sms"`) ist
   veraltet — tatsaechlich sind es „email" und „telegram".
4. **`_fmt_day_agg()`/GLANCE-Kommando bleibt bewusst unveraendert**, obwohl es
   denselben `_aggregate_day()`-Dict liest wie `_fmt_gewitter()` — der neue
   Schluessel `"thunder_signals"` wird dort nicht gelesen (D3, AC-10).
5. **Restrisiko am SMS-Rueckfallausdruck bleibt bestehen, ist aber gemessen
   praktisch tot.** `report.sms_text or report.email_plain`
   (`notification_service.py:417,433`) wuerde bei leerem `sms_text` die
   Herkunft (als Teil von `email_plain`) an SMS/Premium-SMS durchreichen.
   `sms_text` wird laut #868 IMMER erzeugt (`trip_report.py:441`) — der Zweig
   ist praktisch unerreichbar, aber weiterhin ein Restrisiko, keine
   Unmoeglichkeit (Lehre aus Scheibe 1: „Compare-SMS zeigt Gewitter gar nicht"
   war eine gemessen falsche Annahme). Bewacht durch AC-8 und Mutationsprobe
   (d).
6. **`_deserialize_timeseries()` filtert unbekannte Schluessel nicht**
   (`weather_snapshot.py:301-324`). Unveraendert seit Scheibe 1 (dort Known
   Limitation 5) — unkritisch fuer additive Aenderungen, relevant erst bei
   einem kuenftigen Entfernen eines Feldes.

## Nicht in dieser Scheibe

- **`aggregate_stage()`s Dispatch-Zweig fuer `union_of_max_carriers`**
  (`weather_metrics.py:1164-1267`). Das Kontextdokument UND die urspruengliche
  S1-Notiz (dort Known Limitation 7: „die Scheibe, die die Herkunft auf die
  Trip-Seite bringt, MUSS das zuerst loesen") nahmen an, die Trip-Seite liefe
  ueber `aggregate_stage()`. Gemessen umgehen BEIDE Ausgabeorte dieser Scheibe
  ihn strukturell: die Kurzzusammenfassung liest ausschliesslich `hourly`
  (nicht das `SegmentWeatherSummary`, das `_aggregate()`/`aggregate_stage()`
  liefert), das GEWITTER-Kommando baut sein eigenes Dict direkt aus `points`,
  ohne `aggregate_stage()` je aufzurufen. Die Voraussetzung der S1-Notiz trifft
  fuer diese Scheibe damit NICHT zu — dieselbe Lehre wie AC-12 der
  Vorgaengerscheibe (eine uebernommene Aussage nicht ungeprueft weiterreichen),
  hier auf eine schriftliche Notiz statt auf ein Code-Muster angewendet.
  Tech-Lead-Entscheid: NICHT bauen — ein Aggregations-Zweig fuer einen
  Verbraucher, den es nicht gibt, waere Code ohne Wirkort, und ein Test darauf
  bewachte nichts (derselbe Massstab wie S1 Known Limitation 7). Nach dieser
  Scheibe steht der geteilte Helfer `union_of_max_carriers()` bereit — der
  Anschluss an `aggregate_stage()` ist dann ein Dreizeiler (analog D2/D4 dieser
  Spec) und gehoert in die Scheibe, die den **Mehrtages-Ausblick** bringt: dort
  ist `trip_report_scheduler.py:2020ff` der erste ECHTE Verbraucher. Damit
  bleibt `src/services/stage_weather.py:112` (Go-Cockpit-Spiegel, ruft
  `aggregate_stage()` auf) von dieser Scheibe VOLLSTAENDIG unberuehrt — der
  Blast Radius verkleinert sich entsprechend gegenueber der urspruenglichen
  Planung.
- **Mehrtages-Ausblick** (`email/outlook.py:174-298,353-403,453-537`) —
  Token-Pfad mit getrenntem Tag-/Nachtanteil (#1653), **geteilt mit Compare**.
- **Pill „Metriken-Ueberblick"** (`email/helpers.py:1713-1757`) — **geteilt mit
  Compare**.
- **Gewitter-Vorschau** (`email/html.py:1307-1329`, `email/plain.py:307-332`).
- **Kommando-Timeline je Wegpunkt** (`trip_command_processor.py:903-913`) —
  kompakte Zeile ohne Suffix-Platz.
- **Tages-Aggregatzeile `_fmt_day_agg`** (`trip_command_processor.py:832-843`) —
  liest denselben `agg`-Dict, bekommt aber bewusst keinen Zugriff auf den neuen
  Schluessel (s. Known Limitations 4).
- **Stundentabelle** (`trip_report.py:597-601`, `email/html.py:814-825`).
- **Compare-Stundentabelle** — bereits in Scheibe 1 explizit ausgeschlossen.
- **Go-DTO und Frontend** — kein Frontend-Ort rendert heute eine
  Gewitterstufen-Beschriftung.
- **Risiko-Badges der RiskEngine** (`trip_report.py:902-908`) — eigene Skala
  (`RiskLevel`, nicht `ThunderLevel`).
- **Alarm-Renderer** (`alert/render.py:39-53,324-390`) — gibt die rohe
  Ordinalzahl 0-3 aus, keine Wortdarstellung.
- **Fuenfte Fusions-Zutat, Superzellen (`sdi_2`)** — s. Known Limitations 1.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue) — diese Scheibe wendet ADR-0007 (Daten statt
  Empfehlungen), ADR-0025 (eine Gewitter-Quelle fuer alle Kanaele) und
  ADR-0048 (unbekannte/ungeeichte Herkunft = keine Aussage) an, ohne eine davon
  zu aendern.
- **Rationale:** Additive Sichtbarmachung einer bereits vorhandenen internen
  Groesse (welche Zutat trug) an zwei weiteren Ausgabeorten, plus das
  Herausloesen einer bereits existierenden Aggregationsregel in einen geteilten
  Helfer — kein neues Architekturprinzip, keine neue Datenquelle, kein neuer
  Kanal, keine neue Persistenz-Strategie. Kein Bezug zu ADR-0034
  (Herkunfts-Fusszeile/Datenquelle) — andere Dimension, s. Scheibe 1s
  Architektur-Entscheidung fuer die Abgrenzung.

## Changelog

- 2026-08-12: Initial spec created (Issue #1680, Scheibe 2). Grundlage:
  `docs/context/feat-1680-s2-herkunft-trip.md`, PO-Entscheid zum Umfang der
  Scheibe (zwei Ausgabeorte + geteilter Helfer) vom 2026-08-12.
- 2026-08-12 (Korrektur nach Review, vor Freigabe): `aggregate_stage()` aus dem
  Scheiben-Umfang entfernt (Tech-Lead-Entscheid — beide Ausgabeorte umgehen ihn
  strukturell, kein Wirkort in dieser Scheibe, s. Nicht in dieser Scheibe); AC-4
  (alt, aggregate_stage-Test) ersatzlos gestrichen, verbleibende ACs neu
  durchnummeriert (AC-1..AC-10), Mutationsprobe (d) (alt) entfernt und die
  uebrigen umgelabelt. GEWITTER-Kommando-Kanalbefund korrigiert:
  `InboundMessage` hat genau zwei Erzeuger (E-Mail, Telegram) —
  `inbound_sms_reader.py` existiert, ist aber kein Kommando-Reader (Garmin-
  Ruckkanal, #1676 S1); Docstring-Drift `trip_command_processor.py:44`
  (`"email" or "sms"`) vermerkt. D5 (`_format_thunder()`-Herkunft = Spitzenstufe
  des Zeitfensters, vormals D6) als bewusste Tech-Lead-Entscheidung mit
  verworfener Alternative (Vereinigung ueber alle Gewitterstunden im Fenster)
  festgehalten.
