# Context: feat-2050-s6-protokoll-vorwarnzeit

Issue #2050, Scheibe **S6** — Anforderung **E-1** (Nachvollziehbarkeit).
Erstellt 2026-08-22. Vorgaenger: S1 (Pruefstrecke), S2a (Waechter Szenarien 2+3),
S2b (laufendes Ereignis) — alle drei geliefert. Stand: `origin/main` = `5fd9008f`.

Alle Aussagen dieses Dokuments sind am Code nachgeprueft (Kartierung per Explore auf
`5fd9008f`); jede Zeilenangabe ist ein Beleg, keine Schaetzung.

## Request Summary

Das Alarm-Protokoll soll die Groessen festhalten, mit denen sich nachtraeglich belegen
laesst, **warum ein Alarm kam oder ausblieb**: gemeldete Vorwarnzeit, Ereigniszeit,
Messpunkt, Vergleichsbasis und Quelle. Heute fehlt die Vorwarnzeit vollstaendig — ein
Vorfall "kam zu spaet" ist im Nachhinein nicht belegbar.

## Ist-Stand: was das Protokoll heute haelt

Ein Schreibmodul, `src/services/alert_log.py` (613 Zeilen), Ablage pro Nutzer unter
`get_data_dir(user_id) / "alert_log.json"` (`alert_log.py:388`), zwei Top-Level-Listen:

| Liste | Bedeutung | Beleg |
|---|---|---|
| `entries` | mindestens ein Kanal war erreichbar | `alert_log.py:384` |
| `not_delivered` | kein Kanal erreichbar **oder** vor dem Versand abgewiesen | `alert_log.py:479` |

Der Eintrag ist ein rohes dict (keine dataclass), `alert_log.py:358-382`:

```
entity_id, entity_type, sent_at, changes_count, severity,
metrics[{metric_id, aggregation, value?, previous_value?}],
hazards[], reason, channels_sent[], channels_not_sent[{channel, reason}]
```

Additiv-optional: `capture_id` (`:377`), `capture_ids` (`:379`),
`is_addendum` + `addendum_reported_at` (`:381-382`).

## Abgleich mit E-1 — vier von fuenf Groessen fehlen

| E-1-Groesse | Heute | Wo der Wert am Aufrufort bereits vorliegt |
|---|---|---|
| **Vorwarnzeit** | **fehlt vollstaendig** — kein `onset`/`lead`/`minutes`-Schluessel im Modul | `result.onset_minutes` (`trip_alert.py:1523`), `nowcast.onset_minutes` (`compare_radar_alert.py`) |
| **Ereigniszeit** | fehlt. `sent_at` ist der Zeitpunkt des Protokollschreibens (`:364`, `:462`), nicht des Ereignisses. Einzige Ausnahme `addendum_reported_at` (`:382`) — das ist der Meldezeitpunkt der Vorwarnung, nicht die Ereigniszeit | `_onset_dt` (`trip_alert.py:1395`); amtlich `_alert.valid_from`/`valid_to` (`trip_alert.py:2001`) |
| **Messpunkt** | fehlt. `MetricValue.segment_id` existiert (`:93`), dient aber nur der Gleichstands-Aufloesung in `_ist_extremer()` (`:104`) und wird in `_metric_dict()` (`:142-156`) **nicht** serialisiert | `active.segment_id` / `km_from` / `km_to` (`trip_alert.py:1524-1531`); `loc.id` im Ortsvergleich; `change.segment_id` im Abweichungszweig |
| **Vergleichsbasis** | fehlt. `reference_at` wird berechnet, geht aber nur in die Mail-Fusszeile (`output/renderers/alert/render.py:1093`). Der Briefing-Schnappschuss `_briefing_precip` (`trip_alert.py:1428`) landet nur als Freitext im `gate_reason` bei Unterdrueckung (`:1435`) | `reference_at` (`trip_alert.py:388-403`, `compare_alert.py:286-308`) |
| **Quelle** | **teilweise.** `reason` nennt den Zweig (`forecast_change` / `nowcast` / `official_alert`, `alert_log.py:66-68`); der **Datenlieferant** (DWD/RADOLAN, GeoSphere INCA, Open-Meteo) fehlt und ist ueber `capture_id` nur indirekt aufloesbar | `radar_svc.source_label(result.source)` (`trip_alert.py:1536`) |

