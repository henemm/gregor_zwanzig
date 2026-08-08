# Context: fix-1584c-compare-zeitfenster

Workflow: `fix-1584c-compare-zeitfenster` · Issue #1584, Folge-Scheibe C · Track: Full Process
Branch-Basis: `origin/main` @ `963e673e` · erstellt 2026-08-08

## Request Summary

#1584 (Alarme schalten 2 h nach Ankunft ab) ist im Trip-Pfad behoben und seit
2026-08-08 06:56 UTC in Produktion. Offen ist die dort ausgeklammerte Frage:
**Hat der Ortsvergleich dieselbe Zeitfenster-Bindung — und welchen Zeitbegriff
benutzen seine Alarmwege überhaupt?**

## Gemessener Ausgangsbefund (nicht aus dem Ticket abgelesen)

### Das #1584-Fehlerbild existiert im Compare-Pfad nicht

Es gibt im Ortsvergleich keine Segment-/Laufzeit-Bindung, an der etwas ablaufen
könnte. Alle drei Alarmwege arbeiten je Ort, nicht je Etappe
(`compare_alert.py:337-364`, `compare_radar_alert.py:85-178`,
`compare_official_alert.py:85-180`). `_SegmentIdShim`
(`deviation_alert_engine.py:45-61`) setzt `segment_id = point.id`, also die
Ortskennung.

### Stattdessen: drei Alarmwege mit drei verschiedenen Zeitbegriffen

| Alarmweg | Datei | Zeitbegriff der **Beobachtung** | Tagesfenster? |
|---|---|---|---|
| Abweichung | `compare_alert.py` | synthetisches 1-Stunden-Segment `now … now+1h` (`compare_location_weather_source.py:38-50`) | **nein** |
| Radar/NowCast | `compare_radar_alert.py` | Regen-Onset ≤ 20 min, inhärent „jetzt" | **nein** |
| Amtliche Warnung | `compare_official_alert.py` | `window_start=now` … `window_end=` Tagesfenster-Ende **in Ortszeit je Ort**, geklemmt auf `now` (`:203-211`, `:237-262`) | **ja** |

Der amtliche Pfad ist damit das einzige Vorbild im Ortsvergleich — und er löst
die Zeitzone bereits ortsgenau über `tz_for_coords(loc.lat, loc.lon)` auf, mit
ausdrücklicher Klemmung, damit der Vergleich „abends nicht taub wird"
(Docstring `:243-248`).

### Gating-Ketten (Reihenfolge, wie ausgewertet)

| # | Abweichung | Radar | Amtlich |
|---|---|---|---|
| 1 | Stilllegung `:127` | Stilllegung `:95` | Stilllegung `:95` |
| 2 | Cooldown `:139` | `radar_alert_enabled` `:101` | `official_*_enabled` `:107-114` |
| 3 | Tageslimit (`reason=forecast_change`) `:146` | Cooldown `:106` | **Ruhezeiten** `:117` |
| 4 | **Ruhezeiten** `:171` | NowCast-Onset `:205` | Neu/eskaliert `:131` |
| 5 | Metrik-Schwelle `:351` | **Ruhezeiten** `:117` | Tageslimit `:136` |
| 6 | Kanal-Opt-in `:403` | Kanal-Opt-in `:133` | Kanal-Opt-in `:141` |
| 7 | Kanal-Schwelle `:210` | Kanal-Schwelle `:146` | Kanal-Schwelle `:151` |

Ruhezeiten liegen in allen drei Ketten **vor** dem Wetterabruf oder unmittelbar
danach — die aus #1584 bekannte Reihenfolgen-Falle (Abbruch **vor** der
Ruhezeiten-Prüfung) gibt es hier nicht.

### Zeitzone: eine harte Kodierung im Alarmpfad

`deviation_alert_engine.py:31,105` rechnet Ruhezeiten fest in `Europe/Vienna`
(`local_now = aware_now.astimezone(VIENNA)`), laut Docstring für „alle sechs
Aufrufer". Gleiches Muster in `alert_daily_limit.py:23` für den Tageszähler.
Der amtliche Compare-Pfad benutzt dagegen Ortszeit — innerhalb desselben
Produkts stehen beide Konventionen nebeneinander.

### Produktivdaten (gemessen, `data/users/*/compare_presets.json`)

5 Ortsvergleiche, alle bei Nutzer `henning`:

| Vergleich | Orte | Ruhezeiten | Tagesfenster | Radar | Amtlich |
|---|---|---|---|---|---|
| Zillertal täglich | 5 | — | — | — | — |
| Mallorca | 2 | — | — | — | — |
| Zillertal | 5 | — | — | — | — |
| Heimat | 4 | — | — | — | — |
| Le Var | 8 | 22:30–06:00 | — | ✅ | ✅ |

