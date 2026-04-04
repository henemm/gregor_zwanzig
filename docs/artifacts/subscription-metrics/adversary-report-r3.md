# Adversary Report — Round 3 (F14a Subscription Metrics)

**Date:** 2026-04-04
**Validator:** Independent QA Agent (Round 3)
**Files examined:**
- `/home/hem/gregor_zwanzig/src/web/pages/subscriptions.py`
- `/home/hem/gregor_zwanzig/src/web/pages/weather_config.py`
- `/home/hem/gregor_zwanzig/src/app/loader.py`
- `/home/hem/gregor_zwanzig/src/app/user.py`
- `/home/hem/gregor_zwanzig/data/users/default/compare_subscriptions.json`

---

## Test Results

```
tests/tdd/test_subscription_metrics.py       9 passed
tests/tdd/test_channel_switch_subscription.py 9 passed
tests/test_loader.py                          9 passed
Total: 27 passed in 0.50s
```

All 27 tests green.

---

## VALIDATION: Fix 1 (R1 Bug — display_config lost on Edit-Save)

PASSED: Fix 1 correctly implemented
   File: src/web/pages/subscriptions.py, lines 426-430
   Code:
     if not is_new:
         current_subs = load_compare_subscriptions()
         current = next((s for s in current_subs if s.id == sub_id), None)
         if current and current.display_config:
             new_sub.display_config = current.display_config
   
   The fix reads display_config from disk at save time, not from the closed-over
   'sub' object. For the Edit-Save path (is_new=False), the display_config is
   always fetched fresh from disk and preserved correctly.

---

## VALIDATION: Fix 2 (R2 Bug — Stale Closure in Metrics Config Dialog)

PASSED: Fix 2 correctly implemented
   File: src/web/pages/weather_config.py, lines 677-707
   Function: make_subscription_save_handler()
   
   1. Dialog open: show_subscription_weather_config_dialog() reloads subscription
      from disk (lines 600-601) before building the UI.
   2. Save handler: load_compare_subscriptions() is called fresh inside do_save()
      before writing. The target subscription is always loaded from disk, not from
      the stale closure.
   3. The factory pattern (make_subscription_save_handler) only closes over the
      immutable sub_id string, not the mutable subscription object.

---

## NEW BUG FOUND: Stale Closure in Toggle Handler

FAILED: Range/State compatibility — Toggle handler destroys display_config
   
   File: src/web/pages/subscriptions.py, lines 163-183
   Function: make_toggle_handler(subscription)
   
   Problem:
     The toggle handler (Enable/Disable button) constructs a new CompareSubscription
     with ALL fields copied from the 'subscription' parameter — which is the object
     captured when the subscription card was RENDERED, not from disk.
   
     Specifically, line 179:
       display_config=subscription.display_config,
     
     If the user:
       1. Opens the Wetter-Metriken dialog
       2. Saves metric configuration (display_config is now on disk)
       3. WITHOUT reloading the page, clicks Toggle (Enable/Disable)
     
     Then do_toggle() executes with subscription.display_config=None (the stale
     closure value from before metrics were configured). The new subscription is
     saved with display_config=None, overwriting the metric configuration on disk.
   
   Cause:
     make_toggle_handler() was NOT updated with the same "read from disk" fix
     that was applied to make_save_handler(). The R2 fix was incomplete — it
     fixed the Edit dialog save path and the Metrics dialog save path, but the
     toggle action still uses the stale closure.
   
   Proof (automated test):
     Saving a subscription with display_config set, then saving again with
     display_config=None via the toggle pattern results in display_config=None
     on disk. Confirmed by simulation (see test output during validation).
   
   Fix Required:
     Option A (minimal): In do_toggle(), read the current subscription from disk
     before saving:
       def do_toggle() -> None:
           current_subs = load_compare_subscriptions()
           current = next((s for s in current_subs if s.id == subscription.id), None)
           if current is None:
               return
           updated = CompareSubscription(
               id=current.id,
               name=current.name,
               enabled=not current.enabled,
               locations=current.locations,
               forecast_hours=current.forecast_hours,
               time_window_start=current.time_window_start,
               time_window_end=current.time_window_end,
               schedule=current.schedule,
               weekday=current.weekday,
               include_hourly=current.include_hourly,
               top_n=current.top_n,
               send_email=current.send_email,
               send_signal=current.send_signal,
               display_config=current.display_config,  # FRESH FROM DISK
           )
           save_compare_subscription(updated)
           refresh_fn.refresh()
     
     Option B (cleaner): Only update the 'enabled' field in the existing saved
     subscription (partial update), avoiding full reconstruction from stale data.

