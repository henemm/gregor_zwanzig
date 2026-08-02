# Context: Konzept #1458 — Alerts neu ordnen (Zweck einstellbar, Kanal treibt)

Erhoben 2026-08-02. Issue #1458 ist ausdrücklich **Konzept — keine Spec, kein Code**.
Zweck dieses Dokuments: die technische Landkarte, auf der die offenen Entscheidungen
E1–E6 aus dem Issue beantwortet werden können.

## Request Summary

Der Zweck von Ad-hoc-Meldungen (Alerts) soll vom Nutzer einstellbar werden, mit dem
**Kanal als Haupttreiber** (teure Satelliten-SMS vs. kostenlose E-Mail). „Wachhalten"
scheidet aus, akute Gefahr muss durchkommen. #1444 S2b bleibt bis zur Entscheidung
angehalten.

## Die vier Ad-hoc-Auslöser im Code

Alle vier laufen im **Go-Cron alle 15 Minuten** (`internal/scheduler/scheduler.go:145–151`)
und rufen jeweils einen eigenen Python-Endpoint in `api/routers/scheduler.py`:

| Auslöser | Cron-Job | Endpoint | Python-Einstieg |
|---|---|---|---|
| Vorhersage-Änderung ggü. letztem Briefing | `alert_checks` | `POST /api/scheduler/alert-checks` | `TripAlertService.check_all_trips()` → `check_and_send_alerts()` (`trip_alert.py:137`) |
| Eigener Grenzwert gerissen (#1444 S1) | dito — **im selben Lauf** | dito | `evaluate_corridor_thresholds()` (`corridor_threshold.py:68`), aufgerufen aus `check_and_send_alerts()` |
| Regenradar/Nowcast | `radar_alert_checks` | `POST /api/scheduler/radar-alert-checks` | `TripAlertService.check_radar_alerts()` (`trip_alert.py:793`) |
| Amtliche Warnung | (im Alert-Lauf) | — | `trip_alert.py:1198 ff.`, Log-Eintrag `:1210` |
| Ortsvergleich: Änderung / Radar / amtlich | `compare_alert_checks` u.a. | `/api/scheduler/compare-alert-checks`, `-radar-`, `-official-` | `compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` |

**Grenzwert-Melder existiert nur für Touren**, nicht für den Ortsvergleich (E5).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py` (57 kB) | Zentrale des Tour-Alert-Pfads. Alle vier Auslöser münden hier. |
| `src/services/corridor_threshold.py` | Reine Schwellen-Auswertung (#1444 S1/S2a). **Kennt das Briefing nicht** → Befund B1. |
| `src/services/deviation_alert_engine.py` | Ausgelagerter Kern des Änderungs-Wächters (Δ-Vergleich gegen Briefing-Snapshot). |
| `src/services/alert_state.py` | Melde-Gedächtnis („worüber habe ich schon gemeldet"). |
| `src/services/trip_report_scheduler.py:972 / :1036` | `_reset_alert_state_after_briefing()` — löscht das Melde-Gedächtnis nach **jedem** Briefing (#816). Für den Änderungs-Melder richtig, für den Grenzwert-Melder falsch → Befund B1. |
| `src/services/alert_daily_limit.py` | Globales Tageslimit `alert_daily_limit` — heute die **einzige** Mengensteuerung über alle Auslöser. |
| `src/services/notification_service.py:443 / :484` | `send_deviation_alert()` / `send_location_deviation_alert()` — nehmen `effective_channels: set[str]` entgegen. **Hier würde eine kanalabhängige Filterung ansetzen.** |
| `src/services/trip_alert.py:1213` | `_effective_alert_channels()` — löst die aktiven Kanäle auf (`trip.alert_channels`, #1258 S3). Reines An/Aus, kein Schwellwert. |
| `src/services/trip_alert.py:704–720` | `_filter_significant_changes()` — gibt **alle** Änderungen zurück. Kommentar: *„severity is label only, not filter criterion"* (#638) → Befund B2. |
| `src/services/trip_alert.py:721` | `_append_alert_log()` — schreibt `trip_id`, `sent_at`, `changes_count`, `severity`. **Keine Wettergröße** → Befund B3. |
| `src/app/models.py:821` | `AlertSeverity` = INFO / WARNING / CRITICAL — bereits vorhanden, aber wirkungslos. |
| `src/services/weather_change_detection.py:214` | Mapping `AlertSeverity → ChangeSeverity` (MINOR/MODERATE/MAJOR) — existiert, steuert aber nichts. |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` + `alarme-tab/` | Geteilter Alarme-Reiter (Tour + Ortsvergleich). |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | Feste Abschnittsreihenfolge: `official-warnings`, `metric-levels`, `channels`, `cooldown`, `quiet-hours` (+ `radar` nur Vergleich) → Ort für E4. |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte` | Kanal-An/Aus (#1258). Der natürliche Ort für eine **Schwelle je Kanal** (E1). |
| `frontend/src/lib/components/CorridorEditor*.svelte` | Reiter *Wertebereiche* — der vierte Auslöser wohnt hier → Befund B5. |

## Existing Patterns

- **Kanal-Auflösung ist bereits ein eigener Schritt.** `_effective_alert_channels()` liefert
  ein `set[str]`, das an `notification_service.send_deviation_alert(effective_channels=…)`
  gereicht wird. Eine kanalabhängige Schwelle bräuchte also **keinen neuen Datenweg**,
  sondern eine Entscheidung *pro Kanal statt einmal für alle*.
- **Dringlichkeit wird bereits berechnet**, nur nicht benutzt: `AlertSeverity` (Regel-Ebene)
  und `ChangeSeverity` (DTO-Ebene) samt Mapping sind vorhanden. Der Filter wurde bei #638
  bewusst entfernt, weil er still INFO/MINOR verschluckte — eine Wiedereinführung muss
  diesen Fall abdecken (nutzergesteuert statt hartkodiert).
- **RMW-Kontrakt bei Persistenz** (`internal/handler/trip.go:361`): Alle Trip-Felder werden
  Read-Modify-Write gemergt, `alert_channels` ist ein Pointer (nil = erben).
- **Trip/Compare-Teilung ist Pflicht** (CLAUDE.md): Der Alarme-Reiter ist bereits geteilt
  (`shared/AlarmeTab.svelte`, `context: 'route' | 'vergleich'`). Alles Neue gehört dorthin.
- **Alerts haben eine eigene Konfigurationsseite** (PO-Vorgabe, #1088): Neue Alert-Schalter
  gehören in den Alarme-Reiter, nicht in *Wertebereiche*.

## Dependencies

- **Upstream:** Go-Cron (`internal/scheduler/scheduler.go`) → Python-Endpoints
  (`api/routers/scheduler.py`) → `TripAlertService` / `Compare*AlertService`.
- **Downstream:** `notification_service` → `output/channels/{email,sms,telegram}.py`;
  `alert_log.json` wird von Go **read-only** gelesen (`GET /api/cockpit/status`,
  `GET /api/archive/stats`) — ein Schema-Zuwachs muss additiv sein.

## Existing Specs & ADRs

| Dokument | Inhalt |
|---|---|
| `docs/specs/modules/trip_alert.md` | Grundspezifikation Tour-Alerts |
| `docs/specs/modules/feat_1444_s1_schwellen_alarm.md` | Schwellen-Alarm S1 (live) |
| `docs/specs/modules/feat_1444_s2a_schwellen_namensraum.md` | Namensraum-Auflösung S2a (live) |
| `docs/specs/modules/alert_daily_limit.md` | Globales Tageslimit |
| `docs/specs/modules/alert_quiet_hours_localtime.md` | Ruhezeiten |
| `docs/specs/modules/feat_864_859_alert_presets.md` | Alarm-Voreinstellungen |
| `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md` | Zeitgrenze des Alarm-Laufs |
| `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` | Geteilter Alarme-Reiter, Abschnittsreihenfolge |
| ADR-0040 | Schwellen-Alarm-Render-Vertrag (#1444 S1) |

**Historie, die nicht neu hergeleitet werden darf:** #813 (Alert = „was hat sich seit dem
letzten Briefing geändert"), #816/#817/#818 (die drei umgesetzten Scheiben), #1371 S6
(Rückbau des „Warnen"-Schalters, weil er im falschen Reiter stand), #638 (Severity-Filter
entfernt).

## Risks & Considerations

1. **B1 ist live und produziert täglich Wiederholungen** (seit 2026-08-01). Der PO hat
   entschieden: erst Zweck klären, nicht vorschnell stilllegen. Solange die Klärung
   dauert, läuft die Doppelmeldung weiter.
2. **Severity-Filter wiedereinführen ist ein Regress-Risiko** — genau das wurde bei #638
   entfernt, weil er still schluckte. Jede Neufassung braucht Sichtbarkeit dessen, was
   ein Kanal *nicht* bekommen hat.
3. **`alert_log.json` wird von Go gelesen** — Schema-Erweiterung nur additiv (B3/E6).
4. **Zwei Namensräume für Korridor-Metriken** (`AlertMetric` vs. Compare-Katalog,
   `corridor_threshold.py:32`) — eine Vereinheitlichung der Auslöser (E3) trifft
   unweigerlich diese Nahtstelle. Siehe #1455.
5. **Der Ortsvergleich hinkt hinterher** (E5): kein Grenzwert-Melder. Eine Vereinheitlichung
   der Auslöser muss entscheiden, ob Compare mitzieht oder bewusst zurückbleibt.
6. **Mengengerüst:** Juni 76 · Juli 31 · August (bis 02.) 3 Meldungen. Das ist die
   Grundlage, an der sich jede Neuregelung messen lassen muss.

## Nächster Schritt

E1–E6 sind **PO-Entscheidungen**, keine technischen Fragen. Ohne sie kann `/20-analyse`
nichts entscheiden. Reihenfolge-Empfehlung: E2 (woraus ergibt sich Dringlichkeit) →
E1 (wie stellt der Nutzer sein Maß ein) → E3 (ein Melder oder vier) → E4/E5/E6.

---

# Analysis (Phase 2, 2026-08-02)

## Type

**Konzept / Feature-Grundsatzklärung.** Kein Bug-Fix — auch wenn Befund B1 ein
nutzersichtbares Fehlverhalten ist, ist es Folge einer ungeklärten Grundsatzfrage,
nicht eines Programmierfehlers.

## Nachgemessene Korrekturen zur bisherigen Aktenlage

### 1. Der Sicherheits-Override IST gebaut (entgegen bisheriger Notiz)

Issue **#883** (Slice 4 aus Epic #813) ist geschlossen seit 2026-06-25 und live.
Beleg: `trip_alert.py:880–883`

```python
# Sicherheits-Override (Slice 4, #883): konvektive Gefahr (Gewitter/Hagel)
# durchbricht die Briefing-Unterdrückung. Normaler (nicht-konvektiver) …
if _briefing_announced and not result.is_convective:
    continue
```

**Folge für die PO-Vorgabe 4 („akute Gefahr muss durchkommen"):**

| Fall aus der PO-Vorgabe | Stand |
|---|---|
| Gewitter/Hagel, Beginn ≤20 Min (`radar_alert_due(result, threshold_min=20)`, `:871`) | **erfüllt**, live seit 2026-06-25 |
| Einsetzender Regen in den nächsten Minuten | **nicht erfüllt** — wird unterdrückt, wenn das Briefing ihn angekündigt hat (`:883`) |
| Sturmböen | **nicht erfüllt** — aus #883 ausdrücklich ausgeklammert („`NowcastResult` hat kein Wind-Feld"), nie nachgeholt |

Gilt ausschließlich im Radar-/Nowcast-Pfad, nie im Vorhersage-Pfad.

### 2. Trip und Ortsvergleich teilen den Melder bereits

- `DeviationAlertEngine` wird von **beiden** genutzt: `trip_alert.py:262`, `compare_alert.py:183`.
  Ruhezeiten und Cooldown ebenfalls (`compare_radar_alert.py:92/103`, `compare_official_alert.py:107`).
  Festgehalten in **ADR-0021** (#1168) — eine separate Compare-Engine wurde ausdrücklich verworfen.
- **`ComparePreset` hat bereits ein `corridors`-Feld** (`models.py:947`, `compare_preset.go:106`).
  Dem Ortsvergleich fehlt für den Grenzwert-Melder also **nur der Auswerter**, nicht das Datenmodell.
- `corridor_threshold.py` wird heute ausschließlich von `trip_alert.py:25/387` importiert.

**Folge:** E5 ist erheblich kleiner als zunächst geschätzt — kein Datenmodell, kein
Speicherweg, nur der fehlende Leser.

### 3. Rote Linie #638 trifft die naheliegende E1-Lösung

Die naheliegende Antwort auf E1 („je Kanal eine Dringlichkeits-Schwelle") berührt eine
Entscheidung, die 2026-06-09 mit **#638** in die Gegenrichtung fiel: Die Severity-Auswahl
wurde aus der Oberfläche **entfernt**, weil „Info" intern `MINOR` bedeutete und der Filter
erst ab `MODERATE` versendete — der Nutzer stellte einen Alarm ein und bekam nie einen.
Seither gilt: Dringlichkeit wird **abgeleitet und angezeigt**, nie ausgewählt.

**Der Unterschied, auf den es ankommt:** Bei #638 war das Stummschalten **ungewollt und
unsichtbar** — die Einstellung tat das Gegenteil dessen, was sie versprach. Eine
Kanal-Schwelle („SMS erst ab Warnstufe") ist ein **gewolltes** Stummschalten.

**Die Bedingung, unter der E1 keine Wiederholung von #638 ist:** Es darf nie vorkommen,
dass eine Meldung auf *allen* Kanälen unter der Schwelle liegt und spurlos verschwindet.
Was ein Kanal nicht bekommen hat, muss protokolliert und im nächsten Briefing sichtbar
sein. Das verknüpft E1 zwingend mit E6 (Protokoll) — E6 ist damit keine Kür, sondern
Voraussetzung.

## Weitere rote Linien aus der Historie

| Nicht mehr vorschlagbar | Beleg |
|---|---|
| Absolute Schwellen als **Standard**verhalten (additiv erlaubt) | ADR-0009, bestätigt durch ADR-0040 |
| Dringlichkeit als **wählbares** Feld pro Regel | #638 |
| Getrennte Wächter für Radar und Vorhersage | #818 („ein Wächter, zwei Quellen") |
| Vorboten-Größen (Feuchte, Taupunkt, Regenwahrscheinlichkeit, Bewölkung, Luftdruck, gefühlte Temperatur) als Auslöser | ADR-0010 |
| Zweiter Renderer im Frontend | ADR-0011 |
| Eigene Compare-Alert-Engine | ADR-0021 |
| Alarme implizit aus der Anzeige-Konfiguration ableiten | #946 |
| Steuer-Schalter im Reiter *Wertebereiche* neben der Von/Bis-Grenze | #1371 S6, #1425 |

## Scope Assessment (Vorschlag, 5 Scheiben)

| # | Inhalt | Umfang | Risiko |
|---|---|---|---|
| 1 | **E6** — Protokoll um Wettergröße/Grund **und um Nicht-Zustellungen** erweitern | ~30–60 LoC, nur Backend, additiv | LOW |
| 2 | **E3** — Grenzwert wird Empfindlichkeit des Änderungs-Melders statt vierter Auslöser (behebt B1) | mehrere hundert LoC, 5 Backend-Module | **HIGH** |
| 3 | **E1** — Dringlichkeits-Schwelle je Kanal | ~150–250 LoC, Backend + Frontend | MEDIUM |
| 4 | **E4** — Bedienung im Reiter *Alarme* zusammenführen | ~50–100 LoC, nur Frontend | LOW |
| 5 | **E5** — Ortsvergleich gleichziehen | kleiner als geschätzt (nur Auswerter) | LOW |

Reihenfolge-Logik: erst messbar machen (1), dann den akuten Schmerz strukturell beheben (2),
dann den eigentlichen PO-Wunsch liefern (3), dann aufräumen (4), dann Gleichstand (5).

## Risks

1. **Wiederholung von #638** — siehe oben. Bedingung: Nicht-Zustellungen protokollieren.
2. **Scheibe 2 ist der riskanteste Eingriff** — sie fasst `trip_alert.py`,
   `corridor_threshold.py`, `deviation_alert_engine.py`, `alert_state.py` und
   `trip_report_scheduler.py` gleichzeitig an.
3. **Zwei Namensräume für Korridor-Größen** (`corridor_threshold.py:32`) — Scheibe 2 trifft
   diese Nahtstelle zwangsläufig. Siehe #1455, gleiches Muster wie #1257.
4. **`alert_log.json` wird von Go read-only gelesen** — Erweiterung nur additiv.
5. **Messlatte:** Juni 76 · Juli 31 · August (bis 02.) 3 Meldungen. Ziel ist weniger
   Wiederholung, nicht weniger echte Warnung.

## Auswirkung auf #1444

- **S1 + S2a** bleiben funktional, ziehen aber in Scheibe 2 strukturell um: Der Grenzwert
  verliert den Status als eigener vierter Auslöser und wird zur Empfindlichkeits-Einstellung.
- **S2b** (Schalter im Reiter *Wertebereiche*) **entfällt**, sobald E4 im Sinne von
  „Steuerung ausschließlich im Reiter *Alarme*" entschieden wird — konsistent mit #1371 S6.
- Empfehlung: #1444 nach Scheibe 2 schließen, mit Verweis auf #1458.

## Open Questions — PO-Entscheidung nötig

- [ ] **E1/E2** Dringlichkeit je Kanal einstellbar? Und woraus leitet sie sich ab?
- [ ] **E3** Ein Melder statt vier?
- [ ] **E4** Steuerung ausschließlich im Reiter *Alarme*?
- [ ] **NEU: Vorgabe 4 vervollständigen?** Gewitter ist abgedeckt, einsetzender Regen und
      Sturmböen nicht. Sollen sie nachgezogen werden?
- [ ] **E5** Ortsvergleich gleichziehen? (Empfehlung: ja, ist klein)
- [ ] **E6** Protokoll erweitern? (Empfehlung: ja, ist Voraussetzung für E1)

---

# ZIELMODELL (PO-Entscheidung 2026-08-02) — ersetzt „ein Melder"

> Drei unterschiedliche Dinge: (1) ein **Vorhersage-Wert** hat sich signifikant geändert,
> (2) es gibt einen relevanten **Nowcast-Bericht**, (3) es gibt eine relevante **amtliche
> Warnung**. Wobei *relevant* immer einbezieht: (a) der Nutzer will darüber **auf diesem
> Kanal** informiert werden, und (b) er befindet sich zum Zeitpunkt voraussichtlich **auf
> dem Segment**, für das die Warnung/Änderung gilt.

Ergänzt (vom PO angenommen): **(c) es ist neu oder hat sich verschärft** — Punkt 1 ist ein
Ereignis, die Punkte 2 und 3 sind fortbestehende Zustände; ohne Gedächtnis meldet die
15-Minuten-Prüfung sie endlos neu.

**Der Grenzwert ist kein vierter Grund** — er definiert, was bei Punkt 1 „signifikant" heißt.

## Ist-Stand je Bedingung (gemessen)

| | (a) Kanal | (b) Segment/Zeit | (c) neu/verschärft |
|---|---|---|---|
| 1. Vorhersage-Änderung | nur an/aus (`trip_alert.py:1213`) | ✅ (`:688`) | ✅ `alert_state` |
| 1b. Grenzwert (heute eigener Auslöser) | nur an/aus | ✅ (`corridor_threshold.py:87`) | ⚠️ Merker wird nach jedem Briefing gelöscht (`trip_report_scheduler.py:1036`) = **B1** |
| 2. Nowcast | nur an/aus | ✅ (`trip_alert.py:878`) | ✅ Cooldown + Briefing-Vergleich |
| 3. Amtliche Warnung | nur an/aus | ⚠️ **Ort ja, Zeit nein** = **B6** | ✅ `a.level > prev` (`:1159`) |

**B6 (neu):** `trip_alert.py:1144` ruft `get_official_alerts_for_location(*coord)` ohne
Zeitfenster → `base.py:150` setzt `effective_start = now`, `window_end = None` → Filter
(`base.py:85`) kennt **keine obere Grenze**. Eine erst in drei Tagen beginnende Warnung wird
gemeldet, obwohl der Nutzer dann zwei Etappen weiter ist.

**(a) ist heute nirgends erfüllbar** — Kanäle sind reines an/aus, `trip_alert.py:710`:
*„severity is label only, not filter criterion"*. Das ist der Kern des Umbaus.

## Nowcast-Umfang (gemessen, korrigiert eine Fehlannahme)

`radar_service.py:68-75` — ein Nowcast-Ergebnis trägt genau `precip_mm_h` und `is_convective`.
**Kein Wind.** Punkt 2 umfasst damit **Regen und Gewitter**; Sturmböen im Nowcast existieren
nicht. Die Zusage aus #883 („Sturmböen später separat") war schon 2026-06-25 ohne
Datengrundlage und **entfällt ersatzlos**.

Quellenkette (`radar_service.py:271-303`): Brightsky (DE) → GeoSphere INCA (AT) → Radar-DPC
(IT, inkl. Korsika) → ARPAE → AROME-FR → ICON-D2 → Open-Meteo `minutely_15`.

## Entscheidungsstand

| | Stand |
|---|---|
| **E1** Maß je Kanal | ✅ Schwelle je Kanal; „Telegram alles / SMS nur höchste" ist **Beispiel**, einstellbar |
| **E2** Dringlichkeit | folgt aus dem Modell (Unmittelbarkeit + Nutzer-Grenze), nicht separat zu entscheiden |
| **E3** Auslöser | ✅ drei Quellen, EIN Relevanz-Filter |
| **E4** Bedienort | Steuerung nur im Reiter *Alarme* → **#1444 S2b entfällt** |
| **E5** Ortsvergleich | ja (Engine geteilt, `ComparePreset.corridors` existiert) |
| **E6** Protokoll | ✅ zuerst |
| **E7** akute Gefahr | entfällt als eigene Frage — „beginnt in Minuten" ist keine Sonderregel, sondern eine genauere Aussage als „heute Nachmittag", also echte neue Information |

## Reihenfolge (PO: „Erst Protokoll")

1. **Protokoll** — welche Wettergröße, welcher der drei Gründe, was einem Kanal **vorenthalten** wurde
2. **Relevanz-Filter vereinheitlichen** — Grenzwert → Empfindlichkeit von Punkt 1; Gedächtnis (c) für alle drei; Zeitbezug (b) für amtliche Warnungen (B6)
3. **Schwelle je Kanal** (a)
4. **Bedienung** im Reiter *Alarme* zusammenführen
5. **Ortsvergleich** gleichziehen
