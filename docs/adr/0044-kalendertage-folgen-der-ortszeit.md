# ADR-0044: „Heute" und „morgen" bestimmen sich nach der Ortszeit der Tour, nicht nach Weltzeit

- **Status:** Akzeptiert (PO-Entscheidung 2026-08-03)
- **Datum:** 2026-08-03
- **Bezug:** Issue #1470, Issue #1465 (Ursprung), ADR-0035 (Tagesfenster als Zeitraum — ergänzt, nicht abgelöst), Issue #1345 (Hausnorm naive UTC), Issue #1402 (Ortszeit im `/jetzt`-Pfad), Spec `docs/specs/modules/fix_1470_drilldown_ortszeit.md`

## Kontext

Das Produkt beantwortet an mehreren Stellen die Frage „welcher Tag ist gemeint" — im
Telegram-Drilldown („Stunden heute", „Gewitter morgen"), bei den Befehlen `/heute` und
`/morgen`, beim Ruhetag-Vermerk, in der Statusanzeige.

Historisch wurde dieser Tag aus dem Zeitstempel der eingehenden Nachricht abgeleitet
(`msg.received_at.date()`) — und der trägt immer **UTC**. Auf Korsika begann „morgen"
damit um 02:00 Ortszeit: Die ersten zwei Stunden des Tages fehlten, die letzten zwei des
Vortages waren dabei. Kurz nach Ortsmitternacht meldete „heute" den Vortag. Bei einer Tour
in Neuseeland wären es zwölf Stunden Versatz gewesen.

Gefunden wurde das als Nebenbefund von #1465. Solange der Drilldown abstürzte, kam
niemand bis zu dieser Frage.

Die Sache ist **keine Fehlerbehebung, sondern eine Produktentscheidung**: Welche
24 Stunden „morgen" sind, muss jemand festlegen. Sie wurde dem PO ausdrücklich vorgelegt.

## Entscheidung

> **Kalendertage — „heute", „morgen" — bestimmen sich nach der Ortszeit der Tour.**

Die Zone wird aus den Koordinaten des Wegpunkts aufgelöst, mit dreistufigem Rückfall:
Etappe des Weltzeit-Tages → erste Etappe mit Wegpunkten → importierte UTC-Konstante.

