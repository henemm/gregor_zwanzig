# Context: fix-1744-a-alarm-format

Issue #1744, Scheibe A. Scheibe B (quellenübergreifende Entdopplung) ist an #1467 S4 gebucht
und **nicht** Gegenstand dieses Workflows.

## Request Summary

Zwei Alarm-Mails zum selben Ereignis sehen für den Nutzer völlig unterschiedlich aus. Der
Ortsbezug wird in zwei verschiedenen Vokabularen ausgedrückt — `km 8–8` (Radar-Nowcast) gegen
`🏁 Ziel` (amtliche Warnung) — sodass nicht erkennbar ist, ob derselbe Ort gemeint ist. Das
Format soll angeglichen werden.

## Der Rahmen ist bereits gemeinsam — nur ein Feld weicht ab

Beide Betreffzeilen haben dieselbe Bauform `[Trip] <Ort> · <Kern>`:

    [KHW 403] km 8–8 · Gewitter in 8 Min          (Radar-Nowcast)
    [KHW 403] 🏁 Ziel · GELB Gewitter (Di)        (amtliche Warnung)

Die Aufgabe ist damit keine Neukonstruktion, sondern eine **Entscheidung über den Ortsslot**.

## Zwei Betreff-Bauer, nicht mehr

| Funktion | Datei:Zeile | Deckt ab |
|---|---|---|
| `render_subject()` (+ `_render_subject_onset()` `render.py:142`) | `src/output/renderers/alert/render.py:294-325` | Trip-Δ, Vergleich-Δ, Trip-Nowcast, Vergleich-Nowcast |
| `render_official_alert_subject()` | `src/output/renderers/alert/official_alerts.py:859-919` | amtliche Warnung, Trip **und** Vergleich (eine Funktion, `scope_kind="route"\|"locations"`) |

