# Context: fix-1841-ausblick-metrik-tagesfenster

Issue: #1841 · Track: Full Process (Intake-Score 4/6) · Stand der Messung: `e6303c75` (origin/main, 2026-08-14)

## Request Summary

Der Trip-Ausblick der Vollmail zeigt seit #1720 S1 — sobald der Nutzer eine Ausblick-Spaltenauswahl gesetzt hat — die Gewitterstufe wieder aus dem auf die Gehzeit geklemmten Tages-Aggregat (`summary.thunder_level_max`) statt aus dem Tagesfenster (`thunder_day_token`), und kennt in diesem Zweig überhaupt keine Nachtangabe. Das ist dieselbe Fehlerklasse, die #1653 für die drei damaligen Ausgabeorte behoben hat.

## Vorbedingung geprüft: was #1671 tatsächlich geliefert hat

Der Intake-Kommentar zu #1841 verlangte ausdrücklich, dies zu **messen** statt aus der Spec zu lesen. Ergebnis:

| Spec-Absicht (#1671) | Gemessene Lieferung |
|---|---|
| Helfer in `helpers.py` | **Eigenes Modul** `src/output/renderers/email/thunder_branch.py` — bewusste Abweichung, Begründung im Modul-Docstring (kein Import von `helpers`, keine Zirkelimport-Gefahr) |
| `resolve_thunder_day_branch()` | vorhanden, `thunder_branch.py:54`, drei Zweige `day` / `none` / `plain` |
| `_thunder_token_parts()` dorthin verschoben | vorhanden, `thunder_branch.py:35` |
| Aufrufer | drei: `compact.py:94`, `outlook.py:358` (Klartext-**Alt**pfad), `narrow.py:593` |

Der Baustein, den #1841 braucht, existiert also. Der Metrik-Zweig ist schlicht **kein vierter Aufrufer**.

## Befund am aktuellen Stand bestätigt

| Behauptung des Issues | Messung |
|---|---|
| Metrik-Zweig liest `getattr(summary, col["field"])` | bestätigt, `outlook.py:581-587` — Aggregat-Quelle |
| Keine Nachtangabe im Metrik-Zweig | bestätigt, `thunder_night_token` kommt in `outlook.py` nur bei `:394` (Altpfad) vor |
| Altpfad unberührt | bestätigt, früher `return` in `outlook.py:146` (HTML) bzw. `continue` in `:339` (Klartext) greifen nur bei `metrics is not None` |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/outlook.py` | **Wirkort.** `build_outlook_row()` ab `:416`; Metrik-Zweig `:564-587`; HTML-Renderstelle `:136-152`; Klartext-Renderstelle `:328-339`; Altpfad mit Tag/Nacht `:358-394` |
| `src/output/renderers/email/thunder_branch.py` | geteilte Zweigwahl aus #1671 — der Baustein, der im Metrik-Zweig fehlt |
| `src/output/renderers/email/helpers.py` | `format_trend_tokens()`; erzeugt `thunder_day_token`/`thunder_night_token`/`thunder_day_origin` ab `:1005` aus `stage["hourly_thunder"]` + Tagesfenster |
| `src/output/renderers/compare_outlook_metric_ids.py` | `resolve_outlook_metrics()` `:45` (Compare), `resolve_trip_outlook_metrics()` `:78` (Trip); `format_outlook_value()` / `outlook_columns()` |
| `src/output/renderers/email/compare_html.py` | Compare-Zeilenbau `:1168`, Compare-HTML-Renderstelle `:1242` |
| `src/services/trip_report_scheduler.py` | Trip-Zeilenbau `:2200` |
| `src/output/renderers/email/html.py` | Trip-HTML-Renderstelle `:1364` |
| `src/output/renderers/email/plain.py` | Trip-Klartext-Renderstelle `:344` |
| `src/output/renderers/comparison.py` | Compare-Klartext-Renderstelle `:360` |

## Aufrufgraph (gemessen)

```
TRIP                                        COMPARE
trip_report_scheduler.py:2200               compare_html.py:1168
  build_outlook_row(                          build_outlook_row(
    trip_display_config=dc,                     metrics=outlook_metrics,
    report_type=...,                          )   # KEIN Tagesfenster
    day_window_start_hour=…,                  #  KEIN trip_display_config
    day_window_end_hour=…)
        │                                           │
        └─ metrics = resolve_trip_outlook_metrics() └─ metrics kommt fertig herein
                        (outlook.py:462-467)
        ▼                                           ▼
html.py:1364  render_outlook_table()        compare_html.py:1242 render_outlook_table()
plain.py:344  render_outlook_plain()        comparison.py:360    render_outlook_plain()
```

**Der Trip/Compare-Diskriminator existiert bereits am Wirkort:** Der Trip reicht `trip_display_config` + `report_type` + Tagesfenster durch und lässt `build_outlook_row` selbst auflösen; der Ortsvergleich übergibt ein fertiges `metrics` und **kein** Tagesfenster. `outlook.py:459` hält das ausdrücklich fest („Ein ausdrückliches `metrics` hat Vorrang (Compare-Pfad unverändert)").

## Struktureller Kern

`format_trend_tokens(stage)` ist eine **reine Funktion des Zeilen-Dicts** — sie liest ausschließlich `stage`-Schlüssel (`hourly_thunder`, `day_window_start_hour`/`_end_hour`, `hourly_thunder_signals`). Alle diese Schlüssel liegen in `row`, **bevor** der Metrik-Zweig bei `outlook.py:564` beginnt (`row.update(optional)` steht bei `:562`).

Der Fix ist damit **innerhalb von `build_outlook_row()` möglich** und muss nicht an beiden Renderstellen dupliziert werden — was zugleich HTML und Klartext in einem Zug erledigt.

Die frühere Vermutung, der Fix müsse an die Renderstellen (weil dort `tok` liegt), ist damit widerlegt.

## Existing Patterns

- **Geteilte Zweigwahl statt vierter Kopie** (#1671, ADR-0055): `resolve_thunder_day_branch(tok, stage)` entscheidet, jeder Aufrufer formatiert selbst.
- **Additive Spalten-Eigenschaften**: `outlook.py:573-585` reicht `hail` und `signals` als Zusatzschlüssel des Spalten-Dicts an `format_outlook_value()` durch. Eine geänderte Quelle könnte demselben Muster folgen.
- **Stufe und Herkunft aus DEMSELBEN Fenster**: `helpers.py:1025-1035` und der Kommentar `outlook.py:574-579` halten fest, dass eine Herkunft aus einem anderen Fenster als die gezeigte Stufe der AC-12-Fehler aus #1680 Scheibe 1 wäre.

## Dependencies

- **Upstream:** `summarize_points()` / `aggregate_stage()` → `SegmentWeatherSummary`; `resolve_configured_window()` (Tagesfenster aus `trip.report_config`); `render_threshold_peak_value()`; `union_of_max_carriers()` / `thunder_signal_label()`.
- **Downstream:** Trip-Vollmail HTML + Klartext; Ortsvergleich-Mail HTML + Klartext. `build_outlook_row` ist ausdrücklich der **eine** bewusst geteilte Trip/Compare-Baustein (`tests/unit/test_notification_service.py:191` führt genau diesen Import als einzige erlaubte Ausnahme).

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` | hat den Metrik-Zweig für den Trip geöffnet; erwähnt Gewitter/Tagesfenster/Nacht nicht |
| `docs/specs/modules/fix_1671_kompaktmail_ausblick_tagesfenster.md` | grenzt diesen Befund unter „Nicht in dieser Scheibe" ab; liefert den geteilten Helfer |
| #1653 (Tag/Nacht-Trennung) | Ursprungsentscheid: Gehzeit-Aggregat ist für den Trip falsch |
| `feat_1680_s5a` AC-11b | Gegenentscheid für den **Ortsvergleich**: dort ist das Tages-Aggregat richtig |
| ADR-0055 | „drei Auflösungen derselben Frage" — die Regel, gegen die #1720 S1 verstieß |

## Risks & Considerations

1. **🔴 Ein bestehender Test verbietet den naiven Fix.**
   `tests/tdd/test_outlook_day_night_thunder_split.py:665` (`test_compare_metrics_cells_unaffected_by_day_night_split`) sichert zu, dass `row["cells"]` **mit und ohne** `day_window_*` identisch bleibt — aufgerufen mit `metrics=` und ohne `trip_display_config`. Der Test kann Trip und Compare nicht unterscheiden; er prüft nur „cells reagieren nicht auf das Tagesfenster".
   ⇒ Ein Fix, der am Tagesfenster allein ansetzt, macht diesen Test rot. Ein Fix, der am **Trip-Diskriminator** (`trip_display_config`/`report_type`) ansetzt, lässt ihn grün — und das ist auch fachlich richtig, weil AC-11b für Compare weiter gilt.

2. **🔴 Ein zweiter Test verbietet Trip-Formatierung im Compare-Zweig.**
   `test_compare_plain_carries_no_trip_format_remnants` (`:645`) verbietet `"⚡"`, `"°C"`, `"↳"` und `"nachts"` in der Compare-Klartext-Ausgabe des Metrik-Zweigs. Eine Nachtangabe oder ein Blitz-Präfix darf also niemals im Compare-Pfad landen.

3. **🔴 Compare hat sehr wohl eine Stundenreihe.**
   `compare_html.py:1168` übergibt `day_points` an `build_outlook_row` — `hourly_thunder` ist für Compare-Zeilen also **befüllt**. Der Docstring von `resolve_thunder_day_branch` (`thunder_branch.py:65-68`) beschreibt `"plain"` als „keine Stundenreihe (Alt-Aufrufer/**Compare**)". Diese Zuordnung trägt für den Ausblick **nicht**: ein blindes `resolve_thunder_day_branch()` im Metrik-Zweig würde für Compare `"day"`/`"none"` liefern und damit dessen 24-Stunden-Aggregat auf ein Tagesfenster verengen — genau das, was AC-11b ausschließt. (Für Compare ist das Aggregat korrekt, weil es über den **Kalendertag** gebildet wird, nicht über die Gehzeit.)

4. **Stufe und Herkunft hängen zusammen.**
   `outlook.py:580` reicht `summary.thunder_level_max_signals` als Herkunft mit — dieselbe Rechnung wie die gezeigte Stufe. Wird die Stufe auf das Tagesfenster umgestellt, muss die Herkunft mitwandern (`thunder_day_origin` aus `format_trend_tokens`), sonst entsteht der AC-12-Fehler, vor dem der Kommentar an dieser Stelle ausdrücklich warnt.

5. **Formatentscheidung offen.** Die Metrik-Zelle zeigt heute ein Stufen-Label über `_fmt_thunder()`. Der Altpfad zeigt `⚡wort @stunde`. Nur die **Quelle** zu tauschen (Tagesfenster-Stufe statt Aggregat-Stufe) hält das Zellformat stabil; die Uhrzeit mitzunehmen wäre eine zusätzliche Formatänderung.

6. **Nachtangabe ist eine Produktfrage, keine Bugfrage.** Der Metrik-Zweig ist eine **Spaltenauswahl des Nutzers**. Eine Nachtzeile zu ergänzen, die niemand gewählt hat, wäre eine eigene Designentscheidung — Freigabe des PO nötig.

7. **Nebenbefund (nicht in dieser Scheibe):** Der Metrik-Zweig färbt seine Zellen **gar nicht** ein — `outlook.py:141` ruft `_otd(...)` ohne `bg=`, während der Altpfad Ampelfarben setzt. Das betrifft alle Spalten, nicht nur Gewitter. Gehört nach #1199 oder als eigenes Issue, nicht in diesen Fix. (Erledigt zugleich die Anschlussfrage aus dem #1801-Kommentar: der `cells`-Pfad umgeht `thunder_ampel_band()` nicht — er färbt schlicht nicht.)

## Testlage

| Testdatei | Was sie bewacht |
|---|---|
| `tests/tdd/test_outlook_day_night_thunder_split.py` | #1653: Tag/Nacht im Altpfad; **plus die beiden Compare-Wächter aus Risiko 1 und 2** |
| `tests/tdd/test_trip_outlook_metric_selection.py` | #1720 S1: Spaltenauswahl im Trip; arbeitet mit Referenzdatei (laut #1841-Kommentar mit datiertem Kommentar über der Assertion — bei Änderung **zweiten** Eintrag anhängen, nicht ersetzen) |
| `tests/tdd/test_trip_outlook_parity.py` | Byte-Gleichheit des Trip-Ausblicks **ohne** Auswahl |
| `tests/tdd/test_compare_outlook.py`, `test_compare_outlook_placement.py` | Compare-Ausblick |
| `tests/tdd/test_shared_outlook_renderer.py` | Byte-Gleichheit der extrahierten geteilten Renderer |
| `tests/golden/email/test_outlook_thunder_day_night_golden.py` | Golden-Datei über `render_outlook_table` + `render_outlook_plain` |
| `tests/tdd/test_thunder_origin_outlook.py`, `test_thunder_origin_preview.py` | #1680: Herkunft der Gewitterstufe |
| `tests/tdd/test_kompaktmail_ausblick_tagesfenster.py` | #1671: die vier Zweige von `resolve_thunder_day_branch()` |

## Offene Fragen für die Analyse-Phase

1. Fix in `build_outlook_row()` am Trip-Diskriminator (`trip_display_config`/`report_type` gesetzt) — bestätigen, dass das der einzige verlässliche Trip/Compare-Unterschied am Wirkort ist.
2. Wandert die Herkunft (`signals`) mit der Stufe ins Tagesfenster? (Risiko 4 sagt: muss.)
3. Braucht der Metrik-Zweig eine Nachtangabe — und wenn ja, als eigene Spalte, als Zusatz in der Gewitterzelle oder gar nicht? **PO-Entscheid nötig.**
4. Bleibt das Zellformat unverändert (nur Quelltausch) oder kommt die Uhrzeit mit?

---

# Analysis (Phase 2)

Gegengeprüft durch einen unabhängigen `analysis-challenger` (Verdict **CONFIRMED**, B1–B5 halten) und eine Spec-/ADR-Auswertung. Korrekturen an meinen eigenen Aussagen aus Phase 1 sind unten ausdrücklich markiert.

## Type

**Bug.** Regression aus #1720 S1 (gemerged 2026-08-14), nutzersichtbar.

## Korrekturen an Phase 1

1. **🔴 AC-11b begründet nicht, was ich behauptet habe.** Ich schrieb, für den Ortsvergleich sei das Tages-Aggregat „richtig". `feat_1680_s5a` AC-11b verlangt tatsächlich nur **Kohärenz**: die Herkunft muss aus derselben Rechnung stammen wie die daneben gezeigte Stufe. Der eigentliche Compare-Schutz ist **#1653 AC-6**: „bleibt die Compare-Ausgabe **byte-identisch** zum Stand vor dieser Änderung" — dort wurde der Metrik-Zweig ausdrücklich ausgenommen, **weil er damals nur den Ortsvergleich bediente**. Genau diese Voraussetzung hat #1720 S1 aufgehoben.

2. **`test_compare_plain_carries_no_trip_format_remnants` (`:645`) ist für diesen Fix kein Nachweis.** Es ruft `render_outlook_plain()` mit vorgefertigten `rows` (die `cells` bereits enthalten) und berührt `build_outlook_row()` nie. Es bleibt grün, gleichgültig ob der Fix richtig oder falsch ist. Darf in der Adversary-Runde **nicht** als Beleg für die Trip/Compare-Trennung zitiert werden.

3. **Es gibt keine zweite, abweichende Auflösung der Spaltenauswahl.** Ich hatte einen Versatz zwischen `trip_report.py:218` (Spalten) und `trip_report_scheduler.py:2200` (Zellen) vermutet. Nachgemessen: beide lesen dieselbe ungekollabierte `trip.display_config` (`trip_report.py:133`, `trip_report_scheduler.py:2184`) und rufen denselben Auflöser. Kein Befund — ADR-0055 Punkt 4 trägt.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/renderers/email/outlook.py` | MODIFY | Metrik-Zweig `:564-587`: Gewitter-Spalte (`kind == "ordinal"`) im **Trip**-Fall aus dem Tagesfenster statt aus `summary.thunder_level_max` |
| `src/output/renderers/email/helpers.py` | MODIFY | `format_trend_tokens()` additiv um die Tagesfenster-**Stufe** ergänzen — eine Fensterauflösung, an derselben Stelle wie `thunder_day_token` |
| `tests/helpers/trip_outlook_selection.py` | MODIFY | **Pflicht** — `outlook_rows()` auf die echte Trip-Aufrufkonvention ziehen, sonst prüft die #1720-S1-Suite weiter den Compare-Weg |
| `docs/reference/metric_output_matrix.md` | MODIFY | drei veraltete Aussagen korrigieren (`:89`, `:214`, `:376`) |
| `docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md` | MODIFY | Erratum: „Der Metrik-Zweig ist compare-exklusiv" (`:440-444`) ist seit #1720 S1 falsch |
| Testdateien | CREATE/MODIFY | siehe Nachweisführung |

## Technical Approach (Empfehlung)

**Der Fix ist der vierte Aufrufer des geteilten Helfers aus #1671 — genau wie der PO-Intake es vorgezeichnet hat.**

**Wirkort:** `build_outlook_row()`, Metrik-Zweig `outlook.py:564-587`. Dort — und nicht an den Renderstellen — weil `cells` dort entstehen und HTML wie Klartext sie unverändert ausgeben. Ein Fix an den Renderstellen wäre zwei Kopien.

**Diskriminator:** `trip_display_config is not None`. Gemessen (Challenger, unabhängig bestätigt): genau **zwei** Produktionsaufrufer, sauber getrennt — Trip setzt immer `trip_display_config`/`report_type`/Tagesfenster und nie `metrics=`; Compare setzt immer `metrics=` und nie `trip_display_config`. Keine dritte Fundstelle in `api/`, `sms_trip.py` oder Vorschau-Endpunkten. Nicht an `report_type` festmachen (beim Trip immer gesetzt, sagt nichts über den Pfad) und **nicht an der Präsenz des Tagesfensters** — das ist genau die Falle, die `test_compare_metrics_cells_unaffected_by_day_night_split` (`:665`) gezielt stellt.

**Zweigwahl:** `resolve_thunder_day_branch(format_trend_tokens(row), row)` aus `thunder_branch.py` — keine vierte eigene if/elif-Kette.
- `"day"` → Stufe aus dem Tagesfenster
- `"none"` → `ThunderLevel.NONE` (explizit „kein Gewitter")
- `"plain"` → `summary.thunder_level_max` unverändert (heutiges Verhalten)

**Woher die Stufe kommt.** `format_outlook_value()` erkennt die Gewitterspalte an `kind == "ordinal"` (`compare_outlook_metric_ids.py:165`) und übergibt sie an `_fmt_thunder(ThunderLevel, hail, signals)` — es braucht also ein **ThunderLevel-Objekt**, nicht den String `thunder_day_token`. Empfehlung: `format_trend_tokens()` additiv um die Tagesfenster-Stufe erweitern, berechnet aus denselben `_win_start`/`_win_end` wie `thunder_day_token` (`helpers.py:1005-1022`). Damit bleibt es bei **einer** Fensterauflösung — die Regel, gegen die #1653 und #1680 S5a ausdrücklich schreiben. Den Token zurückzuparsen wäre die schlechtere Variante.

⚠️ **Fallstrick bei der Herleitung:** `row["hourly_thunder_signals"]` ist `None`, sobald **kein** Datenpunkt eine Trägerliste führt (`outlook.py:558-560`, Alt-Schnappschüsse) — die Stufe darf deshalb **nicht** allein daraus abgeleitet werden, sonst fällt sie für Bestandsdaten still aus. `row["hourly_thunder"]` ist dagegen immer befüllt, trägt die Stufe aber als Fließkommazahl über `thunder_label_value()`.

**Herkunft muss mitwandern.** `outlook.py:580` reicht heute `summary.thunder_level_max_signals` durch — die Herkunft des Aggregats. Wandert die Stufe ins Tagesfenster, muss die Herkunft mit (`union_of_max_carriers` über dasselbe Fenster, `thunder_scale.py:118`), sonst entsteht der AC-12-Fehler, vor dem der Kommentar an genau dieser Stelle warnt.

**Zellformat bleibt unverändert** — nur die Quelle wird getauscht. Keine Uhrzeit, kein `⚡`. Das hält den Compare-Zweig und die bestehenden Formatwächter unberührt.

## Nachweisführung (der heikelste Teil)

🔴 **`tests/helpers/trip_outlook_selection.py:163` baut die Zeilen mit `metrics=` — der Compare-Konvention** — und behauptet im Docstring, das sei der Parameter, den der Zeitplaner füllt. Gemessen füllt `trip_report_scheduler.py:2200` stattdessen `trip_display_config=dc, report_type=…`. Die gesamte #1720-S1-Renderer-Suite fährt den Metrik-Zweig damit über den **Compare**-Weg.

Folge: Ein Fix am Trip-Diskriminator wäre für diese Tests unsichtbar — sie blieben grün und bewiesen nichts. **Der Helfer muss auf die echte Trip-Konvention gezogen werden, bevor irgendein Nachweis zählt.** Die Testdatei warnt selbst davor (`test_trip_outlook_metric_selection.py:17-20`), und ADR-0055 (`:167-171`) warnt unabhängig davon für `test_trip_outlook_parity.py`: der ruft die Renderer isoliert auf, durchläuft die Verdrahtung nie und blieb bei einer Mutation grün, während vier andere Tests rot wurden.

**Nicht betroffen:** `REFERENCE_TABLE` in `test_ac1_bestandstrip_html_ausblick_bleibt_byte_identisch` rendert einen Trip **ohne** Auswahl, bewacht also den Altpfad. Der im Issue-Kommentar erwartete zweite datierte Eintrag wird voraussichtlich nicht nötig — vor dem Ändern der Aufzeichnung trotzdem nachmessen.

**Mutations-Gegenprobe (Pflicht):** Diskriminator auf `True` festnageln → mindestens ein Compare-Test muss rot werden. Diskriminator auf `False` festnageln → mindestens ein Trip-Test muss rot werden. Wird nur eine Richtung rot, bewacht der Nachweis nur die halbe Trennung.

## Scope Assessment

- Produktivdateien: 2 (`outlook.py`, `helpers.py`) — geschätzt **+40/−5 LoC**, deutlich unter dem 250er-Budget
- Testdateien: 1 Anpassung (Testhelfer) + 1 neue Verhaltensdatei — geschätzt **+150 LoC**, unter dem 500er-Budget
- Dokumentation: 2 Dateien (zählen nicht aufs Budget)
- **Risiko: MEDIUM** — nicht mehr HIGH wie beim Intake: der Diskriminator ist gemessen eindeutig, der geteilte Helfer liegt fertig vor, und die einzige echte Sperre (Testhelfer am falschen Pfad) ist erkannt.

## Dependencies & Reihenfolge

1. Testhelfer auf die Trip-Konvention ziehen — **zuerst**, sonst ist jeder folgende Nachweis wertlos
2. `format_trend_tokens()` additiv um die Tagesfenster-Stufe erweitern
3. Metrik-Zweig auf den geteilten Helfer umstellen, am Trip-Diskriminator gattert
4. Herkunft mitziehen
5. Doku-Korrekturen

## Open Questions

- [ ] **PO: Braucht der Metrik-Zweig eine Nachtangabe?** Dafür spricht: #1653 wurde eingeführt, weil ein Nachtgewitter hinter dem Tageswert verschwinden konnte — als Sicherheitsproblem eingestuft, nicht als Kosmetik. Ein Trip-Nutzer, der die Gewitter-Spalte wählt, verliert im Metrik-Zweig genau die Nachtsicht, die der Altpfad dafür bekam. Dagegen spricht: der Nutzer hat Spalten gewählt, „Nacht" war keine davon; eine ungefragte Zusatzzeile wäre eine neue Designentscheidung.
- [ ] **PO: Fehlende Ampelfarben — eigenes Issue?** Der Metrik-Zweig färbt **keine** Zelle ein (`outlook.py:141`, `_otd()` ohne `bg=`), der Altpfad schon. Gemessen (Challenger): der Pfad existierte für Compare bereits seit #1361/#1368, ist also nicht durch #1720 S1 entstanden — wohl aber dadurch erstmals für **Trip**-Nutzer sichtbar, die vorher Ampelfarben hatten. Das ist ein nutzersichtbares Downgrade und fällt damit unter die Nebenbefund-Regel (a) → eigenes Issue statt Sammel-Eintrag #1199. Nicht in dieser Scheibe.
