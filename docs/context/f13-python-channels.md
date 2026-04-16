# F13 Phase 4b: Python liest Channel-Settings aus User-Profil

## Analyse (2026-04-16)

### Ansatz
`Settings.with_user_profile(user_id)` — lädt user.json, überschreibt Empfänger-Felder.
SMTP-Infrastruktur (host, port, user, pass) bleibt global. Nur Empfänger werden per-User.

### Betroffene Dateien (3)

| Datei | Änderung | LoC |
|-------|----------|-----|
| `src/app/config.py` | `with_user_profile()` Methode | +20 |
| `api/routers/scheduler.py` | Settings mit User-Profil laden | +5 |
| `src/services/trip_report_scheduler.py` | Settings mit User-Profil laden | +5 |
| `src/services/trip_alert.py` | Settings mit User-Profil laden | +5 |

**Gesamt: 4 Dateien, ~35 LoC**
