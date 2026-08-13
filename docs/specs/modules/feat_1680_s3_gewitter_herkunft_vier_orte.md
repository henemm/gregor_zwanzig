---
entity_id: feat_1680_s3_gewitter_herkunft_vier_orte
type: feature
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [thunder, trip, compare, adr-0007, adr-0025, adr-0048, issue-1680, issue-1419]
---

<!-- Issue #1680, Scheibe 3 (vier weitere Ausgabeorte). Vorgaenger: Scheibe 1
     (Ortsvergleich, live seit 2026-08-12) und Scheibe 2 (Trip-Kurzzusammenfassung
     + GEWITTER-Kommando, live seit 2026-08-12, Merge bacc6f29). Bezug: Epic #1419
     Rang 4, Entscheidung E1. Grundlage: PFLICHTLEKTUERE
     docs/context/feat-1680-s3-herkunft-vier-orte.md (gemessen 2026-08-13),
     PO-Entscheid zum Umfang dieser Scheibe (2026-08-13). -->

# Gewitter: Herkunft der Stufe an vier weiteren Ausgabeorten (#1680 Scheibe 3)

## Approval

- [x] Approved — PO-Freigabe „go" am 2026-08-13 auf die sechzehn Akzeptanzkriterien

## Purpose

Seit Scheibe 1 (Ortsvergleich-Tagesuebersicht) und Scheibe 2 (Trip-Kurzzusammenfassung,
GEWITTER-Kommando) zeigen zwei Ausgabeorte neben der fusionierten Gewitterstufe die
tragende(n) Zutat(en). An vier weiteren, vom PO ausgewaehlten Stellen fehlt die
Angabe noch: der Pille im Metriken-Ueberblick der Trip-Mail, der Kommando-Timeline
je Wegpunkt, der GLANCE-Tageszeile und der Ortsvergleich-Stundentabelle. Bei allen
vieren liegt die Zutat bereits als Datenfeld vor — keiner braucht ein neues Feld,
einen strukturellen Umbau oder den Aggregationsweg `aggregate_stage()`, der seit
Scheibe 2 bewusst unangeschlossen bleibt. Die Herkunft nennt weiterhin nur die
Zutat, keine Bewertung und keine Handlungsempfehlung (ADR-0007).

**Diese Scheibe dreht eine Entscheidung aus Scheibe 2 ausdruecklich um.** Scheibe 2
legte fest (dortige Spec D3, Known Limitation 4), die GLANCE-Tageszeile bleibe
"bewusst zeichengleich" — sie liest den seit Scheibe 2 im Aggregat vorhandenen
Schluessel `"thunder_signals"` (`trip_command_processor.py:834-839`) absichtlich
nicht. Der zugehoerige Kommentar (`trip_command_processor.py:832-833`) haelt das
wörtlich fest: "Nur `_fmt_gewitter()` liest den Schluessel; `_fmt_day_agg()`
/GLANCE bleibt bewusst zeichengleich (Spec D3, Known Limitation 4)." Der PO hat
diese Entscheidung am 2026-08-13 bewusst abgeloest — GLANCE zeigt die Herkunft ab
dieser Scheibe genauso wie das GEWITTER-Kommando. Kommentar und Docstring-Verweis
sind im Aenderungssatz zwingend nachzuziehen (s. Implementation Details D3);
ebenso der Docstring-Hinweis in `compare_html.py:215-220`, der die
Compare-Stundentabelle noch als bewusst unveraendert beschreibt (AC-11 aus
Scheibe 1) — beide Notizen wuerden sonst das Gegenteil des neuen Codes behaupten.
Genau diese Fehlerklasse — eine stehengebliebene Notiz, die eine erledigte oder
abgeloeste Entscheidung falsch darstellt — fuehrte in Scheibe 2 bereits einmal zum
Streichen eines ganzen Arbeitspunkts (dort: die urspruengliche S1-Notiz zu
`aggregate_stage()`).

## Source

> **Schicht-Hinweis:** ausschliesslich Python-Core (`src/output/renderers/email/`,
> `src/output/renderers/comparison.py`, `src/services/trip_command_processor.py`).
> Kein Frontend, keine Go-Beteiligung, kein neuer Endpoint, keine neuen
> Persistenz-Felder — reine Renderlogik an vier bestehenden Andockstellen.

- **File:** `src/output/renderers/email/helpers.py` — `_pill_for_metric()`,
  thunder-Zweig (Z. 1713-1757), gespeist von `build_metrics_summary_pills()`
  (Z. 1815-1881, Aufruf `build_day_window_points()` Z. 1861-1864)
- **File:** `src/services/trip_command_processor.py`:
  - `_fmt_timeline()` (Z. 908-939), Gewitterzeile Z. 933-937
  - `_fmt_day_agg()` (Z. 844-854) — GLANCE, liest ab dieser Scheibe
    `agg.get("thunder_signals")`
  - `_aggregate_day()` (Z. 804-842) — Berechnung existiert bereits seit
    Scheibe 2 (Z. 834-839); **nur** der irrefuehrende Kommentar Z. 832-833 wird
    korrigiert, keine Logikaenderung an dieser Stelle
- **File:** `src/output/renderers/email/compare_html.py` — `_render_hour_row()`
  (Z. 962-998, Aufrufstelle Z. 982-983); Docstring-Korrektur an `_fmt_thunder()`
  (Z. 204-233, insbesondere Z. 215-220)
- **File:** `src/output/renderers/comparison.py` — Klartext-Stundenschleife in
  `render_comparison_text()` (Z. 143-341, betroffene Zeilen 322-341, insbesondere
  329-333)
- **Nur Kommentar, keine Logikaenderung:** `src/services/notification_service.py`
  — Kommentare Z. 413-422 (SMS) / Z. 434-441 (Premium-SMS) erwaehnen bereits den
  Rueckfall `sms_text or email_plain`; nachzutragen ist, dass ab dieser Scheibe
  auch Pillen- und GLANCE-Text potenziell betroffener Inhalt sind. Die
  eigentlichen Aufrufstellen liegen bei Messung (2026-08-13) auf Z. 428 (SMS) und
  Z. 446 (Premium-SMS) — die Scheibe-2-Notiz "`:417,433`" referenzierte den
  erklaerenden Kommentar, nicht den Aufruf selbst; Zeilen haben sich seither
  verschoben.
