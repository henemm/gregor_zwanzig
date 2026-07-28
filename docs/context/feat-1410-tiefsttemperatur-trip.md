# Context: feat-1410-tiefsttemperatur-trip

<!-- Issue #1410 — Epic #1372 (Metrik-Zielbild), Nachfolge-Scheibe zu #1357 S4a -->

## Request Summary

Die **Tiefsttemperatur während des Trips** (kälteste Stunde unterwegs) soll als
eigenständiger Wert ausgegeben werden — für **gemessene und gefühlte**
Temperatur. PO-Vorgabe: Die gefühlte Temperatur verhält sich und rechnet
**exakt** wie die gemessene (derselbe Algorithmus auf `wind_chill_c` statt
`t2m_c`) — kein Nachbau, keine Sonderbehandlung. Eingeschlossener Zuschnitt
(PO-Entscheidung 2026-07-28, Intake): die Einführung der gefühlten Temperatur
in den Kurzformen gehört mit dazu.

## Zentraler Befund der Kontextphase: Die Lücke ist kleiner als im Ticket beschrieben

Das Ticket (und die S4a-Spec, „Verifizierte Fakten" Punkt 4) stützt sich auf
`grep -c wind_chill` == 0 in `narrow.py`/`compact_summary.py` und schließt
daraus auf vollständige Unsichtbarkeit in **allen** Kurzformen. Das ist für
Telegram **falsch**: Der Telegram-Renderer ist **katalog-generisch** und nennt
deshalb keine einzige Metrik beim Namen.

Belegkette:
- `email/helpers.py:93-121` (`dp_to_row`) füllt Zeilen über
  `row[metric_def.col_key] = getattr(dp, metric_def.dp_field, None)` — für
  **jede** aktivierte Größe des Katalogs.
- `metric_catalog.py:101-112`: `wind_chill` trägt `dp_field="wind_chill_c"`,
  `col_key="felt"`, `compact_label="TF"`, `summary_fields={"min":
  "wind_chill_min_c", "max": "wind_chill_max_c"}`.
- `trip_report.py:127` baut `seg_tables` daraus und reicht sie an Telegram
  (`narrow.py:479`) **und** Mail durch.
- `narrow.py:544-550` iteriert `dc.get_enabled_metric_ids()` und rendert je
  Größe `_overview_line()` → `{Kürzel} {Min}-{Max}@{Peak-Stunde}`
  (`narrow.py:398-424`).

**Folge:** Ein Trip mit aktivierter „Gefühlte Temperatur" zeigt in Telegram
bereits heute `TF {min}-{max}@{h}` — also genau die geforderte Tiefst-/
Höchstwert-Spanne. Zu verifizieren bleibt (Analyse-Phase), ob das im echten
Versandpfad tatsächlich erscheint.

### Ist-Matrix je Ausgabe (Stand `07fe4641`)

| Ausgabe | Gefühlte Temperatur | Tiefstwert während des Trips |
|---|---|---|
| Mail-Kachelzeile | seit #1357 S4a als Spanne, Auswertung wählbar | als untere Grenze der Spanne (Gehzeit-Fenster) |
| Mail-Stundentabelle | vorhanden (Spalte „Feels", katalog-generisch) | implizit je Stunde |
| Telegram Kurzübersicht + Tabellen | **vorhanden** (`TF min-max@h`, katalog-generisch) | vorhanden (Spannen-Untergrenze) |
| E-Mail-Kurzzusammenfassung (Erzählsatz) | **fehlt** — handverdrahtete Größenliste | abends Spanne, morgens nur Höchstwert |
| SMS-Token | **fehlt** — `N`/`D` sind rein gemessen, `WC` unerreichbar | `N` = **Nacht am Ziel** (abends), morgens gar nichts |

Die echte Arbeit liegt damit in **zwei** Ausgaben: SMS und
E-Mail-Kurzzusammenfassung.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/sms_trip.py:131-240` | `_segments_to_normalized_forecast()` — aggregiert `temps_min`/`temps_max` über Segmente; setzt `wind_chill_*` nicht; Abend-Sonderregel `night_temp_min_c()` bei `report_type == "evening"` (Zeile 143-146) |
| `src/output/tokens/dto.py:22-38` | `DailyForecast` — hat `temp_min_c`/`temp_max_c` und ein **ungenutztes** `wind_chill_c` (Einzelwert, kein Paar) |
| `src/output/tokens/builder.py:222-237` | `N`/`D`-Token; hartes Gate „`N` nur abends" (Zeile 228) |
| `src/output/tokens/builder.py:174-196` | `_wintersport()` mit `WC` — nur erreichbar bei `profile="wintersport"`, das im Produktivpfad nie gesetzt wird (nur `src/app/cli.py:233`) |
| `src/output/tokens/builder.py:37-69` | `PRIORITY` / `POSITIONAL` / `POS_INDEX` — Token-Reihenfolge und Kürzungsrang; jedes neue Token muss hier eingeordnet werden |
| `src/output/renderers/compact_summary.py:140-176` | Handverdrahtete Größenliste des Erzählsatzes: nur `temperature`, `cloud_total`, `precipitation`, `wind`, `thunder` |
| `src/output/renderers/compact_summary.py:229-250` | `_format_temperature()` — morgens nur Höchstwert, abends Spanne mit Nacht-Tiefstwert |
| `src/output/renderers/narrow.py:368-424` | `_overview_line()` — katalog-generisch, Temperatur-Sonderfall (morgens nur Max, abends Nacht-Min) hart auf `metric_id == "temperature"` |
| `src/output/renderers/day_window.py:103,196` | `build_day_window_points()` (04–19 Uhr) und `night_temp_min_c()` — die zwei konkurrierenden Fensterlogiken |
| `src/services/segment_weather.py:254-281` | `_aggregate_for_segment()` — Beleg, dass `temp_*` und `wind_chill_*` aus **derselben** zeitgefilterten Zeitreihe stammen; kein Eingriff nötig |
| `src/app/metric_catalog.py:101-112` | `wind_chill`-Definition inkl. `summary_fields` (min/max bereits vorhanden) |
| `docs/reference/sms_format.md:255-285` | Vertrag: `WC` an `trip.profile == "wintersport"` gebunden; Null-Formen; `N` nur abends |

## Existing Patterns

- **Katalog-generisch schlägt handverdrahtet.** Mail-Tabelle und Telegram
  rendern jede aktivierte Größe ohne Namensnennung. SMS-Token und
  Kurzzusammenfassung sind die beiden verbliebenen handverdrahteten Inseln —
  dort entsteht die Lücke, dort ist auch die Angriffsfläche für den Fix.
- **Auswertungswahl je Größe** (#1357 S4a): `metric_catalog.summary_field_for()`
  / `available_aggregations()` / `pill_default_aggregations()` sind bereits als
  geteilte Naht angelegt und für `wind_chill` mit `min`/`max` bestückt — die
  natürliche Quelle auch für die Kurzformen.
- **Abend-/Morgen-Asymmetrie** (#1319 Scheibe D) ist an drei Stellen dupliziert
  (`sms_trip.py:143`, `compact_summary.py:242-244`, `narrow.py:408-412`) und
  jeweils hart auf die gemessene Temperatur bezogen.
- **Null-/Lücken-Darstellung:** `-` bzw. `?` bei Datenlücke (`has_data_gap`).

## Dependencies

- **Upstream:** `SegmentWeatherSummary.wind_chill_min_c` / `wind_chill_max_c`
  (existieren, korrekt gefenstert), `metric_catalog`, `day_window`.
- **Downstream:** SMS-Zeichenhaushalt GSM-7 / 160 Zeichen (#624) —
  `output/tokens/render.py::render_line()` kürzt nach Priorität; jedes neue
  Token verdrängt ein bestehendes. E-Mail-Betreffzeile
  (`TokenLine.filter_for_subject()`) nutzt dieselbe Token-Liste.
- **Gates:** `compact_summary.py` ist Mail-Inhalts-Datei → **Renderer-Commit-Gate
  #811** greift (Modus-Matrix-Test + frischer `briefing_mail_validator.py`-Lauf
  gegen echt zugestellte Staging-Mail).

## Existing Specs

| Spec | Rolle |
|---|---|
| `docs/specs/modules/trip_aggregation_selection.md` (#1357 S4a) | Direkter Vorgänger; enthält die Schnittempfehlung „Scheibe 2 = Kurzformen" = dieses Ticket |
| `docs/specs/modules/night_temp_evening_only.md` (#1319 D) | Bedeutung von `N` (Nacht am Ziel), PO-freigegeben 2026-07-23 — **berührt** durch die offene Frage 3 |
| `docs/specs/modules/sms_daywindow_aggregation.md` (ADR-0025) | Tagesfenster 04–19 Uhr für `R`/`PR`/`W`/`G`/`TH:` — nicht für Temperatur |
| `docs/specs/modules/sms_trip_formatter.md` | SMS-Formatvertrag |
| `docs/specs/modules/email_metrics_summary_664.md` | Kachelzeile |

## Risks & Considerations

1. **SMS-Zeichenbudget.** 160 Zeichen sind hart. Ein zusätzliches Token
   verdrängt bei vollen Zeilen ein bestehendes. Der Zuschnitt muss festlegen,
   welchen Rang die gefühlte Temperatur in der Kürzungsreihenfolge bekommt.
2. **Zwei ähnlich aussehende Kältewerte.** `N` bedeutet heute „Nacht am
   Schlafplatz". Ein zweiter Tiefstwert „kälteste Stunde unterwegs" daneben ist
   ohne klare Kürzel-Trennung missverständlich (Ticket, Punkt 2).
3. **Offene Designfrage: Abend-Nacht-Regel für die gefühlte Temperatur?**
   Gilt `night_temp_min_c()` analog, oder bleibt die gefühlte Temperatur immer
   die kälteste Gehstunde? Berührt eine PO-freigegebene Spec → braucht eine
   eigene Entscheidung, keine Nebenentscheidung.
4. **Offene Designfrage: Rechenfenster.** Gehzeit (`_collect_hiking_window_dps`,
   heute für Temperatur) vs. Tagesfenster 04–19 Uhr. PO-Vorgabe „exakt wie die
   normale Temperatur" spricht für Gehzeit — dann ist die Frage bereits
   beantwortet und muss nur festgeschrieben werden.
5. **Morgenbriefing hat heute gar keinen Tiefstwert** (`N` entfällt bewusst,
   `compact_summary` zeigt morgens nur den Höchstwert). Die Ticket-Anforderung
   „Tiefsttemperatur während des Trips ausgeben" kollidiert direkt mit dieser
   PO-freigegebenen Morgen-Regel — Klärungsbedarf.
6. **Vertragsänderung `sms_format.md`** inkl. Klärung des toten
   `trip.profile`-Gates für `WC` (vorbestehende Kontraktlücke).
7. **Golden-Tests** für Mail/SMS reagieren auf jede Token-Änderung.

## Next

`/20-analyse` — insbesondere: Telegram-Ist-Zustand am echten Versandpfad
verifizieren und die vier offenen Fragen (Risiken 2–5) für die PO-Vorlage
zuspitzen.

---

## Analysis (Phase 2, 2026-07-28)

### Type

Feature (Erweiterung bestehender Ausgabewege; keine neue Architektur).

### Verifikationsergebnis der drei Recherchen

**1. Telegram — These BESTÄTIGT (mit korrigierter Belegkette).**
Die gefühlte Temperatur erscheint bereits heute in der Telegram-Kurzübersicht
als `TF {min}-{max}@{h}` und bei Standardkonfiguration zusätzlich als
Tabellenspalte.
- Versandkette: `notification_service.py:253,345,354` → `trip_report.py:225-242`
  (`render_telegram_bubbles`) → `narrow.py:544-550` (`_overview_line` je
  `dc.get_enabled_metric_ids()`).
- **Korrektur zur Kontext-Phase:** Der echte Pfad nutzt **nicht**
  `email/helpers.py::dp_to_row`, sondern eine **eigene Kopie**
  `trip_report.py:468-496` (`_dp_to_row`) samt `_extract_hourly_rows`
  (`:306-323`). Funktional gleich (`:486` setzt die Spalte aus
  `getattr(dp, dp_field)`), aber **ohne** den `selectable`-Guard von
  `email/helpers.py:110-111`. → Nebenbefund: doppelter Zeilenbau (#1199).
- `wind_chill_c` wird produktiv befüllt: `providers/openmeteo.py:777`
  (`apparent_temperature`), `providers/geosphere.py:552-573`.
- `get_enabled_metric_ids()` (`models.py:627-629`) ist **ungefiltert** durch
  Kanal/Spaltenlimit → die Kurzübersicht-Zeile ist unabhängig von
  `max_table_cols=8` (`channel_layout.py:22,74-75`).
- **Kein Test und keine Golden-Datei belegt das.**
  `tests/tdd/test_issue_1001_telegram_bubbles.py` enthält keinen
  `wind_chill`/`felt`/`TF`-Fall → Absicherung nötig, sonst kann die
  Eigenschaft unbemerkt wegbrechen.

**2. SMS — es ist Platz, und die Kürzungsmechanik ist dreiteilig.**
- Reale Golden-Zeilen: 64–122 Zeichen von 160 (`tests/golden/sms/*.txt`;
  voll besetzt nur `corsica-vigilance` mit 122).
- Drei **unabhängige** Reihenfolgen: `POSITIONAL`/`POS_INDEX`
  (`builder.py:55-69`) = Anzeigereihenfolge; `DROP_ORDER` (`render.py:9-10`)
  = was zuerst wegfällt; `PRIORITY` (`builder.py:37-46`) = nur
  Last-Resort-Rang (`render.py:81-95`). Ein neues Token muss in **allen
  dreien** eingeordnet werden.
- Freie, kollisionsfreie Kürzel u.a. `GN`/`GD` bzw. `FN`/`FD`. Belegt sind
  `WC`, `HT`/`CD` (amtliche Warn-Kürzel `hazard_symbols.py:21-22`), `TH`,
  `HR`, `SN`, `W`, `FR`, `CL`, `IC`.
- **E-Mail-Betreff ist entkoppelt:** `TokenLine.filter_for_subject()`
  (`dto.py:119-127`) ist ein toter Stub ohne Aufrufer; real filtert
  `subject.py:167` über die Positiv-Liste `_WHITELIST_FORECAST = ("D","W","G")`.
  Ein neues Token erscheint dort also **nicht** automatisch.
- Zeichensatz: keine echte GSM-7-Prüfung im Produktivcode, nur `fold_ascii()`
  (`utils/ascii_fold.py:51-89`). Token-Werte tragen ohnehin keine Einheit
  (`tokens/metrics.py:70-71`).
- Doku-Drift: `sms_format.md:322-328` listet 6 Kürzungsschritte, der Code hat
  einen siebten (Last-Resort, `render.py:81-95`) → mitzuziehen.

**3. Kurzzusammenfassung — nur E-Mail, fünf Golden-Paare betroffen.**
- Der Erzählsatz landet **ausschließlich** in der E-Mail
  (`trip_report.py:154-159,197` → `email/plain.py:138-139`,
  `email/html.py:1220-1221`). SMS und Telegram bekommen ihn **nicht**.
- Handverdrahtete Reihenfolge (`compact_summary.py:140-182`): Temperatur,
  Bewölkung, Niederschlag, Wind, Gewitter — mit `", ".join(parts)`, ohne
  Längenbegrenzung.
- **Formatvorbild existiert bereits** (aus #1357 S4a):
  `email/helpers.py:1205-1208,1285-1319` rendert `gef. 11.6–12.6°C · Max 15:00`
  (Präfix `"gef. "`, 1 Nachkommastelle, En-Dash) — belegt in
  `tests/golden/email/arlberg-winter-morning-plain.txt:10`.
- Brechen bei Änderung: 5× `*-plain.txt` + 5× `*-html.txt` Goldens,
  `tests/unit/test_trip_summary_text.py:104` (byte-identisch),
  `tests/integration/test_multi_day_trend.py:382-388,499`,
  `tests/tdd/test_night_temp_evening_only.py:239,280`. Neu einfrieren über
  `tests/golden/email/regenerate.py`.

**4. Morgen-/Abend-Asymmetrie: fünf Fundstellen, alle nur für `temperature`.**
`compact_summary.py:242-250` · `tokens/builder.py:222-228` (hartes Gate
„`N` nur abends") · `sms_trip.py:143-146` · `narrow.py:288-289`
(Vortagsvergleich) · `narrow.py:407-411` (Kurzübersicht).
Keine davon berücksichtigt `wind_chill`.

### Affected Files (vorläufig, abhängig von der PO-Entscheidung)

| Datei | Art | Beschreibung |
|---|---|---|
| `src/output/tokens/dto.py` | MODIFY | `wind_chill_min_c`/`wind_chill_max_c` auf `DailyForecast` (ersetzt das ungenutzte `wind_chill_c`) |
| `src/output/renderers/sms_trip.py` | MODIFY | Aggregation analog `temps_min`/`temps_max` |
| `src/output/tokens/builder.py` | MODIFY | neues Token-Paar + Eintrag in `POSITIONAL`, `PRIORITY` |
| `src/output/tokens/render.py` | MODIFY | `DROP_ORDER`-Einordnung |
| `src/output/renderers/compact_summary.py` | MODIFY | gefühlte Temperatur im Erzählsatz (Mail-Inhalts-Datei → Gate #811) |
| `src/output/renderers/narrow.py` | MODIFY (evtl.) | Abend-/Morgen-Sonderregel auf `wind_chill` ausdehnen, falls gewünscht |
| `docs/reference/sms_format.md` | MODIFY | Vertrag: neues Token, Null-Form, Kürzungsreihenfolge (+ Drift-Korrektur) |
| `tests/golden/email/*.txt`, `tests/golden/sms/*.txt` | MODIFY | neu einfrieren |
| Tests (neu) | CREATE | Telegram-Absicherung `TF`-Spanne; SMS-Token; Erzählsatz |

### Scope Assessment

- Dateien: 6–7 Produktivdateien + Vertragsdokument + Goldens
- Geschätzte LoC: **+90 bis +140** Produktivcode (unter der 250er-Grenze)
- Risiko: **MEDIUM** — SMS-Vertragsänderung und fünf Golden-Paare; keine
  Persistenz-, Auth- oder Schema-Berührung

### Technical Approach (Empfehlung)

1. **Rechenweg:** keine neue Berechnung. `wind_chill_min_c`/`wind_chill_max_c`
   stammen bereits aus derselben zeitgefilterten Zeitreihe wie `temp_min_c`/
   `temp_max_c` (`segment_weather.py:254-281`). Die PO-Vorgabe „exakt so
   berechnet" ist damit erfüllt — es wird nur abgeholt und durchgereicht.
2. **SMS:** `DailyForecast` bekommt das Paar, `_segments_to_normalized_forecast`
   aggregiert es analog, der Builder gibt ein Token-Paar aus. Das tote
   `WC`-Token entfällt aus dem Vertrag (nie erreichbar).
3. **Erzählsatz:** die gefühlte Temperatur als zweiten Listeneintrag mit dem
   bereits etablierten Präfix `gef. ` und derselben Spannenformatierung wie die
   Kachelzeile — geteilte Formatierung statt Nachbau.
4. **Telegram:** unverändert lassen, aber durch einen Test festnageln.
5. **Nebenbefund** (nicht Teil dieser Lieferung, → #1199): doppelter Zeilenbau
   `trip_report.py:468-496` vs. `email/helpers.py:93-121`; Doku-Drift
   `sms_format.md:322-328`.

### Open Questions (PO-Entscheidung nötig)

- [x] **F1 — PO-Entscheidung 2026-07-28: „Morgens und abends".** Die kälteste
      Stunde **unterwegs** erscheint neu **morgens** (wo es heute gar keinen
      Tiefstwert gibt) **und abends zusätzlich** zur Nacht-Tiefsttemperatur am
      Schlafplatz. `N` behält seine Bedeutung (#1319 Scheibe D bleibt gültig,
      wird nicht umgekehrt) — der neue Wert tritt daneben, nicht an seine
      Stelle. Zwei verschiedene Fragen, beide entscheidungsrelevant.
- [x] **F2 — PO-Entscheidung 2026-07-28: „Ja, mit aufnehmen".** Die gefühlte
      Temperatur wird in den Zusammenfassungssatz der E-Mail aufgenommen
      (`GR221 Tag1: 8–15°C, gef. 6–13°C, teils bewölkt, …`).
- [x] **F3 (beantwortet durch PO-Vorgabe):** Rechenfenster = Gehzeit, exakt wie
      die gemessene Temperatur.
- [x] **F4 (abgeleitet):** Die Abend-Nacht-Regel gilt analog auch für die
      gefühlte Temperatur — „exakt so verhalten wie die normale Temperatur".