**Nichts muss neu berechnet werden.** Alle fuenf Groessen liegen an der jeweiligen
Aufrufstelle bereits als Variable vor. Die Scheibe reicht durch, sie leitet nicht ab.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_log.py` | Das Schreibmodul. `append_entry()` `:275`, `_append()` `:387`, `append_suppressed_entry()` `:402`. Hier entstehen die neuen kwargs und ihre additive Serialisierung |
| `src/services/trip_alert.py` | Drei `append_entry` (`:408` deviation, `:1632` radar, `:2050` official) und vier `append_suppressed_entry` (`:1299`, `:1433`, `:1583`, `:2010`) |
| `src/services/compare_alert.py` | `append_entry` `:327` (deviation, Ortsvergleich); `reference_at` `:286-308` |
| `src/services/compare_radar_alert.py` | `append_entry` `:287`, `append_suppressed_entry` `:199`/`:243` |
| `src/services/compare_official_alert.py` | `append_entry` `:265`, `append_suppressed_entry` `:226` |
| `internal/store/log.go` | Go-Leseseite. `AlertLogEntry` `:48-56` liest **nur sechs Felder** und verwirft alles andere still — deshalb ist eine additive Erweiterung fuer Go unsichtbar |
| `src/services/alert_input_capture.py` | Der Roh-Mitschnitt (E-2, #1948). **Anderes Ablagesystem**, ueber `capture_id` mit dem Protokoll verbunden |

## Existing Patterns

**Additive Feld-Erweiterung ist der etablierte Weg — zweimal erfolgreich gefahren:**

- `capture_id` (#1948): `if capture_id is not None: entry["capture_id"] = capture_id` (`alert_log.py:377`)
- `is_addendum` / `addendum_reported_at` (#2018): `if is_addendum:` (`:381-382`)

Beide folgen derselben Regel: **Absenz statt `null`** (`_metric_dict()` `:142-156`). Alt-Eintraege
bleiben dadurch bit-identisch, es braucht keinen Migrationsschritt. `_append()` faehrt
Read-Modify-Write ueber die volle Datei (`:387-401`) — die Projektregel fuer Persistenz-Aenderungen.

**Fail-soft ist bereits im Schreibpfad verankert:** `_append()` faengt `OSError`/`ValueError`
und legt die Datei notfalls neu an (`:391-394`) — "eine kaputte Datei darf keinen Alarm killen".

## Dependencies

- **Upstream** (was das Protokoll nutzt): `get_data_dir(user_id)`, `metric_catalog`
  (Register-Kennungen, O1 aus #1459), `NotificationResult` (Kanal-Aufschluesselung).
- **Downstream** (was das Protokoll nutzt):
  - Go: `LoadAlertLog()` (`log.go:63`, liest **nur** `entries`) → `AlertCountByEntity()` (`:116`)
    → Archiv-Statistik (`internal/handler/archive_stats.go:22`) und Cockpit-Kachel
    (`internal/handler/cockpit.go:22-41`, Route `GET /api/cockpit/status`, `router.go:197`)
  - Python: `read_undelivered()` (`alert_log.py:536`) → `alert_briefing_anchor.py:247` →
    Briefing-Abschnitt "FEHLGESCHLAGEN / ZURUECKGEHALTEN"
    (`src/output/renderers/email/undelivered_hint.py`)
  - Frontend: liest **nur** die aggregierte Cockpit-Antwort, nie die Datei — kein Feldzugriff
    auf Protokoll-Details

## Existing Specs

- `docs/specs/modules/feat_1459_alert_protokoll.md` — die Grundspec des Protokolls. Enthaelt
  die **harte Nebenbedingung D4** (PO-Entscheidung 2026-08-02): Cockpit-Kachel und
  Archiv-Statistik duerfen sich fuer Bestandstouren **um keine einzige Zahl** aendern.
  Das Protokoll ist ein internes Protokoll, kein Anzeige-Feature. Dort auch die
  offene Luecke **O3** (`:921-931`).
- `docs/specs/modules/alarm_eingangsprotokoll.md` — der Roh-Mitschnitt (E-2, #1948 S1)
- `docs/specs/modules/alarm_pruefstrecke.md` — der Harness aus S1
- `docs/specs/modules/alarm_szenarien_waechter_2_3.md` — S2a
- `docs/specs/modules/alarm_szenario_laufendes_ereignis.md` — S2b

## Risks & Considerations

1. **Die drei `append_entry()`-Aufrufe in `trip_alert.py` sind ungeschuetzt.**
   `:408`, `:1632`, `:2050` — kein `try/except`. Ein neuer Feldbau, der wirft (etwa
   `.isoformat()` auf `None` oder eine Zeitdifferenz gegen `None`), **verhindert den Alarm**.
   Die Unterdrueckungs-Aufrufe sind dagegen alle gewrappt (`:1298`, `:1432`, `:1582`, `:2009`).
   Das ist das einzige echte Schadenspotenzial dieser Scheibe.

2. **D4 aus #1459 muss halten.** Go verwirft unbekannte JSON-Felder still
   (`log.go:48-56`), Cockpit und Archiv-Statistik aendern sich also von selbst um keine Zahl —
   vorausgesetzt, die Erweiterung bleibt rein additiv und fasst die sechs gelesenen Felder
   nicht an.

3. **Der Bestand sichert Schema-Identitaet ausdruecklich zu.**
   `tests/tdd/test_alert_log.py:259` prueft, dass der Normalfall schema-identisch bleibt.
   Rund 2.500 Zeilen Protokoll-Tests in zehn Dateien (`test_alert_log*.py`,
   `test_nowcast_suppression_logging.py` mit 783 Zeilen) muessen mitgezogen werden.

4. **Nicht jede Groesse existiert in jedem Zweig.** Der Abweichungsalarm kennt keine
   Vorwarnzeit im Nowcast-Sinn, die amtliche Warnung hat `valid_from`/`valid_to` statt eines
   Onsets. Das Schema muss "diese Groesse gibt es hier nicht" von "sie fehlt" unterscheiden —
   die Absenz-Regel des Bestands leistet genau das.

5. **Der Mitschnitt (E-2) hilft fuer E-1 nur begrenzt.** Der Nowcast-Mitschnitt haelt rohe
   Frames (`radar_service.py:1146`), **kein** abgeleitetes `onset_minutes`. Die *gemeldete*
   Vorwarnzeit — die Zahl, die beim Nutzer ankam — steht dort nicht und muss ins Protokoll.

## Abgrenzung (bewusst NICHT in dieser Scheibe)

- **Luecke O3** — der Vorhersage-Aenderungsalarm protokolliert seine Unterdrueckungen
  **gar nicht** (`alert_log.py:432-434`, `feat_1459_alert_protokoll.md:921-931`). Das ist
  Anforderung **D-2**, nicht E-1, und gehoert in eine eigene Scheibe.
- **Sichtbarmachung** — keine Go-, keine Frontend-Aenderung. D4 stellt das Protokoll
  ausdruecklich als internes Werkzeug fest.
- **E-2 (Roh-Mitschnitt)** — existiert und funktioniert (#1948 S1); dass er teils unter
  `debug/` liegt, ist ein eigener Befund.