- **Identifier:** `output.renderers.email.helpers._pill_for_metric()`,
  `services.trip_command_processor.TripCommandProcessor._fmt_timeline()`,
  `services.trip_command_processor.TripCommandProcessor._fmt_day_agg()`,
  `output.renderers.email.compare_html._render_hour_row()`,
  `output.renderers.comparison.render_comparison_text()`

## Estimated Scope

- **LoC:** ~70-110 Quellcode (vier duenne, additive Andockstellen + zwei
  Kommentar-/Docstring-Korrekturen, keine neuen Funktionen) + geschaetzt
  ~220-320 Tests (16 ACs quer ueber vier strukturell verschiedene Ausgabeorte,
  jeweils Pruefort=Wirkort bis zum zurueckgegebenen Text) ⇒ Gesamt ~290-430.
  **Schaetzung, keine Messung** — analog Scheibe 1/2 (dort waren fruehere
  Schaetzungen zu optimistisch) ist ein `loc_limit_override` gegen das
  250-Zeilen-Limit voraussichtlich noetig, in der RED-Phase neu zu pruefen.
- **Files:** 5 Quelldateien (s. Source; `notification_service.py` nur
  Kommentar) + 0 neue Testdateien — Erweiterung der bestehenden, nach Verhalten
  benannten Module `tests/tdd/test_thunder_origin_trip.py` (Pille, Timeline,
  GLANCE) und `tests/tdd/test_thunder_origin_compare.py` (Stundentabelle),
  Vorbild Scheibe 1/2. Keine dritte, issue-nummerierte Testdatei.
