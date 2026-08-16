---
entity_id: rework_1467_s4a_amtlich
type: refactor
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [alerts, trip, compare, epic-1458, issue-1467, s4a, amtlich]
---

# Amtlicher Alarmpfad: gemeinsame Freigabe-Steuerung für Trip und Ortsvergleich (Issue #1467 Scheibe S4a, Epic #1458 Teil 4a)

## Approval

- [x] Approved — PO-„go" 2026-08-16 (Beleg: Workflow-State `rework-1467-s4a-amtlich`, `phase4_approved`)

## Purpose

Der amtliche Alarmpfad (offizielle Wetterwarnung, z. B. GELB→ORANGE) läuft heute für Trip
und Ortsvergleich durch zwei eigenständige, an mehreren Stellen unbegründet abweichende
Prüfketten (`compare_official_alert.py::_check_one_preset` bzw.
`trip_alert.py::_send_official_alert_only`). Diese Scheibe zieht beide auf denselben
geteilten Freigabe-Baustein `src/services/alert_gate.py`, den S3 bereits für den
Nowcast-Pfad eingeführt hat (`check_nowcast_gate`). Sie ist damit die **vierte** von vier
Scheiben in #1467 — genauer: ihr **erster** Teil (S4a); die Entdopplung nach
Ereignis-Identität (#1744 Scheibe B) folgt als S4b und schließt #1467 erst dann.

Zwei nutzersichtbare Wirkungen sind bewusst gewollt (PO-Entscheidungen E1/E2,
2026-08-16), der Rest der Scheibe hält Verhalten unverändert:

- **E1 (Kernfall):** Der amtliche Trip-Pfad liest den geteilten `ThrottleStore`-Scope
  `"trip"` künftig nicht mehr. Heute unterdrückt ein zugestellter Änderungsalarm eine
  nachfolgende amtliche Eskalation für denselben Trip bis zu 120 Minuten — das ist die
  Wirkung, die das Issue für den Ortsvergleich ausdrücklich ausschließt und die dieser
  Umbau für den Trip nachzieht. Geschrieben wird der Topf weiterhin (siehe Invarianten).
- **E2:** Der Ortsvergleich prüft die Tages-Obergrenze künftig VOR statt nach dem
  Warnungs-Abruf — ein erschöpftes Kontingent kostet dann keinen Fremd-Abruf mehr gegen
  eine Datenquelle, die produktiv bereits an ihr Tageslimit stößt (belegt in
  `docs/specs/modules/warn_service_consumption.md:22-28`,
  `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md`).

Zusätzlich werden die drei wortgleichen Compare-Helfer (`_load_presets()` und
`_notification_service_for()` in `compare_alert.py`, `compare_radar_alert.py`,
`compare_official_alert.py`) zu einer gemeinsamen Fassung zusammengeführt.

**Leitsatz, unverändert aus S1–S3 übernommen:** Der gefährlichste Fehler ist der
ausbleibende Alarm. Zielmarke ist „Verhalten unverändert", außer den ausdrücklich in
dieser Spec benannten Änderungen E1/E2.

## Source

- **File:** `src/services/alert_gate.py`
- **Identifier:** neue Funktion `check_official_alert_gate`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`). Kein Go-Code, kein
Frontend-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `rework_1467_s3_nowcast` | module | Vorgänger-Scheibe (live) — liefert `alert_gate.py`, `GateResult`-Muster, `check_briefing_imminent`; diese Scheibe erweitert dieselbe Datei um eine zweite, unabhängige Funktion |
| `rework_1467_s2_aenderungsalarm` | module | liefert `compare_alert_guard.is_silenced`, `compare_alert_channels.effective_compare_channels`, beide hier unangetastet |
| `ThrottleStore` | module | Sperrzeit-Ablage; Scope `"trip"` bleibt Schreibziel des amtlichen Trip-Pfads, wird aber nicht mehr gelesen |
| `alert_daily_limit` | module | Tages-Obergrenze für amtliche Alarme, geteilter Zähler über Trip und Ortsvergleich |
| `alert_log` | module | `append_entry`, `REASON_*`-Konstanten — bleiben für den amtlichen Pfad unbenutzt (E3) |
| `DeviationAlertEngine.is_quiet_hours` | module | Ruhezeit-Prüfung, wird vom neuen Baustein unverändert durchgereicht |
| `fix_1594_alarm_vorlauf_sperre` | module | `check_briefing_imminent()` — bleibt in beiden Pfaden ein eigener, unveränderter Aufruf |
| `compare_alert_guard.is_silenced` | module | Stilllegungs-Riegel, bleibt Compare-eigen und außerhalb des geteilten Gates |
| `NotificationService` | module | Kanal-Fan-out — unverändert |
| `official_alerts.get_official_alerts_for_location` | module | Warnungs-Abruf; beim Ortsvergleich künftig NACH dem Gate statt davor |

## Estimated Scope

- **LoC produktiv:** ~150–180 (Baustein `check_official_alert_gate` ~40–60,
  `compare_official_alert.py`-Umbau ~+10–20, `trip_alert.py`-Umbau netto ~−15,
  neues Modul `compare_preset_access.py` ~40–60, drei Wrapper-Umbauten in
  `compare_alert.py`/`compare_radar_alert.py`/`compare_official_alert.py` ~−10 je Datei,
  ADR-Nachtrag zählt nicht mit). Passt unter das 250er-Budget.
- **LoC Tests:** ~700–900, **Budget vom PO auf 1000 angehoben** (Begründung: zwei
  kritische Pfade × zwei bewusste Verhaltensänderungen × Mandantentrennungs-Nachweis).
- **Files:** 1 neu (`compare_preset_access.py`), 5 produktiv geändert
  (`alert_gate.py`, `compare_official_alert.py`, `trip_alert.py`, `compare_alert.py`,
  `compare_radar_alert.py`), 1 ADR-Nachtrag, ~6 Testdateien geändert/neu.
- **Effort:** high.
- **Risiko:** HOCH — kritischer amtlicher Alarmpfad, zwei bewusste
  Verhaltensänderungen gleichzeitig in zwei unterschiedlichen Consumern.

## Implementation Details

### Neuer Baustein: `check_official_alert_gate`

```python
def check_official_alert_gate(
    *, user_id: str, quiet_from: Optional[str], quiet_to: Optional[str],
    context_label: str, now: datetime, zone: ZoneInfo,
) -> GateResult:
```

Zwei Stufen, Abbruch bei der ersten: **Ruhezeit → Tages-Obergrenze**. Die Funktion kennt
**keinen** Cooldown-Parameter — anders als bei `check_nowcast_gate` (S3) ist das hier kein
Implementierungsdetail, sondern die zentrale Zusicherung dieser Scheibe: ein amtlicher
Alarm kann strukturell nicht an einem Cooldown scheitern, weil die Funktion gar keinen
kennt (AC-3). `GateResult` (aus S3) wird unverändert wiederverwendet.

### Aufrufstellen

| Pfad | fällt weg | tritt an die Stelle |
|---|---|---|
| `compare_official_alert.py::_check_one_preset` | `:120-136` (Ruhezeit inline), `:163-166` (Tageslimit inline, bisher NACH `_detect()`) | ein `check_official_alert_gate(...)` **an der Stelle der bisherigen Ruhezeit-Prüfung** — also nach `is_silenced` (`:100`), **vor** `check_briefing_imminent` (`:144`) und **vor** `_detect()` (`:159`) — E2 |
| `trip_alert.py::_send_official_alert_only` | `:1485-1487` (Ruhezeit), `:1494-1496` (**Cooldown-Lesen**, Scope `"trip"`), `:1497-1501` (Tageslimit) | ein `check_official_alert_gate(...)` **an der Stelle der bisherigen Ruhezeit-Prüfung** (`:1485`), also **vor** `_is_briefing_imminent` (`:1491`) — E1 |

**Die Ruhezeit bleibt in beiden Pfaden die erste Stufe.** Das ist keine Feinheit: `trip_alert.py`
hält bei `:1487-1490` ausdrücklich fest, dass die Briefing-Sperre aus #1594 „dieselbe Stufe wie im
Aenderungspfad, gleiche Position (nach der Ruhezeit)" einnimmt. Ein Gate-Aufruf **nach** der
Briefing-Sperre würde diese Festlegung still umdrehen. Der Baustein tritt deshalb dorthin, wo heute
die Ruhezeit steht — nicht dahinter.

**Folge, die ausdrücklich genannt gehört:** Weil die Tages-Obergrenze im Baustein steckt, wandert
sie damit in beiden Pfaden **vor** die Briefing-Sperre. Das ist wirkungsfrei, weil `is_allowed()`
rein lesend ist — gebucht wird ausschließlich über `increment()`, und das läuft unverändert erst
nach erfolgreicher Zustellung (AC-15).

`check_briefing_imminent` bleibt in beiden Pfaden ein **eigener** Aufruf, unmittelbar nach dem
Gate (seit #1594 geteilt). `_throttle_store.record("trip", …)` bei `trip_alert.py:1539`
**bleibt bestehen** — nur das Lesen (`:1494`) entfällt, das Schreiben nicht (E1,
Begründung: die harmlose Richtung „ein Änderungsalarm weniger" bleibt unangetastet,
weil das richtige Werkzeug dafür S4b/#1744 B ist, nicht eine pauschale Zeitsperre).
`_is_throttled_with_cooldown` bleibt als Methode bestehen — weiter genutzt vom
Änderungsalarm (`:246`) und von `get_time_until_next_alert`.

### Geteilter Compare-Helfer

Neues Modul `src/services/compare_preset_access.py`:

```python
def load_compare_alert_presets(user_id: str) -> list[ComparePreset]: ...

def notification_service_for_preset(
    settings, user_id: str, preset: ComparePreset, *, log_label: str,
) -> NotificationService: ...
```

Die drei Bestandsmethoden `_load_presets()` und `_notification_service_for()` in
`compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` werden
Ein-Zeiler-Wrapper. `log_label` trägt die einzige echte Abweichung zwischen den drei
Aufrufern (`"Compare-Alert:"` / `"Compare-Alert (Radar):"` / `"Compare-Alert
(amtlich):"`) — dasselbe Parametermuster wie `context_label` in `alert_gate.py`.

## Invarianten

- **Der gefährlichste Fehler ist der ausbleibende Alarm.** Zielmarke: Verhalten
  unverändert außer E1 (Trip-Cooldown-Lesen entfällt) und E2 (Ortsvergleich prüft
  Tageslimit vor dem Abruf).
- **Reihenfolge im Baustein ist fest:** Ruhezeit → Tages-Obergrenze, Abbruch beim ersten
  Treffer. Kein dritter Parameter, keine dritte Stufe.
- **`check_official_alert_gate` kennt keinen Cooldown-Parameter** — die Zusicherung ist
  eine Eigenschaft des Funktionstyps, nicht eine Disziplin der Aufrufstelle.
- **Der amtliche Trip-Pfad schreibt weiterhin in den `"trip"`-Sperrzeit-Topf**
  (`trip_alert.py:1539` bleibt unverändert bestehen) — nur das Lesen entfällt.
- **Zähler-Reihenfolge:** Tageszähler-Erhöhung und Sperrzeit-Schreiben laufen NIEMALS vor
  der erfolgreichen Zustellung.
- **`is_silenced` bleibt außerhalb des geteilten Gates**, Compare-eigen, und wirkt
  weiterhin VOR allem anderen im Ortsvergleich-Pfad.
- **Trips prüfen `paused_at`/`archived_at` im Alarmpfad weiterhin nicht** (Absicht seit
  #995) — ein pausierter Trip pausiert nur den Briefing-Versand, nicht den Alarm.
- **Der amtliche Pfad protokolliert keine Unterdrückungsgründe** — der S3-Wächter
  `tests/tdd/test_nowcast_suppression_logging.py::test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund`
  bleibt unverändert grün.
- **`_day_window_end()` (`compare_official_alert.py:276`) wird nicht angefasst** — kein
  Zeichen Diff.
- Mandantentrennung: jeder Teil mit ZWEI verschiedenen Nutzern verifiziert, `user_id`
  nie auf `"default"` zurückfallen lassen.
- Datenbeschaffung wird NICHT fusioniert — Trip und Ortsvergleich holen weiterhin
  getrennt amtliche Warnungen.
- Bestandsdaten: Read-Modify-Write mit Merge, nie Replace.
- Testpolitik: kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis
  (Ausnahme: `# doc-compliance-test` für den ADR-Nachtrag-Nachweis, AC-19).
- Testdateien nach VERHALTEN benennen, nie nach Issue-Nummer.

## Nicht-Ziele (ausdrücklich)

- **#1599** (Tagesfenster-Obergrenze: Anzeige zählt Stunde 19 mit, der Alarm nicht) ist
  eine offene Bedeutungsfrage mit drei gleichwertigen Auswegen. S4a entscheidet sie
  **nicht** und darf ihr Ergebnis nicht vorwegnehmen.
- **#1744 Scheibe B** (Entdopplung nach Ereignis-Identität über Quellen hinweg) ist S4b
  und schließt #1467. S4a schließt #1467 **nicht**.
- **Datenbeschaffung wird nicht fusioniert.** Radar- und amtliche Quellen bleiben
  technisch eigenständig; zusammengelegt wird nur die Ablaufsteuerung.
- **Der Trip-Warnungsabruf wird nicht vorgezogen** (`trip_alert.py:479`) — er sitzt im
  Sammel-Lauf über alle Trips, an ganz anderer Stelle; das wäre ein eigener Umbau.
  → Sammel-Issue #1199.
- **`_day_window_end()` wird nicht angefasst.** Ihr Abendverhalten (nullbreites Fenster
  nach Fensterende) ist heute von keinem Test gehalten — das ist ein Befund, kein
  Auftrag dieser Scheibe. → #1199.
- **Unterdrückungsgründe bleiben Nowcast-only** (E3) — der amtliche Pfad protokolliert
  weiterhin keine, der S3-Wächter bleibt unverändert.
- Compare-eigen bleiben: Orte statt Etappen, transponierte Übersicht,
  Compare-Mail-Template, Bündelung aller getriggerten Orte in EINE Nachricht,
  Empfänger als Preset-Attribut, Ortszeit-Bezug.
- Kein Vorgriff auf #1714, #1697, #1695 (offene Alarm-Issues in derselben Fläche).
- Kein neuer Go-Endpunkt, kein neuer Cron-Job. Kein Frontend-Code.

## Reihenfolge der Arbeit

1. `check_official_alert_gate` + eigene Tests **zuerst**, bevor ein Aufrufer angefasst
   wird.
2. **Trip zuerst** (der heiklere Fall): erst der Regressionstest „Änderungsalarm um T,
   amtliche Eskalation um T+15 min wird zugestellt" mit echt befülltem
   `ThrottleStore`-Scope `"trip"`, dann der Umbau.
3. Dann Compare (Reihenfolge-Wechsel Tageslimit-vor-Abruf), profitiert von der
   geschärften Test-Vorlage aus Schritt 2.
4. Ordinal-Wächter **nach jedem** der beiden Umbauten laufen lassen, nicht erst am Ende.
5. Preset-Helfer zum Schluss (reine Strukturverschiebung, fasst dieselben Dateien noch
   einmal an).
6. ADR-Nachtrag zuletzt, wenn das Verhalten feststeht.

## Risiken

| | Risiko (aus Nutzersicht) | Gegenmittel |
|---|---|---|
| **R-A** | Ist die Zonenauflösung oder der Zählerstand im neuen Gate falsch, bleibt der Lauf komplett stumm — vorher wäre wenigstens der Abruf gelaufen und die Symptome sichtbar gewesen. | Nachweis bei Zählerstand 0 **und** Limit-1 (AC-7, AC-15). |
| **R-B** | Bleibt `_is_throttled_with_cooldown` versehentlich im amtlichen Aufrufpfad, bekommt der Nutzer die Eskalation weiterhin nicht. | Regressionstest aus Reihenfolge-Schritt 2 (AC-4, Mutations-Gegenprobe). |
| **R-C** | Zieht jemand `is_silenced` später „vereinheitlichend" ins Gate, ändert sich das Trip-Verhalten still (Trips kennen `is_silenced` gar nicht). | Test, der `is_silenced` ausdrücklich **außerhalb** des Gates nachweist (AC-9). |
| **R-D** | Ein rot gewordener Ordinal-Wächter, der „korrigiert" statt verstanden wird, kann eine echte verlorene Fehlerbehandlung durchwinken — dann bleibt bei einem defekten Ortsdatensatz die Fehlermeldung aus. | Wächter-Lauf nach jedem Umbau-Schritt, Diff-Review der Wächter-Datei selbst (AC-18). |
| **R-E** | `_day_window_end()` wird nicht angefasst — wandert sie beim Umbau versehentlich mit, verliert der Nutzer nach 19 Uhr Ortszeit Warnungen (nullbreites Fenster). | Diff-Nachweis „keine Änderung" (AC-17). |

## Wächter, die mitziehen müssen

| Test | Warum |
|---|---|
| `tests/tdd/test_alert_gate.py` | bekommt die neuen Reihenfolge-Fälle für `check_official_alert_gate` dazu; bestehende `check_nowcast_gate`-Fälle bleiben unverändert grün |
| `tests/tdd/test_nowcast_suppression_logging.py::test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund` | bleibt **unverändert** grün (E3) — NICHT anfassen |
| `tests/tdd/test_compare_official_alert_briefing_imminent.py::test_ac4_sperre_greift_vor_dem_warnungs_abruf` | Sperre-vor-Abruf-Reihenfolge, jetzt um Tageslimit-vor-Abruf ergänzt |
| `tests/tdd/test_compare_official_alert.py` | AC-1 bis AC-8 des Ortsvergleich-Pfads, Messpunkte für die neue Reihenfolge nachziehen |
| `tests/tdd/test_issue_1088_official_alert_triggers.py` | Trip-Auslöser, plus der neue Kernfall-Regressionstest (AC-4) |
| `tests/test_success_status_guard.py`, `tests/test_resolution_loss_guard.py` | verankern `compare_radar_alert.py`/`compare_alert.py`/`compare_official_alert.py` per `datei::funktion::ordinal` — Schlüssel nachziehen, Assertion nicht aufweichen |

## Test-Plan

Kern-Schicht (deterministisch, kein Netz), sofern nicht anders vermerkt.

| AC | Datei | Schicht |
|---|---|---|
| AC-1, AC-2, AC-3 (Baustein-Struktur) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-4 (Kernfall) | `tests/tdd/test_issue_1088_official_alert_triggers.py` (neuer Fall) | Kern |
| AC-5, AC-6 (Gegenprobe, Änderungsalarm-Regression) | `tests/tdd/test_trip_alert_cooldown_scope.py` (neu) | Kern |
| AC-7, AC-8 (Ortsvergleich Tageslimit vor Abruf) | `tests/tdd/test_compare_official_alert_daily_limit_order.py` (neu) | Kern |
| AC-9 (is_silenced außerhalb) | `tests/tdd/test_compare_official_alert.py` (Bestand, ergänzt) | Kern |
| AC-10 (paused_at ungeprüft) | `tests/tdd/test_issue_1088_official_alert_triggers.py` (neuer Fall) | Kern |
| AC-11 (keine Protokollierung) | `tests/tdd/test_nowcast_suppression_logging.py` (Bestand, unverändert grün) | Kern |
| AC-12 (check_briefing_imminent eigenständig) | `tests/tdd/test_compare_official_alert_briefing_imminent.py` (Bestand, ergänzt) | Kern |
| AC-13, AC-14 (geteilter Compare-Helfer) | `tests/tdd/test_compare_preset_access.py` (neu) | Kern |
| AC-15 (Zähler-Invariante) | `tests/tdd/test_alert_gate.py` (neuer Fall) | Kern |
| AC-16 (Mandantentrennung) | `tests/tdd/test_alert_gate.py` (neu, zwei Nutzer-Kontexte) | Kern |
| AC-17 (`_day_window_end` unverändert) | `tests/tdd/test_compare_official_alert.py` (Diff-Nachweis + Verhaltensfall) | Kern |
| AC-18 (Ordinal-Wächter) | `tests/test_success_status_guard.py`, `tests/test_resolution_loss_guard.py` gezielt laufen lassen | Kern |
| AC-19 (ADR-Nachtrag) | `tests/test_adr_index_drift.py` bzw. gezielter `# doc-compliance-test` | Kern |

Live-E2E: keine eigenen Live-Marker-Tests vorgesehen — echte amtliche Eskalationen sind
nicht auf Bestellung provozierbar. Staging-Nachweis erfolgt über den ausgelieferten Code
mit gezielt gesetzten Zustandsdateien (ThrottleStore-Scope `"trip"` vorbelegen,
Tageszähler vorbelegen), nicht über „auf eine echte Warnung warten".

## Acceptance Criteria

**Struktur des geteilten Bausteins**

- **AC-1:** Given die neue Funktion `check_official_alert_gate` in
  `src/services/alert_gate.py`, When der Ortsvergleich-amtliche Pfad
  (`compare_official_alert.py::_check_one_preset`) UND der Trip-amtliche Pfad
  (`trip_alert.py::_send_official_alert_only`) je einen amtlichen Alarm prüfen, Then
  rufen beide dieselbe Funktion auf — nicht zwei eigene Inline-Prüfungen wie vor dieser
  Scheibe.
  - Test: Aufrufzähler (Spion) auf `check_official_alert_gate`, für jeden Pfad
    mindestens 1 Aufruf je Lauf.

- **AC-2:** Given eine Konstellation, in der sowohl Ruhezeit als auch Tages-Obergrenze
  gleichzeitig zuträfen, When `check_official_alert_gate` geprüft wird, Then stoppt der
  Ablauf an der Ruhezeit — die Tages-Obergrenze-Prüfung wird für diesen Aufruf gar nicht
  erst erreicht.
  - Test: Ruhezeit AN + Tageslimit erschöpft gleichzeitig, Aufrufzähler der
    Tageslimit-Prüfung bleibt bei 0.
  - Mutations-Gegenprobe (Pflicht): Reihenfolge im Baustein vertauschen (Tages-Obergrenze
    vor Ruhezeit) MUSS diesen Test rot machen.

- **AC-3:** Given die Funktionssignatur von `check_official_alert_gate`, When man die
  Parameterliste inspiziert, Then existiert kein Parameter, der einen Cooldown oder eine
  Sperrzeit an die Funktion übergibt — die Zusicherung „amtlich hat keinen Cooldown" ist
  eine Eigenschaft der Funktion, nicht eine Disziplin der Aufrufstelle.
  - Test: `inspect.signature(check_official_alert_gate)`, kein Parametername enthält
    „cooldown"/„throttle"/„sperr".

**Der Kernfall: Trip-Cooldown-Lesen entfällt (E1)**

- **AC-4 (Kernfall):** Given ein Trip, für den um Zeitpunkt T ein Änderungsalarm
  zugestellt wurde (er hat den `ThrottleStore`-Scope `"trip"` für diesen Trip befüllt),
  When 15 Minuten später (T+15) eine amtliche Warnung für denselben Trip von GELB auf
  ORANGE eskaliert, Then wird die Eskalation zugestellt — vor dieser Scheibe wäre sie bis
  zu 120 Minuten unterdrückt worden, weil der amtliche Pfad denselben Sperrzeit-Topf
  gelesen hat.
  - Test: `ThrottleStore`-Scope `"trip"` mit einem frischen Eintrag zu T vorbelegen
    (simuliert den zugestellten Änderungsalarm), amtliche GELB→ORANGE-Eskalation zu T+15
    auslösen, Zustellung erfolgt auf mindestens einem Kanal.
  - Mutations-Gegenprobe (Pflicht): das Lesen von Scope `"trip"` im amtlichen Pfad wieder
    einbauen (Zeile `trip_alert.py:1494` reaktivieren) MUSS diesen Test rot machen.

- **AC-5 (Gegenprobe zu AC-4, harmlose Richtung bleibt zu):** Given derselbe Trip, dessen
  amtlicher Alarm aus AC-4 gerade erfolgreich zugestellt wurde, When man danach den
  Zustand des `ThrottleStore`-Scopes `"trip"` betrachtet, Then enthält er einen neuen
  Eintrag für diesen Trip — das Schreibverhalten des amtlichen Pfads ist unverändert
  (`trip_alert.py:1539` bleibt bestehen), sodass ein nachfolgender Änderungsalarm für
  denselben Trip innerhalb des Cooldowns wie bisher unterdrückt bleibt.
  - Test: amtlichen Alarm zustellen, `ThrottleStore`-Snapshot davor/danach vergleichen —
    neuer Eintrag Scope `"trip"`/`trip.id`; anschließend einen Änderungsalarm-Check für
    denselben Trip simulieren, er bleibt unterdrückt (unverändert gegenüber vor der
    Scheibe).

- **AC-6 (Regression, Änderungsalarm-Drosselung unverändert):** Given den
  Änderungsalarm-Pfad selbst (`trip_alert.py:246`), When identische
  Drosselungs-Szenarien vor und nach dieser Scheibe durchlaufen werden, Then bleibt sein
  Zustellverhalten unverändert — diese Scheibe rührt nur den amtlichen Lesezugriff an,
  nicht den Änderungsalarm-Pfad selbst.
  - Test: bestehende Änderungsalarm-Cooldown-Tests unverändert und grün ausführen; kein
    neuer Testfall nötig, aber der Lauf ist Teil des Nachweises dieser Scheibe.

**Ortsvergleich: Tages-Obergrenze vor dem Abruf (E2)**

- **AC-7:** Given einen Ortsvergleich-Nutzer, dessen Tages-Obergrenze für amtliche Alarme
  bereits erreicht ist, When für ein Preset dieses Nutzers eine neue amtliche Warnung
  anstünde, Then wird KEIN Warnungs-Abruf (`get_official_alerts_for_location`)
  ausgelöst — nachweisbar am Aufrufzähler der Abruf-Naht, nicht nur am Ausbleiben der
  Zustellung.
  - Test: Tageszähler auf das Limit vorbelegen, Lauf ausführen, Aufrufzähler der
    Abruf-Naht bleibt bei 0.
  - Mutations-Gegenprobe (Pflicht): die Reihenfolge zurücktauschen (Abruf vor Gate) MUSS
    diesen Test rot machen.

- **AC-8:** Given einen Ortsvergleich-Nutzer mit freiem Kontingent, When für ein Preset
  eine neue oder eskalierte amtliche Warnung eintritt, Then wird sie unverändert
  zugestellt — das Vorziehen der Prüfung ändert nichts am Zustellergebnis bei freiem
  Kontingent.
  - Test: Kontingent frei, neue bzw. eskalierte Warnung simulieren, Zustellung erfolgt
    auf mindestens einem Kanal.

**Was außerhalb des Gates bleibt**

- **AC-9:** Given ein stillgelegtes Ortsvergleich-Preset (`is_silenced(preset) ==
  True`), When der amtliche Ortsvergleich-Lauf für dieses Preset durchläuft, Then wird
  `check_official_alert_gate` gar nicht erst erreicht — der Stilllegungs-Riegel wirkt
  weiterhin VOR allem anderen und bleibt außerhalb des geteilten Bausteins.
  - Test: Preset stilllegen, Lauf ausführen, Aufrufzähler von
    `check_official_alert_gate` für dieses Preset bleibt bei 0.

- **AC-10:** Given einen pausierten Trip (`paused_at` gesetzt), When der amtliche
  Trip-Alarmpfad für diesen Trip läuft, Then wird der amtliche Alarm trotzdem geprüft und
  bei Zutreffen zugestellt — Trips prüfen `paused_at` im Alarmpfad weiterhin nicht
  (Absicht seit #995), nur der Briefing-Versand pausiert, nicht der Alarm.
  - Test: `paused_at` auf dem Trip setzen, amtlichen Eskalations-Trigger auslösen,
    Zustellung erfolgt trotz gesetzter Pause.

- **AC-11:** Given einen amtlichen Alarm (Ortsvergleich oder Trip), der am neuen Gate an
  Ruhezeit oder Tages-Obergrenze scheitert, When der Lauf beendet ist, Then entsteht dafür
  KEIN Protokolleintrag mit den Unterdrückungsgründen `REASON_QUIET_HOURS` /
  `REASON_DAILY_LIMIT` — der bestehende Wächter
  `tests/tdd/test_nowcast_suppression_logging.py::test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund`
  bleibt unverändert grün.
  - Test: bestehenden Wächter unverändert ausführen (Fortbestand des grünen Zustands als
    Nachweis) plus einen gezielten Aufruf des amtlichen Trip-Pfads mit erzwungener
    Unterdrückung, Protokoll enthält keinen neuen Grund-Eintrag.

- **AC-12:** Given beide amtlichen Pfade, When man ihre Aufrufreihenfolge zur Laufzeit
  beobachtet, Then läuft `check_official_alert_gate` als ERSTE Stufe (dort, wo bisher die
  Ruhezeit-Prüfung stand) und `check_briefing_imminent` unmittelbar danach als weiterhin
  eigener Aufruf — die Ruhezeit bleibt damit vor der Briefing-Sperre, wie es
  `trip_alert.py:1487-1490` seit #1594 ausdrücklich festhält, und die Briefing-Sperre wird
  NICHT in `check_official_alert_gate` verschmolzen.
  - Test: Aufruf-Sequenz-Spionage weist in BEIDEN Pfaden die Reihenfolge
    `check_official_alert_gate` → `check_briefing_imminent` nach; ein reiner Quellcode-Grep
    genügt nicht als Nachweis, entscheidend ist die Laufzeit-Reihenfolge.
  - Mutations-Gegenprobe (Pflicht): die beiden Aufrufe vertauschen (Briefing-Sperre vor dem
    Gate) MUSS diesen Test rot machen — sonst bewacht er die Reihenfolge nicht, sondern nur
    das Vorhandensein beider Aufrufe.

- **AC-12b:** Given einen amtlichen Alarm, bei dem gleichzeitig die Tages-Obergrenze
  erschöpft ist UND ein Briefing unmittelbar bevorsteht, When der Lauf durchläuft, Then
  wird nichts zugestellt und der Tageszähler bleibt unverändert — das Vorziehen der
  Tages-Obergrenze vor die Briefing-Sperre ist wirkungsfrei, weil die Prüfung rein lesend
  ist und erst `increment()` nach erfolgreicher Zustellung bucht.
  - Test: beide Bedingungen gleichzeitig herstellen, Zähler-Snapshot vor/nach dem Lauf
    vergleichen, exakte Gleichheit; zusätzlich derselbe Fall mit freiem Kontingent, der
    ebenfalls nichts zustellt (Briefing-Sperre greift), aber aus dem anderen Grund.

**Geteilter Compare-Helfer**

- **AC-13:** Given die drei Compare-Alarmpfade (Änderungsalarm, Nowcast, amtlich), When
  jeder von ihnen seine Presets lädt und seinen Notification-Service aufbaut, Then rufen
  alle drei denselben Helfer (`compare_preset_access.load_compare_alert_presets` /
  `notification_service_for_preset`) auf — die drei Bestandsmethoden sind Ein-Zeiler-
  Wrapper geworden, keine eigenständigen Implementierungen mehr.
  - Test: Aufrufzähler auf die neuen Helferfunktionen, je Pfad mindestens 1 Aufruf pro
    Lauf.

- **AC-14:** Given die drei Compare-Alarmpfade lösen im selben Lauf je eine Warnung für
  dasselbe Preset aus, When man die drei zugestellten Warntexte vergleicht, Then bleibt
  jeder Text weiterhin unterscheidbar (Präfix „Compare-Alert:" / „Compare-Alert
  (Radar):" / „Compare-Alert (amtlich):") — die Zusammenlegung ändert die Struktur, nicht
  den Nutzertext.
  - Test: alle drei Pfade in einem Lauf auslösen, drei zugestellte Nachrichten, drei
    unterschiedliche, den Alarmtyp benennende Präfixe.

**Zähler-Invariante, Mandantentrennung, Unveränderlichkeit**

- **AC-15:** Given einen amtlichen Alarm-Versuch, bei dem die tatsächliche Zustellung
  fehlschlägt (kein Kanal erreichbar), When der Lauf beendet ist, Then sind weder der
  Tageszähler noch — beim Trip — der `"trip"`-Sperrzeit-Eintrag für diese Entität
  erhöht bzw. gesetzt worden.
  - Test: alle Kanäle unerreichbar simulieren, Zähler-Snapshot vor/nach dem Lauf
    vergleichen, exakte Gleichheit.

- **AC-16:** Given zwei verschiedene Nutzer mit je einem Trip bzw. Ortsvergleich-Preset
  gleicher Kennung, deren Tages-Obergrenze für amtliche Alarme unabhängig geführt wird,
  When Nutzer A sein Kontingent ausschöpft und Nutzer B unabhängig davon eine eigene
  amtliche Warnung auslöst, Then wirkt die Sperre von A nicht auf B — B erhält seine
  Warnung, ohne dass ein Rückfall auf `"default"` stattfindet.
  - Test: zwei Datenverzeichnisse (`user_id` A/B), gleiche Preset-/Trip-Kennung, A's
    Kontingent erschöpfen, B's amtliche Warnung geht trotzdem durch.

- **AC-17:** Given `compare_official_alert.py::_day_window_end()`, When man ihren
  Quellcode vor und nach dieser Scheibe vergleicht, Then ist sie textidentisch
  unverändert — ihr Verhalten (auch das nullbreite Fenster nach Fensterende) bleibt exakt
  wie vor der Scheibe.
  - Test: Diff der Methode gegen den Stand vor der Scheibe ist leer; zusätzlich ein
    Verhaltensfall, der ein Fenster nach 19 Uhr Ortszeit prüft und das bekannte
    nullbreite Ergebnis unverändert bestätigt.

- **AC-18:** Given `tests/test_success_status_guard.py` und
  `tests/test_resolution_loss_guard.py`, die `compare_radar_alert.py`,
  `compare_alert.py` und `compare_official_alert.py` per
  `datei::funktion::ordinal` verankern, When diese Scheibe abgeschlossen ist, Then laufen
  beide Wächter unverändert grün — eine durch den Umbau verschobene Ordinal-Zählung wurde
  über nachgezogene Schlüssel aufgefangen, keine Assertion wurde aufgeweicht.
  - Test: beide Wächterdateien gezielt ausführen, Exit 0; Diff der Wächterdateien zeigt
    ausschließlich Schlüssel-/Ordinal-Anpassungen, keine geänderten Erwartungswerte.

**Dokumentation**

- **AC-19:** Given den bestehenden ADR-0021-Nachtrag zu #1467 S3, der wörtlich festhält
  „Änderungs- und amtlicher Alarm bewusst weiterhin nicht" (bezogen auf
  Unterdrückungs-Protokollierung), When diese Scheibe abgeschlossen ist, Then trägt
  ADR-0021 einen neuen, datierten Nachtrag mit Bezug auf #1467 S4a, der festhält, dass
  BEIDE amtlichen Pfade seit dieser Scheibe über denselben geteilten Ablauf-Baustein
  laufen wie zuvor nur die Nowcast-Pfade — ohne den bestehenden Satz zur
  Unterdrückungs-Protokollierung zu widerrufen (der bleibt laut E3 unverändert richtig).
  - Test: `# doc-compliance-test` — ADR-0021 enthält nach dem Abschluss dieser Scheibe
    einen Nachtrag-Absatz mit Bezug auf „#1467" und „S4a", datiert nach dem 2026-08-16.

## Known Limitations

- **#1599 bleibt offen.** Diese Scheibe entscheidet die Tagesfenster-Obergrenzenfrage
  nicht und darf ihr Ergebnis nicht vorwegnehmen.
- **Die harmlose Richtung aus E1 bleibt bestehen.** Ein amtlicher Alarm kann weiterhin
  einen nachfolgenden Änderungsalarm für denselben Trip unterdrücken (unverändertes
  Schreibverhalten, AC-5). Das richtige Werkzeug dafür — Entdopplung nach
  Ereignis-Identität statt einer pauschalen Zeitsperre — liefert S4b (#1744 B), nicht
  diese Scheibe.
- **Der Trip-Warnungsabruf bleibt vor seiner eigenen Kontingent-Prüfung
  (`trip_alert.py:479` vor `:1497`).** Die Asymmetrie zum Ortsvergleich (E2) wird durch
  diese Scheibe kleiner, aber nicht beseitigt — ein Vorziehen des Trip-Abrufs wäre ein
  eigener, größerer Umbau an anderer Stelle. → Sammel-Issue #1199.
- **Ein Rückbau der Entdopplung (Baustein → wieder zwei getrennte Fassungen) ist mit
  Verhaltenstests grundsätzlich nicht fangbar** — beide Fassungen könnten sich weiterhin
  identisch verhalten. Der strukturelle Schutz liegt außerhalb dieser Spec (Code-Review).
- **Struktur-Wächter können nach der Umsetzung nachzuziehen sein** — bei verschobener
  Ordinal-Zählung sind die Wächter-Schlüssel anzupassen, nicht die Wächter selbst
  aufzuweichen (R-D).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilter Auswertungskern) bekommt einen weiteren
  Nachtrag. Der bisherige Nachtrag zu #1467 S3 hält fest: „Änderungs- und amtlicher Alarm
  bewusst weiterhin nicht [protokollieren Unterdrückungsgründe]" — dieser Satz zur
  Protokollierung bleibt unverändert richtig (E3). Was er heute zusätzlich impliziert
  (dass der amtliche Pfad keinen geteilten Ablauf-Baustein nutzt), wird durch diese
  Scheibe sachlich überholt und im neuen Nachtrag korrigiert.
- **Rationale:** Die Ablaufsteuerung bleibt im Muster von ADR-0021 — der amtliche Pfad
  zieht auf denselben geteilten Baustein wie der Nowcast-Pfad (S3), statt zwei
  eigenständige Prüfketten fortzuführen. Kein neues Architekturprinzip, nur konsequente
  Anwendung des bestehenden auf den letzten noch abweichenden Pfad.

## Changelog

- 2026-08-16: Initiale Spec. Vier Entscheidungen E1–E4 nach PO-Vorgabe vom 2026-08-16
  (`docs/context/rework-1467-s4a-amtlich.md`) zugeschnitten, geteilter Baustein von
  Anfang an mit beiden amtlichen Pfaden verdrahtet. Test-Budget vom PO auf 1000 Zeilen
  angehoben. Zeilenangaben gegen den Ist-Stand vom 2026-08-16, Commit `098226ae`,
  verifiziert.
