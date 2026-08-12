---
entity_id: feat_1680_s1_gewitter_herkunft_ortsvergleich
type: feature
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [thunder, compare, adr-0007, adr-0025, adr-0048, issue-1680, issue-1419]
---

<!-- Issue #1680, Scheibe 1 (Ortsvergleich). Bezug #1419 (Epic, Rang 4),
     Entscheidung E1 (PO 2026-08-08). Grundlage: docs/context/feat-1680-thunder-herkunft.md
     (Phase 1+2, gemessen 2026-08-11, Analysis-Abschnitt inkl. PO-Entscheidungen
     am Dateiende). Baut NICHT auf #1760 (CIN-Vorzeichen-Fix) auf, ist aber NACH
     #1760 entstanden — die Fusionsstruktur in metric_format.py, die diese
     Scheibe erweitert, ist der Stand NACH dem #1760-Fix. -->

# Gewitter: Herkunft der Stufe im Ortsvergleich sichtbar machen (#1680 Scheibe 1)

## Approval

- [ ] Approved

## Purpose

Die fusionierte Gewitterstufe (`kein/leicht/mittel/hoch`) entsteht heute aus bis zu
vier Zutaten (Wettercode, Blitzdichte, CAPE gedämpft durch CIN, Blitzpotenzial LPI),
zeigt aber nur das Ergebnis — nicht, welche Zutat es erreicht hat. Im Ortsvergleich
stehen dadurch z. B. Korsika „hoch" und ein Alpen-Ort „hoch" nebeneinander, obwohl
die Stufen auf völlig verschiedenen physikalischen Größen beruhen (Korsika:
Blitzdichte aus AROME; Alpen: CAPE/LPI aus ICON-D2/ICON-EU). Die Zeile suggeriert
eine Vergleichbarkeit, die es auf Rohdaten-Ebene nicht gibt. Diese Scheibe macht
die Herkunft im Ortsvergleich sichtbar, ohne eine der vier Zutaten zu bewerten
oder eine Empfehlung daraus abzuleiten (ADR-0007).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/output/`, `src/providers/`,
> `src/app/models.py`, `src/services/weather_metrics.py`). Kein Frontend, keine
> Go-Beteiligung, kein neuer Endpoint — reine Renderer-/Fusionslogik plus zwei
> additive Datenmodell-Felder.

- **File:** `src/output/metric_format.py` — `thunder_level_from_signals()`
  (Z. 369-457), neue `_signal_levels()`, `thunder_signal_carriers()`,
  `THUNDER_SIGNAL_LABEL_DE`, `thunder_signal_label()`
- **File:** `src/providers/thunder_enrichment.py` — `_fuse_thunder_levels()`
  (Z. 95-144)
- **File:** `src/app/models.py` — `ForecastDataPoint` (Z. 99 ff.),
  `SegmentWeatherSummary` (Z. 405 ff.)
- **File:** `src/services/weather_metrics.py` — `_compute_thunder_level()`
  (Z. 590-609), `compute_metrics()` (Z. 396-492)
- **File:** `src/output/renderers/email/compare_html.py` — `_fmt_thunder()`
  (Z. 204-219), neue `loc_thunder_signals()` (analog `loc_hail_flag()`,
  Z. 643-658), Aufrufstelle `_render_overview_row()` (Z. 703-707)
- **File:** `src/output/renderers/comparison.py` — `_fmt_overview_cell()`
  (Z. 503-515), Aufrufstellen Z. 246 (Klartext-Übersicht),
  `_plain_metric_cell()` (Z. 632-644, Telegram), `_sms_metric_cell()`
  (Z. 605-629, SMS — bewusst NICHT geändert)
- **Identifier:** `output.metric_format.thunder_signal_carriers()`,
  `output.renderers.email.compare_html.loc_thunder_signals()`,
  `output.renderers.comparison._fmt_overview_cell()`

## Estimated Scope

- **LoC:** ~145-165 Quellcode + ~80-110 Tests, geschätzt **~225-250** gesamt
  (Limit 250 je Workflow — **knapp**, s. „Nicht in dieser Scheibe" für den
  ersten Kürzungs-Kandidaten, falls die Umsetzung darüber liegt).
- **Files:** 6 Quelldateien (s. Source) + 1-2 neue Testdateien, nach
  Verhalten benannt (nicht nach Issue-Nummer).
- **Effort:** medium. Kein Breaking Change (additiv, s. D1/D2), kein
  Frontend, keine Migration — das Risiko liegt im SMS-Ausschluss (muss aktiv
  geprüft werden, nicht nur unterlassen) und im Persistenz-Feldtyp (D6).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1680-thunder-herkunft.md` | GRUNDLAGE (gemessen) | Belege, Messwerte, PO-Entscheidungen dieser Spec sind daraus übernommen |
