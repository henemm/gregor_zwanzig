# Context: Issue #181 — Alert-Konfigurator: Cooldown + Stille Stunden

## Request Summary

Issue #181 (Teil von Epic #139): Nutzer sollen im Alerts-Tab pro Trip konfigurieren können,
wie oft (Cooldown-Minuten) und zu welchen Zeiten (Stille Stunden von/bis) Alert-E-Mails
gesendet werden. Vorher galt ein globaler `throttle_hours=2`-Default für alle Trips.

## Implementierungsstatus: VOLLSTÄNDIG COMMITTED

**Alle Änderungen sind bereits committed (dc57d4f) + Adversary-Fix (bb42083).**

### Implementierte Dateien

| Datei | Änderung |
|-------|----------|
| `internal/model/trip.go` | 3 neue Pointer-Felder: `AlertCooldownMinutes`, `AlertQuietFrom`, `AlertQuietTo` |
| `internal/handler/trip.go` | `tripUpdateRequest` + Read-Modify-Write für 3 neue Felder |
| `src/app/trip.py` | 3 neue `Optional`-Felder in Trip-Dataclass |
| `src/app/loader.py` | `_parse_trip()` + `_trip_to_dict()` lesen/schreiben neue Felder |
| `src/services/trip_alert.py` | `_is_quiet_hours()` (Mitternacht-Wrap), `_is_throttled_with_cooldown()` (0=kein Limit) |
| `frontend/src/lib/types.ts` | 3 optionale Felder im Trip-Interface |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | NEU — Number-Input für Cooldown |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | NEU — Time-Inputs + Toggle + Mitternacht-Hint |
| `tests/tdd/test_alert_cooldown_quiet.py` | 11 Tests — alle GRÜN |

### Tests

```
tests/tdd/test_alert_cooldown_quiet.py   11 passed
```

### Adversary-Fund (behoben, bb42083)

- **F001:** `quietFrom`/`quietTo` im AlertsTab als `''` statt `undefined` initialisiert
  → AlertQuietHoursCard.`enabled` war `false` auch wenn keine Stille Stunden gesetzt
  → Fix: `?? undefined` statt `?? ''`

## Spec

`docs/specs/modules/issue_181_alert_cooldown_quiet_hours.md`  
Status: `draft`, Approval: unchecked (Spec wurde parallel zur Implementierung erstellt)

## Acceptance Criteria (alle durch Tests / Implementierung abgedeckt)

| AC | Beschreibung | Status |
|----|-------------|--------|
| AC-1 | Trip ohne cooldown → globaler Default (120 Min) | ✅ Test vorhanden |
| AC-2 | Trip mit cooldown=60, 30 Min nach letztem Alert → unterdrückt | ✅ Test vorhanden |
| AC-3 | Trip mit cooldown=0 → kein Limit, Cooldown-Check übersprungen | ✅ Test vorhanden |
| AC-4 | QuietHours 22:00–07:00, 23:30 Uhr → unterdrückt (Mitternacht-Wrap) | ✅ Test vorhanden |
| AC-5 | QuietHours 22:00–07:00, 07:01 Uhr → NICHT unterdrückt | ✅ Test vorhanden |
| AC-6 | QuietHours 08:00–22:00, 15:00 Uhr → unterdrückt (normales Fenster) | ✅ Test vorhanden |
| AC-7 | Go-Handler: PUT mit cooldown_minutes=45 → Read-Modify-Write korrekt | ✅ Implementiert |
| AC-8 | Bestandstrip ohne cooldown-Feld → None, kein Crash | ✅ Implementiert |
| AC-9 | Frontend AlertCooldownCard speichert alert_cooldown_minutes | ✅ Implementiert |
| AC-10 | Frontend AlertQuietHoursCard speichert quiet_from + quiet_to | ✅ Implementiert |

## Offene Schritte

1. Staging-Deployment + Validierung
2. Prod-Deployment
3. Issue #181 schließen

## Risiken & Überlegungen

- **Backward-Compatibility:** Pointer-Felder + `omitempty` sichern alte Trips ohne diese Felder
- **Mitternacht-Wrap:** `_is_quiet_hours()` behandelt `from > to` korrekt (z.B. 22:00–07:00)
- **0-Cooldown-Semantik:** 0 = "kein Limit", nicht "0 Minuten Cooldown" (explizit dokumentiert)
