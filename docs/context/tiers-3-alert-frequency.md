# Context: Tiers-3 — Alert-/Update-Frequenz nach Nutzerlevel (#1070)

## Request Summary

Harte Tages-Obergrenze für Alerts pro Nutzerlevel: Free = 2/Tag, Standard = 4/Tag,
Premium = kein Tageslimit, aber Mindestabstand 15 Min. Persistierter Tageszähler pro Nutzer
mit Mitternachts-Reset (Europe/Vienna). Bestehender Per-Trip-Cooldown gilt zusätzlich weiter —
das strengere Limit gewinnt. Cron `alertChecks` von 30 auf 15 Min anheben (Premium-Takt).
Teil von Epic #1067, Slice 3. Spec: `docs/specs/modules/epic_user_tiers_overview.md`.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py` | **Kernstück** — enthält BEIDE Alert-Sende-Pfade (nicht `radar_alert_service.py`!). Klasse `TripAlertService`, Cooldown-Logik, Throttle-Persistenz. |
| `src/services/user_tier.py` | Slice-2-Modul mit `sms_allowed(user_id)`. Liest `tier` aus `user.json`. Hier reiht sich ein Tier→Tageslimit-Lookup ein. |
| `internal/scheduler/scheduler.go` | Cron-Definitionen (Zeile 91-99). `alertChecks` = `0,30 * * * *` → auf `*/15 * * * *`. |
| `internal/model/user.go` | `Tier`-Feld existiert bereits (Slice 1, Zeile 22). |
| `api/routers/scheduler.py` | Endpoints `/alert-checks` (→ `check_all_trips`) und `/radar-alert-checks` (→ `check_radar_alerts`); beide bauen `TripAlertService(user_id=user_id)`. |
| `internal/config/config.go` | `SchedulerTimezone` default `Europe/Vienna` (Zeile 20) — Reset-Grenze. |
| `data/users/<user_id>/` | Ort für neuen Tageszähler-State (Muster: `alert_throttle.json`, `alert_state/`). |

## ⚠️ Wichtige Korrektur zur Spec-„Befund"-Sektion

Die Epic-Spec (`epic_user_tiers_overview.md`, Zeilen 63-81, 121-135) verweist auf
`src/services/radar_alert_service.py` mit `AlertService.__init__(throttle_hours=2)` Zeile 55,
`_is_throttled_with_cooldown` Zeile 411-432, `THROTTLE_FILE` Zeile 76, `check_all_trips` Zeile 298.
**Diese Zeilennummern und die Datei stimmen nicht mehr.** `radar_alert_service.py` hat heute nur
101 Zeilen (reiner Renderer/Mail-Helper, keine Throttle-Logik). Die tatsächliche Logik lebt in
`src/services/trip_alert.py`:
- Klasse `TripAlertService.__init__(throttle_hours=2, user_id=...)` — Zeile 53-82
- `_is_throttled_with_cooldown` — Zeile 412-433
- `THROTTLE_FILE = data/users/{user_id}/alert_throttle.json` — Zeile 77
- `check_all_trips()` — Zeile 295 (Kommentar „every 30 minutes" Zeile 299)

## Existing Patterns

- **Zwei getrennte Alert-Sende-Pfade, beide in `trip_alert.py`, beide mit demselben
  `self._user_id`:**
  1. **Deviation-Watcher** (Wetteränderungs-Alerts): `check_and_send_alerts` (Zeile 84) via
     `check_all_trips` (Zeile 295). Throttle-Gate `_is_throttled_with_cooldown` (Zeile 145).
     „Alert gesendet"-Recording bei Erfolg: `self._last_alert_times[trip.id] = now` +
     `_save_throttle_times()` (Zeile 207-208).
  2. **Radar/Onset-Alerts**: `check_radar_alerts` (Methode um Zeile 670-851) via
     `check_radar_alerts` Endpoint. Throttle-Gate `_is_radar_throttled` (Zeile 711).
     Recording bei Erfolg: `_append_alert_log` + `radar_throttle`-State + Legacy-Datei
     `radar_alert_throttle.json` (Zeile 832-849).
  → **Der Tageszähler muss an BEIDEN Erfolgs-Recording-Stellen zählen und an BEIDEN Gates
    prüfen.** (Sonst umgeht ein Pfad das Limit.)
- **State-per-User-Datei-Muster:** `THROTTLE_FILE = Path(f"data/users/{user_id}/alert_throttle.json")`,
  `AlertStateService` (`data/users/{user_id}/alert_state`). Read-Modify-Write mit JSON. Der neue
  Tageszähler folgt exakt diesem Muster: `data/users/<user_id>/alert_daily_count.json` mit
  `{"date": "YYYY-MM-DD", "count": N}`.
- **Tier-Lookup:** `user_tier.sms_allowed()` liest `profile.get("tier", "free")` aus
  `data/users/<user_id>/user.json`. Default „free" wenn Feld fehlt. Ein neuer
  `daily_alert_limit(user_id)` gehört daneben.
- **Cooldown-Semantik:** Per-Trip `trip.alert_cooldown_minutes` (0 = kein Limit, None = globaler
  Default `throttle_hours*60`). Der Tageszähler ist ADDITIV, ersetzt diesen nicht — das strengere
  gewinnt.

## Dependencies

- **Upstream (was der neue Code nutzt):** `data/users/<id>/user.json` (Tier), Europe/Vienna-Zeitzone
  (aktuelles Kalenderdatum für Reset), bestehende JSON-Read-Modify-Write-Muster.
- **Downstream (was den geänderten Code nutzt):** Go-Scheduler → `/api/scheduler/alert-checks` +
  `/radar-alert-checks` → `TripAlertService`. Cron-Frequenz-Änderung betrifft ALLE Nutzer
  (Zustellzeitpunkte verschieben sich; `alertChecks` läuft dann viertelstündlich statt halbstündlich).

## Existing Specs

- `docs/specs/modules/epic_user_tiers_overview.md` — Epic-Overview (Slice 3 = dieses Issue).
  ⚠️ „Befund"-Zeilennummern veraltet (s.o.).
- `docs/specs/modules/trip_alert.md` — Spec des `TripAlertService` (v2.0).

## Risks & Considerations

- **R1 — Begriffs-Ambiguität „Alerts/Updates":** Zählt das Tageslimit nur Alerts (Deviation +
  Radar), oder auch die planmäßigen Trip-Briefings (morning/evening reports)? Die Slice-3-
  Verdrahtung berührt nur die Alert-Pfade, was für „nur Alerts" spricht — aber das Wort „Updates"
  und der Issue-Text sind nicht eindeutig. **In Phase 2/3 mit PO klären.**