| ADR-0007 (`docs/adr/0007-daten-statt-empfehlungen.md`) | ZUSAGE | Herkunfts-Label ist Beschreibung, keine Bewertung |
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | ZUSAGE | Eine Fusion, eine Skala, für Trip UND Ortsvergleich — diese Scheibe fügt der gemeinsamen Fusion ein additives Feld hinzu, baut keine zweite |
| ADR-0048 (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`) | KONTEXT | Unbekannte/ungeeichte Herkunft heißt „keine Aussage" — relevant für die EU_REST-LPI-Einschränkung (Known Limitations) |
| `docs/specs/modules/fix_1760_cin_vorzeichen.md` | VORGÄNGER (Code-Basis) | Die Fusionsstruktur, die diese Scheibe erweitert, ist der Stand NACH diesem Fix |
| `src/output/renderers/alert/official_alerts.py:91-128` (`_SOURCE_LABELS`/`official_alert_source_label`) | MUSTER | Exakt-Treffer vor Heuristik, nie ein erfundener Wert — Vorbild für `thunder_signal_label()` |
| `src/output/metric_format.py:487-496` (`format_hail_note`) + `compare_html.py:204-219` (`_fmt_thunder`) | MUSTER | Additiver `f"{label} · {note}"`-Suffix — Vorbild für den Herkunfts-Suffix |
| `tests/tdd/test_thunder_named_signals_enrichment.py::test_ac9_der_kern_dispatch_kennt_keine_quelle_und_kein_einzelnes_signal` | WÄCHTER | Verbietet Signal-/Quellnamen im Quelltext von `enrich_thunder()` selbst — diese Scheibe hält sich fern davon (D5) |

## PO-Entscheidungen (2026-08-11, nicht verhandelbar)

| Frage | Entscheidung |
|---|---|
| Auslegung | **(ii) Alle tragenden Signale.** Genannt wird JEDE Zutat, die die gezeigte Stufe erreicht — z. B. „hoch · CAPE, Blitzpotenzial". Es wird KEIN Gewinner gekürt. |
| Kanäle | **E-Mail (HTML-Ortsvergleich) + Telegram JA · SMS und Premium-SMS bewusst OHNE Herkunft.** Die Stufe selbst bleibt dort unverändert sichtbar. Das ist eine ausdrückliche Entscheidung, kein stilles Auslassen — der SMS-Zweig muss **aktiv abgewählt** werden. |
| Scheibe | **Ortsvergleich zuerst.** Trip-Mail-Pill, Nachtblock, Kurzzusammenfassung, Mehrtages-Ausblick, GEWITTER-Kommando, Go-DTO und Frontend sind NICHT in dieser Scheibe. |

## Implementation Details

**D1 — Additive Fusion, keine Signaturänderung.** `thunder_level_from_signals()`
hat genau einen Produktiv-Aufrufer (`thunder_enrichment.py:135`). Ihr `if`-Block
(Z. 426-457) wird in eine private `_signal_levels(...) -> dict[str, ThunderLevel]`
gezogen, die je vorhandenem Signal einen Eintrag unter einem festen Schlüssel
liefert (`"wettercode"`, `"blitzdichte"`, `"cape"`, `"blitzpotenzial"` — in
dieser Reihenfolge eingefügt, damit eine spätere Ausgabe deterministisch in
derselben Reihenfolge iteriert, ohne separat sortieren zu müssen).
`thunder_level_from_signals()` wird zeichengleich: `return max_thunder(_signal_levels(...).values()) if _signal_levels(...) else None`.
Alle 11 Bestandstestdateien, die an ihrer Signatur/ihrem Rückgabewert hängen,
bleiben unverändert grün — das ist der Grund für diese Bauweise statt eines
Rückgabetyp-Wechsels.

**D2 — Zweite öffentliche Funktion statt Signaturbruch.**
`thunder_signal_carriers(...)` bekommt dieselbe Keyword-only-Signatur wie
`thunder_level_from_signals()`, ruft ebenfalls `_signal_levels(...)` und
liefert die Liste der Signalnamen, deren übersetzte Stufe die fusionierte
Maximalstufe erreicht (PO-Entscheidung (ii) — **alle** Träger, kein
Gewinner):

```
werte = _signal_levels(...)
if not werte:
    return []
top = max_thunder(werte.values())
return [name for name in werte if werte[name] == top]
```

Löst Befund A (Gleichstands-Reihenfolge, Kontext-Dokument) auf: weil nichts
gekürt wird, ist die interne `if`-Reihenfolge der Fusion keine Produktaussage
mehr.

**D3 — Label-Katalog genau einmal.** `THUNDER_SIGNAL_LABEL_DE` (neben
`THUNDER_LABEL_DE`, `metric_format.py:236-241`) mappt die vier Schlüssel auf
`"Wettercode"`, `"Blitzdichte"`, `"CAPE"`, `"Blitzpotenzial"`.
`thunder_signal_label(name)` liefert bei unbekanntem Namen den rohen Namen
selbst zurück — kein erfundener Ersatztext (Muster
`official_alert_source_label()`, `official_alerts.py:112-128`: Exakt-Treffer
zuerst, dann roher String als Fallback; hier ohne Heuristik-Stufe, weil die
Signalmenge geschlossen ist — vier feste Schlüssel, kein Namensraum mit
Präfix-Varianten wie bei den amtlichen Quellen). Diese vier Zutaten sind
identisch mit den Signalen der Fusion in `metric_format.py` — **nicht** mit
den DWD-Feldnamen aus `thunder_enrichment._SIGNAL_ZU_FELD` (`"lpi"`,
`"cin_ml"`, …), die eine andere Ebene (Rohwert-Routing) beschreiben.

**D4 — Per-Datenpunkt-Feld, gefüllt in `_fuse_thunder_levels()`.**
`ForecastDataPoint.thunder_level_signals: Optional[list[str]] = None` (neu,
additiv, Default `None`). `_fuse_thunder_levels()`
(`thunder_enrichment.py:95-144`) ruft zusätzlich zu
`thunder_level_from_signals(...)` (bereits vorhanden) auch
`thunder_signal_carriers(...)` mit denselben Argumenten und setzt
`dp.thunder_level_signals = carriers`, **nur** wenn `fused is not None`
(exakt dieselbe Überschreib-Bedingung wie beim bestehenden
`dp.thunder_level = fused`, Z. 143-144) — ein bereits vorhandener Wert bleibt
sonst erhalten, analog dem Bestandsverhalten.

**D5 — Kein Signalname im Kern-Dispatch.** Die neuen Aufrufe leben in
`_fuse_thunder_levels()`, **nicht** in `enrich_thunder()` selbst — der von
`test_ac9_der_kern_dispatch_kennt_keine_quelle_und_kein_einzelnes_signal`
bewachte Funktionskörper wird nicht angefasst. Die vier Signalnamen
(`"wettercode"` usw.) stehen ausschließlich in `metric_format.py`
(`THUNDER_SIGNAL_LABEL_DE`, `_signal_levels()`), nicht im Dispatch von
`thunder_enrichment.py`.

**D6 — Tagesaggregat: Vereinigung über die Stunden des Maximums, nicht nur
eine.** `WeatherMetricsService._compute_thunder_level()`
(`weather_metrics.py:590-609`) bleibt unverändert (liefert weiterhin nur die
Stufe). Neue private Methode `_compute_thunder_level_signals(timeseries,
thunder_max) -> list[str]`: sammelt `dp.thunder_level_signals` **aller**
Datenpunkte, deren `dp.thunder_level == thunder_max`, dedupliziert unter
Erhalt der ersten Auftrittsreihenfolge. Grund für die Vereinigung statt
„erste passende Stunde": erreichen zwei verschiedene Stunden desselben Tages
dieselbe Höchststufe über unterschiedliche Zutaten (z. B. 14 Uhr CAPE, 18 Uhr
Blitzpotenzial), nennt der Ortsvergleich beide — sonst würde eine willkürlich
gewählte einzelne Stunde über die angezeigte Herkunft entscheiden.
`compute_metrics()` (Z. 437-479) ruft die neue Methode auf und trägt das
Ergebnis in ein neues `SegmentWeatherSummary.thunder_level_max_signals:
Optional[list[str]] = None` ein (`aggregation_config`-Eintrag:
`"thunder_level_max_signals": "union_of_max_carriers"`, analog dem
bestehenden `"hail_flag": "hail_priority"`-Muster).

**D7 — Kein neues `LocationResult`-Feld, aber Herkunft und Stufe MÜSSEN aus
derselben Rechnung stammen.** 🔴 Das Muster `hail_flag` trägt hier **nicht
ungeprüft**: `app/user.py::LocationResult` hat für `hail_flag` kein eigenes
Feld, weshalb `loc_hail_flag()` strukturell immer live ableitet — **für
Gewitter ist das anders.** `LocationResult.thunder_level_max` **existiert**
als echtes Feld (Issue #1285, `user.py`), und `_metric_value()`
(`compare_html.py:630-642`) gibt dem Engine-Wert **Vorrang** vor der
Live-Ableitung. Ein `loc_thunder_signals()`, das blind live ableitet, würde
also eine Stufe aus dem Engine-Lauf mit einer Herkunft aus einer **zweiten,
unabhängigen Rechnung** paaren — „hoch" von der Engine, „· CAPE" aus
`summarize_points(loc.hourly_data)`. Das ist keine theoretische Kante: es ist
genau der Fehler „Prüfort ≠ Wirkort", nur als Produktaussage.

**Regel:** `loc_thunder_signals(loc, summary=None) -> Optional[list[str]]`
leitet aus `_daily_summary(loc)` ab (kein neues Feld an `LocationResult`,
`services/comparison_engine.py` bleibt unangetastet) und gibt die Träger
**nur dann** zurück, wenn die live abgeleitete `thunder_level_max` **gleich**
der angezeigten Stufe ist. Weichen sie ab oder fehlt eine von beiden, liefert
die Funktion `None` und es erscheint **kein** Herkunfts-Zusatz. „Keine
Aussage" statt einer Aussage, die nicht zur gezeigten Zahl gehört (ADR-0048,
ADR-0007). Der Normalfall — Engine-Lauf und `hourly_data` desselben
Datenstands — erfüllt die Bedingung und zeigt die Herkunft.

**D8 — Rendering: additiver dritter Parameter, SMS aktiv ausgeschlossen.**
`_fmt_thunder(v, hail=None, signals=None)` (`compare_html.py:204-219`) hängt
bei vorhandenen `signals` einen zweiten `·`-Abschnitt an, VOR einem
eventuellen Hagel-Hinweis: `f"{label} · {carrier_text}"` bzw.
`f"{label} · {carrier_text} · {hail_note}"`, wenn beides vorliegt. Alte
Aufrufer mit 1-2 Positionsargumenten bleiben zeichengleich (Default `None`).
Zwei Aufrufwege:
- **HTML-Übersichtszeile** (`_render_overview_row()`, Z. 703-707): dritter
  Positionsparameter `loc_thunder_signals(loc, summaries.get(id(loc)))`.
- **Klartext + Telegram** über `_fmt_overview_cell(fmt, value, loc_result, *,
  include_origin=False)` (comparison.py:503-515, neuer Keyword-Parameter):
  ruft bei `fmt is _fmt_thunder` und `include_origin=True` zusätzlich
  `loc_thunder_signals(loc_result)` auf. Die Klartext-Übersichtszeile
  (Z. 246) und `_plain_metric_cell()` (Telegram, Z. 632-644) setzen
  `include_origin=True`. `_sms_metric_cell()` (Z. 605-629) lässt den
  Parameter **ausdrücklich mit Kommentar** auf `False` — z. B.
  `_fmt_overview_cell(fmt, value, loc_result)  # Issue #1680: SMS bewusst OHNE Herkunft`
  — eine reine Default-Belassung ohne Kommentar wäre nicht von einem
  vergessenen Anschluss unterscheidbar (PO-Vorgabe „aktiv abgewählt, nicht
  stillschweigend ausgelassen").

**D9 — Persistenz: reine `list[str]`, kein Enum.**
`weather_snapshot.py::_serialize_summary()`/`_serialize_segment()`
serialisieren generisch über `vars()` und prüfen nur `isinstance(value, Enum)`
für Skalare (Z. 232-243, 289-295) — ein `list[str]`-Feld durchläuft
`json.dumps` unverändert korrekt, **ohne** Änderung an `weather_snapshot.py`.
Die Falle (Kontext-Dokument, Landmine 1) gilt nur, wenn das Feld ein `set`
oder eine Liste von **Enum-Membern** wäre — deshalb sind
`thunder_level_signals`/`thunder_level_max_signals` bewusst als `list[str]`
(reine Strings, die in D1-D2 erzeugten Schlüssel) typisiert, nie als
`list[ThunderLevel]`. `_deserialize_summary()` filtert unbekannte Schlüssel
(Z. 246-262) — ein alter Schnappschuss ohne das Feld lädt unverändert mit
`thunder_level_max_signals=None`. `_deserialize_timeseries()` filtert
**nicht** (Z. 301-324, `ForecastDataPoint(ts=..., **kwargs)`) — das betrifft
nur ein künftiges **Entfernen** des Feldes, nicht diese Scheibe (additiv).

## Expected Behavior

- **Input:** ein `ComparisonResult` mit mindestens zwei `LocationResult`s,
  deren `hourly_data` `ForecastDataPoint`s mit unterschiedlichen
  Gewitter-Rohwerten trägt (z. B. ein Ort mit CAPE-Werten oberhalb der
  Leiter, ein anderer mit Blitzdichte oberhalb der Leiter), durch die echte
  Anreicherung (`thunder_enrichment.enrich_thunder()`) oder äquivalent
  vorbelegt.
- **Output:** die Gewitter-Zeile der Ortsvergleich-Übersicht (HTML, Klartext,
  Telegram) zeigt neben der Stufe die tragende(n) Zutat(en); SMS/Premium-SMS
  zeigen nur die Stufe.
- **Side effects:** zwei neue additive Felder in Wetter-Schnappschüssen
  (Trip UND Compare, da geteilte Fusion, ADR-0025) — für Trip-Renderer
  unsichtbar (sie lesen die Felder in dieser Scheibe nicht).

## Acceptance Criteria

- **AC-1:** Given zwei Orte im Ortsvergleich tragen ihre „hoch"-Gewitterstufe
  über unterschiedliche Zutaten (ein Alpen-Ort über CAPE, ein Korsika-Ort
  über Blitzdichte), When die HTML-Vergleichsmail versendet wird, Then zeigt
  die Gewitter-Zeile für jeden Ort einzeln die jeweils tragende Zutat, z. B.
  „hoch · CAPE" bzw. „hoch · Blitzdichte" — nicht dieselbe Angabe für beide.
  - Test: `render_compare_email()` mit einer Fixture, die über die echte
    Fusion (`enrich_thunder`) läuft; Assertion auf beide Teilstrings im
    zurückgegebenen `html_body`, je Ortsblock getrennt geprüft.

- **AC-2:** Given an einem Ort tragen zwei Zutaten gemeinsam dieselbe
  Höchststufe (z. B. CAPE UND Blitzpotenzial erreichen beide „hoch"), When
  die Gewitter-Zeile gerendert wird, Then werden BEIDE genannt,
  kommagetrennt („hoch · CAPE, Blitzpotenzial") — es wird kein Gewinner
  gekürt, auch wenn eine Zutat in der internen Prüfreihenfolge zuerst käme.
  - Test: Fixture mit CAPE- und LPI-Rohwerten, die beide auf die
    Höchststufe führen; Assertion, dass der Zellentext beide Labels enthält.

- **AC-3:** Given ein Ort zeigt „kein" Gewitter (keine Zutat liefert eine
  Stufe über NONE), When die Gewitter-Zeile gerendert wird, Then erscheint
  KEIN Herkunfts-Zusatz — die Zeile bleibt wie vor dieser Änderung.
  - Test: Fixture ohne jedes Gewittersignal; Assertion, dass der Zellentext
    keinen `·`-Zusatz trägt.

- **AC-4:** Given der Ortsvergleich wird als Telegram-Nachricht gesendet,
  When der Nutzer die Nachricht liest, Then zeigt die Gewitter-Zeile
  dieselbe Herkunfts-Angabe wie die E-Mail (Fließtext statt Farbzelle, aber
  inhaltsgleich).
  - Test: `render_compare_telegram()` mit derselben Fixture wie AC-1;
    Assertion auf denselben Teilstring im zurückgegebenen Text.

- **AC-5:** Given der Ortsvergleich wird als SMS gesendet, When der Nutzer die
  Nachricht liest, Then zeigt die Nachricht weiterhin die Gewitterstufe
  selbst, aber KEINE Herkunfts-Angabe — kein `CAPE`, kein `Blitzpotenzial`,
  kein `Blitzdichte`, kein `Wettercode` im SMS-Text. (Premium-SMS ist im
  Ortsvergleich-Briefing heute nicht verdrahtet, s. Known Limitations 6 —
  sobald sie es wird, erbt sie über denselben Renderer denselben Ausschluss.)
  - Test: `render_compare_sms()` mit derselben Fixture wie AC-1; Assertion,
    dass die Gewitter-Zelle die Stufen-Abkürzung trägt, aber keinen der vier
    Zutat-Strings.

- **AC-6:** Given ein Ort hat gleichzeitig ein bestätigtes Hagel-Kennzeichen
  UND eine Gewitter-Herkunft, When die E-Mail gerendert wird, Then stehen
  beide Zusätze nebeneinander (z. B. „hoch · CAPE · Hagel: ja"), ohne dass
  einer den anderen verdrängt.
  - Test: Fixture mit `hail_flag=True` UND CAPE-Herkunft; Assertion auf
    beide Teilstrings im `html_body`.

- **AC-7:** Given ein Ort im DWD-Gebiet EU_REST, dessen Gewitterstufe
  ausschließlich über Blitzpotenzial (LPI, unbelegte Interim-Schwelle)
  erreicht wird, When die Herkunft angezeigt wird, Then erscheint
  ausschließlich das Wort „Blitzpotenzial" — ohne Eichungs-Hinweis, ohne
  Handlungsempfehlung, ohne Bewertung der Schwellen-Güte.
  - Test: Fixture mit LPI-Region EU_REST, nur LPI oberhalb der Leiter;
    Assertion auf exakten Zellentext.

- **AC-8:** Given ein bereits versendeter Wetter-Schnappschuss enthält die
  neue Herkunfts-Angabe, When er zu einem späteren Zeitpunkt aus der
  Persistenz geladen und erneut für den Ortsvergleich verwendet wird, Then
  liefert das Laden dieselbe Herkunfts-Angabe zurück, ohne dass der
  Schnappschuss durch einen Serialisierungsfehler verloren geht.
  - Test: Roundtrip über die echten `weather_snapshot`-Serialisierungs-/
    Deserialisierungsfunktionen mit einem `SegmentWeatherSummary`, dessen
    `thunder_level_max_signals` gesetzt ist; Assertion auf Gleichheit vor/
    nach dem Roundtrip UND darauf, dass `json.dumps` nicht scheitert (kein
    `logger.warning`-Pfad ausgelöst).

- **AC-9:** Given ein alter, vor dieser Änderung erzeugter Wetter-
  Schnappschuss ohne das neue Feld wird geladen, When die Vergleichsmail
  gerendert wird, Then erscheint die Gewitterstufe unverändert, nur ohne
  Herkunfts-Zusatz — kein Fehler, kein Absturz.
  - Test: Deserialisierung eines Dict ohne den neuen Schlüssel; Assertion,
    dass `thunder_level_max_signals is None` und der Renderaufruf nicht
    wirft.

- **AC-10:** Given die Gewitterstufe eines Tages entsteht aus mehreren
  Stunden (Ortsvergleich zeigt den Tageswert), und zwei verschiedene Stunden
  erreichen dieselbe Tages-Höchststufe über unterschiedliche Zutaten, When
  die Vergleichsmatrix gerendert wird, Then nennt sie BEIDE Zutaten, nicht
  nur die einer einzelnen (z. B. der ersten) Stunde.
  - Test: Fixture mit zwei Stunden desselben Tages — Stunde A nur CAPE über
    der Leiter, Stunde B nur LPI über derselben Höchststufe — durch die
    echte Aggregation (`compute_metrics()`/`summarize_points()`); Assertion
    auf beide Labels im gerenderten Ergebnis.

- **AC-11:** Given der Trip-Bericht (Stundentabelle, Kurzzusammenfassung,
  Mehrtages-Ausblick) sowie die Compare-Stundentabelle, When #1680 Scheibe 1
  ausgeliefert ist, Then bleiben alle unverändert — kein Herkunfts-Zusatz
  dort; diese Scheibe ändert ausschließlich die Ortsvergleich-Tagesübersicht
  (E-Mail + Telegram).
  - Test: bestehender Trip-Rendertest (Golden-Output-Vergleich oder
    Teilstring-Abwesenheitsprüfung) bleibt unverändert grün; zusätzliche
    Assertion, dass die Compare-Stundentabelle (`_render_hour_row`) keine
    Zutat-Strings enthält.

- **AC-12:** Given die im Ortsvergleich angezeigte Gewitterstufe stammt aus
  dem Engine-Lauf (Feld `LocationResult.thunder_level_max`) und weicht von
  der Stufe ab, die sich aus den Stundenwerten desselben Ortes ergibt, When
  die Gewitter-Zeile gerendert wird, Then erscheint die Stufe unverändert,
  aber KEIN Herkunfts-Zusatz — der Nutzer bekommt nie eine Herkunft
  angezeigt, die zu einer anderen als der gezeigten Stufe gehört.
  - Test: `LocationResult` mit `thunder_level_max=HIGH` gesetzt, während die
    `hourly_data` nur auf MED führen; Assertion, dass „hoch" erscheint und
    keiner der vier Zutat-Strings. Gegenprobe im selben Test: stimmen beide
    überein, erscheint die Herkunft sehr wohl (sonst wäre das AC auch grün,
    wenn die Herkunft nie angezeigt würde).

## Testplan

**Kern-Schicht** (deterministisch, ohne Netz, echte Fusions-/Aggregations-
/Renderpfade — kein Mock-Theater): ein neues Testmodul
`tests/tdd/test_thunder_origin_compare.py` (nach Verhalten benannt) deckt
AC-1 bis AC-7, AC-10, AC-11 über die echten Renderfunktionen
(`render_compare_email`, `render_compare_telegram`, `render_compare_sms`).
Ein zweites, schmales Modul (oder ein eigener Abschnitt im selben Modul)
deckt AC-8/AC-9 über `services.weather_snapshot` direkt (Roundtrip,
Alt-Schnappschuss-Kompatibilität).

**Prüfort = Wirkort:** kein AC wird ausschließlich gegen
`thunder_level_from_signals()`/`thunder_signal_carriers()` isoliert geprüft
— jeder Nachweis läuft mindestens einmal durch die vollständige Kette bis
zur zurückgegebenen `html_body`/`text_body`/Telegram-/SMS-Zeichenkette.

### Pflicht-Mutationsproben (mindestens 3, hier 5)

- **(a) Trägerfilter entfernen** (`thunder_signal_carriers()`: statt
  `werte[name] == top` alle Schlüssel zurückgeben) ⇒ AC-2/AC-3 MÜSSEN rot
  werden — bei „kein" erschiene plötzlich ein Zusatz, bei einem
  Einzel-Träger erschienen fälschlich alle vier möglichen Namen.
- **(b) `include_origin=True` am Klartext-/Telegram-Aufruf entfernen**
  (Default `False` überall) ⇒ AC-1 (Klartext-Teil derselben Mail) UND AC-4
  MÜSSEN rot werden — beweist, dass AC-5 (SMS-Abwesenheit) nicht deshalb grün
  ist, weil die Herkunft überall abgeschaltet wäre.
- **(c) `_sms_metric_cell()` auf `include_origin=True` umstellen** ⇒ AC-5
  MUSS rot werden — das ist die zentrale Gegenprobe zur PO-Vorgabe „aktiv
  abgewählt, nicht stillschweigend ausgelassen".
- **(d) `_compute_thunder_level_signals()` auf „nur erste passende Stunde"
  zurückbauen** (kein `continue`-Sammeln über alle Stunden, sondern
  `break` nach dem ersten Treffer) ⇒ AC-10 MUSS rot werden.
- **(e0) Kohärenz-Bedingung aus `loc_thunder_signals()` entfernen** (Träger
  auch dann zurückgeben, wenn die live abgeleitete Stufe von der angezeigten
  abweicht) ⇒ AC-12 MUSS rot werden — sonst bewacht nichts die Zusicherung,
  dass Stufe und Herkunft aus derselben Rechnung stammen.
- **(e) Feldtyp probeweise auf `set[str]` statt `list[str]` ändern** (an
  einer Kopie, s. Mutations-Protokoll unten) ⇒ AC-8 MUSS rot werden — der
  Roundtrip-Test muss den Verlust erkennen (Snapshot lädt nach dem
  Serialisierungsfehler leer/`None` statt der ursprünglichen Liste), nicht
  nur prüfen, dass kein Python-`Exception` nach außen dringt (der
  Bestandscode schluckt den Fehler in `logger.warning`).

Mutationen ausschließlich per String-Ersetzung mit externer Sicherungskopie
(kein `git checkout`/`stash`/`reset`, CLAUDE.md-Vorgabe).

## Known Limitations

1. **`sdi_2` (Superzellen) bleibt außen vor.** Die Fusion hat vier, nicht
   fünf Zutaten — das Issue-Beispiel „hoch, Blitzpotenzial+Superzelle" ist
   am Code nicht baubar (Kontext-Dokument, Befund). Diese Scheibe erfindet
   keine fünfte Zutat.
2. **EU_REST-LPI ist ein ausgewiesener Interim-Wert** (unbelegte Schwelle,
   Feineichung offen als #1678, ADR-0048). Das Label „Blitzpotenzial" nennt
   NUR, welche Zutat die Stufe erreicht hat — es ist keine Aussage über die
   Güte der Eichung (ADR-0007). Keine Sonderkennzeichnung in dieser Scheibe.
3. **Bei Drift zwischen Engine-Wert und Live-Ableitung entfällt die Herkunft
   (D7, AC-12).** `thunder_level_max_signals` steht bewusst nicht am
   `LocationResult` der Comparison-Engine, sondern wird live aus
   `hourly_data` abgeleitet. Weicht die live abgeleitete Stufe vom
   Engine-Wert ab, zeigt der Ortsvergleich die Stufe **ohne** Herkunft.
   Bewusster Verzicht: lieber keine Angabe als eine, die zu einer anderen
   Stufe gehört. Wer die Herkunft auch in diesem Fall sehen will, braucht ein
   Engine-Feld an `LocationResult` — eigene Scheibe, nicht diese.
6. **Premium-SMS ist im Ortsvergleich-Briefing nicht verdrahtet.**
   `comparison.py` kennt keinen Premium-SMS-Zweig; der Kanal wird heute nur
   im **Alarm**-Pfad aufgelöst (`compare_alert_channels.py:44-45`, #1745).
   Ein Herkunfts-Zusatz kann dorthin also gar nicht lecken. Sobald der
   Ortsvergleich Premium-SMS bedient, erbt er über `render_compare_sms()`
   denselben Ausschluss — die PO-Entscheidung „SMS und Premium-SMS ohne
   Herkunft" ist damit auch vorwärts erfüllt.
4. **Ko-Auftretensrate Wettercode/andere Signale bleibt ungemessen**
   (Kontext-Dokument Befund B) — mit Auslegung (ii) irrelevant für die
   Anzeige (alle Träger erscheinen ohnehin), aber die Häufigkeit, wie oft
   der binäre Wettercode zusammen mit CAPE/LPI/Blitzdichte auf derselben
   Stunde HIGH meldet, ist mit Bordmitteln weiterhin nicht messbar.
5. **`_deserialize_timeseries()` filtert unbekannte Schlüssel nicht**
   (`weather_snapshot.py:301-324`). Unkritisch für diese additive Änderung
   (Hinzufügen ist sicher), aber ein künftiges Entfernen des Feldes bräuchte
   eine explizite Migration.

## Nicht in dieser Scheibe

- **Compare-Stundentabelle** (HTML `_render_hour_row`, Z. 937-938; Klartext
  Z. 327-331): zeigt weiterhin nur Stufe + Hagel, keine Herkunft. Begründung:
  LoC-Budget (`_fmt_thunder`s dritter Parameter ist bereits vorbereitet —
  additiver Ein-Zeiler je Aufrufstelle als natürlicher Folge-Schnitt, kein
  struktureller Umbau nötig) UND der primäre Issue-Zweck (Vergleichbarkeit
  zwischen Orten) wird bereits von der Tagesübersicht bedient, die als
  Erstes und am prominentesten gelesen wird.
- **Trip-Mail-Pill, Nachtblock, Kurzzusammenfassung, Mehrtages-Ausblick,
  GEWITTER-Kommando** (Trip-Seite) — PO-Entscheidung, eigene Scheibe.
- **Go-DTO / Frontend** — kein Frontend-Ort rendert heute eine
  Gewitterstufen-Beschriftung; optional für eine spätere Scheibe.
- **`services/comparison_engine.py`** — bewusst unverändert (D7).
- **Fünfte Fusions-Zutat, Radar-Nowcast (E3), Superzellen (`sdi_2`)** — nicht
  Teil dieser Scheibe, s. Known Limitations 1.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue) — diese Scheibe wendet ADR-0007 (Daten statt
  Empfehlungen), ADR-0025 (eine Gewitter-Quelle für alle Kanäle) und
  ADR-0048 (unbekannte/ungeeichte Herkunft = keine Aussage) an, ohne eine
  davon zu ändern.
- **Rationale:** Kein neues Architekturprinzip — additive Sichtbarmachung
  einer bereits vorhandenen internen Größe (welche Zutat trug), keine neue
  Datenquelle, kein neuer Kanal, keine neue Persistenz-Strategie.
  ⚠️ **Nicht zu verwechseln mit ADR-0034** (Herkunfts-Fußzeile zeigt die
  reale Datenquelle/Provider) — das ist eine andere Dimension (WELCHER
  Provider lieferte die Daten), diese Scheibe fragt nach dem AUSLÖSENDEN
  SIGNAL innerhalb der bereits gelieferten Daten.

## Changelog

- 2026-08-12: Initial spec created (Issue #1680, Scheibe 1). Grundlage:
  `docs/context/feat-1680-thunder-herkunft.md`, PO-Entscheidungen vom
  2026-08-11.
- 2026-08-12 (Korrektur vor Freigabe, am Code nachgemessen): D7 lag falsch.
  Die Annahme „wie `hail_flag`, also immer live abgeleitet" trägt für Gewitter
  nicht — `LocationResult.thunder_level_max` **existiert** als Feld (#1285)
  und `_metric_value()` gibt ihm Vorrang. Ohne Kohärenz-Bedingung hätte die
  Zeile eine Stufe aus dem Engine-Lauf mit einer Herkunft aus einer zweiten
  Rechnung gepaart. Ergänzt: AC-12, Mutationsprobe (e0), Known Limitation 3
  neu gefasst. AC-5 auf SMS präzisiert (Premium-SMS im Ortsvergleich-Briefing
  nicht verdrahtet → Known Limitation 6).
