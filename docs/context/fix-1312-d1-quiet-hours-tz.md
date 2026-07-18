# Context: fix-1312-d1-quiet-hours-tz

## Request Summary

Scheibe D1 aus Epic #1301 (Issue #1312, #1292 P7): Die „Stillen Stunden" der Alarme vergleichen die Nutzereingabe (Lokalzeit-Empfinden, z.B. „22:00–06:00") gegen **UTC** — im Sommer (UTC+2) gehen zwischen 22 und 24 Uhr Ortszeit Alarme raus, morgens 6–8 Uhr wird fälschlich unterdrückt. Fix: **einmal zentral** in `is_quiet_hours` nach Lokalzeit (Europe/Vienna) konvertieren.

## Related Files (verifiziert, Stand be408b7f)

| File | Relevance |
|------|-----------|
| `src/services/deviation_alert_engine.py:72-83` | `is_quiet_hours(now, quiet_from, quiet_to)` — vergleicht `now.time()` direkt; Docstring „1:1 aus TripAlertService._is_quiet_hours() — Mitternachts-Wrap inklusive" |
| `src/services/deviation_alert_engine.py:226` | Aufrufer 1 (Δ-Wächter), übergibt UTC |
| `src/services/compare_official_alert.py:107` | Aufrufer 2 (UTC) |
| `src/services/compare_radar_alert.py:103` | Aufrufer 3 (UTC) |
| `src/services/trip_alert.py:161, :653, :986` | Aufrufer 4-6 via Wrapper `_is_quiet_hours` (`:394-410`), alle `datetime.now(timezone.utc)` bzw. `now_utc` |
| `src/services/alert_daily_limit.py:9-33` | **Vorbild:** `VIENNA = ZoneInfo("Europe/Vienna")`, `now.astimezone(VIENNA)`; `now` als Parameter, kein `datetime.now()` im Modul |

## Bestehende Tests (Audit-Pflicht!)

- `tests/tdd/test_alert_cooldown_quiet.py` — übergibt aware-UTC-Zeiten und kodiert teils die HEUTIGE (falsche) Semantik. Fallweise auditieren: z.B. `:106` (23:30 UTC, Fenster 22:00–07:00 → True) bleibt nach Fix wahr (01:30 Wien, innen); Fälle nahe der Fenstergrenzen können kippen und müssen dann auf die NEUE (korrekte) Erwartung umgestellt werden — mit Docstring-Begründung, nicht stillschweigend.
- Weitere Treffer: `test_issue_1168_alert_engine_extract.py`, `test_compare_official_alert.py`, `test_compare_radar_alert.py`, `test_issue_883_acute_danger_override.py`, `test_throttle_store.py` — auf quiet-hours-Bezug prüfen, gleiche Audit-Regel.

## Design-Entscheidung

Konvertierung **in `is_quiet_hours` selbst** (nicht an den 6 Aufrufstellen): `now.astimezone(VIENNA).time()` für aware datetimes. **Naive datetimes:** Bestand vor #1168 nutzte naive? Aufrufer übergeben heute durchweg aware-UTC; für naive Eingaben definieren: als UTC interpretieren (`now.replace(tzinfo=timezone.utc)`) — konservativ, deterministisch testbar. DST ist durch `ZoneInfo` automatisch korrekt (Sommer +2, Winter +1).

**Nicht im Scope:** Nutzer-konfigurierbare Zeitzone (es gibt kein solches Feld; Europe/Vienna ist die etablierte Projekt-Konvention, vgl. `alert_daily_limit.py` und `scheduler_dispatch_service.py:146`). Keine Queue (Nachliefern existiert: `compare_official_alert.py` verbraucht State bewusst nicht, `compare_radar_alert.py` vor `_finalize`, `deviation_alert_engine.py` vor jedem `save()` — an diesem Verhalten ändert D1 NICHTS).

## Risks & Considerations

- **Alarm-Pfad Trip UND Vergleich** — Verhaltensänderung genau an den Fenstergrenzen (gewollt: das IST der Fix). Regressionsschutz: Mitternachts-Wrap-Logik (`:81-83`) bleibt unverändert, nur der Zeitbezug ändert sich.
- Kern-Tests deterministisch mit festen aware-Zeitstempeln (Sommer- UND Winterfall testen!). Kein `datetime.now()` in Tests.
- Bug-Nachweis rot-vor-grün: 20:30 UTC am Sommertag (= 22:30 Wien) mit Fenster „22:00–06:00" MUSS unterdrückt werden (heute: nicht). Gegenprobe: 05:00 UTC (= 07:00 Wien) darf NICHT mehr unterdrückt werden (heute: wird).
- Parallel-Sessions: C2 (Frontend-Hub) — keine gemeinsamen Dateien. Keine Mail-Renderer-Dateien → kein Renderer-Gate #811.

## Existing Specs

- `docs/specs/modules/issue_181_alert_cooldown_quiet_hours.md` — Ursprungs-Spec der stillen Stunden (Semantik „Mitternachts-Wrap"); D1 präzisiert den Zeitbezug, widerspricht ihr nicht.
- Epic-Plan `~/.claude/plans/warum-verweist-du-immer-crispy-ladybug.md`, Abschnitt D1.