- **R2 — Zwei Pfade, ein Zähler:** Deviation- und Radar-Alerts müssen gegen DENSELBEN Tageszähler
  zählen und prüfen, sonst kann ein Free-Nutzer über den einen Pfad das Limit des anderen umgehen.
- **R3 — Reset-Grenze/Zeitzone:** Reset bei Kalendertag-Wechsel in Europe/Vienna (nicht UTC, nicht
  Berlin). Zähler-Datei speichert das Datum; bei Load prüfen, ob `date` == heute (Europe/Vienna),
  sonst Zähler = 0.
- **R4 — Race/Konsistenz bei Read-Modify-Write:** Increment nur nach erfolgreichem Versand
  (F001-Symmetrie: kein Zustell-Kanal → kein Zählen). Kein Datenverlust bei parallelen Läufen —
  aber Scheduler ruft pro Nutzer sequentiell, geringe Kollisionsgefahr.
- **R5 — Cron-„5 jobs"-Log:** `scheduler.go:111` loggt hart „5 jobs" — kosmetisch, nicht betroffen,
  aber Frequenzänderung testen (Go-Test/Scheduler-Status).
- **R6 — Premium-Semantik:** Premium hat KEIN Tageslimit, nur Mindestabstand 15 Min. Der bestehende
  Cooldown-Mechanismus + Cron-15-Min deckt das ab; der Tageszähler-Check muss für Premium
  no-op sein (Limit = ∞).
- **R7 — Bewusst NICHT in Scope (laut Spec):** rückwirkende Migration eines evtl. eigenen
  Throttle-Pfads — falls beim Implementieren gefunden, eigenes Folge-Issue statt Slice-Sprengung.

---

## Analysis

