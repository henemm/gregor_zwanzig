---
entity_id: channel_switch_subscriptions
type: module
created: 2026-04-04
updated: 2026-04-04
status: draft
version: "1.0"
tags: [subscriptions, channels, email, signal, scheduler]
---

# Channel-Switch für Subscriptions (F12a)

## Approval

- [ ] Approved

## Purpose

Adds per-subscription channel selection (Email/Signal) to `CompareSubscription`, so users can choose how location comparison reports are delivered. Currently location subscriptions are email-only with a hardcoded Signal fallback. This aligns subscriptions with the Trip report pattern where channels are explicitly selectable.

## Source

- **Files:**
  - `src/app/user.py` — `send_email`, `send_signal` fields on `CompareSubscription`
  - `src/app/loader.py` — Serialize/deserialize new fields
  - `src/web/pages/subscriptions.py` — Channel checkboxes in dialog, toggle handler preservation
  - `src/web/scheduler.py` — Respect channel flags in `_execute_subscription()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareSubscription` | Model | `src/app/user.py` (line 107-125); gains 2 new fields |
| `load_compare_subscriptions()` | Function | `src/app/loader.py` (line 669); deserialize with backward compat |
| `save_compare_subscriptions()` | Function | `src/app/loader.py` (line 715); serialize new fields |
| `show_subscription_dialog()` | Function | `src/web/pages/subscriptions.py` (line 247); add channel checkboxes |
| `_execute_subscription()` | Function | `src/web/scheduler.py` (line 205); gate channels on flags |
| `EmailOutput` | Class | `src/outputs/email.py`; existing email sender |
| `SignalOutput` | Class | `src/outputs/signal.py`; existing Signal sender |
| `Settings.can_send_email()` | Function | `src/app/config.py`; checks SMTP credentials |
| `Settings.can_send_signal()` | Function | `src/app/config.py`; checks Signal credentials |

## Implementation Details

### 1. CompareSubscription Model (`src/app/user.py`)

Add two fields after `top_n`:

```python
send_email: bool = True
send_signal: bool = False
```

CompareSubscription is a regular (non-frozen) dataclass, so adding defaulted fields is safe.

### 2. Loader: Serialize/Deserialize (`src/app/loader.py`)

**Deserialization** — in `load_compare_subscriptions()` (line ~699), add to the `CompareSubscription()` constructor:

```python
send_email=sub_data.get("send_email", True),
send_signal=sub_data.get("send_signal", False),
```

**Serialization** — in `save_compare_subscriptions()` (line ~733), add to the dict:

```python
"send_email": sub.send_email,
"send_signal": sub.send_signal,
```

**Backward compat:** Existing JSON without these keys defaults to email=True, signal=False.

### 3. Subscriptions UI (`src/web/pages/subscriptions.py`)

**a) Channel checkboxes in `show_subscription_dialog()`** — add after the `enabled` checkbox:

```python
ui.label("Kanäle").classes("text-subtitle2 q-mt-sm")
with ui.row().classes("gap-4"):
    send_email_cb = ui.checkbox(
        "E-Mail",
        value=True if is_new else sub.send_email,
    )
    send_signal_cb = ui.checkbox(
        "Signal",
        value=False if is_new else sub.send_signal,
    )
```

`is_new` is `sub is None` (create mode).

**b) Save handler** — pass new flags to `CompareSubscription()` constructor:

```python
send_email=send_email_cb.value,
send_signal=send_signal_cb.value,
```

**c) Toggle handler** — in `make_toggle_handler()`, preserve channel flags when reconstructing:

```python
send_email=subscription.send_email,
send_signal=subscription.send_signal,
```

**d) "Run Now" button** — update the inline send logic to respect flags:

```python
if subscription.send_email and settings.can_send_email():
    email_output.send(subject, html_body, plain_text_body=text_body)
if subscription.send_signal and settings.can_send_signal():
    SignalOutput(settings).send(subject, text_body)
```

### 4. Scheduler (`src/web/scheduler.py`)

Replace the current unconditional email + hardcoded Signal logic in `_execute_subscription()` with flag-gated dispatch:

```python
# Generate content (always, regardless of channels)
subject, html_body, text_body = run_comparison_for_subscription(sub, all_locations)

# Dispatch to selected channels
if sub.send_email:
    if settings.can_send_email():
        EmailOutput(settings).send(subject, html_body, plain_text_body=text_body)
    else:
        logger.error(f"Email requested but SMTP not configured: {sub.name}")

if sub.send_signal:
    if settings.can_send_signal():
        try:
            SignalOutput(settings).send(subject, text_body)
        except Exception as e:
            logger.error(f"Signal failed for {sub.name}: {e}")
    else:
        logger.warning(f"Signal requested but not configured: {sub.name}")
```

Key change: Remove the early `return` when SMTP is not configured — content generation must happen before channel dispatch so Signal-only subscriptions work.

## Expected Behavior

### New subscription with default channels

- **Input:** User creates subscription without changing channel checkboxes
- **Output:** Subscription saved with `send_email: true, send_signal: false`
- **Side effects:** Behavior identical to current (email-only)

### Subscription with both channels enabled

- **Input:** User enables both Email and Signal checkboxes
- **Output:** Subscription saved with both flags true
- **Side effects:** Scheduler sends email AND Signal message on trigger

### Signal-only subscription

- **Input:** User unchecks Email, checks Signal
- **Output:** Subscription saved with `send_email: false, send_signal: true`
- **Side effects:** Only Signal message sent; no email

### Legacy subscription JSON (no channel fields)

- **Input:** Existing `compare_subscriptions.json` without `send_email`/`send_signal`
- **Output:** Loaded with defaults `send_email=true, send_signal=false`
- **Side effects:** No behavior change from current

### Toggle enable/disable preserves channels

- **Input:** User clicks pause/play on a subscription with `send_signal=true`
- **Output:** `enabled` toggled, `send_signal` remains true
- **Side effects:** Channel config not lost

### "Run Now" respects channels

- **Input:** User clicks "Run Now" on a Signal-only subscription
- **Output:** Signal message sent, no email
- **Side effects:** UI notification confirms delivery

## Known Limitations

- SMS is not supported (no SMS output implementation exists — separate Feature F1)
- No validation that at least one channel is selected (user can save with both unchecked)
- Signal messages use plain-text comparison body (no HTML formatting)

## Files to Change

| # | File | Action | Est. LoC |
|---|------|--------|---------|
| 1 | `src/app/user.py` | ADD 2 fields to `CompareSubscription` | ~2 |
| 2 | `src/app/loader.py` | EXTEND serialize + deserialize for new fields | ~4 |
| 3 | `src/web/pages/subscriptions.py` | ADD channel checkboxes, update save/toggle/"Run Now" handlers | ~20 |
| 4 | `src/web/scheduler.py` | REFACTOR `_execute_subscription()` to gate on flags | ~18 |

**Total F12a:** ~44 LoC, 4 files

## Changelog

- 2026-04-04: v1.0 — Initial spec for F12a (Channel-Switch Subscriptions)
