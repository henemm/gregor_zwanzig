# Context: feat-1680-s5b-vorschau-herkunft

**Issue:** #1680 (Gewitter: Herkunft der Stufe sichtbar machen), Scheibe 5b — letzte Scheibe.
**Epic:** #1419 (Gewitter — von einem Kürzel zu einer Aussage), Rang 4 / Entscheidung E1.
**Vorgänger:** S1 Ortsvergleich · S2 Trip-Kurzfassung · S3 vier weitere Orte · S4 Trip-Stundentabelle · S5a Mehrtages-Ausblick (alle live).

## Request Summary

Die **Gewitter-Vorschau** (der `+1`/`+2`-Block „⚡ Gewitter-Vorschau" in der Voll-Mail) soll —
wie die fünf bereits fertigen Ausgabeorte — neben der Gewitterstufe die **tragende Zutat**
nennen (z. B. `· CAPE`). Sie ist der letzte Ausgabeort ohne Herkunftsangabe; danach kann #1680
geschlossen werden.

## Related Files

Alle Zeilennummern **frisch gemessen** gegen `1e5e0be9` (die Angaben in
`docs/context/feat-1680-s5-ausblick-vorschau-herkunft.md` sind gedriftet, z. B. `:2103` → `:2138`).

| Datei | Relevanz |
|---|---|
| `src/services/trip_report_scheduler.py:2251` | **Primärpfad** `_thunder_entry_from_trend_row()` — baut den Vorschau-Eintrag aus der Trend-Zeile |
| `src/services/trip_report_scheduler.py:2442` | **Rückfallpfad** `_build_thunder_forecast()` — baut ihn aus frisch geholten `ForecastDataPoint`s |
| `src/services/trip_report_scheduler.py:2138` | `_build_thunder_forecast_from_trend_or_fetch()` — Weiche zwischen beiden |
| `src/output/renderers/email/plain.py:311-332` | **Wirkort 1**: Klartext-Mail, Block „━━ Gewitter-Vorschau ━━" |
| `src/output/renderers/email/html.py:1311-1329` | **Wirkort 2**: HTML-Mail, Block „⚡ Gewitter-Vorschau" |
| `src/output/renderers/email/outlook.py:545-547` | Erzeuger von `row["hourly_thunder_signals"]` (Trägerquelle für den Primärpfad, aus S5a) |
| `src/output/renderers/email/helpers.py:1021-1036` | `format_trend_tokens()` → `thunder_day_origin`; **das fertige Vorbild** für die Träger-Auswertung |
| `src/services/weather_metrics.py:438-462` | `compute_basis_metrics()` setzt `thunder_level_max_signals` am Summary (Trägerquelle für den Rückfallpfad) |
| `src/output/metric_format.py:559` | `union_of_max_carriers()` — vereinigt Träger über mehrere Punkte, `None` bei „keine Aussage" |
| `src/output/metric_format.py:382` | `thunder_signal_label()` — Rohname → Anzeigewort (`cape` → `CAPE`) |
| `src/services/preview_service.py:222-246` | Vorschau-Endpunkt, ruft **dieselbe** Scheduler-Methode; reicht das Dict unverändert durch |

## Der Datenfluss, gemessen

```
                       ┌─ Trend liegt vor ──→ _thunder_entry_from_trend_row()  [PRIMÄR]
_build_thunder_        │                        Träger vorhanden in row["hourly_thunder_signals"]
forecast_from_trend_ ──┤                        → wird heute NICHT gelesen
or_fetch()             │
                       └─ kein Trend ───────→ _build_thunder_forecast()        [RÜCKFALL]
                                                Träger vorhanden in summarize_points(...)
                                                  .thunder_level_max_signals
                                                → wird heute NICHT gelesen (nur .hail_flag)
                                    ↓
                      dict { date, level, hour, text, hail }
                                    ↓
              ┌──────────────┬──────────────────────────┐
        plain.py:311    html.py:1311              sms_trip.py:588
        (nur "full")    (nur "full")        liest NUR level/hour/hail,
     `fc['text']` wörtlich, `fc['text']` wörtlich,   nie `text` → Token "TH+:M@14"
      + Hagel-Suffix       + Hagel-Suffix        → SMS **und** Premium-SMS
```

## Existing Patterns

- **Muster #1475 (Hagel):** Strukturdatum wird in **beiden** Pfaden ins Dict gelegt
  (`"hail": row.get("hail")` — `trip_report_scheduler.py:2371`; `"hail": getattr(summarize_points(thunder_dps), "hail_flag", None)` — `:2587`)
  und erst im Renderer zu Text (`format_hail_note`, angehängt als `f" · {_note}"` in
  `plain.py:327` / `html.py:1322`). **Das ist die Blaupause für diese Scheibe.**
- **Herkunfts-Wortlaut, seit S1 an sechs Fundstellen identisch:** `" · "` vor der Herkunft,
  `", "` zwischen mehreren Zutaten, Anzeigewort über `thunder_signal_label()`. Es gibt
  **keinen** geteilten „Stufe+Herkunft"-Komponierer für die Trip-Seite — jeder Ort baut
  `", ".join(thunder_signal_label(n) for n in traeger)` selbst. (Einzige Ausnahme: der
  Compare-Pfad hat mit `compare_html.py:204 _fmt_thunder()` einen eigenen, bewusst nicht
  ausgelagerten Komponierer.)
- **Reihenfolge im fertigen Nachbarn (S5a-Ausblick):** Herkunft steht **am Tagesteil**, also
  **vor** Nacht-Zusatz und **vor** Hagel (`outlook.py:238-242` HTML, `:378-383` Klartext).
- **Testbenennung:** `tests/tdd/test_thunder_origin_<verhalten>.py` (S1 `_compare`, S2 `_trip`,
  S3 `_four_places`, S4 `_trip_hour_table`, S5a `_outlook`). Für diese Scheibe ist
  `tests/tdd/test_thunder_origin_preview.py` der konsequente Name.

## Dependencies

- **Upstream:** `build_outlook_row()` (S5a-Vertrag, liefert `hourly_thunder_signals`) ·
  `summarize_points()`/`compute_basis_metrics()` · `union_of_max_carriers()` ·
  `thunder_signal_label()` · `hour_in_window()`/`resolve_configured_window()`.
- **Downstream:** genau **zwei** Renderer (Klartext-Mail, HTML-Mail). SMS/Premium-SMS hängen
  am selben Dict, lesen aber nur `level`/`hour`/`hail`.

## Kanal-Lage (strukturell belegt, nicht angenommen)

| Kanal | Sieht die Vorschau? | Beleg |
|---|---|---|
| E-Mail Klartext (`full`) | **ja** | `plain.py:311` |
| E-Mail HTML (`full`) | **ja** | `html.py:1311` |
| E-Mail Kompakt | nein | `render_compact()` (`compact.py:96-117`) kennt den Parameter nicht; `email/__init__.py:105-127` verzweigt vorher |
| Telegram (rich) | nein | `render_telegram_bubbles()` (`narrow.py:631-651`) kennt den Parameter nicht; Aufruf `trip_report.py:283-302` übergibt ihn nicht |
| SMS / Premium-SMS | nur Zahlen | `sms_trip.py:588-608` liest `level`/`hour`/`hail`, nie `text` → Token `TH+:M@14` |

⇒ **SMS und Premium-SMS bleiben ohne Herkunft, ohne dass dafür Code nötig wäre.** Nicht
strukturell garantiert ist allein der dokumentierte Rückfall
`sms_text or email_plain` (`notification_service.py:411-483`) — laut Code-Kommentar dort
„praktisch tot", weil `sms_text` seit #868 nie leer ist. Diese Bewertung ist eine
**Zusicherung per AC, keine bauliche Unmöglichkeit**; sie gilt seit S2 unverändert und wird
durch diese Scheibe nicht verändert.

## 🔴 Der zentrale Befund: welcher Pfad in der Mail überhaupt ankommt

Die Vorschau erscheint in der Mail nur bei `not outlook_active`, mit
`outlook_active = show_outlook and bool(multi_day_trend)` (`plain.py:309`, `html.py:1309`,
Grund laut Kommentar: #1313 — keine Dopplung mit dem Ausblick). Zugleich liefert der
**Primärpfad** nur Einträge, wenn `multi_day_trend` überhaupt existiert. Daraus folgt:

| Bericht | `multi_day_trend` | `show_outlook` | Vorschau in Mail | genutzter Pfad |
|---|---|---|---|---|
| Morgen (Default) | leer (Default `multi_day_trend_reports=["evening"]`, `loader.py:919`) | egal | **sichtbar** | **Rückfall** |
| Abend (Default) | vorhanden | `True` (Default) | unsichtbar | — |
| Abend, Ausblick aus | vorhanden | `False` | **sichtbar** | **Primär** |

**Konsequenz:** Der Rückfallpfad ist **nicht** der Ausnahmefall, sondern der Regelfall der
Morgen-Mail; der Primärpfad erreicht die Mail nur bei abgeschaltetem Ausblick. Das kehrt die
Gewichtung um, die das S5a-Kontextdokument annahm („Primär = Trend-Zeile, Abend-Default" —
`feat-1680-s5-ausblick-vorschau-herkunft.md:229`). **Beide Pfade brauchen einen eigenen
Nachweis; keiner darf als „ohnehin abgedeckt" durchgereicht werden.**

## Risks & Considerations

1. **🔴 Wirkort-Falle (die Fehlerklasse dieses Strangs).** Eine Änderung nur am Primärpfad
   wäre in der Morgen-Mail unsichtbar — grün getestet und wirkungslos. Genau dieser Fehler
   trat in S2 (falscher Textzweig) und S5a (falscher Compare-Zweig) je einmal auf. Für jeden
   der beiden Pfade muss der Nachweis am **zugestellten** Text hängen.
2. **🔴 Herkunft ohne Stufe.** Der Text trägt bei `ThunderLevel.NONE` „Kein Gewitter erwartet"
   (`:2338-2339`). Ein Herkunfts-Zusatz darf dort nie erscheinen. `union_of_max_carriers()`
   liefert bei `NONE` bereits `None` — aber in S5a hat der Adversary widerlegt, dass man sich
   darauf allein berufen darf: die Absicherung muss **an der Stelle** geprüft werden, an der
   sie wirkt.
3. **🔴 Fenster-Kohärenz.** Die angezeigte Stufe kommt aus den Stundenproben **im
   Tagesfenster** (`:2302-2318`); nur wenn dort keine liegt, greift ein Fail-soft auf das
   Kalendertags-Maximum `row["thunder"]` (`:2323-2326`). Die Herkunft muss aus **derselben**
   Probenmenge stammen, sonst nennt sie eine Zutat, die zur gezeigten Stufe nicht gehört.
   Für den Fail-soft-Zweig gibt es im Primärpfad **keine** passende Trägerquelle — dort ist
   „keine Herkunft" die einzig ehrliche Antwort.
4. **Wortlaut-Entscheidung offen (für die Spec):** Der Nacht-Zusatz ist bereits **Teil von
   `text`** (`text += format_night_addendum(...)`, `:2357-2359` bzw. `:2574-2575`), der Hagel-
   Zusatz dagegen ein eigener Dict-Schlüssel, den erst der Renderer anhängt. Die Herkunft kann
   deshalb entweder **im Scheduler direkt hinter den Tagesteil** (wie beim Ausblick, aber
   Text-Bau statt Strukturdatum) oder **als eigener Schlüssel hinter den Nacht-Zusatz** (wie
   Hagel, musterkonform, aber vom Tagesteil abgerückt). Beides ist vertretbar; die Entscheidung
   gehört mit Beispielzeilen in die Spec.
5. **Bruchrisiko Bestandstests, asymmetrisch.** 21 Tests vergleichen `entry["text"]`
   zeichengleich (`tests/unit/test_thunder_forecast_day_window.py` 6×,
   `tests/unit/test_thunder_night_addendum.py` 13×, `tests/tdd/test_thunder_forecast_low_level.py` 4×)
   plus 2 Paritätstests (`test_thunder_night_addendum_parity.py:382,415`, die Versand- und
   Vorschautext gleichsetzen). Für den **Primärpfad** ist das Risiko gering: `hourly_thunder_signals`
   wird im ganzen Repo nur an zwei Stellen berührt (Erzeuger + ein Verbraucher), keine Testfixture
   setzt es. Für den **Rückfallpfad** ist es real: dort entstehen Träger aus echten
   `ForecastDataPoint`s. **Zu messen, nicht anzunehmen.**
6. **Renderer-Gate #811 greift.** Sobald `plain.py`/`html.py` gestaged sind, verlangt
   `renderer_mail_gate.py` (Muster `:43-44`) drei frische Nachweise: Matrix-Test
   `tests/tdd/test_issue_811_mode_matrix.py`, `briefing_mail_validator.py` gegen eine echt
   zugestellte Mail, und grüne `tests/golden/email/`. Nur Scheduler-Änderungen lösen es nicht aus.
7. **Nachweis-Betrieb.** Für den fachlichen Nachweis genügt hier — anders als bei S5a — **kein**
   Trip mit künftigen Etappen im Ausblick, wohl aber ein Trip, dessen Folgetage Gewitter tragen,
   und **zwei** Konfigurationen (Morgen-Report für den Rückfall, Abend mit `show_outlook=False`
   für den Primärpfad).

## Existing Specs

| Datei | Bezug zu dieser Scheibe |
|---|---|
| `docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md:448-451` | geerbter Auftrag, wörtlich: „**Gewitter-Vorschau** — folgt als **Scheibe 5b**; sie konsumiert den hier entstehenden Zeilen-Vertrag über beide ihrer Pfade (`_thunder_entry_from_trend_row` primär, `_build_thunder_forecast` als Rückfall)." |
| `docs/specs/modules/feat_1680_s4_...md:474-477, 497-498` | Known Limitation 4: Vorschau bleibt ohne Herkunft |
| `docs/specs/modules/feat_1680_s3_...md:545-553, 591-593` | Begründung der Zurückhaltung — beruht auf der inzwischen **widerlegten** Annahme, die Träger gingen strukturell verloren |
| `docs/specs/modules/feat_1680_s2_...md:458` | Vorschau erstmals ausgenommen |
| `docs/context/feat-1680-s5-ausblick-vorschau-herkunft.md:225-299` | Vorarbeit der S5a-Session zu 5b (Dateiliste, Wortlaut-Vorschlag, Scope ~20–25 LoC) — **als Vermutung zu behandeln**, Zeilennummern und Pfad-Gewichtung sind überholt |

## Scope Assessment

| | Dateien | Produktiv-LoC (Schätzung) |
|---|---|---|
| Scheduler (beide Pfade) | 1 | ~10–14 |
| Renderer (Klartext + HTML) | 2 | ~6–10, entfällt bei Text-Variante im Scheduler |
| Neue Testsuite | 1 (`tests/tdd/test_thunder_origin_preview.py`) | Tests dominieren wie in S1–S5a |

`loc_limit_override` war in S1–S3 nötig und wird es hier voraussichtlich wieder sein.
