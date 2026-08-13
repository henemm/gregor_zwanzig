---
entity_id: feat_1680_s5a_gewitter_herkunft_ausblick
type: feature
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [thunder, trip, compare, telegram, outlook, adr-0007, adr-0025, issue-1680, issue-1419]
---

<!-- Issue #1680, Scheibe 5a (Mehrtages-Ausblick). Vorgaenger: S1 Ortsvergleich
     (live 2026-08-12), S2 Trip-Kurzzusammenfassung + GEWITTER-Kommando (live
     2026-08-12), S3 vier weitere Orte (live 2026-08-13), S4 Trip-Stundentabelle
     (live 2026-08-13). Nachfolger: S5b (Gewitter-Vorschau) konsumiert den hier
     entstehenden Zeilen-Vertrag. Bezug: Epic #1419 Rang 4, Entscheidung E1.
     Grundlage: PFLICHTLEKTUERE docs/context/feat-1680-s5-ausblick-vorschau-herkunft.md
     (vor dieser Spec gemessen, inkl. vier Explore-Laeufen und einer unabhaengigen
     Bewertung). -->

# Gewitter: Herkunft der Stufe im Mehrtages-Ausblick sichtbar machen (#1680 Scheibe 5a)

## Approval

- [ ] Approved

## Purpose

Seit den Scheiben 1–4 nennen acht Ausgabeorte neben der fusionierten
Gewitterstufe die tragende Zutat (`leicht · CAPE`). Der **Mehrtages-Ausblick**
— die Tabelle „Nächste Etappen" mit einer Zeile je künftiger Etappe — ist
einer der beiden letzten Orte ohne Herkunft. Er zeigt heute
`leicht @16 · nachts hoch @0` und lässt offen, worauf die Einstufung beruht.

Das ist genau dort besonders folgenreich, wo der Ausblick hingehört: Er zeigt
**drei verschiedene Tage an drei verschiedenen Orten** untereinander. Stufen
aus verschiedenen Gebieten und Modellen stehen damit unmittelbar nebeneinander
und suggerieren eine Vergleichbarkeit, die ohne Herkunftsangabe nicht gegeben
ist — dieselbe Begründung, die das Issue für den Ortsvergleich nennt
(Gesamtkonzept Abschnitt 4/4.1).

Die Herkunft nennt weiterhin nur die Zutat, keine Bewertung und keine
Handlungsempfehlung (ADR-0007).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core
> (`src/output/renderers/`). Kein Frontend, keine Go-Beteiligung, kein neuer
> Endpoint, keine neuen Persistenz-Felder. Der Zeitplaner
> (`trip_report_scheduler.py`) wird in dieser Scheibe **nicht** angefasst —
> siehe „Am Code gemessen", Punkt 2.

- **File:** `src/output/renderers/email/outlook.py`
  - `build_outlook_row()` (Z. 415–520) — baut heute `hourly_thunder` als
    `HourlyValue`-Tupel aus den rohen `points` (Z. 463–477) und wirft dabei
    `dp.thunder_level_signals` weg. Hier entsteht das neue, optionale
    Trägerfeld. Additiv-Filter `row.update({k: v for k, v in optional.items()
    if v is not None})` (Z. 517) ist die vorhandene Naht.
  - `render_outlook_table()` — HTML-Gewitterzelle (Z. 233–265)
  - `render_outlook_plain()` — Klartext-Gewitterfeld (Z. 358–397)
- **File:** `src/output/renderers/email/helpers.py` — `format_trend_tokens()`
  (Z. 897–1045), Tag-/Nacht-Aufteilung am Tagesfenster (Z. 1005–1020). **Hier**
  entsteht der Herkunfts-Token, weil hier auch `thunder_day_token` entsteht —
  eine Fensterauflösung, nicht zwei (s. AC-9).
