---
entity_id: feat_1475_hagel_luecken_nachbesserung
type: feature
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.0"
tags: [gewitter, hagel, epic-1419, issue-1475, nachbesserung]
---

# Hagel-Kennzeichen — Nachbesserung fehlender Ausgabeorte

## Approval

- [ ] Approved

## Purpose

#1475 S5a (live seit Commit `2a72175b`) führte das Hagel-Kennzeichen
(`hail_flag`, `hail_priority()`, `format_hail_note()`) ein, deckte aber nur 4
von 13 tatsächlichen Ausgabeorten ab, an denen Gewitter (`thunder_level`)
angezeigt wird. Diese Spec schließt die restlichen Lücken plus eine
Kürzel-Korrektur, sodass Hagel überall dort sichtbar ist, wo auch Gewitter
sichtbar ist — PO-Vorgabe: "Es gibt diverse Ausgabeorte für eine Wettermetrik
und alle müssen hier berücksichtigt werden."

**Korrektur nach zweiter Recherche-Runde (2026-08-05):** Ein ursprünglich
gezählter Ausgabeort ("Trip-Report-Highlights") erwies sich als bereits seit
Issue #790 vom tatsächlichen Mail-Rendering abgekoppelter toter Code — dieser
Punkt entfällt ersatzlos aus dem Umfang (s. Known Limitations 7). Gleichzeitig
wurden zwei bisher komplett übersehene Ausgabeorte gefunden: der Ortsvergleich
hat **eigene** Telegram- und SMS-Renderer (`render_compare_telegram`/
`render_compare_sms` in `comparison.py`), die denselben `_fmt_thunder()`
nutzen wie die bereits bekannten Ortsvergleich-Stellen — dieselbe
Fix-Mechanik (Punkt 5), zwei zusätzliche Aufrufstellen.

## Source

- **File:** `src/output/tokens/builder.py`, `src/output/renderers/email/helpers.py`,
  `src/output/renderers/compact_summary.py`, `src/services/trip_report_scheduler.py`,
  `src/output/renderers/sms_trip.py`, `src/output/renderers/email/compare_html.py`,
  `src/output/renderers/comparison.py`, `src/services/weather_extractor.py`,
  `src/services/trip_command_processor.py`, `docs/reference/sms_format.md`
- **Identifier:** `FORECAST_TH_HAIL_SUFFIX`, `_ampel_dot_css()`, `dp_to_row()`,
  `_format_thunder()` (compact_summary), `_build_thunder_forecast()`,
  `SMSTripFormatter._segments_to_normalized_forecast()` (tomorrow-Zweig),
  `_fmt_thunder()`, `_build_hour_metrics()`/`_render_hour_row()`,
  `_sms_metric_cell()`, `_plain_metric_cell()` (beide `comparison.py`,
  Ortsvergleich-SMS/-Telegram), `WeatherExtractor.drilldown()`,
  `dd_thunder_today`/`dd_thunder_tomorrow`

**`_compute_highlights()` (`trip_report.py`) NICHT mehr Teil dieser Spec** —
s. Korrektur im Purpose-Abschnitt und Known Limitations 7.

**Schicht:** ausschließlich Python-Core (`src/output/`, `src/services/`,
`docs/reference/`). Kein Go-API-DTO betroffen, kein Frontend/Editor-Zugang
(unverändert, s. Known Limitations / AC-9 aus S5a).

> **Schicht-Hinweis geprüft:** Alle betroffenen Symbole liegen im
> Python-Core. Go-API (`internal/`, `cmd/`) und SvelteKit-Frontend
> (`frontend/src/...`) sind nicht betroffen.

## Estimated Scope

- **LoC:** ~280–420 Produktivcode über alle Punkte + vergleichbarer
  Testumfang (Golden-String-/Fixture-Vergleiche pro Kanal) — leicht erhöht
  gegenüber der ersten Fassung durch die zwei zusätzlich gefundenen
  Ortsvergleich-Kanäle (SMS, Telegram), teilweise ausgeglichen durch den
  Wegfall von Punkt 7 (Highlights, toter Code)
- **Files:** ~9 Produktivdateien geändert (`tokens/builder.py`,
  `docs/reference/sms_format.md`, `email/helpers.py`, `compact_summary.py`,
  `trip_report_scheduler.py`, `sms_trip.py`, `email/compare_html.py`,
  `comparison.py`, `trip_command_processor.py`; `weather_extractor.py`
  bleibt unverändert, `trip_report.py` entfällt), keine neue Produktivdatei
  nötig; mind. 6–8 Testdateien geändert/neu
