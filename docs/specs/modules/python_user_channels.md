---
entity_id: python_user_channels
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [python, multi-user, channels, settings, f13]
---

# F13 Phase 4b — Python liest Channel-Settings aus User-Profil

## Approval

- [ ] Approved

## Purpose

Python Services sollen Empfaenger-Einstellungen (mail_to, signal_phone, signal_api_key, telegram_chat_id) aus dem User-Profil (`data/users/{user_id}/user.json`) lesen statt aus der globalen `.env`. Die SMTP/Signal/Telegram Sende-Infrastruktur (Host, Credentials) bleibt global — nur die Empfaenger-Adressen werden per-User.

## Scope

### In Scope

- `src/app/config.py` — neue Methode `Settings.with_user_profile(user_id)`
- `api/routers/scheduler.py` — Settings mit User-Profil laden vor dem Senden
- `src/services/trip_report_scheduler.py` — Settings mit User-Profil laden
- `src/services/trip_alert.py` — Settings mit User-Profil laden

### Out of Scope

- SvelteKit UI fuer Profil-Bearbeitung
- Inbound-E-Mail-Routing per User
- Neue Output-Channel-Implementierungen

## Source

- **File:** `src/app/config.py` **(ERWEITERT)**
- **Identifier:** `Settings.with_user_profile(user_id: str)`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `data/users/{user_id}/user.json` | json file | User-Profil mit Channel-Einstellungen |
| `Settings.model_copy` | pydantic | Kopie mit ueberschriebenen Feldern |

## Implementation Details

### Step 1: `Settings.with_user_profile()` (`src/app/config.py`, +20 LoC)

```python
def with_user_profile(self, user_id: str) -> "Settings":
    """Return a copy with recipient settings from user profile.

    Loads data/users/{user_id}/user.json and overrides:
    - mail_to (if set in profile)
    - signal_phone (if set)
    - signal_api_key (if set)
    - telegram_chat_id (if set)

    SMTP/Signal/Telegram infrastructure stays global.
    Falls back to global settings if profile doesn't exist or fields are empty.
    """
    import json
    from pathlib import Path

    profile_path = Path(f"data/users/{user_id}/user.json")
    if not profile_path.exists():
        return self

    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError):
        return self

    overrides = {}
    if profile.get("mail_to"):
        overrides["mail_to"] = profile["mail_to"]
    if profile.get("signal_phone"):
        overrides["signal_phone"] = profile["signal_phone"]
    if profile.get("signal_api_key"):
        overrides["signal_api_key"] = profile["signal_api_key"]
    if profile.get("telegram_chat_id"):
        overrides["telegram_chat_id"] = profile["telegram_chat_id"]

    if not overrides:
        return self

    return self.model_copy(update=overrides)
```

Fallback: Wenn user.json nicht existiert, Felder leer sind, oder JSON ungueltig → globale Settings unveraendert.

### Step 2: Scheduler-Endpoints (`api/routers/scheduler.py`, +5 LoC)

In `_run_subscriptions_by_schedule` und `_run_weekly_subscriptions`:

```python
settings = Settings().with_user_profile(user_id)
```

Statt bisher `settings = Settings()`.

### Step 3: TripReportSchedulerService (`src/services/trip_report_scheduler.py`, +5 LoC)

In `__init__`:

```python
self._settings = settings if settings else Settings().with_user_profile(user_id)
```

### Step 4: TripAlertService (`src/services/trip_alert.py`, +5 LoC)

In `__init__`:

```python
self._settings = settings if settings else Settings().with_user_profile(user_id)
```

## Expected Behavior

- **User mit Profil:** Subscriptions/Reports/Alerts werden an die im Profil hinterlegte Adresse gesendet
- **User ohne Profil:** Fallback auf globale `.env` Settings (identisches Verhalten wie bisher)
- **User mit teilweise gefuelltem Profil:** Nur gesetzte Felder ueberschreiben, Rest bleibt global

## Known Limitations

- Kein Caching der User-Profile — bei jedem Scheduler-Run wird user.json neu gelesen
- Wenn ein User nur `signal_phone` aber nicht `signal_api_key` setzt, funktioniert Signal nicht (kein Fallback auf global fuer einzelne Felder eines Channels)

## Changelog

- 2026-04-16: Initial spec (F13 Phase 4b — Python User-Channels, GitHub Issue #12)
