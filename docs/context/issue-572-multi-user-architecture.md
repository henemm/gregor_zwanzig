# Context: Issue #572 — Gregor als echtes Multi-User-Produkt

## Request Summary
Gregor hat User-Namespaces (`data/users/{id}/`) und ein Account-System, aber die Inbound-Reader (E-Mail, Telegram) verarbeiten eingehende Nachrichten ohne User-Routing — alle Nachrichten gehen an "default". Sobald ein zweiter Nutzer aktiv ist, werden Inbound-Befehle dem falschen User zugeordnet.

## Was bereits Multi-User-fähig ist ✅

| Bereich | Datei | Status |
|---------|-------|--------|
| Datenpfade | `src/app/loader.py` | Alle Funktionen haben `user_id="default"` Parameter |
| Trip/Locations/Snapshots laden | `loader.py:686-825` | User-namespaced |
| Settings per User | `src/app/config.py:165` | `with_user_profile(user_id)` lädt user.json |
| Go Scheduler User-Loop | `internal/scheduler/scheduler.go:120` | `runForAllUsers()` via `store.ListUserIDs()` |
| Python Endpoints trip-reports | `api/routers/scheduler.py:21` | `user_id` Parameter, Go ruft pro User auf |
| Python Endpoints alert-checks | `api/routers/scheduler.py:36` | `user_id` Parameter |
| Python Endpoints compare-presets | `api/routers/scheduler.py:77` | `user_id` Parameter |
| Profil-Felder im JSON | `data/users/{id}/user.json` | `mail_to`, `telegram_chat_id`, `signal_phone` |

## Die Lücken 🔴

### 1. Kein `list_all_user_ids()` in Python
- Go hat `store.ListUserIDs()` (`internal/store/user.go:16`)
- Python hat KEINE entsprechende Funktion in `loader.py`
- Blockiert jeden Python-seitigen User-Loop

### 2. Inbound Email Reader — kein User-Routing
- `api/routers/scheduler.py:52`: `trigger_inbound()` — nutzt `Settings()` ohne user_id
- `src/services/inbound_email_reader.py:181`: `_authorize()` prüft nur `settings.mail_to` (einzelner User)
- `inbound_email_reader.py:210`: `load_all_trips()` ohne user_id
- **Folge:** Zwei Nutzer mit gleichem Absender-Muster → einer bekommt die Antwort des anderen

### 3. Inbound Telegram Reader — kein User-Routing
- `api/routers/scheduler.py:68`: `trigger_inbound_telegram()` — nutzt `Settings()` ohne user_id
- `src/services/inbound_telegram_reader.py:144`: `load_all_trips()` ohne user_id
- `telegram_reader.py`: chat_id der eingehenden Nachricht wird nicht gegen User-Profile gemappt
- **Folge:** Telegram-Befehle landen beim falschen User (erste gefundene aktive Tour)

## Related Files

| Datei | Relevanz |
|-------|---------|
| `src/app/loader.py:676-825` | Alle User-namespaced Load-Funktionen — hier kommt `list_all_user_ids()` rein |
| `src/app/config.py:165` | `Settings.with_user_profile(user_id)` — User-Profile laden |
| `src/services/inbound_email_reader.py:180` | `_authorize()` — muss auf Multi-User umgebaut werden |
| `src/services/inbound_telegram_reader.py:89` | `_process_update()` — muss chat_id → user_id mappen |
| `api/routers/scheduler.py:52-70` | `trigger_inbound()` + `trigger_inbound_telegram()` — global, kein user_id |
| `internal/scheduler/scheduler.go:155-167` | Inbound-Jobs sind `triggerGlobalEndpoint()` — BY DESIGN (shared mailbox) |
| `data/users/` | Enthält user.json pro User mit mail_to / telegram_chat_id |

## Existing Patterns

- **Go Scheduler → Python User-Loop:** `runForAllUsers()` ruft `/api/scheduler/trip-reports?user_id=X` für jeden User auf
- **Settings.with_user_profile():** Überschreibt mail_to, telegram_chat_id, signal_phone aus user.json
- **Inbound IMAP ist shared mailbox** (eine gemeinsame Inbox): Global-Trigger ist BY DESIGN — kein User-Loop hier, sondern User-Lookup per Absender-Email
- **Inbound Telegram ist shared bot** (ein gemeinsamer Bot): Gleiche Logik — User-Lookup per chat_id

## Architektur-Ziel für diesen Workflow

```
list_all_user_ids() → für jeden User user.json laden
    ↓
build lookup-tables:
    mail_to       → user_id
    telegram_chatid → user_id

InboundEmailReader._authorize(sender):
    user_id = lookup_user_by_email(sender)
    settings = Settings().with_user_profile(user_id)
    → Trips dieses Users laden + Antwort an seine Adresse

InboundTelegramReader._process_update(chat_id):
    user_id = lookup_user_by_telegram_chat_id(chat_id)
    settings = Settings().with_user_profile(user_id)
    → Trips dieses Users laden + Antwort an seinen Chat
```

## Scope dieses Workflows (empfohlen)

- **In Scope:** `list_all_user_ids()` + Inbound Email/Telegram User-Routing
- **Out of Scope (eigene Workflows):** Settings-UI für Kanal-Credentials, Telegram-Onboarding-Flow (`/start`), SMS-Inbound

## Risks & Considerations

- Kein User gefunden → Fallback auf "default" (backward-compatible) — nicht abstürzen
- Mehrere User mit gleicher mail_to → erster Treffer (unwahrscheinlich, aber dokumentieren)
- Tests brauchen mindestens 2 User-Fixtures (user.json mit unterschiedlichen mail_to/chat_ids)
- Die globalen Scheduler-Trigger-Endpoints bleiben global (BY DESIGN für shared mailbox/bot)
