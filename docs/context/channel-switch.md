# Context: Channel-Switch (#11)

## Request Summary
Pro Report (Trip & Subscription) den Versandweg konfigurierbar machen. Aktuell: Email + Signal implementiert. Gewuenscht: zusaetzlich Telegram. SMS weiterhin Placeholder.

## Status Quo

### Implementierte Channels
| Channel | Output-Klasse | Settings-Felder | UI vorhanden | Flag in Model |
|---------|--------------|-----------------|-------------|---------------|
| Email | `src/outputs/email.py` | smtp_host/port/user/pass | Ja (Settings + Checkboxes) | `send_email` |
| Signal | `src/outputs/signal.py` | signal_phone/api_key/api_url | Ja (Settings + Checkboxes) | `send_signal` |
| SMS | **FEHLT** (`sms.py` nicht vorhanden) | sms_gateway_url/api_key/from/to | Nur Checkbox "coming soon" | `send_sms` (Trip only) |
| Console | `src/outputs/console.py` | - | Nein | - |
| Telegram | **FEHLT** | **FEHLT** | Nein | **FEHLT** |

### Channel-Auswahl bereits implementiert (F12a)
- **Subscriptions:** `send_email` + `send_signal` Flags in `CompareSubscription` Model, UI-Checkboxes, Scheduler respektiert Flags
- **Trips:** `send_email` + `send_sms` + `send_signal` Flags in `TripReportConfig`, UI-Checkboxes vorhanden

### Bekannte Gaps
1. `src/outputs/sms.py` fehlt — `get_channel("sms")` wirft ImportError
2. Trip-Scheduler ignoriert `send_email` Flag (sendet immer wenn SMTP konfiguriert)
3. Alert-Service ignoriert per-Trip Channel-Flags komplett
4. Kein SMS-Settings UI

## Related Files
| File | Relevance |
|------|-----------|
| `src/outputs/base.py` | Channel-Factory `get_channel()`, `OutputChannel` Protocol |
| `src/outputs/email.py` | EmailOutput — Referenz-Implementierung |
| `src/outputs/signal.py` | SignalOutput — Referenz fuer HTTP-basierte Channels |
| `src/outputs/console.py` | ConsoleOutput |
| `src/app/config.py` | Settings mit allen Channel-Credentials |
| `src/app/user.py` | CompareSubscription Model mit send_email/send_signal |
| `src/app/models.py` | TripReportConfig mit send_email/send_sms/send_signal |
| `src/app/loader.py` | Serialisierung/Deserialisierung der Channel-Flags |
| `src/services/trip_report_scheduler.py` | Trip-Report Versand (Email/Signal) |
| `src/web/scheduler.py` | Subscription-Versand (`_execute_subscription`) |
| `src/services/trip_alert.py` | Alert-Versand (ignoriert Flags!) |
| `src/web/pages/settings.py` | Settings-UI (Email/Signal Konfiguration) |
| `src/web/pages/subscriptions.py` | Subscription-Dialog mit Channel-Checkboxes |
| `src/web/pages/report_config.py` | Trip Report Config UI mit Channel-Checkboxes |

## Existing Patterns
- **Output-Channel Protocol:** `name: str` + `send(subject, body)` in `base.py`
- **Factory:** `get_channel(name, settings)` in `base.py`
- **Settings:** `can_send_X()` Methode prueft ob Credentials vorhanden
- **Per-Report Flags:** `send_email`, `send_signal` als bool-Felder im Model
- **UI Pattern:** Checkbox pro Channel im Dialog, Safari-safe Factory Pattern

## Dependencies
- **Upstream:** Settings (Credentials), Channel-Factory, Output-Protocol
- **Downstream:** Trip-Scheduler, Subscription-Scheduler, Alert-Service, UI-Dialoge

## Existing Specs
- `docs/specs/modules/channel_switch_subscriptions.md` — F12a (implementiert)
- `docs/specs/modules/signal_output.md` — SignalOutput (implementiert)
- `docs/specs/modules/smtp_mailer.md` — SMTP (implementiert)

## Telegram-Machbarkeit
- **API:** Telegram Bot API (`https://api.telegram.org/bot<TOKEN>/sendMessage`)
- **Voraussetzungen:** Bot-Token (via @BotFather), Chat-ID des Empfaengers
- **Vorteil gegenueber Signal/Callmebot:** Native API, zuverlaessiger, HTML-Formatierung moeglich
- **Implementierungsaufwand:** Minimal — analog zu SignalOutput (HTTP GET/POST)
- **Settings:** `telegram_bot_token`, `telegram_chat_id`

## Scope-Vorschlag
1. **Telegram Output** — Neuer Channel `src/outputs/telegram.py`
2. **Settings + UI** — Telegram-Credentials in Settings, UI-Karte in Settings-Page
3. **Model-Erweiterung** — `send_telegram` Flag in CompareSubscription + TripReportConfig
4. **Scheduler-Integration** — Telegram-Versand in Trip- und Subscription-Scheduler
5. **Bugfixes** — Trip-Scheduler `send_email` Flag respektieren, Alert-Service Flags respektieren
6. **SMS** — Weiterhin Placeholder (kein Gateway konfiguriert)

## Risks & Considerations
- Telegram Bot muss vom User erstellt werden (@BotFather) — Onboarding-Schritt
- Telegram HTML-Subset ist eingeschraenkt (kein CSS, nur <b>, <i>, <a>, <code>, <pre>)
- Message-Limit: 4096 Zeichen (mehr als SMS, weniger als Email)
- Trip-Scheduler Email-Bug (#send_email Flag ignoriert) sollte mitgefixt werden
