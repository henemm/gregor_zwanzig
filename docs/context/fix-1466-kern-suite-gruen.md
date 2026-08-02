# Kontext: Kern-Suite grün — echte Verstöße, Wächter-Schlüssel, Roundtrip-Invariante

Stand 2026-08-02, HEAD `fda6e10d`. Ziel: der deterministische Kern läuft wieder grün
(Dach **#1196**), damit ein rotes Ergebnis wieder ein Signal ist. Messung von heute Nacht:
12 rot; acht davon sind durch #1435 E3b und #1453 bereits weg.

## Warum das zählt

Ein rotes Testnetz ist schlimmer als ein löchriges: Wer die Suite laufen lässt, **erwartet**
Rot und liest es nicht mehr. **Beleg aus dieser Erhebung:** Der Auflösungs-Wächter hat
zwei **echte** neue Verstöße gemeldet — beide gingen im Rauschen der roten Suite unter,
einer davon aus einer Lieferung von gestern. Deckt sich mit dem Audit vom 2026-08-01
(„Wächter meldeten es, keiner las den Lauf").

## Arbeitspaket 1 — zwei echte Verstöße (kein Wächter-Problem)

Beide sind **stille Auflösungsverluste**: eine unbekannte Größe wird kommentarlos verworfen.

| Ort | Funktion | Muster | Herkunft |
|---|---|---|---|
| `src/output/renderers/compare_hourly_metric_ids.py:112` | `normalize_hourly_metrics` | `get_metric(...)` → `except KeyError: continue` | **#1406 B** (`eedeeed9`) |
| `src/output/renderers/email/html.py:615` | `build_trip_corridor_id_map` | `get_metric(...)` → `except (KeyError, TypeError): continue` | #1425 S2b (`b3995b17`) |

Der erste ist besonders unangenehm: #1406 B ist die Lieferung, die Metriken **aus dem
Register auflöst** — ausgerechnet dort verschwindet eine unbekannte Kennung lautlos.

## Arbeitspaket 2 — die Wächter-Schlüssel

**Drei** Wächter, nicht zwei. Der dritte stand nicht in der Rot-Liste:

| Wächter | KNOWN_VIOLATIONS | rot | Scope-Verfolgung? |
|---|---|---|---|
| `tests/test_success_status_guard.py` | 45 Einträge (`:1410`) | 2 | ja (`_scopes()` `:326`) |
| `tests/test_resolution_loss_guard.py` | 22 Einträge (`:616`) | 3 | ja (`_scopes()` `:157`) |
| `tests/test_output_timezone_guard.py` | 22 Einträge (`:381`) | **2** | **nein** — muss nachgerüstet werden |

### Der Schlüssel muss `datei::funktion::ordinal` sein — nicht `datei::funktion`

**Der Funktionsname liegt bereits vor.** Beide Scanner sind AST-basiert und führen ihn
heute schon **im Wert** (`f"{KIND}::{scope_name}"`); `_finding_locations()` baut daraus
bereits `"pfad::funktion"`, und `SPEC_LISTED_FINDINGS` benutzt genau dieses Format
erfolgreich („bewusst OHNE Zeilennummern", `test_success_status_guard.py:1676`). Der Umbau
braucht **keine neue Scanner-Fähigkeit**, nur eine Umschlüsselung.

**Das Ordinal ist Pflicht, nicht Kür.** Ohne es fallen **9 von 70 Funden** aus der Ratsche:

| Treffer | Funktion |
|---|---|
| 4 | `trip_command_processor.py::_handle_query` |
| 3 | `notification_service.py::send_official_alert` |
| 3 | `notification_service.py::_dispatch_alert_message` |
| 2 | `trip_command_processor.py::_trigger_on_demand` |
| 2 | `geosphere_warn.py::_extract_alerts` |

Beide Dateien warnen davor ausdrücklich im Kommentar
(`test_success_status_guard.py:613-616`, `test_resolution_loss_guard.py:580-586`): ein
Schlüssel auf `def`-Ebene machte AC-1/AC-17 **strukturell unerfüllbar**.

### Die Drift ist nachgewiesen, nicht vermutet

**Erfolgs-Wächter: 13 „behoben" ↔ 13 „neu", 13/13 dieselbe Stelle** (Quelltext + Funktion
identisch, gegen `git show 6c82e2ce:` verifiziert). Versatz **nicht konstant**: +3 in
`notification_service.py`, +119/+124 in `trip_alert.py` — händisches Nachziehen ist nicht
mit einer Zahl zu erledigen. Verursacher `4267c90d` (#1444 S1).

**Auflösungs-Wächter: 12 ↔ 14.** Davon 10 reine Verschiebungen (+24, −14, +160, +173,
+176, +7), **2 echte neue Verstöße** (Arbeitspaket 1) und **2 Funktions-Aufteilungen**:
`_extract_alerts_from_cap` wurde mit `9c20f482` (#1445) in `_collect_cap_info_entries` +
`_group_and_map_info_entries` zerlegt.

### Bekannte Grenzen des neuen Schlüssels — ehrlich benennen

| Grenze | Beleg |
|---|---|
| **Funktion umbenannt/aufgeteilt** bricht ihn ebenso | genau das reißt heute `test_scanner_finds_every_spec_listed_finding` — und diese Liste ist **bereits** zeilenfrei. Verschiebt das Problem von „jede Einfügung" auf „jede Umbenennung", nicht auf null. |
| **Kein Klassenkontext** | `_scopes()` liefert flaches `node.name`. 11 mehrdeutige Namen in der Erfolgs-, 14 in der Auflösungs-Scanfläche (`dispatch_orchestrator.py` 6×). Heute kein Fund betroffen. |
| **Ordinal verschiebt sich beim Reparieren** | Wird einer von drei Funden in derselben Funktion behoben, wandern die anderen. Trifft nur die 5 Kollisionsfunktionen und genau in dem Moment, in dem man die Liste ohnehin anfasst. |
| **Dritter Wächter kann noch nicht** | `test_output_timezone_guard.py:175` läuft mit blankem `ast.walk` ohne Scope — `_scopes()` erst nachrüsten. |

Mitzuziehen: `INTENTIONAL_CONSTANT_SUCCESS` / `_WEBHOOK_ACK_LOCATION`
(`test_success_status_guard.py:268`, an drei Stellen als Schlüssel benutzt) ist ebenfalls
zeilenbasiert — dieselbe Bombe mit längerer Lunte.

## Arbeitspaket 3 — die Roundtrip-Invariante

`tests/test_trip_flat_fields_dual_read.py::test_ac13_report_config_byte_identical_after_roundtrip`
fordert: nach Laden+Serialisieren ist `report_config` **byte-identisch**.

**Gemessen:** Ein **gesetztes** Tagesfenster (8–18) überlebt unverändert. Es kommen nur
`day_window_start_hour`/`_end_hour` als `None` **hinzu**, wenn sie im Original fehlten.
**Nichts verschwindet — kein Datenverlust.**

**Die naheliegende Lösung ist falsch.** `_trip_to_dict` (`loader.py:1521-1553`) emittiert
**alle 29 Schlüssel unbedingt**. Ließe man leere weg, bräche der Persistenzpfad:
`save_trip` (`:1629-1644`) nutzt `_deep_merge_preserve_unknown` (`:124-136`), das **in
`report_config` hineinrekursiert** — ein fehlender Schlüssel lässt den **alten
Plattenwert** stehen. Ein einmal gesetztes Tagesfenster wäre nie wieder löschbar. Genau
diese Falle ist schon einmal aufgeschlagen und steht als Warnung im Code (`:1554-1562`,
#1250 Scheibe 4 F002). Zurücksetzen ist ein realer Pfad:
`internal/handler/trip_day_window_write_seam_test.go:48-80` verlangt es.

**Der Test fordert eine unhaltbare Invariante.** Alle 29 Felder verhalten sich gleich; der
Test bemerkt nur diese zwei, weil sie als einzige in der Testvorlage fehlen
(`test_trip_flat_fields_dual_read.py:58-86`). `wind_exposition_min_elevation_m` und
`paused_until` sind derselbe Fall und stehen nur zufällig drin. Vor allem: **`updated_at`
wird bei jedem Laden auf `datetime.now()` gesetzt** (`loader.py:604`) — Byte-Identität ist
für dieses Feld per Definition unerreichbar.

**Entscheidung (Tech Lead, 2026-08-02):** Der Test wird auf die tragfähige Aussage
umgestellt — *es geht keine Information verloren, und es kommt keine hinzu, die etwas
anderes bedeutet als ihre Abwesenheit*. `day_window_* = None` bedeutet exakt dasselbe wie
„Schlüssel fehlt" (`_clamped_day_window`, `loader.py:98-121`, kennt keinen dritten
Zustand). Der Produktivcode bleibt unangetastet; einen Test, der eine unhaltbare Invariante
fordert, verbiegt man nicht mit Produktivcode.

## Nicht anfassen

Andere Sitzungen arbeiten an **#1452** (`meteoalarm-throttle-check`), **#1457**
(`intake-1394`), **#1459** (`snappy-tickling-lighthouse`) — gemessen, nicht vermutet.
