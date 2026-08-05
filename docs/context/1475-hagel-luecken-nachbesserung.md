# Context: 1475-hagel-luecken-nachbesserung

## Request Summary
Nachbesserung zu #1475 S5a (Hagel-Kennzeichen, live seit `2a72175b`): (1) SMS-Kürzel `+HG`
muss `+HL` heißen (Konsistenz mit der dokumentierten Regel "möglichst englische Identifier",
alle anderen Kürzel sind englisch abgeleitet); (2) ein vom PO angeordnetes Vollständigkeits-Audit
fand 5 weitere Ausgabeorte, an denen Gewitter (`thunder_level`) angezeigt wird, aber Hagel fehlt —
diese sollen jetzt ebenfalls angeschlossen werden. PO-Zitat: "Es gibt diverse Ausgabeorte für eine
Wettermetrik und alle müssen hier berücksichtigt werden. Daran gibt es nichts zu rütteln."

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/tokens/builder.py:25,296` | `FORECAST_TH_HAIL_SUFFIX = "+HG"` → `"+HL"` umbenennen (Konstante + Nutzung Zeile ~296) |
| `docs/reference/sms_format.md:120` | Dokumentierte Suffix-Regel `TH:…+HG` → `+HL` nachziehen (Single Source of Truth) |
| `src/app/metric_catalog.py:279-290` | `MetricDefinition(id="thunder", col_key="thunder", col_label="Thdr", ...)` — Gewitter IST eine reguläre Tabellenspalte (**Lücke 1**, vorherige Aussage "keine Spalte" war falsch) |
| `src/output/renderers/email/helpers.py:93-120` (`dp_to_row`) | Generischer Zellwert-Aufbau: `row[metric_def.col_key] = getattr(dp, metric_def.dp_field, None)`. Bereits etabliertes Seitenkanal-Muster für Zusatzinfo pro Zelle: `row["_wmo_code"] = getattr(dp, "wmo_code", None)` (Zeile 120), konsumiert in der `sunshine`-Formatierung (Zeile ~682) für das Wetter-Emoji. Derselbe Seitenkanal-Mechanismus (`row["_hail_flag"] = ...`) ist das naheliegende Muster für die Thunder-Spalte. |
| `src/output/renderers/email/helpers.py:620-635` (Formatierungsfunktion, `key == "thunder"`-Zweig) | **Zwei Darstellungsmodi, die unterschiedlich behandelt werden müssen:** `mode == "raw" or not html` → deutsches Wort aus `THUNDER_LABEL_DE` (Textzelle, dort ist Platz für einen Zusatz). `html`-Ansicht (friendly/einfach) → `thunder_ampel_band()` → **nur ein Ampel-Kreis via `_ampel_dot_css(band)`**, kein Text — dort ist nach Projekt-Konvention (`feedback_simple_view_uses_ampel_dots_not_emoji.md`) **kein Emoji/Zusatztext erlaubt**, nur der Kreis selbst. **Offene Designfrage für die Spec:** wie wird Hagel im Ampel-Kreis-Modus sichtbar (z.B. Kreis-Rand, zweiter kleiner Indikator), wenn Text dort nicht erlaubt ist? |
| `src/output/renderers/compact_summary.py:540-561` (`_format_thunder`) | **Lücke 2.** Komplett eigenständige Implementierung (`"⚡ möglich 8:00–14:00"` bzw. `"Gewitter möglich 8:00–14:00"`), ruft `_pill_for_metric`/`format_hail_note` NICHT auf — Entwickler-Report und Adversary-Protokoll von S5a behaupteten unbelegt, das sei abgedeckt. Muss denselben `format_hail_note`/`hail_priority`-Aufruf bekommen wie `email/helpers.py`. |
| `src/services/trip_report_scheduler.py:1665-1761` (`_build_thunder_forecast`) | **Lücke 3, an der Wurzel.** Baut das `thunder_forecast`-Dict (Schlüssel `"+1"`/`"+2"` → `date`/`level`/`hour`/`text`) NUR aus `dp.thunder_level` — **kein Hagel-Feld im Dict**. Speist gemeinsam: E-Mail „Gewitter-Vorschau" (`email/plain.py:277-284`, `email/html.py`-Pendant), `email/outlook.py` (Mehrtages-Ausblick) UND indirekt das SMS-Token `TH+:`. Eine Lücke an der Wurzel wirkt in mind. 3 Kanälen. |
| `src/output/renderers/sms_trip.py:359` vs. `:460` | Zusatzbefund: `hail_flag` wird für `today` gesetzt (Zeile ~359, `DailyForecast(...)`), aber **nicht** für `tomorrow` (Zeile ~460) — dieselbe Datenklasse wird für "heute" und "morgen" ungleich befüllt. |
| `src/output/renderers/email/compare_html.py:207-210` (`_fmt_thunder(v)`) | **Lücke 4a.** Nimmt nur den skalaren Wert `v` entgegen (Level), kein zweiter Parameter für Hagel — muss um einen `hail`-Parameter erweitert werden. **Wichtig:** `comparison.py` importiert `_fmt_thunder` DIREKT aus `compare_html.py` (`comparison.py:32`) — es ist EINE gemeinsame Funktion für die HTML-Übersichtszeile UND die Klartext-Vergleichszeile. Ein Fix an dieser einen Stelle behebt automatisch BEIDE (vorher fälschlich als 2 getrennte Lücken gezählt — es sind strukturell nur 2, nicht 3). |
| `src/output/renderers/email/compare_html.py:293` (`CV2_METRICS`, `"thunder_max"`-Zeile) | Ruft `_fmt_thunder(v)` mit dem reinen Skalarwert auf — Aufrufstelle muss zusätzlich `hail_flag` aus dem jeweiligen `LocationResult`/`SegmentWeatherSummary` holen und durchreichen. |
| `src/output/renderers/email/compare_html.py:415-438` (`_build_hour_metrics`) | **Lücke 4b, Stundentabelle je Ort im Vergleich.** Generischer `format_value(metric_id, value, style="bare")` ohne Zusatzkanal — analog zur Trip-Stundentabelle (Lücke 1) braucht das dieselbe Seitenkanal-Lösung, wenn es die Ampel-Dot-Beschränkung ebenfalls hat (zu prüfen: nutzt die Compare-Stundentabelle Ampel-Dots oder reinen Text?). |
| `src/services/weather_extractor.py:109-160` (`WeatherExtractor.drilldown()`) | **Lücke 5, Telegram-Stunden-Drilldown — MACHBAR, jetzt verifiziert:** `drilldown(metric=...)` ist bereits metrik-generisch (`getattr(p, metric, None)` auf die volle `ForecastDataPoint`-Zeitreihe). `hail_flag` liegt dort genauso vor wie `thunder_level` — der Aufrufer (`trip_command_processor.py`, `dd_thunder_today`/`dd_thunder_tomorrow`) müsste `drilldown(metric="hail_flag")` zusätzlich aufrufen und mit den Zeitstempeln der `thunder_level`-Liste mergen. Kein struktureller Blocker mehr. |
| `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` | Ursprüngliche S5a-Spec — Scope/AC-Liste dort deckte nur 4 der 9 tatsächlichen Ausgabeorte ab (s. Memory-Analyse). Diese Nachbesserung schließt die verbliebenen 5 plus die Umbenennung. |
| `reference_weather_metric_has_many_output_locations.md` (Memory) | 9-Punkte-Checkliste aller Gewitter-Ausgabeorte, Grundlage dieser Spec — dort auch der volle Fund-Wortlaut mit allen Datei:Zeile-Belegen aus dem Audit-Fork. |

## Existing Patterns

- **Seitenkanal-Muster für Zusatzinfo pro Tabellenzelle:** `row["_wmo_code"] = ...` in `dp_to_row()`,
  konsumiert im `sunshine`-Zweig der Formatierungsfunktion. Hagel kann analog als `row["_hail_flag"]`
  eingeführt und im `thunder`-Zweig gelesen werden — KEIN neuer Mechanismus nötig.
- **Geteilte Formatierungsfunktion `_fmt_thunder`:** bereits zwischen Compare-HTML-Übersicht und
  Compare-Klartext geteilt (Import in `comparison.py`) — die Erweiterung um Hagel muss nur an
  EINER Stelle passieren, wirkt aber automatisch an beiden Ausgabeorten (DRY bereits gegeben,
  nicht neu herstellen).
- **`format_hail_note`/`hail_priority`** (aus S5a, `src/output/metric_format.py`) sind die
  bestehenden, wiederverwendbaren Bausteine — jede der 5 Lücken braucht nur einen zusätzlichen
  Aufruf dieser beiden Funktionen an der jeweiligen Stelle, keine neue Logik.
- **`WeatherExtractor.drilldown()` ist metrik-generisch** — funktioniert für `hail_flag` genauso
  wie für `thunder_level`, ohne Änderung an `drilldown()` selbst.

## Dependencies

- Setzt #1475 S5a voraus (Commit `2a72175b`, live) — `hail_flag`, `hail_priority`,
  `format_hail_note`, `SegmentWeatherSummary.hail_flag` existieren bereits produktiv.
- Betrifft dieselben Renderer-Mail-Gate-Dateien wie S5a (`compact_summary.py`, `compare_html.py`
  sind BEIDE explizit im Gate-Muster `_MAIL_PATTERNS` gelistet) — derselbe Nachweis-Ablauf
  (Matrix-Test + `briefing_mail_validator.py` + `email_spec_validator.py`) wird wieder nötig.

## Existing Specs

- `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` — Vorgänger-Spec, AC-3 (Mutationsschutz
  gegen `thunder_level_from_signals()`) und ADR-0007-Bezug (keine Handlungsempfehlung) gelten
  unverändert weiter und müssen in der neuen Spec erneut verankert werden (Regressionsschutz).

## Risks & Considerations

- **Offene Designfrage: Ampel-Kreis-Modus der Trip-Stundentabelle.** Die "einfache" HTML-Ansicht
  zeigt für Gewitter nur einen farbigen Kreis (`_ampel_dot_css`), kein Text/Emoji ist dort laut
  Projekt-Konvention erlaubt. Eine reine Text-Ergänzung wie in den anderen Kanälen funktioniert
  hier nicht — die Spec muss eine eigene, mit dem Ampel-Kreis-Prinzip vereinbare Lösung festlegen
  (z. B. Kreis-Rand/zweiter kleiner Marker) oder bewusst entscheiden, dass der Ampel-Kreis-Modus
  ausgenommen bleibt (mit Begründung).
- **Root-Fix mit Fernwirkung:** `_build_thunder_forecast()` speist 3 Kanäle gleichzeitig
  (E-Mail-Vorschau, `email/outlook.py`, SMS `TH+:`) — ein Fix dort muss alle 3 Konsumenten korrekt
  weiterreichen, inkl. der bereits gefundenen Inkonsistenz `today` vs. `tomorrow` in `sms_trip.py`.
- **Adversary-Auftrag verschärfen:** Die vorherige Runde akzeptierte eine unbelegte
  Abdeckungsbehauptung («compact_summary.py ist mit abgedeckt») ohne Code-Gegenprüfung — die neue
  Adversary-Runde MUSS für jede der 5 Lücken einen direkten Code-Beleg verlangen, keine Prosa-
  Bestätigung.
- **Kein neuer ADR-0007-Konflikt zu erwarten** — alle Ergänzungen sind rein deskriptiv, exakt
  wie die bereits genehmigte S5a-Darstellung ("Hagel: ja" ohne Ratschlag).

## Analysis (Ergänzung nach Gegenprobe + Strategie-Bewertung)

### Zwei weitere, in der ersten Runde übersehene Fundstellen

- **#10:** `src/output/renderers/trip_report.py::_compute_highlights()` (Zeile 584-597) baut
  die "Highlights"-Zeile ("⚡ Gewitter möglich ab HH:MM (...)") am Kopf des Trip-Berichts nur
  aus `dp.thunder_level`, kein Hagel-Zusatz. Landet in `TripReportResult(highlights=...)`.
- **#11:** `_fmt_thunder(v)` (`compare_html.py:207-210`) hat **drei** externe/interne Aufrufer,
  nicht zwei: `comparison.py:66` (Klartext-Vergleich), `compare_outlook_metric_ids.py:124,130`
  (Mehrtages-Ausblick im Ortsvergleich — eigener, bisher nicht gezählter Ausgabeort), sowie
  intern in `compare_html.py` selbst (Zeile 294 Übersichtstabelle, Zeile 382 Stundentabelle).
  Eine Signaturänderung auf `_fmt_thunder(v, hail=None)` mit Default-Wert behebt alle vier
  Stellen gemeinsam, muss aber an allen vier Aufrufstellen die Hagel-Werte mit durchreichen.

### Ampel-Kreis-Design (offene PO-Entscheidung)

Für die "einfache" HTML-Ansicht (Ampel-Kreis, kein Text erlaubt) empfiehlt die Strategie-Analyse
**Variante B — zweiter `box-shadow`-Ring** an `_ampel_dot_css()` (bestehend: ein Ring
`box-shadow:0 0 0 3px {ring}`, neu: zusätzlicher äußerer Layer bei `hail_flag is True`).
Begründung: geringstes Layout-Risiko in schwachen Mail-Clients (Outlook), reine
Attribut-Erweiterung des einzigen bereits etablierten Musters (Corridor-Marker nutzt
`border-left`, passt aber nicht zur Kreisform). Verworfen: zweiter Kreis daneben (sprengt die
kompakte Zelle), `border-left` (bricht die Kreisform).

### Scope-Schätzung (alle 7 Punkte)

~10-12 Dateien, ~250-400 LoC gesamt — überschreitet die 4-5-Dateien-Konvention klar.
**Aufteilung empfohlen:**
- **Scheibe A** (Text-/Datenkanäle, geringes Risiko): Punkte 1 (Umbenennung), 3
  (compact_summary), 4 (Mehrtages-Vorschau-Wurzel-Fix inkl. `today`/`tomorrow`-Konsistenz in
  `sms_trip.py`), 6 (Telegram-Drilldown), 7 (Highlights-Zeile).
- **Scheibe B** (visuelle Tabellenspalten, PO-Entscheidung + Signaturänderung mit 4 Aufrufern):
  Punkt 2 (Trip-Stundentabelle Ampel-Kreis) + Punkt 5/#11 (Ortsvergleich `_fmt_thunder` an
  allen vier Stellen).

### Reihenfolge
1 → 3 → 7 → 6 (unabhängig, schnell) → 4 (Wurzel-Fix, additiv, kein Feld entfernen) →
5/#11 → 2.

### PO-Entscheidung 2026-08-05: Ampel-Kreis-Design final

**Doppelring + Erklärung darunter** (nicht die zunächst vorgeschlagene reine Ring-Variante ohne
Erklärung — PO-Feedback: "beide Vorschläge waren für den Nutzer nicht klar genug"). Konkret:
`_ampel_dot_css()` bekommt bei `hail_flag is True` einen zweiten, sichtbar abgesetzten äußeren
Ring (zusätzlicher `box-shadow`-Layer). Direkt unter der Stundentabelle erscheint ein kurzer
Erklärungssatz analog zum bestehenden Muster `"  * Temperatur/Nullgradgrenze: Minimum im
2h-Block"` (`email/plain.py:270`), z. B. "* Doppelring bei Gewitter = Hagel möglich" — NUR wenn
mindestens eine Zeile der Tabelle tatsächlich einen Doppelring zeigt (kein Rauschen bei
durchgängig "kein Hagel"/"unbekannt").
