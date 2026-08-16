# Context: rework-1467-s4a-amtlich

Issue **#1467** Scheibe **S4a** (Teilarbeit — schliesst #1467 **nicht**; das tut erst S4b).
Erhoben 2026-08-16 am Stand `098226ae`.

## Request Summary

Die beiden **amtlichen** Alarmpfade (offizielle Wetterwarnungen: Ortsvergleich und Trip) sollen
durch denselben Freigabe-Baustein laufen wie die Nowcast-Pfade seit S3, und die drei wortgleichen
Compare-Helfer sollen zu einem werden. Zielmarke: **Verhalten unveraendert**, ausser wo ein
Akzeptanzkriterium ausdruecklich etwas anderes sagt.

## Ist-Stand (gemessen, nicht aus dem Issue uebernommen)

Die Tabelle im Issue-Kopf stammt vom 2026-08-02 und ist ueberholt: `is_silenced`,
`check_briefing_imminent`, `alert_daily_limit`, `effective_compare_channels`, `alert_log` und
`alert_channel_threshold` sind **bereits geteilt**. Was fehlt, ist der gemeinsame **Ablauf**.

### Stufenvergleich der beiden amtlichen Pfade

| Stufe | Ortsvergleich (`compare_official_alert.py`) | Trip (`trip_alert.py::_send_official_alert_only`) |
|---|---|---|
| Stilllegungs-Riegel | `:100` `is_silenced(preset)` | **fehlt** (Trips kennen das Konzept nicht) |
| Ruhezeit | `:128` | `:1485` |
| Briefing-Vorlauf-Sperre | `:144` | `:1491` |
| Zeit-Cooldown | **keiner** (bewusst, `:10-19`) | `:1494` — Scope **`"trip"`**, geteilt mit dem Aenderungsalarm (`:246`) |
| Tages-Obergrenze | `:164` — **NACH** dem Abruf | `:1497` — **VOR** allem |
| *Datenbeschaffung* | `:159` `_detect()` | entfaellt (Warnungen kommen als Parameter herein) |
| Kanal-Aufloesung | `:169` | `:1503` |
| Schwellwert-Filter | `:179` | `:1511` |
| Versand | `:182` | `:1514` |
| Protokollierung | `:190` `append_entry` | `:1523` `append_entry` |
| Zustand + Zaehler | `:207-208` | `:1538-1542` |

### Wortgleiche Doppelungen

| Helfer | Fundstellen | Befund |
|---|---|---|
| `_load_presets()` | `compare_alert.py:592`, `compare_radar_alert.py:294`, `compare_official_alert.py:336` | **byte-identisch**, 3 Zeilen |
| `_notification_service_for()` | `compare_alert.py:576`, `compare_radar_alert.py:274`, `compare_official_alert.py:322` | strukturgleich, Unterschied **nur** im Warntext (`"Compare-Alert:"` / `"(Radar)"` / `"(amtlich)"`) |

