---
entity_id: fix_1726_ruhezeit_und_zaehler_ortszone
type: bugfix
created: 2026-08-12
updated: 2026-08-12
status: draft
workflow: fix-1726-ruhezeit-ortszone
version: "1.1"
tags: [issue-1726, epic-1722, timezone, adr-0051, adr-0044, alert-daily-limit, quiet-hours, compare, scheduler]
---

# Fix #1726 — Ruhezeit, Alarm-Tageszähler und Ortsvergleichs-Fälligkeit in der Ortszone

## Approval

- [x] Approved — PO-Freigabe („go") 2026-08-12, 15 ACs

## Purpose

Drei Entscheidungen laufen heute unabhängig von Trip oder Ort immer auf der Wiener Uhr, obwohl
sie den Nutzer an SEINEM Ort betreffen: das **Ruhezeit-Fenster** für Alarme
(`deviation_alert_engine.py:31`, Konstante `VIENNA`), der **Reset des Alarm-Tageszählers**
(`alert_daily_limit.py:23`, dieselbe Konstante) und die **Fälligkeits-Zone des
Ortsvergleichs-Versands** (`dispatch_orchestrator.py:128`, `NOCH_NICHT_ORTSZEIT_SIEHE_1726`).
Diese Scheibe stellt alle drei auf die Ortszone um. Beide `VIENNA`-Konstanten entfallen ersatzlos.

## Source

- **Files:** `src/services/deviation_alert_engine.py`, `src/services/alert_daily_limit.py`,
  `src/services/alert_gate.py`, `src/services/point_weather.py`, `src/services/trip_alert.py`,
  `src/services/compare_alert.py`, `src/services/compare_official_alert.py`,
  `src/services/compare_radar_alert.py`, `src/services/dispatch_orchestrator.py`,
  `src/services/compare_slot_scheduler.py`, `src/services/scheduler_dispatch_service.py`,
  `src/utils/timezone.py`,
  `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte`
- **Identifier:** `DeviationAlertEngine.is_quiet_hours`, `DeviationAlertEngine.evaluate`,
  `alert_daily_limit.{load,is_allowed,increment}`, `check_nowcast_gate`,
  `CompareDispatchStrategy.collect_due`, `presets_due_for_hour`,
  `utils.timezone.first_resolvable_tz` (neu)
- Issue #1726, S4 des Epics #1722. Kontext-Dokument
  `docs/context/fix-1726-ruhezeit-ortszone.md` (erhoben 2026-08-12 gegen `bc7dc418`).
- ADR-0051 (drei Zeitbegriffe, Zone an den Daten — Status Vorgeschlagen), ADR-0044 (Kalendertag
  folgt der Ortszeit — Status Akzeptiert, wird hier fortgeschrieben)
- Setzt voraus: #1724 (S2, live), #1725 (S3, live `414b0b87`) — beide liefern das Vorbild für
  die Zonen-Auflösung von Trips (`trip_local_now`/`anchor_tz`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | adr | Regel 2 ("Die Zone gehört an die Daten, nicht an den Server") — Grundlage aller drei Umstellungen |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | adr | Listet `alert_daily_limit`/`deviation_alert_engine` heute als „bewusst NICHT betroffen" — wird hier fortgeschrieben (AC-12) |
| `src/utils/timezone.py` (`resolve_location_tz`, `location_tz`, neu `first_resolvable_tz`) | module | EINZIGER Auflöser für Orte (PO-Entscheidung E3, #1378) — kein zweiter Weg; `first_resolvable_tz` präzisiert „erster Ort" auf „erster AUFLÖSBARER Ort" (E1, AC-15, s. Entwurf Abschnitt B) |
| `src/services/trip_day.py` (`trip_local_now`, `anchor_tz`) | module | EINZIGER Auflöser für Trips, day-aware (nicht `trip_tz`, das ist fix auf die erste Etappe mit Wegpunkten) |
| `src/services/compare_preview_service.py` (`order_locations_by_ids`) | module | Die vom Nutzer konfigurierte Ortsreihenfolge (#1359) — liefert die Sequenz, die `first_resolvable_tz` (s. o.) auswertet |
| `docs/specs/modules/issue_1378_compare_zeitbasis.md` | spec | Liefert den Präzedenzfall „Zone des erstgenannten Orts" (AC-4), hier auf Ruhezeit/Zähler/Fälligkeit übertragen — dort mit derselben, hier erst geschlossenen Lücke (s. Bekannte Grenzen) |
| `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md` | spec | Unmittelbares Vorbild für Struktur und Nachweis-Strategie dieser Spec |
| Issue #1777 | issue | Fälligkeitsfenster + Idempotenz-Vermerk für den Ortsvergleich — bewusst NICHT Teil dieser Scheibe |
| Issue #1727 | issue | S5 des Epics — die ~25 Muster-A-Funde (`date.today()`) der Wächter-Restliste |
| `internal/config/config.go:20` (`SchedulerTimezone`) | go | Der Go-Cron tickt weiterhin in `Europe/Vienna` — unverändert, s. Abgrenzung |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/deviation_alert_engine.py` | MODIFY | `VIENNA`-Konstante entfällt; `is_quiet_hours()` bekommt Pflicht-Parameter `zone: ZoneInfo`; `evaluate()` reicht `config.zone` (Rückfall UTC) durch |
| `src/utils/timezone.py` | MODIFY | Neuer Baustein `first_resolvable_tz(locations, context_label="")` — die EINE Stelle, an der „erster auflösbarer Ort" implementiert ist (Abschnitt B, AC-15) |
| `src/services/point_weather.py` | MODIFY | `AlertEvaluationConfig` bekommt neues Feld `zone: Optional[ZoneInfo] = None` |
| `src/services/alert_gate.py` | MODIFY | `check_nowcast_gate()` bekommt Pflicht-Parameter `zone: ZoneInfo`, reicht ihn an `is_quiet_hours()` UND an `alert_daily_limit.is_allowed()`/`record_nowcast_sent()` an `increment()` weiter |
| `src/services/alert_daily_limit.py` | MODIFY | `VIENNA`-Konstante entfällt; Schema-Wechsel auf zonenweise Zähler (`{"zones": {...}}`); `load`/`is_allowed`/`increment` bekommen Pflicht-Parameter `zone: ZoneInfo`; Rückwärts-Migration für Altbestand |
| `src/services/trip_alert.py` | MODIFY | Sieben Stellen (Ruhezeit-Adapter `:672-691`, drei Aufrufer, `check_nowcast_gate`-Aufruf `:963`, vier `alert_daily_limit`-Aufrufe, `AlertEvaluationConfig`-Konstruktion `:265`) reichen `anchor_tz(trip, now)`/`trip_local_now(...).tzinfo` durch |
| `src/services/compare_official_alert.py` | MODIFY | `:119` (is_quiet_hours) und `:138`/`:182` (alert_daily_limit) bekommen die Zone aus `first_resolvable_tz(...)` (`utils/timezone.py`) |
| `src/services/compare_alert.py` | MODIFY | `:151` (is_allowed — s. Korrektur unten), `:176` (is_quiet_hours über `AlertEvaluationConfig.zone`), `:293` (increment), `_build_eval_config()` (`:452-478`) bekommen die Zone aus `first_resolvable_tz(...)` |
| `src/services/compare_radar_alert.py` | MODIFY | `:131` (`check_nowcast_gate`-Aufruf) bekommt die Zone aus `first_resolvable_tz(...)` |
| `src/services/dispatch_orchestrator.py` | MODIFY | `CompareDispatchStrategy.collect_due()` lädt `all_locations` vorab und übergibt sie an `presets_due_for_hour`; `NOCH_NICHT_ORTSZEIT_SIEHE_1726` entfällt als Fälligkeits-Zone |
| `src/services/compare_slot_scheduler.py` | MODIFY | `presets_due_for_hour(presets, hour, today)` → `presets_due_for_hour(presets, all_locations, now_utc)`, löst je Preset über `first_resolvable_tz(...)` seine eigene Zone auf (s. Entwurf, Abschnitt D) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Kommentar/Konstantenname am manuellen `?hour=`-Trigger angepasst (Verhalten unverändert, s. Entwurf Abschnitt D) |
| `frontend/.../alerts-tab/AlertQuietHoursCard.svelte` | MODIFY | Neue Prop für die Zonen-Bezeichnung im Hinweistext |
| `frontend/.../shared/AlarmeTab.svelte` | MODIFY | Beide Mount-Punkte (`:429`/`:431`) übergeben die neue Prop kontextabhängig |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | Abschnitt „Bewusst NICHT betroffen" fortgeschrieben (AC-12) |
| `tests/test_output_timezone_guard.py` | MODIFY | Vier Einträge (`:622`, `:623`, `:630`, `:635`) entfernt; Blockkommentar `:593` korrigiert |
| `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py` | CREATE | Neue AC-Nachweise (Verhaltensname, nicht Issue-Nummer — `test_naming_gate.py`) |

**Bestehende Tests mit reiner Signatur-Folgeänderung** (kein neuer Testinhalt, aber jeder Aufruf
von `is_quiet_hours`/`check_nowcast_gate`/`alert_daily_limit.*` ohne den neuen `zone`-Parameter
wird zum `TypeError`): `tests/helpers/nowcast_gate_fixtures.py` (zentrale `VIENNA`-Fixture,
`quiet_window_now`/`quiet_window_elsewhere`/`seed_daily_counter`/`read_daily_counter`),
`tests/tdd/test_issue_1070_daily_alert_limit.py`, `tests/tdd/test_alert_quiet_hours_localtime.py`,
`tests/tdd/test_alert_quiet_hours_robustness.py`,
`tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py`,
`tests/tdd/test_compare_radar_alert.py`, `tests/tdd/test_issue_1168_alert_engine_extract.py`,
`tests/tdd/test_issue_883_acute_danger_override.py` (baut das Fenster fälschlich über `VIENNA`
trotz Island-Koordinaten — das ist der Fehlerfall dieses Issues, steckt bereits im Test), dazu
alle Aufrufer von `presets_due_for_hour`: `tests/test_compare_auto_pause_end_date.py`,
`tests/tdd/test_compare_preset_loader.py`, `tests/tdd/test_compare_preset_slot_dispatch.py`,
`tests/tdd/test_compare_alert_paused_archived_silent.py`, `tests/tdd/test_compare_anchor_target_date.py`.

### Estimated Changes

- Files: 13 Produktivdateien (11 Python, 2 Svelte) + 1 ADR + 1 Wächter-Datei + 1 neue Testdatei
  + ~13 bestehende Testdateien mit mechanischer Signatur-Folgeänderung
- LoC: siehe „Estimated Scope" unten (~235 Produktivcode)

## Problem/Kontext

**Ruhezeit.** `DeviationAlertEngine.is_quiet_hours()` (`deviation_alert_engine.py:84-143`)
konvertiert `now` fest nach `Europe/Vienna`, bevor sie gegen `quiet_from`/`quiet_to` prüft.
Gemessen (ADR-0051): für eine Ruhezeit 22:00–07:00 liegt ein Alarm um 08:00 Neuseeland-Ortszeit
(= innerhalb der Wach-Stunden) heute noch in der als Wien ausgewerteten Nacht — er würde
unterdrückt, obwohl der Nutzer wach ist. Umgekehrt geht ein Alarm um 03:00 Neuseeland-Ortszeit
(mitten in der Nacht) durch, weil er auf Wiener Uhr tagsüber liegt.

**Alarm-Tageszähler.** `alert_daily_limit.py` resettet ebenfalls auf Wiener Kalendertag-Wechsel
(`_vienna_date_str`, `:31-32`). Ein Nutzer mit Objekten in mehreren Zonen hat de facto EINEN
gemeinsamen Reset-Zeitpunkt, der zu keiner seiner Zonen passt.

**Ortsvergleichs-Fälligkeit.** `CompareDispatchStrategy.collect_due()`
(`dispatch_orchestrator.py:130-146`) bildet EINEN `vor_ort`-Zeitpunkt aus der festen Konstante
`NOCH_NICHT_ORTSZEIT_SIEHE_1726 = "Europe/Vienna"` und prüft alle Presets eines Laufs gegen
dieselbe Stunde/denselben Tag. Ein auf 07:00 gestelltes Preset mit Orten in Neuseeland geht damit
zur falschen Weltzeit raus.

Ursache aller drei: Die Entscheidung „ist jetzt X" beantwortet der SERVER, nicht der GEGENSTAND,
über den geredet wird (ADR-0051 Regel 2).

## Ziel

Alle drei Entscheidungen lösen ihre Zone aus den Daten auf, EINHEITLICH über die bereits
vorhandenen Bausteine `utils.timezone.{resolve_location_tz,location_tz}` (Orte) und
`services.trip_day.{trip_local_now,anchor_tz}` (Trips) — keine neue Auflösung, keine zweite
Kopie (ADR-0044, "Lehre für die Pflege dieser Liste").

Für Mehrzonen-Fälle (ein Ortsvergleich mit Orten in verschiedenen Zonen) gilt EINHEITLICH die
bereits PO-entschiedene Regel aus #1378 (AC-4): die Zone des **erstgenannten Orts der
konfigurierten Reihenfolge** (`order_locations_by_ids`, #1359), präzisiert als „erster Ort,
dessen Zone sich auflösen lässt" — umgesetzt in `utils.timezone.first_resolvable_tz` (s. Entwurf
Abschnitt B, AC-15). Kein neues Datenfeld, keine zweite Regel für einen anderen Anwendungsfall
derselben Frage.

## Abgrenzung

- **Fälligkeitsfenster + Idempotenz-Vermerk für den Ortsvergleich sind NICHT Teil dieser
  Scheibe** — das trägt Issue **#1777**. Hier wird bei der Ortsvergleichs-Slot-Fälligkeit
  AUSSCHLIESSLICH die Zone getauscht (Wien → erster Ort); die Prüfung selbst bleibt
  Stundengleichheit (`==`, `compare_slot_scheduler.py:152,154`). Die Umstellungstag-Lücke
  (29.03. Slot entfällt ersatzlos, 25.10. Slot geht doppelt raus) bleibt für den Vergleich damit
  vorerst bestehen — unverändert gegenüber heute, nur jetzt in der Zone des ersten Orts statt in
  Wien.
- **Die ~25 Muster-A-Funde der Wächter-Restliste (`date.today()`/`datetime.now()` ohne Zone)
  sind NICHT Teil dieser Scheibe** — sie tragen S5/**#1727**. Diese Scheibe korrigiert nur den
  Blockkommentar, der sie fälschlich #1726 zuweist (AC-14), behebt sie aber nicht.
- **Der Go-Cron tickt weiterhin in `Europe/Vienna`** (`internal/config/config.go:20`,
  `SchedulerTimezone`, Default `Europe/Vienna`). Diese Scheibe ändert nichts an der
  Cron-Auslösung selbst — nur daran, WIE die ausgelöste Prüfung ihre Fälligkeit/Ruhezeit/ihren
  Zähler bewertet. Der an Umstellungstagen ausfallende/doppelte Tick (`robfig/cron/v3`,
  dokumentiert in `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md`) bleibt bestehen
  und ist ebenfalls S5/#1727-Territorium.
- **Keine Nutzer-Zeitzonen-Einstellung.** Bereits in ADR-0044 verworfen, hier nicht erneut zur
  Wahl gestellt.
- **Der manuelle `?hour=`-Testtrigger** (`scheduler_dispatch_service.py:170-181`) behält seine
  Interpretation gegen eine feste Referenz-Zone (s. Entwurf Abschnitt D) — das ist ein
  Ops-/Debug-Werkzeug, kein Nutzerpfad, und nicht Gegenstand einer eigenen Zusicherung in dieser
  Spec.

## Entwurf/Umbau

### A. Ruhezeit — sieben Aufrufstellen, EIN geteilter Kern

`DeviationAlertEngine.is_quiet_hours()` bekommt einen Pflicht-Parameter `zone: ZoneInfo` (kein
Default) statt der festen `VIENNA`-Konstante — bewusst PFLICHT, nicht optional mit
Wien-Rückfall: ein impliziter Rückfall wäre genau die Fehlerklasse, die diese Scheibe beseitigt.
Jede der sieben Aufrufstellen liefert ihre Zone aus dem Objekt, das sie ohnehin im Scope hat:

| # | Aufrufstelle | Zone-Quelle | Code-Änderung nötig an |
|---|---|---|---|
| 1 | `compare_official_alert.py:119` (amtliche Warnung, Vergleich) | `first_resolvable_tz(...)` (`utils/timezone.py`) | dieser Zeile |
| 2 | `trip_alert.py:229` (Adapter-Aufruf, Wetter-Abweichung Trip) | Trip | keine — Zone entsteht im Adapter |
| 3 | `trip_alert.py:688` (`_is_quiet_hours`-Adapter, tatsächlicher `is_quiet_hours`-Aufruf) | `anchor_tz(trip, now)` | dieser Zeile — EINZIGE Codeänderung für #2 UND #4 |
| 4 | `trip_alert.py:1443` (Adapter-Aufruf, amtliche Warnung Trip) | Trip | keine — teilt sich den Adapter mit #2 |
| 5 | `alert_gate.py:93` (Nowcast-Schranke, geteilt Trip+Vergleich) | **kein Objekt im Scope** — Zone als Parameter durchgereicht von den zwei Aufrufern (`trip_alert.py:963`: `anchor_tz(trip, now_utc)`; `compare_radar_alert.py:131`: `first_resolvable_tz(...)`) | `check_nowcast_gate()`-Signatur + beide Aufrufer |
| 6 | `compare_alert.py:176` (Wetter-Abweichung, Vergleich) | `config.zone`, gesetzt in `_build_eval_config()` (`:452-478`) aus `first_resolvable_tz(...)` | `AlertEvaluationConfig`-Konstruktion, nicht die Aufrufzeile selbst |
| 7 | `deviation_alert_engine.py:286` (`evaluate()`, Engine-Kern) | `config.zone` (Rückfall UTC bei `None`, sichtbar dokumentiert) | dieser Zeile |

Zwei und vier bzw. drei sind bewusst als GETRENNTE Zeilen der Tabelle aufgeführt, obwohl sie
sich denselben Code teilen (`_is_quiet_hours`-Adapter, `:672-691`) — jede muss trotzdem
EIGENSTÄNDIG mit einem Alarm in einer Nicht-Wien-Zone nachgewiesen werden. Geteilter Code
bewies in #1697 dreimal in Folge nichts über den jeweiligen Aufrufer (ADR-0051,
„Folgepflichten").

### B. Zonen-Auflösung — es ist nichts zu erfinden

| Werkzeug | Zweck | Rückfall |
|---|---|---|
| `services.trip_day.anchor_tz(trip, now_utc)` bzw. `trip_local_now(trip, now_utc).tzinfo` | Zone eines Trips, **tagesbewusst** (Etappe des Weltzeit-Tages) — dieselbe Auflösung, die #1724/#1725 für die Briefing-Fälligkeit benutzen, NICHT `trip_tz()` (das ist fix auf die erste Etappe mit Wegpunkten und tagesUNabhängig) | importierte `UTC`-Konstante bei Trips ohne Wegpunkte |
| `utils.timezone.location_tz(location)` | Zone eines Orts, MIT UTC-Rückfall (identisch zu `compare_html.py:1537`, derselbe Aufruf für die Compare-Kopfzeile) | `UTC`, sichtbar über dieselbe Konvention wie die Mail-Kopfzeile |
| `utils.timezone.first_resolvable_tz(locations, context_label="")` (NEU) | Zone des ERSTEN Orts EINER SEQUENZ, dessen Zone sich auflösen lässt — Ersatz für den naiven Indexzugriff `location_ids[0]` | `UTC`, protokolliert (s. u.) |

**Warum `location_tz()` (UTC-Rückfall) statt `resolve_location_tz()` (`None`-Rückfall):**
Ruhezeit-/Zähler-/Fälligkeits-Logik brauchen eine KONKRETE Zone, kein `None` — dieselbe
Abwägung, die die Compare-Kopfzeile bereits trifft. Der Rückfall bleibt dadurch konsistent zu
dem, was der Nutzer in der Mail ohnehin sieht, statt eine zweite, abweichende Konvention
einzuführen.

**🔴 „Erster Ort" ist eine fachliche Auswahlregel, kein Indexzugriff.** Nachgemessen: Eine
*leere* Ortsliste ist an beiden Compare-Stellen ausgeschlossen (`compare_alert.py:123`,
`compare_official_alert.py:90`: `if not preset_id or not location_ids`). **Aber die ID kann ins
Leere zeigen** — `compare_official_alert.py:128` filtert genau darauf
(`[all_locations[lid] for lid in location_ids if lid in all_locations]`), weil ein gelöschter Ort
in `location_ids` stehen bleibt. Dann ist `all_locations.get(location_ids[0])` gleich `None`, und
`location_tz(None)` stürzt **nicht** ab, sondern liefert still `UTC`
(`utils/timezone.py:67-71` → `resolve_location_tz` → `getattr(None, "lat", …)` ist `None` →
`None` → `or UTC`). Dasselbe passiert bei einem Ort ohne Koordinaten und bei einem, für den
`tz_for_coords` „UTC" liefert (`:60-64` gibt in beiden Fällen `None`).

Das wäre exakt die Fehlerklasse dieser Scheibe, nur mit UTC statt Wien: ein stiller Rückfall,
obwohl der zweite Ort der Liste eine gültige Zone trägt. Deshalb gilt:

> **Maßgeblich ist der erste Ort der konfigurierten Reihenfolge, dessen Zone auflösbar ist.**
> Erst wenn KEINER der Orte eine Zone liefert, gilt UTC — und dieser Fall wird sichtbar
> protokolliert (`logger.warning` mit Preset-Kennung), nicht verschwiegen.

Das ist keine Abweichung von PO-Entscheidung E1, sondern ihre präzise Fassung: „erster Ort" war
als fachliche Auswahl gemeint, nicht als `[0]`. Nachweis: AC-15.

**Diese Regel bekommt EINEN benannten Baustein, keine fünf Kopien.** Die Auswahl wird an
mindestens fünf Compare-Stellen gebraucht (`compare_alert.py:151`/`:176`/`:293`,
`compare_official_alert.py:119`/`:138`/`:182`, `compare_radar_alert.py:131`, dazu
`presets_due_for_hour`). Würde jede ihre eigene Überspring-Schleife bauen, entstünde genau die
„eigene Kopie der Zonen-Auflösung", die ADR-0044 als Regelverstoß benennt — und diese Spec
fordert an drei Stellen selbst „EINZIGER Auflöser, keine zweite Kopie". Neu in
`src/utils/timezone.py`:

```python
def first_resolvable_tz(locations: Iterable, context_label: str = "") -> ZoneInfo:
    """Zone des ersten Orts der Reihenfolge, dessen Zone sich auflösen lässt.

    Überspringt `None` (gelöschter Ort, ID zeigt ins Leere) und Orte ohne
    auflösbare Zone. Liefert kein Ergebnis einen Treffer, ist der Rückfall UTC
    — dann aber mit `logger.warning` samt `context_label`, nicht still.
    """
```

**Warum `utils/timezone.py` und nicht `compare_preview_service.py`** (wo
`order_locations_by_ids` wohnt): Dort liegen `resolve_location_tz` und `location_tz`, also die
Auflösungs-Domäne selbst — der Baustein ist eine Anwendung dieser Auflösung, kein
Compare-Ablauf. Die Signatur nimmt bewusst eine **fertige Sequenz** statt `(location_ids,
all_locations)`, damit sie kein Compare-Vokabular kennt und vom Trip-Pfad aus nutzbar bleibt.
Die Aufrufer bauen die Sequenz in einer Zeile:

```python
tz = first_resolvable_tz(
    (all_locations.get(lid) for lid in location_ids), context_label=preset_id
)
```

`context_label` folgt dem Muster, das `is_quiet_hours` seit #1479 für protokollierbare Herkunft
verwendet.

**Warum `anchor_tz`/`trip_local_now` statt `trip_tz()` für Trips:** `trip_tz()` beantwortet nur
„welcher Kalendertag ist gerade" (fix auf die erste Etappe mit Wegpunkten). Ruhezeit und Zähler
werden dagegen fortlaufend geprüft, während der Trip läuft — ein mehrtägiger Trek, der die Zone
wechselt, braucht die Zone SEINER AKTUELLEN Etappe, nicht die des Starttags. `trip_local_now`
liefert genau das aus EINER Auflösung (Ortstag UND -stunde), konsistent mit #1725.

### C. Tageszähler — Schema, Migration, korrigierte Aufrufstellen-Liste

**🔴 Korrektur der im Kontext-Dokument gezählten Aufrufstellen:** Das Kontext-Dokument nennte
„zehn Aufrufstellen". Nachgemessen (`grep -n 'alert_daily_limit\.\(is_allowed\|increment\|load\)'`
über `src/`) sind es **elf** — `compare_alert.py:151` (`is_allowed(..., reason="forecast_change")`,
im selben Preset-Loop wie die bereits gelistete `:293`) fehlte in der Aufzählung. Genau diese
Fehlerklasse — eine unvollständige Aufrufstellen-Liste, bei der der ungenannte Weg ungeschützt
bleibt — hat #1725 bereits zweimal getroffen. Vollständige, nachgemessene Liste:

`alert_gate.py:105`/`:123` · `compare_official_alert.py:138`/`:182` ·
`trip_alert.py:240`/`:344`/`:1449`/`:1490` · `compare_alert.py:151`/`:293` · dazu die reine
Lesestelle `trip_report_scheduler.py:1570` (Starkregen-Kurzfristhinweis, bucht nie — s. #1199,
Nebenbefund, unverändert).

**Neues Schema** `data/users/<uid>/alert_daily_count.json`:

```json
{"zones": {"Europe/Vienna": {"date": "2026-08-12", "count": 2},
           "Pacific/Auckland": {"date": "2026-08-12", "count": 1}}}
```

Zonen-Schlüssel = `str(zone)` (IANA-Name, z. B. `"Europe/Vienna"`; UTC-Rückfall unter dem
Schlüssel `"UTC"`). `load`/`is_allowed`/`increment` bekommen einen Pflicht-Parameter
`zone: ZoneInfo` (kein Default — dieselbe Begründung wie bei `is_quiet_hours`). Die Zone für
Compare-Aufrufstellen kommt einheitlich aus `first_resolvable_tz(...)` (Abschnitt B).

**Migration/Bestandserhalt (Projektregel: Read-Modify-Write mit Merge, niemals Replace):** Trifft
`load`/`increment` beim ersten Zugriff auf das ALTE Schema (Top-Level-Schlüssel `"date"`/`"count"`,
kein `"zones"`-Schlüssel), wird der Bestand unter dem Schlüssel `"Europe/Vienna"` in die neue
Struktur übernommen. Begründung: der Alt-Zähler wurde de facto nach Wiener Kalendertag geführt —
`"Europe/Vienna"` ist die einzige Zone, für die der Bestandswert eine korrekte Fortsetzung ist.
Für jede andere Zone beginnt der Zähler bei 0. Die Migration ist idempotent (kein separates
Skript, geschieht beim nächsten Zugriff) und schreibt nur die betroffene Zone — alle übrigen
Zonen-Einträge einer bereits migrierten Datei bleiben beim `increment()` unangetastet (Merge auf
Zonen-Ebene, nicht nur auf Datei-Ebene).

### D. Ortsvergleichs-Slot-Fälligkeit — Zonentausch erfordert Restrukturierung

`CompareDispatchStrategy.collect_due()` bildet heute EINEN `vor_ort`-Zeitpunkt für den GESAMTEN
Lauf und übergibt `presets_due_for_hour(presets, vor_ort.hour, vor_ort.date())` — alle Presets
eines Laufs werden gegen DIESELBE Stunde/denselben Tag geprüft. Unter E1 hat aber JEDES Preset
potenziell eine ANDERE Zone (die seines ersten auflösbaren Orts) — ein einzelner globaler
`vor_ort`-Wert kann das nicht mehr abbilden. Reines Konstanten-Tauschen reicht hier NICHT.

**Umbau:** `presets_due_for_hour(presets, hour, today)` wird zu
`presets_due_for_hour(presets, all_locations, now_utc)`. Intern wird je Preset über
`first_resolvable_tz((all_locations.get(lid) for lid in preset.get("location_ids") or []),
context_label=preset_id)` die Zone aufgelöst, `vor_ort = local_dt(now_utc, zone)` gebildet, und
die BISHERIGE Stundengleichheits-Prüfung (`slots.morning_time.hour == vor_ort.hour` usw.) läuft
unverändert gegen dieses preset-eigene `vor_ort`. `collect_due()` lädt `all_locations` dafür vor
dem Aufruf (bisher nur lazy in `dispatch_one()`, `:168-169`).

**Der manuelle `?hour=`-Testtrigger** (`scheduler_dispatch_service.py:170-181`, Endpunkt für
manuell ausgelöste Testläufe) konstruiert heute einen `now_utc`, dessen Stunde in
`NOCH_NICHT_ORTSZEIT_SIEHE_1726` (Wien) exakt `hour` ist. Mit preset-eigenen Zonen hat „Stunde
X" keine EINE Bedeutung mehr. Entscheidung: der Trigger bleibt gegen eine FESTE Referenz-Zone
verankert (unbenannt umbenannt zu `MANUAL_TRIGGER_REFERENCE_ZONE = "Europe/Vienna"`, reiner
Name-Wechsel zur Klarstellung des jetzt einzigen Zwecks) — er ist ein Ops-/Debug-Werkzeug ohne
Bezug zu einem bestimmten Preset und braucht keine preset-eigene Zone. Das Verhalten des
Endpunkts selbst ändert sich dadurch NICHT.

### E. Oberfläche

`AlertQuietHoursCard.svelte` bekommt eine neue Prop (Text, nicht Zeitzonen-Berechnung — die
Karte kennt keine `ZoneInfo`-Logik, das bleibt Backend-Domäne). `shared/AlarmeTab.svelte`
(`:429`/`:431`) übergibt sie kontextabhängig: beim Trip „der Tour", beim Vergleich „des ersten
Orts" — EIN geteilter Baustein (Trip/Compare-Teilungsregel), keine zweite Komponente.

### F. ADR-0044 Fortschreibung

`docs/adr/0044-kalendertage-folgen-der-ortszeit.md`, Abschnitt „Bewusst NICHT betroffen (feste
Zone ist dort Absicht, kein Verstoß)" nennt heute `alert_daily_limit` und
`deviation_alert_engine` als Ausnahmen. Diese Scheibe kehrt das um — der Abschnitt wird
fortgeschrieben, die beiden Module wandern in „Umgesetzt". Kein neues ADR: ADR-0051 trägt die
Entscheidung bereits (wie bei #1725).

### G. Wächter-Bereinigung

Vier Einträge in `KNOWN_VIOLATIONS` (`tests/test_output_timezone_guard.py`) gehören zu dieser
Scheibe und MÜSSEN verschwinden, weil der Scanner sie nach dem Fix nicht mehr findet
(`test_known_violations_only_shrink()` erzwingt das):

- `:622` — `alert_daily_limit.py::<module>::0` (Muster B, `VIENNA`-Konstante)
- `:623` — `deviation_alert_engine.py::<module>::0` (Muster B, `VIENNA`-Konstante)
- `:630` — `alert_daily_limit.py::_vienna_date_str::0` (raw_astimezone, an Muster B gekoppelt)
- `:635` — `deviation_alert_engine.py::is_quiet_hours::0` (raw_astimezone, an Muster B gekoppelt)

Zusätzlich wird der Blockkommentar bei `:593` korrigiert: er weist derzeit ALLE 53
Bestandseinträge — darunter ~25 Muster-A-Funde, die tatsächlich #1727 zugeordnet sind —
pauschal #1726 zu. Nach dem Schliessen von #1726 darf die Liste nicht mehr auf ein erledigtes
Issue zeigen (AC-14).

## Verworfene Alternativen

- **Tageszähler: jede Aufrufstelle bringt ihre eigene Zone an EINEN gemeinsamen Datensatz** (statt
  getrennter Zonen-Buckets). Verworfen: derselbe Lauf schriebe den `date`-Schlüssel je nach
  Aufrufer zwischen zwei Kalendertagen hin und her; `increment()` setzt bei jedem Nichttreffer auf
  1 zurück (`alert_daily_limit.py:86,90-93`) — das Limit griffe effektiv NIE, und es bremst
  kostenpflichtige Premium-SMS nicht mehr. Bewusster Preis der gewählten Lösung (getrennte
  Zonen-Buckets): Wer Objekte in drei Zonen hat, bekommt das Kontingent dreimal — das ist zu
  benennen, nicht zu verstecken (AC-7).
- **Eine Nutzer-Zeitzonen-Einstellung** als Referenz für den Tageszähler. In ADR-0044 bereits
  verworfen ("der Wanderer ist unterwegs, nicht zu Hause") — hier nicht erneut zur Wahl gestellt,
  aus demselben Grund auf den Zähler übertragen.
- **Alphabetische Sortierung der Orte** als Referenz für „erster Ort" beim Mehrzonen-Vergleich.
  War nie die tatsächliche Regel (der Kommentar bei `comparison.py:201-202` behauptet das noch,
  ist seit #1359 falsch) — die konfigurierte Reihenfolge (`location_ids`) gilt, nicht eine vom
  System erzeugte Sortierung.
- **„Erster Ort" als reiner Indexzugriff `location_ids[0]`.** Erwogen als einfachste Umsetzung,
  aber verworfen: ein gelöschter oder unauflösbarer erster Ort führte zu einem stillen
  UTC-Rückfall, obwohl ein späterer Ort der Liste eine gültige Zone hätte — genau die
  Fehlerklasse, die diese Scheibe beseitigt, nur mit einem anderen falschen Ergebnis (UTC statt
  Wien). Ersetzt durch `first_resolvable_tz()` (Abschnitt B, AC-15).
- **`first_resolvable_tz()` in `compare_preview_service.py` ansiedeln** (neben
  `order_locations_by_ids`, mit Compare-Vokabular `location_ids`/`all_locations` als Parameter).
  Erwogen wegen der thematischen Nähe zu `order_locations_by_ids` — verworfen, weil die Funktion
  selbst kein Compare-Wissen braucht: sie wertet eine FERTIGE Sequenz von Orten aus, kein Preset.
  Mit einer generischen Sequenz-Signatur bleibt sie stattdessen in `utils/timezone.py`, wo bereits
  `resolve_location_tz`/`location_tz` wohnen — die eigentliche Auflösungs-Domäne — und bliebe vom
  Trip-Pfad aus nutzbar, falls dort je ein Mehrzonen-Fall entstünde (heute nicht der Fall, aber
  keine Weichenstellung dagegen). Die Compare-Aufrufer bauen die Sequenz selbst in einer Zeile
  (Abschnitt B).
- **Fälligkeitsfenster + Idempotenz auch für den Ortsvergleich, in derselben Scheibe wie der
  Zonentausch.** Erwogen, aber PO-Entscheidung E3 (2026-08-12): getrennt, weil die
  Fälligkeitsfrage und die Zonenfrage unabhängig beantwortbar sind und die Zusammenlegung die
  Scheibe unnötig vergrössert hätte. Trägt #1777.

## Acceptance Criteria

- **AC-1 (Ruhezeit östlich von Wien wird in der ECHTEN Ortszeit geprüft):** Given ein Trip mit
  Wegpunkt in `Pacific/Auckland` und Ruhezeit 22:00–07:00 / When ein Wetter-Abweichungs-Alarm zu
  einem Zeitpunkt ansteht, der in Auckland innerhalb des Ruhezeit-Fensters, in Wien aber tagsüber
  liegt / Then wird der Alarm unterdrückt — heute ginge er durch, weil die Prüfung fälschlich
  gegen Wien läuft. Wirkt in `deviation_alert_engine.py:84-143`, verdrahtet über
  `trip_alert.py:229/688`.

- **AC-2 (Ruhezeit westlich von Wien wird in der ECHTEN Ortszeit geprüft):** Given derselbe
  Aufbau mit Wegpunkt in `America/Los_Angeles` / When ein Alarm zu einem Zeitpunkt ansteht, der
  in Los Angeles innerhalb, in Wien aber ausserhalb des Ruhezeit-Fensters liegt / Then wird der
  Alarm unterdrückt.

- **AC-3 (Alle sieben Ruhezeit-Prüfstellen bekommen dieselbe Ortszone, nicht nur die
  einfachsten):** Given jede der sieben Stellen, an denen eine Ruhezeit-Prüfung im Code steht —
  amtliche Warnung Vergleich (`compare_official_alert.py:119`), Wetter-Abweichung Trip
  (`trip_alert.py:229`), der geteilte Adapter selbst (`trip_alert.py:688`), amtliche Warnung Trip
  (`trip_alert.py:1443`), die Nowcast-Schranke (`alert_gate.py:93`, kein eigenes Objekt — Zone von
  den zwei Aufrufern durchgereicht), Wetter-Abweichung Vergleich (`compare_alert.py:176`) und der
  Engine-Kern selbst (`deviation_alert_engine.py:286`) / When an dieser Stelle ein Alarm für eine
  Entität in einer Nicht-Wien-Zone ausgelöst würde / Then wertet JEDE der sieben Stellen die
  Ruhezeit in DIESER Zone aus, nicht in Wien — einzeln nachgewiesen, nicht nur über den geteilten
  Code miterschlossen (geteilter Code bewies in #1697 dreimal nichts über den jeweiligen
  Aufrufer).

- **AC-4 (Mehrzonen-Vergleich — Ruhezeit folgt dem ERSTEN Ort und wandert mit der
  Reihenfolge):** Given ein Ortsvergleich mit Orten in zwei verschiedenen Zonen in der vom
  Nutzer konfigurierten Reihenfolge / When die Ruhezeit für diesen Vergleich geprüft wird / Then
  gilt die Ortszeit des ERSTGENANNTEN Orts — und wird ein anderer Ort in der Konfiguration an die
  erste Stelle verschoben, verschiebt sich die wirksame Ruhezeit nachweislich mit. Wirkt in
  `compare_alert.py:176`/`compare_official_alert.py:119`/`compare_radar_alert.py:131`, Grundlage
  ist `order_locations_by_ids` (#1359).

- **AC-5 (#1479 bleibt gewahrt — kein Programmabsturz durch den neuen Zonen-Parameter):** Given
  ein unbrauchbarer Ruhezeit-Wert (`"25:00"`, `"abc"`, ein Nicht-String) / When die Ruhezeit an
  irgendeiner der sieben Stellen geprüft wird / Then gilt weiterhin „keine Ruhezeit gesetzt"
  statt eine Ausnahme durchzureichen — auch mit dem zusätzlichen Zonen-Parameter unverändert.
  Wirkt `deviation_alert_engine.py:109-139`.

- **AC-6 (Tageszähler resettet zur ORTS-Mitternacht, nicht zur Wiener):** Given ein Trip/Preset
  in einer Zone östlich von Wien (`Pacific/Auckland`) UND eines westlich (`America/Los_Angeles`)
  / When ein Alarm knapp VOR bzw. knapp NACH der jeweiligen Orts-Mitternacht ausgelöst wird,
  während in Wien noch derselbe bzw. bereits ein anderer Kalendertag gilt / Then zählt der Alarm
  zum Ortstag, nicht zum Wiener Tag — in beiden Richtungen nachgewiesen. Wirkt
  `alert_daily_limit.py` (`load`/`increment`).

- **AC-7 (Getrennte Zähler pro Zone — kein gegenseitiges Verbrauchen, bewusster Preis
  benannt):** Given ein Nutzer hat zwei Objekte (z. B. zwei Trips oder ein Trip und einen
  Ortsvergleich) in unterschiedlichen Zonen, beide mit erreichtem Tageslimit in ihrer jeweiligen
  Zone / When in beiden Zonen je ein weiterer Alarm ausgelöst würde / Then wird das Kontingent
  jeder Zone UNABHÄNGIG geführt — ein ausgeschöpftes Kontingent in Zone A blockiert Zone B nicht,
  UND ein Alarm in Zone A verbraucht nicht das Kontingent von Zone B. Der bewusste Preis (wer
  Objekte in drei Zonen hat, bekommt das Kontingent dreimal) ist Teil dieser Zusicherung, kein
  verstecktes Nebenprodukt.

- **AC-8 (Bestandsdaten bleiben beim Rollout erhalten — kein Kontingent-Leck):** Given ein
  bestehender Zähler im ALTEN Schema (`{"date": ..., "count": N}`, keine Zonenkennung) liegt
  bereits auf der Festplatte, mit einem Zählerstand ungleich 0 für den heutigen Wiener Tag / When
  der neue Code diesen Zähler zum ersten Mal für einen Trip/Ortsvergleich in `Europe/Vienna`
  liest oder erhöht / Then bleibt der Bestandswert erhalten und wird NICHT unbegründet auf 0
  zurückgesetzt — ein Deploy mitten am Tag führt für Wiener Zeit nicht zu einem Kontingent-Leck
  (Read-Modify-Write mit Merge).

- **AC-9 (Ortsvergleichs-Slot-Fälligkeit folgt der Zone des ersten Orts, Prüfung bleibt
  unverändert):** Given ein Ortsvergleichs-Preset mit Orten in einer Zone abweichend von Wien,
  konfiguriertem Morgen-Slot 07:00 / When der Versandlauf zu einem Zeitpunkt läuft, der in der
  Zone des ERSTEN Orts genau 07:00 ist, aber in Wien eine andere Stunde / Then wird das Preset als
  fällig erkannt — heute würde es das nicht, weil die Prüfung fälschlich gegen Wien läuft. Zwei
  Presets desselben Nutzers mit ersten Orten in unterschiedlichen Zonen sind zu unterschiedlichen
  Weltzeit-Momenten fällig. Die Prüfung selbst bleibt Stundengleichheit (kein Fenster, keine
  Idempotenz — das trägt #1777). Wirkt `dispatch_orchestrator.py` (`CompareDispatchStrategy.
  collect_due`) und `compare_slot_scheduler.py` (`presets_due_for_hour`).

- **AC-10 (Beide Sommerzeit-Wechseltage — Häufigkeit jeder einzelnen Stunde, nicht die
  Zeilenzahl):** Given der Frühjahrs-Umstellungstag 29.03.2026 UND der Herbst-Umstellungstag
  25.10.2026, je in einer Zone mit Sommerzeit-Wechsel und einer Ruhezeit über Mitternacht (Wrap)
  / When der Tageszähler-Reset bzw. die Ruhezeit-Prüfung über den gesamten Tag beobachtet wird,
  Stunde für Stunde / Then verhält sich beides an der jeweils EXAKTEN Orts-Mitternacht korrekt —
  am Frühjahrstag (23 Ortsstunden) ohne vorzeitigen Reset, am Herbsttag (25 Ortsstunden, Stunde 02
  existiert zweimal) ohne doppelten Reset.

- **AC-11 (Oberfläche nennt die Zonen-Basis der Ruhezeit):** Given der Alarme-Reiter zeigt die
  Ruhezeit-Karte, einmal im Trip-Kontext und einmal im Ortsvergleichs-Kontext / When die Karte
  angezeigt wird / Then benennt sie die Ortszeit-Basis unterschiedlich — beim Trip „Ortszeit der
  Tour", beim Vergleich „Ortszeit des ersten Orts" — statt wie bisher gar keine Zone zu nennen.
  Wirkt `AlertQuietHoursCard.svelte`, gemountet aus `shared/AlarmeTab.svelte:429/431` als EIN
  geteilter Baustein für beide Kontexte.

- **AC-12 (ADR-0044 nachgezogen):** Given ADR-0044 listet `alert_daily_limit` und
  `deviation_alert_engine` unter „Bewusst NICHT betroffen (feste Zone ist dort Absicht)" / When
  diese Scheibe live ist / Then ist dieser Abschnitt fortgeschrieben — beide Module stehen nicht
  mehr als Ausnahme, sondern folgen der Ortszone wie die übrigen bereits umgesetzten Bereiche.

- **AC-13 (Wächter-Restliste schrumpft um genau die vier zugehörigen Einträge):** Given die vier
  Einträge `:622`, `:623`, `:630`, `:635` in `tests/test_output_timezone_guard.py` / When diese
  Scheibe live ist / Then findet der Scanner diese Stellen nicht mehr, die vier Einträge sind aus
  `KNOWN_VIOLATIONS` entfernt, und `test_known_violations_only_shrink()` bleibt grün.

- **AC-14 (Fehlzuordnung im Blockkommentar korrigiert):** Given der Blockkommentar bei
  `tests/test_output_timezone_guard.py:593` weist derzeit ALLE 53 Bestandseinträge — auch die
  ~25 Muster-A-Funde, die tatsächlich #1727 zugeordnet sind — pauschal #1726 zu / When diese
  Scheibe schliesst / Then ist der Kommentar so korrigiert, dass er die verbleibenden
  Muster-A-Funde korrekt #1727 nennt und nicht mehr auf ein bereits erledigtes Issue zeigt.
  - Test: Datei-Inhalts-Prüfung mit `# doc-compliance-test`-Kennzeichnung (Ausnahme von der
    „kein Dateiinhalt-Check"-Regel, weil hier die Dokumentations-Korrektheit selbst der
    Gegenstand ist).

- **AC-15 (Ein gelöschter oder unauflösbarer erster Ort kippt den Vergleich nicht still auf
  Weltzeit):** Given ein Ortsvergleich, dessen erstgenannter Ort gelöscht wurde oder keine
  auflösbare Zone hat, während ein späterer Ort in der Liste eine gültige Zone trägt / When
  Ruhezeit, Tageszähler oder Slot-Fälligkeit für diesen Vergleich bestimmt werden / Then gilt die
  Zone des ersten Orts, der sich AUFLÖSEN LÄSST — nicht Weltzeit. Nur wenn kein einziger Ort eine
  Zone liefert, gilt UTC, und dieser Fall wird im Protokoll mit der Vergleichs-Kennung sichtbar
  gemacht, statt still zu geschehen. Wirkt in `utils.timezone.first_resolvable_tz()` (Abschnitt
  B), genutzt von allen Compare-Aufrufstellen dieser Scheibe (Abschnitte A, C, D).

## Nachweis-Strategie

Kern-Schicht, deterministisch: kein Netz, keine echten Postfächer. Zeit wird als Parameter
hereingereicht, nicht per Patch auf die Systemuhr — Muster aus #1724/#1725. Neue Datei
`tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py` (Verhaltensname, nicht
Issue-Nummer — `test_naming_gate.py` blockt sonst).

🔴 **Falle, die die Testfälle vorwegnehmen:** `Europe/Paris` fällt UTC-Offset-mässig mit Wien
zusammen — ein Test dort kann eine Zonen-Zusicherung strukturell nicht von einem Wien-Rückfall
unterscheiden (kostete in #1725 bereits eine Adversary-Runde). Alle Ost/West-Nachweise dieser
Scheibe verwenden deshalb `Pacific/Auckland` (östlich) und `America/Los_Angeles` (westlich).

| AC | Testfall | Verfälschung, die ihn rot macht |
|---|---|---|
| AC-1 | Auckland-Trip, Ruhezeit-Wrap, Alarm bei Weltzeit, die in Auckland Nacht/in Wien Tag ist → unterdrückt | `zone`-Parameter ignorieren, weiter fest `VIENNA` verwenden |
| AC-2 | LA-Trip, spiegelbildlich → unterdrückt | dito |
| AC-3 | Sieben Einzeltests, je EINE der sieben Stellen mit einer Nicht-Wien-Zone | eine der sieben Stellen den `zone`-Parameter NICHT durchreichen lassen — nur die anderen sechs Tests bleiben grün |
| AC-4 | Zwei Orte, zwei Zonen, beide auflösbar, Ruhezeit trifft nur bei Zone von `location_ids[0]`; Reihenfolge tauschen → Ruhezeit-Ergebnis kippt mit | `location_ids[0]` durch eine feste/alphabetische Auswahl ersetzen |
| AC-5 | `"25:00"`/`"abc"`/`None`-Ruhezeitwert mit gesetztem `zone`-Parameter → weiterhin `False`, kein Traceback | `try/except` um den neuen Parameter entfernen |
| AC-6 | Zähler-Reset exakt an Orts-Mitternacht, Auckland UND LA, je knapp davor/danach geprüft | Reset weiterhin gegen `_vienna_date_str` statt zonenspezifisch |
| AC-7 | Zwei Zonen, beide am Limit, unabhängige Zähler | ein gemeinsamer Schlüssel ohne Zonen-Diskriminator |
| AC-8 | Alt-Schema-Datei mit Zählerstand ungleich 0, Zugriff in `Europe/Vienna` → Bestand erhalten | Migration durch Replace statt Merge ersetzen |
| AC-9 | Zwei Presets, unterschiedliche erste Orte, unterschiedliche Zonen, je zur eigenen 07:00 fällig | `presets_due_for_hour` weiterhin mit EINEM globalen `hour`/`today` aufrufen |
| AC-10 | 29.03. und 25.10.2026, Auckland/LA, Reset UND Ruhezeit stundenweise beobachtet | Tageslänge als fixe 24h annehmen statt zu berechnen |
| AC-11 | Playwright/Component-Test: Karte im Trip- vs. Vergleichs-Kontext zeigt unterschiedlichen Text | Text hart auf einen Kontext verdrahten |
| AC-12 | Dateiinhalt-Prüfung (`# doc-compliance-test`): ADR-0044 nennt `alert_daily_limit`/`deviation_alert_engine` nicht mehr unter „Bewusst NICHT betroffen" | ADR unverändert lassen |
| AC-13 | `test_known_violations_only_shrink()` bleibt grün nach Entfernen der vier Einträge | einen der vier Einträge stehen lassen |
| AC-14 | Dateiinhalt-Prüfung: Kommentar bei `:593` referenziert die Muster-A-Restliste korrekt auf #1727 | Kommentar unverändert lassen |
| AC-15 | Vergleich mit gelöschtem erstem Ort + gültigem zweitem Ort in Nicht-UTC-Zone → Ruhezeit folgt dem zweiten Ort; separater Fall „kein Ort auflösbar" → UTC UND Protokolleintrag | `first_resolvable_tz`s Skip-Schleife durch direkten `location_ids[0]`-Zugriff ersetzen (fällt still auf UTC) |

**Mutations-Gegenprobe (Pflicht):** mindestens gegenzuprüfen — `zone`-Parameter an einer der
sieben Ruhezeit-Stellen stillschweigend ignorieren, Zähler-Migration durch Replace ersetzen,
`first_resolvable_tz`s Skip-Schleife durch direkten Index-0-Zugriff ersetzen,
`presets_due_for_hour` mit einem globalen statt preset-eigenen `vor_ort` belassen.

## Estimated Scope

- **LoC:** ~235 Produktivcode über 11 Python- + 2 Svelte-Dateien (grösste Einzelposten:
  `alert_daily_limit.py` ~60 wegen Schema-Migration, `trip_alert.py` ~25 wegen sieben
  Aufrufstellen, `compare_slot_scheduler.py`/`dispatch_orchestrator.py` zusammen ~45 wegen der
  Restrukturierung von `presets_due_for_hour`, `utils/timezone.py` ~15 für
  `first_resolvable_tz`); Testcode und die Wächter-Listen-Korrektur zählen nicht gegen das
  Limit.
- **Files:** 13 Produktivdateien, 1 ADR, 1 Wächter-Datei, 1 neue Testdatei, ~13 bestehende
  Testdateien mit mechanischer Signatur-Folgeänderung.
- **Effort:** high — nicht wegen algorithmischer Komplexität, sondern wegen der Anzahl
  unabhängig nachzuweisender Aufrufstellen (7 Ruhezeit + 11 Zähler + 1 Fälligkeits-Restrukturierung)
  und der Pflicht-Enumeration aus #1725s Lehre.
- **Limit-Reserve:** ~235/250 ist knapp. 🔴 **Die naheliegende Ausweichoption ist keine.** Die
  Restrukturierung von `presets_due_for_hour`/`dispatch_orchestrator.py` (Abschnitt D, ~45 LoC)
  ist zwar technisch die am ehesten separierbare Einheit, aber sie herauszuschneiden hiesse: die
  **Ortsvergleichs-Slot-Fälligkeit bliebe vollständig auf Wien**. Das ist eine der DREI im Issue
  genannten Kernsachen, nicht eine Verfeinerung — die Scheibe schrumpfte von drei Umstellungen
  auf zwei, und AC-9 wanderte samt erneuter Freigabepflicht nach #1777. **Das ist deshalb eine
  PO-Entscheidung, keine Entwickler-Entscheidung.** Der reguläre Weg bei Überschreitung ist die
  Anhebung des LoC-Rahmens per Override — ebenfalls nur mit PO-Zustimmung. Nicht
  herausschneidbar: die Zähler-Migration (Sicherheitsargumentation, AC-8) und die sieben
  Ruhezeit-Stellen (zusammenhängende Zusicherung, AC-3).

## Bekannte Grenzen

- **Compare-Fälligkeits-Lücke bleibt bestehen.** Die Umstellungstag-Lücke (29.03. Slot entfällt,
  25.10. Slot doppelt) für den Ortsvergleich wird durch diese Scheibe NICHT behoben — nur die
  Zone ändert sich, nicht die Prüfmethode. Behebung: #1777.
- **Mehrzonen-Trips behalten den ADR-0044-Restfehler.** `anchor_tz`/`trip_local_now` treffen bei
  einem Zonenwechsel zwischen zwei benachbarten Etappen am selben Tag ggf. die falsche Etappe —
  bereits als akzeptierter Restfehler in ADR-0044 dokumentiert, hier geerbt, nicht neu
  eingeführt.
- **Rollout-Übergang beim Tageszähler ist für Nicht-Wien-Zonen grosszügiger, nie enger.** Jede
  Zone ausser `Europe/Vienna` beginnt beim ersten Zugriff nach dem Rollout bei Zählerstand 0,
  auch wenn am selben Wiener Tag bereits Alarme für ein Objekt in dieser Zone gesendet wurden.
  Das erlaubt für den Rest dieses einen Tages potenziell mehr Alarme als das Limit vorsieht — nie
  weniger. Das ist die sichere Richtung (kein blockierter Alarm) und einmalig auf den Rollout-Tag
  begrenzt.
- **Der Go-Cron bleibt Wien-getaktet** (`internal/config/config.go:20`) und fällt an
  Umstellungstagen weiterhin aus/verdoppelt — unabhängig von dieser Scheibe, s. Abgrenzung.
- **Dieselbe Präzisierung fehlt der Compare-Mail-Kopfzeile.** `compare_html.py:1535-1538` und
  `comparison.py:216` greifen mit `locations[0]` zu und fallen bei einem unauflösbaren ersten Ort
  ebenso still auf UTC — der Präzedenzfall, dem AC-15 folgt, trägt den Mangel selbst. Der
  „gelöschte ID"-Fall tritt dort nicht auf (`result.locations` enthält nur bereits verarbeitete
  Orte), der „unauflösbare Zone"-Fall aber schon. Hier bewusst NICHT mitrepariert (die Kopfzeile
  ist Darstellung, nicht Alarm-Entscheidung, und ein UTC-Zeitstempel dort ist sichtbar falsch
  statt still wirksam). Zu buchen als eigener Eintrag für den Team-Lead.
- **Die Oberfläche nennt einen Referenzpunkt, keinen konkreten Zonennamen.** „Ortszeit der Tour"/
  „Ortszeit des ersten Orts" sagt WOVON die Zeit abhängt, nicht WELCHE IANA-Zone konkret gilt
  (z. B. „Europe/Paris"). Eine genauere Beschriftung wäre möglich, ist aber nicht Teil dieser
  Scheibe (kein PO-Auftrag dafür vorliegend).
- **Der manuelle `?hour=`-Testtrigger** bleibt an eine feste Referenz-Zone gebunden (Abschnitt D)
  — für Presets mit mehreren Zonen gibt es dort strukturell keine EINE richtige Antwort auf
  „Stunde X"; das Werkzeug ist für gezielte Einzeltests gedacht, nicht für einen
  produktionsgetreuen Multi-Zonen-Lauf.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0051, ADR-0044
- **Rationale:** ADR-0051 (Status: Vorgeschlagen) formuliert in Regel 2 bereits „Die Zone gehört
  an die Daten, nicht an den Server" — diese Spec ist die konkrete Anwendung dieser Regel auf
  Ruhezeit, Tageszähler und Ortsvergleichs-Fälligkeit, kein neuer Grundsatz. ADR-0044 (Status:
  Akzeptiert) listet beide betroffenen Module bisher als bewusste Ausnahme; diese Spec hebt die
  Ausnahme auf und schreibt den ADR-Abschnitt „Umgesetzt" fort (AC-12). Ein NEUES ADR ist nicht
  nötig: es entsteht keine neue Entscheidungsfläche, sondern die dritte praktische Umsetzung
  einer bereits vorgeschlagenen Regel im Alarm-/Versandpfad, nach #1724 (Fälligkeit Trip) und
  #1725 (Fälligkeitsfenster + Idempotenz Trip).

## Changelog

- 1.0 (2026-08-12): Initial spec created, aus `docs/context/fix-1726-ruhezeit-ortszone.md` auf
  Basis der Vorlage `fix_1725_faelligkeit_und_idempotenz.md`. Korrektur gegenüber dem
  Kontext-Dokument: die Zähler-Aufrufstellen sind ELF, nicht zehn (`compare_alert.py:151` ergänzt,
  s. Entwurf Abschnitt C).
- 1.1 (2026-08-12): Nachtrag NACH PO-Freigabe (ACs unverändert im Wortlaut, Nummerierung,
  Reihenfolge — nur Verortung der in AC-15 zugesicherten Regel präzisiert). Neue Funktion
  `first_resolvable_tz()` in `utils/timezone.py` benannt (Abschnitt B, mit Skip-Logik über
  gelöschte/unauflösbare Orte + protokolliertem UTC-Rückfall); Platzierung gegen
  `compare_preview_service.py` abgewogen und begründet (generische Sequenz-Signatur statt
  Compare-Vokabular, Nähe zu `resolve_location_tz`/`location_tz`, Abschnitt B + Verworfene
  Alternativen). Dependencies, Affected-Files-Tabelle, Abschnitte A/C/D sowie
  Nachweis-Strategie/Mutations-Gegenprobe auf `first_resolvable_tz(...)` umgestellt statt
  `location_ids[0]`/„erster Ort". Estimated Changes/Scope auf ~235 LoC / 13 Produktivdateien
  angehoben (inkl. `utils/timezone.py` ~15 LoC).
