# Context: fix-1555-nowcast-alert-priority

Issue: #1555 — NowCast-Alarme wurden system-weit nie zugestellt: stille Tier-Lücke +
geteiltes Tagesbudget starvt akute Gefahr.

Der akute Teil (Tier-Lücke bei `henning`) ist bereits per Datenfix behoben
(`data/users/henning/user.json` → `tier: "premium"`). Dieser Workflow behandelt den
verbleibenden strukturellen Vorschlag aus #1555: NowCast/akute Gefahr soll im geteilten
Tages-Alarmbudget nicht mehr "wer zuerst kommt" gegenüber reinen
Vorhersage-Abweichungs-Alarmen verlieren können.

## Analysis

### Type

Bug-Folgefeature (strukturelle Korrektur eines bestehenden, PO-entschiedenen Mechanismus
aus #1070) — kein neues Vorhersage-Abweichungs- oder NowCast-Feature, nur eine geänderte
interne Priorisierung innerhalb des bestehenden Tagesbudgets.

### Root Cause (bereits verifiziert, Step 0/1/2 aus der Bug-Analyse #1555)

1. `daily_alert_limit()` (`src/services/user_tier.py:17-31`) liefert `{"free": 2,
   "standard": 4, "premium": None}` je Konto — Gesamtobergrenze, PO-Entscheidung #1070
   (2026-07-07), **nicht Gegenstand dieses Workflows**.
2. Das Limit ist EIN geteilter Integer-Zähler pro Nutzer über ALLE Trips und ALLE
   Alarm-Gründe (`data/users/<uid>/alert_daily_count.json`,
   `src/services/alert_daily_limit.py::is_allowed()`/`increment()`).
3. Fünf Aufrufstellen teilen sich denselben Zähler, ohne Kenntnis voneinander:
   - `src/services/trip_alert.py:221` — Deviation-Alarm (`check_and_send_alerts`)
   - `src/services/trip_alert.py:761` — Radar/NowCast-Alarm (`check_radar_alerts`)
   - `src/services/trip_alert.py:1169` — amtliche Warnung (Official-Only-Pfad)
   - `src/services/compare_alert.py:145` — Compare-Deviation-Alarm
   - `src/services/compare_official_alert.py:136` — Compare-amtliche Warnung
4. `src/services/compare_radar_alert.py` (Compare-NowCast) ruft `alert_daily_limit`
   **gar nicht** auf — bereits heute ungebudgetiert. Bewusst NICHT Teil dieses
   Workflows (Scope-Explosion), nur als bekannte Inkonsistenz dokumentiert.
5. Cron: `internal/scheduler/scheduler.go:145` (`alertChecks`, Deviation+Official) und
   `:149` (`radarAlertChecks`, NowCast) sind zwei unabhängige `*/15 * * * *`-Jobs.
   `robfig/cron` startet fällige Jobs in getrennten Goroutinen — die
   Registrierungsreihenfolge hat **keinen** Effekt auf die tatsächliche
   Ausführungsreihenfolge. Ein reines Vertauschen der Zeilen würde nichts bewirken.
6. Befund system-weit: 0 von 118+ Alarm-Protokoll-Einträgen (alle 3 Nutzer) tragen
   `"reason": "nowcast"` — Deviation/Official verbrauchen das Budget faktisch immer
   zuerst.

### Affected Files (Empfehlung Option B, s. Technical Approach)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_daily_limit.py` | MODIFY | `is_allowed()` bekommt optionalen `reason`-Parameter (Default `None` = Altverhalten); bei `reason="forecast_change"` gegen `limit - RESERVE` statt `limit` prüfen |
| `src/services/trip_alert.py` | MODIFY | `reason=` an den 3 bestehenden `is_allowed()`-Aufrufen (:221, :761, :1169) ergänzen |
| `src/services/compare_alert.py` | MODIFY | `reason=` an Aufruf :145 ergänzen |
| `src/services/compare_official_alert.py` | MODIFY | `reason=` an Aufruf :136 ergänzen |
| `docs/specs/modules/alert_daily_limit.md` | MODIFY | Reserve-Regel dokumentieren |
| `tests/tdd/test_issue_1070_daily_alert_limit.py` | MODIFY | 1-2 neue AC-Tests für Reserve-Verhalten (Rückrichtung: Deviation zuerst, NowCast danach trotzdem noch möglich — heute ungetestet) |

Kein Eingriff in `internal/scheduler/scheduler.go`, kein Schemawechsel an
`alert_daily_count.json` (bleibt flacher Integer-Zähler).

### Scope Assessment

- Files: 6 (4 Code, 1 Spec, 1 Test)
- Estimated LoC: ~100–170 (Code ~20–35, Spec ~15–30, Tests ~60–100)
- Risk Level: MEDIUM — geteilter Modul-Kern mit 5 Aufrufstellen; Fehler in einer Stelle
  wirkt sich auf alle anderen aus. Bestehender Test
  `test_ac5_cross_path_daily_limit_shared_between_radar_and_deviation`
  (`tests/tdd/test_issue_1070_daily_alert_limit.py:463-536`) verankert die Gegenrichtung
  (Radar zuerst blockiert nachfolgenden Deviation-Alarm) und bleibt bei additivem
  `reason`-Parameter unverändert grün.

### Technical Approach

**Empfehlung: Option B — reserviertes Mindest-Kontingent für `nowcast`/`official_alert`
in `alert_daily_limit.is_allowed()`.**

Verworfene Alternativen:
- **Cron-Reihenfolge umkehren** — wirkungslos (getrennte Goroutinen, s.o.) und würde
  ohnehin unnötig Go/Scheduler anfassen.
- **Gewichtete Zählung** (NowCast zählt 0,5) — bricht das getestete Integer-Format,
  garantiert trotzdem keinen Vorrang (nur langsamer verbraucht).
- **Eigener Zähler pro Alarm-Grund + Gesamt-Obergrenze** — Schemawechsel an
  produktiver Datei, größter Test-Umbau, Risiko einer stillen Aufweichung des
  #1070-Gesamtlimits (2+2+2 statt 2). Für diesen Scope nicht gerechtfertigt.

**Offene Produktentscheidung vor Implementierung:** die konkrete Reserve-Größe (z. B. 1
von 2 Slots bei Free für `nowcast`/`official_alert`) halbiert faktisch die
Deviation-Alarm-Quote für Free-Nutzer — das ist eine PO-Entscheidung, keine rein
technische. Gehört in die Spec-Freigabe (`/30-write-spec`, ACs auf Deutsch).

### Dependencies

- Compare-Pfad (`compare_alert.py`, `compare_official_alert.py`) MUSS mitgeändert
  werden — teilt sich denselben Zähler mit Trip; sonst inkonsistentes Verhalten pro
  Nutzer (Trip priorisiert, Compare nicht).
- Keine Abhängigkeit zu `scheduler.go` (s.o.).
- `compare_radar_alert.py` bleibt unangetastet — als Nebenbefund im Spec-Text und
  ggf. #1199 vermerken, nicht in diesem Workflow beheben.

### Open Questions — PO-Entscheidung 2026-08-07 (geklärt)

- **Reserve-Umfang:** ausschließlich `reason="nowcast"` bekommt Vorrang. `official_alert`
  bleibt im normalen (nicht reservierten) Budget wie bisher — PO-Entscheidung, entgegen
  der Agent-Empfehlung "beide", da amtliche Warnungen bereits über einen eigenen,
  unabhängigen Trigger-Pfad laufen (`check_official_alert_triggers()`).
- **Reserve-Größe:** Free `limit=2` → `forecast_change`-Obergrenze `1` (1 Slot bleibt für
  NowCast reserviert). Standard `limit=4` → `forecast_change`-Obergrenze `2` (2 Slots
  reserviert). Premium (`limit=None`) unverändert kein Limit, kein Reserve-Konzept nötig.
  `nowcast` selbst prüft in allen Tiers weiterhin gegen das volle `limit`.