- **Effort:** medium. Additiv, kein Breaking Change, kein Frontend, keine neue
  Persistenz — alle vier Felder existieren bereits seit Scheibe 1/2. Das Risiko
  liegt (a) im Nachweis der Kohaerenz je Ort einzeln (vier strukturell
  verschiedene Aggregationsebenen: Stundenwerte, ein Datenpunkt,
  Segment-Aggregat, Tages-Aggregat) und (b) im vollstaendigen Nachziehen der
  zwei jetzt falschen Kommentare/Docstrings (Lehre aus Scheibe 2).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1680-s3-herkunft-vier-orte.md` | GRUNDLAGE (gemessen) | Belege, Messwerte, PO-Entscheidungen dieser Spec sind daraus uebernommen |
| `docs/specs/modules/feat_1680_s2_gewitter_herkunft_trip.md` | VORGAENGER | Aufbau/Detailgrad; legt die jetzt ausdruecklich abgeloeste GLANCE-Entscheidung fest (dortige D3, Known Limitation 4) |
| `docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md` | VORGAENGER | AC-12-Lehre (Kohaerenz), `_fmt_thunder`-Docstring-Hinweis (Z. 215-220, hier zu korrigieren), AC-11 (Compare-Stundentabelle "bleibt unveraendert" — hier ebenfalls abgeloest) |
| ADR-0007 (`docs/adr/0007-daten-statt-empfehlungen.md`) | ZUSAGE | Herkunfts-Label ist Beschreibung, keine Bewertung |
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | ZUSAGE | Eine Gewitter-Quelle fuer alle Kanaele — diese Scheibe erweitert additiv, baut keine zweite Fusion |
| ADR-0048 (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`) | KONTEXT | Unbekannte/ungeeichte Herkunft ist keine Aussage ueber die Guete der Eichung |
| `src/output/metric_format.py:559-609` (`union_of_max_carriers()`) | ZUSAGE (S2) | Garantiert seit S2-Finding F001 SELBST, dass Stufe `NONE` auf `None` fuehrt — diese Scheibe importiert nur, sichert nicht erneut ab |
| `src/output/metric_format.py:374-390` (`THUNDER_SIGNAL_LABEL_DE`, `thunder_signal_label()`) | ZUSAGE (S1) | Deutscher Wortkatalog, Katalogreihenfolge wettercode/blitzdichte/cape/blitzpotenzial |
| `src/app/models.py:204` (`ForecastDataPoint.thunder_level_signals`), `:430` (`SegmentWeatherSummary.thunder_level_max_signals`) | ZUSAGE (S1) | Beide Felder existieren bereits additiv, `list[str]` |
| `src/services/trip_command_processor.py:804-842` (`_aggregate_day()`) | ZUSAGE (S2) | `"thunder_signals"` steht bereits im Rueckgabe-Dict — GLANCE liest denselben Schluessel, keine neue Berechnung |
| `src/output/renderers/email/compare_html.py:204-233` (`_fmt_thunder()`) | ZUSAGE (S1) | Dritter Parameter `signals` existiert bereits seit Scheibe 1 — diese Scheibe uebergibt ihn an zwei weiteren Aufrufstellen, aendert den Funktionsrumpf NICHT |
| `.claude/hooks/renderer_mail_gate.py` | WAECHTER | greift fuer `helpers.py` (SHARED_HELPER-Muster — verlangt BEIDE Nachweise, `briefing_mail_validator.py` UND `email_spec_validator.py`, weil die Datei von Trip- UND Compare-Renderern importiert wird) und fuer `compare_html.py` (COMPARE-Muster — verlangt `email_spec_validator.py`). Greift GEMESSEN NICHT fuer `comparison.py` und NICHT fuer `trip_command_processor.py` — keines der vier Pattern-Sets (`_MAIL_PATTERNS`, `_COMPARE_PATTERNS`, `_SHARED_HELPER_PATTERNS`, `_RADAR_PATTERNS`) trifft diese Pfade |
| `.claude/hooks/touched_tests_gate.py` (#1481 A) | WAECHTER | einziger Commit-Gate-Schutz fuer `comparison.py`/`trip_command_processor.py` in dieser Scheibe — blockiert, wenn ein zu diesen Dateien gehoerender Test rot wird |
| `tests/tdd/test_issue_811_mode_matrix.py` | WAECHTER | muss gruen sein, bevor der Renderer-Mail-Gate-Matrix-Nachweis fuer `helpers.py` akzeptiert wird |

## PO-Entscheidungen

**Fortbestehend aus Scheibe 1 (2026-08-11) und Scheibe 2 (2026-08-12),
unveraendert gueltig:**

| Frage | Entscheidung |
|---|---|
| Auslegung | **(ii) Alle tragenden Signale.** Genannt wird JEDE Zutat, die die gezeigte Stufe erreicht. Kein Gewinner wird gekuert. |
| Kanaele | **E-Mail und Telegram JA · SMS und Premium-SMS ausdruecklich OHNE Herkunft** — aktiv abzuwaehlen/zu pruefen, nicht stillschweigend auszulassen. |

**Neu, 2026-08-13 (Umfang dieser Scheibe):**

| Frage | Entscheidung |
|---|---|
| Ausgabeorte | Genau **vier**: Pille im Metriken-Ueberblick, Kommando-Timeline je Wegpunkt, GLANCE-Tageszeile, Ortsvergleich-Stundentabelle (HTML + Klartext). Auswahlgrund: bei allen vieren liegt die Zutat bereits vor — kein neues Feld, kein struktureller Umbau. |
| **GLANCE (abgeloest)** | Scheibe 2 (D3, Known Limitation 4): GLANCE bleibt bewusst zeichengleich. **PO-Entscheid 2026-08-13: aufgehoben.** GLANCE zeigt die Herkunft ab dieser Scheibe, exakt wie das GEWITTER-Kommando, ueber denselben bereits berechneten Aggregat-Schluessel. |
| **Compare-Stundentabelle (abgeloest)** | Scheibe 1 (AC-11): die Compare-Stundentabelle bleibt unveraendert. **Mit dieser Scheibe abgeloest** — der dritte Parameter von `_fmt_thunder()` wird an beiden Aufrufstellen (HTML, Klartext) ab jetzt uebergeben. |
| `aggregate_stage()` | Bleibt weiterhin bewusst unangeschlossen — keiner der vier Orte dieser Scheibe aktiviert diesen Rueckfallweg (vollstaendige Konsumentenanalyse, s. Known Limitations). Tech-Lead-Entscheid unveraendert seit Scheibe 1/2. |

## Implementation Details

**D1 — Pille im Metriken-Ueberblick: Vereinigung ueber das Tagesfenster.**
`_pill_for_metric()` (`helpers.py:1713-1757`) erhaelt bereits `all_dps` — die
rohe `ForecastDataPoint`-Liste des Tagesfensters (04-19 + Zielstunde,
`build_day_window_points()`, `helpers.py:1861-1864`). Zusaetzlich zur
bestehenden `max_lvl`-Schleife (Z. 1721-1736) wird
`traeger = union_of_max_carriers((dp.thunder_level, dp.thunder_level_signals)
for dp in all_dps)` berechnet (call-time Import, Muster Z. 1743). Die Herkunft
haengt NUR am "identifizierten" Zweig an (Z. 1748-1752, wo bereits eine
Erwaehnungsschwelle ueberschritten wurde), VOR dem bestehenden Hagel-Suffix —
analog der Reihenfolge in `_fmt_gewitter()` (Scheibe 2, "Zeitfenster/Stufe ·
Herkunft · Hagel"). Die beiden anderen Rueckgabezweige ("kein Gewitter",
"Gewitter ?" bei Datenluecke, Z. 1755-1757) bekommen KEINEN Herkunfts-Zusatz:
bei "kein Gewitter" liefert `union_of_max_carriers` ohnehin `None` (F001-
Garantie, Stufe `NONE`), bei der Datenluecke wird auch die Stufe selbst nicht
genannt, eine Herkunft dazu waere inkohaerent.

**D2 — Kommando-Timeline: Segment-Aggregat je Wegpunkt.** `_fmt_timeline()`
(`trip_command_processor.py:908-939`) liest `m = p.metrics` (Z. 928) — eine
`SegmentWeatherSummary` je Wegpunkt (`TimelinePoint.metrics = seg.aggregated`,
`weather_extractor.py:98`). Die Gewitterzeile (Z. 933-937) erweitert sich um
`traeger = m.thunder_level_max_signals` und haengt bei vorhandenen Traegern
`" · " + herkunft` hinter `t_label` an: `f"⛈ {t_label} · {herkunft}"` statt
bisher nur `f"⛈ {t_label}"`. Kein zweiter Datenzugriff: `thunder_level_max` UND
`thunder_level_max_signals` stammen aus DEMSELBEN `m`, befuellt von
`compute_basis_metrics()` fuer genau dieses eine Segment — die Timeline zeigt
mehrere Wegpunkte NACHEINANDER, nie aggregiert, daher ist hier keine
Vereinigung ueber mehrere Eintraege noetig (anders als bei Pille/GLANCE).

**D3 — GLANCE: liest den seit Scheibe 2 vorhandenen Schluessel (abgeloeste
Entscheidung).** `_fmt_day_agg()` (`trip_command_processor.py:844-854`)
erweitert sich um `traeger = agg.get("thunder_signals")` und haengt bei
vorhandenen Traegern `f" · {herkunft}"` hinter `{thunder_label}` an:
`f"⛈ Gewitter: {thunder_label} · {herkunft}"` statt bisher nur
`f"⛈ Gewitter: {thunder_label}"`. Kein neuer Datenzugriff: `_aggregate_day()`
(Z. 804-842) berechnet `"thunder_signals"` bereits seit Scheibe 2 ueber
`union_of_max_carriers()` (Z. 834-839) — GENAU der Schluessel, den
`_fmt_gewitter()` bereits liest (Z. 902-905). Der Kommentar Z. 832-833 ("Nur
`_fmt_gewitter()` liest den Schluessel; `_fmt_day_agg()`/GLANCE bleibt bewusst
zeichengleich (Spec D3, Known Limitation 4)") wird durch einen Hinweis auf
diese Scheibe ersetzt — sonst behauptet der Kommentar das Gegenteil des Codes
(Lehre aus Scheibe 2, s. Purpose).

**D4 — Ortsvergleich-Stundentabelle: dritter Parameter an zwei bestehenden
Aufrufstellen, Funktionsrumpf unangetastet.** `_fmt_thunder(v, hail=None,
signals=None)` (`compare_html.py:204-233`) hat den dritten Parameter bereits
seit Scheibe 1 — der Rumpf (Z. 226-233) haengt bei vorhandenen `signals`
bereits korrekt einen `·`-Abschnitt an, VOR dem Hagel-Hinweis. Zwei
Aufrufstellen werden geaendert:
- **HTML** — `_render_hour_row()` (`compare_html.py:982-983`): statt
  `m["fmt"](value, getattr(dp, "hail_flag", None))` neu
  `m["fmt"](value, getattr(dp, "hail_flag", None), getattr(dp,
  "thunder_level_signals", None))`, nur wenn `m["fmt"] is _fmt_thunder`
  (bestehende Bedingung Z. 982 bleibt der Torwaechter).
- **Klartext** — die Stundenschleife in `render_comparison_text()`
  (`comparison.py:329-333`): analog derselbe dritte Positionsparameter.

`value` (aus `getattr(dp, m["key"], None)`) traegt die rohe Stufe
(`dp.thunder_level`), `thunder_level_signals` liegt am SELBEN `dp` — beide aus
demselben Datenpunkt, kein zweiter Rechenweg. Der Docstring-Hinweis
`compare_html.py:215-220` ("🔴 Der Zusatz gehoert bewusst NICHT in den Rumpf:
diese Funktion speist ueber `_HOUR_FMT_OVERRIDES["thunder"]` AUCH die
Compare-Stundentabelle, die in dieser Scheibe unveraendert bleibt (AC-11)")
wird korrigiert: die Compare-Stundentabelle bleibt weiterhin OHNE eigene
Logik im Funktionsrumpf (D4 aendert nur Aufrufstellen), zeigt die Herkunft ab
dieser Scheibe aber SEHR WOHL — der Verweis auf "AC-11 aus Scheibe 1"
(damals: unveraendert) ist durch den Hinweis auf die Aufhebung in dieser
Scheibe zu ersetzen.

**D5 — Kein struktureller Kohaerenz-Guard, vier verschiedene Beweisebenen.**
Anders als in Scheibe 1 (dort D7: `LocationResult.thunder_level_max` UND die
Herkunft koennten aus ZWEI unabhaengigen Rechnungen stammen, daher ein
Laufzeit-Guard in `loc_thunder_signals()`) entstehen an allen vier Orten
dieser Scheibe Stufe UND Herkunft aus DERSELBEN Rechnung bzw. demselben
Objekt:
- **Pille:** dieselbe `all_dps`-Liste speist `max_lvl` UND `traeger`.
- **Timeline:** dasselbe `m` (`SegmentWeatherSummary`) traegt
  `thunder_level_max` UND `thunder_level_max_signals`.
- **GLANCE:** derselbe `_aggregate_day()`-Dict-Aufbau fuellt `"thunder"` UND
  `"thunder_signals"` in EINEM Funktionsaufruf.
- **Stundentabelle:** derselbe `dp` liefert `dp.thunder_level` (via
  `m["key"]`) UND `dp.thunder_level_signals`.

Ein struktureller Guard ist daher an keinem der vier Orte noetig — die
Kohaerenz wird stattdessen durch AC-8/AC-9/AC-10/AC-11 UND die zugehoerigen
Mutationsproben nachgewiesen (s. Testplan), nicht durch eine Laufzeit-Pruefung
im Code. Das ist dieselbe Argumentation wie Scheibe 2s D6, hier auf vier statt
zwei Orte angewendet.

## Expected Behavior

- **Input:** ein Trip- bzw. Ortsvergleich-Kontext, dessen `ForecastDataPoint`s
  bzw. `SegmentWeatherSummary`s ueber die echte Anreicherung
  (`thunder_enrichment.enrich_thunder()`) unterschiedliche Gewitter-Rohwerte
  tragen (z. B. eine Stunde/ein Wegpunkt mit CAPE oberhalb der Leiter, eine
  andere/ein anderer mit Blitzpotenzial oberhalb derselben Hoechststufe).
- **Output:** Pille, Kommando-Timeline, GLANCE-Zeile und
  Ortsvergleich-Stundentabelle (HTML + Klartext) zeigen neben Stufe/Zeitfenster
  die tragende(n) Zutat(en); SMS, Premium-SMS, Compare-SMS und
  Compare-Telegram-Uebersicht bleiben unveraendert ohne Herkunfts-Zusatz.
- **Side effects:** keine neuen Datenfelder, keine Persistenz-Aenderung — alle
  gelesenen Felder existieren bereits additiv seit Scheibe 1/2. Zwei
  Kommentare/Docstrings (`trip_command_processor.py:832-833`,
  `compare_html.py:215-220`) werden inhaltlich korrigiert, keine
  Logikaenderung an den betroffenen Zeilen selbst.

## Acceptance Criteria

- **AC-1:** Given die Pille im Metriken-Ueberblick der Trip-Mail zeigt ein
  Gewitterfenster, das ausschliesslich ueber eine Zutat (z. B. CAPE) zustande
  kommt, When die Mail gerendert wird, Then lautet die Pille „Gewitter ab
  14:00 · stärkste 17:00 · CAPE" statt nur „Gewitter ab 14:00 · stärkste
  17:00".
  - Test: `_pill_for_metric("thunder", ...)` mit einer Fixture, deren
    Tagesfenster-Datenpunkte via echter Anreicherung nur CAPE oberhalb der
    Leiter tragen; Assertion auf den Teilstring „· CAPE" im zurueckgegebenen
    Pillentext.

- **AC-2:** Given die Kommando-Timeline eines Wegpunkts zeigt eine
  Gewitterstufe, die ausschliesslich ueber eine Zutat zustande kommt, When der
  Nutzer TODAY/TOMORROW sendet, Then zeigt die Wegpunkt-Zeile „⛈ leicht ·
  CAPE" statt nur „⛈ leicht".
  - Test: `_fmt_timeline()` mit einer Timeline-Fixture, deren Wegpunkt am
    Zieltag ein `SegmentWeatherSummary` mit `thunder_level_max_signals =
    ["cape"]` traegt; Assertion auf den Teilstring „· CAPE" in der
    zurueckgegebenen Zeile dieses Wegpunkts.

- **AC-3 (abgeloeste Entscheidung):** Given die GLANCE-Antwort zeigt eine
  Tages-Gewitterstufe, die ausschliesslich ueber eine Zutat zustande kommt,
  When der Nutzer GLANCE sendet, Then zeigt die Zeile „⛈ Gewitter: leicht ·
  CAPE" statt — wie bis einschliesslich Scheibe 2 — nur „⛈ Gewitter: leicht".
  Diese Scheibe hebt die in Scheibe 2 getroffene Entscheidung „GLANCE bleibt
  zeichengleich" ausdruecklich auf.
  - Test: `_fmt_day_agg()`/`_fmt_glance()` mit derselben Timeline-Fixture wie
    AC-4 aus Scheibe 2 (zwei Wegpunkte desselben Tages, unterschiedliche
    Zutaten auf derselben Hoechststufe); Assertion, dass die GLANCE-Zeile
    (anders als der Scheibe-2-Bestandstest es fuer GLANCE forderte) NUN den
    Teilstring „· CAPE" bzw. „· Blitzpotenzial" enthaelt.

- **AC-4:** Given ein Ort im Ortsvergleich zeigt in der Stundentabelle eine
  Gewitterstufe, die ausschliesslich ueber eine Zutat zustande kommt, When die
  Vergleichsmail (HTML) bzw. der Klartext-Teil derselben Mail gerendert wird,
  Then zeigt die Stundenzelle „leicht · CAPE" statt nur „leicht" — an BEIDEN
  Stellen (HTML und Klartext) derselben Mail.
  - Test: `render_compare_email()` mit einer Fixture, deren `hourly_data`
    genau einen Datenpunkt mit `thunder_level=LOW`,
    `thunder_level_signals=["cape"]` enthaelt; Assertion auf den Teilstring
    „· CAPE" sowohl im `html_body` (Stundentabellen-Zelle) als auch im
    `text_body` (Klartext-Stundenzeile).

- **AC-5:** Given innerhalb einer Stunde tragen zwei Zutaten gemeinsam die
  Hoechststufe (z. B. CAPE UND Blitzpotenzial erreichen beide „hoch"), When
  die Pille gerendert wird, Then werden BEIDE in der Katalogreihenfolge aus
  `THUNDER_SIGNAL_LABEL_DE` genannt („· CAPE, Blitzpotenzial") — kein Gewinner
  wird gekuert.
  - Test: Fixture mit einem Tagesfenster-Datenpunkt, dessen CAPE- und
    LPI-Rohwerte beide auf die Hoechststufe fuehren; Assertion auf beide
    Labels in dieser Reihenfolge im Pillentext.

- **AC-6:** Given zwei Stunden desselben Tagesfensters erreichen die
  Hoechststufe der Pille ueber verschiedene Zutaten (14 Uhr CAPE, 17 Uhr
  Blitzpotenzial, beide „hoch"), When die Pille gerendert wird, Then nennt sie
  BEIDE Zutaten, nicht nur die der zeitlich ersten oder der Spitzenstunde.
  - Test: `_pill_for_metric("thunder", ...)` mit einer `all_dps`-Fixture aus
    zwei Datenpunkten mit identischer Hoechststufe, aber verschiedenen
    `thunder_level_signals`; Assertion auf beide Labels im Pillentext.

- **AC-7:** Given zwei Wegpunkte desselben Kalendertags erreichen die
  Tages-Hoechststufe von GLANCE ueber verschiedene Zutaten, When der Nutzer
  GLANCE sendet, Then nennt die Zeile BEIDE Zutaten, nicht nur die des
  zeitlich ersten Wegpunkts.
  - Test: `_aggregate_day()`/`_fmt_day_agg()` mit einer Timeline-Fixture aus
    zwei Wegpunkten desselben `target_date` — Wegpunkt A nur CAPE, Wegpunkt B
    nur Blitzpotenzial, beide auf derselben Hoechststufe; Assertion auf beide
    Labels in der GLANCE-Zeile.

- **AC-8 (Kohaerenz Pille):** Given die Pille berechnet Stufe UND Herkunft aus
  DERSELBEN Tagesfenster-Liste (kein zweiter, unabhaengiger Datenzugriff),
  When eine zusaetzliche Stunde AUSSERHALB dieses Fensters eine dritte,
  abweichende Zutat traegt, Then erscheint diese dritte Zutat NICHT in der
  Pille.
  - Test: `_pill_for_metric("thunder", ...)` direkt mit einer `all_dps`-Liste
    aufgerufen, die bewusst NICHT alle Rohdaten des Tages enthaelt (eine
    dritte Zutat existiert nur ausserhalb der uebergebenen Liste); Assertion,
    dass der Pillentext nur Zutaten aus der uebergebenen Liste nennt.

- **AC-9 (Kohaerenz Stundentabelle):** Given zwei benachbarte Stunden
  desselben Ortes tragen ihre jeweilige Stufe ueber verschiedene Zutaten, When
  die Stundentabelle gerendert wird, Then zeigt JEDE Stundenzeile
  ausschliesslich die Zutat(en) IHRES EIGENEN Datenpunkts — keine Vermischung
  zwischen benachbarten Zeilen.
  - Test: `_render_hour_row()`/die Klartext-Schleife mit zwei aufeinander
    folgenden `dp`s, deren `thunder_level_signals` sich unterscheiden (z. B.
    Stunde A nur CAPE, Stunde B nur Blitzdichte); Assertion, dass Zeile A nur
    „CAPE" und Zeile B nur „Blitzdichte" zeigt, nie beide in derselben Zeile.

- **AC-10 (Kohaerenz Timeline):** Given zwei Wegpunkte desselben Tages tragen
  ihre jeweilige Stufe ueber verschiedene Zutaten, When die Timeline gerendert
  wird, Then zeigt JEDE Wegpunkt-Zeile ausschliesslich die Zutat(en) IHRES
  EIGENEN Segment-Aggregats — keine Vermischung zwischen Wegpunkten.
  - Test: `_fmt_timeline()` mit zwei Wegpunkten, deren
    `thunder_level_max_signals` sich unterscheiden; Assertion, dass jede Zeile
    nur die Zutat(en) ihres eigenen Wegpunkts nennt.

- **AC-11 (Kohaerenz GLANCE):** Given `_aggregate_day()` berechnet Stufe UND
  Herkunft von GLANCE aus derselben, nach `target_date` gefilterten
  Wegpunktliste, When ein Wegpunkt eines ANDEREN Kalendertags eine dritte,
  abweichende Zutat traegt, Then erscheint diese dritte Zutat NICHT in der
  GLANCE-Zeile.
  - Test: Timeline-Fixture mit einem Wegpunkt ausserhalb `target_date`, der
    eine dritte Zutat traegt; Assertion, dass die GLANCE-Zeile nur Zutaten von
    Wegpunkten DES Zieltags nennt.

- **AC-12 (kein Leck Compare-SMS/Telegram):** Given die Ortsvergleich-
  Stundentabelle zeigt an mindestens einem Ort eine Herkunft, When derselbe
  Vergleich als SMS oder als Telegram-Nachricht gerendert wird, Then enthaelt
  weder `render_compare_sms()` noch `render_compare_telegram()` irgendeine der
  vier Zutat-Bezeichnungen — beide Kanaele zeigen weiterhin ausschliesslich
  die Uebersichtszeile (kein Zugriff auf die Stundentabellen-Aufrufstellen
  dieser Scheibe).
  - Test: dieselbe Fixture wie AC-4, zusaetzlich durch `render_compare_sms()`
    und `render_compare_telegram()` gerendert; Assertion, dass keiner der
    beiden Texte „CAPE", „Blitzpotenzial", „Blitzdichte" oder „Wettercode"
    enthaelt.

- **AC-13 (kein Leck Trip-SMS/Premium-SMS):** Given die Pille und die
  GLANCE-Zeile tragen Herkunftsangaben, die in `email_plain` landen, When der
  Trip-Bericht versendet wird, Then enthaelt weder `report.sms_text` noch —
  ueber den Rueckfallweg `sms_text or email_plain` — die tatsaechlich
  zugestellte SMS/Premium-SMS irgendeine der vier Zutat-Bezeichnungen; die
  Gewitterstufe selbst bleibt dort unveraendert sichtbar, und `report.sms_text`
  ist nicht-leer (belegt, dass der Rueckfall auf `email_plain` strukturell
  nicht greift, analog Scheibe 2 AC-8/#868).
  - Test: `TripReportFormatter` mit einer Fixture, deren Pillen-/GLANCE-Text
    eine Herkunft ausloesen wuerde; Assertion, dass `report.sms_text` weder
    „CAPE" noch „Blitzpotenzial" noch „Blitzdichte" noch „Wettercode" enthaelt
    UND dass `report.sms_text` nicht-leer ist.

- **AC-14 (S1-Uebersichtszeile bleibt unveraendert):** Given die
  Ortsvergleich-Uebersichtszeile (Tagesuebersicht, nicht die Stundentabelle)
  zeigte vor dieser Scheibe bereits eine Herkunft (Scheibe 1), When diese
  Scheibe ausgeliefert ist, Then bleibt der Text der Uebersichtszeile
  fuer eine unveraenderte Fixture zeichengleich — die Aenderung an den
  Stundentabellen-Aufrufstellen (D4) veraendert NICHT den Rumpf von
  `_fmt_thunder()` und wirkt sich damit nicht auf `_render_overview_row()`
  (`compare_html.py`, unveraenderte Aufrufstelle) oder die Klartext-
  Uebersichtszeile (`comparison.py:248`, unveraenderte Aufrufstelle) aus.
  - Test: Golden-Text-Vergleich der Uebersichtszeile mit derselben Fixture wie
    ein Bestandstest aus Scheibe 1, vor und nach dieser Scheibe identisch.

- **AC-15 (keine Aussage bleibt keine Aussage):** Given ein bereits
  gespeicherter Wetter-Schnappschuss OHNE das Feld
  `thunder_level_max_signals` (Alt-Snapshot vor Scheibe 1/2) wird fuer die
  Kommando-Timeline geladen, When der Nutzer TODAY/TOMORROW sendet, Then zeigt
  die Wegpunkt-Zeile die Gewitterstufe unveraendert, aber OHNE
  Herkunfts-Zusatz — kein „unbekannt", kein leerer Trenner, kein Fehler.
  - Test: `WeatherSnapshotService.load()` mit einem Dict ohne den Schluessel
    deserialisiert; `_fmt_timeline()` mit der daraus entstehenden Timeline
    aufgerufen; Assertion, dass die Stufe erscheint und kein „·" nach dem
    Stufenwort folgt.

- **AC-16 (Zeichengleichheit ohne Herkunft):** Given eine Stunde bzw. ein Tag
  zeigt „kein" Gewitter (keine Zutat erreicht eine Stufe ueber NONE), When
  Pille, Timeline, GLANCE-Zeile und Stundentabelle gerendert werden, Then
  bleibt die Ausgabe an ALLEN VIER Orten zeichengleich zu vor dieser Scheibe —
  kein Herkunfts-Zusatz. Besonders zu pruefen: GLANCE, weil diese Scheibe dort
  erstmals ueberhaupt Herkunft anzeigt (AC-3) — die NONE-Zeichengleichheit
  darf davon nicht beruehrt sein.
  - Test: Fixture ohne jedes Gewittersignal; Assertion, dass
    `_pill_for_metric()`, `_fmt_timeline()`, `_fmt_day_agg()`/`_fmt_glance()`
    und `_render_hour_row()`/die Klartext-Zeile textuell unveraendert zu den
    jeweiligen Bestandsfixtures aus Scheibe 1/2 bleiben.

## Testplan

**Kern-Schicht** (deterministisch, ohne Netz, echte Fusions-/Aggregations-
/Renderpfade — kein Mock-Theater): keine neue Testdatei. Erweitert werden die
beiden bestehenden, nach Verhalten benannten Module:

- `tests/tdd/test_thunder_origin_trip.py` (Vorbild Scheibe 2) deckt AC-1, AC-2,
  AC-3, AC-5, AC-6, AC-7, AC-8, AC-10, AC-11, AC-13, AC-15, AC-16 (Trip-Teile)
  ueber die echten Funktionen (`_pill_for_metric`, `_fmt_timeline`,
  `_fmt_day_agg`/`_fmt_glance`, `WeatherSnapshotService.load`,
  `TripReportFormatter`).
- `tests/tdd/test_thunder_origin_compare.py` (Vorbild Scheibe 1) deckt AC-4,
  AC-9, AC-12, AC-14, AC-16 (Compare-Teil) ueber die echten Funktionen
  (`render_compare_email`, `render_compare_sms`, `render_compare_telegram`).

**Pruefort=Wirkort, ohne Ausnahme:** jeder AC laeuft mindestens einmal durch
die vollstaendige Kette bis zum zurueckgegebenen Mail-/Kommando-Text — keine
Isolation auf `union_of_max_carriers()` allein.

### Pflicht-Mutationsproben (mindestens 3, hier 6)

- **(a) Pille: Vereinigung durch „nur der Datenpunkt der Spitzenstunde"
  ersetzen** (`traeger = peak_dp.thunder_level_signals` statt
  `union_of_max_carriers(...)` ueber `all_dps`) ⇒ AC-6 MUSS rot werden — zwei
  Stunden mit unterschiedlicher Zutat auf derselben Hoechststufe zeigten dann
  nur die Zutat der zeitlich letzten/staerksten Stunde.
- **(b) GLANCE: den neuen Lesezugriff `agg.get("thunder_signals")` wieder
  entfernen** (Rueckbau auf den Scheibe-2-Stand) ⇒ AC-3 MUSS rot werden — das
  ist die zentrale Gegenprobe der in dieser Scheibe abgeloesten Entscheidung.
- **(c) Compare-HTML: den dritten Parameter am `_render_hour_row()`-Aufruf
  wieder entfernen** (Rueckbau auf `m["fmt"](value, getattr(dp, "hail_flag",
  None))`) ⇒ AC-4s HTML-Teilassertion MUSS rot werden.
- **(d) Compare-Klartext: denselben dritten Parameter in der Stundenschleife
  von `render_comparison_text()` entfernen** ⇒ AC-4s Klartext-Teilassertion
  MUSS rot werden — beweist, dass HTML und Klartext unabhaengig voneinander
  geprueft werden, nicht nur einer der beiden Pfade.
- **(e) Timeline: `m.thunder_level_max_signals` durch eine EINMAL ausserhalb
  der Schleife berechnete Traegerliste des ERSTEN Wegpunkts ersetzen** (jede
  Zeile zeigt dieselbe, globale Liste) ⇒ AC-10 MUSS rot werden.
- **(f) Compare-SMS: `_sms_metric_cell()` probeweise so umbauen, dass die
  Gewitter-Zelle ueber dieselbe Aufrufstelle wie die Stundentabelle (mit
  `signals`) statt ueber `_fmt_overview_cell(..., include_origin=False)`
  gebaut wird** (simuliert einen versehentlichen Wiederverwendungs-Bug) ⇒
  AC-12 MUSS rot werden — das ist die aktive Gegenprobe zur PO-Vorgabe „SMS
  aktiv abgewaehlt, nicht nur strukturell unerreichbar".

Mutationen ausschliesslich per String-Ersetzung mit externer Sicherungskopie
(kein `git checkout`/`stash`/`reset`, CLAUDE.md-Vorgabe).

## Known Limitations

1. **`sdi_2` (Superzellen) bleibt aussen vor.** Die Fusion hat vier, nicht
   fuenf Zutaten — unveraendert seit Scheibe 1 (dort Known Limitation 1).
2. **EU_REST-LPI ist ein ausgewiesener Interim-Wert** (unbelegte Schwelle,
   Feineichung offen als #1678, ADR-0048). Unveraendert seit Scheibe 1 (dort
   Known Limitation 2).
3. **`aggregate_stage()` bleibt unangeschlossen.** Gemessen (vollstaendige
   Konsumentenanalyse, Kontextdokument): `stage_weather.py:112` liest die
   Traegerliste nicht (nur Temperatur/Wind/Niederschlag/Wettercode);
   `compact_summary.py:268` (`_aggregate()`) rechnet den Gewittertext bewusst
   daneben, direkt ueber die Stundenwerte mit eigenem
   `union_of_max_carriers()`-Aufruf (`:628`); `trip_report_scheduler.py:2026`
   (Mehrtages-Ausblick) waere der erste ECHTE Verbraucher, liest heute aber
   nur `agg.thunder_level_max`. Keiner der vier Orte dieser Scheibe aktiviert
   den generischen `else`-Zweig (`weather_metrics.py:1265-1266`, liefert
   `values[0]`). Known Limitation 7 aus Scheibe 1 bleibt bestehen und gehoert
   in die Ausblick-Scheibe.
4. **Mehrtages-Ausblick, Trip-Stundentabelle und Gewitter-Vorschau bleiben
   ohne Herkunft.** Beim Ausblick gehen die Traeger strukturell verloren:
   `HourlyValue` (`src/output/tokens/dto.py:15-18`) ist ein frozen Dataclass
   mit nur `hour` und `value` — dazu Tag-/Nacht-Split (#1653). Die
   Trip-Stundentabelle braucht erst einen Seitenkanal analog
   `row["_hail_flag"]` (`trip_report.py:687`) plus Auswertung in `fmt_val()`
   (`helpers.py:732-757`); zusaetzlich rechnet `_aggregate_night_block()`
   (`trip_report.py:596-601`) ohne Traegerlogik. Beide sind eigene, nicht
   diese Scheibe.
5. **Go-DTO und Frontend bleiben ERSATZLOS, nicht aufgeschoben.**
   `model.SegmentWeatherSummary` (`internal/model/segment.go:15`, Feld
   `ThunderLevelMax`) wird in `internal/` nirgends konstruiert oder gelesen —
   kein Feld dort haette einen Verbraucher. `CompareMetrics`
   (`frontend/src/lib/types.ts:426-440`) wird ausserhalb von `types.ts` nicht
   referenziert; keine Svelte-Komponente rendert eine live abgerufene
   Gewitterstufe.
6. **GLANCE-, GEWITTER- und TIMELINE-Kommando erreichen weiterhin
   ausschliesslich E-Mail und Telegram — strukturell unveraendert seit
   Scheibe 2.** `InboundMessage` hat genau zwei Erzeuger
   (`inbound_email_reader.py`, `inbound_telegram_reader.py`); es gibt keinen
   SMS-/Premium-SMS-Kommandopfad. Die neu sichtbare Herkunft in Timeline und
   GLANCE erreicht damit strukturell nur die zwei PO-freigegebenen Kanaele,
   ohne eigene Kanal-Unterscheidung im Code. Die Doku-Drift am Docstring
   `trip_command_processor.py:44` (`channel: str  # "email" or "sms"`) bleibt
   unveraendert offen — nicht Teil dieser Scheibe (nur die zwei explizit in
   Implementation Details genannten Kommentare werden korrigiert).
7. **`renderer_mail_gate.py` deckt `comparison.py` und
   `trip_command_processor.py` GEMESSEN NICHT ab** (s. Dependencies). Der
   einzige Commit-Gate-Schutz fuer diese beiden Dateien in dieser Scheibe ist
   `touched_tests_gate.py` (#1481 A) — kein Mail-Validator-Zwang.
8. **Restrisiko am SMS-Rueckfallausdruck bleibt bestehen** (unveraendert seit
   Scheibe 2 Known Limitation 5), jetzt mit erweitertem Leck-Potenzial: die
   Pille und die GLANCE-Zeile tragen ab dieser Scheibe zusaetzlichen
   Herkunftstext in `email_plain`, der ueber `sms_text or email_plain`
   (`notification_service.py:428`/`446`) durchreichen wuerde, wenn
   `sms_text` je leer wuerde. Bewacht durch AC-13 und Mutationsprobe-Analogie
   zu Scheibe 2 (d).
9. **`_deserialize_timeseries()` filtert unbekannte Schluessel nicht**
   (`weather_snapshot.py:301-324`). Unveraendert seit Scheibe 1 (dort Known
   Limitation 5) — unkritisch fuer additive Aenderungen.

## Nicht in dieser Scheibe

- **Mehrtages-Ausblick** (`email/outlook.py`) — s. Known Limitations 4.
- **Trip-Stundentabelle** (`trip_report.py:597-601`, `email/html.py:814-825`)
  — s. Known Limitations 4.
- **Gewitter-Vorschau** (`email/html.py:1307-1329`, `email/plain.py:307-332`)
  — Primaerpfad liest dieselben traegerlosen `HourlyValue`s wie der Ausblick;
  gehoert zur Ausblick-Scheibe.
- **`aggregate_stage()`s Dispatch-Zweig fuer `union_of_max_carriers`** — s.
  Known Limitations 3. Der geteilte Helfer steht bereit; der Anschluss ist ein
  Dreizeiler (analog D1-D3 dieser Spec), gehoert aber in die Scheibe, die den
  Mehrtages-Ausblick bringt (dort der erste echte Verbraucher).
- **Go-DTO und Frontend** — s. Known Limitations 5, ersatzlos.
- **Risiko-Badges der RiskEngine** (`trip_report.py:902-908`) — eigene Skala
  (`RiskLevel`, nicht `ThunderLevel`), unveraendert seit Scheibe 2.
- **Alarm-Renderer** (`alert/render.py:39-53,324-390`) — gibt die rohe
  Ordinalzahl 0-3 aus, keine Wortdarstellung, unveraendert seit Scheibe 2.
- **Fuenfte Fusions-Zutat, Superzellen (`sdi_2`)** — s. Known Limitations 1.
- **Doku-Drift am `InboundMessage`-Docstring** (`trip_command_processor.py:44`)
  — s. Known Limitations 6, bleibt bewusst offen fuer eine spaetere,
  eigenstaendige Doku-Korrektur.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue) — diese Scheibe wendet ADR-0007 (Daten statt
  Empfehlungen), ADR-0025 (eine Gewitter-Quelle fuer alle Kanaele) und
  ADR-0048 (unbekannte/ungeeichte Herkunft = keine Aussage) an, ohne eine
  davon zu aendern.
- **Rationale:** Additive Sichtbarmachung einer bereits vorhandenen internen
  Groesse (welche Zutat trug) an vier weiteren Ausgabeorten ueber bereits
  bestehende Felder und einen bereits bestehenden geteilten Helfer
  (`union_of_max_carriers()`, Scheibe 2) — kein neues Architekturprinzip,
  keine neue Datenquelle, kein neuer Kanal, keine neue Persistenz-Strategie.
  Das Aufheben zweier fruehererer Tech-Lead-/PO-Entscheidungen (GLANCE,
  Compare-Stundentabelle) ist eine Produktentscheidung ueber den Umfang, keine
  Architekturaenderung — beide betroffenen Stellen nutzen weiterhin denselben
  geteilten Fusionsweg (ADR-0025), nur die Sichtbarkeits-Schranke faellt.
  Kein Bezug zu ADR-0034 (Herkunfts-Fusszeile/Datenquelle) — andere Dimension,
  s. Scheibe 1s Architektur-Entscheidung fuer die Abgrenzung.

## Changelog

- 2026-08-13: Initial spec created (Issue #1680, Scheibe 3). Grundlage:
  `docs/context/feat-1680-s3-herkunft-vier-orte.md`, PO-Entscheid zum Umfang
  der Scheibe (vier Ausgabeorte) vom 2026-08-13, inklusive der ausdruecklichen
  Aufhebung zweier fruehererer Entscheidungen (Scheibe 2: GLANCE bleibt
  zeichengleich; Scheibe 1 AC-11: Compare-Stundentabelle bleibt unveraendert).
  Am Code nachgemessene Korrektur gegenueber der Aufgabenbeschreibung: der
  Rueckfallausdruck `sms_text or email_plain` in `notification_service.py`
  steht bei Messung (2026-08-13) auf Zeile 428 (SMS) bzw. 446 (Premium-SMS),
  nicht auf „417,433" (das waren die erklaerenden Kommentarzeilen aus
  Scheibe 2, seither verschoben). `renderer_mail_gate.py` deckt gemessen
  `comparison.py` und `trip_command_processor.py` nicht ab — als Known
  Limitation 7 aufgenommen.
