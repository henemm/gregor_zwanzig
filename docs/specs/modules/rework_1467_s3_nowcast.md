---
entity_id: rework_1467_s3_nowcast
type: refactor
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [alerts, trip, compare, epic-1458, issue-1467, s3, nowcast]
---

# Nowcast-Alarm: gemeinsame Freigabe-Steuerung für Trip und Ortsvergleich (Issue #1467 Scheibe S3, Epic #1458 Teil 2)

## Approval

- [x] Approved — PO-„go" 2026-08-08 (Beleg: Issue-Kommentar zu #1467)

## Purpose

Der Ortsvergleich-Nowcast-Alarm (Regen-/Gewitter-Onset, `compare_radar_alert.py`) läuft
heute an drei Stellen unbegründet anders als sein Trip-Gegenstück
(`trip_alert.py::check_radar_alerts`): er kennt **keine Tages-Obergrenze** (die Bremse gegen
Meldungsfluten fehlt vollständig), führt seine Sperrzeit in einer **eigenen, ungesicherten
Datei** (`compare_radar_alert_throttle.json`, kein Lock, kein atomarer Write) statt im
geteilten `ThrottleStore`, und prüft die Ruhezeit **nach** statt vor dem Wetterabruf.

Diese Scheibe zieht beide Nowcast-Pfade — Trip UND Ortsvergleich — auf einen gemeinsamen
Freigabe-Baustein (`src/services/alert_gate.py`) mit fester Reihenfolge Ruhezeit → Sperrzeit
→ Tages-Obergrenze. Nutzersichtbarer Gewinn: der Ortsvergleich-Nowcast bekommt die
Tages-Obergrenze, teilt sich die Sperrzeit-Ablage mit dem Trip-Pfad, und beide Pfade
protokollieren künftig, WARUM ein Nowcast-Alarm unterdrückt wurde (Ruhezeit/Sperrzeit/
Tageslimit) — eine seit #1459 vorbereitete, aber bis heute nie geschriebene Information im
Alarm-Protokoll (PO-Entscheidung 2026-08-08).

Sie ist die **dritte** von vier Scheiben in #1467 (S1 live, S2 vollständig live) und betrifft
ausschließlich den Nowcast-Pfad. Der Δ-Wetter-Pfad (S2) und die amtliche Warnung (S4) werden
**nicht** angefasst.

**Leitsatz, unverändert aus S1/S2 übernommen:** Der gefährlichste Fehler ist der ausbleibende
Alarm. Zielmarke ist „Verhalten unverändert", außer den ausdrücklich in dieser Spec benannten
Änderungen — hier: Tages-Obergrenze (neu, wirksam), geteilte Sperrzeit-Ablage, vorgezogene
Ruhezeit-Prüfung, Unterdrückungs-Protokollierung.

## Source