- **File:** `src/output/renderers/narrow.py` — Telegram-Trendblock
  `_outlook_lines()` (Z. 570–599), liest `thunder_day_token`/
  `thunder_night_token` (Z. 588–589), Breite `_TG_PROSE_WIDTH = 56` mit
  Wort-Umbruch.
- **File:** `src/output/metric_format.py` — `union_of_max_carriers()`
  (Z. 559–609) und `THUNDER_SIGNAL_LABEL_DE` (Z. 374–379), beide unverändert
  wiederverwendet.

## Wortlaut (freigabepflichtig)

Die Herkunft steht **unmittelbar hinter der Tagesstufe**, mit demselben
Trenner `" · "` wie in den Scheiben 1–4. Bei mehreren tragenden Zutaten werden
sie mit `", "` verbunden — ebenfalls wie in den Vorgängerscheiben.

| Fall | HTML-Zelle | Klartext | Telegram |
|---|---|---|---|
| nur Tag | `leicht @16 · CAPE` | `⚡leicht · CAPE` | `⚡leicht@16 · CAPE` |
| Tag + Nacht | `leicht @16 · CAPE · nachts hoch @0` | `⚡leicht · CAPE · nachts hoch @0` | `⚡leicht@16 · CAPE · nachts hoch @0` |
| Tag + Nacht + Hagel | `leicht @16 · CAPE · nachts hoch @0 · Hagel: ja` | dito + ` · Hagel: ja` | (Telegram führt keinen Hagel-Zusatz) |
| zwei Zutaten | `leicht @16 · CAPE, Blitzdichte` | `⚡leicht · CAPE, Blitzdichte` | `⚡leicht@16 · CAPE, Blitzdichte` |
| nur Nacht | `nachts hoch @0` (**unverändert, ohne Herkunft**) | dito | dito |
| kein Gewitter | `–` (**unverändert**) | `⚡–` (**unverändert**) | unverändert |

**Der Nachtteil bekommt bewusst KEINE Herkunft** (AC-6). Begründung: Der
Trenner `·` trägt in dieser Zelle bereits zwei Bedeutungen (Tag/Nacht-Trennung
und Hagel-Zusatz). Eine eigene Nachtherkunft brächte bis zu **vier** Trenner
mit **drei** Bedeutungen in eine Zelle, die unter Zeitdruck gelesen wird —
CLAUDE.md-Leitprinzip „Lesbarkeit schlägt Vollständigkeit". Die Asymmetrie ist
zudem bereits etabliert: Die Vorschau liefert `level`/`hour` ohnehin nur für
das Tagesfenster (ADR-0025), der Nacht-Halbsatz trägt schon heute keine
eigenen Strukturdaten.

## Acceptance Criteria

- **AC-1:** Given eine künftige Etappe, deren Tages-Gewitterstufe im
  Tagesfenster von genau einer Zutat getragen wird / When die HTML-Ausblick-
  Tabelle der Trip-Vollmail gerendert wird / Then steht in der Gewitter-Spalte
  dieser Zeile die Stufe mit Uhrzeit, gefolgt von `" · "` und der deutschen
  Bezeichnung der Zutat (z. B. `leicht @16 · CAPE`).

- **AC-2:** Given dieselbe Etappe / When der Klartext-Ausblick derselben Mail
  gerendert wird / Then trägt das Gewitterfeld denselben Zusatz im selben
  Wortlaut (`⚡leicht · CAPE`) — der Klartext führt wie bisher keine
  Tagesuhrzeit.

- **AC-3:** Given dieselbe Etappe / When der Telegram-Trendblock gerendert wird
  / Then nennt auch er die Zutat hinter der Tagesstufe. Der Inhalt muss im
  selben Ausblick-Block stehen, nicht zwingend als zusammenhängender
  Teilstring — die Breite von 56 Zeichen darf umbrechen.

- **AC-4:** Given eine Etappe, deren Höchststufe im Tagesfenster von **zwei**
  Zutaten gleichzeitig getragen wird / When der Ausblick gerendert wird / Then
  werden **beide** Zutaten genannt, mit `", "` verbunden, in stabiler
  Reihenfolge (Auslegung (ii): alle tragenden Signale, kein Gewinner gekürt).