- **Kein einziger Vergleich hat ein Tagesfenster gesetzt** → überall Default 4/19.
- Nur *Le Var* hat Alarme überhaupt aktiv (Cooldown 30 min, Telegram, kein SMS).
- Alle Orte liegen derzeit in Zonen mit demselben UTC-Versatz wie Wien
  (AT/ES/DE/FR) — die Vienna-Kodierung **beißt heute nicht**, ist aber latent.
- Die Presets führen noch `hour_from`/`hour_to` (9–16, Le Var 7–22). Diese Felder
  sind **abgekündigt und wirkungslos** (`report_config_resolver.py:196`,
  `scheduler_dispatch_service.py:356`); das Migrations-Script
  `scripts/migrate_1361_drop_compare_hour_from_to.py` ist noch nicht gelaufen.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/compare_alert.py` | Abweichungs-Alarm, ohne Tagesfenster |
| `src/services/compare_radar_alert.py` | Radar/NowCast, ohne Tagesfenster |
| `src/services/compare_official_alert.py:237-262` | **Vorbild**: Tagesfenster in Ortszeit je Ort |
| `src/services/compare_location_weather_source.py:38-50` | baut das 1-Stunden-Fenster des Abweichungs-Alarms |
| `src/services/deviation_alert_engine.py:31,78-137` | Ruhezeiten, hart Europe/Vienna |
| `src/services/weather_change_detection.py:593-594` | vergleicht `old.aggregated` gegen `new.aggregated` |
| `src/output/renderers/day_window.py` | `resolve_configured_window()`, Default 4/19 |
| `src/utils/timezone.py:29-37` | `tz_for_coords()`, Fallback UTC |
| `src/services/trip_segments.py:238-313` | Trip-Pendant nach dem #1584-Fix |
| `src/app/models.py:1081-1085` | ComparePreset-Felder, Kommentar zur `hour_from`-Ablösung |
| `internal/model/compare_preset.go:122-129` | Go-Seite der Tagesfenster-Felder |

## Existing Patterns

- **Ein Auflöser für beide Seiten:** `resolve_configured_window()` liefert nackte
  Stundenzahlen (0–23), Default 4/19, Mitternachts-Wrap seit #1361/#1372 S1b erlaubt.
- **Ortszeit über Koordinaten:** `tz_for_coords()` (timezonefinder, Fallback UTC) —
  benutzt von `trip_segments.py:263` und `compare_official_alert.py:257`.
- **Klemmung statt Rückwärtsfenster:** der amtliche Pfad klemmt auf `now`, statt
  abends ein negatives Fenster zu bilden.

## Dependencies

- **Upstream:** `resolve_configured_window`, `tz_for_coords`, `SegmentWeatherService`,
  `AlertStateService`, `ThrottleStore`, `alert_daily_limit`
- **Downstream:** `NotificationService` → Kanal-Auflösung
  (`compare_alert_channels.py`) → Kanal-Schwelle (`alert_channel_threshold.py`)

## Existing Specs & ADRs

- `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` — ein Tagesfenster
  für Trip **und** Vergleich, wirksam auf Anzeige und Bewertung; nennt seit #1584
  das Ziel-Segment als Konsumenten. Grenze: kein Mitternachtsfenster am Zielsegment.
- `docs/adr/0021-shared-deviation-alert-engine.md` — gemeinsamer Auswertungskern
  für Trip- und Compare-Alarme.
- `docs/adr/0009-alerts-als-abweichungs-waechter.md` — Alarme sind Δ-Wächter gegen
  den Briefing-Anker, keine absoluten Schwellen.
- `docs/specs/modules/fix_1584_alarm_zeitfenster.md` — die eben gelieferte Scheibe;
  listet unter Known Limitations ausdrücklich die Vienna-Kodierung der Ruhezeiten.
- `docs/specs/modules/compare_shared_day_window.md`, `issue_1378_compare_zeitbasis.md`
- **Keine eigenständige Spec für den Compare-Alarmpfad.**

## Testlage

Zehn Testdateien decken die Compare-Alarme ab (Kanäle, Metrik-Gating, Pausierung,
Kanal-Schwelle, Ruhezeiten vor dem Abruf). **Kein einziger Test prüft eine
Tagesfenster- oder sonstige Uhrzeit-Grenze auf dem Compare-Alarmpfad** — auch
nicht für den amtlichen Weg, der das Fenster bereits benutzt.

## Risks & Considerations

1. **Ein Tagesfenster als Stumm-Gate kann nur unterdrücken.** Wer es dem
   Abweichungs- oder Radar-Pfad vorschaltet, baut das #1584-Fehlerbild in die
   andere Produkthälfte ein. Der amtliche Pfad benutzt das Fenster deshalb als
   *Vorausblick-Horizont mit Klemmung*, nicht als Schalter — dieser Unterschied
   ist der Kern der Analyse-Phase.
2. **Offene Messfrage (unbestätigt, gehört in `/20-analyse`):** Der
   Abweichungs-Alarm vergleicht `aggregated` des Anker-Snapshots gegen
   `aggregated` des Frisch-Abrufs, beide über ein 1-Stunden-Fenster, aber zu
   **verschiedenen Tageszeiten** (Anker beim Report-Versand morgens, Frisch beim
   15-Minuten-Check). Ob damit „Vorhersage hat sich geändert" oder nur „es ist
   eine andere Tageszeit" gemessen wird, ist noch **nicht belegt** und darf bis
   zur Messung nicht behauptet werden.
3. **Zeitzone:** Ein Ortsvergleich kann Orte in mehreren Zonen enthalten; der Trip
   hat genau ein Ziel. Ruhezeiten sind pro Vergleich konfiguriert, nicht pro Ort —
   eine Ortszeit-Auflösung braucht also eine Regel, *welcher* Ort zählt.
4. **Kein Produktiv-Vergleich hat ein Tagesfenster gesetzt.** Jede Änderung wirkt
   ausschließlich über den Default 4/19 — Wirkung ist also sofort für alle spürbar,
   nicht nur für bewusst Konfigurierende.
5. **Regel-Budget:** Ein zusätzlicher Zeit-Regler neben Ruhezeiten und Cooldown
   braucht laut CLAUDE.md eine Ablösung oder ein Prüfdatum.
6. **Teilungs-Gate:** Trip und Vergleich sollen Code teilen. Eine Compare-eigene
   Zeitfenster-Logik neben `trip_segments.py` wäre begründungspflichtig.

---

## Analysis

### Type

**Bug.** Aus Risiko 2 der Kontext-Phase ist ein belegter Defekt geworden.

### Kernbefund (gemessen, ausgeführt — nicht hergeleitet)

**Der Abweichungs-Alarm des Ortsvergleichs vergleicht strukturell zwei
verschiedene Tageszeiten.** Anker-Snapshot und Frisch-Abruf entstehen beide über
`CompareLocationWeatherSource.fetch()`, das bei **jedem** Aufruf ein neues
Ein-Stunden-Segment bei `datetime.now()` baut
(`compare_location_weather_source.py:38-50`).

Ausgeführte Demo (Fixture mit `t2m_c = Stunde`, also *keine* geänderte Vorhersage):

```
Anker  07:00 → aggregated.temp_max_c = 7.0
Frisch 15:00 → aggregated.temp_max_c = 15.0
```

Δ 8,0 gegen eine Schwelle von 7,0 (`weather_change_detection.py:339`). Der reine
Tagesgang genügt zum Auslösen.

- `_aggregate_for_segment` (`segment_weather.py:254-271`) filtert strikt auf das
  Segmentfenster — bestätigt.
- `weather_change_detection.py:562-671` vergleicht `old.aggregated` gegen
  `new.aggregated` **ohne jeden Zeitabgleich** (Abwesenheit belegt: `start_time`/
  `end_time` kommen im Vergleichspfad nur für `new_data` vor, nie old vs. new).
- Im Compare-Pfad existiert gar kein `TripSegment` mehr, gegen das man abgleichen
  könnte — `_SegmentIdShim` (`deviation_alert_engine.py:45-60`) leitet die Zeiten
  aus der Zeitreihe des einen Punkts ab.

**Der Trip macht es strukturell richtig:** `trip_alert.py:940-983` reicht
`cached.segment` — dasselbe Objekt aus dem Anker — an den Frisch-Abruf. Gleiches
Fenster durch Konstruktion.

**Zwei Gesichter desselben Fehlers:** der Alarm meldet falsch (Tagesgang als
Änderung) *und* ist blind für echte Änderungen außerhalb der laufenden Stunde.
Er verletzt ADR-0009 — verglichen wird nicht gegen den Briefing-Stand.

### Beleg aus Produktivdaten

- Anker `cp-eb6ba0b239d90e37__toulon.json`: `aggregated.gust_max_kmh = 32,8`,
  Stundenreihe desselben Schnappschusses **51,5** — 24 Stunden liegen vor,
  bewertet wird eine.
- Alle Anker vom **31.07. 16:00**, seither unverändert (8 Tage).
- `alert_log.json`, 118 Einträge: **genau ein** Vergleichs-Alarm, 04.08. **04:00:26**,
  Metrik `gust/max`, Grund `forecast_change` — die erwartbare Signatur eines
  Vergleichs zwischen einer böigen 16-Uhr-Stunde und einer ruhigen 4-Uhr-Stunde.

### Affected Files (Weg a1, empfohlen)

| Datei | Änderung | ~LoC |
|---|---|---|
| `src/services/compare_location_weather_source.py` | `fetch()` bekommt Fensterstunden; Segment = Tagesfenster des lokalen Kalendertags statt `now…now+1h`; Randfall-Guard | 35–50 |
| `src/services/compare_alert.py` | Fensterstunden aus dem Preset an `fetch()` durchreichen (`:314-345`) | 15–20 |
| `src/services/scheduler_dispatch_service.py` | `_write_compare_alert_snapshots()` (`:475-491`) reicht dasselbe Fenster durch | 10–15 |
| `src/services/report_config_resolver.py` | **unverändert** — `resolve_compare_time_window(preset)` (`:193`) wird wiederverwendet | 0 |
| Tests | Grenzfälle Uhrzeit/Fenster; heute prüft **keine** der zehn Compare-Alarm-Testdateien eine Zeitgrenze | 80–150 |

**Produktivcode ~60–95 LoC** — innerhalb des 250-LoC-Budgets.

### Verworfene Wege

- **(a2) „jetzt bis Fensterende", geklemmt** (Muster des amtlichen Pfades): schrumpft
  das Fenster mit jedem 15-Minuten-Check — Anker und Frisch bleiben verschieden.
  Für den amtlichen Pfad richtig, für den Δ-Wächter falsch.
- **(b) Zeitabgleich im Vergleich selbst:** `PointWeatherData`
  (`point_weather.py:31-42`) trägt bewusst kein Zeitfenster. Ein breiteres Fenster
  lässt sich aus einem 1-Stunden-Anker nicht nachträglich rekonstruieren — läuft
  auf dieselbe Rechnung wie (a1) hinaus, nur an schlechterer Stelle.
- **(c) Anker häufiger schreiben:** löst den Kernbefund nicht (07:00-Anker gegen
  15:00-Abruf bleibt schief) und erzeugt eher mehr Fehlalarme.

### Risiken

- **API-Kontingent: strukturell nicht betroffen.** Open-Meteo wird mit
  `start_date`/`end_date` (Tagesauflösung) abgefragt (`openmeteo.py:707-709`) und
  liefert ohnehin 24 h (`segment_weather.py:239`); gefiltert wird lokal. Ein
  breiteres Fenster innerhalb desselben Kalendertags ändert die Zahl der Abrufe
  nicht. *Aus dem Query-Muster abgeleitet, nicht an einer echten Antwort gemessen.*
- **Cache:** `weather_cache.py:95-117` matcht über „Fenster deckt ab", nicht über
  exakte Segment-Identität — trägt ein breiteres Fenster.
- **Bestandsanker:** alte 1-Stunden-Anker gegen neue Tagesfenster-Werte → einmalig
  je aktivem Vergleich ein möglicher Fehlalarm, bis der nächste Versand einen Anker
  im neuen Zuschnitt schreibt. Produktiv betrifft das **einen** Vergleich.
- **Schwellen:** ein Maximum über 15 h hat andere statistische Eigenschaften als ein
  Momentanwert. Ob die bestehenden Schwellen dann zu träge oder zu empfindlich sind,
  ist **nicht gemessen**.
- **`alert_state`:** Schlüssel bleibt `metric:ortskennung` — keine Migration.

### Abhängigkeit zu #1467

#1467 S1 ist live, S2 AG1–AG6 sind umgesetzt; offen ist die strukturelle
Zusammenlegung von `check_and_send_alerts()` und `check_all_compare_presets()`.
Diese Scheibe arbeitet **unterhalb** davon (Wetterbeschaffung, nicht
Ablaufsteuerung) und fasst `deviation_alert_engine.py` nicht an. **Kein Blocker in
beide Richtungen.**

### Schnitt

**In diese Scheibe:** Weg (a1) für den Abweichungs-Pfad, ausdrücklicher
Randfall-Guard, Grenzfall-Tests.

**Folgescheiben:** Anker-Alterung (unbegrenztes Alter, s. offene Frage 2) ·
Radar/NowCast (hat den Defekt strukturell nicht) · Ruhezeiten in Ortszeit statt
`Europe/Vienna` · die #1467-Zusammenlegung selbst.

### Open Questions (PO)

- [ ] **Randfall außerhalb des Fensters** — was gilt, wenn der 15-Minuten-Check um
      22:00 läuft und das Fenster 4–19 ist?
- [ ] **Anker-Alterung** — die produktiven Anker sind 8 Tage alt, weil der Versand
      dieses Vergleichs seit 16.07. steht, die Alarm-Prüfung aber weiterläuft. Auch
      mit korrektem Fenster vergleicht das „heute" gegen „vor acht Tagen".
- [ ] **Mitternachts-Fenster** (`start_hour > end_hour`) — beim Trip bewusst nicht
      abgebildet; hier ebenso ausklammern?