- **Effort:** high (6 fachliche Codeänderungspunkte über 8 verschiedene
  Ausgabekanäle — Trip: E-Mail/Telegram/SMS, Ortsvergleich: E-Mail/Telegram/
  SMS, plus je 2 Darstellungsmodi bei den Stundentabellen —,
  Renderer-Mail-Gate-Nachweis für 2 Dateien erneut Pflicht)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #1475 S5a (Commit `2a72175b`, live) | Upstream, geschlossen | `hail_flag`, `hail_priority()`, `format_hail_note()`, `SegmentWeatherSummary.hail_flag` existieren bereits produktiv — diese Spec fügt nur Aufrufe hinzu, keine neue Berechnungslogik |
| `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` | Vorgänger-Spec | AC-3-Mutationsschutz (`thunder_level_from_signals()` bleibt unverändert) und ADR-0007-Bezug gelten unverändert weiter und werden hier erneut verankert (Regressionsschutz, s. AC-11) |
| `thunder_level_from_signals()` (`src/output/metric_format.py:326`) | interne Funktion, MUSS **unverändert** bleiben | Abgrenzung Hagel-Flag von der Gewitterstufe — keiner der 8 Punkte darf Hagel als Signal in die Stufenberechnung einspeisen |
| `WeatherExtractor.drilldown()` (`src/services/weather_extractor.py:109-160`) | bereits metrik-generisch, unverändert nutzbar | liefert `hail_flag`-Zeitreihe genau wie `thunder_level` ohne Änderung an der Methode selbst |
| Renderer-Mail-Gate #811 (`renderer_mail_gate.py`) | Commit-Gate | `compact_summary.py` UND `email/compare_html.py` sind beide im Gate-Muster gelistet — Matrix-Test + `briefing_mail_validator.py`/`email_spec_validator.py` gegen echte Staging-Mail wird für den Commit erneut Pflicht (Deploy-Phase, nicht Teil dieser Spec-Freigabe) |
| #1481 DRY-Pflicht | Prozess-Konvention | jede der 8 Änderungen ruft die bestehenden `hail_priority()`/`format_hail_note()` auf, keine neue Parallel-Logik |
| `feedback_simple_view_uses_ampel_dots_not_emoji.md` (Memory) | Projekt-Konvention | Ampel-Kreis-Modus der Trip-Stundentabelle zeigt nie Emoji/Text im Kreis selbst — Grund für die Doppelring-Lösung in Punkt 2 |

## Implementation Details