- **File:** `src/services/compare_radar_alert.py`
- **Identifier:** `class CompareRadarAlertService`, Methode `_check_one_preset()`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`). Kein Go-Code, kein
Frontend-Code — belegt: kein Treffer für `compare_radar_alert`/`radar_alert_throttle` in
`internal/` oder `frontend/src/`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `rework_1467_s2_aenderungsalarm` | module | Vorgänger-Scheibe (live) — liefert `compare_alert_guard.is_silenced`, `compare_alert_channels.effective_compare_channels`, beide bereits an dieser Datei verdrahtet und in dieser Scheibe unangetastet |
| `rework_1467_s1_alarm_kennung` | module | `entity_id`/`entity_type` in `alert_log.append_entry()` sind hier bereits Pflicht |
| `ThrottleStore` | module | Zielspeicher der Sperrzeit — neuer Scope `compare_radar` |
| `alert_daily_limit` | module | Tages-Obergrenze, geteilter Zähler über alle Trips/Presets und Alarm-Gründe |
| `fix_1555_nowcast_alert_priority` | module | Reserve-Mechanik `_FORECAST_CHANGE_RESERVE` — Vorrang-Schutz, den der Ortsvergleich-Nowcast erben MUSS |
| `DeviationAlertEngine` | module | `is_quiet_hours()` — geteilte Ruhezeit-Prüfung, wird vom neuen Baustein unverändert durchgereicht |
| `fix_1479_ruhezeit_wurzel` | module | AC-11 dort: kein eigenes `try/except` um `is_quiet_hours()` in `compare_radar_alert.py` |
| `AlertStateService` | module | Melde-Gedächtnis je Ort — unverändert |
| `feat_1459_alert_protokoll` | module | Protokoll-Format; `REASON_QUIET_HOURS`/`REASON_DAILY_LIMIT`/`REASON_COOLDOWN` werden hier erstmals scharf geschaltet |
| `NotificationService` | module | Kanal-Fan-out — unverändert |

## Estimated Scope

- **LoC:** ~180–240 Produktivcode (Baustein `alert_gate.py` ~70–90, Compare-Umbau netto
  ~+20–40, Trip-Umbau netto ~−10, Unterdrückungs-Protokollierung ~+30–50, Docstring-Ergänzung
  `throttle_store.py` ~2). Passt unter das 250er-Budget, liegt aber nah an der Grenze.
  **Rückfallebene, falls es eng wird:** die Unterdrückungs-Protokollierung (d) wird als
  eigener, unmittelbar folgender Arbeitsgang ausgeliefert — nicht der Kern (a)/(b)/(c), der
  die eigentliche Verhaltensangleichung trägt.
- **Files:** 1 neu (`alert_gate.py`), 3 Produktiv geändert
  (`compare_radar_alert.py`, `trip_alert.py`, `throttle_store.py`-Docstring), ~5 Testdateien
  geändert/neu, 1 ADR-Nachtrag.
- **Effort:** high — ein Baustein mit zwei Verbrauchern, hohes Regressionsrisiko.
- **Risiko:** HOCH — jeder Fehler im Baustein unterdrückt *alle* Nowcast-Alarme beider Pfade
  (Trip und Ortsvergleich gleichzeitig). Genau die Bugklasse, gegen die der `ThrottleStore`
  einst gebaut wurde.

## Ist-Stand (gemessen 2026-08-08)

| | Trip (`trip_alert.py:701-938`) | Ortsvergleich (`compare_radar_alert.py:85-178`) |
|---|---|---|
| **Reihenfolge** | Ruhezeit → Sperrzeit → **Tageslimit** → Abruf → Erkennung | Riegel (Pausiert/Archiviert) → Sperrzeit → **Abruf + Erkennung** → Ruhezeit |
| **Sperrzeit** | `ThrottleStore`, Scope `"radar"`, Key `trip.id`, `fcntl`-Lock, atomar | eigene Datei `compare_radar_alert_throttle.json`, flaches `{preset_id: iso}`, **kein Lock, kein atomarer Write** |
| **Tages-Obergrenze** | `is_allowed(…, reason="nowcast")`, `increment()` nach Zustellung | **fehlt vollständig** — Modul nicht importiert |
| **Unterdrückungs-Protokoll** | keins | keins |

Bereits geteilt und **nicht** Gegenstand dieser Scheibe: `is_silenced` (Pausiert/Archiviert-
Riegel, S2 AG6), `effective_compare_channels` (S2 AG1), `radar_alert_due`,
`DeviationAlertEngine.is_quiet_hours`, `AlertStateService`, `alert_log.append_entry`
(`entity_id`/`entity_type` seit S1), `NotificationService.send_multi_location_radar_alert`,
Dringlichkeit + Kanal-Schwelle (#1461 S3a/S3b).

## Implementation Details

### Ein geteilter Freigabe-Baustein, von Anfang an mit beiden Nowcast-Pfaden verdrahtet

Neues Modul `src/services/alert_gate.py`. Vorgeschlagene, in der Umsetzung präzisierbare
Schnittstelle:

```
class GateResult(NamedTuple):
    allowed: bool
    reason: Optional[str]   # REASON_QUIET_HOURS | REASON_COOLDOWN | REASON_DAILY_LIMIT

def check_nowcast_gate(*, user_id, throttle_scope, throttle_key, cooldown_minutes,
                       quiet_from, quiet_to, context_label, now,
                       daily_limit_reason="nowcast", throttle_store=None) -> GateResult

def record_nowcast_sent(*, user_id, throttle_scope, throttle_key, now,
                        throttle_store=None) -> None