---

## Other Observations (Non-blocking)

WARNING: display_config serialization for subscriptions is incomplete
   File: src/app/loader.py, function save_compare_subscriptions(), lines 752-768
   
   The subscription's display_config is serialized with only 3 keys:
   trip_id, metrics, updated_at.
   
   UnifiedWeatherDisplayConfig has additional fields (show_compact_summary,
   show_night_block, night_interval_hours, thunder_forecast_days,
   multi_day_trend_reports, sms_metrics) that are NOT serialized for subscriptions.
   
   Impact: Currently LOW. run_comparison_for_subscription() does not read
   display_config for rendering. Only the Wetter-Metriken dialog uses these fields,
   and it always starts from the defaults if not stored. But if any renderer is
   extended to use show_compact_summary for subscriptions in the future, the values
   will silently revert to defaults on every save.
   
   Recommendation: Either serialize all fields (align with save_location), or
   document explicitly that subscriptions only support the 'metrics' subfield of
   UnifiedWeatherDisplayConfig.

PASSED: No crash on empty subscriptions file
   If load_compare_subscriptions() returns [] (file deleted/corrupted), the
   do_save() fix at lines 426-430 handles it gracefully: current=None, condition
   is False, new_sub.display_config stays None. No crash.

PASSED: ID stability for Edit dialog
   make_edit_handler captures subscription.id which is fixed at creation.
   CompareSubscription is not frozen but the id field is never reassigned. The
   dialog save uses sub.id (original) as the lookup key, consistent behavior.

PASSED: Legacy JSON migration (missing send_email/send_signal)
   The JSON file on disk is missing send_email and send_signal fields (legacy
   data predates these fields). loader.py uses .get("send_email", True) and
   .get("send_signal", False) as defaults. Fields are written on next save.
   Correct migration-on-save behavior.

PASSED: NiceGUI single-threaded safety
   No concurrency issues. NiceGUI is single-threaded. Async operations use
   run_in_executor correctly and don't race with the toggle handler.

---

## Screenshots

- 06-r3-final.png: Subscriptions page loaded correctly (1 subscription visible)
- 07-r3-dialog.png: Wetter-Metriken dialog opens with saved metric state

---

## Verdict

NOT VERIFIED — New bug found in Round 3.

Fix 1 and Fix 2 are correctly implemented. However, the stale-closure bug that
was fixed for the Edit-Save path (Fix 2) was not applied consistently to the
Toggle handler. The toggle button can destroy display_config without the user
being aware of it, using the same mechanism as the R2 bug.

The two R1/R2 fixes are complete and correct in isolation. The toggle handler
is a third instance of the same pattern that was missed.

---

## Test Plan for Round 4

### Automated Tests
1. [ ] Unit test: Toggle after metrics save — verify display_config preserved
2. [ ] Unit test: Toggle on subscription with display_config=None — no crash
3. [ ] Unit test: Toggle on subscription not found on disk — graceful handling

### Manual / E2E Tests
4. [ ] Configure Wetter-Metriken for subscription (save metrics dialog)
5. [ ] WITHOUT reloading, click Toggle (Enable/Disable)
6. [ ] Verify Wetter-Metriken dialog still shows saved metrics after toggle
7. [ ] Repeat step 5-6 multiple times without page reload