```
Punkt 1 — SMS-Kuerzel-Umbenennung (Konsistenz-Fix, kein Verhaltenswechsel):
  src/output/tokens/builder.py:25
    FORECAST_TH_HAIL_SUFFIX = "+HG"  ->  "+HL"
  src/output/tokens/builder.py:296 (Nutzungsstelle) bleibt strukturell gleich,
  nur der Konstantenwert aendert sich -- KEINE zweite Textstelle noetig.
  docs/reference/sms_format.md:120 (Tabellenzeile "TH:...+HG") wird auf
  "+HL" nachgezogen (Single Source of Truth, DIESELBE Zeile, kein neuer
  Eintrag).

Punkt 2 — Trip-Stundentabelle, Ampel-Kreis-Modus (PO-Entscheidung final,
Doppelring + Erklaerung):
  a) Seitenkanal in dp_to_row() (email/helpers.py, nach Zeile 120, analog
     row["_wmo_code"] = ...):
       row["_hail_flag"] = getattr(dp, "hail_flag", None)
  b) _ampel_dot_css(level: str) -> str (Zeile ~491-498) bekommt einen
     optionalen Parameter, z.B. _ampel_dot_css(level, hail: bool = False).
     Bei hail=True wird dem bestehenden box-shadow EIN zusaetzlicher,
     sichtbar abgesetzter aeusserer Ring angehaengt (additiv zum
     bestehenden "box-shadow:0 0 0 3px {ring}" -- Vorbild-Wert z.B.
     ", 0 0 0 6px <Hagel-Farbe>"). Bei hail=False/None bleibt der
     bisherige Einzelring exakt zeichengleich.
  c) Aufrufstelle im thunder-Zweig (helpers.py ~Zeile 634-636):
       band = thunder_ampel_band(val)
       if band is None:
           return "-"
       return _ampel_dot_css(band, hail=row.get("_hail_flag") is True)
     row muss dazu an die Formatierungsfunktion durchgereicht werden
     (bereits Parameter an anderer Stelle verfuegbar, s. Wind-Zweig
     Zeile ~648-651, das Muster existiert schon fuer row["_wind_dir_deg"]).
  d) Erklaerungssatz unter der Stundentabelle, analog Muster
     email/plain.py:270 ("  * Temperatur/Nullgradgrenze: Minimum im
     2h-Block"): NUR wenn mindestens eine sichtbare Tabellenzeile
     tatsaechlich hail=True zeigte (Zaehler/Flag beim Rendern der Zeilen
     mitfuehren), erscheint
       "* Doppelring bei Gewitter = Hagel moeglich"
     Sonst kein Zusatztext (kein Rauschen bei durchgaengig "kein
     Hagel"/"unbekannt").
  e) Text-/Raw-Modus derselben Spalte (key == "thunder", mode == "raw"
     or not html) zeigt weiter THUNDER_LABEL_DE -- dort reicht ein
     einfacher Textzusatz analog S5a: format_hail_note(row.get("_hail_flag"))
     an den zurueckgegebenen String anhaengen, wenn nicht None.

Punkt 3 — compact_summary.py::_format_thunder() (Zeile ~540-561):
  Muss format_hail_note()/hail_priority() aus metric_format.py aufrufen.
  Die Funktion iteriert bereits `hourly: list[ForecastDataPoint]` und
  sammelt thunder_hours -- ergaenzend werden die hail_flag-Werte derselben
  gefensterten Punkte gesammelt und ueber hail_priority() aggregiert:
    hail_values = [dp.hail_flag for dp in hourly
                   if dp.thunder_level and dp.thunder_level != ThunderLevel.NONE]
    note = format_hail_note(hail_priority(hail_values))
    if note:
        text = f"{text} · {note}"  # sowohl friendly- als auch Text-Zweig
  Das ist der Fall, den S5a faelschlich als "bereits abgedeckt" behauptete,
  ohne Code-Beleg -- diese Spec verlangt einen echten Aufruf-Nachweis
  (AC-3).

Punkt 4 — Mehrtages-Vorschau, Wurzel-Fix:
  a) trip_report_scheduler.py::_build_thunder_forecast() (Zeile
     1665-1761): das forecast[key]-Dict bekommt ein zusaetzliches Feld
     "hail" (additiv, keine bestehenden Schluessel entfernen):
       hail_dps = [dp for dp in thunder_dps if dp.hail_flag is not None
                   or True]  # volle Rohliste an hail_priority uebergeben
       forecast[key]["hail"] = hail_priority(dp.hail_flag for dp in thunder_dps)
     (Aggregation ueber dieselbe thunder_dps-Menge, die auch level/hour
     liefert -- kein zweiter Datenzugriff.)
  b) Konsumenten, die "hail" zusaetzlich lesen und format_hail_note()
     anhaengen:
       - email/plain.py:277-284 (Gewitter-Vorschau-Textblock)
       - email/html.py-Pendant (analoge HTML-Fassung)
       - email/outlook.py (Mehrtages-Ausblick)
       - tokens/builder.py, SMS-Token TH+: (tomorrow.thunder_hourly) --
         hier gilt dieselbe Suffix-Logik wie bei Punkt 1 (jetzt "+HL"),
         angewendet auf den tomorrow-Zweig.
  c) Zusatz-Bugfix im selben Schritt: sms_trip.py setzt hail_flag fuer
     `today` (Zeile ~359, DailyForecast(...), ueber hail_priority(hail_values))
     aber NICHT fuer `tomorrow` (Zeile ~460, tomorrow_day = DailyForecast(
     thunder_hourly=tomorrow_thunder, has_data_gap=tomorrow_gap)). Muss
     angeglichen werden:
       tomorrow_day = DailyForecast(
           thunder_hourly=tomorrow_thunder, has_data_gap=tomorrow_gap,
           hail_flag=thunder_forecast.get("+1", {}).get("hail")
                     if thunder_forecast else None,
       )
     -- sonst bleibt die unter (a) neu bereitgestellte Information fuer
     "morgen" im SMS-Renderer ungenutzt, obwohl das Dict sie jetzt traegt.

Punkt 5 — Ortsvergleich, _fmt_thunder() (email/compare_html.py:207-210):
  a) Signatur additiv erweitert:
       def _fmt_thunder(v, hail: Optional[bool] = None) -> str:
           if v is None:
               return "-"
           key = v.value if hasattr(v, "value") else str(v)
           label = _THUNDER_LEVEL_LABEL.get(key, "-")
           note = format_hail_note(hail)
           return f"{label} · {note}" if note else label
     Bestehende Aufrufer ohne hail-Argument bleiben zeichengleich
     (Default None -> format_hail_note(None) == None -> kein Zusatz).
  b) SECHS Aufrufstellen bekommen den passenden Hagel-Wert durchgereicht
     (zwei davon erst in der zweiten Recherche-Runde gefunden, s.
     Purpose-Korrektur):
     - compare_html.py:294 (CV2_METRICS, "thunder_max"-Zeile,
       Uebersichtstabelle): "fmt": _fmt_thunder wird zu einer Closure/
       partial, die zusaetzlich das aggregierte hail_flag des jeweiligen
       LocationResult/SegmentWeatherSummary liest -- der generische
       Renderaufruf ruft "fmt"(value) auf, die Closure schliesst den
       Hagel-Wert bereits ein (kein Eingriff in den generischen
       Renderpfad noetig).
     - compare_html.py interne Stundentabelle: _render_hour_row() hat
       bereits `dp` im Scope (Zeile 883-911) -- an der Aufrufstelle
       m["fmt"](value) wird fuer den thunder-Key zusaetzlich
       getattr(dp, "hail_flag", None) durchgereicht (analog Windrichtungs-
       Muster Zeile 899-905, das ebenfalls "dp" zusaetzlich zum reinen
       Wert nutzt).
     - comparison.py:66 (Klartext-Vergleich, importiert _fmt_thunder
       direkt aus compare_html.py, Teil des E-Mail-`text_body` aus
       `render_compare_email()`): Aufrufstelle ergaenzt den Hagel-Wert
       aus demselben Aggregat, das auch den thunder_max-Wert liefert.
     - compare_outlook_metric_ids.py:124,130 (Mehrtages-Ausblick im
       Ortsvergleich, ruft _fmt_thunder(value) auf): analog Punkt 4,
       ergaenzt um den Hagel-Wert aus derselben Vorschau-Quelle.
     - comparison.py::_sms_metric_cell() (Zeile ~504-528, Konsument von
       render_compare_sms() -- EIGENER Ortsvergleich-SMS-Kanal, ueber
       NotificationService.send_compare_report() dispatcht): liest
       `row = _PLAIN_ROWS_BY_ID.get(metric_id)`, ruft `fmt(value)` --
       muss zusaetzlich den Hagel-Wert desselben LocationResult
       durchreichen. GSM-7/Budget-Kuerzung (Issue #1362) bleibt
       unangetastet -- der Hagel-Zusatz zaehlt regulaer gegen das
       bestehende Zeichenbudget, kein Sonderfall.
     - comparison.py::_plain_metric_cell() (Zeile ~531-542, Konsument von
       render_compare_telegram() -- EIGENER Ortsvergleich-Telegram-Kanal):
       identisches Muster wie _sms_metric_cell(), ohne Budget-Kuerzung.
  c) Geklaerte Designfrage (Recherche-Ergebnis dieser Spec, s. Known
     Limitations): Die Compare-Stundentabelle nutzt fuer "thunder" KEINEN
     Ampel-Kreis (`_ampel_dot_css`) -- sie zeigt IMMER Textlabel
     (`_fmt_thunder`, aus `_HOUR_FMT_OVERRIDES["thunder"]`) plus separate
     Zell-Toenung ueber `_sev_thunder`/`_sev_cell_style` (Hintergrundfarbe,
     kein Kreis-Icon). Punkt 2's Doppelring-Loesung gilt AUSSCHLIESSLICH
     fuer die Trip-Stundentabelle; die Compare-Stundentabelle nutzt
     denselben einfachen Text-Anhang wie Punkt 3/4/5a (kein zweiter
     Darstellungsmodus noetig, keine Ampel-Kreis-Beschraenkung dort).

Punkt 6 — Telegram-Stunden-Drilldown:
  trip_command_processor.py (Callbacks dd_thunder_today/dd_thunder_tomorrow)
  ruft zusaetzlich WeatherExtractor.drilldown(metric="hail_flag") auf
  (drilldown() selbst bleibt UNVERAENDERT, ist bereits metrik-generisch)
  und mergt das Ergebnis nach Zeitstempel mit der thunder_level-Liste
  (beide Listen sind DrilldownPoint(ts=..., value=...), gleicher Trip,
  gleiches Zeitfenster -- Merge per ts-Dict). Pro Stunde mit
  hail_flag=True wird format_hail_note()-Text an die Zeile angehaengt.

Punkt 7 ENTFAELLT (Trip-Report-Highlights, trip_report.py::
_compute_highlights()) — bei der Test-Recherche verifiziert als toter
Code seit Issue #790 (render_html()/render_plain() verwerfen den
`highlights`-Parameter ausdruecklich ueber **_ignored, s. Docstring-
Kommentar dort: "removed parameters ... are absorbed by **_ignored for
backward compatibility -- they no longer affect output"). Ein
Hagel-Zusatz an dieser Stelle haette KEINE Wirkung beim Nutzer --
Faehigkeit ohne Wirkung ist laut Projektregel (Lehre #1467 AG6) kein
gueltiger AC. S. Known Limitations 7 fuer die getrennte Behandlung
dieses Fundes (Nebenbefund, nicht Teil dieser Spec).
```

