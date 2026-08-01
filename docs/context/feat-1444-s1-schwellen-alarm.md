# Context: feat-1444-s1-schwellen-alarm

Issue #1444, Scheibe 1. Erstellt 2026-08-01.

## Request Summary

Reisst die Vorhersage im Etappenfenster eine vom Nutzer eingestellte Grenze
(Wertebereich mit `notify: true`), soll genau eine Sofort-Meldung ueber die
konfigurierten Alarm-Kanaele rausgehen — **unabhaengig davon, ob sich die
Vorhersage geaendert hat**. Heute existiert nur der Aenderungs-Waechter (Delta),
der bei konstant hoher Gefahr strukturell stumm bleibt.

Scheibe 1 = der Alarm entsteht und wird zugestellt, entprellt, nachgewiesen an
Gewitter und Regen. Editor-Text (S2) und Breite ueber alle Groessen (S3) folgen.

## Ausgangslage: was es schon gibt

Das Ticket sagt „das Vorhandene endlich wirksam machen". Die Bestandsaufnahme
bestaetigt das — **vier von fuenf Bausteinen existieren**, es fehlt der Dienst,
der sie zur Alarmzeit zusammenfuehrt.

| Baustein | Wo | Zustand |
|---|---|---|
| Konfiguration `corridors[]` mit `notify` | `src/app/models.py:876` (`Corridor`), `loader.py:231/1509`, `internal/model/trip.go:114` | vollstaendig persistiert, Round-Trip Python+Go |
| Vergleich Wert ↔ Grenze | `src/services/corridor_match.py:17` (`corridor_inside`) | fertig, heute nur fuer die Mail-Markierung genutzt |
| Metrik → Aggregat-Feld | `src/services/weather_change_detection.py:38` (`_ALERT_METRIC_TO_SUMMARY_FIELD`) | fertig, deckt alle 5 im Feld benutzten Groessen |
| Versandweg | `trip_alert.py:923` `_send_alert` → `NotificationService.send_deviation_alert` | fertig, nimmt eine `WeatherChange`-Liste entgegen |
| **Auswertung Korridor zur Alarmzeit** | — | **existiert nicht** (Kern dieser Scheibe) |

### Echte Daten (Beleg, nicht Vermutung)

Der ausloesende Trip „KHW 403" (`data/users/henning/briefings/5f534011.json`,
gelesen als `claude-gregor`) traegt genau die im Ticket beschriebenen Bereiche —
im **AlertMetric-Vokabular**, nicht im Katalog-Vokabular:

```
wind_gust         [null, 20]   notify=true
precipitation_sum [null,  1]   notify=true
temperature_min   [   5, null] notify=true
temperature_max   [null,  5]   notify=true
thunder_level     [null,  0]   notify=true
alert_cooldown_minutes: 30
```

Zwei Folgerungen:

