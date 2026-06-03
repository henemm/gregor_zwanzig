---
entity_id: issue_572_multi_user_inbound_routing
type: module
created: 2026-06-03
updated: 2026-06-03
status: implemented
version: "1.0"
tags: [multi-user, inbound, email, telegram, routing]
---

<!-- Issue #572 — Gregor als echtes Multi-User-Produkt: Inbound-Routing -->

# Issue 572 — Multi-User Inbound-Routing

## Approval

- [x] Approved (implemented 2026-06-03)

## Purpose

Eingehende Nachrichten (E-Mail-Befehle, Telegram-Befehle) werden dem richtigen
Nutzer zugeordnet, anstatt immer beim "default"-User zu landen. Grundlage ist
eine `list_all_user_ids()`-Funktion und zwei Lookup-Funktionen, die alle
User-Profile nach der Absender-Adresse bzw. Telegram-Chat-ID durchsuchen.

## Source

- **File:** `src/app/loader.py` (ERWEITERT um 3 Funktionen, ~40 LoC)
- **File:** `src/services/inbound_email_reader.py` (UMBAU `_authorize` + `poll_and_process`, ~30 LoC)
- **File:** `src/services/inbound_telegram_reader.py` (UMBAU `_process_update`, ~25 LoC)

## Estimated Scope

- **LoC:** ~150 (Produktion + Tests)
- **Files:** 5 (3 Produktion + 2 Test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py` | intern | Basis für `list_all_user_ids()` |
| `src/app/config.py` | intern | `Settings.with_user_profile(user_id)` für User-Settings |
| `data/users/*/user.json` | Datei | Enthält `mail_to`, `telegram_chat_id` pro Nutzer |

## Implementation Details

### 1. `list_all_user_ids()` in `loader.py`

```python
def list_all_user_ids(data_dir: str = "data") -> list[str]:
    """Returns all user IDs found under data/users/, excluding test- and internal users."""
    users_root = Path(data_dir) / "users"
    if not users_root.exists():
        return []
    return [
        d.name for d in users_root.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith("test")
    ]
```

### 2. Lookup-Funktionen in `loader.py`

```python
def lookup_user_by_email(email: str, data_dir: str = "data") -> str | None:
    """Findet user_id mit mail_to == email. Gibt None zurück wenn kein Match."""
    for uid in list_all_user_ids(data_dir):
        profile_path = Path(data_dir) / "users" / uid / "user.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text())
                if profile.get("mail_to", "").lower() == email.lower():
                    return uid
            except Exception:
                continue
    return None

def lookup_user_by_telegram_chat_id(chat_id: str, data_dir: str = "data") -> str | None:
    """Findet user_id mit telegram_chat_id == chat_id. Gibt None zurück wenn kein Match."""
    for uid in list_all_user_ids(data_dir):
        profile_path = Path(data_dir) / "users" / uid / "user.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text())
                if str(profile.get("telegram_chat_id", "")) == str(chat_id):
                    return uid
            except Exception:
                continue
    return None
```

### 3. Inbound Email Reader — Multi-User-Routing

`poll_and_process()` iteriert weiter über die IMAP-Inbox (shared mailbox).
Pro Nachricht: `lookup_user_by_email(from_addr)` → `settings.with_user_profile(user_id)`.
Fallback auf "default" wenn kein User gefunden.

```python
def _resolve_settings_for_sender(self, from_addr: str, base_settings: Settings) -> tuple[str, Settings]:
    """Gibt (user_id, user_scoped_settings) zurück."""
    from app.loader import lookup_user_by_email
    user_id = lookup_user_by_email(from_addr) or "default"
    return user_id, base_settings.with_user_profile(user_id)
```

`_authorize()` prüft dann gegen die user-spezifischen Settings (nicht mehr globale).

### 4. Inbound Telegram Reader — Multi-User-Routing

`_process_update()` extrahiert `chat_id` aus dem Update und mappt auf user_id.
Fallback auf "default" wenn kein User gefunden.

```python
def _resolve_user_for_chat(self, chat_id: str, base_settings: Settings) -> tuple[str, Settings]:
    """Gibt (user_id, user_scoped_settings) zurück."""
    from app.loader import lookup_user_by_telegram_chat_id
    user_id = lookup_user_by_telegram_chat_id(chat_id) or "default"
    return user_id, base_settings.with_user_profile(user_id)
```

`load_all_trips()` wird dann mit dem aufgelösten `user_id` aufgerufen.

## Expected Behavior

- **Input Email:** Eingehende E-Mail von Absender X
- **Output Email:** System findet User mit `mail_to == X`, lädt dessen Trips, antwortet an dessen Adresse
- **Input Telegram:** Eingehende Nachricht von Chat-ID Y
- **Output Telegram:** System findet User mit `telegram_chat_id == Y`, lädt dessen Trips
- **Fallback:** Kein User-Match → "default" (bestehende Logik unverändert)
- **Kein Absturz:** Kein Match + kein "default"-User → Nachricht wird still übersprungen (Log-Warning)

## Acceptance Criteria

**AC-1:** Given zwei User-Profile (`henning` mit `mail_to=henning@example.com` und `default` mit `mail_to=other@example.com`) / When der Inbound-Email-Reader eine E-Mail von `henning@example.com` verarbeitet / Then wird `lookup_user_by_email` aufgerufen und gibt `"henning"` zurück, die Trips des Users `henning` werden geladen.

**AC-2:** Given ein User-Profil mit `telegram_chat_id=12345` / When der Inbound-Telegram-Reader ein Update von Chat-ID `12345` verarbeitet / Then gibt `lookup_user_by_telegram_chat_id("12345")` die korrekte user_id zurück und `load_all_trips(user_id)` wird mit dieser ID aufgerufen.

**AC-3:** Given kein User-Profil mit passender E-Mail-Adresse / When der Inbound-Email-Reader eine unbekannte Absender-Adresse verarbeitet / Then wird `user_id = "default"` verwendet und kein Fehler geworfen.

**AC-4:** Given kein User-Profil mit passender Telegram-Chat-ID / When der Inbound-Telegram-Reader ein Update von unbekannter Chat-ID verarbeitet / Then wird `user_id = "default"` verwendet und kein Fehler geworfen.

**AC-5:** Given `list_all_user_ids()` wird aufgerufen / When `data/users/` Verzeichnisse enthält die mit `test_` oder `_` beginnen / Then werden diese aus der Rückgabe ausgeschlossen.

**AC-6:** Given ein User-Profil mit `mail_to` / When `lookup_user_by_email` mit der gleichen Adresse in anderer Groß-/Kleinschreibung aufgerufen wird / Then wird der Vergleich case-insensitiv durchgeführt und der User gefunden.
