# Context: feat-2134-adhoc-abruf-metrik-katalog

Issue: [#2134](https://github.com/henemm/gregor_zwanzig/issues/2134) — Scheibe S1 zu Epic
[#2133](https://github.com/henemm/gregor_zwanzig/issues/2133).
Erstellt: 2026-09-06. Alle Zeilenangaben gegen `main` @ `c34626a9` + PR #2135 nachgemessen.

## Request Summary

Der Ad-hoc-Abruf (Nutzer fragt unterwegs per Telegram oder E-Mail nach einer Wettergröße) kennt
heute **drei** Größen, weil sie in einer handgepflegten Kurzliste stehen. Er soll sich stattdessen
aus dem Metrik-Katalog bedienen — dem Ort, an dem alle 29 wählbaren Größen mit deutschem Wort,
Einheit und Stundenfeld bereits vollständig beschrieben sind.

## Gemessener Ist-Stand

### Die Kette ist gebaut — es fehlt genau eine Verbindung

| Glied | Stand | Beleg |
|---|---|---|
| Stundenwerte führen die Felder | ✅ | `src/app/models.py` (`ForecastDataPoint`) |
| Metrik-Katalog beschreibt jede Größe | ✅ **32 Einträge, 29 `selectable`** | `src/app/metric_catalog.py:28-95` (Dataclass), `:1038-1059` (Lookups) |
| **Jede der 29 wählbaren Größen hat ein Stundenfeld** | ✅ **29/29, keine Ausnahme** | selbst nachgemessen, s. u. |
| Abruffunktion ist generisch, ohne Erlaubt-Liste | ✅ | `src/services/weather_extractor.py:169` (`getattr(p, metric, None)`) |
| Zentrale Wert-Formatierung inkl. Einheit + `display_unit` | ✅ | `src/output/metric_format.py:78-130` (`format_value`) |
| **Auswahl im Abruf** | 🔴 **verdrahtet** | s. u. |

### Die Engstellen (alle in `src/services/trip_command_processor.py`)

| Stelle | Zeile | Inhalt |
|---|---|---|
| `_DRILLDOWN_METRICS` | `:287-291` | Dict mit **genau 3** Einträgen: `thunder`→`thunder_level`, `wind`→`wind10m_kmh`, `precip`→`precip_1h_mm`; je Eintrag Überschrift + Formatierer |
| `_DRILLDOWN_PATTERN` | `:224` | `^dd_(thunder\|wind\|precip)_(today\|tomorrow)$` — Spiegelbild derselben drei |
| `_HOURS_PATTERN` | `:225` | `^dd_hours_(today\|tomorrow)$` |
| `_HEUTE_BUTTONS` / `_MORGEN_BUTTONS` | `:117-139` | Vier feste Telegram-Buttons: Stunden · Gewitter · Wind · Regen |
| `_handle_drilldown` | `:709-767` | Einzelgrößen-Verlauf — die Bauform funktioniert, sie ist nur auf drei Größen eingezäunt |
| `_handle_hours_drilldown` | `:771-844` | Vier feste Abrufe `:794-797`, feste vierspaltige Ausgabezeile `:834` |
| **Temperatur-Abbruch** | `:799` | `if not r_temp.available: return` — kippt den **ganzen** Stundenabruf, obwohl Wind/Regen/Gewitter separat abgerufen und per Zeitstempel gemappt werden (`:812-814`), also unabhängig vorhanden sein könnten |
| `_BARE_KEYWORD_MAP` | `:87-103` | Getippte Wörter → interner Schlüssel; **enthält keine Metrik-Wörter** außer `gewitter`→`heute_gewitter` |
| `_VALID_COMMANDS` | `:83` | Whitelist der `### key`-Befehle |

### Katalog-Messung (selbst ausgeführt, 2026-09-06)

```
Katalog gesamt: 32 | selectable: 29
selectable MIT Stundenfeld in ForecastDataPoint: 29
selectable OHNE Stundenfeld:                      0
nicht selectable: temperature_cold, confidence, cape
```

Die 29 wählbaren Größen mit ihrem Stundenfeld:

| id | `label_de` | `dp_field` | Einheit |
|---|---|---|---|
| `temperature` | Temperatur | `t2m_c` | °C |
| `temperature_night` | Nacht-Tiefsttemperatur | `t2m_c` | °C |
| `temperature_day_low` | Tages-Tiefsttemperatur (Gehzeit) | `t2m_c` | °C |
| `temperature_day_high` | Tages-Höchsttemperatur (Gehzeit) | `t2m_c` | °C |
| `wind_chill` | Gefühlte Temperatur | `wind_chill_c` | °C |
| `wind_chill_night` / `_day_low` / `_day_high` | Gefühlte … | `wind_chill_c` | °C |
| `humidity` | Luftfeuchtigkeit | `humidity_pct` | % |
| `dewpoint` | Taupunkt | `dewpoint_c` | °C |
| `wind` | Wind | `wind10m_kmh` | km/h |
| `gust` | Böen | `gust_kmh` | km/h |
| `wind_direction` | Windrichtung | `wind_direction_deg` | ° |
| `precipitation` | Niederschlag | `precip_1h_mm` | mm |
| `rain_probability` | Regenwahrscheinlichkeit | `pop_pct` | % |
| `thunder` | Gewitter | `thunder_level` | — (`is_level=True`) |
| `snowfall_limit` | Schneefallgrenze | `snowfall_limit_m` | m |
| `precip_type` | Niederschlagsart | `precip_type` | — |
| `cloud_total` / `cloud_low` / `cloud_mid` / `cloud_high` | Bewölkung / Tiefe / Mittelhohe / Hohe Wolken | `cloud_*_pct` | % |
| `visibility` | **Sichtweite** | `visibility_m` | m → **Anzeige km** (`display_unit`) |
| `sunshine` | Sonnenstunden | `dni_wm2` | h |
| `uv_index` | UV-Index | `uv_index` | — |
| `pressure` | Luftdruck | `pressure_msl_hpa` | hPa |
| `freezing_level` | Nullgradgrenze | `freezing_level_m` | m |
| `snow_depth` | Schneehöhe | `snow_depth_cm` | cm |
| `fresh_snow` | Neuschnee | `snow_new_24h_cm` | cm |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py` | **Hauptschauplatz** — beide Engstellen, Kommando-Erkennung, Ausgabe-Formatierung |
| `src/app/metric_catalog.py` | Quelle des Vokabulars: `MetricDefinition`, `get_metric`, `get_all_metrics` (liefert nur `selectable=True`) |
| `src/output/metric_format.py` | `format_value(metric_id, value, style)` — Rundung, Einheit, `display_unit`-Umrechnung (m→km). Wiederverwendbar statt eigener Formatierer |
| `src/services/weather_extractor.py` | `drilldown(trip_id, metric, from_time, hours)` — bereits generisch, **unverändert nutzbar** |
| `src/services/inbound_telegram_reader.py` | Eintritt Telegram: `_SHORTCUT_MAP` `:37-58`, `_CALLBACK_QUERY_MAP` `:61-80` |
| `src/services/inbound_email_reader.py` | Eintritt E-Mail `:150` |
| `src/app/models.py` | `ForecastDataPoint` — die Stundenfelder |

## Existing Patterns

- **Katalog als Single Source of Truth** ist im Repo etabliert: `metric_and_aggregation_for_field()`
  (`metric_catalog.py`, Rückwärts-Auflösung Feld→Metrik) und `SMS_MULTI_SYMBOLS_BY_METRIC` werden
  bereits **aus** dem Katalog abgeleitet statt danebengepflegt (Kommentar `metric_catalog.py:88-94`).
  Der Ad-hoc-Abruf ist der verbliebene Nachzügler.
- **Kanalschalter statt Zweitcode:** `with_emoji = channel == "telegram"` (`:718`, `:781`) — eine
  Funktion, ein Parameter, zwei Darstellungen (#1222 AC-6). Dasselbe Muster trägt die Kanaltreue.
- **Zwei Abrufe, Merge über Zeitstempel** (`:812-814`, und `hail_flag` `:740-746`): die generische
  `drilldown()` wird mehrfach gerufen und über `pt.ts` zusammengeführt. Skaliert auf N Größen.
- **Stufen-Größen sind eigene Bauart:** `thunder` trägt `is_level=True`, wird über
  `_thunder_fmt`/`_thunder_symbols()` als Wort/Emoji gerendert, nicht als Zahl.

## Dependencies

- **Upstream:** Metrik-Katalog · `WeatherExtractor.drilldown` · Snapshot-Speicher · `_day_window()`
  (Ortstag-Fensterung, #1470)
- **Downstream:** Telegram-Inbound (Buttons + Callbacks) · E-Mail-Inbound · `CommandResult` →
  `notification_service.send_command_reply_*`

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/trip_command_processor.md` (v2.1) | Hauptspec des Kommando-Verarbeiters |
| `docs/specs/modules/issue_654_telegram_tier3_drilldown.md` (v1.0) | Führte den Einzelgrößen-Drilldown ein — AC-3 nennt genau Wind/Regen/Gewitter |
| `docs/specs/modules/fix_1470_drilldown_ortszeit.md` | Ortstag-Fensterung |
| `docs/specs/modules/issue_667_drilldown_clip.md` | Clipping am Tagesrand |
| `docs/specs/modules/weather_config.md` (v2.0) | Katalog-Spec |
| `docs/reference/metric_output_matrix.md` | Führt `_DRILLDOWN_METRICS` bereits als **„handgeschrieben, als Regex eingefroren, unbewacht gegen den Katalog"** |

**Keine Spec zu #2134** — muss in `/30-write-spec` entstehen.

## Tests (Ist-Abdeckung)

| Datei | Fokus |
|---|---|
| `tests/tdd/test_trip_command_processor.py` (338 Z.) | Kommando-Parser, Drilldown-Muster, Bare-Keywords |
| `tests/unit/test_metric_catalog.py` | Metrik-Definitionen, SMS-Codes |
| `tests/tdd/test_metric_catalog_reverse_lookup.py` | Rückwärts-Auflösung Feld→Metrik |
| `tests/unit/test_metric_catalog_trip_defaults.py` | Trip-Defaults |

🔴 **Kein Test bewacht, ob der Abrufpfad mit dem Katalog synchron ist.** Genau die Lücke, die das
Ticket schließt — und der Grund, warum die Armut nie aufgefallen ist.

## Risks & Considerations

1. **Mehrere Metriken teilen ein Stundenfeld.** `temperature`, `temperature_night`,
   `temperature_day_low`, `temperature_day_high` zeigen alle auf `t2m_c`; ebenso die vier
   `wind_chill_*`. Als **Verlauf** liefern sie denselben Kurvenzug — sie unterscheiden sich nur in
   der Tages-*Auswertung*. Muss in der Spec entschieden werden: alle acht als eigene Abrufwörter,
   oder nur die Basisgrößen.
2. **Das deutsche Wort taugt nicht überall als Tippwort.** „Tages-Höchsttemperatur (Gehzeit)" ist
   kein Kommando. Braucht eine Normalisierung (klein, ohne Klammerzusatz) oder den Rückgriff auf
   `compact_label`/`col_key`.
3. **Geführt ≠ gefüllt.** Nicht jede Größe ist in jedem Gebiet befüllt (Fallback-Kette,
   `docs/reference/decision_matrix.md`). Eine Lücke muss **benannt** werden, nicht als Schweigen
   erscheinen — dieselbe Anforderung wie die Messlücken-Kennzeichnung aus #2050 S4b.
4. **Der Temperatur-Abbruch (`:799`) ist ein eigenständiger Defekt** und wird von AC-3 mit
   abgeräumt. Achtung: nach dem Fix darf die Stundentabelle nicht *stumm* leer antworten.
5. **`selectable=false` darf nicht zweitformuliert werden.** `get_all_metrics()` filtert bereits;
   wer stattdessen über `_METRICS` iteriert, baut die Regel ein zweites Mal — und damit die
   Doppelpflege wieder auf, die das Ticket abschafft.
6. **Stufen- und Sondergrößen:** `thunder` (`is_level`), `precip_type` und `wind_direction` sind
   keine schlichten Messzahlen. `format_value()` deckt sie nicht automatisch ab — es braucht einen
   Formatierer-Bezug, der aus dem Katalogeintrag folgt statt aus einer neuen Liste.
7. **Telegram-Buttons können nicht 29 Größen tragen.** Die Buttons bleiben eine kuratierte
   Auswahl; das getippte Wort ist der Weg zur vollen Breite. Kein Widerspruch, aber ein
   Spec-Punkt: Buttons ≠ Vokabular.
8. **Abgrenzung wahren** (Epic #2133): „ab jetzt"/Wechselpunkte → S2 · Kanaltreue → S3 (#2126) ·
   Premium-SMS als Eingangsweg → S4 · Kurzform-Verlauf → S5. Diese Scheibe ändert **nur** die
   Herkunft des Vokabulars.
9. **LoC-Limit 250.** Der Umbau ersetzt Listen durch Katalogzugriffe; realistisch, aber die
   Formatierer-Zuordnung und der Wächter-Test können es eng machen.

## Next

`/20-analyse` — offene Entscheidungen aus „Risks" 1, 2, 6, 7 klären und die AC-Entwürfe des
Tickets zu prüfbaren ACs schärfen.

---

# Analysis (Phase 2, 2026-09-06)

## Type

**Feature** mit zwei eingeschlossenen Bugs (#2137, #2120) — der Umbau fasst dieselbe Funktion an,
eine Trennung würde konkurrierende Änderungen an `_parse_command` erzeugen.

## Scope nach PO-Ansagen (2026-09-06)

| # | Vorgabe | Quelle |
|---|---|---|
| 1 | Abrufwort ist die Tabellenüberschrift `col_label` — **einheitlich über alle Kanäle** | PO |
| 2 | `Hilfe` gibt die **vollständige** Liste aus, ausdrücklich auch per E-Mail | PO |
| 3 | Der E-Mail-Fußzeilenblock „Antwort-Kommandos" wird angepasst | PO |
| 4 | **Umfangreiche Tests** — heute funktionieren nicht alle Kommandos | PO |
| 5 | #2137 (`> Heute`) und #2120 (`/strecke 5`) mit abräumen | Tech Lead, PO-Befund |

## 🔴 Kernbefund: es sind ACHT handgepflegte Befehlslisten

| # | Ort | Inhalt | Fehlt darin |
|---|---|---|---|
| 1 | `trip_command_processor.py:83` `_VALID_COMMANDS` | 11 Einträge | heute, morgen, gewitter, glance |
| 2 | `:87-103` `_BARE_KEYWORD_MAP` | 15 Wörter | report, startdatum |
| 3 | `:107` `_QUERY_KEYS` | 6 Einträge | — |
| 4 | `:1385-1401` `_show_help` | 12 Zeilen | glance, report, startdatum |
| 5 | `:402` + `:488` Fehlertext | **6 veraltete** | heute, morgen, jetzt, gewitter, strecke, pause, skip, weiter |
| 6 | `email/plain.py:364-375` Klartext-Fußzeile | 9 Zeilen | **strecke** |
| 7 | `email/html.py:471-519` HTML-Fußzeile | 9 Einträge | **strecke, ruhetag** |
| 8 | `inbound_telegram_reader.py:33-35` `_VALID_COMMANDS` + `:206` Fehlertext | 13 / 9 | **strecke, pause, skip** |

Keine zwei dieser Listen stimmen überein. Der Nutzer bekommt je nach Kanal und Fehlerweg eine
andere Auskunft darüber, was er darf.

## Vokabular-Messung (selbst ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| `col_label`, normalisiert, untereinander | **29/29 eindeutig, 0 Kollisionen** |
| `col_label` gegen alle Befehlswörter | **0 Kollisionen** |
| `compact_label` (29) / `sms_code` (27) | ebenfalls kollisionsfrei → als Zweitschreibweise nutzbar |

**🔴 Normalisierungsregel ist entscheidungsrelevant:** `%` muss als `pct` übersetzt werden, nicht
getilgt. Sonst fallen `Rain` (precipitation) und `Rain%` (rain_probability) auf dasselbe Wort
zusammen — gemessen: mit Tilgung 1 Kollision, mit `%`→`pct` **0**. `°` wird getilgt
(`0°Line` → `0line`, zusätzlich per `sms_code` `FZ` erreichbar).

## Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | Ableitung `metric_command_words()` (normalisiertes Wort → `metric.id`), über `get_all_metrics()` — erbt `selectable=False` automatisch |
| `src/services/trip_command_processor.py` | MODIFY | `_COMMAND_SPECS` als Einzelquelle; `_DRILLDOWN_METRICS`/`_DRILLDOWN_PATTERN` durch Katalog-Auflösung ersetzt; `_parse_command` streift führende Zeichen; `_show_help` abgeleitet; Fehlertexte `:402`/`:488` ersetzt; Temperatur-Abbruch `:799` |
| `src/output/metric_format.py` | MODIFY | `PRECIP_TYPE_LABEL_DE` neben bestehendem `THUNDER_LABEL_DE` (~4 Zeilen) |
| `src/services/inbound_telegram_reader.py` | MODIFY | eigene Liste `:33-35` und Fehlertext `:206` an die Einzelquelle hängen |
| `src/output/renderers/email/plain.py` | MODIFY | Fußzeile `:364-375` aus `_COMMAND_SPECS` |
| `src/output/renderers/email/html.py` | MODIFY | `_render_kommandos_section` `:471-519` aus `_COMMAND_SPECS` |
| `tests/golden/email/*-plain.txt`, `*-html.txt` (je 5) | REGENERATE | mit zeilenweisem Diff-Beweis |
| `tests/fixtures/outlook_trip_parity/*` | REGENERATE | dito |
| Tests (neu + angepasst) | CREATE/MODIFY | s. u. |

**Import-Richtung geprüft (kein Zirkel):** `email/plain.py:52` importiert bereits
`ACTIONS_BUBBLE_BUTTONS` aus `trip_command_processor`; `narrow.py:52` ebenso. Die Gegenrichtung
existiert nicht — `trip_command_processor` importiert nur `output.metric_format`, nie
`output.renderers.*`. `_COMMAND_SPECS` folgt dem bestehenden Muster.

## Formatierer-Auflösung für die drei Sondergrößen

Aus dem Katalogeintrag abgeleitet, **keine neue Liste**:

| Bedingung | Formatierer | Beleg |
|---|---|---|
| `metric.is_level` | `_thunder_fmt` (bereits katalog-gespeist über `THUNDER_LABEL_DE`) | `metric_format.py:283` |
| `dp_field == "wind_direction_deg"` | `degrees_to_compass()` — existiert bereits | `src/utils/geo.py:32` |
| `dp_field == "precip_type"` | `PRECIP_TYPE_LABEL_DE` (neu in `metric_format.py`) | Enum `models.py:47` |
| sonst | `format_value(metric.id, value)` — Rundung, Einheit, `display_unit` (m→km) | `metric_format.py:78-130` |

Die Prüfung geht auf `is_level` statt auf `id == "thunder"`, damit eine künftige zweite
Stufengröße automatisch mitgetragen wird.

## Hilfe-Ausgabe: Längenrechnung

12 Befehle × ~55 Zeichen + 29 Metrikwörter × ~35 Zeichen + Rahmen ≈ **1800 Zeichen** gegen die
Telegram-Grenze von 4096 (`output/channels/telegram.py:18`). **Eine Nachricht reicht**, keine
Aufteilung nötig — solange die Metrikzeile das Kürzel plus Einheit trägt und nicht den vollen
`label_de`.

## 🔴 Tests, die den heutigen Zustand festnageln

**Zeichengenaue Vergleichsdateien — brechen sicher, sobald die Fußzeile sich ändert:**
`tests/golden/email/{stem}-plain.txt` (5) · `{stem}-html.txt` (5) ·
`tests/fixtures/outlook_trip_parity/trip_outlook_show_acc_true.{html,txt}`.

**Verfahren (PFLICHT, sonst rutscht eine unbeabsichtigte Änderung mit durch):**
1. Baseline: `git diff` auf die Vergleichsdateien ist leer.
2. Test rot laufen lassen, den gerenderten Ist-Stand in eine Scratch-Datei schreiben.
3. `diff alt neu` **zeilenweise** — jede Abweichung außerhalb des Fußzeilenblocks ist ein
   Abbruchkriterium, keine Rundungstoleranz.
4. Erst dann überschreiben. Der committete Diff ist der Beleg.

**Weitere festnagelnde Tests:** `test_issue_704_telegram_interactive_navigation.py` (AC-4/5
Buttonreihen, AC-6..9) · `test_issue_654_telegram_thunder_drilldown.py` (AC-4) ·
`test_drilldown_day_window_local_date.py` · `test_telegram_drilldown_local_time_boundary.py` ·
`test_command_reply_channel_emoji.py` · `test_strecke_kommando_eingang.py:199-220` (AC-3) ·
`test_trip_command_processor.py:323-331` · `test_inbound_telegram_reader.py:309-310` ·
`test_issue_731_unified_commands.py` (AC-1) · `test_issue_612_report_on_demand.py` (AC-3) ·
`test_bundle_851_852_email_pill_format.py` (AC-3) · `test_issue_790_briefing_simplify.py` ·
`test_shared_outlook_renderer.py:132`.

`test_trip_command_processor.py:327` (`assert "ruhetag" in …`) bricht **bewusst** — die Assertion
prüft exakt die veraltete Liste, die entfernt wird.

## Bindende Vorgaben

- **ADR-0042**: Namensklassen. Der Umbau erzeugt **keine** neue Namensliste, sondern leitet ab —
  erfüllt die Kernregel. Die Zeilen-Zuordnung „3-Tages-Ausblick → deutsch" wird durch die
  PO-Ansage abgelöst (→ #2136, eigenes ADR).
- **ADR-0044**: Ortstag über `trip_local_today()`. `_day_window()` erledigt das bereits —
  unverändert weiterverwenden.
- **ADR-0037 / ADR-0055**: Katalog ist Quelle, nicht handgepflegte Liste — der Umbau setzt das
  Muster fort. Kein Widerspruch gefunden.

## Scope Assessment

- Produktivcode-Dateien: **6** · Testdateien: ~10 angepasst + ~4 neu
- Geschätzte LoC: **~430–550** (Produktiv ~230–280, Tests ~250–320, Vergleichsdateien
  regeneriert)
- **LoC-Limit 250 wird gerissen → Anhebung auf 500 nötig** (`workflow.py set-field
  loc_limit_override 500`); Vergleichsdateien zählen als generiert nicht mit.
- Risiko: **MITTEL** — Umfang groß, aber jeder Schritt einzeln grün-fähig; kein Datenmodell,
  keine Persistenz, keine Migration.

## Technical Approach (Empfehlung, angenommen)

**Eine Scheibe, zwei Liefer-Schritte.** Die Trennung ist ein PR-Schnitt, **keine
Auftragsverkleinerung** — der Fußzeilen-Umbau ist ausdrückliche PO-Vorgabe und gehört in dieselbe
Scheibe, weil er dieselbe Einzelquelle konsumiert.

**Schritt A** — Services/Katalog-Schicht, berührt **keine** Datei unter `output/renderers/email/`,
also **kein** Vergleichsdatei-Risiko:
1. `_parse_command` streift führende `>` / `/` (behebt #2137 + #2120) — isoliert testbar
2. `metric_command_words()` im Katalog, mit Kollisionswächter und der `%`→`pct`-Regel
3. `_DRILLDOWN_METRICS`/`_DRILLDOWN_PATTERN` → Katalog-Auflösung + Formatierer-Dispatch
4. Temperatur-Abbruch `:799`: Abbruch nur, wenn **alle** Größen fehlen
5. `_show_help` aus `_COMMAND_SPECS` + `metric_command_words()`
6. Fehlertexte `:402`/`:488` aus derselben Quelle
7. `inbound_telegram_reader.py:33-35` und `:206` an dieselbe Quelle hängen

**Schritt B** — Präsentationsschicht: `plain.py:364-375` und `html.py:471-519` konsumieren
`_COMMAND_SPECS`; Vergleichsdateien nach dem Diff-Verfahren oben neu gezogen.

Nach Schritt A sind alle bestehenden Vergleichsdateien unverändert grün.

## Open Questions

Keine offenen Fragen an den PO. Alle Entscheidungen sind getroffen:
Vokabular = `col_label` (PO) · Normalisierung `%`→`pct`, `°` getilgt (Tech Lead, gemessen) ·
Zweitschreibweise über `sms_code` (Tech Lead) · Umfang ungeteilt (PO-Vorgabe 3) ·
LoC-Anhebung auf 500 (Tech Lead).

## Next

`/30-write-spec` — ACs auf Deutsch zur PO-Freigabe.