**Abgrenzung zu ADR-0035:** Jenes ADR regelt das Tagesfenster als **Zeitraum** („welche
Stunden zählen für die Bewertung"). Dieses hier regelt den **Kalendertag** („welcher Tag
ist gemeint"). Beide gelten nebeneinander.

**Nicht betroffen: Dauern.** „Die nächsten zwölf Stunden" ist eine Dauer ab jetzt, keine
Kalendertagsgrenze — sie wird in UTC addiert und bleibt es. Sie an der Ortsmitternacht zu
kappen würde die Vorschau kurz vor Mitternacht still auf Minuten schrumpfen lassen.

**Nicht betroffen: die Hausnorm aus #1345.** Wetterdaten tragen weiterhin zeitzonenlose
UTC-Zeitstempel. Die Ortszeit entsteht erst bei der Auswertung „welcher Tag" und bei der
Beschriftung — nicht in den Daten.

## Konsequenzen

**Ein Ortstag hat nicht immer 24 Stunden.** An den Umstellungstagen sind es 23 oder 25, in
Zonen mit halbstündigem Wechsel (Lord Howe Island) auch 23,5. Jedes Tagesfenster muss
seine Länge **berechnen** statt sie zu setzen. Eine Signatur mit `hours: int` ist damit
falsch.

**Wer eine Bezugsgröße von Weltzeit auf Ortszeit umstellt, holt sich die Sommerzeit-Frage
neu ins Haus.** Vorher war die Rechnung umstellungs-immun. Bei #1470 wäre der Fehler
**erst durch die Verbesserung** entstanden — er wurde nur gefunden, weil der Prüfer
ausdrücklich danach gesucht hat. **Immer beide Wechseltage testen**, und zwar auf die
Häufigkeit *jeder einzelnen Stunde*, nicht auf die Zeilenzahl.

**Die Falle beim Rechnen** (bei #1470 gemessen, bevor gebaut wurde):

```
2026-03-29: gleiche tzinfo-Subtraktion=24.0  über UTC=23.0
2026-10-25: gleiche tzinfo-Subtraktion=24.0  über UTC=25.0
```

Tragen zwei zeitzonenbehaftete Zeitpunkte **dasselbe `tzinfo`-Objekt**, rechnet Python auf
den nackten Wanduhr-Werten und ignoriert den Offset-Wechsel — an jedem Tag 24,0. Beide
Zeitpunkte müssen **erst nach UTC umgerechnet** werden, im Projekt über `local_dt(dt, UTC)`
(nicht `dt.astimezone(UTC)` — der Zeitzonen-Wächter flaggt rohes `.astimezone`).

**Bei Touren über mehrere Zeitzonen bleibt ein Rest.** Wechselt der Wanderer an genau
diesem Tag die Zone, kann die Etappe des Weltzeit-Tages eine andere Zone tragen als die des
Ortstages. Der Fehler ist dann die Differenz zweier benachbarter Etappen — in aller Regel
null. Eine Tour dieser Spannweite hat ohnehin keinen eindeutigen „Kalendertag".

### Wo die Zonen-Auflösung liegt (Stand 2026-08-12, Issue #1697, #1724)

Die drei Bausteine waren ursprünglich **private Methoden** auf `TripCommandProcessor`. Seit
#1697 liegen sie als Modulfunktionen in **`src/services/trip_day.py`** und werden von dort
geteilt; #1724 hat `trip_local_now` ergänzt:

| Funktion | Aufgabe |
|---|---|
| `trip_tz(trip)` | Rückfall 2: erste Etappe mit Wegpunkten |
| `display_tz(trip, day_date)` | Zone der Etappe dieses Tages, sonst `trip_tz` |
| `anchor_tz(trip, now_utc)` | Auflösung der Henne-Ei-Falle: Zone der Etappe des **Weltzeit**-Tages |
| `trip_local_now(trip, now_utc)` | Ortstag UND Ortsstunde der Tour aus EINER Zonen-Auflösung |
| `trip_local_today(trip, now_utc)` | **der Ortstag der Tour** — das, was `date.today()` ersetzt; dünne Sicht auf `trip_local_now` |

Wer nur den Kalendertag braucht, ruft `trip_local_today()`; wer zusätzlich die Ortsstunde
braucht — etwa eine Fälligkeitsprüfung wie in #1725 —, ruft `trip_local_now()` direkt, damit
Tag und Stunde aus derselben Auflösung kommen. Eine eigene Kopie der Zonen-Auflösung ist ein
Regelverstoß — genau das war der Zustand vor #1697.

### Umgesetzt

- **Drilldown** (#1470) — der ursprüngliche Anlass dieses ADR.
- **Alarm-Pfad** (#1697, live 2026-08-11): `src/services/trip_alert.py` an allen drei
  Stellen, die einen Kalendertag bestimmen (`:404` Ablauf-Filter, `:584` Schnappschuss-
  Anker, `:911` Segmentwahl). Dieser Pfad stand in der Restliste unten **nie drin** und war
  trotzdem der schwerwiegendste Verstoß: nicht eine falsche Anzeige, sondern **ausbleibende
  Alarme**. Gemessen für eine gewöhnliche Etappe 08:00–19:00 Ortszeit — Neuseeland verlor
  die ersten ~4 von 11 Stunden *jedes* Etappentags, Kalifornien die letzten ~2, Mitteleuropa
  zwei Stunden jede Nacht.
  **Hinweis, kein neuer Haken (Issue #1667 S3, live 2026-08-11):** Die Segmentwahl (`:911`)
  ruft seither `trip_segments.py::resolve_current_segment()` und fällt additiv auf das
  Ziel-Segment des unmittelbaren Vortags zurück, wenn heute nichts aktiv ist. Das ändert
  **nicht** die Zonen-Auflösung dieses ADR — `today`/`gestern` bleiben beide über
  `trip_local_today()` bestimmt —, sondern nur die Tages-**Tiefe** der Suche (ein Tag
  zusätzlich statt nur der eine bereits aufgelöste Ortstag). Details:
  `docs/specs/modules/fix_1667_s3_tagesuebergreifende_segmente.md`.
- **Briefing-/Versand-Pfad** (#1724, live 2026-08-11; Fälligkeitsfenster + Idempotenz #1725,
  live 2026-08-12): `_get_target_date` und `_get_active_trips` in
  `src/services/trip_report_scheduler.py` bestimmen den Zieltag jetzt über `trip_local_today`
  statt `date.today()`; `save_dated`/`load_dated` schreiben und lesen denselben
  Ortstag-Schlüssel, Schreiber und Leser sind also zusammen umgestellt. #1725 löst zusätzlich
  die in ADR-0051 beschriebene Stundengleichheits-Falle: Fälligkeit ist jetzt ein Fenster von
  drei Ortsstunden ab der konfigurierten Stunde, gegen Doppelversand abgesichert über den
  Vermerk-Speicher `services/briefing_slots.py` (Schlüssel `(trip_id, ortstag, slot)`).
- **Ruhezeit, Alarm-Tageszähler und Ortsvergleichs-Slot-Fälligkeit** (#1726, S4 des Epics
  #1722): `deviation_alert_engine.is_quiet_hours()` und `alert_daily_limit.{load,is_allowed,
  increment}` bekamen einen **Pflicht**-Parameter `zone` (kein Default — ein impliziter
  Wien-/UTC-Rückfall wäre genau die behobene Fehlerklasse); beide `VIENNA`-Konstanten sind
  ersatzlos entfallen. Der Tageszähler führt seither einen Stand **je Zone**
  (`{"zones": {...}}`, Altbestand wandert beim ersten Zugriff unter `Europe/Vienna`) — der
  bewusste Preis ist, dass ein Nutzer mit Objekten in drei Zonen das Kontingent dreimal
  bekommt. `compare_slot_scheduler.presets_due_for_hour` prüft jedes Preset gegen die Zone
  **seines ersten auflösbaren Orts** statt alle gegen eine gemeinsame Stunde. Die Zone kommt
  bei Touren aus `anchor_tz`/`trip_local_now`, bei Ortsvergleichen aus dem neuen
  `utils.timezone.first_resolvable_tz()` — der einen fachlichen Auswahlregel für „erster
  Ort" (#1378 AC-4), die einen gelöschten oder zonenlosen Ersteintrag überspringt statt
  still auf Weltzeit zu kippen.
- **Anzeige-/Kommando-Pfad in `trip_command_processor.py` und `inbound_telegram_reader.py`**
  (#1727 S5a, live 2026-08-13, `fd87fca6`; `_handle_query` mit dieser Scheibe, #1795): `_show_status`,
  `_show_now` und `command_date` (für `### ruhetag`) lösen den Kalendertag seither über
  `trip_local_today` auf, `inbound_telegram_reader.py` reicht `received_at` durch statt selbst
  `date.today()` zu bilden. `_handle_query` — löst zusätzlich einen Versand aus, nicht nur eine
  Anzeige — folgt seit #1795 derselben EINEN Auflösung (`trip_local_now`) für Kopfzeile UND
  Ortszeit-Anzeige der Timeline (`_aggregate_day`, `_fmt_glance`, `_fmt_gewitter`,
  `_fmt_timeline`, `_timeline_buttons` bekommen `tz` als Pflichtparameter).

- **Versandpfade von Trip-Briefing und Ortsvergleich** (#1727 S5b): neun Fundstellen, die
  auf tatsächlich VERSENDETE Inhalte wirken und in dieser Liste bis dahin gar nicht standen
  (vierte unvollständige Aufzählung dieses Epics). `select_test_stage`,
  `_send_trip_report_outcome`s Klemm-Vergleich, `_clamp_segments_to_today`,
  `_build_stage_trend` und `_collect_future_stage_weather` folgen seither
  `trip_local_today(trip, now_utc)`; `briefing_target_day_is_current` hat keinen
  Systemuhr-Rückfall mehr (`today` ist Pflicht und kommt als Ortstag der Tour vom
  Aufrufer); `_auto_pause_expired_presets` und der Einzelversand-Zweig von
  `send_one_compare_preset` rechnen über `first_resolvable_tz(locations)` im Ortstag des
  ersten auflösbaren Preset-Orts; `_target_date_from_report` leitet den Präfix-Tag aus der
  am DTO bereits aufgelösten `request.trip_tz` ab. An sechs der neun Stellen ist „jetzt"
  zugleich Pflichtparameter geworden (ADR-0051 Regel 3) — der Briefing-Aufbau steht damit
  auf EINER Zeitabfrage, obwohl zwischen ihr und dem Ausblick ein Wetterabruf mit
  Retry-Backoff liegt. An den Fundstellen `_send_trip_report_outcome`,
  `_target_date_from_report` und `send_one_compare_preset` bleibt die Auflösung bewusst
  funktionsintern (jeweils vor jedem Netzabruf).
- **Vorschau-, Anzeige- und Sofort-Vergleichspfade** (#1727 S5c): sieben Fundstellen in fünf
  Dateien. Die Trip-Vorschau (`preview_service.py`) — `_resolve_target_date` UND
  `_build_report` — folgt seither `trip_local_today(trip, now_utc)`; EIN von den drei
  öffentlichen `render_*_preview`-Methoden einmal gebundenes `now_utc` speist beide Aufrufe,
  die zuvor bei `_build_report` separat aufgelöste zweite Systemuhr entfällt ersatzlos. Die
  Compare-Vorschau (`compare_preview_service.py::_resolve_target_date`) und der
  Sofort-Vergleich (`api/routers/compare.py::run_comparison`, alle drei Funde im selben
  Commit — Stunde UND Zieltag „heute"/„morgen" aus DERSELBEN Auflösung) folgen
  `first_resolvable_tz(locations)`, demselben Muster wie der Compare-Versand seit S5b. Der
  Mail-Footer „Nächster Versand" (`compare_html.py::_compute_next_send`) übernimmt das in
  `render_compare_html` bereits aufgelöste `header_tz`, statt selbst ein zweites Mal
  aufzulösen. Die siebte Fundstelle, `comparison_engine.py::dict_to_comparison_result`,
  wurde NICHT korrigiert, sondern als toter Code (0 Aufrufer im gesamten Repo) ersatzlos
  entfernt.

**Lehre für die Pflege dieser Liste:** Sie war nicht falsch, sondern **unvollständig** — und
eine unvollständige Restliste liest sich wie eine vollständige. Wer hier etwas einträgt,
sucht vorher nach `date.today()`/`datetime.now().date()` im ganzen Produktivcode, statt nur
die Datei zu nennen, in der er gerade gearbeitet hat.

### Noch nicht umgesetzt (Stand 2026-08-14)

Der zuvor hier gelistete Briefing-/Versand-Pfad (`_get_target_date`, `_get_active_trips`,
`save_dated`) ist umgesetzt — s. „Umgesetzt" oben (#1724/#1725). Ebenso der zuvor hier
gelistete Kommando-/Anzeige-Pfad — s. „Umgesetzt" oben (#1727 S5a/#1795) und die neun
Versandpfade aus #1727 S5b.

`preview_service._resolve_target_date` (samt `_build_report`) ist mit #1727 S5c erledigt und
nach „Umgesetzt" oben gewandert. `tools/weather_validation.py` ist damit ebenfalls KEINE
offene Arbeit mehr — s. „Bewusst NICHT betroffen" unten, wo die begründete Ausnahme steht.

**Fünfte unvollständige Aufzählung dieses Epics:** `compare_preview_service._resolve_target_date`
fehlte in dieser Restliste vollständig, obwohl der Wächter
(`tests/test_output_timezone_guard.py::KNOWN_VIOLATIONS`) sie bereits als offenen Fund
führte — weder oben noch unten stand sie je drin. Mit #1727 S5c ist sie behoben (s.
„Umgesetzt" oben); hier ausdrücklich als das benannt, was sie war, statt sie stillschweigend
als „schon immer bekannt" durchgehen zu lassen.

**S5d — vier Dateien, sieben verbleibende Muster-A-Funde (Wächter-Restliste, nachgezählt am
Stand nach S5c):**

- `api/routers/debug.py` — `trigger_radar_alert` (1): Debug-Auslöser für Radar-Alarme datiert
  weiterhin auf die Serveruhr.
- `src/services/gpx_processing.py` — `compute_default_start_date` (2), `gpx_to_stage_data`
  (1).
- `src/services/official_alerts/massif_closure.py` — `_do_request`, `fetch` (2).
- `src/services/official_alerts/meteo_forets.py` — `covers` (1).

**Sechste unvollständige Aufzählung dieses Epics:** die drei letztgenannten Dateien
(`gpx_processing.py`, `massif_closure.py`, `meteo_forets.py`) standen bis zu dieser Scheibe in
KEINEM Abschnitt dieses ADR — weder oben noch unten —, obwohl der Wächter
(`tests/test_output_timezone_guard.py::KNOWN_VIOLATIONS`) sie durchgehend als offene Funde
führte. Nur `api/routers/debug.py` war hier bislang erwähnt. Hier ausdrücklich als das
benannt, was sie waren, statt sie stillschweigend unter „bleibt offen" mitzumeinen. Nach S5d
ist die Muster-A-Liste des Wächters vollständig leer; offen bleiben dann nur noch
`raw_astimezone`-Funde, die dritte Fundart des Wächters (stille Mid-Body-Rückfälle, per
`BoolOp`/`getattr`/`If`/`IfExp` erkannt) sowie die vom Wächter nicht gescannten Bereiche
(S5e).

**Bewusst NICHT betroffen** (feste Zone ist dort Absicht, kein Verstoß):
`forecast_budget._today_utc` und `meteoalarm_budget._today_utc` (Kontingent-Tageswechsel in
UTC) sowie der manuelle `?hour=`-Testauslöser des Versand-Orchestrators
(`CompareDispatchStrategy.MANUAL_TRIGGER_REFERENCE_ZONE`) — ein Ops-/Debug-Werkzeug ohne
Preset-Bezug, für das „Stunde X" bei preset-eigenen Zonen keine EINE Bedeutung mehr hätte.
Seit #1727 S5c außerdem `tools/weather_validation.py`s Punkt-Validierungsmodus (`:288`,
begründet über einen `# gz-main-path:`-Kommentar an der Zeile): das Werkzeug fragt seine
Referenzdaten selbst ausdrücklich mit `"timezone": "UTC"` ab (`fetch_openmeteo`, `:31`) — ein
Ortstag-Default erzeugte einen Widerspruch INNERHALB desselben Skripts (Validierungsziel UTC,
Validierungs-Default Ortszeit).

Die beiden Alarm-Module, die bis 2026-08-12 an dieser Stelle als bewusste Ausnahme standen
(Ruhezeit-Engine und Tageszähler, fest `Europe/Vienna`), sind **keine Ausnahme mehr** — sie
folgen seit #1726 der Ortszone, s. „Umgesetzt" oben. Ebenso die Slot-Stunde des
Ortsvergleichs, die dort ebenfalls gelistet war.

Vollständige Fundstellen-Karte nach Wirkung sortiert:
`docs/context/fix-1697-ortstag-statt-servertag.md`.

Sie sind bewusst ausgegrenzt, nicht vergessen. Wer sie anfasst, richtet sich nach diesem ADR.

## Alternativen, die verworfen wurden

**Alles bei Weltzeit lassen.** Konsistent und sommerzeit-immun — aber für den Nutzer
falsch: Wer um 00:30 Ortszeit „heute" fragt, meint seinen Tag, nicht den in Greenwich.

**Die Zone aus der ersten Etappe der Tour nehmen.** War die erste Fassung von #1470. Bei
einer Tour Neuseeland → Korsika zehn Stunden daneben; die Etappe des Weltzeit-Tages liegt
höchstens einen Tag daneben und trifft praktisch immer die richtige.

**Die Zone aus der Nutzer-Einstellung nehmen.** Es gibt keine solche Einstellung, und sie
wäre falsch: Der Wanderer ist unterwegs, nicht zu Hause.