## Expected Behavior

- **Input:** ein Trip/Ortsvergleich mit mindestens einem Zeitpunkt/einer
  Etappe, deren aggregiertes `hail_flag == True` ist (WMO 96/99, s. S5a)
- **Output:** an allen 12 tatsächlichen Ausgabeorten (4 aus S5a bereits live
  + 8 aus dieser Spec, davon 6 über die `_fmt_thunder()`-Erweiterung in
  Ortsvergleich-HTML/-Klartext/-Ausblick/-SMS/-Telegram) erscheint bei
  `hail_flag is True` ein zusätzlicher, rein deskriptiver Hagel-Hinweis —
  als Text an den übrigen Kanälen, als sichtbar abgesetzter Doppelring plus
  Erklärungssatz in der Trip-Stundentabellen-Ampel-Kreis-Ansicht (Punkt 2).
  Bei `None`/`False` bleibt jeder Ort zeichengleich zum bisherigen Stand
  (kein Rauschen). Das SMS-Kürzel heißt konsistent `+HL` statt `+HG`.
  (Ein 13. ursprünglich gezählter Ort — Trip-Report-Highlights — ist toter
  Code und nicht Teil des Outputs, s. Known Limitations 7.)
- **Side effects:** keine zusätzlichen HTTP-Abrufe (alle Werte stammen aus
  bereits vorhandenen `hail_flag`-Feldern); die Gewitterstufe
  (`thunder_level`) bleibt an jeder der 6 Codeänderungsstellen unverändert
  (AC-10)