Ein geteilter Helfer fuer beides existiert **nicht**. `scheduler_dispatch_service._load_presets_for_dispatch()`
hat eine andere Signatur und ist kein Ersatz.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_gate.py` (318 Z.) | **Die Vorlage.** `check_nowcast_gate` (Ruhezeit → Sperrzeit → Tages-Obergrenze, `GateResult(allowed, reason)`), `check_briefing_imminent`, `record_nowcast_sent` |
| `src/services/compare_official_alert.py` (338 Z.) | Ortsvergleich-Pfad; enthaelt `_day_window_end()` `:276` |
| `src/services/trip_alert.py` (1616 Z.) | Trip-Pfad, `_send_official_alert_only` ab `:1478`, `_is_throttled_with_cooldown` `:743` |
| `src/services/compare_alert.py` (595 Z.) | Traegt zwei der drei Doppelungen |
| `src/services/compare_radar_alert.py` (296 Z.) | Traegt zwei der drei Doppelungen; **von Struktur-Waechtern per Ordinal verankert** |
| `src/services/alert_log.py` | `append_entry`, `append_suppressed_entry`, `REASON_*` `:47-49` |
| `src/services/alert_daily_limit.py` | `is_allowed(user_id, now, zone, reason=None)`, `increment(user_id, now, zone)` |
| `src/services/compare_alert_guard.py` (54 Z.) | `is_silenced(preset)` |
| `src/services/compare_alert_channels.py` | `effective_compare_channels`, `effective_compare_telegram_style` |

## Existing Patterns

- **Hausmuster S2 AG1 / S3:** Ein neuer geteilter Baustein bekommt **sofort beide** Verbraucher.
  Ein Baustein mit genau einem Aufrufer waere keine Entdopplung, sondern eine weitere Fassung.
- **`GateResult`-Muster:** Abbruch bei der ersten zutreffenden Stufe, Grund als `REASON_*`-Konstante
  zurueck; die Aufrufstelle entscheidet, ob sie ihn protokolliert.
- **Zaehler-Invariante:** `alert_daily_limit.increment()` und `throttle_store.record()` laufen erst
  **nach** erfolgreicher Zustellung (`record_nowcast_sent`, `alert_gate.py:304`).
- **Trip/Compare-Teilungsregel:** eine Compare-eigene Zweitfassung eines Trip-Bausteins ist ein Verstoss.

## Dependencies

- **Upstream:** `ThrottleStore`, `AlertStateService`, `DeviationAlertEngine.is_quiet_hours`,
  `alert_daily_limit`, `alert_log`, `official_alerts.get_official_alerts_for_location`,
  `compare_slot_scheduler.presets_due_for_hour`, `output.renderers.day_window.resolve_configured_window`
- **Downstream:** die `*/15`-Scheduler-Endpunkte, `NotificationService.send_official_alert` /
  `send_multi_location_official_alert`, das Alarm-Protokoll (Go liest es: `internal/store/log.go`)

## Existing Specs & ADRs

| Dokument | Was daraus bindet |
|---|---|
| `docs/specs/modules/rework_1467_s3_nowcast.md` | Vorgaenger-Spec, 16 ACs. Struktur und AC-Zuschnitt sind die Vorlage |
| `docs/specs/modules/issue_1216_slice2_compare_official_alert.md` | Ursprungs-Spec des Ortsvergleich-Pfads |
| `docs/specs/modules/compare_official_alert_channels.md` | Kanal-/Schwellenverhalten des amtlichen Alarms |
| `docs/specs/modules/fix_1685_warnfenster_revision.md` | stille Fenster-Revision — darf nicht brechen |
| `docs/adr/0021-shared-deviation-alert-engine.md` | Grundsatz + **drei Nachtraege**; Nachtrag 2 sagt heute ausdruecklich „Aenderungs- und amtlicher Alarm bewusst nicht" — S4a macht diesen Satz falsch und muss ihn als **vierten Nachtrag** korrigieren, kein neues ADR |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | ein Tagesfenster, wirksam auf Anzeige **und** Bewertung |
| `docs/context/rework-1460-alerts-relevanzfilter.md` | Ursprungsanalyse; amtlicher Pfad in Z. 49, 65–67, 76, 99–102, 223–224 |

## Waechter, die mitziehen muessen

| Test | Warum |
|---|---|
| `tests/tdd/test_alert_gate.py` | `test_ac11_ruhezeit_stoppt_vor_der_sperrzeit_pruefung`, `test_ac11_sperrzeit_stoppt_vor_der_tages_obergrenze` — die Reihenfolge-Waechter |
| `tests/tdd/test_nowcast_suppression_logging.py` | **`test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund`** — bewacht heute ausdruecklich, dass der amtliche Pfad **keine** Unterdrueckungs-Gruende protokolliert. Wenn S4a das aendert, ist dieser Waechter zu **ersetzen**, nicht zu loeschen |
| `tests/tdd/test_compare_official_alert_briefing_imminent.py` | `test_ac4_sperre_greift_vor_dem_warnungs_abruf` — Sperre vor der Datenbeschaffung |
| `tests/tdd/test_compare_official_alert.py` | AC-1 bis AC-8 des Ortsvergleich-Pfads |
| `tests/tdd/test_issue_1088_official_alert_triggers.py` | Trip-Ausloeser |
| `tests/test_success_status_guard.py`, `tests/test_resolution_loss_guard.py` | verankern `compare_radar_alert.py` per `datei::funktion::ordinal` — ein zusaetzlicher Aufruf verschiebt die Zaehlung. **Schluessel nachziehen, Waechter nicht aufweichen** |

## Risks & Considerations

**R1 — „Alarm bleibt aus" ist der gefaehrlichste Fehler.** Jede Angleichung, die eine Stufe
hinzufuegt, kann eine echte Warnung unterdruecken. Jede Stufe braucht einen Test, der belegt, dass
sie **nur** in dem Fall greift, fuer den sie gedacht ist.

**R2 — Der Trip-amtliche Cooldown teilt sich den Topf mit dem Aenderungsalarm.**
`trip_alert.py:1494` und `:246` benutzen beide `ThrottleStore`-Scope `"trip"`. Ein Aenderungsalarm
um 16:00 unterdrueckt damit heute eine amtliche GELB→ORANGE-Verschaerfung um 16:20 — genau die
Wirkung, die das Issue fuer den Ortsvergleich ausdruecklich ausschliesst. **Das ist kein Umbau,
sondern eine Entscheidung** (siehe unten).

**R3 — Der Ortsvergleich prueft die Tages-Obergrenze nach dem Abruf.** Ein erschoepftes Kontingent
kostet trotzdem einen Warnungs-Abruf. Vorziehen aendert das Kontingent-Verhalten nicht, aber die
Zahl der Fremd-Abrufe — und damit potentiell die Fehlerbilder bei Quellen-Ausfall.

**R4 — `_day_window_end()` ist Compare-eigen ohne Trip-Pendant** (`compare_official_alert.py:276`).
Zwei Beobachtungen: (a) Bei einem normalen Fenster (4–19) liefert die Methode nach 19:00 Ortszeit
ein **nullbreites** Fenster `[now, now]` — beabsichtigt laut Docstring („statt abends taub"), aber
nirgends von einem Test gehalten. (b) Sie ruft `self._load_presets()` **innerhalb** der Ortsschleife
(`:239` → `:291`), liest also je Ort alle Presets neu.

**R5 — Waechter-Ordinale.** `compare_radar_alert.py` ist per Ordinal verankert; das war schon in S3
eine Known Limitation (R6 dort).

**R6 — Mandantentrennung.** Beide Pfade sind nutzerbezogen; Pflicht-Nachweis mit **zwei**
verschiedenen Nutzern.

**R7 — Bestandsdaten.** Alarm-Protokoll und `alert_state` muessen altlesbar bleiben;
Read-Modify-Write mit Merge.

## Zu entscheiden (gehoert in die Akzeptanzkriterien, nicht in einen Nebeneffekt)

1. **Trip-amtlicher Cooldown** — bleibt er im geteilten `"trip"`-Topf (Status quo, Eskalation kann
   unterdrueckt werden), bekommt er einen eigenen Scope, oder faellt er wie beim Ortsvergleich weg?
2. **Tages-Obergrenze beim Ortsvergleich vor den Abruf ziehen** — ja/nein.
3. **Unterdrueckungs-Gruende protokollieren** — S3 hat das ausdruecklich auf die Nowcast-Pfade
   begrenzt und einen Waechter dafuer gebaut. Zieht S4a den amtlichen Pfad nach?
4. **Stilllegungs-Riegel beim Trip** — Trips kennen kein `is_silenced`. Bleibt das so?

---

# Analysis (Phase 2, 2026-08-16)

## Type

**Feature/Rework** — Umbau mit zwei bewussten Verhaltensaenderungen, kein Bugfix-Workflow.

## Die vier Entscheidungen — jetzt mit Belegen

### E1 — Trip-amtlicher Cooldown: BELEGT, und schlimmer als vermutet

- `trip_alert.py:1494` liest Scope `"trip"` (`:763-765`).
- **Genau zwei** Schreibstellen im Modul: `:358` (Aenderungsalarm) und `:1539` (amtlich) —
  **beide** Scope `"trip"`, beide auf `trip.id`. Radar/Nowcast nutzt `"radar"` (`:53`), ist nicht beteiligt.
- **Kein Eskalations-Umweg.** `_send_official_alert_only` prueft den Cooldown unbedingt vor allem
  Versand-Code; `official_alert_revision_verdict` entscheidet nur, *welche* Warnungen als neu/eskaliert
  gelten, und fasst den ThrottleStore nicht an.
- **Default-Cooldown = 120 Minuten** (`trip.alert_cooldown_minutes` Default `None` →
  `throttle_hours * 60`, `throttle_hours=2` als Konstruktor-Default `trip_alert.py:133`).

⇒ Ein Aenderungsalarm unterdrueckt eine amtliche GELB→ORANGE-Verschaerfung **bis zu zwei Stunden**.
Das ist die Wirkung, die das Issue fuer den Ortsvergleich ausdruecklich ausschliesst.

**Wichtige Unterscheidung, die der erste Entwurf uebersehen hat:** Lesen und Schreiben sind
getrennt zu entscheiden.

| | heute | „ersatzlos streichen" | **Empfehlung** |
|---|---|---|---|
| amtlich **liest** `"trip"` | ja | nein | **nein** |
| amtlich **schreibt** `"trip"` | ja | nein | **ja (bleibt)** |
| Folge fuer die Eskalation | wird verschluckt | kommt durch | **kommt durch** |
| Folge fuer die Aenderungsalarm-Menge | unveraendert | **steigt** | **unveraendert** |

Nur das Lesen zu streichen behebt die gefaehrliche Richtung („Alarm bleibt aus") und laesst die
harmlose Richtung („Alarm kommt zusaetzlich") unangetastet. Die harmlose Richtung ist ohnehin der
Gegenstand von S4b (#1744 B: Entdopplung nach Ereignis-Identitaet) — dort wird sie mit dem richtigen
Werkzeug geloest, nicht mit einer pauschalen Zeitsperre.

### E2 — Tages-Obergrenze vor den Abruf: JA, mit echtem Nutzen

- `official_alerts/warn_egress.py:38-44` — TTL-Cache (30 min Erfolg / 60 s Fehler / 24 h „nicht abgedeckt").
- `official_alerts/meteoalarm_budget.py` — echter Tageskontingent-Zaehler,
  `DEFAULT_DAILY_BUDGET = 100`, Ruecknahme via `x-ratelimit-reset`.
- **Das Kontingent-Problem ist real und produktiv belegt:** `docs/specs/modules/warn_service_consumption.md:22-28`
  („liefert in Prod dauerhaft HTTP 429"), `fix_1397_meteoalarm_coverage_budget.md` (gemessen ~160
  Abrufe / rollierende 24 h).

⇒ Ein Abruf bei erschoepftem Tageslimit ist bei Cache-Treffer folgenlos, bei Cache-Fehltreffer aber
ein echter Netz-Aufruf gegen ein knappes, produktiv bereits erschoepftes Kontingent.

⚠️ **Korrektur zur Phase-1-Darstellung:** Der Trip ruft die Warnungen ebenfalls **vor** seiner
Kontingent-Pruefung ab (`trip_alert.py:479` liegt vor `:1497`). Die Reihenfolge *innerhalb*
`_send_official_alert_only` ist zwar frueher, der teure Abruf aber nicht. Die Asymmetrie zwischen
beiden Pfaden ist damit kleiner als in Phase 1 beschrieben — das Vorziehen beim Trip waere ein
anderer, groesserer Umbau an einer anderen Stelle und ist **Nicht-Ziel** dieser Scheibe.

### E3 — Unterdrueckungsgruende beim amtlichen Pfad protokollieren: NEIN in S4a

`tests/tdd/test_nowcast_suppression_logging.py:637-640` verbietet es mit harter Gleichheit
(`_gate_reasons_in_log(gesperrt) == set()`), Schwester-Test `:577-579` fuer den Aenderungsalarm.
Der Waechter wuerde brechen. Er ist **8 Tage alt und PO-freigegeben** (S3, AC-9) und haelt einen
bewusst gezogenen Geltungsbereich. Ihn in derselben Scheibe zu ersetzen, die den Pfad umbaut,
vermischt zwei Fragen. ⇒ Geltungsbereich bleibt Nowcast-only, Waechter bleibt unveraendert gruen.

### E4 — Trip-„stillgelegt": KEINE Aenderung, es ist Absicht

Trip **hat** `paused_at`/`archived_at` (`app/trip.py:200-201`), aber `trip_alert.py` prueft beide
**nicht** (0 Treffer im Modul). `trip_report_scheduler.py:882-888` sagt warum, woertlich:

> Issue #995: … NUR hier — NICHT in `load_all_trips()`, sonst wuerde der Alert-Dispatch
> (`trip_alert.py`) faelschlich mit unterdrueckt.

Ein pausierter Trip pausiert also den **Briefing-Versand**, nicht den Alarm. Ein `schedule`-Feld
wie beim Preset gibt es beim Trip gar nicht. ⇒ `is_silenced` bleibt **ausserhalb** des geteilten
Gates und Compare-eigen. Eigener Test, der das festhaelt (sonst zieht es der naechste „Vereinheitlicher" hinein).

## Technical Approach

**Neue Funktion in `src/services/alert_gate.py`:**

```python
def check_official_alert_gate(
    *, user_id: str, quiet_from: Optional[str], quiet_to: Optional[str],
    context_label: str, now: datetime, zone: ZoneInfo,
) -> GateResult:
```

Zwei Stufen, Abbruch bei der ersten: **Ruhezeit → Tages-Obergrenze**. **Kein
`cooldown_minutes`-Parameter.** Rueckgabetyp `GateResult` wird wiederverwendet.

**Warum keine Erweiterung von `check_nowcast_gate` um ein Flag:** `ThrottleStore.is_throttled()`
behandelt ein falsy `cooldown_minutes` heute schon als „nie gedrosselt" — mechanisch wuerde ein Flag
funktionieren. Es macht die Invariante „amtlich hat keinen Cooldown" aber zur **Disziplin des
Aufrufers** („vergiss nicht `None` zu uebergeben") statt zur Eigenschaft der Funktion. Bei einer
Zusicherung, deren Verletzung „Warnung bleibt aus" bedeutet, ist das der falsche Tausch.

**Aufrufstellen:**

| Pfad | faellt weg | tritt an die Stelle |
|---|---|---|
| `compare_official_alert.py::_check_one_preset` | `:120-136` (Ruhezeit inline), `:163-166` (Tageslimit inline) | ein `check_official_alert_gate(...)` **nach** `is_silenced` (`:100`) und **vor** `_detect()` (`:159`) |
| `trip_alert.py::_send_official_alert_only` | `:1485-1487` (Ruhezeit), `:1494-1496` (**Cooldown-Lesen**), `:1497-1501` (Tageslimit) | ein `check_official_alert_gate(...)` nach `_is_briefing_imminent` (`:1491`) |

`check_briefing_imminent` bleibt in beiden Pfaden ein **eigener** Aufruf (seit #1594 geteilt,
unveraendert). `_throttle_store.record("trip", …)` bei `trip_alert.py:1539` **bleibt** (siehe E1).
`_is_throttled_with_cooldown` bleibt als Methode bestehen — weiter genutzt vom Aenderungsalarm
(`:246`) und von `get_time_until_next_alert`.

**Geteilter Compare-Helfer:** neues Modul `src/services/compare_preset_access.py` mit
`load_compare_alert_presets(user_id)` und
`notification_service_for_preset(settings, user_id, preset, *, log_label)`. Die drei Bestandsmethoden
werden Ein-Zeiler-Wrapper (`log_label` traegt die einzige echte Abweichung — dasselbe Muster wie
`context_label` in `alert_gate.py`). Kein Verstoss gegen die Teilungsregel: ein Trip-Pendant
existiert nicht und wird nicht gebraucht.

## Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/services/alert_gate.py` | MODIFY | `check_official_alert_gate` (2 Stufen, ohne Cooldown) |
| `src/services/compare_official_alert.py` | MODIFY | Gate-Aufruf vor `_detect()`; Helfer werden Wrapper |
| `src/services/trip_alert.py` | MODIFY | Gate-Aufruf; Cooldown-**Lesen** entfaellt, Schreiben bleibt |
| `src/services/compare_preset_access.py` | CREATE | geteilter Preset-/Notification-Helfer |
| `src/services/compare_alert.py` | MODIFY | zwei Methoden → Wrapper |
| `src/services/compare_radar_alert.py` | MODIFY | zwei Methoden → Wrapper |
| `docs/adr/0021-shared-deviation-alert-engine.md` | MODIFY | **Nachtrag 4** — Nachtrag 2 („amtlicher Alarm bewusst nicht") wird sachlich falsch |
| `tests/tdd/test_alert_gate.py` | MODIFY | Stufen + Reihenfolge der neuen Funktion |
| `tests/tdd/test_compare_official_alert*.py` | MODIFY | Reihenfolge Limit-vor-Abruf, `is_silenced` ausserhalb |
| `tests/tdd/test_issue_1088_official_alert_triggers.py` | MODIFY | **Regression: Eskalation trotz juengerem Aenderungsalarm** |
| `tests/test_success_status_guard.py`, `tests/test_resolution_loss_guard.py` | MODIFY | Ordinal-Anker nachziehen (Assertion nicht aufweichen) |

## Scope Assessment

- Dateien: 6 produktiv (1 neu) + 1 ADR + ~6 Testdateien
- **Produktiv: ~150–180 hinzugefuegte/geaenderte Zeilen** → passt in 250
- **Tests: ~700–900 Zeilen** → **sprengt das Standard-Testbudget von 500**
- Risiko: **HOCH** — kritischer Alarmpfad, zwei bewusste Verhaltensaenderungen

## Reihenfolge der Arbeit

1. `check_official_alert_gate` + eigene Tests **zuerst**, bevor ein Aufrufer angefasst wird.
2. **Trip zuerst** (der heiklere Fall): erst der Regressionstest „Aenderungsalarm um T, amtliche
   Eskalation um T+15 min wird zugestellt" mit echt befuelltem `ThrottleStore`-Scope `"trip"`, dann der Umbau.
3. Dann Compare (nur Reihenfolge-Wechsel, profitiert von der geschaerften Test-Vorlage).
4. Ordinal-Waechter **nach jedem** der beiden Umbauten laufen lassen, nicht erst am Ende.
5. Preset-Helfer zum Schluss (reine Strukturverschiebung, faesst dieselben Dateien noch einmal an).
6. ADR-Nachtrag zuletzt, wenn das Verhalten feststeht.

## Risiken (aus Nutzersicht formuliert)

- **R-A:** Ist die Zonenaufloesung oder der Zaehlerstand im neuen Gate falsch, bleibt der Lauf
  **komplett stumm** — vorher waere wenigstens der Abruf gelaufen und die Symptome sichtbar gewesen.
  Gegenmittel: Nachweis bei Zaehlerstand 0 **und** Limit-1.
- **R-B:** Bleibt `_is_throttled_with_cooldown` versehentlich im amtlichen Aufrufpfad, bekommt der
  Nutzer die Eskalation weiterhin nicht. Gegenmittel: Regressionstest aus Schritt 2.
- **R-C:** Zieht jemand `is_silenced` spaeter „vereinheitlichend" ins Gate, aendert sich das
  Trip-Verhalten still. Gegenmittel: Test, der `is_silenced` ausdruecklich **ausserhalb** nachweist.
- **R-D:** Ein rot gewordener Ordinal-Waechter, der „korrigiert" statt verstanden wird, kann eine
  echte verlorene Fehlerbehandlung durchwinken — dann bleibt bei einem defekten Ortsdatensatz die
  Fehlermeldung aus.
- **R-E:** `_day_window_end()` wird **nicht angefasst**. Wandert es beim Umbau versehentlich mit,
  verliert der Nutzer nach 19 Uhr Ortszeit Warnungen (nullbreites Fenster, R4a).

## Open Questions (PO)

- [ ] E1: nur das **Lesen** des Trip-Cooldowns streichen (Empfehlung) oder Lesen **und** Schreiben?
- [ ] Test-Budget von 500 auf **900** anheben — sonst muss S4a in zwei Lieferungen zerfallen.

## Nicht-Ziele (ausdruecklich)

- **#1599** (Tagesfenster-Obergrenze: Anzeige zaehlt Stunde 19 mit, der Alarm nicht) ist eine offene
  **Bedeutungsfrage** mit drei gleichwertigen Auswegen und widerspricht einer bereits freigegebenen
  AC aus #1584. S4a entscheidet sie **nicht** und darf ihr Ergebnis nicht vorwegnehmen.
- **#1744 Scheibe B** (Entdopplung nach Ereignis-Identitaet ueber Quellen hinweg) ist S4b.
- **Datenbeschaffung wird nicht fusioniert.** Radar- und amtliche Quellen bleiben technisch
  eigenstaendig; zusammengelegt wird die Ablaufsteuerung.
- Compare-eigen bleiben: Orte statt Etappen, transponierte Uebersicht, Compare-Mail-Template,
  Buendelung aller getriggerten Orte in EINE Nachricht, Empfaenger als Preset-Attribut, Ortszeit-Bezug.
- Kein Vorgriff auf #1714, #1697, #1695 (offene Alarm-Issues in derselben Flaeche).
- **Der Trip-Warnungsabruf wird nicht vorgezogen** (`trip_alert.py:479`) — er sitzt im Sammel-Lauf
  ueber alle Trips, an ganz anderer Stelle; das waere ein eigener Umbau. → Sammel-Issue #1199.
- **`_day_window_end()` wird nicht angefasst.** Sein Abendverhalten (nullbreites Fenster nach
  Fensterende) ist heute von keinem Test gehalten — das ist ein Befund, kein Auftrag. → #1199.
- **Unterdrueckungsgruende bleiben Nowcast-only** (E3); der S3-Waechter bleibt unveraendert.