### Type
Feature (Epic #1067, Slice 3).

### PO-Entscheidung (2026-07-07)
**R1 aufgelöst:** Das Tageslimit zählt **nur Alerts** (Deviation-Watcher + Radar/Onset), NICHT die
planmäßigen Morgen-/Abend-Briefings. Ein Free-Nutzer bekommt seine abonnierten Briefings weiterhin
unbegrenzt; begrenzt wird nur die Zahl proaktiver Alerts pro Kalendertag.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_daily_limit.py` | CREATE | Reines Modul: `load(user_id, now)`, `is_allowed(user_id, now)`, `increment(user_id, now)`. Reset = Load-Semantik (date != heute/Vienna → 0). ~60-75 LoC |
| `src/services/user_tier.py` | MODIFY | `daily_alert_limit(user_id) -> int \| None`: free→2, standard→4, premium→None (kein Limit). ~12 LoC |
| `src/services/trip_alert.py` | MODIFY | 2 Gate-Checks (nach Cooldown-Gate, vor Fetch) + 2 Increments (am bestehenden Post-`delivered`-Recording beider Pfade). ~20-30 LoC |
| `internal/scheduler/scheduler.go` | MODIFY | Zeile 93 `"0,30 * * * *"` → `"*/15 * * * *"` (+ Kommentartext). ~2 LoC |
| `tests/tdd/test_issue_1070_*.py` | CREATE | Test A (Modul: Suppression + Vienna-Reset, `now`-injiziert) + Test B (Wiring pro Pfad, echter Dateizustand). ~120-150 LoC |

### Scope Assessment
- Produktionscode: ~4 Dateien, **~95-120 LoC** — deutlich unter 250er-Limit.
- Mit Tests grenzwertig (~250) — Tests zählen aber i.d.R. nicht (generierte/Test-Dateien), Doku/`.go`-Kommentar unkritisch.
- Risk Level: **MEDIUM-HIGH** — kritischer Pfad (echter Alert-Versand), aber kleine, gut isolierte Änderung mit etablierten Mustern.

### Technical Approach (bestätigt durch Strategie-Agent)
1. **Neues Modul** `alert_daily_limit.py` mit **`now` als Parameter** (kein Zeit-Mock nötig → testbar ohne Mocks). Reset ist reine Load-Semantik: bei `date != heute(Europe/Vienna)` liefert `load` 0, kein Write.
2. **Tier→Limit** neben `sms_allowed` in `user_tier.py` (Tier-Wissen bleibt an einer Stelle). Premium → `None` = `is_allowed` immer True (no-op).
3. **Gate und Increment strikt trennen** (F001): Gate NUR prüfen (nach dem bestehenden Cooldown-Gate, vor teurem Fetch/Nowcast); Increment NUR am bestehenden Erfolgs-Recording, strikt hinter dem `delivered`/`if not delivered: continue`-Guard. So zählt ausschließlich tatsächlicher Versand.
4. **Beide Pfade** (`check_and_send_alerts` ~Z.147/206-208 UND `check_radar_alerts` ~Z.713/832-849) teilen `self._user_id` → derselbe Zähler, kein Umgehungspfad.
5. **Vienna-Konversion im Modul**: UTC-`now` nach `ZoneInfo("Europe/Vienna")` konvertieren, DANN `.date()` — sonst springt der Reset um 22:00/23:00 statt Mitternacht.

### Test-Strategie (ohne Mocks, PFLICHT)
- **Test A (Modul):** echte `user.json` mit `tier:"free"`, tmp-`data/`-Root via `chdir`. Zwei injizierte `now` (Tag 1: 2× erlaubt+increment → 3. Prüfung False; Tag 2 knapp nach Mitternacht Vienna → wieder True). Extra: 07.07 23:30 UTC = 08.07 01:30 Vienna → beweist Vienna- statt UTC-Grenze.
- **Test B (Wiring pro Pfad):** Zähler-Datei mit heutigem Vienna-Datum + `count=2` vorseeden, Free-Tier, dann je einen echten Deviation- bzw. Radar-Lauf über bestehende DI-Seams (`mail_sink`, `radar_service`). Assert: kein neuer `alert_log`-Eintrag, Count bleibt 2, `mail_sink` leer. Schließt die Umgehungslücke (R2) beweisbar für BEIDE Pfade.

### Open Questions / Watch-Items
- [x] R1 (Alerts vs. Briefings) — **aufgelöst: nur Alerts** (PO 2026-07-07).
- [ ] **Bestands-Test-Kompatibilität:** `free`-Default bei fehlendem `user.json` (Limit 2) könnte Alt-Tests brechen, die >2 Alerts/Tag für einen default-User ohne `user.json` erwarten. In TDD-Phase gegen bestehende Deviation-/Radar-Test-Fixtures gegenprüfen (Tier setzen oder Limit umgehen, wo Fixtures kein Tier haben).