## Acceptance Criteria

- **AC-1 (SMS-Kürzel-Umbenennung, Ende-zu-Ende):** Given eine Etappe mit
  `hail_flag=True` und aktivierter Gewitter-Metrik / When das SMS-Trip-
  Briefing gerendert wird / Then trägt der Gewitter-Token den Suffix
  `+HL` (nicht mehr `+HG`), UND `docs/reference/sms_format.md` beschreibt
  an derselben Tabellenzeile `+HL`.
  - Test: Golden-String-Vergleich des gerenderten SMS-Tokens gegen ein
    Fixture mit `weather_code=96`; String-Suche nach dem alten `+HG` im
    gerenderten Output MUSS fehlschlagen (negativer Beleg). Zusätzlich ein
    Dokumentations-Abgleichstest (`# doc-compliance-test`), der die Zeile
    in `sms_format.md` gegen die aktive Konstante `FORECAST_TH_HAIL_SUFFIX`
    spiegelt — kein Verhaltensnachweis, ausdrücklich als Doku-Test markiert.

- **AC-2 (Trip-Stundentabelle, Ampel-Kreis-Doppelring erscheint):** Given
  eine Stunde mit `thunder_level != NONE` und `hail_flag=True` in der
  "einfachen" HTML-Ansicht (Ampel-Kreis-Modus, `mode != "raw"`, `html=True`)
  / When die Stundentabelle gerendert wird / Then enthält die CSS-Regel der
  betroffenen Zelle einen zweiten, äußeren `box-shadow`-Layer zusätzlich zum
  bestehenden Ring — die Zelle einer Vergleichsstunde mit `hail_flag=None`
  bei gleichem `thunder_level` bleibt beim einzelnen Ring.
  - Test: Zwei gerenderte HTML-Fragmente (Stunde A `hail_flag=True`,
    Stunde B `hail_flag=None`, beide `thunder_level=HIGH`) werden auf den
    `box-shadow`-Wert der jeweiligen `<td>`/`<span>` verglichen — A hat
    nachweisbar mehr Ring-Layer als B. Läuft gegen den echten
    `briefing_mail_validator.py`-Pfad mit echt zugestellter Staging-Mail,
    nicht nur ein isolierter `_ampel_dot_css()`-Aufruf (Lehre #1467 AG6).

- **AC-3 (Trip-Stundentabelle, Erklärungssatz nur bei mindestens einem
  Doppelring):** Given eine gerenderte Stundentabelle, bei der KEINE Zeile
  einen Doppelring zeigt (alle Stunden `hail_flag` None/False) / When die
  Mail gerendert wird / Then erscheint der Satz "Doppelring bei Gewitter =
  Hagel möglich" NICHT unter der Tabelle. Given mindestens eine Zeile zeigt
  den Doppelring / Then erscheint der Erklärungssatz genau einmal direkt
  unter der Tabelle.
  - Test: Zwei Mail-Renderings (Fixture ohne jede Hagel-Stunde vs. Fixture
    mit genau einer) — der Erklärungssatz erscheint nachweisbar nur im
    zweiten Fall, im ersten Fall ist er nachweislich abwesend (kein
    unbedingtes „immer angehängt").

- **AC-4 (compact_summary.py — echter Code-Beleg, nicht Behauptung):**
  Given eine Etappe mit `thunder_level != NONE` und `hail_flag=True`
  innerhalb des von `_format_thunder()` gefensterten Zeitraums / When die
  Kurzzusammenfassung (`friendly` und Text-Variante) gerendert wird / Then
  enthält der zurückgegebene String zusätzlich zum bestehenden
  "möglich HH:00–HH:00"-Text den Hagel-Hinweis aus `format_hail_note()`.
  - Test: `CompactSummaryFormatter._format_thunder()` (oder der
    öffentliche Renderpfad, der sie aufruft) wird mit einer Fixture-Liste
    von `ForecastDataPoint`s aufgerufen, deren gewitternde Stunde
    `hail_flag=True` trägt — der zurückgegebene String enthält das
    Hagel-Textfragment. Zusätzlich ein struktureller Beleg (Grep/AST auf
    den Aufruf von `format_hail_note`/`hail_priority` innerhalb der
    Funktion), damit die unbelegte S5a-Behauptung nicht wiederholt wird —
    ein Test, der nur prüft, dass die Funktion EXISTIERT, ohne den
    Rückgabewert zu verifizieren, erfüllt diesen AC NICHT.

- **AC-5 (Mehrtages-Vorschau, Wurzel-Fix wirkt in allen 3 Konsumenten):**
  Given ein `+1`-Forecast-Eintrag mit aggregiertem `hail_flag=True` für die
  Folge-Etappe / When (a) die E-Mail-Gewitter-Vorschau (Klartext UND HTML),
  (b) `email/outlook.py` und (c) das SMS-Token `TH+:` gerendert werden /
  Then zeigen alle drei denselben Hagel-Hinweis bzw. Suffix — keiner der
  drei Konsumenten bleibt beim alten, hagel-losen Text.
  - Test: Ein einziges Fixture-`thunder_forecast`-Dict mit dem neuen
    `"hail"`-Feld wird durch alle drei Renderer gespielt; jeder der drei
    Outputs wird einzeln auf das Hagel-Fragment geprüft (drei getrennte
    Assertions, kein „einer reicht").

- **AC-6 (sms_trip.py, today/tomorrow-Konsistenz):** Given ein
  `thunder_forecast["+1"]["hail"] == True` / When das SMS-Trip-Briefing für
  den Folgetag gerendert wird / Then trägt `tomorrow`s `DailyForecast`
  ebenfalls `hail_flag=True` (nicht mehr strukturell leer wie vor dieser
  Spec) UND der gerenderte `TH+:`-Token zeigt den `+HL`-Suffix.
  - Test: Vorher/Nachher-Vergleich am selben Fixture — vor dem Fix bleibt
    `tomorrow.hail_flag` `None`/ungenutzt trotz vorhandener Information im
    Dict (Regressionsnachweis der gefundenen Lücke), nach dem Fix trägt der
    gerenderte SMS-Text den Suffix.

- **AC-7 (Ortsvergleich, alle SECHS `_fmt_thunder`-Aufrufstellen inkl. der
  beiden erst nachträglich gefundenen eigenen Kanäle):** Given ein
  Ortsvergleich mit einem Ort, dessen Tages-`hail_flag=True` ist, und einem
  zweiten Ort mit `hail_flag=None` / When (a) die HTML-Übersichtstabelle,
  (b) die Klartext-Fassung derselben Mail (`comparison.py`, Teil von
  `render_compare_email()`), (c) der Mehrtages-Ausblick
  (`compare_outlook_metric_ids.py`), (d) der eigene Ortsvergleich-SMS-Kanal
  (`render_compare_sms`/`_sms_metric_cell`) UND (e) der eigene
  Ortsvergleich-Telegram-Kanal (`render_compare_telegram`/
  `_plain_metric_cell`) gerendert werden / Then zeigt in allen fünf
  Ausgaben NUR der True-Ort den zusätzlichen Hagel-Hinweis; bestehende
  Aufrufer, die `_fmt_thunder()` ohne den neuen Parameter aufrufen, brechen
  NICHT (Default-Verhalten zeichengleich zum Stand vor dieser Spec).
  - Test: Fünf gerenderte Ausgaben (HTML-Matrix, Klartext, Ausblick, SMS,
    Telegram) aus demselben Zwei-Orte-Fixture; jede einzeln auf den
    Hagel-Hinweis beim True-Ort und dessen Abwesenheit beim None-Ort
    geprüft. Für den SMS-Kanal zusätzlich: das bestehende
    Zeichenbudget/GSM-7-Verhalten (Issue #1362) bleibt unverändert, der
    Hagel-Zusatz zählt regulär gegen das Budget (kein Sonderfall, kann bei
    engem Budget mit verdrängt werden wie jede andere Zelle). Ein
    zusätzlicher Regressionstest ruft `_fmt_thunder(ThunderLevel.HIGH)`
    (EIN Argument, alter Aufruf-Stil) auf und erwartet exakt den
    bisherigen String ohne `TypeError` und ohne Hagel-Fragment.

- **AC-8 (Ortsvergleich-Stundentabelle, Text statt Ampel-Kreis — geklärte
  Designfrage):** Given eine Compare-Stundentabellen-Zeile mit
  `hail_flag=True` für eine Stunde mit `thunder_level != NONE` / When die
  Stundentabelle des Ortsvergleichs gerendert wird / Then zeigt die Zelle
  den Hagel-Hinweis als Text-Anhang an `_fmt_thunder()` — NICHT als
  Doppelring, weil die Compare-Stundentabelle für "thunder" keinen
  Ampel-Kreis (`_ampel_dot_css`) nutzt, sondern Textlabel + separate
  Zell-Tönung (`_sev_thunder`).
  - Test: Gerendertes HTML-Fragment der Compare-Stundenzeile enthält den
    Hagel-Text in der Zelle; ein Test, der stattdessen einen zweiten
    `box-shadow`-Ring in dieser Zeile erwartet, MUSS fehlschlagen — belegt,
    dass die beiden Stundentabellen (Trip vs. Compare) bewusst
    unterschiedliche Darstellungsmodi für dieselbe Information nutzen.

- **AC-9 (Telegram-Stunden-Drilldown):** Given ein Nutzer ruft den
  `⛈ Gewitter`-Drilldown (`dd_thunder_today`/`dd_thunder_tomorrow`) für
  einen Trip mit mindestens einer Stunde `hail_flag=True` auf / When die
  Antwort gebaut wird / Then enthält die entsprechende Stundenzeile den
  Hagel-Hinweis, Stunden mit `hail_flag=None` bleiben unverändert.
  - Test: `trip_command_processor`-Callback wird mit einer Fixture-
    Snapshot-Zeitreihe aufgerufen (über `WeatherExtractor.drilldown()`,
    kein Mock der Drilldown-Methode selbst); die zurückgegebene
    Telegram-Nachricht wird auf das Hagel-Textfragment in der richtigen
    Zeile geprüft.

- **AC-10 (Abgrenzung zur Gewitterstufe — PFLICHT-Mutationsschutz, gilt
  unverändert aus S5a AC-3):** Given eine der 6 Codeänderungen dieser Spec
  (Punkte 2–6, Punkt 1 ist reine Kürzel-Umbenennung ohne Signalwirkung) ist
  umgesetzt / When `thunder_level_from_signals()` mit derselben
  Signalkombination (Wettercode, Blitzdichte, CAPE, Blitzpotenzial) einmal
  mit und einmal ohne `hail_flag` aufgerufen wird / Then ist das Ergebnis
  in jedem der 6 betroffenen Aufrufkontexte identisch — Hagel fließt an
  keiner der 6 neuen Stellen in die Stufenberechnung ein.
  - Test: Regressionstest (Fortsetzung des S5a-Tests) prüft nach jeder der
    6 Änderungen erneut, dass `thunder_level_from_signals()` zeichengleich
    bleibt. Gegenprobe (Adversary-Mutationskandidat): Wird `hail_flag` in
    irgendeiner der 6 neuen Aufrufstellen versehentlich zusätzlich an
    `thunder_level_from_signals()` durchgereicht oder beeinflusst die
    dortige Text-/Farbentscheidung, MUSS dieser Test rot werden.

- **AC-11 (keine Handlungsempfehlung, ADR-0007, alle neuen Textstellen):**
  Given jede der neu ergänzten Ausgaben (compact_summary, Mehrtages-Vorschau
  ×3 Konsumenten, Ortsvergleich ×5 Aufrufer inkl. SMS/Telegram,
  Telegram-Drilldown) mit `hail_flag=True` / When der tatsächlich sichtbare
  Text geprüft wird / Then enthält er an keiner Stelle einen Ratschlags-/
  Imperativtext ("Schutz suchen", "Vorsicht", "meiden", o.ä.) — nur die
  faktische Kennzeichnung, identisch zum in S5a etablierten Muster
  ("Hagel: ja").
  - Test: Rendert alle betroffenen Stellen für eine True-Fixture und prüft
    den tatsächlich gerenderten, an den Nutzer gehenden Text auf Abwesenheit
    einer festgelegten Verbotswortliste (dieselbe Liste wie S5a AC-8) —
    Verhaltensnachweis am Renderer-Output, keine Ersatzprüfung an einer
    Quelldatei.

## Known Limitations

1. **Diese Spec fügt ausschließlich Anzeige-Aufrufe hinzu — keine neue
   Berechnungslogik.** `hail_flag`, `hail_priority()`, `format_hail_note()`
   bleiben unverändert aus S5a; alle Punkte konsumieren sie nur an neuen
   Stellen.
2. **Die WMO-Code-Grenze aus S5a gilt unverändert weiter** (kein
   verlässliches "nein" möglich, s. S5a Known Limitations 1–2) — diese
   Nachbesserung ändert nichts an der Datenqualität, nur an der
   Vollständigkeit der Ausgabeorte.
3. **Compare-Stundentabelle nutzt keinen Ampel-Kreis für Gewitter** (im
   Gegensatz zur Trip-Stundentabelle) — die in dieser Spec unter Punkt 2
   ausgearbeitete Doppelring-Lösung ist bewusst NUR für die
   Trip-Stundentabelle gedacht; ein künftiger Wechsel der
   Compare-Stundentabelle auf Ampel-Kreise (falls je gewünscht) bräuchte
   eine eigene Folgeentscheidung inkl. eigenem Design für den Hagel-Zusatz.
4. **`aggregate_stage()`'s Level-2-Filter-Einschränkung aus S5a Known
   Limitation 3 bleibt unverändert bestehen** — wird von keinem der Punkte
   dieser Spec berührt, da alle nur bereits aggregierte `hail_flag`-Werte
   konsumieren, nicht neu aggregieren.
5. **Kein Frontend-/Editor-Zugang** (unverändert aus S5a AC-9) — auch diese
   Nachbesserung fügt keinen wählbaren Hagel-Eintrag im Trip-Editor oder
   `GET /api/metrics` hinzu.
6. **Renderer-Mail-Gate #811 gilt für zwei der geänderten Dateien**
   (`compact_summary.py`, `email/compare_html.py`) — der Commit dieser
   Spec kann erst abgeschlossen werden, wenn `test_issue_811_mode_matrix.py`
   grün ist UND ein erfolgreicher `briefing_mail_validator.py`-Lauf gegen
   echte Staging-Mail vorliegt (Teil der Deploy-Phase, nicht dieser Spec).
7. **Trip-Report-Highlights (`trip_report.py::_compute_highlights()`) sind
   toter Code seit Issue #790** — der `highlights`-Parameter wird von
   `render_html()`/`render_plain()` seither ausdrücklich über `**_ignored`
   verworfen und beeinflusst die tatsächliche Ausgabe nicht mehr. Ursprünglich
   als 7. Lücke gezählt, dann bei der Test-Recherche als wirkungslos erkannt
   und aus dem Umfang dieser Spec entfernt (s. Purpose-Korrektur). Eigener
   Fund, unabhängig von Hagel: entweder ein bewusst abgeschalteter,
   inzwischen überflüssiger Code, der aufgeräumt werden könnte, oder eine
   vergessene Abschaltung einer eigentlich gewünschten Funktion — Klärung
   und ggf. Aufräumen ist NICHT Teil dieser Spec (Nebenbefund, s. #1199).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Bezug auf **ADR-0007** (Daten statt
  Empfehlungen, aktiv, nicht abgelöst), unverändert aus S5a.
- **Rationale:** Alle neuen Ausgabeorte zeigen Hagel ausschließlich als
  deskriptives Faktum (identisch zum bereits genehmigten S5a-Muster
  "Hagel: ja"/Doppelring), niemals als Handlungsempfehlung. Es wird keine
  neue Architektur-Entscheidung getroffen, sondern die bestehende
  konsequent auf alle Ausgabeorte angewendet — kein neues ADR nötig.

## Changelog

- 2026-08-05: Initial spec created (Issue #1475 Nachbesserung, Epic #1419;
  schließt die ursprünglich übersehenen Ausgabeorte plus SMS-Kürzel-
  Umbenennung `+HG` → `+HL`; PO-Entscheidung 2026-08-05: Ampel-Kreis-Modus
  der Trip-Stundentabelle bekommt Doppelring + Erklärungssatz, Compare-
  Stundentabelle bleibt textbasiert, da sie keinen Ampel-Kreis für
  Gewitter nutzt).
- 2026-08-05 (Korrektur, zweite Recherche-Runde, PO-Auftrag "zähle alle
  Orte in allen Nachrichten/Channeln auf"): Punkt 7 (Trip-Report-Highlights)
  als toter Code seit #790 identifiziert und ersatzlos aus dem Umfang
  entfernt (AC-10 alt gestrichen, s. Known Limitations 7). Zwei bisher
  komplett übersehene Ausgabeorte gefunden und in Punkt 5/AC-7 ergänzt:
  Ortsvergleich hat eigene Telegram- und SMS-Renderer
  (`render_compare_telegram`/`render_compare_sms` in `comparison.py`), die
  denselben `_fmt_thunder()` nutzen wie die bereits bekannten
  Ortsvergleich-Stellen — sechs statt vier Aufrufstellen. AC-Nummerierung
  entsprechend angepasst (AC-11/AC-12 alt → AC-10/AC-11 neu).