(`output/subject.py::build_email_subject` ist ein dritter Bauer, aber nur für die
Briefing-Mail — kein Alarm-Pfad.)

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py:100-111` | `_km_str`, `_km_str_onset` — Quelle des `km {a}–{b}`-Formats |
| `src/output/renderers/alert/render.py:294-325` | `render_subject` — Betreff Δ/Onset/Korridor |
| `src/output/renderers/alert/render.py:361-388` | E-Mail-Datenblock „Wo & wann" |
| `src/output/renderers/alert/render.py:551-584` | `render_telegram` (Kopfzeile mit km) |
| `src/output/renderers/alert/render.py:619-687` | `render_sms` — Kurzform, **Grenze 140 Zeichen** |
| `src/output/renderers/alert/official_alerts.py:264-291` | `format_segment_reference` — Quelle von `Segment 3–5` / `🏁 Ziel` / `N Segmente` |
| `src/output/renderers/alert/official_alerts.py:834-919` | `_scope_display`, `render_official_alert_subject` |
| `src/output/renderers/alert/official_alerts.py:1936-1995` | `build_official_alert_notices` — baut `scope_label` und `sms_scope` |
| `src/output/renderers/alert/model.py:20-80` | `AlertEvent`/`OnsetEvent`/`CorridorEvent`/`AlertMessage` — Ortsfelder |
| `src/output/renderers/alert/project.py:96-221, 300-315` | Projektion Domäne → Renderer-Modell; setzt `location_label` |
| `src/services/trip_segments.py:299-320` | erzeugt `segment_id="Ziel"` |
| `src/app/models.py:386-401` | `TripSegment` — trägt `segment_id`, **keinen Namen** |

## Der entscheidende Befund: das Δ/Onset-Modell kennt keine Segmente

| Dataclass | Ortsfelder | Segment-Kennung? | Sprechender Name? |
|---|---|---|---|
| `AlertEvent` (`model.py:20-27`) | `km_from`, `km_to`, `location_label` | **nein** | nur `location_label`, und das setzt der Trip-Pfad **nie** |
| `OnsetEvent` (`model.py:31-45`) | dito | **nein** | dito |
| `CorridorEvent` (`model.py:49-61`) | dito | **nein** | `location_label` wird **nirgends** gesetzt |
| `OfficialAlertNotice` | `scope_label`, `affected_chips`, `sms_scope` | **ja** (aus rohen `segment_id`) | — |

`"🏁 Ziel"` ist damit **keine Ortsnamens-Auflösung**, sondern das Rendering des literalen
Strings `segment_id="Ziel"` durch `format_segment_reference`. Der Δ/Onset-Pfad sieht das
Ziel-Segment ausschließlich als km-Wert (`km_from == km_to == cumulative_dist_km`), weil die
Segment-Zuordnung dort nur über `distance_from_start_km` läuft.

**Ein sprechender Ortsname ist für Trip-Segmente heute nicht verlässlich verfügbar:**
`TripSegment` hat kein Namensfeld; erreichbar wäre nur `TripSegment.waypoint.name`
(`DetectedWaypoint.name`, `app/models.py:375`) — optional und nur gesetzt, wenn in der Nähe ein
benannter GPX-Wegpunkt liegt.

**Der Ortsvergleich ist bereits konsistent:** dort sprechen beide Alarmarten in Ortsnamen
(`location_label` bzw. `"alle Orte"`/`"nur Toulon"`). Uneinheitlich ist allein der **Trip**-Pfad.

## Existing Patterns

- **`format_segment_reference()`** (`official_alerts.py:264-291`) ist die einzige bestehende
  gemeinsame Ortsformatierung: Range-Verdichtung (`Segment 3–5`), Aufzählung (`Segment 3, 5`),
  Ziel-Sonderfall (`🏁 Ziel`), Verdichtung ab >4 Segmenten (`N Segmente`).
- **Additive optionale Ortsfelder** sind das etablierte Erweiterungsmuster: `location_label`
  wurde in #1169/#1170/#1041 genau so eingeführt — neues Feld mit Default `None`, Trip-Pfad
  setzt es nicht, Regressions-Invariante per Golden-Test abgesichert.

## Existing Specs & ADRs

| Dokument | Was es festlegt |
|---|---|
| `docs/specs/modules/warnmail_official_alert_display.md` AC-3 (#1248) | Betreff nennt bei **gemischtem** Umfang eine ehrliche Sammelangabe („mehrere Segmente"), nie ein führendes Einzelsegment |
| `docs/adr/0033-warn-karte-nur-betroffene-segmente.md` | Warn-Karte nennt ausschließlich den betroffenen Umfang; `free_chips` im Trip-Pfad fest `[]` |
| `docs/adr/0042-namensform-folgt-der-platzgrenze.md` | Namensklassen für **Metrik**-Labels (nicht für Ortsangaben) |
| `docs/specs/modules/sms_official_alert_tokens.md` | SMS-Kurzform amtlicher Warnungen inkl. `sms_scope` |
| PO-Entscheid 2026-08-04 (`e9f23605`, #1467 S2 AG3b) | **Alarm-Kurznachrichten nennen keinen Ort** — die Positionszahl ist die Ortsangabe |

## Risks & Considerations

1. **Die Kurzform ist ausgenommen.** Ein Ortsname in der SMS würde den PO-Entscheid vom
   2026-08-04 rückgängig machen. Scheibe A betrifft E-Mail, Telegram-Langform und Betreff.
2. **Zeichengrenze ist 140, nicht 160.** Alle drei Alarm-SMS-Renderer sind auf `limit: int = 140`
   verdrahtet (`render.py:285`, `render.py:621`, `official_alerts.py:1836`). Die 160 gilt nur für
   die Briefing-SMS.
3. **ADR-0033 und AC-3 dürfen nicht still fallen.** Würde die amtliche Warnung auf km-Spannen
   umgestellt, kollidiert das mit der Sammelangabe-Regel bei gemischtem Umfang. Abweichung ⇒
   neues ADR, nie stille Rücknahme.
4. **Der Korridor-Renderer ist toter Code — nicht mit angleichen.** `evaluate_corridor_thresholds()`
   (`src/services/corridor_threshold.py:68`) hat **keinen** Aufrufer in `src/`/`api/`; der Auslöser
   wurde am 2026-08-03 in `8f2053f9` (#1460 P1a) bewusst abgelöst („löst #1444 S1 ab", absolute
   Grenzen standen quer zu ADR-0009/ADR-0013). `corridor_hits` bleibt im Produktivlauf immer leer.
   Ein Angleichen dieses Pfades wäre Blindleistung und würde eine Fähigkeit suggerieren, die es
   nicht gibt.
5. **Renderer-Commit-Gate greift.** Jede Änderung an `src/output/renderers/alert/*.py` blockiert
   den Commit, bis `tests/tdd/test_issue_811_mode_matrix.py` grün ist und ein
   `briefing_mail_validator.py`-Lauf bestanden hat.
6. **Golden-Tests sichern die heutigen Betreffe byte-genau.** Jede Formatänderung zieht mindestens
   nach: `tests/tdd/test_issue_1169_compare_alert_consumer.py:709`,
   `tests/tdd/test_issue_917_alert_renderer.py:205`,
   `tests/tdd/test_issue_919_radar_alert_canonical.py:69`,
   `tests/tdd/test_official_alert_subject_compact.py:126`.
7. **Trip/Vergleich-Teilungsregel.** Die Angleichung muss auf **eine** gemeinsame
   Ortsformatierung hinauslaufen, nicht auf zwei gepflegte Zweitfassungen.

## Nebenbefunde (getrennt gebucht, nicht Teil dieses Workflows)

- **Mehrort-Nowcast verliert in Kurzform alle Orte außer dem ersten.**
  `_render_sms_onset` (`render.py:285-291`) und `_render_telegram_onset` (`render.py:276-282`)
  lesen ausschließlich `msg.events[0]`, obwohl `to_multi_location_onset_alert_message`
  (`project.py:300-315`) N Ereignisse baut. Bewusster Scope-Schnitt aus #1041 Slice 1a, seither
  ohne Nachzug und ohne Test. → eigenes Issue.
- **Toter Korridor-Render-Pfad** (Modell, Projektion, vier Renderer, eigener Betreff-Zweig).
  → Sammel-Eintrag #1199.