```

Feste, in dieser Reihenfolge geprüfte Abfolge — 1:1 nach der Trip-Vorlage
(`trip_alert.py:748-765`): **Ruhezeit → Sperrzeit → Tages-Obergrenze**, Abbruch beim ersten
Treffer. `check_nowcast_gate` reicht `is_quiet_hours` **unverändert durch** — kein eigenes
`try/except` um den Aufruf (`fix_1479_ruhezeit_wurzel` AC-11, AST-Wächter
`tests/tdd/test_alert_quiet_hours_robustness.py`). `record_nowcast_sent` bündelt
`ThrottleStore.record()` und `alert_daily_limit.increment()` und wird **ausschließlich nach
erfolgreicher Zustellung** gerufen — genau wie heute an beiden Bestandsstellen
(`trip_alert.py:930/935`, `compare_radar_alert.py:175-177`).

**Warum beide Verbraucher sofort, nicht erst der Ortsvergleich:** ein Baustein mit genau
einem Aufrufer ist keine Entdopplung, sondern eine dritte Fassung derselben Abfolge — das
Issue-Ziel lautet Zusammenlegen, nicht Danebenlegen. Hausmuster S2 AG1: dort wurden beide
Bestandsstellen des Kanal-Resolvers sofort zu dünnen Wrappern, der Trip-Radar-Zweig verliert
netto ~18 Zeilen Inline-Logik.

### (a) Tages-Obergrenze

`compare_radar_alert.py::_check_one_preset` ruft `check_nowcast_gate(..., daily_limit_reason=
"nowcast")` — exakt dieselbe Prüfung wie der Trip-Nowcast. Der Ortsvergleich erbt damit den
Vorrang-Schutz aus #1555: `alert_daily_limit.is_allowed(..., reason="nowcast")` prüft gegen
das **volle** Limit, die Reserve (`_FORECAST_CHANGE_RESERVE`) kappt ausschließlich
`reason="forecast_change"`. Ein Compare-eigener Grund (z. B. `"compare_nowcast"`) würde diesen
Schutz still verlieren — das ist die gefährlichste Falle dieser Scheibe (Randbedingung 5,
eigenes AC).

### (b) Geteilte Sperrzeit statt eigene Datei

Neuer Scope `"compare_radar"` im `ThrottleStore`, Schlüssel = `preset_id`.

- **Nicht `"radar"`**: dieser Scope ist ausschließlich mit **Trip**-IDs belegt. Seit dem
  #1250-Cutover liegen Trips und Ortsvergleiche im selben Verzeichnis `briefings/<id>.json`,
  unterschieden nur durch `kind`; IDs sind frei gewählte Slugs, keine UUIDs ⇒ Kollision ist
  real möglich.
- **Nicht `"compare_preset"`**: dieser Scope ist bereits vom Änderungsalarm (S2) auf
  **demselben** `preset_id`-Schlüssel belegt. Wiederverwendung würde
  `tests/tdd/test_alert_log_compare_and_tenancy.py::test_ac12_ortsvergleich_protokolliert_alle_drei_ausloeser`
  rot machen — dort löst ein Preset im selben Lauf Δ-, Nowcast- und amtlichen Alarm aus und
  erwartet `(1,1,1)` unabhängig gezählte Alarme.

`compare_radar_alert.py` verliert `_load_throttle_times()`/`_save_throttle_times()` und den
Konstruktor-Pfad `self._throttle_file`; die Sperrzeit-Prüfung läuft ausschließlich über den
Baustein.

**Altdaten:** bewusster Verzicht auf Migration. `ThrottleStore._migrate_if_needed()` bricht
ab, sobald `throttle_state.json` bereits existiert — bei allen drei realen Nutzern der Fall.
Eine zusätzliche Legacy-Konstante wäre totes Gerüst; der real existierende Alteintrag
(`henning`, `cp-eb6ba0b239d90e37`, 25.07., längst außerhalb jedes Cooldowns) bleibt in der
Altdatei liegen und wirkt nicht mehr. Die Altdatei wird nicht mehr geschrieben und nicht
gelöscht.

### (c) Ruhezeit vor Datenbeschaffung

Die Ruhezeit-Prüfung (heute `compare_radar_alert.py:117-124`, NACH
`_detect_triggered_locations()`) wandert in den Baustein und läuft damit VOR dem Nowcast-Abruf
— Muster `compare_official_alert.py:105-113`. Das Meldeverhalten bleibt gleich: in beiden
Fällen (alt: nach Erkennung unterdrückt, neu: vor Abruf gar nicht erst geprüft) geht während
der Ruhezeit kein Alarm raus. Was sich ändert, ist ausschließlich der Kontingentverbrauch —
und auch das nur bedingt (s. Known Limitations).

**Zwei archivierte Zusicherungen werden dadurch abgelöst** und fallen mit dieser Scheibe:
`docs/specs/_archive/modules/issue_1041b_compare_radar_alert_service.md` AC-5 und
`docs/specs/_archive/modules/issue_1041_compare_radar_alert.md` AC-6 sichern „wird der Onset
erkannt, der Alarm aber unterdrückt" zu. Mit dem Vorziehen kann während der Ruhezeit kein
Onset mehr erkannt werden — die Ablösung ist beabsichtigt und hier dokumentiert (Archivablage
sagt nichts über Gültigkeit; die Umkehrung ist eine bewusste Entscheidung dieser Scheibe).

### (d) Unterdrückungen protokollieren (PO-Entscheidung 2026-08-08)

Wird ein Nowcast-Lauf (Trip ODER Ortsvergleich) für eine Entität vom Baustein an einer der
drei Stufen abgewiesen (`GateResult.allowed == False`), entsteht dafür GENAU EIN Eintrag im
Alarm-Protokoll mit dem entsprechenden Grund — unabhängig davon, ob zum Zeitpunkt der
Abweisung überhaupt ein Onset vorläge (das ist zu diesem Zeitpunkt strukturell noch nicht
bekannt, da die Erkennung erst nach dem Gate läuft, s. (c)). Die drei Konstanten
`REASON_QUIET_HOURS`, `REASON_COOLDOWN`, `REASON_DAILY_LIMIT` (`alert_log.py:47-49`) sind seit
#1459 dokumentiert, aber repo-weit unbenutzt — diese Scheibe schaltet sie erstmals scharf.

**Geltungsbereich strikt auf die beiden Nowcast-Pfade begrenzt:** `trip_alert.py::
check_radar_alerts` und `compare_radar_alert.py::_check_one_preset`. Der Vorhersage-
Änderungsalarm (S2) und die amtliche Warnung (S4) protokollieren Unterdrückungen weiterhin
NICHT — das bleibt eine offene Lücke dort (dokumentiert in `feat_1459_alert_protokoll.md`
Known Limitations, Punkt O3) und wird durch diese Scheibe nicht geschlossen.

Der bestehende Schreibpfad `alert_log.append_entry()` ist auf tatsächliche Zustellversuche
zugeschnitten (`changes_count`, `severity`, `metrics`, Kanal-Aufschlüsselung nach Zustellung)
und passt nicht 1:1 auf eine Vor-Abruf-Abweisung, bei der weder Schweregrad noch betroffene
Metrik bekannt sind. Die Umsetzung ergänzt `alert_log.py` um einen zweiten, schlanken
Schreibpfad für genau diesen Fall (alle `effective_channels` der Entität erhalten denselben
Gate-Grund als `channels_not_sent`-Eintrag, Ziel-Liste `not_delivered` — Go liest diese
Liste ohnehin nicht, Cockpit-Kachel und Archiv-Statistik bleiben unverändert). Die genaue
Funktionssignatur ist Implementierungsdetail; verbindlich ist die beobachtbare Wirkung in den
Acceptance Criteria.

## Invarianten

- **Der gefährlichste Fehler ist der ausbleibende Alarm.** Zielmarke: Verhalten unverändert
  außer den ausdrücklich benannten Punkten (a)–(d).
- **Reihenfolge im Baustein ist fest:** Ruhezeit → Sperrzeit → Tages-Obergrenze, Abbruch beim
  ersten Treffer.
- **Zähler-Reihenfolge:** `record_nowcast_sent()` (bündelt `increment()` + `record()`) läuft
  NIEMALS vor der erfolgreichen Zustellung.
- **Vorrang-Schutz aus #1555 bleibt erhalten:** der Ortsvergleich-Nowcast prüft mit
  `reason="nowcast"` gegen das volle Tageslimit, nie gegen ein Compare-eigenes, reduziertes
  Limit.
- Mandantentrennung: jeder Teil mit ZWEI verschiedenen Nutzern verifiziert, `user_id` nie auf
  `"default"` zurückfallen lassen.
- Datenbeschaffung wird NICHT fusioniert — Trip und Ortsvergleich holen weiterhin getrennt
  Wetter.
- Bestandsdaten: Read-Modify-Write mit Merge, nie Replace.
- Testpolitik: kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis.
- Testdateien nach VERHALTEN benennen, nie nach Issue-Nummer.

## Nicht-Ziele / bewusst unverändert

- **#1594 (nächster geplanter Versandzeitpunkt) wird NICHT mitgebaut.** Der Freigabe-Baustein
  ist der spätere Andockpunkt, liefert diese Information in dieser Scheibe aber noch nicht.
- **Datenbeschaffung wird nicht fusioniert** — Trip und Ortsvergleich holen weiterhin über
  getrennte Aufrufe Wetter.
- **Vorhersage-Änderungsalarm (S2) und amtliche Warnung (S4) bleiben unberührt** — insbesondere
  bekommen sie durch diese Scheibe KEINE Unterdrückungs-Protokollierung (Geltungsbereich von
  (d) ist strikt auf die beiden Nowcast-Pfade begrenzt).
- **Keine Migration der Altdatei** `compare_radar_alert_throttle.json` — sie bleibt
  unangetastet liegen, wird aber nicht mehr geschrieben oder gelesen.
- **Handversand-Sonderregeln unverändert.** `compare_radar_alert.py` hat keinen eigenen
  Handversand-Endpunkt (anders als der Δ-Wetter-Pfad, S2 AG5) — diese Scheibe führt keinen ein
  und ändert am `on_demand`-Konzept nichts.
- **Kein neuer Go-Endpunkt, kein neuer Cron-Job** — `api/routers/scheduler.py:80-97` und
  `internal/scheduler/scheduler.go:305-324` bleiben unangetastet.
- **Kein Frontend-Code.**

## Risiken

| | Risiko | Test, der es fängt |
|---|---|---|
| **R1** | Fehler im Baustein unterdrückt alle Nowcast-Alarme beider Pfade gleichzeitig (Trip UND Ortsvergleich) — die Bugklasse, gegen die der `ThrottleStore` einst gebaut wurde | AC-11 (Reihenfolge), AC-16 (Trip-Zustellverhalten unverändert), Gate-Stufen einzeln bewacht |
| **R2** | Ein Compare-eigener Tageslimit-Grund verliert still den #1555-Vorrang-Schutz | AC-12 |
| **R3** | `increment`/`record` vor statt nach der Zustellung bucht fehlgeschlagene Versuche als verbraucht | AC-13 |
| **R4** | Scope-Kollision bei falscher Schlüsselwahl (`"radar"` oder `"compare_preset"` statt `"compare_radar"`) | AC-14 (Scope-Trennung, Bestandswächter `test_ac12_…`) |
| **R5** | Ruhezeit-Vorziehen kippt zwei archivierte ACs (#1041/#1041b) unbemerkt — Meldeverhalten muss gleich bleiben | AC-5 |
| **R6** | Struktur-Wächter (`tests/test_success_status_guard.py`, `tests/test_resolution_loss_guard.py`) verankern `compare_radar_alert.py` per Ordinal — ein zusätzlicher Riegel verschiebt die Zählung | Wächter-Lauf nach der Umsetzung; bei Verschiebung Ordinal-Schlüssel nachziehen, Wächter nicht aufweichen |
| **R7** | Mandantentrennung — Zähler/Sperrzeit unter `data/users/<user_id>/` müssen strikt getrennt bleiben | AC-15 |
| **R8** | Bestandstests (`test_data_root_migration_services.py`, `test_compare_radar_alert.py` AC-7) messen an der abgelösten Datei und werden ohne Anpassung fälschlich rot | Messpunkt wandert auf `throttle_state.json`, Zusicherung bleibt inhaltlich erhalten |

## Test-Plan

Kern-Schicht (deterministisch, kein Netz) sofern nicht anders vermerkt.

| AC | Datei | Schicht |
|---|---|---|
| AC-1 (a) | `tests/tdd/test_compare_radar_alert_daily_limit.py` (neu) | Kern |
| AC-2, AC-3 (b) | `tests/tdd/test_compare_radar_alert_shared_throttle.py` (neu) | Kern |
| AC-4, AC-5 (c) | `tests/tdd/test_compare_radar_alert_quiet_hours_precedes_fetch.py` (neu, Muster analog S2 AG2) | Kern |
| AC-6, AC-7, AC-8, AC-9 (d, Ortsvergleich + Geltungsbereich) | `tests/tdd/test_nowcast_suppression_logging.py` (neu) | Kern |
| AC-10 (d, Trip) | `tests/tdd/test_nowcast_suppression_logging.py` (neu, gleiche Datei, Trip-Fälle) | Kern |
| AC-11 (Reihenfolge) | `tests/tdd/test_alert_gate.py` (neu) | Kern |
| AC-12 (Vorrang-Schutz) | `tests/tdd/test_alert_gate.py` (neu) | Kern |
| AC-13 (Zähler-Invariante) | `tests/tdd/test_alert_gate.py` (neu) | Kern |
| AC-14 (Scope-Trennung) | `tests/tdd/test_alert_log_compare_and_tenancy.py` (Bestand, MUSS unverändert grün bleiben) | Kern |
| AC-15 (Mandantentrennung) | `tests/tdd/test_alert_gate.py` (neu, zwei Nutzer-Kontexte) | Kern |
| AC-16 (Trip-Zustellverhalten unverändert) | `tests/tdd/test_trip_radar_nowcast_gate_migration.py` (neu) | Kern |
| Pflicht-Nachzug (kein eigenes AC) | `tests/tdd/test_data_root_migration_services.py:74-82` (Messpunkt `throttle_state.json` statt `compare_radar_alert_throttle.json`) | Kern |
| Pflicht-Nachzug (kein eigenes AC) | `tests/tdd/test_compare_radar_alert.py:688-693` (AC-7 dort, Messpunkt gewandelt) | Kern |
| Regression | `tests/test_success_status_guard.py`, `tests/test_resolution_loss_guard.py` gezielt laufen lassen; bei Ordinal-Verschiebung Schlüssel nachziehen | Kern |

Live-E2E: keine eigenen Live-Marker-Tests vorgesehen — Nowcast ist live schwer provozierbar
(echter Regen-/Gewitter-Onset ≤20 Min, R6 aus der Analyse). Staging-Nachweis erfolgt über den
ausgelieferten Code + gezielt gesetzte Zustandsdateien (Rezept aus S2 AG5/AG6), nicht über
„auf Regen warten".

## Acceptance Criteria

**(a) Tages-Obergrenze**

- **AC-1:** Given ein Ortsvergleich-Nutzer, dessen Tages-Obergrenze für Alarme bereits erreicht
  ist (z. B. durch zwei vorangegangene Alarme desselben Tages), When für ein Preset dieses
  Nutzers ein Nowcast-Onset eintritt, Then wird KEIN Nowcast-Alarm für den Ortsvergleich
  versendet — vor dieser Scheibe wäre er versendet worden, da keine Tages-Obergrenze geprüft
  wurde.
  - Test: Tageszähler auf das Limit vorbelegen, Onset-Bedingung erfüllen, keine Zustellung auf
    keinem Kanal, Protokoll bleibt ohne neuen Zustellungs-Eintrag.

**(b) Geteilte Sperrzeit**

- **AC-2:** Given ein Ortsvergleich-Preset, dessen letzter Nowcast-Alarm vor Kurzem über den
  geteilten `ThrottleStore` (Scope `compare_radar`) vermerkt wurde und dessen Cooldown noch
  läuft, When ein erneuter Onset für dasselbe Preset eintritt, Then bleibt der Alarm
  unterdrückt — die Sperrzeit wirkt aus dem geteilten Speicher, nicht mehr aus einer
  presetseigenen Datei.
  - Test: Eintrag über `ThrottleStore.record("compare_radar", preset_id, …)` setzen, Onset
    auslösen, keine Zustellung.

- **AC-3:** Given ein Eintrag ausschließlich in der alten Datei
  `compare_radar_alert_throttle.json` (kein entsprechender Eintrag im `ThrottleStore`), When
  ein Onset für dasselbe Preset eintritt, Then wird der Alarm zugestellt — die Altdatei
  entfaltet keine Sperrwirkung mehr, wie bewusst entschieden (kein Migrationsmechanismus).
  - Test: Alte Datei mit frischem Sperrzeit-Eintrag vorbelegen, `ThrottleStore` leer lassen,
    Onset auslösen, Zustellung erfolgt trotz „alter" Sperre.

**(c) Ruhezeit vor Datenbeschaffung**

- **AC-4:** Given ein Ortsvergleich-Preset mit aktiver Ruhezeit zur aktuellen Ortszeit, When
  `CompareRadarAlertService.check_all_compare_presets()` läuft, Then wird für keinen Ort
  dieses Presets ein Nowcast-Abruf (`get_nowcast`) ausgelöst — 0 Aufrufe.
  - Test: Fetch-Spion (Zähl-Seam) auf den Radar-Service, Aufrufzähler nach dem Lauf bei 0.

- **AC-5:** Given identische Ruhezeit-Bedingungen vor und nach dieser Scheibe, When ein
  Nowcast-Onset während der Ruhezeit einträte, Then bleibt der Alarm in beiden Fällen
  gleichermaßen aus — kein Alarm, der vorher unterdrückt wurde, geht jetzt durch, und
  umgekehrt geht kein zuvor zugestellter Alarm jetzt verloren.
  - Test: Szenario mit Ruhezeit AUS und Onset ⇒ Zustellung; Szenario mit Ruhezeit AN und
    identischem Onset ⇒ keine Zustellung — beide Fälle vor und nach dem Umbau identisch.

**(d) Unterdrückungen protokollieren**

- **AC-6:** Given ein Ortsvergleich-Preset, dessen Nowcast-Lauf an der Ruhezeit scheitert,
  When der Lauf beendet ist, Then enthält das Alarm-Protokoll des Nutzers für dieses Preset
  einen Eintrag mit dem Unterdrückungs-Grund „Ruhezeit" (`REASON_QUIET_HOURS`).
  - Test: Ruhezeit erzwingen, Lauf ausführen, `alert_log.json` laden, passenden
    `not_delivered`-Eintrag mit dem Grund finden.

- **AC-7:** Given ein Ortsvergleich-Preset, dessen Nowcast-Lauf an der Sperrzeit scheitert,
  When der Lauf beendet ist, Then enthält das Alarm-Protokoll einen Eintrag mit dem
  Unterdrückungs-Grund „Sperrzeit" (`REASON_COOLDOWN`).
  - Test: aktiven `ThrottleStore`-Eintrag setzen, Lauf ausführen, Protokoll prüfen.

- **AC-8:** Given ein Ortsvergleich-Nutzer, dessen Tages-Obergrenze erreicht ist, When ein
  Nowcast-Lauf für ein Preset dieses Nutzers deswegen unterdrückt wird, Then enthält das
  Alarm-Protokoll einen Eintrag mit dem Unterdrückungs-Grund „Tages-Obergrenze"
  (`REASON_DAILY_LIMIT`).
  - Test: Tageszähler auf Limit vorbelegen, Lauf ausführen, Protokoll prüfen.

- **AC-9:** Given ein Vorhersage-Änderungsalarm oder ein amtlicher Alarm, der durch Ruhezeit,
  Sperrzeit oder Tages-Obergrenze unterdrückt wird, When der jeweilige Lauf beendet ist, Then
  entsteht dafür KEIN Protokolleintrag mit den drei neuen Unterdrückungsgründen — der
  Geltungsbereich dieser Scheibe bleibt strikt auf die beiden Nowcast-Pfade begrenzt.
  - Test: Δ-Wetter-Lauf bzw. amtlicher Lauf mit erzwungener Unterdrückung, Protokoll enthält
    keinen neuen Eintrag mit `quiet_hours`/`cooldown`/`daily_limit` als Grund aus diesen Pfaden.

- **AC-10:** Given ein Trip, dessen Nowcast-Lauf an Ruhezeit, Sperrzeit oder Tages-Obergrenze
  scheitert, When der Lauf beendet ist, Then enthält das Alarm-Protokoll — anders als vor
  dieser Scheibe — einen Eintrag mit dem jeweiligen Unterdrückungs-Grund. Der Trip-Nowcast-Pfad
  bekommt die Protokollierung gleichermaßen wie der Ortsvergleich.
  - Test: je eine der drei Bedingungen erzwingen, `check_radar_alerts()` laufen lassen,
    Protokoll prüfen.

**Reihenfolge, Vorrang-Schutz, Zähler-Invariante**

- **AC-11:** Given eine Konstellation, in der sowohl Ruhezeit als auch Sperrzeit gleichzeitig
  zuträfen, When der Freigabe-Baustein geprüft wird, Then stoppt der Ablauf an der Ruhezeit —
  die Sperrzeit-Prüfung wird für diesen Aufruf nicht erreicht (nachgewiesen über einen
  Aufrufzähler auf der Sperrzeit-Prüfung).
  - Test: Ruhezeit AN + Sperrzeit-Bedingung erfüllt, Aufrufzähler der Sperrzeit-Prüfung bleibt
    bei 0.

- **AC-12:** Given einen Ortsvergleich-Nutzer mit endlichem Tageslimit, dessen Restbudget nur
  noch innerhalb der #1555-Reserve für `reason="forecast_change"` liegt (z. B. Limit 2,
  Reserve 1, ein Platz belegt), When ein Ortsvergleich-Nowcast-Onset eintritt, Then wird der
  Nowcast-Alarm trotzdem zugestellt — der Ortsvergleich-Nowcast prüft wie der Trip-Nowcast
  gegen das VOLLE Tageslimit, nicht gegen ein durch die Reserve reduziertes.
  - Test: Tier mit Limit 2 (Reserve 1), einen Alarm-Slot verbrauchen, Ortsvergleich-Nowcast
    auslösen, Zustellung erfolgt trotz „nur noch Reserve-Platz frei".

- **AC-13:** Given einen Nowcast-Alarm-Versuch, bei dem die tatsächliche Zustellung fehlschlägt
  (kein Kanal erreichbar), When der Lauf beendet ist, Then sind weder der Sperrzeit-Eintrag im
  `ThrottleStore` noch der Tageszähler für diese Entität erhöht worden.
  - Test: alle Kanäle unerreichbar simulieren, Onset auslösen, Zähler-Snapshot vor/nach dem
    Lauf vergleichen — exakte Gleichheit.

**Scope-Trennung, Mandantentrennung, Trip-Unveränderlichkeit**

- **AC-14:** Given ein Ortsvergleich-Preset, das im selben Lauf einen Änderungsalarm, einen
  Nowcast-Alarm und einen amtlichen Alarm auslöst, When alle drei Checker nacheinander laufen,
  Then werden alle drei unabhängig gezählt — keiner unterdrückt fälschlich einen anderen über
  eine geteilte Sperrzeit-Ablage.
  - Test: `tests/tdd/test_alert_log_compare_and_tenancy.py::
    test_ac12_ortsvergleich_protokolliert_alle_drei_ausloeser` bleibt nach dem Umbau
    unverändert grün, Ergebnis weiterhin `(1, 1, 1)`.

- **AC-15:** Given zwei verschiedene Nutzer mit je einem Ortsvergleich-Preset gleicher
  Kennung, deren Sperrzeit- und Tageslimit-Zustand unabhängig geführt wird, When beide
  unabhängig voneinander einen Nowcast-Onset auslösen, Then wirkt weder die Sperrzeit noch das
  Tageslimit des einen Nutzers auf den anderen.
  - Test: zwei Datenverzeichnisse (`user_id` A/B), gleiche Preset-Kennung, Onset für A
    unterdrückt Alarm für A, Alarm für B geht trotzdem durch.

- **AC-16:** Given den Trip-Radar-Nowcast-Pfad, When identische Szenarien (Ruhezeit an/aus,
  Sperrzeit an/aus, Tageslimit erreicht/nicht erreicht, jeweils mit auslösendem Onset) vor und
  nach dem Umklemmen auf den geteilten Baustein durchlaufen werden, Then bleibt die
  Zustellentscheidung (versendet ja/nein, welcher Kanal) in jedem Szenario identisch zum Stand
  vor dieser Scheibe — einzige neue Wirkung für den Trip ist die Protokollierung aus (d),
  AC-10.
  - Test: Szenario-Matrix (4 Kombinationen) vor/nach dem Umbau vergleichen, Zustellergebnis je
    Szenario bit-identisch.
  - Mutations-Gegenprobe (Pflicht): Reihenfolge im Baustein vertauschen (Sperrzeit vor
    Ruhezeit) · `record_nowcast_sent` vor statt nach der Zustellung aufrufen · Scope
    `compare_radar` durch `radar` ersetzen — jede dieser drei Verfälschungen MUSS mindestens
    einen der obigen Tests rot machen.

## Known Limitations

**Nachtrag nach der RED-Phase (2026-08-08, am Ist-Code gemessen — ändert kein AC):**

- **Ein Preset ohne jeden aktiven Kanal bekommt auch keinen Unterdrückungs-Eintrag.**
  `alert_log.append_entry()` steigt bei leerem `effective_channels` wortlos aus
  (`alert_log.py:190-192`). Das ist Bestandsverhalten und bleibt so; für (d) heißt es, dass die
  Frage „warum kam kein Alarm?" für ein kanalloses Preset weiterhin unbeantwortet bleibt.
- **Die Kanalauflösung muss für (d) vorgezogen werden.** `effective_compare_channels()` steht
  heute erst **nach** der Erkennung (`compare_radar_alert.py:133`), der Unterdrückungs-Eintrag
  braucht die Kanäle aber bereits am Gate. Die Funktion ist rein und nebenwirkungsfrei, das
  Vorziehen ist gefahrlos — es ist aber eine bewusste Änderung, keine Nebensache.
- **Im Nowcast-Pfad entstehen zwei Sorten `not_delivered`-Einträge.** Schon heute schreibt der
  Compare-Nowcast bei gescheiterter Zustellung einen Eintrag mit `reason="nowcast"`, weil der
  `append_entry`-Aufruf vor dem `notif_result.sent`-Guard steht. Die neuen Gate-Einträge sind
  davon strikt zu unterscheiden (Filter auf die drei Gate-Konstanten).
- **Risiko R3 der Analyse ist gegenstandslos:** `_finalize_triggered_state()` (Melde-Gedächtnis)
  wird auch heute nur nach erfolgreicher Zustellung gerufen — das Vorziehen der Ruhezeit hat
  darauf keinen Seiteneffekt. Gemessen, nicht angenommen.

- **Tages-Obergrenze wirkt nicht für `tier: premium`.** `daily_alert_limit()` liefert dort
  `None`, `is_allowed()` gibt dann immer `True` zurück. Von den drei realen Konten ist eines
  premium — für dieses Konto bleibt der Nowcast-Alarmfluss unbegrenzt, wie beim Trip-Pfad
  auch.
- **Die Kontingent-Ersparnis von (c) tritt nur bei einem echten Cache-Fehltreffer im
  open-meteo-Zweig ein.** `get_nowcast` trifft häufig den geteilten Cache (TTL 300 s) — ein
  Treffer kostet ohnehin nichts. RADOLAN/INCA/DPC sind ungegatet. Die messbare Wirkung von (c)
  ist damit primär das unveränderte Meldeverhalten, die Kontingent-Ersparnis ein Nebeneffekt
  mit begrenzter Reichweite.
- **Ein Rückbau der Entdopplung (Baustein → wieder zwei getrennte Fassungen) ist mit
  Verhaltenstests grundsätzlich nicht fangbar** — beide Fassungen könnten sich weiterhin
  identisch verhalten. Der strukturelle Schutz liegt außerhalb dieser Spec (Code-Review,
  Pendant-Gate #1481 B greift hier nicht, da kein neues einseitiges Compare-/Trip-Verzeichnis
  entsteht).
- **Altdaten der abgelösten Datei bleiben dauerhaft ungenutzt liegen.** Kein Löschen, keine
  Migration — der einzige reale Alteintrag (`henning`, 25.07.) ist längst außerhalb jedes
  Cooldowns und damit folgenlos.
- **#1594 (nächster geplanter Versandzeitpunkt) bleibt offen.** Der Baustein ist der spätere
  Andockpunkt, liefert diese Information noch nicht.
- **Struktur-Wächter können nach der Umsetzung nachzuziehen sein** — `compare_radar_alert.py`
  ist per `datei::funktion::ordinal` in `tests/test_success_status_guard.py` und
  `tests/test_resolution_loss_guard.py` verankert; verschiebt der Baustein-Aufruf die
  Ordinal-Zählung, sind die Wächter-Schlüssel anzupassen, nicht die Wächter selbst
  aufzuweichen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilter Auswertungskern) bekommt einen **Nachtrag**.
  Dessen bisheriger Satz „Tageslimit … bleiben unverändert Trip-spezifisch (kein
  Compare-Bedarf bekannt)" ist durch diese Scheibe sachlich überholt und wird auf „Tageslimit
  gilt seit #1467 S3 gemeinsam für Trip- und Ortsvergleich-Nowcast, über den geteilten
  Freigabe-Baustein `alert_gate.py`" fortgeschrieben.
- **Rationale:** Die Ablaufsteuerung bleibt im Muster von ADR-0021 — Ortsvergleich zieht an
  den bestehenden Trip-Ablauf heran, ergänzt um einen echten Sammelbaustein, statt eine
  Compare-eigene Zweitfassung fortzuführen. Kein neues Architekturprinzip, nur konsequente
  Anwendung des bestehenden auf den letzten noch abweichenden Pfad.

## Nachträge

- **Nachtrag (Issue #2065, 2026-08-22):** die feste Reihenfolge des Bausteins bleibt
  Ruhezeit → Sperrzeit → Tages-Obergrenze, und `check_nowcast_gate()` bleibt in
  Signatur UND Verhalten unverändert. Neu ist, was der **Trip-Zweig** mit dem
  Ergebnis `REASON_COOLDOWN` macht: er hält nicht mehr sofort an, sondern holt den
  Nowcast (weiterhin **genau EIN** `get_nowcast`-Abruf je Trip, #1329) und prüft mit
  `alert_gate.radar_overtakes_cooldown()`, ob die gemessene Menge die zuletzt
  gemeldete deutlich übersteigt (≥ 2,0-fach UND ≥ 2,0 mm im 60-Minuten-Fenster).
  Kein Treffer → unverändert Stille mit Protokollgrund `cooldown`. Treffer → der Lauf
  läuft weiter wie im ungesperrten Fall, **inklusive erneuter Prüfung der
  Tages-Obergrenze** (sie wurde wegen des Abbruchs an der Sperrzeit nie erreicht) und
  mit derselben Mengen-Feststellung als `quantitative_escalation` an
  `check_event_identity_gate()`. Die Vergleichsbasis ist die zuletzt gemeldete Menge
  im `ThrottleStore` (`{"at": iso, "precip_mm": float|null}`, Alt-Einträge als reiner
  ISO-String bleiben lesbar); sie wird — wie die Sperrzeit selbst — ausschließlich
  NACH erfolgreicher Zustellung fortgeschrieben (`record_nowcast_sent(precip_mm=…)`,
  F001-Symmetrie). **Ruhezeit (#1955) und Tages-Obergrenze bleiben unbrechbar.** Der
  **Ortsvergleich-Nowcast bleibt unverändert** — er schreibt keine Vergleichsmenge und
  bekommt die Ausnahme nicht (PO-Rückstellung). Details:
  `docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md`, ADR-0021-Nachtrag
  vom selben Tag.

## Changelog

- 2026-08-08: Initiale Spec. Vier Änderungen (a)–(d) nach PO-Entscheidungen E1–E4
  (`docs/context/rework-1467-s3-nowcast.md`) zugeschnitten, geteilter Baustein von Anfang an
  mit beiden Nowcast-Pfaden verdrahtet (Abweichung von der Strategie-Agent-Empfehlung, Analyse
  E1). Zeilenangaben gegen den Ist-Stand vom 2026-08-08 verifiziert.
- 2026-08-22: Nachtrag zu Issue #2065 (Verschärfung überholt die Sperrzeit im Trip-Zweig).