- **AC-5:** Given eine Etappe mit Gewitter **und** Hagel-Kennzeichen / When der
  Ausblick gerendert wird / Then steht die Herkunft **vor** dem Hagel-Zusatz,
  und der Hagel-Zusatz bleibt wortgleich erhalten
  (`leicht @16 · CAPE · Hagel: ja`).

- **AC-6:** Given eine Etappe mit Gewitter **im Nachtfenster** / When der
  Ausblick gerendert wird / Then trägt der Nachtteil **keine** Herkunft, und
  der Nachtteil bleibt gegenüber heute zeichengleich. Gegenprobe an derselben
  Fixture: Läge dasselbe Gewitter im Tagesfenster, erschiene die Herkunft sehr
  wohl — der Test darf nicht vakuum-grün sein.

- **AC-7:** Given eine Etappe **ohne** Gewitter im Tagesfenster / When der
  Ausblick gerendert wird / Then enthält die Gewitterzelle **weder** eine
  Zutat-Bezeichnung **noch** einen zusätzlichen `·`-Trenner — sie bleibt
  zeichengleich zu heute (`–` bzw. `⚡–`).

- **AC-8:** Given Ausblick-Zeilen, die **keine** Trägerinformation führen
  (Alt-Aufrufer, aufgezeichnete Fixtures) / When HTML- und Klartext-Ausblick
  gerendert werden / Then ist die Ausgabe **byte-identisch** zu heute. Nachweis
  ist der unveränderte Bestandswächter `tests/tdd/test_trip_outlook_parity.py`,
  der grün bleiben MUSS, ohne dass seine Golden-Dateien angefasst werden.

- **AC-9:** Given ein Trip mit einem vom Standard **abweichenden** Tagesfenster
  (nicht 4–19 Uhr) und einem Gewitter, das nur in diesem abweichenden Fenster
  liegt / When der Ausblick gerendert wird / Then stammen angezeigte Stufe
  **und** angezeigte Herkunft aus demselben Fenster — die Herkunft wird an
  derselben Stelle und mit demselben Fensterwert ermittelt wie
  `thunder_day_token`.

- **AC-10:** Given eine Etappe, deren Wetterpunkte eine Gewitterstufe tragen,
  für die **keine** Trägerliste vorliegt (z. B. aufgezeichneter Schnappschuss
  vor Scheibe 1) / When der Ausblick gerendert wird / Then erscheint die Stufe
  **ohne** Herkunft — nie eine Herkunft, die nicht zur gezeigten Stufe gehört
  (AC-12-Regel aus Scheibe 1).

- **AC-11:** Given einen Ortsvergleich mit aktivem Ausblick / When dessen
  Ausblick-Tabelle gerendert wird / Then nennt auch sie die Herkunft — der
  geteilte Zeilenbau wird **nicht** trip-seitig abgeschaltet
  (Trip/Compare-Teilungs-Invariante).

- **AC-12:** Given einen Trip-Briefing-Versand über SMS bzw. Premium-SMS /
  When der Text erzeugt wird / Then enthält er **keine** der vier
  Zutat-Bezeichnungen. Nachweis per Sonde (Beschriftungsfunktion zur Laufzeit
  markieren), nicht per Wortsuche — mit Gegenprobe, dass die Sonde in E-Mail
  und Telegram anschlägt.