1. **Kein Namensraum-Umbau noetig.** `corridor.metric` traegt im Trip-Kontext
   dieselben Bezeichner wie `_ALERT_METRIC_TO_SUMMARY_FIELD` — der Weg vom
   Korridor zum Ist-Wert ist eine einzige Nachschlage-Operation. (Der bekannte
   Mismatch aus #1257 betrifft die *Katalog*-IDs, nicht diesen Pfad.)
2. **`temperature_max ≤ 5 °C` ist im Alpen-Hochsommer dauerhaft gerissen.** Die
   Entprellung ist damit kein Randfall, sondern die Bedingung dafuer, dass die
   Funktion ueberhaupt zumutbar ist. Ein naiver Bau erzeugt auf diesem realen
   Trip Dauerfeuer.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py` | Alarm-Lauf (`check_all_trips:298`), Einzelpruefung (`check_and_send_alerts:124`), Versand (`_send_alert:923`), Kanalwahl (`_effective_alert_channels:1086`) |
| `src/services/deviation_alert_engine.py` | Auswertungskern (Ruhezeit, Detektor-Wahl, Delta-Erkennung, Melde-Gedaechtnis-Filter, Severity) — location-generisch, kennt keinen Trip |
| `src/services/weather_change_detection.py` | `_ALERT_METRIC_TO_SUMMARY_FIELD:38`, `_ALERT_METRIC_COMPARISON:168`, **`_detect_absolute_changes:640`** (s.u.) |
| `src/services/corridor_match.py` | `corridor_inside()` — die Vergleichsregel, inkl. „Grenzwert selbst zaehlt als drin" |
| `src/services/alert_state.py` | Melde-Gedaechtnis je Trip (`AlertStateService.load/save`) |
| `src/app/models.py` | `Corridor:876`, `AlertMetric:828`, `WeatherChange:448`, `AlertRule:852` |
| `src/output/renderers/alert/project.py` | `WeatherChange` → `AlertMessage`; **`_resolve_metric_id(field, direction):16`** erwartet `increase`/`decrease` |
| `src/output/renderers/email/html.py:579` | `build_trip_corridor_id_map()` — wie die Mail-Markierung Korridore heute aufloest (Vorbild + Ausschlussregeln) |

## Existing Patterns

- **Auswertung ist von Trip-Wissen getrennt.** `DeviationAlertEngine.evaluate()`
  nimmt Wetterpunkte + `AlertEvaluationConfig` + Melde-Gedaechtnis und gibt ein
  `EvaluationResult` zurueck; `TripAlertService` ist nur noch Adapter (#1168).
  Eine Schwellen-Auswertung gehoert nach demselben Muster dorthin, nicht als
  Sonderzweig in den Adapter.
- **Melde-Gedaechtnis statt reinem Zeit-Throttle.** `alert_state` merkt je
  `metrik:etappe` den zuletzt gemeldeten Wert; gemeldet wird erst wieder, wenn
  sich der Wert um mindestens den Schwellwert bewegt hat
  (`_filter_against_alert_state:191`). Genau dieses Muster traegt AC-3
  („unveraenderte Lage → kein zweiter Alert, Verschaerfung darf melden").
- **Gewitter ist ordinal.** Werte sind Enum-Instanzen; `thunder_ordinal()`
  (`output/metric_format.py`) ist die kanonische Ordnungsquelle. Jeder
  Zahlenvergleich muss vorher dadurch.
- **Fail-soft im Lauf.** Jeder Trip ist in `try/except` gekapselt; ein Fehler
  darf den Lauf fuer andere Touren nicht abbrechen.

## Dependencies

- **Upstream:** `WeatherSnapshotService` (Vorhersage-Schnappschuss),
  `load_all_trips`, `thunder_ordinal`, `corridor_inside`.
- **Downstream:** `NotificationService.send_deviation_alert` → Alarm-Renderer
  (`src/output/renderers/alert/*`) → E-Mail/Telegram/SMS. Beruehrung mit dem
  **Renderer-Commit-Gate #811**, sobald Renderer-Dateien angefasst werden.
- **Nachbarn:** `alert_daily_limit` (Tages-Obergrenze je Nutzer),
  `_throttle_store` (Zeit-Cooldown je Trip), Ruhezeiten.

## Existing Specs

- `docs/specs/modules/trip_alert.md` — Alarm-Dienst
- `docs/specs/modules/issue_1231_korridor_editor.md` — Wertebereiche, `notify`/`mark`
- `docs/specs/modules/fix_1425_s2_corridor_pool.md` — Groessen-Pool + entferntes Sofort-Meldungs-Versprechen (S2c)
- `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md` — `alarmCapable` im Register
- `docs/specs/modules/alert_render_foundation.md` — Projektion und Darstellung
- `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md` — Zeitgrenze des Laufs (frisch live)

## Risks & Considerations

### R1 — Zwei Sperren im Lauf verschlucken den neuen Alarm, bevor er entsteht

`check_all_trips` ueberspringt eine Tour vollstaendig, wenn

- `if not cached: continue` (`trip_alert.py:377`) — ohne Morgen-Schnappschuss
  gibt es keinen Alarm. Fuer einen Schwellen-Alarm ist der Vergleichsstand aber
  **irrelevant**: er braucht nur die frische Vorhersage.
- `has_active_rules` nur Delta-Quellen zaehlt (`:342-355`) — eine Tour, die
  **ausschliesslich** Wertebereiche gesetzt hat, gilt heute als „keine aktive
  Alarmquelle" und wird nie geprueft.

Beides muss die Spec ausdruecklich adressieren, sonst ist die Funktion auf dem
Papier fertig und im Feld weiterhin stumm — exakt der Fehler aus #1425 S2c.

### R2 — Ein abgeschalteter Absolut-Pfad existiert bereits

`WeatherChangeDetectionService._detect_absolute_changes():640` wertet
`AlertRule(kind="absolute")` gegen einen festen Schwellwert aus — inklusive
Gewitter-Sonderregel (`>=` statt `>`, #222 F003). Im Alarm-Lauf ist er seit
**#816 ausdruecklich abgeschaltet** (`include_absolute=False`,
`deviation_alert_engine.py:179`).

Das ist die zentrale Analyse-Frage: **diesen Pfad aus den Korridoren speisen und
wieder einschalten**, oder daneben eine eigene Korridor-Auswertung stellen? Fuer
den Bestandspfad spricht Wiederverwendung; dagegen sprechen (a) der unbekannte
Grund der Abschaltung in #816 — muss vor der Spec geklaert werden, sonst
reaktivieren wir einen bewusst stillgelegten Laermerzeuger, (b) eine `AlertRule`
kennt **eine** Grenze und **eine** Richtung, ein Korridor hat **zwei** und ist
einseitig offen (`[null, 20]`).

### R3 — Die Projektion in die Meldung kennt nur „gestiegen/gefallen"

`alert/project.py:_resolve_metric_id(field, direction)` erwartet
`increase`/`decrease` und wirft bei mehrdeutigen Feldern sonst `ValueError`. Der
bestehende Absolut-Pfad setzt stattdessen `direction="above"/"below"` und
`old_value=0.0` — auf `temp_min_c` (mehrdeutig: `temperature` vs.
`temperature_cold`) laeuft das in den definierten Fehler. Ein Schwellen-Treffer
hat zudem fachlich **kein** „vorher": die Meldung muss „Grenze X gerissen,
aktuell Y" sagen, nicht „von 0 auf Y gestiegen". Wie der Treffer bis in den
Meldungstext transportiert wird, ist Spec-pflichtig.

### R4 — Dauerfeuer-Risiko ist real, nicht theoretisch

Siehe `temperature_max ≤ 5 °C` oben. Zeit-Cooldown (30 min) allein genuegt
nicht: er wuerde alle 30 Minuten eine Meldung erlauben. Es braucht das
wertbasierte Melde-Gedaechtnis, mit einer definierten Antwort auf „was ist eine
Verschaerfung?" — bei Gewitter die naechste Stufe, bei Regen/Boeen ein
Zahlenabstand.

### R5 — Zwei Alarmarten in einem Lauf

Feuern Aenderungs- und Schwellen-Waechter gleichzeitig, darf daraus **eine**
Nachricht werden (Muster #1088: amtliche Warnungen werden in dieselbe Nachricht
gebuendelt), nicht zwei Zustellungen kurz hintereinander. Ebenso muss geklaert
sein, wie beide auf denselben Zeit-Cooldown und dieselbe Tages-Obergrenze
wirken.

### R6 — Nicht jede Groesse ist vergleichbar

`build_trip_corridor_id_map()` schliesst strukturell aus: `aggregation == "sum"`
(Tages-Summen gegen Stundenwerte waere fachlich falsch) und `kind == "enum"`
(`corridor_inside` wirft `TypeError` auf Enum-Werte). Fuer die Alarmauswertung
gilt derselbe Vorbehalt — hier allerdings auf **Aggregat**-Ebene, wo
`precipitation_sum` sehr wohl der richtige Vergleich ist. Die Auswahl der
zulaessigen Groessen muss eigenstaendig hergeleitet werden, nicht aus der
Mail-Markierung kopiert.

## Analysis

### Type

Feature (Funktionsluecke — die Konfigurationsflaeche existiert und wird von
keinem Dienst gelesen).

### Der zentrale Befund: #1444 beruehrt eine dokumentierte Grundsatzentscheidung

Die vier offenen Fragen sind beantwortet; die erste hat die Analyse verschoben.

**ADR-0009 „Alerts sind Abweichungs-Waechter, keine absoluten Schwellen"
(Status: Akzeptiert, 2026-06-16)** verwirft absolute Schwellen ausdruecklich —
woertlich: *„feuert bei bereits bekanntem Schlechtwetter → Alarm-Muedigkeit"*.
Der Absolut-Pfad wurde deshalb in #816 nicht kaputtgemacht, sondern **bewusst
stillgelegt**.

**ADR-0013** nennt denselben Pfad als Known Limitation und formuliert die
Vorbedingung, unter der er zurueckkehren darf:

> `_detect_absolute_changes()` setzt `old_value=0.0` und ist mit dieser Semantik
> inkompatibel — im Versandpfad seit #816 tot. **Vor einer Reaktivierung von
> Absolut-Regeln muss dieser Pfad einen eigenen Render-Vertrag bekommen.**

Der reale Befund aus 6 Wochen KHW 403 ist die Gegenerfahrung zur Annahme von
ADR-0009: Bei **konstant** hoher Gefahr (Alpen-Hochsommer, taeglich Gewitter)
ist der Abweichungs-Waechter strukturell stumm — und Stille bei bekannter Gefahr
ist gefaehrlicher als Laerm. Beide Beobachtungen sind richtig; sie widersprechen
sich nicht, sondern beschreiben zwei verschiedene Lagen.

**Empfehlung:** Kein Rueckbau von ADR-0009, sondern ein **zweiter, additiver
Alarm-Typ** — Vorbild ADR-0016 (amtliche Warnungen als additiver externer
Typ). Der Abweichungs-Waechter bleibt unveraendert das Default-Verhalten; der
Schwellen-Waechter feuert nur, wo der Nutzer selbst eine Grenze gesetzt hat
(`notify: true`), und bekommt — wie von ADR-0013 gefordert — einen **eigenen
Render-Vertrag** statt `WeatherChange` mit `old_value=0.0` zu missbrauchen.
Das erfordert ein neues ADR; es gehoert in die Spec-Freigabe.

### Antworten auf die uebrigen Fragen

**F2 — „Etappe im aktiven Zeitfenster" ist bereits definiert** und braucht keine
neue Regel: `_fetch_fresh_weather():891-895` behandelt genau die Etappen, die
noch nicht vorbei sind (`end_time >= jetzt`) und heute oder frueher beginnen
(`start_time.date() <= heute`). Dieselbe Menge ist die richtige fuer den
Schwellen-Alarm.

**F3 — Ort der Auswertung:** eigener, reiner Baustein neben der
`DeviationAlertEngine`, kein Sonderzweig im `TripAlertService`. Begruendung:
ADR-0021 (geteilte Engine fuer Trip und Compare) und die Absicht, denselben
Waechter spaeter fuer den Ortsvergleich zu nutzen. Der Baustein bekommt
Wetterpunkte + Korridore herein und gibt Treffer heraus — kein Trip-Wissen,
kein Versand.

**F4 — „Verschaerfung":** ordinal (Gewitter) = naechsthoehere Stufe; stetig
(Regen, Boeen, Temperatur) = der Wert entfernt sich von der Grenze um
mindestens die im Katalog hinterlegte Aenderungs-Empfindlichkeit
(`MetricDefinition.default_change_threshold`, z.B. Boeen 20 km/h). Damit
entsteht keine neue Konfigurationsflaeche — die Zahl existiert bereits.

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/services/corridor_threshold.py` | CREATE | Reiner Auswertungs-Baustein: Korridore + Wetterpunkte → Treffer (Metrik, Wert, Grenze, Etappe, Zeit). Nutzt `corridor_inside` und `thunder_ordinal`. |
| `src/services/trip_alert.py` | MODIFY | Baustein im Lauf aufrufen; die beiden Sperren aus R1 oeffnen (Korridore mit `notify` zaehlen als aktive Alarmquelle; fehlender Schnappschuss verhindert den Schwellen-Alarm nicht). |
| `src/services/alert_state.py` | MODIFY | Melde-Gedaechtnis um den Schwellen-Zweig erweitern (eigener Schluesselraum, damit der Delta-Zweig unberuehrt bleibt). |
| `src/output/renderers/alert/model.py` + `project.py` | MODIFY | Eigener Render-Vertrag fuer den Schwellen-Treffer (ADR-0013-Pflicht): „Grenze X gerissen, aktuell Y" statt „von A auf B". **Loest das Renderer-Commit-Gate #811 aus.** |
| `tests/tdd/test_corridor_threshold_alert.py` | CREATE | Verhaltenstests zu den ACs (Namensregel: nach Verhalten, nicht nach Issue-Nummer). |
| `docs/adr/00XX-schwellen-alarm-additiver-typ.md` | CREATE | Neues ADR + Index-Eintrag (Drift-Test `test_adr_index_drift.py`). |

### Scope Assessment

- Dateien: 6 (2 neu, 4 geaendert) + ADR
- Geschaetzte LoC: **+280 / −20** (Kern ~120, Renderer-Vertrag ~60, Tests ~120)
- Risiko: **HIGH** — Versandpfad, alle Nutzer, Dauerfeuer-Potenzial (R4)

**Hinweis zum Groessenlimit:** 250 LoC pro Arbeitsgang wird voraussichtlich
knapp ueberschritten. Wenn es soweit ist, frage ich einmal nach der Freigabe —
kein stiller Override.

### Technical Approach

1. **Auswertung** (`corridor_threshold.py`): je Etappe im aktiven Fenster und je
   Korridor mit `notify=true` den Aggregatwert ueber
   `_ALERT_METRIC_TO_SUMMARY_FIELD` holen, Enum-Werte ueber `thunder_ordinal`
   normalisieren, mit `corridor_inside(wert, min, max)` pruefen. `False` = Grenze
   gerissen → Treffer mit Metrik, Ist-Wert, gerissener Grenze, Richtung, Etappe,
   Zeitpunkt.
2. **Entprellung**: Treffer gegen das Melde-Gedaechtnis filtern (eigener
   Schluesselraum `corridor:<metrik>:<etappe>`). Neu → melden. Bekannt und nicht
   verschaerft → schweigen. Verschaerft nach F4 → erneut melden. Lage vorbei →
   Eintrag raeumen, damit ein spaeterer Rueckfall wieder melden darf.
3. **Buendelung**: Treffer und Delta-Aenderungen desselben Laufs gehen in **eine**
   Nachricht (Muster #1088), teilen Zeit-Cooldown, Ruhezeiten und Tages-Obergrenze.
4. **Darstellung**: eigener Ereignistyp im Alert-Renderer mit eigenem Wortlaut.

### Open Questions (fuer die Spec-Freigabe)

- [x] Grund der #816-Abschaltung — geklaert (ADR-0009/0013, s.o.)
- [x] Definition des Etappenfensters — geklaert (Bestandsregel)
- [x] Ort der Auswertung — geklaert (eigener Baustein)
- [x] Definition „Verschaerfung" — geklaert (ordinal/stetig, Katalogwert)
- [ ] **PO-Entscheidung:** additiver zweiter Alarm-Typ neben ADR-0009 (Empfehlung)
      — wird mit den Akzeptanzkriterien vorgelegt
