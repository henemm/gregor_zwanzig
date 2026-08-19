---
entity_id: rework_1917_s4b2_compare_entdopplung
type: refactor
created: 2026-08-18
updated: 2026-08-18
status: draft
version: "1.0"
tags: [alerts, compare, epic-1458, issue-1467, issue-1744, issue-1917, s4b, s4b-2, entdopplung]
---

# Quellenübergreifende Alarm-Entdopplung nach Ereignis-Identität — Ortsvergleich-Fläche (Issue #1917, Scheibe S4b-2, Epic #1458 Teil 4b)

## Approval

- [x] Approved (2026-08-18, PO)

## Purpose

Die quellenübergreifende Ereignis-Identitäts-Entdopplung — verhindert, dass
ein und dasselbe Gewitter über einen Radar-Nowcast UND eine amtliche Warnung
doppelt zugestellt wird — ist auf der Trip-Fläche bereits live
(`check_event_identity_gate()`/`record_event_identity()`,
`src/services/alert_gate.py:560-654`, Issue #1467 Scheibe S4b-1). Der
Baustein wurde dort **von Anfang an entitätsparametrisiert** gebaut, exakt
damit die Ortsvergleich-Verdrahtung eine reine Zusatz-Verdrahtung ohne neue
Kernlogik ist (rework_1467_s4b_entdopplung.md, Non-Goal-Absatz).

Auf dem Ortsvergleich (Compare) fehlt diese Verdrahtung komplett — dort
können Radar-Nowcast und amtliche Warnung zum selben Ereignis für denselben
Ort weiterhin doppelt zugestellt werden. Diese Scheibe schließt die Lücke:
`src/services/compare_radar_alert.py` und
`src/services/compare_official_alert.py` rufen denselben, unveränderten
Baustein an derselben Position im jeweiligen Ablauf auf — gespiegelt aus dem
Trip-Vorbild (`trip_alert.py:1305-1406` Nowcast, `trip_alert.py:1671-1803`
amtlich).

**Leitsatz, unverändert aus S4b-1 übernommen:** Der gefährlichste Fehler ist
der ausbleibende Alarm. Jede Unsicherheit — fehlender Zeitbezug, fehlende
Ortskennung, unbekannte Gefahrenart, kaputtes Registerformat — entscheidet
sich **immer** Richtung Zustellung, nie Richtung Unterdrückung.

**Kritische Design-Entscheidung, bereits am Code verifiziert (nicht mehr
offen):** Bei Compare läuft die Ortstrennung strukturell über
`entity_id = f"{preset_id}:{loc.id}"` (eine eigene Registerdatei pro Ort),
nicht wie beim Trip über den `segment_ids`-Parameter innerhalb EINER
gemeinsamen Datei. Die naheliegende erste Annahme — `segment_ids` bleibt bei
Compare leer, weil die Ortstrennung ja schon über die Dateigrenze läuft —
ist **falsch** und wäre ein stiller No-Op-Bug: `alert_gate.py:508-510`
(`_find_matching_entry`) gibt bei leerer `segment_ids`-Menge — aktuell ODER
gespeichert — **immer** „kein Match" zurück (Docstring nennt das
ausdrücklich „AC-5 Bruchstelle"). Ein Compare-Aufruf mit `segment_ids=[]`
sähe verdrahtet aus, würde aber nie unterdrücken. Entschieden:
`segment_ids=[loc.id]` (einelementige Liste) bei JEDEM Compare-Aufruf,
sowohl Check als auch Record (AC-0 unten).

## Source

- **File:** `src/services/compare_radar_alert.py`,
  `src/services/compare_official_alert.py`
- **Identifier:** `CompareRadarAlertService._check_one_preset`,
  `CompareOfficialAlertService._check_one_preset`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`). Der
wiederzuverwendende Baustein selbst (`src/services/alert_gate.py`,
`check_event_identity_gate`/`record_event_identity`/`resolve_hazard_class`)
bleibt **unverändert** — kein Go-Code, kein Frontend-Code.

## Estimated Scope

- **LoC produktiv:** ~60–90 (`compare_radar_alert.py` Gate-Aufruf +
  Teilfilterung + Record ~25–35, `compare_official_alert.py` dasselbe für
  den Mehrfach-Ort-pro-Alert-Fall ~35–55). Kein neuer Code in `alert_gate.py`
  — der Baustein wird nur importiert und aufgerufen.
- **LoC Tests:** ~250–350 — voraussichtlich über dem 250er-Budget
  (`loc_limit_override` wahrscheinlich nötig, analog S4b-1). Begründung:
  Live-Multi-Tenant-Zustellpfad, Mutations-Gegenprobe zu V1/V2 PFLICHT,
  Mandantentrennungs-Nachweis, Batch-Teilfilterung in zwei Varianten
  (einfache Liste bei Radar, Mehrfach-Ort-pro-Alert bei amtlich).
- **Files:** 0 neu in `src/`, 2 produktiv geändert
  (`compare_radar_alert.py`, `compare_official_alert.py`), 1 ADR-Nachtrag,
  2 neue Testdateien, 1 bestehende Testdatei ergänzt.
- **Effort:** medium.
- **Risiko:** MEDIUM — Live-Zustellpfad für alle Ortsvergleichs-Nutzer
  (Multi-Tenant), aber fail-soft-Konstruktion begrenzt den Schaden einer
  Fehlfunktion auf „zu viel senden", nie „zu wenig". Kein neuer Baustein,
  reine Verdrahtung eines bereits produktiv gehärteten Bausteins.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `rework_1467_s4b_entdopplung` | module | Vorgänger-Scheibe (Trip, live) — liefert den unveränderten Baustein `check_event_identity_gate`/`record_event_identity`/`resolve_hazard_class`, das Vorbild für Aufrufstellen-Position und Batch-Filterung |
| `services.alert_gate.check_event_identity_gate` / `record_event_identity` / `resolve_hazard_class` | module | der wiederzuverwendende Baustein selbst — unverändert, keine Signaturänderung nötig |
| `services.alert_urgency` | module | geteilte Dringlichkeits-Skala und Ableitungen `urgency_from_radar`, `urgency_from_official_level`, `highest_urgency` — bereits in beiden Compare-Services importiert und genutzt |
| `services.alert_state.AlertStateService` | module | Melde-Gedächtnis-Ablage; das neue Ereignis-Identität-Register liegt in derselben Datei wie das bestehende Compare-Dedup-Gedächtnis (`radar_onset`/amtliche Warnstufen), eigener Schlüssel-Präfix `event_identity:` |
| `services.alert_log.append_suppressed_entry` / `REASON_EVENT_DUPLICATE` | module | Protokollierung der Unterdrückung — dieselbe Konstante wie S4b-1, keine neue |
| `services.alert_channel_threshold.split_by_threshold` | module | bleibt unverändert NACH dem neuen Gate — Kanal-Schwelle entscheidet WIE, das Gate entscheidet OB (ADR-0046, V3) |

## Implementation Details

### AC-0-Design: `segment_ids=[loc.id]` bei JEDEM Compare-Aufruf

Siehe „Purpose" oben für die vollständige Herleitung. Konkret an beiden
Aufrufstellen:

```python
# compare_radar_alert.py, pro getriggertem Ort
identity_gate = check_event_identity_gate(
    user_id=self._user_id, entity_id=f"{preset_id}:{loc.id}",
    hazard_class=resolve_hazard_class(is_convective=nowcast.is_convective),
    segment_ids=[loc.id], severity=urgency, now=now_utc, point_at=onset_dt,
)
...
record_event_identity(
    user_id=self._user_id, entity_id=f"{preset_id}:{loc.id}",
    hazard_class=..., segment_ids=[loc.id], severity=urgency,
    point_at=onset_dt, now=datetime.now(timezone.utc),
)
```

```python
# compare_official_alert.py, pro (alert, loc_id)-Kombination
identity_gate = check_event_identity_gate(
    user_id=self._user_id, entity_id=f"{preset_id}:{loc_id}",
    hazard_class=resolve_hazard_class(hazard=alert.hazard),
    segment_ids=[loc_id], severity=severity, now=now_utc,
    window_start=alert.valid_from, window_end=alert.valid_to,
)
```

### `compare_radar_alert.py` — Gate pro getriggertem Ort, vor dem gebündelten Versand

`_check_one_preset()` bündelt heute **alle** getriggerten Orte eines Presets
in EINEM Versand (`send_multi_location_radar_alert`, Z. 207-211). Gespiegelt
aus dem Trip-Nowcast-Vorbild (`trip_alert.py:1305-1406`), aber pro Ort in der
`triggered`-Liste statt pro Trip:

1. Nach `_detect_triggered_locations()` (liefert `(loc.name, loc,
   NowcastResult)`-Tripel), **vor** dem Versand: für jeden getriggerten Ort
   `check_event_identity_gate(entity_id=f"{preset_id}:{loc.id}",
   hazard_class=resolve_hazard_class(is_convective=nowcast.is_convective),
   segment_ids=[loc.id], severity=<pro-Ort-Dringlichkeit>, ...)`.
2. Nicht zugelassene Orte werden aus `triggered` gefiltert (Protokolleintrag
   `alert_log.append_suppressed_entry(..., reason=REASON_NOWCAST,
   gate_reason=...)`, analog Trip-Vorbild), bevor `severity` (aktuell
   `alert_urgency.highest_urgency(...)` über die ganze Liste, Z. 193-199) neu
   aus der verbleibenden Teilmenge berechnet wird — dieselbe
   Reihenfolge-Lehre wie im amtlichen Trip-Pfad (Filtern VOR
   Dringlichkeits-Neuberechnung).
3. Bleibt die gefilterte Liste leer, wird nichts verschickt (analoge
   Rückgabe `False`, kein `record_nowcast_sent`).
4. Nach erfolgreichem Versand (`notif_result.sent`): `record_event_identity`
   je erfolgreich zugestelltem Ort (Schleife über die gefilterte
   `triggered`-Liste), **vor** oder zusammen mit dem bestehenden
   `_finalize_triggered_state()`-Aufruf — analog F001-Symmetrie zu
   `record_nowcast_sent`, ausschließlich nach Erfolg.

### `compare_official_alert.py` — Gate pro `(alert, loc_id)`-Kombination

Eigenheit gegenüber dem Trip-Vorbild: `tagged_alerts` sind `(alert,
loc_ids)`-Paare — **ein Alert kann mehrere Orte betreffen**
(`_detect()`-Rückgabe, Z. 222-285). Der Trip-Pfad hat dagegen `segment_ids`
als EINE Liste pro Alert und braucht deshalb nur einen Gate-Aufruf je Alert.
Bei Compare wird — weil die Registertrennung über die Ortsdatei läuft —
**pro betroffenem Ort ein eigener Gate-Aufruf** benötigt:

1. Nach `_detect()`, **vor** dem gebündelten Versand
   (`send_multi_location_official_alert`, Z. 193-199): für jedes
   `(alert, loc_ids)`-Paar in `tagged_alerts`, für jeden `loc_id` in
   `loc_ids` einzeln `check_event_identity_gate(entity_id=f"{preset_id}:
   {loc_id}", hazard_class=resolve_hazard_class(hazard=alert.hazard),
   segment_ids=[loc_id], severity=alert_urgency.urgency_from_official_level(
   alert.level), window_start=alert.valid_from, window_end=alert.valid_to,
   ...)`.
2. **Mehrfach-Ort-Fall (eigene AC):** Betrifft ein Alert zwei Orte und ist an
   einem Ort bereits ein passender Registereintrag vorhanden, am anderen
   nicht, wird das Paar auf die verbleibende Teilmenge der `loc_ids`
   reduziert (`(alert, [loc_id_b])` statt `(alert, [loc_id_a, loc_id_b])`) —
   NICHT das ganze Paar verworfen und NICHT ungefiltert an beide Orte
   zugestellt. Analog zur Batch-Teilfilterung im Trip-Vorbild, nur auf der
   Orts-Achse statt der Alert-Achse.
3. Wird durch die Filterung ein `loc_ids`-Rest leer, entfällt das gesamte
   Paar aus der zu versendenden Liste (Protokolleintrag je unterdrücktem
   `(alert, loc_id)`, analog Trip-Vorbild).
4. `severity` (aktuell `alert_urgency.highest_urgency(...)` über die
   ungefilterte Liste, Z. 186-189) wird **nach** dem Filtern aus der
   verbleibenden Teilmenge neu berechnet — dieselbe Reihenfolge-Lehre wie im
   Trip-Vorbild (Z. 1749-1752).
5. Bleibt die gefilterte Liste vollständig leer, wird nichts verschickt.
6. Nach erfolgreichem Versand (`result.sent`): `record_event_identity` je
   erfolgreich zugestelltem `(alert, loc_id)`-Paar — analog dem bestehenden
   `_record_state()`-Aufruf (Z. 218), F001-Symmetrie, ausschließlich nach
   Erfolg.

### Kanalübergreifend, nicht je Kanal (V3) — unverändert aus S4b-1

Der neue Gate-Aufruf steht in beiden Services **vor**
`alert_channel_threshold.split_by_threshold()` (`compare_radar_alert.py:200`
/ `compare_official_alert.py:190`) — ein Ergebnis für den betroffenen Ort,
danach entscheidet die Kanal-Schwelle nur noch, auf welchem Weg eine bereits
freigegebene Meldung geht (ADR-0046).

### Aufrufstellen — letzte Stufe vor dem Versand, gespiegelt aus S4b-1

| Pfad | Position | Bestehende Stufen davor |
|---|---|---|
| `CompareRadarAlertService._check_one_preset()` | unmittelbar vor `notification_service.send_multi_location_radar_alert(...)` (`:207`), nach `severity`-Erstberechnung (`:193`) | `is_silenced` → `radar_alert_enabled` → `check_nowcast_gate` (`:145`) |
| `CompareOfficialAlertService._check_one_preset()` | unmittelbar vor `notification_service.send_multi_location_official_alert(...)` (`:193`), nach `severity`-Erstberechnung (`:186`) | `is_silenced` → `official_warnings.enabled` → `check_official_alert_gate` (`:143`) → `check_briefing_imminent` (`:159`) |

### Register — Ablage im bestehenden `AlertStateService`, EIN Register je Ort

Kein neuer Speicherort. `AlertStateService(user_id).load(f"{preset_id}:
{loc.id}")` liefert dieselbe Datei, in der bereits `radar_onset` (Radar) bzw.
die amtlichen Warnstufen-Schlüssel liegen — der neue `event_identity:`-
Präfix landet als zusätzlicher Schlüssel in derselben Ort-Datei (Read-
Modify-Write mit Merge, CLAUDE.md — bestehende Schlüssel bleiben unberührt).

### Reset-Regression (Pendant zu AC-14 aus S4b-1)

`AlertStateService.reset()` behält nur Schlüssel mit Präfix `official_alert:`
und verwirft alles andere (`alert_state.py:73-100`, S4b-1-Erkenntnis). Der
neue `event_identity:`-Präfix profitiert davon automatisch — auch für
Compare-Entitäten, ohne Code-Änderung an `reset()` selbst. Diese Scheibe
sichert das mit einem eigenen Test in `tests/tdd/
test_alert_state_briefing_reset.py` ab (Datei-Präfix `preset_id:loc_id`
statt `trip_id`).

## Expected Behavior

- **Input:** Radar-Nowcast bzw. amtliche Warnung für einen Compare-Preset,
  bereits vorhandener passender Registereintrag derselben Gefahrenklasse,
  desselben Orts und überlappenden Zeitfensters unter demselben Ort-Schlüssel
  `f"{preset_id}:{loc.id}"`.
- **Output:** die zweite Meldung wird — außer bei Eskalation (V2) oder
  wesentlicher Zeitfenster-Erweiterung (V1-Ausnahme) — für genau diesen Ort
  unterdrückt; andere Orte im selben Lauf und andere, eigenständige Alarme im
  selben Lauf bleiben unberührt.
- **Side effects:** Protokolleintrag (`alert_log.append_suppressed_entry`,
  `REASON_EVENT_DUPLICATE`) bei Unterdrückung; Registereintrag
  (`record_event_identity`) ausschließlich nach erfolgreicher Zustellung.

## Acceptance Criteria

**Design-Entscheidung `segment_ids`**

- **AC-0:** Given zwei aufeinanderfolgende Meldungen für DENSELBEN
  Compare-Ort (`preset_id`+`loc.id` identisch), gleiche Gefahrenklasse,
  überlappendes Zeitfenster — erst ein Radar-Nowcast, danach eine amtliche
  Warnung —, When beide über `check_event_identity_gate` mit
  `segment_ids=[loc.id]` geprüft werden, Then erkennt die zweite Prüfung
  tatsächlich einen Match und die amtliche Warnung wird unterdrückt — nicht
  nur, dass der Gate-Aufruf stattfindet, sondern dass er wirksam ein
  Duplikat erkennt.
  - Test: Nowcast erfolgreich zustellen (Registereintrag entsteht), danach
    amtliche Warnung mit überlappendem Fenster/gleichem Ort/gleicher Klasse
    auslösen, `allowed=False` UND `reason=REASON_EVENT_DUPLICATE`.
  - Mutations-Gegenprobe (PFLICHT): `segment_ids=[]` statt `segment_ids=
    [loc.id]` an beiden Aufrufstellen (Check UND Record) MUSS diesen Test rot
    machen — genau der No-Op-Bug, den diese AC ausschließen soll.

**Baustein-Wiring (Radar)**

- **AC-1:** Given einen getriggerten Ort in `CompareRadarAlertService.
  _check_one_preset()`, When der Nowcast vor dem gebündelten Versand geprüft
  wird, Then ruft der Pfad denselben `check_event_identity_gate` auf, der
  bereits im Trip-Nowcast-Pfad läuft — kein eigener, zweiter Compare-Baustein.
  - Test: Aufrufzähler (Spion, gepatcht auf `compare_radar_alert`-Modul-
    Namespace, da benannter Import) auf `check_event_identity_gate`, ≥1
    Aufruf je getriggertem Ort in einem Preset-Lauf mit `wet`-Klasse.

- **AC-2:** Given eine erfolgreich zugestellte Radar-Nowcast-Meldung für
  einen Compare-Ort, When der Versand abgeschlossen ist, Then legt
  `record_event_identity` genau EINEN Registereintrag unter dem Präfix
  `event_identity:<hazard_class>:` in der Ort-Datei
  (`f"{preset_id}:{loc.id}"`) ab.
  - Test: Zustellung simulieren, `AlertStateService.load(f"{preset_id}:
    {loc.id}")` nach dem Lauf enthält genau einen neuen `event_identity:`-
    Schlüssel mit allen Pflichtfeldern.

- **AC-3:** Given einen fehlgeschlagenen Zustellversuch (kein Kanal
  erreichbar), When der Lauf beendet ist, Then wurde KEIN Registereintrag
  angelegt — Registrierung ausschließlich nach erfolgreicher Zustellung
  (F001-Symmetrie).
  - Test: alle Kanäle unerreichbar simulieren, Register-Snapshot vor/nach
    dem Lauf identisch.

**Baustein-Wiring (amtlich)**

- **AC-4:** Given ein `(alert, loc_ids)`-Paar in `CompareOfficialAlertService.
  _check_one_preset()`, When die amtliche Warnung vor dem gebündelten
  Versand geprüft wird, Then ruft der Pfad denselben
  `check_event_identity_gate` auf wie der Radar-Pfad und der Trip-Pfad — kein
  eigener, dritter Baustein.
  - Test: Aufrufzähler (Spion, gepatcht auf `compare_official_alert`-Modul-
    Namespace), ≥1 Aufruf je betroffenem Ort in einem Preset-Lauf mit
    `wet`-Klasse.

- **AC-5:** Given eine erfolgreich zugestellte amtliche Warnung für einen
  Compare-Ort, When der Versand abgeschlossen ist, Then legt
  `record_event_identity` genau EINEN Registereintrag unter dem Präfix
  `event_identity:<hazard_class>:` in der Ort-Datei ab, mit Segment-Kennung,
  Dringlichkeit und Zeitfenster.
  - Test: Zustellung simulieren, Register-Datei enthält genau einen neuen
    `event_identity:`-Schlüssel mit allen Pflichtfeldern.

**Kernfall — Ereignis-Identität greift**

- **AC-6:** Given einen bereits registrierten Radar-Nowcast-Eintrag
  (Klasse `wet`, Ort `A`, Onset `T`), When kurz danach eine amtliche
  Warnung derselben Klasse für denselben Ort eintrifft, deren
  Gültigkeitsfenster den Onset-Punkt (mit dem bestehenden 60-Min-Puffer)
  überlappt, Then wird die amtliche Warnung unterdrückt — der Ort wird aus
  der zu versendenden `tagged_alerts`-Teilmenge entfernt.
  - Test: Nowcast-Eintrag vorbelegen (echte Zustellung oder direktes
    `record_event_identity`), amtliche Warnung mit überlappendem Fenster
    auslösen, `tagged_alerts`/versendete Warnungen enthalten den Ort NICHT
    mehr, Protokoll zeigt einen `not_delivered`-Eintrag mit
    `gate_reason=REASON_EVENT_DUPLICATE`.

- **AC-7 (Gegenrichtung):** Given einen bereits registrierten amtlichen
  Warnungs-Eintrag derselben Klasse für einen Ort, When danach ein
  Radar-Nowcast mit überlappendem Zeitfenster für denselben Ort ausgelöst
  wird, Then wird der Nowcast unterdrückt — die Entdopplung wirkt
  symmetrisch in beide Richtungen (dasselbe Register, wer zuerst zustellt,
  schreibt).
  - Test: amtliche Warnung zuerst registrieren, Nowcast mit überlappendem
    Onset danach auslösen, Ort wird aus der Radar-Zielliste gefiltert.

**Eskalation durchbricht immer (V2)**

- **AC-8:** Given eine bereits registrierte Meldung niedrigerer
  Dringlichkeit für einen Compare-Ort, When eine zweite Meldung derselben
  Klasse/desselben Orts mit HÖHERER Dringlichkeit eintrifft — unabhängig
  davon, ob ihr Zeitfenster das abgedeckte wesentlich erweitert —, Then wird
  sie zugestellt, nicht unterdrückt.
  - Test: zweite Meldung mit höherer Dringlichkeit und Zeitfenster
    vollständig innerhalb des abgedeckten Fensters, Ort bleibt in der
    versendeten Zielliste.
  - Mutations-Gegenprobe (PFLICHT): keine eigene Eskalationslogik in den
    Compare-Services einbauen, die den geteilten Baustein umgeht — dieser
    Test bricht bereits, wenn `check_event_identity_gate` durch eine lokale
    Vergleichsfunktion ersetzt wird, die die Eskalation nicht implementiert.

**Fail-soft**

- **AC-9:** Given eine Meldung ohne vergleichbaren Zeitbezug ODER einen
  Registereintrag mit unparsbarem/fehlendem Feld (kaputtes Format), When
  `check_event_identity_gate` in einem der beiden Compare-Pfade geprüft
  wird, Then entsteht KEIN Match — die Meldung wird zugestellt, kein
  Absturz.
  - Test: je ein Fall mit fehlendem Zeitbezug pro Pfad UND ein Fall mit
    kaputtem Registereintrag (fehlendes `severity`-Feld), alle Fälle liefern
    Zustellung.

**Registrierung ausschließlich nach Erfolg**

- **AC-10:** Given einen erfolgreich zugestellten Compare-Radar-Alarm, When
  man die Aufrufreihenfolge zur Laufzeit beobachtet, Then wird
  `record_event_identity` ERST NACH `notification_service.
  send_multi_location_radar_alert(...)` UND nur bei `notif_result.sent ==
  True` aufgerufen — niemals davor.
  - Test: Aufruf-Sequenz-Spionage (Order-Spy) über beide Funktionen, echter
    Lauf mit erfolgreichem Versand; zusätzlich ein Lauf mit `sent=False`
    (kein zustellbarer Kanal), der zeigt, dass `record_event_identity` DANN
    gar nicht aufgerufen wird. Ein reiner Quellcode-Grep genügt nicht —
    entscheidend ist die Laufzeit-Reihenfolge (das ist exakt die Lücke, die
    in S4b-1 erst die Mutations-Gegenprobe fand).

- **AC-11:** Dasselbe für den amtlichen Compare-Pfad — `record_event_identity`
  läuft ERST NACH `notification_service.
  send_multi_location_official_alert(...)` UND nur bei `result.sent ==
  True`.
  - Test: Order-Spy analog AC-10 für `CompareOfficialAlertService`.

**Batch-Teilfilterung — Radar**

- **AC-12:** Given einen Preset-Lauf mit zwei getriggerten Orten — einer
  davon ein Duplikat eines bereits registrierten amtlichen Ereignisses, der
  andere unabhängig neu —, When `_check_one_preset()` läuft, Then wird NUR
  der duplizierte Ort aus der gebündelten Radar-Alarm-Mail entfernt, der
  andere Ort bleibt enthalten — keine Alles-oder-nichts-Entscheidung über
  das ganze Preset.
  - Test: zwei Orte im selben Preset-Lauf, einer mit vorregistriertem
    passendem amtlichen Eintrag, `entities`/versendete Zielliste enthält nur
    den nicht-duplizierten Ort, Protokoll zeigt einen `not_delivered`-
    Eintrag für den unterdrückten Ort.

**Batch-Teilfilterung — amtlich, inkl. Mehrfach-Ort-pro-Alert**

- **AC-13:** Given einen Preset-Lauf mit zwei amtlichen Warnungen
  unterschiedlicher Hazards für unterschiedliche Orte — eine davon ein
  Duplikat eines bereits registrierten Nowcast-Ereignisses, die andere
  eigenständig —, When `_check_one_preset()` läuft, Then wird NUR die
  duplizierte Warnung unterdrückt, die andere wird zugestellt.
  - Test: analog AC-17 aus S4b-1, auf zwei verschiedene `tagged_alerts`-
    Paare übertragen.

- **AC-14 (Mehrfach-Ort-pro-Alert):** Given EINEN amtlichen Alert, der ZWEI
  Compare-Orte betrifft (`(alert, [loc_a, loc_b])`), von denen an `loc_a`
  bereits ein passender Registereintrag existiert und an `loc_b` nicht,
  When `_check_one_preset()` diesen Alert prüft, Then wird die Warnung NUR
  an `loc_a` unterdrückt und weiterhin an `loc_b` zugestellt — das Paar wird
  auf `(alert, [loc_b])` reduziert, nicht komplett verworfen und nicht
  ungefiltert an beide Orte gesendet.
  - Test: ein Alert mit `loc_ids=[loc_a.id, loc_b.id]`, Registereintrag nur
    für `loc_a` vorbelegen, versendete `tagged_alerts`-Struktur enthält den
    Alert nur noch mit `loc_ids=[loc_b.id]`, Protokoll zeigt einen
    `not_delivered`-Eintrag für `(alert, loc_a)`.

**Mandantentrennung**

- **AC-15:** Given zwei verschiedene Nutzer mit je einem Compare-Preset
  gleicher `preset_id` und gleicher `location_ids`, deren Registereinträge
  unabhängig geführt werden, When Nutzer A einen Nowcast-Eintrag
  registriert und Nutzer B unabhängig davon eine amtliche Warnung derselben
  Klasse/desselben Orts auslöst, Then wirkt A's Registereintrag NICHT auf
  B — B erhält seine Warnung, ohne Rückfall auf `"default"`.
  - Test: zwei `user_id`-Kontexte (A/B), gleiche `preset_id`/`location_id`,
    A registriert, B's amtliche Warnung geht trotzdem durch — für BEIDE
    Services (Radar UND amtlich) je ein Fall.

**Reset-Regression**

- **AC-16:** Given einen Compare-Ort mit einem `event_identity:`-
  Registereintrag UND einem bestehenden Compare-Dedup-Eintrag
  (`radar_onset` bzw. amtlicher Warnstufen-Schlüssel), When
  `AlertStateService.reset(f"{preset_id}:{loc.id}")` beim Briefing-Versand
  läuft (falls für Compare-Entitäten aufgerufen — sonst als reiner
  Bausteintest ohne Compare-Aufrufer), Then ist der `event_identity:`-
  Eintrag danach verschwunden, der bestehende Dedup-Eintrag bleibt
  unverändert erhalten.
  - Test: Ergänzung in `tests/tdd/test_alert_state_briefing_reset.py`,
    Datei-Präfix `f"{preset_id}:{loc_id}"` statt `trip_id`, sonst identischer
    Aufbau zu AC-14 aus S4b-1.

**Regression zu S4b-1**

- **AC-17:** Given die Funktionssignaturen von `check_event_identity_gate`,
  `record_event_identity` und `resolve_hazard_class` nach Abschluss dieser
  Scheibe, When man sie inspiziert, Then sind sie UNVERÄNDERT gegenüber
  S4b-1 — diese Scheibe fügt keine neuen Parameter hinzu, sie ruft den
  bestehenden Baustein nur an zwei neuen Stellen auf.
  - Test: `inspect.signature(...)` für alle drei Funktionen unverändert
    gegenüber dem S4b-1-Stand (Diff der Parameterliste ist leer).

- **AC-18:** Given die bestehenden Trip-Wiring-Tests aus S4b-1
  (`tests/tdd/test_issue_1088_official_alert_triggers.py::
  TestS4bEventIdentityWiring`, Nowcast-Äquivalent), When diese Scheibe
  abgeschlossen ist, Then bleiben sie unverändert grün — die
  Compare-Verdrahtung ändert nichts am Trip-Verhalten.
  - Test: bestehende S4b-1-Suite unverändert ausführen, keine Regression.

**Dokumentation**

- **AC-19:** Given den ADR-0021-Nachtrag aus S4b-1 (Issue #1467, datiert
  2026-08-16), When diese Scheibe abgeschlossen ist, Then trägt ADR-0021
  einen weiteren, datierten Nachtrag mit Bezug auf „#1917" und „S4b-2", der
  festhält, dass die quellenübergreifende Ereignis-Identität-Prüfung seit
  dieser Scheibe auch für den Ortsvergleich gilt (nicht nur Trip) — ohne die
  S4b-1-Aussagen zu widerrufen.
  - Test: `# doc-compliance-test` — ADR-0021 enthält nach Abschluss einen
    Nachtrag-Absatz mit Bezug auf „#1917" und „S4b-2", datiert nach dem
    2026-08-18.

## Known Limitations

- **Der Mehrfach-Ort-pro-Alert-Fall (AC-14) erhöht die Zahl der
  Gate-Aufrufe** gegenüber dem Trip-Pfad — ein Alert mit N betroffenen Orten
  löst N einzelne `check_event_identity_gate`-Aufrufe aus statt einem
  Aufruf mit einer `segment_ids`-Liste. Fachlich richtig (Registertrennung
  läuft je Ort), aber ein künftiges Performance-Audit sollte diese Stelle
  kennen, falls Presets mit sehr vielen Orten üblich werden.
- **Punkt-gegen-Punkt und Intervall-gegen-Intervall bleiben weiterhin
  isoliert getestet** (S4b-1-Limitation, unverändert) — auch über die
  Compare-Aufrufstellen ist nur Punkt-gegen-Intervall real erreichbar.
- **Änderungsalarm (Δ) als dritte Prüfrichtung bleibt offen** (S4b-3,
  optional, falls PO das priorisiert) — außerhalb des Scopes dieser Scheibe.
- **Weitere Gefahrenarten über den `wet`-Kanon hinaus** bleiben außerhalb
  des Scopes — der Kanon ist eine S4b-1-Entscheidung, hier unverändert
  übernommen.

## Non-Goals / Notes

- **Der Baustein selbst (`alert_gate.py`) wird nicht verändert** — kein
  neuer Parameter, keine neue Klasse, kein neues Zeitvergleichs-Verhalten.
  Diese Scheibe ist reine Verdrahtung.
- **Kein neuer Go-Endpunkt, kein neuer Cron-Job, kein Frontend-Code.**
- **Der bestehende Compare-Dedup-Mechanismus** (`radar_onset`-Eintrag im
  Radar-Pfad, amtliche Warnstufen-Vergleich in `official_alert_revision_
  verdict` im amtlichen Pfad) bleibt vollständig bestehen und unverändert
  zuständig für gleiche-Quelle-gegen-gleiche-Quelle — diese Scheibe fügt nur
  die quellenübergreifende, letzte Stufe hinzu (analog S4b-1 T7-Abgrenzung
  zum Trip-Doppel-Alert-Guard, hier gibt es aber kein Compare-Pendant zu T7,
  da Compare bislang keinen sektionsübergreifenden Guard hatte).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilter Auswertungskern) bekommt
  einen weiteren Nachtrag, im Anschluss an den S4b-1-Nachtrag
  (`docs/adr/0021-shared-deviation-alert-engine.md:189-206`).
- **Rationale:** Diese Scheibe führt kein neues Architekturprinzip ein —
  sie verdrahtet einen in S4b-1 bewusst entitätsparametrisiert gebauten
  Baustein an zwei zusätzlichen, bereits bestehenden Aufrufstellen. Die
  Konsistenz-Aussage aus ADR-0021 (ein geteilter Baustein statt N
  eigenständiger Prüfketten je Quelle/Fläche) gilt damit vollständig auch
  für Compare.

## Test-Plan

Kern-Schicht (deterministisch, kein Netz), sofern nicht anders vermerkt.

| AC | Datei | Schicht |
|---|---|---|
| AC-0 inkl. Gegenprobe | `tests/tdd/test_compare_radar_alert_event_identity.py` ODER `test_compare_official_alert_event_identity.py` (ein Fall genügt strukturell, empfohlen: beide) | Kern |
| AC-1, AC-2, AC-3 (Radar-Wiring) | `tests/tdd/test_compare_radar_alert_event_identity.py` | Kern |
| AC-4, AC-5 (amtlich-Wiring) | `tests/tdd/test_compare_official_alert_event_identity.py` | Kern |
| AC-6 (Kernfall) | `tests/tdd/test_compare_official_alert_event_identity.py` | Kern |
| AC-7 (Gegenrichtung) | `tests/tdd/test_compare_radar_alert_event_identity.py` | Kern |
| AC-8 inkl. Gegenprobe (V2 Eskalation) | eine der beiden neuen Testdateien | Kern |
| AC-9 (fail-soft) | beide neuen Testdateien, je ein Fall | Kern |
| AC-10 (Reihenfolge Radar) | `tests/tdd/test_compare_radar_alert_event_identity.py` | Kern |
| AC-11 (Reihenfolge amtlich) | `tests/tdd/test_compare_official_alert_event_identity.py` | Kern |
| AC-12 (Batch-Teilfilterung Radar) | `tests/tdd/test_compare_radar_alert_event_identity.py` | Kern |
| AC-13, AC-14 (Batch-Teilfilterung amtlich, Mehrfach-Ort) | `tests/tdd/test_compare_official_alert_event_identity.py` | Kern |
| AC-15 (Mandantentrennung) | beide neuen Testdateien | Kern |
| AC-16 (Reset-Regression) | `tests/tdd/test_alert_state_briefing_reset.py` (ergänzt) | Kern |
| AC-17 (Signatur-Regression) | eine der beiden neuen Testdateien | Kern |
| AC-18 (Trip-Regression) | bestehende `tests/tdd/test_issue_1088_official_alert_triggers.py::TestS4bEventIdentityWiring` unverändert grün | Kern |
| AC-19 (ADR-Nachtrag) | `# doc-compliance-test` bzw. `tests/test_adr_index_drift.py` | Kern |

Live-E2E: keine eigenen Live-Marker-Tests — echte quellenübergreifende
Doppelungen für Compare sind nicht auf Bestellung provozierbar. Staging-
Nachweis über gezielt gesetzte Registereinträge (analog S4b-1), nicht über
„auf ein echtes Gewitter warten".

## Wächter, die mitziehen müssen

| Test | Warum |
|---|---|
| `tests/tdd/test_compare_radar_alert.py` | bestehendes Compare-Radar-Verhalten (Cooldown, Ruhezeit, Tageslimit) bleibt unverändert grün — die neue Stufe kommt NACH allen bestehenden |
| `tests/tdd/test_compare_official_alert.py` | bestehendes Compare-amtlich-Verhalten bleibt unverändert grün |
| `tests/tdd/test_issue_1088_official_alert_triggers.py::TestS4bEventIdentityWiring` | Trip-Verhalten aus S4b-1 bleibt unverändert (AC-18) |
| `tests/tdd/test_alert_state_briefing_reset.py` | bestehende Trip-Reset-Fälle aus S4b-1 bleiben unverändert grün, neuer Compare-Fall kommt hinzu |
| `tests/test_adr_index_drift.py` | Index↔Datei-Konsistenz für den ADR-Nachtrag |

## Reihenfolge der Arbeit

1. `compare_radar_alert.py` zuerst verdrahten (kleinerer, einfacherer Pfad —
   eine `loc.id` je getriggertem Ort, keine Mehrfach-Ort-Komplexität):
   AC-0 (Radar-Hälfte), AC-1, AC-2, AC-3, AC-7, AC-10, AC-12, AC-15
   (Radar-Hälfte).
2. `compare_official_alert.py` verdrahten inkl. Mehrfach-Ort-pro-Alert-Fall:
   AC-0 (amtlich-Hälfte), AC-4, AC-5, AC-6, AC-8, AC-9, AC-11, AC-13, AC-14,
   AC-15 (amtlich-Hälfte).
3. Reset-Regression (AC-16), Signatur-Regression (AC-17), Trip-Regression
   (AC-18) zuletzt, wenn das Verhalten feststeht.
4. ADR-Nachtrag zuletzt (AC-19).

## Risiken

| | Risiko (aus Nutzersicht) | Gegenmittel |
|---|---|---|
| **R-A** | `segment_ids=[]` statt `segment_ids=[loc.id]` verdrahtet — Gate sieht aus wie aktiv, unterdrückt aber nie (stiller No-Op-Bug). | AC-0 mit PFLICHT-Mutations-Gegenprobe genau auf diesen Fall zugeschnitten. |
| **R-B** | Mehrfach-Ort-pro-Alert wird als Alles-oder-nichts behandelt statt pro Ort gefiltert — ein Ort verliert fälschlich seine berechtigte Warnung, oder der andere Ort bekommt fälschlich eine Dublette. | AC-14 als eigener Test mit differenzierten Registerständen je Ort. |
| **R-C** | `record_event_identity` wird vor dem Versand oder unabhängig vom Zustellergebnis aufgerufen. | AC-10/AC-11 mit Order-Spy UND explizitem Fehlschlag-Fall (analog der S4b-1-Lücke, die erst die Mutations-Gegenprobe fand). |
| **R-D** | Batch-Teilfilterung im Radar-Pfad verschluckt einen echten zweiten, eigenständigen Alarm zusammen mit einer Dublette im selben Preset-Lauf. | AC-12 mit zwei unterschiedlichen Orten im selben Lauf. |
| **R-E** | Ein leeres/unbekanntes Registerformat wird als Match interpretiert und unterdrückt fälschlich. | AC-9 fail-soft-Test mit kaputtem Registereintrag. |

## Changelog

- 2026-08-18: Initiale Spec, gespiegelt aus `rework_1467_s4b_entdopplung.md`
  (S4b-1, Trip). Segment-IDs-Design-Entscheidung gegen den tatsächlichen
  Code verifiziert (`alert_gate.py:508-510`), Aufrufstellen-Positionen und
  Signaturen gegen `compare_radar_alert.py`/`compare_official_alert.py`/
  `trip_alert.py` verifiziert (Zeilenangaben gegen den Stand dieses
  Worktrees zum Zeitpunkt der Spec-Erstellung).