- **AC-13:** Given ein Trip-Briefing im **Kompaktformat** / When die Mail
  gerendert wird / Then bleibt deren Ausblick-Block („Naechste Etappen")
  zeichengleich zu heute — er liest `thunder_plain` und wird von dieser
  Scheibe nicht berührt.

## Am Code gemessen (korrigiert gegenüber den Vorgängerscheiben)

**1. Die Stufe im Ausblick kommt NICHT aus `aggregate_stage()`.** S1–S4 haben
weitergereicht, der Mehrtages-Ausblick sei „der erste echte Verbraucher" dieses
Aggregators. Gemessen: `aggregate_stage()` läuft dort zwar
(`trip_report_scheduler.py:2026`), aber die **angezeigte** Stufe stammt aus den
Stundenproben im Tagesfenster (`outlook.py:234-243`, `helpers.py:1013-1017`).
Das Aggregat speist nur `row["thunder"]` — und das dient ausschließlich einem
Notnagel-Zweig.

**2. Dieser Notnagel-Zweig ist in BEIDEN Produktivpfaden unerreichbar** —
bewiesen, nicht vermutet:
- `aggregate_stage()` aggregiert ausschließlich Segmente mit `has_error=False`
  (`weather_metrics.py:1194-1197`).
- Von den drei Konstruktionen einer `SegmentWeatherData` tragen die beiden mit
  `timeseries=None` **immer** `has_error=True` (`segment_weather.py:158-166`,
  `:205-213`); die einzige mit `has_error=False` hat **immer** eine Zeitreihe
  (`:283-289`).
- `_flat_points` sammelt aus allen Segmenten mit Zeitreihe
  (`trip_report_scheduler.py:2046-2049`) — enthält also die Punkte jedes
  aggregierten Segments.
- `_compute_thunder_level()` (`weather_metrics.py:605-607`) und der
  Stundenreihen-Bau (`outlook.py:471`) filtern mit **derselben** Bedingung
  `dp.thunder_level is not None`.
- Folge: „Aggregat trägt eine Stufe" ⟹ „Stundenreihe ist nicht leer". Der Zweig
  verlangt beides gegenteilig gleichzeitig und ist damit unerreichbar. Im
  Compare-Pfad ist die Punktmenge ohnehin identisch
  (`compare_html.py:1164-1168`).

**Konsequenz:** Der in `aggregation_config` (`weather_metrics.py:478`)
deklarierte, aber in `aggregate_stage()` **nicht implementierte** Zweig
`union_of_max_carriers` bleibt auch in dieser Scheibe ohne erreichbaren
Verbraucher. Ihn hier zu ergänzen wäre Code ohne Wirkort — genau der Fehler,
den Scheibe 2 bewusst vermieden hat. Er bleibt Known Limitation, **aber ab
sofort mit Beweiskette statt mit Vermutung** (s. Known Limitations 1).

**3. Der Zeitplaner darf `union_of_max_carriers` nicht importieren.** Eine
Architektur-Wache (`tests/unit/test_notification_service.py:183-192`) erlaubt
in `trip_report_scheduler.py` **zeilengenau einen** Import aus der
Darstellungsschicht (`build_outlook_row`). Die Berechnung gehört deshalb in
die Darstellungsschicht — was ohnehin der richtige Ort ist (Punkt 4).

**4. Die Trägerinformation geht nicht verloren, sie wird weggeworfen.**
`build_outlook_row()` bekommt die rohen `ForecastDataPoint`s und verengt sie
**selbst** zu `HourlyValue` (nur `hour`/`value`). `dp.thunder_level_signals` ist
dort verfügbar (gesetzt in `thunder_enrichment.py:151`, unter **derselben**
Bedingung wie die Stufe selbst). Eine Änderung an `HourlyValue` ist **nicht**
nötig — die in S3/S4 notierte „strukturelle Blockade" bestand nur eine Zeile zu
spät.

**5. Die Anreicherung läuft auf dem Ausblick-Pfad ohne Schalter**
(`openmeteo.py:1198-1204`, bewusst nicht an `enrich_ensemble` gekoppelt).
Diese Scheibe verursacht **keine** zusätzlichen Netzabrufe — sie liest ein Feld,
das ohnehin gefüllt wird (relevant für Kontingent #1329).

**6. SMS erreicht der Ausblick strukturell nicht.** SMS und Premium-SMS bauen
ihren Text über `SMSTripFormatter` und sehen `multi_day_trend` nie. Der Token
`thunder_sms` aus `format_trend_tokens()` wird **nirgends** gelesen. AC-12 ist
damit eine strukturelle Zusicherung, kein Balanceakt.

**7. Die Kompakt-Mail erbt nicht mit.** Sie liest ausschließlich
`thunder_plain` (`compact.py:234`) und faltet ihren Text nach ASCII
(`_ascii()`), was den Trenner `·` ohnehin zerstörte. Daher AC-13 als
Abwesenheits-Zusicherung.

**8. Die aus S4 übernommene Telegram-Breite von 32 Zeichen gilt hier nicht.**
Der Trendblock nutzt `_TG_PROSE_WIDTH = 56` mit Wort-Umbruch
(`narrow.py:53`); die 32 (`_TG_TABLE_WIDTH`) gehören der Stundentabelle aus S4.

## Implementation Details

1. **`build_outlook_row()` reicht die Träger je Stunde durch, fertig
   berechnet wird nichts.** Parallel zu `hourly_thunder` entsteht ein
   optionales Feld mit `(Stunde, Stufe, Trägerliste)` je Punkt, der eine
   Gewitterstufe trägt. Es wird **nur gesetzt, wenn mindestens ein Punkt eine
   Trägerliste hat** — über den vorhandenen `optional`-Filter (Z. 517). Damit
   bleibt der Bestandstest `test_build_outlook_row_without_selection_is_unchanged`
   grün, ohne ihn anzufassen.

2. **Die Fensterfilterung und die Vereinigung passieren in
   `format_trend_tokens()`** — an **derselben** Stelle, an der auch
   `thunder_day_token` entsteht (`helpers.py:1005-1020`), mit **demselben**
   `win_start`/`win_end`. Das ist die einzige Konstruktion, die AC-9
   strukturell erfüllt statt durch Disziplin; zwei unabhängige
   Fensterauflösungen wären genau die Fehlerklasse aus #1653/#1498.

3. **Vereinigt wird über den vorhandenen Baustein**
   `union_of_max_carriers((stufe, träger) …)` (`metric_format.py:559`) über die
   Stunden **im Tagesfenster**. Er liefert selbst `None` statt `[]`, wenn keine
   Träger vorliegen — kein Sonderfall nötig. Damit gilt AC-10 aus eigener Kraft
   der Funktion (die in S2 als Finding F001 nachgehärtete Garantie).

4. **Ergebnis ist ein neuer Token** (fertiger Zusatztext oder `None`), den die
   drei Renderer an derselben Stelle anhängen, an der sie heute schon den
   Tagesteil bauen. Die Zeichensetzung bleibt je Kanal die vorhandene.

5. **Neue Testdatei** `tests/tdd/test_thunder_origin_outlook.py` — nach
   Verhalten benannt, nicht nach Issue-Nummer (Namensregel).

## Was sich NICHT ändern darf

- `tests/tdd/test_trip_outlook_parity.py` **und seine Golden-Dateien** bleiben
  unangetastet und grün (AC-8). Wird dieser Wächter rot, ist das der Befund —
  nicht ein veralteter Referenzstand.
- `tests/golden/email/test_outlook_thunder_day_night_golden.py` bleibt grün und
  seine Golden-Datei unangetastet (Fixture führt keine Träger).
- `HourlyValue` (`src/output/tokens/dto.py:15-18`) bleibt unverändert.
- `aggregate_stage()` bleibt unverändert (s. „Am Code gemessen", Punkt 2).
- `src/services/trip_report_scheduler.py` wird **nicht** angefasst.
- Die Kompakt-Mail bleibt zeichengleich (AC-13).
- SMS und Premium-SMS bleiben ohne Herkunft (AC-12).
- Der Nachtteil bleibt zeichengleich (AC-6).

## Test-Strategie

Kern-Schicht, deterministisch: echte Renderkette bis zum zurückgegebenen
String, keine Mocks. Jeder Abwesenheits-AC (AC-6, AC-7, AC-10, AC-12, AC-13)
trägt eine **Gegenprobe an derselben Fixture**, die belegt, dass die Herkunft
dort überhaupt entstünde — sonst bewacht er nichts (Muster aus S1–S4).

### Pflicht-Mutationen (Gegenprobe, keine Kür)

Jede Mutation nur per String-Ersetzung mit externer Sicherungskopie — **nie**
`git checkout`/`stash`/`reset`.

- **(a)** Herkunft an den **Nacht**teil statt an den Tagesteil hängen → AC-6
  muss rot werden.
- **(b)** Fensterfilterung für die Träger entfernen (ganzer Kalendertag) →
  AC-9 muss rot werden.
- **(c)** `union_of_max_carriers` durch „erste Trägerliste" ersetzen → AC-4
  muss rot werden.
- **(d)** Trägerliste auch bei Stufe ohne passende Träger anhängen → AC-10 muss
  rot werden.
- **(e)** Feld bedingungslos setzen statt nur bei vorhandenen Trägern → der
  Bestandstest `test_build_outlook_row_without_selection_is_unchanged` muss rot
  werden (Beleg, dass AC-8 nicht durch Zufall grün ist).
- **(f)** Herkunft **vor** statt hinter der Uhrzeit einfügen → AC-1 muss rot
  werden.
- **(g)** Herkunfts-Zusatz zusätzlich in die Kompakt-Mail hängen → AC-13 muss
  rot werden.

Kommt eine Mutation durch, ist das ein Finding, kein Nebenbefund.

## Known Limitations

1. **`aggregate_stage()` bleibt unangeschlossen — jetzt mit Beweis.** Der in
   `aggregation_config` deklarierte Zweig `union_of_max_carriers` ist weiterhin
   nicht implementiert (`weather_metrics.py:1265-1266`, `else: values[0]`). Bei
   einer Etappe mit mehreren Segmenten lieferte er die Trägerliste des
   **ersten** Segments statt der Vereinigung. Erreichbar ist dieser Wert heute
   **nur** über den in „Am Code gemessen" Punkt 2 als unerreichbar bewiesenen
   Notnagel-Zweig. Bleibt gebucht (#1199); ein Fix braucht zuerst einen echten
   Verbraucher.
2. **Der Nachtteil trägt nie eine Herkunft** (AC-6, bewusst). Reine
   Nachtgewitter-Tage zeigen damit keine Zutat.
3. **`sdi_2` (Superzellen) bleibt außen vor** — die Fusion hat vier Zutaten,
   nicht fünf (unverändert seit S1).
4. **EU_REST-LPI bleibt ein ausgewiesener Interim-Wert** (#1678, ADR-0048),
   unverändert seit S1.
5. **Telegram erbt den Zusatz strukturell** (wie S4): Wer künftig den
   Tages-Token ändert, ändert Telegram mit. Ein eigener Kanal-Schalter existiert
   bewusst nicht.
6. **Ein Zeilenumbruch im Telegram-Trendblock ist hinnehmbar** (56 Zeichen,
   Wort-Umbruch) — kein Datenverlust, s. AC-3.

## Nicht in dieser Scheibe

- **Gewitter-Vorschau** — folgt als **Scheibe 5b**; sie konsumiert den hier
  entstehenden Zeilen-Vertrag über beide ihrer Pfade
  (`_thunder_entry_from_trend_row` primär, `_build_thunder_forecast` als
  Rückfall).
- **`aggregate_stage()`s Dispatch-Zweig** — s. Known Limitations 1.
- **Eine eigene Herkunft für den Nachtteil** — s. AC-6, bewusste
  Produktentscheidung.
- **Go-DTO und Frontend** — ersatzlos, kein Verbraucher (unverändert seit S3).
- **Kompakt-Mail** — s. AC-13.
